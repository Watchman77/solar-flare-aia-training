#!/usr/bin/env python3
"""17B: append-only canonical issue times and CONDITIONAL event-window audit.

Reads the four already-cached CSVs and three already-downloaded NOAA reports.
No network, gcloud, source edits, deduplication, label replacement, or training.
Requires Astropy 7.1.0 and NumPy. Run directly; no opt-in flags are required.

The full event export's UTC scale is a DIAGNOSTIC HYPOTHESIS, not certified by
three matching reports. A catalogue hit of zero is NOT a verified negative label.
"""
from __future__ import annotations
import argparse
from bisect import bisect_right
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import gzip
import hashlib
from importlib import metadata
import json
from pathlib import Path
import re
import shutil
import sys
from typing import Any

VERSION = "aia17-time-label-impact-v1"
RUN_ID = "20260915T005020436079Z"
PRIMARY_ID = "primary_sources_20260915T164444194047Z"
HORIZON_US = 172800 * 1000000  # 48 physical hours on a continuous TAI axis.
SCOPE_END = "2026-07-01T00:00:00"  # Finite historical scope, not future leap prediction.
ASSUMPTION = "FULL_EVENT_EXPORT_UTC_HYPOTHESIS_NOT_VERIFIED"
TAI_RE = re.compile(r"^(\d{4})\.(\d{2})\.(\d{2})_(\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?)_TAI$")
ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?$")
REQUIRED_TARGET = ("sample_id", "T_REC_dt", "HARPNUM", "NOAA_AR_clean", "label_48h_final")
EVENT_FIELDS = ("event_starttime", "event_peaktime", "event_endtime", "fl_goescls", "NOAA_AR_clean", "flux")


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(4 * 1024**2), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path: Path) -> dict:
    if not path.is_file() or path.stat().st_size > 25 * 1024**2:
        raise ValueError(f"Missing or oversized JSON: {path}")
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return obj


def write_json(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8") as f:
        json.dump(value, f, indent=2, allow_nan=False)
        f.write("\n")


def rows(path: Path, required: tuple[str, ...]):
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, strict=True)
        cols = reader.fieldnames or []
        if len(set(cols)) != len(cols) or not set(required) <= set(cols):
            raise ValueError(f"Unexpected CSV schema: {path}")
        for n, row in enumerate(reader, 1):
            if None in row or any(v is None for v in row.values()):
                raise ValueError(f"Malformed CSV row {n}: {path}")
            yield n, row


def id_string(value: str) -> str:
    try:
        x = Decimal(str(value).strip())
    except InvalidOperation as exc:
        raise ValueError(f"Invalid region identifier: {value!r}") from exc
    if not x.is_finite() or x != x.to_integral_value() or x <= 0:
        raise ValueError(f"Invalid region identifier: {value!r}")
    return str(int(x))


def label(value: str) -> int:
    if str(value).strip() not in {"0", "1", "0.0", "1.0"}:
        raise ValueError(f"Unrecognised original binary label: {value!r}")
    return int(float(value))


def naive_iso(value: str) -> str:
    s = str(value).strip()
    if not ISO_RE.fullmatch(s):
        raise ValueError(f"Unexpected naive clock representation: {value!r}")
    # Current audited sources contain no leap-second text in this naive column.
    t = datetime.fromisoformat(s)
    iso = t.isoformat(timespec="microseconds")
    if not "2010-01-01T00:00:00" <= iso < SCOPE_END:
        raise ValueError(f"Clock outside the fixed 2010--first-half-2026 scope: {s}")
    return iso


def raw_tai_iso(value: str) -> str:
    m = TAI_RE.fullmatch(str(value).strip())
    if not m:
        raise ValueError(f"Unsupported explicit TAI source: {value!r}")
    return naive_iso(f"{m[1]}-{m[2]}-{m[3]}T{m[4]}")


def representation_us(iso: str) -> int:
    # This is deliberately a clock-only reference, NOT a physical UTC conversion.
    d = datetime.fromisoformat(iso) - datetime(1970, 1, 1)
    return (d.days * 86400 + d.seconds) * 1000000 + d.microseconds


def target_identity(row: dict) -> tuple:
    sid = row["sample_id"].strip()
    if not sid:
        raise ValueError("Missing sample ID.")
    return (sid, naive_iso(row["T_REC_dt"]), id_string(row["HARPNUM"]),
            id_string(row["NOAA_AR_clean"]), label(row["label_48h_final"]))


def event_key(row: dict) -> str:
    return "|".join((row["NOAA_AR_clean"].strip(), row["event_starttime"].strip(),
                     row["event_peaktime"].strip(), row["fl_goescls"].strip().upper()))


def window_count(index: dict[str, list[int]], noaa: str, issue: int) -> int:
    values = index.get(noaa, ())
    return bisect_right(values, issue + HORIZON_US) - bisect_right(values, issue)


class AstroClock:
    """Explicit scales; continuous integer-microsecond TAI axis for comparisons."""
    def __init__(self):
        try:
            import numpy as np
            from astropy.time import Time
            from astropy.utils import iers
        except ImportError as exc:
            raise RuntimeError(
                "Astropy/NumPy not available in this interpreter. Use the supplied "
                "venv/pip command, then run with $HOME/aia17_time_venv/bin/python."
            ) from exc
        iers.conf.auto_download = False  # No automatic IERS network fetch.
        self.np, self.Time = np, Time

    def ticks(self, iso: list[str], scale: str) -> list[int]:
        if not iso:
            return []
        t = self.Time(iso, format="isot", scale=scale, precision=6)
        val = t.tai.to_value("unix_tai", subfmt="long") * self.np.longdouble(1000000)
        return [int(x) for x in self.np.rint(val).astype(self.np.int64)]

    def utc_text(self, ticks: list[int]) -> list[str]:
        if not ticks:
            return []
        val = self.np.array(ticks, dtype=self.np.longdouble) / self.np.longdouble(1000000)
        t = self.Time(val, format="unix_tai", scale="tai", precision=6)
        return [str(v) + "Z" for v in self.np.atleast_1d(t.utc.isot)]

    def check(self) -> dict:
        # Expected historical offsets are independently specified; no fixed offset
        # is used in the actual conversion. The historical scope is finite.
        cases = [
            ("2010-05-21T03:48:00", "2010-05-21T03:47:26"),
            ("2012-07-01T00:01:00", "2012-07-01T00:00:25"),
            ("2015-07-01T00:01:00", "2015-07-01T00:00:24"),
            ("2017-01-01T00:01:00", "2017-01-01T00:00:23"),
            ("2026-05-10T12:00:00", "2026-05-10T11:59:23"),
        ]
        for tai, utc in cases:
            if self.ticks([tai], "tai") != self.ticks([utc], "utc"):
                raise ValueError(f"Historical scale-conversion self-test failed: {tai}")
        leap = self.ticks(["2016-12-31T23:59:59", "2016-12-31T23:59:60", "2017-01-01T00:00:00"], "utc")
        if leap[1]-leap[0] != 1000000 or leap[2]-leap[1] != 1000000:
            raise ValueError("Leap-second interval self-test failed.")
        if self.utc_text([leap[1]])[0] != "2016-12-31T23:59:60.000000Z":
            raise ValueError("Leap-second round-trip self-test failed.")
        span_start = self.ticks(["2016-12-30T12:00:00"], "utc")[0]
        if self.utc_text([span_start + HORIZON_US])[0] != "2017-01-01T11:59:59.000000Z":
            raise ValueError("Physical 48-hour leap-crossing self-test failed.")
        return {"passed": True, "offset_anchor_cases": len(cases),
                "leap_second_sequence_and_round_trip": True,
                "48_physical_hour_leap_crossing": True,
                "scope_end_exclusive": SCOPE_END,
                "reference": "https://www.nist.gov/pml/time-and-frequency-division/time-realization/leap-seconds"}


def validate_inputs(run: Path, primary_path: Path):
    primary = read_json(primary_path)
    required_days = {"20240508", "20240818", "20241118"}
    sources = primary.get("primary_sources", [])
    if {s.get("day") for s in sources} != required_days or len(sources) != 3:
        raise ValueError("Expected precisely the three completed primary-source days.")
    if any(s.get("status") != "PRIMARY_REPORT_READ" for s in sources):
        raise ValueError("Public verification was skipped or incomplete. Use its completed run.")
    stamps = {str(primary_path): sha(primary_path)}
    for name, expected in primary.get("input_sha256", {}).items():
        p = Path(name).expanduser().resolve()
        if not p.is_file() or sha(p) != expected:
            raise ValueError(f"Primary verification input changed or missing: {p}")
        stamps[str(p)] = expected
    for s in sources:
        p = primary_path.parent / (s["day"] + "events.txt")
        if not p.is_file() or p.stat().st_size > 128 * 1024 or sha(p) != s.get("sha256"):
            raise ValueError(f"Saved primary report hash mismatch: {p}")
        lines = p.read_text(encoding="utf-8-sig").splitlines()
        for rec in s.get("xra_records", []):
            if lines[rec["line_number"]-1] != rec["raw_line"]:
                raise ValueError("Saved primary record no longer matches raw source line.")
        stamps[str(p)] = s["sha256"]
    stage_path, lock_path = run/"stage1_report.json", run/"source_lock_snapshot.json"
    stage, lock = read_json(stage_path), read_json(lock_path)
    if stage.get("status") != "STAGE1_COMPLETE_REVIEW_REQUIRED":
        raise ValueError("The Stage-1 run is not complete.")
    forensic = read_json(Path(primary["forensic_review"]))
    if Path(forensic["source_run"]).resolve() != run:
        raise ValueError("Primary/forensic evidence refers to a different Stage-1 run.")
    profiles = {p["source"]: p for p in stage["source_profiles"]}
    specs = {}
    for source_id in ("curated_master", "baseline_manifest", "extension", "events"):
        matches = [s for s in lock["sources"] if s["id"] == source_id]
        if len(matches) != 1:
            raise ValueError(f"Missing/ambiguous pinned source: {source_id}")
        s = matches[0]; p = Path(s["local_path"]).expanduser().resolve()
        if not p.is_file() or p.stat().st_size != int(s["size_bytes"]) or sha(p) != s.get("sha256"):
            raise ValueError(f"Cached source does not match pinned audit: {source_id}")
        specs[source_id] = s
        stamps[str(p)] = s["sha256"]
    for p in (stage_path, lock_path, Path(primary["forensic_review"])):
        stamps[str(p)] = sha(p)
    return primary, forensic, profiles, specs, stamps


def event_views(spec: dict, primary: dict, forensic: dict, clock):
    comparisons = {c["audit_key"]: c for c in primary["comparisons"]}
    if len(comparisons) != 3:
        raise ValueError("Expected three distinct source comparisons.")
    events = []; register = []
    bad_keys = {r["audit_key"] for r in forensic["events"]["time_anomaly_records"]}
    dup_keys = {g["audit_key"] for g in forensic["events"]["duplicate_groups"]}
    for rownum, row in rows(Path(spec["local_path"]), EVENT_FIELDS):
        key = event_key(row)
        cls = row["fl_goescls"].strip().upper()
        if not re.fullmatch(r"[MX](?:\d+(?:\.\d*)?|\.\d+)", cls):
            raise ValueError(f"Unexpected event-class scope at row {rownum}: {cls}")
        rec = {"rownum": rownum, "raw": row, "key": key, "noaa": id_string(row["NOAA_AR_clean"]),
               "start": naive_iso(row["event_starttime"]), "bad_peak": key in bad_keys,
               "duplicate": key in dup_keys}
        # All source records stay in these indices. No physical event deduplication.
        events.append(rec)
        if key in comparisons:
            c = comparisons[key]
            matches = c["time_class_region_candidates"]
            if not matches:
                raise ValueError(f"No saved primary match for flagged event: {key}")
            if key in bad_keys and c["raw_unique_max_tokens"] != ["////"]:
                raise ValueError("Peak-null overlay requires the observed missing primary MAX.")
            if any(m["begin_raw"] != datetime.fromisoformat(rec["start"]).strftime("%H%M")
                   or m["class_raw"] != cls for m in matches):
                raise ValueError("Primary comparison no longer matches start/class.")
            register.append({"source_record_number": rownum, "audit_key": key,
                "raw": row, "primary_candidate_lines": [m["raw_line"] for m in matches],
                "review_status": "PEAK_UNKNOWN_PRIMARY_MAX_MISSING" if rec["bad_peak"] else "END_CONFLICT_UNRESOLVED",
                "peak_time_review": None if rec["bad_peak"] else row["event_peaktime"],
                "end_time_review": None if rec["duplicate"] else row["event_endtime"],
                "peak_based_input_authorised": False, "duration_input_authorised": False,
                "catalogue_record_removed": False,
                "note": "Review overlay only; start retained for conditional target-existence test. No reporting-time claim."})
    if {r["audit_key"] for r in register} != set(comparisons):
        raise ValueError("One or more primary targets absent from cached event export.")
    physical = clock.ticks([e["start"] for e in events], "utc")
    names = ("reference", "utc_scenario", "bad_peak", "non_bad_peak", "duplicate")
    indices = {name: defaultdict(list) for name in names}
    for e, tick in zip(events, physical):
        indices["reference"][e["noaa"]].append(representation_us(e["start"]))
        indices["utc_scenario"][e["noaa"]].append(tick)
        indices["bad_peak" if e["bad_peak"] else "non_bad_peak"][e["noaa"]].append(tick)
        if e["duplicate"]:
            indices["duplicate"][e["noaa"]].append(tick)
    for mapping in indices.values():
        for values in mapping.values():
            values.sort()
    return events, register, indices


def cohort_index(spec: dict, expected: int) -> dict:
    members = {}
    for _, row in rows(Path(spec["local_path"]), REQUIRED_TARGET):
        identity = target_identity(row)
        if identity[0] in members:
            raise ValueError("Duplicate ID in existing cohort; no silent resolution.")
        members[identity[0]] = identity
    if len(members) != expected:
        raise ValueError("Existing cohort count differs from Stage 1.")
    return members


OUT_COLUMNS = ["sample_id", "HARPNUM", "NOAA_AR_clean", "T_REC_raw_TAI", "T_REC_dt_original",
    "T_REC_utc_derived", "forecast_end_utc_48_SI_hours", "stored_year", "utc_year",
    "original_label_48h_final", "in_baseline_manifest", "in_extension",
    "catalogue_start_hit_clock_only_reference", "catalogue_start_hit_utc_hypothesis",
    "clock_interpretation_changes_start_hit", "utc_hypothesis_differs_from_original_label",
    "window_contains_missing_peak_event", "window_supported_only_by_missing_peak_events",
    "window_contains_end_conflict_records", "event_scale_status", "followup_status", "training_authorised"]


def analyse_batch(batch, clock, indices, cohorts, counters, writer, changed, seen):
    identities = [target_identity(row) for _, row in batch]
    raw_iso = [raw_tai_iso(row["T_REC"]) for _, row in batch]
    for identity, raw in zip(identities, raw_iso):
        if identity[1] != raw:
            raise ValueError(f"Stored clock no longer equals raw TAI fields: {identity[0]}")
    ticks = clock.ticks(raw_iso, "tai")
    utc = clock.utc_text(ticks)
    ends = clock.utc_text([t+HORIZON_US for t in ticks])
    for (_, raw), identity, tick, canonical, end in zip(batch, identities, ticks, utc, ends):
        sid, old_iso, harp, noaa, y = identity
        if sid in seen:
            raise ValueError("Duplicate master ID; no silent deduplication.")
        seen.add(sid)
        if canonical < "2010-01-01T00:00:00" or end >= SCOPE_END:
            raise ValueError("Physical forecast interval outside the verified conversion scope.")
        memberships = []
        for name, members in cohorts.items():
            if sid in members:
                if identity != members[sid]:
                    raise ValueError(f"Cohort identity differs from master: {name}, {sid}")
                memberships.append(name)
        reference = int(window_count(indices["reference"], noaa, representation_us(old_iso)) > 0)
        scenario = int(window_count(indices["utc_scenario"], noaa, tick) > 0)
        bad = int(window_count(indices["bad_peak"], noaa, tick) > 0)
        sole_bad = int(bad and window_count(indices["non_bad_peak"], noaa, tick) == 0)
        dup = int(window_count(indices["duplicate"], noaa, tick) > 0)
        item = dict(zip(OUT_COLUMNS, (sid, harp, noaa, raw["T_REC"], raw["T_REC_dt"], canonical, end,
            old_iso[:4], canonical[:4], y, int("baseline_manifest" in memberships), int("extension" in memberships),
            reference, scenario, int(reference != scenario), int(scenario != y), bad, sole_bad, dup,
            ASSUMPTION, "NOT_VERIFIED", False)))
        writer.writerow(item)
        if reference != scenario or scenario != y or bad or dup:
            changed.writerow(item)
        for name in ["curated_master"] + memberships:
            # Cohorts are separate summaries; NEVER add extension/baseline counts to master.
            for year in ("ALL", old_iso[:4]):
                c = counters[(name, year)]
                c.update({"rows": 1, "original_positive_rows": y, "clock_reference_hits": reference,
                    "utc_hypothesis_hits": scenario, "clock_changed": int(reference != scenario),
                    "clock_0_to_1": int(reference == 0 and scenario == 1),
                    "clock_1_to_0": int(reference == 1 and scenario == 0),
                    "reference_vs_original": int(reference != y), "utc_hypothesis_vs_original": int(scenario != y),
                    "missing_peak_windows": bad, "only_missing_peak_support": sole_bad,
                    "end_conflict_windows": dup, "utc_year_changed": int(old_iso[:4] != canonical[:4])})


def run_audit(run: Path, primary_path: Path, clock, repo: Path) -> Path:
    print("===== 17B CANONICAL CLOCK / CONDITIONAL LABEL IMPACT =====", flush=True)
    print("No network or source changes. The event UTC assumption is NOT certification.", flush=True)
    checks = clock.check()
    primary, forensic, profiles, specs, fingerprints = validate_inputs(run, primary_path)
    if shutil.disk_usage(run).free < 512 * 1024**2:
        raise ValueError("Less than 512 MiB free. No output table has been started.")
    events, register, indices = event_views(specs["events"], primary, forensic, clock)
    if len(events) != int(profiles["events"]["rows"]):
        raise ValueError("Event count differs from Stage 1.")
    cohorts = {name: cohort_index(specs[name], int(profiles[name]["rows"]))
               for name in ("baseline_manifest", "extension")}
    out = run.parent.parent/"reviews"/("time_label_impact_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    out.mkdir(parents=True, exist_ok=False)
    marker = out/"INCOMPLETE.txt"
    marker.write_text("Output is not accepted unless COMPLETE.json exists. Originals remain unchanged.\n")
    counters = defaultdict(Counter); seen = set(); batch = []
    with gzip.open(out/"sample_time_and_window_diagnostics.csv.gz", "wt", encoding="utf-8", newline="") as f, \
         gzip.open(out/"affected_samples.csv.gz", "wt", encoding="utf-8", newline="") as g:
        w = csv.DictWriter(f, fieldnames=OUT_COLUMNS); d = csv.DictWriter(g, fieldnames=OUT_COLUMNS)
        w.writeheader(); d.writeheader()
        for rec in rows(Path(specs["curated_master"]["local_path"]), REQUIRED_TARGET + ("T_REC",)):
            batch.append(rec)
            if len(batch) == 4096:
                analyse_batch(batch, clock, indices, cohorts, counters, w, d, seen)
                print(f"  Canonicalised/audited {len(seen):,} target rows", flush=True)
                batch = []
        if batch:
            analyse_batch(batch, clock, indices, cohorts, counters, w, d, seen)
    if len(seen) != int(profiles["curated_master"]["rows"]):
        raise ValueError("Master row count differs from Stage 1.")
    if any(set(members)-seen for members in cohorts.values()):
        raise ValueError("A cohort is not fully represented in the master.")
    if any(sha(Path(p)) != h for p, h in fingerprints.items()):
        raise ValueError("An input changed during this run; output remains INCOMPLETE.")
    summary_rows = [{"cohort": name, "stored_year": year, **dict(c)}
                    for (name, year), c in sorted(counters.items())]
    with (out/"window_impact_by_year.csv").open("x", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(summary_rows[0])); w.writeheader(); w.writerows(summary_rows)
    write_json(out/"event_source_resolution_overlay.json", {"version": VERSION,
        "status": "REVIEW_OVERLAY_NOT_A_REPLACEMENT_CATALOGUE", "records": register,
        "primary_review": str(primary_path), "primary_review_sha256": fingerprints[str(primary_path)]})
    versions = {}
    for name in ("astropy", "numpy", "pyerfa", "astropy-iers-data"):
        try: versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError: versions[name] = "not-installed-in-test-engine"
    gates = [
        "Full event-export UTC provenance, catalogue completeness and region association still unverified.",
        "Original label-builder start/peak/boundary semantics not yet established.",
        "No-event matches are not certified negative labels; continuous 48h follow-up not established.",
        "AIA actual timestamps, no-future-image rule and 180-second tolerance still require audit.",
        "SHARP/AIA sequence coverage and split/purge/calibration-region design still require audit.",
        "Peak/end times are not report-availability times; past-only GOES input features are not authorised.",
        "UQ protocol installed separately; no UQ/calibration/training results produced here.",
    ]
    result = {"version": VERSION, "status": "TIME_LABEL_IMPACT_COMPLETE_CONDITIONAL_NO_REPAIRS",
        "conversion_self_tests": checks, "python": sys.version, "versions": versions,
        "source_run": str(run), "input_sha256": fingerprints, "time_scale_assumption": ASSUMPTION,
        "interpretation": {"canonical_issue_times": "Converted from explicit raw TAI using Astropy; sample IDs/paths unchanged.",
            "clock_reference": "As-stored naive clock-field comparison; not asserted to reproduce the historical label builder.",
            "utc_hypothesis": "Event starts provisionally interpreted as UTC; compare on continuous TAI using (t,t+172800 SI s].",
            "catalogue_hit": "Existence of a matching M/X catalogue start in the given window, not verified occurrence/absence truth.",
            "event_groups": "All exported event records retained. Duplicate counts never used as inputs; existence queries naturally ignore repetition.",
            "review_overlay": "Known unsupported peaks are null ONLY in a separate overlay; source records are untouched.",
            "peak_defect_impact": "Flagged start-window support reported; excluding events is not adopted as a negative-label policy.",
            "summary_year": "Stored-year cohorts for before/after comparability; UTC year also exported and changes counted."},
        "summary": summary_rows, "training_authorised": False, "original_labels_replaced": False,
        "new_calibration_fit": False, "remaining_gates": gates,
        "uq_files_present": {p: (repo/p).is_file() for p in ("docs/TRUSTWORTHY_RESEARCH_STANDARD.md",
            "docs/AIA_UQ_CALIBRATION_PROTOCOL.md", "configs/aia_uq_calibration_protocol.json")}}
    write_json(out/"time_label_impact_report.json", result)
    totals = counters[("curated_master", "ALL")]
    note = ["# 17B canonical time and conditional event-window impact", "", f"Source run: {run.name}",
        "", "No source labels, times, IDs, paths, or source event records were replaced.",
        "", "The full catalogue UTC interpretation is a diagnostic hypothesis, NOT a verified new label set.",
        f"Targets audited: {totals['rows']:,}.",
        f"Clock interpretation changes catalogue start hits: {totals['clock_changed']:,}.",
        f"Clock-reference disagreements with original labels: {totals['reference_vs_original']:,}.",
        f"UTC-hypothesis disagreements with original labels: {totals['utc_hypothesis_vs_original']:,}.",
        "", "Missing primary MAX values are preserved as unknown in a review overlay. Conflicting end times remain unresolved.",
        "", "Neither zero changes nor improved file agreement verifies catalogue completeness or image causality.",
        "", "## Remaining gates", ""] + ["- "+g for g in gates]
    (out/"research_log_time_label_impact.md").write_text("\n".join(note)+"\n", encoding="utf-8")
    output_hashes = {p.name: sha(p) for p in out.iterdir() if p.name != marker.name and p.is_file()}
    write_json(out/"COMPLETE.json", {"status": result["status"], "output_sha256": output_hashes})
    marker.unlink()
    print("\n===== TIME / LABEL IMPACT RESULTS =====")
    print("Conversion self-tests:", json.dumps(checks))
    print("Event UTC interpretation:", ASSUMPTION)
    print("Review overlay records:", len(register), "(no source rows removed)")
    print("cohort | rows | original positives | clock-reference hits | UTC-hypothesis hits | clock-changed | reference/original disagreements | UTC/original disagreements")
    for name in ("curated_master", "baseline_manifest", "extension"):
        c = counters[(name, "ALL")]
        print(name, c["rows"], c["original_positive_rows"], c["clock_reference_hits"], c["utc_hypothesis_hits"],
              c["clock_changed"], c["reference_vs_original"], c["utc_hypothesis_vs_original"], sep=" | ")
    print("\nMASTER BY STORED YEAR: year | clock changes 0->1 | 1->0 | UTC/original disagreements | missing-peak windows")
    for (name, year), c in sorted(counters.items()):
        if name == "curated_master" and year != "ALL":
            print(year, c["clock_0_to_1"], c["clock_1_to_0"], c["utc_hypothesis_vs_original"], c["missing_peak_windows"], sep=" | ")
    print("\nOriginal source files unchanged. Zero catalogue hits do NOT certify negatives.")
    print("STATUS:", result["status"])
    print("REPORT:", out/"time_label_impact_report.json")
    print("RESEARCH LOG:", out/"research_log_time_label_impact.md")
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", type=Path, default=Path.home()/"aia17_metadata_stage1"/"runs"/RUN_ID)
    p.add_argument("--primary-review", type=Path, default=Path.home()/"aia17_metadata_stage1"/"reviews"/PRIMARY_ID/"primary_source_review.json")
    p.add_argument("--repo", type=Path, default=Path.home()/"solar_flare_aia")
    p.add_argument("--self-test-only", action="store_true")
    args = p.parse_args()
    try:
        clock = AstroClock()
        if args.self_test_only:
            print(json.dumps(clock.check(), indent=2)); return 0
        run_audit(args.run.expanduser().resolve(), args.primary_review.expanduser().resolve(), clock, args.repo.expanduser().resolve())
        return 0
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, csv.Error) as exc:
        print(f"STOP: {type(exc).__name__}: {exc}\nNo source-label repair, network or training action attempted.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
