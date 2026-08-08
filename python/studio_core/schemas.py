"""Schema loading and validation for OpenFIQA Studio.

JSON Schema in ``packages/schemas`` is the single source of truth for the scientific type system.
Python and TypeScript both derive from it; neither defines these shapes independently. That is what
satisfies the P02 gate requirement that frontend and backend types cannot silently diverge.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

SCHEMA_ROOT = Path(__file__).resolve().parents[2] / "packages" / "schemas"
PLUGIN_ROOT = SCHEMA_ROOT / "plugins"

SCIENTIFIC_OBJECTS = "scientific-objects.schema.json"
PLUGIN = "plugin.schema.json"


def load_schema(name: str) -> dict[str, Any]:
    """Read one schema document by filename."""
    return json.loads((SCHEMA_ROOT / name).read_text())


def load_plugin_manifests() -> dict[str, dict[str, Any]]:
    """Read every plugin manifest, keyed by plugin_id."""
    manifests = {}
    for path in sorted(PLUGIN_ROOT.glob("*.plugin.json")):
        manifest = json.loads(path.read_text())
        manifests[manifest["plugin_id"]] = manifest
    return manifests


def validator_for(name: str) -> Draft202012Validator:
    """Build a validator for a whole schema document."""
    schema = load_schema(name)
    return Draft202012Validator(schema)


def definition_validator(defn: str) -> Draft202012Validator:
    """Build a validator for one ``$defs`` entry of the scientific-objects schema.

    The full ``$defs`` block is carried into the subschema so that internal ``$ref`` pointers such
    as ``#/$defs/EngineRef`` resolve locally. Nothing is fetched over the network — the studio must
    validate offline, and a validator that silently reached for ``$id`` would break air-gapped use.
    """
    schema = load_schema(SCIENTIFIC_OBJECTS)
    if defn not in schema["$defs"]:
        raise KeyError(f"no such definition: {defn}")
    subschema = dict(schema["$defs"][defn])
    subschema["$defs"] = schema["$defs"]
    return Draft202012Validator(subschema)


def is_valid(defn: str, instance: Any) -> bool:
    """True when ``instance`` satisfies the named scientific-object definition."""
    return definition_validator(defn).is_valid(instance)


def errors_for(defn: str, instance: Any) -> list[str]:
    """Human-readable validation errors, empty when the instance is valid."""
    validator = definition_validator(defn)
    return [e.message for e in validator.iter_errors(instance)]


def blocked_plugins() -> dict[str, str]:
    """Plugins the registry must refuse to execute, mapped to their blocker id.

    A blocked engine stays listed with its reason. It is never hidden from the registry and never
    reported as working — that is the difference between an honest gap and a fabricated capability.
    """
    return {
        pid: m["availability"]["blocker_id"]
        for pid, m in load_plugin_manifests().items()
        if m["availability"]["state"] == "BLOCKED"
    }
