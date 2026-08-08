# OpenFIQA Studio
## Biometric Quality & Verification IDE

> Autonomous PRD / UltraPrompt execution artifact

### Global operating rules

Act as a principal research-software engineering organization. Inspect actual repositories and runtimes before making implementation claims. Build working software, run tests, capture evidence, repair failures, and continue through all unblocked nodes autonomously.

Never fabricate a successful run, reproduced result, model capability, package version, standard-conformance result, or test outcome. Keep `COMPUTED`, `VALIDATED`, `REPRODUCED`, `CONFORMANT`, and `PUBLICATION-READY` as separate states. Preserve engine-specific semantics for OFIQ, OFIQpy, US-FIQA, OpenFIQA, matchers, and learned models. Never silently normalize or equate scores across engines. Preserve dirty Git state and experimental artifacts before modification. Never expose restricted biometric data or credentials in public artifacts.

Autonomous repair loop:

```text
INSPECT → PLAN ATOMIC CHANGE → IMPLEMENT → TEST → FUNCTIONAL RUN
→ INSPECT OUTPUT → ADVERSARIAL CRITIC
   ├─ defect → REPAIR → RETEST
   ├─ external blocker → DOCUMENT → CONTINUE OTHER BRANCHES
   └─ pass → CAPTURE EVIDENCE → COMMIT → HANDOFF
```

Persistent state:

```text
orchestration/state.json
orchestration/evidence.jsonl
orchestration/blockers.md
orchestration/decisions/
```

Allowed states: `NOT_READY | READY | RUNNING | NEEDS_REVISION | BLOCKED | PASSED`.

Every passed node requires evidence: Git SHA, exact commands, exit codes, tests, outputs, hashes, and critic result.

# UltraPrompt 05 — Dataset Studio, Image Laboratory, Preprocessing, and Degradation Engine

## Requirement

Researchers must inspect and deliberately degrade biometric samples inside Studio and observe downstream effects.

## Graph

```text
I01 dataset manifest
 ├→ I02 import
 ├→ I03 subject/session metadata
 ├→ I04 split manager
 └→ I05 pair generator
      ↓
I06 sample browser
 ↓
I07 image laboratory
 ↓
I08 detect/landmark/align
 ↓
I09 degradation operators
 ↓
I10 interactive preview
 ↓
I11 parameter sweep
 ↓
I12 multidimensional degradation grid
 ↓
I13 transformed-artifact provenance
```

## Dataset capabilities

Directory/CSV/JSON/Parquet import; subject/session/acquisition metadata; train/validation/test splits; subject-disjointness checks; enrollment/probe/gallery/query roles; genuine/impostor pair generation; duplicate/hash detection.

## Image Lab

`Original | Processed | Difference | Metadata | Face box | Landmarks | Quality | Engine outputs | Transform history | Provenance`

Use synchronized zoom/pan.

## Required degradation nodes

JPEG, resolution/downsample, interpolation, Gaussian blur, motion blur, brightness, contrast, gamma, Gaussian noise, crop, rotation, translation, occlusion, grayscale/color perturbation.

Each node records implementation, parameters, seed if stochastic, input hash, and output hash.

## Gate

Interactive preview and batch execution must call the same transform implementation and match for deterministic settings.
