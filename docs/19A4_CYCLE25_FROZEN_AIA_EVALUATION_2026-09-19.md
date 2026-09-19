# 19A4 Frozen Temporal AIA Cycle-25 Evaluation

Date: 2026-09-19

## Primary independent test

The pre-specified primary Cycle-25 evaluation covers 2021-2025.

- Targets: 49,329
- M/X positives: 2,351
- Prevalence: 0.0476595917

2026 remains a separate supplementary out-of-sample evaluation and is not
included in the primary 2021-2025 score.

## Frozen pipeline

Base-model SHA256:
11dc35e089101c8b79d2a6ba6f82d02cdb470d583552cad73e6071016c2a2d76

Platt coefficient:
0.5846760189574352

Platt intercept:
-3.6728404851652265

Frozen operating threshold:
0.030438695842933242

No model refitting, recalibration or threshold reselection occurred after
Cycle-25 predictions were generated.

## Overall 2021-2025 result

- ROC-AUC: 0.6641056216
- PR-AUC: 0.0905447384
- PR lift over prevalence: 1.8998219475
- Brier: 0.0456647899
- Log loss: 0.2007059248
- TSS: 0.2225234202
- HSS: 0.0642017065
- Precision: 0.0818850038
- Recall: 0.5070182901
- F1: 0.1409983440

Confusion matrix:
- TN: 33,613
- FP: 13,365
- FN: 1,159
- TP: 1,192

## 2025 production-schema finding

All 10,879 staged 2025 objects were verified to contain float32 tensors of
shape 512x512x6 with physical wavelength order:

94, 131, 171, 193, 211, 335 Angstrom.

The 2025 production-v1 objects store this ordering under `wavelengths`,
whereas legacy objects use string-valued `channels`. The inference loader
was made schema-compatible without changing the scientific model contract.

## Test integrity

All five annual prediction shards were generated using the same frozen:
- model weights;
- normalisation;
- Platt calibrator;
- operating threshold.

Metrics were computed only after all 49,329 frozen prediction rows passed
integrity checks.

The 2025 performance behavior is retained exactly as observed and is not
used to alter the frozen pipeline.

Scientific clearance remains false because inherited historical-source and
label-clearance limitations still apply.
