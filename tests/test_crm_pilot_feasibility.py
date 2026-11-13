from __future__ import annotations

import hashlib
import math
import tempfile
import unittest
from pathlib import Path
from statistics import NormalDist

from src.crm_pilot_feasibility import (
    allocate_enrollment,
    capacity_sensitivity,
    commercial_scenarios,
    mean_difference_mde,
    sample_size_scenarios,
    statistical_commercial_comparison,
    variance_reduction_scenarios,
    write_scenario_outputs,
)


class CRMPilotFeasibilityTests(unittest.TestCase):
    def test_capacity_rounding_and_odd_arm_allocation(self):
        self.assertEqual(allocate_enrollment(25, 0.10), {
            "eligible_customers": 25,
            "capacity": 0.10,
            "enrolled_customers": 3,
            "treatment_customers": 2,
            "control_customers": 1,
            "not_enrolled_customers": 22,
            "enrollment_fraction": 3 / 25,
            "treatment_fraction_eligible": 2 / 25,
        })
        self.assertEqual(allocate_enrollment(10, 0.50)["enrolled_customers"], 5)

    def test_full_capacity_and_validation(self):
        allocation = allocate_enrollment(100, 1.0)
        self.assertEqual(allocation["enrolled_customers"], 100)
        self.assertEqual(allocation["not_enrolled_customers"], 0)
        for args in ((10, 0), (10, 1.1), (0, 0.10)):
            with self.assertRaises(ValueError):
                allocate_enrollment(*args)

    def test_mde_matches_predeclared_normal_approximation(self):
        actual = mean_difference_mde(50, 50, 20, alpha=0.05, power=0.80)
        expected = (
            NormalDist().inv_cdf(0.975) + NormalDist().inv_cdf(0.80)
        ) * 20 * math.sqrt(1 / 50 + 1 / 50)
        self.assertAlmostEqual(actual, expected)

    def test_mde_scales_with_sample_size_and_standard_deviation(self):
        base = mean_difference_mde(100, 100, 50)
        self.assertAlmostEqual(mean_difference_mde(400, 400, 50), base / 2)
        self.assertAlmostEqual(mean_difference_mde(100, 100, 100), 2 * base)

    def test_sample_scenarios_reconcile_unique_customer_counts(self):
        scenarios = sample_size_scenarios([1_000], [20, 50])
        self.assertEqual(len(scenarios), 2)
        row = scenarios.iloc[0]
        self.assertEqual(row.enrolled_customers, 100)
        self.assertEqual(row.treatment_customers, 50)
        self.assertEqual(row.control_customers, 50)
        self.assertEqual(row.not_enrolled_customers, 900)
        self.assertEqual(row.enrolled_customers + row.not_enrolled_customers, row.eligible_customers)

    def test_contact_cost_break_even_and_campaign_total(self):
        scenarios = commercial_scenarios([1_000], [0.20], [0.0, 1.0])
        no_increment = scenarios.loc[
            scenarios.incremental_gross_contribution_gbp_per_treatment_assignment == 0
        ].iloc[0]
        self.assertAlmostEqual(no_increment.break_even_gross_contribution_gbp_per_treatment_assignment, 0.20)
        self.assertAlmostEqual(no_increment.net_incremental_contribution_gbp_per_treatment_assignment, -0.20)
        self.assertAlmostEqual(no_increment.expected_contact_cost_gbp, 10.0)
        self.assertAlmostEqual(no_increment.total_expected_net_incremental_contribution_gbp, -10.0)
        break_even = scenarios.loc[
            scenarios.incremental_gross_contribution_gbp_per_treatment_assignment == 1.0
        ].iloc[0]
        self.assertAlmostEqual(break_even.total_expected_net_incremental_contribution_gbp, 40.0)
        self.assertAlmostEqual(
            break_even.total_expected_net_incremental_contribution_gbp,
            break_even.treatment_customers * (1.0 - 0.20),
        )

    def test_itt_arm_difference_is_distinct_from_cohort_average_campaign_value(self):
        campaign = commercial_scenarios([10_000], [0.20], [1.0]).iloc[0]
        comparison = statistical_commercial_comparison(
            [10_000], [50], [0.20], [1.0]
        ).iloc[0]
        self.assertEqual(campaign.treatment_customers, 500)
        self.assertEqual(campaign.enrolled_customers, 1_000)
        self.assertAlmostEqual(campaign.net_incremental_contribution_gbp_per_treatment_assignment, 0.80)
        self.assertAlmostEqual(campaign.total_expected_net_incremental_contribution_gbp, 400.0)
        self.assertAlmostEqual(campaign.net_incremental_contribution_gbp_per_enrolled_customer, 0.40)
        # The ITT arm-mean contrast is g-c (£0.80), while the cohort average is £0.40.
        # The MDE is compared with the arm-mean difference, not the cohort average.
        self.assertAlmostEqual(comparison.net_itt_effect_gbp_per_randomized_customer, 0.80)
        self.assertAlmostEqual(comparison.mde_gbp_per_randomized_customer, mean_difference_mde(500, 500, 50))

    def test_capacity_sensitivity_enrollment_and_mde(self):
        frame = capacity_sensitivity([5_000], [0.10, 0.20, 0.50, 1.0], [50, 100])
        at_10 = frame[(frame.capacity == 0.10) & (frame.outcome_sd_gbp == 50)].iloc[0]
        at_100 = frame[(frame.capacity == 1.0) & (frame.outcome_sd_gbp == 50)].iloc[0]
        self.assertEqual(at_10.enrolled_customers, 500)
        self.assertEqual(at_10.treatment_customers, 250)
        self.assertEqual(at_10.control_customers, 250)
        self.assertEqual(at_100.enrolled_customers, 5_000)
        self.assertLess(at_100.mde_gbp_per_randomized_customer, at_10.mde_gbp_per_randomized_customer)

    def test_variance_reduction_uses_one_minus_r_squared(self):
        frame = variance_reduction_scenarios(10.0, [0.0, 0.25, 0.50])
        self.assertEqual(list(frame.adjusted_variance_ratio), [1.0, 0.75, 0.5])
        expected = [10.0, 10.0 * math.sqrt(0.75), 10.0 * math.sqrt(0.50)]
        for actual, target in zip(frame.adjusted_mde_gbp, expected):
            self.assertAlmostEqual(actual, target)

    def test_scenario_outputs_are_deterministic(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            first = Path(temp_dir) / "first"
            second = Path(temp_dir) / "second"
            write_scenario_outputs(first)
            write_scenario_outputs(second)
            names = (
                "sample_size_scenarios.csv",
                "commercial_scenarios.csv",
                "statistical_commercial_comparison.csv",
                "capacity_sensitivity.csv",
                "m4_002_scenario_manifest.json",
            )
            for name in names:
                digest_first = hashlib.sha256((first / name).read_bytes()).hexdigest()
                digest_second = hashlib.sha256((second / name).read_bytes()).hexdigest()
                self.assertEqual(digest_first, digest_second)


if __name__ == "__main__":
    unittest.main()
