# M2-008 — Established-Customer Baseline Results

## Summary

The predeclared Model C met the primary criterion on the fixed July–November 2011 chronological holdout: snapshot-weighted ROC-AUC **0.76599**, customer-clustered percentile 95% CI **[0.75646, 0.77490]**. The lower endpoint is above 0.50. The RFM-only model also discriminated well (AUC 0.75995). Adding the other eight predictors produced a modest descriptive improvement; no inferential Model C-versus-B test was predeclared or conducted.

This is predictive association in one historical holdout, not evidence that a CRM intervention will cause additional purchases. It does not establish deployment readiness or generalisation beyond this period.

## Protocol, source, and partitions

Execution verified the frozen protocol hash **`790d5377d4817ea3148b5a290bd9d24cfa5c3e3866a6b89f90418aa1b748e7b4`** before fitting. The protocol file was not changed.

| Provenance item | SHA-256 |
| --- | --- |
| Corrected M2-004 Parquet | `44c580a83bea993fd0e2f8df8a03bb7aa2f11e64085671ea2ed78c9e28e952a8` |
| Dataset manifest | `3d7ee78afa96a1d4abe7ee8f7762a994e652bc5c799b892d227f56be03c96a13` |
| Snapshot builder | `58f29d2780f541c591312c8d7773815b28d3d828c4be2adea5994c47c8cfa82b` |

Training and test rows were selected only from the manifest's `evaluation_partition`, and matched the expected counts:

| Partition | Snapshots | Customers | Positive | Negative | Prevalence |
| --- | ---: | ---: | ---: | ---: | ---: |
| Training, Jan–Jun 2011 | 25,647 | 4,808 | 4,573 | 21,074 | 17.8305% |
| Test, Jul–Nov 2011 | 21,672 | 4,999 | 5,092 | 16,580 | 23.4958% |

There are 4,265 customers in both partitions. Only fully mature labels were used. The five-month test prevalence exceeds training prevalence by **5.665 percentage points**. The cohort, strict 365-day history definition, 30-day outcome, and chronological split were unchanged.

## Models and preprocessing

- **A — constant:** every test probability is training prevalence, `4,573 / 25,647 = 0.17830545`.
- **B — RFM:** the three protocol-ordered recency, 365-day occasion-count, and 365-day gross-merchandise features.
- **C — full:** all 11 verified `FEATURE_COLUMNS`, in protocol order.

For B and C, all allowlisted predictors were transformed with `log1p`; transformed missing values were imputed with training-only medians; centering and population standardisation were fitted on training only. Logistic regression used L2, `C=1.0`, `lbfgs`, intercept, `tol=1e-8`, `max_iter=5000`, and seed `20261112`. No class weighting, tuning, feature selection, test recalibration, or threshold selection was used. Both fits converged: B in 12 iterations and C in 86. Coefficients below are on the standardized `log1p` scale.

| Feature | Model B coefficient | Model C coefficient |
| --- | ---: | ---: |
| `days_since_last_qualifying_purchase` | -0.2253 | -0.0296 |
| `qualifying_purchase_occasions_365d` | 0.7391 | 0.0156 |
| `qualifying_purchase_dates_365d` | — | 0.8823 |
| `qualifying_gross_merchandise_365d` | 0.2440 | -0.1116 |
| `average_qualifying_basket_value_365d` | — | 0.1872 |
| `average_qualifying_basket_quantity_365d` | — | 0.0533 |
| `average_basket_product_diversity_365d` | — | 0.0537 |
| `qualifying_unique_product_count_365d` | — | -0.0381 |
| `median_interpurchase_interval_days_365d` | — | -0.0055 |
| `qualifying_purchase_occasions_90d` | — | 0.4112 |
| `qualifying_gross_merchandise_90d` | — | -0.1207 |
| **Intercept** | **-1.8468** | **-1.8341** |

## Primary and secondary metrics

| Model | ROC-AUC | Average precision | Brier score | Mean predicted test probability |
| --- | ---: | ---: | ---: | ---: |
| A — constant | 0.50000 | 0.23496 | 0.18296 | 0.17831 |
| B — RFM | 0.75995 | 0.54830 | 0.14968 | 0.17758 |
| C — full 11 | **0.76599** | **0.56595** | **0.14744** | 0.17692 |

Observed test prevalence is 0.23496. Model C's two-sided customer-clustered percentile interval used 2,000 resamples of the 4,999 test customers, seed `20261112`; all **2,000 were valid and zero** were omitted for single-class outcomes. Interval: **[0.75646, 0.77490]**. The predeclared success criterion (lower bound strictly greater than 0.50) **was met**.

Relative to RFM, Model C's AUC was +0.00603, average precision +0.01765, and Brier score lower by 0.00224. These are descriptive differences only. Both logistic models improve the Brier score versus the constant baseline; Model C's mean predicted probability remains 5.80 points below observed test prevalence.

## Calibration

Joint calibration intercept/slope diagnostics were estimated on fixed test predictions and labels, for diagnosis only. Predictions were not adjusted.

| Model | Intercept | Slope | Diagnostic status |
| --- | ---: | ---: | --- |
| A — constant | 0.3473 | Not identifiable | Intercept-only calibration-in-the-large |
| B — RFM | 0.3428 | 0.9321 | Diagnostic only |
| C — full 11 | 0.4114 | 0.9730 | Stationary optimum after optimizer warning; numerical stability checks passed |

The positive intercepts and the fixed-band calibration table indicate systematic underprediction at the test prevalence. The slope estimates are near one, but do not remove that level shift. Calibration bands (mean predicted / observed prevalence) were:

| Probability band | B: n | B: predicted / observed | C: n | C: predicted / observed |
| --- | ---: | ---: | ---: | ---: |
| [0.0, 0.1) | 10,061 | 0.061 / 0.100 | 10,415 | 0.065 / 0.102 |
| [0.1, 0.2) | 5,245 | 0.142 / 0.214 | 5,327 | 0.142 / 0.217 |
| [0.2, 0.3) | 2,582 | 0.246 / 0.318 | 2,344 | 0.244 / 0.323 |
| [0.3, 0.4) | 1,446 | 0.346 / 0.414 | 1,317 | 0.345 / 0.436 |
| [0.4, 0.5) | 858 | 0.447 / 0.514 | 760 | 0.447 / 0.503 |
| [0.5, 0.6) | 605 | 0.546 / 0.608 | 502 | 0.547 / 0.639 |
| [0.6, 0.7) | 385 | 0.648 / 0.766 | 390 | 0.648 / 0.741 |
| [0.7, 0.8) | 288 | 0.745 / 0.858 | 302 | 0.747 / 0.854 |
| [0.8, 0.9) | 113 | 0.845 / 0.858 | 195 | 0.843 / 0.897 |
| [0.9, 1.0] | 89 | 0.938 / 1.000 | 120 | 0.949 / 0.983 |

Model A assigns all rows probability 0.1783: its single occupied band `[0.1,0.2)` contains all 21,672 rows, with observed prevalence 0.235.

## Ranking at fixed capacities

All ties at a probability boundary were included. There were no ties that changed the requested selected row counts in this test.

| Nominal capacity | Model | Selected | Precision | Lift over test prevalence |
| --- | --- | ---: | ---: | ---: |
| 5% | A random-selection expectation | 1,084 | 0.235 | 1.00 |
|  | B — RFM | 1,084 | 0.792 | 3.37 |
|  | C — full 11 | 1,084 | 0.827 | 3.52 |
| 10% | A random-selection expectation | 2,168 | 0.235 | 1.00 |
|  | B — RFM | 2,168 | 0.673 | 2.87 |
|  | C — full 11 | 2,168 | 0.693 | 2.95 |
| 20% | A random-selection expectation | 4,335 | 0.235 | 1.00 |
|  | B — RFM | 4,335 | 0.538 | 2.29 |
|  | C — full 11 | 4,335 | 0.549 | 2.34 |

These are retrospective ranking summaries on the holdout. They are not treatment effects and do not estimate incremental campaign purchases.

## Monthly test performance

| Month | Snapshots | Customers | Positives | Prevalence | AUC A | AUC B | AUC C |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2011-07 | 4,314 | 4,314 | 809 | 18.75% | 0.500 | 0.769 | 0.777 |
| 2011-08 | 4,326 | 4,326 | 795 | 18.38% | 0.500 | 0.807 | 0.812 |
| 2011-09 | 4,324 | 4,324 | 1,043 | 24.12% | 0.500 | 0.767 | 0.773 |
| 2011-10 | 4,364 | 4,364 | 1,049 | 24.04% | 0.500 | 0.737 | 0.742 |
| 2011-11 | 4,344 | 4,344 | 1,396 | 32.14% | 0.500 | 0.745 | 0.751 |

Each month has both outcome classes. The November prevalence increase is material. The test has only one short later-season period, and monthly rows are not independent time origins.

## Predictor and predicted-probability drift

Values below are raw feature summaries (median and interquartile range); only the median interpurchase interval has missing values. Its missing share is 36.83% in training and 38.13% in test. These are descriptive row summaries, not independent-sample significance tests.

| Predictor | Train median [Q1, Q3] | Test median [Q1, Q3] |
| --- | --- | --- |
| Recency days | 97.44 [39.43, 182.24] | 96.55 [29.51, 234.47] |
| Occasions, 365d | 2 [1, 5] | 2 [1, 4] |
| Purchase dates, 365d | 2 [1, 4] | 2 [1, 4] |
| Gross merchandise, 365d | 660.28 [302.35, 1,611.99] | 642.58 [301.36, 1,552.09] |
| Average basket value, 365d | 286.71 [179.52, 425.35] | 289.04 [180.90, 426.43] |
| Average basket quantity, 365d | 154 [90.74, 260.24] | 156 [91.50, 264.76] |
| Average basket product diversity, 365d | 17.33 [9.75, 27.60] | 17 [9.54, 27.85] |
| Unique products, 365d | 36 [16, 76] | 34 [16, 74] |
| Median purchase interval, 365d | 49 [27, 91] | 51.5 [28, 98] |
| Occasions, 90d | 0 [0, 1] | 0 [0, 1] |
| Gross merchandise, 90d | 0 [0, 383.47] | 0 [0, 409.46] |

Model C mean predicted probability is 17.83% in training resubstitution and 17.69% in test; its test median [Q1, Q3] is 10.55% [6.30%, 21.57%]. Model B's corresponding test summary is 17.76% mean and 11.00% [5.67%, 23.13%]. Training probability summaries are in-sample and are not an unbiased performance estimate. Month-specific test score distributions are retained in the run manifest.

## Interpretation and limits

The RFM features carry substantial predictive ranking information in this fixed holdout: Model B AUC is 0.760 versus the constant comparator's 0.500, with average precision 0.548 against 0.235 test prevalence. The full 11-feature model meets the primary criterion and is modestly better descriptively than RFM on AUC, average precision, Brier score, and the stated capacities. The extra features do not establish a statistically reliable improvement over RFM because that comparison was not the primary hypothesis and no inferential comparison was predeclared.

The clustered interval accounts for repeated snapshots within each of the 4,999 test customers; 4,265 customers also contributed training snapshots. It does not create independent seasonal replications or fully capture uncertainty across future time periods. Test prevalence is 5.67 points above training, rises to 32.14% in November, and both logistic models underpredict the test prevalence. Ranking is stronger than calibration. A single historical holdout cannot establish stable probability thresholds for future CRM use.

The result can justify a carefully designed prospective CRM pilot as a research hypothesis, with random assignment and a contemporaneous holdout to estimate incremental impact. It does not justify targeting as if predicted purchasing were caused by outreach. A pilot should assess incremental qualifying purchases and commercial value, monitor calibration/drift, and preserve customer-level randomization or valid cluster-aware inference.

## Reproducibility and artifacts

The run used Python 3.11.14, NumPy 2.4.4, pandas 3.0.2, SciPy 1.17.1, scikit-learn 1.8.0, and PyArrow 24.0.0. The frozen run manifest records preprocessing statistics, coefficients, convergence, metrics, and hashes.

All model/prediction artifacts are outside Git:

- Models/preprocessing JSON: `<LOCAL_DATA_DIR>/m2_008_baseline_outputs/monthly_purchase_baselines_m2_008_models.json` (SHA-256 `e971ffa7712c56c0a02c1d6157e15e573c5ad6dd24b4f421b165fbf6dc807b3f`)
- Test predictions Parquet: `<LOCAL_DATA_DIR>/m2_008_baseline_outputs/monthly_purchase_baselines_m2_008_test_predictions.parquet` (SHA-256 `facdd36297340138ec23ddbd98bc9cc551776c6bdf635e731ced08cc440626c1`)
- Run manifest: `<LOCAL_DATA_DIR>/m2_008_baseline_outputs/monthly_purchase_baselines_m2_008_run_manifest.json` (SHA-256 `81bb760a60c4d9badd6b3b65baf93086165e5a4c30ec1e9391390b4e30c2e14a`)

Reproduce from the repository root by setting `LOCAL_DATA_DIR` to the verified local source directory and using a new output directory:

```sh
LOCAL_DATA_DIR=/path/to/uci_online_retail_ii
.venv/bin/python src/monthly_purchase_baselines.py \
  --dataset "$LOCAL_DATA_DIR/monthly_customer_snapshots_m2_004.parquet" \
  --manifest "$LOCAL_DATA_DIR/monthly_customer_snapshots_m2_004.parquet.manifest.json" \
  --output-dir "$LOCAL_DATA_DIR/m2_008_baseline_outputs_reproduction"
```

The run stops if the frozen protocol, dataset, manifest, builder, feature order, or expected partitions differ. It refuses to write row-level/model outputs inside the repository or overwrite existing output files. The frozen protocol's model settings were executed without changes. scikit-learn 1.8 emitted a `FutureWarning` that the explicitly protocol-required `penalty="l2"` argument is deprecated for a future release; it did not affect this run and was retained to preserve the frozen configuration.

## Verification

All six focused baseline tests passed. The repository suite completed with **102 tests total; 1 skipped** (the existing Spark test requiring unavailable Java). Coverage includes protocol feature order, train-only preprocessing, deterministic fitting and prediction invariance to altered test labels, customer-cluster bootstrap multiplicity, single-class resample omission, and metric/calibration calculations. The sklearn deprecation warning described above was emitted during tests as well. No model was refit after holdout evaluation, and no test result was used to choose a model or setting.
