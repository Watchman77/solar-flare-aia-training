# Realistic Class-Imbalance AIA CNN Year-Holdout Sanity Experiment

Purpose: Realistic class-imbalance AIA CNN year-holdout sanity experiment; not final publication result

Experiment: `realistic_imbalance_aia_cnn_year_holdout_10to1`

## Protocol

- Train years: [2010, 2011, 2012, 2013]
- Validation years: [2014]
- Train rows: 1650
- Validation rows: 825
- Train label counts: {'0': 1500, '1': 150}
- Validation label counts: {'0': 750, '1': 75}
- Original input: 512 × 512 × 6
- Model input: 224 × 224 × 6
- Label used: `label_48h_final`
- Embedded NPZ `y`: ignored
- Loss: weighted BCEWithLogitsLoss
- pos_weight: 10.0000

## Final validation metrics at fixed threshold 0.5

- ROC-AUC: 0.7264177777777778
- PR-AUC: 0.19798268783934198
- Accuracy: 0.7236
- Precision: 0.1745
- Recall: 0.5467
- Specificity: 0.7413
- F1: 0.2645
- TSS: 0.2880
- HSS: 0.1469
- TP: 41
- TN: 556
- FP: 194
- FN: 34

## Final validation metrics at best validation TSS threshold

- Threshold: 0.437500
- Accuracy: 0.6873
- Precision: 0.1744
- Recall: 0.6533
- Specificity: 0.6907
- F1: 0.2753
- TSS: 0.3440
- HSS: 0.1538
- TP: 49
- TN: 518
- FP: 232
- FN: 26

## Important note

This is a sanity experiment under controlled imbalanced sampling, not a final publication result.
