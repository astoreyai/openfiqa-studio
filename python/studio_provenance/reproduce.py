"""Reproduction mode (P09 P11–P13).

Take a frozen publication manifest, rerun the workflow it names, compare, and return a verdict:

    EXACT | WITHIN_TOLERANCE | DIFFERENT | MISSING_DEPENDENCY | MISSING_DATA | BLOCKED

**The reference is never altered to agree with a rerun.** That rule is the whole point. A
reproduction system that quietly updates the published value when it disagrees reports success
every time and detects nothing — it measures its own willingness to overwrite, not reproducibility.

`BLOCKED` is a first-class outcome, not an error. One engine's source is not publicly released
(B-P01-08), so a third party genuinely cannot rerun that leg, and the honest report says so rather
than failing obscurely or silently dropping the stage.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from studio_workflow.executor import WorkflowExecutor, workflow_digest
from studio_workflow.graph import Workflow

Verdict = str
EXACT = "EXACT"
WITHIN_TOLERANCE = "WITHIN_TOLERANCE"
DIFFERENT = "DIFFERENT"
MISSING_DEPENDENCY = "MISSING_DEPENDENCY"
MISSING_DATA = "MISSING_DATA"
BLOCKED = "BLOCKED"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class PublicationManifest:
    """A frozen result. Once written it is read-only as far as reproduction is concerned."""

    title: str
    workflow_name: str
    workflow_sha256: str
    workflow_yaml: str
    frozen_at: str
    node_outputs: dict[str, list[str]]
    node_statuses: dict[str, str]
    blocked_nodes: dict[str, str] = field(default_factory=dict)
    environment: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "workflow_name": self.workflow_name,
            "workflow_sha256": self.workflow_sha256,
            "workflow_yaml": self.workflow_yaml,
            "frozen_at": self.frozen_at,
            "node_outputs": self.node_outputs,
            "node_statuses": self.node_statuses,
            "blocked_nodes": self.blocked_nodes,
            "environment": self.environment,
        }

    def write(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2))
        return path

    @classmethod
    def read(cls, path: Path) -> "PublicationManifest":
        data = json.loads(Path(path).read_text())
        return cls(**data)


def freeze(
    title: str, workflow: Workflow, run_manifest: dict[str, Any], *, environment: dict[str, Any]
) -> PublicationManifest:
    """Capture everything needed to re-derive a result.

    The workflow YAML is embedded rather than referenced by path: a manifest that points at a file
    somewhere else is not reproducible by anyone who does not already have that file.
    """
    return PublicationManifest(
        title=title,
        workflow_name=workflow.name,
        workflow_sha256=workflow_digest(workflow),
        workflow_yaml=workflow.to_yaml(),
        frozen_at=_now(),
        node_outputs={n["node_id"]: list(n.get("outputs", [])) for n in run_manifest["nodes"]},
        node_statuses={n["node_id"]: n["status"] for n in run_manifest["nodes"]},
        blocked_nodes={
            n["node_id"]: n["blocker_id"]
            for n in run_manifest["nodes"]
            if n["status"] == "blocked" and n.get("blocker_id")
        },
        environment=environment,
    )


@dataclass
class NodeComparison:
    node_id: str
    verdict: Verdict
    reference_outputs: int
    rerun_outputs: int
    detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "verdict": self.verdict,
            "reference_outputs": self.reference_outputs,
            "rerun_outputs": self.rerun_outputs,
            "detail": self.detail,
        }


@dataclass
class ReproductionReport:
    title: str
    workflow_sha256_reference: str
    workflow_sha256_rerun: str
    verdict: Verdict
    nodes: list[NodeComparison]
    reproduced_at: str
    reference_mutated: bool = False  # always False; asserted in the report for the reader

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "workflow_sha256_reference": self.workflow_sha256_reference,
            "workflow_sha256_rerun": self.workflow_sha256_rerun,
            "verdict": self.verdict,
            "nodes": [n.to_dict() for n in self.nodes],
            "reproduced_at": self.reproduced_at,
            "reference_mutated": self.reference_mutated,
        }

    def to_markdown(self) -> str:
        lines = [
            f"# Reproduction report — {self.title}",
            "",
            f"**Verdict:** {self.verdict}",
            "",
            f"- reference workflow sha256: `{self.workflow_sha256_reference}`",
            f"- rerun workflow sha256: `{self.workflow_sha256_rerun}`",
            f"- reproduced at: {self.reproduced_at}",
            "- reference values were not modified at any point",
            "",
            "| node | verdict | reference | rerun | detail |",
            "|---|---|---|---|---|",
        ]
        for node in self.nodes:
            lines.append(
                f"| `{node.node_id}` | {node.verdict} | {node.reference_outputs} | "
                f"{node.rerun_outputs} | {node.detail or ''} |"
            )
        return "\n".join(lines) + "\n"


def reproduce(
    manifest: PublicationManifest, workdir: Path, *, tolerance: float = 0.0
) -> ReproductionReport:
    """Rerun the frozen workflow and compare. Nothing in `manifest` is written to."""
    workflow = Workflow.from_yaml(manifest.workflow_yaml)
    rerun_digest = workflow_digest(workflow)

    rerun = WorkflowExecutor(Path(workdir)).run(workflow).to_dict()
    rerun_by_id = {n["node_id"]: n for n in rerun["nodes"]}

    comparisons: list[NodeComparison] = []
    for node_id, reference_outputs in manifest.node_outputs.items():
        reference_status = manifest.node_statuses.get(node_id)
        rerun_node = rerun_by_id.get(node_id)

        if rerun_node is None:
            comparisons.append(
                NodeComparison(node_id, MISSING_DEPENDENCY, len(reference_outputs), 0,
                               "node absent from the rerun")
            )
            continue

        if reference_status == "blocked":
            blocker = manifest.blocked_nodes.get(node_id, "unknown blocker")
            comparisons.append(
                NodeComparison(node_id, BLOCKED, len(reference_outputs),
                               len(rerun_node["outputs"]),
                               f"blocked in the reference by {blocker}")
            )
            continue

        rerun_outputs = list(rerun_node["outputs"])
        if rerun_outputs == list(reference_outputs):
            verdict, detail = EXACT, None
        elif len(rerun_outputs) != len(reference_outputs):
            verdict = MISSING_DATA
            detail = (
                f"output count differs: reference {len(reference_outputs)}, "
                f"rerun {len(rerun_outputs)}"
            )
        else:
            overlap = len(set(rerun_outputs) & set(reference_outputs))
            fraction = overlap / len(reference_outputs) if reference_outputs else 0.0
            if tolerance and (1.0 - fraction) <= tolerance:
                verdict = WITHIN_TOLERANCE
                detail = f"{overlap}/{len(reference_outputs)} identical, within tolerance"
            else:
                verdict = DIFFERENT
                detail = f"only {overlap}/{len(reference_outputs)} outputs identical"
        comparisons.append(
            NodeComparison(node_id, verdict, len(reference_outputs), len(rerun_outputs), detail)
        )

    verdicts = {c.verdict for c in comparisons}
    if manifest.workflow_sha256 != rerun_digest:
        overall = DIFFERENT
    elif verdicts <= {EXACT, BLOCKED}:
        # A run whose only non-EXACT nodes were blocked in the reference too is as reproduced as it
        # can be; the blocked stages are reported rather than counted as agreement.
        overall = EXACT if BLOCKED not in verdicts else BLOCKED
    elif DIFFERENT in verdicts:
        overall = DIFFERENT
    elif MISSING_DATA in verdicts:
        overall = MISSING_DATA
    elif MISSING_DEPENDENCY in verdicts:
        overall = MISSING_DEPENDENCY
    else:
        overall = WITHIN_TOLERANCE

    return ReproductionReport(
        title=manifest.title,
        workflow_sha256_reference=manifest.workflow_sha256,
        workflow_sha256_rerun=rerun_digest,
        verdict=overall,
        nodes=comparisons,
        reproduced_at=_now(),
    )
