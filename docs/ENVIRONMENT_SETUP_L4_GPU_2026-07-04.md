# Solar Flare AIA GPU Training Environment Setup

Date: 2026-07-04
Project: Solar Flare AIA Deep Learning / Solar Flare Forecasting
Google Cloud Project ID: sonorous-shore-450510-i4
VM: solar-flare-aia-training-l4-c
Zone: europe-west4-c

## Purpose

This document records the reproducible GPU training environment for the Solar Flare AIA image-based flare forecasting pipeline.

The aim is to avoid undocumented cloud experimentation and ensure that all setup steps, training runs, metrics, models, logs and configurations can be reproduced later.

## Working GPU VM

VM name: solar-flare-aia-training-l4-c
Zone: europe-west4-c
Machine type: g2-standard-4
GPU: NVIDIA L4
GPU memory: 23034 MiB
Operating system: Ubuntu 24.04.4 LTS
Kernel: 6.17.0-1020-gcp

## NVIDIA Driver Validation

NVIDIA-SMI: 610.43.02
KMD Version: 610.43.02
CUDA UMD Version: 13.3
GPU: NVIDIA L4
Memory: 23034 MiB

Validation command:

```bash
nvidia-smi
```

## PyTorch CUDA Validation

Torch: 2.11.0+cu128
CUDA available: True
GPU: NVIDIA L4
VRAM GB: 22.06
CUDA matmul test: passed

## Python Environment

Training environment:

```text
~/solar_flare_aia/train_venv
```

Activate with:

```bash
cd ~/solar_flare_aia
source ~/solar_flare_aia/train_venv/bin/activate
```

## Important Metadata Files

```text
~/solar_flare_aia/training/final_metadata/baseline_2010_2016_AR_SPECIFIC_manifest.csv
~/solar_flare_aia/training/final_metadata/curated_sharp_suryabench_true96min_48h_AR_SPECIFIC_2010_2026.csv
```

## Important Label Rule

Use `label_48h_final` from the manifest for training.
Do not rely on old embedded `y` labels inside NPZ files.

## Storage Strategy

GitHub stores code, notebooks, docs and configs.
Google Cloud Storage stores NPZ data, FITS files, checkpoints and large logs.
The GPU VM is for active training and temporary cache.
The MacBook should keep a local clone of the GitHub repository.

## Cost Control

Stop the VM when not training:

```bash
gcloud compute instances stop \
  solar-flare-aia-training-l4-c \
  --project=sonorous-shore-450510-i4 \
  --zone=europe-west4-c
```

## Research Rule

Every serious training run must save:

- config file
- code/script version
- timestamp
- training log
- metrics CSV/JSON
- model checkpoint
- train/validation/test split definition
- final interpretation note

No undocumented training result should be treated as final.
