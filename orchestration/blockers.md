# Blockers

Live register. An entry leaves this file only when its clearing condition is met and the evidence
is recorded in `evidence.jsonl`. Per the global operating rules, a blocker is documented and other
branches continue — it is never worked around by fabricating the missing thing.

| ID | Blocks | Severity | State |
|---|---|---|---|
| B-P01-01 | P04 B07, MVP slice | Blocker | OPEN |
| B-P01-02 | P04 B06/B07, MVP slice | Blocker | OPEN |
| B-P04-00 | P04 B01, P05, P12 | Blocker | OPEN — **needs Aaron** |
| B-P01-03 | trustworthy US-FIQA output | High | OPEN — upstream |
| B-P01-04 | P04 B03 | High | OPEN |
| B-P01-05 | provenance correctness | Medium | OPEN — upstream |
| B-P01-06 | P02 A09, P03 | Medium | OPEN — resolve in P02 |
| B-P01-08 | P09 P11, P10 T10 | Medium | OPEN — needs a decision |

---

## B-P04-00 — No authorized fixture corpus exists · **BLOCKER · NEEDS AARON**

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
