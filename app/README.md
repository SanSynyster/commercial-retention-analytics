# Customer Intelligence & Decision Support

A local Streamlit application presenting four research and planning views built from corrected Online Retail II analysis. Historical pages describe or predict purchasing in the 2009–2011 data; they do not show current CRM customers or estimate the effect of marketing contact. The experiment page is a hypothetical calculator, not a launched campaign.

## Pages

- **Customer Overview** — corrected-V2 purchasing, mature 90-day follow-up, revenue concentration, cohort activity and descriptive frequency/recency groups.
- **Purchase Propensity** — separate M1 new-customer and M2 established-customer prediction results, plus exploratory calibration. M1 and M2 are different tasks; calibration reuses a previously examined holdout.
- **CRM Targeting Explorer** — retrospective purchase capture for four policies at the evaluated 5%, 10% and 20% capacities. Purchase propensity is not causal CRM uplift.
- **CRM Experiment Feasibility** — hypothetical enrollment, allocation, MDE and economics for the proposed M4 randomized pilot. No treatment effect or business input is estimated from the historical data.

## Install and launch

Use Python 3.11 from the repository root:

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements-app.txt
.venv/bin/streamlit run app/streamlit_app.py
```

The app runs locally and makes no network or database calls.

## Data and evidence limits

The three historical pages read only the reviewed aggregate JSON bundles in `app_data/`. The feasibility page calculates in memory using the M4 scenario functions. The app does not require raw transactions, customer-level records, prediction rows, targeting lists or model binaries.

The underlying retail data are observational and historical, with a partial source endpoint in December 2011. First observed purchase is not verified acquisition; gross merchandise is not net sales, margin or profit; and descriptive groups are not validated CRM segments. Prediction and retrospective targeting metrics measure purchasing patterns, not treatment response. Actual eligibility, consent, contact rules, margin variance and costs are not established. See the root [project README](../README.md) and [data provenance and attribution](../docs/DATA_PROVENANCE.md) for research definitions and source terms.

## Tests

Run the focused application and M4 tests:

```sh
.venv/bin/python -m unittest \
  tests.test_customer_overview_bundle \
  tests.test_dashboard_app \
  tests.test_propensity_summary_bundle \
  tests.test_purchase_propensity_page \
  tests.test_targeting_bundle \
  tests.test_experiment_feasibility_page \
  tests.test_crm_pilot_feasibility
```

Run the full repository suite:

```sh
.venv/bin/python -m unittest discover -s tests
```

Some research-input rebuild tests skip when the external source aggregates are unavailable. They are not needed to run the app or its page tests.

## Aggregate bundles and provenance

The three historical bundles were generated from approved corrected-V2 and M1–M3 research outputs and reviewed aggregate sources; the hypothetical M4 page calculates scenarios in memory. Each bundle loader independently pins the approved content hash and validates schema and provenance. This detects content changes relative to the approved version; it is not a cryptographic authenticity guarantee if both code and pin are changed. The application reads aggregate JSON only. Rebuilding the bundles requires source aggregates, manifests and (for some analyses) prediction or calibration inputs that are not distributed in this release.
