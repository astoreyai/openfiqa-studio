# OpenFIQA Studio

**Biometric Quality & Verification IDE**

> Build, break, measure, verify.

A local-first scientific IDE for face image quality assessment, verification research, controlled
degradation experiments, model development, reproducible evaluation, and publication artifact
generation.

---

## Status

**Under construction. 2 of 12 build phases complete. The application does not exist yet.**

| Phase | State |
|---|---|
| P01 Discovery & Canonicalization | **PASSED** |
| P02 Product Architecture & Schemas | **PASSED** — 18/18 tests, exit 0 |
| P03 Desktop + Backend Foundation | READY — toolchain verified |
| P04–P12 | not started |

What exists is the design record, a validated scientific type system, and a discovery inventory of
the engines the studio will drive. There is no desktop shell, no backend service, and no working
adapter. **No engine has processed a biometric sample**, because no authorized fixture corpus is
available — see `orchestration/blockers.md`, B-P04-00. No benchmark, figure, or measurement is
reported anywhere in this repository.

Live state: [`orchestration/state.json`](orchestration/state.json) ·
blockers: [`orchestration/blockers.md`](orchestration/blockers.md) ·
evidence: [`orchestration/evidence.jsonl`](orchestration/evidence.jsonl)

## What it is

OpenFIQA Studio is the orchestration, experimentation, visualisation, and reproducibility layer
*above* existing quality engines. It is **not** a replacement implementation of OFIQ, OFIQpy,
US-FIQA, or OpenFIQA, and it must never silently normalise or equate scores from different FIQA
systems — each engine keeps its own feature semantics, ranges, configuration, provenance, and
version.

The core promise is that a researcher can construct and execute:

```text
Dataset
   ↓
Degradation / preprocessing
   ↓
OFIQ / OFIQpy / OpenFIQA          (component extraction)
   ↓
Feature engineering                (polarity normalisation + composites)
   ↓
US-FIQA                            (unified scoring)
   ↓
Matcher / ML model
   ↓
Verification + FIQA evaluation
   ↓
Visualization + failure analysis
   ↓
Publication artifact
```

and trace every result back to the exact code, model, parameters, inputs, transformations,
environment, random seeds, run, and Git commit that produced it.

## Two layers

The IDE is the first layer. The second is a controlled evaluation environment built on the same
graph runtime, adapter registry, and provenance engine:

```text
OpenFIQA Studio                        →   OpenFIQA Studio — T&E Edition
Biometric Quality & Verification IDE       Standards Conformance, Quality Assurance
                                           & Biometric Evaluation Workbench
```

The exploratory mode answers *what does this data show*. The T&E mode answers *does this
implementation conform, and can that finding be reproduced by someone else*. Requirements for the
second layer — conformance adapters for ISO/IEC 29794-5, DoD EBTS, NATO STANAG 4715, and INTERPOL
biometric transmission specifications; implementation equivalence testing; end-to-end evidence
lineage; one-click reproduction — are specified in
[`docs/03_CONFORMANCE_AND_TE_REQUIREMENTS.md`](docs/03_CONFORMANCE_AND_TE_REQUIREMENTS.md).

## Documents

| File | Contents |
|---|---|
| [`docs/00_PROJECT.md`](docs/00_PROJECT.md) | Canonical name, mission, naming contract, repository identity, design principles |
| [`docs/01_PRD.md`](docs/01_PRD.md) | Product requirements — 40 sections, from execution model to delivery phases |
| [`docs/02_ULTRAPROMPT.md`](docs/02_ULTRAPROMPT.md) | Autonomous build specification — 38 execution nodes with gates and acceptance criteria |
| [`docs/03_CONFORMANCE_AND_TE_REQUIREMENTS.md`](docs/03_CONFORMANCE_AND_TE_REQUIREMENTS.md) | 50 standards-conformance and test-and-evaluation requirements |
| [`docs/discovery/repository-map.md`](docs/discovery/repository-map.md) | N01 — source repositories and engine boundary resolution |
| [`docs/discovery/capability-map.md`](docs/discovery/capability-map.md) | N02 — per-engine capability inventory, confirmed vs unresolved |
| [`docs/discovery/integration-risks.md`](docs/discovery/integration-risks.md) | N01 — risk register, two blockers on the MVP |
| [`config/engine-capabilities.yaml`](config/engine-capabilities.yaml) | Machine-readable capability inventory |
| [`config/repository-locks.yaml`](config/repository-locks.yaml) | Source repositories pinned to exact commits |
| [`docs/ultraprompts/`](docs/ultraprompts/) | The 13-prompt build series, P00–P12 |
| [`docs/ultraprompts/RECONCILIATION.md`](docs/ultraprompts/RECONCILIATION.md) | Where discovery superseded the series |
| [`orchestration/decisions/`](orchestration/decisions/) | ADR-0001 … ADR-0010 |
| [`packages/schemas/`](packages/schemas/) | JSON Schema — the source of truth for scientific types |

## Running the tests

```bash
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python pytest jsonschema
.venv/bin/python -m pytest tests/ -q
```

Current baseline: **18 passed, exit 0.** The suite is mostly negative tests — it fails if a model
discovery disproved (a bare score float, a feature table treated as a quality vector, a plugin
claiming a capability it has not demonstrated) becomes representable again.

## Intended architecture

Recorded in `docs/01_PRD.md` §3 and not yet built:

- **Desktop** — Tauri 2, React, TypeScript, `@xyflow/react` node graph, Monaco-compatible editor
- **Control plane** — FastAPI, WebSockets for live logs and run state, worker processes, typed
  adapter registry
- **ML and analytics** — PyTorch, ONNX Runtime, MLflow, Optuna, SQLite for metadata, Parquet for
  tabular outputs, DuckDB for interactive queries

The frontend configures, launches, observes, filters, and visualises scientific operations. It
does not reimplement OFIQ, OFIQpy, US-FIQA, OpenFIQA, matcher metrics, or training logic for UI
convenience.

## Related projects

OpenFIQA Studio integrates these through adapters rather than vendoring their source:

| Project | Role | Stage |
|---|---|---|
| [`OFIQ-Project`](https://github.com/BSI-OFIQ/OFIQ-Project) | BSI C++ reference implementation of ISO/IEC 29794-5 | Component extraction |
| [`ofiqpy`](https://github.com/AVHBAC/ofiqpy) | Behaviour-preserving pure-Python port of BSI OFIQ | Component extraction |
| `openfiqa` | ISO/IEC 29794-5:2025 components + `standard:mode` profile scoring | Component extraction |
| `ofiq-quality` (**= US-FIQA**) | Unified score predicted from a 47-column engineered feature table | Unified scoring |

The four are not interchangeable and do not sit at the same pipeline stage — US-FIQA accepts no
image input. Boundaries, capabilities, and integration risks are recorded in
[`docs/discovery/`](docs/discovery/).

## Data handling

The IDE is useful with no network access and no cloud service. Defaults, specified in
`docs/01_PRD.md` §35: no automatic upload, no telemetry containing biometric images or subject
identifiers, no image transmission without explicit user action, no public artifact export
containing restricted samples, no credentials in run logs, and no private biometric samples in
public test fixtures.

**No biometric imagery, dataset, or model is distributed in this repository.**

## License

MIT — see [`LICENSE`](LICENSE).
