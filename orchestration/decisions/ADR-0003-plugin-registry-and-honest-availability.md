# ADR-0003 — Capabilities are declared, validated, and may be BLOCKED

**Status:** accepted 2026-08-07 · **Prompt:** P02 A03

## Decision

Every executable capability enters through a manifest validated against `plugin.schema.json`. The
registry never infers a capability that was not declared. `availability.state` is one of
`AVAILABLE | DEGRADED | BLOCKED | UNVERIFIED`, and `BLOCKED` or `DEGRADED` requires both a
`blocker_id` pointing into `orchestration/blockers.md` and a human-readable reason.

## Why

Two of four engines cannot run today and a third has never processed a sample. A registry with only
a working/absent distinction would have to either hide them or lie about them. Neither is
acceptable: hiding loses the information that the engine exists and why it is unavailable, and
lying produces a UI affordance that fails at the worst moment.

`capabilities` fields accept the literal `"unknown"` for the same reason. P01 could not determine
whether ofiqpy supports batch or GPU. `"unknown"` is the true answer; `false` would be a fabrication.

## Consequences

- The registry lists blocked engines with their reason and refuses to execute them.
- `test_no_plugin_claims_to_be_available` fails the build if a manifest claims AVAILABLE while
  B-P04-00 is open.
- Clearing a blocker is a manifest edit plus an evidence entry, not a silent state change.
