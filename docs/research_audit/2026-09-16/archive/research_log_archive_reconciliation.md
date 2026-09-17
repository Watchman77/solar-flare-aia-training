# AIA archive object reconciliation

**Status: object inventory only; no training clearance.**

Locked master target rows: 141,644.

|Stored year|Targets|Exact nonempty|Not found|Zero-byte|Multiple|Alternate|
|---|---:|---:|---:|---:|---:|---:|
|2010|3316|3306|10|0|0|0|
|2011|11277|11142|135|0|0|0|
|2012|10855|10815|40|0|0|0|
|2013|13333|13066|267|0|0|0|
|2014|11653|11627|26|0|0|0|
|2015|11259|11236|23|0|0|0|
|2016|6885|6818|67|0|0|0|
|2017|3462|3444|18|0|0|0|
|2018|1711|1711|0|0|0|0|
|2019|1058|1057|1|0|0|0|
|2020|2089|2089|0|0|0|0|
|2021|5828|5797|31|0|0|0|
|2022|11534|11506|28|0|0|0|
|2023|14677|14308|369|0|0|0|
|2024|14732|14720|12|0|0|0|
|2025|14774|12133|2641|0|0|0|
|2026|3201|2939|262|0|0|0|

## Interpretation

- Listings are current-object metadata as observed at the recorded times, not an atomic archive snapshot.
- Cached successful listings are deliberately reused, not silently refreshed.
- Missing means no matching object in the specified yearly prefix, not absence everywhere or a negative flare label.
- Names, nonzero byte sizes and listed checksums do not validate NPZ contents.
- Storage creation/update times and sample-ID clocks are NOT AIA observation times.
- Neither the 180-second tolerance nor no-future-image condition has been tested in this run.
- Next canary selection is deterministic and not a representative statistical sample or a completeness certificate.
- Catalogue completeness, reporting availability, qualified histories and final split/calibration design remain open.
