# Cross-engine unified score — ofiqpy vs openfiqa, 60 LFW subjects

**n = 60**

Spearman rank correlation **+0.239** (SE ≈ 0.130) — interpretable.

| engine | min | median | mean | max |
|---|---|---|---|---|
| ofiqpy | 4.0 | 53.0 | 49.2 | 90.0 |
| openfiqa | 51.3 | 67.5 | 66.9 | 75.4 |

## Range overlap

The ranges overlap over 24.1 points, 28% of their combined span.

## Caveats

- ofiqpy.UnifiedQualityScore and openfiqa.unified_score are different quantities; this comparison uses 'rank' and asserts no numeric equivalence

These are `COMPUTED` values. Nothing here has been validated, reproduced by a third party, or checked against a recognition outcome — the question of whether either score predicts biometric failure needs a matcher, which this workspace does not have (B-P04-08).


---

# Component finding: openfiqa C08 looks degenerate

Comparing ofiqpy's named `Sharpness` against openfiqa's `C08` (its sharpness component) on the same
60 images:

| | ofiqpy.Sharpness | openfiqa.C08 |
|---|---|---|
| exactly 0 | 0 / 60 | **39 / 60 (65%)** |
| distinct values | 40 | **9** |
| range | 5–100 | 0–93 |

Spearman between them is +0.654 (SE 0.130), so they do rank
broadly together — but openfiqa's component collapses to zero on nearly two thirds of the sample
and takes only 9 distinct values across 60 images. On those 39 images ofiqpy's
Sharpness spans 5–99 with a median of 42: it
sees the full range of sharpness where openfiqa reports none.

## What this is evidence for, and what it is not

This is **consistent with** the second condition recorded in B-P04-11: openfiqa's C08 head is a
`RandomForestClassifier` pickled under scikit-learn 1.8.0 and loaded under 1.9.0, and
scikit-learn's own warning says that "might lead to breaking code or invalid results". A classifier
whose output has collapsed to a handful of values, mostly zero, is what a broken unpickle would
look like.

It does **not** establish that cause. Two alternatives are not excluded: C08 may legitimately be a
coarse classifier with few output levels, and LFW is low-resolution web photography that a strict
sharpness measure might genuinely score near zero. Distinguishing them needs the model re-saved
under the loading version and the comparison re-run — that is the clearing condition already
recorded for B-P04-11.

Until then, openfiqa's C08 should not be used as a sharpness measurement.

## Method

One image per subject (`*_0001.jpg`), first 60 subjects alphabetically — a deterministic,
subject-disjoint sample. Both engines saw identical files. openfiqa ran DEGRADED on CPU. Raw
per-sample scores are kept out of this repository; only these aggregates are published.
