"""Cross-engine comparison (P04 B11).

Two engines' scores may only be compared by an explicitly named method. There is no default,
because the default people reach for — compare the raw numbers — is the invalid one.

`ofiqpy.UnifiedQualityScore` and `openfiqa.unified_score` are different quantities with different
definitions. Both happen to be 0–100 and higher-is-better, which is exactly what makes conflating
them easy: the numbers look commensurable and are not.

Rank correlation is offered because it needs only a shared ordering, not a shared scale. Its
sampling error is reported alongside it, because a correlation quoted without one at small n is a
number that will be believed more than it deserves.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

METHODS = (
    "raw_side_by_side",
    "rank",
    "percentile",
    "standardized",
    "calibrated_mapping",
    "correlation",
    "downstream_utility",
)


class ComparisonError(ValueError):
    """The comparison as requested is not valid."""


def _ranks(values: list[float]) -> list[float]:
    """Ranks with ties averaged."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        average = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = average
        i = j + 1
    return ranks


def spearman(x: list[float], y: list[float]) -> float:
    if len(x) != len(y):
        raise ComparisonError("series must be the same length")
    if len(x) < 3:
        raise ComparisonError("rank correlation needs at least 3 paired observations")
    rx, ry = _ranks(x), _ranks(y)
    n = len(x)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    den = math.sqrt(sum((r - mx) ** 2 for r in rx) * sum((r - my) ** 2 for r in ry))
    if den == 0:
        raise ComparisonError("a series has zero rank variance; correlation is undefined")
    return num / den


def spearman_standard_error(n: int) -> float:
    """Approximate standard error, 1/sqrt(n-1).

    Reported with every correlation. At n=5 this is 0.5, which is the honest way of saying the
    estimate cannot distinguish strong agreement from strong disagreement.
    """
    if n < 3:
        raise ComparisonError("need at least 3 observations")
    return 1.0 / math.sqrt(n - 1)


@dataclass
class EngineSeries:
    engine_id: str
    definition_id: str
    values: list[float]
    sample_ids: list[str] = field(default_factory=list)


@dataclass
class ComparisonResult:
    method: str
    engines: list[str]
    definition_ids: list[str]
    n: int
    statistic: float | None
    standard_error: float | None
    ranges: dict[str, tuple[float, float]]
    interpretable: bool
    caveats: list[str]
    # Pinned false. No comparison may claim engine scores are numerically equivalent.
    asserts_numeric_equivalence: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "engines": self.engines,
            "definition_ids": self.definition_ids,
            "n": self.n,
            "statistic": self.statistic,
            "standard_error": self.standard_error,
            "ranges": {k: list(v) for k, v in self.ranges.items()},
            "interpretable": self.interpretable,
            "caveats": self.caveats,
            "asserts_numeric_equivalence": self.asserts_numeric_equivalence,
        }

    def summary(self) -> str:
        if self.statistic is None:
            return f"{self.method} over n={self.n}: no statistic computed"
        confidence = (
            "" if self.interpretable
            else " — NOT INTERPRETABLE at this sample size"
        )
        return (
            f"{self.method} over n={self.n}: {self.statistic:+.2f} "
            f"(SE ~{self.standard_error:.2f}){confidence}"
        )


# Below this, a rank correlation's standard error exceeds a third of the full [-1, 1] range and the
# estimate cannot separate agreement from disagreement.
MIN_INTERPRETABLE_N = 20


def compare(
    left: EngineSeries, right: EngineSeries, *, method: str = "rank"
) -> ComparisonResult:
    if method not in METHODS:
        raise ComparisonError(f"unknown method {method!r}; expected one of {METHODS}")
    if left.definition_id == right.definition_id:
        raise ComparisonError(
            "both series carry the same definition_id; a cross-engine comparison needs two "
            "distinct quantities"
        )
    if method == "raw_side_by_side":
        raise ComparisonError(
            "raw_side_by_side produces no statistic by design — it exists so a viewer can show "
            "two columns without implying they are commensurable"
        )
    if len(left.values) != len(right.values):
        raise ComparisonError("series must be the same length")

    n = len(left.values)
    caveats: list[str] = []
    statistic: float | None = None
    standard_error: float | None = None

    if method in {"rank", "correlation"}:
        statistic = spearman(left.values, right.values)
        standard_error = spearman_standard_error(n)

    interpretable = n >= MIN_INTERPRETABLE_N
    if not interpretable:
        caveats.append(
            f"n={n} is below {MIN_INTERPRETABLE_N}; the standard error "
            f"({standard_error:.2f}) spans most of the possible range, so this statistic cannot "
            f"distinguish agreement from disagreement"
        )
    caveats.append(
        f"{left.definition_id} and {right.definition_id} are different quantities; this "
        f"comparison uses '{method}' and asserts no numeric equivalence"
    )

    return ComparisonResult(
        method=method,
        engines=[left.engine_id, right.engine_id],
        definition_ids=[left.definition_id, right.definition_id],
        n=n,
        statistic=statistic,
        standard_error=standard_error,
        ranges={
            left.engine_id: (min(left.values), max(left.values)),
            right.engine_id: (min(right.values), max(right.values)),
        },
        interpretable=interpretable,
        caveats=caveats,
    )


def series_from_vectors(vectors: list[dict[str, Any]]) -> EngineSeries:
    """Build a series from QualityVectors, refusing to mix engines or skip missing scores."""
    if not vectors:
        raise ComparisonError("no vectors supplied")
    engines = {v["engine"]["engine_id"] for v in vectors}
    if len(engines) != 1:
        raise ComparisonError(f"vectors come from more than one engine: {sorted(engines)}")

    definitions = {v["unified"]["semantics"]["definition_id"] for v in vectors if v.get("unified")}
    if len(definitions) != 1:
        raise ComparisonError(f"vectors carry more than one score definition: {sorted(definitions)}")

    missing = [v["sample_id"] for v in vectors if not v.get("unified")
               or v["unified"]["value"] is None]
    if missing:
        raise ComparisonError(
            f"{len(missing)} sample(s) have no unified score; dropping them would compare a "
            f"different population than the caller asked for"
        )

    return EngineSeries(
        engine_id=engines.pop(),
        definition_id=definitions.pop(),
        values=[float(v["unified"]["value"]) for v in vectors],
        sample_ids=[v["sample_id"] for v in vectors],
    )
