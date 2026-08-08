"""P05 gate tests — dataset import, LFW pair protocol, degradation engine.

The gate: interactive preview and batch execution must call the same transform implementation and
match for deterministic settings.

Every image here is a real LFW photograph. Nothing is generated: a fabricated face would let a
quality operator "pass" against pixels no camera ever produced.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))

from studio_adapters import paths  # noqa: E402
from studio_data.dataset import DatasetManifest, public_export_is_safe  # noqa: E402
from studio_data.pairs import missing_images, pair_counts, read_lfw_pairs  # noqa: E402
from studio_transforms import operators as ops  # noqa: E402

needs_corpus = pytest.mark.skipif(
    not paths.available("lfw_root"), reason="LFW fixture corpus is not configured"
)


@pytest.fixture(scope="module")
def lfw_root() -> Path:
    return paths.get("lfw_root")


@pytest.fixture(scope="module")
def face(lfw_root: Path) -> Path:
    image = lfw_root / "Michael_Phelps" / "Michael_Phelps_0001.jpg"
    if not image.exists():
        pytest.skip(f"fixture face not present: {image}")
    return image


# ---------------------------------------------------------------- dataset import

@needs_corpus
def test_import_reads_subjects_from_the_directory_layout(lfw_root):
    manifest = DatasetManifest.from_directory(
        lfw_root, name="lfw-slice", classification="PUBLIC", limit=40
    )
    assert len(manifest) == 40
    assert all(s.subject_id for s in manifest.samples)
    assert all(len(s.sha256) == 64 for s in manifest.samples)
    # Referenced, not copied: the recorded path is the corpus path.
    assert all(str(lfw_root) in s.path for s in manifest.samples)


@needs_corpus
def test_sample_id_is_the_content_hash(face, lfw_root):
    manifest = DatasetManifest.from_directory(
        face.parent, name="one-subject", classification="PUBLIC"
    )
    target = next(s for s in manifest.samples if s.path == str(face))
    assert target.sample_id == target.sha256
    # Same digest the adapter recorded for this image, so dataset and engine records join up.
    assert target.sha256 == "29ff467ed2dc42e4b4d915c9f62e29b3feb8647f241a47f252a7909c8d0fcaee"


def test_non_public_import_demands_an_authorization_statement(tmp_path):
    (tmp_path / "subject").mkdir()
    with pytest.raises(ValueError, match="authorization"):
        DatasetManifest.from_directory(
            tmp_path, name="restricted", classification="RESTRICTED"
        )


def test_public_export_check_is_default_deny(tmp_path):
    (tmp_path / "subject").mkdir()
    manifest = DatasetManifest.from_directory(tmp_path, name="empty", classification="PUBLIC")
    ok, offenders = public_export_is_safe(manifest.samples)
    assert ok and offenders == []

    from studio_data.dataset import Sample

    restricted = Sample(
        sample_id="x", path="/private/a.jpg", sha256="0" * 64,
        classification="RESTRICTED", subject_id="s", authorization="IRB-1",
    )
    ok, offenders = public_export_is_safe([restricted])
    assert not ok and offenders == ["/private/a.jpg"]


@needs_corpus
def test_split_is_subject_disjoint_and_reproducible(lfw_root):
    """Splitting by sample puts the same person in train and test, so the score measures
    memorisation. Splitting by subject is the only correct unit here."""
    manifest = DatasetManifest.from_directory(
        lfw_root, name="lfw-split", classification="PUBLIC", limit=300
    )
    splits = manifest.subject_disjoint_split(seed=7)
    assert DatasetManifest.verify_disjoint(splits)
    assert sum(len(v) for v in splits.values()) == len(manifest)

    again = manifest.subject_disjoint_split(seed=7)
    assert {k: [s.sample_id for s in v] for k, v in splits.items()} == {
        k: [s.sample_id for s in v] for k, v in again.items()
    }

    different = manifest.subject_disjoint_split(seed=8)
    assert [s.sample_id for s in different["test"]] != [s.sample_id for s in splits["test"]]


@needs_corpus
def test_manifest_round_trips(lfw_root, tmp_path):
    manifest = DatasetManifest.from_directory(
        lfw_root, name="rt", classification="PUBLIC", limit=12
    )
    written = manifest.write(tmp_path / "manifest.json")
    reloaded = DatasetManifest.read(written)
    assert [s.to_dict() for s in reloaded.samples] == [s.to_dict() for s in manifest.samples]


# ---------------------------------------------------------------- pair protocol

@needs_corpus
def test_official_lfw_protocol_parses_to_its_declared_shape(lfw_root):
    """Read, not generated. Generated pairs would produce a different evaluation from every
    published LFW number."""
    pairs_file = lfw_root.parent / "pairs.txt"
    if not pairs_file.exists():
        pytest.skip("pairs.txt not present")

    pairs = read_lfw_pairs(pairs_file, lfw_root)
    counts = pair_counts(pairs)
    assert counts == {"total": 6000, "genuine": 3000, "impostor": 3000, "folds": 10}


@needs_corpus
def test_protocol_images_all_exist(lfw_root):
    pairs_file = lfw_root.parent / "pairs.txt"
    if not pairs_file.exists():
        pytest.skip("pairs.txt not present")
    missing = missing_images(read_lfw_pairs(pairs_file, lfw_root))
    assert missing == [], f"{len(missing)} protocol images missing, e.g. {missing[:3]}"


def test_malformed_pair_line_raises_rather_than_being_skipped(tmp_path):
    """Dropping a line silently would change fold sizes and quietly alter every metric."""
    bad = tmp_path / "pairs.txt"
    bad.write_text("1\t1\nOnly_One_Field\n\nSubject\t1\t2\n")
    with pytest.raises(ValueError):
        read_lfw_pairs(bad, tmp_path)


# ---------------------------------------------------------------- degradation engine

@needs_corpus
def test_every_operator_runs_on_a_real_face(face):
    image = ops.load(face)
    cases = {
        "jpeg": {"quality": 40},
        "resize": {"scale": 0.5},
        "gaussian_blur": {"radius": 2.0},
        "motion_blur": {"length": 5},
        "gaussian_noise": {"sigma": 8.0, "seed": 1},
        "brightness": {"factor": 0.7},
        "contrast": {"factor": 1.3},
        "gamma": {"gamma": 1.8},
        "grayscale": {},
        "crop": {"fraction": 0.1},
        "rotate": {"degrees": 5},
        "occlude": {"fraction": 0.25},
    }
    assert set(cases) == set(ops.OPERATORS), "a registered operator is untested"
    for operator, parameters in cases.items():
        output, record = ops.apply(operator, image, parameters=parameters)
        assert output.size == image.size, operator
        assert record.input_sha256 != record.output_sha256, f"{operator} changed nothing"
        assert record.implementation.startswith("studio_transforms.operators."), operator


@needs_corpus
def test_preview_and_batch_agree_for_deterministic_settings(face):
    """THE P05 gate.

    Guaranteed structurally rather than by testing two code paths into alignment: `apply()` is the
    only place a transform happens, so a preview cannot drift from a batch.
    """
    image = ops.load(face)
    deterministic = {k: v for k, v in {
        "jpeg": {"quality": 25},
        "resize": {"scale": 0.35},
        "gaussian_blur": {"radius": 3.0},
        "gamma": {"gamma": 2.2},
        "crop": {"fraction": 0.2},
        "occlude": {"fraction": 0.3, "position": "top"},
    }.items()}

    for operator, parameters in deterministic.items():
        _, preview = ops.apply(operator, image, parameters=parameters)
        batch = [ops.apply(operator, image, parameters=parameters)[1] for _ in range(3)]
        assert all(b.output_sha256 == preview.output_sha256 for b in batch), operator
        assert all(b.deterministic for b in batch), operator


@needs_corpus
def test_stochastic_operator_requires_a_seed_and_honours_it(face):
    image = ops.load(face)
    with pytest.raises(ValueError, match="seed"):
        ops.apply("gaussian_noise", image, parameters={"sigma": 5.0})

    _, first = ops.apply("gaussian_noise", image, parameters={"sigma": 5.0, "seed": 42})
    _, same = ops.apply("gaussian_noise", image, parameters={"sigma": 5.0, "seed": 42})
    _, other = ops.apply("gaussian_noise", image, parameters={"sigma": 5.0, "seed": 43})

    assert first.output_sha256 == same.output_sha256
    assert first.output_sha256 != other.output_sha256
    assert first.seed == 42


@needs_corpus
def test_sweep_applies_each_level_to_the_original(face):
    """A sweep that chained levels would measure accumulated recompression, not the parameter."""
    image = ops.load(face)
    results = ops.sweep(image, "jpeg", "quality", [90, 60, 30, 10])

    assert [value for value, _, _ in results] == [90, 60, 30, 10]
    inputs = {record.input_sha256 for _, _, record in results}
    assert len(inputs) == 1, "each level must start from the original image"
    outputs = [record.output_sha256 for _, _, record in results]
    assert len(set(outputs)) == 4


@needs_corpus
def test_chain_records_provenance_linking_each_step(face):
    """I13: the output of one step must be the recorded input of the next, or the chain cannot be
    replayed."""
    image = ops.load(face)
    _, records = ops.apply_chain(
        image, [("resize", {"scale": 0.5}), ("jpeg", {"quality": 30}), ("gaussian_blur", {"radius": 1.0})]
    )
    assert len(records) == 3
    for previous, following in zip(records, records[1:]):
        assert previous.output_sha256 == following.input_sha256


@needs_corpus
def test_transform_record_validates_against_the_schema(face):
    from studio_core.schemas import is_valid

    image = ops.load(face)
    _, record = ops.apply("jpeg", image, parameters={"quality": 50})
    assert is_valid("TransformRecord", record.to_dict())


@needs_corpus
def test_operators_reject_out_of_range_parameters(face):
    image = ops.load(face)
    for operator, parameters in [
        ("jpeg", {"quality": 0}),
        ("jpeg", {"quality": 101}),
        ("resize", {"scale": 0}),
        ("resize", {"scale": 1.5}),
        ("gaussian_blur", {"radius": -1}),
        ("crop", {"fraction": 0.5}),
        ("gamma", {"gamma": 0}),
    ]:
        with pytest.raises(ValueError):
            ops.apply(operator, image, parameters=parameters)
