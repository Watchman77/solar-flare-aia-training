# Separate PINN/PIML Portfolio Track

**Date:** 2026-09-08  
**Purpose:** Create a separate, interview-safe physics-informed machine learning track that demonstrates PINN/PIML capability without overclaiming a full solar-MHD PINN.

## Why this track is separate

The main solar-flare sprint focuses on multimodal flare forecasting: AIA EUV image sequences, SHARP magnetic time series, past-only GOES activity descriptors, and cross-cycle evaluation.

The PINN/PIML track is deliberately separate because a full magnetohydrodynamic PINN for solar flares would require strong assumptions about plasma state variables, boundary conditions, and governing equations that are not directly available in the current forecasting dataset.

This track therefore focuses on implementable, defensible physics-informed learning.

## Interview-safe claim

After completing this track, the correct claim is:

> I implemented a separate physics-informed machine learning prototype for solar/space-weather forecasting, using auxiliary physical constraints and regularisation to encourage physically meaningful magnetic-energy, helicity, and temporal-consistency representations.

Avoid claiming:

> I solved solar flare prediction with a full MHD PINN.

## Track goals

1. Build a small standalone PINN/PIML notebook.
2. Demonstrate understanding of physics-informed loss design.
3. Apply the idea to solar-flare-relevant physical proxies.
4. Keep it lightweight enough to run without expensive cloud compute.
5. Produce one portfolio-ready notebook, one figure, and one short write-up.

## Proposed notebooks

- `20A_pinn_foundation_heat_equation_demo.ipynb`  
  A clean PINN demonstration using a simple PDE such as the 1D heat/diffusion equation. This proves core PINN knowledge: data loss, physics residual loss, boundary/initial constraints, and training stability.

- `20B_physics_informed_sharp_proxy_learning.ipynb`  
  A solar-flare-relevant PIML notebook using SHARP-derived physical proxies. The model predicts 48-hour M/X flare probability while also using auxiliary objectives linked to magnetic-energy and helicity proxies.

- `20C_piml_interview_summary_and_figures.ipynb`  
  Generates a compact explanation figure and interview-ready summary.

## Practical PIML design for solar flare forecasting

### Inputs

- SHARP magnetic features and temporal aggregates.
- Optional GOES past-only flare-history descriptors.
- Optional AIA embedding from prior models if available.

### Main task

Predict whether an active region produces an M/X flare within 48 hours.

### Auxiliary physics-informed tasks

Examples:

- Reconstruct or predict key physical proxies such as `R_VALUE`, `USFLUX`, `TOTPOT`, `TOTUSJH`, `ABSNJZH`.
- Encourage temporal smoothness in predicted risk unless magnetic/flare-history activity changes strongly.
- Penalise physically implausible instability in learned embeddings.
- Use monotonic or ranking regularisation cautiously for energy/helicity proxies, without claiming causality.

### Loss structure

```text
Total loss = classification loss
           + lambda_energy * magnetic_proxy_loss
           + lambda_temporal * temporal_consistency_loss
           + lambda_calibration * optional_calibration_loss
```

### Evaluation

- TSS
- HSS
- ROC-AUC
- PR-AUC
- Precision
- Recall
- F1
- Brier score
- Confusion matrix
- Calibration plot if feasible

## Boundaries

This track is not a full MHD solver and does not require solving the complete plasma physics of magnetic reconnection.

It is a physics-informed representation-learning prototype designed to show that domain knowledge can be injected into the training objective.

## Completion criteria

- A clean PINN foundation notebook.
- A solar-flare-relevant PIML prototype notebook.
- One concise result table.
- One explanatory figure showing data loss plus physics-informed loss.
- One short interview-ready paragraph.
- No cloud GPU required unless later justified.

## Interview wording

> Alongside the multimodal solar-flare forecasting work, I built a separate physics-informed machine learning prototype. I used a simple PINN demonstration to validate the principle of physics residual learning, then adapted the idea to solar-flare forecasting through auxiliary losses tied to magnetic-energy, helicity, and temporal-consistency proxies. I was careful not to claim a full MHD PINN, because the available forecasting data do not fully specify the plasma state or boundary conditions. The contribution is a practical physics-informed forecasting prototype rather than a complete physical simulator.
