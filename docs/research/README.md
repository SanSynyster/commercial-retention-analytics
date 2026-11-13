# Research documents included with the application

This folder contains the frozen protocols, results and reviews that explain the historical metrics shown in the application and the hypothetical M4 pilot design. These documents are preserved byte-for-byte because the application bundles pin their source hashes.

## Included documents

| Documents | What they support |
| --- | --- |
| `COMMERCIAL_DS_P2_M1_009_BASELINE_PROTOCOL.md`, `COMMERCIAL_DS_P2_M1_009_BASELINE_RESULTS.md` | M1 Day-21 first-observed-customer prediction task and results. |
| `COMMERCIAL_DS_P2_M2_007_BASELINE_PROTOCOL.md`, `COMMERCIAL_DS_P2_M2_008_BASELINE_RESULTS.md`, `COMMERCIAL_DS_P2_M2_012_SEQUENTIAL_CALIBRATION_RESULTS.md` | M2 monthly established-customer prediction and exploratory calibration results. M1 and M2 are different tasks and populations. |
| `COMMERCIAL_DS_P2_M3_002_TARGETING_COMPARISON.md`, `COMMERCIAL_DS_P2_M3_003_INDEPENDENT_TARGETING_REVIEW.md` | Retrospective comparison of purchase capture for the frozen targeting policies, including uncertainty and tie sensitivity. |
| `COMMERCIAL_DS_P2_M4_001_CRM_PILOT_DESIGN.md`, `COMMERCIAL_DS_P2_M4_002_CRM_PILOT_FEASIBILITY.md`, `COMMERCIAL_DS_P2_M4_003_INDEPENDENT_FEASIBILITY_REVIEW.md` | Proposed randomized-pilot design and hypothetical feasibility calculations. No campaign effect was measured. |

The corrected-V2 customer description and attribution are documented in `../DATA_PROVENANCE.md` and `../../reports/corrected_v2/`.

## Supporting material not distributed

The following research code is not included with this application release:

- `src/day21_baseline.py` and `src/monthly_customer_snapshots.py`, used in the M1/M2 prediction work.
- `src/monthly_purchase_calibration.py` and its supporting test, used for the M2-012 calibration analysis.
- `src/monthly_targeting_policies.py` and its supporting test, used for the M3 targeting evaluation.
- Earlier milestone designs, implementation notes and reviews not listed above.

The referenced raw data, customer-level snapshots, external run manifests, calibration inputs, fitted models, predictions, targeting selections and other private aggregate rebuild inputs are not included. Consequently, historical reproduction commands in the included research documents may require files unavailable in this release; the release does not claim end-to-end reproduction of the historical analyses from raw data.

The four-page application operates independently using only the reviewed aggregate JSON bundles in `app_data/`, plus in-memory calculations for hypothetical M4 scenarios. No private research input, customer-level prediction or selection file is needed to run the application and its focused tests.

## M4-001 source link note

The frozen M4-001 design document refers to `../../src/monthly_customer_snapshots.py`, which is not included in this release. The link is intentionally left unchanged so the approved document remains byte-identical. Its relevant M2 context is summarized in the included M2 protocol/results above; the app does not import that research module.
