# M3-003 — Independent Review of M3-002 Retrospective Targeting Comparison

**Reviewer:** Claude Code (independent scientific reviewer)
**Date:** 2026-11-12
**Verdict:** **PASS WITH CONDITIONS**

All policy selections, pooled and monthly metrics, overlaps, contact-concentration counts and paired bootstrap intervals reproduce exactly from independent code. The bootstrap is coherent, and the interpretation keeps propensity separate from causal or commercial value.

One disclosure is required. A substantial share of the frequency rule's selections are decided by customer-key tie-breaking. Plausible alternative tie rules move its precision by about as much as the reported Model C − frequency differences.

## A. Policy implementation

**Population.** The test population has 21,672 mature, complete-coverage customer-months from 4,999 customers. Monthly counts are 4,314, 4,326, 4,324, 4,364 and 4,344. Each customer appears at most once per month.

**Capacity.** Capacity is `ceil(capacity × monthly n)`: 216–219 customers at 5%, 432–437 at 10% and 863–873 at 20%. All policies use the same counts. The pooled event totals of 1,087, 2,170 and 4,336 are sums of the monthly ceilings.

**Scores and rules.**

| Policy | Score | Notes |
| --- | --- | --- |
| Model C | `probability_C_full_11` | Frozen M2-008 predictions; input hashes verified |
| RFM (Model B) | `probability_B_rfm` | Frozen M2-008 predictions |
| Frequency | `qualifying_purchase_dates_365d` | An existing pre-decision feature |
| Random | — | Analytical expectation |

- No model is fitted.
- The policies sort by score descending, then by customer key ascending. Neither step uses outcomes.
- The 365-day date-count frequency rule and the customer-key tie-break were specified in the owner's M3-002 instruction before any results. They replace M3-001's suggested 90-day occasion count and pseudorandom tie key, and the report discloses the change in frequency rule.

**Two output runs.** The two external output directories (`m3_002_targeting_outputs` and `..._final`) have identical selections and differ only in how contact concentration is grouped (the bug fix that split it by capacity). The final run was therefore not chosen for its results.

## B. Aggregate metrics (independent recomputation)

| Capacity | Policy | Selected | Positives | Precision | Capture | Lift |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 5% | C / RFM / Freq / Random | 1,087 | 894 / 856 / 878 / 255.43 | 82.24 / 78.75 / 80.77 / 23.50% | 17.56 / 16.81 / 17.24 / 5.02% | 3.50 / 3.35 / 3.44 / 1.00 |
| 10% | C / RFM / Freq / Random | 2,170 | 1,505 / 1,459 / 1,493 / 509.87 | 69.35 / 67.24 / 68.80 / 23.50% | 29.56 / 28.65 / 29.32 / 10.01% | 2.95 / 2.86 / 2.93 / 1.00 |
| 20% | C / RFM / Freq / Random | 4,336 | 2,380 / 2,323 / 2,350 / 1,018.75 | 54.89 / 53.57 / 54.20 / 23.50% | 46.74 / 45.62 / 46.15 / 20.01% | 2.34 / 2.28 / 2.31 / 1.00 |

**Pooling.** Pooled values sum selected events and positives before dividing, as the code shows. Because monthly capacities are nearly equal, the unweighted mean of monthly precisions happens to agree here, for example 0.6935 for C at 10%.

**Overlap.** Model C's selections overlap with RFM by 88.7%, 87.9% and 90.5%, and with frequency by **86.9%, 85.9% and 87.2%**, at 5%, 10% and 20% respectively.

**Contact concentration** matches the report:

| Capacity | Model C: unique / selected in multiple months | Frequency: unique / selected in multiple months |
| --- | --- | --- |
| 10% | 598 / 498 | 540 / 481 |
| 20% | 1,205 / 1,008 | — |

Every monthly cell matches as well. Model C selects at least as many purchasers as RFM in every month and capacity.

### Finding 1 (Medium; required disclosure): frequency selections depend on the tie-break

Frequency is an integer score with heavy ties. At 10% capacity, the boundary score is 8 purchase dates in every month. About 355–365 customers score above it, and **67–79 of the 432–437 slots per month (about 17% of selections)** are filled from tied pools of 79–98 customers. Those customers are chosen purely by ascending customer key. Tied-pool prevalence ranges from 0.40 to 0.62 across months. Model C has no material ties.

Pooled frequency precision under other outcome-independent tie rules:

| Tie rule | 5% | 10% | 20% |
| --- | ---: | ---: | ---: |
| Key ascending (reported) | 80.77% | 68.80% | 54.20% |
| Expected under uniform random tie-break | 81.02% | 68.58% | 53.89% |
| Key descending | 81.23% | 68.48% | 53.57% |
| SHA-256(key, month), as in the M3-001 design | 81.14% | 68.43% | 54.24% |

Frequency precision therefore moves by up to about **0.5–0.7 pp** depending on an arbitrary rule. That is the same order as the reported Model C − frequency differences (+1.47, +0.55 and +0.69 pp). Customer ID is essentially unrelated to the outcome (r = −0.016), so the rule is not biased, but the specific point differences are not robust. The bootstrap keeps the tie order fixed, so its intervals are conditional on this rule.

**Consequence.** The qualitative conclusion stands: Model C and frequency are not distinguished. The reported Model C − frequency point differences, and their sign in individual months, should not be read as meaningful.

**Smallest correction.** Add a short paragraph to the M3-002 report covering:

- the tied-pool share at each capacity
- the expected frequency precision under a random tie-break, or the range across tie rules shown above
- that the intervals are conditional on the customer-key tie rule

No rerun is required.

## C. Statistical uncertainty

`paired_customer_cluster_bootstrap` draws the 4,999 customers with replacement using `PCG64(20261112)` and weights each customer's monthly rows by their draw multiplicity.

**Monthly capacity.** For each month and policy, capacity is recomputed as `ceil(capacity × resampled monthly n)`. Selection walks the original score order and takes row weights up to `k`, so duplicated copies can be partly selected at the boundary.

**Paired comparisons.** All policies and the random expectation are computed on the same replicate weights.

**Are duplicated customer-months handled correctly? Yes.** In the bootstrap pseudo-population, a customer drawn twice represents two distinct, identical customers. Each occupies a slot, and capacity scales with the pseudo-population. This is the standard nonparametric bootstrap of a "precision at the top q-fraction" statistic and preserves the estimand: a fixed capacity share per month, pooled by snapshot.

Copies share a score and so are contiguous. Fractional selection at the boundary is equivalent to choosing some of the copies, so it does not change the estimand. Within-customer dependence across months is preserved because whole trajectories are resampled.

**Reproduction.** I re-implemented the bootstrap with the same seed. All nine precision-difference intervals are identical, with 2,000 valid replicates:

| Capacity | C − RFM | C − Frequency | C − Random |
| --- | --- | --- | --- |
| 5% | [+1.67, +5.44] | [−0.09, +3.21] | [+55.83, +61.61] |
| 10% | [+0.79, +3.26] | [−0.50, +2.17] | [+42.69, +48.79] |
| 20% | [+0.51, +1.80] | [−0.28, +1.26] | [+29.41, +32.97] |

The report labels these as exploratory percentile intervals on a holdout that had already been examined. They exclude random-list draw variability and, per Finding 1, tie-rule variability.

## D. Scientific interpretation

The report correctly separates three things:

- predictive ranking and historical purchase capture, which is what was measured
- incremental treatment response, which is not estimable without randomised assignment
- incremental commercial value, which also needs margin and cost data

It makes no causal or profitability claim.

"Model C is not clearly better than frequency" and "this sample does not distinguish" them are supported. The report does not claim equivalence, which is correct: the upper bounds still allow a Model C advantage of up to about 2–3 pp at 5–10% capacity.

"Frequency captured most of Model C's performance" is fair. The policies overlap by about 86–87%, and frequency's lift is about 98–99% of Model C's at every capacity.

The Model C − RFM advantage (+1.3 to +3.5 pp) is positive in every interval but small. Calling it "modest" is appropriate.

## E. Reproducibility

- **Hashes:** input hashes match the frozen M2-004 and M2-008 artifacts. The final aggregate (`5e9558f7…`), selections (`bd94ff0b…`) and manifest (`7422a915…`) hashes match the report.
- **Tests:** 8 of 8 targeting tests pass, covering capacity rounding, deterministic ties, unique monthly selection, accounting, random expectation, bootstrap multiplicity and pooling. The full `tests/` suite runs 117 tests with 1 Spark skip.
- **Storage:** no Parquet or selection files are tracked by Git.
- **Scope:** no M2 artifact or model was changed.

Optional: label the superseded first output directory (`m3_002_targeting_outputs`) as such, or remove it locally, to avoid confusion.

## Readiness

After the Finding 1 disclosure is added to the M3-002 report, **M3-001 through M3-003 are ready for a scoped local commit**:

- `src/monthly_targeting_policies.py`
- `tests/test_monthly_targeting_policies.py`
- the M3-001, M3-002 and M3-003 documents

Customer-level selections stay outside Git.

No code, data, prior reports or Git state were modified by this review. Reviewer scripts are kept outside the repository.
