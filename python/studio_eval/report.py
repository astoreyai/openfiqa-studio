"""Cross-engine study reporting.

Turns a paired score table into a statement that says what the sample size supports and no more.

The rule this module exists to enforce: a correlation is reported with its standard error and an
explicit interpretability verdict, or it is not reported. A bare coefficient invites a reader to
treat n=5 and n=500 identically, and at n=5 the estimate is close to noise.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from studio_eval.cross_engine import (
    MIN_INTERPRETABLE_N,
    EngineSeries,
    compare,
    spearman,
    spearman_standard_error,
)


def load_rows(path: str | Path) -> list[dict[str, Any]]:
    return json.loads(Path(path).read_text())


def summarise(rows: list[dict[str, Any]], left_key: str, right_key: str,
              left_definition: str, right_definition: str) -> dict[str, Any]:
    """Paired summary of two score columns.

    Rows missing either score are reported, never silently dropped: dropping them would summarise a
    different population than the one the caller sampled.
    """
    complete = [r for r in rows if r.get(left_key) is not None and r.get(right_key) is not None]
    dropped = len(rows) - len(complete)

    left = EngineSeries(left_key, left_definition, [float(r[left_key]) for r in complete])
    right = EngineSeries(right_key, right_definition, [float(r[right_key]) for r in complete])
    result = compare(left, right, method="rank")

    def describe(values: list[float]) -> dict[str, float]:
        ordered = sorted(values)
        n = len(ordered)
        return {
            "min": ordered[0],
            "median": ordered[n // 2] if n % 2 else (ordered[n // 2 - 1] + ordered[n // 2]) / 2,
            "max": ordered[-1],
            "mean": sum(ordered) / n,
        }

    return {
        "n": result.n,
        "rows_dropped_for_missing_scores": dropped,
        "spearman": result.statistic,
        "standard_error": result.standard_error,
        "interpretable": result.interpretable,
        "min_interpretable_n": MIN_INTERPRETABLE_N,
        "distributions": {left_key: describe(left.values), right_key: describe(right.values)},
        "overlap": _overlap(left.values, right.values),
        "caveats": result.caveats,
        "asserts_numeric_equivalence": False,
    }


def _overlap(a: list[float], b: list[float]) -> dict[str, Any]:
    """Do the two score distributions occupy the same region at all?

    More robust at small n than a correlation: it needs no pairing assumption, only the ranges.
    """
    lo = max(min(a), min(b))
    hi = min(max(a), max(b))
    if hi < lo:
        return {"ranges_disjoint": True, "gap": lo - hi}
    span = max(max(a), max(b)) - min(min(a), min(b))
    return {
        "ranges_disjoint": False,
        "overlap_width": hi - lo,
        "fraction_of_combined_span": (hi - lo) / span if span else 0.0,
    }


def to_markdown(summary: dict[str, Any], title: str) -> str:
    verdict = (
        "interpretable" if summary["interpretable"]
        else f"NOT interpretable (n < {summary['min_interpretable_n']})"
    )
    lines = [
        f"# {title}",
        "",
        f"**n = {summary['n']}**"
        + (f" ({summary['rows_dropped_for_missing_scores']} rows lacked a score)"
           if summary["rows_dropped_for_missing_scores"] else ""),
        "",
        f"Spearman rank correlation **{summary['spearman']:+.3f}** "
        f"(SE ≈ {summary['standard_error']:.3f}) — {verdict}.",
        "",
        "| engine | min | median | mean | max |",
        "|---|---|---|---|---|",
    ]
    for name, stats in summary["distributions"].items():
        lines.append(
            f"| {name} | {stats['min']:.1f} | {stats['median']:.1f} | "
            f"{stats['mean']:.1f} | {stats['max']:.1f} |"
        )
    overlap = summary["overlap"]
    lines += ["", "## Range overlap", ""]
    if overlap["ranges_disjoint"]:
        lines.append(
            f"The two score ranges are **disjoint**, separated by {overlap['gap']:.1f} points. "
            "No image is rated in a comparable band by both engines."
        )
    else:
        lines.append(
            f"The ranges overlap over {overlap['overlap_width']:.1f} points, "
            f"{overlap['fraction_of_combined_span']:.0%} of their combined span."
        )
    lines += ["", "## Caveats", ""] + [f"- {c}" for c in summary["caveats"]]
    lines += [
        "",
        "These are `COMPUTED` values. Nothing here has been validated, reproduced by a third "
        "party, or checked against a recognition outcome — the question of whether either score "
        "predicts biometric failure needs a matcher, which this workspace does not have "
        "(B-P04-08).",
    ]
    return "\n".join(lines) + "\n"


__all__ = ["load_rows", "summarise", "to_markdown", "spearman", "spearman_standard_error"]
