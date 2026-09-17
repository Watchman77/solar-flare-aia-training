# Broader Cycle-24 SHARP input arrays

This build reuses v2 region reservations and forward development folds. It does
not choose a new split, repair targets or train a model. Only Cycle-24 training,
calibration and threshold candidates receive arrays; Cycle-25/2026 arrays are not
constructed. The raw source CSV is nevertheless scanned as a file covering all
years; unrequested records are ignored.

Each array row has three exact historical HARP/TAI records at lags 288, 192 and
96 minutes, using the 15 existing magnetic features. No TOTUSJH is fabricated.
NaN marks absent, duplicate or nonfinite/unparseable values. A complete finite
row is not a QUALITY, latency, label or timing certificate. No rows are silently
dropped; source-record counts, explicit NOAA conflicts and QUALITY are retained.

No scaler or imputer is fitted, and the tiny engineering-test preprocessing is
not reused. Future training must fit preprocessing within each training fold.
These sparse three-slot inputs do not replace the planned 6/12/24h history
experiments. Paired AIA/SHARP comparisons will need an explicitly matched eligible
population. Final calibration is region-held-out within Cycle 24. The forecast
label and 48-hour horizon are unchanged; full readiness remains open.
