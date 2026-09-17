# 18C2 — Frozen SHARP Independent Cycle-25 Evaluation

Date: 17 September 2026

## Purpose

Evaluate the already-frozen Cycle-24 SHARP reference pipelines on the independent 2021–2025 Cycle-25 test set.

No Cycle-25 sample was used for:
- model fitting;
- preprocessing refitting;
- calibration fitting;
- threshold selection;
- feature selection;
- post-test sample-rule modification.

## Independent test set

- Samples: 45,433
- Positive M/X targets: 2,159
- Region components: 987
- Years: 2021–2025
- Input shape: 3 temporal SHARP records × 15 magnetic features
- Historical offsets: t−288, t−192 and t−96 minutes
- Conservative SHARP quality rule retained from Cycle-24 development.

## Frozen Cycle-25 results

### Logistic Regression
- ROC-AUC: 0.8722
- PR-AUC: 0.2836
- TSS: 0.6048
- HSS: 0.1704
- Precision: 0.1380
- Recall: 0.8786
- F1: 0.2385
- Frozen threshold: 0.0231323

### Random Forest
- ROC-AUC: 0.8741
- PR-AUC: 0.2173
- TSS: 0.5062
- HSS: 0.2744
- Precision: 0.2210
- Recall: 0.6142
- F1: 0.3251
- Frozen threshold: 0.0827212

## Interpretation

Both frozen SHARP models retained useful ranking skill under the Cycle-24 to Cycle-25 distribution shift.

The logistic-regression reference retained substantially higher recall and TSS, while the random forest produced fewer false positives and consequently higher HSS, precision and F1.

Year-specific performance varies considerably across Cycle 25, supporting explicit regime/cycle-aware reporting rather than relying only on one aggregate score.

## Scientific status

This is the independent cross-cycle SHARP evaluation.

No post-test tuning is permitted from these results.

Earlier documented label-clearance and historical-source-availability limitations remain in force, therefore the protocol retains `scientific_clearance=false`.
