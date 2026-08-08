# OpenFIQA Studio — project context

**Local path:** `/mnt/projects/OpenFIQAStudio/` · **GitHub:** `astoreyai/openfiqa-studio` (public)
· **License:** MIT · **Status:** planning stage, no implementation

The directory name and the repository name differ deliberately: `openfiqa-studio` is the canonical
repository name fixed by the naming contract in `docs/00_PROJECT.md`.

## What this repository is right now

Design documents, a validated JSON Schema type system, ten ADRs, a discovery inventory, and 18
passing tests. **No application.** No desktop shell, no backend service, no working adapter.

Do not scaffold placeholder modules, stub adapters, or empty test files to make it look further
along — under the no-stubs rule, code lands only when it does real work. The four plugin manifests
in `packages/schemas/plugins/` describe real engines and honestly report `UNVERIFIED` or `BLOCKED`;
none claims `AVAILABLE`, and a test enforces that.

**Build state is tracked, not remembered.** Read `orchestration/state.json` for phase states,
`orchestration/blockers.md` for what is stuck and why, `orchestration/evidence.jsonl` for what was
actually run with real exit codes, and `orchestration/handoffs/` for what each phase concluded.
Update them as work proceeds; a phase is not PASSED until its gate has been executed and recorded.

**Test baseline: 18 passed, exit 0** (`.venv/bin/python -m pytest tests/ -q`). Diff against that
number before claiming no regressions.

**The binding blocker is B-P04-00:** no authorized fixture corpus exists, so no engine has
processed a biometric sample. Do not resolve it by generating an image. That is fabricated
biometric data and it invalidates every downstream quality number.

## Naming contract (do not drift)

| Concept | Canonical name |
|---|---|
| Product | OpenFIQA Studio |
| Short name | OFS |
| Repository | `openfiqa-studio` |
| CLI | `openfiqa-studio` |
| Python package | `openfiqa_studio` |
| Existing research project | OpenFIQA |
| Existing Python distribution | `ofiq-quality` (import `ofiq_quality`) |
| Pure-Python BSI port | `ofiqpy` |
| C++ reference implementation | `OFIQ-Project` |
| Unified research model | US-FIQA |

## Hard invariants

1. **Never equate scores across engines.** OFIQ, OFIQpy, OpenFIQA, and US-FIQA each keep their
   own feature semantics, ranges, configuration, provenance, and version. No universal epsilon,
   no silent normalisation.
2. **Studio orchestrates, it does not reimplement.** Scientific computation stays in the engines
   and is reached through adapters. The frontend never recomputes a metric for UI convenience.
3. **No biometric data in this repository, ever.** No imagery, no subject identifiers, no
   restricted samples in fixtures. `.gitignore` blocks image and model extensions by default.
4. **Computed ≠ validated ≠ reproduced ≠ conformant.** These are four distinct states and must
   stay distinguishable in every surface that reports a result.
5. **Public repo.** Everything committed here is world-readable. Internal positioning, agency
   strategy, and unpublished results do not belong in it.

## Source repositories to integrate (local, not vendored)

```text
/mnt/projects/02_perception_biometrics/ofiq_29794/     # US-FIQA / ISO 29794-5 components
/mnt/projects/02_perception_biometrics/ofiqpy/         # BSI OFIQ Python port (PyPI)
/mnt/projects/02_perception_biometrics/OFIQ-Project/   # BSI C++ reference fork
```

Inventory their Git state before touching them; integrate through adapters, never by bulk copy.

## Documents

- `docs/00_PROJECT.md` — mission, naming contract, design principles
- `docs/01_PRD.md` — 40-section product requirements document
- `docs/02_ULTRAPROMPT.md` — 38-node autonomous build specification with gates
- `docs/03_CONFORMANCE_AND_TE_REQUIREMENTS.md` — 50 standards-conformance and T&E requirements
