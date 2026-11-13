from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "app")]
STREAMLIT_AVAILABLE = importlib.util.find_spec("streamlit") is not None


@unittest.skipUnless(STREAMLIT_AVAILABLE, "Install requirements-app.txt to render the Streamlit page.")
class PurchasePropensityPageTests(unittest.TestCase):
    def _render(self):
        from streamlit.testing.v1 import AppTest

        def page_script() -> None:
            import sys
            from pathlib import Path

            sys.path[:0] = [str(Path.cwd() / "src"), str(Path.cwd() / "app")]
            from views.purchase_propensity import render

            render()

        app = AppTest.from_function(page_script, default_timeout=60)
        app.run()
        return app

    def test_page_renders_separate_m1_m2_and_calibration_sections(self) -> None:
        app = self._render()
        self.assertFalse(app.exception, [e.value for e in app.exception])
        self.assertEqual(app.title[0].value, "Purchase Propensity")
        headers = [x.value for x in app.header]
        self.assertIn("M1 · New-customer second-purchase prediction", headers)
        self.assertIn("M2 · Established-customer monthly purchase prediction", headers)
        self.assertIn("Exploratory calibration update", headers)
        metric_values = {x.label: x.value for x in app.metric}
        self.assertEqual(metric_values["M1 — Model C ROC-AUC"], "0.519")
        self.assertEqual(metric_values["M2 — Model C ROC-AUC"], "0.766")
        self.assertEqual(metric_values["Predeclared criterion"], "Not met")
        guard = "M1 and M2 evaluate different customer populations and prediction tasks; their performance estimates are not a head-to-head comparison."
        self.assertIn(guard, [x.value for x in app.warning])
        self.assertTrue(any("different months" in x.value and "raw September–November pooled diagnostic was not estimable" in x.value
                            for x in app.caption))
        brier_delta = next(x.delta for x in app.metric if x.label == "Sep–Nov adjusted Brier")
        self.assertEqual(brier_delta, "-0.0045")
        source = (ROOT / "app/views/purchase_propensity.py").read_text(encoding="utf-8")
        self.assertIn('delta_color="inverse"', source)

    def test_missing_and_malformed_bundle_show_controlled_error(self) -> None:
        original = json.loads((ROOT / "app_data/propensity_summary_v1.json").read_text(encoding="utf-8"))
        for payload in (None, {**original, "provenance": {}}):
            with self.subTest(malformed=payload is not None):
                previous = os.environ.get("PURCHASE_PROPENSITY_BUNDLE")
                if payload is None:
                    path = ROOT / "app_data/absent_propensity_bundle.json"
                else:
                    handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
                    json.dump(payload, handle)
                    handle.close()
                    path = Path(handle.name)
                os.environ["PURCHASE_PROPENSITY_BUNDLE"] = str(path)
                try:
                    app = self._render()
                finally:
                    if payload is not None:
                        path.unlink(missing_ok=True)
                    if previous is None:
                        os.environ.pop("PURCHASE_PROPENSITY_BUNDLE", None)
                    else:
                        os.environ["PURCHASE_PROPENSITY_BUNDLE"] = previous
                self.assertFalse(app.exception)
                self.assertEqual(len(app.error), 1)
                self.assertIn("could not be loaded", app.error[0].value)
                self.assertEqual(len(app.metric), 0)


if __name__ == "__main__":
    unittest.main()
