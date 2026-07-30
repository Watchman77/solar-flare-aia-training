# AIA ResNet18 Physics-Safe Fold 2015 Full-Natural Benchmark Summary

## Run

- Experiment: `aia_resnet18_physics_safe_fold2015_fullnatural_benchmark`
- Mode: `fullnatural_physics_safe`
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
| train   |  38329 |        1230 |       37099 |       0.0320906 | [2010, 2011, 2012, 2013] |
| val     |  11627 |         629 |       10998 |       0.0540982 | [2014]                   |
| test    |  11236 |         531 |       10705 |       0.0472588 | [2015]                   |

## Model

- Architecture: `ResNet18 six-channel AIA CNN`
- Trainable parameters: `11186433`
- Image size: `224`
- Batch size: `32`
- Epochs: `6`
- Learning rate: `0.0001`
- Weight decay: `0.0005`
- Dropout: `0.3`
- Pos weight: `30.1618`

## Best validation checkpoint

- Best epoch: `1`
- Validation-selected threshold: `0.2050`
- Validation ROC-AUC: `0.6715`
- Validation PR-AUC: `0.0771`
- Validation best TSS: `0.2997`
- Validation best HSS: `0.0612`

## Test result at validation-selected threshold

- Test ROC-AUC: `0.7477`
- Test PR-AUC: `0.0971`
- Test Brier score: `0.1990`
- Test threshold: `0.2050`
- Test Accuracy: `0.5986`
- Test Precision: `0.0941`
- Test Recall: `0.8682`
- Test Specificity: `0.5852`
- Test F1: `0.1697`
- Test TSS: `0.4534`
- Test HSS: `0.0923`
- Confusion matrix: TP=`461`, TN=`6265`, FP=`4440`, FN=`70`

## Interpretation note

This is the first full-natural, physics-safe image-only CNN benchmark for fold-2015. Capped-subset AlexNet experiments should be treated as engineering baselines; this ResNet18 experiment is intended as the stronger natural-distribution image-only benchmark.
