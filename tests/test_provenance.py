"""P09 gate tests — provenance DAG, publication freeze, reproduction.

The gate is a traversal: publication figure ← metric ← evaluation ← scores ← model ← transformed
samples ← transforms ← original dataset ← git/environment. The UI half is blocked by B-P03-01, so
the traversal is exercised through the store's query API instead, which is the same graph the view
would render.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "python"))

from studio_adapters import paths  # noqa: E402
from studio_provenance.reproduce import (  # noqa: E402
    BLOCKED,
    DIFFERENT,
    EXACT,
    PublicationManifest,
    freeze,
    reproduce,
)
from studio_provenance.store import (  # noqa: E402
    RELATIONS,
    OrphanArtifact,
    ProvenanceStore,
    ingest_run_manifest,
)
from studio_workflow.executor import WorkflowExecutor  # noqa: E402
from studio_workflow.graph import Workflow  # noqa: E402

WORKFLOW_FILE = REPO / "workflows" / "jpeg-degradation-sweep.yaml"

needs_engines = pytest.mark.skipif(
    not (paths.available("ofiqpy_root") and paths.available("ofiq_project_root")),
    reason="engines are not configured on this machine",
)
needs_corpus = pytest.mark.skipif(
    not paths.available("lfw_root"), reason="LFW fixture corpus is not configured"
)


@pytest.fixture
def store(tmp_path) -> ProvenanceStore:
    return ProvenanceStore(tmp_path / "provenance.sqlite")


@pytest.fixture(scope="module")
def run_manifest(tmp_path_factory) -> dict:
    if not (paths.available("ofiqpy_root") and paths.available("lfw_root")):
        pytest.skip("engines or corpus not configured")
    workdir = tmp_path_factory.mktemp("run")
    return WorkflowExecutor(workdir).run(Workflow.read(WORKFLOW_FILE)).to_dict()


# ---------------------------------------------------------------- the DAG

def test_relation_vocabulary_is_closed(store):
    store.add_artifact("a", "figure")
    store.add_artifact("b", "metric")
    with pytest.raises(ValueError, match="unknown relation"):
        store.relate("a", "COMES_FROM_SOMEWHERE", "b")
    assert "DERIVED_FROM" in RELATIONS and "REPRODUCES" in RELATIONS


def test_edge_to_an_unregistered_artifact_is_refused(store):
    """A dangling reference is a lineage that looks complete and is not."""
    store.add_artifact("known", "figure")
    with pytest.raises(OrphanArtifact):
        store.relate("known", "DERIVED_FROM", "never-registered")


def test_traversal_runs_in_both_directions(store):
    """Forward answers 'what is this figure built from'. Backward answers 'which published claims
    depend on this sample' — the direction that catches a withdrawn authorization."""
    chain = [
        ("dataset", "dataset"), ("transform", "node:transform"), ("scores", "node:engine"),
        ("metric", "metric"), ("figure", "figure"),
    ]
    for artifact_id, kind in chain:
        store.add_artifact(artifact_id, kind)
    for child, parent in zip([c[0] for c in chain[1:]], [c[0] for c in chain[:-1]]):
        store.relate(child, "DERIVED_FROM", parent)

    assert store.ancestors("figure") == ["metric", "scores", "transform", "dataset"]
    assert store.descendants("dataset") == ["transform", "scores", "metric", "figure"]


def test_orphan_detection(store):
    store.add_artifact("connected_a", "x")
    store.add_artifact("connected_b", "y")
    store.add_artifact("lonely", "z")
    store.relate("connected_a", "DERIVED_FROM", "connected_b")
    assert store.orphans() == ["lonely"]


@needs_engines
@needs_corpus
def test_run_manifest_ingests_into_a_traversable_graph(store, run_manifest):
    run_id = ingest_run_manifest(store, run_manifest)

    engine_node = f"{run_id}/ofiqpy"
    ancestors = store.ancestors(engine_node)
    # The engine's lineage reaches back through every JPEG level to the dataset node.
    assert f"{run_id}/lfw" in ancestors
    assert any("jpeg[quality" in a for a in ancestors)
    assert run_id in ancestors

    lineage = store.lineage_path(engine_node)
    assert lineage[0]["artifact_id"] == engine_node
    assert len(lineage) == len(ancestors) + 1


@needs_engines
@needs_corpus
def test_blocked_stages_appear_in_the_lineage(store, run_manifest):
    """A lineage that omitted blocked nodes would show a complete pipeline where a stage never
    ran."""
    run_id = ingest_run_manifest(store, run_manifest)
    blocked = store.get(f"{run_id}/usfiqa")
    assert blocked is not None
    assert blocked.attributes["status"] == "blocked"
    assert blocked.attributes["blocker_id"] == "B-P01-02"


# ---------------------------------------------------------------- freeze and reproduce

@needs_engines
@needs_corpus
def test_freeze_embeds_the_workflow_rather_than_pointing_at_it(run_manifest):
    """A manifest that points at a file elsewhere is not reproducible by anyone who lacks it."""
    workflow = Workflow.read(WORKFLOW_FILE)
    manifest = freeze("sweep", workflow, run_manifest, environment={"python": "3.11"})
    assert "nodes:" in manifest.workflow_yaml
    assert manifest.workflow_sha256 == run_manifest["workflow_sha256"]
    assert manifest.blocked_nodes == {
        "usfiqa_features": "B-P01-01", "usfiqa": "B-P01-02"
    }


@needs_engines
@needs_corpus
def test_reproduction_of_a_deterministic_workflow_is_exact(tmp_path, run_manifest):
    """The real thing: rerun the frozen workflow and compare against the reference."""
    workflow = Workflow.read(WORKFLOW_FILE)
    manifest = freeze("sweep", workflow, run_manifest, environment={})
    report = reproduce(manifest, tmp_path / "rerun")

    assert report.workflow_sha256_reference == report.workflow_sha256_rerun
    # Every executable node matched; the only non-EXACT nodes were blocked in the reference too.
    non_blocked = [n for n in report.nodes if n.verdict != BLOCKED]
    assert all(n.verdict == EXACT for n in non_blocked), [n.to_dict() for n in report.nodes]
    assert report.verdict == BLOCKED, "blocked stages must be surfaced in the overall verdict"


@needs_engines
@needs_corpus
def test_reproduction_never_mutates_the_reference(tmp_path, run_manifest):
    """The rule that makes reproduction mean anything. A system that updates the published value
    when it disagrees reports success every time and detects nothing."""
    workflow = Workflow.read(WORKFLOW_FILE)
    manifest = freeze("sweep", workflow, run_manifest, environment={})
    before = json.dumps(manifest.to_dict(), sort_keys=True)

    reproduce(manifest, tmp_path / "rerun")

    assert json.dumps(manifest.to_dict(), sort_keys=True) == before


def test_a_changed_workflow_reproduces_as_different(tmp_path):
    """If the workflow itself changed, the result cannot be called reproduced whatever the
    outputs happen to say."""
    manifest = PublicationManifest(
        title="tampered",
        workflow_name="x",
        workflow_sha256="0" * 64,  # does not match the embedded YAML
        workflow_yaml="name: x\nnodes: [{id: n, kind: dataset, parameters: {root: /nonexistent}}]\nedges: []\n",
        frozen_at="2026-08-08T00:00:00+00:00",
        node_outputs={"n": []},
        node_statuses={"n": "completed"},
    )
    report = reproduce(manifest, tmp_path / "rerun")
    assert report.verdict == DIFFERENT
    assert report.workflow_sha256_reference != report.workflow_sha256_rerun


def test_missing_node_reproduces_as_missing_dependency(tmp_path):
    manifest = PublicationManifest(
        title="missing-node",
        workflow_name="x",
        workflow_sha256="",
        workflow_yaml="name: x\nnodes: [{id: present, kind: dataset, parameters: {root: /nonexistent}}]\nedges: []\n",
        frozen_at="2026-08-08T00:00:00+00:00",
        node_outputs={"present": [], "vanished": ["abc"]},
        node_statuses={"present": "failed", "vanished": "completed"},
    )
    report = reproduce(manifest, tmp_path / "rerun")
    verdicts = {n.node_id: n.verdict for n in report.nodes}
    assert verdicts["vanished"] == "MISSING_DEPENDENCY"


@needs_engines
@needs_corpus
def test_report_renders_markdown_stating_the_reference_was_untouched(tmp_path, run_manifest):
    workflow = Workflow.read(WORKFLOW_FILE)
    report = reproduce(freeze("sweep", workflow, run_manifest, environment={}), tmp_path / "r")
    markdown = report.to_markdown()
    assert "# Reproduction report — sweep" in markdown
    assert "reference values were not modified at any point" in markdown
    assert report.reference_mutated is False
