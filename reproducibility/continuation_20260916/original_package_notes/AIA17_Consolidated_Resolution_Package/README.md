# 17B consolidated evidence batch

This is a finite source-evidence collection, NOT a global approval, a repair, or a new extraction pipeline.
It brings the original manifests, the completed canary, per-channel source attributes, and base-series JSOC
metadata together in one report. It preserves existing metadata, labels, tensors, and Git state.

## Run in the existing Cloud Shell

Upload `aia17_consolidated_resolution.py` to your home directory. In the existing terminal run:

```bash
"$HOME/aia17_time_venv/bin/python" -m pip install --no-cache-dir --only-binary=:all: \
  "numpy==2.2.6" "astropy==7.1.0" "h5py==3.14.0" \
&& "$HOME/aia17_time_venv/bin/python" -m pip check \
&& "$HOME/aia17_time_venv/bin/python" -u "$HOME/aia17_consolidated_resolution.py"
```

The install keeps the established NumPy and Astropy pins and adds h5py. It uses internet for packages.
The script performs metadata/source reads by default; no extra run/fetch flag is needed.
`--local-only` is available for debugging but does not fetch or clear missing source evidence.
Do not use `--local-only` for the intended combined source collection.

## Existing inputs

- Checkpoint source lock: `~/solar_flare_aia/docs/research_audit/2026-09-15/stage1/source_lock_snapshot.json`.
- Its recorded master and baseline CSVs, already present in the Stage 1 cache.
- Canary report: `~/aia17_metadata_stage1/npz_timing_canary_v1/reports/20260916T102919362266Z/npz_canary_report.json`.
- Existing availability CSV in that same report directory (included when present).
- The saved 16B source/executed notebooks, when present in the local sparse checkout. They are read, never executed.

## External reads

1. Thirteen precisely named original manifest/log CSVs for 2013, 2014, 2015 and 2024.
   These are fetched from the user's GCS bucket with their object generations fixed and verified.
   No recursive listing is performed. Maximum 20 MiB per CSV, 96 MiB combined selected CSV size.
2. Attributes from the sixteen exact SuryaBench `.nc` paths recorded in the canary.
   Read-only h5py file access uses 32 KiB HTTP ranges, capped at 2 MiB per source and 96 requests per source.
   No pixel datasets are indexed or loaded. Ranges may include incidental adjacent bytes.
   If the server ignores Range, the script refuses a full object download.
   Ranges are held to a strong ETag; it is an identity validator, not a cryptographic content checksum.
   A source path + current ETag does not prove that the object is unchanged since the historical extraction.
3. Twelve JSOC `rs_list` base-series queries, one per channel for the 2025 and 2026 candidates.
   Each response is capped at 1 MiB. No export job or FITS download is submitted.
   The query endpoint is HTTPS; connection/endpoint failures are reported, not silently downgraded to HTTP.
   Returned T_REC/wavelength are checked against the recorded filename before a match is reported.
   A matching base record is not a recovered original processed FITS header.

The batch has a 20-minute external-read time budget. A source can remain unresolved when a request fails,
a size cap is reached, the timing scale is absent, or an identity is ambiguous. The batch continues to record
other evidence rather than declaring a failed read to be an empty or safe dataset. Local scans and final packaging
can extend elapsed runtime a little beyond the external-read budget. Successful source caches are retained.

Google credentials stay in the existing CLI configuration. No credential export or service-account key is used.
No authentication is performed automatically. A credential error is recorded without assuming a billing or IAM failure.
GCS request/transfer charges and package downloads can apply; byte limits are NOT monetary caps.

## Output

`~/aia17_metadata_stage1/consolidated_resolution_v1/reports/<timestamp>/resolution_evidence.zip`

Send this single ZIP for review. It contains:
- `resolution_report.json`: all matched manifest/log rows, exact label comparisons, source-time attributes,
  JSOC metadata, errors, and evidence hashes.
- `resolution_summary.md`: short disposition summary.
- Existing availability-by-label CSV, when locally present.
- `artifact_hashes.json`: checksums for the report files.

Raw downloaded CSVs and range caches remain outside the repository. The report has absolute local paths as provenance.
It does not modify or commit Git files, start training, relabel data, approve arbitrary time scales, or relax tolerance.
It does not independently certify event catalogue coverage or the complete archive's observation times.

## Interpreting a legacy-label result

`LEGACY_GLOBAL_LABEL_MATCH_CONFIRMED_FOR_THIS_SAMPLE` requires the embedded NPZ label to match
`label_48h_global_old`, the recorded final label to match the canary's official label, and a non-ambiguous source record.
Any conflicting final label or duplicate matching source group prevents this closure status.
A correct legacy-label explanation does not independently certify the final catalogue labels.

## Timing interpretation

Only strings with explicit UTC/TAI scales (or an explicit TIMESYS) are converted. Nominal file keys are not silently
promoted to exposure times. Each field retains its original name and value. T_REC, T_OBS and DATE-OBS are NOT silently
substituted for one another. Exposure-end and product-availability semantics still need review before a causal claim.
No sample or full-archive clearance is produced automatically.

## Tests performed here

See `TEST_RESULTS.txt`. Unit tests cover exact legacy-label logic, duplicate/conflict handling, cached-source integrity,
HTTP Range/ETag/size handling, real synthetic HDF5 attribute access without allocated pixel chunks, read-only notebook
scans, and source-budget exhaustion. They run with local mocked HTTP/GCS responses, not the user's live sources.
The local runtime has h5py 3.15.1 and NumPy 2.3.5, not the target pins, and does not have Astropy installed.
Therefore the live source requests and the new script's Astropy path have NOT been executed here. The target environment
runs an explicit known-offset anchor before any external read. The existing user's full conversion self-tests already
passed in their recorded environment; that is separate from these new code tests.

## Primary implementation references

- h5py file-like access: https://docs.h5py.org/en/3.15.0/high/file.html
- h5py 3.14.0 release/wheels: https://pypi.org/project/h5py/3.14.0/
- GCS native copy: https://docs.cloud.google.com/sdk/gcloud/reference/storage/cp
- DRMS CGI configuration: https://github.com/sunpy/drms/blob/main/drms/config.py
- SuryaBench upstream attribute writer identified in the conversation:
  `NASA-IMPACT/SuryaBench/core_sdo/core_sdo_mlready_processing_multi.py`, at commit
  `ce8b841bb999a7a917bcc004cd17a57ca2109b81`.
