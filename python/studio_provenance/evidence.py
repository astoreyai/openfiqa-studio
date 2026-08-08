"""Evidence package export (P09 P13, P10 T10).

Bundles everything a third party needs to check a result: the frozen workflow, the run manifest,
provenance, engine and environment locks, the conformance report, the reproduction report, and a
README that states what the package does *not* establish.

Two refusals are the point of this module.

**Restricted material is refused, not filtered.** A package containing a `RESTRICTED` sample is
not silently trimmed and shipped — export fails and names the offenders. Trimming would produce a
package that looks complete and quietly describes a different dataset.

**Open blockers travel with the package.** A recipient reading a conformance report with 8 passes
should see, in the same directory, that two engines could not run and one produced degenerate
output. Evidence that omits its own caveats is advocacy.
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class ExportRefused(RuntimeError):
    """The package would have contained material that must not leave the machine."""


@dataclass
class PackageContents:
    title: str
    workflow_yaml: str | None = None
    publication_manifest: dict[str, Any] | None = None
    run_manifest: dict[str, Any] | None = None
    reproduction_report: dict[str, Any] | None = None
    reproduction_markdown: str | None = None
    conformance_report: dict[str, Any] | None = None
    conformance_markdown: str | None = None
    sbom: dict[str, Any] | None = None
    engine_locks: dict[str, Any] | None = None
    dataset_manifest: dict[str, Any] | None = None
    golden_vector_checks: list[dict[str, Any]] = field(default_factory=list)
    open_blockers: str | None = None
    extra_notes: str | None = None


def _classification_offenders(dataset_manifest: dict[str, Any] | None) -> list[str]:
    if not dataset_manifest:
        return []
    return [
        sample["path"]
        for sample in dataset_manifest.get("samples", [])
        if sample.get("classification") != "PUBLIC"
    ]


def _looks_like_image(name: str) -> bool:
    return Path(name).suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}


def build_readme(contents: PackageContents, manifest_index: dict[str, str]) -> str:
    lines = [
        f"# Evidence package — {contents.title}",
        "",
        "This package contains everything needed to re-derive and check the result it describes.",
        "",
        "## What this package establishes",
        "",
        "- what was run, on which inputs, with which engine at which commit",
        "- whether a rerun reproduced it, and where it did not",
        "- which conformance requirements passed, failed, or were not tested",
        "",
        "## What it does NOT establish",
        "",
        "- **Conformance to any published specification.** The conformance profile included here "
        "is non-normative: its requirements were derived from observed implementation behaviour, "
        "not from a standards document.",
        "- **That a quality score predicts recognition failure.** No matcher was available, so no "
        "error-versus-reject or ROC analysis exists (blocker B-P04-08).",
        "- **Independent verification.** Nobody outside the producing repository has reviewed "
        "this.",
        "",
        "## Contents",
        "",
        "| file | sha256 |",
        "|---|---|",
    ]
    for name, digest in sorted(manifest_index.items()):
        lines.append(f"| `{name}` | `{digest[:16]}…` |")
    lines += [
        "",
        "## Open blockers",
        "",
        "`blockers.md` in this package lists every condition still open against the work it "
        "describes. Read it before quoting any number here: evidence that omits its own caveats "
        "is advocacy.",
    ]
    if contents.extra_notes:
        lines += ["", "## Notes", "", contents.extra_notes]
    return "\n".join(lines) + "\n"


def export(
    contents: PackageContents,
    destination: Path,
    *,
    allow_restricted: bool = False,
) -> Path:
    """Write a zip evidence package. Refuses rather than trims."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)

    offenders = _classification_offenders(contents.dataset_manifest)
    if offenders and not allow_restricted:
        raise ExportRefused(
            f"{len(offenders)} sample(s) are not classified PUBLIC and would be described by this "
            f"package: {offenders[:3]}{'...' if len(offenders) > 3 else ''}. "
            f"Export refused. Pass allow_restricted=True only if the recipient is authorised for "
            f"this material — the package is NOT trimmed, because a trimmed package looks complete "
            f"while describing a different dataset."
        )

    files: dict[str, str] = {}

    def add(name: str, payload: Any) -> None:
        if payload is None:
            return
        files[name] = payload if isinstance(payload, str) else json.dumps(payload, indent=2)

    add("workflow.yaml", contents.workflow_yaml)
    add("publication_manifest.json", contents.publication_manifest)
    add("run_manifest.json", contents.run_manifest)
    add("reproduction_report.json", contents.reproduction_report)
    add("reproduction_report.md", contents.reproduction_markdown)
    add("conformance_report.json", contents.conformance_report)
    add("conformance_report.md", contents.conformance_markdown)
    add("sbom.json", contents.sbom)
    add("engine_lock.json", contents.engine_locks)
    add("dataset_manifest.json", contents.dataset_manifest)
    add("blockers.md", contents.open_blockers)
    if contents.golden_vector_checks:
        add("golden_vector_checks.json", contents.golden_vector_checks)

    # No image may ever enter a package. Checked by name as a backstop against a future caller
    # adding one through `extra` content.
    images = [name for name in files if _looks_like_image(name)]
    if images:
        raise ExportRefused(f"package would contain image files: {images}")

    index = {
        name: hashlib.sha256(body.encode()).hexdigest() for name, body in files.items()
    }
    files["README.md"] = build_readme(contents, index)
    index["README.md"] = hashlib.sha256(files["README.md"].encode()).hexdigest()
    files["MANIFEST.sha256"] = "\n".join(
        f"{digest}  {name}" for name, digest in sorted(index.items())
    ) + "\n"

    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, body in sorted(files.items()):
            archive.writestr(name, body)
    return destination


def verify(package: Path) -> tuple[bool, list[str]]:
    """Re-hash every member against the package's own MANIFEST.sha256."""
    problems: list[str] = []
    with zipfile.ZipFile(package) as archive:
        names = set(archive.namelist())
        if "MANIFEST.sha256" not in names:
            return False, ["package has no MANIFEST.sha256"]

        recorded: dict[str, str] = {}
        for line in archive.read("MANIFEST.sha256").decode().splitlines():
            if not line.strip():
                continue
            digest, _, name = line.partition("  ")
            recorded[name] = digest

        for name, digest in recorded.items():
            if name not in names:
                problems.append(f"{name} is listed in the manifest but absent from the package")
                continue
            actual = hashlib.sha256(archive.read(name)).hexdigest()
            if actual != digest:
                problems.append(f"{name}: sha256 mismatch")

        for name in names - {"MANIFEST.sha256"} - set(recorded):
            problems.append(f"{name} is in the package but not listed in the manifest")

    return (not problems), problems
