"""ADR-0004 enforcement — the frontend's types must not drift from the schemas.

The P02 handoff recorded this as a known risk: divergence was "prevented by policy rather than by
a build step". Policy means someone has to remember. This makes it mechanical — edit a schema
without regenerating and the suite fails.

The generator earned its place immediately: it revealed that `prefixItems` (JSON Schema 2020-12
tuple syntax) compiled to `never[]`, so the frontend's type for a score range was silently wrong
while every other gate was green.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
GENERATED = REPO / "apps" / "desktop" / "src" / "generated" / "schema-types.ts"
SCHEMA_DIR = REPO / "packages" / "schemas"

node = shutil.which("node")
needs_node = pytest.mark.skipif(
    node is None or not (REPO / "node_modules").exists(),
    reason="node and an installed workspace are required to check generated types",
)


@needs_node
def test_generated_types_are_not_stale():
    """Fails when packages/schemas has changed since the types were last generated."""
    result = subprocess.run(
        [node, "scripts/generate-types.mjs", "--check"],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, (
        f"generated types are stale — run `pnpm generate:types`\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


def _code_only(text: str) -> str:
    """Strip block comments so assertions inspect emitted code, not prose.

    Needed because the schema descriptions quote the very TypeScript this module asserts against —
    the first version of `test_score_range_is_a_tuple_not_never` failed on its own documentation.
    """
    out, i, n = [], 0, len(text)
    while i < n:
        if text.startswith("/*", i):
            end = text.find("*/", i)
            i = n if end == -1 else end + 2
            continue
        if text.startswith("//", i):
            end = text.find("\n", i)
            i = n if end == -1 else end
            continue
        out.append(text[i])
        i += 1
    return "".join(out)


def test_every_scientific_definition_reaches_the_frontend():
    """A type defined in the schema but absent from the generated file is a silent divergence.

    Object definitions emit as `interface`; enum definitions such as ScientificState emit as a
    `type` alias, so both forms count as present.
    """
    assert GENERATED.exists(), "generated types missing — run `pnpm generate:types`"
    emitted = GENERATED.read_text()
    schema = json.loads((SCHEMA_DIR / "scientific-objects.schema.json").read_text())
    missing = [
        name
        for name in schema["$defs"]
        if f"export interface {name}" not in emitted and f"export type {name}" not in emitted
    ]
    assert not missing, f"not emitted to TypeScript: {missing}"


def test_score_range_is_a_tuple_not_never():
    """Regression for the prefixItems defect.

    `never[]` accepts only an empty array, so a frontend assigning a real [min, max] would have
    failed type-checking — or worse, the field would have been quietly unusable.
    """
    code = _code_only(GENERATED.read_text())
    assert "range?: [number, number]" in code
    assert "never[]" not in code


def test_generated_file_is_marked_do_not_edit():
    assert "DO NOT EDIT" in GENERATED.read_text()
