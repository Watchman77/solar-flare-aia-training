# AIA Baseline 2010–2016 Protocol Summary

## Dataset

- Manifest: `/home/abmoses2000/solar_flare_aia/training/final_metadata/baseline_2010_2016_AR_SPECIFIC_manifest.csv`
- Input tensor: `x`, shape `(512, 512, 6)`
- Channels: `aia94`, `aia131`, `aia171`, `aia193`, `aia211`, `aia335`
- Label: `label_48h_final`
- Embedded NPZ `y` is ignored for formal training.
- Task: same-active-region M/X flare prediction within 48 hours.

## Split protocol

- Rolling-origin chronological year-holdout.
- For test year `Y`, validation year is `Y-1`; training years are all years before `Y-1`.
- Threshold is selected on validation by maximum TSS and applied unchanged to test.

## Candidate folds

- `test_2012`: train=[2010], val=2011, test=2012, train_pos=29, val_pos=404, test_pos=305, usable=False. Low training positive count; may be unstable for deep CNN training.
- `test_2013`: train=[2010, 2011], val=2012, test=2013, train_pos=433, val_pos=305, test_pos=492, usable=True. Candidate fold for formal benchmark.
- `test_2014`: train=[2010, 2011, 2012], val=2013, test=2014, train_pos=738, val_pos=492, test_pos=629, usable=True. Candidate fold for formal benchmark.
- `test_2015`: train=[2010, 2011, 2012, 2013], val=2014, test=2015, train_pos=1230, val_pos=629, test_pos=531, usable=True. Candidate fold for formal benchmark.
- `test_2016`: train=[2010, 2011, 2012, 2013, 2014], val=2015, test=2016, train_pos=1859, val_pos=531, test_pos=8, usable=False. Very low positive count in test year; report cautiously or treat as stress fold.

## Outputs

- Year counts: `/home/abmoses2000/solar_flare_aia/results/metrics/aia_baseline_2010_2016_protocol_year_counts.csv`
- Fold summary: `/home/abmoses2000/solar_flare_aia/results/metrics/aia_baseline_2010_2016_protocol_fold_summary.csv`
- Fold assignments: `/home/abmoses2000/solar_flare_aia/results/metrics/aia_baseline_2010_2016_protocol_fold_assignments.csv`
- Protocol JSON: `/home/abmoses2000/solar_flare_aia/results/metrics/aia_baseline_2010_2016_protocol.json`
