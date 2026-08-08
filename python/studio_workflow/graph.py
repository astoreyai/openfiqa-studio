"""Workflow graph: definition, typed validation, and compilation (P06 W02–W06).

A workflow is `nodes + typed edges + parameters`, serialised to YAML. The same definition executes
from the GUI and the CLI — ADR-0009 — so this module is the only place that decides what a
workflow means.

Edges are type-checked before anything runs. Wiring a `QualityVector` into a node expecting a
`FeatureTable` is the mistake that would silently skip the missing feature-engineering stage
(B-P01-01), so it is rejected at validation rather than discovered as a confusing runtime error.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import product
from pathlib import Path
from typing import Any

import yaml

# What each node kind consumes and produces, in the vocabulary of scientific-objects.schema.json.
NODE_PORTS: dict[str, dict[str, list[str]]] = {
    "dataset":       {"inputs": [],                "outputs": ["ImageSample"]},
    "transform":     {"inputs": ["ImageSample"],   "outputs": ["ImageSample"]},
    "engine":        {"inputs": ["ImageSample"],   "outputs": ["QualityVector"]},
    "feature_table": {"inputs": ["QualityVector"], "outputs": ["FeatureTable"]},
    "scorer":        {"inputs": ["FeatureTable"],  "outputs": ["EngineScore"]},
    "artifact":      {"inputs": ["QualityVector", "EngineScore"], "outputs": []},
}


class WorkflowError(ValueError):
    """The workflow is not executable as written."""


@dataclass
class Node:
    id: str
    kind: str
    parameters: dict[str, Any] = field(default_factory=dict)
    # Sweep values expand one node into several at compile time.
    sweep: dict[str, list[Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"id": self.id, "kind": self.kind}
        if self.parameters:
            out["parameters"] = self.parameters
        if self.sweep:
            out["sweep"] = self.sweep
        return out


@dataclass
class Edge:
    source: str
    target: str

    def to_dict(self) -> dict[str, str]:
        return {"source": self.source, "target": self.target}


@dataclass
class Workflow:
    name: str
    nodes: list[Node]
    edges: list[Edge]
    version: int = 1

    # ------------------------------------------------------------------ serialisation

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "name": self.name,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
        }

    def to_yaml(self) -> str:
        return yaml.safe_dump(self.to_dict(), sort_keys=False, default_flow_style=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Workflow":
        if "name" not in data or "nodes" not in data:
            raise WorkflowError("workflow needs at least `name` and `nodes`")
        return cls(
            name=data["name"],
            version=data.get("version", 1),
            nodes=[
                Node(
                    id=n["id"],
                    kind=n["kind"],
                    parameters=n.get("parameters", {}) or {},
                    sweep=n.get("sweep", {}) or {},
                )
                for n in data["nodes"]
            ],
            edges=[Edge(source=e["source"], target=e["target"]) for e in data.get("edges", [])],
        )

    @classmethod
    def from_yaml(cls, text: str) -> "Workflow":
        loaded = yaml.safe_load(text)
        if not isinstance(loaded, dict):
            raise WorkflowError("workflow YAML must be a mapping")
        return cls.from_dict(loaded)

    @classmethod
    def read(cls, path: str | Path) -> "Workflow":
        return cls.from_yaml(Path(path).read_text())

    # ------------------------------------------------------------------ validation

    def validate(self) -> list[str]:
        """Return every problem found. An empty list means the workflow is executable."""
        problems: list[str] = []
        by_id = {n.id: n for n in self.nodes}

        if len(by_id) != len(self.nodes):
            seen, duplicates = set(), set()
            for node in self.nodes:
                (duplicates if node.id in seen else seen).add(node.id)
            problems.append(f"duplicate node ids: {sorted(duplicates)}")

        for node in self.nodes:
            if node.kind not in NODE_PORTS:
                problems.append(f"{node.id}: unknown node kind {node.kind!r}")
            for parameter in node.sweep:
                if not node.sweep[parameter]:
                    problems.append(f"{node.id}: sweep over {parameter!r} has no values")

        for edge in self.edges:
            if edge.source not in by_id:
                problems.append(f"edge references unknown source {edge.source!r}")
                continue
            if edge.target not in by_id:
                problems.append(f"edge references unknown target {edge.target!r}")
                continue
            source, target = by_id[edge.source], by_id[edge.target]
            if source.kind not in NODE_PORTS or target.kind not in NODE_PORTS:
                continue
            produced = NODE_PORTS[source.kind]["outputs"]
            accepted = NODE_PORTS[target.kind]["inputs"]
            if not produced:
                problems.append(f"{source.id} ({source.kind}) produces nothing to feed {target.id}")
            elif not set(produced) & set(accepted):
                problems.append(
                    f"type error {source.id} -> {target.id}: "
                    f"{source.kind} produces {produced}, {target.kind} accepts {accepted}"
                )

        problems.extend(self._cycle_problems())
        return problems

    def _cycle_problems(self) -> list[str]:
        outgoing: dict[str, list[str]] = {n.id: [] for n in self.nodes}
        for edge in self.edges:
            if edge.source in outgoing and edge.target in outgoing:
                outgoing[edge.source].append(edge.target)

        UNVISITED, ACTIVE, DONE = 0, 1, 2
        marks = dict.fromkeys(outgoing, UNVISITED)
        problems: list[str] = []

        def visit(node_id: str, trail: list[str]) -> None:
            marks[node_id] = ACTIVE
            for nxt in outgoing[node_id]:
                if marks[nxt] == ACTIVE:
                    cycle = trail[trail.index(nxt):] if nxt in trail else [nxt]
                    problems.append(f"cycle: {' -> '.join([*cycle, nxt])}")
                elif marks[nxt] == UNVISITED:
                    visit(nxt, [*trail, nxt])
            marks[node_id] = DONE

        for node_id in outgoing:
            if marks[node_id] == UNVISITED:
                visit(node_id, [node_id])
        return problems

    def require_valid(self) -> None:
        problems = self.validate()
        if problems:
            raise WorkflowError("; ".join(problems))


# ---------------------------------------------------------------------------- compilation


@dataclass
class CompiledNode:
    id: str
    kind: str
    parameters: dict[str, Any]
    upstream: list[str]
    sweep_values: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "parameters": self.parameters,
            "upstream": self.upstream,
            "sweep_values": self.sweep_values,
        }


def compile_workflow(workflow: Workflow) -> list[CompiledNode]:
    """Expand sweeps and order nodes for execution.

    Deterministic by construction: sweep values expand in declared order and the topological sort
    breaks ties by node id. The same YAML therefore compiles to the same plan on every machine,
    which is what lets the CLI and GUI be compared at all.
    """
    workflow.require_valid()

    by_id = {n.id: n for n in workflow.nodes}
    upstream: dict[str, list[str]] = {n.id: [] for n in workflow.nodes}
    downstream: dict[str, list[str]] = {n.id: [] for n in workflow.nodes}
    for edge in workflow.edges:
        upstream[edge.target].append(edge.source)
        downstream[edge.source].append(edge.target)

    order = _topological_order(workflow, downstream)

    compiled: list[CompiledNode] = []
    expansions: dict[str, list[str]] = {}

    for node_id in order:
        node = by_id[node_id]
        parents: list[str] = []
        for parent in sorted(upstream[node_id]):
            parents.extend(expansions.get(parent, [parent]))

        if not node.sweep:
            compiled.append(
                CompiledNode(id=node.id, kind=node.kind, parameters=dict(node.parameters),
                             upstream=parents)
            )
            expansions[node.id] = [node.id]
            continue

        names = list(node.sweep)
        produced: list[str] = []
        for combination in product(*(node.sweep[name] for name in names)):
            values = dict(zip(names, combination))
            suffix = "_".join(f"{k}{v}" for k, v in values.items())
            expanded_id = f"{node.id}[{suffix}]"
            compiled.append(
                CompiledNode(
                    id=expanded_id,
                    kind=node.kind,
                    parameters={**node.parameters, **values},
                    upstream=parents,
                    sweep_values=values,
                )
            )
            produced.append(expanded_id)
        expansions[node.id] = produced

    return compiled


def _topological_order(workflow: Workflow, downstream: dict[str, list[str]]) -> list[str]:
    indegree = {n.id: 0 for n in workflow.nodes}
    for edge in workflow.edges:
        indegree[edge.target] += 1

    # Ties break by id so the order is reproducible rather than dict-insertion dependent.
    ready = sorted([n for n, d in indegree.items() if d == 0])
    order: list[str] = []
    while ready:
        node_id = ready.pop(0)
        order.append(node_id)
        for nxt in sorted(downstream[node_id]):
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                ready.append(nxt)
                ready.sort()
    if len(order) != len(workflow.nodes):
        raise WorkflowError("workflow contains a cycle")
    return order
