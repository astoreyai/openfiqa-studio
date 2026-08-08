# ADR-0001 — Desktop shell and scientific backend are separate processes

**Status:** accepted 2026-08-07 · **Prompt:** P02 A01

## Decision

Tauri 2 + React + TypeScript renders. A Python FastAPI control plane owns every scientific
operation. They communicate over HTTP and a WebSocket; they share no in-process state.

## Why

The frontend must never become a second implementation of the science. The failure is not
hypothetical: a UI that recomputes a mean, rescales a component, or normalises two engines onto one
axis "just for the chart" produces a number with no provenance and no way to reproduce it.
Separating the processes makes that physically harder — the frontend has no engine to call.

## Consequences

- Every displayed number arrives from the backend carrying its `EngineRef` and `ScoreSemantics`.
- The frontend may sort, filter, and lay out. It may not compute a scientific quantity.
- Startup, health, and shutdown of the sidecar become first-class product concerns (P03 F05).
- Offline operation is preserved: both halves are local, and no network call is required to run.
