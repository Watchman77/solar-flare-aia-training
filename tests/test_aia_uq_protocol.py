"""Protocol contract tests, not evidence that UQ methods have been implemented."""
import json
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
class UQProtocolTests(unittest.TestCase):
    def setUp(self):
        self.uq = json.loads((ROOT / "configs/aia_uq_calibration_protocol.json").read_text())
        self.meta = json.loads((ROOT / "configs/aia17_metadata_stage1.json").read_text())
    def test_exact_standing_checklist(self):
        self.assertEqual(self.uq["research_checklist"], ["Performance","Calibration","Uncertainty","Robustness","Explainability","Statistical significance"])
    def test_no_training_or_uq_execution_claim(self):
        self.assertFalse(self.uq["training_authorised"])
        self.assertFalse(self.uq["uq_experiments_executed_by_this_update"])
        self.assertFalse(self.uq["stage1_audit_computation_changed"])
    def test_calibration_never_fitted_on_test(self):
        self.assertFalse(self.uq["calibration"]["fit_on_test_allowed"])
        self.assertFalse(self.uq["calibration"]["threshold_selection_on_test_allowed"])
        self.assertTrue(self.uq["calibration"]["threshold_selection_after_calibration"])
    def test_grouped_paired_bootstrap_contract(self):
        u=self.uq["metric_uncertainty"]
        self.assertFalse(u["row_iid_bootstrap_primary"])
        self.assertTrue(u["paired_identical_resample_indices"])
        self.assertTrue(u["bootstrap_models_calibrators_thresholds_frozen"])
    def test_separate_pinn_and_original_task_preserved(self):
        self.assertEqual(self.uq["pinn_track"], "SEPARATE_20A_20B_20C")
        self.assertEqual(self.uq["label"], self.meta["label"])
        self.assertEqual(self.meta["aia_channels_angstrom"], [94,131,171,193,211,335])
        self.assertEqual(self.meta["forecast_horizon_hours"],48)
        self.assertEqual(self.meta["max_total_source_bytes"],450*1024**2)
        self.assertEqual(len(self.meta["sources"]),5)
    def test_notebook_addenda_present_without_execution_claims(self):
        paths=list((ROOT/"notebooks/training").glob("17[AB]_*.ipynb"))
        self.assertEqual(len(paths),2)
        for path in paths:
            nb=json.loads(path.read_text())
            self.assertEqual(nb["metadata"]["aia_uq_protocol"]["status"],"requirements_only_not_executed")
            self.assertEqual(sum(c.get("id")=="uq-protocol-20260914" for c in nb["cells"]),1)
if __name__ == "__main__":
    unittest.main()
