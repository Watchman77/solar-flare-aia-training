# SHARP-only Temporal Baseline from Fusion Manifest

**Generated:** 2026-08-03 17:45:12

## Scope

This notebook trained SHARP-only baselines using the AIA+SHARP+GOES fusion alignment manifest from Notebook 14.

The experiment remains **Solar Cycle 24 only**. The chronological folds use 2010–2015 data and should be interpreted as within-cycle chronological/regime testing, not Cycle 24 to Cycle 25 generalisation.

## Modality usage

- AIA image pixels were not used.
- SHARP magnetic parameters were used as input features.
- GOES was used only through the official target label lineage, `label_48h_final`.
- No GOES/XRS input features were used.

## Label

Official target: `label_48h_final`.

Embedded `.npz` labels remain ignored.

## SHARP feature set

Available preferred SHARP features:

`['MEANGBZ', 'MEANGAM', 'MEANGBT', 'MEANGBH', 'MEANJZD', 'TOTUSJZ', 'MEANALP', 'MEANJZH', 'ABSNJZH', 'SAVNCPP', 'MEANSHR', 'SHRGT45', 'R_VALUE', 'USFLUX', 'TOTPOT']`

Missing preferred SHARP features:

`['TOTUSJH']`

Optional SHARP features available:

`['MEANPOT', 'AREA_ACR']`

## Feature views evaluated

`['snapshot_available_preferred', 'snapshot_plus_optional', 'temporal_6h_available_preferred', 'temporal_12h_available_preferred', 'temporal_24h_available_preferred']`

24h history is treated as a sensitivity feature view. 48h history was not used for first official SHARP-only baseline because Notebook 14 showed low coverage.

## Validation-selected result

The validation-selected SHARP-only configuration was `random_forest_balanced` with feature view `temporal_24h_available_preferred`. It achieved mean validation TSS=0.7337 ± 0.1142, mean official test TSS=0.6402 ± 0.1902, mean test ROC-AUC=0.9170, and mean test PR-AUC=0.3998.

## Evaluation protocol

For every fold and feature view:

1. Train on earlier years.
2. Validate on the year immediately before the test year.
3. Select the decision threshold using validation TSS.
4. Apply the selected threshold unchanged to the held-out test year.

Diagnostic test-best thresholds were computed only as an error-analysis reference and must not be used for official model selection.

## Next step

Use this SHARP-only branch result as the magnetic baseline before training AIA+SHARP fusion.

Recommended next notebook:

`16_aia_sharp_fusion_training_protocol.ipynb`

The first fusion experiment should compare:

1. AIA-only ResNet18 baseline.
2. SHARP-only temporal baseline.
3. Intermediate fusion: AIA image embedding + SHARP temporal/snapshot embedding.
4. Later optional GOES branch after past-only GOES/XRS feature extraction.