"""Golden reference vectors (P10 T04, and T&E requirements 16–17).

A golden vector pins an implementation's output on a known input, so that a later version changing
that output is *detected* rather than discovered by a reader wondering why a number moved.

Two rules make this worth having:

**The image is identified by content hash, never by path.** A vector keyed on a filename silently
follows whatever bytes end up at that name.

**Recording a vector is not blessing it.** `expected` is what the implementation produced at
capture time, not what it ought to produce. A vector captured from a defective implementation
faithfully reproduces the defect — which is why every vector carries the commit that produced it
and any blocker open against it. openfiqa's C08 is the live example: it can be pinned, and the
pinning must not read as endorsement.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

MATCH = "MATCH"
DRIFT = "DRIFT"
MISSING = "MISSING"
NEW = "NEW"


@dataclass
class GoldenVector:
    vector_id: str
    image_sha256: str
    engine_id: str
    engine_commit: str | None
    captured_at: str
    expected: dict[str, float | None]
    tolerance: dict[str, float] = field(default_factory=dict)
    default_tolerance: float = 0.0
    # Blockers open against the implementation when this vector was captured.
    known_blockers: list[str] = field(default_factory=list)
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "vector_id": self.vector_id,
            "image_sha256": self.image_sha256,
            "engine_id": self.engine_id,
            "engine_commit": self.engine_commit,
            "captured_at": self.captured_at,
            "expected": self.expected,
            "tolerance": self.tolerance,
            "default_tolerance": self.default_tolerance,
            "known_blockers": self.known_blockers,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GoldenVector":
        return cls(**data)

    def tolerance_for(self, feature: str) -> float:
        """Per-feature tolerance.

        Never one global epsilon: components differ in scale and in how they degrade, so a single
        threshold is either too loose for the stable ones or too tight for the noisy ones.
        """
        return self.tolerance.get(feature, self.default_tolerance)


@dataclass
class FeatureComparison:
    feature: str
    verdict: str
    expected: float | None
    actual: float | None
    delta: float | None
    tolerance: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature": self.feature,
            "verdict": self.verdict,
            "expected": self.expected,
            "actual": self.actual,
            "delta": self.delta,
            "tolerance": self.tolerance,
        }


@dataclass
class VectorCheck:
    vector_id: str
    engine_id: str
    captured_commit: str | None
    current_commit: str | None
    features: list[FeatureComparison]
    known_blockers: list[str] = field(default_factory=list)

    @property
    def drifted(self) -> list[FeatureComparison]:
        return [f for f in self.features if f.verdict == DRIFT]

    @property
    def passed(self) -> bool:
        return not any(f.verdict in {DRIFT, MISSING} for f in self.features)

    def to_dict(self) -> dict[str, Any]:
        return {
            "vector_id": self.vector_id,
            "engine_id": self.engine_id,
            "captured_commit": self.captured_commit,
            "current_commit": self.current_commit,
            "passed": self.passed,
            "drifted": len(self.drifted),
            "known_blockers": self.known_blockers,
            "features": [f.to_dict() for f in self.features],
        }

    def summary(self) -> str:
        if self.passed:
            same = "same commit" if self.captured_commit == self.current_commit else (
                f"commit changed {(self.captured_commit or '?')[:12]} -> "
                f"{(self.current_commit or '?')[:12]}"
            )
            return f"{self.vector_id}: MATCH across {len(self.features)} features ({same})"
        return (
            f"{self.vector_id}: {len(self.drifted)} feature(s) drifted "
            f"({', '.join(f.feature for f in self.drifted[:5])})"
        )


def capture(
    vector_id: str,
    quality_vector: dict[str, Any],
    *,
    captured_at: str,
    tolerance: dict[str, float] | None = None,
    default_tolerance: float = 0.0,
    known_blockers: list[str] | None = None,
    note: str | None = None,
) -> GoldenVector:
    """Pin an engine's current output on one image.

    Components the engine could not assess are recorded as None, not zero — the sentinel rule
    applies here too, and a zero would make an unassessed component look like a measured one that
    later "improved".
    """
    engine = quality_vector["engine"]
    expected: dict[str, float | None] = {
        component["name"]: component["scalar"] if component["computed"] else None
        for component in quality_vector["components"]
    }
    unified = quality_vector.get("unified")
    if unified:
        expected["__unified__"] = unified["value"]

    return GoldenVector(
        vector_id=vector_id,
        image_sha256=quality_vector["sample_id"],
        engine_id=engine["engine_id"],
        engine_commit=engine.get("commit"),
        captured_at=captured_at,
        expected=expected,
        tolerance=tolerance or {},
        default_tolerance=default_tolerance,
        known_blockers=known_blockers or [],
        note=note,
    )


def check(vector: GoldenVector, quality_vector: dict[str, Any]) -> VectorCheck:
    """Compare a fresh run against a pinned one."""
    if quality_vector["sample_id"] != vector.image_sha256:
        raise ValueError(
            f"vector {vector.vector_id} pins image {vector.image_sha256[:12]} but was checked "
            f"against {quality_vector['sample_id'][:12]}"
        )

    actual: dict[str, float | None] = {
        component["name"]: component["scalar"] if component["computed"] else None
        for component in quality_vector["components"]
    }
    unified = quality_vector.get("unified")
    if unified:
        actual["__unified__"] = unified["value"]

    comparisons: list[FeatureComparison] = []
    for feature, expected_value in vector.expected.items():
        tol = vector.tolerance_for(feature)
        if feature not in actual:
            comparisons.append(
                FeatureComparison(feature, MISSING, expected_value, None, None, tol)
            )
            continue
        actual_value = actual[feature]
        if expected_value is None and actual_value is None:
            comparisons.append(FeatureComparison(feature, MATCH, None, None, None, tol))
        elif expected_value is None or actual_value is None:
            # One side unassessed and the other measured is drift, not a match. The engine's
            # ability to assess the component changed, which is exactly what this catches.
            comparisons.append(
                FeatureComparison(feature, DRIFT, expected_value, actual_value, None, tol)
            )
        else:
            delta = abs(actual_value - expected_value)
            verdict = MATCH if delta <= tol else DRIFT
            comparisons.append(
                FeatureComparison(feature, verdict, expected_value, actual_value, delta, tol)
            )

    for feature in actual:
        if feature not in vector.expected:
            comparisons.append(FeatureComparison(feature, NEW, None, actual[feature], None, 0.0))

    return VectorCheck(
        vector_id=vector.vector_id,
        engine_id=vector.engine_id,
        captured_commit=vector.engine_commit,
        current_commit=quality_vector["engine"].get("commit"),
        features=comparisons,
        known_blockers=vector.known_blockers,
    )


class VectorStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def write(self, vectors: list[GoldenVector]) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(
                {"format": "openfiqa-golden-vectors/1",
                 "vectors": [v.to_dict() for v in vectors]},
                indent=2,
            )
        )
        return self.path

    def read(self) -> list[GoldenVector]:
        data = json.loads(self.path.read_text())
        return [GoldenVector.from_dict(v) for v in data["vectors"]]
