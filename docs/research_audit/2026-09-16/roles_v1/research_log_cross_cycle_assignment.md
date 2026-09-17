# Cross-cycle role assignment proposal

First benchmark proposal, not a frozen scientific or GPU-run approval.

- train: [2010-01-01T00:00:00Z, 2014-01-01T00:00:00Z) — Fit preprocessing and model weights on this subset of Cycle 24.
- model_validation: [2014-01-01T00:00:00Z, 2014-07-01T00:00:00Z) — Model/epoch/hyperparameter selection, not weight fitting.
- calibration_fit: [2014-07-01T00:00:00Z, 2015-01-01T00:00:00Z) — Fit a prespecified calibrator to the frozen selected model.
- threshold_selection: [2015-01-01T00:00:00Z, 2016-01-01T00:00:00Z) — Assess calibration and select operating threshold; not independent test.
- late_period_diagnostic: [2016-01-01T00:00:00Z, 2020-01-01T00:00:00Z) — Post-freeze diagnostic only; this block includes the late-2019 cycle transition.
- early_cycle25_diagnostic: [2020-01-01T00:00:00Z, 2021-01-01T00:00:00Z) — Separate 2020 low-activity diagnostic, never a development set.
- independent_cycle25_test: [2021-01-01T00:00:00Z, 2026-01-01T00:00:00Z) — Primary held-out 2021-2025 cross-cycle evaluation, no tuning/refitting.
- supplementary_2026: [2026-01-01T00:00:00Z, 2027-01-01T00:00:00Z) — Only the actually covered 2026 records, not a complete-year claim.

All source targets and labels are preserved. Region-component exclusions and boundary checks are explicit; actual timing, label validity, SHARP support and development support remain to be cleared. No tests or experiment scores selected this calendar allocation.

## Limitations

- This is an explicit FIRST benchmark proposal. Only 2010-2013 fits model weights; it does not use all Cycle-24 data for fitting.
- 2014 model-selection/calibration subperiods must have their retained support reviewed. No automatic date fallback.
- 2015 is a threshold/calibration-assessment development set, not an independent test.
- 2016-2019 diagnostics must not be used to revise the selected model; late 2019 spans the physical cycle transition.
- The 2021-2025 test period remains independent; 2020 and the covered portion of 2026 are separate.
- Only canonical timestamps and forecast endpoints already in the locked index are used; no new TAI/UTC conversion occurs.
- 48-hour endpoint and AIA nominal-history boundary checks are structural; actual exposure and product availability are still pending.
- SHARP history construction, contributing observation windows, availability, and any further boundary embargo remain to be verified.
- A nominal history pass is not source-time clearance. Labels and continuous follow-up are still not certified.
- Region links are conservative identifier associations, not independently established physical-region identities.
- No calibration-method, significance threshold, model-selection metric or architecture is selected by this program.
- Retained class/group counts are based on original labels; diagnostic statistics are not performance results.
- A model-time or group cutoff can remove a whole region; excluded targets remain in the sidecar with their reasons.
- This new sidecar does not rewrite the source index, fit a model, authorize a GPU, or publish to GitHub.
