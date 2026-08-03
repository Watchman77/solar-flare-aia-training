## Research log update — Cycle/Regime Diagnostics for AIA ResNet18

**Timestamp:** 2026-08-03 15:51:49

### Diagnostic purpose

Completed CPU-only cycle/regime diagnostics after the AIA ResNet18 physics-safe multifold and hyperparameter sensitivity experiments. This notebook did not train models; it analysed fold-level behaviour, threshold transfer, false-alarm/miss patterns, and regime labels for the chronological test years.

### Main finding

The hardest chronological regime remains **cycle24_maximum** / **test_2014**, with mean official test TSS=0.0038. This supports the conclusion that the weak fold is not fully explained by small hyperparameter choices.

### Validation-selected model

`higher_dropout` was selected by mean validation TSS (0.2403 ± 0.0219). Its mean official test TSS was 0.1819 ± 0.1409.

The existing baseline retained mean official test TSS=0.2339 with high fold-to-fold variation (std=0.2227).

### Scientific interpretation

The current AIA-only experiment is best interpreted as a **within-Solar-Cycle-24 chronological robustness test**, not a direct Cycle 24 versus Cycle 25 experiment. The performance variation across 2013, 2014, and 2015 indicates that image-only AIA snapshots can capture useful morphology/thermal-emission cues, but they are not sufficiently stable across solar-cycle phase/regime shifts.

The 2014 fold remains scientifically important because it represents the Cycle 24 maximum-regime diagnostic case in this experimental setup. The persistence of weak official test TSS around this fold strengthens the argument for multimodal forecasting rather than further image-only tuning.

### Next step

Proceed to the AIA+SHARP fusion stage:

1. AIA branch for EUV morphology and coronal emission structure.
2. SHARP temporal branch for magnetic free-energy, shear, current, flux, and active-region evolution.
3. Chronological fold evaluation with validation-selected thresholds.
4. Regime-aware reporting to show where multimodal fusion improves or fails.

### Files generated

- `results/metrics/aia_resnet18_cycle_phase_regime_diagnostics_config_fold_summary.csv`
- `results/metrics/aia_resnet18_cycle_phase_regime_diagnostics_fold_regime_hardness.csv`
- `results/metrics/aia_resnet18_cycle_phase_regime_diagnostics_selected_config_profile.csv`
- `results/metrics/aia_resnet18_cycle_phase_regime_diagnostics_threshold_transfer_by_regime.csv`
- `results/metrics/aia_resnet18_cycle_phase_regime_diagnostics_research_log_update.md`
- `results/figures/aia_resnet18_cycle_phase_regime_*.png`