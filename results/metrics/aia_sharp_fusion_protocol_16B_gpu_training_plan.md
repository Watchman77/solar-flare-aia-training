# 16B GPU Training Plan — AIA + SHARP Intermediate Fusion

**Generated:** 2026-08-03 18:54:04

## Objective

Train the first AIA + SHARP intermediate-fusion model using Solar Cycle 24 chronological folds.

This is not a Cycle 24 → Cycle 25 experiment.  
It is a within-cycle chronological/regime robustness experiment across 2010–2015.

## Inputs required on GPU VM

Repository:

`/home/abmoses2000/solar_flare_aia`

Required committed files:

- `training/fusion_manifests/aia_sharp_goes_fusion_alignment_manifest_2010_2016.csv`
- `training/fusion_manifests/aia_sharp_goes_fusion_fold_assignments_2013_2015.csv`
- `results/metrics/aia_sharp_fusion_protocol_candidate_selection.json`
- `results/metrics/aia_sharp_fusion_protocol_fold_readiness.csv`

Required AIA image cache:

- AIA `.npz` files referenced by `gcp_path`
- local cache path should follow the previous image-baseline cache convention

## Primary fusion architecture

### AIA branch

- ResNet18 adapted to 6 AIA channels.
- Input image size: 224×224 or the previous physics-safe image size.
- Preprocessing: train-only robust channel statistics.
- No random flips/rotations/crops.

### SHARP branch

- 24h temporal aggregate vector using available preferred SHARP features.
- Exclude `sharp_24h_history_count` in the primary fusion run.
- Use train-only imputation and scaling per fold.
- Include a sensitivity run with history_count only if clearly labelled.

### Fusion head

- Concatenate AIA embedding + SHARP embedding.
- Dense layers with dropout.
- Binary output logit.
- Loss: BCEWithLogitsLoss with train-fold class imbalance handling.
- Optimiser: AdamW.
- Threshold: selected by validation TSS only.

## Fold protocol

- `test_2013`: train 2010–2011, val 2012, test 2013
- `test_2014`: train 2010–2012, val 2013, test 2014
- `test_2015`: train 2010–2013, val 2014, test 2015

## Required comparisons

Report side-by-side:

1. AIA-only ResNet18 baseline.
2. SHARP-only temporal baseline.
3. AIA+SHARP fusion.
4. Conservative SHARP-only no-history-count result.
5. Optional fusion sensitivity without/with SHARP history_count if run.

## Safety checks

Before training:

- confirm every sample uses `label_48h_final`;
- confirm no embedded `.npz y` is used;
- confirm SHARP features are computed using only times <= `T_REC_dt`;
- confirm train-only normalisation;
- confirm validation-only threshold selection;
- confirm GOES is not used as input.

## Recommended first GPU run

Start with one fold first:

`test_2015`

Reason:

- it has the strongest existing AIA full-natural result;
- it has mature training data volume;
- it provides a fast sanity check before running all folds.

Then run:

- `test_2013`
- `test_2014`

The 2014 fold remains the critical hard regime.