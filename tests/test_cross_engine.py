"""P04 B05 + B11 — the openfiqa adapter and cross-engine comparison.

Two engines now run here. That makes conflating them possible for the first time, so most of these
tests are about refusing to.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "python"))

from studio_adapters import paths  # noqa: E402
from studio_adapters.ofiqpy_adapter import OfiqpyAdapter  # noqa: E402
from studio_adapters.openfiqa_adapter import OpenfiqaAdapter  # noqa: E402
from studio_adapters.registry import get_adapter, implemented  # noqa: E402
from studio_core.schemas import is_valid, load_plugin_manifests  # noqa: E402
from studio_eval.cross_engine import (  # noqa: E402
    MIN_INTERPRETABLE_N,
    ComparisonError,
    EngineSeries,
    compare,
    series_from_vectors,
    spearman,
    spearman_standard_error,
)

needs_both = pytest.mark.skipif(
    not (paths.available("ofiqpy_root") and paths.available("ofiq_project_root")
         and paths.available("openfiqa_workspace") and paths.available("lfw_root")),
    reason="both engines and the corpus must be configured",
)


@pytest.fixture(scope="module")
def paired_vectors():
    if not (paths.available("openfiqa_workspace") and paths.available("lfw_root")):
        pytest.skip("engines or corpus not configured")
    faces = sorted(paths.get("lfw_root").glob("*/*_0001.jpg"))[:4]
    ofiqpy, openfiqa = OfiqpyAdapter(), OpenfiqaAdapter()
    return (
        [ofiqpy.run(f).typed for f in faces],
        [openfiqa.run(f).typed for f in faces],
    )


# ---------------------------------------------------------------- openfiqa adapter (B05)

def test_openfiqa_now_has_an_adapter():
    assert implemented() == ["ofiqpy", "openfiqa"]
    assert get_adapter("openfiqa") is not None


def test_openfiqa_is_degraded_with_both_reasons_recorded():
    """DEGRADED, not AVAILABLE. It works, but on a CPU fallback and with a model unpickled across
    a scikit-learn version boundary — both recorded rather than hidden behind a green light."""
    availability = load_plugin_manifests()["openfiqa"]["availability"]
    assert availability["state"] == "DEGRADED"
    assert availability["blocker_id"] == "B-P04-11"
    assert "12020" in availability["reason"]        # the driver version
    assert "1.8.0" in availability["reason"]        # the sklearn boundary
    assert availability["verified_by"]["rc"] == 0


@needs_both
def test_openfiqa_produces_a_valid_quality_vector():
    face = paths.get("lfw_root") / "Michael_Phelps" / "Michael_Phelps_0001.jpg"
    result = OpenfiqaAdapter().run(face)
    vector = result.typed

    assert is_valid("QualityVector", vector)
    assert len(vector["components"]) == 28
    assert vector["unified"]["semantics"]["definition_id"] == "openfiqa.unified_score"
    assert vector["state"] == "COMPUTED"
    assert result.env["device"] == "cpu"


@needs_both
def test_openfiqa_components_keep_their_own_vocabulary():
    """openfiqa reports C01..C28; ofiqpy reports names. No verified mapping between the two exists
    in this repository, so inventing one would silently align measurements that may not
    correspond."""
    face = paths.get("lfw_root") / "Michael_Phelps" / "Michael_Phelps_0001.jpg"
    names = {c["name"] for c in OpenfiqaAdapter().run(face).typed["components"]}
    assert names == {f"C{i:02d}" for i in range(1, 29)}
    assert "Sharpness" not in names


# ---------------------------------------------------------------- comparison discipline (B11)

def test_two_series_from_the_same_definition_cannot_be_compared():
    same = EngineSeries("ofiqpy", "ofiqpy.UnifiedQualityScore", [1.0, 2.0, 3.0])
    with pytest.raises(ComparisonError, match="same definition_id"):
        compare(same, same, method="rank")


def test_raw_side_by_side_yields_no_statistic_by_design():
    """It exists so a viewer can show two columns without implying commensurability."""
    a = EngineSeries("ofiqpy", "ofiqpy.UnifiedQualityScore", [1.0, 2.0, 3.0])
    b = EngineSeries("openfiqa", "openfiqa.unified_score", [3.0, 2.0, 1.0])
    with pytest.raises(ComparisonError, match="no statistic"):
        compare(a, b, method="raw_side_by_side")


def test_unknown_method_is_refused():
    a = EngineSeries("x", "x.score", [1.0, 2.0, 3.0])
    b = EngineSeries("y", "y.score", [1.0, 2.0, 3.0])
    with pytest.raises(ComparisonError, match="unknown method"):
        compare(a, b, method="just_compare_them")


def test_comparison_never_asserts_numeric_equivalence():
    a = EngineSeries("x", "x.score", [1.0, 2.0, 3.0, 4.0])
    b = EngineSeries("y", "y.score", [1.0, 2.0, 3.0, 4.0])
    result = compare(a, b, method="rank")
    assert result.asserts_numeric_equivalence is False
    assert result.to_dict()["asserts_numeric_equivalence"] is False


def test_small_samples_are_marked_uninterpretable():
    """The guard that stops a five-point correlation being quoted as a finding."""
    a = EngineSeries("x", "x.score", [1.0, 2.0, 3.0, 4.0, 5.0])
    b = EngineSeries("y", "y.score", [5.0, 1.0, 4.0, 2.0, 3.0])
    result = compare(a, b, method="rank")

    assert result.n == 5
    assert result.interpretable is False
    assert result.standard_error == pytest.approx(0.5)
    assert any("cannot distinguish agreement from disagreement" in c for c in result.caveats)
    assert "NOT INTERPRETABLE" in result.summary()


def test_large_samples_are_marked_interpretable():
    values = list(range(MIN_INTERPRETABLE_N))
    a = EngineSeries("x", "x.score", [float(v) for v in values])
    b = EngineSeries("y", "y.score", [float(v) for v in values])
    result = compare(a, b, method="rank")
    assert result.interpretable is True
    assert result.statistic == pytest.approx(1.0)


def test_spearman_matches_known_values():
    assert spearman([1, 2, 3, 4, 5], [1, 2, 3, 4, 5]) == pytest.approx(1.0)
    assert spearman([1, 2, 3, 4, 5], [5, 4, 3, 2, 1]) == pytest.approx(-1.0)
    assert spearman_standard_error(5) == pytest.approx(0.5)
    assert spearman_standard_error(101) == pytest.approx(0.1)


def test_series_builder_refuses_to_mix_engines():
    def vector(engine_id, definition_id):
        return {
            "sample_id": "s", "engine": {"engine_id": engine_id},
            "unified": {"value": 1.0, "semantics": {"definition_id": definition_id}},
        }

    with pytest.raises(ComparisonError, match="more than one engine"):
        series_from_vectors([vector("ofiqpy", "a"), vector("openfiqa", "a")])


def test_series_builder_refuses_to_silently_drop_missing_scores():
    """Dropping them would compare a different population than the caller asked for."""
    good = {
        "sample_id": "s1", "engine": {"engine_id": "ofiqpy"},
        "unified": {"value": 1.0, "semantics": {"definition_id": "d"}},
    }
    missing = {"sample_id": "s2", "engine": {"engine_id": "ofiqpy"}, "unified": None}
    with pytest.raises(ComparisonError, match="no unified score"):
        series_from_vectors([good, missing])


# ---------------------------------------------------------------- the real measurement

@needs_both
def test_real_cross_engine_comparison_on_lfw(paired_vectors):
    """Both engines on the same faces.

    The assertion is deliberately not about the correlation's value. At this n the statistic is
    uninformative, and a test asserting a particular sign would be encoding noise as a finding.
    What IS asserted: the machinery reports the sample size honestly and refuses to call the
    result interpretable.
    """
    ofiqpy_vectors, openfiqa_vectors = paired_vectors
    left = series_from_vectors(ofiqpy_vectors)
    right = series_from_vectors(openfiqa_vectors)

    assert left.sample_ids == right.sample_ids, "the two engines must have seen the same images"

    result = compare(left, right, method="rank")
    assert result.definition_ids == ["ofiqpy.UnifiedQualityScore", "openfiqa.unified_score"]
    assert result.n == len(ofiqpy_vectors)
    assert result.interpretable is False, "4 samples cannot support an interpretable correlation"
    assert result.asserts_numeric_equivalence is False

    # The distributional observation is more robust at small n than the correlation is.
    ofiqpy_range = result.ranges["ofiqpy"]
    openfiqa_range = result.ranges["openfiqa"]
    assert ofiqpy_range[1] - ofiqpy_range[0] > 0
    assert openfiqa_range[1] - openfiqa_range[0] > 0


# ---------------------------------------------------------------- study reporting

def test_summary_reports_dropped_rows_rather_than_hiding_them():
    """Silently dropping incomplete rows would summarise a different population than was sampled."""
    from studio_eval.report import summarise

    rows = [{"a": 1.0, "b": 2.0}, {"a": 2.0, "b": 3.0}, {"a": 3.0, "b": None},
            {"a": 4.0, "b": 5.0}]
    summary = summarise(rows, "a", "b", "engine_a.score", "engine_b.score")
    assert summary["n"] == 3
    assert summary["rows_dropped_for_missing_scores"] == 1


def test_summary_marks_small_n_uninterpretable_and_says_so_in_markdown():
    from studio_eval.report import summarise, to_markdown

    rows = [{"a": float(i), "b": float(-i)} for i in range(5)]
    summary = summarise(rows, "a", "b", "engine_a.score", "engine_b.score")
    assert summary["interpretable"] is False

    markdown = to_markdown(summary, "small study")
    assert "NOT interpretable" in markdown
    assert "SE ≈" in markdown
    assert "B-P04-08" in markdown, "the matcher gap must be stated with any quality-score summary"


def test_disjoint_ranges_are_named_as_such():
    """More robust at small n than a correlation: it needs only the ranges, no pairing assumption."""
    from studio_eval.report import summarise, to_markdown

    rows = [{"a": float(i), "b": float(i + 100)} for i in range(6)]
    summary = summarise(rows, "a", "b", "engine_a.score", "engine_b.score")
    assert summary["overlap"]["ranges_disjoint"] is True
    assert "disjoint" in to_markdown(summary, "t")


def test_overlapping_ranges_report_their_overlap():
    from studio_eval.report import summarise

    rows = [{"a": float(i), "b": float(i + 2)} for i in range(10)]
    summary = summarise(rows, "a", "b", "engine_a.score", "engine_b.score")
    assert summary["overlap"]["ranges_disjoint"] is False
    assert summary["overlap"]["overlap_width"] > 0


def test_summary_never_asserts_numeric_equivalence():
    from studio_eval.report import summarise

    rows = [{"a": float(i), "b": float(i)} for i in range(25)]
    summary = summarise(rows, "a", "b", "engine_a.score", "engine_b.score")
    assert summary["asserts_numeric_equivalence"] is False
    assert summary["interpretable"] is True
