"""P06 gate tests — typed ports, validation, YAML, compiler, sweeps, CLI equivalence.

THE gate: the same workflow must run from GUI and CLI and produce equivalent deterministic
artifacts and manifests.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "python"))

from studio_adapters import paths  # noqa: E402
from studio_backend.app import create_app  # noqa: E402
from studio_workflow.executor import WorkflowExecutor, workflow_digest  # noqa: E402
from studio_workflow.graph import Workflow, WorkflowError, compile_workflow  # noqa: E402

WORKFLOW_FILE = REPO / "workflows" / "jpeg-degradation-sweep.yaml"

needs_engines = pytest.mark.skipif(
    not (paths.available("ofiqpy_root") and paths.available("ofiq_project_root")),
    reason="engines are not configured on this machine",
)
needs_corpus = pytest.mark.skipif(
    not paths.available("lfw_root"), reason="LFW fixture corpus is not configured"
)


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(workspace=tmp_path / "workspace")) as c:
        yield c


def _small_workflow(root: Path) -> str:
    return f"""
version: 1
name: equivalence-check
nodes:
  - id: src
    kind: dataset
    parameters: {{root: {root}, classification: PUBLIC, limit: 1}}
  - id: blur
    kind: transform
    parameters: {{operator: gaussian_blur, radius: 2.0}}
  - id: engine
    kind: engine
    parameters: {{plugin_id: ofiqpy}}
edges:
  - {{source: src, target: blur}}
  - {{source: blur, target: engine}}
"""


# ---------------------------------------------------------------- typed validation

def test_type_error_between_incompatible_ports_is_rejected():
    """Wiring a QualityVector into a scorer would silently skip the feature-engineering stage that
    B-P01-01 says does not exist. It is a validation error, not a runtime surprise."""
    workflow = Workflow.from_yaml("""
name: bad-types
nodes:
  - {id: e, kind: engine, parameters: {plugin_id: ofiqpy}}
  - {id: s, kind: scorer, parameters: {}}
edges:
  - {source: e, target: s}
""")
    problems = workflow.validate()
    assert any("type error" in p for p in problems), problems
    assert any("QualityVector" in p and "FeatureTable" in p for p in problems)


def test_correct_chain_validates():
    workflow = Workflow.from_yaml("""
name: good-types
nodes:
  - {id: e, kind: engine, parameters: {}}
  - {id: f, kind: feature_table, parameters: {}}
  - {id: s, kind: scorer, parameters: {}}
edges:
  - {source: e, target: f}
  - {source: f, target: s}
""")
    assert workflow.validate() == []


def test_cycles_are_detected():
    workflow = Workflow.from_yaml("""
name: cyclic
nodes:
  - {id: a, kind: transform, parameters: {}}
  - {id: b, kind: transform, parameters: {}}
edges:
  - {source: a, target: b}
  - {source: b, target: a}
""")
    assert any("cycle" in p for p in workflow.validate())


def test_unknown_node_kind_and_dangling_edge_are_reported():
    workflow = Workflow.from_yaml("""
name: broken
nodes:
  - {id: a, kind: teleporter, parameters: {}}
edges:
  - {source: a, target: nowhere}
""")
    problems = workflow.validate()
    assert any("unknown node kind" in p for p in problems)
    assert any("unknown target" in p for p in problems)


def test_duplicate_node_ids_are_reported():
    workflow = Workflow.from_yaml("""
name: dupes
nodes:
  - {id: a, kind: dataset, parameters: {}}
  - {id: a, kind: transform, parameters: {}}
""")
    assert any("duplicate node ids" in p for p in workflow.validate())


# ---------------------------------------------------------------- serialisation and compilation

def test_yaml_round_trips_without_changing_identity():
    original = Workflow.read(WORKFLOW_FILE)
    reparsed = Workflow.from_yaml(original.to_yaml())
    assert workflow_digest(original) == workflow_digest(reparsed)


def test_digest_is_canonical_not_textual():
    """Reformatting a workflow must not change what it IS, or every manifest comparison breaks on
    whitespace."""
    a = Workflow.from_yaml("name: x\nnodes: [{id: n, kind: dataset}]\nedges: []\n")
    b = Workflow.from_yaml("name: x\nnodes:\n  - id: n\n    kind: dataset\nedges: []\n")
    assert workflow_digest(a) == workflow_digest(b)


def test_sweep_expands_into_one_node_per_level():
    plan = compile_workflow(Workflow.read(WORKFLOW_FILE))
    jpeg = [n for n in plan if n.kind == "transform"]
    assert [n.id for n in jpeg] == [
        "jpeg[quality90]", "jpeg[quality40]", "jpeg[quality10]"
    ]
    assert [n.parameters["quality"] for n in jpeg] == [90, 40, 10]
    # Downstream sees every expanded node, not just the last.
    engine = next(n for n in plan if n.kind == "engine")
    assert len(engine.upstream) == 3


def test_compilation_order_is_deterministic():
    workflow = Workflow.read(WORKFLOW_FILE)
    first = [n.id for n in compile_workflow(workflow)]
    for _ in range(3):
        assert [n.id for n in compile_workflow(workflow)] == first


def test_compiling_an_invalid_workflow_raises():
    workflow = Workflow.from_yaml("""
name: bad
nodes:
  - {id: e, kind: engine, parameters: {}}
  - {id: s, kind: scorer, parameters: {}}
edges: [{source: e, target: s}]
""")
    with pytest.raises(WorkflowError):
        compile_workflow(workflow)


# ---------------------------------------------------------------- execution

@needs_engines
@needs_corpus
def test_blocked_stages_are_reported_not_skipped(tmp_path):
    """A workflow that quietly dropped its scoring stage would still produce a manifest, and the
    manifest would look complete."""
    manifest = WorkflowExecutor(tmp_path).run(Workflow.read(WORKFLOW_FILE))

    by_id = {n.node_id: n for n in manifest.nodes}
    assert by_id["usfiqa_features"].status == "blocked"
    assert by_id["usfiqa_features"].blocker_id == "B-P01-01"
    assert by_id["usfiqa"].status == "blocked"
    assert by_id["usfiqa"].blocker_id == "B-P01-02"

    assert manifest.status == "partial", "a run with blocked stages is not 'completed'"
    assert by_id["ofiqpy"].status == "completed"


@needs_engines
@needs_corpus
def test_full_slice_produces_quality_vectors_for_every_sweep_level(tmp_path):
    manifest = WorkflowExecutor(tmp_path).run(Workflow.read(WORKFLOW_FILE))
    engine = next(n for n in manifest.nodes if n.kind == "engine")
    # 2 samples x 3 JPEG levels
    assert len(engine.outputs) == 6
    assert manifest.artifacts["quality_vectors"] == 6


# ---------------------------------------------------------------- THE gate: CLI == GUI

@needs_engines
@needs_corpus
def test_cli_and_api_produce_equivalent_manifests(tmp_path, client):
    """P06 gate.

    Both paths call the same compiler and executor, so equivalence is structural. This test proves
    the structure actually holds rather than assuming it.
    """
    root = paths.get("lfw_root") / "Michael_Phelps"
    workflow_yaml = _small_workflow(root)
    workflow_file = tmp_path / "wf.yaml"
    workflow_file.write_text(workflow_yaml)

    cli_manifest_path = tmp_path / "cli-manifest.json"
    completed = subprocess.run(
        [sys.executable, str(REPO / "python" / "studio_cli.py"), "run", str(workflow_file),
         "--workdir", str(tmp_path / "cli"), "--manifest", str(cli_manifest_path)],
        capture_output=True, text=True, cwd=REPO, timeout=900,
    )
    assert completed.returncode == 0, completed.stderr
    cli = json.loads(cli_manifest_path.read_text())

    response = client.post(
        "/api/workflows/run", json={"yaml": workflow_yaml, "workdir": str(tmp_path / "api")}
    )
    assert response.status_code == 200
    api = response.json()

    # Same workflow identity, same status, same per-node outcomes.
    assert cli["workflow_sha256"] == api["workflow_sha256"]
    assert cli["status"] == api["status"] == "completed"
    assert [n["node_id"] for n in cli["nodes"]] == [n["node_id"] for n in api["nodes"]]
    assert [n["status"] for n in cli["nodes"]] == [n["status"] for n in api["nodes"]]

    # And the same scientific output: identical sample ids from identical pixels.
    cli_engine = next(n for n in cli["nodes"] if n["kind"] == "engine")
    api_engine = next(n for n in api["nodes"] if n["kind"] == "engine")
    assert cli_engine["outputs"] == api_engine["outputs"]
    assert cli_engine["outputs"], "engine produced no output in either path"


def test_cli_validate_exits_nonzero_on_a_bad_workflow(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("""
name: bad
nodes:
  - {id: e, kind: engine, parameters: {}}
  - {id: s, kind: scorer, parameters: {}}
edges: [{source: e, target: s}]
""")
    completed = subprocess.run(
        [sys.executable, str(REPO / "python" / "studio_cli.py"), "validate", str(bad)],
        capture_output=True, text=True, cwd=REPO, timeout=120,
    )
    assert completed.returncode == 1
    assert "type error" in completed.stdout


def test_api_validate_matches_cli_validate(client):
    text = WORKFLOW_FILE.read_text()
    body = client.post("/api/workflows/validate", json={"yaml": text}).json()
    assert body["valid"] is True
    assert body["workflow_sha256"] == workflow_digest(Workflow.read(WORKFLOW_FILE))
    assert body["nodes"] == 6 and body["edges"] == 5


# ---------------------------------------------------------------- canvas contract (W01)

def test_node_kinds_endpoint_serves_the_backend_port_table(client):
    """The canvas fetches its connection rules from here rather than carrying a copy.

    A frontend with its own type table keeps drawing edges the executor rejects the moment the
    schema changes (ADR-0001, ADR-0004).
    """
    from studio_workflow.graph import NODE_PORTS

    kinds = {k["kind"]: k for k in client.get("/api/workflows/node-kinds").json()["kinds"]}
    assert set(kinds) == set(NODE_PORTS)
    for kind, spec in NODE_PORTS.items():
        assert kinds[kind]["inputs"] == spec["inputs"]
        assert kinds[kind]["outputs"] == spec["outputs"]

    # Blocked kinds are advertised so the palette can mark them before anyone wires one up.
    assert kinds["feature_table"]["blocked_by"] == "B-P01-01"
    assert kinds["scorer"]["blocked_by"] == "B-P01-02"
    assert kinds["engine"]["blocked_by"] is None


def test_canvas_style_yaml_is_accepted_by_the_backend(client):
    """Byte-for-byte the shape WorkflowCanvas.toYaml() emits: two-space indent, JSON-quoted
    scalars, inline edge mappings. If the generator drifts from the parser, the Run button fails
    at the worst possible moment."""
    canvas_yaml = (
        "version: 1\n"
        "name: canvas-drawn\n"
        "nodes:\n"
        "  - id: dataset_1\n"
        "    kind: dataset\n"
        "    parameters:\n"
        '      root: "/tmp/does-not-need-to-exist"\n'
        '      classification: "PUBLIC"\n'
        "      limit: 2\n"
        "  - id: transform_2\n"
        "    kind: transform\n"
        "    parameters:\n"
        '      operator: "jpeg"\n'
        "    sweep:\n"
        "      quality: [90,40]\n"
        "  - id: engine_3\n"
        "    kind: engine\n"
        "    parameters:\n"
        '      plugin_id: "ofiqpy"\n'
        "edges:\n"
        "  - {source: dataset_1, target: transform_2}\n"
        "  - {source: transform_2, target: engine_3}\n"
    )
    body = client.post("/api/workflows/validate", json={"yaml": canvas_yaml}).json()
    assert body["valid"] is True, body["problems"]
    assert body["nodes"] == 3 and body["edges"] == 2

    # And it compiles, with the sweep expanding exactly as the canvas preview implies.
    plan = compile_workflow(Workflow.from_yaml(canvas_yaml))
    assert [n.id for n in plan if n.kind == "transform"] == [
        "transform_2[quality90]", "transform_2[quality40]"
    ]


def test_canvas_cannot_draw_an_edge_the_executor_would_reject(client):
    """The rule the canvas enforces client-side must be the same one the backend enforces."""
    kinds = {k["kind"]: k for k in client.get("/api/workflows/node-kinds").json()["kinds"]}

    def canvas_allows(source: str, target: str) -> bool:
        return bool(set(kinds[source]["outputs"]) & set(kinds[target]["inputs"]))

    for source, target, expected in [
        ("dataset", "transform", True),
        ("transform", "engine", True),
        ("engine", "feature_table", True),
        ("feature_table", "scorer", True),
        ("engine", "scorer", False),      # skips the missing feature-engineering stage
        ("dataset", "scorer", False),
        ("artifact", "engine", False),    # artifact produces nothing
    ]:
        assert canvas_allows(source, target) is expected, f"{source} -> {target}"

        workflow = Workflow.from_yaml(
            f"name: t\nnodes:\n"
            f"  - {{id: a, kind: {source}, parameters: {{}}}}\n"
            f"  - {{id: b, kind: {target}, parameters: {{}}}}\n"
            f"edges: [{{source: a, target: b}}]\n"
        )
        backend_allows = not any("type error" in p or "produces nothing" in p
                                 for p in workflow.validate())
        assert backend_allows is expected, f"backend disagrees on {source} -> {target}"
