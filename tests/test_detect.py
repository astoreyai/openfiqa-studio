"""P05 I08 — face detection and landmarks.

The overlay cannot be inspected on this headless machine, so correctness has to be argued
structurally. Two things carry that weight: preprocessing is delegated to the library that owns
the model rather than reimplemented, and every detection is checked against geometric invariants
before it reaches the UI.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "python"))

from studio_adapters import paths  # noqa: E402
from studio_adapters.base import AdapterFailed  # noqa: E402
from studio_adapters.detect_adapter import DetectAdapter, geometry_is_consistent  # noqa: E402
from studio_adapters.runners.detect_runner import extract_json  # noqa: E402
from studio_backend.app import create_app  # noqa: E402

needs_detector = pytest.mark.skipif(
    not (paths.available("openfiqa_workspace") and paths.available("lfw_root")),
    reason="detector workspace and corpus must be configured",
)


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(workspace=tmp_path / "workspace")) as c:
        yield c


@pytest.fixture(scope="module")
def detection() -> dict:
    if not (paths.available("openfiqa_workspace") and paths.available("lfw_root")):
        pytest.skip("detector or corpus not configured")
    face = paths.get("lfw_root") / "Michael_Phelps" / "Michael_Phelps_0001.jpg"
    return DetectAdapter().run(face)


def _face(bbox=(10, 10, 90, 110), landmarks=None):
    x0, y0, x1, y1 = bbox
    return {
        "bbox": [x0, y0, x1, y1],
        "det_score": 0.9,
        # left eye, right eye, nose, left mouth, right mouth
        "keypoints": [[30, 40], [70, 40], [50, 65], [35, 90], [65, 90]],
        "landmarks_106": landmarks if landmarks is not None else [[50, 60]] * 106,
    }


def _payload(faces=None, width=200, height=200):
    return {
        "image_width": width, "image_height": height,
        "detections": faces if faces is not None else [_face()],
    }


# ---------------------------------------------------------------- geometry invariants

def test_a_well_formed_detection_is_consistent():
    ok, problems = geometry_is_consistent(_payload())
    assert ok, problems


def test_bbox_outside_the_image_is_caught():
    ok, problems = geometry_is_consistent(_payload([_face(bbox=(10, 10, 500, 110))]))
    assert not ok
    assert any("not inside the image" in p for p in problems)


def test_eyes_below_the_nose_are_caught():
    """The canonical vertical ordering is the cheapest signal that an overlay is upside down or
    that coordinates were mapped from the wrong space."""
    face = _face()
    face["keypoints"] = [[30, 80], [70, 80], [50, 65], [35, 90], [65, 90]]
    ok, problems = geometry_is_consistent(_payload([face]))
    assert not ok
    assert any("eyes are not above the nose" in p for p in problems)


def test_mouth_above_the_nose_is_caught():
    face = _face()
    face["keypoints"] = [[30, 40], [70, 40], [50, 95], [35, 60], [65, 60]]
    ok, problems = geometry_is_consistent(_payload([face]))
    assert not ok
    assert any("nose is not above the mouth" in p for p in problems)


def test_mirrored_eyes_are_caught():
    face = _face()
    face["keypoints"] = [[70, 40], [30, 40], [50, 65], [35, 90], [65, 90]]
    ok, problems = geometry_is_consistent(_payload([face]))
    assert not ok
    assert any("left eye is not left" in p for p in problems)


def test_landmarks_far_from_the_bbox_are_caught():
    """The failure mode of guessed preprocessing: points that look like a face somewhere else."""
    ok, problems = geometry_is_consistent(_payload([_face(landmarks=[[1000, 1000]] * 106)]))
    assert not ok
    assert any("landmarks near the bbox" in p for p in problems)


def test_wrong_keypoint_count_is_caught():
    face = _face()
    face["keypoints"] = [[30, 40], [70, 40]]
    ok, problems = geometry_is_consistent(_payload([face]))
    assert not ok
    assert any("expected 5 keypoints" in p for p in problems)


# ---------------------------------------------------------------- output extraction

def test_json_is_extracted_from_a_log_polluted_stream():
    """insightface writes model-load lines to stdout, so the payload lives in the tail."""
    stream = 'Applied providers: [...]\nfind model: /x/y.onnx\n{"image_width": 1, "detections": []}'
    assert extract_json(stream)["image_width"] == 1


def test_a_stream_with_no_json_returns_none_rather_than_a_partial():
    """A half-built detection would put an overlay somewhere confidently wrong."""
    assert extract_json("Applied providers: [...]\nno payload here\n") is None
    assert extract_json("{ this is not valid json") is None


# ---------------------------------------------------------------- real detection

@needs_detector
def test_real_detection_passes_every_geometric_invariant(detection):
    assert detection["n_faces"] == 1
    ok, problems = geometry_is_consistent(detection)
    assert ok, problems

    face = detection["detections"][0]
    assert len(face["keypoints"]) == 5
    assert len(face["landmarks_106"]) == 106
    assert 0.0 < face["det_score"] <= 1.0
    assert len(face["pose_pitch_yaw_roll"]) == 3


@needs_detector
def test_coordinates_are_in_original_image_pixels(detection):
    """Returning them in an internal crop space and letting the caller map back is how an overlay
    ends up confidently misplaced."""
    width, height = detection["image_width"], detection["image_height"]
    assert (width, height) == (250, 250)  # LFW funneled

    x0, y0, x1, y1 = detection["detections"][0]["bbox"]
    assert 0 <= x0 < x1 <= width
    assert 0 <= y0 < y1 <= height
    # A face should occupy a meaningful fraction of a funneled LFW crop, not a few pixels.
    assert (x1 - x0) * (y1 - y0) > 0.05 * width * height


@needs_detector
def test_detection_is_not_typed_as_a_quality_vector(detection):
    """Geometry is not a measurement of quality. Typing it as one would let it flow into places
    that average scores."""
    assert "components" not in detection
    assert "unified" not in detection
    assert "state" not in detection


@needs_detector
def test_endpoint_reports_the_geometry_verdict(client):
    src = client.get("/api/samples?limit=1").json()["samples"][0]["path"]
    body = client.post("/api/samples/detect", json={"image_path": src}).json()
    assert body["geometry_consistent"] is True
    assert body["geometry_problems"] == []
    assert body["describe"]["preprocessing"].startswith("delegated to insightface")


@needs_detector
def test_detecting_a_file_outside_the_corpus_is_refused(client):
    assert client.post(
        "/api/samples/detect", json={"image_path": "/etc/hosts"}
    ).status_code == 403


@needs_detector
def test_a_missing_image_fails_rather_than_returning_an_empty_detection():
    with pytest.raises(AdapterFailed):
        DetectAdapter().run("/nonexistent/face.jpg")
