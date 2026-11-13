from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import propensity_summary_bundle as psb  # noqa: E402


def _rehash(bundle: dict) -> dict:
    bundle["content_sha256"] = psb.content_hash(bundle)
    return bundle


class PropensityBundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = psb.load_bundle()

    def test_bundle_pin_schema_and_approved_metrics(self) -> None:
        self.assertEqual(self.bundle["content_sha256"], psb.EXPECTED_CONTENT_SHA256)
        self.assertEqual(self.bundle["m1"]["test"], {
            "customers": 208, "positive": 97, "negative": 111, "prevalence": 97 / 208,
        })
        m1c = self.bundle["m1"]["models"]["C_three_feature"]
        self.assertEqual(m1c["roc_auc"], 0.5189)
        self.assertEqual(self.bundle["m1"]["auc_interval"]["lower"], 0.4410)
        self.assertEqual(self.bundle["m1"]["auc_interval"]["upper"], 0.5963)
        self.assertFalse(self.bundle["m1"]["success_criterion_met"])
        m2 = self.bundle["m2"]
        self.assertEqual(m2["test"]["snapshots"], 21672)
        self.assertEqual(m2["test"]["customers"], 4999)
        self.assertEqual(m2["customer_overlap"], 4265)
        self.assertAlmostEqual(m2["models"]["C_full_11"]["roc_auc"], 0.7659859786)
        self.assertAlmostEqual(m2["models"]["C_full_11"]["average_precision"], 0.5659489004)
        self.assertAlmostEqual(m2["models"]["C_full_11"]["precision_10pct"], 0.6928044280)
        self.assertEqual(len(m2["monthly"]), 5)

    def test_task_definitions_and_calibration_are_separate(self) -> None:
        self.assertIn("Day 21", self.bundle["m1"]["decision"])
        self.assertIn("Day 111", self.bundle["m1"]["outcome"])
        self.assertIn("30 days", self.bundle["m2"]["outcome"])
        cal = self.bundle["m2_calibration"]
        self.assertEqual([p["target_month"] for p in cal["pools"]], ["2011-09", "2011-10", "2011-11"])
        self.assertEqual(cal["pooled"]["snapshots"], 13032)
        self.assertAlmostEqual(cal["pooled"]["raw"]["brier"], 0.1681532657)
        self.assertAlmostEqual(cal["pooled"]["adjusted"]["brier"], 0.1636881830)
        self.assertAlmostEqual(cal["pooled"]["brier_difference"], -0.0044582162)
        self.assertEqual(cal["pooled"]["bootstrap"]["resamples"], 2000)

    def test_aggregate_only_and_source_provenance(self) -> None:
        text = psb.DEFAULT_BUNDLE_PATH.read_text(encoding="utf-8").lower()
        for fragment in ("customer_id", "customerid", "prediction_rows", "feature_matrix", "invoice_no", "stockcode"):
            self.assertNotIn(fragment, text)
        self.assertEqual(self.bundle["provenance"]["source_sha256"], psb.EXPECTED_INPUT_SHA256)
        self.assertEqual(set(self.bundle["provenance"]["source_documents"]), set(psb.SOURCE_DOCUMENTS))

    def test_recomputed_embedded_hash_does_not_authorise_changed_results(self) -> None:
        bundle = copy.deepcopy(self.bundle)
        bundle["m2"]["models"]["C_full_11"]["roc_auc"] = 0.99
        _rehash(bundle)
        with self.assertRaisesRegex(psb.BundleError, "independently approved"):
            psb.validate_bundle(bundle)

    def test_missing_or_malformed_bundle_metadata_fails_clearly(self) -> None:
        for section in ("provenance", "m1", "m2", "m2_calibration"):
            with self.subTest(section=section):
                bundle = copy.deepcopy(self.bundle)
                bundle[section] = {}
                with self.assertRaises(psb.BundleError):
                    psb.validate_bundle(bundle)
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
            handle.write("{not json")
            path = Path(handle.name)
        self.addCleanup(path.unlink, missing_ok=True)
        with self.assertRaisesRegex(psb.BundleError, "JSON"):
            psb.load_bundle(path)

    def test_build_from_verified_external_aggregates_when_available(self) -> None:
        configured_root = os.environ.get("LOCAL_DATA_DIR")
        if not configured_root:
            self.skipTest("Set LOCAL_DATA_DIR to run the external-aggregate rebuild check.")
        source_root = Path(configured_root)
        manifest = source_root / "m2_008_baseline_outputs/monthly_purchase_baselines_m2_008_run_manifest.json"
        calibration = source_root / "m2_012_sequential_calibration_outputs/m2_012_sequential_calibration_aggregate.json"
        if not manifest.is_file() or not calibration.is_file():
            self.skipTest("External M2 aggregate manifests are not present in this checkout.")
        rebuilt = psb.build_bundle(manifest, calibration)
        self.assertEqual(psb.content_hash(rebuilt), self.bundle["content_sha256"])
        self.assertEqual(rebuilt["m2"], self.bundle["m2"])
        self.assertEqual(rebuilt["m2_calibration"], self.bundle["m2_calibration"])


if __name__ == "__main__":
    unittest.main()
