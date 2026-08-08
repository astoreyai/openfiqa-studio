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

# UltraPrompt 06 — Visual Workflow Graph, Script Runner, Scheduler, Cache, and CLI

## Requirement

Anything performed interactively must be representable as a version-controlled executable graph.

## Node classes

Data: Dataset, Sample, PairSet, Manifest, Artifact  
Preprocess: Detect, Landmark, Align, Normalize  
Transform: JPEG, Resize, Blur, Noise, Occlusion, Crop, Rotate, Illumination  
Biometrics: OFIQ, OFIQpy, US-FIQA, OpenFIQA, Matcher, Embedding  
ML: LoadModel, Train, FineTune, Inference, ExportONNX  
Evaluation: ROC, DET, ERC, AUERC, Distribution, Correlation, Bootstrap, Regression  
Control: Map, Sweep, Branch, Filter, Merge, Condition, Cache, Checkpoint  
Script: PythonScript, PythonModule, ShellCommand, Notebook  
Artifact: SaveJSON, SaveCSV, SaveParquet, Figure, Table, PublicationArtifact

## Graph

```text
W01 graph UI
 ↓
W02 typed ports
 ↓
W03 graph validation
 ↓
W04 YAML serialization
 ↓
W05 DAG compiler
 ↓
W06 sweep expansion
 ↓
W07 scheduler
 ├→ W08 process isolation
 ├→ W09 resource allocation
 ├→ W10 cache
 └→ W11 cancellation/failure propagation
      ↓
W12 script runner
 ↓
W13 CLI equivalence
 ↓
W14 run history
 ↓
W15 E2E graph test
```

## CLI

```text
openfiqa-studio validate workflow.yaml
openfiqa-studio run workflow.yaml
openfiqa-studio reproduce publication_manifest.yaml
```

## Security rule

Executable nodes must be registered or explicitly locally approved. Never execute arbitrary untrusted text as shell code.

## Gate

The same workflow must run from GUI and CLI and produce equivalent deterministic artifacts/manifests.
