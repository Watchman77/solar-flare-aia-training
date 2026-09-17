# Broader Cycle-24 final-fit proposal (v2)

## Why this exists
The user's September 16 terminal output reports a successful real AIA/SHARP
engineering test: four targets, three historical images each, twelve exact
magnetic records, and ten disposable CPU updates on two training examples only.
This is a model-interface test, not a forecasting-performance experiment. This
package does not rerun it or claim the private JSON report was inspected.

The user objected to restricting final weight fitting to 2010–2013. This package
implements a **separate proposal** that can include later Cycle-24 years in a
final refit while preserving held-out calibration and threshold data. It does
not replace or freeze the existing v1 date assignment.

## Proposed design — not an automatic protocol change
1. Development pool: available targets before 2019-12-01 UTC. That cutoff is a
   month-boundary convention reflecting the reported December 2019 cycle minimum,
   not a physically exact transition instant.
2. Reserve whole connected HARP/NOAA groups within this pool. Stratify groups by
   whether they have any original-positive structurally eligible targets. Within
   each stratum use one fixed hash ordering, without seed searching, to reserve
   approximately 10% for calibration, 10% for threshold assessment, and 80% for
   fitting. These percentages refer to GROUPS, not rows. All snapshots in a
   component keep the same final role. Existing event labels are not recertified.
3. Model-selection folds use only the fitting pool, with validation years 2013,
   2014 and 2015 and training strictly earlier than each validation year. Purge
   forecast endpoints at boundaries, check historical slots, and exclude groups
   spanning the train/validation boundary within each fold. No random row split.
4. After model settings and training duration have been selected, refit from
   scratch on the whole eligible fitting pool, now including later-year records
   (such as 2015–2017) outside the reserved groups. Refit preprocessing too.
5. Fit the final-model calibrator on the reserved calibration group set. Assess
   prespecified calibration alternatives and choose the operating threshold on
   the separate threshold set. Do not reuse the debug scaler or an earlier
   model's calibrator/threshold.
6. Freeze the pipeline, then test on 2021–2025. Apply that same frozen pipeline to
   the eligible covered portion of 2026. December 2019–2020 is separately retained
   for diagnostic evaluation. Do not use those evaluation scores to tune anything.

**Important trade-off:** final calibration and threshold data are retrospective
region holdouts within Cycle 24, not chronologically later than every observation
in the final fit. They therefore do not independently estimate future-regime
calibration. The cross-cycle test answers that. The model-selection folds stay
chronological. An explicit protocol decision is required before adopting v2.

## Execution
Upload only `aia17_prepare_broad_cycle24_fit.py` to the existing Cloud Shell home
and run:

```bash
"$HOME/aia17_time_venv/bin/python" "$HOME/aia17_prepare_broad_cycle24_fit.py"
```

The existing `~/aia17_assign_cross_cycle_roles.py` must still be present and must
match its recorded checksum. It is reused ONLY as a schema/checksum/identity
reader; its v1 role-assignment outputs are not imported or modified.

Defaults read the already-completed nominal temporal index:
`~/aia17_metadata_stage1/temporal_manifest_v1/reports/20260916T143622218859Z/`.

Outputs are NEW files under:
`~/aia17_metadata_stage1/broad_cycle24_finalfit_v2/reports/<timestamp>/`.

There are no network calls, package installations, raw-image reads, source writes,
Git actions, GPU launches or model updates. Standard-library Python only. The
script scans the existing index to calculate memberships; it does not rerun data
extraction, inventory, source-header retrieval or model integration.

## Main outputs
- `broad_cycle24_final_role_candidates.csv.gz`: every original target and label,
  its new proposed role, structural status, and pending scientific-clearance fields.
- `forward_development_fold_candidates.csv.gz`: forward-fold candidate roles
  for the final-fit pool only. Intentional reuse across separate development
  folds is different from forbidden train/validation sharing within one fold.
- `final_role_support.csv`, `final_roles_by_year.csv`, `forward_fold_support.csv`.
- `region_reservations.csv`: reproducible component assignments.
- `broad_cycle24_protocol_PROPOSED.json`: exact proposed conventions.
- `broad_cycle24_fit_report.json`, research note, checksums and a small ZIP.

A successful status is `BROAD_CYCLE24_FIT_PROPOSAL_BUILT_NOT_FROZEN`. It is not
training permission. The actual numbers of retained later-year samples and
positive groups remain to be measured on the user's data.

## Scientific safeguards
- Preserves original labels and known boundary-review exclusions.
- Requires the original nominal index's schema, row totals, and checksums.
- Excludes outer-period-spanning components; does not claim all connected
  identifiers are independently certified physical active regions.
- Enforces disjoint version-pinned AIA objects across final roles and within
  train/validation of each forward fold.
- Uses no evaluation labels or model performance to reserve development groups.
  Evaluation labels are copied/count-reported only, not used for reservations.
- Rechecks input hashes after processing. No seed retry if support is low.
- A five-positive-component warning threshold is merely a descriptive screen,
  not a guarantee that calibration or confidence intervals are reliable.
- Nominal object availability is NOT full timestamp, SHARP support, quality,
  event completeness, follow-up or operational-availability clearance.

## Tests actually executed in this environment
`python3 -m unittest -v test_broad_cycle24` — 22 tests passed on Python 3.13.5.
Tests use a synthetic multi-year source emitted by the existing temporal-index
builder, including the command-line workflow, hash verification, source
preservation, later-year fitting eligibility, whole-group reservations, forward
chronology, test-label invariance, object separation and output checksums.
No real 141,644-row assignment or live cloud operation has run here.

## Method references
- NASA/NOAA cycle-minimum announcement (December 2019, not an exact date-time):
  https://www.nasa.gov/news-release/solar-cycle-25-is-here-nasa-noaa-scientists-explain-what-that-means/
- Calibration requires data disjoint from classifier fitting:
  https://scikit-learn.org/stable/modules/generated/sklearn.calibration.CalibratedClassifierCV
- Time-ordered and group-aware evaluation principles:
  https://scikit-learn.org/stable/modules/cross_validation.html

These references support the general methodological distinctions. The 80/10/10
component allocation, cutoff convention and particular folds are NEW PROPOSED
research choices, not prescriptions taken from the references.
