# 17C: real AIA–SHARP model integration (engineering only)

## Basis and scope
The supplied real_sequence_canary_summary.zip was read, not replaced with the older 18-file report.
Its 15 included hashed artifacts match COMPLETE.json. The original engineering_batch.npy and
manifest_targets.npy are referenced but were NOT uploaded here. Their bytes will be verified on
Cloud Shell, against that original receipt, before model integration.

The 72 channel timing entries agree with recomputed datetime differences. The latest of the
selected historical exposures ends an estimated 5,747.655812 seconds (95 minutes 47.656 seconds)
before its target issue time. This is the original mean-exposure estimate, NOT a certified latest
contributor bound or historical data-availability certificate. Those flags remain unchanged.

## New executable step
Upload aia17_model_integration.py into your Cloud Shell home directory. Use the existing
`aia17_time_venv` environment. Install the pinned CPU PyTorch build and then run:

```bash
"$HOME/aia17_time_venv/bin/python" -m pip install --no-cache-dir --only-binary=:all: \
  "torch==2.10.0+cpu" --index-url https://download.pytorch.org/whl/cpu \
&& "$HOME/aia17_time_venv/bin/python" -m pip check \
&& "$HOME/aia17_time_venv/bin/python" -u "$HOME/aia17_model_integration.py"
```

Installation downloads software, not research data. Do not install CUDA/torchvision/torchaudio
for this script. PyTorch provides CPU wheels including Python 3.12/Linux x86_64 for this pin.
The runtime itself has no network, cloud, Git, image-download or source-repair operations.

The default inputs are the real sequence run 20260916T172352521004Z and the published local
Stage-1 source_lock_snapshot.json. It verifies the saved image batch and labels and the cached
SHARP96 CSV against recorded hashes. It scans the cached CSV once to find exactly twelve
HARPNUM/T_REC (explicit TAI) keys matching the image-history slots. It never substitutes a
nearby magnetic record, target-time magnetic row, historical NPZ label or absent TOTUSJH.

Inputs assembled: image (4,3,6,512,512), SHARP (4,3,15), target (4,).
This is a THREE-RECORD SHARP interface check, not the final 24-hour magnetic feature design.
QUALITY and NOAA association fields are retained for review; no new science quality policy is
silently applied. Magnetic temporal-contribution and product-availability bounds remain unverified.

## The computational experiment is explicitly a software test
A compact shared CNN + AIA LSTM and a SHARP LSTM feed a fusion MLP. Images are resized to 64x64
for this bounded CPU test without changing the source images. Magnetic imputation/scaling use
only the two designated training targets (six historical rows). Ten disposable AdamW updates use
those two targets only. Model-validation images are forward-only and their labels enter no loss
or model selection. No independent-cycle or supplementary targets are loaded.

The script checks finite logits/losses, finite nonzero branch gradients and parameter updates.
It does NOT estimate forecasting skill, produce TSS/AUC, fit a calibrator, estimate UQ, select a
model or save research-model weights. Debug scalers are labelled DEBUG_ONLY and must not be used
for the full study. Weight changes occur in this test: do not describe it as 'no fitting at all'.
They are not a trained cross-cycle research model.

## Main study and scope decisions remain distinct
The 2010–2013 + split-2014 + 2015 roles were a provisional first benchmark and selection mechanism
for the four-example canary. They are NOT locked as the final main-paper fitting allocation.
The proposed broader eligible Cycle-24 fit including later years such as 2015–2017, with separate
region-safe development/calibration/threshold subsets, has not been implemented by this file.
2021–2025 remains the primary independent test proposal. Eligible available 2026 records remain
additional held-out evaluation. Reusing a calibrator or threshold across differently fitted final
models is not authorised. PINN/PIML remains a separate track.

## Outputs
New timestamped directory under ~/aia17_metadata_stage1/model_integration_v1/reports/:
model_integration_report.json, model_integration_summary.zip, source SHARP values for the twelve
matched rows, debug-scaled SHARP and debug scaler, and a research-log note. No AIA tensor is copied.
Original canary files, original labels, raw magnetic table and Git checkout are not changed.

## Verification performed here
20 unittest tests passed under Python 3.13, PyTorch 2.10.0+cpu, NumPy 2.3.5. They exercise a
full-shape synthetic image batch, synthetic SHARP rows and the ACTUAL supplied metadata schema,
with the socket connection disabled during the full workflow. They verify exact joins, missing/
duplicate handling, no validator-label influence on gradients, train-only preprocessing, full
forward/backward behavior and input preservation. The supplied live image batch and real SHARP
values were not available here. The user's environment is Python 3.12 with NumPy 2.2.6; that exact
environment combination has not been executed here. Tests do not certify solar labels/timing.

Run tests in a development checkout with numpy/torch installed:
`python -m unittest discover -s tests -v`

Sources (software only):
- https://download.pytorch.org/whl/cpu/torch/
- https://docs.pytorch.org/get-started/previous-versions/
