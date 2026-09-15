# Solar Flare AIA Deep Learning Pipeline

<!-- aia17-checkpoint-20260915 -->
> **Current checkpoint: 15 September 2026.** 17A/17B metadata, source and conditional timing reviews have run in Cloud Shell. Full 17B readiness is NOT yet cleared. UQ requirements are installed; UQ, calibration and the separate PINN/PIML experiments are not claimed as completed. The GPU environment below is historical, not a claim that a VM currently exists. See [the current checkpoint](docs/RESEARCH_CHECKPOINT_2026-09-15.md).
<!-- /aia17-checkpoint-20260915 -->

This repository contains reproducible code, notebooks, configuration files and documentation for the Solar Flare AIA image-based flare forecasting pipeline.

## Project aim

Develop and evaluate deep-learning models for solar flare forecasting using SDO/AIA multi-wavelength image cutouts and SHARP-derived active-region metadata.

## Historical training environment (July 2026)

VM: solar-flare-aia-training-l4-c  
Zone: europe-west4-c  
GPU: NVIDIA L4  
Driver: 610.43.02  
Torch: 2.11.0+cu128  

See:

```text
docs/ENVIRONMENT_SETUP_L4_GPU_2026-07-04.md
```

## Storage policy

GitHub stores code, docs, notebooks and configs.

Google Cloud Storage stores large data, NPZ files, FITS files, checkpoints and large logs.

## Important rule

Training labels must use `label_48h_final` from the official manifest.
