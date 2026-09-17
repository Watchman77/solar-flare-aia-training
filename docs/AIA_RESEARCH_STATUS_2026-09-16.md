# Research status — 16 September 2026

This is a dated source-grounded continuation record, not a training authorisation. The last remote checkpoint read while preparing this package was `a66a9928125a2775b02358df2774a3e5e3f41849`. Later runs below are evidenced by supplied reports and terminal logs; this document does not imply they were already pushed.

| Stage / run | Demonstrated outcome | Not demonstrated |
|---|---|---|
| Boundary review `20260916T065814216457Z` | The July 2024 event is 37 seconds beyond the corrected upper endpoint under the event-UTC hypothesis. | Independent full-catalogue UTC/label certification; no original label replacement. |
| Archive `20260916T073559880010Z` | 137,714 exact nonempty objects for 141,644 targets; 3,930 unmatched in audited prefixes; 68,010 baseline objects present. | Tensor correctness or timing for every object; no deletion cause inferred. |
| NPZ canary `20260916T102919362266Z` | 18 checksum-verified tensors passed content checks. | Archive-wide exposure-time or label clearance. |
| Consolidated sources `20260916T125903405600Z` | 13 manifests/logs and 16 source-attribute records read; the 3 examined legacy labels explained. | 12 production JSOC header queries unresolved; full event coverage unresolved. |
| Temporal index `20260916T143622218859Z` | 141,644 targets retained; 118,217 nominal three-frame histories available; 23,427 incomplete/excluded. | Full-population timing eligibility. |
| Chronological role proposal v1 `20260916T151222233858Z` | Provisional roles and protected groups established for engineering. | Final adoption as main training allocation. |
| Real sequence canary `20260916T172352521004Z` | Four real sequences / twelve unique NPZs, batch `[4,3,6,512,512]`, targets `[0,1,0,1]`; recorded-time screens passed. | Certified strict contributing-time/product-availability bound; full-population validation. |
| CPU model integration `20260916T181303106801Z` | Twelve exact SHARP rows; `[4,3,15]`; ten disposable updates on two training examples; both branches/fusion received gradients. | Forecasting skill, validation fitting, calibration, UQ or test performance. |
| Broader Cycle-24 proposal v2 `20260916T191645934223Z` | 52,155 final-training candidates; 6,253 calibration; 6,317 threshold; 49,329 Cycle-25 test; 2,086 supplementary 2026. | Frozen scientifically eligible final populations. |
| SHARP arrays `20260916T195026327454Z` | `[64,725,3,15]` raw arrays; 70,217 unique requested keys all matched; no duplicate keys or explicit NOAA conflicts. | Source-quality filter, imputation/scaling, final label/timing clearance or scored model training. |

## SHARP completeness, based on the uploaded report

| Role | Candidates | Complete raw numeric / no explicit NOAA conflict | Numeric-incomplete candidates |
|---|---:|---:|---:|
| Final training pool | 52,155 | 52,013 | 142 |
| Calibration | 6,253 | 6,213 | 40 |
| Threshold selection | 6,317 | 6,293 | 24 |
| Total | 64,725 | 64,519 | 206 |

Explicit NOAA conflict counts are zero in all three roles. The report contains missing/unparseable values in several magnetic features; 206 is the number of affected candidate rows, not a count of unique bad source records. The detailed source QUALITY records must still inform the eligibility decision. Test arrays were not constructed. No scientific training, calibration or threshold was fitted by this array build.

## What the next checkpoint is for

Preserve the source code, original small report bytes, original test sources/logs, proposal evolution and large-artifact references in the existing repository. This must not repeat extraction, source requests, audits or engineering updates. Copy rather than remove the current working files, because some script defaults and dependency hashes still refer to the existing home-directory layout.

## Next research action after consolidation

Specify the first scored SHARP development run: applicable quality/identity/missingness policy, input and label eligibility, chronological development folds, train-only preprocessing, baseline settings and VM resource/backup/stop plan. The broader v2 allocation remains the preferred proposal for review; no new split search is requested by this document. Preserve the separate calibration/threshold pools and frozen future test roles.
