"""Retrospective CRM targeting comparison page."""
from __future__ import annotations

import os
from pathlib import Path
import altair as alt
import pandas as pd
import streamlit as st
from targeting_bundle import BundleError, DEFAULT_BUNDLE_PATH, load_bundle
from targeting_metrics import policy_comparison, pairwise_comparison


def render_targeting_explorer() -> None:
    st.title("CRM Targeting Explorer")
    path=os.environ.get("TARGETING_BUNDLE", str(DEFAULT_BUNDLE_PATH))
    try: bundle=load_bundle(path)
    except BundleError as exc:
        st.error(f"The aggregate targeting bundle could not be loaded, so no results are shown. {exc}")
        st.caption(f"Expected file: {Path(path).name}. Rebuild using `src/targeting_bundle.py` and the frozen M3 aggregate.")
        return
    st.caption("**Evidence type: Retrospective targeting.** Historical purchase capture is not the causal effect of contact.")
    choice=st.radio("Evaluated contact capacity", ["5%", "10%", "20%"], horizontal=True, index=1, key="targeting_capacity")
    capacity=int(choice[:-1])/100
    table=policy_comparison(bundle,capacity)
    st.subheader(f"Policy comparison at {choice} capacity")
    st.caption(f"{bundle['holdout']['snapshots']:,} mature customer-month snapshots; {bundle['holdout']['positive_snapshots']:,} positive outcomes; {bundle['holdout']['unique_customers']:,} distinct customers, July–November 2011. Monthly selected counts use {bundle['holdout']['capacity_rule']}.")
    st.dataframe(table.style.format({"Precision":"{:.2%}","Purchase capture":"{:.2%}","Lift vs random":"{:.2f}×"}), hide_index=True, width="stretch")
    chart=alt.Chart(table).mark_bar().encode(x=alt.X("Policy:N",sort=None),y=alt.Y("Precision:Q",title="Precision among selected snapshots",scale=alt.Scale(domain=[0,1])),color=alt.Color("Policy:N",legend=None),tooltip=["Policy",alt.Tooltip("Selected customer-month snapshots:Q",format=","),alt.Tooltip("Precision:Q",format=".1%"),alt.Tooltip("Purchase capture:Q",format=".1%"),alt.Tooltip("Lift vs random:Q",format=".2f")]).properties(height=250)
    st.altair_chart(chart,width="stretch")
    st.subheader("Model C versus alternatives")
    diffs=pairwise_comparison(bundle,capacity)
    st.dataframe(diffs.style.format({"Difference (percentage points)":"{:+.2f}","95% interval lower":"{:+.2f}","95% interval upper":"{:+.2f}"}),hide_index=True,width="stretch")
    st.caption("Intervals are paired customer-cluster percentile 95% intervals conditional on the frozen holdout and historical tie rule. They are exploratory, not confirmatory; interval overlap is not a hypothesis test. Intervals crossing zero mean this analysis does not distinguish a difference, not that policies are equivalent. Policy-specific intervals were unavailable in the frozen output.")
    overlap=bundle["overlap"][choice[:-1]+"pct"]
    st.subheader("Policy overlap and frequency ties")
    ov=pd.DataFrame([{"Policy":bundle["definitions"]["policy_labels"][p],"Share of Model C selected in common":v["share_of_model_c_selections"],"Jaccard overlap":v["jaccard_of_summed_monthly_sets"]} for p,v in overlap.items() if p in ("rfm","frequency")])
    st.dataframe(ov.style.format({"Share of Model C selected in common":"{:.1%}","Jaccard overlap":"{:.3f}"}),hide_index=True,width="stretch")
    ties=bundle["frequency_tie_sensitivity"]["precision_by_rule"][choice[:-1]+"pct"]
    st.dataframe(pd.DataFrame([{"Frozen deterministic key ascending":ties["customer_key_ascending"],"Uniform random tie expectation":ties["uniform_random_expectation"],"Key descending":ties["customer_key_descending"],"SHA-256 key and month":ties["sha256_key_month"]}]).style.format("{:.2%}"),hide_index=True,width="stretch")
    st.caption("Frequency-rule pooled precision; Model C has no material ties.")
    st.markdown("Model C and frequency select many of the same customer-month snapshots. About 17% of frequency-policy selections at the 10% capacity are affected by tied scores. Across the evaluated capacities, changing the tie rule shifts frequency precision by approximately 0.5–0.7 percentage points, comparable to the Model C minus frequency differences (+1.47 pp at 5%, +0.55 pp at 10%, and +0.69 pp at 20%). Those small point differences are sensitive to tie handling and should not be read as robust; this does not establish equivalence. The frozen deterministic customer-key ascending tie-break remains the primary retrospective evaluation. Alternative tie-breaking results are sensitivity analyses, not replacement estimates. A prospective CRM pilot could prespecify a pseudorandom hash tie-break.")
    st.subheader("Repeated selection across monthly decisions")
    rep=pd.DataFrame([r for r in bundle["repeated_selection"] if r["capacity"]==capacity])
    rep["Policy"]=rep["policy"].map(bundle["definitions"]["policy_labels"])
    rep=rep.rename(columns={"selected_snapshots":"Customer-month selection events","unique_customers":"Distinct customers selected","selected_multiple_months":"Customers selected in multiple months","maximum_months_selected":"Maximum months selected"})
    st.dataframe(rep[["Policy","Customer-month selection events","Distinct customers selected","Customers selected in multiple months","Maximum months selected"]],hide_index=True,width="stretch")
    st.caption("Repeated selection describes retrospective list membership, not repeated actual CRM contact. A campaign would need an approved contact-frequency and suppression policy.")
    st.warning("Scientific limits: this is a retrospective comparison of future purchasing, not randomized treatment response. Better precision does not establish greater incremental CRM value. The simple frequency rule may be operationally attractive despite small, inconclusive differences. M3 does not establish CRM eligibility, consent, contact policies, costs or economics.")
    with st.expander("Definitions and provenance"):
        st.markdown("Policies: **Model C** frozen 11-feature logistic regression; **Model B (RFM)** frozen RFM logistic regression; **365-day frequency** qualifying purchase-date count; **random benchmark** analytical uniform-selection expectation, with no random list drawn. Outcome: any qualifying purchase in the next 30 days.")
        st.markdown(f"Sources: `{bundle['provenance']['source_documents']['results']}` and `{bundle['provenance']['source_documents']['independent_review']}`. Aggregate source SHA-256: `{bundle['provenance']['source_aggregate_sha256']}`. Bundle content SHA-256: `{bundle['content_sha256']}`.")
        st.caption(bundle["definitions"]["bootstrap"]["limitations"])
