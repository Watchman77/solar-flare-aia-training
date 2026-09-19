# 19A4E–19A4E3 Cycle-25 AIA Shift Diagnostic Checkpoint

Date: 2026-09-19

## Scope

Post-test diagnostics following the frozen 19A4 independent Cycle-25
evaluation. No model weights, normalisation parameters, calibrator,
operating threshold, or primary 2021–2025 results were changed.

## 19A4E — Score-distribution shift

The 2025 failure at the frozen operating threshold is accompanied by a
large downward score shift while ranking discrimination remains relatively
preserved.

2024:
- ROC-AUC: 0.737244
- PR-AUC: 0.234446
- positive fraction above frozen threshold: 0.701368
- positive median calibrated probability: 0.038478
- positive median raw logit: 0.777215

2025:
- ROC-AUC: 0.728086
- PR-AUC: 0.108026
- positive fraction above frozen threshold: 0.0078125
- positive median calibrated probability: 0.007163
- positive median raw logit: -2.153109

2024-vs-2025 KS statistics:
- all samples: 0.645481
- positive class: 0.768807
- negative class: 0.652294

Interpretation: ranking information largely survives, but the absolute
score scale changes strongly enough to break transfer of the frozen
operating threshold.

## 19A4E2 — 2024 vs 2025 input/production audit

The production contract changes between 2024 and 2025.

2024 uses the legacy NPZ contract containing:
- channels
- crop_meta
- used_s3_path
- used_timestamp

2025 uses production-v1 containing:
- wavelengths
- block_id
- channel_metadata
- label_48h_final
- source

2025 source lineage:
JSOC HARP-block tracked im_patch + local WCS crop

Input distributions also change in a channel-dependent manner.

AIA 335 is especially notable:
- 2024 raw mean: 0.448803
- 2025 raw mean: 0.379887
- 2024 zero fraction: 0.000629
- 2025 zero fraction: 0.015710
- 2024 transformed mean: 0.495509
- 2025 transformed mean: 0.046491

These results establish a covariate/production-domain change but do not
alone prove its causal contribution to the 2025 model-score shift.

## 19A4E3 — 2025 vs early-2026 verification

2025 and currently available 2026 samples use the same production contract:

- metadata mode: wavelengths
- wavelengths: 94, 131, 171, 193, 211, 335 Å
- source: JSOC HARP-block tracked im_patch + local WCS crop

Both sampled years contain 400 verified objects.

2025-vs-2026 channel KS statistics:
- AIA 94: 0.025891
- AIA 131: 0.046440
- AIA 171: 0.008293
- AIA 193: 0.028594
- AIA 211: 0.038750
- AIA 335: 0.081965

The 2025-to-2026 differences are substantially smaller than the previously
observed 2024-to-2025 production/input transition. AIA 335 shows the
largest continuing drift.

## Current interpretation

The evidence is consistent with 2025 marking a production/domain-regime
boundary. The frozen model retains ranking skill but suffers operating-point
failure under the associated score shift.

Causality is NOT claimed. Solar-regime evolution and production-pipeline
effects remain confounded in the year-wise comparison.

A future matched same-observation experiment is required to isolate the
effect of production methodology.

## 2026 status

Current verified 2026 production data only cover the existing early-2026
archive. The planned April–September 2026 extension remains supplementary
and must not be merged into the frozen 2021–2025 primary test.

## Protocol flags

model_weights_changed: false
normalisation_changed: false
calibrator_refit: false
threshold_reselected: false
cycle25_used_for_tuning: false
primary_2021_2025_result_changed: false
2026_merged_into_primary_test: false
