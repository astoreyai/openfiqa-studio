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

# UltraPrompt 07 — Verification Evaluation, FIQA Utility, Visualization, and Failure Mining

## Requirement

Turn quality measurements into defensible biometric-performance analysis.

## Graph

```text
E01 score/pair schema
 ↓
E02 verification metrics
 ├→ E03 ROC
 ├→ E04 DET
 ├→ E05 FMR/FNMR/TAR/thresholds
 └→ E06 score distributions
      ↓
E07 FIQA utility
 ├→ E08 ERC
 ├→ E09 AU-ERC
 ├→ E10 quality-conditioned performance
 └→ E11 rank/correlation analysis
      ↓
E12 degradation-response analysis
 ↓
E13 uncertainty/statistics
 ↓
E14 visualization library
 ↓
E15 interactive failure explorer
 ↓
E16 cross-engine disagreement explorer
 ↓
E17 publication table/figure preview
```

## Direct evaluation

Implement explicit, versioned definitions for genuine/impostor distributions, ROC, DET, FMR, FNMR, TAR, FRR where used, EER, operating thresholds, ERC, AU-ERC, quality bins, quality-conditioned recognition, rank correlation, and bootstrap confidence intervals.

## Failure explorer queries

Examples:

```text
OFIQ high AND US-FIQA low AND verification = false_non_match
```

```text
JPEG <= 40 AND matcher_score crosses threshold AND FIQA rank remains high
```

Charts must retain sample-level linkage. Clicking a point/bin should expose contributing sample IDs, images, quality outputs, matcher scores, degradation parameters, source run, and provenance.

## Scientific critic

Check score direction, labels, threshold convention, ERC rejection ordering, AU-ERC definition/integration, leakage, bootstrap sampling unit, and invalid raw-scale cross-model comparisons.

## Gate

Every metric has an analytic/synthetic fixture, unit test, numerical tolerance, metadata definition, and traceable input artifact.
