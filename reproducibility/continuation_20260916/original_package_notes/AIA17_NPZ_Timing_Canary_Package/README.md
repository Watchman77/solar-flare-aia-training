# 17B small NPZ content / timing-evidence canary

## Current input checkpoint

The uploaded 16 September 2026 archive log completed all 17 yearly listings:
137,714 exact nonempty matches out of 141,644 locked targets; 3,930 not found in
the audited prefixes. The result is an object inventory, not validation of image
contents, full catalogue coverage or temporal causality. The boundary-case object
is an exact nonempty match. Eighteen deterministic canary candidates were saved.

The next script uses that saved candidate list without reselection. It also profiles
availability by stored year and original label from the saved target register. It
prints an explicit baseline-subset object-status count rather than deducing identity
completeness merely from equal totals.

## Run in the user's existing Cloud Shell

Upload `aia17_npz_timing_canary.py` into the home directory, then use:

```bash
"$HOME/aia17_time_venv/bin/python" "$HOME/aia17_npz_timing_canary.py"
```

No new flags or package installation are required. The existing environment should
have NumPy 2.2.6 and Astropy 7.1.0. The script imports the checksum-verified existing
`scripts/aia17_time_label_impact.py` helper from `~/solar_flare_aia`, runs its
historical time-conversion self-tests, and disables automatic IERS downloads there.
The script assumes the known archive report at:

```
~/aia17_metadata_stage1/archive_reconciliation_v1/reports/20260916T073559880010Z/
```

Use `--help` for alternative local paths. Output/cache cannot be inside the Git repo.

## Cloud and resource scope

This is a read-only **download** step, unlike the previous metadata-only listing.
It requests at most 18 NPZs at the object generations already recorded in the
inventory. The total planned NPZ payload must be at most 128 MiB, with at most
16 MiB per object and a 1 GiB free-disk reserve. These limits are not monetary caps.
Cloud Storage operations, retrieval, and transfer charges can apply.

There is one GET attempt per uncached object per invocation; a network error stops
the run, and successfully verified cache entries can be reused. Repeated invocations
can retransfer a failed partial download. The script does not silently request a
newer generation, retry an arbitrary URL, or relist a bucket. The endpoint is fixed
to Google Cloud Storage, and HTTP redirects are rejected. The existing `gcloud`
login is used; credentials are not requested from the user, printed, or stored in
reports. Authentication does not grant any new IAM permissions.

No cloud writes, billing changes, VM/GPU operations, package installations, Git
operations, catalogue repair, relabeling, model loading, or training are performed.

## Checks and interpretation

* Verify source-report/candidate-list/listing/source-file checksums and identities.
* Verify downloaded size, listed CRC32C/MD5, then record a local SHA256 receipt.
* Reject unsafe ZIP member names, excessive sizes, unsupported header versions,
  duplicate member names, forged array allocations and object/pickle arrays.
* Inspect tensor shape `(512,512,6)`, float dtype, finite pixels, per-channel
  summary statistics, IDs, timestamp metadata, and channel declarations/order.
* Compare embedded labels only as historical metadata; never substitute them for
  `label_48h_final`.
* Distinguish a shared `used_timestamp` from per-channel `channel_metadata`.
* Compare naive image-time fields separately under UTC and TAI hypotheses. Report
  signed frame-minus-issue differences and BOTH the 180-second tolerance and
  at-or-before-issue rules. Do not adopt an unproven scale convention.
* Treat a source filename's explicit Z stamp as filename evidence, not a verified
  original observation header. Storage creation/update time is not frame time.

Even all 18 content checks passing does not certify every archive image. This is a
small deterministic format/timing probe, not a representative prevalence estimate.
Per-channel source observation headers and availability remain unverified by this
canary alone. Signed positive deltas under a hypothesis are conditional findings,
not automatically archive-wide leakage. Missing objects are not negative labels.

## Outputs

```
~/aia17_metadata_stage1/npz_timing_canary_v1/
    input_contract.json
    objects/                         # checksum-verified NPZ cache and receipts
    reports/<timestamp>/
        <sample_id>.json             # each file's results and raw metadata
        npz_canary_report.json
        object_availability_by_year_and_original_label.csv
        research_log_npz_canary.md
        COMPLETE.json
```

The complete banner is `NPZ_CANARY_COMPLETE_REVIEW_REQUIRED_NO_TRAINING`.
It means all selected objects were processed, not that every one passed: consult
`content_status_counts` and the individual records. Content/read defects remain
explicit. A failed download instead produces a stopped run, with no completion claim.

## Local testing

`python -m unittest -v test_aia17_npz_timing_canary.py` passed **22 tests** in the
creation environment. These use synthetic NPZ data, a fixed-offset fake clock and
simulated downloads. They include a full 18-file workflow, repeat-run cache reuse,
checksum/tamper rejection, shape/channel/nonfinite checks, pickle and allocation
rejection, scale ambiguity, exact timing inequalities and redirect rejection.

The creation environment did not have Astropy installed, so the real Astropy
backend and live Google Cloud downloads were **not** run here. The user's existing
clock helper is checksum-verified and its self-tests must pass before cloud reads.
The helper's actual historical/leap-second tests already passed in the user's
preceding Cloud Shell run; this is not a new local claim of executing that backend.

## Primary documentation

* https://docs.cloud.google.com/storage/docs/json_api/v1/objects/get
* https://docs.cloud.google.com/storage/pricing
* https://numpy.org/doc/2.2/reference/generated/numpy.load.html
* https://docs.astropy.org/en/stable/time/

Research scope and prior task labels are unchanged. The separate PINN/PIML and
UQ/calibration requirements remain separate from completing this image audit.
