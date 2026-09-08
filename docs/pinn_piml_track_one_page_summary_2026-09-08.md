# One-Page Summary: Separate PINN/PIML Track

## Motivation

The main solar-flare project focuses on multimodal temporal forecasting using AIA imagery, SHARP magnetic features, GOES flare history, and cross-cycle evaluation. A separate PINN/PIML track provides additional evidence of physics-informed modelling capability.

## Aim

Develop a defensible physics-informed machine learning prototype for space-weather forecasting.

## Approach

1. Start with a simple PINN demonstration using a standard PDE.
2. Translate the principle into flare forecasting through auxiliary physical-proxy losses.
3. Use SHARP magnetic descriptors linked to flux, free-energy proxies, helicity/current structure, and temporal consistency.
4. Evaluate under leakage-safe chronological rules.

## Expected outputs

- PINN foundation notebook.
- SHARP-based PIML prototype notebook.
- Loss-decomposition figure.
- Result table.
- Interview-safe summary.

## Claim

This track demonstrates physics-informed representation learning for solar/space-weather forecasting. It is not a full MHD PINN.
