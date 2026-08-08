"""P08 gate tests — M01–M07 loading and inspection, M14 registry.

Models here are the real BSI ONNX files shipped with OFIQ-Project, at the commit pinned in
config/repository-locks.yaml. Inference runs a real forward pass on a real LFW face.

Training and fine-tuning (M08–M11) are not covered yet; state.json records them as remaining
rather than this file pretending otherwise.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))

from studio_adapters import paths  # noqa: E402
from studio_models.loaders import (  # noqa: E402
    ModelLoadError,
    OnnxLoader,
    inspect_model,
    loader_for,
    sha256_file,
)
from studio_models.registry import (  # noqa: E402
    FORBIDDEN_STATE_WORDS,
    STATES,
    Lineage,
    LineageIncomplete,
    ModelRegistry,
)

OFIQ_COMMIT = "bb5dc91d00477e02ce53d2530d28e35021484393"

needs_models = pytest.mark.skipif(
    not paths.available("ofiq_project_root"),
    reason="OFIQ-Project must be configured to reach its bundled ONNX models",
)
needs_corpus = pytest.mark.skipif(
    not paths.available("lfw_root"), reason="LFW fixture corpus is not configured"
)


@pytest.fixture(scope="module")
def model_dir() -> Path:
    root = paths.get("ofiq_project_root") / "data" / "models"
    if not root.exists():
        pytest.skip(f"model directory not present: {root}")
    return root


@pytest.fixture(scope="module")
def head_pose_model(model_dir: Path) -> Path:
    path = model_dir / "head_pose_estimation" / "mb1_120x120.onnx"
    if not path.exists():
        pytest.skip(f"model not present: {path}")
    return path


# ---------------------------------------------------------------- loaders

def test_loader_dispatch_is_by_extension():
    assert loader_for("model.onnx").framework == "onnx"
    assert loader_for("checkpoint.pt").framework == "pytorch"
    assert loader_for("weights.pth").framework == "pytorch"
    assert loader_for("notes.txt") is None


def test_missing_model_raises_rather_than_returning_an_empty_model():
    with pytest.raises(ModelLoadError):
        inspect_model("/nonexistent/model.onnx")


def test_unknown_format_is_refused():
    with pytest.raises(ModelLoadError, match="no loader"):
        inspect_model("/tmp/model.bin")


@needs_models
def test_inspection_reads_the_real_graph_signature(head_pose_model):
    """Read from the model's own graph, not a sidecar description that can drift from the file."""
    info = inspect_model(
        head_pose_model,
        source_repository="https://github.com/BSI-OFIQ/OFIQ-Project.git",
        source_commit=OFIQ_COMMIT,
        license="BSI terms",
    )
    assert info.framework == "onnx"
    assert info.sha256 == sha256_file(head_pose_model)
    assert len(info.sha256) == 64

    assert [i.name for i in info.inputs] == ["input"]
    assert info.inputs[0].shape == [1, 3, 120, 120]
    assert info.outputs[0].shape == [1, 62]
    assert info.source_commit == OFIQ_COMMIT
    assert info.license == "BSI terms"


@needs_models
def test_dynamic_batch_dimensions_are_preserved_as_symbols(model_dir):
    """A symbolic dimension must not be silently turned into a number — that would make a
    variable-batch model look fixed-batch to everything downstream."""
    path = model_dir / "unified_quality_score" / "magface_iresnet50_norm.onnx"
    if not path.exists():
        pytest.skip("magface model not present")
    info = inspect_model(path)
    assert info.inputs[0].shape[0] == "batch_size"
    assert info.inputs[0].shape[1:] == [3, 112, 112]


@needs_models
@needs_corpus
def test_real_forward_pass_on_a_real_face(model_dir):
    """M07. A genuine inference: a real LFW photograph through a real BSI model."""
    import numpy as np

    from studio_transforms import operators as ops

    path = model_dir / "head_pose_estimation" / "mb1_120x120.onnx"
    if not path.exists():
        pytest.skip("head pose model not present")

    face = paths.get("lfw_root") / "Michael_Phelps" / "Michael_Phelps_0001.jpg"
    if not face.exists():
        pytest.skip("fixture face not present")

    image = ops.load(face).resize((120, 120))
    array = np.asarray(image, dtype=np.float32).transpose(2, 0, 1)[None] / 255.0

    session = OnnxLoader().session(path)
    outputs = session.run(None, {session.get_inputs()[0].name: array})

    assert outputs[0].shape == (1, 62)
    assert np.isfinite(outputs[0]).all(), "model produced NaN or inf on a real face"


# ---------------------------------------------------------------- registry

@needs_models
def test_registration_requires_complete_lineage(tmp_path, head_pose_model):
    registry = ModelRegistry(tmp_path / "models.sqlite")
    info = inspect_model(head_pose_model)

    with pytest.raises(LineageIncomplete):
        registry.register(info, Lineage(
            source="", base_checkpoint=None, dataset_manifest=None,
            training_run_id=None, git_commit=None,
        ))


@needs_models
def test_lineage_records_absence_explicitly(tmp_path, head_pose_model):
    """None is a statement — 'no base checkpoint' — where omission would be silence, and silence
    reads as an oversight six months later."""
    registry = ModelRegistry(tmp_path / "models.sqlite")
    record = registry.register(
        inspect_model(head_pose_model, source_commit=OFIQ_COMMIT, license="BSI terms"),
        Lineage(
            source="OFIQ-Project bundled model",
            base_checkpoint=None,
            dataset_manifest=None,
            training_run_id=None,
            git_commit=OFIQ_COMMIT,
            notes="third-party model; the studio did not train it",
        ),
    )
    assert record.state == "EXPERIMENTAL"
    assert set(Lineage.REQUIRED) <= set(record.lineage)
    assert record.lineage["training_run_id"] is None
    assert record.lineage["git_commit"] == OFIQ_COMMIT


@needs_models
def test_states_never_imply_certification(tmp_path, head_pose_model):
    registry = ModelRegistry(tmp_path / "models.sqlite")
    record = registry.register(
        inspect_model(head_pose_model),
        Lineage(source="s", base_checkpoint=None, dataset_manifest=None,
                training_run_id=None, git_commit=None),
    )
    assert set(STATES) == {"EXPERIMENTAL", "CANDIDATE", "VALIDATED", "ARCHIVED"}
    assert not (set(STATES) & FORBIDDEN_STATE_WORDS)

    for word in ("APPROVED", "CERTIFIED", "PRODUCTION"):
        with pytest.raises(ValueError):
            registry.promote(record.model_id, word, evidence="x")  # type: ignore[arg-type]


@needs_models
def test_validation_requires_linked_evidence(tmp_path, head_pose_model):
    """A state settable by assertion alone means nothing."""
    registry = ModelRegistry(tmp_path / "models.sqlite")
    record = registry.register(
        inspect_model(head_pose_model),
        Lineage(source="s", base_checkpoint=None, dataset_manifest=None,
                training_run_id=None, git_commit=None),
    )
    with pytest.raises(ValueError, match="evidence"):
        registry.promote(record.model_id, "VALIDATED", evidence="   ")

    promoted = registry.promote(
        record.model_id, "VALIDATED", evidence="forward pass on LFW face, finite outputs"
    )
    assert promoted.state == "VALIDATED"
    assert promoted.evidence[-1]["kind"] == "promoted_to_VALIDATED"
    assert "LFW" in promoted.evidence[-1]["detail"]


@needs_models
def test_integrity_check_detects_changed_bytes(tmp_path, head_pose_model):
    """A model whose bytes changed is not the model that was registered."""
    import shutil

    copy = tmp_path / "copy.onnx"
    shutil.copy(head_pose_model, copy)

    registry = ModelRegistry(tmp_path / "models.sqlite")
    record = registry.register(
        inspect_model(copy),
        Lineage(source="copy", base_checkpoint=None, dataset_manifest=None,
                training_run_id=None, git_commit=None),
    )
    ok, reason = registry.verify_integrity(record.model_id)
    assert ok and reason is None

    with open(copy, "ab") as handle:
        handle.write(b"\x00")
    ok, reason = registry.verify_integrity(record.model_id)
    assert not ok and "sha256 changed" in reason


@needs_models
def test_registry_survives_reopen(tmp_path, head_pose_model):
    db = tmp_path / "models.sqlite"
    record = ModelRegistry(db).register(
        inspect_model(head_pose_model),
        Lineage(source="s", base_checkpoint=None, dataset_manifest=None,
                training_run_id=None, git_commit=None),
    )
    reopened = ModelRegistry(db).get(record.model_id)
    assert reopened is not None
    assert reopened.sha256 == record.sha256
    assert len(ModelRegistry(db).all()) == 1
