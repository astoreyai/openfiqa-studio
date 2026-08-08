# ADR-0006 — Provenance is a queryable DAG, not a log

**Status:** accepted 2026-08-07 · **Prompt:** P02 A06

## Decision

Provenance is stored as typed relationships between artifacts — `DERIVED_FROM`,
`TRANSFORMED_FROM`, `GENERATED_BY`, `EVALUATED_BY`, `TRAINED_FROM`, `USES_MODEL`, `USES_DATASET`,
`USES_CONFIG`, `VISUALIZED_FROM`, `PUBLISHED_AS`, `REPRODUCES` — and is traversable in both
directions. No result may be an orphan.

## Why

A log answers "what happened". T&E requirement 38 asks a harder question: given this figure, show
me the samples behind it, and given this sample, show me every published claim it supports. Only
the second direction catches "this figure includes a subject we later lost authorization for".

## Consequences

- Writing an artifact without its edges is a validation failure, not a warning.
- The polarity-map revision (B-P01-03) is a provenance field, so scores computed through the
  defective map remain identifiable after it is fixed.
- Provenance queries must work offline against the local store.
