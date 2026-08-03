# SHARP Temporal Leakage and Robustness Audit

**Generated:** 2026-08-03 18:27:38

## Scope

This audit examined the strong SHARP-only temporal baseline from Notebook 15 before AIA+SHARP fusion.

The experiment remains **Solar Cycle 24 only** and should be described as within-cycle chronological/regime testing across 2010–2015.

## Selected configuration audited

- Model: `random_forest_balanced`
- Feature view: `temporal_24h_available_preferred`
- Modality: SHARP only
- GOES usage: label lineage only; no GOES/XRS input features
- AIA usage: sample alignment only; no image pixels

## Leakage audit

The selected feature set contains 91 features. The audit found no explicit target-label, future-window, AIA path, GOES/XRS, or split columns among the selected SHARP model inputs.

The main review-level feature is `sharp_24h_history_count`. It is not label leakage, but it may encode observational completeness/track length, so it was ablated.

## Temporal past-only audit

Past-only window violations: **0**

Lower-bound window violations: **0**

24h sequence coverage: **52.38%**

The 24h aggregate construction uses SHARP rows with timestamps less than or equal to the forecast issue time.

## Fold robustness

Weakest selected-config fold:

- Fold: `test_2014`
- Official test TSS: 0.4224
- Diagnostic test-best TSS: 0.6045
- Selected threshold: 0.0875

The 2014 fold remains weaker than 2013 and 2015, consistent with the earlier Cycle 24 maximum-regime difficulty observed in AIA-only analysis.

## Feature-importance audit

Top feature importances were saved to:

`results/metrics/sharp_temporal_leakage_audit_rf_feature_importance_top20.csv`

`sharp_24h_history_count` ranked 91 by mean RF importance, with mean importance=0.0000.

## History-count ablation

Mean official test TSS with history count: **0.6402 ± 0.1902**

Mean official test TSS without history count: **0.6330 ± 0.2052**

Difference, with minus without: **0.0072**

If performance remains strong without `history_count`, the SHARP-only result is less likely to depend on sampling-density shortcut information. If performance drops materially, the conservative no-history-count value should be emphasised.

## Paper-safe interpretation

The SHARP-only 24h temporal Random Forest baseline is a strong magnetic-branch result, but it is coverage-limited because only about half of aligned samples satisfy the 24h history requirement. It should be reported alongside snapshot, 6h, and 12h views.

The result supports the multimodal methodology: SHARP magnetic evolution provides strong physical pre-flare information, while AIA image features can later contribute coronal morphology and thermal-emission context.

## Next step

Proceed to AIA+SHARP fusion only after reviewing this audit.

Recommended next notebook:

`16_aia_sharp_fusion_training_protocol.ipynb`