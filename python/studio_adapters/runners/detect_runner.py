"""Face detection and landmarks (P05 I08).

Runs in the OpenFIQA workspace interpreter, which has insightface and the buffalo_l models.

**Preprocessing is delegated, not reimplemented.** ADNet is available in the OFIQ-Project tree, but
writing its input pipeline from inspection would produce landmarks that land plausibly and are
wrong — and this machine is headless, so nobody could look at the overlay and notice. insightface
carries its own detector and aligner, so the geometry comes from the library that owns it.

Coordinates are returned in ORIGINAL image pixels. Returning them in some internal crop space and
letting the caller map back is how an overlay ends up confidently misplaced.
"""

import json
import sys

_APP = None


def extract_json(text):
    """Return the trailing JSON object from a stream that also carries library log lines.

    insightface prints provider and model-load lines to stdout, so the payload cannot be parsed
    from the whole stream. Returning None on failure rather than a partial parse: a half-built
    detection would put an overlay somewhere confidently wrong.
    """
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.strip().startswith("{"):
            try:
                return json.loads("\n".join(lines[index:]))
            except json.JSONDecodeError:
                continue
    return None


def _analyser():
    global _APP
    if _APP is None:
        from insightface.app import FaceAnalysis

        app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
        app.prepare(ctx_id=-1, det_size=(640, 640))
        _APP = app
    return _APP


def main():
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage: detect_runner.py <image>"}), file=sys.stderr)
        return 2

    image_path = sys.argv[1]
    try:
        import cv2

        image = cv2.imread(image_path)
        if image is None:
            print(json.dumps({"error": f"could not read image: {image_path}"}), file=sys.stderr)
            return 3
        height, width = image.shape[:2]
        faces = _analyser().get(image)
    except Exception as exc:  # noqa: BLE001 - the failure is the result
        print(json.dumps({"error": f"{type(exc).__name__}: {exc}"}), file=sys.stderr)
        return 4

    detections = []
    for face in faces:
        entry = {
            "bbox": [float(v) for v in face.bbox],
            "det_score": float(face.det_score),
            # Five canonical keypoints: left eye, right eye, nose, left mouth, right mouth.
            "keypoints": [[float(x), float(y)] for x, y in face.kps],
        }
        landmarks = getattr(face, "landmark_2d_106", None)
        if landmarks is not None:
            entry["landmarks_106"] = [[float(x), float(y)] for x, y in landmarks]
        pose = getattr(face, "pose", None)
        if pose is not None:
            entry["pose_pitch_yaw_roll"] = [float(v) for v in pose]
        detections.append(entry)

    # Sorted largest first, so "the face" is a stable choice rather than detector order.
    detections.sort(key=lambda d: (d["bbox"][2] - d["bbox"][0]) * (d["bbox"][3] - d["bbox"][1]),
                    reverse=True)

    print(json.dumps({
        "image_width": width,
        "image_height": height,
        "n_faces": len(detections),
        "detections": detections,
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
