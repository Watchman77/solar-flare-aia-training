# Standard Research Checklist: Trustworthy Scientific Machine Learning

**Adopted at the user's request. Protocol revision: 14 September 2026.**

## Standing checklist

**Performance → Calibration → Uncertainty → Robustness → Explainability → Statistical significance.**

This is a research-quality checklist, not a claim that each project has implemented all methods. For every serious ML study, record each item as implemented and evaluated, planned, not feasible with the available evidence, or not applicable with a reason. Use methods proportionate to the question, data, and compute budget.

## Three distinct uncertainty questions

| Level | Question | Evidence to retain |
|---|---|---|
| Prediction uncertainty | How stable is an individual forecast across plausible fitted models or stochastic passes? | Mean probability, disagreement, method, seeds/passes, calibration state, and diagnostic performance. |
| Metric uncertainty | How uncertain is the estimated population performance from this finite evaluation sample? | Point estimates, dependence-aware bootstrap 95% confidence intervals, sampling units, and failed/undefined replicates. |
| Calibration | Do forecast probabilities agree with observed event frequencies in comparable cases? | Brier score, log loss, reliability diagrams with bin counts, ECE definition, and raw-versus-calibrated comparisons. |

A model probability is not a measurement of our certainty about that probability. An ensemble standard deviation is not automatically a 95% confidence interval, and a narrow spread does not rule out shared model bias or failure under distribution shift. Calibration concerns groups of forecasts and is not a guarantee about an individual outcome. [1–5]

## Minimum reporting contract

**Performance.** Define the population, task, horizon, independent sampling units, class distribution, split and baselines. Report appropriate discrimination, decision and probabilistic metrics. Distinguish average precision from trapezoidal PR-AUC. Preserve predictions and evaluation code.

**Calibration.** Assess raw probabilities before choosing a recalibration method. Fit any calibrator on development data separated from model fitting and keep the final test independent. Report bin construction and support, not ECE alone. Brier and log loss assess more than calibration in isolation. [3,5,6]

**Uncertainty.** Choose a practicable prediction-UQ method when relevant: Monte Carlo dropout in a compatible trained architecture, or independently trained deep ensembles are starting options. Keep prediction spread separate from metric CIs and training-seed variation. Resample at the unit justified by the data dependency structure, not automatically at image/frame/row level. [1,2,7]

**Robustness.** Evaluate relevant time, site, instrument, missing-data and distribution-shift conditions using a prespecified plan. Treat instrument-noise propagation as separate from model disagreement unless it is explicitly implemented. Do not claim shift-proof calibration. [4]

**Explainability.** Relate explanations to correct and incorrect predictions, uncertainty and missing modalities. Examine stability across seeds/perturbations where feasible. An explanation is not evidence of causal correctness.

**Statistical significance.** Prespecify the main comparisons and effect sizes. Use paired, dependency-aware comparisons on common evaluation cases, report CIs for performance differences, and account for multiple comparisons when making confirmatory claims. A collection of overlapping or nonoverlapping single-model CIs is not a substitute for an appropriate paired comparison. Formal significance must not substitute for practical importance.

## Project applications

**Solar AIA + SHARP.** Preserve the same-active-region 48-hour M/X target and chronological cross-cycle protocol. Audit AR/track/time dependencies; hold calibration and threshold choices outside the final test. A separate PINN/PIML track stays separate.

**PV anomaly detection.** Evaluate a human-review option for uncertain hotspot/shading/crack classifications. Report the fraction automatically classified, fraction referred, class-specific errors, and risk versus coverage. Retain full-test performance; do not hide difficult cases by removing them from the denominator. Group related images by panel/site/acquisition session where such identifiers exist; document absent identifiers. This is a proposed evaluation design, not a deployed safety guarantee. [8]

**Other projects.** Apply the same questions to digital twins, engineering, health prediction and other research without conflating their data or experimental results.

## Scientific identity and status

Research direction: **Scientific ML + UQ + XAI + robust validation.** This describes the research programme. Use “implemented”, “validated”, or “improved” only where executed code and recorded results support those claims. Existing results remain unchanged until the new analyses have actually been run.

## References

[1] Gal & Ghahramani (2016), Dropout as a Bayesian Approximation. PMLR 48. https://proceedings.mlr.press/v48/gal16.html

[2] Lakshminarayanan, Pritzel & Blundell (2017), Simple and Scalable Predictive Uncertainty Estimation using Deep Ensembles. NeurIPS 30. https://proceedings.neurips.cc/paper_files/paper/2017/hash/9ef2ed4b7fd2c810847ffa5fa85bce38-Abstract.html

[3] Guo et al. (2017), On Calibration of Modern Neural Networks. PMLR 70. https://proceedings.mlr.press/v70/guo17a.html

[4] Ovadia et al. (2019), Can You Trust Your Model's Uncertainty? NeurIPS 32. https://papers.neurips.cc/paper_files/paper/2019/hash/8558cb408c1d76621371888657d2eb1d-Abstract.html

[5] scikit-learn, Probability calibration, official documentation (checked 14 September 2026). https://scikit-learn.org/stable/modules/calibration.html

[6] Roelofs et al. (2022), Mitigating Bias in Calibration Error Estimation. PMLR 151. https://proceedings.mlr.press/v151/roelofs22a.html

[7] Saravanan, Berman & Sober (2020), Application of the hierarchical bootstrap to multi-level data in neuroscience. The general dependence principle motivates project-specific AR/group resampling; this is not a solar-specific validation of a chosen bootstrap. https://pmc.ncbi.nlm.nih.gov/articles/PMC7906290/

[8] Geifman & El-Yaniv (2019), SelectiveNet: A Deep Neural Network with an Integrated Reject Option. PMLR 97. https://proceedings.mlr.press/v97/geifman19a.html
