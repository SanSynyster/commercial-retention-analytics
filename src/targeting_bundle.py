"""Pinned, aggregate-only M3 targeting result bundle."""
from __future__ import annotations
import argparse, hashlib, json, math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLE_PATH = ROOT / "app_data/targeting_v1.json"
SOURCE = "docs/research/COMMERCIAL_DS_P2_M3_002_TARGETING_COMPARISON.md"
REVIEW = "docs/research/COMMERCIAL_DS_P2_M3_003_INDEPENDENT_TARGETING_REVIEW.md"
BUNDLE_NAME, BUNDLE_VERSION, SCHEMA_VERSION = "crm_targeting_aggregate", "1.0.0", 1
EXPECTED_CONTENT_SHA256 = "44bcf66762056a8746333239e731e6d79809d2a0a29904924dd9b8c858a7c6f9"
EXPECTED_AGGREGATE_SHA256 = "5e9558f7d26a144587325d6465164bed7f6ce1718facc35f0e7a6cd6c15b509d"
EXPECTED_MANIFEST_SHA256 = "7422a915e6d78f556494867946776dae70a52df3ddb0f73a8e24b37c607358fe"
EXPECTED_SOURCE_MANIFEST_INPUT_SHA256 = {
    "baseline_run_manifest": "81bb760a60c4d9badd6b3b65baf93086165e5a4c30ec1e9391390b4e30c2e14a",
    "dataset": "44c580a83bea993fd0e2f8df8a03bb7aa2f11e64085671ea2ed78c9e28e952a8",
    "predictions": "facdd36297340138ec23ddbd98bc9cc551776c6bdf635e731ced08cc440626c1",
    "source_manifest": "3d7ee78afa96a1d4abe7ee8f7762a994e652bc5c799b892d227f56be03c96a13",
}
EXPECTED_SOURCE_DOCUMENTS = {"results": SOURCE, "independent_review": REVIEW}
EXPECTED_PROVENANCE = {
    "source_aggregate_sha256": EXPECTED_AGGREGATE_SHA256,
    "source_manifest_input_sha256": EXPECTED_SOURCE_MANIFEST_INPUT_SHA256,
    "source_documents": EXPECTED_SOURCE_DOCUMENTS,
    "source_manifest": "m3_002_targeting_manifest.json",
    "builder": "src/targeting_bundle.py",
}
CAPACITY_KEYS = {"5pct": 0.05, "10pct": 0.10, "20pct": 0.20}
POLICY_LABELS = {"model_c": "Model C — 11-feature logistic regression", "rfm": "Model B — RFM logistic regression",
                 "frequency": "365-day qualifying purchase-date frequency", "random": "Random-selection benchmark"}
METRICS = {"precision", "purchase_capture_recall", "lift"}

class BundleError(ValueError): pass

def _hash(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    return hashlib.sha256(raw.encode()).hexdigest()

def content_hash(bundle: dict[str, Any]) -> str:
    return _hash({k: bundle[k] for k in ("holdout", "capacities", "overlap", "frequency_tie_sensitivity", "repeated_selection", "definitions")})

def _finite(x: Any) -> bool:
    return not isinstance(x, bool) and isinstance(x, (int, float)) and math.isfinite(x)

def _require_dict(value: Any, where: str, keys: set[str] | None = None) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise BundleError(f"{where} must be an object")
    if keys is not None and set(value) != keys:
        raise BundleError(f"{where} has missing or unexpected fields")
    return value

def _require_list(value: Any, where: str) -> list[Any]:
    if not isinstance(value, list):
        raise BundleError(f"{where} must be a list")
    return value

def _no_ids(v: Any) -> None:
    forbidden = ("customer_id", "customerid", "prediction", "outcome_row", "selected_customer_ids", "selection_list")
    if isinstance(v, dict):
        for k, x in v.items():
            if any(f in str(k).lower() for f in forbidden): raise BundleError(f"prohibited field: {k}")
            _no_ids(x)
    elif isinstance(v, list):
        for x in v: _no_ids(x)

def validate_bundle(b: Any) -> dict[str, Any]:
    keys = {"bundle_name","bundle_version","schema_version","evidence_label","holdout","capacities","overlap","frequency_tie_sensitivity","repeated_selection","definitions","provenance","content_sha256"}
    _require_dict(b, "targeting bundle", keys)
    for section in ("holdout", "capacities", "overlap", "frequency_tie_sensitivity", "definitions", "provenance"):
        _require_dict(b[section], f"targeting bundle {section}")
    _require_list(b["repeated_selection"], "targeting bundle repeated_selection")
    if isinstance(b["schema_version"], bool) or not isinstance(b["schema_version"], int):
        raise BundleError("schema_version must be an integer")
    if (b["bundle_name"], b["bundle_version"], b["schema_version"], b["evidence_label"]) != (BUNDLE_NAME,BUNDLE_VERSION,SCHEMA_VERSION,"Retrospective targeting"):
        raise BundleError("unsupported targeting bundle identity or evidence label")
    if set(b["capacities"]) != set(CAPACITY_KEYS): raise BundleError("capacities must be exactly 5%, 10% and 20%")
    if set(b["holdout"]) != {"months","snapshots","positive_snapshots","unique_customers","prevalence","capacity_rule"}: raise BundleError("malformed holdout schema")
    if b["holdout"]["snapshots"] != 21672 or b["holdout"]["positive_snapshots"] != 5092: raise BundleError("holdout counts differ from approved M3 results")
    for ck, c in b["capacities"].items():
        _require_dict(c, f"capacities.{ck}", {"capacity","policies","model_c_differences"})
        if not _finite(c["capacity"]) or c["capacity"] != CAPACITY_KEYS[ck]: raise BundleError("capacity key/value not approved")
        _require_dict(c["policies"], f"capacities.{ck}.policies")
        _require_dict(c["model_c_differences"], f"capacities.{ck}.model_c_differences")
        if set(c["policies"]) != set(POLICY_LABELS): raise BundleError("policy set differs from approved M3 policies")
        for p, row in c["policies"].items():
            _require_dict(row, f"capacities.{ck}.policies.{p}", {"selected_snapshots", "precision", "capture", "lift", "precision_interval", "capture_interval"})
            if isinstance(row["selected_snapshots"], bool) or not isinstance(row["selected_snapshots"], int): raise BundleError("invalid selection count")
            for m in ("precision","capture","lift"):
                if not _finite(row[m]): raise BundleError(f"invalid {m}")
            for m in ("precision_interval","capture_interval"):
                ci=row[m]
                if ci is not None and (not isinstance(ci,list) or len(ci)!=2 or not all(_finite(x) for x in ci) or ci[0]>ci[1]): raise BundleError("invalid uncertainty interval")
        if set(c["model_c_differences"]) != {"rfm","frequency","random"}: raise BundleError("malformed pairwise comparisons")
        for comp in c["model_c_differences"].values():
            _require_dict(comp, "model_c_differences entry", {"precision","capture"})
            for v in comp.values():
                _require_dict(v, "pairwise interval", {"estimate","interval"})
                if not _finite(v["estimate"]) or not isinstance(v["interval"],list) or len(v["interval"])!=2 or not all(_finite(x) for x in v["interval"]): raise BundleError("malformed pairwise interval")
    provenance = _require_dict(b["provenance"], "provenance", set(EXPECTED_PROVENANCE))
    for field, expected in EXPECTED_PROVENANCE.items():
        if provenance[field] != expected:
            raise BundleError(f"provenance {field} differs from approved M3 metadata")
    _require_dict(provenance["source_manifest_input_sha256"], "provenance.source_manifest_input_sha256", set(EXPECTED_SOURCE_MANIFEST_INPUT_SHA256))
    _require_dict(provenance["source_documents"], "provenance.source_documents", set(EXPECTED_SOURCE_DOCUMENTS))
    if set(b["overlap"]) != set(CAPACITY_KEYS): raise BundleError("malformed overlap capacities")
    for cap in b["overlap"].values():
        _require_dict(cap, "overlap capacity")
        if set(cap) != {"model_c", "rfm", "frequency", "random_expected"}: raise BundleError("malformed overlap policy set")
        for name, row in cap.items():
            _require_dict(row, f"overlap.{name}")
            required={"expected_intersection_count_across_monthly_snapshots","expected_share_of_model_c_selections","note"} if name=="random_expected" else {"intersection_count_across_monthly_snapshots","share_of_model_c_selections","jaccard_of_summed_monthly_sets"}
            if set(row)!=required: raise BundleError("malformed overlap metrics")
    _require_dict(b["frequency_tie_sensitivity"], "frequency_tie_sensitivity", {"precision_by_rule", "source"})
    tie_rules = _require_dict(b["frequency_tie_sensitivity"]["precision_by_rule"], "frequency_tie_sensitivity.precision_by_rule")
    if set(tie_rules) != set(CAPACITY_KEYS): raise BundleError("malformed tie capacity set")
    for row in tie_rules.values():
        _require_dict(row, "frequency tie sensitivity row")
        if set(row)!={"customer_key_ascending","uniform_random_expectation","customer_key_descending","sha256_key_month"} or not all(_finite(x) for x in row.values()): raise BundleError("malformed tie metrics")
    for row in b["repeated_selection"]:
        _require_dict(row, "repeated_selection row", {"capacity","policy","selected_snapshots","unique_customers","selected_multiple_months","maximum_months_selected"})
    if set(b["definitions"])!={"policy_labels","outcome","evaluation_unit","bootstrap"} or b["definitions"]["policy_labels"]!=POLICY_LABELS: raise BundleError("approved policy labels or definitions missing")
    _no_ids({k:b[k] for k in keys-{"provenance","content_sha256"}})
    if b["content_sha256"] != content_hash(b) or b["content_sha256"] != EXPECTED_CONTENT_SHA256: raise BundleError("targeting content differs from independently pinned approved bundle")
    return b

def load_bundle(path: str|Path=DEFAULT_BUNDLE_PATH) -> dict[str,Any]:
    p=Path(path)
    try: b=json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError: raise BundleError(f"Targeting bundle not found: {p.name}") from None
    except (OSError,UnicodeDecodeError,json.JSONDecodeError) as e: raise BundleError(f"Targeting bundle could not be read: {e}") from None
    return validate_bundle(b)

def build_bundle(aggregate_path: str|Path) -> dict[str,Any]:
    p=Path(aggregate_path)
    try: src=json.loads(p.read_text(encoding="utf-8"))
    except (OSError,UnicodeDecodeError,json.JSONDecodeError) as e: raise BundleError(f"M3 aggregate could not be read: {e}") from None
    if not isinstance(src,dict): raise BundleError("M3 aggregate must be a JSON object")
    if hashlib.sha256(p.read_bytes()).hexdigest() != "5e9558f7d26a144587325d6465164bed7f6ce1718facc35f0e7a6cd6c15b509d": raise BundleError("M3 aggregate hash is not the independently reviewed frozen result")
    pooled=src["monthly_and_pooled_results"]["pooled_snapshot_weighted"]
    intervals=src["paired_customer_cluster_bootstrap"]["difference_intervals"]
    capacities={}
    for ck, cap in CAPACITY_KEYS.items():
        raw=pooled[ck]
        policies={}
        for pkey in POLICY_LABELS:
            r=raw[pkey]
            precision_ci=capture_ci=None
            if pkey!="random":
                comp=intervals[ck].get(f"model_c_minus_{pkey}")
                # Policy intervals themselves are unavailable; paired intervals are preserved below.
            policies[pkey]={"selected_snapshots":int(r["selected_snapshot_events"]),"precision":r["precision_snapshot_weighted"],"capture":r["purchase_capture_recall_snapshot_weighted"],"lift":r["lift_over_pooled_prevalence"],"precision_interval":precision_ci,"capture_interval":capture_ci}
        diffs={}
        for pkey, suffix in (("rfm","rfm"),("frequency","frequency"),("random","random")):
            x=intervals[ck][f"model_c_minus_{suffix}"]
            # Derive point difference from approved pooled point estimates; interval is the frozen paired customer-cluster interval.
            base=pooled[ck]["model_c"]
            other=pooled[ck][pkey]
            diffs[pkey]={"precision":{"estimate":base["precision_snapshot_weighted"]-other["precision_snapshot_weighted"],"interval":x["precision"]},"capture":{"estimate":base["purchase_capture_recall_snapshot_weighted"]-other["purchase_capture_recall_snapshot_weighted"],"interval":x["capture"]}}
        capacities[ck]={"capacity":cap,"policies":policies,"model_c_differences":diffs}
    pooled_overlap=src["monthly_and_pooled_results"]["pooled_overlap_with_model_c"]
    overlap={k:pooled_overlap[k] for k in ("5pct","10pct","20pct")}
    concentration=src["monthly_and_pooled_results"]["contact_concentration_ranked_policies"]
    repeat=[]
    for policy in ("model_c", "frequency"):
        for ck in ("5pct", "10pct", "20pct"):
            stats=concentration[policy][ck]
            repeat.append({"capacity":CAPACITY_KEYS[ck],"policy":policy,"selected_snapshots":stats["total_customer_month_contact_events"],"unique_customers":stats["unique_customers_selected_at_least_once"],"selected_multiple_months":stats["customers_selected_in_multiple_months"],"maximum_months_selected":stats["maximum_months_selected"]})
    tie={"precision_by_rule":{"5pct":{"customer_key_ascending":.8077,"uniform_random_expectation":.8102,"customer_key_descending":.8123,"sha256_key_month":.8114},"10pct":{"customer_key_ascending":.6880,"uniform_random_expectation":.6858,"customer_key_descending":.6848,"sha256_key_month":.6843},"20pct":{"customer_key_ascending":.5420,"uniform_random_expectation":.5389,"customer_key_descending":.5357,"sha256_key_month":.5424}},"source":REVIEW}
    b={"bundle_name":BUNDLE_NAME,"bundle_version":BUNDLE_VERSION,"schema_version":SCHEMA_VERSION,"evidence_label":"Retrospective targeting","holdout":{"months":src["holdout"]["months"],"snapshots":src["holdout"]["snapshots"],"positive_snapshots":src["holdout"]["positive_snapshots"],"unique_customers":src["holdout"]["unique_customers_across_holdout"],"prevalence":src["holdout"]["pooled_prevalence_snapshot_weighted"],"capacity_rule":src["capacity_rule"]},"capacities":capacities,"overlap":overlap,"frequency_tie_sensitivity":tie,"repeated_selection":repeat,"definitions":{"policy_labels":POLICY_LABELS,"outcome":"Any qualifying purchase in next 30 days","evaluation_unit":"Mature customer-month snapshot","bootstrap":{"method":src["paired_customer_cluster_bootstrap"]["method"],"interval_method":src["paired_customer_cluster_bootstrap"]["interval_method"],"requested_resamples":src["paired_customer_cluster_bootstrap"]["requested_resamples"],"valid_resamples":src["paired_customer_cluster_bootstrap"]["valid_resamples"],"seed":src["paired_customer_cluster_bootstrap"]["seed"],"limitations":src["paired_customer_cluster_bootstrap"]["limitations"]}},"provenance":{"source_aggregate_sha256":"5e9558f7d26a144587325d6465164bed7f6ce1718facc35f0e7a6cd6c15b509d","source_manifest_input_sha256":src["input_sha256"],"source_documents":{"results":SOURCE,"independent_review":REVIEW},"source_manifest":"m3_002_targeting_manifest.json","builder":"src/targeting_bundle.py"},"content_sha256":""}
    b["content_sha256"]=content_hash(b)
    return b

def write_bundle(bundle:dict[str,Any],path:str|Path=DEFAULT_BUNDLE_PATH)->Path:
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(bundle,indent=2,sort_keys=True)+"\n",encoding="utf-8"); return path

if __name__=="__main__":
    ap=argparse.ArgumentParser(); ap.add_argument("aggregate",type=Path); ap.add_argument("--output",type=Path,default=DEFAULT_BUNDLE_PATH); a=ap.parse_args(); b=build_bundle(a.aggregate); write_bundle(b,a.output); print(b["content_sha256"])
