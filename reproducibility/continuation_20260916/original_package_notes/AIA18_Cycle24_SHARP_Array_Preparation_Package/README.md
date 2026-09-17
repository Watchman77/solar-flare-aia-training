# Cycle-24 raw SHARP arrays for the broader training proposal

**Scope:** data preparation, not training or scientific clearance. The existing v2
proposal is consumed unchanged; no new split, image, label, calibrator or model
is created. Version: `18a-cycle24-raw-sharp-three-slot-arrays-v1`.

## Inputs already present in Cloud Shell

- Broader-role proposal: `~/aia17_metadata_stage1/broad_cycle24_finalfit_v2/reports/20260916T191645934223Z/`.
- Temporal index at the source directory recorded inside that proposal.
- Source lock: `~/solar_flare_aia/docs/research_audit/2026-09-15/stage1/source_lock_snapshot.json`.
- Raw SHARP CSV at the path recorded in that source lock.

No network, cloud command, image load, package installation or Git operation is
performed. Run using the existing NumPy environment:

```bash
"$HOME/aia17_time_venv/bin/python" "$HOME/aia18_build_sharp_training_arrays.py"
```

CLI overrides: `--proposal-run`, `--source-lock`, `--output-root`.
Default output root: `~/aia17_metadata_stage1/sharp_arrays_cycle24_v1/reports/`.

## Scientific interpretation

For the reported v2 proposal there are 52,155 structural training candidates,
6,253 calibration candidates and 6,317 threshold-holdout candidates. The expected
raw array shape is therefore `(64725, 3, 15)`, subject to the checked proposal.
Every selected row remains present if a SHARP record is absent or duplicated.

The three lags are 288, 192 and 96 minutes, oldest first. This extends the matched
three-slot interface test to the Cycle-24 candidate population. It is not a new
24-hour aggregate or a replacement for the planned longer-history experiments.

Exact keys are `(HARPNUM, explicit raw TAI T_REC)`. Time arithmetic stays on a
uniform TAI coordinate and does not attach UTC to naive values. The 15 magnetic
feature names and their order match the integration test. `TOTUSJH` is not used
or substituted. Original labels come from the role/target manifest, never the
historical SHARP records or NPZ labels.

Values are unscaled and not imputed. Nonfinite or unparseable values remain NaN.
Any duplicated exact raw key invalidates the entire corresponding raw slot;
no first/last row is selected. Missing and duplicate counts are saved. Raw QUALITY
and NOAA fields are retained in source evidence; no scientific quality filter
or general NOAA association certificate is applied here. Explicit NOAA_AR_clean
mismatches, if present, receive a separate flag. The file scan covers the existing
all-year CSV, but only requested Cycle-24 records are retained in arrays.

Only the Cycle-24 final-training pool and reserved calibration/threshold groups
are included. Final roles and forward-development exclusions do not change.
Fold-to-array indices are checked against the reported retained fold counts.
Preprocessing must later be fitted within each development training fold, then
refitted on the accepted final training pool. No old debugging scaler is reused.

Training remains unapproved pending the existing label, follow-up, observation-
time, SHARP quality/availability and final-protocol decisions. Calibration here
is retrospective region-held-out within Cycle 24, not chronologically later than
all final-model training observations. Cycle-25 and 2026 arrays are not built by
this step. The PINN/PIML track is unchanged and separate.

## Outputs

- `sharp_raw_three_slot.npy`: raw float64 magnetic values, `[N,3,15]`.
- `sharp_finite_mask.npy`: explicit finite-value mask.
- `sharp_record_match_counts.npy`: exact source-row counts per historical slot.
- `original_manifest_targets.npy`: unchanged target labels.
- `cycle24_array_rows.csv.gz`: row indices, identities, proposed roles, checks.
- `unique_sharp_source_records.jsonl.gz`: source-record indices, raw QUALITY/NOAA,
  historical image identity and object generation, match and numeric counts.
- `forward_development_array_rows.csv.gz`: checked forward-fold row indices.
- `sharp_array_build_report.json`, research log, `COMPLETE.json` and small summary.

File presence/finite values are not a scientific eligibility rule. A failed run
without COMPLETE.json is not a finished array release. No source file is changed.
The program requires at least 1 GiB free before starting; output arrays and small
records are separate from the source directories.

## Tests

Run `python3 -m unittest -v test_sharp_arrays` within this package. Eighteen local
synthetic tests passed. A separate compatibility run exercised the actual earlier
temporal builder and broader v2 role builder on synthetic inputs, then created
240 target arrays with 720 exact matching records using this new script.
The real 64,725-target build has not been executed here. No solar forecasting
result, calibration claim or live-cloud test is implied by these software tests.
