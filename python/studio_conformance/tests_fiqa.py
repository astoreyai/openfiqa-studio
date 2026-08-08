"""Conformance tests for a FIQA implementation (P10 T05).

Each test checks something observable about a real run. None of them checks conformance to a
published specification, because no published specification has been read into this repository —
see the caveat in `profiles/local-fiqa-behaviour.yaml`.

What they do check is worth checking anyway: that an implementation is deterministic, bounded,
honest about failure, and that its provenance is complete enough to re-derive a result. Those are
the properties a conformance assessment would rest on before it ever reached clause-by-clause work.
"""

from __future__ import annotations

from typing import Any

from studio_conformance.runner import (
    BLOCKED,
    FAIL,
    PASS,
    WARNING,
    ConformanceRunner,
    TestOutcome,
)
from studio_conformance.profile import Requirement

runner = ConformanceRunner()


@runner.register("component_count")
def component_count(requirement: Requirement, context: dict[str, Any]) -> TestOutcome:
    """The implementation returns the expected number of quality components."""
    vector = context["quality_vector"]
    actual = len(vector["components"])
    expected = requirement.expected
    if actual == expected:
        return TestOutcome(PASS, f"{actual} components", {"count": actual})
    return TestOutcome(
        FAIL, f"expected {expected} components, got {actual}", {"count": actual}
    )


@runner.register("scalar_bounds")
def scalar_bounds(requirement: Requirement, context: dict[str, Any]) -> TestOutcome:
    """Every computed scalar lies within the declared range.

    Components the engine could not assess are excluded — they carry `computed: false`, and
    counting them as out-of-range would penalise honest reporting of a failure to assess.
    """
    vector = context["quality_vector"]
    low, high = requirement.expected
    offenders = [
        {"name": c["name"], "scalar": c["scalar"]}
        for c in vector["components"]
        if c["computed"] and c["scalar"] is not None and not (low <= c["scalar"] <= high)
    ]
    if offenders:
        return TestOutcome(
            FAIL, f"{len(offenders)} component(s) outside [{low}, {high}]", {"offenders": offenders}
        )
    computed = sum(1 for c in vector["components"] if c["computed"])
    return TestOutcome(PASS, f"all {computed} computed scalars within [{low}, {high}]")


@runner.register("failure_sentinel_not_scored")
def failure_sentinel_not_scored(_: Requirement, context: dict[str, Any]) -> TestOutcome:
    """A component that could not be assessed must not carry a numeric score.

    OFIQ signals this with (raw 0, scalar -1). A -1 left in a score column reads as very poor
    quality to every mean, axis and threshold downstream.
    """
    vector = context["quality_vector"]
    leaked = [
        c["name"]
        for c in vector["components"]
        if not c["computed"] and c["scalar"] is not None
    ]
    negative = [c["name"] for c in vector["components"] if (c["scalar"] or 0) < 0]
    if leaked or negative:
        return TestOutcome(
            FAIL,
            f"unassessed components carrying scores: {leaked or negative}",
            {"leaked": leaked, "negative": negative},
        )
    unassessed = [c["name"] for c in vector["components"] if not c["computed"]]
    return TestOutcome(
        PASS,
        f"{len(unassessed)} unassessed component(s) correctly carry no score",
        {"unassessed": unassessed},
    )


@runner.register("determinism")
def determinism(_: Requirement, context: dict[str, Any]) -> TestOutcome:
    """The same input yields the same output.

    Non-determinism does not make an implementation wrong, but it makes every reproduction verdict
    meaningless, so it is reported as a failure of this profile rather than a warning.
    """
    repeats = context.get("repeat_vectors")
    if not repeats or len(repeats) < 2:
        return TestOutcome(BLOCKED, "fewer than two runs were supplied to compare")

    signatures = [
        tuple((c["name"], c["scalar"], c["computed"]) for c in v["components"]) for v in repeats
    ]
    if len(set(signatures)) == 1:
        return TestOutcome(PASS, f"{len(repeats)} runs produced identical component values")
    return TestOutcome(
        FAIL, f"{len(set(signatures))} distinct outputs across {len(repeats)} identical runs"
    )


@runner.register("provenance_completeness")
def provenance_completeness(requirement: Requirement, context: dict[str, Any]) -> TestOutcome:
    """Every field needed to re-derive the result is present and non-null."""
    engine = context["quality_vector"]["engine"]
    required = requirement.expected or ["engine_id", "version", "commit"]
    missing = [field for field in required if not engine.get(field)]
    if missing:
        return TestOutcome(FAIL, f"missing provenance: {missing}", {"engine": engine})
    return TestOutcome(PASS, f"all of {required} present", {"engine": engine})


@runner.register("external_dependency_declared")
def external_dependency_declared(_: Requirement, context: dict[str, Any]) -> TestOutcome:
    """If the implementation loads config or weights from another repository, it must say so.

    ofiqpy reads its config and every model weight from an OFIQ-Project checkout. A result is
    therefore a function of two commits, and recording only one under-specifies the run.
    """
    describe = context.get("describe", {})
    weights_source = describe.get("weights_source")
    weights_commit = describe.get("ofiq_project_commit")
    if weights_source and not weights_commit:
        return TestOutcome(
            FAIL, f"weights loaded from {weights_source} but the supplying commit is not recorded"
        )
    if weights_source:
        return TestOutcome(
            PASS,
            f"external weight source declared with commit {weights_commit[:12]}",
            {"weights_source": weights_source, "commit": weights_commit},
        )
    return TestOutcome(WARNING, "no external data dependency declared; unverified")


@runner.register("state_not_overclaimed")
def state_not_overclaimed(_: Requirement, context: dict[str, Any]) -> TestOutcome:
    """A freshly computed result must be COMPUTED, not VALIDATED or CONFORMANT."""
    vector = context["quality_vector"]
    state = vector.get("state")
    if state != "COMPUTED":
        return TestOutcome(
            FAIL, f"a fresh adapter result claims state {state!r}; it should be COMPUTED"
        )
    unified = vector.get("unified")
    if unified and unified.get("state") != "COMPUTED":
        return TestOutcome(FAIL, f"unified score claims state {unified.get('state')!r}")
    return TestOutcome(PASS, "result and unified score are COMPUTED")


@runner.register("polarity_not_laundered")
def polarity_not_laundered(_: Requirement, context: dict[str, Any]) -> TestOutcome:
    """While the upstream polarity map is known wrong for 10 of 27 components, an implementation
    must not present a polarity it cannot justify."""
    vector = context["quality_vector"]
    claimed = {
        c["name"]: c["raw_polarity"]
        for c in vector["components"]
        if c["raw_polarity"] != "unknown" and not c.get("polarity_map_revision")
    }
    if claimed:
        return TestOutcome(
            FAIL,
            f"{len(claimed)} component(s) claim a polarity with no map revision recorded",
            {"components": sorted(claimed)},
        )
    return TestOutcome(PASS, "no unjustified polarity claims")
