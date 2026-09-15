# AIA 17A/17B metadata-first continuation package

Created 8 September 2026. Basis: restored main checkpoint `d1b921e`, the final-sprint plan and the user's source/header probe. This package does not contain research data, credentials or trained models.

## Files

- `notebooks/training/17A_final_cycle24_to_cycle25_temporal_multimodal_protocol.ipynb`: protocol scaffold, with exact splits explicitly **not frozen**.
- `notebooks/training/17B_cycle24_to_cycle25_multimodal_data_readiness_audit.ipynb`: runnable **stage 1 only** of the readiness audit.
- `configs/aia17_metadata_stage1.json`: scientific guardrails, five exact source objects and size limits.
- `src/aia17_metadata_audit.py`: standard-library staging/audit implementation.
- `scripts/run17_metadata.py`: terminal entry point using the same implementation.
- `tests/test_aia17_metadata.py`: synthetic-data tests, not solar research results.

## Run in the restored Cloud Shell workspace

The supplied `aia_17ab_setup.py` installer installs these files without overwriting different existing files. It does not change branch, commit or push.

```bash
python3 ~/aia_17ab_setup.py --repo "$HOME/solar_flare_aia" --run
```

Without `--run`, it only installs files and runs local synthetic tests. Once installed, the audit can also be invoked directly:

```bash
python3 ~/solar_flare_aia/scripts/run17_metadata.py --repo "$HOME/solar_flare_aia"
```

Python 3.9+ standard library, SQLite with window-function support and an authenticated `gcloud` command are required for the cloud run. No pip packages, GPUs or VM creation are required. Five exact CSVs are staged; the twelve-minute SHARP table, AIA NPZ archive and model checkpoints are excluded. Source payload cap: 450 MiB; additional disk reserve: 1 GiB. **These are byte guards, not a guarantee of zero cost or a monetary cap.**

## Outputs and interpretation

Outputs default to `~/aia17_metadata_stage1/runs/<UTC timestamp>/`. `source_lock.json` pins the source versions and cache checksums. `latest_report_path.txt` identifies the most recent completed run. A cache source is reused only when it matches recorded checksums. If files were changed or a download was interrupted, the code stops rather than overwriting or silently repairing them.

`STAGE1_COMPLETE_REVIEW_REQUIRED` is a program-completion state, not a scientific green light. Read `stage1_summary.md`, `stage1_report.json`, `source_year_counts.csv`, `feature_availability.csv`, `duplicate_audit.csv`, `identity_comparisons.csv` and `findings.csv`. Raw files, the SQLite audit database and local paths remain outside the repository; review small reports before committing.

The audit does not reconstruct/relabel targets, merge the extension into the master, impute values, infer UTC from naive times, generate GOES features, or train. It compares only IDs unique within each source, and reports duplicate/ambiguous IDs separately. Timestamp representations are inspected but TAI-to-UTC conversion is deliberately deferred until lineage is known. Exact object listing and checkpoint loadability remain later work.

## Source-derived decisions versus new proposals

Existing contracts: six channels, 96-minute AIA source cadence, same-AR 48-hour target, official manifest labels, train-only preprocessing, validation-only thresholds; completed 16B is Cycle 24 only; PINN/PIML remains separate. Current schema and object names come from the user's probe. The proposed 2010–2017 / 2018–2019 / 2021–2025 split is a **new unfrozen allocation** within the alternatives in the committed plan; it is not represented as a prior approved split.

The earlier plan's routine billing-disablement advice is explicitly superseded in the new protocol, not silently retained. This package has no API calls that change billing or cloud resources.

## Technical documentation checked

- Google Cloud CLI `gcloud storage cp` reference: https://docs.cloud.google.com/sdk/gcloud/reference/storage/cp
- Google Cloud Storage checksum guidance: https://docs.cloud.google.com/storage/docs/working-with-big-data
- Cloud Shell file transfers: https://docs.cloud.google.com/shell/docs/uploading-and-downloading-files
- Cloud Shell storage constraints: https://docs.cloud.google.com/shell/docs/quotas-limits

## Project records checked

Repository `Watchman77/solar-flare-aia-training`: Issue #1; `docs/final_bigbang_cycle24_to_cycle25_execution_plan_2026-09-08.md`; `results/metrics/aia_sharp_goes_fusion_protocol.md`; completed 16B report; separate PINN/PIML track documents. A missing preferred `TOTUSJH` column was already reported in the August alignment protocol.

## Verification boundary

The supplied software is tested using synthetic fixtures. That is not execution against the user's private bucket. The user's Cloud Shell run must supply the real audit outputs. Neither a successful header probe nor existence of three .pt objects is a tensor-integrity or checkpoint-loadability certificate.

## UQ/calibration protocol update — 14 September 2026

Version 2 adds the standing research checklist, a solar-specific UQ/calibration evaluation protocol, a separate JSON configuration and guidance cells in 17A/17B. It does **not** alter stage-1 audit computation or download sources. No UQ algorithms or new scientific results are claimed.

Use `aia_17ab_setup_uq.py` in place of the original installer for installation or an exact-v1 upgrade. The installer backs up recognized original package files before replacing them and refuses unknown modifications. It does not commit/push or access cloud services unless `--run` is explicitly supplied. Do not supply `--run` merely to update the protocol, and let any active audit/notebook session finish before upgrading. A modified or executed notebook will be preserved and flagged as a conflict rather than silently overwritten.

```bash
python3 ~/aia_17ab_setup_uq.py --repo "$HOME/solar_flare_aia"
```

Directly run the existing `scripts/run17_metadata.py` entry point later when a new metadata audit is actually needed. Large local audit outputs are outside the repository and untouched by the update.
