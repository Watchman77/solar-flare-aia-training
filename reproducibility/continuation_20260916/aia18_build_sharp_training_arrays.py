#!/usr/bin/env python3
"""Prepare unscaled three-slot SHARP arrays for the existing broader Cycle-24 proposal.

No training, imputation, scaling, test-array construction, cloud or Git operation.
Input source tables, candidate identities, original labels and split proposal stay
unchanged. Output completeness flags are engineering checks, not science clearance.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import sys
import zipfile

import numpy as np

VERSION = "18a-cycle24-raw-sharp-three-slot-arrays-v1"
STATUS = "CYCLE24_SHARP_ARRAYS_BUILT_NO_TRAINING_OR_CLEARANCE"
PROPOSAL_STATUS = "BROAD_CYCLE24_FIT_PROPOSAL_BUILT_NOT_FROZEN"
INDEX_STATUS = "TEMPORAL_INDEX_BUILT_TIMING_AND_LABEL_CLEARANCE_PENDING"
FIT = "cycle24_final_refit_pool"
CAL = "cycle24_calibration_holdout"
THR = "cycle24_threshold_holdout"
ROLES = (FIT, CAL, THR)
LAGS = (288, 192, 96)
FEATURES = ("MEANGBZ", "MEANGAM", "MEANGBT", "MEANGBH", "MEANJZD",
            "TOTUSJZ", "MEANALP", "MEANJZH", "ABSNJZH", "SAVNCPP",
            "MEANSHR", "SHRGT45", "R_VALUE", "USFLUX", "TOTPOT")
SID = re.compile(r"(\d{8}_\d{4})_HARP(\d+)_NOAA(\d+)")
TAI = re.compile(r"(\d{4})\.(\d{2})\.(\d{2})_(\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?)_TAI")
MAX_FILE = 400 * 1024**2
MAX_ROWS = 250000


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(4 * 1024**2), b""):
            h.update(chunk)
    return h.hexdigest()


def regular(path, max_bytes=MAX_FILE):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), f"Missing or symlinked input: {path}")
    require(0 < path.stat().st_size <= max_bytes, f"Input size outside limit: {path}")
    return path


def load_json(path):
    data = json.loads(regular(path, 32 * 1024**2).read_text(encoding="utf-8"))
    require(isinstance(data, dict), f"JSON object required: {path}")
    return data


def write_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def verified(path, expected):
    regular(path)
    require(re.fullmatch(r"[0-9a-f]{64}", str(expected)) is not None, f"Missing hash: {path}")
    require(sha(path) == expected, f"Checksum differs: {path}; no automatic replacement.")
    return expected


def bundle_files(folder, expected_status, names):
    marker_path = folder / "COMPLETE.json"
    marker = load_json(marker_path)
    require(marker.get("status") == expected_status, f"Unexpected completion status: {folder}")
    locks = {str(marker_path): sha(marker_path)}
    for name in names:
        locks[str(folder / name)] = verified(folder / name, marker.get("output_sha256", {}).get(name))
    return locks


def csv_rows(path, required):
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f, strict=True)
        cols = r.fieldnames or []
        require(len(cols) == len(set(cols)) and set(required) <= set(cols), f"CSV schema mismatch: {path}")
        for row in r:
            require(None not in row and all(v is not None for v in row.values()), f"Malformed CSV record: {path}:{r.line_num}")
            yield row


def flag(value):
    require(str(value) in ("0", "1"), f"Expected binary indicator, got {value!r}")
    return int(value)


def int_id(value):
    text = str(value).strip()
    require(re.fullmatch(r"\d+(?:\.0+)?", text) is not None, f"Invalid region identifier: {value!r}")
    return int(text.split(".")[0])


def tick(raw):
    m = TAI.fullmatch(str(raw))
    require(m is not None, f"Explicit TAI required for this join: {raw!r}")
    value = datetime.fromisoformat(f"{m[1]}-{m[2]}-{m[3]}T{m[4]}")
    d = value - datetime(1970, 1, 1)
    return (d.days * 86400 + d.seconds) * 1000000 + d.microseconds


def load_roles(path, report):
    selected = {}
    seen = set()
    totals = Counter()
    positives = Counter()
    owners = {}
    n = 0
    required = ("target_sample_id", "issue_utc", "stored_year", "HARPNUM", "NOAA_AR_clean",
                "original_label_48h_final", "region_component_id", "proposed_final_role",
                "structural_candidate", "exclusion_reasons", "training_authorised")
    for row in csv_rows(path, required):
        n += 1
        require(n <= MAX_ROWS, "Role table row cap exceeded.")
        sid = row["target_sample_id"]
        require(sid not in seen, f"Duplicate target in role assignment: {sid}")
        seen.add(sid)
        if row["proposed_final_role"] not in ROLES or not flag(row["structural_candidate"]):
            continue
        m = SID.fullmatch(sid)
        require(m is not None, f"Unsupported ID: {sid}")
        require((int_id(row["HARPNUM"]), int_id(row["NOAA_AR_clean"])) == (int(m[2]), int(m[3])), "Role/ID region mismatch.")
        require(row["issue_utc"].endswith("Z"), "Canonical issue UTC required.")
        issue = datetime.fromisoformat(row["issue_utc"].replace("Z", "+00:00"))
        require(datetime(2010, 1, 1, tzinfo=timezone.utc) <= issue < datetime(2019, 12, 1, tzinfo=timezone.utc), "Non-Cycle-24 proposal target selected.")
        require(not row["exclusion_reasons"], "Retained role row still has exclusions.")
        require(row["training_authorised"].lower() in ("false", "0"), "Role file unexpectedly grants training clearance.")
        label = flag(row["original_label_48h_final"])
        role, group = row["proposed_final_role"], row["region_component_id"]
        require(bool(group) and (group not in owners or owners[group] == role), "Region component shared across final roles.")
        owners[group] = role
        row = dict(row, array_row=len(selected))
        selected[sid] = row
        totals[role] += 1
        positives[role] += label
    require(n == report["target_rows_preserved"], "Role count disagrees with proposal report.")
    expected = {r["role"]: r for r in report["role_support"]}
    for role in ROLES:
        require(totals[role] == expected[role]["retained"] and positives[role] == expected[role]["positive"], f"Support disagrees for {role}.")
    require(bool(selected), "No retained Cycle-24 candidates.")
    return selected


def requested_slots(path, selected, expected_rows):
    requests, frames_by_target, seen = {}, {}, set()
    n = 0
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            require(len(line) < 128 * 1024, "Unexpectedly long candidate record.")
            rec = json.loads(line)
            n += 1
            require(n <= MAX_ROWS, "Candidate row cap exceeded.")
            sid = rec["target_sample_id"]
            require(sid not in seen, "Duplicate candidate ID.")
            seen.add(sid)
            if sid not in selected:
                continue
            s = selected[sid]
            harp, noaa = int_id(s["HARPNUM"]), int_id(s["NOAA_AR_clean"])
            require((rec["HARPNUM"], rec["NOAA_AR_clean"], rec["original_label_48h_final"]) == (harp, noaa, flag(s["original_label_48h_final"])), "Index/role region or label mismatch.")
            require(rec["issue_utc"] == s["issue_utc"] and rec["stored_year"] == int(s["stored_year"]), "Index/role time mismatch.")
            require(rec["training_authorised"] is False and not rec["label_boundary_review_required"], "Unexpected clearance or unresolved retained target label.")
            it = tick(rec["issue_raw_TAI"])
            require(it == rec["issue_tai_us"], "Raw/index issue clock mismatch.")
            frames = rec["frames"]
            require([f["lag_minutes"] for f in frames] == list(LAGS), "Three historical slots required in oldest-first order.")
            keys = []
            for frame in frames:
                ft = tick(frame["raw_T_REC_TAI"])
                require(ft == frame["requested_slot_tai_us"] == it - frame["lag_minutes"] * 60 * 1000000, "Frame does not match requested TAI slot.")
                fm = SID.fullmatch(frame["history_sample_id"])
                require(fm is not None and (int(fm[2]), int(fm[3])) == (harp, noaa), "Wrong-region historical frame.")
                require(frame["nominal_candidate"] is True and frame["object_status"] == "EXACT_NONEMPTY_OBJECT", "Historical object was not structurally available.")
                require(frame["history_sample_id"] != "20240714_0724_HARP11520_NOAA13753", "Known excluded frame entered proposal.")
                key = (harp, ft)
                info = {"HARPNUM": harp, "NOAA_AR_clean": noaa, "raw_T_REC_TAI": frame["raw_T_REC_TAI"],
                        "history_sample_id": frame["history_sample_id"], "record_utc": frame["record_utc"],
                        "object_uri": frame["object_uri"], "object_generation": str(frame["object_generation"]),
                        "region_component_id": s["region_component_id"], "final_role": s["proposed_final_role"]}
                if key in requests:
                    require(requests[key] == info, "Historical SHARP key shared with conflicting identity, role or object version.")
                else:
                    requests[key] = info
                keys.append(key)
            frames_by_target[sid] = keys
            if n % 25000 == 0:
                print(f"  Read {n:,} existing candidate records; no images.", flush=True)
    require(n == expected_rows and set(frames_by_target) == set(selected), "Candidate index does not cover selected targets.")
    return requests, frames_by_target


def scan_sharp(path, requests):
    keys = sorted(requests)
    positions = {key: i for i, key in enumerate(keys)}
    harps = {key[0] for key in keys}
    raw = np.full((len(keys), len(FEATURES)), np.nan, dtype=np.float64)
    matches = np.zeros(len(keys), dtype=np.int32)
    info = [dict(requests[k], match_count=0, source_csv_record_numbers=[], raw_QUALITY=[], raw_noaa_fields=[], noaa_conflict=False) for k in keys]
    numeric_flags = Counter()
    scanned = 0
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, strict=True)
        cols = reader.fieldnames or []
        require(len(cols) == len(set(cols)), "Duplicate SHARP columns.")
        missing = sorted(set(FEATURES + ("T_REC", "HARPNUM")) - set(cols))
        require(not missing, f"Required SHARP columns missing: {missing}. No fabricated feature.")
        for nr, row in enumerate(reader, 1):
            scanned = nr
            require(nr <= 1000000, "Unexpectedly large raw SHARP table.")
            require(None not in row and all(v is not None for v in row.values()), "Malformed raw SHARP CSV record.")
            if nr % 200000 == 0:
                print(f"  Raw SHARP scan: {nr:,} records; exact historical keys only.", flush=True)
            try:
                harp = int_id(row["HARPNUM"])
            except ValueError:
                continue
            if harp not in harps:
                continue
            key = (harp, tick(row["T_REC"]))
            if key not in positions:
                continue
            idx = positions[key]
            matches[idx] += 1
            evidence = info[idx]
            evidence["match_count"] = int(matches[idx])
            evidence["source_csv_record_numbers"].append(nr)
            evidence["raw_QUALITY"].append(row.get("QUALITY"))
            nf = {name: row[name] for name in ("NOAA_AR_clean", "NOAA_AR", "NOAA_ARS") if name in cols}
            evidence["raw_noaa_fields"].append(nf)
            explicit = nf.get("NOAA_AR_clean", "").strip()
            if explicit and explicit.lower() not in ("nan", "none", "null"):
                try:
                    conflict = int_id(explicit) != evidence["NOAA_AR_clean"]
                except ValueError:
                    conflict = True
                evidence["noaa_conflict"] |= conflict
            if matches[idx] > 1:
                raw[idx] = np.nan
                continue
            for j, feature in enumerate(FEATURES):
                text = row[feature].strip()
                try:
                    val = float(text)
                except ValueError:
                    numeric_flags[(feature, "missing_or_unparseable")] += 1
                    continue
                if not math.isfinite(val):
                    numeric_flags[(feature, "nonfinite")] += 1
                    continue
                raw[idx, j] = val
    return keys, positions, raw, matches, info, {"source_rows_scanned": scanned,
        "TOTUSJH_present_in_source": "TOTUSJH" in cols, "TOTUSJH_used": False,
        "numeric_input_flags": [{"feature": f, "issue": k, "count": v} for (f,k),v in sorted(numeric_flags.items())]}


def write_csv(path, rows, fields):
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "wt", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def build(proposal_dir, source_lock, output_root):
    proposal_dir, source_lock, output_root = [Path(p).expanduser().resolve() for p in (proposal_dir, source_lock, output_root)]
    names = ("broad_cycle24_fit_report.json", "broad_cycle24_protocol_PROPOSED.json",
             "broad_cycle24_final_role_candidates.csv.gz", "forward_development_fold_candidates.csv.gz")
    locks = bundle_files(proposal_dir, PROPOSAL_STATUS, names)
    report = load_json(proposal_dir / names[0])
    protocol = load_json(proposal_dir / names[1])
    require(report.get("structural_blockers") == [], "Proposal contains structural blockers; no override.")
    require(protocol.get("proposal_not_frozen") is True and report.get("model_fitted") is False, "Unexpected input proposal state.")
    index_dir = Path(report["source_directory"]).expanduser().resolve()
    ilocks = bundle_files(index_dir, INDEX_STATUS, ("temporal_manifest_report.json", "temporal_sequence_candidates.jsonl.gz"))
    locks.update(ilocks)
    for name, expected in report["source_files_sha256"].items():
        require(sha(index_dir / name) == expected, f"Index changed since the broader-role proposal: {name}")
    source_cfg = load_json(source_lock)
    locks[str(source_lock)] = sha(source_lock)
    entries = [e for e in source_cfg.get("sources", []) if e.get("id") == "sharp96"]
    require(len(entries) == 1, "Exactly one sharp96 source lock required.")
    source = entries[0]
    raw_path = Path(source["local_path"]).expanduser().resolve()
    print("Verifying the already-cached SHARP source; no download.", flush=True)
    locks[str(raw_path)] = verified(raw_path, source.get("sha256"))
    require(raw_path.stat().st_size == source["size_bytes"], "SHARP size differs from recorded source.")
    selected = load_roles(proposal_dir / names[2], report)
    requests, frames = requested_slots(index_dir / "temporal_sequence_candidates.jsonl.gz", selected, report["target_rows_preserved"])
    print(f"Cycle-24 targets selected: {len(selected):,}; requested unique SHARP keys: {len(requests):,}.", flush=True)
    keys, positions, raw, matches, slot_info, scan_info = scan_sharp(raw_path, requests)
    # No first/last choice when source keys are duplicated. Those slots remain NaN.
    row_order = list(selected)
    indices = np.asarray([[positions[k] for k in frames[sid]] for sid in row_order], dtype=np.int64)
    values = raw[indices]
    counts = matches[indices]
    source_conflicts = np.asarray([e["noaa_conflict"] for e in slot_info], dtype=bool)[indices]
    unique_match = (counts == 1).all(axis=1)
    finite = np.isfinite(values)
    complete = finite.all(axis=(1,2)) & unique_match & ~source_conflicts.any(axis=1)
    role_rows = []
    for role in ROLES:
        ix = np.asarray([selected[s]["proposed_final_role"] == role for s in row_order])
        labels = np.asarray([flag(selected[s]["original_label_48h_final"]) for s in row_order])
        role_rows.append({"role": role, "targets": int(ix.sum()), "original_positive": int(labels[ix].sum()),
            "three_unique_exact_records": int((ix & unique_match).sum()),
            "complete_raw_numeric_no_explicit_noaa_conflict": int((ix & complete).sum()),
            "missing_or_duplicate_source_record": int((ix & ~unique_match).sum()),
            "explicit_noaa_conflict_targets": int((ix & source_conflicts.any(axis=1)).sum())})
    # Preserve all chosen Cycle-24 rows, including those with source or numeric flags.
    out = output_root / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    require(not any(out == p or p in out.parents for p in (proposal_dir, index_dir)), "Output must be separate from input directories.")
    out.mkdir(parents=True, exist_ok=False)
    np.save(out / "sharp_raw_three_slot.npy", values, allow_pickle=False)
    np.save(out / "sharp_finite_mask.npy", finite, allow_pickle=False)
    np.save(out / "sharp_record_match_counts.npy", counts, allow_pickle=False)
    np.save(out / "original_manifest_targets.npy", labels.astype(np.int8), allow_pickle=False)
    samples = []
    for i, sid in enumerate(row_order):
        s = selected[sid]
        samples.append({"array_row": i, "target_sample_id": sid, "issue_utc": s["issue_utc"],
            "stored_year": s["stored_year"], "HARPNUM": s["HARPNUM"], "NOAA_AR_clean": s["NOAA_AR_clean"],
            "original_label_48h_final": s["original_label_48h_final"], "region_component_id": s["region_component_id"],
            "proposed_final_role": s["proposed_final_role"], "three_unique_exact_records": int(unique_match[i]),
            "raw_numeric_complete": int(complete[i]), "slot_source_indices": json.dumps(indices[i].tolist()),
            "quality_clearance": "NOT_APPLIED", "label_clearance": "UNCHANGED_PENDING", "training_authorised": False})
    write_csv(out / "cycle24_array_rows.csv.gz", samples, list(samples[0]))
    with gzip.open(out / "unique_sharp_source_records.jsonl.gz", "wt", encoding="utf-8") as f:
        for i,e in enumerate(slot_info):
            e = dict(e, slot_source_index=i, finite_feature_count=int(np.isfinite(raw[i]).sum()))
            f.write(json.dumps(e, allow_nan=False) + "\n")
    fold_rows, fcounts, seen = [], defaultdict(Counter), set()
    for r in csv_rows(proposal_dir / names[3], ("fold_id", "target_sample_id", "region_component_id", "fold_role", "structural_candidate", "exclusion_reasons")):
        if not flag(r["structural_candidate"]):
            continue
        sid = r["target_sample_id"]
        require(sid in selected and selected[sid]["proposed_final_role"] == FIT, "Holdout or test target entered model-development fold.")
        require(r["region_component_id"] == selected[sid]["region_component_id"], "Fold region mismatch.")
        require((r["fold_id"], sid) not in seen, "Repeated target within development fold.")
        seen.add((r["fold_id"], sid))
        require(r["fold_role"] in ("train", "validation") and not r["exclusion_reasons"], "Bad retained fold record.")
        i = selected[sid]["array_row"]
        fold_rows.append(dict(r, array_row=i, raw_numeric_complete=int(complete[i])))
        fcounts[(r["fold_id"],r["fold_role"])].update({"retained":1,"positive":flag(selected[sid]["original_label_48h_final"])})
    for r in report["forward_fold_support"]:
        got = fcounts[(r["fold_id"],r["role"])]
        require(got["retained"] == r["retained"] and got["positive"] == r["positive"], "Development-fold support changed.")
    require(bool(fold_rows), "No model-development fold rows.")
    write_csv(out / "forward_development_array_rows.csv.gz", fold_rows, list(fold_rows[0]))
    for path, expected in locks.items():
        require(sha(Path(path)) == expected, f"Input changed while building: {path}")
    output_report = {"version":VERSION,"status":STATUS,"created_utc":datetime.now(timezone.utc).isoformat(),
        "input_sha256":locks,"script_sha256":sha(Path(__file__)),"numpy_version":np.__version__,
        "array_shape":list(values.shape),"array_dtype":str(values.dtype),"feature_order":list(FEATURES),
        "lag_minutes_oldest_to_newest":list(LAGS),"role_support":role_rows,
        "unique_requested_sharp_keys":len(keys),"unique_exact_source_keys":int((matches==1).sum()),
        "missing_source_keys":int((matches==0).sum()),"duplicate_source_keys":int((matches>1).sum()),
        "scan":scan_info,"test_arrays_constructed":False,"calibration_or_threshold_fitted":False,
        "imputation_or_scaling_fitted":False,"model_trained":False,"training_authorised":False,
        "split_frozen":False,"original_labels_replaced":False,"source_quality_filter_applied":False,
        "semantic_note":"Exact HARP/TAI key join; NOAA_ARS retained as provenance, not a certified association. Three sparse historical steps, not a 24h aggregate.",
        "remaining_gates":["Label provenance, completeness and 48h follow-up remain pending.",
            "SHARP contributing-time support, historical availability and final quality rules remain pending.",
            "AIA full-population timing remains pending; this step reads no images.",
            "Missing or duplicated records remain explicit; no automatic deletion or source substitution.",
            "Fit preprocessing only inside each development training fold; later refit on accepted final training pool.",
            "Calibration and threshold holdouts are retrospective region holdouts, not chronological future holdouts."]}
    write_json(out / "sharp_array_build_report.json", output_report)
    note = """# Broader Cycle-24 SHARP input arrays

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
"""
    (out / "research_log_sharp_arrays.md").write_text(note,encoding="utf-8")
    write_json(out / "COMPLETE.json", {"status":STATUS,"output_sha256":{p.name:sha(p) for p in out.iterdir() if p.is_file()}})
    with zipfile.ZipFile(out / "sharp_arrays_summary.zip", "x", compression=zipfile.ZIP_DEFLATED) as z:
        for name in ("sharp_array_build_report.json", "research_log_sharp_arrays.md", "COMPLETE.json"):
            z.write(out / name, name)
    print("\n===== CYCLE-24 SHARP ARRAY RESULTS =====")
    print("Raw array shape:",list(values.shape),"| no scaling, imputation or training")
    print("Role | candidates | exact three records | complete raw numeric | original positive")
    for r in role_rows:
        print(" | ".join(str(r[k]) for k in ("role","targets","three_unique_exact_records","complete_raw_numeric_no_explicit_noaa_conflict","original_positive")))
    print("Unique missing SHARP keys:",output_report["missing_source_keys"],"| duplicate keys:",output_report["duplicate_source_keys"])
    print("Cycle-25/2026 arrays constructed: 0")
    print("STATUS:",STATUS)
    print("REPORT:",out / "sharp_array_build_report.json")
    print("SUMMARY:",out / "sharp_arrays_summary.zip")
    return output_report


def main(argv=None):
    h = Path.home()
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--proposal-run", type=Path, default=h/"aia17_metadata_stage1/broad_cycle24_finalfit_v2/reports/20260916T191645934223Z")
    p.add_argument("--source-lock", type=Path, default=h/"solar_flare_aia/docs/research_audit/2026-09-15/stage1/source_lock_snapshot.json")
    p.add_argument("--output-root", type=Path, default=h/"aia17_metadata_stage1/sharp_arrays_cycle24_v1/reports")
    a = p.parse_args(argv)
    try:
        parent = a.output_root.expanduser().resolve()
        while not parent.exists():
            parent = parent.parent
        require(shutil.disk_usage(parent).free > 1024**3, "Less than 1 GiB free; do not delete research files blindly.")
        print("===== FULL CYCLE-24 SHARP ARRAY PREPARATION =====", flush=True)
        print("Existing broader proposal; exact three-slot inputs. No images, cloud, test arrays or training.", flush=True)
        build(a.proposal_run, a.source_lock, a.output_root)
        return 0
    except (Exception, KeyboardInterrupt) as exc:
        print(f"\nSTOP: {type(exc).__name__}: {exc}",file=sys.stderr)
        print("Originals unchanged. Partial outputs without COMPLETE.json are not accepted datasets.",file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
