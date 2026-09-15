"""Synthetic tests only; no GCP credentials, network calls or solar results."""
import base64
from contextlib import redirect_stdout
import csv
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import aia17_metadata_audit as audit


class MetadataTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.config = json.loads((ROOT / "configs/aia17_metadata_stage1.json").read_text())

    def tearDown(self):
        self.tmp.cleanup()

    def make_csv(self, name, rows, columns=None):
        path = self.root / (name + ".csv")
        with path.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=columns or list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        return path

    def fixtures(self, duplicate=False):
        def target(sid, t, label):
            return dict(sample_id=sid, T_REC_dt=t, T_REC=t.replace("-", ".").replace(" ", "_")+"_TAI",
                        HARPNUM="10", NOAA_AR_clean="11010", label_48h_final=str(label), USFLUX="42", QUALITY="0")
        first = target("sample_a", "2010-05-21 00:00:00", 0)
        second = target("sample_b", "2025-05-21 00:00:00", 1)
        third = target("sample_c", "2026-01-21 00:00:00", 0)
        master = [first, second, third]
        if duplicate:
            master += [{**second, "label_48h_final": "0"}]
        raw = [dict(T_REC_dt=t, T_REC=t.replace("-", ".").replace(" ", "_")+"_TAI", HARPNUM="10", USFLUX="42", QUALITY="0")
               for t in ["2010-05-21 00:00:00", "2010-05-21 01:36:00", "2010-05-21 03:12:00"]]
        events = [dict(event_starttime="2025-05-21T12:00:00Z", event_peaktime="2025-05-21T12:04:00Z", event_endtime="2025-05-21T12:10:00Z", fl_goescls=family, NOAA_AR_clean="11010", flux="0.00002") for family in ["M2.0", "C1.0"]]
        tables = {"baseline_manifest": [first], "curated_master": master, "extension": [second, third], "sharp96": raw, "events": events}
        return {"sources": [{**s, "local_path": str(self.make_csv(s["id"], tables[s["id"]]))} for s in self.config["sources"]]}

    def run_fixture(self, duplicate=False):
        lock = self.fixtures(duplicate)
        with redirect_stdout(io.StringIO()):
            return audit.run_audit(lock, self.config, self.root / "results")

    def test_contract_preserved(self):
        audit.check_protocol(self.config)
        self.assertFalse(self.config["training_authorised"])
        self.assertFalse(any("12MIN" in s["uri"] for s in self.config["sources"]))

    def test_raw_labels_not_required(self):
        result = self.run_fixture()
        raw = next(x for x in result["source_profiles"] if x["source"] == "sharp96")
        self.assertFalse(raw["label_present"])
        self.assertEqual(raw["label_invalid"], 0)
        self.assertEqual(raw["label_missing"], 0)

    def test_extension_subset_not_concatenated(self):
        result = self.run_fixture()
        comparison = result["identity_comparisons"][0]
        self.assertEqual(comparison["matched_ids"], 2)
        self.assertEqual(comparison["left_without_unambiguous_right_match"], 0)
        master = next(x for x in result["source_profiles"] if x["source"] == "curated_master")
        self.assertEqual(master["rows"], 3)
        self.assertFalse(result["training_authorised"])

    def test_duplicate_conflicting_labels_not_silently_merged(self):
        result = self.run_fixture(duplicate=True)
        d = next(x for x in result["duplicate_audit"] if x["source"] == "curated_master")
        self.assertEqual(d["conflicting_label_id_groups"], 1)
        self.assertEqual(result["identity_comparisons"][0]["matched_ids"], 1)
        self.assertEqual(result["identity_comparisons"][0]["left_without_unambiguous_right_match"], 1)

    def test_missing_feature_not_created(self):
        result = self.run_fixture()
        raw = next(x for x in result["source_profiles"] if x["source"] == "sharp96")
        self.assertNotIn("TOTUSJH", raw["columns"])
        self.assertNotIn("TOTUSJH", raw["feature_counts"])

    def test_tai_is_not_assumed_utc(self):
        stamp, _, _, kind = audit.parsed_clock("2025-01-01 00:00:00")
        self.assertEqual(kind, "naive_unresolved_scale")
        self.assertNotIn("+00:00", stamp)
        self.assertEqual(audit.raw_time_tag("2025.01.01_00:00:00_TAI"), "TAI_tag")
        self.assertEqual(audit.parsed_clock("2025-01-01T01:00:00+01:00")[0], "2025-01-01T00:00:00+00:00")
        self.assertEqual(audit.parsed_clock("2025.01.01_00:00:00_TAI")[3], "unparsed")

    def test_actual_event_classes_and_raw_cadence(self):
        result = self.run_fixture()
        event = next(x for x in result["source_profiles"] if x["source"] == "events")
        self.assertEqual(event["event_class_counts"], {"M": 1, "C": 1})
        self.assertEqual(result["raw_sharp96_cadence"]["most_common_positive_gaps_seconds"], [{"gap_seconds": 5760.0, "count": 2}])

    def test_invalid_labels_not_zero_filled(self):
        self.assertIsNone(audit.label_value("nan"))
        self.assertIsNone(audit.label_value("2"))
        self.assertIsNone(audit.label_value("False"))
        self.assertEqual(audit.label_value("1.0"), 1)
        lock = self.fixtures()
        spec = next(s for s in lock["sources"] if s["id"] == "extension")
        text = Path(spec["local_path"]).read_text().replace(",1,42,0", ",banana,42,0")
        Path(spec["local_path"]).write_text(text)
        with redirect_stdout(io.StringIO()):
            result = audit.run_audit(lock, self.config, self.root / "badlabels")
        ext = next(s for s in result["source_profiles"] if s["source"] == "extension")
        self.assertEqual(ext["label_invalid"], 1)
        self.assertFalse(result["training_authorised"])

    def test_staging_reuses_verified_source_and_does_not_write_cloud(self):
        payload = b"a,b\n1,2\n"
        cfg = {"project":"test-project", "max_total_source_bytes":100, "disk_reserve_bytes":0,
               "sources":[{"id":"small", "uri":"gs://example/small.csv", "role":"test", "max_bytes":100}]}
        calls = []
        def fake_gcloud(*args, **kwargs):
            calls.append(args)
            if args[:3] == ("storage", "objects", "describe"):
                return json.dumps({"size":str(len(payload)), "generation":"123", "md5Hash":base64.b64encode(hashlib.md5(payload).digest()).decode()})
            if args[:2] == ("storage", "cp"):
                self.assertEqual(args[3], "gs://example/small.csv#123")
                self.assertFalse(args[4].startswith("gs://"))
                Path(args[4]).write_bytes(payload)
                return None
            self.fail("Unexpected external command")
        with patch.object(audit.shutil, "which", return_value="gcloud"), patch.object(audit, "gcloud", side_effect=fake_gcloud), redirect_stdout(io.StringIO()):
            audit.stage_sources(cfg, self.root / "work")
            audit.stage_sources(cfg, self.root / "work")
        self.assertEqual(sum(c[:2] == ("storage", "cp") for c in calls), 1)
        self.assertEqual(sum(c[:3] == ("storage", "objects", "describe") for c in calls), 1)

    def test_total_byte_cap_blocks_all_downloads(self):
        cfg = {"project":"test", "max_total_source_bytes":5, "disk_reserve_bytes":0,
               "sources":[{"id":"test", "uri":"gs://example/small.csv", "role":"test", "max_bytes":20}]}
        with patch.object(audit.shutil, "which", return_value="gcloud"), patch.object(audit, "gcloud", return_value=json.dumps({"size":"10", "generation":"1"})) as fake, redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError, "exceeds"):
                audit.stage_sources(cfg, self.root / "work")
        self.assertEqual(fake.call_count, 1)
        self.assertFalse((self.root / "work/source_lock.json").exists())


if __name__ == "__main__":
    unittest.main()
