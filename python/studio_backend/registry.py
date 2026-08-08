"""Plugin registry.

Reads the manifests in ``packages/schemas/plugins`` and validates every one against the plugin
contract before serving it. Per ADR-0003 the registry reports engines it cannot run: a BLOCKED
plugin is listed with its blocker id and reason and refuses execution. It is never hidden, and it
is never presented as working.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from studio_core.schemas import PLUGIN, load_plugin_manifests, validator_for  # noqa: E402

EXECUTABLE_STATES = {"AVAILABLE", "DEGRADED"}


class RegistryError(RuntimeError):
    """A manifest failed validation. The registry refuses to serve an invalid contract."""


class PluginNotExecutable(RuntimeError):
    """Execution was requested for a plugin whose availability forbids it."""

    def __init__(self, plugin_id: str, state: str, blocker_id: str | None, reason: str | None):
        self.plugin_id = plugin_id
        self.state = state
        self.blocker_id = blocker_id
        self.reason = reason
        super().__init__(f"{plugin_id} is {state}" + (f" ({blocker_id})" if blocker_id else ""))


class PluginRegistry:
    def __init__(self) -> None:
        self._manifests: dict[str, dict[str, Any]] = {}
        self.reload()

    def reload(self) -> None:
        manifests = load_plugin_manifests()
        validator = validator_for(PLUGIN)
        for plugin_id, manifest in manifests.items():
            errors = [e.message for e in validator.iter_errors(manifest)]
            if errors:
                raise RegistryError(f"{plugin_id}: {errors}")
        self._manifests = manifests

    def all(self) -> list[dict[str, Any]]:
        return [self._summary(m) for m in self._manifests.values()]

    def get(self, plugin_id: str) -> dict[str, Any] | None:
        manifest = self._manifests.get(plugin_id)
        return dict(manifest) if manifest else None

    def executable(self) -> list[str]:
        return [
            pid
            for pid, m in self._manifests.items()
            if m["availability"]["state"] in EXECUTABLE_STATES
        ]

    def assert_executable(self, plugin_id: str) -> dict[str, Any]:
        """Raise unless this plugin may actually run.

        The check happens here rather than at the call site so that no execution path can skip it.
        """
        manifest = self._manifests.get(plugin_id)
        if manifest is None:
            raise KeyError(plugin_id)
        availability = manifest["availability"]
        if availability["state"] not in EXECUTABLE_STATES:
            raise PluginNotExecutable(
                plugin_id,
                availability["state"],
                availability.get("blocker_id"),
                availability.get("reason"),
            )
        return manifest

    @staticmethod
    def _summary(manifest: dict[str, Any]) -> dict[str, Any]:
        availability = manifest["availability"]
        return {
            "plugin_id": manifest["plugin_id"],
            "name": manifest["name"],
            "version": manifest["version"],
            "kind": manifest["kind"],
            "mode": manifest["implementation"]["mode"],
            "inputs": [p["type"] for p in manifest["ports"]["inputs"]],
            "outputs": [p["type"] for p in manifest["ports"]["outputs"]],
            "capabilities": manifest["capabilities"],
            "availability": {
                "state": availability["state"],
                "blocker_id": availability.get("blocker_id"),
                "reason": availability.get("reason"),
                "verified_by": availability.get("verified_by"),
            },
            "executable": availability["state"] in EXECUTABLE_STATES,
            "provenance": manifest["provenance"],
        }
