# Reconciliation — where this series is superseded by P01 findings

The thirteen prompts in this directory are the execution spine. They were written before discovery
ran. P01 executed on 2026-08-07 and disproved five things the series assumes. **Where this
directory and the discovery documents disagree, the discovery documents win** — they were produced
by inspecting the actual repositories, and the evidence is in `orchestration/evidence.jsonl`.

| # | The series says | Discovery found | Affects |
|---|---|---|---|
| C1 | US-FIQA and `ofiq-quality` are separate adapters (`04`, B06 and B07) | One engine. `ofiq-quality` self-describes as the Unified Facial Image Quality Scoring Framework | `04` |
| C2 | `OFIQ / OFIQpy / US-FIQA / OpenFIQA` sit at one pipeline stage | `ofiq-quality predict` takes `FEATURES_PATH` and accepts no image. It is downstream, not a peer | series `README`, `00`, `12` step 11 |
| C3 | Extraction feeds scoring directly | A feature-engineering stage sits between them, produces 20 of 47 columns, and is packaged nowhere | `04`, `06` node classes |
| C4 | The OpenFIQA workspace publishes one distribution | Two — `openfiqa` 0.5.0 and `ofiq-quality` 0.2.0, fixed by its ADR-002 | `01`, `04` |
| C5 | The standards registry (`10` T02) is to be built | `openfiqa profiles` already implements one: `iso-29794-5` (27 components) and `icao-9303` (17), five modes each with accept/reject thresholds | `10` |

Full statements with evidence: [`../../orchestration/handoffs/P01.yaml`](../../orchestration/handoffs/P01.yaml)
under `canonicalization_findings`.

## Two additions the series has no slot for

**A `FeatureEngineering` plugin kind.** C3 established a required stage that none of the ten plugin
kinds in `02` can express. Without it the gap is unrepresentable, and a graph would silently wire an
extractor into US-FIQA. Added in `packages/schemas/plugin.schema.json`.

**A `BLOCKED` availability state.** Two of four engines cannot run. The series assumes a plugin
either works or is absent. A registry with only those two options must either hide a blocked engine
or misreport it. Added, with `blocker_id` and `reason` required whenever the state is `BLOCKED` or
`DEGRADED`.

## Relationship to `docs/02_ULTRAPROMPT.md`

Both describe the same build. The single-file version carries node-level detail (N01–N38) that this
series compresses; this series carries the gate, evidence, and handoff discipline that the
single-file version lacks. **This series is the execution order.** `02_ULTRAPROMPT.md` is retained
as node-level reference, not as a second plan. Where they conflict, this series wins — and where
either conflicts with discovery, discovery wins.

## What is not superseded

The global operating rules at the head of every prompt hold in full, and P01/P02 were executed under
them: no fabricated run, no invented capability, separate scientific states, no silent
normalisation across engines, dirty Git state preserved, no restricted data in public artifacts.
