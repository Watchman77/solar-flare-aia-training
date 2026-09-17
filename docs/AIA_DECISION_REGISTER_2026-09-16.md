# Decision register — 16 September 2026

A decision record distinguishes source findings from proposed action. It does not silently patch source data or change configurations. Read alongside the preserved 8 September plan and the dated research-status record. Internal proposal documents are retained privately and are not included in this public checkpoint.

| ID | Earlier position | New evidence / change | Disposition |
|---|---|---|---|
| D01 | Existing AIA repository | User and repository checks confirm one populated authoritative AIA history. | Continue `Watchman77/solar-flare-aia-training`; no merge or new repository. |
| D02 | 2018–2019 validation example | Current labels contain no positives in those years. | Superseded as the intended positive-event development window, not erased from history. |
| D03 | v1 model training restricted to 2010–2013 | User requested later Cycle-24 training; broader v2 reservations now built. | Prefer v2 for the next protocol review; keep v1 for reproducibility of its canary. No split frozen here. |
| D04 | 2026 supplementary | Covered portion retained as held-out evaluation. | Keep; not training data, not a complete 2026-year claim. |
| D05 | NPZ and manifest labels differ | Three values match old global labels; inspected 16B reads final manifest. | Explained for those cases/loading path. Preserve old values; no retraining solely for unused NPZ y. |
| D06 | Nominal slot treated like exact exposure instant | Source headers separate slot, start/midpoint and exposure. | New lagged-history experiment; do not retroactively relabel old runs as strict causal forecasts. |
| D07 | July target 07:24 with source 07:00 | Original manifests and headers preserve the mismatch. | Keep original pairing; exclude it from claimed strict aligned subset pending correction. Distinct from D08. |
| D08 | One positive July 2024 label | Event-window match changes under unverified export-UTC hypothesis. | Conditional diagnostic; original label not replaced. |
| D09 | Three-frame canary | Real AIA/SHARP engineering path works. | Engineering completed; weights/debug preprocessing discarded, not a full forecast result. |
| D10 | Missing magnetic inputs | All exact keys matched; 206 candidate rows numerically incomplete; zero explicit NOAA conflicts. | Specify quality and train-only imputation rules before scientific training; no arbitrary zero fill. |
| D11 | GOES input branch | Full export/availability still uncleared; current inspected catalogue is M/X only. | Retain M2/M3/M6 in scope. Do not fabricate C counts/XRS or silently describe M5 as full M6. |
| D12 | UQ not previously standardised | Standing checklist and addendum adopted. | Preserve calibration, prediction/metric uncertainty and paired statistics as planned evaluation; not completed experiments. |
| D13 | PINN/PIML advanced idea | Separate 20A–20C plan. | Separate within the same repo; not part of the current trained/debug fusion network or a completed MHD solver. |
| D14 | Routine billing disconnection | Superseded archival-data operating rule. | Keep storage and compute management separate; verified durable backup before deletions. No cloud changes here. |
| D15 | Source scripts run from Cloud Shell home | Later work not all pushed after a66a992. | Copy exact scripts/tests and small evidence into a reviewed checkpoint; do not remove original paths or claim a full data backup. |

Outstanding common eligibility: event time-scale/region provenance, catalogue completeness and follow-up; source-quality criteria; strict contributing-time and historical availability where claimed; full-population input timing; accepted model/split configuration. A successful software check does not waive them.

## Publication selection — 17 September 2026

The completed earlier image, magnetic and intermediate-fusion experiments are the baseline phase. This continuation documents preparation for a separate cross-cycle temporal extension. The internal master proposal and the documentation copier containing its embedded text are withheld from this public checkpoint; their original bytes are preserved locally. No source-data, label, split, scientific-code or result correction is performed by that selection. Public technical configurations are proposal/evidence snapshots, not a frozen final experiment or supervisor approval.
