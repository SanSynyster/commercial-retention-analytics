from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import customer_overview_bundle as cob  # noqa: E402
import customer_overview_metrics as com  # noqa: E402


def _rehash(bundle: dict) -> dict:
    bundle["content_sha256"] = cob.content_hash(bundle)
    return bundle


class TrackedBundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = cob.load_bundle(cob.DEFAULT_BUNDLE_PATH)

    def test_schema_fields_and_types(self) -> None:
        self.assertEqual(set(self.bundle), set(cob.TOP_LEVEL_FIELDS))
        self.assertEqual(self.bundle["schema_version"], cob.SCHEMA_VERSION)
        self.assertEqual(set(self.bundle["headline"]), set(cob.HEADLINE_FIELDS))
        for row in self.bundle["cohort_activity"]:
            self.assertEqual(set(row), set(cob.COHORT_FIELDS))
        self.assertIsInstance(self.bundle["headline"]["qualifying_gross_merchandise"], str)

    def test_accepted_corrected_v2_values(self) -> None:
        head = self.bundle["headline"]
        self.assertEqual(head["identified_customers"], 5852)
        self.assertEqual(head["qualifying_purchase_occasions"], 36594)
        self.assertEqual(head["qualifying_gross_merchandise"], "17123740.997")
        self.assertEqual(self.bundle["concentration"]["top_decile_customer_count"], 586)
        self.assertAlmostEqual(self.bundle["concentration"]["top_decile_share"], 0.638114, places=6)
        self.assertEqual(head["mature_90d_customers"] + head["insufficient_follow_up_customers"], 5852)

    def test_no_customer_level_fields_and_small_cells_suppressed(self) -> None:
        text = cob.DEFAULT_BUNDLE_PATH.read_text(encoding="utf-8").lower()
        for fragment in ("customer_id", "customerid", "invoiceno", "stockcode", "probability"):
            self.assertNotIn(fragment, text)
        observed = [r for r in self.bundle["cohort_activity"]
                    if r["cell_status"] == "observed_complete" and r["month_index"] > 0]
        self.assertTrue(all(r["active_customers"] >= cob.SMALL_CELL_THRESHOLD for r in observed))
        suppressed = [r for r in self.bundle["cohort_activity"] if r["cell_status"] == "suppressed_small_cell"]
        self.assertEqual(len(suppressed), self.bundle["publication_review"]["suppressed_cohort_cells"])
        self.assertTrue(all(r["active_customers"] is None and r["activity_fraction"] is None for r in suppressed))
        self.assertTrue(all(r["customer_count"] >= cob.SMALL_CELL_THRESHOLD for r in self.bundle["segments"]))
        self.assertIn("not a disclosure guarantee", self.bundle["publication_review"]["suppression_rule"])

    def test_rebuild_from_private_aggregates_matches_tracked_bundle(self) -> None:
        if not all((cob.DEFAULT_SOURCE_DIR / name).is_file() for name in cob.SOURCE_FILES):
            self.skipTest("Private corrected-V2 aggregate outputs are not available in this checkout.")
        rebuilt = cob.build_bundle(cob.DEFAULT_SOURCE_DIR)
        for section in cob.DATA_SECTIONS:
            self.assertEqual(rebuilt[section], self.bundle[section], section)
        self.assertEqual(rebuilt["provenance"]["source_aggregate_sha256"],
                         self.bundle["provenance"]["source_aggregate_sha256"])


class InvalidBundleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.valid = cob.load_bundle(cob.DEFAULT_BUNDLE_PATH)

    def _write(self, content: str) -> Path:
        handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
        handle.write(content)
        handle.close()
        self.addCleanup(Path(handle.name).unlink)
        return Path(handle.name)

    def test_missing_and_unreadable_files_fail_closed(self) -> None:
        with self.assertRaisesRegex(cob.BundleError, "not found"):
            cob.load_bundle(ROOT / "app_data/does_not_exist.json")
        with self.assertRaisesRegex(cob.BundleError, "JSON"):
            cob.load_bundle(self._write("{not json"))
        with self.assertRaisesRegex(cob.BundleError, "JSON object"):
            cob.validate_bundle([1, 2, 3])

    def test_schema_and_type_violations(self) -> None:
        bundle = copy.deepcopy(self.valid)
        del bundle["segments"]
        with self.assertRaisesRegex(cob.BundleError, "top-level"):
            cob.validate_bundle(bundle)
        bundle = copy.deepcopy(self.valid)
        bundle["schema_version"] = 2
        with self.assertRaisesRegex(cob.BundleError, "schema version"):
            cob.validate_bundle(bundle)
        bundle = copy.deepcopy(self.valid)
        bundle["headline"]["identified_customers"] = "5852"
        with self.assertRaisesRegex(cob.BundleError, "type"):
            cob.validate_bundle(_rehash(bundle))

    def test_content_hash_detects_edits(self) -> None:
        bundle = copy.deepcopy(self.valid)
        bundle["segments"][0]["customer_count"] += 1
        with self.assertRaisesRegex(cob.BundleError, "content hash"):
            cob.validate_bundle(bundle)

    def test_rehashed_consistent_edit_differs_from_approved_content_pin(self) -> None:
        bundle = copy.deepcopy(self.valid)
        row = next(r for r in bundle["repeat_90d"]
                   if r["first_observed_month"] == "2009-12" and r["population"] == cob.PRE)
        row["repeat_numerator"] = 900
        row["conversion_fraction"] = 900 / row["mature_customer_count"]
        _rehash(bundle)
        with self.assertRaisesRegex(cob.BundleError, "independently approved"):
            cob.validate_bundle(bundle)

    def test_provenance_and_publication_review_are_required_and_typed(self) -> None:
        for field in ("provenance", "publication_review"):
            for malformed in ({}, None, []):
                with self.subTest(field=field, malformed=malformed):
                    bundle = copy.deepcopy(self.valid)
                    bundle[field] = malformed
                    with self.assertRaisesRegex(cob.BundleError, field):
                        cob.validate_bundle(bundle)

        bundle = copy.deepcopy(self.valid)
        bundle["provenance"]["source_aggregate_sha256"] = []
        with self.assertRaisesRegex(cob.BundleError, "source_aggregate_sha256"):
            cob.validate_bundle(bundle)

    def test_consistency_checks_catch_rehashed_edits(self) -> None:
        bundle = copy.deepcopy(self.valid)
        bundle["segments"][0]["customer_count"] += 1
        bundle["segments"][1]["customer_count"] -= 1
        with self.assertRaisesRegex(cob.BundleError, "accepted corrected-V2"):
            cob.validate_bundle(_rehash(bundle))
        bundle = copy.deepcopy(self.valid)
        bundle["concentration"]["top_decile_share"] += 0.01
        with self.assertRaisesRegex(cob.BundleError, "top-decile share"):
            cob.validate_bundle(_rehash(bundle))
        bundle = copy.deepcopy(self.valid)
        row = next(r for r in bundle["repeat_90d"] if r["mature_customer_count"] > 0)
        row["conversion_fraction"] = 0.99
        with self.assertRaisesRegex(cob.BundleError, "conversion"):
            cob.validate_bundle(_rehash(bundle))
        bundle = copy.deepcopy(self.valid)
        bundle["repeat_90d"].append({**bundle["repeat_90d"][0], "first_observed_month": "ALL"})
        with self.assertRaisesRegex(cob.BundleError, "strata"):
            cob.validate_bundle(_rehash(bundle))

    def test_identifier_fields_and_unsuppressed_small_cells_rejected(self) -> None:
        bundle = copy.deepcopy(self.valid)
        bundle["segments"][0]["customer_id"] = "synthetic-placeholder"
        with self.assertRaisesRegex(cob.BundleError, "forbidden customer-level field"):
            cob.validate_bundle(_rehash(bundle))
        bundle = copy.deepcopy(self.valid)
        cell = next(r for r in bundle["cohort_activity"] if r["cell_status"] == "suppressed_small_cell")
        cell.update(cell_status="observed_complete", active_customers=2, activity_fraction=2 / cell["cohort_size"])
        with self.assertRaisesRegex(cob.BundleError, "small cohort cell"):
            cob.validate_bundle(_rehash(bundle))
        bundle = copy.deepcopy(self.valid)
        future = next(r for r in bundle["cohort_activity"] if r["cell_status"] == "not_observed_incomplete_or_future")
        future.update(active_customers=0, activity_fraction=0.0)
        with self.assertRaisesRegex(cob.BundleError, "null"):
            cob.validate_bundle(_rehash(bundle))

    def test_builder_rejects_missing_private_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as empty:
            with self.assertRaisesRegex(cob.BundleError, "missing"):
                cob.build_bundle(empty)


class MetricFunctionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundle = cob.load_bundle(cob.DEFAULT_BUNDLE_PATH)

    def test_repeat_table_keeps_immature_strata_null_and_unpooled(self) -> None:
        table = com.repeat_table(self.bundle)
        self.assertEqual(len(table), 25)
        self.assertNotIn("ALL", set(table["first_observed_month"]))
        immature = table.loc[table["maturity"].eq("Not yet mature")]
        self.assertTrue(immature["conversion_pct"].isna().all())
        self.assertEqual(set(immature["first_observed_month"]), {"2011-10", "2011-11", "2011-12"})
        self.assertEqual(table.loc[table["maturity"].eq("Partly mature"), "first_observed_month"].tolist(), ["2011-09"])

    def test_concentration_and_segments_reconcile(self) -> None:
        conc = com.concentration_table(self.bundle)
        self.assertAlmostEqual(conc["share_of_gross"].sum(), 1.0, places=12)
        self.assertEqual(conc["customers"].sum(), 5852)
        segments = com.segment_table(self.bundle)
        self.assertEqual(segments["customer_count"].sum(), 5852)
        self.assertAlmostEqual(segments["share_of_customers"].sum(), 1.0, places=12)
        self.assertEqual(segments["frequency_label"].tolist()[:3], ["One purchase day"] * 3)

    def test_cohort_table_excludes_entry_and_preserves_unavailable_cells(self) -> None:
        for population in com.POPULATION_LABELS:
            table = com.cohort_table(self.bundle, population)
            self.assertTrue((table["month_index"] > 0).all())
            unavailable = table["cell_status"].ne("observed_complete")
            self.assertTrue(table.loc[unavailable, "activity_pct"].isna().all())
            self.assertTrue(table.loc[~unavailable, "activity_pct"].notna().all())
        with self.assertRaises(ValueError):
            com.cohort_table(self.bundle, "unknown")
        headline = com.headline_metrics(self.bundle)
        self.assertAlmostEqual(headline["occasions_per_customer"], 36594 / 5852)


if __name__ == "__main__":
    unittest.main()
