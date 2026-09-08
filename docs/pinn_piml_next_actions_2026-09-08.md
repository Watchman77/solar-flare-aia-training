# PINN/PIML Next Actions

## Immediate next action

Create the actual notebook:

```text
notebooks/training/20A_pinn_foundation_heat_equation_demo.ipynb
```

## Implementation outline

1. Import PyTorch, NumPy, Matplotlib.
2. Define the analytical heat equation solution.
3. Sample training points.
4. Build MLP.
5. Use autograd to compute physics residual.
6. Train with data + PDE + boundary/initial losses.
7. Plot prediction/residual.
8. Save outputs to `results/metrics` and `results/figures`.

## After 20A

Create:

```text
notebooks/training/20B_physics_informed_sharp_proxy_learning.ipynb
```

This should use existing SHARP data and avoid cloud GPU unless absolutely necessary.
