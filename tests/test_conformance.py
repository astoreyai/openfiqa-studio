"""P10 gate tests — profile schema, standards registry, conformance execution, evidence.

The gate: one local test profile must execute end to end and produce requirement-level evidence
automatically.

The tests below spend most of their effort on the ways this layer could lie: a profile claiming
authority it does not have, a missing test reading as a pass, a broken test reading as a pass, and
a report whose wording implies a determination nobody made.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "python"))

from studio_adapters import paths  # noqa: E402
from studio_adapters.ofiqpy_adapter import OfiqpyAdapter  # noqa: E402
from studio_conformance.profile import Profile, ProfileError, load_profiles  # noqa: E402
from studio_conformance.runner import (  # noqa: E402
    BLOCKED,
    FAIL,
    NOT_APPLICABLE,
    NOT_TESTED,
    PASS,
    ConformanceRunner,
    TestOutcome,
)
from studio_conformance.tests_fiqa import runner as fiqa_runner  # noqa: E402
from studio_transforms import operators as ops  # noqa: E402

PROFILE_DIR = REPO / "profiles"
LOCAL_PROFILE = PROFILE_DIR / "local-fiqa-behaviour.yaml"

needs_engines = pytest.mark.skipif(
    not (paths.available("ofiqpy_root") and paths.available("ofiq_project_root")),
    reason="engines are not configured on this machine",
)
needs_corpus = pytest.mark.skipif(
    not paths.available("lfw_root"), reason="LFW fixture corpus is not configured"
)


@pytest.fixture(scope="module")
def ofiqpy_context():
    if not (paths.available("ofiqpy_root") and paths.available("lfw_root")):
        pytest.skip("engines or corpus not configured")
    face = paths.get("lfw_root") / "Michael_Phelps" / "Michael_Phelps_0001.jpg"
    adapter = OfiqpyAdapter()
    runs = [adapter.run(face).typed for _ in range(2)]
    return {
        "quality_vector": runs[0],
        "repeat_vectors": runs,
        "describe": adapter.describe(),
    }


# ---------------------------------------------------------------- profile integrity

def test_profile_must_be_version_pinned():
    with pytest.raises(ProfileError, match="version"):
        Profile.from_dict({
            "profile_id": "x", "title": "t", "authority": "a", "effective_date": "2026-01-01",
            "requirements": [],
        })


def test_a_profile_cannot_claim_normative_authority_it_lacks():
    """The single most important guard in this layer.

    Without it, `normative: true` is a one-line assertion that turns observations into apparent
    standard compliance — and a conformance report is only worth the weakest citation in it.
    """
    with pytest.raises(ProfileError, match="normative"):
        Profile.from_dict({
            "profile_id": "fake-iso",
            "title": "ISO/IEC 29794-5 conformance",
            "authority": "ISO/IEC",
            "version": "2025",
            "effective_date": "2026-01-01",
            "normative": True,
            "requirements": [{
                "requirement_id": "R1",
                "description": "sharpness shall be assessed",
                "test_id": "component_count",
                "severity": "critical",
                "source": "implementation_derived",   # not a normative document
                "citation": "I watched the engine do it",
            }],
        })


def test_requirement_source_is_a_closed_enum():
    with pytest.raises(ProfileError, match="source"):
        Profile.from_dict({
            "profile_id": "x", "title": "t", "authority": "a", "version": "1",
            "effective_date": "2026-01-01",
            "requirements": [{
                "requirement_id": "R1", "description": "d", "test_id": "t",
                "severity": "major", "source": "vibes", "citation": "c",
            }],
        })


def test_every_requirement_needs_a_citation():
    with pytest.raises(ProfileError, match="citation"):
        Profile.from_dict({
            "profile_id": "x", "title": "t", "authority": "a", "version": "1",
            "effective_date": "2026-01-01",
            "requirements": [{
                "requirement_id": "R1", "description": "d", "test_id": "t",
                "severity": "major", "source": "local_policy",
            }],
        })


def test_shipped_profile_does_not_claim_a_standard_it_has_not_read():
    profile = Profile.read(LOCAL_PROFILE)
    assert profile.normative is False
    assert not any(r.source == "normative_document" for r in profile.requirements)
    assert "not a standards body" in profile.authority


def test_registry_loads_the_profile_directory():
    profiles = load_profiles(PROFILE_DIR)
    assert "local-fiqa-behaviour" in profiles


# ---------------------------------------------------------------- verdict discipline

def test_a_missing_test_is_not_tested_never_pass():
    """A conformance report where absence reads as compliance is worse than no report."""
    profile = Profile.read(LOCAL_PROFILE)
    requirement = profile.requirement("BEH-009")
    assert requirement is not None
    outcome = ConformanceRunner()._execute_one(requirement, {})
    assert outcome.verdict == NOT_TESTED


def test_a_raising_test_is_blocked_never_pass():
    runner = ConformanceRunner()

    @runner.register("explodes")
    def _explodes(_req, _ctx):
        raise RuntimeError("the harness itself is broken")

    profile = Profile.from_dict({
        "profile_id": "p", "title": "t", "authority": "a", "version": "1",
        "effective_date": "2026-01-01",
        "requirements": [{
            "requirement_id": "R1", "description": "d", "test_id": "explodes",
            "severity": "critical", "source": "local_policy", "citation": "c",
        }],
    })
    report = runner.execute(profile, {}, implementation={"plugin_id": "x"})
    assert report.results[0].verdict == BLOCKED
    assert "the harness itself is broken" in report.results[0].detail


def test_applies_when_yields_not_applicable():
    runner = ConformanceRunner()

    @runner.register("always_pass")
    def _always(_req, _ctx):
        return TestOutcome(PASS, "ok")

    profile = Profile.from_dict({
        "profile_id": "p", "title": "t", "authority": "a", "version": "1",
        "effective_date": "2026-01-01",
        "requirements": [{
            "requirement_id": "R1", "description": "d", "test_id": "always_pass",
            "severity": "minor", "source": "local_policy", "citation": "c",
            "applies_when": {"modality": "iris"},
        }],
    })
    report = runner.execute(profile, {"modality": "face"}, implementation={})
    assert report.results[0].verdict == NOT_APPLICABLE


def test_unknown_verdict_is_rejected_at_construction():
    with pytest.raises(ValueError, match="unknown verdict"):
        TestOutcome("CONFORMANT", "nice try")


# ---------------------------------------------------------------- real execution

@needs_engines
@needs_corpus
def test_profile_executes_end_to_end_against_a_real_implementation(ofiqpy_context):
    """THE gate."""
    profile = Profile.read(LOCAL_PROFILE)
    report = fiqa_runner.execute(
        profile, ofiqpy_context, implementation={"plugin_id": "ofiqpy"}
    )

    assert len(report.results) == len(profile.requirements)
    counts = report.counts
    assert counts[FAIL] == 0, [r.to_dict() for r in report.results if r.verdict == FAIL]
    assert counts[PASS] == 8
    assert counts[NOT_TESTED] == 1  # BEH-009 has no implementation, deliberately

    # Requirement-level evidence, automatically: each result carries what a reviewer would check.
    for result in report.results:
        assert result.citation
        assert result.detail


@needs_engines
@needs_corpus
def test_failure_sentinel_requirement_detects_the_real_degraded_case(tmp_path, ofiqpy_context):
    """BEH-003 against an image that genuinely triggers FailureToAssess.

    At JPEG quality 5 ofiqpy cannot assess two exposure components. The requirement must pass —
    because the adapter reports them honestly — while confirming the unassessed components exist.
    """
    face = paths.get("lfw_root") / "Michael_Phelps" / "Michael_Phelps_0001.jpg"
    degraded = tmp_path / "q005.png"
    ops.apply("jpeg", ops.load(face), parameters={"quality": 5})[0].save(degraded)

    vector = OfiqpyAdapter().run(degraded).typed
    profile = Profile.read(LOCAL_PROFILE)
    report = fiqa_runner.execute(
        profile,
        {"quality_vector": vector, "repeat_vectors": [vector, vector],
         "describe": ofiqpy_context["describe"]},
        implementation={"plugin_id": "ofiqpy"},
    )
    by_id = {r.requirement_id: r for r in report.results}

    assert by_id["BEH-003"].verdict == PASS
    assert by_id["BEH-003"].evidence["unassessed"], "expected FailureToAssess at quality 5"
    assert by_id["BEH-002"].verdict == PASS, "no negative scalar may survive into a score column"


def test_a_dishonest_adapter_would_fail_beh_003():
    """The requirement has teeth: an implementation that left -1 in a score column fails."""
    dishonest = {
        "sample_id": "x",
        "engine": {"engine_id": "ofiqpy", "version": "0.1.1", "commit": "abc"},
        "components": [
            {"name": "OverExposurePrevention", "raw": 0.0, "scalar": -1.0,
             "computed": False, "raw_polarity": "unknown"},
        ],
        "state": "COMPUTED",
    }
    profile = Profile.read(LOCAL_PROFILE)
    report = fiqa_runner.execute(
        profile, {"quality_vector": dishonest, "repeat_vectors": [dishonest, dishonest]},
        implementation={},
    )
    by_id = {r.requirement_id: r for r in report.results}
    assert by_id["BEH-003"].verdict == FAIL
    assert "OverExposurePrevention" in str(by_id["BEH-003"].evidence)


# ---------------------------------------------------------------- report wording

@needs_engines
@needs_corpus
def test_report_never_claims_conformance(ofiqpy_context):
    """The one sentence a reader will quote must not imply a determination nobody made."""
    report = fiqa_runner.execute(
        Profile.read(LOCAL_PROFILE), ofiqpy_context, implementation={"plugin_id": "ofiqpy"}
    )
    statement = report.statement()
    assert "not a determination of conformance" in statement
    assert "NON-NORMATIVE" in statement

    markdown = report.to_markdown()
    assert "## Caveat" in markdown
    assert "does not demonstrate conformance to" in markdown
    for standard in ("ISO/IEC 29794-5", "ICAO 9303", "DoD EBTS", "NATO STANAG 4715"):
        assert standard in markdown


@needs_engines
@needs_corpus
def test_report_is_written_as_machine_readable_evidence(tmp_path, ofiqpy_context):
    import json

    report = fiqa_runner.execute(
        Profile.read(LOCAL_PROFILE), ofiqpy_context, implementation={"plugin_id": "ofiqpy"}
    )
    written = report.write(tmp_path / "report.json")
    payload = json.loads(written.read_text())

    assert payload["profile_version"] == "0.1.0"
    assert payload["profile_normative"] is False
    assert len(payload["results"]) == 9
    assert set(payload["counts"]) >= {PASS, FAIL, BLOCKED, NOT_TESTED}
