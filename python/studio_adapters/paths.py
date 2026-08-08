"""Where the engines live on this machine.

Engine locations are machine-specific and one of the repositories is not publicly released, so
they are never hard-coded here. Resolution order:

1. environment variables — ``OFS_OFIQPY_ROOT``, ``OFS_OFIQ_PROJECT_ROOT``, ``OFS_LFW_ROOT``
2. ``config/local-paths.yaml`` — gitignored; see ``config/local-paths.example.yaml``

A missing path is reported as a plain unavailability, never guessed at. An adapter that guessed a
path would fail later with a confusing error instead of saying which variable to set.
"""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LOCAL_PATHS = REPO_ROOT / "config" / "local-paths.yaml"

_KEYS = {
    "ofiqpy_root": "OFS_OFIQPY_ROOT",
    "ofiq_project_root": "OFS_OFIQ_PROJECT_ROOT",
    "lfw_root": "OFS_LFW_ROOT",
}


class PathNotConfigured(RuntimeError):
    def __init__(self, key: str):
        self.key = key
        super().__init__(
            f"{key} is not configured. Set the {_KEYS[key]} environment variable, or add "
            f"`{key}:` to {LOCAL_PATHS} (see config/local-paths.example.yaml)."
        )


def _from_file() -> dict[str, str]:
    """Read the local overrides file.

    Parsed with a two-line scanner rather than a YAML dependency: this file is a flat
    ``key: /path`` mapping, and the control plane should not need PyYAML to locate an engine.
    """
    if not LOCAL_PATHS.exists():
        return {}
    values: dict[str, str] = {}
    for line in LOCAL_PATHS.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, _, value = line.partition(":")
        value = value.strip().strip('"').strip("'")
        if value:
            values[key.strip()] = value
    return values


def get(key: str, *, required: bool = True) -> Path | None:
    if key not in _KEYS:
        raise KeyError(key)
    raw = os.environ.get(_KEYS[key]) or _from_file().get(key)
    if not raw:
        if required:
            raise PathNotConfigured(key)
        return None
    return Path(raw).expanduser()


def available(key: str) -> bool:
    path = get(key, required=False)
    return path is not None and path.exists()
