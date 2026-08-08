"""Runs inside the OpenFIQA workspace interpreter.

Depends only on the standard library and the `openfiqa` CLI, per ADR-0002.

Two environment facts force choices here:

- the workspace venv carries ``torch 2.13.0+cu130`` while this machine's NVIDIA driver reports
  12020, so ``torch._C._cuda_init()`` raises. ``--device cpu`` is passed explicitly rather than
  left to a default that happens to work.
- the CLI writes its JSON to stdout *after* insightface's provider logs, so the payload has to be
  extracted from the tail rather than parsed from the whole stream.
"""

import json
import subprocess
import sys


def extract_json(text):
    """Return the trailing JSON object from a stream that also carries log lines.

    Scans backwards for the last line that starts an object and parses from there. Returning None
    on failure is deliberate: a partial parse would hand the caller a half-built result that looks
    like a measurement.
    """
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.strip().startswith("{"):
            candidate = "\n".join(lines[index:])
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue
    return None


def main():
    if len(sys.argv) < 3:
        print(json.dumps({"error": "usage: openfiqa_runner.py <cli> <image>"}), file=sys.stderr)
        return 2

    cli, image_path = sys.argv[1], sys.argv[2]
    process = subprocess.run(
        [cli, "assess", image_path, "--format", "json", "--device", "cpu"],
        capture_output=True,
        text=True,
    )

    if process.returncode != 0:
        print(json.dumps({"error": f"openfiqa exited {process.returncode}",
                          "stderr": process.stderr[-2000:]}), file=sys.stderr)
        return process.returncode

    payload = extract_json(process.stdout)
    if payload is None:
        print(json.dumps({"error": "no JSON object found in openfiqa stdout",
                          "stdout_tail": process.stdout[-500:]}), file=sys.stderr)
        return 5

    # Surface the runtime warnings verbatim. The sklearn cross-version unpickle warning is a real
    # reproducibility concern for the C08 head and must not be swallowed.
    payload["_stderr_warnings"] = [
        line for line in process.stderr.splitlines()
        if "Warning" in line or "warn" in line.lower()
    ][:20]
    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    sys.exit(main())
