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

# UltraPrompt 11 — Security, Privacy, Supply Chain, Validation, CI/CD, and Release Engineering

## Requirement

Biometric data and executable ML/research code make security and reproducibility first-class product requirements.

## Graph

```text
S01 threat model
 ├→ S02 biometric-data boundary
 ├→ S03 command-execution boundary
 ├→ S04 secrets/logging review
 └→ S05 plugin trust model
      ↓
S06 dependency/SBOM
 ↓
S07 package integrity
 ↓
S08 CI matrix
 ↓
S09 unit/integration/E2E suite
 ↓
S10 clean-machine install
 ↓
S11 offline/local mode
 ↓
S12 performance/resource tests
 ↓
S13 documentation build
 ↓
S14 release candidate
 ↓
S15 independent audit
```

## Security requirements

Local-first processing; no default cloud upload; no biometric telemetry; restricted samples excluded from public fixtures; sanitized logs; explicit executable registration; shell-injection defenses; constrained filesystem permissions; plugin trust state; model hash verification; dependency locks; SBOM; reproducible release manifests where practical.

## CI separation

```text
frontend unit
backend unit
adapter integration
workflow tests
numerical regression
package/build
desktop E2E
documentation
security/static analysis
```

Full private-data experiments do not belong in public CI.

## Release evidence

```text
RELEASE_READINESS.md
SECURITY_REVIEW.md
SCIENTIFIC_VALIDATION.md
KNOWN_LIMITATIONS.md
SBOM
build hashes
test report
supported-platform matrix
```

## Gate

A clean environment installs, launches, discovers fixture plugins, executes the canonical workflow, produces artifacts, shuts down cleanly, and reproduces deterministic hashes where expected.
