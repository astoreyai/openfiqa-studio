# N01 — Repository Map

**Discovery date:** 2026-08-07
**Method:** read-only inspection. No source repository was modified, and no engine was executed
beyond `--help` and `info` subcommands.
**Redaction:** one source repository is not publicly released. It is described by role and
capability only; its remote, branch, commit, and local paths are withheld. The unredacted map is
kept locally and is not tracked by this repository.

---

## Boundary resolution

The PRD and ultraprompt name five entities — OFIQ, OFIQpy, OpenFIQA, `ofiq-quality`, US-FIQA —
without fixing the boundaries between them. N01 resolves them to **four distinct invocation
surfaces**, which is not the same partition the PRD assumed.

| PRD name | Resolves to | Kind |
|---|---|---|
| OFIQ | `OFIQ-Project` C++ reference | Component extractor |
| OFIQpy | `ofiqpy` distribution | Component extractor |
| OpenFIQA | `openfiqa` distribution | Component extractor + normative scorer |
| `ofiq-quality` | `ofiq-quality` distribution | Unified scorer over extracted features |
| US-FIQA | **the `ofiq-quality` distribution** | — same as above |

**US-FIQA and `ofiq-quality` are one engine, not two.** Confirmed with the project owner
2026-08-07; `ofiq-quality`'s own CLI describes itself as the "Unified Facial Image Quality
Scoring Framework."

**The PRD's parallel-engine model is wrong.** `docs/01_PRD.md` §1 and the core pipeline in
`docs/00_PROJECT.md` place all four engines at the same pipeline stage:

```text
OFIQ / OFIQpy / OpenFIQA / US-FIQA        ← as written, incorrect
```

Three of the four consume images and emit quality components. US-FIQA consumes **pre-extracted
features** and emits a single unified score; it accepts no image input. It is a downstream node,
not a peer. The corrected topology is:

```text
Image ──┬─→ OFIQ C++   ──┐
        ├─→ OFIQpy      ─┼─→ component table ──→ feature engineering ──→ US-FIQA ──→ unified score
        └─→ OpenFIQA   ──┘
```

The `feature engineering` stage is a real, required, and currently unpackaged step. See
[`integration-risks.md`](integration-risks.md) R1.

---

## R1 · ofiqpy

| Field | Value |
|---|---|
| Remote | `git@github.com:AVHBAC/ofiqpy.git` (public) |
| Branch / commit | `main` @ `c80fb38` |
| Working tree | clean, 0 modified paths |
| On-disk size | 722 MB |
| Distribution | `ofiqpy`, `pyproject.toml` declares **0.1.1** |
| Import package | `ofiqpy` |
| CLI | `ofiqpy` → `ofiqpy.cli:main` |
| Python API | `ofiqpy.assess(image) -> dict` |
| Tests | `tests/` present |
| License | MIT |

**Version inconsistency:** `pyproject.toml` declares `version = "0.1.1"` but the imported module
reports `ofiqpy.__version__ == "0.1.0"`. Provenance records must capture both, or capture the
commit rather than the version string. This is exactly the failure mode T&E requirement 14
(implementation provenance) and 7 (standards-version pinning) exist to prevent.

**Not importable from the system interpreter** — `import ofiqpy` fails under `python3` without the
repository on `sys.path` or its own `.venv` activated. Each engine needs its own resolved
environment; the studio cannot assume one shared interpreter.

## R2 · OFIQ-Project

| Field | Value |
|---|---|
| Remote | `https://github.com/BSI-OFIQ/OFIQ-Project.git` (public, fork) |
| Branch / commit | `main` @ `bb5dc91` |
| Working tree | **44 modified paths — uninventoried** |
| On-disk size | 981 MB |
| Kind | C++ / CMake, `build/` and `install_x86_64_linux/` present |
| License | see `LICENSE.md` (BSI terms, not MIT) |

The 44 uncommitted paths must be inventoried and preserved before any adapter work touches this
tree. The ultraprompt is explicit: *do not modify source repositories before their Git state is
inventoried and preserved.* Until that is done, this repository is read-only.

## R3 · OpenFIQA workspace *(source repository not publicly released — identifiers withheld)*

A `uv` workspace whose `pyproject.toml` carries **no `[project]` table by design**. Its ADR-002
fixes the repository at **exactly two published distributions**; a third would be created
accidentally by adding a root project table. Both are installed in the workspace's own virtual
environment.

| Distribution | Local version | CLI | Role |
|---|---|---|---|
| `openfiqa` | 0.5.0 | `openfiqa` → `openfiqa.cli:main` | ISO/IEC 29794-5:2025 component extraction + normative scoring |
| `ofiq-quality` | 0.2.0 | `ofiq-quality` → `ofiq_quality.cli:main` | Unified score prediction from pre-extracted features (**= US-FIQA**) |

Both declare MIT and `requires-python >= 3.10`. Version numbers are local working versions and
should not be read as released artifacts.

The workspace also contains research material, including a paper-track directory whose scripts
implement the feature-engineering stage that US-FIQA depends on. That code is not part of either
published distribution.

---

## Consequence for the naming contract

`docs/00_PROJECT.md` lists `ofiq-quality` as *the* existing Python distribution and does not
account for a distribution named `openfiqa`. One exists. The contract predates the workspace
refactor and has been corrected in that file as part of N01.

## Consequence for the delivery plan

- **N11 (US-FIQA adapter) keeps its node** but changes type: its input edge is a feature table,
  not an image. It cannot be modelled as a peer of N08–N10.
- **N04 (shared schemas) must define a `FeatureTable` type** distinct from `Image` and from
  `ComponentTable`, before any adapter is written.
- **The MVP vertical slice in `01_PRD.md` §36 is not executable as written.** See
  [`integration-risks.md`](integration-risks.md) R1 and R2.
