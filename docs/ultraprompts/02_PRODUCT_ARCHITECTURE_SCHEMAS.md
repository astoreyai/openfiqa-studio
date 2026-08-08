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

# UltraPrompt 02 — Product Architecture, Domain Model, and Plugin Contracts

## Requirement

Define one architecture for face quality today and other biometric modalities later without embedding OFIQ semantics into the workflow engine.

## Domain model

```text
BiometricSample | Dataset | Transform | QualityEngine | FeatureExtractor
Matcher | Model | Trainer | Evaluator | Visualization | Artifact | Run | Provenance
```

## Default stack

```text
Desktop: Tauri 2
Frontend: React + TypeScript
Graph: React Flow
Editor: Monaco-compatible
Backend: Python + FastAPI
Realtime: WebSocket
Metadata: SQLite
Analytics: Parquet + DuckDB
ML: PyTorch
Portable inference: ONNX Runtime
Tracking: MLflow
Optimization: Optuna
```

## Graph

```text
A01 context boundaries
 ↓
A02 domain entities
 ├→ A03 plugin interfaces
 ├→ A04 workflow schemas
 ├→ A05 run schemas
 └→ A06 provenance schemas
      ↓
A07 API contracts
 ↓
A08 storage architecture
 ↓
A09 security boundary
 ↓
A10 ADR review
 ↓
A11 schema compatibility tests
```

## Plugin contracts

`QualityEnginePlugin | MatcherPlugin | DetectorPlugin | LandmarkPlugin | TransformPlugin | ModelPlugin | TrainerPlugin | EvaluatorPlugin | VisualizerPlugin | ScriptPlugin`

Each declares ID, name, version, implementation, typed input/output ports, parameter schema, capabilities, runtime requirements, source, and provenance fields.

## Typed scientific objects

`ImageSample | FaceImage | AlignedFace | QualityVector | QualityScore | Embedding | ComparisonPair | ComparisonScore | LabeledScoreSet | VerificationMetrics | ERCResult | TrainingCheckpoint | PublicationArtifact`

## Required ADRs

Desktop/backend split; Python sidecar/process model; plugin architecture; typed workflow graph; artifact store; provenance DAG; ML lifecycle; dataset/privacy boundary; CLI/GUI equivalence; modality extensibility.

## Gate

Schemas validate, frontend/backend types cannot silently diverge, engine-specific score meaning is not embedded in generic types, and at least one fixture plugin validates.
