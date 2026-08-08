# OpenFIQA Studio — Product Requirements Document

**Product:** OpenFIQA Studio  
**Subtitle:** Biometric Quality & Verification IDE  
**Product class:** Local-first scientific desktop IDE  
**Initial domain:** Face image quality assessment and biometric verification  
**Initial engines:** OFIQ, OFIQpy, OpenFIQA/ofiq-quality, US-FIQA  

---

## 1. Product vision

OpenFIQA Studio shall provide a unified visual environment in which a biometric researcher can:

- load images and datasets;
- inspect individual biometric samples and comparison pairs;
- apply controlled image degradations;
- run OFIQ, OFIQpy, OpenFIQA/ofiq-quality, US-FIQA, and future FIQA engines;
- run biometric matchers;
- construct experiments visually as executable graphs;
- execute existing Python, module, notebook, and shell workflows;
- load ML models and checkpoints;
- train and fine-tune models;
- perform sweeps, ablations, and robustness experiments;
- evaluate FIQA and verification performance;
- visualize aggregate and sample-level failures;
- compare implementations, models, runs, and degradations;
- generate publication figures, tables, manifests, and reproducibility bundles;
- trace every result to source data, code, model, parameters, environment, run, and Git revision.

The target experience is approximately:

> **VS Code + visual ML pipeline designer + biometric evaluation laboratory + experiment tracker.**

OpenFIQA Studio must not reduce independent quality engines to a single indistinguishable score. Each implementation retains its own feature semantics, ranges, configuration, provenance, and version.

---

## 2. Central execution model

The core abstraction is an executable typed graph:

```text
DATA
  ↓
TRANSFORM / DEGRADATION
  ↓
BIOMETRIC PROCESSING
  ↓
FIQA / MATCHER / MODEL
  ↓
EVALUATION
  ↓
VISUALIZATION
  ↓
ARTIFACT
  ↓
PUBLICATION
```

A workflow is defined by:

```text
nodes + typed edges + parameters + environment + artifacts + provenance
```

Every graphical workflow must serialize to a human-readable representation and execute without the GUI.

---

## 3. Recommended architecture

### Desktop

- Tauri 2
- React
- TypeScript
- `@xyflow/react` / React Flow for node graph editing
- Monaco-compatible editor for source/script inspection

### Python control plane

- FastAPI
- WebSockets for live logs, metrics, run state, and progress
- worker processes for scientific and ML jobs
- typed adapter/plugin registry

### ML and analytics

- PyTorch
- ONNX Runtime for portable exported inference
- MLflow for run/model lineage where useful
- Optuna for hyperparameter search
- SQLite for project/run metadata
- Parquet for large tabular outputs
- DuckDB for interactive analytical queries where useful

### Architectural boundary

The frontend configures, launches, observes, filters, and visualizes scientific operations. It must not independently reimplement OFIQ, OFIQpy, US-FIQA, OpenFIQA, matcher metrics, or training logic merely for UI convenience.

---

## 4. Main application layout

```text
┌──────────────────────────────────────────────────────────────────────┐
│ Project │ Run │ Experiment │ Models │ View │ Tools │ Help           │
├───────────────┬─────────────────────────────────────┬────────────────┤
│ PROJECT       │                                     │ INSPECTOR      │
│ EXPLORER      │             WORKSPACE               │                │
│               │                                     │ Parameters     │
│ datasets/     │ Graph / Image / Code / Evaluation  │ Inputs         │
│ models/       │                                     │ Outputs        │
│ workflows/    │                                     │ Provenance     │
│ scripts/      │                                     │ Resources      │
│ experiments/  │                                     │ Source         │
│ runs/         │                                     │                │
│ artifacts/    │                                     │                │
├───────────────┴─────────────────────────────────────┴────────────────┤
│ TERMINAL │ RUN LOG │ GPU │ METRICS │ PROBLEMS │ PROVENANCE         │
└──────────────────────────────────────────────────────────────────────┘
```

Primary screens:

```text
HOME
PROJECTS
DATASETS
IMAGE LAB
WORKFLOWS
RUNS
MODELS
TRAINING
EVALUATION
COMPARE
ARTIFACTS
PUBLICATIONS
CODE
SETTINGS
```

---

## 5. Dataset Studio

The Dataset Studio shall support:

- directory import;
- CSV manifests;
- JSON manifests;
- Parquet manifests;
- existing OpenFIQA experiment manifests;
- dataset hashing;
- metadata inspection;
- train/validation/test assignment;
- enrollment/probe assignment;
- genuine/impostor pair generation;
- search/filter;
- annotation;
- dataset integrity validation;
- restricted/public/synthetic classification.

Views:

```text
Grid
Filmstrip
Metadata table
Pair browser
Quality distributions
Embedding view
Failure browser
```

Biometric image bytes should normally remain referenced on disk rather than copied into the metadata database.

---

## 6. Image Laboratory

Selecting an image opens a scientific inspection view with:

```text
Original
Processed
Difference
Quality
Landmarks
Metadata
Transform history
Model outputs
Provenance
```

Example interactive pipeline:

```text
Original
    ↓
Downsample 512 → 96 px
    ↓
JPEG q=40
    ↓
Gaussian Blur σ=1.7
    ↓
Brightness -20%
    ↓
OFIQpy
    ↓
US-FIQA
    ↓
Matcher
```

The preview path and batch execution path must use the same underlying transform implementations.

---

## 7. Degradation Studio

Degradation is a first-class scientific subsystem.

### Initial degradation classes

**Compression**

- JPEG
- JPEG2000 where available
- WebP
- AVIF where available

**Resolution**

- downsampling
- upsampling
- nonuniform scaling
- interpolation selection

**Blur**

- Gaussian
- motion
- defocus
- directional

**Noise**

- Gaussian
- Poisson
- salt-and-pepper
- sensor-style noise

**Illumination**

- brightness
- contrast
- gamma
- local shadow
- highlight clipping
- underexposure
- overexposure

**Occlusion**

- rectangular
- mask-driven
- landmark-driven
- random
- semantic region

**Color**

- grayscale
- saturation
- color temperature
- channel perturbation
- bit depth

**Geometry**

- crop
- rotation
- translation
- perspective
- face-size change
- padding

Every transform must emit parameters and transform provenance.

---

## 8. Degradation sweeps

Any degradation parameter can become a sweep variable.

Example:

```text
JPEG quality = [100, 90, 80, 70, 60, 50, 40, 30, 20]
```

The system expands:

```text
Image
   ├── q100 ── FIQA ── Matcher ── Evaluation
   ├── q90  ── FIQA ── Matcher ── Evaluation
   ├── q80  ── FIQA ── Matcher ── Evaluation
   └── q20  ── FIQA ── Matcher ── Evaluation
```

Outputs may include:

- FIQA score/component changes;
- matcher similarity;
- FMR/FNMR;
- ROC/DET movement;
- ERC/AU-ERC;
- rank shifts;
- feature degradation response.

The interface must estimate and warn about combinatorial explosion for multidimensional sweeps.

---

## 9. Workflow graph

### Node taxonomy

#### Data

```text
Dataset
Image
PairSet
TrainSplit
ValidationSplit
TestSplit
Manifest
Artifact
```

#### Transform

```text
Resize
JPEG
Blur
Noise
Occlusion
Crop
Rotate
Illumination
Normalize
Align
CustomTransform
```

#### Face processing

```text
FaceDetector
LandmarkDetector
FaceAlignment
CropGenerator
EmbeddingExtractor
```

#### FIQA

```text
OFIQ_CPP
OFIQpy
ofiq-quality
OpenFIQA
US-FIQA
CustomFIQA
```

#### Matchers

```text
ArcFaceAdapter
AdaFaceAdapter
CustomEmbeddingMatcher
ExternalMatcher
ScoreFileLoader
```

#### ML

```text
LoadModel
InitializeModel
FreezeLayers
FineTune
Train
Validate
Checkpoint
ExportONNX
Inference
HyperparameterSearch
```

#### Evaluation

```text
PairGeneration
VerificationEvaluation
QualityEvaluation
ERC
AUERC
ROC
DET
ScoreDistribution
Correlation
Regression
Calibration
StatisticalTest
Bootstrap
Ablation
```

#### Visualization

```text
ImageViewer
Histogram
Scatter
BoxPlot
Violin
ROCPlot
DETPlot
ERCPlot
Heatmap
CorrelationMatrix
FeaturePanel
FailureBrowser
Table
```

#### Script

```text
PythonScript
PythonModule
ShellCommand
Notebook
ExistingExperiment
```

#### Control

```text
Branch
Sweep
Map
Merge
Filter
Condition
Repeat
Cache
Checkpoint
```

#### Artifact

```text
SaveJSON
SaveCSV
SaveParquet
SaveFigure
SaveModel
PublicationTable
PublicationFigure
ExperimentManifest
```

---

## 10. Typed edges

Edges must carry semantic types.

Examples:

```text
Dataset<Image>
PairSet<VerificationPair>
Model<EmbeddingModel>
Model<FIQAModel>
Features<QualityVector>
Scores<ComparisonScore>
Evaluation<VerificationMetrics>
Artifact<File>
```

Invalid graph connections should be rejected before execution and explained in the UI.

---

## 11. Scientific adapter architecture

Every scientific implementation is wrapped by a typed adapter.

```text
BiometricPlugin
├── QualityEngine
├── Matcher
├── Detector
├── Degrader
├── Model
├── Trainer
├── Evaluator
└── Visualizer
```

Each adapter declares:

```text
id
name
implementation
version
commit
runtime
input schema
output schema
feature definitions
configuration schema
dependencies
entry command/API
```

Required first adapters:

- OFIQpy adapter
- OFIQ C++ adapter
- OpenFIQA/ofiq-quality adapter
- US-FIQA adapter

Adapter startup process:

```text
Discover → Probe → Validate → Read capabilities → Register
```

The application must not silently remap engine-specific features to common names without an explicit, reviewable mapping.

---

## 12. Existing script execution

Legacy scripts must remain first-class citizens.

Support:

```text
python script.py
python -m module
bash script.sh
registered external executable
```

Script-node configuration:

- interpreter/environment;
- working directory;
- arguments;
- environment variables;
- input bindings;
- output bindings;
- CPU allocation;
- GPU allocation;
- memory constraints;
- timeout.

Capture:

- stdout;
- stderr;
- exit code;
- start/end time;
- runtime;
- working directory;
- environment identity;
- Git commit;
- input hashes;
- output hashes.

Terminal output must stream live into the UI.

---

## 13. Run system

Every execution becomes an immutable Run record.

```text
Run
├── run_id
├── workflow_id
├── Git SHA
├── dirty-state hash
├── environment
├── inputs
├── input hashes
├── parameters
├── random seeds
├── nodes executed
├── logs
├── metrics
├── artifacts
├── models
├── start/end
└── status
```

Statuses:

```text
QUEUED
PREPARING
RUNNING
PAUSED
FAILED
CANCELLED
COMPLETED
VALIDATED
REPRODUCED
```

`COMPLETED` must never imply `VALIDATED` or `REPRODUCED`.

---

## 14. Cache system

A deterministic node should derive a cache key from:

```text
hash(
    implementation
    + version
    + parameters
    + input hashes
    + environment
)
```

Stochastic nodes additionally include seed state.

Cache hits must remain visible and user-overridable.

---

## 15. Machine Learning Studio

Support model adapters for:

- PyTorch checkpoints;
- TorchScript;
- ONNX;
- scikit-learn where appropriate;
- registered custom Python models.

Model inspector fields:

```text
Model
Architecture
Input shape
Output shape
Parameters
Trainable parameters
Device
Precision
Checkpoint
Hash
Source
Version
Source run
```

---

## 16. Training and fine-tuning

Visual training flow:

```text
Base model
    ↓
Dataset
    ↓
Train/validation split
    ↓
Augmentation workflow
    ↓
Freeze policy
    ↓
Optimizer
    ↓
Scheduler
    ↓
Objective
    ↓
Training
    ↓
Validation
    ↓
Checkpoint
```

Configurable fields:

- epochs;
- batch size;
- learning rate;
- weight decay;
- optimizer;
- scheduler;
- layer freezing/unfreezing;
- loss;
- seed;
- precision;
- gradient accumulation;
- early stopping;
- device;
- workers.

Training dashboard should stream:

```text
Epoch
Train loss
Validation loss
Selected metrics
Learning rate
GPU utilization
VRAM
Checkpoint events
```

Training completion does not establish scientific validity.

---

## 17. Hyperparameter optimization

Provide an optional search node with:

- search spaces;
- trial execution;
- pruning;
- parallel trials;
- trial comparison;
- Pareto views where applicable;
- best-candidate selection.

Every trial remains a separate provenance-bearing run.

The UI must distinguish training, validation/search, and held-out test sets and warn against test-set-driven optimization.

---

## 18. Model registry

Model registry fields:

```text
model name
version
source run
dataset
training configuration
metrics
checkpoint
architecture
environment
Git SHA
hash
status
```

Allowed research statuses:

```text
EXPERIMENTAL
CANDIDATE
VALIDATED
ARCHIVED
```

Do not use terms implying operational biometric certification unless a separate formal certification process exists.

---

## 19. Verification evaluation

Required initial metrics and views:

- genuine/impostor score distributions;
- ROC;
- DET;
- EER;
- FMR;
- FNMR;
- TAR at defined FAR/FMR operating points;
- threshold analysis;
- pair-level failure inspection.

Metric definitions must be machine-readable and versioned.

---

## 20. FIQA evaluation

Required analyses:

- error-versus-reject/discard curves;
- AU-ERC or the project-defined integral metric;
- quality/error relationship;
- quality/matcher relationship;
- rank association;
- conditional verification performance;
- quality bins;
- failure prediction;
- engine comparison.

Cross-engine comparisons must not assume raw score scales are directly comparable.

---

## 21. Degradation evaluation

Support:

```text
quality vs degradation
verification vs degradation
feature vs degradation
model vs degradation
```

Examples:

```text
JPEG q → AU-ERC
Resolution → FNMR
Blur σ → quality
Occlusion fraction → matcher similarity
```

Users must be able to move from the aggregate curve to the individual samples responsible for failures.

---

## 22. Statistical evaluation

Provide plugin nodes for:

- bootstrap confidence intervals;
- paired comparisons;
- Pearson/Spearman association;
- regression;
- mixed-effects model invocation;
- effect sizes;
- multiple-testing correction;
- calibration analysis.

Methods must be replaceable without changing UI architecture.

---

## 23. Evaluation visualization

Required initial visualization types:

- ROC;
- DET;
- ERC;
- quality distributions;
- score distributions;
- quality-vs-score scatter;
- degradation-response curves;
- feature correlation matrices;
- heatmaps;
- box/violin plots;
- quality-bin performance;
- bootstrap intervals;
- model comparison tables.

Each visualized result must retain links to its source run and artifacts.

---

## 24. Interactive failure analysis

Researchers must be able to query conditions such as:

```text
OFIQ says high quality
AND
US-FIQA says low quality
AND
matcher fails
```

The failure browser shows:

```text
probe/enrollment images
quality scores
quality components
match score
ground truth
degradation history
model/version
run
provenance
```

Selecting a point or bin in an aggregate visualization should filter the sample browser where technically possible.

---

## 25. Feature inspector

For an image, display engine-scoped feature trees:

```text
IMAGE
├── OFIQ
├── OFIQpy
├── US-FIQA
└── OpenFIQA
```

Every feature carries:

```text
name
engine
definition
unit
range
direction
version
source function
```

Normalization must be an explicit operation, never a silent display transformation used in analysis.

---

## 26. OFIQ ↔ OFIQpy equivalence workflow

Provide a first-class implementation comparison template:

```text
           ┌── OFIQ C++ ──┐
Image ─────┤              ├── Feature comparator
           └── OFIQpy ────┘
                         ↓
                 Agreement analysis
```

Report:

- mean difference;
- median difference;
- maximum difference;
- correlations;
- tolerance violations;
- outlier samples;
- unsupported or non-equivalent features.

---

## 27. Code workspace

Provide:

- project explorer;
- source editor;
- syntax highlighting;
- global search;
- integrated terminal;
- problem panel;
- Git diff inspection;
- source links from graph nodes.

The objective is not to replace VS Code completely; it is to keep source code adjacent to experiments, images, runs, models, and results.

---

## 28. Provenance graph

Results must expose lineage such as:

```text
Publication Figure
      ↑
Evaluation Artifact
      ↑
Matcher Scores
      ↑
Matcher Model v4
      ↑
Degraded Images
      ↑
JPEG q40
      ↑
Dataset Manifest
```

and parallel model lineage:

```text
US-FIQA Scores
      ↑
US-FIQA Model v3
      ↑
Training Run
      ↑
Training Dataset
```

Relationship types should include:

```text
DERIVED_FROM
GENERATED_BY
TRAINED_FROM
TRANSFORMED_FROM
EVALUATED_BY
VISUALIZED_FROM
PUBLISHED_AS
```

---

## 29. Publication mode

Any validated result can be promoted to a publication artifact.

Freeze:

- run ID;
- Git SHA;
- dirty-state hash;
- environment;
- data manifest;
- model hash;
- workflow;
- parameters;
- metric definition;
- figure/table configuration;
- output hash.

Publication artifact types:

```text
Figure
Table
Supplement
Experiment Manifest
Reproduction Bundle
```

---

## 30. Reproduction mode

Given a publication manifest:

```text
Load manifest
    ↓
Validate environment
    ↓
Validate inputs
    ↓
Resolve models
    ↓
Execute workflow
    ↓
Compare outputs
    ↓
Generate discrepancy report
```

Statuses:

```text
EXACT
WITHIN_TOLERANCE
DIFFERENT
MISSING
BLOCKED
```

Never alter target values to agree with newly generated outputs.

---

## 31. Workflow serialization

Graphs must serialize to human-readable YAML or equivalent.

Example:

```yaml
name: jpeg_usfiqa_robustness

nodes:
  input:
    type: dataset
    dataset: evaluation_set

  degrade:
    type: jpeg
    quality:
      sweep: [100, 80, 60, 40, 20]

  fiqa:
    type: usfiqa
    model: usfiqa-v3

  matcher:
    type: matcher
    adapter: selected_matcher

  eval:
    type: verification_evaluation

edges:
  - input -> degrade
  - degrade -> fiqa
  - degrade -> matcher
  - fiqa -> eval
  - matcher -> eval
```

Workflows must be diffable, versionable, scriptable, reviewable, and reproducible.

---

## 32. CLI equivalence

Anything executed through the visual graph should eventually be executable headlessly:

```bash
openfiqa-studio run workflows/jpeg_usfiqa.yaml
```

This allows the same workflow to run through:

- GUI;
- CI;
- workstation CLI;
- remote execution later;
- publication reproduction.

---

## 33. Process architecture

```text
┌─────────────────────────────┐
│        Tauri Desktop        │
│ React / TS / Graph Editor   │
└──────────────┬──────────────┘
               │ HTTP / WS
               ▼
┌─────────────────────────────┐
│       Python Control        │
│          FastAPI            │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│       Job Scheduler         │
└─────┬────────┬────────┬─────┘
      │        │        │
      ▼        ▼        ▼
 OFIQ worker ML worker Script worker
      │        │        │
      └────────┴────────┘
               │
               ▼
       Artifact / Run Store
```

---

## 34. Project structure

```text
openfiqa-studio/
├── apps/
│   ├── desktop/
│   └── backend/
├── packages/
│   ├── ui/
│   ├── graph/
│   ├── schemas/
│   └── client/
├── python/
│   ├── openfiqa_studio/
│   │   ├── execution/
│   │   ├── provenance/
│   │   ├── evaluation/
│   │   ├── training/
│   │   ├── artifacts/
│   │   └── adapters/
│   │       ├── ofiq/
│   │       ├── ofiqpy/
│   │       ├── openfiqa/
│   │       └── usfiqa/
├── workflows/
│   ├── examples/
│   └── schemas/
├── tests/
│   ├── frontend/
│   ├── backend/
│   ├── adapters/
│   ├── workflows/
│   └── e2e/
├── orchestration/
├── docs/
└── examples/
```

Existing scientific repositories remain independently testable and are consumed through adapters.

---

## 35. Security and biometric-data requirements

Default rules:

- no automatic cloud upload;
- no telemetry containing biometric images or subject identifiers;
- no image transmission without explicit user action;
- no public artifact export containing restricted samples;
- no credentials in run logs;
- no unrestricted shell execution from arbitrary frontend text;
- no private biometric samples in public test fixtures.

Project data should be classifiable as:

```text
PUBLIC
RESTRICTED
PRIVATE
SYNTHETIC
GENERATED
```

Publication export must scan for restricted material.

---

## 36. MVP vertical slice

The MVP must prove the full architecture, not only UI appearance.

```text
Import images
      ↓
JPEG degradation
      ↓
OFIQpy
      ↓
US-FIQA
      ↓
Matcher or imported score set
      ↓
Verification/FIQA evaluation
      ↓
Visualization
      ↓
Provenance + artifact save
```

MVP requirements:

- desktop shell;
- project explorer;
- dataset import;
- image viewer;
- graph canvas;
- Python backend;
- OFIQpy adapter;
- US-FIQA adapter;
- JPEG transform node;
- script node;
- run system;
- log streaming;
- parameter inspector;
- ROC;
- ERC;
- scatter plot;
- artifact browser;
- YAML workflow serialization;
- provenance record.

---

## 37. Delivery phases

### Phase 1 — Vertical slice

MVP above.

### Phase 2 — Biometric laboratory

- OFIQ C++ adapter;
- OpenFIQA/ofiq-quality adapter;
- complete degradation suite;
- dataset browser;
- engine comparison;
- feature inspector;
- parameter sweeps;
- caching;
- publication figures.

### Phase 3 — ML Studio

- PyTorch model loading;
- training;
- fine-tuning;
- checkpoint management;
- model comparison;
- MLflow integration;
- ONNX export;
- hyperparameter optimization.

### Phase 4 — Advanced scientific analysis

- advanced statistics;
- bootstrap workflows;
- ablations;
- failure mining;
- embedding visualization;
- subset analysis;
- publication reproduction;
- experiment scheduling.

### Phase 5 — Optional scale-out

- remote workers;
- multi-GPU execution;
- SSH workers;
- SLURM adapter;
- container execution;
- shared artifact repository;
- collaboration server.

Local operation must not require Phase 5 infrastructure.

---

## 38. Non-goals

Initial OpenFIQA Studio shall not attempt to:

- replace every general-purpose IDE feature;
- become an operational biometric identity-decision system;
- automatically infer scientific conclusions;
- silently equate FIQA engines;
- hide underlying scripts;
- replace Python/C++ as the scientific implementation layers.

---

## 39. Scientific state model

The UI must explicitly preserve:

```text
COMPUTED
≠
VALIDATED
≠
REPRODUCED
≠
SCIENTIFICALLY SUPPORTED
```

These are separate states and require separate evidence.

---

## 40. Product success condition

OpenFIQA Studio succeeds when a researcher can:

```text
Dataset
 ↓
Degradation sweep
 ↓
OFIQ + OFIQpy + US-FIQA + OpenFIQA
 ↓
Matcher
 ↓
Verification evaluation
 ↓
ERC / ROC / degradation analysis
 ↓
Failure exploration
 ↓
Model fine-tuning
 ↓
Run comparison
 ↓
Publication figure
```

and trace every resulting number, plot, checkpoint, and figure to its exact computational lineage.

That is the threshold for a **biometric IDE**, rather than a dashboard or script launcher.
