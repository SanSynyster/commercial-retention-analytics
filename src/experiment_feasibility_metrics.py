"""Presentation-ready scenario values built only from the frozen M4 calculator."""
from __future__ import annotations

from typing import Any

import pandas as pd

try:  # Support both `src.*` imports in tests and app-root source-path imports.
    from .crm_pilot_feasibility import (
        DEFAULT_CAPACITIES, allocate_enrollment, capacity_sensitivity,
        commercial_scenarios, mean_difference_mde, statistical_commercial_comparison,
    )
except ImportError:  # pragma: no cover - exercised by Streamlit's source path.
    from crm_pilot_feasibility import (
        DEFAULT_CAPACITIES, allocate_enrollment, capacity_sensitivity,
        commercial_scenarios, mean_difference_mde, statistical_commercial_comparison,
    )


def build_scenario(
    eligible_customers: int,
    capacity: float,
    outcome_sd_gbp: float,
    gross_increment_gbp: float,
    contact_cost_gbp: float,
) -> dict[str, Any]:
    """Return allocation, MDE, economics and capacity sensitivity for one scenario."""
    allocation = allocate_enrollment(eligible_customers, capacity)
    mde = mean_difference_mde(
        int(allocation["treatment_customers"]),
        int(allocation["control_customers"]),
        outcome_sd_gbp,
        alpha=0.05,
        power=0.80,
    )
    economics = commercial_scenarios(
        [eligible_customers], [contact_cost_gbp], [gross_increment_gbp], capacity=capacity
    ).iloc[0].to_dict()
    sensitivity = capacity_sensitivity(
        populations=[eligible_customers],
        capacities=DEFAULT_CAPACITIES,
        standard_deviations=[outcome_sd_gbp],
        alpha=0.05,
        power=0.80,
    )
    statistical_comparison = statistical_commercial_comparison(
        [eligible_customers], [outcome_sd_gbp], [contact_cost_gbp],
        [gross_increment_gbp], capacity=capacity, alpha=0.05, power=0.80,
    ).iloc[0].to_dict()
    return {
        "allocation": allocation,
        "mde_gbp_per_randomized_customer": mde,
        "economics": economics,
        "capacity_sensitivity": sensitivity,
        "statistical_comparison": statistical_comparison,
    }


def effect_mde_interpretation(net_itt_effect_gbp: float, mde_gbp: float, m4_comparison: dict[str, Any]) -> dict[str, Any]:
    """Interpret an assumed arm-mean ITT effect relative to the frozen M4 MDE.

    For a nonnegative effect, use M4's existing `g-c >= MDE` comparison flag.
    For a negative effect, compare absolute magnitude as required for a
    two-sided test; the M4 flag itself is one-sided for this display purpose.
    """
    magnitude = abs(net_itt_effect_gbp)
    meets_mde = (
        bool(m4_comparison["net_effect_at_or_above_approx_80pct_power_mde"])
        if net_itt_effect_gbp >= 0 else magnitude >= mde_gbp
    )
    mde_text = f"£{mde_gbp:,.2f}"
    if meets_mde:
        if net_itt_effect_gbp < 0:
            message = (
                f"The assumed net ITT effect is negative (−£{magnitude:,.2f}), but its absolute magnitude meets or exceeds "
                f"the approximate {mde_text} MDE under the stated assumptions. Statistical significance is not guaranteed."
            )
        else:
            message = (
                f"The assumed £{magnitude:,.2f} net ITT effect meets or exceeds the approximate {mde_text} MDE under the "
                "stated assumptions. Statistical significance is not guaranteed."
            )
    elif net_itt_effect_gbp < 0:
        message = (
            f"The assumed net ITT effect is negative (−£{magnitude:,.2f}); its absolute magnitude is below the approximate "
            f"{mde_text} MDE. This proposed sample is not designed to provide 80% power to detect an effect of that magnitude."
        )
    else:
        message = (
            f"The assumed £{magnitude:,.2f} net ITT effect is below the approximate {mde_text} MDE, so this proposed sample "
            "is not designed to provide 80% power to detect an effect of that magnitude. A positive hypothetical campaign "
            "contribution does not mean this experiment has adequate power to detect that effect."
        )
    return {"meets_mde": meets_mde, "absolute_effect_gbp": magnitude, "message": message}


def sensitivity_table(scenario: dict[str, Any]) -> pd.DataFrame:
    """Select and label the M4 approved capacity-sensitivity measures."""
    frame = scenario["capacity_sensitivity"]
    return frame[[
        "capacity", "enrolled_customers", "treatment_customers", "control_customers",
        "mde_gbp_per_randomized_customer",
    ]].rename(columns={
        "capacity": "Enrollment capacity",
        "enrolled_customers": "Enrolled customers",
        "treatment_customers": "Treatment assignments",
        "control_customers": "Control assignments",
        "mde_gbp_per_randomized_customer": "Approximate MDE (£ per randomized customer)",
    })
