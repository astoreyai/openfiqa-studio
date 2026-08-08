"""Which plugin ids have a working adapter.

Deliberately sparse. Only ofiqpy has one, because only ofiqpy has been shown to run here:

- ``ofiq_project`` is frozen behind B-P01-04 (44 unpreserved paths)
- ``ofiq_quality`` is blocked by B-P01-01 and B-P01-02 (no packaged producer for its 47-column
  input, and no conforming model directory)
- ``openfiqa`` now HAS an adapter. Its weights turned out to be present in the workspace already —
  the earlier note that they had never been fetched was wrong. It is DEGRADED, not AVAILABLE: it
  runs only on CPU because the venv's CUDA build does not match this machine's driver

Returning ``None`` for those is the honest answer, and the API turns it into a 501 that names the
gap rather than a result that implies one exists.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from studio_adapters import paths
from studio_adapters.base import Adapter
from studio_adapters.ofiqpy_adapter import RUNNER, OfiqpyAdapter
from studio_adapters.openfiqa_adapter import OpenfiqaAdapter

_ADAPTERS: dict[str, type[Adapter]] = {
    "ofiqpy": OfiqpyAdapter,
    "openfiqa": OpenfiqaAdapter,
}


def get_adapter(plugin_id: str) -> Adapter | None:
    factory = _ADAPTERS.get(plugin_id)
    return factory() if factory else None


def implemented() -> list[str]:
    return sorted(_ADAPTERS)


def adapter_run_spec(plugin_id: str, image_path: str) -> dict[str, Any] | None:
    """argv and env to execute this adapter's engine through the run system.

    The streaming path invokes the same runner script the adapter does, in the same interpreter
    with the same environment, so the two paths cannot drift into different results.
    """
    if plugin_id != "ofiqpy":
        return None
    ofiqpy_root = paths.get("ofiqpy_root", required=False)
    ofiq_root = paths.get("ofiq_project_root", required=False)
    if ofiqpy_root is None or ofiq_root is None:
        return None
    interpreter = ofiqpy_root / ".venv" / "bin" / "python"
    if not interpreter.exists():
        return None
    return {
        "argv": [str(interpreter), str(RUNNER), str(Path(image_path))],
        "env": {"OFIQPY_OFIQ_DATA": str(ofiq_root / "data")},
    }
