# ADR-0004 — JSON Schema is the source of truth for the scientific type system

**Status:** accepted 2026-08-07 · **Prompt:** P02 A02/A04

## Decision

`packages/schemas/*.json` defines the scientific types. Python and TypeScript both derive from it.
Neither side may define these shapes independently. Workflow graphs serialise to YAML whose node
ports reference these types by name.

## Why

The P02 gate requires that frontend and backend types cannot silently diverge. Two hand-maintained
type definitions always diverge eventually, and the divergence shows up as a chart that renders a
field the backend stopped sending.

The type system also encodes what P01 disproved, so the disproved model is unrepresentable:

- `EngineScore` has no bare-number form — a float cannot carry which engine produced it.
- `FeatureTable` is a distinct type from `QualityVector`, so an extractor cannot be wired straight
  into US-FIQA, skipping the feature-engineering stage that does not yet exist.
- `CrossEngineComparison.asserts_numeric_equivalence` is pinned `false`.

## Consequences

- A schema change is a deliberate, reviewable act with a test suite behind it.
- Adding a type means adding it to the schema first, then regenerating both sides.
- The negative tests in `tests/test_schemas.py` fail if a future edit reopens a disproved shape.
