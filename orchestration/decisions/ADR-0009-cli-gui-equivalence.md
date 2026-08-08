# ADR-0009 — One canonical workflow definition; the GUI is a client of it

**Status:** accepted 2026-08-07 · **Prompt:** P02 A07/A04

## Decision

The visual graph and the CLI execute the same serialised workflow definition through the same
compiler and scheduler. The GUI constructs and inspects that definition; it does not have a private
execution path. Interactive preview and batch execution call the identical transform implementation.

## Why

The studio's claim is reproducibility. A GUI with its own execution path produces results nobody
else can rerun, and the divergence is invisible until someone tries. Making the GUI a client of the
same definition means "run it from the CLI" is a test, not a porting exercise.

Preview and batch sharing one implementation is the same argument at sample scale: a preview that
approximates the real transform silently teaches the researcher the wrong thing.

## Consequences

- `openfiqa-studio run workflow.yaml` and pressing Run must produce equivalent artifacts for
  deterministic settings, and that equivalence is a gate.
- Any GUI-only convenience that changes numerical behaviour is a defect.
