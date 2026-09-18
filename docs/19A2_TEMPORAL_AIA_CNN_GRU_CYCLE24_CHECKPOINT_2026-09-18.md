# 19A2 Temporal AIA CNN-GRU Cycle-24 Checkpoint

Date: 2026-09-18

## Scientific contract

The temporal AIA baseline uses three six-channel AIA frames at:
- t-288 min
- t-192 min
- t-96 min

Forecast target: same-active-region M/X occurrence in (t, t+48 h].

The authoritative target is `label_48h_final`.
Embedded NPZ `y` values are not used.

## Model

Shared CNN spatial encoder followed by a GRU temporal encoder.

Input AIA channel order:
`aia94, aia131, aia171, aia193, aia211, aia335`

Training resolution: 256 x 256.

## Development

Model development used Cycle-24 only.

Six internal development epochs were completed.
The pre-specified model-selection criterion was validation PR-AUC.

Selected epoch:
- epoch 2
- ROC-AUC: 0.8287144734
- PR-AUC: 0.0369599540
- Brier: 0.1443672924
- log loss: 0.4209085966

The decline after epoch 2 supported early model selection rather than continued fitting.

## Final refit

The architecture was reinitialized and refit on the complete
`cycle24_final_refit_pool` for the frozen two-epoch duration.

Final refit training loss:
- epoch 1: 1.2001781048
- epoch 2: 1.1075681454

## Leakage firewall

During 19A2:
- Cycle-25 was not used.
- Calibration holdout was not used.
- Threshold holdout was not used.
- Model calibration was not fitted.
- Operating threshold was not selected.

The next stage is 19A3, which fits calibration and selects the operating
threshold on their dedicated Cycle-24 holdouts before any independent
Cycle-25 evaluation.

## Model hashes

Final Cycle-24 model SHA256:
`11dc35e089101c8b79d2a6ba6f82d02cdb470d583552cad73e6071016c2a2d76`

Internal-best development model SHA256:
`fcd9f8f743f739228ba8c6a6c2193fa4cc34a16eef61574d9199e409862c8ea3`

Model weights are stored outside Git and are not committed to this repository.
