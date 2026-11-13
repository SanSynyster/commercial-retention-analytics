from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app/streamlit_app.py"

STREAMLIT_AVAILABLE = importlib.util.find_spec("streamlit") is not None


@unittest.skipUnless(STREAMLIT_AVAILABLE, "Streamlit is not installed; install requirements-app.txt.")
class DashboardAppTests(unittest.TestCase):
    def _run(self, page: str | None = None):
        from streamlit.testing.v1 import AppTest

        app = AppTest.from_file(str(APP), default_timeout=60)
        app.run()
        if page is not None:
            app.switch_page(page)
            app.run()
        return app

    def test_customer_overview_renders_without_errors(self) -> None:
        app = self._run()
        self.assertFalse(app.exception, [e.value for e in app.exception])
        self.assertEqual(len(app.error), 0)
        self.assertEqual(app.title[0].value, "Customer Overview")
        labels = [metric.label for metric in app.metric]
        self.assertIn("Identified customers", labels)
        values = {metric.label: metric.value for metric in app.metric}
        self.assertEqual(values["Identified customers"], "5,852")
        self.assertEqual(values["Qualifying purchase occasions"], "36,594")
        self.assertEqual(values["Top-10% customer gross share"], "63.8%")
        subheaders = [s.value for s in app.subheader]
        self.assertIn("Second purchase within 90 days", subheaders)
        self.assertIn("Purchase frequency × recency groups", subheaders)

    def test_cohort_population_toggle(self) -> None:
        app = self._run()
        app.radio(key="cohort_population").set_value("first_observed_on_or_after_2010-12-01").run()
        self.assertFalse(app.exception)

    def test_navigation_registers_four_pages(self) -> None:
        app = self._run()
        source = APP.read_text(encoding="utf-8")
        for title in ("Customer Overview", "Purchase Propensity", "CRM Targeting Explorer", "CRM Experiment Feasibility"):
            self.assertIn(f'title="{title}"', source)
        self.assertIn("st.navigation(PAGES)", source)
        self.assertFalse(app.exception)

    def test_missing_bundle_shows_error_instead_of_failing(self) -> None:
        previous = os.environ.get("CUSTOMER_OVERVIEW_BUNDLE")
        os.environ["CUSTOMER_OVERVIEW_BUNDLE"] = str(ROOT / "app_data/missing_bundle.json")
        try:
            app = self._run()
        finally:
            if previous is None:
                os.environ.pop("CUSTOMER_OVERVIEW_BUNDLE", None)
            else:
                os.environ["CUSTOMER_OVERVIEW_BUNDLE"] = previous
        self.assertFalse(app.exception)
        self.assertEqual(len(app.error), 1)
        self.assertIn("could not be loaded", app.error[0].value)
        self.assertEqual(len(app.metric), 0)

    def test_malformed_metadata_shows_controlled_bundle_error(self) -> None:
        bundle_path = ROOT / "app_data/customer_overview_v1.json"
        original = json.loads(bundle_path.read_text(encoding="utf-8"))
        for field in ("provenance", "publication_review"):
            with self.subTest(field=field), tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", encoding="utf-8", delete=False
            ) as handle:
                modified = dict(original)
                modified[field] = {}
                json.dump(modified, handle)
                path = Path(handle.name)
            previous = os.environ.get("CUSTOMER_OVERVIEW_BUNDLE")
            os.environ["CUSTOMER_OVERVIEW_BUNDLE"] = str(path)
            try:
                app = self._run()
            finally:
                path.unlink(missing_ok=True)
                if previous is None:
                    os.environ.pop("CUSTOMER_OVERVIEW_BUNDLE", None)
                else:
                    os.environ["CUSTOMER_OVERVIEW_BUNDLE"] = previous
            self.assertFalse(app.exception)
            self.assertEqual(len(app.error), 1)
            self.assertIn("could not be loaded", app.error[0].value)
            self.assertEqual(len(app.metric), 0)


if __name__ == "__main__":
    unittest.main()
