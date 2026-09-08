# First Executable Notebook Specification

## Notebook

`notebooks/training/20A_pinn_foundation_heat_equation_demo.ipynb`

## Aim

Implement a small PINN for the one-dimensional heat equation.

## Required cells

1. Title and purpose.
2. Imports and reproducibility seed.
3. Define analytical solution.
4. Generate collocation, boundary, initial, and data points.
5. Build PyTorch MLP.
6. Compute PDE residual with autograd.
7. Train model.
8. Plot predicted solution and residual.
9. Save figures and metrics.
10. Write interview-safe explanation.

## Output locations

- `results/figures/pinn_heat_equation_*`
- `results/metrics/pinn_heat_equation_*`

## Compute

CPU only.
