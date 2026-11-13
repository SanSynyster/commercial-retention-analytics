# M1-009 — Predeclared Day-21 Baseline Protocol

**Protocol status:** frozen before model fitting and holdout evaluation.  
**Evaluation cutoff:** `2011-07-01 00:00:00` (source-naive timestamp).

## Question and estimand

Assess whether first-day qualifying purchase characteristics rank second-purchase outcomes among customers in the approved 12-month qualifying-purchase acquisition proxy. Each row is a customer who made a first qualifying purchase at `t0`, reached decision time `t0 + 21 days`, and had not made a qualifying purchase on a strictly later calendar date at or before that decision. The label is 1 when the second qualifying purchase occurs in `(decision, decision + 90 days]` (through Day 111), and 0 only when this complete interval is observed with no event.

The acquisition threshold is the verified source's first timestamp (`2009-12-01 07:45:00`) plus 12 calendar months (`2010-12-01 07:45:00`). This is an observed qualifying-history proxy, not verified first-ever acquisition. The canonical customer × invoice occasions and earliest valid qualifying line timestamp rule are unchanged.

## Frozen partitions

- **Training:** 304 customers, 90 positive and 214 negative. Decisions precede the July 1 cutoff, and each complete outcome deadline was at or before the cutoff.
- **Test:** 208 customers, 97 positive and 111 negative. Decisions are at/after the cutoff, and each complete 90-day follow-up is observable through the source boundary.
- **Excluded from fitting and primary evaluation:** the 326 mature outcomes whose decisions were before the cutoff but whose labels matured after it; all immature/unknown outcomes; and all non-primary-eligible customers. No future-matured, partial-horizon, or unknown label enters training.
- The test labels will be evaluated once. The test cohort will not be used for feature selection, tuning, threshold selection, refitting, or recalibration.

## Features and transformations

Use explicit allowlists and only these first-day merchandise characteristics:

- **Model B:** `log1p(first_day_qualifying_gross)`.
- **Model C:** `log1p(first_day_qualifying_gross)`, `log1p(first_day_item_quantity)`, and `log1p(first_day_product_diversity)`.

All inputs must be nonnegative and finite. Apply `log1p`, then standardise each included transformed feature using the corresponding training mean and population standard deviation (`ddof=0`). Apply those frozen training statistics unchanged to test rows. Fail if any training feature has zero variance. Do not include dates/timestamps, weekday, month, occasion count, labels/status/maturity fields, or future information.

## Exactly three models

A. **Constant comparator:** predict the training positive prevalence (`90 / 304`) for every test customer.

B. **Gross-only logistic regression:** unpenalised binomial logistic regression with an intercept and Model B's single standardised feature.

C. **Three-feature logistic regression:** unpenalised binomial logistic regression with an intercept and Model C's three standardised features.

Use a deterministic solver/configuration and fixed convergence tolerance/iteration cap. No feature selection, hyperparameter search, threshold tuning, or model changes after test results are observed. Report coefficients on the standardised log1p scale.

## Evaluation plan

Evaluate the three frozen models once on the 208-customer test partition.

**Primary metric and success rule:** ROC-AUC for Model C. Compute a two-sided 95% percentile interval from 2,000 customer-level bootstrap resamples of the test rows, using fixed seed `20261112`. Each replicate samples 208 customers with replacement. A replicate with only one outcome class has undefined AUC and is omitted; do not redraw it. Report valid and omitted replicate counts. The predeclared criterion is met only if the lower endpoint of the 95% interval is strictly greater than 0.50.

**Secondary descriptive metrics:** gross-only ROC-AUC; point difference `AUC(C) - AUC(B)`; Brier scores for A, B and C (including C versus A); and observed versus mean predicted test prevalence. No confidence interval or inferential claim is planned for the secondary metrics.

Calibration intercept and slope are diagnostic-only summaries for Models B and C. Use the test outcomes to estimate logistic calibration regressions of outcome on the fixed prediction logit (joint intercept and slope); report estimates and mark them unavailable if fitting is numerically unstable or non-identifiable. For Model A, the slope is non-identifiable because predictions are constant; do not report one. These diagnostics do not modify predictions and will not be used to recalibrate, refit, or select a model.

Report test counts, positives, negatives, prevalence, ROC-AUC and Brier score separately for July, August, and September decision months. Mark a monthly AUC unavailable if the month has one outcome class; do not combine months or change the primary test definition.

## Interpretation constraints

The training and test outcome prevalences differ materially in this seasonal, short historical period. The sample is small and uncertainty is expected. Discrimination (ranking) and calibration (probability accuracy) are separate properties. A positive result does not establish deployment readiness or generalisation beyond the evaluated period; a null or weak result is acceptable. No model is trained before this protocol is hashed, and no holdout metric is computed before that freeze.
