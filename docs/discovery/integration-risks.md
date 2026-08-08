# N01 — Integration Risks

**Discovery date:** 2026-08-07
Each risk states the evidence that produced it and what would clear it. Nothing here is
speculative; every entry was observed during read-only inspection.

---

## R1 — The MVP vertical slice has a missing stage · **BLOCKER**

`01_PRD.md` §36 specifies the slice as `images → JPEG degradation → OFIQpy → US-FIQA → matcher →
evaluation`. That edge from OFIQpy to US-FIQA does not exist.

US-FIQA consumes a **47-column** feature table. Only 27 of those columns are components an
extractor emits. The other 20 — 7 `_polnorm` polarity-normalised derivatives and 13 engineered
composites (`exposure_composite`, `pose_magnitude`, `feature_rank_std`, `n_nan_features`, …) — are
produced by a feature-engineering stage that **neither published distribution exposes through its
CLI**. It exists as research-track code.

*Evidence:* `data/models/feature_columns.json` (47 entries); `ofiq-quality predict --help` accepts
`FEATURES_PATH` only.

*Impact:* piping `ofiqpy.assess()` output straight into `ofiq-quality predict` fails, or worse,
silently mis-scores if column order is coerced.

*Clears when:* the feature-engineering stage is confirmed callable as a library function, its
input contract is pinned, and it is modelled as an explicit node between extraction and scoring.

## R2 — US-FIQA model artifacts do not match the required filenames · **BLOCKER**

`ofiq-quality predict` requires `--model-dir` (no default) containing exactly
`quality_predictor.onnx`, `scaler.pkl`, and `model_config.json`.

The research model directory contains none of those three names:

| Required by CLI | Present on disk |
|---|---|
| `quality_predictor.onnx` | `quality_predictor_xgboost.onnx` (21.5 MB) |
| `scaler.pkl` | `scaler_params.json` (1.9 KB) |
| `model_config.json` | `feature_columns.json` (1.1 KB) |

Also present: `quality_predictor_xgboost.pkl`, and three ResNet-50 checkpoints
(`cnn_resnet50_quality.pt`, `_seed1_`, `_seed3_`, ~96 MB each).

*Impact:* US-FIQA cannot be invoked today. This is a filename/format comparison, not a run —
`predict` was not executed, because doing so needs a real feature table that does not yet exist.

*Clears when:* either the packaged CLI's expected names are reconciled with the research
artifacts, or a conforming model directory is located. Whether `scaler_params.json` is
format-compatible with a `scaler.pkl` loader is **unverified** and is the part most likely to
break after renaming.

## R3 — The shipped polarity map is wrong for 10 of 27 components · **HIGH**

The upstream project recorded this defect on **2026-08-06**, one day before this inventory. Its
own note states the file *"declares itself a polarity map for OFIQ RAW measures"* and that for
eight components *"the raw number is the DEFECT MAGNITUDE while the column name states the quality
concept, so the declared `positive` polarity is inverted."*

The file is **shipped package data**, not a paper artifact: it lives inside the `ofiq-quality`
package's `configs/` and is loaded by that package's feature-engineering module.

*Impact:* the 7 `_polnorm` columns are derived through this map. Any studio adapter that wraps the
packaged feature engineering inherits the defect, and every US-FIQA score computed through it is
suspect. This is a live upstream bug, not a studio bug — but the studio would launder it into
results that look clean.

*Clears when:* the upstream fix lands and the studio pins a `ofiq-quality` version at or after it.
Until then the US-FIQA adapter must record which polarity-map revision produced each score. This
is precisely the case T&E requirement 7 (standards-version pinning) and 14 (implementation
provenance) exist for.

## R4 — OFIQ-Project has 44 uninventoried modified paths · **HIGH**

*Evidence:* `git status --porcelain` reports 44 paths on `main` @ `bb5dc91`.

*Impact:* N09 (OFIQ C++ adapter) cannot start. The ultraprompt forbids modifying a source
repository before its Git state is inventoried and preserved, and a 981 MB tree with a live
`build/` directory is easy to disturb accidentally.

*Clears when:* the 44 paths are classified as intentional local work, build residue, or drift, and
preserved on a branch or stash with a recorded SHA.

## R5 — ofiqpy reports two different versions · **MEDIUM**

`pyproject.toml` declares `0.1.1`; `ofiqpy.__version__` reports `0.1.0`.

*Impact:* a provenance record that captures "ofiqpy 0.1.1" and one that captures "ofiqpy 0.1.0"
may describe the same execution. Version strings alone are not a sufficient provenance key.

*Clears when:* the adapter records the **commit SHA** alongside the version, and the upstream
mismatch is reported.

## R6 — There is no shared interpreter · **MEDIUM**

`import ofiqpy` fails under the system `python3`. The OpenFIQA workspace runs from its own `.venv`
on Python 3.11.2 with `torch 2.13.0+cu130`.

*Impact:* the control plane cannot import engines in-process. Adapters must be subprocess- or
sidecar-based with per-engine environment resolution, decided in N03 — not retrofitted after the
adapters exist. This also means environment capture is part of provenance from day one.

*Clears when:* N03 records an ADR for per-engine environment resolution.

## R7 — Three different quantities are all called a unified score · **MEDIUM**

`ofiqpy` emits a `UnifiedQualityScore` component; `openfiqa` emits a profile score against
accept/reject thresholds; `ofiq-quality` emits a predicted unified score from a trained model.

*Impact:* placing these in one table column, one chart series, or one comparison view without a
semantic label violates `00_PROJECT.md` design principle 20 and T&E requirement 12. The failure is
silent and looks like a working feature.

*Clears when:* N04 gives each score a typed, engine-scoped identity that cannot be widened into a
generic `quality_score` float.

## R8 — One engine's source is not publicly released · **MEDIUM**

The OpenFIQA workspace supplying both `openfiqa` and `ofiq-quality` is a private repository.

*Impact:* third-party reproduction (T&E requirements 40 and 42) cannot cover the US-FIQA path
while its source and model artifacts are unavailable. A reproduction verdict for a US-FIQA result
would have to be `BLOCKED`, and the studio should be able to say so rather than fail obscurely.

*Clears when:* release status is decided, or the reproduction model formally supports
`BLOCKED — source unavailable` as a first-class verdict with a reason.

## R9 — Optional explanation dependencies are absent · **LOW**

`ofiq-quality info` reports `lightgbm: NOT INSTALLED` and `shap: NOT INSTALLED`.

*Impact:* `predict --explain` may return degraded or no component-level explanation. Unverified —
`predict` was not run.

*Clears when:* `--explain` is exercised once a conforming model directory exists (R2).

---

## Severity summary

| Risk | Severity | Blocks |
|---|---|---|
| R1 missing feature-engineering stage | **Blocker** | MVP slice, N11 |
| R2 model artifact mismatch | **Blocker** | MVP slice, N11 |
| R3 polarity map defect | High | trustworthy US-FIQA output |
| R4 OFIQ-Project dirty tree | High | N09 |
| R5 ofiqpy version mismatch | Medium | provenance correctness |
| R6 no shared interpreter | Medium | N03, adapter architecture |
| R7 conflated score semantics | Medium | N04 schemas |
| R8 private engine source | Medium | reproduction coverage |
| R9 missing optional deps | Low | `--explain` |

**Two blockers sit on the MVP.** Both are on the US-FIQA leg. The `images → degradation → ofiqpy →
components` half of the slice has no blocker against it and can proceed while R1 and R2 are
resolved.
