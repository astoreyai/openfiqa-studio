"""P10 T04 golden vectors + P09 P13 / P10 T10 evidence packages.

Both are mechanisms for handing a result to somebody who does not trust you. Most of these tests
are about what the mechanisms refuse to do.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
import sys

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "python"))

from studio_adapters import paths  # noqa: E402
from studio_adapters.ofiqpy_adapter import OfiqpyAdapter  # noqa: E402
from studio_conformance.vectors import (  # noqa: E402
    DRIFT,
    MATCH,
    MISSING,
    NEW,
    VectorStore,
    capture,
    check,
)
from studio_provenance.evidence import (  # noqa: E402
    ExportRefused,
    PackageContents,
    export,
    verify,
)

needs_engine = pytest.mark.skipif(
    not (paths.available("ofiqpy_root") and paths.available("ofiq_project_root")
         and paths.available("lfw_root")),
    reason="engine and corpus must be configured",
)

CAPTURED_AT = "2026-08-08T00:00:00+00:00"


def _vector(name: str, scalar: float, computed: bool = True) -> dict:
    return {
        "name": name, "raw": None, "scalar": scalar if computed else None,
        "computed": computed, "raw_polarity": "unknown", "polarity_map_revision": None,
    }


def _quality_vector(components, sample_id="a" * 64, commit="c" * 40, unified=50.0):
    return {
        "sample_id": sample_id,
        "engine": {"engine_id": "ofiqpy", "version": "0.1.1", "commit": commit},
        "components": components,
        "unified": {
            "value": unified,
            "engine": {"engine_id": "ofiqpy", "version": "0.1.1", "commit": commit},
            "semantics": {"definition_id": "ofiqpy.UnifiedQualityScore", "direction": "unknown"},
            "state": "COMPUTED",
        },
        "state": "COMPUTED",
    }


# ---------------------------------------------------------------- golden vectors

def test_vector_is_keyed_on_content_hash_not_path():
    """A vector keyed on a filename silently follows whatever bytes end up at that name."""
    vector = capture("v1", _quality_vector([_vector("Sharpness", 80.0)]), captured_at=CAPTURED_AT)
    assert vector.image_sha256 == "a" * 64
    assert not hasattr(vector, "image_path")


def test_identical_rerun_matches():
    qv = _quality_vector([_vector("Sharpness", 80.0), _vector("HeadSize", 40.0)])
    result = check(capture("v1", qv, captured_at=CAPTURED_AT), qv)
    assert result.passed
    assert all(f.verdict == MATCH for f in result.features)
    assert "MATCH across" in result.summary()


def test_drift_beyond_tolerance_is_detected():
    baseline = _quality_vector([_vector("Sharpness", 80.0)])
    vector = capture("v1", baseline, captured_at=CAPTURED_AT, default_tolerance=1.0)

    within = check(vector, _quality_vector([_vector("Sharpness", 80.5)]))
    assert within.passed

    beyond = check(vector, _quality_vector([_vector("Sharpness", 85.0)]))
    assert not beyond.passed
    assert [f.feature for f in beyond.drifted] == ["Sharpness"]
    assert beyond.drifted[0].delta == pytest.approx(5.0)


def test_tolerance_is_per_feature_not_one_global_epsilon():
    """Components differ in scale and in how they degrade; one threshold is either too loose for
    the stable ones or too tight for the noisy ones."""
    baseline = _quality_vector([_vector("Sharpness", 80.0), _vector("HeadSize", 40.0)])
    vector = capture(
        "v1", baseline, captured_at=CAPTURED_AT,
        tolerance={"Sharpness": 5.0}, default_tolerance=0.0,
    )
    assert vector.tolerance_for("Sharpness") == 5.0
    assert vector.tolerance_for("HeadSize") == 0.0

    result = check(vector, _quality_vector([
        _vector("Sharpness", 83.0),   # within its own tolerance
        _vector("HeadSize", 40.5),    # outside the default
    ]))
    verdicts = {f.feature: f.verdict for f in result.features}
    assert verdicts["Sharpness"] == MATCH
    assert verdicts["HeadSize"] == DRIFT


def test_becoming_unassessable_counts_as_drift():
    """An engine that stops being able to assess a component has changed behaviour, and a
    None-versus-number comparison must not be quietly treated as a match."""
    baseline = _quality_vector([_vector("OverExposurePrevention", 100.0)])
    vector = capture("v1", baseline, captured_at=CAPTURED_AT)
    result = check(vector, _quality_vector([_vector("OverExposurePrevention", None, computed=False)]))
    assert not result.passed
    assert result.features[0].verdict == DRIFT


def test_both_unassessed_is_a_match():
    baseline = _quality_vector([_vector("OverExposurePrevention", None, computed=False)])
    vector = capture("v1", baseline, captured_at=CAPTURED_AT)
    result = check(vector, _quality_vector([_vector("OverExposurePrevention", None, computed=False)]))
    assert result.passed


def test_removed_and_added_components_are_distinguished():
    baseline = _quality_vector([_vector("Sharpness", 80.0), _vector("Gone", 10.0)])
    vector = capture("v1", baseline, captured_at=CAPTURED_AT)
    result = check(vector, _quality_vector([_vector("Sharpness", 80.0), _vector("Fresh", 20.0)]))
    verdicts = {f.feature: f.verdict for f in result.features}
    assert verdicts["Gone"] == MISSING
    assert verdicts["Fresh"] == NEW
    assert not result.passed


def test_checking_against_the_wrong_image_raises():
    vector = capture("v1", _quality_vector([_vector("Sharpness", 80.0)]), captured_at=CAPTURED_AT)
    with pytest.raises(ValueError, match="pins image"):
        check(vector, _quality_vector([_vector("Sharpness", 80.0)], sample_id="b" * 64))


def test_a_vector_carries_the_blockers_open_against_it():
    """Pinning is not blessing. A vector captured from a defective implementation faithfully
    reproduces the defect, so the caveat travels with it."""
    vector = capture(
        "openfiqa-c08", _quality_vector([_vector("C08", 0.0)]),
        captured_at=CAPTURED_AT, known_blockers=["B-P04-11"],
        note="C08 is degenerate on this build; pinned to detect change, not as a correct value",
    )
    assert vector.known_blockers == ["B-P04-11"]
    assert check(vector, _quality_vector([_vector("C08", 0.0)])).known_blockers == ["B-P04-11"]


def test_vector_store_round_trips(tmp_path):
    vectors = [capture("v1", _quality_vector([_vector("Sharpness", 80.0)]), captured_at=CAPTURED_AT)]
    store = VectorStore(tmp_path / "vectors.json")
    store.write(vectors)
    assert [v.to_dict() for v in store.read()] == [v.to_dict() for v in vectors]


@needs_engine
def test_real_engine_reproduces_its_own_golden_vector():
    """The regression check that would catch an engine upgrade changing results."""
    face = paths.get("lfw_root") / "Michael_Phelps" / "Michael_Phelps_0001.jpg"
    adapter = OfiqpyAdapter()

    vector = capture("ofiqpy-lfw-phelps", adapter.run(face).typed, captured_at=CAPTURED_AT)
    result = check(vector, adapter.run(face).typed)

    assert result.passed, [f.to_dict() for f in result.drifted]
    assert len(result.features) == 29  # 28 components plus the unified score
    assert result.captured_commit == result.current_commit


# ---------------------------------------------------------------- evidence packages

def _package(**overrides) -> PackageContents:
    base = {
        "title": "test package",
        "workflow_yaml": "name: t\nnodes: []\nedges: []\n",
        "run_manifest": {"status": "partial", "nodes": []},
        "open_blockers": "# Blockers\n\nB-P04-08 open.\n",
    }
    base.update(overrides)
    return PackageContents(**base)


def test_export_refuses_restricted_material_rather_than_trimming(tmp_path):
    """A trimmed package looks complete while describing a different dataset."""
    contents = _package(dataset_manifest={
        "samples": [
            {"path": "/public/a.jpg", "classification": "PUBLIC"},
            {"path": "/private/b.jpg", "classification": "RESTRICTED"},
        ]
    })
    with pytest.raises(ExportRefused, match="not classified PUBLIC"):
        export(contents, tmp_path / "pkg.zip")

    assert not (tmp_path / "pkg.zip").exists(), "nothing may be written on refusal"


def test_export_permits_restricted_only_when_explicitly_authorised(tmp_path):
    contents = _package(dataset_manifest={
        "samples": [{"path": "/private/b.jpg", "classification": "RESTRICTED"}]
    })
    package = export(contents, tmp_path / "pkg.zip", allow_restricted=True)
    assert package.exists()


def test_public_only_package_exports(tmp_path):
    contents = _package(dataset_manifest={
        "samples": [{"path": "/public/a.jpg", "classification": "PUBLIC"}]
    })
    package = export(contents, tmp_path / "pkg.zip")
    with zipfile.ZipFile(package) as archive:
        names = set(archive.namelist())
    assert {"README.md", "MANIFEST.sha256", "workflow.yaml", "blockers.md"} <= names


def test_package_carries_its_own_blockers(tmp_path):
    """Evidence that omits its own caveats is advocacy."""
    package = export(_package(), tmp_path / "pkg.zip")
    with zipfile.ZipFile(package) as archive:
        assert "B-P04-08" in archive.read("blockers.md").decode()
        readme = archive.read("README.md").decode()
    assert "What it does NOT establish" in readme
    assert "non-normative" in readme
    assert "B-P04-08" in readme


def test_manifest_hashes_every_member_and_verifies(tmp_path):
    package = export(_package(), tmp_path / "pkg.zip")
    ok, problems = verify(package)
    assert ok, problems


def test_verify_detects_a_tampered_member(tmp_path):
    package = export(_package(), tmp_path / "pkg.zip")

    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(package) as source, zipfile.ZipFile(tampered, "w") as target:
        for item in source.namelist():
            body = source.read(item)
            if item == "workflow.yaml":
                body = b"name: something-else\nnodes: []\nedges: []\n"
            target.writestr(item, body)

    ok, problems = verify(tampered)
    assert not ok
    assert any("workflow.yaml" in p and "mismatch" in p for p in problems)


def test_package_can_never_contain_an_image(tmp_path):
    contents = _package()
    contents.extra_notes = "note"
    package = export(contents, tmp_path / "pkg.zip")
    with zipfile.ZipFile(package) as archive:
        for name in archive.namelist():
            assert Path(name).suffix.lower() not in {".jpg", ".jpeg", ".png", ".bmp", ".tif"}


def test_readme_lists_every_file_with_its_digest(tmp_path):
    package = export(_package(sbom={"components": []}), tmp_path / "pkg.zip")
    with zipfile.ZipFile(package) as archive:
        readme = archive.read("README.md").decode()
        manifest = archive.read("MANIFEST.sha256").decode()
    for name in ("workflow.yaml", "run_manifest.json", "sbom.json"):
        assert f"`{name}`" in readme
        assert name in manifest
