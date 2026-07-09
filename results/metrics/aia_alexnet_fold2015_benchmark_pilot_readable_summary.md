# AIA AlexNet Fold-2015 Pilot Benchmark

## Protocol

- Experiment: `aia_alexnet_fold2015_benchmark`
- Run mode: `pilot`
- Fold: `test_2015`
- Label: `label_48h_final`
- Input channels: `aia94, aia131, aia171, aia193, aia211, aia335`
- Threshold rule: validation-selected maximum TSS, applied unchanged to test.

## Main pilot result

| Item                          | Value                   |
|:------------------------------|:------------------------|
| Run mode                      | pilot                   |
| Fold                          | test_2015               |
| Train years                   | 2010, 2011, 2012, 2013  |
| Validation years              | 2014                    |
| Test years                    | 2015                    |
| Validation-selected threshold | 0.91                    |
| Best epoch                    | 1                       |
| Test ROC-AUC                  | 0.7252711111111111      |
| Test PR-AUC                   | 0.1912054437353224      |
| Test TSS                      | 0.29899999999999993     |
| Test HSS                      | 0.11938510680774606     |
| Test Precision                | 0.15349194167306215     |
| Test Recall                   | 0.6666666666666666      |
| Test Specificity              | 0.6323333333333333      |
| Test F1                       | 0.24953212726138488     |
| Test Accuracy                 | 0.6354545454545455      |
| Test Brier score              | 0.5779051525381913      |
| TP / TN / FP / FN             | 200 / 1897 / 1103 / 100 |

## Important note

The official pilot test result uses the validation-selected threshold `0.91`.

The diagnostic test-best threshold is not the main reported result because it selects the threshold on the test set.
