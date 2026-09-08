# 20C PIML Interview Summary and Figures

This notebook/document turns the separate PINN/PIML track into interview-ready evidence.

## Purpose

Create a compact, honest explanation of the PINN/PIML work for PhD/RA/job interviews.

## Outputs

1. One architecture diagram.
2. One loss-decomposition figure.
3. One small results table if 20B is run.
4. One limitations paragraph.
5. One interview answer in plain English.

## Interview answer draft

> I developed a separate physics-informed machine learning prototype alongside my multimodal solar-flare forecasting work. I first implemented a small PINN demonstration using a simple PDE to show that I understood physics-residual learning. I then adapted the idea to solar-flare forecasting by adding auxiliary physical-proxy losses based on SHARP magnetic-energy and helicity-related descriptors. I was careful not to claim a full MHD PINN, because that would require full plasma-state variables and boundary conditions that are not available in the forecasting dataset. The work demonstrates practical physics-informed modelling and domain-aware regularisation for space-weather prediction.

## Key caution

Do not overclaim. The strength of this track is honesty plus implementation.
