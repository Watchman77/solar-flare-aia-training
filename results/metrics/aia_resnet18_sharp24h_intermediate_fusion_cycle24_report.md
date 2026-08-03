# AIA + SHARP Intermediate Fusion Training Results

**Generated:** 2026-08-03 22:25:54

## Experiment

`aia_resnet18_sharp24h_intermediate_fusion_cycle24`

## Scope

This experiment is **Solar Cycle 24 only** and should be interpreted as within-cycle chronological/regime robustness.

## Modalities

- AIA: six-channel EUV image tensors.
- SHARP: 24h leakage-safe temporal magnetic aggregate vector.
- GOES: label-lineage only through `label_48h_final`; no GOES/XRS input features.

## Primary safety choices

- Embedded NPZ labels ignored.
- SHARP `history_count` excluded from the primary fusion feature vector: `True`.
- AIA preprocessing statistics estimated from training split only.
- SHARP imputer/scaler fitted on training split only.
- Threshold selected by validation TSS only.

## Folds completed

`['fusion_test_2015']`

## Mean completed-fold performance

- Mean official test TSS: 0.3934
- Std official test TSS: NA
- Mean test ROC-AUC: 0.8668
- Mean test PR-AUC: 0.2818

## Notes

If only one fold was run, this is a sanity result and must not be reported as the final multimodal result. Run all three folds before paper-level comparison.

The 2014 fold remains the critical regime-stress fold.

## Outputs

- Summary: `results/metrics/aia_resnet18_sharp24h_intermediate_fusion_cycle24_run_summary.csv`
- Branch comparison: `results/metrics/aia_resnet18_sharp24h_intermediate_fusion_cycle24_branch_comparison_with_fusion.csv`
- Models: `results/models/aia_resnet18_sharp24h_intermediate_fusion_cycle24_*_best.pt`
- Predictions: `results/predictions/aia_resnet18_sharp24h_intermediate_fusion_cycle24_*_test_predictions.csv`