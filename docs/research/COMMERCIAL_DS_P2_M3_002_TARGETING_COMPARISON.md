# M3-002 — Retrospective CRM Targeting Policy Comparison

## Summary

On the previously examined, fully mature July–November 2011 holdout, all three ranked policies selected purchasers substantially more often than uniform random targeting. Model C's pooled advantage over RFM was modest but positive. Its edge over the transparent 365-day purchase-date frequency rule was small, and paired customer-cluster intervals included zero at every capacity. The frequency rule captured most of Model C's retrospective ranking performance.

These results measure **historical purchase propensity and capture**, not incremental campaign impact. The UCI data contains no randomized CRM treatment assignment or reliable exposure record. No treatment effects or causal uplift were estimated.

## Data, policies and selection rule

Inputs were the verified M2-004 monthly snapshot dataset, its manifest, the frozen M2-008 test-prediction Parquet and baseline run manifest. Hashes were checked before analysis; the test predictions were reused unchanged. The test population comprises 21,672 mature customer-month snapshots, 5,092 positive outcomes (23.50%), and 4,999 distinct customers across July–November. There is one record per customer in each month; customers can reappear in later months.

| Input | SHA-256 |
| --- | --- |
| M2-004 dataset | `44c580a83bea993fd0e2f8df8a03bb7aa2f11e64085671ea2ed78c9e28e952a8` |
| M2-004 source manifest | `3d7ee78afa96a1d4abe7ee8f7762a994e652bc5c799b892d227f56be03c96a13` |
| M2-008 test predictions | `facdd36297340138ec23ddbd98bc9cc551776c6bdf635e731ced08cc440626c1` |
| M2-008 run manifest | `81bb760a60c4d9badd6b3b65baf93086165e5a4c30ec1e9391390b4e30c2e14a` |

Policies:

- **Model C:** frozen `probability_C_full_11`, descending.
- **RFM:** frozen `probability_B_rfm`, descending.
- **Frequency:** existing `qualifying_purchase_dates_365d`, descending; no model fitted.
- **Random:** analytical uniform-selection expectation; no random list or favorable draw selected.

The requested frequency variable is the 365-day qualifying purchase-date count. M3-001 had suggested the alternative 90-day occasion count; this implementation follows the more specific M3-002 definition and introduces no new feature taxonomy.

Within each decision month, capacity is `ceil(capacity × eligible mature customers)`. This yields monthly selections of 216–219 customers at 5%, 432–437 at 10%, and 863–873 at 20%; all policies use the same capacity. Ranked ties are resolved by customer key ascending, independently of outcome. The same customer is selected at most once within a month. Selection identities are retained only in a local Parquet outside Git.

Precision is selected positives / selected customers; capture is selected positives / all monthly positives; lift is precision / monthly prevalence. Pooled values sum selected customer-month events and positives first, then calculate metrics (snapshot weighting), rather than averaging monthly rates. Random expected selected positives may be fractional. Its expected precision is the monthly prevalence, expected capture is the selected fraction, and lift is 1 within each month.

## Pooled July–November results

The pooled capacity events are the sum of the five monthly ceilings, so they need not equal one ceiling applied to the full 21,672-row population.

| Capacity | Policy | Selected events | Selected positive outcomes | Precision | Purchase capture | Lift over pooled prevalence |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 5% | Model C | 1,087 | 894 | 82.24% | 17.56% | 3.50× |
|  | RFM | 1,087 | 856 | 78.75% | 16.81% | 3.35× |
|  | Frequency | 1,087 | 878 | 80.77% | 17.24% | 3.44× |
|  | Random expectation | 1,087 | 255.43 | 23.50% | 5.02% | 1.00× |
| 10% | Model C | 2,170 | 1,505 | 69.35% | 29.56% | 2.95× |
|  | RFM | 2,170 | 1,459 | 67.24% | 28.65% | 2.86× |
|  | Frequency | 2,170 | 1,493 | 68.80% | 29.32% | 2.93× |
|  | Random expectation | 2,170 | 509.87 | 23.50% | 10.01% | 1.00× |
| 20% | Model C | 4,336 | 2,380 | 54.89% | 46.74% | 2.34× |
|  | RFM | 4,336 | 2,323 | 53.57% | 45.62% | 2.28× |
|  | Frequency | 4,336 | 2,350 | 54.20% | 46.15% | 2.31× |
|  | Random expectation | 4,336 | 1,018.75 | 23.50% | 20.01% | 1.00× |

At 10%, Model C's precision was 2.12 percentage points above RFM and 0.55 points above frequency. Its capture was 0.90 points above RFM and 0.24 points above frequency. At 20%, broader coverage raised Model C capture to 46.74%, while precision fell to 54.89%. The frequency rule was within 0.70 precision points of Model C at 20% and within 0.56 points at 5%.

## Frequency-rule tie sensitivity

The frequency policy ranks customers by the integer-valued `qualifying_purchase_dates_365d` feature. Ties are resolved by ascending customer key, a deterministic rule selected before evaluation. At 10% capacity the cutoff is eight qualifying purchase dates in every month; approximately 17% of selected customers are chosen from tied scores at that boundary. M3-003 independently assessed alternative outcome-independent tie rules and found the following pooled frequency precision:

| Capacity | Original key ordering | Random tie expectation | Descending key | Hashed key |
| --- | ---: | ---: | ---: | ---: |
| 5% | 80.77% | 81.02% | 81.23% | 81.14% |
| 10% | 68.80% | 68.58% | 68.48% | 68.43% |
| 20% | 54.20% | 53.89% | 53.57% | 54.24% |

The Model C versus frequency point differences are therefore sensitive to the tie rule. The existing bootstrap intervals are conditional on the implemented ascending customer-key ordering and do not include tie-rule variability. This does not invalidate the reported comparison, but it limits claims about the exact size of Model C's advantage over frequency.

## Month-level stability

Each cell gives `precision (capture; lift)`. Random targeting has expected monthly precision equal to prevalence, capture approximately equal to capacity (minor rounding from integer selection), and lift 1.00×.

### 5% capacity

| Month | Eligible / selected / prevalence | Selected positives C / RFM / Frequency / Random expected | Model C precision (capture; lift) | RFM precision (capture; lift) | Frequency precision (capture; lift) |
| --- | ---: | ---: | --- | --- | --- |
| July | 4,314 / 216 / 18.75% | 174 / 164 / 170 / 40.5 | 80.6% (21.5%; 4.30×) | 75.9% (20.3%; 4.05×) | 78.7% (21.0%; 4.20×) |
| August | 4,326 / 217 / 18.38% | 171 / 167 / 168 / 39.9 | 78.8% (21.5%; 4.29×) | 77.0% (21.0%; 4.19×) | 77.4% (21.1%; 4.21×) |
| September | 4,324 / 217 / 24.12% | 178 / 173 / 174 / 52.3 | 82.0% (17.1%; 3.40×) | 79.7% (16.6%; 3.31×) | 80.2% (16.7%; 3.32×) |
| October | 4,364 / 219 / 24.04% | 173 / 161 / 168 / 52.6 | 79.0% (16.5%; 3.29×) | 73.5% (15.3%; 3.06×) | 76.7% (16.0%; 3.19×) |
| November | 4,344 / 218 / 32.14% | 198 / 191 / 198 / 70.1 | 90.8% (14.2%; 2.83×) | 87.6% (13.7%; 2.73×) | 90.8% (14.2%; 2.83×) |

### 10% capacity

| Month | Eligible / selected / prevalence | Selected positives C / RFM / Frequency / Random expected | Model C precision (capture; lift) | RFM precision (capture; lift) | Frequency precision (capture; lift) |
| --- | ---: | ---: | --- | --- | --- |
| July | 4,314 / 432 / 18.75% | 280 / 275 / 275 / 81.0 | 64.8% (34.6%; 3.46×) | 63.7% (34.0%; 3.39×) | 63.7% (34.0%; 3.39×) |
| August | 4,326 / 433 / 18.38% | 293 / 275 / 277 / 79.6 | 67.7% (36.9%; 3.68×) | 63.5% (34.6%; 3.46×) | 64.0% (34.8%; 3.48×) |
| September | 4,324 / 433 / 24.12% | 302 / 292 / 308 / 104.4 | 69.7% (29.0%; 2.89×) | 67.4% (28.0%; 2.80×) | 71.1% (29.5%; 2.95×) |
| October | 4,364 / 437 / 24.04% | 282 / 281 / 290 / 105.0 | 64.5% (26.9%; 2.68×) | 64.3% (26.8%; 2.68×) | 66.4% (27.6%; 2.76×) |
| November | 4,344 / 435 / 32.14% | 348 / 336 / 343 / 139.8 | 80.0% (24.9%; 2.49×) | 77.2% (24.1%; 2.40×) | 78.9% (24.6%; 2.45×) |

### 20% capacity

| Month | Eligible / selected / prevalence | Selected positives C / RFM / Frequency / Random expected | Model C precision (capture; lift) | RFM precision (capture; lift) | Frequency precision (capture; lift) |
| --- | ---: | ---: | --- | --- | --- |
| July | 4,314 / 863 / 18.75% | 420 / 404 / 409 / 161.8 | 48.7% (51.9%; 2.60×) | 46.8% (49.9%; 2.50×) | 47.4% (50.6%; 2.53×) |
| August | 4,326 / 866 / 18.38% | 441 / 432 / 434 / 159.1 | 50.9% (55.5%; 2.77×) | 49.9% (54.3%; 2.71×) | 50.1% (54.6%; 2.73×) |
| September | 4,324 / 865 / 24.12% | 490 / 482 / 482 / 208.6 | 56.6% (47.0%; 2.35×) | 55.7% (46.2%; 2.31×) | 55.7% (46.2%; 2.31×) |
| October | 4,364 / 873 / 24.04% | 452 / 430 / 442 / 209.8 | 51.8% (43.1%; 2.15×) | 49.3% (41.0%; 2.05×) | 50.6% (42.1%; 2.11×) |
| November | 4,344 / 869 / 32.14% | 577 / 575 / 583 / 279.3 | 66.4% (41.3%; 2.07×) | 66.2% (41.2%; 2.06×) | 67.1% (41.8%; 2.09×) |

Prevalence rose from about 18% in July–August to 32.14% in November. Precision therefore increased in November even as lift declined, so raw precision across months should not be read as stable policy quality. Model C led RFM in each month/capacity cell. Frequency matched or exceeded Model C in some cells, especially at 10% in September and October and 20% in November.

## Policy overlap and repeated selections

Pooled across month-specific lists, Model C overlapped with RFM in 88.7%, 87.9% and 90.5% of its selected snapshots at 5%, 10% and 20%, respectively (Jaccard 0.797, 0.784, 0.827). Model C overlapped with frequency in 86.9%, 85.9% and 87.2% (Jaccard 0.769, 0.754, 0.773). A uniform random list would be expected to overlap Model C by approximately its capacity share: 5%, 10% or 20%; no random customer identities were generated.

Independent monthly targeting would repeatedly select many customers. At 10% capacity, Model C produced 2,170 customer-month selections across 598 distinct customers, with 498 selected in multiple months (some in all five). Frequency produced 2,170 selections across 540 distinct customers, with 481 selected multiple times. At 20%, Model C produced 4,336 selections across 1,205 customers, with 1,008 selected multiple times. These are retrospective repeated selections, not actual contacts; a campaign needs an approved contact-frequency/suppression rule.

## Customer-cluster uncertainty

We used 2,000 paired customer-cluster bootstrap replicates (PCG64 seed `20261112`). Each replicate samples the 4,999 customer trajectories with replacement, applies customer multiplicity to all that customer's monthly rows, recomputes each month's integer capacity and ranked selections, and compares pooled snapshot-weighted metrics. All 2,000 replicates were valid. Intervals are percentile 95% intervals conditional on the fixed historical period; they do not account for future-season variation. Random policy is its analytical expectation, so finite random-list draw variability is not included.

| Capacity | Model C minus policy | Precision difference, 95% interval | Capture difference, 95% interval |
| --- | --- | --- | --- |
| 5% | RFM | +3.50 pp [ +1.67, +5.44 ] | +0.75 pp [ +0.36, +1.17 ] |
|  | Frequency | +1.47 pp [ −0.09, +3.21 ] | +0.31 pp [ −0.02, +0.68 ] |
|  | Random expectation | +58.75 pp [ +55.83, +61.61 ] | +12.54 pp [ +11.89, +13.22 ] |
| 10% | RFM | +2.12 pp [ +0.79, +3.26 ] | +0.90 pp [ +0.34, +1.37 ] |
|  | Frequency | +0.55 pp [ −0.50, +2.17 ] | +0.24 pp [ −0.21, +0.91 ] |
|  | Random expectation | +45.86 pp [ +42.69, +48.79 ] | +19.54 pp [ +18.37, +20.65 ] |
| 20% | RFM | +1.31 pp [ +0.51, +1.80 ] | +1.12 pp [ +0.43, +1.53 ] |
|  | Frequency | +0.69 pp [ −0.28, +1.26 ] | +0.59 pp [ −0.23, +1.08 ] |
|  | Random expectation | +31.39 pp [ +29.41, +32.97 ] | +26.73 pp [ +25.28, +27.90 ] |

The Model C versus frequency intervals cross zero at all capacities: this sample does not distinguish their pooled targeting precision/capture. The Model C versus RFM intervals are positive in this bootstrap. These exploratory intervals are not confirmatory tests, and the 2011 holdout was already examined.

## Interpretation and limits

Model C ranks purchasers better than RFM by a small pooled margin and is not clearly better than the transparent 365-day frequency rule. That simple rule captures most of the observed purchasing concentration, so its low complexity may be attractive if an owner later prioritizes operational simplicity. At 20% capacity all ranked policies capture about 46% of positive customer-months; at 5% they capture about 17%, with higher precision. This is a capacity/coverage tradeoff, not incremental customer response.

Historical purchase capture is not treatment effect. The data have no randomized CRM treatment assignment, exposure, contact costs, incentives or contribution-margin accounting. No policy can be declared commercially profitable or selected as the causal winner from these results. A contemporaneous customer-randomized campaign with a control group is required to measure incremental purchases and value.

## Implementation, validation and outputs

Added `src/monthly_targeting_policies.py` and `tests/test_monthly_targeting_policies.py`. The analysis verifies the frozen M2 input hashes and mature holdout counts, reuses the saved predictions, and writes aggregate JSON plus customer-level monthly selections outside the repository. No model was fitted and no M2 artifact was modified.

Eight focused targeting tests passed. The full repository suite passed **117 tests with 1 existing skip** (the Spark test requiring Java). Tests cover capacity rounding, deterministic ties, unique monthly selections, metric accounting, random expectations, bootstrap multiplicity/reproducibility, and snapshot-weighted pooling.

External outputs are under `<LOCAL_DATA_DIR>/m3_002_targeting_outputs_final/`:

- Aggregate JSON SHA-256: `5e9558f7d26a144587325d6465164bed7f6ce1718facc35f0e7a6cd6c15b509d`
- Customer-selection Parquet SHA-256: `bd94ff0bf15f07c715921cea8a2d049a2ad03b9e4d352faba969d6b9392d5d49`
- Output manifest SHA-256: `7422a915e6d78f556494867946776dae70a52df3ddb0f73a8e24b37c607358fe`

Reproduce from the repository root, setting `LOCAL_DATA_DIR` to the verified local source directory and using a new output directory:

```sh
.venv/bin/python src/monthly_targeting_policies.py \
  --dataset "$LOCAL_DATA_DIR/monthly_customer_snapshots_m2_004.parquet" \
  --source-manifest "$LOCAL_DATA_DIR/monthly_customer_snapshots_m2_004.parquet.manifest.json" \
  --predictions "$LOCAL_DATA_DIR/m2_008_baseline_outputs/monthly_purchase_baselines_m2_008_test_predictions.parquet" \
  --baseline-run-manifest "$LOCAL_DATA_DIR/m2_008_baseline_outputs/monthly_purchase_baselines_m2_008_run_manifest.json" \
  --output-dir "$LOCAL_DATA_DIR/m3_002_targeting_outputs_reproduction"
```
