"""Corrected-V2 customer concentration, signed sensitivity and descriptive segments."""
from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))

import COMMERCIAL_DS_003_REVENUE_BRIDGE as bridge  # noqa: E402
from COMMERCIAL_DS_003_PURCHASE_OCCASIONS import (  # noqa: E402
    DATA_END_DATE,
    build_purchase_occasions,
    load_validated_purchase_input,
)
from COMMERCIAL_DS_007B_CUSTOMER_ANALYTICS import (  # noqa: E402
    build_customer_analytics,
)

DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "processed" / "corrected_v2_customer_analytics"
RECENT_FIRST_OBSERVED_DAYS = 30
RECENCY_REFERENCE_DATE = DATA_END_DATE
SEGMENT_FIELDS = (
    "purchase_frequency",
    "recency_state",
    "customer_count",
    "qualifying_gross_merchandise",
    "share_of_identified_qualifying_gross",
)
CONCENTRATION_FIELDS = (
    "eligible_customer_count",
    "top_decile_customer_count",
    "top_decile_qualifying_gross",
    "identified_qualifying_gross_denominator",
    "top_decile_share",
    "ranking_rule",
    "monetary_measure",
    "unattributed_positive_merchandise_excluded",
)
SIGNED_FIELDS = (
    "view_label",
    "identified_customer_count",
    "qualifying_positive_merchandise_rows",
    "qualifying_positive_merchandise_amount",
    "identified_return_cancellation_rows",
    "identified_return_cancellation_signed_amount",
    "signed_merchandise_sensitivity_amount",
    "returns_only_customer_count",
    "negative_net_customer_count",
    "unattributed_return_cancellation_rows_excluded",
    "unattributed_return_cancellation_signed_amount_excluded",
    "manual_credits_included",
    "manual_credits_bridge_identifiable_amount_separate",
)
FLAG_FIELDS = ("flag", "customer_count", "qualifying_gross_merchandise")
CUSTOMER_FLAG_FIELDS = (
    "customer_id",
    "purchase_frequency",
    "recency_days",
    "recency_state",
    "recent_first_observed_30d",
    "top_decile_qualifying_gross",
    "qualifying_gross_merchandise",
)
SIGNED_CUSTOMER_FIELDS = (
    "customer_id",
    "qualifying_positive_merchandise",
    "identified_returns_cancellations_signed",
    "unlinked_signed_merchandise_sensitivity",
    "has_qualifying_purchase",
    "is_returns_only",
    "is_negative_net_sensitivity",
)


def _date(value: object) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _decimal(value: object) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float):
        raise TypeError("monetary values must be Decimal or exact strings")
    return value if isinstance(value, Decimal) else Decimal(str(value))


def build_concentration(customer_metrics: list[dict], unattributed_positive_merchandise: object) -> tuple[list[dict], dict]:
    """Rank identified qualifying gross; ties resolve by canonical ID ascending."""
    customers = sorted(
        customer_metrics,
        key=lambda row: (-_decimal(row["qualifying_gross_merchandise"]), int(row["customer_id"])),
    )
    if not customers:
        raise ValueError("concentration requires at least one qualifying customer")
    ids = [str(row["customer_id"]) for row in customers]
    if len(ids) != len(set(ids)):
        raise ValueError("customer metrics must contain unique customer IDs")
    denominator = sum((_decimal(row["qualifying_gross_merchandise"]) for row in customers), Decimal(0))
    top_count = (len(customers) + 9) // 10
    top_gross = sum((_decimal(row["qualifying_gross_merchandise"]) for row in customers[:top_count]), Decimal(0))
    summary = {
        "eligible_customer_count": len(customers),
        "top_decile_customer_count": top_count,
        "top_decile_qualifying_gross": top_gross,
        "identified_qualifying_gross_denominator": denominator,
        "top_decile_share": top_gross / denominator,
        "ranking_rule": "qualifying gross descending; canonical customer ID ascending for ties",
        "monetary_measure": "identified qualifying gross merchandise; not accounting revenue, net sales, margin or profit",
        "unattributed_positive_merchandise_excluded": _decimal(unattributed_positive_merchandise),
    }
    ranked = []
    top_ids = {row["customer_id"] for row in customers[:top_count]}
    for rank, row in enumerate(customers, start=1):
        ranked.append({**row, "qualifying_gross_rank": rank, "top_decile_qualifying_gross": row["customer_id"] in top_ids})
    return ranked, summary


def build_signed_merchandise_sensitivity(source_rows: list[dict], qualifying_source_row_ids: set[int], bridge_leaves: dict) -> tuple[list[dict], dict]:
    """Build an unlinked identified signed merchandise-line sensitivity.

    Include qualifying positive merchandise and all identified negative
    merchandise return/cancellation lines. Do not infer invoice linkage or add
    credits, other positive merchandise, or unattributed activity.
    """
    by_customer: dict[str, dict] = {}
    qualifying_total = Decimal(0)
    qualifying_count = 0
    returns_total = Decimal(0)
    returns_count = 0
    unattributed_returns_total = Decimal(0)
    unattributed_returns_count = 0
    qualifying_ids_seen: set[int] = set()
    for row in source_rows:
        source_id = int(row["source_row_number"])
        amount = bridge._amount(row["Quantity"], row["UnitPrice"])
        if row["category"] != "merchandise":
            continue
        is_qualifying = source_id in qualifying_source_row_ids
        is_return = amount < 0
        if not is_qualifying and not is_return:
            continue
        customer_id = bridge.canonical_customer_id(row["CustomerID"])
        if is_qualifying and customer_id is None:
            raise AssertionError("frozen qualifying purchase line lacks an identifiable customer")
        if is_qualifying:
            if amount <= 0:
                raise AssertionError("qualifying occasion source row is not positive merchandise")
            qualifying_ids_seen.add(source_id)
            qualifying_total += amount
            qualifying_count += 1
        if is_return:
            if customer_id is None:
                unattributed_returns_total += amount
                unattributed_returns_count += 1
                continue
            returns_total += amount
            returns_count += 1
        if customer_id is None:
            continue
        customer = by_customer.setdefault(customer_id, {"positive": Decimal(0), "returns": Decimal(0), "has_qualifying": False})
        if is_qualifying:
            customer["positive"] += amount
            customer["has_qualifying"] = True
        elif is_return:
            customer["returns"] += amount

    if qualifying_ids_seen != qualifying_source_row_ids:
        missing = len(qualifying_source_row_ids - qualifying_ids_seen)
        raise AssertionError(f"{missing} qualifying source rows absent from signed merchandise rows")
    qualifying_leaf = bridge_leaves["qualifying_gross_merchandise_purchases"]
    returns_leaf = bridge_leaves["merchandise_returns_cancellations"]
    if qualifying_total != Decimal(qualifying_leaf["identifiable_amount"]):
        raise AssertionError("identified qualifying positive merchandise does not reconcile to frozen bridge leaf")
    if qualifying_count != qualifying_leaf["identifiable_rows"]:
        raise AssertionError("qualifying positive merchandise row count does not reconcile to frozen bridge leaf")
    if returns_total != Decimal(returns_leaf["identifiable_amount"]):
        raise AssertionError("identified merchandise returns do not reconcile to frozen bridge leaf")
    if returns_count != returns_leaf["identifiable_rows"]:
        raise AssertionError("identified merchandise return row count does not reconcile to frozen bridge leaf")

    result = []
    for customer_id in sorted(by_customer, key=int):
        row = by_customer[customer_id]
        net = row["positive"] + row["returns"]
        result.append({
            "customer_id": customer_id,
            "qualifying_positive_merchandise": row["positive"],
            "identified_returns_cancellations_signed": row["returns"],
            "unlinked_signed_merchandise_sensitivity": net,
            "has_qualifying_purchase": row["has_qualifying"],
            "is_returns_only": not row["has_qualifying"] and row["returns"] < 0,
            "is_negative_net_sensitivity": net < 0,
        })
    summary = {
        "view_label": "unlinked signed merchandise-line sensitivity; not net sales, CLV or profit",
        "identified_customer_count": len(result),
        "qualifying_positive_merchandise_rows": qualifying_count,
        "qualifying_positive_merchandise_amount": qualifying_total,
        "identified_return_cancellation_rows": returns_count,
        "identified_return_cancellation_signed_amount": returns_total,
        "signed_merchandise_sensitivity_amount": qualifying_total + returns_total,
        "returns_only_customer_count": sum(row["is_returns_only"] for row in result),
        "negative_net_customer_count": sum(row["is_negative_net_sensitivity"] for row in result),
        "unattributed_return_cancellation_rows_excluded": unattributed_returns_count,
        "unattributed_return_cancellation_signed_amount_excluded": unattributed_returns_total,
        "manual_credits_included": False,
        "manual_credits_bridge_identifiable_amount_separate": Decimal(bridge_leaves["standalone_manual_credits"]["identifiable_amount"]),
    }
    return result, summary


def build_descriptive_segments(customer_metrics: list[dict], recent_days: int = RECENT_FIRST_OBSERVED_DAYS) -> tuple[list[dict], list[dict], list[dict]]:
    """Assign descriptive groups and independent flags.

    By default, ``recent_first_observed_30d`` includes first-observed dates
    from 0 through 30 calendar days before 2011-12-09, inclusive of day 30.
    This inclusive window is a descriptive implementation convention; it has
    not been validated for CRM targeting or predictive use.
    """
    if recent_days < 0:
        raise ValueError("recent_days must be nonnegative")
    required_states = (
        "one_observed_purchase_day", "repeat_observed_purchase_days",
    )
    recency_states = (
        "active_observed", "inactive_60_89_days", "no_observed_purchase_90_plus_days",
    )
    ranked_for_flag, _ = build_concentration(customer_metrics, Decimal(0))
    top_ids = {row["customer_id"] for row in ranked_for_flag if row["top_decile_qualifying_gross"]}
    rows = []
    seen: set[str] = set()
    for source in customer_metrics:
        customer_id = str(source["customer_id"])
        if customer_id in seen:
            raise ValueError(f"duplicate customer metric row: {customer_id}")
        seen.add(customer_id)
        purchase_days = int(source["distinct_purchase_day_count"])
        if purchase_days < 1:
            raise ValueError("each customer must have at least one observed purchase day")
        recency = int(source["recency_days"])
        if recency < 0:
            raise ValueError("recency cannot be negative")
        frequency = required_states[0] if purchase_days == 1 else required_states[1]
        if recency <= 59:
            recency_state = recency_states[0]
        elif recency <= 89:
            recency_state = recency_states[1]
        else:
            recency_state = recency_states[2]
        first_date = _date(source["first_observed_date"])
        is_recent_first = 0 <= (RECENCY_REFERENCE_DATE - first_date).days <= recent_days
        rows.append({
            "customer_id": customer_id,
            "purchase_frequency": frequency,
            "recency_days": recency,
            "recency_state": recency_state,
            "recent_first_observed_30d": is_recent_first,
            "top_decile_qualifying_gross": customer_id in top_ids,
            "qualifying_gross_merchandise": _decimal(source["qualifying_gross_merchandise"]),
        })
    segment_map = {(row["purchase_frequency"], row["recency_state"]): [] for row in rows}
    for row in rows:
        segment_map[(row["purchase_frequency"], row["recency_state"])].append(row)
    # Always emit all six groups, including empty groups.
    output = []
    for frequency in required_states:
        for state in recency_states:
            members = segment_map.get((frequency, state), [])
            gross = sum((row["qualifying_gross_merchandise"] for row in members), Decimal(0))
            output.append({
                "purchase_frequency": frequency,
                "recency_state": state,
                "customer_count": len(members),
                "qualifying_gross_merchandise": gross,
                "share_of_identified_qualifying_gross": None,
            })
    total_gross = sum((row["qualifying_gross_merchandise"] for row in rows), Decimal(0))
    for row in output:
        row["share_of_identified_qualifying_gross"] = (
            Decimal(0) if total_gross == 0 else row["qualifying_gross_merchandise"] / total_gross
        )
    flag_summaries = []
    for flag_name in ("recent_first_observed_30d", "top_decile_qualifying_gross"):
        members = [row for row in rows if row[flag_name]]
        flag_summaries.append({
            "flag": flag_name,
            "customer_count": len(members),
            "qualifying_gross_merchandise": sum((row["qualifying_gross_merchandise"] for row in members), Decimal(0)),
        })
    if sum(row["customer_count"] for row in output) != len(rows):
        raise AssertionError("six-group descriptive segmentation is not exhaustive")
    return rows, output, flag_summaries


def apply_top_decile_flag(segment_customers: list[dict], ranked_customers: list[dict]) -> None:
    top_ids = {row["customer_id"] for row in ranked_customers if row["top_decile_qualifying_gross"]}
    for row in segment_customers:
        row["top_decile_qualifying_gross"] = row["customer_id"] in top_ids


def _csv_value(value: object) -> object:
    return str(value) if isinstance(value, Decimal) else value


def _write_csv(path: Path, rows: list[dict], fields: tuple[str, ...]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field)) for field in fields})


def write_outputs(result: dict, output_dir: Path = DEFAULT_OUTPUT_DIR) -> None:
    output_dir = output_dir.resolve()
    safe_root = (REPO_ROOT / "data" / "processed").resolve()
    if output_dir != safe_root and safe_root not in output_dir.parents:
        raise ValueError("customer-level outputs may only be written below data/processed/")
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(output_dir / "customer_value_segment_flags.csv", result["customer_segment_flags"], CUSTOMER_FLAG_FIELDS)
    _write_csv(output_dir / "concentration_summary.csv", [result["concentration_summary"]], CONCENTRATION_FIELDS)
    _write_csv(output_dir / "segment_summary.csv", result["segment_summary"], SEGMENT_FIELDS)
    _write_csv(output_dir / "segment_flag_summary.csv", result["segment_flag_summary"], FLAG_FIELDS)
    _write_csv(output_dir / "signed_merchandise_sensitivity_customers.csv", result["signed_sensitivity_customers"], SIGNED_CUSTOMER_FIELDS)
    _write_csv(output_dir / "signed_merchandise_sensitivity_summary.csv", [result["signed_sensitivity_summary"]], SIGNED_FIELDS)
    with (output_dir / "value_segments_reconciliation.json").open("w", encoding="utf-8") as handle:
        json.dump(result["reconciliation"], handle, indent=2, sort_keys=True)
        handle.write("\n")


def build_real_data_value_segments() -> dict:
    validated = load_validated_purchase_input()
    occasions, frozen_occasion_summary = build_purchase_occasions(validated)
    base = build_customer_analytics(occasions)
    bridge_result = bridge.build_revenue_bridge(validated)
    ranked, concentration = build_concentration(
        base["customer_metrics"],
        bridge_result["merchandise_positive_reconciliation"]["other_positive_nonqualifying_merchandise"],
    )
    qualifying_source_ids = {int(source_id) for occasion in occasions for source_id in occasion["source_row_numbers"]}
    source_rows = validated._frame.to_dict(orient="records")
    signed_customers, signed_summary = build_signed_merchandise_sensitivity(
        source_rows, qualifying_source_ids, bridge_result["bridge_leaves"]
    )
    segment_customers, segment_summary, flag_summary = build_descriptive_segments(base["customer_metrics"])
    apply_top_decile_flag(segment_customers, ranked)
    # Rebuild independent flag totals after applying the ranked concentration flag.
    flag_summary = []
    for flag_name in ("recent_first_observed_30d", "top_decile_qualifying_gross"):
        selected = [row for row in segment_customers if row[flag_name]]
        flag_summary.append({"flag": flag_name, "customer_count": len(selected), "qualifying_gross_merchandise": sum((r["qualifying_gross_merchandise"] for r in selected), Decimal(0))})
    bridge_leaves = bridge_result["bridge_leaves"]
    rec = {
        "customer_count": len(base["customer_metrics"]),
        "qualifying_occasion_count": frozen_occasion_summary["occasion_count"],
        "qualifying_gross_merchandise": str(concentration["identified_qualifying_gross_denominator"]),
        "identified_returns_cancellations_signed": str(Decimal(bridge_leaves["merchandise_returns_cancellations"]["identifiable_amount"])),
        "manual_credits_identifiable_separate": str(Decimal(bridge_leaves["standalone_manual_credits"]["identifiable_amount"])),
        "unattributed_positive_merchandise_excluded": str(Decimal(bridge_result["merchandise_positive_reconciliation"]["other_positive_nonqualifying_merchandise"])),
        "unattributed_returns_cancellations_excluded": str(Decimal(bridge_leaves["merchandise_returns_cancellations"]["unattributed_amount"])),
        "signed_bridge_validated_against_frozen_reference": True,
        "customer_level_outputs_local_only": True,
    }
    if concentration["identified_qualifying_gross_denominator"] != Decimal(frozen_occasion_summary["qualifying_gross_merchandise"]):
        raise AssertionError("customer qualifying gross does not reconcile to frozen occasion summary")
    return {
        "ranked_customer_metrics": ranked,
        "customer_segment_flags": segment_customers,
        "segment_summary": segment_summary,
        "segment_flag_summary": flag_summary,
        "signed_sensitivity_customers": signed_customers,
        "signed_sensitivity_summary": signed_summary,
        "concentration_summary": concentration,
        "reconciliation": rec,
    }


if __name__ == "__main__":
    result = build_real_data_value_segments()
    write_outputs(result)
    print(json.dumps(result["reconciliation"], sort_keys=True, indent=2))
