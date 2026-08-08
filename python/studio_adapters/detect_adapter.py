"""Face detection and landmark adapter (P05 I08).

Wraps insightface's buffalo_l detector, running in the OpenFIQA workspace interpreter per ADR-0002.

This is not a quality engine and does not emit a `QualityVector`. It produces geometry — a box,
five canonical keypoints, 106 landmarks and a head pose — which the Image Lab draws over the
sample. Keeping it out of the quality type system matters: a landmark set is not a measurement of
quality, and giving it a QualityVector would let it flow into places that average scores.

Every returned coordinate is in ORIGINAL image pixels.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from studio_adapters import paths
from studio_adapters.base import AdapterFailed
from studio_adapters.runners.detect_runner import extract_json

RUNNER = Path(__file__).resolve().parent / "runners" / "detect_runner.py"
DEFAULT_TIMEOUT_S = 300


class DetectAdapter:
    plugin_id = "insightface_detect"

    def __init__(self, timeout_s: int = DEFAULT_TIMEOUT_S):
        self.timeout_s = timeout_s

    def _venv_python(self) -> Path | None:
        root = paths.get("openfiqa_workspace", required=False)
        if root is None:
            return None
        candidate = root / ".venv" / "bin" / "python"
        return candidate if candidate.exists() else None

    def available(self) -> tuple[bool, str | None]:
        if self._venv_python() is None:
            return False, (
                "detector interpreter not found — set OFS_OPENFIQA_WORKSPACE to a checkout whose "
                ".venv has insightface"
            )
        models = Path.home() / ".insightface" / "models" / "buffalo_l"
        if not (models / "det_10g.onnx").exists():
            return False, f"insightface buffalo_l models not found under {models}"
        return True, None

    def describe(self) -> dict[str, Any]:
        return {
            "plugin_id": self.plugin_id,
            "detector": "insightface buffalo_l (det_10g)",
            "landmarks": "2d106det, 106 points",
            "preprocessing": "delegated to insightface — not reimplemented from ADNet",
            "coordinate_space": "original image pixels",
        }

    def run(self, image_path: str | Path) -> dict[str, Any]:
        ok, reason = self.available()
        if not ok:
            raise AdapterFailed(reason or "detector unavailable", exit_code=-1, stderr="")

        image = Path(image_path)
        if not image.exists():
            raise AdapterFailed(f"image not found: {image}", exit_code=-1, stderr="")

        interpreter = self._venv_python()
        assert interpreter is not None
        argv = [str(interpreter), str(RUNNER), str(image)]

        started = time.monotonic()
        process = subprocess.run(
            argv, capture_output=True, text=True, env={**os.environ}, timeout=self.timeout_s
        )
        duration = time.monotonic() - started

        if process.returncode != 0:
            raise AdapterFailed(
                f"detector exited {process.returncode}",
                exit_code=process.returncode,
                stderr=process.stderr,
            )

        payload = extract_json(process.stdout)
        if payload is None:
            raise AdapterFailed(
                "detector produced no JSON object",
                exit_code=process.returncode,
                stderr=process.stderr[-2000:],
            )
        payload["duration_s"] = round(duration, 3)
        payload["describe"] = self.describe()
        return payload


def geometry_is_consistent(payload: dict[str, Any]) -> tuple[bool, list[str]]:
    """Structural checks on a detection.

    This machine is headless, so nobody can look at an overlay and notice it is in the wrong place.
    These checks are the substitute: a box inside the image, keypoints inside the box, and the
    canonical vertical ordering eyes → nose → mouth. They cannot prove the landmarks are accurate,
    only that the geometry is not obviously broken.
    """
    problems: list[str] = []
    width, height = payload["image_width"], payload["image_height"]

    for index, face in enumerate(payload["detections"]):
        x0, y0, x1, y1 = face["bbox"]
        if not (0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height):
            problems.append(f"face {index}: bbox is not inside the image")

        keypoints = face["keypoints"]
        if len(keypoints) != 5:
            problems.append(f"face {index}: expected 5 keypoints, got {len(keypoints)}")
            continue
        left_eye, right_eye, nose, left_mouth, right_mouth = keypoints
        if (left_eye[1] + right_eye[1]) / 2 >= nose[1]:
            problems.append(f"face {index}: eyes are not above the nose")
        if nose[1] >= (left_mouth[1] + right_mouth[1]) / 2:
            problems.append(f"face {index}: nose is not above the mouth")
        if left_eye[0] >= right_eye[0]:
            problems.append(f"face {index}: left eye is not left of the right eye")

        landmarks = face.get("landmarks_106") or []
        if landmarks:
            # Contour points legitimately sit slightly outside the box, so this is a majority
            # check rather than a containment requirement.
            inside = sum(
                1 for x, y in landmarks if x0 - 5 <= x <= x1 + 5 and y0 - 5 <= y <= y1 + 5
            )
            if inside < 0.9 * len(landmarks):
                problems.append(
                    f"face {index}: only {inside}/{len(landmarks)} landmarks near the bbox"
                )

    return (not problems), problems
