# Commercial DS P2 Release 001 — Curated Application Candidate Verification

**Status:** assembled and locally committed; not pushed, published, or released.
**Development source commit:** `8d89a6b6050cfc44f186f6dbf0a3c19ee66a3d7e`.
**Public destination:** `https://github.com/SanSynyster/commercial-retention-analytics`.
**Verified public baseline:** `24852b5bfd99a15003becdf9a792317225ba049e` (`main`, initial public release).
**Local branch:** `release/customer-intelligence-app`.

The development commit was read directly by object ID. No development Git history was copied. The release checkout remote was verified as the exact destination URL above before work began. The baseline tree was clean. The original 28 tracked Phase 1 paths listed below are retained; `README.md` is the only replaced baseline file.

## Included-file manifest

### Existing public Phase 1 files retained

All of these paths remain in the release tree. Other than the root `README.md`, their baseline content is unchanged.

```text
.gitignore
.python-version
LICENSE
README.md
docs/DATA_PROVENANCE.md
docs/recovery/COMMERCIAL_DS_002A_STOCK_CODE_INVENTORY.csv
docs/recovery/COMMERCIAL_DS_002B_CONTRACT_SPECIFICATION.md
docs/recovery/COMMERCIAL_DS_002B_INTEGRATION.py
docs/recovery/COMMERCIAL_DS_002B_TAXONOMY.py
docs/recovery/COMMERCIAL_DS_002B_TAXONOMY_SEED.csv
docs/recovery/COMMERCIAL_DS_002_ANALYSIS.py
docs/recovery/COMMERCIAL_DS_003_PURCHASE_OCCASIONS.py
docs/recovery/COMMERCIAL_DS_003_REVENUE_BRIDGE.py
docs/recovery/COMMERCIAL_DS_003_STAGE_A_REFERENCE_PINS.json
docs/recovery/COMMERCIAL_DS_003_STAGE_B2A_BRIDGE_REFERENCE_PINS.json
docs/recovery/COMMERCIAL_DS_003_STAGE_B2A_REFERENCE_PINS.json
docs/recovery/COMMERCIAL_DS_007B_CUSTOMER_ANALYTICS.py
docs/recovery/COMMERCIAL_DS_007C_VALUE_SEGMENTS.py
docs/recovery/COMMERCIAL_DS_007D_PACKAGE.py
docs/recovery/test_COMMERCIAL_DS_007B_CUSTOMER_ANALYTICS.py
docs/recovery/test_COMMERCIAL_DS_007C_VALUE_SEGMENTS.py
reports/corrected_v2/README.md
reports/corrected_v2/corrected_v2_scientific_results.md
reports/corrected_v2/figures/fig01_mature_90d_repeat_by_month.svg
reports/corrected_v2/figures/fig02_first_observed_cohort_activity.svg
reports/corrected_v2/figures/fig03_qualifying_gross_concentration.svg
reports/corrected_v2/figures/fig04_descriptive_frequency_recency_segments.svg
requirements-minimal.txt
```

### Application, bundles, tests, requirements, and research documents added from the approved development commit

```text
app/README.md
app/streamlit_app.py
app/views/__init__.py
app/views/customer_overview.py
app/views/experiment_feasibility.py
app/views/purchase_propensity.py
app/views/targeting_explorer.py
app_data/customer_overview_v1.json
app_data/propensity_summary_v1.json
app_data/targeting_v1.json
requirements-app.txt
src/crm_pilot_feasibility.py
src/customer_overview_bundle.py
src/customer_overview_metrics.py
src/experiment_feasibility_metrics.py
src/propensity_summary_bundle.py
src/targeting_bundle.py
src/targeting_metrics.py
tests/test_crm_pilot_feasibility.py
tests/test_customer_overview_bundle.py
tests/test_dashboard_app.py
tests/test_experiment_feasibility_page.py
tests/test_propensity_summary_bundle.py
tests/test_purchase_propensity_page.py
tests/test_targeting_bundle.py
docs/research/COMMERCIAL_DS_P2_M1_009_BASELINE_PROTOCOL.md
docs/research/COMMERCIAL_DS_P2_M1_009_BASELINE_RESULTS.md
docs/research/COMMERCIAL_DS_P2_M2_007_BASELINE_PROTOCOL.md
docs/research/COMMERCIAL_DS_P2_M2_008_BASELINE_RESULTS.md
docs/research/COMMERCIAL_DS_P2_M2_012_SEQUENTIAL_CALIBRATION_RESULTS.md
docs/research/COMMERCIAL_DS_P2_M3_002_TARGETING_COMPARISON.md
docs/research/COMMERCIAL_DS_P2_M3_003_INDEPENDENT_TARGETING_REVIEW.md
docs/research/COMMERCIAL_DS_P2_M4_001_CRM_PILOT_DESIGN.md
docs/research/COMMERCIAL_DS_P2_M4_002_CRM_PILOT_FEASIBILITY.md
docs/research/COMMERCIAL_DS_P2_M4_003_INDEPENDENT_FEASIBILITY_REVIEW.md
docs/research/README.md
docs/release/COMMERCIAL_DS_P2_RELEASE_001_VERIFICATION.md
```

`README.md` is replaced with the reviewed M5-006 version. Existing `LICENSE`, `docs/DATA_PROVENANCE.md`, corrected-V2 report/figures and `requirements-minimal.txt` already match the approved candidate content, so their baseline copies are retained. The final local release commit SHA is the `HEAD` containing this report; its exact value is provided in the release completion handoff because a commit cannot contain its own resulting hash.

## Documentation additions

- `docs/research/README.md` lists the included frozen reports and protocols, excluded research modules and private inputs, and explains why historical reproduction may require unavailable files. The application and its tests use only reviewed aggregate bundles. It notes that M4-001's link to excluded `src/monthly_customer_snapshots.py` is intentionally left unchanged to preserve the approved document hash.
- `app/README.md` explains that the historical bundles come from corrected-V2 and M1–M3 approved outputs, their independently pinned content hashes, aggregate-only runtime access, and unavailable rebuild inputs. M4 remains an in-memory hypothetical calculator.

## Excluded content and public-content inspection

No new raw transactions, transaction-level rows, customer identifiers, customer-level prediction records, targeting selection lists, model binaries, private research outputs, credentials, tokens, or machine-specific absolute paths were added. Runtime app modules use the three JSON bundles; tests validate aggregate-only bundle schemas. No external prediction/selection Parquets or private research inputs are included.

The Phase 1 baseline has two CSV files for the public stock-code inventory and taxonomy seed; they are retained unchanged as existing public Phase 1 content, not transaction or customer records. The only `.csv` files are those two taxonomy artifacts. No `.parquet`, `.xlsx`, `.pkl`, `.joblib`, `.onnx`, `.pt`, or `.model` files are in the candidate. `.venv/` is local and ignored; it is not included. The intended new application paths are not ignored, are visible as untracked before staging, and are included in the release commit. A scoped credential/machine-path scan of the application, bundles, reports and documentation found no matching secret material or absolute local paths.

The following are intentionally absent:

- Raw UCI files and ignored `data/raw/`, `data/processed/`, and `data/warehouse/` contents.
- Customer-level feature tables, snapshots, prediction outputs, targeting selections, external model files and research manifests.
- M1/M2/M3 supporting research modules not needed at app runtime, earlier milestone design/review notes, and M5 implementation/review notes.
- Local environments, caches, logs, credentials, and machine-specific outputs.

## Provenance verification

All ten included M1–M4 research documents match the approved development commit byte-for-byte. The M1/M2 source hashes also match the values pinned in the propensity aggregate provenance. The M3 result and independent review documents remain unchanged, and the corrected-V2 report remains the existing public baseline file.

| Included aggregate | SHA-256 | Result |
| --- | --- | --- |
| `app_data/customer_overview_v1.json` | `c2555d79c7b25b7af64cc186400322634748b07c5a5825fc9185a7fda7cdd87c` | Byte-identical to approved source |
| `app_data/propensity_summary_v1.json` | `fa6e5d16f00604accb1b660612de4cfe1033935607b358d3d6f5981fc3b5aa27` | Byte-identical to approved source |
| `app_data/targeting_v1.json` | `56dc435c14c79af1479fa41971089d272ea0f22367a37eca421b3557e3079b2e` | Byte-identical to approved source |

Research document SHA-256 values were computed and compared with `git show 8d89a6b6050cfc44f186f6dbf0a3c19ee66a3d7e:<path>` for every file listed here:

| Document | SHA-256 |
| --- | --- |
| `docs/research/COMMERCIAL_DS_P2_M1_009_BASELINE_PROTOCOL.md` | `d5be6bfefbbbddf8e5f7dfe8a81202cc04c1d18e7480c698aec5211b3c92c3ac` |
| `docs/research/COMMERCIAL_DS_P2_M1_009_BASELINE_RESULTS.md` | `9b48774fa5171e12c3b1658b168440e50a56943298e7c8a785f17de503e01808` |
| `docs/research/COMMERCIAL_DS_P2_M2_007_BASELINE_PROTOCOL.md` | `790d5377d4817ea3148b5a290bd9d24cfa5c3e3866a6b89f90418aa1b748e7b4` |
| `docs/research/COMMERCIAL_DS_P2_M2_008_BASELINE_RESULTS.md` | `3d4668810e9c542e38a666e2b74cfa0341830da51e331a2e0c1fb9a29651d856` |
| `docs/research/COMMERCIAL_DS_P2_M2_012_SEQUENTIAL_CALIBRATION_RESULTS.md` | `f0ced66ed2659d25a1723ba6f64f177a3de950e60548ee1796a9ef5416556508` |
| `docs/research/COMMERCIAL_DS_P2_M3_002_TARGETING_COMPARISON.md` | `d5ad06c24e2d9ccac79d914624ae3f975e044fb2139c3de19c67e376e9d0fc9f` |
| `docs/research/COMMERCIAL_DS_P2_M3_003_INDEPENDENT_TARGETING_REVIEW.md` | `49219c606ffa5e020ad8f6852055bf86cb23a9b105f627fc58d52c6e55fc0547` |
| `docs/research/COMMERCIAL_DS_P2_M4_001_CRM_PILOT_DESIGN.md` | `8a41de51b54eeb9e3e4f9df76bee30b64d2f13eee0c98952653264a8440d7e28` |
| `docs/research/COMMERCIAL_DS_P2_M4_002_CRM_PILOT_FEASIBILITY.md` | `c097778d39147cd4fe690e2b0b73b086ebfefce0bddecccddb0ee56227a6ab45` |
| `docs/research/COMMERCIAL_DS_P2_M4_003_INDEPENDENT_FEASIBILITY_REVIEW.md` | `12a6c7e17b2b88dfd943ec79cd99a8ab5146f6f291815d7021177187cc674f39` |

## Verification commands and results

A new Python 3.11 virtual environment was created in the release checkout. Only `requirements-app.txt` was installed for application verification.

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install --disable-pip-version-check -r requirements-app.txt
.venv/bin/python -m unittest \
  tests.test_customer_overview_bundle \
  tests.test_dashboard_app \
  tests.test_propensity_summary_bundle \
  tests.test_purchase_propensity_page \
  tests.test_targeting_bundle \
  tests.test_experiment_feasibility_page \
  tests.test_crm_pilot_feasibility -v
.venv/bin/python -m unittest discover -s docs/recovery -p 'test_COMMERCIAL_DS_007*.py' -v
.venv/bin/streamlit run app/streamlit_app.py --server.headless true --server.port 8769 --browser.gatherUsageStats false
curl --fail --silent --show-error http://127.0.0.1:8769/_stcore/health
```

Results:

- Application suites and AppTests: **53 tests run, 51 passed, 2 skipped**. Skips require private corrected-V2/M2 rebuild inputs, absent by design. The app, bundle checks, navigation, and all four page views rendered without errors.
- Existing 007 recovery tests: **15 passed**.
- Streamlit startup: successful; health endpoint returned **`ok`**; server stopped after the check.
- All three bundle SHA-256 values and all ten research-document SHA-256 values match the approved source commit.
- Worktree whitespace check passed. The staged check passed for authored files; the ten immutable M1–M4 Markdown documents retain pre-existing trailing spaces used for Markdown hard line breaks. They were excluded from the whitespace-only staged check and remain byte-identical to the approved source. No whitespace was changed in those hash-pinned documents.

## Remaining publication blockers

No technical blocker remains for this local candidate. It is not published. The missing external/private research inputs prevent full historical raw-to-result reproduction but do not affect app runtime; the application is explicitly documented as operating from the pinned reviewed aggregate bundles. No push, pull request, or GitHub release was made.
