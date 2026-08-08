"""Adapter harness (P04 B02).

An adapter turns one engine's native output into a typed scientific object, and records enough
provenance that the result can be re-derived. The harness fixes what every adapter must do:

- detect its runtime and refuse honestly when it is missing;
- report version and source, including any repository other than its own that supplied weights;
- preserve the raw output before parsing it;
- emit a typed object that validates against the schema;
- surface a failure as a failure, never as a default value.

The last point is the one that matters scientifically. An adapter that returns 0.0 when an engine
fails produces a number that looks like a measurement, and it will be averaged into a figure by
something downstream that has no way to know it was invented.
"""

from __future__ import annotations

import abc
import hashlib
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from studio_core.schemas import errors_for  # noqa: E402


class AdapterUnavailable(RuntimeError):
    """The engine cannot be run here. Carries the reason, never a substitute result."""


class AdapterFailed(RuntimeError):
    """The engine ran and failed. Carries its exit code and stderr."""

    def __init__(self, message: str, *, exit_code: int, stderr: str):
        self.exit_code = exit_code
        self.stderr = stderr
        super().__init__(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit(repo: Path) -> str | None:
    """Full commit of a repository, or None when it cannot be determined.

    None is a legitimate answer and is preferable to a plausible-looking wrong one — provenance
    that records the wrong commit is worse than provenance that admits it does not know.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() or None if result.returncode == 0 else None


@dataclass
class AdapterResult:
    """A typed engine output plus everything needed to re-derive it."""

    typed: dict[str, Any]
    raw_stdout: str
    raw_stderr: str
    exit_code: int
    argv: list[str]
    env: dict[str, str]
    duration_s: float
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def validate(self, definition: str) -> None:
        errors = errors_for(definition, self.typed)
        if errors:
            raise AdapterFailed(
                f"adapter emitted an object that does not satisfy {definition}: {errors}",
                exit_code=self.exit_code,
                stderr=self.raw_stderr,
            )


class Adapter(abc.ABC):
    """Base class for every engine adapter.

    Declared abstract rather than raising NotImplementedError in placeholder bodies: `abc` enforces
    the contract at instantiation, so an incomplete adapter cannot be constructed at all — there is
    no half-built object to accidentally call.
    """

    plugin_id: str

    @abc.abstractmethod
    def available(self) -> tuple[bool, str | None]:
        """(True, None) when the engine can run here, else (False, reason)."""

    @abc.abstractmethod
    def describe(self) -> dict[str, Any]:
        """Runtime and provenance facts, gathered by inspection rather than assumed."""

    def require_available(self) -> None:
        ok, reason = self.available()
        if not ok:
            raise AdapterUnavailable(reason or f"{self.plugin_id} is unavailable")
