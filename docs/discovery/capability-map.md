# N02 — Scientific Capability Inventory

**Discovery date:** 2026-08-07
**Rule applied:** never invent a missing capability. Every field below is either **confirmed** by
a command that was actually run, or marked **UNRESOLVED**. Nothing is filled in by convention.

Machine-readable form: [`../../config/engine-capabilities.yaml`](../../config/engine-capabilities.yaml).

---

## E1 · ofiqpy — component extractor

| Field | Value | Status |
|---|---|---|
| Accepted inputs | path to an image file (`str` or PathLike), **or** a BGR `uint8` array of shape `(H, W, 3)` | confirmed — docstring of `ofiqpy.assess` |
| Python API | `assess(image: str \| object) -> dict` | confirmed — `inspect.signature` |
| Output schema | `{component_name: (raw_native_value, scalar_0_100)}` | confirmed — docstring |
| No-face behaviour | returns an **empty dict** | confirmed — docstring |
| Public exports | `assess`, `annotations` | confirmed |
| Component set | includes `UnifiedQualityScore`, `HeadPose{Pitch,Roll,Yaw}`, `FaceOcclusionPrevention`, `FaceOcclusionSegmentation`, `MouthOcclusionPrevention` | confirmed — string constants in source |
| Full component list | UNRESOLVED — not enumerated without running inference on a real image |
| Scalar score direction | UNRESOLVED — 0–100 range confirmed; higher-is-better not verified in this package |
| Raw value direction | **varies per component**, and is mis-declared upstream for 10 of 27 — see risks R3 | confirmed |
| Batch capability | UNRESOLVED — `assess` is single-image; CLI batch behaviour not probed |
| CPU/GPU | UNRESOLVED |
| Model requirements | UNRESOLVED — bundled vs downloaded not determined |
| Environment | requires its own `.venv`; not importable from the system interpreter | confirmed |

The single-function, tuple-returning API is the cleanest adapter surface of the four engines.

## E2 · openfiqa — component extractor + normative scorer

| Field | Value | Status |
|---|---|---|
| Accepted inputs | `IMAGE_PATHS...` (variadic) | confirmed — `openfiqa assess --help` |
| CLI subcommands | `assess`, `analyze`, `batch`, `download-models`, `profiles` | confirmed — `openfiqa --help` |
| Output formats | `json`, `text`, `csv`; optional PDF report via `-v/--visual -o` | confirmed |
| Device selection | `-d/--device TEXT` | confirmed |
| Optional stages | `--enable-vit`, `--enable-matcher` | confirmed |
| Batch capability | **yes** — `batch` runs multiple datasets from config; `analyze` runs dataset-level analysis | confirmed |
| Model requirements | weights fetched from HuggingFace Hub via `download-models` | confirmed |
| Config | `-c/--config PATH` (YAML) | confirmed |
| Python API | UNRESOLVED — only the CLI surface was probed |
| Score direction / range | UNRESOLVED at component level; profile thresholds imply higher-is-better on the profile score | inferred |

### Standards profiles — already implemented upstream

`openfiqa profiles` exposes a `standard:mode` registry with accept/reject thresholds:

| Standard | Components | Modes and accept/reject |
|---|---|---|
| `iso-29794-5` | 27 | passport 80/60 · kiosk 70/50 · enrollment 65/45 · probe 50/30 · forensic 0/0 |
| `icao-9303` | 17 | passport 80/60 · kiosk 70/50 · enrollment 65/45 · probe 50/30 · forensic 0/0 |

This is directly load-bearing for the conformance workspace. T&E requirements 6 (standards
registry) and 7 (standards-version pinning) do not start from zero — this registry is the thing
the studio should surface and extend, not reimplement. The `icao-9303` 17-component subset is
already a worked example of a profile narrowing a standard.

## E3 · ofiq-quality — unified scorer *(this is US-FIQA)*

| Field | Value | Status |
|---|---|---|
| Accepted inputs | `FEATURES_PATH` — a CSV or Parquet table of **pre-extracted features**. Accepts no image. | confirmed — `ofiq-quality predict --help` |
| CLI subcommands | `predict`, `batch`, `info` | confirmed |
| Required artifacts | `--model-dir` is **required**, and must contain `quality_predictor.onnx`, `scaler.pkl`, `model_config.json` | confirmed |
| Output | JSON; `--explain` adds component-level explanation | confirmed |
| Feature contract | **47 columns**, fixed order, from `feature_columns.json` | confirmed |
| Runtime | Python 3.11.2 · numpy 2.4.6 · pandas 2.3.3 · torch 2.13.0+cu130 · sklearn 1.9.0 · onnxruntime 1.28.0 · xgboost 2.1.4 | confirmed — `ofiq-quality info` |
| Missing optional deps | `lightgbm` NOT INSTALLED · `shap` NOT INSTALLED | confirmed |
| Score direction / range | UNRESOLVED |
| Batch capability | yes — `batch` over a directory of feature files | confirmed |

### The 47-column feature contract

| Class | Count | Examples |
|---|---|---|
| Raw ISO-style components | 27 | `BackgroundUniformity`, `Sharpness`, `CompressionArtifacts`, `DynamicRange`, `ExpressionNeutrality`, `EyesOpen`, `HeadSize`, `InterEyeDistance`, `NaturalColour`, `SingleFacePresent` |
| Polarity-normalised derivatives | 7 | `HeadPosePitch_polnorm`, `HeadPoseRoll_polnorm`, `HeadPoseYaw_polnorm`, `LuminanceMean_polnorm`, `LuminanceVariance_polnorm`, `NaturalColour_polnorm`, `SingleFacePresent_polnorm` |
| Engineered composites | 13 | `crop_lr_symmetry`, `crop_tb_symmetry`, `exposure_composite`, `occlusion_composite`, `pose_magnitude`, `ied_head_ratio`, `sharpness_x_illumination`, `feature_rank_{min,max,mean,std}`, `n_nan_features`, `n_near_zero` |

**Only the first 27 come from an extractor.** The remaining 20 are produced by a feature
engineering stage that is not exposed by either distribution's CLI. `shap` is absent, so
`--explain` may be degraded — unverified, since `predict` was not run.

## E4 · OFIQ-Project — C++ reference

Not probed. The working tree carries 44 uncommitted paths and the ultraprompt forbids touching a
source repository before its Git state is inventoried and preserved. Every field is **UNRESOLVED**
pending that inventory.

---

## Cross-engine comparison

| | ofiqpy | openfiqa | ofiq-quality (US-FIQA) | OFIQ-Project |
|---|---|---|---|---|
| Takes images | yes | yes | **no** | UNRESOLVED |
| Takes feature tables | no | no | **yes** | UNRESOLVED |
| Emits components | yes | yes | no | UNRESOLVED |
| Emits unified score | `UnifiedQualityScore` component | profile score | yes, predicted | UNRESOLVED |
| Batch | UNRESOLVED | yes | yes | UNRESOLVED |
| Python API confirmed | yes | no | no | no |
| Standards profiles | no | **yes, 2 × 5** | no | UNRESOLVED |
| Runs today | yes | UNRESOLVED (weights not fetched) | **no** — see R2 | UNRESOLVED |

Per PRD §35 and design principle 20 of `00_PROJECT.md`, these score spaces must never be
normalised onto each other. `ofiqpy`'s `UnifiedQualityScore` component, `openfiqa`'s profile
score, and `ofiq-quality`'s predicted score are three different quantities with three different
definitions. Presenting them in one column without a semantic label is a defect, not a feature.

---

## Open items blocking N08–N11

1. Full component list and score direction for `ofiqpy` — needs one inference run on a real image.
2. `openfiqa` Python API surface — only the CLI was probed.
3. Score direction and range for `ofiq-quality`.
4. Everything about `OFIQ-Project`, gated behind its 44-path inventory.
5. Where the feature-engineering stage lives and whether it is callable as a library.
