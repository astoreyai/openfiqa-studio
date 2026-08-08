"""Runs inside ofiqpy's own interpreter, not the control plane's.

ADR-0002 forbids importing an engine into the control plane, so this script is the whole of what
executes in the engine's environment. It must depend on nothing but the standard library and
``ofiqpy`` — the control plane's packages are not importable here.

Contract: argv[1] is an image path. On success, prints one JSON object to stdout and exits 0.
On failure, prints a JSON object with an ``error`` key and exits non-zero. It never prints a
partial or invented result.
"""

import json
import sys


def main() -> int:
    if len(sys.argv) != 2:
        print(json.dumps({"error": "usage: ofiqpy_runner.py <image-path>"}), file=sys.stderr)
        return 2

    image_path = sys.argv[1]

    try:
        import ofiqpy
    except Exception as exc:  # noqa: BLE001 - report any import failure verbatim
        print(json.dumps({"error": f"import ofiqpy failed: {exc}"}), file=sys.stderr)
        return 3

    try:
        result = ofiqpy.assess(image_path)
    except Exception as exc:  # noqa: BLE001 - the engine's failure is the result
        print(json.dumps({"error": f"assess failed: {type(exc).__name__}: {exc}"}), file=sys.stderr)
        return 4

    # An empty mapping is ofiqpy's documented "no face detected". It is a real outcome, not an
    # error, and must reach the caller as such rather than being turned into a zero score.
    components = {name: [value[0], value[1]] for name, value in result.items()}

    print(
        json.dumps(
            {
                "components": components,
                "n_components": len(components),
                "face_detected": len(components) > 0,
                "engine_version": getattr(ofiqpy, "__version__", None),
                "python": sys.version.split()[0],
            }
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
