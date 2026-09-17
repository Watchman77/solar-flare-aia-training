#!/usr/bin/env python3
"""17B follow-up: inspect cached event records and stored TAI clock evidence.

Standard library only. No network calls, package installs, Git commands, cloud
changes, source repair, deduplication, time-scale conversion, or model training.
Reads the completed Stage-1 database in SQLite read-only mode and the exact
cached event CSV recorded by that run. Writes NEW diagnostic reports only.

Examples:
  python3 ~/aia17_event_time_forensics.py
  python3 ~/aia17_event_time_forensics.py --run /path/to/completed/stage1/run
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import sys

VERSION = "aia17-event-time-forensics-v1"
RUN_ID = "20260915T005020436079Z"
EVENT_FIELDS = ("event_starttime", "event_peaktime", "event_endtime",
                "fl_goescls", "NOAA_AR_clean", "flux")
NA = {"", "nan", "none", "null", "nat", "na", "n/a"}
TAI_RE = re.compile(r"^(\d{4})\.(\d{2})\.(\d{2})_(\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?)_TAI$")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        obj = json.load(f)
    if not isinstance(obj, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return obj


def parse_clock(text: str | None):
    """Parse representation only. NEVER assume a naive clock is UTC."""
    text = (text or "").strip()
    if text.lower() in NA:
        return None, "missing"
    try:
        t = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None, "unparsed"
    if t.tzinfo is not None and t.utcoffset() is not None:
        return t.astimezone(timezone.utc), "explicit_offset"
    return t, "naive_unresolved_scale"


def audit_key(row: dict) -> str:
    """Reproduce the Stage-1 audit key; this is NOT a physical event ID."""
    return "|".join((row["NOAA_AR_clean"].strip(), row["event_starttime"].strip(),
                     row["event_peaktime"].strip(), row["fl_goescls"].strip().upper()))


def event_flags(row: dict) -> list[str]:
    clocks = {name: parse_clock(row[field]) for name, field in (
        ("start", "event_starttime"), ("peak", "event_peaktime"), ("end", "event_endtime"))}
    flags = [f"{name}_{kind}" for name, (t, kind) in clocks.items() if t is None]
    for first, second, bad in (("start", "peak", "peak_before_start"),
                               ("peak", "end", "end_before_peak"),
                               ("start", "end", "end_before_start")):
        t1, k1 = clocks[first]
        t2, k2 = clocks[second]
        if t1 is None or t2 is None:
            continue
        if k1 != k2:
            flags.append(f"{first}_{second}_representation_mismatch")
        elif t2 < t1:
            flags.append(bad)
    return flags


def read_events(spec: dict, expected_rows: int, db_events: dict) -> dict:
    path = Path(spec["local_path"]).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Cached event CSV missing: {path}. No download attempted.")
    if not 0 < path.stat().st_size <= 10 * 1024**2:
        raise ValueError("The cached event CSV exceeds this review's 10 MiB size guard or is empty.")
    if path.stat().st_size != int(spec["size_bytes"]):
        raise ValueError("Cached event CSV byte size differs from the run's source snapshot.")
    digest = sha256_file(path)
    if not spec.get("sha256") or digest != spec["sha256"]:
        raise ValueError("Cached event CSV SHA256 does not match the completed run. No repair attempted.")
    groups = defaultdict(list)
    anomaly_rows = []
    flags = Counter()
    parsed_kind_counts = {field: Counter() for field in EVENT_FIELDS[:3]}
    records = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, strict=True)
        columns = reader.fieldnames or []
        if len(set(columns)) != len(columns) or not set(EVENT_FIELDS).issubset(columns):
            raise ValueError("Event CSV headers do not meet the recorded schema.")
        for rownum, row in enumerate(reader, 1):
            if None in row or any(v is None for v in row.values()):
                raise ValueError(f"Malformed event CSV record {rownum}.")
            key = audit_key(row)
            if db_events.get(rownum) != key:
                raise ValueError(f"Event CSV record {rownum} does not match the Stage-1 database key.")
            reasons = event_flags(row)
            record = {"source_record_number": rownum, "csv_end_line": reader.line_num,
                      "audit_key": key, "flags": reasons, "raw": dict(row)}
            records.append(record)
            groups[key].append(record)
            flags.update(reasons)
            if reasons:
                anomaly_rows.append(record)
            for field in EVENT_FIELDS[:3]:
                parsed_kind_counts[field][parse_clock(row[field])[1]] += 1
    if len(records) != expected_rows or len(db_events) != len(records):
        raise ValueError("Event row count does not match the completed Stage-1 run/database.")
    duplicate_groups = []
    duplicate_rownums = set()
    for key, members in groups.items():
        if len(members) < 2:
            continue
        differing = [c for c in columns if len({r['raw'][c] for r in members}) > 1]
        duplicate_groups.append({"audit_key": key, "record_count": len(members),
            "all_exported_field_values_identical": not differing,
            "differing_exported_columns": differing, "records": members})
        duplicate_rownums.update(r["source_record_number"] for r in members)
    anomaly_rownums = {r["source_record_number"] for r in anomaly_rows}
    return {"source_path": str(path), "generation": spec["generation"],
        "source_sha256": digest, "record_count": len(records),
        "audit_key_fields": ["NOAA_AR_clean", "event_starttime", "event_peaktime", "fl_goescls"],
        "audit_key_note": "Whitespace stripped; class uppercased, as in Stage 1. End time and flux are NOT in the key. No physical event identity inferred.",
        "duplicate_group_count": len(duplicate_groups),
        "duplicate_excess_records": sum(g["record_count"] - 1 for g in duplicate_groups),
        "duplicate_groups": duplicate_groups, "event_time_flag_counts": dict(flags),
        "time_representation_counts": {k: dict(v) for k, v in parsed_kind_counts.items()},
        "time_anomaly_record_count": len(anomaly_rows), "time_anomaly_records": anomaly_rows,
        "records_in_both_duplicate_and_time_anomaly_sets": sorted(duplicate_rownums & anomaly_rownums),
        "distinct_records_flagged_for_any_reason": len(duplicate_rownums | anomaly_rownums)}


def compare_tai_clock(raw: str, stored: str):
    """Compare clock fields WITHOUT converting TAI to UTC."""
    match = TAI_RE.fullmatch((raw or "").strip())
    if not match:
        return "raw_TAI_format_not_supported", None
    try:
        clock = datetime.fromisoformat(f"{match[1]}-{match[2]}-{match[3]}T{match[4]}")
    except ValueError:
        return "raw_TAI_clock_unparsed", None
    t, kind = parse_clock(stored)
    if t is None:
        return "stored_clock_missing_or_unparsed", None
    if kind != "naive_unresolved_scale":
        return "stored_clock_has_offset_requires_scale_review", None
    delta = (t - clock).total_seconds()
    return ("same_clock_fields_as_raw_TAI" if delta == 0 else "different_clock_fields"), delta


def clock_review(conn: sqlite3.Connection, source: str) -> dict:
    counts = Counter()
    examples = []
    n = 0
    query = "SELECT rownum,raw_trec,t FROM records WHERE src=? ORDER BY rownum"
    for rownum, raw, t in conn.execute(query, (source,)):
        n += 1
        status, delta = compare_tai_clock(raw, t)
        counts[status] += 1
        if status != "same_clock_fields_as_raw_TAI" and len(examples) < 10:
            examples.append({"source_record_number": rownum, "raw_T_REC": raw,
                             "stored_T_REC_dt": t, "status": status,
                             "clock_field_difference_seconds": delta})
    if n == 0:
        raise ValueError(f"No records found for {source} in the completed database.")
    return {"source": source, "records_checked": n, "counts": dict(counts),
        "exceptions_preview": examples,
        "interpretation": "Tests stored clock fields against explicit raw TAI. Not a UTC conversion, observation-availability audit or certification of previous label joins."}


def baseline_review(conn: sqlite3.Connection) -> dict:
    for source in ("baseline_manifest", "curated_master"):
        n = conn.execute("""SELECT count(*) FROM (SELECT sid FROM records
            WHERE src=? AND sid IS NOT NULL GROUP BY sid HAVING count(*)>1)""", (source,)).fetchone()[0]
        if n:
            return {"status": "AMBIGUOUS_IDS_NO_INHERITANCE_CHECK", "source": source}
    counts = Counter()
    for row in conn.execute("""SELECT b.sid,b.t,b.harp,b.noaa,b.label,
             m.sid,m.t,m.harp,m.noaa,m.label,m.raw_trec
        FROM records b LEFT JOIN records m ON m.src='curated_master' AND m.sid=b.sid
        WHERE b.src='baseline_manifest'"""):
        counts["baseline_rows"] += 1
        if row[5] is None:
            counts["no_unique_master_match"] += 1
            continue
        if any(x is None for x in row[:10]):
            counts["unknown_identity_or_label_fields"] += 1
            continue
        if row[:5] != row[5:10]:
            counts["identity_label_or_stored_time_differs"] += 1
            continue
        status, _ = compare_tai_clock(row[10], row[1])
        counts["matched_with_raw_TAI_clock_evidence" if status == "same_clock_fields_as_raw_TAI"
               else "matched_but_clock_evidence_needs_review"] += 1
    return {"status": "REVIEW_ONLY_NO_COLUMNS_CREATED", "counts": dict(counts),
        "note": "Matched sample_id with matching HARP, NOAA, label and clock fields supplies lineage evidence. No IDs or object paths are changed; no physical UTC time is written."}


def run_review(run: Path, repo: Path) -> Path:
    report_path = run / "stage1_report.json"
    snapshot_path = run / "source_lock_snapshot.json"
    dbpath = run / "metadata_audit.sqlite"
    for p in (report_path, snapshot_path, dbpath):
        if not p.is_file():
            raise FileNotFoundError(f"Expected completed Stage-1 artifact missing: {p}")
    report = load_json(report_path)
    if report.get("status") != "STAGE1_COMPLETE_REVIEW_REQUIRED":
        raise ValueError("Input is not a completed Stage-1 report.")
    snapshot = load_json(snapshot_path)
    event_specs = [s for s in snapshot["sources"] if s["id"] == "events"]
    profiles = {p["source"]: p for p in report["source_profiles"]}
    if len(event_specs) != 1 or "events" not in profiles:
        raise ValueError("Expected exactly one pinned event source.")

    print("===== 17B EVENT/TIME FORENSICS =====", flush=True)
    print("Reading completed run:", run, flush=True)
    conn = sqlite3.connect(dbpath.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        conn.execute("PRAGMA query_only=ON")
        cols = {r[1] for r in conn.execute("PRAGMA table_info(records)")}
        if not {"src", "rownum", "sid", "raw_trec", "t", "harp", "noaa", "label"} <= cols:
            raise ValueError("Unexpected Stage-1 database schema.")
        db_events = dict(conn.execute("SELECT rownum,sid FROM records WHERE src='events'"))
        events = read_events(event_specs[0], int(profiles["events"]["rows"]), db_events)
        expected_duplicate = next((d for d in report["duplicate_audit"] if d.get("source") == "events"), None)
        if expected_duplicate and events["duplicate_group_count"] != expected_duplicate["duplicate_id_groups"]:
            raise ValueError("Event duplicate groups do not reproduce Stage 1.")
        clocks = []
        for source in ("curated_master", "extension", "sharp96"):
            print("Checking every stored/raw clock pair:", source, flush=True)
            result = clock_review(conn, source)
            if result["records_checked"] != profiles[source]["rows"]:
                raise ValueError(f"Database row count disagrees with report for {source}.")
            clocks.append(result)
        baseline = baseline_review(conn)
        support_cols = ["year_as_stored", "sample_rows", "positive_rows", "positive_harps", "positive_noaa_ids"]
        support = [dict(zip(support_cols, row)) for row in conn.execute("""
            SELECT substr(t,1,4),count(*),sum(CASE WHEN label=1 THEN 1 ELSE 0 END),
              count(DISTINCT CASE WHEN label=1 THEN harp END),
              count(DISTINCT CASE WHEN label=1 THEN noaa END)
            FROM records WHERE src='curated_master' AND t IS NOT NULL
            GROUP BY substr(t,1,4) ORDER BY substr(t,1,4)
        """)]
    finally:
        conn.close()

    uq_paths = ("docs/TRUSTWORTHY_RESEARCH_STANDARD.md", "docs/AIA_UQ_CALIBRATION_PROTOCOL.md",
                "configs/aia_uq_calibration_protocol.json")
    result = {"version": VERSION, "status": "FORENSIC_REVIEW_COMPLETE_NO_REPAIRS",
        "training_authorised": False, "source_run": str(run),
        "stage1_report_sha256": sha256_file(report_path),
        "source_lock_snapshot_sha256": sha256_file(snapshot_path),
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "events": events, "stored_TAI_clock_checks": clocks, "baseline_lineage_check": baseline,
        "positive_region_support": support,
        "positive_region_support_note": "Distinct identifiers, not independently certified events/AR groups. Stored years not yet recomputed in UTC. No split is selected.",
        "uq_protocol_file_presence": {p: (repo / p).is_file() for p in uq_paths},
        "uncleared_gates": [
          "Event catalogue provenance, completeness, source versions, units and availability delay.",
          "Expert/source review of flagged event rows; no automatic deduplication or timestamp sorting.",
          "Physical TAI/UTC conversion and label-window impact, before training.",
          "AIA observed timestamps versus forecast issue time and 180-second matching rule.",
          "Qualified history coverage, non-overlapping AR-safe development split with positive support.",
          "48-hour follow-up completeness and matched populations for calibration/UQ evaluation."]}
    # New reports only; never overwrite the Stage-1 run or any research source.
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    out = run.parent.parent / "reviews" / f"event_time_{stamp}"
    out.mkdir(parents=True, exist_ok=False)
    (out / "event_time_review.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    flagged = {}
    for group in events["duplicate_groups"]:
        for r in group["records"]:
            flagged[r["source_record_number"]] = {**r, "duplicate_group_member": True}
    for r in events["time_anomaly_records"]:
        flagged.setdefault(r["source_record_number"], {**r, "duplicate_group_member": False})
    with (out / "flagged_event_records.csv").open("w", encoding="utf-8", newline="") as f:
        fields = ["source_record_number", "duplicate_group_member", "flags"] + list(EVENT_FIELDS)
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for _, r in sorted(flagged.items()):
            writer.writerow({"source_record_number": r["source_record_number"],
                "duplicate_group_member": r["duplicate_group_member"], "flags": ";".join(r["flags"]),
                **{c: r["raw"][c] for c in EVENT_FIELDS}})
    notes = ["# 17B event/time forensic review", "", f"Source run: `{run.name}`", "",
        "This review reads frozen local audit artifacts. It does not change sources, labels, sample IDs, paths or splits.",
        "", f"Duplicate audit-key groups: {events['duplicate_group_count']}.",
        f"Duplicate excess records: {events['duplicate_excess_records']}.",
        f"Records with time flags: {events['time_anomaly_record_count']}.",
        f"Distinct flagged records: {events['distinct_records_flagged_for_any_reason']}.", "",
        "Audit key: NOAA_AR_clean, event_starttime, event_peaktime and uppercased fl_goescls. End time and flux are not in this key.",
        "An identical audit key is not proof of an identical physical event. Compare all exported fields and original catalogue entries.", "",
        "## Clock evidence", ""]
    for c in clocks:
        notes.append(f"- {c['source']}: {c['records_checked']:,} pairs; {json.dumps(c['counts'])}.")
    notes += ["", "Clock-field equality with a _TAI source is evidence of retained TAI clock fields, not a UTC conversion.",
        "The baseline's matched sample IDs can provide raw-time lineage, but originals must remain unchanged.", "",
        "## Research boundaries", "", "No development split is frozen. Earlier zero-positive candidate years remain unsuitable for validation-TSS selection under current labels.",
        "The catalogue's latest event is not proof of continuous coverage or full forecast follow-up.",
        "UQ, calibration, AR-group bootstrap and significance requirements remain in force; PINN/PIML stays separate.", "",
        "## Outstanding decisions", ""] + ["- " + g for g in result["uncleared_gates"]]
    (out / "event_time_review.md").write_text("\n".join(notes) + "\n", encoding="utf-8")

    print("\n===== FORENSIC RESULTS =====")
    print("Duplicate audit-key groups:", events["duplicate_group_count"])
    print("Excess records in those groups:", events["duplicate_excess_records"])
    for group in events["duplicate_groups"][:10]:
        print("\nDUPLICATE GROUP:", group["audit_key"])
        print("All exported fields identical:", group["all_exported_field_values_identical"])
        print("Differing fields:", group["differing_exported_columns"])
        for r in group["records"][:10]:
            print(json.dumps(r))
    print("\nEVENT TIME FLAG COUNTS:", events["event_time_flag_counts"])
    print("Time-flagged records:", events["time_anomaly_record_count"])
    print("Duplicate/time-flag overlap:", events["records_in_both_duplicate_and_time_anomaly_sets"])
    for r in events["time_anomaly_records"][:10]:
        print(json.dumps(r))
    print("\nALL-ROW CLOCK EVIDENCE:")
    for c in clocks:
        print(c["source"], c["records_checked"], json.dumps(c["counts"]))
        if c["exceptions_preview"]:
            print("Exceptions:", json.dumps(c["exceptions_preview"]))
    print("BASELINE LINEAGE:", json.dumps(baseline))
    print("\nPOSITIVE SUPPORT: stored year | positive rows | positive HARPs | positive NOAA IDs")
    for r in support:
        print(r["year_as_stored"], r["positive_rows"], r["positive_harps"], r["positive_noaa_ids"], sep=" | ")
    print("Distinct IDs are not yet independently certified event/group counts.")
    print("UQ FILE PRESENCE:", json.dumps(result["uq_protocol_file_presence"]))
    print("\nSTATUS: FORENSIC_REVIEW_COMPLETE_NO_REPAIRS")
    print("FULL REPORT:", out / "event_time_review.json")
    print("FLAGGED RECORDS:", out / "flagged_event_records.csv")
    print("RESEARCH NOTE:", out / "event_time_review.md")
    print("Original metadata, database, labels, IDs, paths and Git files were not changed.")
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", type=Path, default=Path.home() / "aia17_metadata_stage1" / "runs" / RUN_ID)
    p.add_argument("--repo", type=Path, default=Path.home() / "solar_flare_aia")
    args = p.parse_args()
    try:
        run_review(args.run.expanduser().resolve(), args.repo.expanduser().resolve())
        return 0
    except (OSError, ValueError, KeyError, TypeError, csv.Error, sqlite3.Error) as exc:
        print(f"STOP: {type(exc).__name__}: {exc}\nNo source repair or cloud action was attempted.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
