# Solar Flare AIA Training Run Protocol

Every training run must be reproducible.

## Before training

Record:

- date and time
- VM name
- GPU type
- Git commit hash
- Python environment
- dataset manifest path
- label column
- split definition
- model name
- image size
- batch size
- learning rate
- epochs
- random seed
- class balancing or weighting strategy

## During training

Save:

- terminal log
- per-epoch metrics
- validation threshold
- confusion matrix
- model checkpoint

## After training

Save:

- final metrics JSON
- predictions CSV
- plots
- short interpretation note
- known limitations

## Required metrics

At minimum:

- Accuracy
- Precision
- Recall
- F1
- Specificity
- TSS
- HSS where applicable
- ROC-AUC
- PR-AUC
- Brier score where applicable
- Confusion matrix

## Research rule

Do not treat any result as final unless the corresponding config, code version, metrics and log are saved.
