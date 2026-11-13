"""Pure presentation-ready calculations for the Customer Overview page.

Functions take a validated bundle (see ``customer_overview_bundle``) and return
small pandas tables. They perform no I/O and contain no Streamlit code.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

import pandas as pd

POPULATION_LABELS = {
    "first_observed_before_2010-12-01": "First observed before Dec 2010",
    "first_observed_on_or_after_2010-12-01": "First observed from Dec 2010",
}
FREQUENCY_LABELS = {
    "one_observed_purchase_day": "One purchase day",
    "repeat_observed_purchase_days": "Repeat purchase days",
}
RECENCY_LABELS = {
    "active_observed": "Last purchase 0–59 days before data end",
    "inactive_60_89_days": "Last purchase 60–89 days before data end",
    "no_observed_purchase_90_plus_days": "No purchase in last 90+ days",
}
COHORT_STATUS_LABELS = {
    "observed_complete": "Observed",
    "not_observed_incomplete_or_future": "Not yet observable",
    "suppressed_small_cell": "Suppressed (<5 customers)",
}


def headline_metrics(bundle: dict[str, Any]) -> dict[str, Any]:
    head = bundle["headline"]
    conc = bundle["concentration"]
    gross = Decimal(head["qualifying_gross_merchandise"])
    return {
        "identified_customers": head["identified_customers"],
        "qualifying_purchase_occasions": head["qualifying_purchase_occasions"],
        "qualifying_merchandise_lines": head["qualifying_merchandise_lines"],
        "qualifying_gross_merchandise_gbp": float(gross),
        "occasions_per_customer": head["qualifying_purchase_occasions"] / head["identified_customers"],
        "top_decile_customer_count": conc["top_decile_customer_count"],
        "top_decile_share": conc["top_decile_share"],
        "mature_90d_customers": head["mature_90d_customers"],
        "insufficient_follow_up_customers": head["insufficient_follow_up_customers"],
        "unattributed_positive_merchandise_gbp": float(Decimal(head["unattributed_positive_merchandise_excluded"])),
        "observation_start_date": head["observation_start_date"],
        "source_end_timestamp": head["source_end_timestamp"],
        "last_complete_activity_month": head["last_complete_activity_month"],
    }


def repeat_table(bundle: dict[str, Any]) -> pd.DataFrame:
    """Mature 90-day second-purchase conversion by first-observed month.

    Strata without any mature customer keep a null conversion and are flagged;
    partially mature strata are flagged so no pooled or full-cohort rate is implied.
    """
    frame = pd.DataFrame(bundle["repeat_90d"])
    frame["population_label"] = frame["population"].map(POPULATION_LABELS)
    frame["conversion_pct"] = frame["conversion_fraction"].astype("Float64") * 100
    frame["maturity"] = "All mature"
    frame.loc[frame["insufficient_follow_up_count"] > 0, "maturity"] = "Partly mature"
    frame.loc[frame["mature_customer_count"] == 0, "maturity"] = "Not yet mature"
    return frame.sort_values(["population", "first_observed_month"]).reset_index(drop=True)


def concentration_table(bundle: dict[str, Any]) -> pd.DataFrame:
    conc = bundle["concentration"]
    numerator = Decimal(conc["top_decile_qualifying_gross"])
    denominator = Decimal(conc["identified_qualifying_gross_denominator"])
    top_n = conc["top_decile_customer_count"]
    total_n = conc["eligible_customer_count"]
    return pd.DataFrame([
        {"group": f"Top 10% of customers ({top_n:,})", "customers": top_n,
         "qualifying_gross_gbp": float(numerator), "share_of_gross": float(numerator / denominator),
         "share_of_customers": top_n / total_n},
        {"group": f"Remaining customers ({total_n - top_n:,})", "customers": total_n - top_n,
         "qualifying_gross_gbp": float(denominator - numerator), "share_of_gross": float((denominator - numerator) / denominator),
         "share_of_customers": (total_n - top_n) / total_n},
    ])


def cohort_table(bundle: dict[str, Any], population: str, *, include_entry_month: bool = False) -> pd.DataFrame:
    """Long cohort-activity table for one population; unavailable cells stay null."""
    if population not in POPULATION_LABELS:
        raise ValueError(f"unknown population: {population}")
    frame = pd.DataFrame(bundle["cohort_activity"])
    frame = frame.loc[frame["population"].eq(population)].copy()
    if not include_entry_month:
        frame = frame.loc[frame["month_index"].gt(0)]
    frame["activity_pct"] = frame["activity_fraction"].astype("Float64") * 100
    frame["status_label"] = frame["cell_status"].map(COHORT_STATUS_LABELS)
    return frame.sort_values(["cohort_month", "month_index"]).reset_index(drop=True)


def segment_table(bundle: dict[str, Any]) -> pd.DataFrame:
    frame = pd.DataFrame(bundle["segments"])
    frame["frequency_label"] = frame["purchase_frequency"].map(FREQUENCY_LABELS)
    frame["recency_label"] = frame["recency_state"].map(RECENCY_LABELS)
    total = frame["customer_count"].sum()
    frame["share_of_customers"] = frame["customer_count"] / total
    frame["qualifying_gross_gbp"] = frame["qualifying_gross_merchandise"].map(lambda v: float(Decimal(v)))
    frame["gross_per_customer_gbp"] = frame["qualifying_gross_gbp"] / frame["customer_count"]
    order = {(f, r): i for i, (f, r) in enumerate(
        (f, r) for f in FREQUENCY_LABELS for r in RECENCY_LABELS)}
    frame["_order"] = [order[(f, r)] for f, r in zip(frame["purchase_frequency"], frame["recency_state"])]
    return frame.sort_values("_order").drop(columns="_order").reset_index(drop=True)
