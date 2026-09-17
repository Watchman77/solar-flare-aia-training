# 18A — SHARP Temporal Development Baseline

**Date:** 17 September 2026  
**Status:** Development diagnostic completed; not a final independent-test result.

## Purpose
First substantive SHARP-only temporal modelling run in the Cycle-24 to Cycle-25 extension. Earlier image-only, magnetic-only and intermediate-fusion experiments remain the historical baseline phase.

## Forecast task
Predict same-active-region M/X flare occurrence in `(t, t+48 h]`.

## Inputs
Three historical SHARP records at t-288, t-192 and t-96 minutes, with 15 magnetic features each, flattened to 45 ordered features.

## Conservative quality rule
All three records require QUALITY=0, 15/15 finite features, exactly one source match, no explicit NOAA conflict and three unique exact records. No imputation was used.

Cycle-24 candidates: 64,725. Conservative eligible targets: 55,871. Eligible positives: 1,800.

## Development folds
2013: train 15,203 / validation 7,586. 2014: train 22,963 / validation 7,102. 2015: train 30,187 / validation 6,649. Region overlap between train and validation was zero in every fold.

## Models
Logistic Regression with training-fold-only scaling and balanced class weights; Random Forest with 500 trees and balanced-subsample weighting.

## Logistic Regression results
2013: ROC-AUC 0.9297, PR-AUC 0.4540, TSS@0.5 0.6930, validation-selected TSS 0.7155.
2014: ROC-AUC 0.9231, PR-AUC 0.4703, TSS@0.5 0.7100, validation-selected TSS 0.7376.
2015: ROC-AUC 0.9549, PR-AUC 0.6189, TSS@0.5 0.8163, validation-selected TSS 0.8176.

## Random Forest results
2013: ROC-AUC 0.9351, PR-AUC 0.4854, TSS@0.5 0.1937, validation-selected TSS 0.7574.
2014: ROC-AUC 0.8385, PR-AUC 0.3356, TSS@0.5 0.1357, validation-selected TSS 0.5274.
2015: ROC-AUC 0.9334, PR-AUC 0.4271, TSS@0.5 0.1051, validation-selected TSS 0.7662.

## Important limitations
Cycle-25 was not used. Calibration and threshold holdouts were not used. Label clearance and SHARP historical availability/contributing-time review remain pending. Validation-selected thresholds are development diagnostics, not independent-test estimates.

## Evidence preserved
Clean notebook, executed notebook, CSV/JSON results, protocol record, environment freeze, validation predictions and SHA-256 artifact manifest. Large model binaries remain outside ordinary Git but are hash-recorded.
