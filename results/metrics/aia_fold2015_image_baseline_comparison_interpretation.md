# Interpretation: Fold-2015 Image-Only Baselines

The fold-2015 image-only experiments show a clear progression from capped AlexNet engineering baselines toward a more scientifically defensible full-natural benchmark.

The strongest official TSS in this comparison is from **09 ResNet18 physics-safe full-natural**, with **TSS=0.4534**, **Recall=0.8682**, **Specificity=0.5852**, and **ROC-AUC=0.7477**.

The full-natural ResNet18 run used **38329 training samples**, **11627 validation samples**, and **11236 test samples**, with **531 positives** and **10705 negatives** in the 2015 test set. At the validation-selected threshold of **0.2050**, it achieved **TSS=0.4534**, **HSS=0.0923**, **Recall=0.8682**, and **Precision=0.0941**.

The low precision should be interpreted in the context of severe natural class imbalance. The result indicates high event sensitivity but many false alarms, which is a known operational trade-off in rare-event space-weather forecasting. Importantly, the threshold was selected on validation data and then applied unchanged to the test set.

Overall, AlexNet-style models are retained as useful baselines and pipeline validation experiments, but the physics-safe full-natural ResNet18 result is the current strongest image-only benchmark for fold-2015.
