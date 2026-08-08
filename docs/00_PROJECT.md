# OpenFIQA Studio

**Subtitle:** Biometric Quality & Verification IDE  
**Repository:** `openfiqa-studio`  
**Application:** OpenFIQA Studio  
**Abbreviation:** OFS  
**CLI:** `openfiqa-studio`  
**Python namespace:** `openfiqa_studio`  

## Mission

OpenFIQA Studio is a local-first scientific IDE for biometric image-quality assessment, verification research, controlled degradation experiments, machine-learning model development, reproducible evaluation, and publication artifact generation.

It unifies OFIQ, OFIQpy, OpenFIQA/ofiq-quality, US-FIQA, biometric matchers, degradation operators, model training/fine-tuning, evaluation routines, visualization, and legacy research scripts behind a typed workflow graph and a provenance-aware execution engine.

## Product identity

OpenFIQA Studio is **not** a replacement implementation of OFIQ, OFIQpy, US-FIQA, or OpenFIQA. It is the orchestration, experimentation, visualization, and reproducibility layer above them.

The project should preserve the scientific identity of every engine and never silently normalize or equate scores from different FIQA systems.

## Core product promise

A researcher should be able to construct and execute:

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

and trace every result back to the exact code, model, parameters, inputs, transformations, environment, random seeds, run, and Git commit that produced it.

## Canonical repositories

Recommended separation:

```text
openfiqa/                # scientific packages and publication implementation
openfiqa-studio/         # desktop IDE, graph runtime, adapters, UI
ofiqpy/                  # independently versioned BSI OFIQ Python port
OFIQ-Project/            # independently versioned BSI C++ reference fork
```

## Naming contract

| Concept | Canonical name |
|---|---|
| Product | OpenFIQA Studio |
| Short name | OFS |
| GitHub repository | `openfiqa-studio` |
| Desktop executable | `OpenFIQA Studio` |
| CLI | `openfiqa-studio` |
| Python package | `openfiqa_studio` |
| Existing research project | OpenFIQA |
| Existing Python distribution | `ofiq-quality` |
| Existing import package | `ofiq_quality` |
| Pure-Python BSI port | `ofiqpy` |
| C++ reference implementation | `OFIQ-Project` |
| Unified research model | US-FIQA |

## Tagline options

Primary:

> **Build, break, measure, verify.**

Technical:

> **A provenance-first IDE for biometric quality and verification research.**

Publication-facing:

> **Visual biometric experimentation from sample degradation to reproducible evidence.**

## Design principles

1. Scientific computations remain in Python/C++ implementations, not duplicated in the frontend.
2. Graphs are executable, typed, serializable, diffable, and headless-runnable.
3. Computed, validated, reproduced, and scientifically supported are different states.
4. Every metric and figure has machine-readable provenance.
5. Existing scripts can run as first-class graph nodes before they are refactored.
6. Image degradation is a first-class experiment primitive.
7. Aggregate metrics must link back to individual samples and failure cases.
8. Models retain complete training, checkpoint, dataset, and run lineage.
9. Public exports must not accidentally contain restricted biometric data.
10. The IDE remains useful locally without cloud services.
