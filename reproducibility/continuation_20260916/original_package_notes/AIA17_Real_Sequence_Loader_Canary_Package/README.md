# 17C real-sequence engineering canary

Run ONLY the new driver after uploading it to the existing Cloud Shell home directory:

```bash
"$HOME/aia17_time_venv/bin/python" "$HOME/aia17_real_sequence_canary.py"
```

No extra arguments or package installation are needed. NumPy, Astropy and h5py must already be installed in that environment, as in the completed source-resolution run.

## Scope

Four deterministic target sequences: train negative, train positive, model_validation negative, model_validation positive. Four different HARP/NOAA connected components are required. No training, calibration, threshold-selection, test evaluation, date modification or test-set image loading occurs.

Each sequence uses nominal TAI slots t-288, t-192, t-96 minutes in oldest-to-newest order. The label is the ORIGINAL FORECAST TARGET's designated manifest label, never the embedded label or label of a historical frame.

Reads the full local assignment sidecar and temporal index using their recorded hashes. This is a streaming lookup, not reconstruction of either artifact. Retrieves checksum-pinned metadata from existing local inventory listings; no new bucket listing.

Downloads at most twelve historical NPZ files, up to 16 MiB each, 128 MiB total planned payload. Successful exact-generation cached downloads are reused. Native Google CLI child commands use the previously verified account/project explicitly without altering persistent configuration. There is no automatic login flow; authentication errors stop and retain caches.

Reads original per-channel attributes at the exact SuryaBench S3 source path preserved inside each historical NPZ. Reuses the existing consolidated reader and metadata cache. No full NetCDF file or NetCDF pixel array is loaded. The previous reader bounds returned range bytes to 2 MiB/source, 96 requests/source, and a per-source time cap. Network operations remain chargeable under provider terms; caps are not money or total retry-traffic guarantees.

## Important engineering/scientific distinction

Produces actual finite float32 tensors, nominal identities and recorded-header timing screens. AIA original meta_0 is used; processed meta_1 EXPTIME is never substituted. Where the original AIA FITS header has no TIMESYS, the documented FITS default UTC is recorded explicitly, not applied to arbitrary project timestamps.

A mean exposure end estimate is NOT a verified upper bound on the latest contributing data, and is NOT the historical time of product publication. The new driver does not set `end_bound_verified=True` or weaken the existing strict loader. It is a separately named engineering loader; no model training interface is invoked. The final report intentionally leaves `strict_contributing_time_clearance=False`, `historical_product_availability_verified=False`, `label_validity_and_followup_certified=False`, and `training_authorised=False`.

If a recorded midpoint or nominal record is outside the 180-second HISTORICAL-slot tolerance, or the estimated mean end lies after FORECAST issue, or original headers are missing/inconsistent, it stops with an explicit failed report. It does not silently replace the candidate with a convenient example. In particular, a nominal lag is not accepted as source evidence.

The runtime source identity is tied by the NPZ's stored source path and version-pinned GCS bytes plus S3 range ETags. This is not a pixelwise reproduction of historical preprocessing or proof that the public source never changed since extraction.

## Dependencies already present in the user's home directory

- aia17_npz_timing_canary.py
- aia17_npz_timing_canary_gcloud.py
- aia17_consolidated_resolution.py
- aia17_build_temporal_manifest.py
- solar_flare_aia/scripts/aia17_time_label_impact.py

Their known hashes are checked before network access. Do not overwrite or rerun those scripts. Copies under dependencies/ in this package are for tests and reproducibility, not a request to reinstall them.

## Outputs

A new dated folder under ~/aia17_metadata_stage1/real_sequence_canary_v1/reports/ contains:

- canary_plan.json (exact target records, proposal identity and input hashes)
- twelve or fewer historical-frame reports with source evidence and checksums
- real_sequence_canary_report.json
- engineering_batch.npy (about 72 MiB, shape 4,3,6,512,512)
- manifest_targets.npy (0,1,0,1 in this selection order)
- research_log_real_sequence_canary.md
- COMPLETE.json
- real_sequence_canary_summary.zip (small JSON/Markdown evidence, NOT images/batch)

The data arrays remain outside Git and should not be uploaded to the chat. Attach only the summary ZIP after a successful run. If an error occurs, keep its message. Verified downloads remain cached. The driver never deletes source data or credentials. It writes a local advisory lock released automatically on process exit and its own new outputs.

## Tests performed here

20 local tests passed. The integrated test writes and loads twelve REAL synthetic NPZ arrays, assembles a 4x3x6x512x512 batch, confirms manifest labels despite intentionally different embedded labels, and checks cache reuse. Another test uses a real in-memory HDF5 file and the existing original-attribute reader. Download transport and astronomical conversion are simulated/reference fixtures; no live GCS or S3 calls were tested and Astropy could not be installed in this runtime. The existing project's Astropy self-checks must pass in Cloud Shell before the run begins.

Run packaged tests (does not contact the network):

```bash
python -m unittest discover -s . -p 'test_aia17_real_sequence.py' -v
```

## Software references

- https://numpy.org/doc/2.2/reference/generated/numpy.load.html
- https://docs.h5py.org/en/3.14.0/high/file.html
- https://docs.astropy.org/en/stable/time/index.html
- https://docs.sunpy.org/en/stable/generated/api/sunpy.map.sources.AIAMap.html
- https://fits.gsfc.nasa.gov/standard40/fits_standard40aa-le.pdf (FITS time-scale default)
- https://docs.cloud.google.com/sdk/gcloud/reference/storage/cp

These explain APIs and conventions. They do not certify this research dataset.
