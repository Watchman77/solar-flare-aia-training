# Research checkpoint — 15 September 2026

**Status: 17B metadata/provenance/timing reviews completed; full readiness NOT cleared.**
This is a checkpoint, not a dataset release or approval to train. Local files and
report outputs were collected from the completed runs below, not rerun.

## Scientific contract

Same-active-region M/X forecasting over (t, t+48h]; six AIA channels
94/131/171/193/211/335 Å; source cadence 96 minutes; 180-second tolerance
AND the no-future-image rule require actual-timestamp verification.
`label_48h_final` is preserved; embedded NPZ labels are not authorised truth.
The baseline and 2025–2026 extension are subsets of the master, not append jobs.

## Conditional timing result — NOT a replacement label set

Event-scale assumption: `FULL_EVENT_EXPORT_UTC_HYPOTHESIS_NOT_VERIFIED`.

| Cohort | Rows | Original positives | Clock-reference hits | UTC-hypothesis hits | Clock changes | UTC/original disagreements |
|---|---:|---:|---:|---:|---:|---:|
| baseline_manifest | 68010 | 2398 | 2398 | 2398 | 0 | 0 |
| curated_master | 141644 | 5634 | 5634 | 5633 | 1 | 1 |
| extension | 17975 | 998 | 998 | 998 | 0 | 0 |

Clock-field-reference agreement is not independent catalogue verification.
Zero hits do not certify negatives. Zero baseline changes do not certify AIA
causality, catalogue completeness or every previous modelling decision.
Only the current script's same-region, start-window calculation was compared.
No original labels, raw event rows, IDs or cloud objects were repaired.

## Event evidence and remaining decisions

Retain the four flagged original records. The May group has matching start/peak/class
but conflicting end times. The matching August and November primary reports provide
no peak (MAX=////); unsupported exported peaks remain unknown in a review overlay.
The full event catalogue's UTC provenance, completeness and reporting availability
are not established by these three daily reports. The one conditional 2024 label
difference still needs sample-level boundary review.

## Development split

The example 2018–2019 validation allocation in the September 8 plan and original
17A draft is superseded by the audit's zero-positive finding. No replacement split
is frozen. Few positive region identifiers in 2016/2017 are not automatically
adequate calibration/validation support. Retain the intended independent Cycle-25
test boundary; do not tune models or thresholds using its performance.
The unchanged metadata configuration remains a historical, unfrozen proposal, not
a training specification. Further label/provenance checks precede split selection.

## Evaluation and separate physics-informed track

Performance → Calibration → Uncertainty → Robustness → Explainability → Statistical significance.
See [research standard](TRUSTWORTHY_RESEARCH_STANDARD.md) and
[UQ/calibration protocol](AIA_UQ_CALIBRATION_PROTOCOL.md).
UQ requirements are installed, not experimental UQ/calibration results.
The 20A/20B/20C PINN/PIML track remains separate and planned; past-tense interview
paragraphs are completion templates only. No full MHD PINN is claimed.

## Active compute/storage policy

Do not routinely disconnect billing on the project holding the archive.
Use bounded runs and known storage costs; verify backups before any resource deletion.
This checkpoint performs no resource operation. The README's July L4 description is
historical, not current resource inventory. Google warns that billing disconnection
can remove some resources: https://docs.cloud.google.com/billing/docs/how-to/modify-project
Issue #1 still needs a separate update; a Git commit cannot edit an issue body.

## Evidence and reproducibility

- Original repository base for preparation: `d1b921ecb950085f29547d5bc9aa093842b4ecd3`.
- Stage 1: `20260915T005020436079Z`.
- Event forensics: `event_time_20260915T103446628773Z`.
- Primary evidence: `primary_sources_20260915T164444194047Z`.
- Conditional timing: `time_label_impact_20260915T172829490191Z`.
- Evidence snapshots: [research_audit/2026-09-15](research_audit/2026-09-15/).
- Exact time-environment pins and its recorded freeze: `../configs/aia17_time_*`.
- Standalone review scripts are now under `../scripts/`; their defaults still
  refer to this Cloud Shell home-directory layout and dated runs. Adjust documented
  CLI paths when reproducing elsewhere; copying a report does not relocate its inputs.
- The fixture/protocol test log is included. It is NOT a model-training test.

Small evidence copies preserve their bytes and report/source hashes. Absolute local
paths inside them are historical provenance, not evidence those files exist on another
machine. The two large compressed diagnostic CSVs, raw metadata, SQLite database,
images, checkpoints and virtual environments are deliberately NOT copied into Git.
Their recorded checksums do not constitute an off-machine backup. The detailed outputs
still need separately verified durable storage. Checkpoints remain only locally staged
until a reviewed commit is pushed and the remote commit is verified.

## Outstanding gates

- Full event-export UTC provenance, catalogue completeness and region association still unverified.
- Original label-builder start/peak/boundary semantics not yet established.
- No-event matches are not certified negative labels; continuous 48h follow-up not established.
- AIA actual timestamps, no-future-image rule and 180-second tolerance still require audit.
- SHARP/AIA sequence coverage and split/purge/calibration-region design still require audit.
- Peak/end times are not report-availability times; past-only GOES input features are not authorised.
- UQ protocol installed separately; no UQ/calibration/training results produced here.
