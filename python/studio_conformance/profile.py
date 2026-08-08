"""Conformance profile schema (P10 T01–T03).

A profile is a version-pinned list of requirements, each bound to a test and an expected result.

**Provenance of a requirement is mandatory.** Every requirement declares where its text came from,
and `source` is a closed enum. There is no way to write a requirement that merely *sounds* like a
standard: a profile claiming `iso-29794-5` authority must cite a clause, and a profile derived from
watching an implementation must say so. Encoding a plausible-sounding requirement as though it were
normative is the failure mode that would make this whole layer worse than useless — a conformance
report is only worth the weakest citation in it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml

Severity = Literal["critical", "major", "minor", "informational"]
SEVERITIES = ("critical", "major", "minor", "informational")

# Where a requirement's text came from. Closed on purpose.
RequirementSource = Literal["normative_document", "implementation_derived", "local_policy"]
SOURCES = ("normative_document", "implementation_derived", "local_policy")


class ProfileError(ValueError):
    """The profile is not usable as written."""


@dataclass
class Requirement:
    requirement_id: str
    description: str
    test_id: str
    severity: Severity
    source: RequirementSource
    citation: str
    expected: Any = None
    applies_when: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "requirement_id": self.requirement_id,
            "description": self.description,
            "test_id": self.test_id,
            "severity": self.severity,
            "source": self.source,
            "citation": self.citation,
            "expected": self.expected,
            "applies_when": self.applies_when,
        }


@dataclass
class Profile:
    profile_id: str
    title: str
    authority: str
    version: str
    effective_date: str
    requirements: list[Requirement]
    # True only when `authority` names an external standards body AND every requirement cites it.
    normative: bool = False
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "title": self.title,
            "authority": self.authority,
            "version": self.version,
            "effective_date": self.effective_date,
            "normative": self.normative,
            "notes": self.notes,
            "requirements": [r.to_dict() for r in self.requirements],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Profile":
        for key in ("profile_id", "title", "authority", "version", "effective_date"):
            if not data.get(key):
                raise ProfileError(f"profile is missing {key!r}; profiles must be version-pinned")

        requirements = []
        for raw in data.get("requirements", []):
            for key in ("requirement_id", "description", "test_id", "severity", "source",
                        "citation"):
                if not raw.get(key):
                    raise ProfileError(
                        f"requirement {raw.get('requirement_id', '?')} is missing {key!r}"
                    )
            if raw["severity"] not in SEVERITIES:
                raise ProfileError(f"unknown severity {raw['severity']!r}; expected {SEVERITIES}")
            if raw["source"] not in SOURCES:
                raise ProfileError(f"unknown source {raw['source']!r}; expected {SOURCES}")
            requirements.append(
                Requirement(
                    requirement_id=raw["requirement_id"],
                    description=raw["description"],
                    test_id=raw["test_id"],
                    severity=raw["severity"],
                    source=raw["source"],
                    citation=raw["citation"],
                    expected=raw.get("expected"),
                    applies_when=raw.get("applies_when", {}) or {},
                )
            )

        profile = cls(
            profile_id=data["profile_id"],
            title=data["title"],
            authority=data["authority"],
            version=data["version"],
            effective_date=data["effective_date"],
            requirements=requirements,
            normative=bool(data.get("normative", False)),
            notes=data.get("notes"),
        )
        profile._check_normative_claim()
        return profile

    def _check_normative_claim(self) -> None:
        """A profile may only call itself normative if every requirement cites a document.

        Without this, `normative: true` is a one-line assertion that turns observations into
        apparent standard compliance.
        """
        if not self.normative:
            return
        offenders = [
            r.requirement_id for r in self.requirements if r.source != "normative_document"
        ]
        if offenders:
            raise ProfileError(
                f"profile {self.profile_id} claims to be normative but these requirements are not "
                f"sourced from a normative document: {offenders}"
            )

    @classmethod
    def read(cls, path: str | Path) -> "Profile":
        return cls.from_dict(yaml.safe_load(Path(path).read_text()))

    def requirement(self, requirement_id: str) -> Requirement | None:
        return next((r for r in self.requirements if r.requirement_id == requirement_id), None)

    def by_severity(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for requirement in self.requirements:
            counts[requirement.severity] = counts.get(requirement.severity, 0) + 1
        return counts


def load_profiles(directory: str | Path) -> dict[str, Profile]:
    """Load every profile in a directory (T02, the standards registry)."""
    profiles: dict[str, Profile] = {}
    for path in sorted(Path(directory).glob("*.yaml")):
        profile = Profile.read(path)
        profiles[profile.profile_id] = profile
    return profiles
