# 17C preparation: nominal temporal manifest and strict local sequence loader

## What is implemented

`aia17_build_temporal_manifest.py` joins the completed canonical issue-time table
with the completed target/object register. It produces a new three-frame history
index without relisting the bucket or downloading any tensor.

This is a **proposed history-only experiment**. Each target retains its original
identity, physical issue time and original `label_48h_final`. The nominal frame
slots are t−288, t−192 and t−96 minutes, in chronological order, inside a six-hour
lookback window. No current-slot image is used. This does not replace the earlier
snapshot benchmarks or certify their metrics. It does not freeze a train/test split.

The chosen starting design has three frames over a 192-minute first-to-last span;
"six-hour lookback" is a selection window, not a claim of continuous six-hour imagery.
Its latest frame is nominally 96 minutes old, a freshness/coverage trade-off to
measure. A lagged single-frame comparator should use the same latest frame and
matched targets, avoiding conflating temporal modelling with different freshness.

## Run on the restored Cloud Shell

Upload the single Python file to the home directory. Run:

```bash
"$HOME/aia17_time_venv/bin/python" "$HOME/aia17_build_temporal_manifest.py"
```

The build path uses only the standard library. There is no dependency install,
Google login, browser request, gcloud invocation, image read, source repair or Git
operation. The optional local tensor loader uses NumPy already in that environment.

Existing inputs are pinned by SHA256:

- `~/aia17_metadata_stage1/archive_reconciliation_v1/reports/20260916T073559880010Z/target_object_register.csv`
- `~/aia17_metadata_stage1/reviews/time_label_impact_20260915T172829490191Z/sample_time_and_window_diagnostics.csv.gz`

It does not silently choose a newer file. A missing file/hash mismatch stops the
build; do not rerun unrelated download/extraction steps to work around that error.

## Outputs

New, timestamped directory:
`~/aia17_metadata_stage1/temporal_manifest_v1/reports/<timestamp>/`.

- `temporal_sequence_candidates.jsonl.gz`: one record for every target, including
  missing histories, object generations, original label, issue UTC, nominal source
  slots, and explicit pending statuses.
- `sequence_coverage_by_year_and_original_label.csv`: nominal coverage, with original
  positive/negative denominators and distinct HARP–NOAA identifier-pair support.
- `temporal_manifest_report.json`: selected design, counts and limitations.
- `research_log_temporal_manifest.md`: research checkpoint.
- `COMPLETE.json`: hashes of generated outputs; absence means an incomplete build.
- `summary_for_review.zip`: only the small summary files, not the full history index.

Every target is retained. Missing images do not become negative labels. A target's
own current image need not exist if all three preceding images exist; report this
population change when comparing with a snapshot baseline. Sources outside the
curated table are not searched. Selection uses exact nominal TAI slots and the same
HARP and NOAA identifiers, never the preceding three global dataframe rows.

The known July 2024 stale source/target pairing is excluded as a history frame. Its
target row and original label remain in the index, with the previously reported
conditional label disagreement flagged. All original labels remain unrecertified.

The histories can cross calendar years; no fold assignment is invented. Downstream
splitting must explicitly account for region overlap, input-history policy and
48-hour label-window purge. Distinct IDs are not certified independent events.

## Three separate meanings of “ready”

1. **Nominal history objects available:** the three requested records and their
   exact nonempty object generations are in the completed inventory. This build
   measures that status. It does not extrapolate 18 canary files to the archive.
2. **Observation-time eligible:** each channel's actual source evidence is tied
   to the selected object, meets historical-slot alignment and has a verified
   contributing-data bound no later than the fixed issue time. Nominal lag alone
   does not establish this status.
3. **Research-run eligible:** labels/follow-up, input availability, split/purge,
   calibration roles and the approved experimental protocol are also satisfied.

No row is automatically granted status 2 or 3 by this build. The output always
states `training_authorised: false`. This is not a reason to repeat the completed
source investigations; it is a machine-readable boundary between candidate indices
and a fully checked modelling population.

## Strict local loader API (implemented; fixture-tested)

```python
result = load_local_sequence(candidate_record, local_objects, timing_evidence)
x = result['x_tchw']  # (3, 6, 512, 512), float32
original_target = result['original_manifest_target']
```

`local_objects` maps `(object_uri, generation)` to a local NPZ. No download fallback
exists. `timing_evidence` maps each historical sample ID to a record with:

- `history_sample_id`, `object_uri`, `object_generation`, `HARPNUM`, `NOAA_AR_clean`;
- `npz_sha256`, independently verified against the pinned cached object;
- `channels`: exactly 94, 131, 171, 193, 211 and 335; each record contains
  `midpoint_tai_us`, `contributing_end_tai_us`, `end_bound_verified`, `source_record`
  and `conversion_provenance`.

The integer times are microseconds on the continuous TAI coordinate from the
1970-01-01 TAI epoch, compatible with the earlier scale-aware time layer. Source UTC
must be converted, not relabelled as TAI. Original raw TAI record intervals use that
uniform coordinate, not naive UTC differences across leap seconds. The main build
reuses already-converted issue UTC strings without recomputing them.

Do not set `end_bound_verified=True` merely from nominal time, filename time, a
mean-exposure proxy, the 18-file canary, or the observed maximum offset in it. The
loader enforces the supplied provenance contract; it cannot establish whether a
caller honestly obtained that provenance. It does not certify product publication
latency, SHARP temporal support, labels or operational readiness.

The loader refuses unknown bounds, future-contributing data, wrong object versions,
wrong source identity, nonfinite/wrong-shape arrays and wrong channel order. It uses
`allow_pickle=False`. It returns the original manifest label, never embedded NPZ y.
The full target-label validation and model training are NOT performed by this API.

## Tests and publication status

Run `python -m unittest -v test_aia17_temporal_manifest.py` from this package folder.
24 local tests passed at preparation, including a small end-to-end file-build fixture
and real synthetic NPZ arrays loaded as a (3,6,512,512) sequence. No live archive or
full user table was executed here. `tests_run.txt` records the actual test run.

The package has not been installed in the user's Cloud Shell or pushed to GitHub.
The original AIA+SHARP+past-only GOES model roadmap, evaluation standard (performance,
calibration, UQ, robustness, explainability, statistical comparisons), and separate
PINN/PIML track remain unchanged. Final SHARP inputs need contributing-time/availability
checks too; delaying AIA alone does not validate the magnetic branch.
