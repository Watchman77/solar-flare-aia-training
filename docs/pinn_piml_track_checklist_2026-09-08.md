# PINN/PIML Separate Track Checklist

## Track identity

This is a separate portfolio/research-evidence track. It supports the main solar-flare project but should not be presented as the main multimodal model unless later integrated through proper experiments.

## Deliverables

- [ ] `20A_pinn_foundation_heat_equation_demo.ipynb`
- [ ] `20B_physics_informed_sharp_proxy_learning.ipynb`
- [ ] `20C_piml_interview_summary_and_figures.ipynb`
- [ ] One clean architecture diagram
- [ ] One loss-decomposition figure
- [ ] One small result table
- [ ] One limitations statement
- [ ] One interview-safe summary paragraph

## Step 20A: PINN foundation

- [ ] Define the heat/diffusion equation.
- [ ] Generate synthetic training/collocation points.
- [ ] Build MLP for `u(x,t)`.
- [ ] Use autograd for `u_t` and `u_xx`.
- [ ] Compute PDE residual.
- [ ] Train with data + residual + boundary/initial losses.
- [ ] Plot prediction and residual.

## Step 20B: Solar PIML prototype

- [ ] Load leakage-safe SHARP data.
- [ ] Select physical-proxy variables.
- [ ] Build tabular/temporal neural model.
- [ ] Add auxiliary proxy reconstruction/prediction loss.
- [ ] Add optional temporal-consistency loss.
- [ ] Train using chronological split.
- [ ] Select threshold on validation only.
- [ ] Evaluate on test.

## Step 20C: Portfolio explanation

- [ ] Generate architecture diagram.
- [ ] Generate loss figure.
- [ ] Summarise results.
- [ ] Write interview-safe claim.
- [ ] State boundaries and limitations.

## Cost policy

- Run 20A locally/CPU.
- Run 20B locally first using small data.
- Do not use paid cloud GPU for this track unless the main final sprint already has funded/controlled cloud access.

## Completion wording

> Completed a separate physics-informed ML prototype for solar/space-weather forecasting, including a PINN foundation demo and a SHARP-based physics-informed representation-learning experiment.
