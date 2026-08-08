"""P04 gate tests — B02 harness, B04 OFIQpy adapter, B09 typed output, B10 raw preservation.

The gate: every adapter must detect its runtime, report version and source, execute a fixture,
preserve raw output, emit typed output, pass unit tests, pass integration smoke, and surface
failures honestly.

These run against a real LFW face. They are skipped — not faked — when the engines are not
configured on this machine, because the alternative to a real face is a fabricated one.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))

from studio_adapters import paths  # noqa: E402
from studio_adapters.base import AdapterFailed  # noqa: E402
from studio_adapters.ofiqpy_adapter import OfiqpyAdapter  # noqa: E402
from studio_adapters.registry import get_adapter, implemented  # noqa: E402
from studio_backend.app import create_app  # noqa: E402
from studio_core.schemas import is_valid  # noqa: E402

engines_configured = paths.available("ofiqpy_root") and paths.available("ofiq_project_root")
needs_engines = pytest.mark.skipif(
    not engines_configured,
    reason="ofiqpy and OFIQ-Project must be configured (see config/local-paths.example.yaml)",
)
needs_corpus = pytest.mark.skipif(
    not paths.available("lfw_root"), reason="LFW fixture corpus is not configured"
)


@pytest.fixture(scope="module")
def face() -> Path:
    root = paths.get("lfw_root")
    image = root / "Michael_Phelps" / "Michael_Phelps_0001.jpg"
    if not image.exists():
        pytest.skip(f"fixture face not present: {image}")
    return image


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(workspace=tmp_path / "workspace")) as c:
        yield c


# ---------------------------------------------------------------- harness

def test_only_verified_engines_have_adapters():
    """Sparse on purpose: an adapter exists only for an engine that has actually run here.

    openfiqa joined the list once it was shown to run (DEGRADED, on CPU). The two that remain
    without adapters are blocked, and claiming adapters for them would imply a capability neither
    has demonstrated.
    """
    assert implemented() == ["ofiqpy", "openfiqa"]
    for blocked in ("ofiq_quality", "ofiq_project"):
        assert get_adapter(blocked) is None


def test_adapter_cannot_be_instantiated_incomplete():
    """The base class is abstract, so a partial adapter fails at construction rather than at the
    moment someone calls the method that was never written."""
    from studio_adapters.base import Adapter

    class Incomplete(Adapter):
        plugin_id = "incomplete"

    with pytest.raises(TypeError):
        Incomplete()  # type: ignore[abstract]


# ---------------------------------------------------------------- runtime detection

@needs_engines
def test_adapter_detects_its_runtime_and_both_sources():
    adapter = OfiqpyAdapter()
    ok, reason = adapter.available()
    assert ok, reason

    described = adapter.describe()
    assert described["interpreter"].endswith("/.venv/bin/python")
    # B-P01-09: an ofiqpy result depends on two repositories, so both commits are recorded.
    assert len(described["ofiqpy_commit"]) == 40
    assert len(described["ofiq_project_commit"]) == 40
    assert described["ofiqpy_commit"] != described["ofiq_project_commit"]
    assert "BSI" in described["weights_license"]


def test_missing_paths_are_reported_not_guessed(monkeypatch):
    monkeypatch.setenv("OFS_OFIQPY_ROOT", "/nonexistent/ofiqpy")
    monkeypatch.setattr(paths, "LOCAL_PATHS", Path("/nonexistent/local-paths.yaml"))
    ok, reason = OfiqpyAdapter().available()
    assert ok is False
    assert "OFS_OFIQPY_ROOT" in reason


# ---------------------------------------------------------------- execution + typing

@needs_engines
@needs_corpus
def test_assessment_of_a_real_face_is_typed_and_valid(face):
    result = OfiqpyAdapter().run(face)
    quality_vector = result.typed

    assert is_valid("QualityVector", quality_vector)
    assert len(quality_vector["components"]) == 28
    assert result.exit_code == 0

    # sample_id is the image's content hash, so the record names the exact bytes measured.
    assert quality_vector["sample_id"] == (
        "29ff467ed2dc42e4b4d915c9f62e29b3feb8647f241a47f252a7909c8d0fcaee"
    )


@needs_engines
@needs_corpus
def test_raw_output_is_preserved_alongside_the_typed_object(face):
    """B10. The typed object is an interpretation; the raw bytes are the evidence."""
    result = OfiqpyAdapter().run(face)
    assert result.raw_stdout.strip().startswith("{")
    assert "UnifiedQualityScore" in result.raw_stdout
    assert result.argv[1].endswith("ofiqpy_runner.py")
    assert "OFIQPY_OFIQ_DATA" in result.env


@needs_engines
@needs_corpus
def test_polarity_is_not_copied_from_a_map_known_to_be_wrong(face):
    """B-P01-03: the upstream polarity map is wrong for 10 of 27 components. Recording `unknown`
    is the honest reading; copying it would launder a known defect into typed output."""
    result = OfiqpyAdapter().run(face)
    polarities = {c["raw_polarity"] for c in result.typed["components"]}
    assert polarities == {"unknown"}
    assert all(c["polarity_map_revision"] is None for c in result.typed["components"])


@needs_engines
@needs_corpus
def test_scores_stay_at_computed(face):
    """Nothing has been validated, reproduced, or checked for conformance. An adapter has no
    authority to advance a score past COMPUTED."""
    result = OfiqpyAdapter().run(face)
    assert result.typed["state"] == "COMPUTED"
    assert result.typed["unified"]["state"] == "COMPUTED"
    assert result.typed["unified"]["semantics"]["definition_id"] == "ofiqpy.UnifiedQualityScore"


@needs_engines
def test_a_missing_image_fails_rather_than_returning_a_score():
    with pytest.raises(AdapterFailed):
        OfiqpyAdapter().run("/nonexistent/face.jpg")


@needs_engines
def test_a_non_image_fails_honestly(tmp_path):
    """An engine failure must surface as a failure. Returning 0.0 here would produce a number that
    looks like a measurement to everything downstream."""
    junk = tmp_path / "not-an-image.jpg"
    junk.write_bytes(b"this is not a JPEG")
    with pytest.raises(AdapterFailed) as excinfo:
        OfiqpyAdapter().run(junk)
    assert excinfo.value.exit_code != 0


# ---------------------------------------------------------------- HTTP surface

@needs_engines
@needs_corpus
def test_assess_endpoint_returns_typed_output_and_provenance(client, face):
    response = client.post("/api/engines/ofiqpy/assess", json={"image_path": str(face)})
    assert response.status_code == 200
    body = response.json()

    assert is_valid("QualityVector", body["quality_vector"])
    assert len(body["quality_vector"]["components"]) == 28
    assert body["provenance"]["exit_code"] == 0
    assert len(body["provenance"]["ofiq_project_commit"]) == 40
    assert "UnifiedQualityScore" in body["raw_output"]


def test_assess_on_a_blocked_engine_is_refused_with_its_blocker(client):
    response = client.post(
        "/api/engines/ofiq_quality/assess", json={"image_path": "/does/not/matter.jpg"}
    )
    assert response.status_code == 409
    assert response.json()["detail"]["blocker_id"] == "B-P01-02"


@needs_engines
def test_engine_status_reports_adapter_presence(client):
    ofiqpy = client.get("/api/engines/ofiqpy/status").json()
    assert ofiqpy["adapter"] is True and ofiqpy["available"] is True

    openfiqa = client.get("/api/engines/openfiqa/status").json()
    assert openfiqa["adapter"] is True
    assert openfiqa["available"] is True
    assert openfiqa["describe"]["device"] == "cpu"

    blocked = client.get("/api/engines/ofiq_quality/status").json()
    assert blocked["adapter"] is False
    assert "no adapter" in blocked["reason"]


@needs_engines
@needs_corpus
def test_streaming_run_uses_the_same_runner_as_the_adapter(client, face):
    """GUI and API must not drift into different results, so both paths invoke one runner."""
    import time

    created = client.post("/api/runs/plugin/ofiqpy", json={"image_path": str(face)}).json()
    deadline = time.time() + 120
    while time.time() < deadline:
        body = client.get(f"/api/runs/{created['run_id']}").json()
        if body["status"] in {"completed", "failed", "cancelled"}:
            break
        time.sleep(0.1)
    else:
        pytest.fail("streaming adapter run did not finish")

    assert body["status"] == "completed"
    assert body["exit_code"] == 0
    stdout = "".join(e.get("line", "") for e in body["events"] if e["type"] == "stdout")
    assert "UnifiedQualityScore" in stdout


# ---------------------------------------------------------------- FailureToAssess sentinel

@needs_engines
@needs_corpus
def test_failure_sentinel_never_reaches_a_score_column(tmp_path, face):
    """OFIQ signals "could not assess" with (raw 0, scalar -1) — ofiqpy's output.py names it the
    FailureToAssess sentinel.

    Found by a real JPEG sweep: at quality 5, UnderExposurePrevention and OverExposurePrevention
    both returned -1. Stored as a score, that -1 reads as very poor quality to every mean, axis and
    threshold downstream, and the error is invisible because -1 looks like a number.
    """
    from studio_transforms import operators as ops

    degraded_path = tmp_path / "q005.png"
    ops.apply("jpeg", ops.load(face), parameters={"quality": 5})[0].save(degraded_path)

    quality_vector = OfiqpyAdapter().run(degraded_path).typed
    by_name = {c["name"]: c for c in quality_vector["components"]}

    failed = [c for c in quality_vector["components"] if not c["computed"]]
    assert failed, "expected at least one FailureToAssess at JPEG quality 5"

    for component in failed:
        assert component["scalar"] is None, component["name"]
        assert component["failure_sentinel"] == -1, component["name"]

    # No component anywhere carries a negative score.
    scalars = [c["scalar"] for c in quality_vector["components"] if c["scalar"] is not None]
    assert all(0 <= s <= 100 for s in scalars)
    assert all(by_name[n]["computed"] for n in ("Sharpness", "HeadSize"))


@needs_engines
@needs_corpus
def test_a_computed_component_is_marked_computed(face):
    quality_vector = OfiqpyAdapter().run(face).typed
    assert all(c["computed"] for c in quality_vector["components"])
    assert all(c["failure_sentinel"] is None for c in quality_vector["components"])
