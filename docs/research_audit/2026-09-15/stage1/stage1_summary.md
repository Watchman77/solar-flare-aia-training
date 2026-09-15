# 17B stage 1 — metadata content audit

Status: STAGE1_COMPLETE_REVIEW_REQUIRED

**No training is authorised by this report. No labels or source files were repaired.**

## Source rows (not verified image sample counts)

| Source | Rows | Official label column |
|---|---:|---|
| baseline_manifest | 68,010 | True |
| curated_master | 141,644 | True |
| extension | 17,975 | True |
| sharp96 | 663,265 | False |
| events | 2,185 | False |

## Overlap and identity checks

### extension versus curated_master

```json
{
  "left_source": "extension",
  "right_source": "curated_master",
  "comparison_scope": "IDs unique within each table only; no duplicate resolution or label repair",
  "left_unique_id_rows": 17975,
  "right_unique_id_rows": 141644,
  "matched_ids": 17975,
  "left_without_unambiguous_right_match": 0,
  "label_mismatches": 0,
  "label_unknown_comparisons": 0,
  "harp_mismatches": 0,
  "harp_unknown_comparisons": 0,
  "noaa_mismatches": 0,
  "noaa_unknown_comparisons": 0,
  "t_mismatches": 0,
  "t_unknown_comparisons": 0,
  "timestamp_note": "Comparison is representation-level only; timescale provenance remains unresolved."
}
```

### baseline_manifest versus curated_master

```json
{
  "left_source": "baseline_manifest",
  "right_source": "curated_master",
  "comparison_scope": "IDs unique within each table only; no duplicate resolution or label repair",
  "left_unique_id_rows": 68010,
  "right_unique_id_rows": 141644,
  "matched_ids": 68010,
  "left_without_unambiguous_right_match": 0,
  "label_mismatches": 0,
  "label_unknown_comparisons": 0,
  "harp_mismatches": 0,
  "harp_unknown_comparisons": 0,
  "noaa_mismatches": 0,
  "noaa_unknown_comparisons": 0,
  "t_mismatches": 0,
  "t_unknown_comparisons": 0,
  "timestamp_note": "Comparison is representation-level only; timescale provenance remains unresolved."
}
```

## Event families actually observed

{"M": 2050, "X": 135}

A zero C-class count does not establish a C-quiet period. Catalogue completeness is unverified.
Peak class/peak flux cannot be treated as known before the peak; end information cannot be used before the end. Reporting delays remain unresolved.

## Findings

1 nonzero issues require review. See findings.csv.

## Remaining gates

- Cross-cycle AIA object/manifest reconciliation and actual image timestamps not yet audited.
- TAI/UTC provenance and availability-time conversion must be established before cross-instrument joins.
- Exact date splits, forecast-window purge and AR-group overlap policy are not frozen.
- Qualified SHARP/AIA 6h/12h/24h history coverage and missingness policy remain to be audited.
- GOES catalogue completeness, units, reporting delay and feature availability have not been verified.
- 2025-2026 extension comparison does not authorise automatic concatenation or source-label repair.
- Source-label lineage and complete 48h follow-up coverage (right-censoring) remain to be verified.
- HMI magnetic-image coverage and checkpoint loadability have not been tested.

## Diagnostic limits

Naive timestamps remain naive. No TAI-to-UTC conversion was performed. Annual summaries use the year in the parsed source representation. This stage deliberately does not produce model tensors, imputed features, trained models, or test metrics.
