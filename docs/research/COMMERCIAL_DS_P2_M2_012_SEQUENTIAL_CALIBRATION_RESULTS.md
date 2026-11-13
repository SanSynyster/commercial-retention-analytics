# M2-012 — Sequential Intercept Calibration and Temporal Robustness

## Summary

The frozen Model B and C predictions were verified against the saved coefficients and training preprocessing; the original M2-008 test metrics reproduced. No purchase model was refit. A sequential, intercept-only adjustment was then evaluated using labels available strictly before each target decision.

The adjusted Model C had a lower pooled September–November Brier score by **0.00447** (adjusted minus raw), with a customer-clustered percentile interval of **[-0.00553, -0.00340]**. This is exploratory evidence on the previously examined holdout, not independent confirmation. Mean predicted probability rose from 17.76% to 19.68% against 26.76% observed prevalence; substantial underprediction remained. The adjustment improved the risk-scale calibration gap in each of the three months and did not change within-month rankings or capacity selection.

## Data and historical label availability

Verified inputs were the M2-004 dataset (SHA-256 `44c580a83bea993fd0e2f8df8a03bb7aa2f11e64085671ea2ed78c9e28e952a8`), its manifest (`3d7ee78afa96a1d4abe7ee8f7762a994e652bc5c799b892d227f56be03c96a13`), M2-008 test predictions (`facdd36297340138ec23ddbd98bc9cc551776c6bdf635e731ced08cc440626c1`), saved model coefficients/preprocessing (`e971ffa7712c56c0a02c1d6157e15e573c5ad6dd24b4f421b165fbf6dc807b3f`) and baseline run manifest (`81bb760a60c4d9badd6b3b65baf93086165e5a4c30ec1e9391390b4e30c2e14a`). The unchanged M2-007 protocol hash is `790d5377d4817ea3148b5a290bd9d24cfa5c3e3866a6b89f90418aa1b748e7b4`.

For a snapshot at decision time `T`, the outcome is `[T, T + 30 days)` and its complete-label maturity timestamp is the exclusive end `T + 30 days`. A historical label was included only when the source marked follow-up complete, its label was binary, and **maturity timestamp `<` target decision timestamp**. Incomplete, unknown, or equality-boundary labels were excluded.

| Target decision | Eligible calibration snapshots | Unique customers | Positive / negative | Pool prevalence | Latest included maturity | Target evaluation snapshots |
| --- | ---: | ---: | ---: | ---: | --- | ---: |
| 2011-09-01 | 8,640 (July–August) | 4,432 | 1,604 / 7,036 | 18.56% | 2011-08-31 00:00 | 4,324 (September) |
| 2011-10-01 | 8,640 (July–August) | 4,432 | 1,604 / 7,036 | 18.56% | 2011-08-31 00:00 | 4,364 (October) |
| 2011-11-01 | 17,328 (July–October) | 4,756 | 3,696 / 13,632 | 21.33% | 2011-10-31 00:00 | 4,344 (November) |

The September window ends exactly at 2011-10-01 00:00, so it is **not** strictly prior to the October decision and was excluded from October's pool. It is strictly prior to the November decision and is then included. The strict earlier-than maturity condition was an owner-specified conservative eligibility rule adopted before calibration execution. Labels whose outcome windows ended exactly at the target decision timestamp would also have been fully observed and could have been included under an inclusive maturity convention. Their exclusion is a design choice, not a correction of information leakage. Each evaluation month had complete follow-up and both outcome classes. The evaluated September–November set contains 13,032 snapshots from 4,796 customers.

## Fixed scorer and calibration method

The saved Model B and C predictions were reconstructed from the frozen feature lists, `log1p`/training-median imputation/training standardisation and stored coefficients. They matched saved predictions within numerical tolerance. Recomputed baseline test ROC-AUC, average precision and Brier scores matched M2-008. The models, preprocessing and July–November predictions were not changed.

At each boundary, a single `delta` was fit by maximum likelihood on only the eligible, prior matured Model C predictions:

`adjusted probability = logistic(logit(raw probability) + delta)`

The slope remained fixed at one. Epsilon `1e-6` was used only for a boundary-safe logit calculation. The fitted offsets were `+0.08328` for September, `+0.08328` for October and `+0.30286` for November. This adjustment preserves each target month's customer ordering. July and August were unadjusted warm-up months.

## Probability calibration results

Calibration-in-the-large below is shown as observed prevalence minus mean predicted probability (risk-scale percentage-point gap). Calibration intercept and slope are the existing joint logistic diagnostic on fixed predictions; they are diagnostic only and did not alter predictions.

| Month | Observed prevalence | Raw C mean prediction | Adjusted C mean prediction | Raw / adjusted Brier | Raw / adjusted risk gap | Raw C intercept / slope | Adjusted C intercept / slope |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| September | 24.12% | 17.44% | 18.40% | 0.15050 / 0.14901 | 6.69 / 5.72 pp | 0.519 / 1.000 | 0.435 / 1.000 |
| October | 24.04% | 17.76% | 18.74% | 0.15694 / 0.15577 | 6.27 / 5.29 pp | 0.259 / 0.853 | 0.188 / 0.853 |
| November | 32.14% | 18.07% | 21.90% | 0.19700 / 0.18625 | 14.06 / 10.24 pp | 0.930 / 0.979 | 0.633 / 0.979 |
| **Pooled Sep–Nov** | **26.76%** | **17.76%** | **19.68%** | **0.16815 / 0.16369** | **9.01 / 7.08 pp** | unavailable / unavailable | 0.435 / 0.949 |

The raw pooled intercept/slope diagnostic was unavailable because the existing numerical stability checks rejected that fit. The adjusted pooled diagnostic reached a stationary optimum after an optimizer warning and passed the stability checks. No diagnostic was used to recalibrate. The paired customer-cluster bootstrap of the pooled Brier difference refit each lagged offset within each resample: **-0.00446**, 95% percentile interval **[-0.00553, -0.00340]**; 2,000/2,000 valid resamples, zero omitted, PCG64 seed `20261112`. This interval is conditional on the same historical months and is not evidence of future-period generalisation.

## Temporal ranking and targeting

The table gives prevalence and month-specific ranking for raw Models B/C. `AP` is average precision. Capacity entries are precision / lift over that month's prevalence. The sequentially adjusted Model C had exactly the same within-month AUC, average precision and capacity selections as raw C; the adjusted capacity figures therefore equal C's figures below.

| Month | Prevalence | B AUC / AP | C AUC / AP | Brier B / C raw / C adjusted | B @5% | C @5% | B @10% | C @10% | B @20% | C @20% |
| --- | ---: | ---: | ---: | --- | --- | --- | --- | --- | --- | --- |
| July | 18.75% | 0.769 / 0.517 | 0.777 / 0.544 | 0.12254 / 0.11946 / — | 75.9% / 4.05 | 80.6% / 4.30 | 63.7% / 3.39 | 64.8% / 3.46 | 46.8% / 2.50 | 48.7% / 2.60 |
| August | 18.38% | 0.807 / 0.551 | 0.812 / 0.570 | 0.11526 / 0.11294 / — | 77.0% / 4.19 | 78.8% / 4.29 | 63.5% / 3.46 | 67.7% / 3.68 | 49.9% / 2.71 | 50.9% / 2.77 |
| September | 24.12% | 0.767 / 0.563 | 0.773 / 0.578 | 0.15239 / 0.15050 / 0.14901 | 79.7% / 3.31 | 82.0% / 3.40 | 67.4% / 2.80 | 69.7% / 2.89 | 55.7% / 2.31 | 56.6% / 2.35 |
| October | 24.04% | 0.737 / 0.513 | 0.742 / 0.529 | 0.15898 / 0.15694 / 0.15577 | 73.5% / 3.06 | 79.0% / 3.29 | 64.3% / 2.68 | 64.5% / 2.68 | 49.3% / 2.05 | 51.8% / 2.15 |
| November | 32.14% | 0.745 / 0.624 | 0.751 / 0.638 | 0.19885 / 0.19700 / 0.18625 | 87.6% / 2.73 | 90.8% / 2.83 | 77.2% / 2.40 | 80.0% / 2.49 | 66.2% / 2.06 | 66.4% / 2.07 |

Across September–November, Model C's pooled AUC changed from 0.7542 raw to 0.7582 adjusted, and average precision from 0.5805 to 0.5857. Different month offsets can reorder rows **across months**, so these pooled changes do not contradict within-month rank preservation and should not be interpreted as improved within-month discrimination. Monthly RFM-to-full AUC differences were small (about 0.005–0.008). Lift declined as prevalence rose, despite high precision among the top-ranked rows. These rankings describe natural purchasing propensity; they do not estimate incremental campaign response.

## Interpretation and limitations

The simple historical intercept update reduced Brier score and the average underprediction gap in each calibrated month, most noticeably in November. It did not eliminate underprediction, and its offset rose substantially only after November's earlier pool incorporated September and October. Only three target months were evaluated after warm-up, the July–November holdout had already been examined, and the data provide no independent later period. The bootstrap handles repeated customers within this timeline but cannot estimate variation across seasons or future periods. Calibration drift may reflect changing prevalence, changing customer mix, or both.

The adjustment does not change within-month rankings. Month-to-month precision/lift varies with outcome prevalence; the full model's advantage over RFM was modest. Neither calibration nor targeting summaries demonstrate CRM treatment benefit or deployment readiness. A future CRM pilot needs randomised controls and contemporaneous monitoring; a confirmatory calibration study needs a newly collected later period with mature labels and a protocol fixed before outcomes are inspected.

## Implementation, tests and outputs

Added `src/monthly_purchase_calibration.py` and `tests/test_monthly_purchase_calibration.py`. The script verifies all frozen input hashes, reconstructs the saved baseline predictions without fitting models, enforces strict label maturity, fits the sequential offsets, calculates monthly and pooled diagnostics, and writes row-level predictions outside the repository.

Seven focused calibration tests passed. The full repository suite passed **109 tests with 1 existing skip** (the Spark test requiring Java). No model artifacts or customer-level outputs were written inside Git. Original M2-007 through M2-009 files were not changed.

External outputs are under `<LOCAL_DATA_DIR>/m2_012_sequential_calibration_outputs/`:

- `m2_012_sequential_calibration_aggregate.json` — SHA-256 `3cafd6ab08543f2f7675768d005598814ea20a1c4c3bedb0efee84542a4ef030`
- `m2_012_sequential_calibration_predictions.parquet` — SHA-256 `cfa19ac9fe393739f9fe0013788539bf2f1b0b61f0c586a8e004fed4d07fcd5c`
- `m2_012_sequential_calibration_manifest.json` — SHA-256 `6f1df402ae4b5d0df62df44b00c31429db85b7f0c39a26bd711cffad510b0c04`

Reproduce by setting `LOCAL_DATA_DIR` to the verified local source directory and choosing a new output directory:

```sh
.venv/bin/python src/monthly_purchase_calibration.py \
  --dataset "$LOCAL_DATA_DIR/monthly_customer_snapshots_m2_004.parquet" \
  --source-manifest "$LOCAL_DATA_DIR/monthly_customer_snapshots_m2_004.parquet.manifest.json" \
  --predictions "$LOCAL_DATA_DIR/m2_008_baseline_outputs/monthly_purchase_baselines_m2_008_test_predictions.parquet" \
  --models "$LOCAL_DATA_DIR/m2_008_baseline_outputs/monthly_purchase_baselines_m2_008_models.json" \
  --run-manifest "$LOCAL_DATA_DIR/m2_008_baseline_outputs/monthly_purchase_baselines_m2_008_run_manifest.json" \
  --output-dir "$LOCAL_DATA_DIR/m2_012_sequential_calibration_outputs_reproduction"
```
