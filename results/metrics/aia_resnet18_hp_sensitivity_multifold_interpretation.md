# Interpretation: ResNet18 Hyperparameter Sensitivity

This sensitivity study tested a small predefined set of physics-safe ResNet18 configurations across the usable chronological folds. Hyperparameter selection was based only on **mean validation TSS across folds**; test metrics were reported after selection and were not used to choose the configuration.

The validation-selected configuration was **higher_dropout**, with mean validation TSS=0.2403 ± 0.0219. Its official test performance was mean TSS=0.1819 ± 0.1409, mean Recall=0.5340 ± 0.2902, and mean ROC-AUC=0.6311 ± 0.0313.

The existing baseline achieved mean validation TSS=0.2315 and mean official test TSS=0.2339. The results should be interpreted as a controlled sensitivity analysis rather than an open-ended search. If no configuration substantially stabilises the weak 2014 fold, this supports the conclusion that image-only AIA snapshots are sensitive to chronological/solar-cycle regime shift and motivates the next multimodal stage using AIA imagery plus SHARP magnetic temporal features.
