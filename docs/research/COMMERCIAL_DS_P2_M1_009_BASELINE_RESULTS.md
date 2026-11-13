# M1-009 — Predeclared Day-21 Baseline Results

## Protocol and execution

The protocol was written and hashed before fitting or evaluating the holdout. SHA-256:

`d5be6bfefbbbddf8e5f7dfe8a81202cc04c1d18e7480c698aec5211b3c92c3ac`

The runner verifies this hash before loading partitions for the experiment. The 12-month qualifying-history proxy, exact Day-21 decision and `(decision, Day 111]` outcome, July 1, 2011 split, feature lists, metrics and bootstrap rule are frozen in [the protocol](COMMERCIAL_DS_P2_M1_009_BASELINE_PROTOCOL.md).

Exactly three predeclared predictions were evaluated once: training-prevalence constant comparator, gross-only unpenalised logistic regression, and three-feature unpenalised logistic regression. Both logistic models were fitted only on the 304 mature labels available at the cutoff. Unknown labels, partial-horizon positives and the 326 pre-cutoff labels that matured later were not used for training. Test comprises 208 fully mature later decisions. No tuning, threshold selection, refitting or recalibration was performed.

## Results

| Model | Test ROC-AUC | Brier score | Mean predicted positive rate | Calibration diagnostic |
| --- | ---: | ---: | ---: | --- |
| A. Training-prevalence constant | 0.500 | 0.2779 | 0.2961 | Slope not identifiable for constant predictions |
| B. Gross spend only | 0.5439 | 0.2761 | 0.3033 | Intercept 0.112; slope 0.295 |
| C. Three features (primary) | **0.5189** | **0.2743** | 0.3091 | Not stably estimable with the predeclared diagnostic optimizer |

Test observed prevalence was `97 / 208 = 0.4663`; training prevalence was `90 / 304 = 0.2961`, a **17.03 percentage-point increase**. Each model's mean predicted prevalence is materially below the observed test rate. Model C's Brier score is 0.00359 lower than the constant comparator's; this small probability-score difference coexists with weak discrimination and is not evidence of reliable calibration. Calibration diagnostics are summaries only and do not alter the predictions.

**Primary Model C 95% customer-bootstrap interval:** ROC-AUC `0.5189`, percentile interval **[0.4410, 0.5963]**. All 2,000 requested resamples contained both classes; none were omitted. Seed: `20261112`.

**Predeclared success criterion:** **not met**. The lower interval bound (0.4410) is not greater than 0.50.

Gross-only ROC-AUC was 0.5439. The descriptive difference `AUC(C) − AUC(B)` was **−0.0250**. It is not an inferential comparison and does not justify selecting gross-only after seeing the test result.

## Coefficients

Unpenalised logistic coefficients are on training-standardised `log1p` features. Scaling used training data only (`ddof=0`).

| Model / term | Coefficient |
| --- | ---: |
| B intercept | −0.8721 |
| B: `log1p(first_day_qualifying_gross)` | 0.1719 |
| C intercept | −0.8812 |
| C: `log1p(first_day_qualifying_gross)` | −0.0883 |
| C: `log1p(first_day_item_quantity)` | 0.2253 |
| C: `log1p(first_day_product_diversity)` | 0.1427 |

Convergence took 6 iterations for B and 12 for C. The sign change for gross spend after adding correlated basket measures is descriptive of this small fitted sample and should not be interpreted causally.

## Monthly test descriptives

| Decision month | n (+ / −) | Observed prevalence | AUC A / B / C | Brier A / B / C |
| --- | ---: | ---: | ---: | ---: |
| July | 78 (31 / 47) | 0.397 | 0.500 / 0.548 / 0.551 | 0.250 / 0.250 / 0.245 |
| August | 101 (55 / 46) | 0.545 | 0.500 / 0.502 / 0.444 | 0.310 / 0.306 / 0.309 |
| September | 29 (11 / 18) | 0.379 | 0.500 / 0.581 / 0.657 | 0.242 / 0.243 / 0.232 |

Monthly values are descriptive only. September is especially small; no monthly result was used to select a model.

## Interpretation and limitations

The three-feature model's ranking is only slightly above chance at the point estimate, and its interval includes values below and above chance. The gross-only point AUC is higher, but it also has no uncertainty interval in this predeclared experiment and should not be selected post hoc. Together these results suggest **limited predictive signal in these first-day characteristics under this split**, with substantial uncertainty.

The observed test prevalence increased from 29.6% in training to 46.6% in testing, with month-to-month variation. This seasonal/calendar shift and small sample limit statistical precision. ROC-AUC measures ranking; Brier score and calibration diagnostics concern probability accuracy. The logistic-model probabilities underpredict the aggregate test prevalence, and Model C's calibration regression did not yield a stable estimate under the frozen diagnostic procedure. No recalibration was attempted.

This is a historical, short-period baseline, not deployment evidence. It supports no claim of deployment readiness or generalisation beyond the evaluated period. The result is scientifically acceptable as a weak/null baseline and argues against more elaborate modelling on the same split without a stronger data basis or a new predeclared design.

## Verification and reproducibility

Focused tests passed: **5 baseline tests** covering feature allowlists, training-only standardisation, exact partition selection, exclusion of unavailable/unknown labels, metric calculation, bootstrap reproducibility and single-class resample accounting; plus **18 Day-21 cohort tests**. Total: **23 passed**. The protocol hash was rechecked after execution and matched.

Environment: Python 3.11.14, pandas 3.0.2, scikit-learn 1.8.0, SciPy 1.17.1; the single evaluation ran at `2026-11-12T00:44:49Z`. Scikit-learn emitted a `penalty=None` future-deprecation warning, but both unpenalised fits converged (6 and 12 iterations); the recorded version/configuration is required to reproduce this run. The source cohort remains the external M1-007 Parquet with the verified corrected-V2 hashes in its manifest. The experiment produced aggregate results only; no per-customer predictions or fitted model artifact were retained.

Run the frozen experiment from the repository root with:

```sh
.venv/bin/python -m src.day21_baseline \
  --cohort /path/to/external/day21_customer_cohort_m1_007.parquet \
  --protocol docs/research/COMMERCIAL_DS_P2_M1_009_BASELINE_PROTOCOL.md
```

## Erratum — 2026-11-12 (M1-010 independent review)

This dated correction supersedes the earlier Model C calibration diagnostic above. The original recorded value/status (“not stably estimable”) is retained as the result of the frozen run; the corrected diagnostic was independently verified by M1-010 after that experiment. **Model C calibration intercept is 0.172 (approx. SE 0.45) and slope is 0.376 (approx. SE 0.53).**

The original `calibration_diagnostic()` treated `fit.success == False` as a failure. BFGS returned a precision-loss warning near `(0.1722, 0.3758)`, although the score/gradient was approximately `2e-8` and the solution was a stationary optimum with a finite, well-conditioned information matrix. The diagnostic was therefore estimable; the optimizer status had been classified too strictly. No baseline experiment was rerun for this correction. The primary ROC-AUC, bootstrap interval, Brier scores, coefficients, predictions and run provenance remain unchanged.

**Holdout disclosure:** Before the M1-009 protocol was frozen, the M1-008 independent review had examined test outcome prevalence overall, by decision month, and by first-day-gross-spend third. The test set was therefore not entirely unseen. M1-010 found no test-driven tuning or model selection: the descriptive look did not lead to tuning against the holdout, selecting a model, or changing the predeclared success rule. It does qualify the protocol's statement that no holdout metric had been examined before freeze; the frozen protocol file and its hash remain unchanged as the contemporaneous pre-fit record.

The scientific conclusion is unchanged: Model C ROC-AUC is 0.519 with 95% bootstrap interval `[0.441, 0.596]`, so the predeclared success criterion was not met. The result is inconclusive rather than evidence that no signal exists. The corrected calibration slope remains imprecise, and this historical test does not establish deployment readiness or generalisation beyond the evaluated period.
