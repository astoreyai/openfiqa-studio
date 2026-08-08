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

# UltraPrompt 04 — OFIQ, OFIQpy, US-FIQA, OpenFIQA, and Matcher Integration

## Requirement

Studio must directly execute biometric engines, preserve native results, and provide typed outputs.

## Graph

```text
B01 fixture corpus
 ↓
B02 adapter harness
 ├→ B03 OFIQ C++ adapter
 ├→ B04 OFIQpy adapter
 ├→ B05 OpenFIQA adapter
 ├→ B06 ofiq-quality adapter
 ├→ B07 US-FIQA adapter
 └→ B08 matcher/score adapter
      ↓
B09 typed output layer
 ↓
B10 raw output preservation
 ↓
B11 cross-engine comparison
 ↓
B12 OFIQ↔OFIQpy equivalence
 ↓
B13 engine health UI
 ↓
B14 scientific adversarial review
```

## Direct Studio actions

Run any engine on one sample or dataset; display complete quality vectors; display engine/version/commit; expose raw and parsed outputs; sort/filter by output; compare engines; flag equivalence tolerance violations.

## Semantics constraint

Never assume OFIQ, US-FIQA, and OpenFIQA scores are numerically equivalent. Cross-engine comparison methods must be explicit: raw side-by-side, ranks, percentiles, standardized scores, calibrated mappings, correlations, or downstream utility.

## OFIQ equivalence workflow

```text
Image
 ├→ OFIQ C++ ─┐
 └→ OFIQpy ───┴→ feature comparator → tolerance violations → sample browser
```

## Gate

Every adapter must detect runtime, report version/source, execute a fixture, preserve raw output, emit typed output, pass unit tests, pass integration smoke, and surface failures honestly.
