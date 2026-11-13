# M2-007 — Established-Customer Baseline Protocol

**Protocol status:** predeclared; no model has been fitted and no test model performance has been calculated.  
**Protocol version:** 1.0  
**Date:** 2026-11-12  
**Foundation commit:** `22f3a542d00c2d6a8fce7ba79793c7447ba60332`

## Research question and estimand

Among established customers eligible for a monthly snapshot, can the previous 365 days of qualifying purchase behaviour rank whether the customer makes at least one qualifying purchase in the next 30 days? This is an observational prediction estimand. It does not estimate CRM treatment effect, incremental purchases, or campaign value.

Each row is one eligible customer-month at decision timestamp `T`, 00:00 on the first day of the snapshot month. Predictors use qualifying occasions in `[T − 365 days, T)`; the label is any qualifying purchase in `[T, T + 30 days)`. Only fully mature labels 0/1 are eligible for fitting and primary evaluation. Unknown and partially followed rows are excluded from both partitions. The 365-day population rule, strict source coverage, canonical purchase definitions and December 2010 exclusion remain unchanged.

## Frozen data and partitions

Use only the corrected local M2-004 dataset and its matching manifest, kept outside Git:

- Dataset: `<LOCAL_DATA_DIR>/monthly_customer_snapshots_m2_004.parquet`
- Dataset SHA-256: `44c580a83bea993fd0e2f8df8a03bb7aa2f11e64085671ea2ed78c9e28e952a8`
- Manifest: `<LOCAL_DATA_DIR>/monthly_customer_snapshots_m2_004.parquet.manifest.json`
- Manifest SHA-256: `3d7ee78afa96a1d4abe7ee8f7762a994e652bc5c799b892d227f56be03c96a13`
- Snapshot builder SHA-256: `58f29d2780f541c591312c8d7773815b28d3d828c4be2adea5994c47c8cfa82b`
- Source pins: V1 `43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d`; corrected V2 `32569a66f3842a82b0d8c4d63b263c5d98a76bde5d1f65c6c01bf457e541d3a9`; taxonomy `7b4611c78ca22d108c2616076c84b7c1db2efb8453ee9a32faceb027bb181e4e`.

Select rows only by the stored `evaluation_partition`, after checking the partition and label invariants against the manifest:

| Partition | Decision months | Snapshots | Customers | Positive | Negative | Prevalence |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Training | 2011-01 to 2011-06 | 25,647 | 4,808 | 4,573 | 21,074 | 17.8305% |
| Chronological test | 2011-07 to 2011-11 | 21,672 | 4,999 | 5,092 | 16,580 | 23.4958% |

The training-label availability cutoff is `2011-07-01 00:00:00`: training decision times precede it and each complete outcome endpoint is at or before it. Test decisions are at or after it and have mature follow-up. Do not add unknown/immature outcomes, use random splitting, or make the primary split customer-disjoint. The same customer may have earlier training and later test snapshots; the test uncertainty procedure below accounts for test customers' repeated rows.

## Predictor allowlists

Use the manifest’s `feature_columns` and `src/monthly_customer_snapshots.py::FEATURE_COLUMNS` as the authoritative ordered list. The protocol asserts exact equality before fitting.

**Model B, RFM (exact order):**

1. `days_since_last_qualifying_purchase`
2. `qualifying_purchase_occasions_365d`
3. `qualifying_gross_merchandise_365d`

**Model C, full model (exact order):**

1. `days_since_last_qualifying_purchase`
2. `qualifying_purchase_occasions_365d`
3. `qualifying_purchase_dates_365d`
4. `qualifying_gross_merchandise_365d`
5. `average_qualifying_basket_value_365d`
6. `average_qualifying_basket_quantity_365d`
7. `average_basket_product_diversity_365d`
8. `qualifying_unique_product_count_365d`
9. `median_interpurchase_interval_days_365d`
10. `qualifying_purchase_occasions_90d`
11. `qualifying_gross_merchandise_90d`

Model A has no feature inputs. Exclude all other dataset columns, particularly customer identifiers, snapshot/calendar timestamps, `snapshot_month`, first-observed metadata, labels, outcome status/maturity, partition fields, and coverage fields. `snapshot_month` is retained only for temporal summaries. No target-derived or future information is allowed.

## Frozen preprocessing

Apply this deterministic preprocessing independently to Model B and Model C:

1. Confirm input columns appear in the allowlisted order. Treat all predictors as numeric and nonnegative; reject non-finite observed values or negative values before transformation.
2. Apply `log1p(x)` to every allowlisted predictor. For missing inputs, preserve missingness through the transform.
3. Fit a median imputer on transformed **training** values only, then apply those fixed medians to test. This handles a missing recency value without consulting future rows; the approved eligibility and snapshot builder should ordinarily make recency complete. The interval feature is legitimately null when fewer than two qualifying purchase dates occur in the 365-day window. Do not add missingness indicators, new predictors, or full-dataset imputation statistics.
4. Fit centering and population standard deviation (`ddof=0`) on the imputed transformed training data only. Apply those fixed statistics unchanged to test. For a zero-variance training column, use scale 1 (resulting training values are zero); record this condition and do not refit or remove the feature after seeing test results.
5. Record imputation medians, transformed means/scales, and any constant training columns in the run manifest. No preprocessing decision is made from test outcomes.

This applies `log1p` to recency, all counts, gross merchandise, basket summaries, product diversity, and interval days. The monetary fields retain the canonical **gross merchandise** meaning and are not net revenue or profit. No train/test row is used to fit parameters for the other partition.

## Exactly three models

**Model A — constant probability.** Predict the training prevalence `4,573 / 25,647 = 0.17830545482902485` for every test snapshot. Its ROC-AUC is 0.50 by the conventional tie rule; it has no meaningful risk ranking for capacity targeting. This is the no-information probability/Brier baseline.

**Model B — RFM logistic regression.** Fit an intercept and L2-regularised binomial logistic regression on the three RFM predictors above after the frozen preprocessing.

**Model C — full logistic regression.** Fit an intercept and L2-regularised binomial logistic regression on all 11 predictors above after the frozen preprocessing.

For B and C use scikit-learn `LogisticRegression(solver="lbfgs", penalty="l2", C=1.0, fit_intercept=True, class_weight=None, tol=1e-8, max_iter=5000, random_state=20261112)`. `C=1.0` is fixed in advance; there is no parameter search, feature selection, class reweighting, threshold tuning, or training-only validation. With `lbfgs`, the result is deterministic; the fixed seed is retained for reproducible API configuration. Verify finite coefficients and an intercept, and verify convergence (`n_iter_ < max_iter`). If either fit fails convergence or has non-finite parameters, stop and report the failure; do not change solver/settings after test evaluation. Report coefficients on the standardized log1p scale.

The three models are fitted once on the approved training rows. Generate each test probability once. Do not refit, recalibrate, select features, choose settings, or choose decision thresholds from test performance.

## Primary endpoint and hypothesis

The sole primary endpoint is snapshot-weighted ROC-AUC for Model C on the 21,672 mature chronological test snapshots.

- Null reference: `AUC = 0.50` (chance-level ranking).
- Primary comparison: Model C versus that chance-level reference.
- Success criterion: the lower endpoint of the two-sided 95% customer-clustered percentile bootstrap interval is **strictly greater than 0.50**.

This is a predeclared criterion for evidence of above-chance discrimination in this test period. It is not a test of Model C versus Model B, and it does not establish operational or causal value.

## Customer-clustered bootstrap

Use **2,000** bootstrap replicates and fixed seed **20261112**, with NumPy `Generator(PCG64(20261112))`.

1. Define the test resampling frame as the 4,999 unique test customer clusters, with cluster IDs sorted deterministically before sampling.
2. For each replicate, draw 4,999 customer clusters with replacement. Include every test customer-month row belonging to each selected cluster. If a cluster is sampled multiple times, give all its rows the corresponding multiplicity weight. This preserves within-customer dependence and the full repeated-snapshot pattern.
3. Compute Model C ROC-AUC over the resampled snapshots using those multiplicity weights. Do not resample individual customer-month rows independently.
4. If a replicate has only one weighted outcome class, its AUC is undefined: omit that replicate, do not redraw it, and report valid and omitted counts.
5. Use the 2.5th and 97.5th percentiles of valid replicate AUCs as the two-sided 95% percentile interval. If no valid replicates remain, report the interval as unavailable and the primary criterion as not established. The point estimate is the unweighted ROC-AUC on all test snapshots.

The replicate draws and any helper ordering must be deterministic. Customer bootstrap intervals quantify customer resampling uncertainty in this fixed historical period; they do not create independent seasonal periods. Snapshot and outcome-window overlap remain limitations.

## Secondary and diagnostic metrics

Calculate these once on the fixed test predictions; these are secondary/descriptive and do not alter the primary decision:

- **Average precision / PR-AUC** for Models A, B and C (Model A's constant score yields prevalence under average-precision tie handling).
- **Brier score** for Models A, B and C; compare B/C against Model A descriptively.
- **Calibration:** for B and C, use the existing `src/day21_baseline.py::calibration_diagnostic()` on fixed test probabilities and labels to estimate a joint logistic calibration intercept and slope. It is diagnostic only and cannot adjust predictions. For A, the slope is non-identifiable with constant predictions; report calibration-in-the-large as `logit(test prevalence) − logit(training prevalence)` and slope as not identifiable. If the diagnostic reports an unstable or non-identifiable fit, report it as unavailable without substituting another fit.
- **Calibration bands:** use fixed-width probability bands `[0,.1), [.1,.2), …, [.9,1]`; report row count, mean predicted probability, and observed prevalence. Empty bands remain empty; do not merge bands after seeing results.
- **Targeting capacity summaries:** for B and C, rank test rows by predicted probability and report precision and lift over test prevalence among the top 5%, 10% and 20%. Use `ceil(capacity × test-row-count)` as the nominal row count. Include all ties at the boundary and report actual selected count/capacity. These are ranking summaries only. Model A has no ranking; report random-selection precision equal to test prevalence and lift 1, not an identifier-based pseudo-ranking.
- **Month-level reporting:** for July–November 2011, report eligible test rows, unique customers, positives, negatives and prevalence. Report monthly ROC-AUC for each model only when both outcome classes are present; Model A's AUC is 0.50 when estimable. Monthly metrics are descriptive and do not redefine the primary endpoint.

No test-derived calibration correction, threshold, band boundary, or capacity is used to refit or alter any model.

## Temporal and predictor drift reporting

Report the fixed training/test prevalence difference and the monthly test prevalence table. For each of the 11 raw predictors, report training and test missing share, median, and interquartile range. These are descriptive comparisons of repeated customer-month rows; do not use row-level p-values as if snapshots were independent, and do not use the differences to select or remove predictors.

Report predicted probability median and interquartile range on training and test for B/C, clearly labelling training predictions as **in-sample/resubstitution** and test predictions as out-of-time. Also report test probability summaries by month. This comparison is descriptive; no test recalibration follows from it. Seasonal distribution shift, repeated customers, and overlapping outcome windows must be acknowledged.

## Interpretation constraints

Discrimination, probability calibration, and operational ranking are distinct. The primary result concerns only discrimination in the July–November 2011 mature test period. The training and test prevalences differ (17.83% versus 23.50%); this is a short seasonal holdout with repeated customer clusters, not multiple independent time origins. No result establishes causal CRM uplift, deployment readiness, or generalisation beyond this evaluated period. A weak or null result is scientifically acceptable.

The M2-001 feasibility work reported outcome prevalence by month, and M2-005 independently verified the cohort and aggregate outcome counts. Those are known design facts. No test predictor–outcome associations, model fits, or performance results were inspected to choose this protocol's transformations or settings.

## Reproducibility and outputs

Use Python 3.11.14 and the repository-pinned versions: NumPy 2.4.4, pandas 3.0.2, SciPy 1.17.1, scikit-learn 1.8.0, and PyArrow 24.0.0. Read the Parquet using PyArrow/pandas and verify its checksum plus manifest checksum before selecting partitions. Record exact runtime versions, protocol SHA-256, dataset/manifest hashes, selected row counts, feature order, transformed training medians/means/scales, model parameters/convergence, coefficients, bootstrap seed/valid/omitted counts, and output hashes.

Planned M2-008 artifacts are an aggregate-only results report under `docs/research/` and a machine-readable run manifest. Any row-level prediction output, if retained for reproducibility, stays under `<LOCAL_DATA_DIR>` outside Git; do not publish customer IDs or snapshot predictions. The protocol SHA-256 must be computed from this finalized file and recorded in the run manifest before the first fit. Any protocol amendment after hashing requires a new dated protocol and must occur before fitting/evaluation.

## Stop conditions

Before fitting, stop and report if the dataset or manifest hash differs, if the feature list/order differs, if the prescribed partitions/counts differ, if labels are not all fully mature 0/1, if any prohibited column enters a model matrix, or if training-only preprocessing cannot be fitted. Do not repair discrepancies by changing cohort, labels, split, features, or model settings in response to test results.
