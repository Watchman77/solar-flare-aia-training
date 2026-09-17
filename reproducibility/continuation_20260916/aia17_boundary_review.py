#!/usr/bin/env python3
"""Review the saved conditional clock-change cases; no full audit or repair.

Uses the pinned time-label report, small affected-sample CSV, cached event CSV,
and the existing repository's AstroClock. Does not call gcloud or the network,
install dependencies, update source data, stage files, commit, or train.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

VERSION = "aia17-boundary-review-v1"
REVIEW_ID = "time_label_impact_20260915T172829490191Z"
SNAPSHOT = Path("docs/research_audit/2026-09-15")
HORIZON_US = 172800 * 1_000_000
ASSUMPTION = "FULL_EVENT_EXPORT_UTC_HYPOTHESIS_NOT_VERIFIED"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def document(path: Path) -> dict:
    if not path.is_file() or path.stat().st_size > 10 * 1024**2:
        raise ValueError(f"Missing/oversized JSON: {path}")
    result = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return result


def checked(path: Path, expected: str) -> str:
    if not expected or not path.is_file() or digest(path) != expected:
        raise ValueError(f"Missing file or checksum mismatch: {path}")
    return expected


def bit(value: str) -> int:
    if value not in ("0", "1"):
        raise ValueError(f"Unexpected binary field: {value!r}")
    return int(value)


def inside(lead_us: int) -> bool:
    return 0 < lead_us <= HORIZON_US


def describe_change(reference_us: int, physical_us: int) -> str:
    if inside(reference_us) and not inside(physical_us):
        return ("AFTER_CORRECTED_UPPER_BOUNDARY" if physical_us > HORIZON_US
                else "AT_OR_BEFORE_CORRECTED_ISSUE_TIME")
    if not inside(reference_us) and inside(physical_us):
        return "NEWLY_INSIDE_CORRECTED_WINDOW"
    return "WINDOW_MEMBERSHIP_UNCHANGED"


def load_clock_helper(repo: Path):
    path = repo / "scripts/aia17_time_label_impact.py"
    manifest = document(repo / SNAPSHOT / "checkpoint_file_manifest.json")
    matches = [x for x in manifest["files"] if x["path"] == "scripts/aia17_time_label_impact.py"]
    if len(matches) != 1:
        raise ValueError("Expected exactly one clock-helper entry in checkpoint manifest.")
    checked(path, matches[0]["sha256"])
    if path.stat().st_size != matches[0]["bytes"]:
        raise ValueError("Clock-helper size differs from the recorded checkpoint.")
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("aia17_saved_clock", path)
    if spec is None or spec.loader is None:
        raise ValueError("Could not load the existing clock helper.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # its main()/dataset audit is NOT called
    if module.HORIZON_US != HORIZON_US or module.ASSUMPTION != ASSUMPTION:
        raise ValueError("Clock-helper protocol differs from this review.")
    return module


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.home() / "solar_flare_aia")
    parser.add_argument("--review", type=Path, default=Path.home() / "aia17_metadata_stage1/reviews" / REVIEW_ID)
    args = parser.parse_args()
    repo, review = args.repo.expanduser().resolve(), args.review.expanduser().resolve()
    try:
        print("===== 17B SAVED-SAMPLE BOUNDARY REVIEW =====", flush=True)
        # Compare local evidence with the copied checkpoint, not just a banner.
        marker_path = repo / SNAPSHOT / "time/COMPLETE.json"
        marker = document(marker_path)
        hashes = marker["output_sha256"]
        report_path = review / "time_label_impact_report.json"
        affected_path = review / "affected_samples.csv.gz"
        inputs = {str(report_path): checked(report_path, hashes[report_path.name]),
                  str(affected_path): checked(affected_path, hashes[affected_path.name])}
        report = document(report_path)
        if report["status"] != "TIME_LABEL_IMPACT_COMPLETE_CONDITIONAL_NO_REPAIRS":
            raise ValueError("Expected a completed conditional timing run.")
        if report["time_scale_assumption"] != ASSUMPTION or report["original_labels_replaced"] is not False:
            raise ValueError("Unexpected label/clock policy in the saved report.")
        totals = [s for s in report["summary"] if s["cohort"] == "curated_master" and s["stored_year"] == "ALL"]
        if len(totals) != 1:
            raise ValueError("Ambiguous master summary.")

        lock_path = Path(report["source_run"]) / "source_lock_snapshot.json"
        inputs[str(lock_path)] = checked(lock_path, report["input_sha256"].get(str(lock_path)))
        specs = [s for s in document(lock_path)["sources"] if s["id"] == "events"]
        if len(specs) != 1:
            raise ValueError("Ambiguous event-source entry.")
        events_path = Path(specs[0]["local_path"])
        inputs[str(events_path)] = checked(events_path, report["input_sha256"].get(str(events_path)))

        with gzip.open(affected_path, "rt", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f, strict=True)
            cases = [r for r in reader if bit(r["clock_interpretation_changes_start_hit"])]
        if len(cases) != totals[0]["clock_changed"] or len(cases) != 1:
            raise ValueError("Expected the one saved clock-change case; no repair attempted.")

        helper = load_clock_helper(repo)
        clock = helper.AstroClock()
        self_tests = clock.check()
        # This converts only the small event table and selected sample, not the master.
        events = list(helper.rows(events_path, helper.EVENT_FIELDS))
        event_start_iso = [helper.naive_iso(r["event_starttime"]) for _, r in events]
        event_ticks = clock.ticks(event_start_iso, "utc")
        outputs = []
        for sample in cases:
            region = helper.id_string(sample["NOAA_AR_clean"])
            raw_iso = helper.raw_tai_iso(sample["T_REC_raw_TAI"])
            old_iso = helper.naive_iso(sample["T_REC_dt_original"])
            if raw_iso != old_iso:
                raise ValueError("Stored sample clock differs from its raw TAI evidence.")
            issue = clock.ticks([raw_iso], "tai")[0]
            canonical = clock.utc_text([issue])[0]
            end = clock.utc_text([issue + HORIZON_US])[0]
            if canonical != sample["T_REC_utc_derived"] or end != sample["forecast_end_utc_48_SI_hours"]:
                raise ValueError("Recomputed sample times disagree with saved diagnostics.")
            old_tick = helper.representation_us(old_iso)
            comparisons, hits_reference, hits_physical = [], 0, 0
            for (number, event), iso, tick in zip(events, event_start_iso, event_ticks):
                if helper.id_string(event["NOAA_AR_clean"]) != region:
                    continue
                ref = helper.representation_us(iso) - old_tick
                physical = tick - issue
                hits_reference += int(inside(ref))
                hits_physical += int(inside(physical))
                if inside(ref) or inside(physical):
                    comparisons.append({"source_record_number": number,
                        "catalogue_record": event,
                        "reference_lead_seconds_clock_fields_only": ref / 1_000_000,
                        "physical_lead_seconds_under_utc_hypothesis": physical / 1_000_000,
                        "seconds_after_corrected_48h_end": (physical - HORIZON_US) / 1_000_000,
                        "reference_window_hit": inside(ref), "utc_hypothesis_window_hit": inside(physical),
                        "boundary_explanation": describe_change(ref, physical)})
            if (int(hits_reference > 0) != bit(sample["catalogue_start_hit_clock_only_reference"])
                    or int(hits_physical > 0) != bit(sample["catalogue_start_hit_utc_hypothesis"])):
                raise ValueError("Selected sample does not reproduce its saved hit flags.")
            outputs.append({"sample": sample, "event_comparisons": comparisons,
                "raw_record_hits_reference": hits_reference, "raw_record_hits_utc_hypothesis": hits_physical})

        # Reject inputs changed during the review before writing an accepted output.
        for name, expected in inputs.items():
            checked(Path(name), expected)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        out = review.parent / ("boundary_review_" + stamp)
        out.mkdir(parents=True, exist_ok=False)
        result = {"version": VERSION, "status": "BOUNDARY_REVIEW_COMPLETE_CONDITIONAL_NO_REPAIRS",
                  "input_sha256": inputs, "source_timing_report": str(report_path),
                  "time_scale_assumption": ASSUMPTION, "conversion_self_tests": self_tests,
                  "cases": outputs, "original_labels_replaced": False, "training_authorised": False,
                  "caveats": ["The full event export's UTC interpretation remains unverified.",
                    "No catalogue hit does not certify a negative label or complete follow-up.",
                    "This reviews a boundary calculation, not catalogue completeness or AIA causality.",
                    "Repeated source records are preserved; raw hit counts are not unique-flare features."]}
        report_out = out / "boundary_review.json"
        with report_out.open("x", encoding="utf-8") as f:
            json.dump(result, f, indent=2, allow_nan=False)
            f.write("\n")
        text = ["# 17B conditional single-sample boundary review", "",
                "Source labels and event records unchanged; no training authorised.", "",
                f"Event interpretation: `{ASSUMPTION}`", ""]
        print("\n===== SINGLE-SAMPLE BOUNDARY RESULTS =====")
        for case in outputs:
            s = case["sample"]
            lines = [f"Sample: {s['sample_id']}", f"HARP: {s['HARPNUM']} | NOAA: {s['NOAA_AR_clean']}",
                     f"Raw TAI: {s['T_REC_raw_TAI']}", f"Derived issue UTC: {s['T_REC_utc_derived']}",
                     f"Corrected 48-hour end UTC: {s['forecast_end_utc_48_SI_hours']}",
                     f"Original label (unchanged): {s['original_label_48h_final']}",
                     f"In baseline: {s['in_baseline_manifest']} | In extension: {s['in_extension']}"]
            print("\n".join(lines)); text += lines + [""]
            for c in case["event_comparisons"]:
                e = c["catalogue_record"]
                lines = [f"Event source row: {c['source_record_number']} | class: {e['fl_goescls']}",
                    f"Event start (UTC hypothesis): {e['event_starttime']}",
                    f"Clock-only reference lead: {c['reference_lead_seconds_clock_fields_only']:.6f} seconds",
                    f"Physical lead under hypothesis: {c['physical_lead_seconds_under_utc_hypothesis']:.6f} seconds",
                    f"Seconds AFTER corrected 48h end: {c['seconds_after_corrected_48h_end']:.6f}",
                    f"Window match: {c['reference_window_hit']} -> {c['utc_hypothesis_window_hit']}",
                    f"Explanation: {c['boundary_explanation']}"]
                print("\n".join(lines)); text += lines + [""]
        text += ["## Interpretation limits", ""] + result["caveats"]
        note = out / "research_log_boundary_review.md"
        note.write_text("\n\n".join(text) + "\n", encoding="utf-8")
        complete = {"status": result["status"], "output_sha256": {
            report_out.name: digest(report_out), note.name: digest(note)}}
        with (out / "COMPLETE.json").open("x", encoding="utf-8") as f:
            json.dump(complete, f, indent=2); f.write("\n")
        print("\nSTATUS:", result["status"])
        print("REPORT:", report_out)
        print("RESEARCH LOG:", note)
        print("No network, source changes, full audit rerun, Git operations or training.")
        return 0
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, csv.Error, AttributeError) as exc:
        print(f"STOP: {type(exc).__name__}: {exc}\nNo source-label repair or training was attempted.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
