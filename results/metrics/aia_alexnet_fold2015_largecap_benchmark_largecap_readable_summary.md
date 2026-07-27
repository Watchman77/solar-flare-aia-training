# AIA AlexNet Fold 2015 Benchmark Summary

## Run

- Experiment: `aia_alexnet_fold2015_largecap_benchmark`
- Mode: `largecap`
- Fold: `test_2015`
- Train years: `[2010, 2011, 2012, 2013]`
- Validation year: `[2014]`
- Test year: `[2015]`
- Label: `label_48h_final`
- Threshold rule: validation-selected max TSS, applied unchanged to test

## Data

| split   |   rows |   positives |   negatives |   positive_rate | years                    |
|:--------|-------:|------------:|------------:|----------------:|:-------------------------|
| train   |  11230 |        1230 |       10000 |       0.109528  | [2010, 2011, 2012, 2013] |
| val     |   5629 |         629 |        5000 |       0.111743  | [2014]                   |
| test    |   5531 |         531 |        5000 |       0.0960043 | [2015]                   |

## Best validation checkpoint

- Best epoch: `1`
- Validation-selected threshold: `0.6975`
- Validation ROC-AUC: `0.6122`
- Validation PR-AUC: `0.1346`
- Validation best TSS: `0.2647`
- Validation best HSS: `0.0995`

## Test result at validation-selected threshold

- Test ROC-AUC: `0.6791`
- Test PR-AUC: `0.2117`
- Test Brier score: `0.3859`
- Test threshold: `0.6975`
- Test Accuracy: `0.5384`
- Test Precision: `0.1280`
- Test Recall: `0.6554`
- Test Specificity: `0.5260`
- Test F1: `0.2142`
- Test TSS: `0.1814`
- Test HSS: `0.0638`
- Confusion matrix: TP=`348`, TN=`2630`, FP=`2370`, FN=`183`

## Interpretation note

This notebook is configured with `RUN_MODE = "largecap"`, so it keeps the formal fold-2015 chronology but uses all available positives and capped negatives for a cost-controlled benchmark. The validation-selected max-TSS threshold is applied unchanged to the test split for the main reported result.
