"""Conformance execution and result classification (P10 T05–T07, T10).

Runs a profile's tests against one implementation and returns a verdict per requirement:

    PASS | FAIL | WARNING | NOT_APPLICABLE | BLOCKED | NOT_TESTED

`NOT_TESTED` is the default. A requirement whose test does not exist stays NOT_TESTED — it never
silently becomes PASS, because a conformance report where absence reads as compliance is worse than
no report at all.

The report never says "conformant". It says which requirements passed, against which profile
version, using which implementation. Whether that constitutes conformance is a judgement belonging
to whoever has the authority to make it — which is not this software.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from studio_conformance.profile import Profile, Requirement

PASS = "PASS"
FAIL = "FAIL"
WARNING = "WARNING"
NOT_APPLICABLE = "NOT_APPLICABLE"
BLOCKED = "BLOCKED"
NOT_TESTED = "NOT_TESTED"

VERDICTS = (PASS, FAIL, WARNING, NOT_APPLICABLE, BLOCKED, NOT_TESTED)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class TestOutcome:
    """What a conformance test returned. `evidence` is what a reviewer would need to check it."""

    # Not a pytest test class. The name is right for the domain — a conformance test has an
    # outcome — so tell the collector to leave it alone rather than rename the domain concept.
    __test__ = False

    verdict: str
    detail: str
    evidence: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.verdict not in VERDICTS:
            raise ValueError(f"unknown verdict {self.verdict!r}; expected {VERDICTS}")


@dataclass
class RequirementResult:
    requirement_id: str
    description: str
    severity: str
    source: str
    citation: str
    verdict: str
    detail: str
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "requirement_id": self.requirement_id,
            "description": self.description,
            "severity": self.severity,
            "source": self.source,
            "citation": self.citation,
            "verdict": self.verdict,
            "detail": self.detail,
            "evidence": self.evidence,
        }


@dataclass
class ConformanceReport:
    profile_id: str
    profile_version: str
    profile_authority: str
    profile_normative: bool
    implementation: dict[str, Any]
    executed_at: str
    results: list[RequirementResult]

    @property
    def counts(self) -> dict[str, int]:
        counts = dict.fromkeys(VERDICTS, 0)
        for result in self.results:
            counts[result.verdict] += 1
        return counts

    @property
    def critical_failures(self) -> list[RequirementResult]:
        return [r for r in self.results if r.verdict == FAIL and r.severity == "critical"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "profile_version": self.profile_version,
            "profile_authority": self.profile_authority,
            "profile_normative": self.profile_normative,
            "implementation": self.implementation,
            "executed_at": self.executed_at,
            "counts": self.counts,
            "results": [r.to_dict() for r in self.results],
            "statement": self.statement(),
        }

    def statement(self) -> str:
        """The one sentence a reader will quote. It must not overclaim."""
        counts = self.counts
        scope = (
            "against a normative profile"
            if self.profile_normative
            else "against a NON-NORMATIVE profile derived from observed implementation behaviour"
        )
        return (
            f"{counts[PASS]} of {len(self.results)} requirements passed {scope} "
            f"({self.profile_id} v{self.profile_version}). "
            f"{counts[FAIL]} failed, {counts[BLOCKED]} blocked, {counts[NOT_TESTED]} not tested. "
            f"This is a test result, not a determination of conformance."
        )

    def to_markdown(self) -> str:
        symbol = {
            PASS: "PASS", FAIL: "FAIL", WARNING: "WARN", NOT_APPLICABLE: "N/A",
            BLOCKED: "BLOCKED", NOT_TESTED: "NOT TESTED",
        }
        lines = [
            f"# Conformance report — {self.profile_id} v{self.profile_version}",
            "",
            f"**Authority:** {self.profile_authority}",
            f"**Normative:** {'yes' if self.profile_normative else 'NO — see the caveat below'}",
            f"**Implementation:** {self.implementation.get('plugin_id', 'unknown')} "
            f"{self.implementation.get('version', '')}",
            f"**Executed:** {self.executed_at}",
            "",
            f"> {self.statement()}",
            "",
            "| requirement | severity | verdict | source | detail |",
            "|---|---|---|---|---|",
        ]
        for result in self.results:
            lines.append(
                f"| `{result.requirement_id}` | {result.severity} | "
                f"**{symbol[result.verdict]}** | {result.source} | {result.detail} |"
            )
        if not self.profile_normative:
            lines += [
                "",
                "## Caveat",
                "",
                "This profile is **not normative**. Its requirements were derived from observed "
                "implementation behaviour, not from a standards document. Passing it demonstrates "
                "internal consistency and reproducibility — it does not demonstrate conformance to "
                "ISO/IEC 29794-5, ICAO 9303, DoD EBTS, NATO STANAG 4715, or any other published "
                "specification.",
            ]
        return "\n".join(lines) + "\n"

    def write(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2))
        return path


TestFunction = Callable[[Requirement, dict[str, Any]], TestOutcome]


class ConformanceRunner:
    """Holds the test registry and executes a profile against a context."""

    def __init__(self) -> None:
        self._tests: dict[str, TestFunction] = {}

    def register(self, test_id: str) -> Callable[[TestFunction], TestFunction]:
        def decorator(function: TestFunction) -> TestFunction:
            self._tests[test_id] = function
            return function

        return decorator

    def registered(self) -> list[str]:
        return sorted(self._tests)

    def execute(
        self, profile: Profile, context: dict[str, Any], *, implementation: dict[str, Any]
    ) -> ConformanceReport:
        results: list[RequirementResult] = []

        for requirement in profile.requirements:
            outcome = self._execute_one(requirement, context)
            results.append(
                RequirementResult(
                    requirement_id=requirement.requirement_id,
                    description=requirement.description,
                    severity=requirement.severity,
                    source=requirement.source,
                    citation=requirement.citation,
                    verdict=outcome.verdict,
                    detail=outcome.detail,
                    evidence=outcome.evidence,
                )
            )

        return ConformanceReport(
            profile_id=profile.profile_id,
            profile_version=profile.version,
            profile_authority=profile.authority,
            profile_normative=profile.normative,
            implementation=implementation,
            executed_at=_now(),
            results=results,
        )

    def _execute_one(self, requirement: Requirement, context: dict[str, Any]) -> TestOutcome:
        for key, expected in requirement.applies_when.items():
            if context.get(key) != expected:
                return TestOutcome(
                    NOT_APPLICABLE,
                    f"applies only when {key}={expected!r}; context has {context.get(key)!r}",
                )

        test = self._tests.get(requirement.test_id)
        if test is None:
            # The important default. Absence must never read as compliance.
            return TestOutcome(
                NOT_TESTED, f"no test is implemented for {requirement.test_id!r}"
            )

        try:
            return test(requirement, context)
        except Exception as exc:  # noqa: BLE001 - a broken test is BLOCKED, never PASS
            return TestOutcome(
                BLOCKED, f"test raised {type(exc).__name__}: {exc}"
            )
