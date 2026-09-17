# Broader Cycle-24 final-fit proposal — 16 September 2026

17C four-sequence AIA+SHARP integration was reported as successful by the user.
This step does not repeat that test and does not review or certify its unseen JSON.

This is a separate proposed experiment, not a silent rewrite of v1. Retain the
v1 canary assignments and old snapshot benchmarks. For the main design, reserve
whole Cycle-24 region components approximately 10% for calibration and 10% for
threshold assessment within positive/negative component strata; the remaining
approximately 80% are a broader fitting pool. Fractions refer to groups, not rows.
No test label or model score selects the split and no seed is searched.

Use chronological forward development folds within that fitting pool. After
selection, refit from scratch on all eligible fitting-pool observations through
November 2019, including 2015–2017 wherever retained. Refit preprocessing too.
Holdout groups stay excluded from every model-development and final-model fit.
Calibrate the final model on the calibration holdout, assess prespecified
calibration choices and choose a threshold on the threshold holdout, then freeze.
The 2021–2025 test and covered 2026 extension remain time-held-out evaluations.

IMPORTANT: the final within-Cycle-24 calibration/threshold design is a
RETROSPECTIVE REGION HOLDOUT, not a future-period chronological holdout. It does
not estimate future-regime calibration; that is assessed on the independent
cycle. It trades chronological calibration ordering for broader fitting-year
coverage. Adopting it requires an explicit protocol decision. A strict future-
period calibration alternative is not implemented by this file.

All targets and original labels remain preserved with structural exclusions.
Region components are linked identifiers, not certified independent physical
regions. Nominal history availability and these assignments do not certify
all source timestamps, SHARP time support, event completeness or follow-up.
No GPU, cloud or Git operations and no model fitting were performed.
