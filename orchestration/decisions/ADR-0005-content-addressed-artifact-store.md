# ADR-0005 — Artifacts are content-addressed; biometric bytes are referenced, not copied

**Status:** accepted 2026-08-07 · **Prompt:** P02 A08

## Decision

Every artifact carries a sha256 of its content and is addressed by it. Biometric image bytes stay
where they are on disk and are referenced by path plus hash. Metadata lives in SQLite; large
tabular output in Parquet; interactive queries via DuckDB.

## Why

Content addressing is what makes "this figure came from these exact bytes" checkable rather than
asserted, and it is the mechanism behind reproduction verdicts in P09.

Not copying image bytes is a privacy decision as much as a storage one. A studio that copies
biometric samples into its own store multiplies the number of places a restricted sample lives, and
every copy is a place it can leak from.

## Consequences

- Moving or editing a source image invalidates its hash and is detected rather than silently used.
- The artifact store can be inspected, diffed, and garbage-collected without parsing formats.
- Datasets of 80 GB are referenced in place. Storage cost stays with the dataset owner.
