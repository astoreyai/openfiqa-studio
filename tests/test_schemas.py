"""P02 gate tests — A11 schema compatibility.

The gate has four clauses. Each is tested here, and the last two are tested NEGATIVELY: a schema
that merely permits the right shape proves nothing, because the failure mode is that it also
permits the wrong one. These tests fail if the disproved models become representable again.

    1. schemas validate
    2. frontend/backend types cannot silently diverge
    3. engine-specific score meaning is not embedded in generic types
    4. at least one fixture plugin validates
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))

from studio_core.schemas import (  # noqa: E402
    PLUGIN,
    SCIENTIFIC_OBJECTS,
    blocked_plugins,
    is_valid,
    load_plugin_manifests,
    load_schema,
    validator_for,
)

# The real US-FIQA feature contract digest, from feature_columns.json observed 2026-08-07.
USFIQA_CONTRACT_DIGEST = "3b6ec824ab4768410bcb98b9d7f14e391abb25fd0d85f619dfafacbd89872410"


# ---------------------------------------------------------------- clause 1: schemas validate

@pytest.mark.parametrize("name", [SCIENTIFIC_OBJECTS, PLUGIN])
def test_schema_document_is_wellformed(name):
    Draft202012Validator.check_schema(load_schema(name))


def test_every_scientific_definition_is_a_wellformed_schema():
    schema = load_schema(SCIENTIFIC_OBJECTS)
    assert schema["$defs"], "the scientific type system must not be empty"
    for defn, subschema in schema["$defs"].items():
        Draft202012Validator.check_schema(subschema), defn


# -------------------------------------------- clause 2: types cannot silently diverge

def test_plugin_port_types_all_exist_in_the_scientific_schema():
    """A port type the type system does not define is exactly how the two sides drift apart."""
    port_types = set(load_schema(PLUGIN)["$defs"]["Port"]["properties"]["type"]["enum"])
    defined = set(load_schema(SCIENTIFIC_OBJECTS)["$defs"])
    # Dataset, Embedding, Model, Artifact and PairSet arrive with later prompts; the types that
    # P01 established must already be present and wired.
    established = {"ImageSample", "QualityVector", "FeatureTable", "EngineScore", "ComparisonScore"}
    assert established <= port_types
    assert established <= defined


def test_feature_table_and_quality_vector_are_not_interchangeable():
    """P01/C2: ofiq-quality consumes a FeatureTable and accepts no image.

    If a QualityVector validated as a FeatureTable, the graph would happily wire an extractor
    straight into US-FIQA and silently skip the feature-engineering stage that B-P01-01 says does
    not exist yet.
    """
    quality_vector = {
        "sample_id": "s1",
        "engine": {"engine_id": "ofiqpy", "version": "0.1.1", "commit": "c80fb38"},
        "components": [
            {
                "name": "Sharpness",
                "raw": 0.5,
                "scalar": 72.0,
                "computed": True,
                "raw_polarity": "unknown",
            }
        ],
        "state": "COMPUTED",
    }
    assert is_valid("QualityVector", quality_vector)
    assert not is_valid("FeatureTable", quality_vector)


# ------------------------------- clause 3: score meaning is not embedded in generic types

def test_a_bare_number_is_not_a_score():
    """The whole point of EngineScore. A float cannot say which engine made it or what it means."""
    assert not is_valid("EngineScore", 87.5)
    assert not is_valid("EngineScore", {"value": 87.5})


def test_score_requires_engine_and_semantics():
    incomplete = {
        "value": 87.5,
        "engine": {"engine_id": "ofiqpy", "version": "0.1.1", "commit": "c80fb38"},
        "state": "COMPUTED",
    }
    assert not is_valid("EngineScore", incomplete), "semantics must not be optional"

    complete = dict(incomplete)
    complete["semantics"] = {
        "definition_id": "ofiqpy.UnifiedQualityScore",
        "direction": "unknown",
    }
    assert is_valid("EngineScore", complete)


def test_unknown_direction_is_representable():
    """P01 could not verify score direction for any engine. Recording `unknown` must be legal;
    the alternative is that the schema forces a guess."""
    score = {
        "value": None,
        "engine": {"engine_id": "ofiq_quality", "version": "0.2.0", "commit": None},
        "semantics": {"definition_id": "ofiq_quality.predicted_score", "direction": "unknown"},
        "state": "COMPUTED",
    }
    assert is_valid("EngineScore", score)


def test_three_unified_scores_cannot_share_a_definition_id():
    """P01/R7: ofiqpy, openfiqa and ofiq_quality each emit something called a unified score.
    They are three different quantities and must carry three different definition ids."""
    ids = {
        "ofiqpy": "ofiqpy.UnifiedQualityScore",
        "openfiqa": "openfiqa.profile_score",
        "ofiq_quality": "ofiq_quality.predicted_score",
    }
    assert len(set(ids.values())) == 3
    for engine_id, definition_id in ids.items():
        assert is_valid(
            "EngineScore",
            {
                "value": 50.0,
                "engine": {"engine_id": engine_id, "version": "x", "commit": None},
                "semantics": {"definition_id": definition_id, "direction": "unknown"},
                "state": "COMPUTED",
            },
        )


def test_cross_engine_comparison_cannot_claim_numeric_equivalence():
    base = {
        "method": "rank",
        "engines": [
            {"engine_id": "ofiqpy", "version": "0.1.1", "commit": "c80fb38"},
            {"engine_id": "openfiqa", "version": "0.5.0", "commit": None},
        ],
    }
    assert is_valid("CrossEngineComparison", {**base, "asserts_numeric_equivalence": False})
    assert not is_valid("CrossEngineComparison", {**base, "asserts_numeric_equivalence": True})


def test_comparison_method_is_mandatory_and_closed():
    engines = [
        {"engine_id": "ofiqpy", "version": "0.1.1", "commit": "c80fb38"},
        {"engine_id": "openfiqa", "version": "0.5.0", "commit": None},
    ]
    assert not is_valid(
        "CrossEngineComparison", {"engines": engines, "asserts_numeric_equivalence": False}
    )
    assert not is_valid(
        "CrossEngineComparison",
        {"method": "just_compare_them", "engines": engines, "asserts_numeric_equivalence": False},
    )


def test_scientific_states_are_not_collapsible():
    schema = load_schema(SCIENTIFIC_OBJECTS)
    states = schema["$defs"]["ScientificState"]["enum"]
    assert states == ["COMPUTED", "VALIDATED", "REPRODUCED", "CONFORMANT", "PUBLICATION_READY"]


# ------------------------------------------------- clause 4: fixture plugins validate

def test_all_plugin_manifests_validate():
    manifests = load_plugin_manifests()
    assert manifests, "no plugin manifests found"
    validator = validator_for(PLUGIN)
    for plugin_id, manifest in manifests.items():
        errors = [e.message for e in validator.iter_errors(manifest)]
        assert not errors, f"{plugin_id}: {errors}"


def test_blocked_plugin_must_name_its_blocker():
    """A registry entry that says BLOCKED without a reason is indistinguishable from a bug."""
    validator = validator_for(PLUGIN)
    manifest = dict(load_plugin_manifests()["ofiq_quality"])
    manifest["availability"] = {"state": "BLOCKED"}
    assert not validator.is_valid(manifest)


def test_the_engines_p01_blocked_are_recorded_as_blocked():
    blocked = blocked_plugins()
    assert blocked["ofiq_quality"] == "B-P01-02"
    assert blocked["ofiq_project"] == "B-P01-04"


def test_available_requires_a_recorded_execution():
    """AVAILABLE is a claim that must be paid for.

    B-P04-00 has cleared and ofiqpy genuinely ran on a real LFW face, so AVAILABLE is now a true
    statement about one engine. The guard therefore moves rather than disappearing: a manifest may
    say AVAILABLE only when it carries `verified_by` evidence of an rc=0 execution. Asserting
    availability in the manifest alone remains a fabricated capability.
    """
    validator = validator_for(PLUGIN)
    for plugin_id, manifest in load_plugin_manifests().items():
        availability = manifest["availability"]
        if availability["state"] == "AVAILABLE":
            assert availability.get("verified_by"), f"{plugin_id} claims AVAILABLE with no evidence"
            assert availability["verified_by"]["rc"] == 0

    unpaid = dict(load_plugin_manifests()["ofiqpy"])
    unpaid["availability"] = {"state": "AVAILABLE", "last_checked": "2026-08-07"}
    assert not validator.is_valid(unpaid), "AVAILABLE without verified_by must be rejected"


def test_ofiqpy_declares_its_external_data_dependency():
    """ofiqpy is MIT but loads BSI-licensed config and weights from an OFIQ-Project checkout
    (B-P01-09). An adapter that does not set OFIQPY_OFIQ_DATA fails with FileNotFoundError, so the
    dependency has to be declared rather than discovered at runtime."""
    env = load_plugin_manifests()["ofiqpy"]["implementation"]["environment"]
    assert "OFIQPY_OFIQ_DATA" in env["required_env"]
    dep = env["external_data_dependency"]
    assert dep["blocker_id"] == "B-P01-09"
    assert dep["from_commit"] == "bb5dc91d00477e02ce53d2530d28e35021484393"


def test_usfiqa_consumes_a_feature_table_not_an_image():
    inputs = load_plugin_manifests()["ofiq_quality"]["ports"]["inputs"]
    assert [p["type"] for p in inputs] == ["FeatureTable"]


def test_feature_table_records_the_real_contract_digest():
    table = {
        "columns": ["Sharpness"],
        "contract_digest": USFIQA_CONTRACT_DIGEST,
        "column_order_significant": True,
        "produced_by": None,
        "storage": "csv",
        "path": "features.csv",
    }
    assert is_valid("FeatureTable", table)
    assert not is_valid("FeatureTable", {**table, "column_order_significant": False})
    assert not is_valid("FeatureTable", {**table, "contract_digest": "not-a-digest"})
