from __future__ import annotations
import copy, json, os, tempfile, unittest
from pathlib import Path
import importlib.util
from src.targeting_bundle import BundleError, DEFAULT_BUNDLE_PATH, EXPECTED_CONTENT_SHA256, load_bundle, validate_bundle, content_hash
from src.targeting_metrics import policy_comparison, pairwise_comparison

class TargetingBundleTests(unittest.TestCase):
    def setUp(self): self.bundle=load_bundle()

    def test_schema_provenance_and_independent_pin(self):
        self.assertEqual(validate_bundle(self.bundle)["content_sha256"],EXPECTED_CONTENT_SHA256)
        self.assertEqual(self.bundle["provenance"]["source_documents"]["results"],"docs/research/COMMERCIAL_DS_P2_M3_002_TARGETING_COMPARISON.md")

    def test_exact_capacity_and_policy_values(self):
        self.assertEqual({v["capacity"] for v in self.bundle["capacities"].values()},{.05,.1,.2})
        bad=copy.deepcopy(self.bundle); bad["capacities"]["15pct"]={"capacity":.15,"policies":{},"model_c_differences":{}}
        with self.assertRaises(BundleError): validate_bundle(bad)
        self.assertEqual(set(self.bundle["definitions"]["policy_labels"]),{"model_c","rfm","frequency","random"})

    def test_customer_level_fields_rejected(self):
        bad=copy.deepcopy(self.bundle); bad["capacities"]["10pct"]["customer_id"]="private"
        bad["content_sha256"]=content_hash(bad)
        with self.assertRaises(BundleError): validate_bundle(bad)

    def test_unavailable_policy_intervals_remain_null(self):
        self.assertIsNone(self.bundle["capacities"]["10pct"]["policies"]["model_c"]["precision_interval"])
        pair=pairwise_comparison(self.bundle,.1)
        self.assertEqual(len(pair),6)

    def test_missing_and_malformed_bundle_controlled(self):
        with self.assertRaisesRegex(BundleError,"not found"): load_bundle("/tmp/not-a-targeting-bundle.json")
        with tempfile.NamedTemporaryFile(mode="w",suffix=".json") as f:
            f.write("{"); f.flush()
            with self.assertRaises(BundleError): load_bundle(f.name)

    def test_malformed_section_and_provenance_raise_bundle_error(self):
        bad_section=copy.deepcopy(self.bundle); bad_section["capacities"]=None
        with self.assertRaisesRegex(BundleError,"capacities must be an object"):
            validate_bundle(bad_section)
        bad_provenance=copy.deepcopy(self.bundle); bad_provenance["provenance"]["source_documents"]={}
        with self.assertRaisesRegex(BundleError,"provenance source_documents"):
            validate_bundle(bad_provenance)

    @unittest.skipUnless(importlib.util.find_spec("streamlit"), "Streamlit app dependency unavailable")
    def test_malformed_bundle_shows_page_error(self):
        from streamlit.testing.v1 import AppTest
        root=Path(__file__).resolve().parents[1]
        broken=copy.deepcopy(self.bundle); broken["capacities"]=None
        with tempfile.NamedTemporaryFile(mode="w",suffix=".json") as f:
            json.dump(broken,f); f.flush()
            old=os.environ.get("TARGETING_BUNDLE"); os.environ["TARGETING_BUNDLE"]=f.name
            try:
                def script(root):
                    import sys
                    sys.path.insert(0,str(root/"app")); sys.path.insert(0,str(root/"src"))
                    from views.targeting_explorer import render_targeting_explorer
                    render_targeting_explorer()
                app=AppTest.from_function(script,args=(root,),default_timeout=60).run()
            finally:
                if old is None: os.environ.pop("TARGETING_BUNDLE",None)
                else: os.environ["TARGETING_BUNDLE"]=old
        self.assertFalse(app.exception,[e.value for e in app.exception])
        self.assertEqual(len(app.error),1)
        self.assertIn("aggregate targeting bundle could not be loaded",app.error[0].value)

    def test_capacity_preparation(self):
        self.assertEqual(len(policy_comparison(self.bundle,.05)),4)
        with self.assertRaises(ValueError): policy_comparison(self.bundle,.15)

    @unittest.skipUnless(importlib.util.find_spec("streamlit"), "Streamlit app dependency unavailable")
    def test_targeting_page_capacity_comparison_and_caveats(self):
        from streamlit.testing.v1 import AppTest
        root=Path(__file__).resolve().parents[1]
        def script(root):
            import sys
            sys.path.insert(0,str(root/"app")); sys.path.insert(0,str(root/"src"))
            from views.targeting_explorer import render_targeting_explorer
            render_targeting_explorer()
        app=AppTest.from_function(script,args=(root,),default_timeout=60).run()
        self.assertFalse(app.exception,[e.value for e in app.exception])
        self.assertEqual(app.title[0].value,"CRM Targeting Explorer")
        self.assertIn("Model C versus alternatives",[x.value for x in app.subheader])
        self.assertTrue(any("not randomized treatment response" in x.value for x in app.warning))
        self.assertIn("Frequency-rule pooled precision; Model C has no material ties.",[x.value for x in app.caption])
        self.assertTrue(any("About 17%" in x.value and "0.5–0.7 percentage points" in x.value and "not replacement estimates" in x.value for x in app.markdown))
        for capacity in ("5%", "10%", "20%"):
            app.radio(key="targeting_capacity").set_value(capacity).run()
            self.assertFalse(app.exception,[e.value for e in app.exception])
            self.assertIn(f"Policy comparison at {capacity} capacity",[x.value for x in app.subheader])

if __name__=="__main__": unittest.main()
