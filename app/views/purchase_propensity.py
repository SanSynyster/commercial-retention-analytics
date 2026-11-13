"""Purchase propensity results page for the separate M1 and M2 prediction tasks."""
from __future__ import annotations

import os
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from propensity_summary_bundle import BundleError, DEFAULT_BUNDLE_PATH, load_bundle

BUNDLE_ENV_VAR = "PURCHASE_PROPENSITY_BUNDLE"


@st.cache_data(show_spinner=False)
def _load(path: str) -> dict:
    return load_bundle(path)


def _bundle_path() -> str:
    return os.environ.get(BUNDLE_ENV_VAR, str(DEFAULT_BUNDLE_PATH))


def _pct(value: float) -> str:
    return f"{value:.1%}"


def render() -> None:
    st.title("Purchase Propensity")
    try:
        bundle = _load(_bundle_path())
    except BundleError as exc:
        st.error(f"The aggregate propensity bundle could not be loaded, so no results are shown. {exc}")
        st.caption(f"Expected file: {Path(_bundle_path()).name}. Rebuild with `src/propensity_summary_bundle.py`.")
        return

    st.caption("**Evidence type: Historical prediction.** These results describe purchasing propensity, not the effect of marketing contact.")
    st.warning("M1 and M2 evaluate different customer populations and prediction tasks; their performance estimates are not a head-to-head comparison.")

    _m1_section(bundle["m1"])
    st.divider()
    _m2_section(bundle["m2"])
    st.divider()
    _calibration_section(bundle["m2"], bundle["m2_calibration"])
    _limitations(bundle)


def _m1_section(m1: dict) -> None:
    st.header("M1 · New-customer second-purchase prediction")
    st.markdown(
        "**Question:** among customers in the approved 12-month qualifying-history acquisition proxy, "
        "can first-purchase characteristics rank a second qualifying purchase after a Day-21 decision?"
    )
    st.caption(
        f"Decision: {m1['decision']} Outcome: {m1['outcome']} "
        f"Evaluation unit: {m1['evaluation_unit']}"
    )
    c = m1["models"]["C_three_feature"]
    interval = m1["auc_interval"]
    cols = st.columns(4)
    cols[0].metric("M1 — Model C ROC-AUC", f"{c['roc_auc']:.3f}")
    cols[1].metric("95% customer-bootstrap interval", f"[{interval['lower']:.3f}, {interval['upper']:.3f}]")
    cols[2].metric("Chronological test", f"{m1['test']['customers']:,} customers",
                   help=f"{m1['test']['positive']} positive, {m1['test']['negative']} negative")
    cols[3].metric("Predeclared criterion", "Not met")
    st.warning(
        "The interval spans below and above chance. First-day purchasing features showed limited predictive "
        "evidence in this small evaluation; this is not a successful discrimination result."
    )
    rows = []
    names = {"A_constant": "A · Training-prevalence constant", "B_gross_only": "B · Gross spend only",
             "C_three_feature": "C · Three first-day features"}
    for key, model in m1["models"].items():
        rows.append({"Model": names[key], "ROC-AUC": model["roc_auc"], "Brier score": model["brier_score"]})
    st.dataframe(pd.DataFrame(rows).style.format({"ROC-AUC": "{:.4f}", "Brier score": "{:.4f}"}), hide_index=True, width="stretch")
    st.caption("Average precision is not reported for the M1 logistic models. M1 Model A's capacity ranking is not estimated.")
    with st.expander("M1 population and evaluation"):
        st.markdown(
            f"Training: **{m1['training']['customers']:,} customers** "
            f"({m1['training']['positive']} positive, {m1['training']['negative']} negative; "
            f"{_pct(m1['training']['prevalence'])} positive). Test: **{m1['test']['customers']:,} customers** "
            f"({m1['test']['positive']} positive, {m1['test']['negative']} negative; "
            f"{_pct(m1['test']['prevalence'])} positive). The 95% interval uses {interval['resamples']:,} "
            f"customer bootstrap resamples (seed {interval['seed']})."
        )
        for limitation in m1["limitations"]:
            st.markdown(f"- {limitation}")
        cal = c["calibration"]
        st.caption(f"Corrected Model C calibration diagnostic: intercept {cal['intercept']:.3f}, slope {cal['slope']:.3f} "
                   "(approximate standard errors 0.45 and 0.53; imprecise).")
        st.caption("M1's unit is one customer. Its AUC must not be compared as if it were a controlled head-to-head with M2.")


def _m2_section(m2: dict) -> None:
    st.header("M2 · Established-customer monthly purchase prediction")
    st.markdown("**Question:** can the previous year of customer purchasing behaviour rank any qualifying purchase in the next 30 days?")
    st.caption(f"Decision: {m2['decision']} Outcome: {m2['outcome']} Evaluation unit: {m2['evaluation_unit']}")
    rows = []
    labels = {"A_constant": "A · Constant / random expectation", "B_rfm": "B · RFM logistic", "C_full_11": "C · Full 11-feature logistic"}
    for name, model in m2["models"].items():
        rows.append({"Model": labels[name], "ROC-AUC": model["roc_auc"], "Average precision": model["average_precision"],
                     "Brier score": model["brier_score"], "Top-10% precision": model["precision_10pct"],
                     "Top-10% lift": model["lift_10pct"]})
    st.dataframe(pd.DataFrame(rows).style.format({"ROC-AUC": "{:.3f}", "Average precision": "{:.3f}",
                                                   "Brier score": "{:.4f}", "Top-10% precision": "{:.1%}",
                                                   "Top-10% lift": "{:.2f}×"}), hide_index=True, width="stretch")
    st.caption("Model A has no ranking; its 10% precision and lift are the analytical random-selection expectation, not a selected list.")

    interval = m2["model_c_auc_interval"]
    cols = st.columns(4)
    cols[0].metric("M2 — Model C ROC-AUC", f"{m2['models']['C_full_11']['roc_auc']:.3f}")
    cols[1].metric("95% customer-clustered interval", f"[{interval['lower']:.3f}, {interval['upper']:.3f}]")
    cols[2].metric("Top-decile precision", _pct(m2["models"]["C_full_11"]["precision_10pct"]))
    cols[3].metric("Top-decile lift", f"{m2['models']['C_full_11']['lift_10pct']:.2f}×")

    monthly = pd.DataFrame(m2["monthly"])
    chart_data = monthly.melt(id_vars="month", value_vars=["auc_b", "auc_c"], var_name="model", value_name="value")
    chart_data["model"] = chart_data["model"].map({"auc_b": "B · RFM", "auc_c": "C · Full 11"})
    chart = alt.Chart(chart_data).mark_line(point=True).encode(
        x=alt.X("month:O", title="2011 test decision month", sort=None),
        y=alt.Y("value:Q", title="Monthly ROC-AUC", scale=alt.Scale(domain=[0.4, 1.0])),
        color=alt.Color("model:N", title="Model"), tooltip=["month", "model", alt.Tooltip("value:Q", format=".3f")],
    ).properties(height=240)
    st.altair_chart(chart, width="stretch")
    prevalence_chart = alt.Chart(monthly).mark_bar(color="#147D83").encode(
        x=alt.X("month:O", title="2011 test decision month", sort=None),
        y=alt.Y("prevalence:Q", title="Observed purchase prevalence", axis=alt.Axis(format="%")),
        tooltip=["month", "snapshots", "positive", alt.Tooltip("prevalence:Q", format=".1%")],
    ).properties(height=180)
    st.altair_chart(prevalence_chart, width="stretch")

    st.caption(
        f"Training: {m2['training']['snapshots']:,} customer-month snapshots from {m2['training']['customers']:,} customers; "
        f"test: {m2['test']['snapshots']:,} snapshots from {m2['test']['customers']:,} customers. "
        f"Positive prevalence was {_pct(m2['training']['prevalence'])} in training and {_pct(m2['test']['prevalence'])} in test. "
        f"{m2['customer_overlap']:,} customers appeared in both periods."
    )
    with st.expander("M2 evaluation and model definitions"):
        st.markdown(
            "The chronological training period was January–June 2011; the mature test period was July–November 2011. "
            "Model A predicts training prevalence, Model B uses recency/frequency/monetary predictors, and Model C uses the "
            "verified 11-feature list. Model C's AUC interval resampled test customers with snapshot multiplicity "
            f"({interval['resamples']:,} replicates; {interval['valid']:,} valid, {interval['omitted']} omitted; seed {interval['seed']})."
        )
        for limitation in m2["limitations"]:
            st.markdown(f"- {limitation}")


def _calibration_section(m2: dict, calibration: dict) -> None:
    st.header("Exploratory calibration update")
    st.caption("Same frozen Model C. A sequential intercept-only adjustment uses only labels matured strictly before each target month; model coefficients are not refit.")
    pooled = calibration["pooled"]
    raw, adjusted = pooled["raw"], pooled["adjusted"]
    cols = st.columns(4)
    cols[0].metric("Sep–Nov raw Brier", f"{raw['brier']:.4f}")
    cols[1].metric("Sep–Nov adjusted Brier", f"{adjusted['brier']:.4f}", delta=f"{pooled['brier_difference']:.4f}", delta_color="inverse")
    cols[2].metric("Observed prevalence", _pct(raw["prevalence"]))
    cols[3].metric("Mean predicted · raw → adjusted", f"{_pct(raw['mean_probability'])} → {_pct(adjusted['mean_probability'])}")
    baseline_cal = m2["models"]["C_full_11"]["calibration"]
    adjusted_cal = adjusted["calibration"]
    cal_cols = st.columns(2)
    cal_cols[0].metric("Baseline C calibration (Jul–Nov)", f"{baseline_cal['intercept']:.3f} / {baseline_cal['slope']:.3f}",
                       help="Diagnostic logistic calibration intercept / slope on the original full test predictions.")
    cal_cols[1].metric("Sequential adjusted pooled diagnostic (Sep–Nov)",
                       f"{adjusted_cal['intercept']:.3f} / {adjusted_cal['slope']:.3f}",
                       help="Exploratory joint calibration intercept / slope; stationary optimum after optimizer warning.")
    st.caption("These intercept/slope estimates cover different months and are not a before/after comparison. The raw September–November pooled diagnostic was not estimable.")
    st.caption(
        f"Brier difference adjusted − raw: {pooled['brier_difference']:.5f}; customer-clustered 95% interval "
        f"[{pooled['brier_ci'][0]:.5f}, {pooled['brier_ci'][1]:.5f}]. Risk-scale underprediction gap changed "
        f"from {raw['risk_gap']:.1%} to {adjusted['risk_gap']:.1%}. This exploratory interval is conditional on the same, previously examined holdout."
    )
    monthly = pd.DataFrame(calibration["monthly"])
    calibrated = monthly[monthly["month"].isin(["2011-09", "2011-10", "2011-11"])].copy()
    selected = st.selectbox("Calibration view", ["Brier score", "Mean prediction vs prevalence"], key="propensity_calibration_view")
    if selected == "Brier score":
        chart_data = calibrated.melt(id_vars="month", value_vars=["raw_brier", "adjusted_brier"], var_name="series", value_name="value")
        chart_data["series"] = chart_data["series"].map({"raw_brier": "Raw", "adjusted_brier": "Sequential intercept-adjusted"})
        chart = alt.Chart(chart_data).mark_line(point=True).encode(x=alt.X("month:O", title="Target month", sort=None),
            y=alt.Y("value:Q", title="Brier score; lower is better"), color="series:N", tooltip=["month", "series", alt.Tooltip("value:Q", format=".4f")]).properties(height=220)
    else:
        chart_data = calibrated.melt(id_vars="month", value_vars=["raw_mean_probability", "adjusted_mean_probability", "prevalence"], var_name="series", value_name="value")
        chart_data["series"] = chart_data["series"].map({"raw_mean_probability": "Raw mean prediction", "adjusted_mean_probability": "Adjusted mean prediction", "prevalence": "Observed prevalence"})
        chart = alt.Chart(chart_data).mark_line(point=True).encode(x=alt.X("month:O", title="Target month", sort=None),
            y=alt.Y("value:Q", title="Probability", axis=alt.Axis(format="%")), color="series:N", tooltip=["month", "series", alt.Tooltip("value:Q", format=".1%")]).properties(height=220)
    st.altair_chart(chart, width="stretch")
    pools = pd.DataFrame(calibration["pools"])
    pools = pools.rename(columns={"target_month": "Target month", "snapshots": "Mature calibration snapshots", "customers": "Customers",
                                  "positive": "Positive", "negative": "Negative", "prevalence": "Pool prevalence",
                                  "maturity_as_of": "Latest included maturity", "delta": "Fitted intercept offset"})
    st.dataframe(pools, hide_index=True, width="stretch", column_config={
        "Pool prevalence": st.column_config.NumberColumn(format="percent"),
        "Fitted intercept offset": st.column_config.NumberColumn(format="%.3f"),
    })
    with st.expander("Calibration method and limitations"):
        st.markdown(calibration["method"] + " " + calibration["pool_rule"])
        for limitation in calibration["limitations"]:
            st.markdown(f"- {limitation}")
        st.caption("The adjustment modestly improved probability scores in these months; it is not prospective validation and does not change within-month customer ranking.")


def _limitations(bundle: dict) -> None:
    with st.expander("Scientific interpretation and sources"):
        st.warning("M1 and M2 are different research tasks, populations, outcomes, evaluation units and sample sizes. Their AUCs are not a controlled head-to-head comparison.")
        st.markdown(
            "M2 is a short historical chronological holdout with repeated customer snapshots and rising seasonal prevalence. "
            "Model C underpredicted the test purchase rate. Calibration is exploratory on the same previously examined holdout. "
            "Neither propensity ranking nor calibration estimates the incremental effect of CRM contact."
        )
        docs = bundle["provenance"]["source_documents"]
        st.markdown("**Verified research sources:** " + ", ".join(f"`{path}`" for path in docs.values()))
        st.markdown(f"Bundle content SHA-256: `{bundle['content_sha256']}`")
