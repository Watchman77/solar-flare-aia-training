# Interpretation: ResNet18 Physics-Safe Multi-Fold Full-Natural Benchmark

The multi-fold ResNet18 benchmark evaluates image-only AIA flare forecasting across the usable chronological folds `test_2013`, `test_2014`, and `test_2015`. Each fold uses train-only robust channel normalisation, no spatial augmentation, no embedded NPZ labels, and validation-selected max-TSS thresholding applied unchanged to the test year.

Across folds, ResNet18 achieved mean **TSS=0.2339 ± 0.2227**, mean **Recall=0.6636 ± 0.2501**, and mean **ROC-AUC=0.6348 ± 0.1269**. Precision remains low, with mean precision around **0.0680**, reflecting severe natural class imbalance and the operational preference for high event sensitivity.

These results are more defensible than a single test year because they test year-wise stability under chronological distribution shift. They should be interpreted as a high-recall, false-alarm-heavy image-only benchmark for later comparison against AIA+SHARP fusion models.
