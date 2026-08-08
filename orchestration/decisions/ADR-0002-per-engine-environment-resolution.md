# ADR-0002 — Engines run in their own environments, never in the control plane

**Status:** accepted 2026-08-07 · **Prompt:** P02 A09 · **Resolves:** B-P01-06

## Decision

No engine is imported into the control-plane interpreter. Every engine runs as a subprocess under
its own resolved environment, declared in its plugin manifest under `implementation.environment`.
`python_inprocess` remains in the schema but is legal only for a plugin that imports cleanly in the
control plane's own environment — which no current engine does.

## Why

This was forced by measurement, not preference. `import ofiqpy` fails under the system interpreter;
the OpenFIQA workspace runs its own Python 3.11.2 with `torch 2.13.0+cu130`. A single shared
interpreter cannot host both without dependency conflict, and pretending otherwise would surface as
an import error halfway through building adapters.

## Consequences

- Adapters are subprocess or CLI based. Cost: serialisation overhead per call. Accepted.
- The environment is part of provenance from the first run, not retrofitted later.
- A missing environment is a plugin `availability` problem, reported honestly, not a crash.
- Engine crashes are isolated from the control plane.
