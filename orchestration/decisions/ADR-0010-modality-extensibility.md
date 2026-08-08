# ADR-0010 — Face-specific meaning lives in plugins and profiles, never in the engine

**Status:** accepted 2026-08-07 · **Prompt:** P02 A01

## Decision

The workflow engine, scheduler, artifact store, and provenance layer know about samples, typed
ports, runs, and artifacts. They do not know what a face is. ISO/IEC 29794-5 component names,
landmark conventions, and face-specific thresholds live in plugin manifests and standards profiles.

## Why

The requirement is one architecture for face quality today and other modalities later. The way that
fails is not a missing feature — it is `sharpness` and `inter_eye_distance` leaking into the graph
compiler as first-class concepts, after which adding a second modality means rewriting the engine.

The specific temptation here is real: `openfiqa` ships a profile registry with component counts and
thresholds, and it would be easy to hard-code those into the comparison view.

## Consequences

- Adding a modality means adding plugins and profiles, not editing the scheduler.
- The comparison view renders whatever components a `QualityVector` declares; it has no built-in
  list of face component names.
- Cost: slightly more indirection for the face-only case today. Accepted deliberately.
