# AIA AlexNet-v2 Physics-Safe Fold 2015 Largecap Benchmark Summary

## Run

- Experiment: `aia_alexnet_v2_physics_safe_fold2015_largecap_benchmark`
- Mode: `largecap_v2_physics_safe`
- Fold: `test_2015`
- Label: `label_48h_final`
- Threshold rule: validation-selected max TSS, applied unchanged to test

## Physics-safe protocol

- Embedded NPZ label used: `False`
- Spatial augmentation used: `False`
- Random flip/rotation/crop used: `False`
- Normalisation: `train_derived_channel_robust_q01_q99_clip_median_iqr_scale`
- Normalisation source: training split only
- Weighted random sampler: `False`
- Class imbalance handling: `BCEWithLogitsLoss(pos_weight=...)`

## Data

| split   |   rows |   positives |   negatives |   positive_rate | years                    |
|:--------|-------:|------------:|------------:|----------------:|:-------------------------|
| train   |  11230 |        1230 |       10000 |       0.109528  | [2010, 2011, 2012, 2013] |
| val     |   5629 |         629 |        5000 |       0.111743  | [2014]                   |
| test    |   5531 |         531 |        5000 |       0.0960043 | [2015]                   |

## Model

- Architecture: `AlexNet-v2 six-channel CNN with BatchNorm`
- Trainable parameters: `12196097`
- Image size: `224`
- Batch size: `32`
- Epochs: `6`
- Learning rate: `0.0001`
- Weight decay: `0.0005`
- Dropout: `0.5`
- Pos weight: `8.1301`

## Best validation checkpoint

- Best epoch: `1`
- Validation-selected threshold: `0.0450`
- Validation ROC-AUC: `0.5859`
- Validation PR-AUC: `0.1263`
- Validation best TSS: `0.1957`
- Validation best HSS: `0.0580`

## Test result at validation-selected threshold

- Test ROC-AUC: `0.6811`
- Test PR-AUC: `0.1683`
- Test Brier score: `0.1320`
- Test threshold: `0.0450`
- Test Accuracy: `0.3784`
- Test Precision: `0.1251`
- Test Recall: `0.9134`
- Test Specificity: `0.3216`
- Test F1: `0.2201`
- Test TSS: `0.2350`
- Test HSS: `0.0616`
- Confusion matrix: TP=`485`, TN=`1608`, FP=`3392`, FN=`46`

## Interpretation note

This notebook is intended as the official physics-safe AlexNet-v2 comparison point. It deliberately avoids non-physical image augmentations and uses train-derived channel statistics only, preserving chronological forecasting discipline.
