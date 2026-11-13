"""Hypothetical CRM pilot planning page using the frozen M4 calculator."""
from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from experiment_feasibility_metrics import build_scenario, effect_mde_interpretation, sensitivity_table


CAPACITY_OPTIONS = (0.10, 0.20, 0.50, 1.00)
SD_OPTIONS = (20.0, 50.0, 100.0, 200.0)
COST_OPTIONS = (0.01, 0.05, 0.20, 1.00)
# Include the default £0.20 send cost as an explicit break-even gross value.
GROSS_OPTIONS = (0.0, 0.10, 0.20, 0.50, 1.0, 2.0, 5.0)


def _gbp(value: float) -> str:
    return f"£{value:,.2f}"


def render() -> None:
    st.title("CRM Experiment Feasibility")
    st.caption("**Evidence type: Hypothetical scenario.** No CRM experiment has been launched and no causal uplift has been measured.")
    st.markdown(
        "**Proposed design:** one enrollment wave among established customers who meet current CRM eligibility rules; "
        "select the top 10% by 365-day qualifying purchase-date frequency; randomize persistently at customer level 1:1; "
        "send one non-discount study email to treatment and no study email to control. Both arms otherwise receive "
        "comparable business-as-usual treatment. Primary outcome: 30-day net customer contribution margin; primary "
        "analysis: intention-to-treat difference in mean outcome between assigned arms."
    )

    st.subheader("Hypothetical scenario inputs")
    st.caption("All numerical values below are planning assumptions, not observed CRM or finance data. The primary M4 design uses 10% total enrollment; other capacities are sensitivity scenarios.")
    input_cols = st.columns(3)
    eligible = input_cols[0].number_input(
        "Eligible customers (assumed)", min_value=100, max_value=1_000_000,
        value=10_000, step=100, key="experiment_eligible_customers",
        help="Hypothetical unique customers after actual eligibility, consent, contactability and suppression checks.",
    )
    capacity = input_cols[1].selectbox(
        "Enrollment capacity (assumed)", CAPACITY_OPTIONS, index=0,
        format_func=lambda x: f"{x:.0%}", key="experiment_capacity",
        help="Capacity is the share enrolled across both arms, including controls. M4's primary design is 10%.",
    )
    outcome_sd = input_cols[2].selectbox(
        "30-day outcome SD (assumed)", SD_OPTIONS, index=1,
        format_func=lambda x: _gbp(x), key="experiment_outcome_sd",
        help="Hypothetical customer-level standard deviation of 30-day net contribution margin.",
    )
    economics_inputs = st.columns(2)
    gross_increment = economics_inputs[0].selectbox(
        "Gross increment per treatment assignment (assumed)", GROSS_OPTIONS, index=4,
        format_func=lambda x: _gbp(x), key="experiment_gross_increment",
        help="Hypothetical incremental gross contribution per treatment assignment before the study email cost; not an estimated treatment effect.",
    )
    contact_cost = economics_inputs[1].selectbox(
        "Email cost per treatment assignment (assumed)", COST_OPTIONS, index=2,
        format_func=lambda x: _gbp(x), key="experiment_contact_cost",
        help="Hypothetical variable cost charged once to every treatment assignment, following M4 arithmetic.",
    )

    scenario = build_scenario(int(eligible), capacity, outcome_sd, gross_increment, contact_cost)
    allocation = scenario["allocation"]
    economics = scenario["economics"]
    st.subheader("Enrollment and 1:1 allocation")
    st.caption("M4 convention: enrollment is ceil(eligible customers × capacity). For scenario arithmetic, treatment receives an odd extra assignment; a real trial must allocate through its prespecified randomization procedure.")
    alloc_cols = st.columns(5)
    alloc_cols[0].metric("Eligible customers", f"{allocation['eligible_customers']:,}")
    alloc_cols[1].metric("Enrollment capacity", f"{capacity:.0%}")
    alloc_cols[2].metric("Enrolled customers", f"{allocation['enrolled_customers']:,}")
    alloc_cols[3].metric("Treatment assignments", f"{allocation['treatment_customers']:,}", help="One study email is assigned per treatment customer; controls do not receive the study email.")
    alloc_cols[4].metric("Control assignments", f"{allocation['control_customers']:,}")
    st.info("Controls count toward enrollment capacity. At 10% enrollment and 1:1 assignment, about 5% of the eligible base is assigned the study email.")

    st.subheader("Statistical feasibility")
    mde = scenario["mde_gbp_per_randomized_customer"]
    net_itt_effect = economics["net_incremental_contribution_gbp_per_treatment_assignment"]
    stats_cols = st.columns(4)
    stats_cols[0].metric("Approximate MDE for treatment − control mean net margin", _gbp(mde), help="Per randomized customer; a normal-approximation planning value, not expected campaign uplift.")
    stats_cols[1].metric("Assumed outcome SD", _gbp(outcome_sd))
    stats_cols[2].metric("Hypothetical net ITT effect", _gbp(net_itt_effect), help="Treatment − control mean contribution margin under the assumed gross increment and contact cost; this is not the cohort-average contribution.")
    stats_cols[3].metric("Planning assumptions", "80% power · α = 0.05", help="Two-sided significance level; independent-arm normal approximation with the M4 1:1 allocation convention.")
    st.caption("MDE is the approximate treatment − control difference in mean net margin per randomized customer detectable at the stated power and significance assumptions. It is not an expected campaign effect or a promise of exact power.")
    assessment = effect_mde_interpretation(net_itt_effect, mde, scenario["statistical_comparison"])
    if assessment["meets_mde"]:
        st.info(assessment["message"])
    else:
        st.warning(assessment["message"])

    st.subheader("Hypothetical economics")
    econ_cols = st.columns(4)
    econ_cols[0].metric("Gross increment per treatment assignment", _gbp(gross_increment))
    econ_cols[1].metric("Contact cost per treatment assignment", _gbp(contact_cost))
    econ_cols[2].metric("Total incremental campaign contribution", _gbp(economics["total_expected_net_incremental_contribution_gbp"]))
    econ_cols[3].metric("Break-even gross increment", _gbp(economics["break_even_gross_contribution_gbp_per_treatment_assignment"]))
    st.caption(f"Average hypothetical net contribution per enrolled customer: **{_gbp(economics['net_incremental_contribution_gbp_per_enrolled_customer'])}**. This differs from the net ITT arm-mean contrast because control customers count in the randomized cohort but are not assigned the study email. M4 charges one send cost to each treatment assignment.")

    st.subheader("Enrollment-capacity sensitivity")
    st.caption(f"MDE recalculated with the selected eligible population ({eligible:,}) and assumed SD ({_gbp(outcome_sd)}), using the existing M4 formula.")
    sensitivity = sensitivity_table(scenario)
    chart_data = sensitivity.rename(columns={
        "Enrollment capacity": "capacity", "Approximate MDE (£ per randomized customer)": "mde",
        "Enrolled customers": "enrolled", "Treatment assignments": "treatment", "Control assignments": "control",
    })
    chart = alt.Chart(chart_data).mark_line(point=True).encode(
        x=alt.X("capacity:Q", title="Enrollment capacity (both arms)", axis=alt.Axis(format="%"), scale=alt.Scale(domain=[0.1, 1.0])),
        y=alt.Y("mde:Q", title="Approximate MDE (£ per randomized customer)", scale=alt.Scale(zero=True)),
        tooltip=[alt.Tooltip("capacity:Q", format=".0%"), alt.Tooltip("enrolled:Q", format=","),
                 alt.Tooltip("treatment:Q", format=","), alt.Tooltip("control:Q", format=","), alt.Tooltip("mde:Q", title="Approximate MDE", format="£.2f")],
    ).properties(height=260)
    st.altair_chart(chart, width="stretch")
    st.dataframe(sensitivity.style.format({
        "Enrollment capacity": "{:.0%}",
        "Approximate MDE (£ per randomized customer)": "£{:.2f}",
        "Enrolled customers": "{:,.0f}", "Treatment assignments": "{:,.0f}", "Control assignments": "{:,.0f}",
    }), hide_index=True, width="stretch")
    st.caption("Higher enrollment generally lowers the MDE under this formula, but capacity changes the frequency-ranked population and potentially the estimand. Sensitivity points are analytical scenarios, not historical performance extrapolations.")

    st.warning(
        "Scientific and operational limits: no causal CRM uplift has been measured. This calculator is hypothetical. "
        "Actual eligibility, consent, contribution margins, costs and contact rules remain unknown. Changing enrollment "
        "capacity changes the selected population and potentially the estimand; the primary M4 design is 10% enrollment. "
        "Contact displacement and comparable business-as-usual treatment need operational decisions. Power calculations "
        "depend on assumed outcome variability and normal-approximation assumptions; skew, unequal variance, clustering "
        "and incomplete finance linkage may affect real precision."
    )
    with st.expander("Design definitions and readiness questions"):
        st.markdown(
            "The proposed pilot is one wave among established, contact-eligible customers with a complete 365-day "
            "history and at least one qualifying purchase. Rank by 365-day qualifying purchase-date frequency, "
            "prespecify an outcome-independent deterministic hash tie-break, and select the top 10% before randomization. "
            "Assignment is persistent at customer level and defines intention-to-treat, regardless of delivery or engagement. "
            "The primary outcome is 30-day net customer contribution margin with finance-approved treatment of discounts, "
            "refunds, COGS, variable fulfilment/payment costs and settlement lag."
        )
        st.markdown(
            "Before any launch, the CRM/finance owners must establish current eligibility and consent, contact suppression "
            "rules, the randomization unit, contact displacement and business-as-usual comparability, actual margin and "
            "cost definitions, outcome maturity, a minimum worthwhile ITT effect, budget and harm guardrails."
        )
        st.caption("M4 methods reused: `allocate_enrollment`, `mean_difference_mde`, `commercial_scenarios`, and `capacity_sensitivity` in `src/crm_pilot_feasibility.py`.")
