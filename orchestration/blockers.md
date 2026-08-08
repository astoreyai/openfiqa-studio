# Blockers

Live register. An entry leaves this file only when its clearing condition is met and the evidence
is recorded in `evidence.jsonl`. Per the global operating rules, a blocker is documented and other
branches continue — it is never worked around by fabricating the missing thing.

| ID | Blocks | Severity | State |
|---|---|---|---|
| B-P01-01 | P04 B07, MVP slice | Blocker | OPEN |
| B-P01-02 | P04 B06/B07, MVP slice | Blocker | OPEN |
| B-P04-00 | P04 B01, P05, P12 | Blocker | **CLEARED 2026-08-07** |
| B-P01-09 | P04 B04 provenance, licensing | High | OPEN |
| B-P01-03 | trustworthy US-FIQA output | High | OPEN — upstream |
| B-P01-04 | P04 B03 | High | OPEN |
| B-P01-05 | provenance correctness | Medium | OPEN — upstream |
| B-P01-06 | P02 A09, P03 | Medium | OPEN — resolve in P02 |
| B-P01-08 | P09 P11, P10 T10 | Medium | OPEN — needs a decision |

---

## B-P01-09 — ofiqpy is not standalone; it loads BSI-licensed data at runtime · **HIGH**

`ofiqpy` reads `ofiq_config.jaxn` and every model weight from an **OFIQ-Project checkout**, not
from its own package. Its config module states the reason plainly: the models "are separately
licensed and NOT bundled", and the port reuses them "so the port loads the *same* weights OFIQ
uses". The path defaults to the CWD-relative `OFIQ-Project/data` and is overridable only through
the `OFIQPY_OFIQ_DATA` environment variable. Without it, `assess()` raises `FileNotFoundError`.

*Evidence:* the first execution attempt failed on exactly that path; setting the variable to the
locked OFIQ-Project checkout produced 28 components, rc=0.

*Impact, three ways.* Deployment — an adapter that forgets the variable fails at runtime, so it is
declared in the manifest as `required_env`. Licensing — an MIT package requires BSI-licensed assets
to function, which matters for any redistribution claim. Provenance — an ofiqpy result is a
function of *two* commits, its own and whichever OFIQ-Project checkout supplied the weights, so
recording the ofiqpy version alone under-specifies the run.

*Clears when:* the adapter records both commits in every provenance entry, and the licensing
consequence is stated wherever ofiqpy is described as MIT.

## ~~B-P04-00~~ — No authorized fixture corpus · **CLEARED 2026-08-07**

Resolved without a download. **LFW** was already present at `/mnt/projects/datasets/lfw` —
`lfw_funneled/` with **13,233 real JPEGs** in subject-labelled directories, 521 MB, plus the
official `pairs.txt` verification protocol. Public, real, subject-labelled, with a genuine
enrollment/probe pairing scheme.

Referenced by manifest and hash; **never copied into this repository**. See
`config/fixture-corpus.yaml`.

One caveat that matters for interpretation rather than for the block: LFW is not a passport-style
corpus. The first real run scored `HeadSize` 14, `InterEyeDistance` 19, and `UnifiedQualityScore`
12 on a 250×250 funneled image. Those low values are the correct behaviour of an ISO/IEC 29794-5
implementation on low-resolution web photography, not a defect — but a degradation study needs
headroom above its starting point, so LFW is a good pipeline fixture and a poor degradation
baseline.

<details>
<summary>Original blocker text, retained for the record</summary>

### No authorized fixture corpus exists · BLOCKER · NEEDS AARON

P04 B01 requires a fixture corpus. P05 requires a dataset to import. P12 step 3 requires importing
a fixture or authorized dataset. **No face image is available to this build.**

`ofiqpy/tests/` contains `test_smoke.py`, `verify_ofiq.py`, and `gate_slice.py` — no image files.
A search of `tests/`, `examples/`, and the package tree for `*.png|*.jpg|*.jpeg|*.bmp` returned
nothing.

This cannot be worked around. Generating a face image, or any stand-in for one, would be
fabricated biometric data, which the project rules forbid outright and which would make every
downstream quality number meaningless. The correct state is BLOCKED, not "tested on a synthetic
sample."

*Consequence:* no engine can be executed on a biometric sample. Every adapter capability that
requires processing an image is unverifiable until this clears — including the ofiqpy component
list and score direction left unresolved in `capability-map.md`.

*Clears when:* Aaron names a dataset that is licensed and authorized for use as a development
fixture, and states whether it may be referenced by manifest only (restricted) or copied into a
local fixture directory. It must never enter the public repository under either answer.

</details>

## B-P01-01 — No packaged producer for the 47-column feature contract · **BLOCKER**

`ofiq-quality` consumes 47 columns; extractors emit 27. The 7 `_polnorm` and 13 engineered columns
come from a feature-engineering stage exposed by neither published distribution.

*Clears when:* that stage is confirmed callable as a library function with a pinned input contract,
and is modelled as an explicit graph node between extraction and scoring.

## B-P01-02 — US-FIQA model directory does not satisfy the CLI contract · **BLOCKER**

`ofiq-quality predict` requires `--model-dir` containing `quality_predictor.onnx`, `scaler.pkl`,
`model_config.json`. The research model directory contains `quality_predictor_xgboost.onnx`,
`scaler_params.json`, and `feature_columns.json`. Zero of three names match.

*Clears when:* a conforming model directory is located, or the names are reconciled **and**
`scaler_params.json` is shown to load through a `scaler.pkl` code path. The second half is the
part most likely to fail after a rename.

## B-P01-03 — Upstream polarity map is wrong for 10 of 27 components · **HIGH**

Recorded upstream on 2026-08-06, in shipped package data rather than paper-only material. The 7
`_polnorm` columns derive from it.

*Clears when:* the upstream fix lands and the studio pins `ofiq-quality` at or after that version.
Until then any US-FIQA adapter must record the polarity-map revision in provenance, and no US-FIQA
score may be promoted past `COMPUTED`.

## B-P01-04 — OFIQ-Project has 44 unpreserved modified paths · **HIGH**

`bb5dc91d00477e02ce53d2530d28e35021484393`, 44 dirty paths. The global rules require dirty state be
preserved before modification; `repository-locks.yaml` marks the tree `frozen_until_preserved`.

*Clears when:* the 44 paths are classified and preserved on a branch or stash with a recorded SHA.

## B-P01-05 — ofiqpy version strings disagree · **MEDIUM**

`pyproject.toml` says `0.1.1`; `ofiqpy.__version__` says `0.1.0` (confirmed, rc=0).

*Clears when:* adapters record the commit SHA as the authoritative provenance key, and the
mismatch is reported upstream. `engine-capabilities.yaml` already sets
`version_authoritative: null` for this reason.

## B-P01-06 — No shared interpreter across engines · **MEDIUM**

`import ofiqpy` fails under the system `python3`; the OpenFIQA workspace runs its own 3.11.2
environment with `torch 2.13.0+cu130`.

*Clears when:* P02 A09 records an ADR for per-engine environment resolution. This must be decided
before adapters exist, not retrofitted.

## B-P01-08 — One engine's source is not publicly released · **MEDIUM**

*Consequence:* third-party reproduction cannot cover the US-FIQA path. A reproduction verdict for a
US-FIQA result must be `BLOCKED` with a reason, which P09's state set already supports.

*Clears when:* release status is decided, or `BLOCKED — source unavailable` is implemented as a
first-class reproduction outcome rather than an error.

## B-P03-01 — The desktop window has never been opened · **MEDIUM · NEEDS AARON**

Two clauses of the P03 gate require a display: *desktop launches backend* and *frontend observes
health*. This machine is headless, so neither has been executed.

What **is** verified: the shell compiles to an 11 MB ELF linking webkit/gtk; the frontend builds
under `tsc` strict; the control plane serves every endpoint the frontend calls; CORS admits the
Tauri and dev-server origins and refuses others; and the WebSocket path the log panel uses streams
`queued → started → stdout → completed` end-to-end against a real subprocess.

What is **not**: that the window opens, renders, and paints. Compilation is not rendering, and
saying "verified on device" here would be exactly the claim the operating rules forbid.

*Impact:* none on P04–P08, which are backend and adapter work. This blocks only the final P12
acceptance walk, which drives the GUI.

*Clears when:* Aaron runs it on a machine with a display —
`cd apps/desktop && pnpm build && cd src-tauri && cargo run --release`, with the control plane up
via `.venv/bin/python -m uvicorn studio_backend.app:app --app-dir python --port 8790`.

## B-P04-08 — No matcher exists in this workspace · **BLOCKER**

P07's metrics — ROC, DET, FMR/FNMR/TAR/FRR, EER, ERC, AU-ERC, quality-conditioned performance —
all take **matcher comparison scores** as input. There is no face matcher in this workspace, and
no score set to import. LFW ships the pair protocol (6000 pairs, verified) but not scores.

*Why this cannot be worked around:* the FIQA question that matters is *does the quality measure
predict conditions associated with biometric failure* (T&E requirement 24). Answering it needs
genuine recognition outcomes. Computing ERC over invented scores would produce a curve that looks
exactly like an evaluation and measures nothing — the most dangerous possible artifact for this
product, because it is indistinguishable from a real result.

*Impact:* P07 in full, and the parts of P12 that walk ROC/ERC.

*Clears when:* Aaron names a matcher available for use (an ArcFace/MagFace ONNX checkpoint would
be enough — `magface_iresnet50_norm.onnx` is already in the OFIQ-Project tree but is a quality
model, not an identity embedder), or supplies a precomputed score set for the LFW protocol.

## B-P04-11 — openfiqa runs DEGRADED: no CUDA, and a cross-version model unpickle · **MEDIUM**

`openfiqa` works. It produced 28 component scores and a unified score of 68.3 on a real LFW face,
rc=0. Two conditions stop it being `AVAILABLE`:

**CUDA is unavailable.** The workspace venv carries `torch 2.13.0+cu130`; this machine's NVIDIA
driver reports **12020** (CUDA 12.2). Left to itself the CLI raises in `torch._C._cuda_init()`, so
the adapter forces `--device cpu`. CPU and GPU code paths are not guaranteed to produce identical
values, and no comparison between them has been made here.

**A model is unpickled across a scikit-learn version boundary.** The C08 Sharpness head is a
`RandomForestClassifier` saved under 1.8.0 and loaded under 1.9.0. scikit-learn's own warning says
this "might lead to breaking code or invalid results". C08 scored **1** on an image where ofiqpy's
named `Sharpness` scored **91** — the two are not the same measure and are not directly comparable,
but that gap is large enough to be worth resolving before either number is used.

*Also corrected:* an earlier note claimed openfiqa's weights had never been fetched on this machine.
That was wrong — `download-models` resolved every one of the five registered models from files
already in the workspace and downloaded nothing.

**Evidence that the C08 concern is not theoretical.** A 60-image study (2026-08-08) found openfiqa's
C08 returns exactly **0 on 39 of 60 images (65%)** and takes only **9 distinct values** across the
sample, where ofiqpy's named `Sharpness` takes 40 and spans 5–99 on those same 39 images. A
classifier collapsed to a handful of values, mostly zero, is what a broken unpickle looks like —
though it is not proof, since C08 may be a legitimately coarse classifier and LFW is low-resolution
photography. See `docs/studies/2026-08-08-cross-engine-n60.md`.

**Until this clears, openfiqa's C08 must not be used as a sharpness measurement.**

*Clears when:* the venv's torch matches the driver (or a CPU-only build is pinned deliberately),
and the C08 head is re-saved under the scikit-learn version that loads it — after which the
degeneracy check should be re-run to see whether the zeros persist.
