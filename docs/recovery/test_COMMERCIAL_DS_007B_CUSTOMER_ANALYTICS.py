import unittest
from datetime import date, timedelta
from decimal import Decimal

from COMMERCIAL_DS_007B_CUSTOMER_ANALYTICS import (
    POPULATION_BEFORE_CUTOFF,
    POPULATION_ON_OR_AFTER_CUTOFF,
    build_cohort_activity,
    build_customer_analytics,
    build_customer_metrics,
    build_repeat_summary,
)


def occasion(customer_id, invoice_id, day, gross="10.000", source_row=1):
    return {
        "customer_id": str(customer_id),
        "invoice_id": invoice_id,
        "transaction_date": day.isoformat(),
        "qualifying_gross_merchandise": gross,
        "eligible_line_count": 1,
        "source_row_numbers": [source_row],
    }


class CorrectedV2CustomerAnalyticsTests(unittest.TestCase):
    def test_customer_uniqueness_canonical_ids_and_exact_decimal_metrics(self):
        rows = [
            occasion(100, "500001", date(2011, 1, 1), "0.125", 1),
            occasion(100, "500002", date(2011, 1, 1), "1.005", 2),
            occasion(100, "500003", date(2011, 3, 31), "10.10", 3),
        ]
        metrics = build_customer_metrics(rows)
        self.assertEqual(len(metrics), 1)
        row = metrics[0]
        self.assertEqual(row["customer_id"], "100")
        self.assertEqual(row["qualifying_occasion_count"], 3)
        self.assertEqual(row["distinct_purchase_day_count"], 2)
        self.assertEqual(row["first_observed_date"], "2011-01-01")
        self.assertEqual(row["last_observed_date"], "2011-03-31")
        self.assertEqual(row["first_observed_month"], "2011-01")
        self.assertEqual(row["observed_tenure_days"], 89)
        self.assertEqual(row["recency_days"], (date(2011, 12, 9) - date(2011, 3, 31)).days)
        self.assertTrue(row["recency_reference_date_is_partial"])
        self.assertEqual(row["qualifying_gross_merchandise"], Decimal("11.230"))
        with self.assertRaisesRegex(ValueError, "duplicate customer × invoice"):
            build_customer_metrics([rows[0], rows[0]])
        with self.assertRaisesRegex(ValueError, "canonical positive integer"):
            build_customer_metrics([occasion("00100", "500004", date(2011, 1, 1))])

    def test_same_day_invoices_are_separate_occasions_but_one_purchase_day(self):
        day = date(2011, 1, 1)
        rows = [occasion(100, "500001", day, source_row=1), occasion(100, "500002", day, source_row=2)]
        result = build_customer_analytics(rows)
        customer = result["customer_metrics"][0]
        self.assertEqual(customer["qualifying_occasion_count"], 2)
        self.assertEqual(customer["distinct_purchase_day_count"], 1)
        self.assertIsNone(customer["days_to_second_purchase_within_90d"])
        repeat = result["repeat_90d_by_first_observed_month"][0]
        self.assertEqual(repeat["repeat_numerator"], 0)

    def test_day_89_is_included_and_day_90_is_excluded(self):
        first = date(2011, 1, 1)
        day_89 = first + timedelta(days=89)
        day_90 = first + timedelta(days=90)
        rows = [
            occasion(100, "500001", first, source_row=1),
            occasion(100, "500002", day_89, source_row=2),
            occasion(101, "500003", first, source_row=3),
            occasion(101, "500004", day_90, source_row=4),
        ]
        summary = build_repeat_summary(build_customer_metrics(rows))
        self.assertEqual(len(summary), 1)
        self.assertEqual(summary[0]["mature_customer_count"], 2)
        self.assertEqual(summary[0]["repeat_numerator"], 1)
        self.assertEqual(summary[0]["denominator"], 2)
        self.assertEqual(summary[0]["conversion_fraction"], 0.5)
        self.assertEqual(summary[0]["mature_repeat_timing_count"], 1)
        self.assertEqual(summary[0]["median_days_to_second_purchase_among_mature_repeaters"], 89)

    def test_immature_observed_repeat_remains_outside_denominator(self):
        first = date(2011, 9, 11)
        rows = [
            occasion(200, "500001", first, source_row=1),
            occasion(200, "500002", first + timedelta(days=89), source_row=2),
        ]
        result = build_customer_analytics(rows)
        summary = result["repeat_90d_by_first_observed_month"][0]
        self.assertEqual(summary["eligible_customer_count"], 1)
        self.assertEqual(summary["mature_customer_count"], 0)
        self.assertEqual(summary["repeat_numerator"], 0)
        self.assertEqual(summary["denominator"], 0)
        self.assertIsNone(summary["conversion_fraction"])
        self.assertEqual(summary["insufficient_follow_up_count"], 1)
        self.assertEqual(result["customer_metrics"][0]["days_to_second_purchase_within_90d"], 89)

    def test_maturity_boundary_september_10_is_mature_september_11_is_not(self):
        rows = [
            occasion(210, "500001", date(2011, 9, 10), source_row=1),
            occasion(211, "500002", date(2011, 9, 11), source_row=2),
        ]
        summary = build_repeat_summary(build_customer_metrics(rows))
        self.assertEqual(len(summary), 1)
        self.assertEqual(summary[0]["eligible_customer_count"], 2)
        self.assertEqual(summary[0]["mature_customer_count"], 1)
        self.assertEqual(summary[0]["denominator"], 1)
        self.assertEqual(summary[0]["insufficient_follow_up_count"], 1)

    def test_cutoff_populations_remain_separate_and_no_pooled_rate_is_emitted(self):
        rows = [
            occasion(200, "500001", date(2010, 11, 30), source_row=1),
            occasion(200, "500002", date(2010, 12, 1), source_row=2),
            occasion(201, "500003", date(2010, 12, 1), source_row=3),
        ]
        result = build_customer_analytics(rows)
        groups = result["repeat_90d_by_first_observed_month"]
        self.assertEqual({row["population"] for row in groups}, {
            POPULATION_BEFORE_CUTOFF,
            POPULATION_ON_OR_AFTER_CUTOFF,
        })
        self.assertEqual({row["first_observed_month"] for row in groups}, {"2010-11", "2010-12"})
        pre_cutoff = next(row for row in groups if row["first_observed_month"] == "2010-11")
        self.assertEqual(pre_cutoff["population"], POPULATION_BEFORE_CUTOFF)
        self.assertEqual(pre_cutoff["eligible_customer_count"], 1)
        self.assertEqual(pre_cutoff["repeat_numerator"], 1)
        self.assertFalse(any("pooled" in row["population"] for row in groups))
        self.assertFalse(result["reconciliation"]["pooled_repeat_rate_published"])

    def test_cohort_maturity_partial_december_and_future_cells_are_null(self):
        rows = [
            occasion(300, "500001", date(2011, 11, 30), source_row=1),
            occasion(301, "500002", date(2011, 12, 1), source_row=2),
        ]
        metrics = build_customer_metrics(rows)
        cohorts = build_cohort_activity(rows, metrics)
        nov0 = next(r for r in cohorts if r["cohort_month"] == "2011-11" and r["month_index"] == 0)
        nov1 = next(r for r in cohorts if r["cohort_month"] == "2011-11" and r["month_index"] == 1)
        nov2 = next(r for r in cohorts if r["cohort_month"] == "2011-11" and r["month_index"] == 2)
        dec0 = next(r for r in cohorts if r["cohort_month"] == "2011-12" and r["month_index"] == 0)
        self.assertEqual((nov0["active_customers"], nov0["activity_fraction"]), (1, 1.0))
        self.assertTrue(nov0["is_mature"])
        self.assertTrue(nov0["is_cohort_entry"])
        self.assertEqual(nov0["cell_status"], "observed_complete")
        self.assertFalse(nov1["is_cohort_entry"])
        self.assertTrue(dec0["is_cohort_entry"])
        for row in (nov1, nov2, dec0):
            self.assertFalse(row["is_mature"])
            self.assertIsNone(row["active_customers"])
            self.assertIsNone(row["activity_fraction"])
        self.assertEqual(nov1["activity_month"], "2011-12")
        self.assertEqual(nov2["activity_month"], "2012-01")
        self.assertEqual(dec0["cohort_size"], 1)

    def test_anonymous_activity_cannot_be_assigned_to_customer(self):
        with self.assertRaisesRegex(ValueError, "canonical positive integer"):
            build_customer_metrics([occasion(None, "500001", date(2011, 1, 1))])

    def test_outputs_are_stable_under_shuffled_occasion_order(self):
        rows = [
            occasion(500, "500001", date(2010, 11, 30), "3.125", 1),
            occasion(500, "500002", date(2010, 12, 2), "4.875", 2),
            occasion(501, "500003", date(2011, 11, 30), "8.00", 3),
            occasion(502, "500004", date(2011, 12, 1), "2.25", 4),
        ]
        forward = build_customer_analytics(rows)
        backward = build_customer_analytics(list(reversed(rows)))
        self.assertEqual(forward, backward)


if __name__ == "__main__":
    unittest.main()
