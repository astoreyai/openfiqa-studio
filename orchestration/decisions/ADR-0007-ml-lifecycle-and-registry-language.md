# ADR-0007 — Model registry states describe evidence, never operational approval

**Status:** accepted 2026-08-07 · **Prompt:** P02 A07

## Decision

Registry states are `EXPERIMENTAL | CANDIDATE | VALIDATED | ARCHIVED`. No label implies
certification, accreditation, or operational approval. Unsuccessful HPO trials are preserved with
their configuration. An exported ONNX model is not equivalent to its source until compared on a
registered fixture within a declared tolerance.

## Why

This product is aimed partly at conformance and T&E readers, which makes vocabulary a safety issue.
A registry that says "APPROVED" will eventually be screenshotted into a slide, and the studio has
no authority to approve anything. `VALIDATED` means specific evidence exists and is linked; it does
not mean anyone accepted it.

Preserving failed trials matters because a search reported only by its winner is unfalsifiable.

## Consequences

- P12 final statuses top out at `VALIDATED_RESEARCH_RELEASE`.
- Export equivalence is a measured claim with a fixture and a tolerance, not a property of exporting.
