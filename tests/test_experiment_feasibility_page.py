from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

from src.crm_pilot_feasibility import (
    allocate_enrollment,
    mean_difference_mde,
)
from src.experiment_feasibility_metrics import build_scenario, effect_mde_interpretation, sensitivity_table


class ExperimentFeasibilityMetricsTests(unittest.TestCase):
    def test_adapter_agrees_with_frozen_m4_reference_example(self):
        scenario = build_scenario(10_000, 0.10, 50.0, 1.0, 0.20)
        allocation = scenario["allocation"]
        economics = scenario["economics"]
        self.assertEqual((allocation["enrolled_customers"], allocation["treatment_customers"], allocation["control_customers"]), (1_000, 500, 500))
        self.assertAlmostEqual(scenario["mde_gbp_per_randomized_customer"], 8.86, places=2)
        self.assertAlmostEqual(economics["net_incremental_contribution_gbp_per_treatment_assignment"], 0.80)
        self.assertAlmostEqual(economics["total_expected_net_incremental_contribution_gbp"], 400.0)
        self.assertAlmostEqual(economics["net_incremental_contribution_gbp_per_enrolled_customer"], 0.40)
        self.assertAlmostEqual(economics["break_even_gross_contribution_gbp_per_treatment_assignment"], 0.20)
        self.assertAlmostEqual(scenario["statistical_comparison"]["net_itt_effect_gbp_per_randomized_customer"], 0.80)
        self.assertFalse(scenario["statistical_comparison"]["net_effect_at_or_above_approx_80pct_power_mde"])

    def test_mde_interpretation_default_above_break_even_and_negative(self):
        default = build_scenario(10_000, 0.10, 50.0, 1.0, 0.20)
        below = effect_mde_interpretation(
            default["economics"]["net_incremental_contribution_gbp_per_treatment_assignment"],
            default["mde_gbp_per_randomized_customer"], default["statistical_comparison"],
        )
        self.assertFalse(below["meets_mde"])
        self.assertIn("assumed £0.80 net ITT effect is below the approximate £8.86 MDE", below["message"])
        self.assertIn("positive hypothetical campaign contribution does not mean", below["message"])

        above_scenario = build_scenario(100_000, 0.10, 20.0, 5.0, 0.01)
        above = effect_mde_interpretation(
            above_scenario["economics"]["net_incremental_contribution_gbp_per_treatment_assignment"],
            above_scenario["mde_gbp_per_randomized_customer"], above_scenario["statistical_comparison"],
        )
        self.assertTrue(above["meets_mde"])
        self.assertIn("meets or exceeds", above["message"])
        self.assertIn("Statistical significance is not guaranteed", above["message"])

        break_even_scenario = build_scenario(10_000, 0.10, 50.0, 0.20, 0.20)
        break_even = effect_mde_interpretation(
            break_even_scenario["economics"]["net_incremental_contribution_gbp_per_treatment_assignment"],
            break_even_scenario["mde_gbp_per_randomized_customer"], break_even_scenario["statistical_comparison"],
        )
        self.assertFalse(break_even["meets_mde"])
        self.assertIn("assumed £0.00 net ITT effect", break_even["message"])

        negative_scenario = build_scenario(10_000, 0.10, 50.0, 0.0, 1.0)
        negative = effect_mde_interpretation(
            negative_scenario["economics"]["net_incremental_contribution_gbp_per_treatment_assignment"],
            negative_scenario["mde_gbp_per_randomized_customer"], negative_scenario["statistical_comparison"],
        )
        self.assertFalse(negative["meets_mde"])
        self.assertIn("negative (−£1.00)", negative["message"])

    def test_allocation_and_mde_are_the_m4_functions(self):
        scenario = build_scenario(25, 0.10, 20, 1.0, 0.20)
        self.assertEqual(scenario["allocation"], allocate_enrollment(25, 0.10))
        self.assertEqual(scenario["mde_gbp_per_randomized_customer"], mean_difference_mde(2, 1, 20))
        table = sensitivity_table(scenario)
        self.assertEqual(list(table["Enrollment capacity"]), [0.10, 0.20, 0.50, 1.0])

    def test_break_even_is_zero_expected_net_value(self):
        economics = build_scenario(1_000, 0.10, 50, 0.20, 0.20)["economics"]
        self.assertEqual(economics["net_incremental_contribution_gbp_per_treatment_assignment"], 0)
        self.assertEqual(economics["total_expected_net_incremental_contribution_gbp"], 0)
        self.assertEqual(economics["net_incremental_contribution_gbp_per_enrolled_customer"], 0)

    def test_m4_input_validation_is_preserved(self):
        for args in ((0, 0.1, 50, 1, 0.2), (100, 0, 50, 1, 0.2), (100, 0.1, 0, 1, 0.2), (100, 0.1, 50, 1, -0.1)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                build_scenario(*args)


@unittest.skipUnless(importlib.util.find_spec("streamlit"), "Streamlit app dependency unavailable")
class ExperimentFeasibilityPageTests(unittest.TestCase):
    def test_page_renders_controls_and_updates_scenario(self):
        from streamlit.testing.v1 import AppTest

        root = Path(__file__).resolve().parents[1]

        def script(root):
            import sys
            sys.path.insert(0, str(root / "app"))
            sys.path.insert(0, str(root / "src"))
            from views.experiment_feasibility import render
            render()

        app = AppTest.from_function(script, args=(root,), default_timeout=60).run()
        self.assertFalse(app.exception, [e.value for e in app.exception])
        self.assertEqual(app.title[0].value, "CRM Experiment Feasibility")
        self.assertIn("Approximate MDE for treatment − control mean net margin", [m.label for m in app.metric])
        self.assertIn("Hypothetical net ITT effect", [m.label for m in app.metric])
        self.assertIn("Enrolled customers", [m.label for m in app.metric])
        self.assertTrue(any("no causal CRM uplift has been measured" in w.value for w in app.warning))
        self.assertTrue(any("assumed £0.80 net ITT effect is below the approximate £8.86 MDE" in w.value for w in app.warning))
        values = {m.label: m.value for m in app.metric}
        self.assertEqual(values["Enrolled customers"], "1,000")
        self.assertEqual(values["Treatment assignments"], "500")
        app.selectbox(key="experiment_capacity").set_value(0.2).run()
        self.assertFalse(app.exception, [e.value for e in app.exception])
        values = {m.label: m.value for m in app.metric}
        self.assertEqual(values["Enrolled customers"], "2,000")
        self.assertEqual(values["Treatment assignments"], "1,000")

        app.number_input(key="experiment_eligible_customers").set_value(100_000).run()
        app.selectbox(key="experiment_outcome_sd").set_value("£20.00").run()
        app.selectbox(key="experiment_gross_increment").set_value("£5.00").run()
        app.selectbox(key="experiment_contact_cost").set_value("£0.01").run()
        self.assertTrue(any("meets or exceeds" in info.value and "not guaranteed" in info.value for info in app.info))

        app.number_input(key="experiment_eligible_customers").set_value(10_000).run()
        app.selectbox(key="experiment_capacity").set_value(0.10).run()
        app.selectbox(key="experiment_outcome_sd").set_value("£50.00").run()
        app.selectbox(key="experiment_gross_increment").set_value("£0.20").run()
        app.selectbox(key="experiment_contact_cost").set_value("£0.20").run()
        self.assertTrue(any("assumed £0.00 net ITT effect" in warning.value for warning in app.warning))
        app.selectbox(key="experiment_gross_increment").set_value("£0.00").run()
        app.selectbox(key="experiment_contact_cost").set_value("£1.00").run()
        self.assertTrue(any("negative (−£1.00)" in warning.value for warning in app.warning))


if __name__ == "__main__":
    unittest.main()
