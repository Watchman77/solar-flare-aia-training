# Solar Flare AIA Deep Learning Pipeline

<!-- aia-continuation-documentation-20260916 -->
> **16 September 2026 continuation evidence; publication review 17 September.** The completed AIA-only, SHARP-only and AIA + SHARP experiments remain the **baseline phase**. The newer temporal and cross-cycle work is a separate extension. See [AIA start here](docs/AIA_START_HERE.md) and the [dated status](docs/AIA_RESEARCH_STATUS_2026-09-16.md) for the completed engineering and data-preparation evidence. No new scored cross-cycle result, final protocol freeze or full scientific clearance is claimed. Internal proposal documents are not included in this public checkpoint. Historical records below remain unchanged.
<!-- /aia-continuation-documentation-20260916 -->


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
