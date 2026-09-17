# 17C real-sequence engineering canary

Four three-frame sequences from train/model_validation only. No independent-test image is selected.
The role proposal is reused unchanged; this run neither freezes scientific readiness nor fits a model.

Batch shape: [4, 3, 6, 512, 512]; dtype: float32.
Target labels: designated target manifest, never historical NPZ y.
Source-time screening uses retained original AIA FITS meta_0; original mean exposure duration is used.
**Mean-exposure end estimates are NOT certified latest-contributing-time bounds.**
Strict contributing-time, product availability, SHARP, label lineage/follow-up and final readiness remain separate gates.
Existing strict selection/loader functions are unmodified. No experimental results are generated here.

The engineering_batch.npy is local debugging data, not an approved training release.
