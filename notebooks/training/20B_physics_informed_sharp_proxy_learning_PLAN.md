# 20B Physics-Informed SHARP Proxy Learning

This is the second notebook in the separate PINN/PIML portfolio track.

## Purpose

Build a solar-flare-relevant physics-informed machine learning prototype using SHARP-derived magnetic proxies. This is not a full MHD PINN; it is a physics-informed representation-learning model.

## Dataset

Use existing leakage-safe SHARP/fusion metadata where available.

Inputs must use only information at or before sample time `t`.

Label:

```text
M/X flare in (t, t + 48h]
```

## Candidate physical proxies

- `R_VALUE`
- `USFLUX`
- `TOTPOT`
- `TOTUSJH` where available
- `ABSNJZH`
- `MEANJZH`
- `MEANSHR`
- `SHRGT45`

## Model idea

A neural network learns a latent representation from SHARP temporal features.

The representation is trained for two purposes:

1. Main classification task: predict 48-hour M/X flare occurrence.
2. Auxiliary physical task: preserve/reconstruct/predict physically meaningful magnetic proxies.

## Loss structure

```text
L_total = L_classification
        + lambda_proxy * L_physical_proxy
        + lambda_temporal * L_temporal_consistency
```

## Evaluation

- TSS
- HSS
- ROC-AUC
- PR-AUC
- Precision
- Recall
- F1
- Brier score
- Confusion matrix

## Leakage rules

- No future SHARP values.
- No GOES events inside the forecast window as input.
- Train-only imputation/scaling.
- Validation-only threshold selection.
- No test threshold tuning.

## Expected claim

Correct:

> A physics-informed neural forecasting prototype using auxiliary losses tied to magnetic-energy, helicity, and temporal-consistency proxies.

Avoid:

> A full MHD PINN for solar flare prediction.

## Cloud policy

Start with CPU or small local run. Do not use paid GPU unless the small prototype proves it needs scaling.
