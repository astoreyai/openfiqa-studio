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

# UltraPrompt 00 — Master Program Orchestrator

## Mission

Build OpenFIQA Studio as a complete face-biometric research IDE supporting datasets, image inspection, preprocessing, controlled degradation, OFIQ C++, OFIQpy, US-FIQA, OpenFIQA/ofiq-quality, matchers, verification evaluation, FIQA utility, failure analysis, visual workflow graphs, scripts, model loading, training/fine-tuning, provenance, reproduction, publication, and a controlled T&E extension.

The Studio is not a GUI around scripts. The visual graph and CLI must execute the same canonical workflow definition.

## Program graph

```text
P01 Discovery & Canonicalization
 ↓
P02 Product Architecture & Schemas
 ↓
P03 Desktop + Backend Foundation
 ├─────────────┬─────────────────┐
 ↓             ↓                 ↓
P04           P05               P08
Biometrics    Image/Data Lab     ML Foundation
 └──────┬──────┘                 │
        ↓                        │
       P06 Workflow Engine ←─────┘
        ↓
       P07 Evaluation & Failure Analysis
        ↓
       P09 Provenance/Reproduction/Publication
        ↓
       P10 T&E/Standards Layer
        ↓
       P11 Security/Validation/Release
        ↓
       P12 Final Acceptance Gauntlet
        │
        └── defects → responsible prior prompt → downstream retest
```

## Master acceptance criteria

A user must be able to create a project; import a dataset; inspect a sample; preprocess and degrade it; execute OFIQpy plus another FIQA engine; compare outputs without conflating scales; build and run a degradation sweep; run/import a matcher; compute ROC/DET/ERC/AU-ERC where applicable; drill from aggregate failure to exact samples; load and fine-tune a model; register a checkpoint; compare runs; freeze a publication artifact; reproduce it; and export an evidence package.

## Handoff schema

```yaml
handoff:
  prompt:
  status:
  git_sha:
  passed_gates: []
  blocked_gates: []
  artifacts: []
  schemas_added: []
  APIs_added: []
  workflows_added: []
  tests_added: []
  known_risks: []
  next_prompt_inputs: []
```

Start with `01_DISCOVERY_CANONICALIZATION.md`.
