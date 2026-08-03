## Research log update — ResNet18 physics-safe multifold hyperparameter sensitivity and error analysis

**Timestamp:** 2026-08-03 12:36:30

### Experiment completed

Completed CPU post-analysis for `12_aia_resnet18_multifold_error_analysis_and_research_log_update.ipynb`, following the completed Notebook 12 hyperparameter sensitivity experiment.

The hyperparameter sensitivity study used a predefined, physics-safe search over:

- `lower_lr`
- `higher_dropout`
- `reduced_pos_weight`
- existing baseline comparison

Selection was based only on **mean validation TSS across chronological folds**. Test metrics were reported after selection and were not used to choose the configuration.

### Validation-selected configuration

The validation-selected configuration was **`higher_dropout`**, with:

- Mean validation TSS: 0.2403 ± 0.0219
- Mean validation ROC-AUC: 0.6480 ± 0.0355
- Mean validation PR-AUC: 0.0845 ± 0.0070

Official test performance for the validation-selected configuration:

- Mean test TSS: 0.1819 ± 0.1409
- Mean test ROC-AUC: 0.6311 ± 0.0313
- Mean test PR-AUC: 0.0802 ± 0.0151
- Mean recall: 0.5340 ± 0.2902
- Mean specificity: 0.6480 ± 0.1700
 The existing baseline had mean validation TSS=0.2315 and mean official test TSS=0.2339.

### Error-analysis finding

The hardest chronological fold was **`test_2014`**, with mean official test TSS=0.0038. This confirms that the weak fold is not fully corrected by small hyperparameter changes.

The highest mean official test TSS across configurations was observed for **`baseline_existing`** with mean official test TSS=0.2339. This is reported as analysis only, not as the selection criterion.

### Scientific interpretation

The controlled sensitivity study suggests that higher dropout can improve validation stability, but image-only AIA ResNet18 remains unstable across chronological folds. The weakness of the 2014 fold persists after tuning, supporting the interpretation that the limitation is not only architecture or hyperparameter choice. It is likely linked to chronological/solar-cycle phase shift and the limited information content of single-time AIA EUV cutouts.

### Next research step

Proceed to a multimodal, physics-aware stage:

1. Keep AIA imagery as a morphology/thermal-emission branch.
2. Add SHARP magnetic temporal features as a magnetic-evolution branch.
3. Include chronological/cycle-phase analysis as a regime diagnostic.
4. Preserve the official protocol: validation-selected threshold, chronological folds, no test-set tuning.

### Files generated

- `results/metrics/aia_resnet18_multifold_error_analysis_confusion_summary.csv`
- `results/metrics/aia_resnet18_multifold_error_analysis_fold_hardness.csv`
- `results/metrics/aia_resnet18_multifold_error_analysis_threshold_transfer.csv`
- `results/metrics/aia_resnet18_multifold_error_analysis_labelled_test_predictions.csv` if prediction files were available
- `results/metrics/aia_resnet18_multifold_error_analysis_top_false_positives_selected_config.csv` if prediction files were available
- `results/metrics/aia_resnet18_multifold_error_analysis_top_false_negatives_selected_config.csv` if prediction files were available
- `results/metrics/aia_resnet18_multifold_error_analysis_research_log_update.md`
- `results/figures/aia_resnet18_error_analysis_*.png`