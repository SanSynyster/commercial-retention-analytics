# M4-002 — CRM Pilot Feasibility and Scenario Analysis

## Executive summary

Under the proposed top-10% enrollment design, an eligible base of 10,000 unique customers yields 1,000 randomized customers (500 per arm); only about 5% of the eligible base receives the study email. With hypothetical 30-day contribution-margin SD £50, the approximate 80%-power MDE is £8.86 per randomized customer. At SD £100 it is £17.72. These detectable effects are large relative to most illustrative gross contribution scenarios (£0–£5 before contact cost).

The pilot can be commercially positive at small effects when incremental gross contribution exceeds send cost, but a positive expected value is not the same as adequate power or evidence for rollout. Under the tested grid, small eligible bases are underpowered for all listed £0–£5 effects at most assumed margin SDs. Actual feasibility cannot be determined without current contactable population size, policy-matched outcome variance, a business minimum worthwhile effect and finance-approved margin data.

All calculations below are transparent planning scenarios. No historical treatment effect, customer margin distribution, deliverability rate or eligibility count was estimated. Scenario outputs are reproducible and kept outside Git.

## Pilot specification carried forward from M4-001

The evaluated design is one enrollment wave of established, contact-eligible customers with a complete 365-day history and at least one qualifying purchase in `[T − 365 days, T)`. At the month-start decision timestamp `T`, rank by `qualifying_purchase_dates_365d`, break ties with a prespecified deterministic pseudorandom key, and select the top 10%. Randomize selected unique customers 1:1, persist assignment, send one non-discount study email to treatment, and withhold only the study email from control while comparable business-as-usual communications continue.

The primary endpoint is the ITT difference in 30-day net customer contribution margin. Purchase outcomes use `[assignment_time, assignment_time + 30 days)`. The provisional extra 30-day financial-adjustment lag is an assumption, not a verified return-window rule; finance must confirm it. The 10% cohort includes controls, so treatment sends are approximately 5% of the eligible base. If 10% instead means send capacity, the enrollment denominator must change before the experiment is designed.

The M2/M3 history consists of customer-month snapshots, including repeated customers; it is not a set of independent experimental customers. All sample calculations here count unique eligible customers once in a single pilot wave.

## Sample-size feasibility at 10% enrollment

Capacity uses `ceil(0.10 × eligible customers)`. Treatment receives the extra customer when the enrollment count is odd; this convention only makes scenario tables deterministic. A live assignment should use the documented randomization procedure and balance as closely as possible.

For two independent equal-allocation arms, two-sided α=0.05 and 80% power:

`MDE = (z[0.975] + z[0.80]) × σ × sqrt(1/n_treatment + 1/n_control)`

| Eligible unique customers | Enrolled | Treatment | Control | Not enrolled | Enrollment | Eligible base sent to treatment | MDE σ=£20 | MDE σ=£50 | MDE σ=£100 | MDE σ=£200 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1,000 | 100 | 50 | 50 | 900 | 10% | 5% | £11.21 | £28.02 | £56.03 | £112.06 |
| 2,500 | 250 | 125 | 125 | 2,250 | 10% | 5% | £7.09 | £17.72 | £35.44 | £70.88 |
| 5,000 | 500 | 250 | 250 | 4,500 | 10% | 5% | £5.01 | £12.53 | £25.06 | £50.12 |
| 10,000 | 1,000 | 500 | 500 | 9,000 | 10% | 5% | £3.54 | £8.86 | £17.72 | £35.44 |
| 25,000 | 2,500 | 1,250 | 1,250 | 22,500 | 10% | 5% | £2.24 | £5.60 | £11.21 | £22.41 |
| 50,000 | 5,000 | 2,500 | 2,500 | 45,000 | 10% | 5% | £1.58 | £3.96 | £7.92 | £15.85 |

Every SD column is hypothetical; none is measured in the UCI history. These are assumed standard deviations of the customer-level net-margin outcome, not estimates from UCI. They are normal-approximation planning values, not exact power guarantees. They assume independent randomized customers, equal arm variance, no household clustering, complete linked outcomes, a two-sided test and no variance reduction. Heavy right skew, influential high-value orders, refunds, negative margins and heterogeneous variance may make normal approximations inaccurate. Use real policy-matched margin distributions for final power planning and predefine robust/influence diagnostics without changing the estimand after results are seen.

## Commercial break-even scenarios

Let `g` be hypothetical incremental gross contribution per treatment assignment, before experimental email cost. It is an ITT-scale scenario value (not contribution among openers/delivered-only customers). Let `c` be one variable send cost charged to every treatment assignment. No experimental incentive is assumed. Then:

- Net incremental contribution per treatment assignment = `g − c`.
- ITT treatment-minus-control difference in mean net contribution margin = `g − c` under this simplified scenario.
- Expected campaign increment versus no study email among the randomized cohort = `n_treatment × (g − c)`.
- Average campaign increment per enrolled customer = `n_treatment × (g − c) / n_enrolled`; this is a cohort-average budget quantity, not the treatment-minus-control ITT effect.
- Break-even gross contribution per treatment assignment = `c`.

The MDE applies to the treatment-minus-control difference in mean net contribution margin, which is `g − c` here. Do not compare the average campaign increment per enrolled customer with the MDE.

The generated scenario schema already distinguishes these quantities: `net_itt_effect_gbp_per_randomized_customer` is `g − c`, while `net_incremental_contribution_gbp_per_enrolled_customer` is `n_treatment × (g − c) / n_enrolled`. The latter is cohort-average campaign value, not an ITT effect. No CSV field rename is needed. The MDE field represents the treatment-minus-control difference in mean net contribution margin.

This uses contact cost once. Do not subtract it again if the finance-linked primary outcome already includes campaign costs. BAU costs common to both arms are not treated as incremental study costs.

The cost convention assumes one attempted send and charges `c` to every treatment assignment, including a bounce/non-delivery after the attempt. The scenario gross contribution is already on an assignment/ITT basis; if a business supplies an effect per delivered customer instead, it must be diluted for non-delivery before this comparison. For example, with `g=£1`, net contribution per treatment assignment is £0.99, £0.95, £0.80 or £0.00 at costs £0.01, £0.05, £0.20 or £1.00 respectively. Non-delivery customers remain in the treatment arm for analysis.

For a 10,000-customer eligible base, 1,000 enroll and 500 receive an assigned treatment email. Each cell below is total expected incremental campaign contribution in pounds for that hypothetical gross contribution and send cost:

| Send cost per treatment assignment | Break-even gross contribution | £0 gross | £0.10 gross | £0.50 gross | £1 gross | £2 gross | £5 gross |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| £0.01 | £0.01 | −£5 | £45 | £245 | £495 | £995 | £2,495 |
| £0.05 | £0.05 | −£25 | £25 | £225 | £475 | £975 | £2,475 |
| £0.20 | £0.20 | −£100 | −£50 | £150 | £400 | £900 | £2,400 |
| £1.00 | £1.00 | −£500 | −£450 | −£250 | £0 | £500 | £2,000 |

The total scales linearly with treatment-assignment count under the scenario assumptions. For example, at £1 gross and £0.20 contact cost, net increment is £0.80 per treatment assignment; totals are £40, £100, £200, £400, £1,000 and £2,000 for eligible populations of 1,000, 2,500, 5,000, 10,000, 25,000 and 50,000 respectively. This arithmetic is not a forecast: neither `g` nor `c` is observed, and the effect must be estimated by randomization.

## Statistical versus commercial feasibility

Profitability in this simplified grid requires `g > c`. Approximate 80%-power detectability requires the net ITT effect `g − c` to be at least the MDE. Neither condition alone establishes a statistically significant result in the realized experiment or justifies rollout; rollout also requires uncertainty bounds, a business-defined minimum worthwhile value, operational constraints and acceptable guardrails.

The largest net effect in the requested grid is £4.99 (`g=£5`, `c=£0.01`). At 10% capacity:

- With 1,000–5,000 eligible customers, no requested gross/cost combination reaches the MDE, even at the lowest assumed SD (£20); the 5,000 case is nearly at the boundary (£4.99 versus £5.01).
- With 10,000 or 25,000 eligible customers, only the lowest-SD (£20) scenarios can reach the MDE, and only at the largest gross contribution (£5). In both populations, all four contact-cost cases reach the MDE: the minimum net effect is £4.00, above the respective £3.54 and £2.24 MDEs.
- With 50,000 eligible customers, SD £20 permits some £2 and £5 gross scenarios to exceed the MDE, and SD £50 permits the £5 gross scenarios. At SD £100 or £200, none of the requested effects reaches the MDE.

Thus a campaign can have positive expected value at (for example) £0.10 gross and £0.05 contact cost, while being far too small to distinguish from zero in a modest pilot. Conversely, a large detectable average effect may still fail the owner's economic threshold or guardrails. The MDE is not a pass/fail criterion for a single observed estimate and does not guarantee evidence for rollout.

## Enrollment-capacity sensitivity

Increasing capacity adds lower-frequency customers to the targeted population. It raises sample size and lowers the MDE, but changes the population and therefore potentially the treatment-effect estimand. Do not extrapolate top-decile effects to broader capacity.

| Eligible customers | Capacity | Enrolled | Treatment | Control | Not enrolled | MDE σ=£50 | MDE σ=£100 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 5,000 | 10% | 500 | 250 | 250 | 4,500 | £12.53 | £25.06 |
| 5,000 | 20% | 1,000 | 500 | 500 | 4,000 | £8.86 | £17.72 |
| 5,000 | 50% | 2,500 | 1,250 | 1,250 | 2,500 | £5.60 | £11.21 |
| 5,000 | 100% | 5,000 | 2,500 | 2,500 | 0 | £3.96 | £7.92 |
| 10,000 | 10% | 1,000 | 500 | 500 | 9,000 | £8.86 | £17.72 |
| 10,000 | 20% | 2,000 | 1,000 | 1,000 | 8,000 | £6.26 | £12.53 |
| 10,000 | 50% | 5,000 | 2,500 | 2,500 | 5,000 | £3.96 | £7.92 |
| 10,000 | 100% | 10,000 | 5,000 | 5,000 | 0 | £2.80 | £5.60 |
| 25,000 | 10% | 2,500 | 1,250 | 1,250 | 22,500 | £5.60 | £11.21 |
| 25,000 | 20% | 5,000 | 2,500 | 2,500 | 20,000 | £3.96 | £7.92 |
| 25,000 | 50% | 12,500 | 6,250 | 6,250 | 12,500 | £2.51 | £5.01 |
| 25,000 | 100% | 25,000 | 12,500 | 12,500 | 0 | £1.77 | £3.54 |

100% enrollment is a population-wide experiment, not a top-decile targeting pilot. At each capacity, the selected frequency-ranked fraction defines the experimental target population; treatment assignment remains randomized within that selected group.

## Optional baseline-covariate adjustment

Predeclared adjustment for strong pre-randomization predictors (e.g. 365-day gross contribution, purchase frequency, recency and market) can improve precision. In a simple linear approximation, residual variance is `σ² × (1 − R²)` and MDE scales by `sqrt(1 − R²)`. `R²` is not known here and must not be borrowed from the purchase-propensity model's AUC. As purely hypothetical scale, `R²=0.25` would multiply MDE by 0.866; `R²=0.50` by 0.707. Fit/choose no adjustment from treatment outcomes; specify the baseline covariates before launch and use only pre-assignment values. Report the unadjusted ITT estimate as a reference.

## Limitations and required business inputs

What these calculations establish: the 10%/1:1 design enrolls half as many treatment sends as selected customers; detectable margin differences shrink with larger unique-customer samples and lower outcome SD; contact-cost break-even is transparent under the stated accounting assumption.

What they do not establish: the live eligible base, consent/contactability rate, actual send cost, margin variance, return-lag completeness, treatment effect, or economically worthwhile threshold. The historical 21,672 M2 test snapshots are repeated monthly observations and cannot be substituted for unique pilot customers. Historical purchase prevalence/precision is not an untreated control rate, and model AUC is not a margin variance or treatment effect.

Before a real power calculation, obtain:

1. Current number of unique, contactable customers satisfying the full 365-day history and suppression rules, plus linked household/account structure.
2. Recent policy-relevant customer-level 30-day net contribution-margin distribution, including zeros, negative values, returns and late adjustment completion; estimate its SD and missing-linkage rate.
3. Finance-approved accounting for net sales, discounts/refunds, COGS, variable fulfilment/payment cost and whether campaign costs are charged per attempted or delivered message.
4. Approved financial adjustment lag, current email delivery cost, actual intervention/send capacity and treatment exposure expectations.
5. Owner-selected minimum worthwhile ITT contribution-margin effect, confidence/power requirements, budget, harm thresholds and interpretation of the 10% capacity denominator.

## Recommended decisions and next milestone

Retain 10% total enrollment with 1:1 allocation as the provisional targeted pilot design, but do not describe it as adequately powered until actual variance and effect thresholds are supplied. Prefer a pilot sized around the net-margin endpoint rather than purchase incidence. If the required sample exceeds the available top-decile cohort, the owner must choose among extending a predeclared enrollment window, increasing capacity (and accepting a broader target population), or treating the first pilot as estimation/feasibility work with limited power. Do not automatically move to 100% capacity.

The next scientific milestone should be a business-data readiness and power calculation: validate current eligibility and finance linkage, estimate margin variance/adjustment completeness, obtain the minimum worthwhile effect, and calculate the required unique enrollment count and feasible duration. No model retraining or historical uplift analysis is needed.

## Validation and generated outputs

Nine focused unit tests pass for capacity rounding, odd allocation, MDE arithmetic and scaling, commercial break-even/cost accounting, capacity sensitivity, variance-reduction scaling and deterministic output generation. The full repository unittest suite passed **126 tests with 1 skip**. The M4 scenario analysis used no customer-level inputs and wrote only aggregate tables.

The reference run wrote four aggregate CSV tables and `m4_002_scenario_manifest.json` outside the repository. The manifest records the module SHA-256 (`41dfba677a8e51e2e86888ec64c1072af585383323390c35c58730c5064b57bf`) and output hashes. Re-running with the same code and dependencies produces identical table and manifest bytes.

## Reproducibility

Run from the repository root after installing the existing minimal dependencies:

```sh
.venv/bin/python src/crm_pilot_feasibility.py --output-dir /path/outside/repository/m4_002_scenario_outputs
.venv/bin/python -m unittest tests.test_crm_pilot_feasibility -v
```

The module writes aggregate scenario CSVs and a manifest containing the module and output hashes. It uses no customer-level input. The reference run wrote outputs outside the repository; its sample, commercial, statistical-comparison and capacity tables each reconcile to the formulas above.
