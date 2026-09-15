# AIA + SHARP: Uncertainty, Calibration and Statistical Evaluation Addendum

**Revision:** 14 September 2026. **Status:** adopted evaluation requirements; specific tuning choices are provisional. **Executed UQ experiments:** none supplied by this update.

This addendum implements the user's requested research checklist in the 17A/17B planning package. It adds evaluation requirements, configuration and notebook guidance. It does not train models, compute real UQ results, freeze date splits, change the staged CSV sources, or modify cloud resources. The 17B stage-1 audit code is unchanged.

## 1. Scientific contract retained

Same-active-region M/X occurrence in `(t, t+48h]`; official target `label_48h_final`; six AIA channels 94/131/171/193/211/335 Å; 96-minute source cadence; 512×512×6 source tensor; 180-second matching tolerance with no image after issue time; train-only preprocessing; development-only calibration and thresholds; independent Cycle-25 testing. Date roles remain proposed until the readiness audit and protocol review are complete.

Completed 16B is the historical within-Cycle-24 reference. Its saved 2013, 2014 and 2015 fold checkpoints are **not** interchangeable ensemble members for any of those historical tests: their training periods differ and a later fold may include another fold's test year. Build/reuse ensemble members only when their eligible training and development data match the evaluated split.

The 20A heat-equation PINN, 20B SHARP physical-proxy learning and 20C evidence summary remain a separate track. When 20B is run, use the appropriate forecasting evaluation standard; for 20A, use solution error, equation residual and boundary/initial-condition errors rather than forcing classification metrics onto a PDE demonstration.

## 2. Prediction uncertainty

**Cost-controlled candidate A: MC dropout.** Start with a canary on a compatible checkpoint that was trained with the relevant dropout mechanism. Proposed pilot: 30 stochastic passes; check stability using more passes on development data before freezing the official pass count. At inference, activate only the intended stochastic mechanism; keep normalization behaviour fixed and do not refit preprocessing. Inspect actual architecture code before implementation, especially functional/recurrent dropout. Without compatible trained dropout, this is not an automatic retrofit. [1]

**Candidate B: deep ensembles.** Proposed minimum pilot: three independently trained seeds with the same data split and model specification; expand toward five only when justified by validation and budget. Fix the member set using development rules, not test performance. Average probabilities as the initial aggregation rule; preserve member probabilities and raw logits when available. Three members are not enough evidence to advertise precise tail-coverage guarantees. [2]

Candidate sizes above are new planning defaults, not universal constants and not claimed optimal. Compare against a single-model baseline; do not automatically train ensembles for every architecture or modality.

**Required prediction outputs when feasible:** mean raw probability, calibrated probability from the chosen frozen calibrator, raw member/pass standard deviation, predictive entropy, member/pass count, UQ method, seed list, sample/AR/time/split identifiers, and calibration model ID. A high-entropy forecast can occur even when all members agree near 0.5; therefore do not report disagreement as the only uncertainty quantity.

For raw probabilities `p_m`, use `p_bar = mean(p_m)`, sample dispersion with the denominator explicitly recorded, and `H(p_bar)` where `H(p) = -p log p - (1-p) log(1-p)`. An optional `H(p_bar) - mean(H(p_m))` is a model-disagreement diagnostic, not a directly measured separation of all physical uncertainty sources. Use natural logarithms and define boundary handling. A calibrator applied to the mean does not automatically calibrate the raw dispersion or create a calibrated interval for the true probability.

Do not call a member range, dropout quantile range, or mean ± 1.96 standard deviations a guaranteed 95% interval for the true flare probability. Distinguish epistemic-model proxies from instrument noise, missing observations, label/censoring uncertainty and event-outcome variability. Cross-cycle shift can leave all members confidently wrong. [1,2,4]

## 3. Metric uncertainty and paired comparisons

Report 95% confidence intervals for TSS, HSS, ROC-AUC, average precision/defined PR-AUC, precision, recall, F1, Brier and other headline metrics when estimable. Proposed initial setting: **2,000 bootstrap replicates**, with Monte Carlo stability checks and a recorded seed.

**Primary resampling unit is not an individual timestamp.** Audit HARP-to-NOAA mappings and connected physical-region/track identities, then resample independent AR groups while retaining their within-group records. Prespecify the statistic's weighting: initial proposal is sample-weighted performance over the defined forecast-issue population, not an accidental switch to equal-AR weighting. If common time-dependent effects remain material, add an appropriate time-block sensitivity analysis. Freeze units/block-length rules without using favourable test results. Group bootstrap is not a universal guarantee; few positive groups and nonstationarity limit inference. [7]

Keep fitted models, calibration mappings and thresholds fixed during ordinary test bootstrap. These intervals quantify evaluation-sampling uncertainty **conditional on the fitted pipeline**; report training-seed variability separately. Do not refit or optimize a threshold in each test replicate.

When a replicate has no positive or negative examples or an undefined metric, record it as undefined and report the attempted, valid and invalid counts. Do not replace undefined values with zero or quietly resample until all are valid. Too many degenerate replicates or too few independent positive groups require a limitation or withholding the interval, not a more optimistic estimator chosen after viewing the result.

For comparisons, use common eligible sample IDs and the **same bootstrap group draw for both models**, then report differences such as `TSS_fusion - TSS_SHARP` with paired 95% CIs. Preserve full-coverage results separately when modalities differ in availability. Prespecify a small primary comparison family; select any formal clustered test and multiplicity procedure before confirmatory testing. Ordinary row-level McNemar tests must not be assumed valid for correlated AR snapshots.

Historical saved prediction CSVs can support retrospective metrics/calibration diagnostics and paired intervals if they retain labels, scores, IDs and times. Retrospective diagnostics are not new independent test evidence and must not be used to tune the final cross-cycle protocol against historical test labels.

## 4. Calibration and development-set roles

Always retain uncalibrated probabilities and report raw and calibrated results. Required: Brier score, binary log loss, event-probability reliability diagram with bin support, and clearly defined ECE. Add a constant training-prevalence probability reference, applied unchanged to test; do not select a deployment probability by inspecting test prevalence. Brier measures overall probabilistic accuracy, not calibration alone. [3,5]

**ECE convention:** use the M/X event probability, not just confidence in the predicted majority class. For bins `B_b`, use `sum_b (n_b/N) * abs(mean(p in B_b) - mean(y in B_b))`. Initial reporting proposal: ten equal-width probability bins, with twenty-bin and equal-frequency sensitivity summaries; merge/report sparse or empty bins transparently and do not use test ECE to pick the calibration method. Show sample and positive counts because rare-event aggregate summaries can hide weakly supported high-risk bins. ECE is sensitive to binning and finite-sample estimation. [6]

**Candidates:** sigmoid/Platt or temperature scaling as parsimonious starting options; isotonic only when development support is sufficient, including independent positive groups. Treat the no-calibration baseline as a real candidate. Candidate selection uses held-out or time/group-aware development evaluation; do not choose methods by their in-sample calibration fit or by final test results. Isotonic can overfit a small calibration set. [3,5]

**Logical data roles:** model fitting → development model/checkpoint selection → calibration fitting → calibration-method assessment and operating-threshold selection → locked test. These need not require five calendar partitions. Use appropriately separated chronological/AR-safe development portions or a defensible nested forward-chaining scheme. Exact dates and sample counts are **pending the audit**; when rare positives do not support the preferred separation, document a simpler design rather than calling reused development scores independent estimates.

Fit the final calibrator for the actual deployed predictor (e.g. the ensemble mean), then choose the TSS operating threshold on the corresponding calibrated development scores and freeze both. Do not transfer a threshold defined on raw scores unchanged onto recalibrated probabilities without validating that decision rule. Natural/representative prevalence must be preserved in calibration/evaluation; do not balance the calibration set without a justified prevalence correction.

Inspect calibration separately by held-out year/regime using the frozen predictor. Pooled calibration must not conceal cross-cycle deterioration. No Cycle-25 labels may be used to calibrate the independent Cycle-25 test. A later operational recalibration experiment must be a separately declared forward-evaluation design. [4]

## 5. Robustness, explanation and referral evaluation

Prespecify tests for cross-cycle shift, history gaps, missing channels/features, quality strata and modality ablation where scientifically meaningful. Perturbations based on documented instrument uncertainty are distinct from generic stress tests; neither should be claimed to measure all observational noise by default. Check uncertainty/error association and confident errors, not just uncertainty histograms. [4]

Explain low- and high-uncertainty true positives, false positives and false negatives. Where feasible, compare explanations across seeds and modalities. Attention/gating weights and saliency do not automatically establish physical causality.

PV transfer: assess a validation-frozen review/referral rule for uncertain hotspot/shading/crack cases. Report risk–coverage curves, automated coverage, referral load, per-class retained errors and full-population performance. Human review is not assumed perfect. In solar forecasting, abstention must not silently become a no-flare forecast; a fallback/escalation policy would require its own evaluation. [8]

## 6. Integration and budget

| Stage | New requirement | Status in this update |
|---|---|---|
| 17A | Explicit UQ/calibration/bootstrap/evaluation protocol | Documented; detailed settings provisional |
| 17B | Audit grouping, positive-group counts, candidate calibration support, time/quality/missingness and paired eligibility | Requirements documented; not added to stage-1 computation |
| 17C | Verify score/logit export, ID alignment, deterministic baseline, stochastic path and normalization stability | Planned |
| 18A | Saved tabular predictions, raw/calibrated probabilistic metrics, dependency-aware CIs | Planned |
| 18B/18C | Costed MC-dropout and/or seed-ensemble comparison on selected candidates | Planned |
| 19A | Reliability, uncertainty/error, risk–coverage, paired-effect and explanation reports | Planned |
| 20A–20C | Retain separate physics-informed track with task-appropriate evidence | Separate; no automatic merger |

No additional GPU run, model retraining or repeated AIA download is authorised by this protocol update. First reuse valid saved predictions for lightweight evaluation where possible. Benchmark any stochastic inference on development data before allocating paid compute. The current 17B metadata run can finish unchanged.

## 7. Reproducibility outputs

Later execution should save: protocol/config version; source versions; split and group definitions; model/checkpoint and seed IDs; raw/mean/calibrated probabilities and raw logits where available; calibrator fit IDs; frozen thresholds; per-model point estimates/CIs; bootstrap indices or reproducible group-draw configuration; paired metric differences; reliability bin counts; uncertainty diagnostics; missing-modality masks and error explanations. Store large arrays/checkpoints externally, commit reviewed small summaries and code in one coherent batch.

**References:** numbered [1]–[8] refer to `docs/TRUSTWORTHY_RESEARCH_STANDARD.md`. Project history is retained in the prior continuation record and original 17A/17B package. This addendum makes new evaluation requirements explicit rather than rewriting earlier results.
