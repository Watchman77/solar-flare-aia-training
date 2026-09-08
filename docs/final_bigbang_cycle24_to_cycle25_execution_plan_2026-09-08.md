# Final Big-Bang Execution Plan

**Project:** XFlareXAI final multimodal extension  
**Date:** 2026-09-08  
**Scope:** 48-hour M/X-class solar flare forecasting  
**Strategic goal:** Complete a final, disciplined solar-flare research package before moving to the next research direction.

## 1. Scientific aim

The final phase will extend the existing XFlareXAI work into a leakage-safe, solar-cycle-aware multimodal temporal forecasting framework.

The central research question is:

> Can a model trained on Solar Cycle 24 generalise to Solar Cycle 25 when it integrates AIA EUV image evolution, HMI/SHARP magnetic information, SHARP temporal parameters, and past-only GOES flare-history descriptors?

This phase should not be treated as open-ended exploration. It is a defined final sprint aimed at producing manuscript-ready evidence, a reproducible codebase, and a clear final contribution.

## 2. Methodological backbone

The final framework follows five methodological pillars:

1. **Data collection and preprocessing**
   - SDO/AIA EUV images.
   - SDO/HMI SHARP magnetic parameters.
   - HMI/SHARP CEA magnetic image products where feasible.
   - GOES XRS/event data used only in leakage-safe ways.
   - Synchronisation by active region and timestamp.

2. **Representation learning**
   - CNN/ResNet/ConvLSTM or spatio-temporal image models for AIA EUV data.
   - LSTM/GRU/Transformer/temporal-MLP models for SHARP parameter histories.
   - MLP branch for past-only GOES activity features.
   - Optional CNN branch for HMI/SHARP magnetic image maps.

3. **Multimodal fusion**
   - Intermediate fusion as the reproducible baseline.
   - Gated/attention fusion as the advanced candidate.
   - Hierarchical fusion if HMI/SHARP image maps are included.

4. **Training and optimisation**
   - AdamW optimiser.
   - Learning-rate scheduling.
   - Dropout/normalisation.
   - Class-imbalance-aware loss functions.
   - Validation-only checkpoint and threshold selection.

5. **Evaluation and validation**
   - TSS, HSS, ROC-AUC, PR-AUC, precision, recall, F1, Brier score, confusion matrix.
   - Chronological validation.
   - Independent Solar Cycle 25 testing.
   - Ablation across modalities.
   - Explainability and error analysis.

## 3. Current completed foundation

The following foundation already exists in the repository:

- AIA-only image baseline.
- SHARP-only temporal magnetic baseline.
- AIA+SHARP intermediate fusion baseline.
- Leakage-safe chronological Solar Cycle 24 folds.
- Validation-only thresholding.
- Full all-fold fusion run for 2013, 2014, and 2015.
- Prediction CSVs and prefetch scripts committed.
- Trained model checkpoints backed up externally.

These results become the benchmark floor for the final phase.

## 4. Final data split strategy

### 4.1 Within-cycle benchmark

Use existing Solar Cycle 24 chronological folds to preserve continuity with completed work:

- `fusion_test_2013`
- `fusion_test_2014`
- `fusion_test_2015`

Purpose: regime-stress evaluation within Solar Cycle 24.

### 4.2 Cross-cycle generalisation test

Primary final test:

- **Train:** Solar Cycle 24 training years, e.g. 2010-2017 or 2010-2018.
- **Validation:** late Cycle 24 / minimum-transition period, e.g. 2018-2019.
- **Test:** Solar Cycle 25, preferably 2021-2025.

Avoid using 2020 blindly in the main test because it is a transition/minimum year. It can be analysed separately as a sensitivity period.

## 5. Leakage rules

For each active-region sample at time `t`:

- Inputs must use only information at or before `t`.
- Label is whether an M/X-class flare occurs in `(t, t+48h]`.
- No GOES flare event inside the 48-hour forecast window may be used as an input.
- AIA images after `t` must not be used.
- SHARP rows after `t` must not be used.
- HMI/SHARP image products after `t` must not be used.
- Imputation/scaling statistics must be fitted on training data only.
- Thresholds must be selected on validation data only and then frozen for test evaluation.
- Any regime-aware threshold must be fitted without test labels.

## 6. Model ladder

The final sprint should use a controlled ladder instead of one uncontrolled model.

### M1: SHARP temporal baseline

Purpose: preserve the strongest known magnetic branch reference.

### M2: GOES past-only baseline

Purpose: measure how much recent flare-history persistence predicts future M/X events.

### M3: SHARP + GOES tabular fusion

Purpose: test whether magnetic state plus past flare activity improves cross-cycle robustness.

### M4: AIA temporal sequence model

Candidate architectures:

- TimeDistributed ResNet + temporal pooling.
- CNN-LSTM.
- ConvLSTM.
- Lightweight temporal transformer if memory permits.

Purpose: test whether EUV image evolution improves over AIA snapshot baselines.

### M5: AIA temporal + SHARP temporal fusion

Purpose: evaluate image-magnetic complementarity.

### M6: AIA temporal + SHARP temporal + GOES past-only full fusion

Purpose: main final multimodal model.

### M7: Optional HMI/SHARP image fusion

Purpose: include magnetic morphology maps if data coverage and compute budget permit.

This should not block the final paper if HMI image coverage is not ready.

## 7. Input construction

### AIA EUV sequences

Candidate channels:

- 94 Å
- 131 Å
- 171 Å
- 193 Å
- 211 Å
- 335 Å

Candidate windows:

- 6h sequence.
- 12h sequence.
- 24h sequence.

Start with a short window to control compute and coverage. Expand only if data-readiness audit supports it.

### SHARP temporal parameters

Use the leakage-audited SHARP parameter history already established in earlier notebooks.

Candidate windows:

- 6h.
- 12h.
- 24h.
- optional 48h if coverage is acceptable.

### GOES past-only features

Examples:

- M/X count in last 24h and 48h.
- C-class count in last 24h and 48h.
- Maximum past X-ray flux before `t`.
- Time since last C/M/X flare before `t`.
- Past flare activity index.

All GOES features must be generated from events strictly before or at `t`, never from the forecast window.

### HMI/SHARP image maps

Candidate products:

- LOS or radial magnetogram maps.
- SHARP CEA image products.
- Derived magnetic morphology channels where available.

This branch is optional until a coverage audit confirms feasibility.

## 8. Evaluation protocol

For each model:

1. Train only on training period.
2. Select epoch using validation performance.
3. Select threshold using validation TSS.
4. Freeze threshold.
5. Evaluate once on test period.
6. Save predictions, metrics, confusion matrix, and calibration outputs.

Report:

- TSS.
- HSS.
- ROC-AUC.
- PR-AUC.
- Precision.
- Recall.
- F1.
- Brier score.
- False-alarm ratio.
- Confusion matrix.

## 9. Explainability plan

### Tabular branches

- SHAP values.
- Permutation importance.
- Logistic coefficients where applicable.

### Image branches

- Grad-CAM or saliency maps on AIA channels.
- Case studies of true positives, false positives, and false negatives.

### Fusion branch

- Modality ablation.
- Gating/attention weights if used.
- Fold-specific error analysis.

## 10. Compute budget discipline

No cloud training run should begin unless the following are ready:

- Run name.
- Dataset manifest.
- Expected disk requirement.
- Expected GPU runtime.
- Backup path.
- Git commit plan.
- Shutdown/delete command.
- Stop condition.

Recommended operating rules:

- Use canary run first.
- Use small capped run second.
- Use official run only after loader/data audits pass.
- Copy models/results immediately after run.
- Commit small outputs to GitHub.
- Delete VM and disk immediately after each official run.
- Keep billing disabled unless actively running an approved experiment.

## 11. Immediate notebook sequence

### 17A: Protocol notebook

`notebooks/training/17A_final_cycle24_to_cycle25_temporal_multimodal_protocol.ipynb`

Purpose: formalise methodology, splits, model ladder, leakage rules, and compute plan.

### 17B: Data-readiness audit

`notebooks/training/17B_cycle24_to_cycle25_multimodal_data_readiness_audit.ipynb`

Purpose: measure actual coverage for AIA sequences, SHARP history, GOES past features, HMI images, and Cycle 25 samples.

### 17C: Loader canary

`notebooks/training/17C_temporal_multimodal_loader_canary.ipynb`

Purpose: verify tensor shapes, labels, splits, and no-leakage checks using tiny caps.

### 18A: Cross-cycle SHARP+GOES baseline

Purpose: establish Cycle 24 to Cycle 25 tabular reference before expensive image training.

### 18B: AIA temporal model

Purpose: evaluate temporal EUV image evolution.

### 18C: Full fusion model

Purpose: final AIA + SHARP + GOES multimodal temporal model.

### 19A: Explainability and manuscript figures

Purpose: generate final figures, ablation tables, error analysis, and paper-ready interpretation.

## 12. Final success criteria

A successful final phase must produce:

- A clean cross-cycle dataset audit.
- At least one Cycle 24 to Cycle 25 baseline.
- A temporal AIA model result.
- A multimodal fusion result.
- Modality ablation evidence.
- Explainability figures.
- A final manuscript-ready results table.
- A reproducible GitHub repository state.

The project should then be closed as a completed solar-flare research package.

## 13. Manuscript framing

The final paper should be framed as:

> A leakage-safe, solar-cycle-aware multimodal temporal framework for 48-hour M/X solar flare forecasting, integrating AIA EUV image evolution, SHARP magnetic time-series information, and past-only GOES activity descriptors, with independent Solar Cycle 25 testing and explainable model analysis.

Avoid claims of universal operational deployment unless calibration and false-alarm burden are fully addressed.
