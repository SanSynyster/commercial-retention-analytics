"""Aggregate-only data bundle for the Customer Overview dashboard page.

Two separate responsibilities live here:

* ``build_bundle`` / ``main``: a one-time research step that reads the accepted
  corrected-V2 aggregate outputs (ignored local ``data/processed`` files),
  re-applies the accepted 007D contract checks, removes fields the page does
  not need, marks small cohort cells as suppressed for display and writes a
  versioned JSON bundle.
* ``load_bundle`` / ``validate_bundle``: the application runtime path. It reads
  only the tracked bundle and fails closed on any schema, consistency,
  integrity or identifier problem. It never touches raw or customer-level data.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DIR = ROOT / "data/processed/corrected_v2_customer_analytics"
DEFAULT_BUNDLE_PATH = ROOT / "app_data/customer_overview_v1.json"

BUNDLE_NAME = "customer_overview"
BUNDLE_VERSION = "1.0.0"
SCHEMA_VERSION = 1
SMALL_CELL_THRESHOLD = 5
# Independent pin for the approved data sections. This detects changes relative
# to this application bundle; it is not an authenticity guarantee if source code
# and this constant are both changed.
EXPECTED_CONTENT_SHA256 = "5bd05077dd03d8a053150c752bd9610431c96b35e5b269b045eebf065d006c4c"
PRE = "first_observed_before_2010-12-01"
POST = "first_observed_on_or_after_2010-12-01"
POPULATIONS = (PRE, POST)
FREQUENCIES = ("one_observed_purchase_day", "repeat_observed_purchase_days")
RECENCIES = ("active_observed", "inactive_60_89_days", "no_observed_purchase_90_plus_days")

# Accepted corrected-V2 reference values (README and corrected_v2_scientific_results.md).
REFERENCE = {
    "identified_customers": 5852,
    "qualifying_purchase_occasions": 36594,
    "qualifying_merchandise_lines": 788127,
    "qualifying_gross_merchandise": Decimal("17123740.997"),
    "top_decile_customer_count": 586,
    "top_decile_qualifying_gross": Decimal("10926893.967"),
    "unattributed_positive_merchandise_excluded": Decimal("2575930.13"),
    "mature_90d_customers": 5256,
    "insufficient_follow_up_customers": 596,
    "repeat_strata": 25,
    "cohort_cells": 625,
    # Accepted 007C segment counts (corrected_v2_scientific_results.md, segment table).
    "segment_customer_counts": {
        ("one_observed_purchase_day", "active_observed"): 251,
        ("one_observed_purchase_day", "inactive_60_89_days"): 125,
        ("one_observed_purchase_day", "no_observed_purchase_90_plus_days"): 1297,
        ("repeat_observed_purchase_days", "active_observed"): 2123,
        ("repeat_observed_purchase_days", "inactive_60_89_days"): 386,
        ("repeat_observed_purchase_days", "no_observed_purchase_90_plus_days"): 1670,
    },
}

SOURCE_FILES = (
    "reconciliation.json",
    "concentration_summary.csv",
    "repeat_90d_by_first_observed_month.csv",
    "first_observed_cohort_activity.csv",
    "segment_summary.csv",
)
EXCLUDED_SOURCE_FILES = {
    "customer_metrics.csv": "customer-level",
    "customer_value_segment_flags.csv": "customer-level",
    "signed_merchandise_sensitivity_customers.csv": "customer-level",
    "signed_merchandise_sensitivity_summary.csv": "not needed for this page; small returns-only/negative-net counts",
    "segment_flag_summary.csv": "not needed for this page",
    "value_segments_reconciliation.json": "not needed for this page",
}

TOP_LEVEL_FIELDS = (
    "bundle_name", "bundle_version", "schema_version", "evidence_label", "provenance",
    "publication_review", "headline", "concentration", "repeat_90d", "cohort_activity",
    "segments", "content_sha256",
)
DATA_SECTIONS = ("headline", "concentration", "repeat_90d", "cohort_activity", "segments")
HEADLINE_FIELDS = {
    "identified_customers": int,
    "qualifying_purchase_occasions": int,
    "qualifying_merchandise_lines": int,
    "qualifying_gross_merchandise": "decimal",
    "unattributed_positive_merchandise_excluded": "decimal",
    "mature_90d_customers": int,
    "insufficient_follow_up_customers": int,
    "observation_start_date": str,
    "source_end_timestamp": str,
    "source_end_is_partial_day": bool,
    "last_complete_activity_month": str,
}
CONCENTRATION_FIELDS = {
    "eligible_customer_count": int,
    "top_decile_customer_count": int,
    "top_decile_qualifying_gross": "decimal",
    "identified_qualifying_gross_denominator": "decimal",
    "top_decile_share": float,
    "ranking_rule": str,
    "monetary_measure": str,
}
REPEAT_FIELDS = {
    "population": str,
    "first_observed_month": str,
    "eligible_customer_count": int,
    "mature_customer_count": int,
    "repeat_numerator": int,
    "conversion_fraction": (float, type(None)),
    "median_days_to_second_purchase_among_mature_repeaters": (float, type(None)),
    "insufficient_follow_up_count": int,
}
COHORT_FIELDS = {
    "population": str,
    "cohort_month": str,
    "month_index": int,
    "activity_month": str,
    "cohort_size": int,
    "active_customers": (int, type(None)),
    "activity_fraction": (float, type(None)),
    "cell_status": str,
}
COHORT_STATUSES = ("observed_complete", "not_observed_incomplete_or_future", "suppressed_small_cell")
PROVENANCE_FIELDS = {
    "population": str,
    "source_aggregate_sha256": dict,
    "source_generators": dict,
    "contract_checks": str,
    "reference_report": str,
    "builder": str,
    "builder_sha256": str,
}
PUBLICATION_REVIEW_FIELDS = {
    "customer_level_fields_included": bool,
    "small_cell_threshold": int,
    "suppressed_cohort_cells": int,
    "suppression_rule": str,
    "excluded_source_files": dict,
    "excluded_fields": list,
}
SEGMENT_FIELDS = {
    "purchase_frequency": str,
    "recency_state": str,
    "customer_count": int,
    "qualifying_gross_merchandise": "decimal",
    "share_of_identified_qualifying_gross": float,
}
FORBIDDEN_KEY_FRAGMENTS = (
    "customer_id", "customerid", "customer_key", "invoice", "stockcode", "stock_code",
    "description", "probability", "prediction", "selection", "policy_score", "email",
)


class BundleError(ValueError):
    """Raised when the dashboard bundle is missing, malformed or inconsistent."""


# --------------------------------------------------------------------------- helpers

def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def content_hash(bundle: dict[str, Any]) -> str:
    """SHA-256 of the canonical JSON of the data sections only."""
    payload = {key: bundle[key] for key in DATA_SECTIONS}
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _dec(value: Any, where: str) -> Decimal:
    if not isinstance(value, str):
        raise BundleError(f"{where} must be a decimal string")
    try:
        number = Decimal(value)
    except InvalidOperation:
        raise BundleError(f"{where} is not a valid decimal") from None
    if not number.is_finite():
        raise BundleError(f"{where} must be finite")
    return number


def _check_type(value: Any, expected: Any, where: str) -> None:
    if expected == "decimal":
        _dec(value, where)
        return
    allowed = expected if isinstance(expected, tuple) else (expected,)
    if isinstance(value, bool) and bool not in allowed:
        raise BundleError(f"{where} has type bool; expected {allowed}")
    if not isinstance(value, allowed):
        raise BundleError(f"{where} has type {type(value).__name__}; expected {allowed}")
    if isinstance(value, float) and not math.isfinite(value):
        raise BundleError(f"{where} must be finite")


def _check_record(record: Any, fields: dict[str, Any], where: str) -> None:
    if not isinstance(record, dict):
        raise BundleError(f"{where} must be an object")
    if set(record) != set(fields):
        missing = sorted(set(fields) - set(record))
        extra = sorted(set(record) - set(fields))
        raise BundleError(f"{where} fields differ from schema (missing={missing}, unexpected={extra})")
    for name, expected in fields.items():
        _check_type(record[name], expected, f"{where}.{name}")


def _check_no_identifier_keys(value: Any, where: str = "bundle") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            lowered = str(key).lower()
            if any(fragment in lowered for fragment in FORBIDDEN_KEY_FRAGMENTS):
                raise BundleError(f"forbidden customer-level field name at {where}.{key}")
            _check_no_identifier_keys(item, f"{where}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _check_no_identifier_keys(item, f"{where}[{index}]")


# --------------------------------------------------------------------------- validation

def validate_bundle(bundle: Any) -> dict[str, Any]:
    """Validate schema, types, accepted values and internal consistency."""
    if not isinstance(bundle, dict):
        raise BundleError("bundle must be a JSON object")
    if set(bundle) != set(TOP_LEVEL_FIELDS):
        raise BundleError(f"bundle top-level fields differ from schema: {sorted(bundle)}")
    if bundle["bundle_name"] != BUNDLE_NAME or bundle["schema_version"] != SCHEMA_VERSION:
        raise BundleError("unsupported bundle name or schema version")
    if bundle["evidence_label"] != "Historical description":
        raise BundleError("Customer Overview bundle must be labelled 'Historical description'")
    _check_record(bundle["provenance"], PROVENANCE_FIELDS, "provenance")
    _check_record(bundle["publication_review"], PUBLICATION_REVIEW_FIELDS, "publication_review")
    provenance = bundle["provenance"]
    for field in ("population", "contract_checks", "reference_report", "builder"):
        if not provenance[field].strip():
            raise BundleError(f"provenance.{field} must be non-empty")
    source_hashes = provenance["source_aggregate_sha256"]
    if set(source_hashes) != set(SOURCE_FILES) or any(
        not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None
        for value in source_hashes.values()
    ):
        raise BundleError("provenance.source_aggregate_sha256 must contain a SHA-256 for each accepted source")
    generators = provenance["source_generators"]
    expected_generators = {
        "COMMERCIAL_DS_007B_CUSTOMER_ANALYTICS",
        "COMMERCIAL_DS_007C_VALUE_SEGMENTS",
    }
    if set(generators) != expected_generators or any(not isinstance(value, str) or not value for value in generators.values()):
        raise BundleError("provenance.source_generators has missing or malformed entries")
    if re.fullmatch(r"[0-9a-f]{64}", provenance["builder_sha256"]) is None:
        raise BundleError("provenance.builder_sha256 must be a SHA-256")
    if set(bundle["publication_review"]["excluded_source_files"]) != set(EXCLUDED_SOURCE_FILES):
        raise BundleError("publication_review.excluded_source_files has unexpected entries")
    if any(not isinstance(k, str) or not isinstance(v, str)
           for k, v in bundle["publication_review"]["excluded_source_files"].items()):
        raise BundleError("publication_review.excluded_source_files must map strings to strings")
    if not all(isinstance(value, str) for value in bundle["publication_review"]["excluded_fields"]):
        raise BundleError("publication_review.excluded_fields must contain strings")
    if not bundle["publication_review"]["suppression_rule"].strip():
        raise BundleError("publication_review.suppression_rule must be non-empty")
    if bundle["publication_review"]["customer_level_fields_included"] is not False:
        raise BundleError("publication_review.customer_level_fields_included must be false")
    if bundle["publication_review"]["small_cell_threshold"] != SMALL_CELL_THRESHOLD:
        raise BundleError("publication_review.small_cell_threshold differs from the application contract")
    _check_no_identifier_keys({k: bundle[k] for k in DATA_SECTIONS})
    if bundle["content_sha256"] != content_hash(bundle):
        raise BundleError("bundle content hash does not match its data sections")

    headline = bundle["headline"]
    _check_record(headline, HEADLINE_FIELDS, "headline")
    concentration = bundle["concentration"]
    _check_record(concentration, CONCENTRATION_FIELDS, "concentration")
    repeat = bundle["repeat_90d"]
    cohort = bundle["cohort_activity"]
    segments = bundle["segments"]
    for name, rows, fields in (("repeat_90d", repeat, REPEAT_FIELDS), ("cohort_activity", cohort, COHORT_FIELDS),
                               ("segments", segments, SEGMENT_FIELDS)):
        if not isinstance(rows, list) or not rows:
            raise BundleError(f"{name} must be a non-empty list")
        for index, row in enumerate(rows):
            _check_record(row, fields, f"{name}[{index}]")

    customers = headline["identified_customers"]
    gross = _dec(headline["qualifying_gross_merchandise"], "headline.qualifying_gross_merchandise")
    for key in ("identified_customers", "qualifying_purchase_occasions", "qualifying_merchandise_lines",
                "mature_90d_customers", "insufficient_follow_up_customers"):
        if headline[key] != REFERENCE[key]:
            raise BundleError(f"headline.{key} differs from the accepted corrected-V2 value")
    for key in ("qualifying_gross_merchandise", "unattributed_positive_merchandise_excluded"):
        if _dec(headline[key], key) != REFERENCE[key]:
            raise BundleError(f"headline.{key} differs from the accepted corrected-V2 value")

    # Concentration: ceiling top decile; share equals numerator / denominator.
    top_n = math.ceil(customers / 10)
    if concentration["eligible_customer_count"] != customers or concentration["top_decile_customer_count"] != top_n:
        raise BundleError("concentration counts do not reconcile with identified customers")
    numerator = _dec(concentration["top_decile_qualifying_gross"], "concentration numerator")
    denominator = _dec(concentration["identified_qualifying_gross_denominator"], "concentration denominator")
    if denominator != gross or numerator != REFERENCE["top_decile_qualifying_gross"] or not 0 < numerator <= denominator:
        raise BundleError("concentration gross values do not reconcile")
    if abs(concentration["top_decile_share"] - float(numerator / denominator)) > 1e-12:
        raise BundleError("top-decile share does not equal numerator over denominator")

    # Repeat strata: no pooled row; counts reconcile; null fractions for empty strata.
    if len(repeat) != REFERENCE["repeat_strata"]:
        raise BundleError("unexpected number of 90-day repeat strata")
    keys = set()
    for row in repeat:
        if row["population"] not in POPULATIONS or row["first_observed_month"] == "ALL":
            raise BundleError("unexpected or pooled repeat stratum")
        keys.add((row["population"], row["first_observed_month"]))
        mature, numerator_r = row["mature_customer_count"], row["repeat_numerator"]
        if not 0 <= numerator_r <= mature <= row["eligible_customer_count"]:
            raise BundleError("repeat stratum counts are inconsistent")
        if row["eligible_customer_count"] != mature + row["insufficient_follow_up_count"]:
            raise BundleError("repeat stratum eligible count does not reconcile")
        if mature == 0:
            if row["conversion_fraction"] is not None or row["median_days_to_second_purchase_among_mature_repeaters"] is not None:
                raise BundleError("empty mature stratum must have null conversion and timing")
        elif row["conversion_fraction"] is None or abs(row["conversion_fraction"] - numerator_r / mature) > 1e-12:
            raise BundleError("repeat conversion does not equal numerator over mature denominator")
    if len(keys) != len(repeat):
        raise BundleError("duplicate repeat strata")
    if sum(r["eligible_customer_count"] for r in repeat) != customers:
        raise BundleError("repeat eligible counts do not sum to identified customers")
    if sum(r["mature_customer_count"] for r in repeat) != headline["mature_90d_customers"]:
        raise BundleError("repeat mature counts do not sum to the headline")
    if sum(r["insufficient_follow_up_count"] for r in repeat) != headline["insufficient_follow_up_customers"]:
        raise BundleError("repeat immature counts do not sum to the headline")

    # Cohort grid: entry month, immature nulls, small-cell suppression.
    if len(cohort) != REFERENCE["cohort_cells"]:
        raise BundleError("unexpected cohort grid size")
    cohort_keys = set()
    entry_sizes: dict[tuple[str, str], int] = {}
    for row in cohort:
        if row["population"] not in POPULATIONS or row["cell_status"] not in COHORT_STATUSES:
            raise BundleError("unexpected cohort population or status")
        if row["month_index"] < 0 or row["cohort_size"] <= 0:
            raise BundleError("invalid cohort index or size")
        cohort_keys.add((row["population"], row["cohort_month"], row["month_index"]))
        status, active, fraction = row["cell_status"], row["active_customers"], row["activity_fraction"]
        if status == "observed_complete":
            if active is None or fraction is None or not 0 < active <= row["cohort_size"]:
                raise BundleError("observed cohort cell must have a positive count within cohort size")
            if row["month_index"] > 0 and active < SMALL_CELL_THRESHOLD:
                raise BundleError("unsuppressed small cohort cell")
            if abs(fraction - active / row["cohort_size"]) > 1e-12:
                raise BundleError("cohort activity fraction does not equal active over cohort size")
            if row["month_index"] == 0:
                if active != row["cohort_size"]:
                    raise BundleError("cohort entry month must equal cohort size")
                entry_sizes[(row["population"], row["cohort_month"])] = active
        elif active is not None or fraction is not None:
            raise BundleError("unobserved or suppressed cohort cell must be null")
        if row["activity_month"] > headline["last_complete_activity_month"] and status != "not_observed_incomplete_or_future":
            raise BundleError("cohort cell after the last complete month must be unobserved")
    if len(cohort_keys) != len(cohort):
        raise BundleError("duplicate cohort cells")
    if sum(entry_sizes.values()) != customers - sum(
        r["eligible_customer_count"] for r in repeat if r["first_observed_month"] > headline["last_complete_activity_month"]
    ):
        raise BundleError("cohort entry sizes do not reconcile with first-observed counts")

    # Segments: exactly six groups summing to customers and gross.
    groups = {(row["purchase_frequency"], row["recency_state"]) for row in segments}
    if len(segments) != 6 or groups != {(f, r) for f in FREQUENCIES for r in RECENCIES}:
        raise BundleError("segments must contain exactly the six descriptive groups")
    if sum(row["customer_count"] for row in segments) != customers:
        raise BundleError("segment customer counts do not sum to identified customers")
    segment_gross = sum((_dec(row["qualifying_gross_merchandise"], "segment gross") for row in segments), Decimal(0))
    if segment_gross != gross:
        raise BundleError("segment gross does not sum to identified qualifying gross")
    for row in segments:
        if row["customer_count"] != REFERENCE["segment_customer_counts"][(row["purchase_frequency"], row["recency_state"])]:
            raise BundleError("segment customer count differs from the accepted corrected-V2 value")
        if row["customer_count"] < SMALL_CELL_THRESHOLD:
            raise BundleError("segment below small-cell threshold")
        expected_share = float(_dec(row["qualifying_gross_merchandise"], "segment gross") / gross)
        if abs(row["share_of_identified_qualifying_gross"] - expected_share) > 1e-12:
            raise BundleError("segment gross share does not reconcile")
    if bundle["content_sha256"] != EXPECTED_CONTENT_SHA256:
        raise BundleError("bundle content hash differs from the independently approved application bundle")
    return bundle


def load_bundle(path: str | Path = DEFAULT_BUNDLE_PATH) -> dict[str, Any]:
    """Load and validate the tracked bundle; fail closed with ``BundleError``."""
    path = Path(path)
    if not path.is_file():
        raise BundleError(f"Customer Overview bundle not found: {path.name}")
    try:
        bundle = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BundleError(f"Customer Overview bundle could not be read as JSON: {exc}") from None
    return validate_bundle(bundle)


# --------------------------------------------------------------------------- one-time build

def _optional_float(value: str) -> float | None:
    return None if value in ("", None) else float(value)


def _optional_int(value: str) -> int | None:
    return None if value in ("", None) else int(value)


def build_bundle(source_dir: str | Path = DEFAULT_SOURCE_DIR) -> dict[str, Any]:
    """Build the allowlisted bundle from accepted corrected-V2 aggregate outputs."""
    source_dir = Path(source_dir)
    missing = [name for name in SOURCE_FILES if not (source_dir / name).is_file()]
    if missing:
        raise BundleError(f"accepted corrected-V2 aggregate inputs are missing: {missing}")
    sys.path.insert(0, str(ROOT / "docs/recovery"))
    try:
        import COMMERCIAL_DS_007D_PACKAGE as package  # accepted aggregate contract
    finally:
        sys.path.pop(0)
    inputs = {}
    for name, fields in package.INPUT_SCHEMAS.items():
        path = source_dir / name
        inputs[name] = package.read_json(path, fields) if name.endswith(".json") else package.read_csv(path, fields)
    package.validate(inputs)  # re-apply the accepted 007D contract before any extraction

    rec = inputs["reconciliation.json"]
    conc = inputs["concentration_summary.csv"][0]
    repeat_rows = inputs["repeat_90d_by_first_observed_month.csv"]
    headline = {
        "identified_customers": int(rec["customer_count"]),
        "qualifying_purchase_occasions": int(rec["occasion_count"]),
        "qualifying_merchandise_lines": int(rec["qualifying_line_count"]),
        "qualifying_gross_merchandise": str(Decimal(rec["qualifying_gross_merchandise"])),
        "unattributed_positive_merchandise_excluded": str(Decimal(conc["unattributed_positive_merchandise_excluded"])),
        "mature_90d_customers": sum(int(r["mature_customer_count"]) for r in repeat_rows),
        "insufficient_follow_up_customers": sum(int(r["insufficient_follow_up_count"]) for r in repeat_rows),
        "observation_start_date": "2009-12-01",
        "source_end_timestamp": rec["recency_reference_timestamp"],
        "source_end_is_partial_day": bool(rec["recency_reference_date_is_partial"]),
        "last_complete_activity_month": rec["last_complete_activity_month"],
    }
    numerator = Decimal(conc["top_decile_qualifying_gross"])
    denominator = Decimal(conc["identified_qualifying_gross_denominator"])
    concentration = {
        "eligible_customer_count": int(conc["eligible_customer_count"]),
        "top_decile_customer_count": int(conc["top_decile_customer_count"]),
        "top_decile_qualifying_gross": str(numerator),
        "identified_qualifying_gross_denominator": str(denominator),
        "top_decile_share": float(numerator / denominator),
        "ranking_rule": "customers ranked by identified qualifying gross; top ceil(10%) of customers",
        "monetary_measure": conc["monetary_measure"],
    }
    repeat = [{
        "population": r["population"],
        "first_observed_month": r["first_observed_month"],
        "eligible_customer_count": int(r["eligible_customer_count"]),
        "mature_customer_count": int(r["mature_customer_count"]),
        "repeat_numerator": int(r["repeat_numerator"]),
        "conversion_fraction": (int(r["repeat_numerator"]) / int(r["denominator"])) if int(r["denominator"]) else None,
        "median_days_to_second_purchase_among_mature_repeaters": _optional_float(
            r["median_days_to_second_purchase_among_mature_repeaters"]),
        "insufficient_follow_up_count": int(r["insufficient_follow_up_count"]),
    } for r in repeat_rows]

    cohort = []
    suppressed = 0
    for r in inputs["first_observed_cohort_activity.csv"]:
        index = int(r["month_index"])
        active = _optional_int(r["active_customers"])
        size = int(r["cohort_size"])
        status = r["cell_status"]
        if status == "observed_complete" and index > 0 and active is not None and active < SMALL_CELL_THRESHOLD:
            status, active = "suppressed_small_cell", None
            suppressed += 1
        cohort.append({
            "population": r["population"],
            "cohort_month": r["cohort_month"],
            "month_index": index,
            "activity_month": r["activity_month"],
            "cohort_size": size,
            "active_customers": active,
            "activity_fraction": (active / size) if active is not None else None,
            "cell_status": status,
        })

    segment_rows = inputs["segment_summary.csv"]
    gross = Decimal(rec["qualifying_gross_merchandise"])
    segments = [{
        "purchase_frequency": r["purchase_frequency"],
        "recency_state": r["recency_state"],
        "customer_count": int(r["customer_count"]),
        "qualifying_gross_merchandise": str(Decimal(r["qualifying_gross_merchandise"])),
        "share_of_identified_qualifying_gross": float(Decimal(r["qualifying_gross_merchandise"]) / gross),
    } for r in segment_rows]

    bundle: dict[str, Any] = {
        "bundle_name": BUNDLE_NAME,
        "bundle_version": BUNDLE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "evidence_label": "Historical description",
        "provenance": {
            "population": "identified customers with at least one qualifying merchandise purchase in corrected V2",
            "source_aggregate_sha256": {name: _sha256_file(source_dir / name) for name in SOURCE_FILES},
            "source_generators": {
                "COMMERCIAL_DS_007B_CUSTOMER_ANALYTICS": "34fce9a8f8c2c800550e7a17fb6713bf76ae3ddd",
                "COMMERCIAL_DS_007C_VALUE_SEGMENTS": "eb2677e55de7a96e715cee92073352c186af341a",
            },
            "contract_checks": "docs/recovery/COMMERCIAL_DS_007D_PACKAGE.py::validate applied before extraction",
            "reference_report": "reports/corrected_v2/corrected_v2_scientific_results.md",
            "builder": "src/customer_overview_bundle.py",
            "builder_sha256": _sha256_file(Path(__file__)),
        },
        "publication_review": {
            "customer_level_fields_included": False,
            "small_cell_threshold": SMALL_CELL_THRESHOLD,
            "suppressed_cohort_cells": suppressed,
            "suppression_rule": (
                "Dashboard display convention only: 4 post-entry cohort cells with 1-4 active customers are null here; "
                "not a disclosure guarantee because the accepted corrected-V2 Figure 2 SVG encodes the underlying values."
            ),
            "excluded_source_files": EXCLUDED_SOURCE_FILES,
            "excluded_fields": [
                "concentration ranking tie-break description referencing customer IDs",
                "cohort is_mature/is_cohort_entry flags (derivable from cell_status and month_index)",
                "repeat denominator and timing-count duplicates of mature/numerator counts",
            ],
        },
        "headline": headline,
        "concentration": concentration,
        "repeat_90d": repeat,
        "cohort_activity": cohort,
        "segments": segments,
        "content_sha256": "",
    }
    bundle["content_sha256"] = content_hash(bundle)
    return validate_bundle(copy.deepcopy(bundle))


def write_bundle(bundle: dict[str, Any], path: str | Path = DEFAULT_BUNDLE_PATH) -> Path:
    validate_bundle(bundle)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(bundle, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the aggregate-only Customer Overview bundle (one-time research step).")
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_BUNDLE_PATH)
    args = parser.parse_args(argv)
    path = write_bundle(build_bundle(args.source_dir), args.output)
    print(json.dumps({"bundle": str(path), "sha256": _sha256_file(path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
