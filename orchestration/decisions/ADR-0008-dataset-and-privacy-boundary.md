# ADR-0008 — Classification is mandatory and export is default-deny

**Status:** accepted 2026-08-07 · **Prompt:** P02 A09

## Decision

Every sample carries `classification` ∈ `PUBLIC | RESTRICTED | PRIVATE | SYNTHETIC | GENERATED`, a
required field. Anything other than `PUBLIC` requires a non-null `authorization` before P05 may
import it. Publication and evidence export scan for restricted material and refuse by default. No
network egress happens without an explicit user action. No biometric image, subject identifier, or
restricted sample may enter the public repository or a public fixture.

## Why

Required-with-no-default is the point. An optional classification field defaults to whatever the
importer forgot, and the failure mode is a restricted sample in a public artifact — discovered
after publication, when it cannot be recalled.

`SYNTHETIC` and `GENERATED` are distinct states and permanently attached, so a generated sample can
never be mistaken for an authentic acquisition downstream.

## Consequences

- Import is stricter and slower. Accepted.
- The studio runs fully offline; cloud is not a fallback path.
- Public CI runs on public fixtures only. Private-data experiments never enter public CI.
