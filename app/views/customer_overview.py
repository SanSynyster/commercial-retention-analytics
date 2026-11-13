"""Customer Overview page: historical description of corrected-V2 purchasing."""
from __future__ import annotations

import os
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from customer_overview_bundle import DEFAULT_BUNDLE_PATH, BundleError, load_bundle
from customer_overview_metrics import (
    POPULATION_LABELS,
    concentration_table,
    cohort_table,
    headline_metrics,
    repeat_table,
    segment_table,
)

BUNDLE_ENV_VAR = "CUSTOMER_OVERVIEW_BUNDLE"
GRAY = "#C9D1D7"


@st.cache_data(show_spinner=False)
def _load(path: str) -> dict:
    return load_bundle(path)


def _bundle_path() -> str:
    return os.environ.get(BUNDLE_ENV_VAR, str(DEFAULT_BUNDLE_PATH))


def _money(value: float) -> str:
    return f"£{value / 1e6:,.2f}m" if value >= 1e6 else f"£{value:,.0f}"


def render() -> None:
    st.title("Customer Overview")
    try:
        bundle = _load(_bundle_path())
    except BundleError as exc:
        st.error(f"The aggregate data bundle could not be loaded, so no figures are shown. {exc}")
        st.caption(f"Expected file: {Path(_bundle_path()).name}. Rebuild it with `src/customer_overview_bundle.py`.")
        return

    head = headline_metrics(bundle)
    st.caption(
        f"**Evidence type: {bundle['evidence_label']}.** Identified customers with at least one qualifying "
        f"merchandise purchase, {head['observation_start_date']} to {head['source_end_timestamp']} "
        "(the final day is partial). Corrected UCI Online Retail II data."
    )

    cols = st.columns(4)
    cols[0].metric("Identified customers", f"{head['identified_customers']:,}")
    cols[1].metric("Qualifying purchase occasions", f"{head['qualifying_purchase_occasions']:,}",
                   help="One occasion = one identified customer × invoice with qualifying merchandise lines.")
    cols[2].metric("Qualifying gross merchandise", _money(head["qualifying_gross_merchandise_gbp"]),
                   help="Gross merchandise value of qualifying lines; not net sales, margin or profit.")
    cols[3].metric("Top-10% customer gross share", f"{head['top_decile_share']:.1%}",
                   help=f"Top {head['top_decile_customer_count']:,} customers ranked by qualifying gross.")
    st.caption(
        f"{head['occasions_per_customer']:.1f} purchase occasions per customer on average, from "
        f"{head['qualifying_merchandise_lines']:,} qualifying merchandise lines. "
        f"{_money(head['unattributed_positive_merchandise_gbp'])} of positive merchandise could not be attributed "
        "to an identified customer and is excluded from every customer measure."
    )

    _repeat_section(bundle, head)
    _concentration_section(bundle, head)
    _cohort_section(bundle, head)
    _segment_section(bundle, head)
    _provenance(bundle)


def _repeat_section(bundle: dict, head: dict) -> None:
    st.subheader("Second purchase within 90 days")
    st.caption(
        "Share of customers whose second qualifying purchase day falls within 90 days of their first observed "
        "purchase, by first-observed month. Denominator: customers with a complete 90-day follow-up only "
        f"({head['mature_90d_customers']:,} mature; {head['insufficient_follow_up_customers']:,} too recent). "
        "Customers first observed before December 2010 may have bought before the data starts, so they are "
        "shown separately and no pooled rate is given."
    )
    table = repeat_table(bundle)
    chart_data = table.dropna(subset=["conversion_pct"])
    chart = (
        alt.Chart(chart_data)
        .mark_line(point=True)
        .encode(
            x=alt.X("first_observed_month:O", title="First-observed month"),
            y=alt.Y("conversion_pct:Q", title="Second purchase within 90 days (%)", scale=alt.Scale(domain=[0, 100])),
            color=alt.Color("population_label:N", title="Population",
                            scale=alt.Scale(domain=list(POPULATION_LABELS.values()), range=["#4472A1", "#D89A2B"]),
                            legend=alt.Legend(orient="bottom", labelLimit=400)),
            tooltip=[
                alt.Tooltip("first_observed_month:O", title="Month"),
                alt.Tooltip("population_label:N", title="Population"),
                alt.Tooltip("conversion_pct:Q", title="Conversion %", format=".1f"),
                alt.Tooltip("repeat_numerator:Q", title="Repeaters"),
                alt.Tooltip("mature_customer_count:Q", title="Mature denominator"),
                alt.Tooltip("maturity:N", title="Follow-up"),
            ],
        )
        .properties(height=380)
    )
    st.altair_chart(chart, width="stretch")
    partial = table.loc[table["maturity"].eq("Partly mature")]
    unplotted = table.loc[table["maturity"].eq("Not yet mature"), "first_observed_month"].tolist()
    notes = [f"{row.first_observed_month} is only partly mature ({row.mature_customer_count} of "
             f"{row.eligible_customer_count} customers)" for row in partial.itertuples()]
    if unplotted:
        notes.append(f"{', '.join(unplotted)} have no mature follow-up and are not plotted")
    if notes:
        st.caption("; ".join(notes) + ".")
    with st.expander("Monthly figures"):
        st.dataframe(
            table[["population_label", "first_observed_month", "eligible_customer_count", "mature_customer_count",
                   "repeat_numerator", "conversion_pct", "median_days_to_second_purchase_among_mature_repeaters", "maturity"]],
            hide_index=True,
            column_config={
                "population_label": "Population",
                "first_observed_month": "First-observed month",
                "eligible_customer_count": st.column_config.NumberColumn("Customers", format="localized"),
                "mature_customer_count": st.column_config.NumberColumn("Mature (denominator)", format="%d"),
                "repeat_numerator": st.column_config.NumberColumn("Second purchase ≤90 days", format="%d"),
                "conversion_pct": st.column_config.NumberColumn("Conversion %", format="%.1f"),
                "median_days_to_second_purchase_among_mature_repeaters": st.column_config.NumberColumn(
                    "Median days to second purchase", format="%.1f"),
                "maturity": "Follow-up",
            },
        )


def _concentration_section(bundle: dict, head: dict) -> None:
    st.subheader("Revenue concentration")
    table = concentration_table(bundle)
    left, right = st.columns([2, 1])
    chart = (
        alt.Chart(table)
        .mark_bar()
        .encode(
            x=alt.X("share_of_gross:Q", title="Share of identified qualifying gross", axis=alt.Axis(format="%"),
                    scale=alt.Scale(domain=[0, 1])),
            y=alt.Y("group:N", title=None, sort=None, axis=alt.Axis(labelLimit=300)),
            color=alt.Color("group:N", legend=None,
                            scale=alt.Scale(domain=list(table["group"]), range=["#147D83", GRAY])),
            tooltip=[alt.Tooltip("group:N", title="Group"),
                     alt.Tooltip("share_of_gross:Q", title="Share of gross", format=".1%"),
                     alt.Tooltip("qualifying_gross_gbp:Q", title="Qualifying gross (£)", format=",.0f")],
        )
        .properties(height=140)
    )
    left.altair_chart(chart, width="stretch")
    top = table.iloc[0]
    right.markdown(
        f"The top **{int(top['customers']):,}** customers (10%) account for **{top['share_of_gross']:.1%}** "
        f"of identified qualifying gross merchandise ({_money(top['qualifying_gross_gbp'])} of "
        f"{_money(head['qualifying_gross_merchandise_gbp'])})."
    )
    st.caption("Denominator: identified qualifying gross merchandise across the full observation period. Gross merchandise, not net sales or profit; unattributed merchandise is excluded.")


def _cohort_section(bundle: dict, head: dict) -> None:
    st.subheader("Monthly activity after first observed purchase")
    choice = st.radio(
        "Population", options=list(POPULATION_LABELS), format_func=POPULATION_LABELS.get, horizontal=True,
        key="cohort_population",
    )
    table = cohort_table(bundle, choice)
    base = alt.Chart(table).encode(
        x=alt.X("month_index:O", title="Months after first observed month"),
        y=alt.Y("cohort_month:O", title="First-observed month"),
        tooltip=[alt.Tooltip("cohort_month:O", title="Cohort"),
                 alt.Tooltip("month_index:O", title="Months after"),
                 alt.Tooltip("activity_month:O", title="Activity month"),
                 alt.Tooltip("cohort_size:Q", title="Cohort size"),
                 alt.Tooltip("active_customers:Q", title="Active customers"),
                 alt.Tooltip("activity_pct:Q", title="Active %", format=".1f"),
                 alt.Tooltip("status_label:N", title="Status")],
    )
    background = base.mark_rect(color=GRAY)
    observed = base.transform_filter("isValid(datum.activity_pct)").mark_rect().encode(
        color=alt.Color("activity_pct:Q", title="Active %", scale=alt.Scale(scheme="tealblues", domain=[0, 60]))
    )
    st.altair_chart((background + observed).properties(height=max(260, 24 * table["cohort_month"].nunique())),
                    width="stretch")
    suppressed = int((table["cell_status"] == "suppressed_small_cell").sum())
    st.caption(
        "Each cell is the share of a first-observed cohort with at least one qualifying purchase in that calendar "
        f"month. Grey cells are not yet observable (after {head['last_complete_activity_month']}, the last complete "
        "month) or suppressed because fewer than 5 customers were active. Month 0, cohort entry, is 100% by "
        "construction and omitted. First observed is not a verified acquisition date."
        + (f" {suppressed} cell(s) suppressed in this view." if suppressed else "")
    )


def _segment_section(bundle: dict, head: dict) -> None:
    st.subheader("Purchase frequency × recency groups")
    st.caption(
        f"All {head['identified_customers']:,} customers grouped by observed purchase days (one versus repeat) and "
        f"days since last purchase as of the partial data end ({head['source_end_timestamp'][:10]}). Descriptive "
        "groups only: not churn predictions, validated segments or CRM targeting rules."
    )
    table = segment_table(bundle)
    table["group_label"] = table["frequency_label"] + " · " + table["recency_label"]
    left, right = st.columns([3, 2])
    for column, field, title, fmt, show_labels in (
            (left, "share_of_customers", "Share of customers", "%", True),
            (right, "share_of_identified_qualifying_gross", "Share of qualifying gross", "%", False)):
        chart = (
            alt.Chart(table)
            .mark_bar()
            .encode(
                x=alt.X(f"{field}:Q", title=title, axis=alt.Axis(format=fmt), scale=alt.Scale(domain=[0, 1])),
                y=alt.Y("group_label:N", title=None, sort=list(table["group_label"]),
                        axis=alt.Axis(labelLimit=360, labels=show_labels, ticks=show_labels)),
                color=alt.Color("recency_label:N", title="Recency", legend=None,
                                scale=alt.Scale(range=["#31856E", "#D89A2B", "#C65D4B"])),
                tooltip=[alt.Tooltip("frequency_label:N", title="Frequency"),
                         alt.Tooltip("recency_label:N", title="Recency"),
                         alt.Tooltip("customer_count:Q", title="Customers", format=","),
                         alt.Tooltip(f"{field}:Q", title=title, format=".1%")],
            )
            .properties(height=230)
        )
        column.altair_chart(chart, width="stretch")
    st.dataframe(
        table[["frequency_label", "recency_label", "customer_count", "share_of_customers", "qualifying_gross_gbp",
               "share_of_identified_qualifying_gross", "gross_per_customer_gbp"]],
        hide_index=True,
        column_config={
            "frequency_label": "Purchase frequency",
            "recency_label": "Recency",
            "customer_count": st.column_config.NumberColumn("Customers", format="localized"),
            "share_of_customers": st.column_config.NumberColumn("Share of customers", format="percent"),
            "qualifying_gross_gbp": st.column_config.NumberColumn("Qualifying gross (£)", format="localized"),
            "share_of_identified_qualifying_gross": st.column_config.NumberColumn("Share of gross", format="percent"),
            "gross_per_customer_gbp": st.column_config.NumberColumn("Gross per customer (£)", format="localized"),
        },
    )


def _provenance(bundle: dict) -> None:
    with st.expander("Definitions and provenance"):
        prov = bundle["provenance"]
        review = bundle["publication_review"]
        st.markdown(
            "- **Qualifying purchase occasion:** an identified customer × invoice containing positive-quantity, "
            "positive-price merchandise lines under the corrected-V2 taxonomy.\n"
            "- **Qualifying gross merchandise:** quantity × unit price of qualifying lines; not net sales, margin or profit.\n"
            "- **First observed:** earliest observed qualifying purchase; history before December 2009 is unobserved.\n"
            "- **Populations differ by section:** concentration and frequency × recency use all identified customers "
            "over the full period; the 90-day and cohort views are stratified by first-observed month.\n"
            f"- **Source report:** `{prov['reference_report']}`. Bundle `{bundle['bundle_name']}` "
            f"v{bundle['bundle_version']}, content SHA-256 `{bundle['content_sha256'][:12]}…`.\n"
            f"- **Cohort-cell display convention:** {review['suppression_rule']}\n"
            f"- **Bundle content pin:** `{bundle['content_sha256']}` is checked against the approved application value. "
            "This detects content changes relative to that approved bundle; it does not authenticate modified source code."
        )
        st.dataframe(
            pd.DataFrame([{"source aggregate": k, "sha256": v} for k, v in prov["source_aggregate_sha256"].items()]),
            hide_index=True,
        )
