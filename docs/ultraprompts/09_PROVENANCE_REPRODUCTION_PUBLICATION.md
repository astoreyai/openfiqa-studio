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

# UltraPrompt 09 — Provenance DAG, Reproduction Mode, Publication Artifacts, and Evidence Packages

## Requirement

No Studio result may be an orphan. Every number, point, table, model, and figure must be traceable to computational ancestry.

## Graph

```text
P01 artifact identity/hash
 ↓
P02 run manifest
 ↓
P03 provenance relationships
 ↓
P04 provenance query API
 ↓
P05 provenance viewer
 ↓
P06 publication freeze
 ├→ P07 figure artifact
 ├→ P08 table artifact
 └→ P09 model artifact
      ↓
P10 publication manifest
 ↓
P11 reproduction runner
 ↓
P12 discrepancy analysis
 ↓
P13 evidence package
 ↓
P14 independent reproduction critic
```

## Provenance vocabulary

`DERIVED_FROM | TRANSFORMED_FROM | GENERATED_BY | EVALUATED_BY | TRAINED_FROM | USES_MODEL | USES_DATASET | USES_CONFIG | VISUALIZED_FROM | PUBLISHED_AS | REPRODUCES`

## Publication freeze

Preserve artifact ID, run ID, workflow hash, Git SHA, dirty-state hash, dataset manifest, input hashes, model hashes, engine versions, parameters, seeds, environment, metric definition, visualization configuration, and output hash.

## Reproduction states

`EXACT | WITHIN_TOLERANCE | DIFFERENT | MISSING_DEPENDENCY | MISSING_DATA | BLOCKED`

Never alter the reference/published value to agree with a rerun.

## Evidence package

```text
README.md
publication_manifest.yaml
workflow.yaml
environment lock
engine lock
model lock
dataset manifest
input hash manifest
result manifest
figures/
tables/
logs/
reproduction_report.md
```

Restricted samples should be referenced by authorized manifest/hash rather than copied unless explicitly permitted.

## Gate

Demonstrate UI traversal:

```text
Publication figure ← metric ← evaluation ← scores ← matcher/model
← transformed samples ← transforms ← original dataset ← Git/environment
```
