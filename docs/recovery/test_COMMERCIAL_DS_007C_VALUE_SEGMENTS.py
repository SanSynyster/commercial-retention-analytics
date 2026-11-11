import csv
import io
import unittest
from datetime import date, timedelta
from decimal import Decimal

from COMMERCIAL_DS_007C_VALUE_SEGMENTS import (
    SEGMENT_FIELDS,
    _write_csv,
    apply_top_decile_flag,
    build_concentration,
    build_descriptive_segments,
    build_signed_merchandise_sensitivity,
)
from COMMERCIAL_DS_007B_CUSTOMER_ANALYTICS import build_customer_metrics


def metric(cid, gross="10.00", days=1, recency=0, first="2011-12-09"):
    return {
        "customer_id": str(cid),
        "qualifying_gross_merchandise": Decimal(gross),
        "distinct_purchase_day_count": days,
        "recency_days": recency,
        "first_observed_date": first,
    }


class CorrectedV2ValueSegmentTests(unittest.TestCase):
    def test_deterministic_tie_order_and_top_decile_ceiling(self):
        customers = [metric(i, "1.00") for i in range(11, 0, -1)]
        ranked, summary = build_concentration(customers, Decimal("7.25"))
        self.assertEqual([r["customer_id"] for r in ranked[:2]], ["1", "2"])
        self.assertEqual(summary["top_decile_customer_count"], 2)
        self.assertEqual(summary["top_decile_qualifying_gross"], Decimal("2.00"))
        self.assertEqual(summary["identified_qualifying_gross_denominator"], Decimal("11.00"))
        self.assertEqual(summary["top_decile_share"], Decimal(2) / Decimal(11))
        self.assertEqual(summary["unattributed_positive_merchandise_excluded"], Decimal("7.25"))

    def test_tie_order_is_stable_under_input_shuffle(self):
        rows = [metric(30, "5"), metric(10, "5"), metric(20, "5")]
        a, summary_a = build_concentration(rows, "0")
        b, summary_b = build_concentration(list(reversed(rows)), "0")
        self.assertEqual(a, b)
        self.assertEqual(summary_a, summary_b)
        self.assertEqual([r["customer_id"] for r in a], ["10", "20", "30"])

    def test_signed_sensitivity_reconciles_leaves_excludes_anonymous_and_credits(self):
        rows = [
            {"source_row_number": 1, "category": "merchandise", "Quantity": 2, "UnitPrice": "5.00", "CustomerID": 10},
            {"source_row_number": 2, "category": "merchandise", "Quantity": -1, "UnitPrice": "3.00", "CustomerID": 10},
            {"source_row_number": 3, "category": "merchandise", "Quantity": -1, "UnitPrice": "4.00", "CustomerID": 20},
            {"source_row_number": 4, "category": "merchandise", "Quantity": -1, "UnitPrice": "2.00", "CustomerID": None},
            {"source_row_number": 5, "category": "standalone_manual_credit", "Quantity": -1, "UnitPrice": "99.00", "CustomerID": 10},
        ]
        leaves = {
            "qualifying_gross_merchandise_purchases": {"identifiable_amount": "10.00", "identifiable_rows": 1},
            "merchandise_returns_cancellations": {"identifiable_amount": "-7.00", "identifiable_rows": 2, "unattributed_amount": "-2.00", "unattributed_rows": 1},
            "standalone_manual_credits": {"identifiable_amount": "-99.00"},
        }
        customers, summary = build_signed_merchandise_sensitivity(rows, {1}, leaves)
        self.assertEqual(len(customers), 2)
        c10, c20 = customers
        self.assertEqual(c10["customer_id"], "10")
        self.assertEqual(c10["unlinked_signed_merchandise_sensitivity"], Decimal("7.00"))
        self.assertFalse(c10["is_negative_net_sensitivity"])
        self.assertTrue(c20["is_returns_only"])
        self.assertTrue(c20["is_negative_net_sensitivity"])
        self.assertEqual(c20["unlinked_signed_merchandise_sensitivity"], Decimal("-4.00"))
        self.assertEqual(summary["signed_merchandise_sensitivity_amount"], Decimal("3.00"))
        self.assertEqual(summary["returns_only_customer_count"], 1)
        self.assertEqual(summary["unattributed_return_cancellation_rows_excluded"], 1)
        self.assertEqual(summary["unattributed_return_cancellation_signed_amount_excluded"], Decimal("-2.00"))
        self.assertFalse(summary["manual_credits_included"])
        self.assertEqual(summary["manual_credits_bridge_identifiable_amount_separate"], Decimal("-99.00"))

    def test_recency_boundaries_and_same_day_invoice_count(self):
        rows = [
            metric(1, days=1, recency=59), metric(2, days=2, recency=60),
            metric(3, days=1, recency=89), metric(4, days=2, recency=90),
        ]
        customers, groups, _ = build_descriptive_segments(rows)
        states = {r["customer_id"]: r["recency_state"] for r in customers}
        self.assertEqual(states, {"1": "active_observed", "2": "inactive_60_89_days", "3": "inactive_60_89_days", "4": "no_observed_purchase_90_plus_days"})
        self.assertEqual(customers[0]["purchase_frequency"], "one_observed_purchase_day")
        self.assertEqual(customers[1]["purchase_frequency"], "repeat_observed_purchase_days")
        self.assertEqual(len(groups), 6)
        self.assertEqual(sum(r["customer_count"] for r in groups), 4)
        same_day_occasions = [
            {"customer_id": "50", "invoice_id": "A", "transaction_date": "2011-01-01", "qualifying_gross_merchandise": "3.00", "eligible_line_count": 1},
            {"customer_id": "50", "invoice_id": "B", "transaction_date": "2011-01-01", "qualifying_gross_merchandise": "4.00", "eligible_line_count": 1},
        ]
        same_day_customer = build_customer_metrics(same_day_occasions)[0]
        self.assertEqual(same_day_customer["qualifying_occasion_count"], 2)
        self.assertEqual(same_day_customer["distinct_purchase_day_count"], 1)
        same_day_segment, _, _ = build_descriptive_segments([same_day_customer])
        self.assertEqual(same_day_segment[0]["purchase_frequency"], "one_observed_purchase_day")

    def test_recent_first_observed_flag_and_top_decile_are_independent(self):
        recent_date = (date(2011, 12, 9) - timedelta(days=30)).isoformat()
        outside_date = (date(2011, 12, 9) - timedelta(days=31)).isoformat()
        rows = [
            metric(1, "100", days=1, recency=0, first=recent_date),
            metric(2, "1", days=2, recency=90, first="2010-01-01"),
            metric(3, "0.50", days=1, recency=90, first=outside_date),
        ]
        seg_customers, _, _ = build_descriptive_segments(rows)
        ranked, _ = build_concentration(rows, "0")
        apply_top_decile_flag(seg_customers, ranked)
        flags = {row["customer_id"]: (row["recent_first_observed_30d"], row["top_decile_qualifying_gross"]) for row in seg_customers}
        self.assertEqual(flags["1"], (True, True))
        self.assertEqual(flags["2"], (False, False))
        self.assertEqual(flags["3"], (False, False))
        self.assertEqual(len({(r["purchase_frequency"], r["recency_state"]) for r in seg_customers}), 3)

    def test_aggregate_serialization_is_deterministic(self):
        customers = [metric(2, "2.000", days=2, recency=60), metric(1, "1.230", days=1, recency=10)]
        _, rows_a, _ = build_descriptive_segments(customers)
        _, rows_b, _ = build_descriptive_segments(list(reversed(customers)))
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            p1, p2 = Path(tmp) / "a.csv", Path(tmp) / "b.csv"
            _write_csv(p1, rows_a, SEGMENT_FIELDS)
            _write_csv(p2, rows_b, SEGMENT_FIELDS)
            self.assertEqual(p1.read_bytes(), p2.read_bytes())
            self.assertIn("1.230", p1.read_text())
            self.assertIn("2.000", p1.read_text())


if __name__ == "__main__":
    unittest.main()
