"""OFIQpy adapter (P04 B04).

Runs ofiqpy in its own interpreter and turns the result into a `QualityVector`.

Two facts from discovery shape this adapter:

**B-P01-09** — ofiqpy is not standalone. It loads `ofiq_config.jaxn` and every model weight from an
OFIQ-Project checkout, via `OFIQPY_OFIQ_DATA`, falling back to a CWD-relative path. So a result
here is a function of *two* commits, and both are recorded. Setting the variable is not
configuration; without it `assess()` raises `FileNotFoundError`.

**B-P01-03** — the polarity of raw component values is mis-declared upstream for 10 of 27
components. This adapter therefore records `raw_polarity: "unknown"` for every component rather
than copying a map known to be wrong. The 0–100 scalar is reported as measured; the raw value is
preserved but not interpreted.
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

RUNNER = Path(__file__).resolve().parent / "runners" / "ofiqpy_runner.py"
DEFAULT_TIMEOUT_S = 300


class OfiqpyAdapter(Adapter):
    plugin_id = "ofiqpy"

    def __init__(self, timeout_s: int = DEFAULT_TIMEOUT_S):
        self.timeout_s = timeout_s

    # ------------------------------------------------------------------ runtime detection

    def _venv_python(self) -> Path | None:
        root = paths.get("ofiqpy_root", required=False)
        if root is None:
            return None
        candidate = root / ".venv" / "bin" / "python"
        return candidate if candidate.exists() else None

    def _ofiq_data(self) -> Path | None:
        root = paths.get("ofiq_project_root", required=False)
        if root is None:
            return None
        data = root / "data"
        return data if (data / "ofiq_config.jaxn").exists() else None

    def available(self) -> tuple[bool, str | None]:
        if self._venv_python() is None:
            return False, (
                "ofiqpy interpreter not found — set OFS_OFIQPY_ROOT to a checkout containing "
                ".venv/bin/python"
            )
        if self._ofiq_data() is None:
            return False, (
                "OFIQ-Project data/ not found (B-P01-09) — ofiqpy loads its config and weights "
                "from an OFIQ-Project checkout; set OFS_OFIQ_PROJECT_ROOT"
            )
        return True, None

    def describe(self) -> dict[str, Any]:
        ofiqpy_root = paths.get("ofiqpy_root", required=False)
        ofiq_root = paths.get("ofiq_project_root", required=False)
        return {
            "plugin_id": self.plugin_id,
            "interpreter": str(self._venv_python()) if self._venv_python() else None,
            "ofiqpy_commit": git_commit(ofiqpy_root) if ofiqpy_root else None,
            # Recorded because the weights come from here, not from ofiqpy (B-P01-09).
            "ofiq_project_commit": git_commit(ofiq_root) if ofiq_root else None,
            "weights_source": str(self._ofiq_data()) if self._ofiq_data() else None,
            "weights_license": "BSI terms — separate from ofiqpy's MIT",
        }

    # ------------------------------------------------------------------ execution

    def run(self, image_path: str | Path) -> AdapterResult:
        self.require_available()
        image = Path(image_path)
        if not image.exists():
            raise AdapterFailed(f"image not found: {image}", exit_code=-1, stderr="")

        interpreter = self._venv_python()
        assert interpreter is not None  # guarded by require_available
        env_overrides = {"OFIQPY_OFIQ_DATA": str(self._ofiq_data())}
        argv = [str(interpreter), str(RUNNER), str(image)]

        started = time.monotonic()
        process = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            env={**os.environ, **env_overrides},
            timeout=self.timeout_s,
        )
        duration = time.monotonic() - started

        if process.returncode != 0:
            raise AdapterFailed(
                f"ofiqpy exited {process.returncode}",
                exit_code=process.returncode,
                stderr=process.stderr,
            )

        try:
            payload = json.loads(process.stdout)
        except json.JSONDecodeError as exc:
            raise AdapterFailed(
                f"ofiqpy produced unparseable output: {exc}",
                exit_code=process.returncode,
                stderr=process.stderr,
            ) from exc

        typed = self._to_quality_vector(payload, image)
        result = AdapterResult(
            typed=typed,
            raw_stdout=process.stdout,
            raw_stderr=process.stderr,
            exit_code=process.returncode,
            argv=argv,
            env=env_overrides,
            duration_s=duration,
        )
        result.validate("QualityVector")
        return result

    # ------------------------------------------------------------------ typing

    @staticmethod
    def _component(name: str, raw: float | None, scalar: float | None) -> dict[str, Any]:
        """Turn one (raw, scalar) tuple into a typed component.

        OFIQ signals "could not assess" with the FailureToAssess sentinel — ofiqpy's own
        ``output.py`` defines it as ``(0.0, -1.0)``. That -1 must never reach a score column: a
        mean, a chart axis or a threshold would read it as very poor quality rather than as a
        missing measurement, and the error would be invisible because -1 is a plausible-looking
        number. It is converted to ``scalar: null`` with ``computed: false``, and preserved in
        ``failure_sentinel`` for audit.
        """
        failed = scalar is not None and scalar < 0
        return {
            "name": name,
            "raw": raw,
            "scalar": None if failed else scalar,
            "computed": not failed,
            "failure_sentinel": scalar if failed else None,
            # Not copied from the upstream polarity map: it is wrong for 10 of 27 components
            # (B-P01-03). "unknown" is the honest reading until that is fixed.
            "raw_polarity": "unknown",
            "polarity_map_revision": None,
        }

    def _to_quality_vector(self, payload: dict[str, Any], image: Path) -> dict[str, Any]:
        described = self.describe()
        components = [
            self._component(name, raw, scalar)
            for name, (raw, scalar) in sorted(payload["components"].items())
        ]

        engine = {
            "engine_id": "ofiqpy",
            "version": payload.get("engine_version"),
            "commit": described["ofiqpy_commit"],
            "runtime": f"python {payload.get('python')}",
            # Distinguishes two runs that share an ofiqpy commit but differ in weights.
            "config_digest": described["ofiq_project_commit"],
        }

        unified = None
        if "UnifiedQualityScore" in payload["components"]:
            _, scalar = payload["components"]["UnifiedQualityScore"]
            # Same sentinel rule as the components, and it matters more here: this is the single
            # number a reader is most likely to quote or plot.
            unified = {
                "value": None if (scalar is not None and scalar < 0) else scalar,
                "engine": engine,
                "semantics": {
                    "definition_id": "ofiqpy.UnifiedQualityScore",
                    "range": [0, 100],
                    "direction": "higher_is_better",
                    "standard": "iso-29794-5",
                    "standard_version": None,
                },
                # COMPUTED only. Nothing here has been validated, reproduced, or checked for
                # conformance, and the adapter has no authority to claim otherwise.
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
