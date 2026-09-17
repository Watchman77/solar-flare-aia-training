# Temporal candidate index — implementation checkpoint

**Candidate objects indexed; scientific training clearance remains pending.**

Target rows: 141,644. Original labels and source objects unchanged.
Nominal frame slots: t−288, t−192, t−96 minutes; original 48-hour forecast window unchanged.
This is an explicit proposed history-only experiment, not replacement of prior snapshot benchmarks.

## Nominal object support

{
  "NOMINAL_HISTORY_INCOMPLETE_OR_EXCLUDED": 23427,
  "NOMINAL_HISTORY_OBJECTS_AVAILABLE_TIMING_PENDING": 118217
}

## Remaining checks

- Nominal history completeness is not verified exposure-time or product-availability completeness.
- Only samples in the curated table are used as historical frames; other raw source frames may exist.
- The current target image is not required for a history-only sequence; absent history is not a negative label.
- Every target remains in this index, including incomplete histories and the unresolved boundary target.
- The known stale source/target pairing is excluded as a frame, not repaired or deleted.
- The one conditional label disagreement is flagged; labels are not silently replaced.
- Same HARP/NOAA is a conservative identity restriction, not independent region-group certification.
- Full split/purge/calibration design, label follow-up and per-modality contributing times remain separate gates.
- SHARP row time alone is not verification of its contributing observation window or availability.
- AIA/SHARP/GOES final experiment ladder and separate PINN/PIML scope are not changed by this index.
- The local loader is implemented and fixture-tested, not run here against a verified real three-frame sequence.
