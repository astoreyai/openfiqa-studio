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

# UltraPrompt 10 — Government T&E / Standards-Conformance Extension

## Requirement

Add a controlled Test & Evaluation mode suitable for independent biometric-engine assessment. This does not assert official certification; it creates the machinery to encode profiles, execute prescribed tests, preserve evidence, and report findings.

## T&E workflow

```text
Select profile
 ↓
Select implementation/version
 ↓
Select reference corpus/test vectors
 ↓
Validate environment
 ↓
Execute prescribed tests
 ↓
Collect evidence
 ↓
Investigate deviations
 ↓
Reproduce
 ↓
Generate T&E/conformance report
```

## Graph

```text
T01 profile schema
 ↓
T02 standards registry
 ↓
T03 requirement/test mapping
 ↓
T04 reference-vector system
 ↓
T05 conformance execution
 ↓
T06 result classification
 ↓
T07 exception drill-down
 ↓
T08 implementation equivalence
 ↓
T09 interoperability/export validation
 ↓
T10 evidence package
 ↓
T11 reviewer signoff workflow
```

## Requirement states

`PASS | FAIL | WARNING | NOT_APPLICABLE | BLOCKED | NOT_TESTED`

## Profile schema

```yaml
profile_id:
title:
authority:
version:
effective_date:
requirements:
  - requirement_id:
    citation:
    description:
    test_id:
    severity:
    expected:
```

Architect for quality-algorithm conformance, image/record format validation, transaction/profile validation, implementation equivalence, interface interoperability, and reproducibility requirements.

Specific standards or government profiles may only be encoded from verified requirements and must be version-pinned.

## Gate

One synthetic/local test profile must execute end-to-end and produce requirement-level evidence automatically.
