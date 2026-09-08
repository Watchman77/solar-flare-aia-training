# Second Executable Notebook Specification

## Notebook

`notebooks/training/20B_physics_informed_sharp_proxy_learning.ipynb`

## Aim

Adapt physics-informed learning ideas to the solar flare forecasting dataset using SHARP magnetic physical proxies.

## Main design

Train a neural model for 48-hour M/X flare prediction while adding an auxiliary physical-proxy loss.

## Candidate proxy variables

- `R_VALUE`
- `USFLUX`
- `TOTPOT`
- `TOTUSJH` when available
- `ABSNJZH`
- `MEANJZH`
- `MEANSHR`
- `SHRGT45`

## Required cells

1. Title and purpose.
2. Load available leakage-safe SHARP metadata/results.
3. Define chronological split.
4. Build feature matrix and proxy targets.
5. Fit train-only imputer/scaler.
6. Build neural classifier with proxy head.
7. Train with classification + proxy loss.
8. Select threshold on validation only.
9. Evaluate on held-out test.
10. Compare against non-PIML baseline.
11. Save metrics, predictions, and figure.
12. Write boundary statement.

## Compute

Start with CPU/small model. Use paid GPU only if later justified.
