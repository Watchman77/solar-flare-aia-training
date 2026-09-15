# 17B event/time forensic review

Source run: `20260915T005020436079Z`

This review reads frozen local audit artifacts. It does not change sources, labels, sample IDs, paths or splits.

Duplicate audit-key groups: 1.
Duplicate excess records: 1.
Records with time flags: 2.
Distinct flagged records: 4.

Audit key: NOAA_AR_clean, event_starttime, event_peaktime and uppercased fl_goescls. End time and flux are not in this key.
An identical audit key is not proof of an identical physical event. Compare all exported fields and original catalogue entries.

## Clock evidence

- curated_master: 141,644 pairs; {"same_clock_fields_as_raw_TAI": 141644}.
- extension: 17,975 pairs; {"same_clock_fields_as_raw_TAI": 17975}.
- sharp96: 663,265 pairs; {"same_clock_fields_as_raw_TAI": 663265}.

Clock-field equality with a _TAI source is evidence of retained TAI clock fields, not a UTC conversion.
The baseline's matched sample IDs can provide raw-time lineage, but originals must remain unchanged.

## Research boundaries

No development split is frozen. Earlier zero-positive candidate years remain unsuitable for validation-TSS selection under current labels.
The catalogue's latest event is not proof of continuous coverage or full forecast follow-up.
UQ, calibration, AR-group bootstrap and significance requirements remain in force; PINN/PIML stays separate.

## Outstanding decisions

- Event catalogue provenance, completeness, source versions, units and availability delay.
- Expert/source review of flagged event rows; no automatic deduplication or timestamp sorting.
- Physical TAI/UTC conversion and label-window impact, before training.
- AIA observed timestamps versus forecast issue time and 180-second matching rule.
- Qualified history coverage, non-overlapping AR-safe development split with positive support.
- 48-hour follow-up completeness and matched populations for calibration/UQ evaluation.
