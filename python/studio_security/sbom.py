"""Software bill of materials (P11 S06, S07).

Generated from what is actually installed, not from a declared dependency list. A lockfile says
what should be present; an SBOM built by reading the environment says what is. When they disagree
— a transitive pin resolved differently, a package installed by hand — the difference is the
supply-chain fact worth knowing.

Every entry carries the distribution's own recorded metadata. Fields that cannot be determined are
null rather than guessed, for the same reason the capability inventory leaves nulls: a plausible
wrong licence in an SBOM is worse than an admitted gap.
"""

from __future__ import annotations

import json
import platform
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]


@dataclass
class Component:
    name: str
    version: str
    ecosystem: str
    license: str | None = None
    location: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "ecosystem": self.ecosystem,
            "license": self.license,
            "location": self.location,
        }


@dataclass
class SBOM:
    generated_at: str | None
    platform: dict[str, Any]
    components: list[Component] = field(default_factory=list)
    external_engines: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": "openfiqa-studio-sbom/1",
            "generated_at": self.generated_at,
            "platform": self.platform,
            "component_count": len(self.components),
            "components": [c.to_dict() for c in self.components],
            # Engines are NOT pip dependencies. They are separate repositories with their own
            # licences, and one supplies BSI-licensed weights to an MIT package (B-P01-09). An SBOM
            # that listed only pip packages would miss the licensing question entirely.
            "external_engines": self.external_engines,
        }

    def write(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2))
        return path


def _license_of(distribution: Any) -> str | None:
    """Read the licence the distribution itself declares.

    Three sources, in the order of precision the packaging ecosystem actually uses:

    1. ``License-Expression`` — PEP 639, an SPDX expression. Modern wheels use only this, and a
       reader checking just the legacy ``License`` field reports None for them. pytest 9.1.1 is
       one such package, which is how this gap was found.
    2. ``License`` — the legacy free-text field.
    3. A ``License ::`` trove classifier, the coarsest of the three.
    """
    metadata = distribution.metadata

    expression = metadata.get("License-Expression")
    if expression and expression.strip():
        return expression.strip()[:120]

    declared = metadata.get("License")
    if declared and declared not in {"UNKNOWN", ""}:
        return declared.splitlines()[0][:120]

    for classifier in metadata.get_all("Classifier") or []:
        if classifier.startswith("License ::"):
            return classifier.split("::")[-1].strip()
    return None


def python_components() -> list[Component]:
    import importlib.metadata as md

    components = []
    for distribution in md.distributions():
        name = distribution.metadata.get("Name")
        if not name:
            continue
        components.append(
            Component(
                name=name,
                version=distribution.version or "unknown",
                ecosystem="pypi",
                license=_license_of(distribution),
                location=str(getattr(distribution, "_path", "")) or None,
            )
        )
    return sorted(components, key=lambda c: c.name.lower())


def node_components(lockfile: Path | None = None) -> list[Component]:
    """Read pnpm's lockfile. Returns an empty list when it is absent rather than inventing entries."""
    lockfile = lockfile or REPO / "pnpm-lock.yaml"
    if not lockfile.exists():
        return []
    try:
        import yaml

        data = yaml.safe_load(lockfile.read_text()) or {}
    except Exception:
        return []

    components: list[Component] = []
    for key in (data.get("packages") or {}):
        # keys look like  /name@version  or  name@version
        raw = key.lstrip("/")
        if "@" not in raw:
            continue
        name, _, version = raw.rpartition("@")
        if not name:
            continue
        components.append(Component(name=name, version=version, ecosystem="npm"))
    return sorted(components, key=lambda c: c.name.lower())


def external_engines() -> list[dict[str, Any]]:
    """Engines and the repositories that supply their weights."""
    from studio_adapters import paths
    from studio_adapters.base import git_commit

    engines = []
    for key, name, license_ in (
        ("ofiqpy_root", "ofiqpy", "MIT (code) — weights are BSI-licensed and come from OFIQ-Project"),
        ("ofiq_project_root", "OFIQ-Project", "BSI terms"),
    ):
        root = paths.get(key, required=False)
        engines.append({
            "name": name,
            "present": bool(root and root.exists()),
            "commit": git_commit(root) if root and root.exists() else None,
            "license": license_,
            "ecosystem": "git",
        })
    return engines


def generate(*, timestamp: str | None = None) -> SBOM:
    return SBOM(
        generated_at=timestamp,
        platform={
            "python": sys.version.split()[0],
            "implementation": platform.python_implementation(),
            "system": platform.system(),
            "machine": platform.machine(),
        },
        components=python_components() + node_components(),
        external_engines=external_engines(),
    )


def git_tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(REPO), "ls-files"], capture_output=True, text=True, timeout=60
    )
    return result.stdout.splitlines() if result.returncode == 0 else []
