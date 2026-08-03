# Research Log Update — AIA + SHARP Fusion Protocol

**Generated:** 2026-08-03 18:54:04

## Current stage

Completed local CPU-only protocol notebook 16A for the first AIA+SHARP fusion experiment.

## Scientific framing

The current dataset and planned fusion folds remain **Solar Cycle 24 only**. The correct interpretation is within-cycle chronological/regime robustness, not Cycle 24 to Cycle 25 generalisation.

## Existing branch evidence

AIA-only ResNet18 multifold mean official test TSS=0.2339 ± 0.2227.

SHARP-only selected temporal baseline mean official test TSS=0.6402 ± 0.1902.

Conservative SHARP no-history-count reference mean official test TSS=0.6330 ± 0.2052.

## Fusion decision

The first fusion model will use:

- AIA ResNet18 image embedding as the coronal morphology branch.
- SHARP 24h temporal aggregate feature vector as the magnetic evolution branch.
- GOES only as target-label lineage through `label_48h_final`; no GOES/XRS input features yet.

The primary fusion run should exclude `sharp_24h_history_count`; a sensitivity run may include it, but the conservative branch is preferred for paper-safe reporting.

## Rationale

AIA-only modelling showed useful but unstable image-branch skill across chronological regimes. SHARP-only temporal modelling showed substantially stronger magnetic-branch skill after leakage and robustness audit. Fusion is therefore scientifically justified as intermediate fusion between coronal EUV morphology and magnetic evolution.

## Next step

Create and run GPU notebook 16B:

`16B_aia_sharp_intermediate_fusion_training.ipynb`

Start with the `test_2015` fold as a sanity run, then run `test_2013` and `test_2014`.