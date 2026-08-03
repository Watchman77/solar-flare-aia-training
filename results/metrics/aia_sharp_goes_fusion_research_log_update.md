# AIA + SHARP + GOES Fusion Alignment Protocol

**Generated:** 2026-08-03 16:50:16

## Purpose

This protocol prepares the next multimodal flare-forecasting stage. It aligns AIA image samples with SHARP magnetic metadata and audits the current status of GOES information.

## Source files

- AIA baseline modelling manifest: `training/final_metadata/baseline_2010_2016_AR_SPECIFIC_manifest.csv`
- SHARP curated metadata table: `training/final_metadata/curated_sharp_suryabench_true96min_48h_AR_SPECIFIC_2010_2026.csv`
- AIA master manifest: `training/manifests/aia_master_manifest_2010_2026.csv`
- AIA master labelled manifest: `training/manifests/aia_master_manifest_2010_2026_LABELLED.csv`

## Official label

The official target label remains `label_48h_final`.

This label represents the active-region-specific future M/X flare label within the 48-hour forecast window. Embedded `.npz` labels are not used as scientific truth.

## AIA-SHARP alignment

Primary alignment key: `sample_id`.

Secondary checks:

- `HARPNUM`
- `NOAA_AR_clean`
- `T_REC_dt`
- label consistency between AIA and SHARP tables

AIA-SHARP sample match rate: **100.00%**.

AIA-vs-SHARP label mismatch count: **0**.

## SHARP feature audit

Preferred SHARP features available:

`['MEANGBZ', 'MEANGAM', 'MEANGBT', 'MEANGBH', 'MEANJZD', 'TOTUSJZ', 'MEANALP', 'MEANJZH', 'ABSNJZH', 'SAVNCPP', 'MEANSHR', 'SHRGT45', 'R_VALUE', 'USFLUX', 'TOTPOT']`

Preferred SHARP features missing:

`['TOTUSJH']`

Missing features must not be silently imputed into the feature set.

## SHARP temporal sequence design

Candidate lookback windows audited:

`[6, 12, 24, 48]` hours

The long-lookback audit row is:

- lookback_hours: 48.0
- expected_steps: 31.0
- coverage_rate: 29.15%

Recommended first fusion temporal branch:

- start with **24h SHARP history** if coverage is strong;
- use 48h only if coverage remains acceptable and computation is manageable;
- preserve train-only normalisation statistics.

## GOES status

GOES is currently present as the source lineage behind the flare labels, through `label_48h_final` and the AR-specific label columns.

GOES input-feature status: **not confirmed as a clean input-feature table in the current repository scan**.

Therefore, the next stage should treat GOES in two layers:

1. **Target supervision:** already active through `label_48h_final`.
2. **Future optional input branch:** requires a separate past-only GOES/XRS feature extraction notebook.

Safe GOES input features must use only information before the issue time `T_REC_dt`.

Unsafe GOES leakage:

- any flare or XRS information from the 48h forecast window;
- any peak class/event information after the issue timestamp.

## Fold protocol

Fusion folds generated:

- `fusion_test_2013`
- `fusion_test_2014`
- `fusion_test_2015`

## Outputs

- `training/fusion_manifests/aia_sharp_goes_fusion_alignment_manifest_2010_2016.csv`
- `training/fusion_manifests/aia_sharp_goes_fusion_fold_assignments_2013_2015.csv`
- `results/metrics/aia_sharp_goes_fusion_*.csv`
- `results/metrics/aia_sharp_goes_fusion_protocol.md`
- `results/figures/aia_sharp_goes_fusion_*.png`

## Next notebook

Recommended next notebook:

`15_sharp_temporal_baseline_from_fusion_manifest.ipynb`

Purpose:

Train a SHARP-only temporal baseline using the fusion manifest before introducing full AIA+SHARP(+GOES) neural fusion.