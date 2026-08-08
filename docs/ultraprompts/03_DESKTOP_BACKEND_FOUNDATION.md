# OpenFIQA Studio
## Biometric Quality & Verification IDE

> Autonomous PRD / UltraPrompt execution artifact

### Global operating rules

Act as a principal research-software engineering organization. Inspect actual repositories and runtimes before making implementation claims. Build working software, run tests, capture evidence, repair failures, and continue through all unblocked nodes autonomously.

Never fabricate a successful run, reproduced result, model capability, package version, standard-conformance result, or test outcome. Keep `COMPUTED`, `VALIDATED`, `REPRODUCED`, `CONFORMANT`, and `PUBLICATION-READY` as separate states. Preserve engine-specific semantics for OFIQ, OFIQpy, US-FIQA, OpenFIQA, matchers, and learned models. Never silently normalize or equate scores across engines. Preserve dirty Git state and experimental artifacts before modification. Never expose restricted biometric data or credentials in public artifacts.

Autonomous repair loop:

```text
INSPECT → PLAN ATOMIC CHANGE → IMPLEMENT → TEST → FUNCTIONAL RUN
→ INSPECT OUTPUT → ADVERSARIAL CRITIC
   ├─ defect → REPAIR → RETEST
   ├─ external blocker → DOCUMENT → CONTINUE OTHER BRANCHES
   └─ pass → CAPTURE EVIDENCE → COMMIT → HANDOFF
```

Persistent state:

```text
orchestration/state.json
orchestration/evidence.jsonl
orchestration/blockers.md
orchestration/decisions/
```

Allowed states: `NOT_READY | READY | RUNNING | NEEDS_REVISION | BLOCKED | PASSED`.

Every passed node requires evidence: Git SHA, exact commands, exit codes, tests, outputs, hashes, and critic result.

# UltraPrompt 03 — Desktop Shell, Python Backend, Project System, and Realtime Runtime

## Requirement

Deliver the executable application shell in which all scientific capabilities run.

## UX shell

```text
┌──────────────────────────────────────────────────────────────┐
│ Menu / command palette                                      │
├──────────────┬──────────────────────────────┬────────────────┤
│ Explorer     │ Workspace                    │ Inspector      │
│ datasets     │ graph/image/code/evaluation │ parameters     │
│ workflows    │                              │ provenance     │
│ models       │                              │ inputs/outputs │
│ runs         │                              │               │
├──────────────┴──────────────────────────────┴────────────────┤
│ Terminal | Runs | Metrics | Problems | GPU | Provenance     │
└──────────────────────────────────────────────────────────────┘
```

## Graph

```text
F01 repository bootstrap
 ├→ F02 FastAPI service
 ├→ F03 Tauri shell
 └→ F04 React IDE frame
      ↓
F05 backend lifecycle
 ↓
F06 HTTP APIs
 ↓
F07 WebSocket events
 ↓
F08 project create/open/save
 ↓
F09 command palette/routing
 ↓
F10 terminal/log panel
 ↓
F11 clean startup/shutdown tests
```

## Minimum APIs

`/api/health`, `/api/plugins`, `/api/projects`, `/api/workflows/validate`, `/api/runs`, `/api/models`, `/api/artifacts`, `/ws/runs/{run_id}`.

Realtime events must include run/node queued, started, stdout/stderr, metrics, artifact creation, completion/failure, and cancellation.

## Gate

Desktop launches backend; frontend observes health; project persists/reopens; synthetic runs stream events; cancellation works; backend terminates cleanly; scientific computations are not reimplemented in frontend code.
