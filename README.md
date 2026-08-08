# OpenFIQA Studio

**Biometric Quality & Verification IDE**

> Build, break, measure, verify.

A local-first scientific IDE for face image quality assessment, verification research, controlled
degradation experiments, model development, reproducible evaluation, and publication artifact
generation.

---

## Status

**Planning stage. There is no implementation in this repository yet.**

What exists here is the design record: the naming contract, a full product requirements document,
an executable build specification, and a standards-conformance requirements set. Code will land
against those documents, not ahead of them. Nothing in this repository is a working component,
and no benchmark, figure, or measurement is reported anywhere in it.

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
OFIQ / OFIQpy / OpenFIQA / US-FIQA
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

| Project | Role |
|---|---|
| [`OFIQ-Project`](https://github.com/BSI-Bund/OFIQ-Project) | BSI C++ reference implementation of ISO/IEC 29794-5 |
| `ofiqpy` | Behaviour-preserving pure-Python port of BSI OFIQ |
| `ofiq-quality` / OpenFIQA | Research quality implementation |
| US-FIQA | Unified research model |

## Data handling

The IDE is useful with no network access and no cloud service. Defaults, specified in
`docs/01_PRD.md` §35: no automatic upload, no telemetry containing biometric images or subject
identifiers, no image transmission without explicit user action, no public artifact export
containing restricted samples, no credentials in run logs, and no private biometric samples in
public test fixtures.

**No biometric imagery, dataset, or model is distributed in this repository.**

## License

MIT — see [`LICENSE`](LICENSE).
