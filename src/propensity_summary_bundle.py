"""Allowlisted aggregate bundle for the M1/M2 Purchase Propensity dashboard."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLE_PATH = ROOT / "app_data/propensity_summary_v1.json"
BUNDLE_NAME = "purchase_propensity_summary"
BUNDLE_VERSION = "1.0.0"
SCHEMA_VERSION = 1
EXPECTED_CONTENT_SHA256 = "a4fcc6d60cac7ddc2de3a5c62c457c9f706237792b42b1bdffa1715d09535562"

EXPECTED_INPUT_SHA256 = {
    "m1_results_report": "9b48774fa5171e12c3b1658b168440e50a56943298e7c8a785f17de503e01808",
    "m1_protocol": "d5be6bfefbbbddf8e5f7dfe8a81202cc04c1d18e7480c698aec5211b3c92c3ac",
    "m2_results_report": "3d4668810e9c542e38a666e2b74cfa0341830da51e331a2e0c1fb9a29651d856",
    "m2_protocol": "790d5377d4817ea3148b5a290bd9d24cfa5c3e3866a6b89f90418aa1b748e7b4",
    "m2_run_manifest": "81bb760a60c4d9badd6b3b65baf93086165e5a4c30ec1e9391390b4e30c2e14a",
    "m2_calibration_report": "f0ced66ed2659d25a1723ba6f64f177a3de950e60548ee1796a9ef5416556508",
    "m2_calibration_aggregate": "3cafd6ab08543f2f7675768d005598814ea20a1c4c3bedb0efee84542a4ef030",
}
UPSTREAM_ARTIFACT_SHA256 = {
    "m2_dataset": "44c580a83bea993fd0e2f8df8a03bb7aa2f11e64085671ea2ed78c9e28e952a8",
    "m2_dataset_manifest": "3d7ee78afa96a1d4abe7ee8f7762a994e652bc5c799b892d227f56be03c96a13",
    "m2_snapshot_builder": "58f29d2780f541c591312c8d7773815b28d3d828c4be2adea5994c47c8cfa82b",
    "m2_protocol": "790d5377d4817ea3148b5a290bd9d24cfa5c3e3866a6b89f90418aa1b748e7b4",
    "m2_models": "e971ffa7712c56c0a02c1d6157e15e573c5ad6dd24b4f421b165fbf6dc807b3f",
    "m2_predictions": "facdd36297340138ec23ddbd98bc9cc551776c6bdf635e731ced08cc440626c1",
}
SOURCE_DOCUMENTS = {
    "m1_results_report": "docs/research/COMMERCIAL_DS_P2_M1_009_BASELINE_RESULTS.md",
    "m1_protocol": "docs/research/COMMERCIAL_DS_P2_M1_009_BASELINE_PROTOCOL.md",
    "m2_results_report": "docs/research/COMMERCIAL_DS_P2_M2_008_BASELINE_RESULTS.md",
    "m2_protocol": "docs/research/COMMERCIAL_DS_P2_M2_007_BASELINE_PROTOCOL.md",
    "m2_run_manifest": "external M2-008 aggregate run manifest",
    "m2_calibration_report": "docs/research/COMMERCIAL_DS_P2_M2_012_SEQUENTIAL_CALIBRATION_RESULTS.md",
    "m2_calibration_aggregate": "external M2-012 aggregate summary",
}
FORBIDDEN_KEY_PARTS = ("customer_id", "customerid", "invoice", "stockcode", "prediction_row", "feature_matrix")


class BundleError(ValueError):
    """Raised for missing, malformed or unapproved propensity summary bundles."""


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def content_hash(bundle: dict[str, Any]) -> str:
    payload = {key: bundle[key] for key in ("m1", "m2", "m2_calibration")}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BundleError(f"{label} could not be read as JSON: {exc}") from None
    if not isinstance(obj, dict):
        raise BundleError(f"{label} must be a JSON object")
    return obj


def _finite_number(value: Any, where: str, *, nullable: bool = False) -> None:
    if nullable and value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise BundleError(f"{where} must be a finite number")


def _require_keys(obj: Any, keys: set[str], where: str) -> None:
    if not isinstance(obj, dict) or set(obj) != keys:
        raise BundleError(f"{where} has missing or unexpected fields")


def _reject_customer_data(value: Any, where: str = "bundle") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            name = str(key).lower()
            if any(part in name for part in FORBIDDEN_KEY_PARTS):
                raise BundleError(f"prohibited row-level field name at {where}.{key}")
            _reject_customer_data(item, f"{where}.{key}")
    elif isinstance(value, list):
        for i, item in enumerate(value):
            _reject_customer_data(item, f"{where}[{i}]")


def validate_bundle(bundle: Any) -> dict[str, Any]:
    if not isinstance(bundle, dict):
        raise BundleError("propensity bundle must be a JSON object")
    expected = {"bundle_name", "bundle_version", "schema_version", "evidence_label", "m1", "m2",
                "m2_calibration", "provenance", "content_sha256"}
    _require_keys(bundle, expected, "bundle")
    if bundle["bundle_name"] != BUNDLE_NAME or bundle["bundle_version"] != BUNDLE_VERSION or bundle["schema_version"] != SCHEMA_VERSION:
        raise BundleError("unsupported propensity bundle name, version or schema")
    if bundle["evidence_label"] != "Historical prediction":
        raise BundleError("propensity bundle must be labelled Historical prediction")
    _require_keys(bundle["m1"], {"task", "decision", "outcome", "evaluation_unit", "training", "test", "models", "auc_interval", "success_criterion_met", "limitations"}, "m1")
    _require_keys(bundle["m2"], {"task", "decision", "outcome", "evaluation_unit", "training", "test", "customer_overlap",
                                      "model_c_auc_interval", "models", "monthly", "limitations"}, "m2")
    _require_keys(bundle["m2_calibration"], {"method", "pool_rule", "pools", "pooled", "monthly", "limitations"}, "m2_calibration")
    _require_keys(bundle["provenance"], {"source_sha256", "upstream_artifact_sha256", "source_documents", "builder", "builder_sha256"}, "provenance")
    provenance = bundle["provenance"]
    if set(provenance["source_sha256"]) != set(EXPECTED_INPUT_SHA256) or provenance["source_sha256"] != EXPECTED_INPUT_SHA256:
        raise BundleError("source hashes differ from the approved research inputs")
    if provenance["upstream_artifact_sha256"] != UPSTREAM_ARTIFACT_SHA256:
        raise BundleError("upstream dataset/model/protocol hashes differ from the approved M2 artifacts")
    if provenance["source_documents"] != SOURCE_DOCUMENTS:
        raise BundleError("source document references differ from the approved research inputs")
    if not isinstance(provenance["builder"], str) or not isinstance(provenance["builder_sha256"], str) or re.fullmatch(r"[0-9a-f]{64}", provenance["builder_sha256"]) is None:
        raise BundleError("bundle builder provenance is malformed")

    _require_keys(bundle["m1"]["training"], {"customers", "positive", "negative", "prevalence"}, "m1.training")
    _require_keys(bundle["m1"]["test"], {"customers", "positive", "negative", "prevalence"}, "m1.test")
    _require_keys(bundle["m1"]["auc_interval"], {"lower", "upper", "method", "resamples", "seed"}, "m1.auc_interval")
    for key in ("lower", "upper"):
        _finite_number(bundle["m1"]["auc_interval"][key], f"m1.auc_interval.{key}")
    if not isinstance(bundle["m1"]["success_criterion_met"], bool):
        raise BundleError("m1.success_criterion_met must be boolean")
    _require_keys(bundle["m2"]["training"], {"snapshots", "customers", "positive", "negative", "prevalence"}, "m2.training")
    _require_keys(bundle["m2"]["test"], {"snapshots", "customers", "positive", "negative", "prevalence"}, "m2.test")
    for task in (bundle["m1"], bundle["m2"]):
        if not isinstance(task["task"], str) or not isinstance(task["decision"], str) or not isinstance(task["outcome"], str):
            raise BundleError("task definitions must be text")
        if not isinstance(task["evaluation_unit"], str) or not isinstance(task["limitations"], list) or not all(isinstance(x, str) for x in task["limitations"]):
            raise BundleError("task evaluation metadata is malformed")
    for group in (bundle["m1"]["training"], bundle["m1"]["test"], bundle["m2"]["training"], bundle["m2"]["test"]):
        for key, value in group.items():
            _finite_number(value, f"counts.{key}")
    for task_name, unit_name, groups in (
        ("m1", "customers", (bundle["m1"]["training"], bundle["m1"]["test"])),
        ("m2", "snapshots", (bundle["m2"]["training"], bundle["m2"]["test"])),
    ):
        for group in groups:
            if group["positive"] + group["negative"] != group[unit_name] or abs(group["prevalence"] - group["positive"] / group[unit_name]) > 1e-12:
                raise BundleError(f"{task_name} label counts/prevalence do not reconcile")
    if isinstance(bundle["m2"]["customer_overlap"], bool) or not isinstance(bundle["m2"]["customer_overlap"], int):
        raise BundleError("m2.customer_overlap must be an integer")

    _require_keys(bundle["m1"]["models"], {"A_constant", "B_gross_only", "C_three_feature"}, "m1.models")
    _require_keys(bundle["m2"]["models"], {"A_constant", "B_rfm", "C_full_11"}, "m2.models")
    metric_keys = {"roc_auc", "average_precision", "brier_score"}
    for group in (bundle["m1"]["models"], bundle["m2"]["models"]):
        for name, model in group.items():
            _require_keys(model, metric_keys | {"precision_10pct", "lift_10pct", "calibration"}, f"models.{name}")
            for field in metric_keys | {"precision_10pct", "lift_10pct"}:
                _finite_number(model[field], f"models.{name}.{field}", nullable=True)
            _require_keys(model["calibration"], {"intercept", "slope", "status"}, f"models.{name}.calibration")
            _finite_number(model["calibration"]["intercept"], f"models.{name}.calibration.intercept", nullable=True)
            _finite_number(model["calibration"]["slope"], f"models.{name}.calibration.slope", nullable=True)
            if not isinstance(model["calibration"]["status"], str):
                raise BundleError("calibration status must be text")

    ci = bundle["m2"].get("model_c_auc_interval")
    _require_keys(ci, {"lower", "upper", "method", "resamples", "valid", "omitted", "seed"}, "m2.model_c_auc_interval")
    for key in ("lower", "upper"):
        _finite_number(ci[key], f"m2.model_c_auc_interval.{key}")
    for key in ("resamples", "valid", "omitted", "seed"):
        if isinstance(ci[key], bool) or not isinstance(ci[key], int):
            raise BundleError(f"m2.model_c_auc_interval.{key} must be an integer")
    if not isinstance(ci["method"], str):
        raise BundleError("m2.model_c_auc_interval.method must be text")

    for key in ("monthly",):
        if not isinstance(bundle["m2"][key], list) or not bundle["m2"][key]:
            raise BundleError(f"m2.{key} must be a non-empty list")
    for row in bundle["m2"]["monthly"]:
        _require_keys(row, {"month", "snapshots", "customers", "positive", "negative", "prevalence", "auc_a", "auc_b", "auc_c"}, "m2.monthly[]")
        if not isinstance(row["month"], str):
            raise BundleError("m2 monthly month must be text")
        for key in set(row) - {"month"}:
            _finite_number(row[key], f"m2.monthly.{key}")
        if row["positive"] + row["negative"] != row["snapshots"] or abs(row["prevalence"] - row["positive"] / row["snapshots"]) > 1e-12:
            raise BundleError("m2 monthly label counts/prevalence do not reconcile")

    cal = bundle["m2_calibration"]
    for key in ("method", "pool_rule"):
        if not isinstance(cal[key], str):
            raise BundleError(f"m2_calibration.{key} must be text")
    if not all(isinstance(cal[k], list) for k in ("pools", "monthly", "limitations")) or not all(isinstance(x, str) for x in cal["limitations"]):
        raise BundleError("m2_calibration lists are malformed")
    _require_keys(cal["pooled"], {"months", "snapshots", "customers", "raw", "adjusted", "brier_difference", "brier_ci", "bootstrap"}, "m2_calibration.pooled")
    pooled = cal["pooled"]
    if not isinstance(pooled["months"], list) or not all(isinstance(x, str) for x in pooled["months"]):
        raise BundleError("m2_calibration.pooled.months must be a list of month labels")
    for part in ("raw", "adjusted"):
        _require_keys(pooled[part], {"brier", "mean_probability", "prevalence", "risk_gap", "auc", "average_precision", "calibration"}, f"m2_calibration.pooled.{part}")
        for key in set(pooled[part]) - {"calibration"}:
            _finite_number(pooled[part][key], f"m2_calibration.pooled.{part}.{key}")
        _require_keys(pooled[part]["calibration"], {"intercept", "slope", "status"}, f"m2_calibration.pooled.{part}.calibration")
        for key in ("intercept", "slope"):
            _finite_number(pooled[part]["calibration"][key], f"m2_calibration.pooled.{part}.calibration.{key}", nullable=True)
    _finite_number(pooled["brier_difference"], "m2_calibration.pooled.brier_difference")
    if not isinstance(pooled["brier_ci"], list) or len(pooled["brier_ci"]) != 2:
        raise BundleError("m2_calibration.pooled.brier_ci must contain two limits")
    for value in pooled["brier_ci"]:
        _finite_number(value, "m2_calibration.pooled.brier_ci[]")
    _require_keys(pooled["bootstrap"], {"method", "resamples", "valid", "omitted", "seed"}, "m2_calibration.pooled.bootstrap")
    for entry in cal["pools"]:
        _require_keys(entry, {"target_month", "snapshots", "customers", "positive", "negative", "prevalence", "maturity_as_of", "delta"}, "m2_calibration.pools[]")
        for key in set(entry) - {"target_month", "maturity_as_of"}:
            _finite_number(entry[key], f"m2_calibration.pools.{key}")
        if entry["positive"] + entry["negative"] != entry["snapshots"] or abs(entry["prevalence"] - entry["positive"] / entry["snapshots"]) > 1e-12:
            raise BundleError("m2 calibration-pool counts/prevalence do not reconcile")
    for row in cal["monthly"]:
        _require_keys(row, {"month", "snapshots", "prevalence", "raw_brier", "adjusted_brier", "raw_mean_probability", "adjusted_mean_probability", "raw_auc", "adjusted_auc"}, "m2_calibration.monthly[]")
        for key in set(row) - {"month"}:
            _finite_number(row[key], f"m2_calibration.monthly.{key}")
    _reject_customer_data({k: bundle[k] for k in ("m1", "m2", "m2_calibration")})
    if bundle["content_sha256"] != content_hash(bundle):
        raise BundleError("propensity bundle embedded content hash mismatch")
    if bundle["content_sha256"] != EXPECTED_CONTENT_SHA256:
        raise BundleError("propensity bundle content differs from the independently approved application bundle")
    return bundle


def load_bundle(path: str | Path = DEFAULT_BUNDLE_PATH) -> dict[str, Any]:
    path = Path(path)
    if not path.is_file():
        raise BundleError(f"Purchase Propensity bundle not found: {path.name}")
    try:
        bundle = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BundleError(f"Purchase Propensity bundle could not be read as JSON: {exc}") from None
    return validate_bundle(bundle)


def build_bundle(m2_run_manifest_path: str | Path, m2_calibration_aggregate_path: str | Path) -> dict[str, Any]:
    """Build the compact bundle from hash-verified aggregate manifests and frozen report facts."""
    paths = {
        "m1_results_report": ROOT / SOURCE_DOCUMENTS["m1_results_report"],
        "m1_protocol": ROOT / SOURCE_DOCUMENTS["m1_protocol"],
        "m2_results_report": ROOT / SOURCE_DOCUMENTS["m2_results_report"],
        "m2_protocol": ROOT / SOURCE_DOCUMENTS["m2_protocol"],
        "m2_run_manifest": Path(m2_run_manifest_path),
        "m2_calibration_report": ROOT / SOURCE_DOCUMENTS["m2_calibration_report"],
        "m2_calibration_aggregate": Path(m2_calibration_aggregate_path),
    }
    hashes = {key: sha256_file(path) for key, path in paths.items()}
    if hashes != EXPECTED_INPUT_SHA256:
        raise BundleError("source hash mismatch; do not silently rebuild from changed research artifacts")
    run = _read_json(paths["m2_run_manifest"], "M2-008 run manifest")
    calibration = _read_json(paths["m2_calibration_aggregate"], "M2-012 aggregate")
    results = run["results"]
    partitions = results["partition_counts"]
    source_models = results["models"]

    def model(source: dict[str, Any], *, calibration_values: dict[str, Any] | None = None) -> dict[str, Any]:
        caps = source.get("targeting_capacities", [])
        top_decile = next((x for x in caps if x["nominal_capacity"] == 0.1), None)
        cal = calibration_values or source["calibration"]
        return {
            "roc_auc": source["roc_auc"],
            "average_precision": source["average_precision"],
            "brier_score": source["brier_score"],
            "precision_10pct": top_decile["precision"] if top_decile else None,
            "lift_10pct": top_decile["lift"] if top_decile else None,
            "calibration": {"intercept": cal.get("intercept"), "slope": cal.get("slope"), "status": cal.get("status", "not_identifiable")},
        }

    m1 = {
        "task": "Day-21 second qualifying purchase among customers in the approved 12-month qualifying-history acquisition proxy.",
        "decision": "Day 21: first qualifying purchase timestamp + 21 days.",
        "outcome": "Second qualifying purchase in (Day 21, Day 111], a 90-day forward window.",
        "evaluation_unit": "Customer; 208 fully mature customers in chronological test.",
        "training": {"customers": 304, "positive": 90, "negative": 214, "prevalence": 90 / 304},
        "test": {"customers": 208, "positive": 97, "negative": 111, "prevalence": 97 / 208},
        "models": {
            "A_constant": {"roc_auc": 0.5, "average_precision": None, "brier_score": 0.2779,
                           "precision_10pct": None, "lift_10pct": None,
                           "calibration": {"intercept": None, "slope": None, "status": "constant comparator; slope not identifiable"}},
            "B_gross_only": {"roc_auc": 0.5439, "average_precision": None, "brier_score": 0.2761,
                             "precision_10pct": None, "lift_10pct": None,
                             "calibration": {"intercept": 0.112, "slope": 0.295, "status": "diagnostic"}},
            "C_three_feature": {"roc_auc": 0.5189, "average_precision": None, "brier_score": 0.2743,
                                "precision_10pct": None, "lift_10pct": None,
                                "calibration": {"intercept": 0.172, "slope": 0.376,
                                                "status": "M1-010 corrected diagnostic; approximate SE 0.45 and 0.53"}},
        },
        "auc_interval": {"lower": 0.4410, "upper": 0.5963, "method": "customer-level percentile bootstrap", "resamples": 2000, "seed": 20261112},
        "success_criterion_met": False,
        "limitations": [
            "The confidence interval includes values below and above chance; the predeclared success criterion was not met.",
            "Only 304 training and 208 test customers; substantial seasonal prevalence shift (29.61% training to 46.63% test).",
            "The test set was not entirely unseen: M1-008 had examined prevalence by month and spend third before protocol freeze; no test-driven tuning or model selection was identified.",
        ],
    }
    m2_models = {}
    for key, mapped in (("A_constant", "A_constant"), ("B_rfm", "B_rfm"), ("C_full_11", "C_full_11")):
        source = source_models[key]
        if key == "A_constant":
            top_decile = next(x for x in source["targeting_capacities"] if x["nominal_capacity"] == 0.1)
            m2_models[mapped] = {"roc_auc": source["roc_auc"], "average_precision": source["average_precision"],
                                 "brier_score": source["brier_score"], "precision_10pct": top_decile["precision"],
                                 "lift_10pct": top_decile["lift"],
                                 "calibration": {"intercept": source["calibration"]["intercept"], "slope": source["calibration"]["slope"], "status": source["calibration"]["status"]}}
        else:
            m2_models[mapped] = model(source)
    m2 = {
        "task": "Established-customer monthly prediction of at least one qualifying purchase in the next fixed 30 days.",
        "decision": "One eligible customer-month snapshot; decision at 00:00 on the first day of the snapshot month; preceding 365-day features.",
        "outcome": "Any qualifying purchase in [decision timestamp, decision timestamp + 30 days); mature labels only.",
        "evaluation_unit": "Customer-month snapshot; repeated customers are allowed and clustered for uncertainty.",
        "training": {"snapshots": partitions["training_snapshots"], "customers": partitions["training_unique_customers"],
                     "positive": partitions["training_positive"], "negative": partitions["training_negative"],
                     "prevalence": partitions["training_positive"] / partitions["training_snapshots"]},
        "test": {"snapshots": partitions["test_snapshots"], "customers": partitions["test_unique_customers"],
                 "positive": partitions["test_positive"], "negative": partitions["test_negative"],
                 "prevalence": partitions["test_positive"] / partitions["test_snapshots"]},
        "customer_overlap": partitions["customer_overlap"],
        "model_c_auc_interval": {"lower": results["model_c_customer_clustered_auc_95"]["lower_95"],
                                  "upper": results["model_c_customer_clustered_auc_95"]["upper_95"],
                                  "method": results["model_c_customer_clustered_auc_95"]["method"],
                                  "resamples": results["model_c_customer_clustered_auc_95"]["requested_resamples"],
                                  "valid": results["model_c_customer_clustered_auc_95"]["valid_resamples"],
                                  "omitted": results["model_c_customer_clustered_auc_95"]["omitted_single_class_resamples"],
                                  "seed": results["model_c_customer_clustered_auc_95"]["seed"]},
        "models": m2_models,
        "monthly": [{"month": row["snapshot_month"], "snapshots": row["snapshots"], "customers": row["unique_customers"],
                     "positive": row["positive"], "negative": row["negative"], "prevalence": row["prevalence"],
                     "auc_a": row["roc_auc"]["A_constant"], "auc_b": row["roc_auc"]["B_rfm"], "auc_c": row["roc_auc"]["C_full_11"]}
                    for row in results["monthly"]],
        "limitations": [
            "The July–November 2011 holdout was previously examined and is one short seasonal period, not independent temporal replication.",
            "Training prevalence was 17.83% and test prevalence 23.50%; monthly test prevalence rose to 32.14% in November.",
            "4,265 customers occur in both partitions; reported uncertainty clusters repeated test snapshots by customer.",
            "Model C underpredicts test prevalence (17.69% mean prediction versus 23.50% observed). Discrimination does not establish causal CRM impact.",
        ],
    }
    pools = [{"target_month": p["target_month"], "snapshots": p["calibration_snapshots"],
              "customers": p["calibration_unique_customers"], "positive": p["calibration_positives"],
              "negative": p["calibration_negatives"], "prevalence": p["calibration_prevalence"],
              "maturity_as_of": p["latest_maturity_timestamp"], "delta": p["fitted_intercept_delta"]}
             for p in calibration["calibration_pools"]]
    pooled = calibration["pooled_september_november"]
    raw, adjusted = pooled["raw_model_c"], pooled["sequentially_adjusted_model_c"]
    cal_bundle = {
        "method": "Exploratory sequential intercept-only adjustment; fixed Model C coefficients and slope=1.",
        "pool_rule": "Only fully mature labels with maturity strictly before each target decision; no contemporaneous/future labels.",
        "pools": pools,
        "pooled": {"months": pooled["months"], "snapshots": pooled["snapshots"], "customers": pooled["unique_customers"],
                   "raw": {"brier": raw["brier_score"], "mean_probability": raw["mean_predicted_probability"],
                           "prevalence": raw["positive_prevalence"], "risk_gap": raw["calibration_in_the_large_risk_difference"],
                           "auc": raw["roc_auc"], "average_precision": raw["average_precision"], "calibration": raw["calibration_intercept_slope"]},
                   "adjusted": {"brier": adjusted["brier_score"], "mean_probability": adjusted["mean_predicted_probability"],
                                "prevalence": adjusted["positive_prevalence"], "risk_gap": adjusted["calibration_in_the_large_risk_difference"],
                                "auc": adjusted["roc_auc"], "average_precision": adjusted["average_precision"], "calibration": adjusted["calibration_intercept_slope"]},
                   "brier_difference": calibration["paired_customer_cluster_bootstrap"]["estimate_brier_difference_adjusted_minus_raw"],
                   "brier_ci": calibration["paired_customer_cluster_bootstrap"]["percentile_95_interval"],
                   "bootstrap": {"method": calibration["paired_customer_cluster_bootstrap"]["method"],
                                 "resamples": calibration["paired_customer_cluster_bootstrap"]["requested_resamples"],
                                 "valid": calibration["paired_customer_cluster_bootstrap"]["valid_resamples"],
                                 "omitted": calibration["paired_customer_cluster_bootstrap"]["omitted_resamples"],
                                 "seed": calibration["paired_customer_cluster_bootstrap"]["seed"]}},
        "monthly": [{"month": month, "snapshots": row["snapshots"], "prevalence": row["prevalence"],
                     "raw_brier": row["models"]["C_full_raw"]["brier_score"],
                     "adjusted_brier": row["models"].get("C_full_adjusted", {}).get("brier_score", row["models"]["C_full_raw"]["brier_score"]),
                     "raw_mean_probability": row["models"]["C_full_raw"]["mean_predicted_probability"],
                     "adjusted_mean_probability": row["models"].get("C_full_adjusted", {}).get("mean_predicted_probability", row["models"]["C_full_raw"]["mean_predicted_probability"]),
                     "raw_auc": row["models"]["C_full_raw"]["roc_auc"],
                     "adjusted_auc": row["models"].get("C_full_adjusted", {}).get("roc_auc", row["models"]["C_full_raw"]["roc_auc"])}
                    for month, row in calibration["monthly_metrics"].items()],
        "limitations": [
            "Exploratory re-analysis of the previously examined July–November holdout, not independent prospective validation.",
            "Only September–November have sequentially calibrated results; July and August are unadjusted warm-up months.",
            "Adjustment modestly improves Brier score but underprediction remains; month-specific intercepts can reorder observations across months.",
            "Within-month ranking is unchanged. No causal campaign effect or future-period generalisation is established.",
        ],
    }
    bundle = {"bundle_name": BUNDLE_NAME, "bundle_version": BUNDLE_VERSION, "schema_version": SCHEMA_VERSION,
              "evidence_label": "Historical prediction", "m1": m1, "m2": m2, "m2_calibration": cal_bundle,
              "provenance": {"source_sha256": hashes, "upstream_artifact_sha256": UPSTREAM_ARTIFACT_SHA256,
                             "source_documents": SOURCE_DOCUMENTS,
                             "builder": "src/propensity_summary_bundle.py", "builder_sha256": sha256_file(Path(__file__))},
              "content_sha256": ""}
    bundle["content_sha256"] = content_hash(bundle)
    return bundle


def write_bundle(bundle: dict[str, Any], path: str | Path = DEFAULT_BUNDLE_PATH) -> Path:
    validate_bundle(bundle)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(bundle, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--m2-run-manifest", type=Path, required=True)
    parser.add_argument("--m2-calibration-aggregate", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_BUNDLE_PATH)
    args = parser.parse_args(argv)
    path = write_bundle(build_bundle(args.m2_run_manifest, args.m2_calibration_aggregate), args.output)
    print(json.dumps({"bundle": str(path), "content_sha256": content_hash(load_bundle(path))}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
