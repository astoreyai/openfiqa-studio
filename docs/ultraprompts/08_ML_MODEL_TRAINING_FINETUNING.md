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

# UltraPrompt 08 — Model Loading, Training, Fine-Tuning, Optimization, and Registry

## Requirement

Studio must directly support model experimentation, not only fixed-model evaluation.

## Graph

```text
M01 model contract
 ├→ M02 PyTorch loader
 ├→ M03 TorchScript loader
 ├→ M04 ONNX loader
 └→ M05 custom Python adapter
      ↓
M06 model inspector
 ↓
M07 inference
 ↓
M08 training configuration
 ↓
M09 training worker
 ↓
M10 checkpoint/resume
 ↓
M11 fine-tuning controls
 ↓
M12 evaluation hook
 ↓
M13 run comparison
 ↓
M14 model registry
 ↓
M15 HPO/Optuna
 ↓
M16 ONNX export/equivalence
```

## Model Inspector

Display architecture/class, checkpoint, hash, framework, input/output shape, parameter count, trainable parameters, dtype, device, source run, and Git SHA.

## Training controls

Dataset, split, augmentation workflow, base checkpoint, frozen layers, optimizer, learning rate, scheduler, loss, epochs, batch size, accumulation, seed, precision, early stopping, workers, and device.

## Live events

Epoch, step, training/validation loss, metrics, learning rate, GPU utilization, VRAM, checkpoint creation.

## Registry states

`EXPERIMENTAL | CANDIDATE | VALIDATED | ARCHIVED`

Never use labels that imply operational certification.

## HPO rule

Every trial remains independently traceable; preserve unsuccessful trials and search configuration.

## ONNX rule

Exported models are not equivalent until compared against source inference on a registered fixture and tolerance.

## Gate

A controlled tiny fixture must load a base model, infer, fine-tune, change parameters, checkpoint, reload, evaluate, and register complete lineage.
