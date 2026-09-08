# Interview-Safe PINN/PIML Claims

This document defines what can be safely said about the separate PINN/PIML track.

## Strong but honest claim

> I implemented a separate physics-informed machine learning prototype for space-weather forecasting. I first used a standard PINN demonstration to show physics-residual learning, then adapted the idea to solar-flare forecasting through auxiliary objectives tied to magnetic-energy, helicity, and temporal-consistency proxies.

## More technical version

> The core multimodal flare model focuses on AIA, SHARP, and GOES fusion. Separately, I explored physics-informed representation learning by adding auxiliary physical-proxy losses to a neural forecasting model. The goal was to encourage the latent representation to preserve physically meaningful magnetic descriptors such as flux, free-energy proxies, helicity/current-related parameters, and temporal consistency.

## Boundary statement

> I do not claim this is a full MHD PINN. A full MHD PINN would require detailed plasma variables, governing-equation constraints, and boundary conditions that are outside the available forecasting dataset. My contribution is a practical physics-informed forecasting prototype.

## One-minute interview answer

> Alongside the main multimodal solar-flare forecasting work, I built a separate physics-informed learning track. I started with a simple PINN example to demonstrate how data loss and physics-residual loss can be combined. I then transferred the principle into the flare-forecasting context by using SHARP magnetic proxies as auxiliary physical objectives. This encouraged the neural representation to remain sensitive to physically meaningful quantities such as magnetic flux, free-energy proxies, helicity, and temporal consistency. I was careful not to overclaim it as a full MHD PINN, because the forecasting dataset does not provide the full plasma state or boundary conditions. So the contribution is a defensible physics-informed ML prototype, not a physical simulator.

## Avoid these claims

- I solved solar flare prediction with a full PINN.
- I implemented full MHD physics.
- The model proves flare causality.
- The physics loss guarantees physical correctness.

## Use these phrases instead

- physics-informed representation learning
- domain-aware regularisation
- auxiliary physical-proxy loss
- magnetic-energy and helicity-aware learning
- temporal-consistency regularisation
- leakage-safe forecasting prototype
