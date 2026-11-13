# M4-001 — Randomised CRM Pilot Design

## Purpose and evidence boundary

This document proposes a practical customer-randomised pilot to estimate whether one CRM intervention increases customer contribution margin among customers chosen by a fixed targeting policy. It is a design only: no campaign is launched and no treatment effect is estimated here.

M2 found that the frozen full model ranked future purchasers well in one historical holdout (ROC-AUC 0.766; top-decile precision 69.3%, lift 2.95×). M3 found that the 365-day purchase-date frequency rule achieved about 98–99% of the full model's retrospective lift; the small Model C advantage was sensitive to frequency tie-breaking. These are purchase-propensity results, not evidence of campaign responsiveness. The UCI data has no verified campaign assignment, exposure, consent or financial cost records. See the [M2-008 baseline results](COMMERCIAL_DS_P2_M2_008_BASELINE_RESULTS.md), [M2-012 calibration results](COMMERCIAL_DS_P2_M2_012_SEQUENTIAL_CALIBRATION_RESULTS.md), [M3-002 targeting comparison](COMMERCIAL_DS_P2_M3_002_TARGETING_COMPARISON.md) and [M3-003 independent review](COMMERCIAL_DS_P2_M3_003_INDEPENDENT_TARGETING_REVIEW.md).

## Research question and estimand

Among contact-eligible established customers selected by the predeclared policy, what is the intention-to-treat (ITT) effect of assignment to one non-discount CRM email, compared with no study email, on 30-day net customer contribution margin?

The primary estimand is the mean difference per randomized customer:

`E[net contribution margin | assigned treatment] − E[net contribution margin | assigned control]`

Assignment, rather than successful delivery, opening or clicking, defines treatment for the primary analysis. This estimates the effect of offering/sending the campaign under actual delivery conditions. A delivered-only comparison would be confounded and is not the primary estimand.

### Primary economic outcome

For each randomized customer, sum contribution from qualifying orders placed in `[assignment_time, assignment_time + 30 days)`, then subtract the incremental campaign costs attributable to that customer. Define order contribution before campaign costs as:

`net merchandise sales after discounts and refunds − cost of goods sold − agreed variable fulfilment/payment costs`

Subtract variable send/contact cost and any incremental incentive cost once. The initial intervention has no experimental discount, reducing incentive ambiguity; discounts or promotions received through business as usual must still be recorded. If the finance system's net sales already reflects discounts, do not subtract them a second time. Include zero margin for customers with no qualifying order. Freeze the accounting specification, currency/tax treatment and cost allocation before assignment.

Orders must be attributed by order timestamp in the 30-day window. Returns, refunds and other late adjustments linked to those orders should be included through a common, predeclared settlement lag after the window. Finance must specify that lag from actual return and adjustment practice. The outcome is not mature until the full order window and adjustment lag have elapsed and both-arm transaction linkage is complete. If these cost or linkage components cannot be supplied, the requested net contribution-margin primary endpoint is not measurable; do not silently replace it with gross revenue. A purchase-incidence endpoint may be reported as a secondary operational outcome, but it does not establish profitability.

## Population and time zero

Use the M2 monthly snapshot convention and canonical qualifying purchase definitions from [`src/monthly_customer_snapshots.py`](../../src/monthly_customer_snapshots.py):

- One decision time `T`, at 00:00 on the first day of the enrollment month.
- Complete 365-day history `[T − 365 days, T)` and at least one qualifying purchase occasion in that interval.
- Features and ranking use only transactions strictly before `T`.

`T` is the monthly targeting and feature-snapshot timestamp. Record the actual random-assignment timestamp separately as `assignment_time`; it may occur after `T` and must not be assumed equal to it. Anchor the primary and every secondary outcome window at assignment: `[assignment_time, assignment_time + 30 days)`. The financial-adjustment lag begins after that outcome window and remains separately specified.

For a live CRM population, complete look-back means that the business transaction feed can establish the full window; it does not mean that missing activity is inferred from the historical UCI source. Use the existing M2 qualifying-purchase and gross-merchandise definitions without reclassifying transactions for this pilot.

Research eligibility is not contact eligibility. Before ranking, apply current business and legal checks: channel permission/consent, valid deliverable address, jurisdiction and policy eligibility, opt-out/suppression status, and any predeclared service, complaint, fraud or active-case exclusions. Apply a fixed recent-contact suppression period and existing contact-frequency limits. The CRM owner must specify the period and rules from current policy. Record an exclusion reason for every removed customer. The UCI data cannot establish any of these conditions.

Deduplicate to one stable customer entity before selection. If linked accounts or households can share communications or purchases, either make that linked entity the randomization unit or suppress duplicates and document the choice. A customer must not appear more than once in this pilot enrollment.

## Targeting and randomisation

### Stage A — Freeze and apply one targeting rule

At the enrollment decision:

1. Freeze the eligible, contactable population and its point-in-time feature snapshot.
2. Rank by descending `qualifying_purchase_dates_365d`.
3. Break frequency ties using an outcome-independent deterministic pseudorandom key, for example SHA-256 over a versioned fixed seed and normalized stable customer key. Sort tied customers by the digest. Keep the customer key and digest in restricted operational records, not reports.
4. Select `ceil(0.10 × eligible contactable population)` customers.
5. Freeze the list, policy version, input timestamp, eligible denominator, feature/selection code hash and realized capacity before randomization.

The 10% capacity is a provisional pilot design choice, not an optimized commercial optimum. The pseudorandom tie rule avoids relying on arbitrary key order; it does not change the score or imply that the frequency rule is causally superior. Do not compare Model C as a second policy in this pilot. A future policy trial would need its own design and sample-size justification.

### Stage B — Randomize selected customers once

Randomize selected customers 1:1 to treatment or control, using reproducible random assignment within a small set of predeclared strata: frequency-count band and, if operationally material, market/channel. Avoid many sparse strata. Store assignment, timestamp, stratum, allocation probability, policy version and randomization seed/version in the experiment record. Assignment remains persistent; no customer switches arms or is randomized again.

Use one fixed enrollment wave for the first pilot. Suppress every randomized customer from re-enrollment during the experiment and its follow-up. Treatment customers receive one study email only; control customers receive none of the study email. This avoids overlapping outcome windows, repeated assignment and within-customer dependence in this initial test. Normal business-as-usual communications continue in both arms and are logged.

**Capacity convention:** the selected top 10% is the total experimental enrollment cohort, including both treatment and control. Control customers therefore consume places in the 10% cohort but do not consume send slots. At 1:1 allocation, experimental sends are approximately 5% of the full contact-eligible population. This is the recommended convention because it keeps the target population and randomized comparison aligned. If the business instead means 10% *actual sends*, it must approve targeting up to 20% for a 1:1 experiment, or another allocation/capacity design, before list construction; do not change the denominator after seeing outcomes.

Customer is the assignment and primary analysis unit unless household/account linkage requires randomizing a larger shared-contact unit. For household randomization, calculate capacity and power in units and use cluster-robust or randomization-based inference at that unit.

## Intervention and control

Treatment: one standardized, non-discount email with a concise product reminder or discovery message, sent within a fixed short interval after assignment (recommended within 24 hours). Fix the template, eligibility, product-selection rule, sender, subject/content variants and send schedule before launch. Personalization should use only approved pre-assignment data; if reliable current catalog/product mapping is unavailable, use a single common curated message rather than inventing a product taxonomy. No experimental coupon or price incentive is included.

Control: no study email during `[assignment_time, assignment_time + 30 days)`. Continue ordinary business-as-usual contacts under the same existing rules; log their channel, timestamp and campaign so treatment contrast can be interpreted. Do not withhold service or legally required messages.

Record assignment separately from attempted send, accepted delivery, bounce, open, click and unsubscribe. Failed delivery and non-engagement remain in the assigned treatment arm for ITT. Keep any operational delivery analysis secondary and descriptive. Cap study contact at one email per randomized customer; apply the business's ordinary global contact limit across both study and non-study messages. Before launch, determine whether the study email displaces another permitted business-as-usual contact and record any displacement.

## Outcomes, analysis and guardrails

Primary analysis includes every randomized unit in its assigned arm. Estimate the treatment-control mean difference in 30-day net contribution margin with a two-sided 95% confidence interval and a two-sided 5% test, respecting any randomization strata and household clustering. Predeclare any baseline covariate adjustment using only pre-assignment variables; report the unadjusted ITT estimate as the transparent reference. Do not exclude customers for non-delivery, non-opening, purchase absence, or post-randomization behavior. Report assignment counts, delivery, outcome linkage and maturity by arm.

Secondary outcomes over the same `[assignment_time, assignment_time + 30 days)` order window:

- Any canonical qualifying purchase (absolute risk difference and interval).
- Number of qualifying purchase occasions and net merchandise revenue.
- Order value, returns/refunds and discount/redemption measures.
- Delivery, bounce, unsubscribe, complaint and other pre-agreed customer-harm outcomes.

These are secondary; designate a small number as key and treat the rest as descriptive to avoid a large unplanned testing family. Opens and clicks measure engagement, not incremental commercial value. Do not infer causality from within-treatment engagement comparisons.

Set guardrails before launch for total send spend, frequency, deliverability, unsubscribe/complaint rates, data linkage and operational errors. Use stop rules for customer harm, compliance, or budget limits. Do not stop early or repeatedly inspect purchase outcomes unless a sequential design and error control are explicitly planned. Report no deployment or profitability claim unless the primary net-margin estimate and uncertainty support the predeclared business threshold.

## Sample size and decision threshold

Before launch, the owner must specify a minimum economically worthwhile ITT margin effect, `δ`, and finance must supply a plausible customer-level margin variance, `σ²`, from an appropriate recent population. For a continuous outcome and equal allocation, a first approximation is:

`n per arm ≈ 2 × (z[0.975] + z[0.80])² × σ² / δ²`

Use at least 80% power and two-sided α=0.05 as a planning default, then adjust for household clustering, incomplete financial linkage and any non-normality using simulation or robust planning on business data. Keep all randomized customers in analysis; do not inflate by removing non-deliveries as if they were attrition.

For the binary purchase secondary endpoint, a two-proportion calculation needs a current untreated/control baseline and a business-relevant absolute effect. M3's historical 23.5% overall prevalence and 69.3% top-decile precision are not valid untreated control rates. As scale only, the usual independent equal-arm approximation is `2 × (z[0.975] + z[0.80])² × p(1−p) / δ²`; replace `p` and `δ` with current, policy-matched business inputs. The selected top 10% must contain at least twice the calculated per-arm requirement, and the contactable base must be large enough for that top-decile cohort. If not, extend enrollment only under a predeclared multi-wave design or do not launch an underpowered pilot.

The success criterion should be commercial as well as statistical: predeclare a minimum net contribution margin improvement per randomized customer that justifies operating costs and uncertainty. A statistically positive purchase-rate difference alone does not pass a profitability decision.

## Interference, contamination and interpretation

Potential contamination includes forwarded emails, shared household accounts, treatment customers seeing campaign content elsewhere, control customers receiving an equivalent business-as-usual campaign, and concurrent promotions. Record account links and all contacts; randomize at shared exposure units where material; pause or document overlapping campaigns consistently. ITT remains the effect of assignment under the observed background communications. Contamination generally dilutes contrast and limits interpretation; it is not a reason to remove customers after randomization.

This pilot estimates an average effect for customers selected by this one frequency rule under the campaign and operating context tested. It does not show effects for unselected customers, prove that the frequency score identifies treatment responders, or establish that Model C is a better allocation policy. With sufficiently large randomized data across a broader eligible population, later work could estimate heterogeneous treatment effects or evaluate prespecified uplift policies on held-out experimental data. Do not train an uplift model on propensity outcomes alone.

## Minimum business data and launch blockers

The UCI snapshots can support historical feature and ranking definitions only. A live pilot requires:

1. Current stable customer/entity keys, transaction feed and the full pre-assignment 365-day history; canonical order line, timestamp and qualifying-status fields.
2. Current consent/permission, deliverability, jurisdiction, suppression, contact history and customer/account linkage.
3. Randomization and campaign logs: frozen eligible denominator and selected list, assignment/stratum/probability, policy version, message content, send/delivery/engagement timestamps, and all concurrent business-as-usual contacts.
4. Order-linked net sales, discounts, refunds/returns, COGS, variable fulfilment/payment costs, campaign send costs and finance-approved margin rules.
5. Complete order and financial adjustment linkage for both arms, with a predeclared return/adjustment lag and enough observation time to mature outcomes.
6. A current eligible population size, control-rate/margin distribution for planning, operating capacity, and the owner's minimum worthwhile effect and budget/guardrails.

Without items 2–5, the campaign cannot support the proposed contactable population or net-margin ITT endpoint. Without item 6, sample size and commercial success thresholds cannot be fixed. These are genuine pre-launch data/decision dependencies; they do not block preparing this design.

## Decisions to approve before implementation or launch

- Confirm top 10% means total randomized cohort, with about 5% actual experimental sends at 1:1 allocation; otherwise choose the send-capacity interpretation and revise enrollment size.
- Approve the non-discount email, send timing, one-contact cap and business-as-usual control policy.
- Set consent, suppression and recent-contact rules; define customer versus household randomization unit from available links.
- Approve the contribution-margin accounting and fixed return/adjustment maturity lag.
- Supply the minimum worthwhile net-margin effect, current population/variance inputs, budget and harm guardrails.

## Recommended next implementation milestone

Implement a small **pilot-readiness and power specification** using current CRM/finance data, without launching a campaign: validate eligibility and contactability fields, calculate the reachable top-decile enrollment size, estimate outcome/margin completeness and variance, and return feasible enrollment duration and power for owner-selected effect thresholds. Freeze the intervention, margin formula, return lag, capacity convention and assignment plan in that milestone before producing any campaign list. No retrospective uplift analysis or new model fitting is needed.
