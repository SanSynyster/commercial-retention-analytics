"""Corrected-V2 customer metrics and censoring-aware repeat/cohort summaries.

Customer-level rows are local derived data. The public-facing outputs from this
module are the aggregate repeat and first-observed cohort tables only.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re
import sys
from statistics import median

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))

from COMMERCIAL_DS_003_PURCHASE_OCCASIONS import (  # noqa: E402
    ACQUISITION_CUTOFF,
    DATA_END_DATE,
    DATA_END_TIMESTAMP,
    OBSERVATION_START,
    build_purchase_occasions,
    label_is_mature,
    load_validated_purchase_input,
    primary_later_day_repeat,
)

DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "processed" / "corrected_v2_customer_analytics"
ACTIVITY_END_EXCLUSIVE = date(2011, 12, 1)  # November 2011 is last complete month.
MAX_COHORT_MONTH_INDEX = (
    (DATA_END_DATE.year - OBSERVATION_START.year) * 12
    + DATA_END_DATE.month - OBSERVATION_START.month
)
POPULATION_BEFORE_CUTOFF = "first_observed_before_2010-12-01"
POPULATION_ON_OR_AFTER_CUTOFF = "first_observed_on_or_after_2010-12-01"

CUSTOMER_FIELDS = (
    "customer_id",
    "qualifying_occasion_count",
    "distinct_purchase_day_count",
    "first_observed_date",
    "last_observed_date",
    "first_observed_month",
    "observed_tenure_days",
    "recency_days",
    "second_purchase_date_within_90d",
    "days_to_second_purchase_within_90d",
    "recency_reference_date",
    "recency_reference_date_is_partial",
    "qualifying_gross_merchandise",
)
REPEAT_FIELDS = (
    "population",
    "first_observed_month",
    "eligible_customer_count",
    "mature_customer_count",
    "repeat_numerator",
    "denominator",
    "conversion_fraction",
    "mature_repeat_timing_count",
    "median_days_to_second_purchase_among_mature_repeaters",
    "insufficient_follow_up_count",
)
COHORT_FIELDS = (
    "population",
    "cohort_month",
    "month_index",
    "activity_month",
    "cohort_size",
    "active_customers",
    "activity_fraction",
    "is_mature",
    "is_cohort_entry",
    "cell_status",
)


def _canonical_customer_id(value: object) -> str:
    """Validate the canonical string IDs emitted by the occasion API."""
    if not isinstance(value, str) or re.fullmatch(r"[1-9][0-9]*", value) is None:
        raise ValueError(f"occasion customer_id is not a canonical positive integer: {value!r}")
    return value


def _occasion_date(value: object) -> date:
    if isinstance(value, datetime):
        raise TypeError("occasion transaction_date must be a calendar date, not a timestamp")
    if isinstance(value, date):
        result = value
    elif isinstance(value, str):
        try:
            result = date.fromisoformat(value)
        except ValueError:
            raise ValueError(f"invalid ISO occasion date: {value!r}") from None
        if result.isoformat() != value:
            raise ValueError(f"occasion date must use canonical YYYY-MM-DD form: {value!r}")
    else:
        raise TypeError(f"occasion date must be a date or ISO date string, got {type(value).__name__}")
    if not OBSERVATION_START <= result <= DATA_END_DATE:
        raise ValueError(f"occasion date is outside the frozen observed date range: {result}")
    return result


def _occasion_amount(value: object) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float):
        raise TypeError("occasion gross must use Decimal or its exact string representation")
    try:
        amount = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f"invalid occasion gross: {value!r}") from None
    if not amount.is_finite() or amount <= 0:
        raise ValueError(f"qualifying occasion gross must be finite and positive: {value!r}")
    return amount


def _month_start(value: date) -> date:
    return date(value.year, value.month, 1)


def _add_months(value: date, months: int) -> date:
    month_index = value.year * 12 + (value.month - 1) + months
    year, month_zero = divmod(month_index, 12)
    return date(year, month_zero + 1, 1)


def _population(first_observed_date: date) -> str:
    if first_observed_date < ACQUISITION_CUTOFF:
        return POPULATION_BEFORE_CUTOFF
    return POPULATION_ON_OR_AFTER_CUTOFF


def build_customer_metrics(occasions: list[dict]) -> list[dict]:
    """Build one exact-Decimal customer row from frozen qualifying occasions."""
    customers: dict[str, dict] = {}
    seen_occasions: set[tuple[str, str]] = set()

    for occasion in occasions:
        customer_id = _canonical_customer_id(occasion.get("customer_id"))
        invoice_id = occasion.get("invoice_id")
        if not isinstance(invoice_id, str) or not invoice_id:
            raise ValueError(f"occasion invoice_id is missing or invalid: {invoice_id!r}")
        key = (customer_id, invoice_id)
        if key in seen_occasions:
            raise ValueError(f"duplicate customer × invoice occasion: {key!r}")
        seen_occasions.add(key)

        day = _occasion_date(occasion.get("transaction_date"))
        gross = _occasion_amount(occasion.get("qualifying_gross_merchandise"))
        line_count = occasion.get("eligible_line_count")
        if isinstance(line_count, bool) or not isinstance(line_count, int) or line_count <= 0:
            raise ValueError(f"occasion eligible_line_count must be a positive integer: {line_count!r}")

        row = customers.setdefault(
            customer_id,
            {"days": set(), "first": day, "last": day, "occasion_count": 0, "gross": Decimal(0)},
        )
        row["days"].add(day)
        row["first"] = min(row["first"], day)
        row["last"] = max(row["last"], day)
        row["occasion_count"] += 1
        row["gross"] += gross

    if not customers and occasions:
        raise AssertionError("non-empty occasion input produced no customers")

    result = []
    for customer_id in sorted(customers, key=int):
        row = customers[customer_id]
        first = row["first"]
        last = row["last"]
        if last > DATA_END_DATE:
            raise AssertionError("last purchase date exceeds frozen recency reference date")
        observed_later_days = sorted(
            day
            for day in row["days"]
            if primary_later_day_repeat(
                datetime.combine(first, datetime.min.time()),
                datetime.combine(day, datetime.min.time()),
            )
        )
        second_day = observed_later_days[0] if observed_later_days else None
        result.append(
            {
                "customer_id": customer_id,
                "qualifying_occasion_count": row["occasion_count"],
                "distinct_purchase_day_count": len(row["days"]),
                "first_observed_date": first.isoformat(),
                "last_observed_date": last.isoformat(),
                "first_observed_month": _month_start(first).isoformat()[:7],
                "observed_tenure_days": (last - first).days,
                "recency_days": (DATA_END_DATE - last).days,
                "second_purchase_date_within_90d": None if second_day is None else second_day.isoformat(),
                "days_to_second_purchase_within_90d": None if second_day is None else (second_day - first).days,
                "recency_reference_date": DATA_END_DATE.isoformat(),
                "recency_reference_date_is_partial": True,
                "qualifying_gross_merchandise": row["gross"],
            }
        )
    return result


def build_repeat_summary(customer_metrics: list[dict]) -> list[dict]:
    """Summarize mature 90-day date-level repeats by cutoff group and month."""
    groups: dict[tuple[str, str], list[dict]] = {}
    seen: set[str] = set()
    for row in customer_metrics:
        customer_id = _canonical_customer_id(row.get("customer_id"))
        if customer_id in seen:
            raise ValueError(f"duplicate customer metric row: {customer_id}")
        seen.add(customer_id)
        first = _occasion_date(row.get("first_observed_date"))
        groups.setdefault((_population(first), _month_start(first).isoformat()[:7]), []).append(row)

    result = []
    for population, cohort_month in sorted(groups):
        group = groups[(population, cohort_month)]
        mature_rows = []
        for row in group:
            first = _occasion_date(row["first_observed_date"])
            if label_is_mature(datetime.combine(first, datetime.min.time())):
                mature_rows.append(row)

        timing_days = [
            row["days_to_second_purchase_within_90d"]
            for row in mature_rows
            if row.get("days_to_second_purchase_within_90d") is not None
        ]
        numerator = len(timing_days)
        denominator = len(mature_rows)
        result.append(
            {
                "population": population,
                "first_observed_month": cohort_month,
                "eligible_customer_count": len(group),
                "mature_customer_count": denominator,
                "repeat_numerator": numerator,
                "denominator": denominator,
                "conversion_fraction": None if denominator == 0 else numerator / denominator,
                "mature_repeat_timing_count": len(timing_days),
                "median_days_to_second_purchase_among_mature_repeaters": (
                    None if not timing_days else median(timing_days)
                ),
                "insufficient_follow_up_count": len(group) - denominator,
            }
        )
    return result


def build_cohort_activity(occasions: list[dict], customer_metrics: list[dict]) -> list[dict]:
    """Build full-month-mature first-observed cohort activity cells.

    The common 0..24 month-index grid includes explicit null cells for the
    partial December 2011 month and all later relative months. Month 0 is
    flagged as cohort entry, not repeat retention. December 2011 cohort
    results are immature and must be flagged or excluded from future
    maturity-dependent charts.
    """
    customers_by_cohort: dict[tuple[str, str], set[str]] = {}
    customer_population: dict[str, str] = {}
    for row in customer_metrics:
        customer_id = _canonical_customer_id(row.get("customer_id"))
        if customer_id in customer_population:
            raise ValueError(f"duplicate customer metric row: {customer_id}")
        first = _occasion_date(row.get("first_observed_date"))
        cohort_month = _month_start(first).isoformat()[:7]
        key = (_population(first), cohort_month)
        customer_population[customer_id] = key[0]
        customers_by_cohort.setdefault(key, set()).add(customer_id)

    active_by_month: dict[tuple[str, date], set[str]] = {}
    for occasion in occasions:
        customer_id = _canonical_customer_id(occasion.get("customer_id"))
        day = _occasion_date(occasion.get("transaction_date"))
        population = customer_population.get(customer_id)
        if population is None:
            raise ValueError(f"occasion customer is absent from customer metrics: {customer_id}")
        active_by_month.setdefault((population, _month_start(day)), set()).add(customer_id)

    result = []
    for (population, cohort_month_text), cohort_customers in sorted(customers_by_cohort.items()):
        cohort_month = date.fromisoformat(f"{cohort_month_text}-01")
        for month_index in range(MAX_COHORT_MONTH_INDEX + 1):
            activity_month = _add_months(cohort_month, month_index)
            period_end = _add_months(activity_month, 1)
            mature = period_end <= ACTIVITY_END_EXCLUSIVE
            active = (
                len(active_by_month.get((population, activity_month), set()) & cohort_customers)
                if mature
                else None
            )
            result.append(
                {
                    "population": population,
                    "cohort_month": cohort_month_text,
                    "month_index": month_index,
                    "activity_month": activity_month.isoformat()[:7],
                    "cohort_size": len(cohort_customers),
                    "active_customers": active,
                    "activity_fraction": None if active is None else active / len(cohort_customers),
                    "is_mature": mature,
                    "is_cohort_entry": month_index == 0,
                    "cell_status": "observed_complete" if mature else "not_observed_incomplete_or_future",
                }
            )
    return result


def build_customer_analytics(occasions: list[dict]) -> dict:
    """Transform trusted occasion records into local and aggregate outputs."""
    metrics = build_customer_metrics(occasions)
    repeat_summary = build_repeat_summary(metrics)
    cohort_activity = build_cohort_activity(occasions, metrics)

    occasion_count = sum(row["qualifying_occasion_count"] for row in metrics)
    gross = sum((row["qualifying_gross_merchandise"] for row in metrics), Decimal(0))
    if occasion_count != len(occasions):
        raise AssertionError(f"customer occasion count does not reconcile: {occasion_count} != {len(occasions)}")
    if gross != sum((_occasion_amount(o["qualifying_gross_merchandise"]) for o in occasions), Decimal(0)):
        raise AssertionError("customer gross does not reconcile to occasions")

    return {
        "customer_metrics": metrics,
        "repeat_90d_by_first_observed_month": repeat_summary,
        "first_observed_cohort_activity": cohort_activity,
        "reconciliation": {
            "customer_count": len(metrics),
            "occasion_count": occasion_count,
            "qualifying_gross_merchandise": str(gross),
            "all_customer_rows_have_unique_ids": len({r["customer_id"] for r in metrics}) == len(metrics),
            "repeat_rows_are_stratified_only": True,
            "pooled_repeat_rate_published": False,
            "recency_reference_date": DATA_END_DATE.isoformat(),
            "recency_reference_timestamp": DATA_END_TIMESTAMP.isoformat(sep=" "),
            "recency_reference_date_is_partial": True,
            "last_complete_activity_month": "2011-11",
            "maximum_cohort_month_index": MAX_COHORT_MONTH_INDEX,
        },
    }


def build_real_data_customer_analytics() -> dict:
    """Run only through the validated corrected-V2 production API."""
    validated = load_validated_purchase_input()
    occasions, frozen_summary = build_purchase_occasions(validated)
    result = build_customer_analytics(occasions)
    reconciliation = result["reconciliation"]
    for key, result_key in (
        ("customer_count", "customer_count"),
        ("occasion_count", "occasion_count"),
        ("qualifying_gross_merchandise", "qualifying_gross_merchandise"),
    ):
        if reconciliation[result_key] != frozen_summary[key]:
            raise AssertionError(
                f"customer metric reconciliation mismatch for {key}: "
                f"{reconciliation[result_key]} != {frozen_summary[key]}"
            )
    reconciliation["qualifying_line_count"] = frozen_summary["qualifying_line_count"]
    reconciliation["occasion_reference_validated_by_production_api"] = True
    return result


def _csv_value(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _write_csv(path: Path, rows: list[dict], fields: tuple[str, ...]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(row.get(key)) for key in fields})


def write_local_outputs(result: dict, output_dir: Path = DEFAULT_OUTPUT_DIR) -> None:
    """Write internal customer rows and reviewable aggregates under data/processed."""
    output_dir = output_dir.resolve()
    safe_root = (REPO_ROOT / "data" / "processed").resolve()
    if output_dir != safe_root and safe_root not in output_dir.parents:
        raise ValueError("customer-level outputs may only be written below data/processed/")
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "customer_metrics.csv", result["customer_metrics"], CUSTOMER_FIELDS)
    _write_csv(
        output_dir / "repeat_90d_by_first_observed_month.csv",
        result["repeat_90d_by_first_observed_month"],
        REPEAT_FIELDS,
    )
    _write_csv(
        output_dir / "first_observed_cohort_activity.csv",
        result["first_observed_cohort_activity"],
        COHORT_FIELDS,
    )
    with (output_dir / "reconciliation.json").open("w", encoding="utf-8") as handle:
        json.dump(result["reconciliation"], handle, indent=2, sort_keys=True)
        handle.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="ignored local output directory below data/processed/",
    )
    args = parser.parse_args()
    result = build_real_data_customer_analytics()
    write_local_outputs(result, args.output_dir)
    print(json.dumps(result["reconciliation"], sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
