# M4-003 — Independent Review of M4-001 Pilot Design and M4-002 Feasibility

**Reviewer:** Claude Code (independent scientific reviewer)
**Date:** 2026-11-12
**Verdict:** **PASS WITH CONDITIONS**

The pilot design identifies a coherent causal estimand. Every MDE, allocation, break-even, campaign total and capacity figure reproduces exactly, and the scenario outputs are byte-for-byte deterministic. Before closure, one ITT terminology error and two small text inconsistencies need correcting. None changes a numerical result or conclusion.

## A. Experimental design (M4-001)

All ten requested design elements are present:

1. One enrollment wave, with no re-enrollment.
2. The top `ceil(10%)` of contact-eligible established customers, ranked by `qualifying_purchase_dates_365d`.
3. Ties broken by SHA-256 over a versioned seed and customer key, fixed in advance. This adopts the M3-003 recommendation.
4. Persistent customer-level 1:1 assignment. Optional frequency-band or market strata are allowed.
5. Controls counted inside the 10% cohort, so about 5% of the eligible base receive sends.
6. One standardised non-discount email.
7. No study email for controls.
8. Business-as-usual (BAU) contacts continued and logged in both arms.
9. A 30-day order window plus a finance-specified adjustment lag.
10. Intention-to-treat (ITT) analysis by assigned arm, with no delivery- or engagement-based exclusions.

The estimand is `E[net margin | assigned email] − E[net margin | assigned no study email]` among frequency-selected, contact-eligible customers, under the prevailing BAU background. Randomisation identifies it. The design correctly limits generalisation to that selected population and campaign, and excludes uplift and policy-comparison claims.

The report separates operational approvals (capacity convention, consent and suppression rules, margin accounting, lag, minimum worthwhile effect, guardrails) from the statistical design.

### Finding 2 (Low; required clarification): the outcome window is defined two ways

The primary outcome uses `[assignment_time, assignment_time + 30 days)`. However, M4-001 also states that "the behavioral outcome window is `[T, T + 30 days)`", and the secondary outcomes use "the same `[T, T+30 days)` order window".

If assignment happens after `T`, the `[T, …)` window includes pre-assignment purchases, and the primary and secondary windows differ. This causes no bias under randomisation, but it adds noise and leaves the definition inconsistent.

**Correction:** use one window, `[assignment_time, assignment_time + 30 days)`, for all outcomes, or require assignment at `T`.

### Finding 3 (Low; recommended before launch): the global contact cap can displace BAU messages

M4-001 applies "the business's ordinary global contact limit across both study and non-study messages". In the treatment arm, the study email could then displace a BAU email that controls still receive. The contrast would become "study email versus the displaced BAU message", not "study email versus no study email".

**Correction:** before launch, either exempt the single study email from the cap, or state that displacement is part of the estimand and log displaced messages by arm. This is an operational decision, not a design flaw.

## B. Sample size and power (independently reproduced)

`z₀.₉₇₅ = 1.95996` and `z₀.₈₀ = 0.84162`, which sum to 2.80159. `MDE = 2.80159 × σ × √(1/nₜ + 1/n_c)`.

| Eligible | Enrolled (T/C) | σ £20 | σ £50 | σ £100 | σ £200 |
| ---: | --- | ---: | ---: | ---: | ---: |
| 1,000 | 100 (50/50) | 11.21 | 28.02 | 56.03 | 112.06 |
| 2,500 | 250 (125/125) | 7.09 | 17.72 | 35.44 | 70.88 |
| 5,000 | 500 (250/250) | 5.01 | 12.53 | 25.06 | 50.12 |
| 10,000 | 1,000 (500/500) | 3.54 | 8.86 | 17.72 | 35.44 |
| 25,000 | 2,500 (1,250/1,250) | 2.24 | 5.60 | 11.21 | 22.41 |
| 50,000 | 5,000 (2,500/2,500) | 1.58 | 3.96 | 7.92 | 15.85 |

All values are identical to M4-002.

- **Rounding:** the `ceil` rounding and the odd-enrollment rule (treatment gets the extra customer, e.g. 1,005 → 101 = 51/50) are correct and disclosed as a scenario convention only.
- **Scaling:** the MDE scales with σ and with `1/√n` as stated.
- **Caveats:** the report labels the MDE as an illustrative normal approximation. It acknowledges right skew, outliers, negative margins, unequal variance and incomplete linkage, and states that SDs are hypothetical rather than estimated from UCI.
- **Stratification:** ignoring stratification makes the MDE conservative. The R² adjustment factors (0.866 and 0.707) are correct.

## C. Commercial calculations

Values reproduced:

- **Break-even** gross contribution per treatment assignment = `c`.
- **Net** contribution per treatment assignment = `g − c`. For example, at `g = £1`: £0.99, £0.95, £0.80 and £0.00.
- **Campaign totals** for a 10,000-customer eligible base (500 treatment assignments), `500 × (g − c)`: all 24 cells match, from −£500 to £2,495.
- **Scaling** at `g = £1`, `c = £0.20`: £40, £100, £200, £400, £1,000 and £2,000.

**Accounting.** `g` is an ITT-scale gross effect per treatment assignment before the study send cost. `c` is charged once, to every treatment assignment including bounces. The comparison table tests `g − c ≥ MDE`. This is consistent with M4-001's outcome, which is margin net of attributable campaign cost, so control has no cost and treatment carries `c`. **The cost is subtracted exactly once.**

### Finding 1 (Medium; required correction): a mislabelled "ITT contrast"

M4-002 states: "Mean ITT contrast across all randomized customers is approximately `(n_treatment / n_enrolled) × (g − c)`". The code exports the same quantity as `net_incremental_contribution_gbp_per_enrolled_customer`.

Under M4-001, the ITT estimand per randomised customer is the **difference in arm means**, which equals `g − c`. The quantity `(nₜ/n_e)(g − c)`, about `(g − c)/2`, is the **campaign increment averaged over every enrolled customer**: the total increment divided by the cohort size. It is a budget figure, not the estimand, and must not be compared with the MDE.

The four quantities are:

| Quantity | Formula |
| --- | --- |
| Gross increment per treatment assignment | `g` |
| Net increment per treatment assignment = ITT treatment − control difference | `g − c` |
| Total campaign increment | `nₜ(g − c)` |
| Cohort-average increment | `nₜ(g − c)/n_e` |

Labelling the last one an "ITT contrast" invites halving effect sizes or comparing the wrong quantity with the MDE.

The code's comparison itself is correct: it uses `g − c` against the MDE. So are all numerical conclusions.

**Correction:**

- Reword that sentence in M4-002 to describe the cohort-average increment.
- Describe the MDE as "for the treatment − control difference in mean net margin per customer" rather than the bare "per randomized customer".
- Annotate or rename the CSV column. No rerun of the scenario conclusions is needed.

### Finding 4 (Low; required text fix): an incorrect detectability statement

M4-002 says that at 10,000 and 25,000 eligible customers and σ = £20, the £5 scenarios reach the MDE and "whether they do depends on send cost". Independent enumeration shows that **all four** £5 scenarios reach the MDE at both sizes, because the smallest net effect is £4.00, above the £3.54 and £2.24 MDEs. The answer does not depend on cost.

The other detectability statements are correct:

- None of the grid reaches the MDE at 1,000–5,000 eligible customers (£4.99 against £5.01 at 5,000).
- At 50,000 and σ = £20, the £2 scenarios with `c ≤ £0.20` and all £5 scenarios reach it.
- At 50,000 and σ = £50, the £5 scenarios reach it.
- At 50,000 and σ = £100 or £200, nothing reaches it.

**Correction:** delete "whether they do depends on send cost".

## D. Capacity sensitivity

All 12 enrollment and allocation rows and the MDE values at σ = £50 and £100 reproduce. For example, at 10,000 eligible customers: 10%: 8.86 / 17.72; 20%: 6.26 / 12.53; 50%: 3.96 / 7.92; 100%: 2.80 / 5.60.

The report correctly states that wider capacity adds lower-frequency customers. Wider capacity improves power but changes the target population and therefore the estimand. It also forbids extrapolating top-decile effects. It does not assume constant effects across rank, and it notes that 100% is a population-wide experiment.

## E. Scientific interpretation

The reports distinguish four different things:

| Concept | Definition used |
| --- | --- |
| Commercial break-even | `g > c` |
| Minimum worthwhile effect | Owner-specified δ |
| Statistical detectability | Net effect ≥ MDE, which is also not a pass/fail rule for a single estimate |
| Rollout evidence | Interval, threshold and guardrails |

No treatment effect, margin variance, deliverability or campaign outcome is presented as a UCI finding. The historical repeated snapshots and propensity metrics are explicitly excluded as substitutes for unique customers or control rates.

The recommended next step, a business-data readiness and power milestone with no model fitting, follows from the evidence: feasibility depends entirely on unknown eligible-base size, margin SD and minimum worthwhile effect.

## F. Reproducibility

- **Tests:** 9 of 9 focused tests pass. The full `tests/` suite runs 126 tests with 1 Spark skip.
- **Hashes:** the module SHA-256 `41dfba67…` matches the scenario manifest. A reviewer rerun produced byte-identical CSVs and manifest (all four table hashes and manifest `ddf454a4…`).
- **Inputs and storage:** no customer data is loaded and no model is fitted. Outputs are aggregate CSVs outside the repository. No new CSV or scenario file is tracked by Git; the only tracked CSVs are pre-existing taxonomy files.

## Readiness

After Findings 1, 2 and 4 are corrected as text in M4-002 and M4-001, with an optional CSV column annotation, **M4-001 through M4-003 are ready for a scoped local commit**:

- `src/crm_pilot_feasibility.py`
- `tests/test_crm_pilot_feasibility.py`
- the M4-001, M4-002 and M4-003 documents

Finding 3 is a pre-launch operational decision, not a closure blocker.

No code, data, prior reports or Git state were modified by this review. Reviewer scripts are kept outside the repository.
