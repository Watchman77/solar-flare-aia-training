# 19A3 Temporal AIA Calibration and Threshold Checkpoint

Date: 2026-09-18

## Purpose

Freeze probability calibration and the operating threshold for the
Cycle-24 temporal AIA CNN-GRU before any independent Cycle-25 evaluation.

No CNN-GRU model weights were updated in this stage.

## Frozen base model

Final Cycle-24 CNN-GRU SHA256:

`11dc35e089101c8b79d2a6ba6f82d02cdb470d583552cad73e6071016c2a2d76`

Normalisation SHA256:

`c7552cebf1629f799936edf41365d0ab0e0eb16ed47207ea90490d501962503e`

## Calibration

Method: Platt scaling on frozen CNN-GRU raw logits.

Calibration role:

`cycle24_calibration_holdout`

Platt parameters:

- coefficient: 0.5846760189574352
- intercept: -3.6728404851652265

Calibration holdout prevalence:

0.021269790500559733

Raw metrics:

- ROC-AUC: 0.6841527839
- PR-AUC: 0.0381190016
- Brier: 0.2043660788
- log loss: 0.5727020749

After Platt calibration:

- ROC-AUC: 0.6841527839
- PR-AUC: 0.0381190016
- Brier: 0.0206251396
- log loss: 0.0987437378

As expected for monotonic calibration, ranking metrics were unchanged,
while probability calibration improved substantially.

## Operating threshold

Threshold-selection role:

`cycle24_threshold_holdout`

Selection rule:

maximum TSS

Frozen calibrated-probability threshold:

`0.030438695842933242`

Threshold-holdout metrics:

- ROC-AUC: 0.7823895145
- PR-AUC: 0.0903245909
- Brier: 0.0304252937
- log loss: 0.1308890589
- TSS: 0.4402321835
- HSS: 0.0746225000
- precision: 0.0702534460
- recall: 0.7821782178
- F1: 0.1289269686

Confusion matrix:

- TN: 4024
- FP: 2091
- FN: 44
- TP: 158

## Leakage firewall

During 19A3:

- Cycle-25 was not used.
- 2026 supplementary data were not used.
- CNN-GRU weights were not updated.
- Calibration used only the dedicated Cycle-24 calibration holdout.
- Threshold selection used only the dedicated Cycle-24 threshold holdout.
- The embedded NPZ `y` field was not used as the target.

The complete Cycle-24 AIA inference pipeline is now frozen.

Next stage:

19A4 independent 2021-2025 Cycle-25 evaluation.

No post-test recalibration, refitting or threshold reselection is permitted.
