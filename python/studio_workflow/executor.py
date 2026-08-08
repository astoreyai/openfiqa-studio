"""Workflow execution (P06 W07, W12, W14).

Executes a compiled plan and writes a run manifest. The manifest is the point: it records the
workflow hash, every node's parameters, every artifact hash, and the engine provenance, so the
same workflow run twice can be compared rather than trusted.

Node kinds that are not implemented are reported as `BLOCKED` with the blocker id. They are never
skipped silently — a workflow that quietly drops its scoring stage would still produce a manifest,
and the manifest would look complete.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from studio_adapters.registry import get_adapter
from studio_data.dataset import DatasetManifest
from studio_transforms import operators as ops
from studio_workflow.graph import CompiledNode, Workflow, compile_workflow

BLOCKED_KINDS = {
    "feature_table": "B-P01-01",
    "scorer": "B-P01-02",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class NodeResult:
    node_id: str
    kind: str
    status: str  # completed | failed | blocked
    parameters: dict[str, Any]
    outputs: list[str] = field(default_factory=list)
    detail: str | None = None
    blocker_id: str | None = None
    # Carried into the manifest so provenance edges can be rebuilt from the manifest alone,
    # without needing the original workflow file.
    upstream: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "kind": self.kind,
            "status": self.status,
            "parameters": self.parameters,
            "outputs": self.outputs,
            "detail": self.detail,
            "blocker_id": self.blocker_id,
            "upstream": self.upstream,
        }


@dataclass
class RunManifest:
    workflow_name: str
    workflow_sha256: str
    started_at: str
    finished_at: str | None
    nodes: list[NodeResult]
    artifacts: dict[str, Any] = field(default_factory=dict)

    @property
    def status(self) -> str:
        if any(n.status == "failed" for n in self.nodes):
            return "failed"
        if any(n.status == "blocked" for n in self.nodes):
            return "partial"
        return "completed"

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_name": self.workflow_name,
            "workflow_sha256": self.workflow_sha256,
            "status": self.status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "nodes": [n.to_dict() for n in self.nodes],
            "artifacts": self.artifacts,
        }


def workflow_digest(workflow: Workflow) -> str:
    """Hash the canonical form, so formatting changes do not change the identity of a workflow."""
    canonical = json.dumps(workflow.to_dict(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


class WorkflowExecutor:
    def __init__(self, workdir: Path):
        self.workdir = Path(workdir)
        self.workdir.mkdir(parents=True, exist_ok=True)

    def run(self, workflow: Workflow, *, limit_samples: int | None = None) -> RunManifest:
        plan = compile_workflow(workflow)
        manifest = RunManifest(
            workflow_name=workflow.name,
            workflow_sha256=workflow_digest(workflow),
            started_at=_now(),
            finished_at=None,
            nodes=[],
        )

        # node id -> the images or vectors it produced
        images: dict[str, list[Path]] = {}
        vectors: dict[str, list[dict[str, Any]]] = {}

        for node in plan:
            try:
                result = self._execute(node, images, vectors, limit_samples)
            except Exception as exc:  # noqa: BLE001 - a node failure is a result, not a crash
                result = NodeResult(
                    node_id=node.id, kind=node.kind, status="failed",
                    parameters=node.parameters, detail=f"{type(exc).__name__}: {exc}",
                )
            result.upstream = list(node.upstream)
            manifest.nodes.append(result)

        manifest.finished_at = _now()
        manifest.artifacts = {
            "quality_vectors": sum(len(v) for v in vectors.values()),
            "images_written": sum(len(v) for v in images.values()),
        }
        return manifest

    # ------------------------------------------------------------------ node kinds

    def _execute(
        self,
        node: CompiledNode,
        images: dict[str, list[Path]],
        vectors: dict[str, list[dict[str, Any]]],
        limit_samples: int | None,
    ) -> NodeResult:
        if node.kind in BLOCKED_KINDS:
            blocker = BLOCKED_KINDS[node.kind]
            return NodeResult(
                node_id=node.id, kind=node.kind, status="blocked",
                parameters=node.parameters, blocker_id=blocker,
                detail=(
                    f"{node.kind} nodes are blocked by {blocker}; the workflow ran every other "
                    f"branch and this stage produced nothing"
                ),
            )

        if node.kind == "dataset":
            return self._dataset(node, images, limit_samples)
        if node.kind == "transform":
            return self._transform(node, images)
        if node.kind == "engine":
            return self._engine(node, images, vectors)
        if node.kind == "artifact":
            return self._artifact(node, vectors)

        return NodeResult(
            node_id=node.id, kind=node.kind, status="failed",
            parameters=node.parameters, detail=f"no executor for kind {node.kind!r}",
        )

    def _dataset(
        self, node: CompiledNode, images: dict[str, list[Path]], limit_samples: int | None
    ) -> NodeResult:
        root = Path(node.parameters["root"])
        limit = node.parameters.get("limit", limit_samples)
        manifest = DatasetManifest.from_directory(
            root,
            name=node.id,
            classification=node.parameters.get("classification", "PUBLIC"),
            authorization=node.parameters.get("authorization"),
            limit=limit,
        )
        images[node.id] = [Path(s.path) for s in manifest.samples]
        return NodeResult(
            node_id=node.id, kind=node.kind, status="completed",
            parameters=node.parameters,
            outputs=[s.sha256 for s in manifest.samples],
            detail=f"{len(manifest)} samples, {len(manifest.subjects)} subjects",
        )

    def _transform(self, node: CompiledNode, images: dict[str, list[Path]]) -> NodeResult:
        sources = [p for parent in node.upstream for p in images.get(parent, [])]
        if not sources:
            return NodeResult(
                node_id=node.id, kind=node.kind, status="failed",
                parameters=node.parameters, detail="no upstream images",
            )
        operator = node.parameters["operator"]
        parameters = {k: v for k, v in node.parameters.items() if k != "operator"}

        out_dir = self.workdir / node.id.replace("/", "_")
        out_dir.mkdir(parents=True, exist_ok=True)

        written, hashes = [], []
        for source in sources:
            image = ops.load(source)
            output, record = ops.apply(operator, image, parameters=parameters)
            destination = out_dir / f"{source.stem}.png"
            output.save(destination)
            written.append(destination)
            hashes.append(record.output_sha256)

        images[node.id] = written
        return NodeResult(
            node_id=node.id, kind=node.kind, status="completed",
            parameters=node.parameters, outputs=hashes,
            detail=f"{operator} applied to {len(written)} images",
        )

    def _engine(
        self,
        node: CompiledNode,
        images: dict[str, list[Path]],
        vectors: dict[str, list[dict[str, Any]]],
    ) -> NodeResult:
        plugin_id = node.parameters["plugin_id"]
        adapter = get_adapter(plugin_id)
        if adapter is None:
            return NodeResult(
                node_id=node.id, kind=node.kind, status="blocked",
                parameters=node.parameters, blocker_id=None,
                detail=f"no adapter is implemented for {plugin_id}",
            )
        ok, reason = adapter.available()
        if not ok:
            return NodeResult(
                node_id=node.id, kind=node.kind, status="blocked",
                parameters=node.parameters, detail=reason,
            )

        sources = [p for parent in node.upstream for p in images.get(parent, [])]
        produced = []
        for source in sources:
            produced.append(adapter.run(source).typed)
        vectors[node.id] = produced
        return NodeResult(
            node_id=node.id, kind=node.kind, status="completed",
            parameters=node.parameters,
            outputs=[v["sample_id"] for v in produced],
            detail=f"{plugin_id} assessed {len(produced)} samples",
        )

    def _artifact(
        self, node: CompiledNode, vectors: dict[str, list[dict[str, Any]]]
    ) -> NodeResult:
        collected = [v for parent in node.upstream for v in vectors.get(parent, [])]
        destination = self.workdir / f"{node.id.replace('/', '_')}.json"
        payload = {"node": node.id, "count": len(collected), "quality_vectors": collected}
        destination.write_text(json.dumps(payload, indent=2))
        digest = hashlib.sha256(destination.read_bytes()).hexdigest()
        return NodeResult(
            node_id=node.id, kind=node.kind, status="completed",
            parameters=node.parameters, outputs=[digest],
            detail=f"wrote {destination.name} ({len(collected)} vectors)",
        )
