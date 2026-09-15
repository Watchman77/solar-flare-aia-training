"""AIA 17B, stage 1: bounded metadata staging and read-only source-content audit.

Python standard library only. No model training, NPZ downloads, source repair,
cloud writes, automatic Git commits, or paid-compute management.
Timestamp parsing reports representations; it does NOT convert TAI to UTC.
"""
from __future__ import annotations

import argparse
import base64
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
from typing import Any

VERSION = "17ab-metadata-stage1-v1"
GIB = 1024**3
MIB = 1024**2
NA = {"", "nan", "none", "null", "nat", "na", "n/a"}
PREFERRED = ["MEANGBZ", "MEANGAM", "MEANGBT", "MEANGBH", "MEANJZD",
             "TOTUSJZ", "MEANALP", "MEANJZH", "ABSNJZH", "SAVNCPP",
             "MEANSHR", "SHRGT45", "R_VALUE", "USFLUX", "TOTPOT", "TOTUSJH"]
OPTIONAL = ["MEANPOT", "AREA_ACR"]
EVENT_COLUMNS = ["event_starttime", "event_peaktime", "event_endtime",
                 "fl_goescls", "NOAA_AR_clean", "flux"]


def dump_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def number(value: Any) -> float | None:
    try:
        out = float(clean(value))
        return out if math.isfinite(out) else None
    except (TypeError, ValueError):
        return None


def integer(value: Any) -> str | None:
    out = number(value)
    return str(int(out)) if out is not None and out.is_integer() else None


def label_value(value: Any) -> int | None:
    out = number(value)
    return int(out) if out in (0.0, 1.0) else None


def parsed_clock(value: Any) -> tuple[str | None, float | None, int | None, str]:
    """Parse ISO-like clocks WITHOUT assigning a timescale to timezone-naive data.

    Explicit offsets are normalised to UTC. A naive clock remains naive. The
    numeric tick is for same-representation diagnostics, never a TAI/UTC join.
    """
    text = clean(value)
    if text.lower() in NA:
        return None, None, None, "missing"
    try:
        stamp = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None, None, None, "unparsed"
    year = stamp.year
    if stamp.tzinfo is not None and stamp.utcoffset() is not None:
        stamp = stamp.astimezone(timezone.utc)
        tick = stamp.timestamp()
        return stamp.isoformat(), tick, year, "explicit_offset"
    tick = (stamp - datetime(1970, 1, 1)).total_seconds()
    return stamp.isoformat(), tick, year, "naive_unresolved_scale"


def raw_time_tag(value: Any) -> str:
    text = clean(value).upper()
    if not text:
        return "missing"
    if "TAI" in text:
        return "TAI_tag"
    if "UTC" in text or text.endswith("Z"):
        return "UTC_tag_or_Z"
    return "unlabelled"


def hash_file(path: Path) -> dict[str, str]:
    sha = hashlib.sha256()
    md5 = hashlib.md5()  # Integrity check, not cryptographic authentication.
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(4 * MIB), b""):
            sha.update(block)
            md5.update(block)
    return {"sha256": sha.hexdigest(), "md5_base64": base64.b64encode(md5.digest()).decode()}


def gcloud(*args: str, project: str, timeout: int = 180, capture: bool = True):
    env = dict(os.environ, CLOUDSDK_CORE_DISABLE_PROMPTS="1")
    cmd = ["gcloud", *args, f"--project={project}"]
    result = subprocess.run(cmd, env=env, timeout=timeout, text=True,
                            stdout=subprocess.PIPE if capture else None,
                            stderr=subprocess.PIPE if capture else None)
    if result.returncode:
        msg = (result.stderr or "See gcloud output above.").strip()
        raise RuntimeError(f"gcloud exited {result.returncode}: {msg}")
    return result.stdout if capture else None


def stage_sources(config: dict, work: Path) -> dict:
    """Pin five exact CSV objects and stage generation-specific local copies.

    A fixed total-size cap is checked before ANY full-object transfer. A local
    cache is reused only when its checksum agrees with recorded provenance.
    """
    if shutil.which("gcloud") is None:
        raise RuntimeError("gcloud is not available. Run this stage in the restored Cloud Shell.")
    cache = work / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    lock_path = work / "source_lock.json"
    if lock_path.exists():
        lock = json.loads(lock_path.read_text())
        expected = {s["id"]: s["uri"] for s in config["sources"]}
        actual = {s["id"]: s["uri"] for s in lock["sources"]}
        if expected != actual or lock["project"] != config["project"]:
            raise RuntimeError("Existing source lock differs from config. Use a new --work directory.")
        print("Reusing recorded object generations; no silent switch to newer data.", flush=True)
    else:
        entries = []
        for spec in config["sources"]:
            print("Metadata:", spec["id"], flush=True)
            meta = json.loads(gcloud("storage", "objects", "describe", spec["uri"],
                                     "--raw", "--format=json", project=config["project"]))
            if str(meta.get("contentEncoding", "")).lower() not in ("", "identity"):
                raise RuntimeError(f"Unexpected content encoding for {spec['id']}; no download attempted.")
            size = int(meta["size"])
            if size <= 0 or size > spec["max_bytes"]:
                raise RuntimeError(f"Object-size guard failed for {spec['id']}: {size:,} bytes.")
            generation = str(meta["generation"])
            if not generation.isdecimal():
                raise RuntimeError("Unexpected object generation.")
            entries.append({**spec, "size_bytes": size, "generation": generation,
                            "version_uri": f"{spec['uri']}#{generation}",
                            "local_path": str(cache / f"{spec['id']}_{generation}.csv"),
                            "object_metadata": meta})
        lock = {"version": VERSION, "project": config["project"],
                "created_utc": datetime.now(timezone.utc).isoformat(), "sources": entries}
        # Only write the source lock after validating the complete request.
        total = sum(e["size_bytes"] for e in entries)
        if total > config["max_total_source_bytes"]:
            raise RuntimeError(f"Total metadata {total / MIB:.1f} MiB exceeds the configured cap.")
        dump_json(lock_path, lock)

    total = sum(e["size_bytes"] for e in lock["sources"])
    if total > config["max_total_source_bytes"]:
        raise RuntimeError("Pinned source total exceeds the current configured cap.")
    missing = sum(e["size_bytes"] for e in lock["sources"] if not Path(e["local_path"]).exists())
    free = shutil.disk_usage(work).free
    reserve = int(config["disk_reserve_bytes"])
    print(f"Source total: {total / MIB:.2f} MiB; free disk: {free / GIB:.2f} GiB", flush=True)
    if free < missing + reserve:
        raise RuntimeError("Not enough free disk for missing sources plus the scratch-space reserve.")

    for entry in lock["sources"]:
        path = Path(entry["local_path"])
        existed = path.exists()
        part = path.with_suffix(".csv.part")
        if not existed:
            if part.exists():
                raise RuntimeError(f"An interrupted download remains at {part}. Keep it; inspect before retrying.")
            print(f"Downloading {entry['id']} ({entry['size_bytes'] / MIB:.2f} MiB)", flush=True)
            gcloud("storage", "cp", "--do-not-decompress", entry["version_uri"], str(part),
                   project=config["project"], timeout=1200, capture=False)
            candidate = part
        else:
            print("Checking cached file:", entry["id"], flush=True)
            candidate = path
        if candidate.stat().st_size != entry["size_bytes"]:
            raise RuntimeError(f"Byte-size mismatch for {candidate}; file has NOT been accepted.")
        hashes = hash_file(candidate)
        expected_md5 = entry["object_metadata"].get("md5Hash")
        if expected_md5 and hashes["md5_base64"] != expected_md5:
            raise RuntimeError(f"MD5 mismatch for {candidate}; file has NOT been accepted.")
        if existed and entry.get("sha256") != hashes["sha256"]:
            raise RuntimeError(f"Cached file lacks matching SHA256 provenance: {path}.")
        if not existed:
            part.rename(path)
        entry.update(hashes)
        entry["transport_validation"] = "gcloud cp checksum validation plus local size/SHA256; MD5 compared when supplied"
        dump_json(lock_path, lock)
    return lock


def ingest_source(conn: sqlite3.Connection, spec: dict, out: Path) -> dict:
    path = Path(spec["local_path"])
    source_id = spec["id"]
    profile = {"source": source_id, "uri": spec.get("uri", "synthetic_fixture"),
               "rows": 0, "time_kinds": Counter(), "raw_T_REC_tags": Counter(),
               "feature_counts": {}, "year_counts": {}, "time_examples": [],
               "label_present": False, "role": spec["role"], "invalid_times": 0,
               "invalid_harp": 0, "invalid_noaa": 0, "blank_sample_ids": 0,
               "raw_quality_counts_top": {}, "label_invalid": 0, "label_missing": 0,
               "event_class_counts": Counter(), "event_time_issues": Counter()}
    quality = Counter()
    years = defaultdict(Counter)
    sample_minmax = defaultdict(lambda: [None, None])
    event_minmax = defaultdict(lambda: [None, None])
    buffer = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = reader.fieldnames or []
        if not columns or len(set(columns)) != len(columns):
            raise ValueError(f"Missing or duplicate CSV headers: {source_id}.")
        required = EVENT_COLUMNS if spec["role"] == "event_catalogue" else ["T_REC_dt", "HARPNUM"]
        if spec["role"] in ("curated_targets", "baseline_manifest", "extension_targets"):
            required += ["sample_id", "NOAA_AR_clean", "label_48h_final"]
        absent = sorted(set(required) - set(columns))
        if absent:
            raise ValueError(f"{source_id} lacks required columns: {absent}")
        profile["columns"] = columns
        profile["label_present"] = "label_48h_final" in columns
        features = [c for c in PREFERRED + OPTIONAL if c in columns]
        feature_counts = {f: Counter() for f in features}
        for row in reader:
            if None in row or any(v is None for v in row.values()):
                raise ValueError(f"Malformed CSV row near {reader.line_num} in {source_id}.")
            profile["rows"] += 1
            idx = profile["rows"]
            is_event = spec["role"] == "event_catalogue"
            raw_t = row.get("event_starttime" if is_event else "T_REC_dt", "")
            t, tick, year, kind = parsed_clock(raw_t)
            profile["time_kinds"][kind] += 1
            profile["raw_T_REC_tags"][raw_time_tag(row.get("T_REC"))] += 1
            if year is None:
                profile["invalid_times"] += 1
            bucket = str(year) if year is not None else "INVALID"
            years[bucket]["rows"] += 1
            if t is not None:
                pair = sample_minmax[kind]
                pair[0] = t if pair[0] is None else min(pair[0], t)
                pair[1] = t if pair[1] is None else max(pair[1], t)
            if len(profile["time_examples"]) < 4:
                profile["time_examples"].append({"T_REC": row.get("T_REC"),
                    "T_REC_dt": row.get("T_REC_dt"), "event_starttime": row.get("event_starttime"),
                    "parsed_kind": kind})
            raw_sid = clean(row.get("sample_id"))
            sid = raw_sid if raw_sid.lower() not in NA else None
            if "sample_id" in columns and sid is None:
                profile["blank_sample_ids"] += 1
            harp = integer(row.get("HARPNUM"))
            noaa = integer(row.get("NOAA_AR_clean"))
            if "HARPNUM" in columns and (harp is None or int(harp) <= 0):
                profile["invalid_harp"] += 1
                harp = None
            if "NOAA_AR_clean" in columns and (noaa is None or int(noaa) <= 0):
                profile["invalid_noaa"] += 1
                noaa = None
            label = label_value(row.get("label_48h_final")) if profile["label_present"] else None
            if profile["label_present"]:
                raw_label = clean(row.get("label_48h_final"))
                if label is None:
                    missing_label = raw_label.lower() in NA
                    profile["label_missing" if missing_label else "label_invalid"] += 1
                    years[bucket]["missing_labels" if missing_label else "invalid_labels"] += 1
                else:
                    years[bucket]["positives" if label else "negatives"] += 1
            for f in features:
                value = clean(row[f])
                status = "finite" if number(value) is not None else ("missing" if value.lower() in NA else "nonfinite_or_nonnumeric")
                feature_counts[f][status] += 1
            if "QUALITY" in columns:
                quality[clean(row["QUALITY"])] += 1
            if is_event:
                cls = clean(row["fl_goescls"]).upper()
                matched = re.fullmatch(r"([ABCMX])\s*(?:\d+(?:\.\d*)?|\.\d+)", cls)
                family = matched.group(1) if matched else "UNPARSED_OR_MISSING"
                profile["event_class_counts"][family] += 1
                years[bucket][f"class_{family}"] += 1
                pt, pk, _, p_kind = parsed_clock(row["event_peaktime"])
                et, ek, _, e_kind = parsed_clock(row["event_endtime"])
                for name, x, kval in (("peak", pt, p_kind), ("end", et, e_kind)):
                    if x is None:
                        profile["event_time_issues"][f"missing_or_invalid_{name}"] += 1
                    else:
                        pair = event_minmax[f"{name}_{kval}"]
                        pair[0] = x if pair[0] is None else min(pair[0], x)
                        pair[1] = x if pair[1] is None else max(pair[1], x)
                if tick is not None and pk is not None:
                    if kind != p_kind:
                        profile["event_time_issues"]["start_peak_representation_mismatch"] += 1
                    elif pk < tick:
                        profile["event_time_issues"]["peak_before_start"] += 1
                if pk is not None and ek is not None:
                    if p_kind != e_kind:
                        profile["event_time_issues"]["peak_end_representation_mismatch"] += 1
                    elif ek < pk:
                        profile["event_time_issues"]["end_before_peak"] += 1
                # An audit identity, NOT a claim that every matching key is one event.
                sid = "|".join([clean(row["NOAA_AR_clean"]), clean(row["event_starttime"]),
                                clean(row["event_peaktime"]), cls])
            buffer.append((source_id, idx, sid, harp, noaa, t, tick, kind, label,
                           clean(row.get("gcp_path")), clean(row.get("T_REC"))))
            if len(buffer) >= 10000:
                conn.executemany("INSERT INTO records VALUES (?,?,?,?,?,?,?,?,?,?,?)", buffer)
                buffer.clear()
            if idx % 100000 == 0:
                print(f"  {source_id}: {idx:,} rows inspected", flush=True)
        if buffer:
            conn.executemany("INSERT INTO records VALUES (?,?,?,?,?,?,?,?,?,?,?)", buffer)
    conn.commit()
    profile["year_counts"] = {y: dict(c) for y, c in sorted(years.items())}
    profile["feature_counts"] = {f: dict(c) for f, c in feature_counts.items()}
    profile["time_ranges_by_representation"] = dict(sample_minmax)
    profile["event_peak_end_ranges"] = dict(event_minmax)
    profile["raw_quality_counts_top"] = dict(quality.most_common(10))
    profile["raw_quality_distinct"] = len(quality)
    # No QUALITY, longitude, or finite-feature filtering is silently applied here.
    print(f"  Finished {source_id}: {profile['rows']:,} rows", flush=True)
    return profile


def duplicate_audit(conn: sqlite3.Connection, source_id: str) -> dict:
    def count(sql: str) -> int:
        return int(conn.execute(sql, (source_id,)).fetchone()[0])
    return {
        "source": source_id,
        "duplicate_id_groups": count("SELECT count(*) FROM (SELECT sid FROM records WHERE src=? AND sid IS NOT NULL GROUP BY sid HAVING count(*)>1)"),
        "duplicate_id_excess_rows": count("SELECT coalesce(sum(n-1),0) FROM (SELECT count(*) n FROM records WHERE src=? AND sid IS NOT NULL GROUP BY sid HAVING count(*)>1)"),
        "conflicting_label_id_groups": count("SELECT count(*) FROM (SELECT sid FROM records WHERE src=? AND sid IS NOT NULL GROUP BY sid HAVING count(DISTINCT label)>1)"),
        "duplicate_harp_time_groups": count("SELECT count(*) FROM (SELECT harp,t,kind FROM records WHERE src=? AND harp IS NOT NULL AND t IS NOT NULL GROUP BY harp,t,kind HAVING count(*)>1)"),
    }


def compare_unique_ids(conn: sqlite3.Connection, left: str, right: str) -> dict:
    """Compare only unambiguous IDs, with explicit unknown-vs-mismatch counts."""
    conn.execute("DROP TABLE IF EXISTS lhs")
    conn.execute("DROP TABLE IF EXISTS rhs")
    for name, source in (("lhs", left), ("rhs", right)):
        conn.execute(f"CREATE TEMP TABLE {name} AS SELECT * FROM records WHERE src=? AND sid IN (SELECT sid FROM records WHERE src=? AND sid IS NOT NULL GROUP BY sid HAVING count(*)=1)", (source, source))
        conn.execute(f"CREATE UNIQUE INDEX {name}_sid ON {name}(sid)")
    result = {"left_source": left, "right_source": right,
              "comparison_scope": "IDs unique within each table only; no duplicate resolution or label repair"}
    result["left_unique_id_rows"] = conn.execute("SELECT count(*) FROM lhs").fetchone()[0]
    result["right_unique_id_rows"] = conn.execute("SELECT count(*) FROM rhs").fetchone()[0]
    result["matched_ids"] = conn.execute("SELECT count(*) FROM lhs JOIN rhs USING(sid)").fetchone()[0]
    result["left_without_unambiguous_right_match"] = conn.execute("SELECT count(*) FROM lhs LEFT JOIN rhs USING(sid) WHERE rhs.sid IS NULL").fetchone()[0]
    for column in ("label", "harp", "noaa", "t"):
        result[column + "_mismatches"] = conn.execute(f"SELECT count(*) FROM lhs a JOIN rhs b USING(sid) WHERE a.{column} IS NOT NULL AND b.{column} IS NOT NULL AND a.{column} != b.{column}").fetchone()[0]
        result[column + "_unknown_comparisons"] = conn.execute(f"SELECT count(*) FROM lhs a JOIN rhs b USING(sid) WHERE a.{column} IS NULL OR b.{column} IS NULL").fetchone()[0]
    result["timestamp_note"] = "Comparison is representation-level only; timescale provenance remains unresolved."
    return result


def cadence_audit(conn: sqlite3.Connection) -> dict:
    """Profile distinct raw SHARP clocks, not a qualified sequence-coverage pass."""
    rows = conn.execute("""
        WITH pts AS (
          SELECT DISTINCT harp,kind,tick FROM records
          WHERE src='sharp96' AND harp IS NOT NULL AND tick IS NOT NULL
        ), gaps AS (
          SELECT tick-lag(tick) OVER (PARTITION BY harp,kind ORDER BY tick) AS gap FROM pts
        )
        SELECT round(gap,3), count(*) FROM gaps WHERE gap>0
        GROUP BY round(gap,3) ORDER BY count(*) DESC LIMIT 12
    """).fetchall()
    return {"basis": "Distinct timestamps per HARP within one timestamp representation; no quality filtering",
            "most_common_positive_gaps_seconds": [{"gap_seconds": g, "count": n} for g, n in rows],
            "note": "Not an AIA-sequence coverage or leakage certification. TAI/UTC not resolved."}


def run_audit(lock: dict, config: dict, out: Path) -> dict:
    out.mkdir(parents=True, exist_ok=False)
    dbpath = out / "metadata_audit.sqlite"
    conn = sqlite3.connect(dbpath)
    conn.execute("PRAGMA cache_size=-32768")
    conn.execute("PRAGMA temp_store=FILE")
    conn.execute("CREATE TABLE records(src TEXT, rownum INTEGER, sid TEXT, harp TEXT, noaa TEXT, t TEXT, tick REAL, kind TEXT, label INTEGER, gcp_path TEXT, raw_trec TEXT)")
    sources = []
    try:
        for spec in lock["sources"]:
            print("\nAuditing:", spec["id"], flush=True)
            sources.append(ingest_source(conn, spec, out))
        conn.execute("CREATE INDEX rec_sid ON records(src,sid)")
        conn.execute("CREATE INDEX rec_harp_clock ON records(src,harp,kind,tick)")
        duplicates = [duplicate_audit(conn, s["source"]) for s in sources]
        comparisons = [compare_unique_ids(conn, "extension", "curated_master"),
                       compare_unique_ids(conn, "baseline_manifest", "curated_master")]
        cadence = cadence_audit(conn)
        counts = []
        features = []
        for p in sources:
            for year, c in p["year_counts"].items():
                counts.append({"source": p["source"], "year_as_stored": year, **c,
                    "label_present": p["label_present"],
                    "interpretation": "Unfiltered source rows, not verified AIA sample coverage"})
            if p["role"] not in ("event_catalogue", "baseline_manifest"):
                for f in PREFERRED + OPTIONAL:
                    features.append({"source": p["source"], "feature": f,
                        "column_present": f in p["columns"],
                        **p["feature_counts"].get(f, {})})
        findings = []
        for p in sources:
            if p["rows"] == 0:
                findings.append({"severity": "BLOCKER", "source": p["source"], "issue": "empty_source", "count": 0})
            for key in ("invalid_times", "blank_sample_ids", "invalid_harp", "invalid_noaa", "label_invalid", "label_missing"):
                if p[key]:
                    findings.append({"severity": "REVIEW_REQUIRED", "source": p["source"], "issue": key, "count": p[key]})
        for d in duplicates:
            for key in ("duplicate_id_groups", "conflicting_label_id_groups", "duplicate_harp_time_groups"):
                if d[key]:
                    findings.append({"severity": "REVIEW_REQUIRED", "source": d["source"], "issue": key, "count": d[key]})
        for comparison in comparisons:
            for key, value in comparison.items():
                if (key.endswith("_mismatches") or key.endswith("_unknown_comparisons") or key == "left_without_unambiguous_right_match") and value:
                    findings.append({"severity": "REVIEW_REQUIRED", "source": comparison["left_source"] + " vs " + comparison["right_source"], "issue": key, "count": value})
        blockers = [
            "Cross-cycle AIA object/manifest reconciliation and actual image timestamps not yet audited.",
            "TAI/UTC provenance and availability-time conversion must be established before cross-instrument joins.",
            "Exact date splits, forecast-window purge and AR-group overlap policy are not frozen.",
            "Qualified SHARP/AIA 6h/12h/24h history coverage and missingness policy remain to be audited.",
            "GOES catalogue completeness, units, reporting delay and feature availability have not been verified.",
            "2025-2026 extension comparison does not authorise automatic concatenation or source-label repair.",
            "Source-label lineage and complete 48h follow-up coverage (right-censoring) remain to be verified.",
            "HMI magnetic-image coverage and checkpoint loadability have not been tested.",
        ]
        report = {"version": VERSION, "stage": "17B_stage1_metadata_content", "status": "STAGE1_COMPLETE_REVIEW_REQUIRED",
            "training_authorised": False, "source_profiles": sources, "duplicate_audit": duplicates,
            "identity_comparisons": comparisons, "raw_sharp96_cadence": cadence,
            "findings": findings, "remaining_training_gates": blockers,
            "created_utc": datetime.now(timezone.utc).isoformat()}
        dump_json(out / "stage1_report.json", report)
        dump_json(out / "source_lock_snapshot.json", lock)
        dump_json(out / "protocol_snapshot.json", config)
        year_cols = ["source", "year_as_stored", "rows", "label_present", "positives", "negatives", "missing_labels", "invalid_labels"] + [f"class_{c}" for c in ("A", "B", "C", "M", "X", "UNPARSED_OR_MISSING")] + ["interpretation"]
        write_csv(out / "source_year_counts.csv", counts, year_cols)
        write_csv(out / "feature_availability.csv", features, ["source", "feature", "column_present", "finite", "missing", "nonfinite_or_nonnumeric"])
        write_csv(out / "duplicate_audit.csv", duplicates, list(duplicates[0]))
        write_csv(out / "identity_comparisons.csv", comparisons, list(comparisons[0]))
        write_csv(out / "findings.csv", findings, ["severity", "source", "issue", "count"])
        lines = ["# 17B stage 1 — metadata content audit", "", "Status: STAGE1_COMPLETE_REVIEW_REQUIRED", "",
            "**No training is authorised by this report. No labels or source files were repaired.**", "",
            "## Source rows (not verified image sample counts)", "", "| Source | Rows | Official label column |", "|---|---:|---|"]
        for p in sources:
            lines.append(f"| {p['source']} | {p['rows']:,} | {p['label_present']} |")
        lines += ["", "## Overlap and identity checks", ""]
        for c in comparisons:
            lines += [f"### {c['left_source']} versus {c['right_source']}", "", "```json", json.dumps(c, indent=2), "```", ""]
        events = next(p for p in sources if p["source"] == "events")
        lines += ["## Event families actually observed", "", json.dumps(dict(events["event_class_counts"])), "",
            "A zero C-class count does not establish a C-quiet period. Catalogue completeness is unverified.",
            "Peak class/peak flux cannot be treated as known before the peak; end information cannot be used before the end. Reporting delays remain unresolved.", "",
            "## Findings", "", f"{len(findings)} nonzero issues require review. See findings.csv.", "",
            "## Remaining gates", ""] + ["- " + b for b in blockers]
        lines += ["", "## Diagnostic limits", "", "Naive timestamps remain naive. No TAI-to-UTC conversion was performed. Annual summaries use the year in the parsed source representation. This stage deliberately does not produce model tensors, imputed features, trained models, or test metrics.", ""]
        (out / "stage1_summary.md").write_text("\n".join(lines), encoding="utf-8")
        print("\n===== 17B STAGE 1 RESULTS =====")
        for p in sources:
            print(f"{p['source']}: {p['rows']:,} rows | time representations: {dict(p['time_kinds'])}")
        print("\n===== SOURCE YEAR COUNTS (NOT AIA COMPLETENESS) =====")
        for r in counts:
            desc = f"{r['source']:18} {r['year_as_stored']:7} rows={r['rows']:8,}"
            if r["label_present"]:
                desc += f" positives={r.get('positives',0):6,} invalid/missing={r.get('invalid_labels',0)+r.get('missing_labels',0)}"
            print(desc)
        print("\n===== EXTENSION AND BASELINE CHECKS =====")
        for c in comparisons:
            print(json.dumps(c, indent=2))
        print("Event classes:", dict(events["event_class_counts"]))
        print("Preferred SHARP columns missing:", [f for f in PREFERRED if f not in next(p for p in sources if p["source"] == "sharp96")["columns"]])
        print("Issues requiring review:", len(findings))
        print("STAGE1_COMPLETE_REVIEW_REQUIRED — NO TRAINING RUN")
        print("SUMMARY:", out / "stage1_summary.md")
        print("FULL REPORT:", out / "stage1_report.json")
        return report
    except Exception as exc:
        dump_json(out / "stage1_failure.json", {"status": "FAILED", "training_authorised": False,
            "error_type": type(exc).__name__, "error": str(exc),
            "finished_source_profiles": sources})
        raise
    finally:
        conn.close()


def check_protocol(config: dict) -> None:
    assert config["label"] == "label_48h_final"
    assert config["forecast_horizon_hours"] == 48
    assert config["aia_channels_angstrom"] == [94, 131, 171, 193, 211, 335]
    assert config["aia_source_cadence_minutes"] == 96
    assert config["aia_time_tolerance_seconds"] == 180
    assert config["split_status"] == "PROPOSED_NOT_FROZEN"
    groups = config["proposed_date_roles"]
    values = [set(years) for years in groups.values()]
    for i, a in enumerate(values):
        for b in values[i + 1:]:
            if a & b:
                raise ValueError("Proposed date-role years overlap.")
    if any("12MIN" in s["uri"] or not s["uri"].endswith(".csv") for s in config["sources"]):
        raise ValueError("This stage permits only the specified small CSVs; 12-minute bulk source is excluded.")


def run_pipeline(repo: Path, work: Path) -> Path:
    config = json.loads((repo / "configs/aia17_metadata_stage1.json").read_text())
    check_protocol(config)
    work.mkdir(parents=True, exist_ok=True)
    runlock = work / ".running.lock"
    try:
        fd = os.open(runlock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise RuntimeError(f"A run lock exists at {runlock}. Check for an active run before removing it.")
    os.write(fd, f"pid={os.getpid()}\n".encode())
    os.close(fd)
    try:
        source_lock = stage_sources(config, work)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        out = work / "runs" / stamp
        run_audit(source_lock, config, out)
        commit = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                                capture_output=True, text=True, timeout=20)
        run_manifest = {"version": VERSION, "python": sys.version,
            "sqlite": sqlite3.sqlite_version, "repository_path": str(repo),
            "git_head": commit.stdout.strip() if commit.returncode == 0 else "unavailable",
            "helper_sha256": hash_file(Path(__file__))["sha256"],
            "config_sha256": hash_file(repo / "configs/aia17_metadata_stage1.json")["sha256"],
            "training_authorised": False,
            "execution_note": "CLI/helper execution; notebook files are not falsely marked executed."}
        dump_json(out / "execution_manifest.json", run_manifest)
        (work / "latest_report_path.txt").write_text(str(out) + "\n")
        return out
    finally:
        runlock.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.home() / "solar_flare_aia")
    parser.add_argument("--work", type=Path, default=Path.home() / "aia17_metadata_stage1")
    args = parser.parse_args()
    try:
        run_pipeline(args.repo.expanduser().resolve(), args.work.expanduser().resolve())
        return 0
    except Exception as exc:
        print(f"\nSTOP — {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
