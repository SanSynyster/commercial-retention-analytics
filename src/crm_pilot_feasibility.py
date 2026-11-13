"""Transparent scenario calculations for the proposed randomized CRM pilot.

All monetary and variance inputs are hypothetical unless supplied by the
business. The module does not load customer records or estimate treatment
effects from historical data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
from pathlib import Path
from statistics import NormalDist
from typing import Iterable

import numpy as np
import pandas as pd


DEFAULT_POPULATIONS = (1_000, 2_500, 5_000, 10_000, 25_000, 50_000)
DEFAULT_STANDARD_DEVIATIONS = (20.0, 50.0, 100.0, 200.0)
DEFAULT_CONTACT_COSTS = (0.01, 0.05, 0.20, 1.00)
DEFAULT_GROSS_CONTRIBUTIONS = (0.0, 0.10, 0.50, 1.0, 2.0, 5.0)
DEFAULT_CAPACITIES = (0.10, 0.20, 0.50, 1.0)


def _validate_population(population: int) -> int:
    if isinstance(population, bool) or int(population) != population or population < 1:
        raise ValueError("population must be a positive integer")
    return int(population)


def _validate_capacity(capacity: float) -> float:
    capacity = float(capacity)
    if not math.isfinite(capacity) or not 0 < capacity <= 1:
        raise ValueError("capacity must be in (0, 1]")
    return capacity


def allocate_enrollment(population: int, capacity: float = 0.10) -> dict[str, int | float]:
    """Apply ceil capacity; for odd enrollment, treatment receives the extra.

    This deterministic allocation is only for scenario arithmetic. A real
    trial randomizes individuals 1:1, so which arm receives an odd extra must
    be determined by the prespecified randomization procedure.
    """
    population = _validate_population(population)
    capacity = _validate_capacity(capacity)
    enrolled = min(population, math.ceil(population * capacity))
    treatment = (enrolled + 1) // 2
    control = enrolled // 2
    return {
        "eligible_customers": population,
        "capacity": capacity,
        "enrolled_customers": enrolled,
        "treatment_customers": treatment,
        "control_customers": control,
        "not_enrolled_customers": population - enrolled,
        "enrollment_fraction": enrolled / population,
        "treatment_fraction_eligible": treatment / population,
    }


def mean_difference_mde(
    n_treatment: int,
    n_control: int,
    outcome_sd: float,
    *,
    alpha: float = 0.05,
    power: float = 0.80,
) -> float:
    """Normal-approximation MDE for a two-sided independent-arm mean contrast."""
    if isinstance(n_treatment, bool) or int(n_treatment) != n_treatment or n_treatment < 1:
        raise ValueError("n_treatment must be a positive integer")
    if isinstance(n_control, bool) or int(n_control) != n_control or n_control < 1:
        raise ValueError("n_control must be a positive integer")
    outcome_sd = float(outcome_sd)
    alpha = float(alpha)
    power = float(power)
    if not math.isfinite(outcome_sd) or outcome_sd <= 0:
        raise ValueError("outcome_sd must be finite and positive")
    if not 0 < alpha < 1:
        raise ValueError("alpha must be in (0, 1)")
    if not 0.5 < power < 1:
        raise ValueError("power must be in (0.5, 1)")
    normal = NormalDist()
    z_alpha = normal.inv_cdf(1 - alpha / 2)
    z_power = normal.inv_cdf(power)
    return (z_alpha + z_power) * outcome_sd * math.sqrt(1 / n_treatment + 1 / n_control)


def sample_size_scenarios(
    populations: Iterable[int] = DEFAULT_POPULATIONS,
    standard_deviations: Iterable[float] = DEFAULT_STANDARD_DEVIATIONS,
    *,
    capacity: float = 0.10,
    alpha: float = 0.05,
    power: float = 0.80,
) -> pd.DataFrame:
    """Return one row per eligible population and hypothetical outcome SD."""
    rows: list[dict[str, int | float]] = []
    for population in populations:
        allocation = allocate_enrollment(population, capacity)
        for sd in standard_deviations:
            rows.append({
                **allocation,
                "outcome_sd_gbp": float(sd),
                "alpha": float(alpha),
                "power": float(power),
                "mde_gbp_per_randomized_customer": mean_difference_mde(
                    int(allocation["treatment_customers"]),
                    int(allocation["control_customers"]),
                    float(sd), alpha=alpha, power=power,
                ),
            })
    return pd.DataFrame(rows)


def commercial_scenarios(
    populations: Iterable[int] = DEFAULT_POPULATIONS,
    contact_costs: Iterable[float] = DEFAULT_CONTACT_COSTS,
    gross_contributions: Iterable[float] = DEFAULT_GROSS_CONTRIBUTIONS,
    *,
    capacity: float = 0.10,
) -> pd.DataFrame:
    """Calculate hypothetical net ITT value, charging each treatment assignment.

    ``gross_contribution`` means hypothetical incremental gross contribution
    per treatment-assigned customer before experimental send cost. It is an
    ITT scenario input, not a delivered-only effect.
    """
    rows: list[dict[str, int | float | bool]] = []
    for population in populations:
        allocation = allocate_enrollment(population, capacity)
        n_treatment = int(allocation["treatment_customers"])
        n_enrolled = int(allocation["enrolled_customers"])
        for contact_cost in contact_costs:
            contact_cost = float(contact_cost)
            if not math.isfinite(contact_cost) or contact_cost < 0:
                raise ValueError("contact costs must be finite and nonnegative")
            for gross in gross_contributions:
                gross = float(gross)
                if not math.isfinite(gross):
                    raise ValueError("gross contributions must be finite")
                net_per_treatment_assignment = gross - contact_cost
                total_contact_cost = n_treatment * contact_cost
                total_net_increment = n_treatment * net_per_treatment_assignment
                rows.append({
                    **allocation,
                    "contact_cost_gbp_per_treatment_assignment": contact_cost,
                    "incremental_gross_contribution_gbp_per_treatment_assignment": gross,
                    "net_incremental_contribution_gbp_per_treatment_assignment": net_per_treatment_assignment,
                    "expected_contact_cost_gbp": total_contact_cost,
                    "total_expected_net_incremental_contribution_gbp": total_net_increment,
                    "net_incremental_contribution_gbp_per_enrolled_customer": total_net_increment / n_enrolled,
                    "break_even_gross_contribution_gbp_per_treatment_assignment": contact_cost,
                    "positive_expected_net_contribution": net_per_treatment_assignment > 0,
                })
    return pd.DataFrame(rows)


def statistical_commercial_comparison(
    populations: Iterable[int] = DEFAULT_POPULATIONS,
    standard_deviations: Iterable[float] = DEFAULT_STANDARD_DEVIATIONS,
    contact_costs: Iterable[float] = DEFAULT_CONTACT_COSTS,
    gross_contributions: Iterable[float] = DEFAULT_GROSS_CONTRIBUTIONS,
    *,
    capacity: float = 0.10,
    alpha: float = 0.05,
    power: float = 0.80,
) -> pd.DataFrame:
    """Compare hypothetical net effects with approximate 80%-power MDEs."""
    rows: list[dict[str, int | float | bool]] = []
    for population in populations:
        allocation = allocate_enrollment(population, capacity)
        n_treatment = int(allocation["treatment_customers"])
        n_control = int(allocation["control_customers"])
        for sd in standard_deviations:
            mde = mean_difference_mde(n_treatment, n_control, float(sd), alpha=alpha, power=power)
            for cost in contact_costs:
                for gross in gross_contributions:
                    net_effect = float(gross) - float(cost)
                    rows.append({
                        **allocation,
                        "outcome_sd_gbp": float(sd),
                        "contact_cost_gbp_per_treatment_assignment": float(cost),
                        "incremental_gross_contribution_gbp_per_treatment_assignment": float(gross),
                        "net_itt_effect_gbp_per_randomized_customer": net_effect,
                        "mde_gbp_per_randomized_customer": mde,
                        "positive_expected_net_contribution": net_effect > 0,
                        "net_effect_at_or_above_approx_80pct_power_mde": net_effect >= mde,
                    })
    return pd.DataFrame(rows)


def capacity_sensitivity(
    populations: Iterable[int] = (5_000, 10_000, 25_000),
    capacities: Iterable[float] = DEFAULT_CAPACITIES,
    standard_deviations: Iterable[float] = (50.0, 100.0),
    *,
    alpha: float = 0.05,
    power: float = 0.80,
) -> pd.DataFrame:
    """Return allocation and MDE by enrollment capacity and population."""
    rows: list[dict[str, int | float]] = []
    for population in populations:
        for capacity in capacities:
            allocation = allocate_enrollment(population, capacity)
            for sd in standard_deviations:
                rows.append({
                    **allocation,
                    "outcome_sd_gbp": float(sd),
                    "mde_gbp_per_randomized_customer": mean_difference_mde(
                        int(allocation["treatment_customers"]),
                        int(allocation["control_customers"]),
                        float(sd), alpha=alpha, power=power,
                    ),
                })
    return pd.DataFrame(rows)


def variance_reduction_scenarios(
    reference_mde: float,
    r_squared_values: Iterable[float] = (0.0, 0.25, 0.50),
) -> pd.DataFrame:
    """Illustrate ANCOVA MDE scaling under hypothetical baseline R-squared."""
    reference_mde = float(reference_mde)
    if not math.isfinite(reference_mde) or reference_mde <= 0:
        raise ValueError("reference_mde must be finite and positive")
    rows = []
    for r_squared in r_squared_values:
        r_squared = float(r_squared)
        if not 0 <= r_squared < 1:
            raise ValueError("r_squared values must be in [0, 1)")
        variance_ratio = 1 - r_squared
        rows.append({
            "hypothetical_baseline_r_squared": r_squared,
            "adjusted_variance_ratio": variance_ratio,
            "adjusted_mde_gbp": reference_mde * math.sqrt(variance_ratio),
        })
    return pd.DataFrame(rows)


def write_scenario_outputs(output_dir: str | Path) -> dict[str, str]:
    """Write reproducible aggregate scenario CSVs and a small manifest."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    tables = {
        "sample_size_scenarios.csv": sample_size_scenarios(),
        "commercial_scenarios.csv": commercial_scenarios(),
        "statistical_commercial_comparison.csv": statistical_commercial_comparison(),
        "capacity_sensitivity.csv": capacity_sensitivity(),
    }
    hashes: dict[str, str] = {}
    for filename, frame in tables.items():
        path = output_dir / filename
        frame.to_csv(path, index=False, float_format="%.10g", lineterminator="\n")
        hashes[filename] = hashlib.sha256(path.read_bytes()).hexdigest()
    source_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    manifest = {
        "analysis": "M4-002 illustrative CRM pilot feasibility scenarios",
        "module_sha256": source_hash,
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "pandas_version": pd.__version__,
        "assumptions": {
            "capacity_rounding": "ceil eligible population times capacity",
            "odd_enrollment_allocation": "treatment receives the extra customer",
            "allocation": "approximately equal treatment/control",
            "alpha_two_sided": 0.05,
            "power": 0.80,
            "contact_cost": "one variable send cost charged to every treatment assignment",
            "treatment_effect": "hypothetical incremental gross contribution per treatment assignment before send cost",
            "data_based_effect_or_variance_estimated": False,
        },
        "outputs_sha256": hashes,
    }
    manifest_path = output_dir / "m4_002_scenario_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    hashes[manifest_path.name] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    return hashes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, help="External directory for aggregate scenario CSVs")
    args = parser.parse_args()
    hashes = write_scenario_outputs(args.output_dir)
    print(json.dumps({"output_dir": str(Path(args.output_dir).resolve()), "sha256": hashes}, indent=2))


if __name__ == "__main__":
    main()
