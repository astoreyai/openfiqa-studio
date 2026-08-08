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

# UltraPrompt 01 — Discovery, Canonicalization, and Scientific Inventory

## Requirement

Establish ground truth about every implementation before building adapters.

Known candidates:

```text
/mnt/projects/02_perception_biometrics/ofiq_29794/
/mnt/projects/02_perception_biometrics/ofiqpy/
/mnt/projects/02_perception_biometrics/OFIQ-Project/
```

Discover the authoritative US-FIQA implementation rather than guessing.

## Graph

```text
D01 Git inventory
 ├→ D02 Python packages
 ├→ D03 C++/binary interfaces
 ├→ D04 models/checkpoints
 ├→ D05 datasets/manifests
 └→ D06 scripts/experiments
      ↓
D07 dependencies + licenses
      ↓
D08 engine capability matrix
      ↓
D09 naming/canonicalization ADR
      ↓
D10 integration-risk review
      ↓
D11 discovery gate
```

## Engine record

```yaml
engine_id:
display_name:
implementation_type:
repository:
remote:
commit:
dirty_state:
package_name:
import_name:
cli:
python_api:
binary_api:
input_types:
output_schema:
feature_names:
score_direction:
score_range:
preprocessing_assumptions:
models:
runtime:
gpu_support:
batch_support:
license:
known_tests:
known_experiments:
known_publications:
```

## Outputs

```text
docs/discovery/repository-map.md
docs/discovery/capability-map.md
docs/discovery/integration-risks.md
config/engine-capabilities.yaml
config/repository-locks.yaml
orchestration/handoffs/P01.yaml
```

## Critic

Verify what is reference versus port/reimplementation; distinguish `openfiqa` from `ofiq-quality`; determine score semantics from code/docs; distinguish executed experiments from referenced results; identify preprocessing differences.

## Gate

Each initial engine must have either a verified invocation path or an evidence-backed blocker.
