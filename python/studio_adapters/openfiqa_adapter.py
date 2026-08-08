"""OpenFIQA adapter (P04 B05).

Turns `openfiqa assess` output into a `QualityVector`.

**This engine is DEGRADED, not AVAILABLE.** It runs, but two conditions make its output less
trustworthy than a clean run, and both are recorded rather than hidden:

- **CUDA unavailable.** The workspace venv carries `torch 2.13.0+cu130`; this machine's driver
  reports 12020. Left to itself the CLI raises in `torch._C._cuda_init()`, so the adapter forces
  `--device cpu`. CPU and GPU paths are not guaranteed to produce identical values.
- **Cross-version model unpickle.** The C08 Sharpness head is a `RandomForestClassifier` pickled
  under scikit-learn 1.8.0 and loaded under 1.9.0. scikit-learn's own warning says this "might
  lead to breaking code or invalid results".

openfiqa reports components as codes `C01`–`C28`, not names. They are **not** joined to ofiqpy's
named components: no verified mapping between the two vocabularies exists in this repository, and
inventing one would silently align measurements that may not correspond.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from studio_adapters import paths
from studio_adapters.base import (
    Adapter,
    AdapterFailed,
    AdapterResult,
    git_commit,
    sha256_file,
)

RUNNER = Path(__file__).resolve().parent / "runners" / "openfiqa_runner.py"
DEFAULT_TIMEOUT_S = 900


class OpenfiqaAdapter(Adapter):
    plugin_id = "openfiqa"

    def __init__(self, timeout_s: int = DEFAULT_TIMEOUT_S):
        self.timeout_s = timeout_s

    # ------------------------------------------------------------------ runtime detection

    def _venv_python(self) -> Path | None:
        root = paths.get("openfiqa_workspace", required=False)
        if root is None:
            return None
        candidate = root / ".venv" / "bin" / "python"
        return candidate if candidate.exists() else None

    def _cli(self) -> Path | None:
        root = paths.get("openfiqa_workspace", required=False)
        if root is None:
            return None
        candidate = root / ".venv" / "bin" / "openfiqa"
        return candidate if candidate.exists() else None

    def available(self) -> tuple[bool, str | None]:
        if self._venv_python() is None or self._cli() is None:
            return False, (
                "openfiqa CLI not found — set OFS_OPENFIQA_WORKSPACE to a checkout containing "
                ".venv/bin/openfiqa"
            )
        return True, None

    def describe(self) -> dict[str, Any]:
        root = paths.get("openfiqa_workspace", required=False)
        return {
            "plugin_id": self.plugin_id,
            "cli": str(self._cli()) if self._cli() else None,
            "workspace_commit": git_commit(root) if root else None,
            "device": "cpu",
            "degraded_because": [
                "CUDA unavailable: venv torch is cu130, system driver reports 12020",
                "C08 Sharpness head unpickled across a scikit-learn version boundary (1.8.0 -> 1.9.0)",
            ],
        }

    # ------------------------------------------------------------------ execution

    def run(self, image_path: str | Path) -> AdapterResult:
        self.require_available()
        image = Path(image_path)
        if not image.exists():
            raise AdapterFailed(f"image not found: {image}", exit_code=-1, stderr="")

        interpreter = self._venv_python()
        cli = self._cli()
        assert interpreter is not None and cli is not None
        argv = [str(interpreter), str(RUNNER), str(cli), str(image)]

        started = time.monotonic()
        process = subprocess.run(
            argv, capture_output=True, text=True, env={**os.environ}, timeout=self.timeout_s
        )
        duration = time.monotonic() - started

        if process.returncode != 0:
            raise AdapterFailed(
                f"openfiqa exited {process.returncode}",
                exit_code=process.returncode,
                stderr=process.stderr,
            )

        try:
            payload = json.loads(process.stdout)
        except json.JSONDecodeError as exc:
            raise AdapterFailed(
                f"openfiqa produced unparseable output: {exc}",
                exit_code=process.returncode,
                stderr=process.stderr,
            ) from exc

        result = AdapterResult(
            typed=self._to_quality_vector(payload, image),
            raw_stdout=process.stdout,
            raw_stderr=process.stderr,
            exit_code=process.returncode,
            argv=argv,
            env={"device": "cpu"},
            duration_s=duration,
        )
        result.validate("QualityVector")
        return result

    # ------------------------------------------------------------------ typing

    def _to_quality_vector(self, payload: dict[str, Any], image: Path) -> dict[str, Any]:
        described = self.describe()
        scores = payload.get("quality_scores", {}) or {}

        components = [
            {
                "name": code,          # C01..C28, deliberately NOT renamed to ofiqpy's vocabulary
                "raw": None,           # openfiqa reports only the scaled score
                "scalar": float(value) if value is not None and value >= 0 else None,
                "computed": value is not None and value >= 0,
                "failure_sentinel": value if (value is not None and value < 0) else None,
                "raw_polarity": "unknown",
                "polarity_map_revision": None,
            }
            for code, value in sorted(scores.items())
        ]

        engine = {
            "engine_id": "openfiqa",
            "version": None,           # the CLI does not report it in the assess payload
            "commit": described["workspace_commit"],
            "runtime": "cpu (CUDA unavailable — see degraded_because)",
            "config_digest": None,
        }

        unified = None
        if payload.get("unified_score") is not None:
            unified = {
                "value": float(payload["unified_score"]),
                "engine": engine,
                "semantics": {
                    # A DIFFERENT quantity from ofiqpy.UnifiedQualityScore. Sharing an id would be
                    # the exact conflation the type system exists to prevent.
                    "definition_id": "openfiqa.unified_score",
                    "range": [0, 100],
                    "direction": "higher_is_better",
                    "standard": None,
                    "standard_version": None,
                },
                "state": "COMPUTED",
            }

        return {
            "sample_id": sha256_file(image),
            "engine": engine,
            "components": components,
            "unified": unified,
            "raw_output": None,
            "state": "COMPUTED",
        }
