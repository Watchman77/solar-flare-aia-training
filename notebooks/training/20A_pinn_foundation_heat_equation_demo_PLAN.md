# 20A PINN Foundation: Heat/Diffusion Equation Demo

This is the first notebook in the separate PINN/PIML portfolio track.

## Purpose

Demonstrate core Physics-Informed Neural Network understanding using a simple, controlled PDE before applying physics-informed ideas to solar-flare forecasting.

## Problem

Use the one-dimensional heat/diffusion equation:

```text
u_t = alpha * u_xx
```

The model learns `u(x,t)` while being penalised when its prediction violates the PDE residual.

## Loss components

```text
L_total = L_data + lambda_pde * L_residual + lambda_bc * L_boundary + lambda_ic * L_initial
```

## What the notebook should show

1. Define synthetic data for a simple heat-equation solution.
2. Build an MLP that takes `(x,t)` and predicts `u`.
3. Use automatic differentiation to compute `u_t` and `u_xx`.
4. Compute the physics residual `u_t - alpha*u_xx`.
5. Train with data + physics + boundary/initial condition losses.
6. Plot true solution, PINN solution, and residual error.
7. Write an interview-safe explanation of what was implemented.

## Why this matters

This notebook proves basic PINN competence without overclaiming a full MHD solar flare PINN.

## Cloud policy

This notebook should run locally or on free/low-cost CPU. No cloud GPU required.
