# OpenFIQA Studio — UltraPrompt Loop/Graph PRD Series

**Product:** OpenFIQA Studio  
**Subtitle:** Biometric Quality & Verification IDE

This bundle decomposes the Studio build into a sequence of autonomous, evidence-gated engineering prompts. Each file is both a focused PRD and an execution specification.

## Execution order

1. `00_MASTER_ORCHESTRATOR.md`
2. `01_DISCOVERY_CANONICALIZATION.md`
3. `02_PRODUCT_ARCHITECTURE_SCHEMAS.md`
4. `03_DESKTOP_BACKEND_FOUNDATION.md`
5. `04_BIOMETRIC_ENGINE_INTEGRATION.md`
6. `05_DATASET_IMAGE_DEGRADATION_LAB.md`
7. `06_VISUAL_WORKFLOW_EXECUTION.md`
8. `07_EVALUATION_VISUALIZATION_FAILURE_ANALYSIS.md`
9. `08_ML_MODEL_TRAINING_FINETUNING.md`
10. `09_PROVENANCE_REPRODUCTION_PUBLICATION.md`
11. `10_DFBA_TE_STANDARDS_LAYER.md`
12. `11_SECURITY_VALIDATION_RELEASE.md`
13. `12_FINAL_ACCEPTANCE_GAUNTLET.md`

## Execution model

Do not paste the entire series into one context unless necessary. Run the master prompt, then execute each subsystem using the machine-readable handoff from its predecessor.

```text
Master
 ↓
Focused PRD/UltraPrompt
 ↓
Implementation
 ↓
Tests
 ↓
Functional execution
 ↓
Adversarial critic
 ↓
Repair loop
 ↓
Evidence
 ↓
Atomic commit
 ↓
Handoff
 ↓
Next subsystem
```

## Primary scientific vertical

```text
Dataset
 ↓
Preprocessing
 ↓
Degradation
 ↓
OFIQ / OFIQpy / US-FIQA / OpenFIQA
 ↓
Matcher
 ↓
Verification + FIQA utility
 ↓
Visualization + failure analysis
 ↓
Model training/fine-tuning
 ↓
Publication artifact
 ↓
Reproduction
 ↓
T&E evidence package
```

## Core rule

The Studio must preserve:

```text
COMPUTED ≠ VALIDATED ≠ REPRODUCED ≠ CONFORMANT ≠ PUBLICATION-READY
```

## Suggested repository

```text
openfiqa-studio/
├── apps/
│   ├── desktop/
│   └── backend/
├── packages/
│   ├── ui/
│   ├── graph/
│   ├── schemas/
│   └── client/
├── python/
│   ├── studio_core/
│   ├── adapters/
│   ├── execution/
│   ├── evaluation/
│   ├── training/
│   └── provenance/
├── workflows/
├── orchestration/
├── tests/
├── docs/
└── examples/
```
