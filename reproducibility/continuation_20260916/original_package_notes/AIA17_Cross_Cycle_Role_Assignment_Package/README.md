# First cross-cycle role assignment — explicit proposal

This package builds a **new role-assignment sidecar** for the already completed
`17c-nominal-history-index-v1` index. It does not rebuild that index, download data,
read image tensors, fit a model, replace labels, freeze the protocol, or publish to GitHub.

## Run in the existing Cloud Shell

Upload only `aia17_assign_cross_cycle_roles.py` to the home directory, then run:

```bash
"$HOME/aia17_time_venv/bin/python" "$HOME/aia17_assign_cross_cycle_roles.py"
```

No new dependencies or extra flags are needed. The default input is the completed run
`~/aia17_metadata_stage1/temporal_manifest_v1/reports/20260916T143622218859Z/`.
The program reads its `COMPLETE.json`, verifies the recorded checksums of the
JSONL candidate index and report, validates their schema, and rechecks the source
hashes after creating new outputs. It does not require uploading `summary_for_review.zip`
back to ChatGPT first.

## Proposed first benchmark, NOT a final/all-Cycle-24 weight fit

| Role | UTC interval, end exclusive |
|---|---|
| Weight fitting and train-only preprocessing | 2010-01-01 to 2014-01-01 |
| Model / epoch / hyperparameter selection | 2014-01-01 to 2014-07-01 |
| Calibration fitting for the selected model | 2014-07-01 to 2015-01-01 |
| Threshold selection and development calibration assessment | 2015-01-01 to 2016-01-01 |
| Post-freeze late-period diagnostic, no further selection | 2016-01-01 to 2020-01-01 |
| Separate early-Cycle-25 diagnostic | 2020-01-01 to 2021-01-01 |
| Primary independent Cycle-25 test | 2021-01-01 to 2026-01-01 |
| Covered portion of 2026, supplementary only | 2026-01-01 to 2027-01-01 |

**This is an explicit new candidate calendar allocation.** The existing earlier
2018-2019 validation example is not used. Only 2010-2013 is used for weight fitting
in this proposed first benchmark; later Cycle-24 records have development/diagnostic
roles. Do not call this training on every available Cycle-24 year. No alternate
allocation is silently selected if a development role loses its positives.

The first and second halves of 2014 are not presumed to contain adequate independent
positive support: the program measures the retained counts before any protocol freeze.
A both-class absence is a structural blocker. Fewer than five positive identifier
components triggers a descriptive warning; five is not a statistical adequacy threshold.
Final scientific adequacy requires more than these checks.

## Structural exclusions and retained evidence

- All target rows and original labels stay in the sidecar, with exclusion reasons.
- Canonical UTC issue times and physical 48-hour UTC endpoints come from the existing
  locked index. This program does not reimplement TAI/UTC conversion.
- The inclusive forecast endpoint must be strictly before the next calendar role.
- Nominal AIA frames may not come from another calendar role.
- HARP and NOAA identifiers are linked in conservative connected components. Whole
  components spanning different calendar roles are excluded from the proposed retained
  population; incomplete histories still participate in this overlap check.
- The known July 2024 stale source pairing cannot become a nominal history candidate.
- Targets flagged for the conditional label-boundary decision are held out from the
  proposed retained population without replacement labels.
- The program verifies that no pinned AIA object is shared by retained roles.
- These identifier components are not independently certified physical active regions.
- SHARP histories/contributing windows, original label/censoring provenance, actual AIA
  times, and historical product availability remain separate readiness requirements.

The UQ standard and separate PINN/PIML track are preserved. No test model metrics
are calculated or used in choosing the proposed dates. Models/scalers/calibrators/
thresholds must not be fitted on the Cycle-25 test set.

## Outputs

New timestamped directory under `~/aia17_metadata_stage1/cross_cycle_role_proposal_v1/reports/`:

- `cross_cycle_role_assignments.csv.gz`: per-target role sidecar, join to the source
  index by target ID and the source-index checksum in the report.
- `cross_cycle_role_support.csv`: counts before/after structural exclusions by role.
- `region_components.csv`: conservative identifier links and role membership.
- `cross_cycle_assignment_report.json`: status, hashes, blockers, caveats.
- `first_cross_cycle_protocol_proposal.json`: the proposed, not frozen calendar rules.
- `research_log_cross_cycle_assignment.md`: a research-log addition.
- `COMPLETE.json`: output hashes; incomplete runs do not have a completion marker.
- `cross_cycle_summary_for_review.zip`: small report package, excluding the large sidecar.

A completed run is **CROSS_CYCLE_ROLE_PROPOSAL_BUILT_NOT_FROZEN**. It always retains
`training_authorised: false`. A 'role_constraints_pass' value of 1 means structural
assignment checks passed, NOT that the sample is eligible for final model training.

## Tests

From this package's extracted directory:

```bash
python3 test_aia17_cross_cycle_roles.py
```

The included original `aia17_build_temporal_manifest.py` is an unchanged fixture
provider for integration testing, not an instruction to rerun the real temporal build.
Seventeen local tests passed, including an end-to-end run using 64 synthetic records
written by that builder. No actual full 141,644-row assignment was run here; no live
cloud/Git operations or training have been tested or performed by this package.

## Reference methodology

The precise dates are a proposed design choice, not an externally established optimal
split. The general separation of fitting, calibration and evaluation follows:

- https://scikit-learn.org/stable/modules/generated/sklearn.calibration.CalibratedClassifierCV.html
- https://scikit-learn.org/stable/common_pitfalls.html
- https://scikit-learn.org/stable/modules/cross_validation.html

December 2019 marks the solar-cycle transition, so the 2016-2019 diagnostic block
is deliberately described as a calendar block, not entirely Cycle 24:

- https://www.nasa.gov/news-release/solar-cycle-25-is-here-nasa-noaa-scientists-explain-what-that-means/
