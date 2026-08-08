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

# UltraPrompt 12 — Integrated Acceptance Gauntlet and Autonomous Defect Closure

## Mission

Independently attack the release candidate. Subsystem self-reports are not sufficient evidence.

## Canonical E2E workflow

```text
Fixture/authorized dataset
 ↓
Face preprocessing
 ↓
Controlled degradation sweep
 ↓
OFIQ C++ + OFIQpy + US-FIQA + OpenFIQA
 ↓
Matcher / score adapter
 ↓
Verification evaluation
 ↓
FIQA utility / ERC
 ↓
Failure explorer
 ↓
Model load/fine-tune
 ↓
Run comparison
 ↓
Publication artifact
 ↓
Reproduction
 ↓
Evidence package
```

## Mandatory actions

1. Launch Studio.
2. Create project.
3. Import fixture/authorized dataset.
4. Inspect metadata.
5. Verify subject-disjoint split logic.
6. Open sample in Image Lab.
7. Run preprocessing.
8. Apply JPEG interactively.
9. Verify preview/batch equality.
10. Execute OFIQpy.
11. Execute another FIQA engine.
12. Compare without implicit scale equivalence.
13. Create degradation sweep graph.
14. Save graph as YAML.
15. Run from GUI.
16. Run from CLI.
17. Compare deterministic outputs.
18. Run/import matcher scores.
19. Compute ROC/DET/FIQA utility.
20. Click aggregate failure to sample.
21. Load model.
22. Fine-tune small fixture model and register checkpoint.
23. Freeze figure/table as publication artifact.
24. Reproduce from publication manifest.
25. Export evidence package and validate hashes.

## Independent reviewers

`R1 Scientific | R2 Architecture | R3 Reproducibility | R4 ML | R5 UX | R6 Security | R7 Release | R8 T&E`

Each returns `PASS | CHANGES_REQUIRED | BLOCKED`.

## Defect routing

```text
adapter        → P04
dataset/image  → P05
workflow       → P06
metric         → P07
ML             → P08
provenance     → P09
T&E            → P10
security/build → P11
architecture   → P02/P03
```

After repair, rerun the responsible subsystem gate and all affected downstream gates.

## Final statuses

`NOT_READY | RESEARCH_PREVIEW | ALPHA | BETA | RELEASE_CANDIDATE | VALIDATED_RESEARCH_RELEASE`

Never claim certification or operational approval.

## Final reports

```text
FINAL_ACCEPTANCE_REPORT.md
DEFECT_CLOSURE_LEDGER.md
REPRODUCTION_REPORT.md
SCIENTIFIC_VALIDATION.md
SECURITY_REVIEW.md
T_AND_E_READINESS.md
```

## Completion

The Studio must be demonstrably `VISUAL + EXECUTABLE + REPRODUCIBLE + TRACEABLE + EXTENSIBLE + SCIENTIFICALLY_AUDITABLE + LOCAL_FIRST`.
