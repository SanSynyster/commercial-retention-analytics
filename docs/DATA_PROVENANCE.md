# Data Provenance and Attribution

## Source datasets

The project uses two UCI Machine Learning Repository datasets donated by Daqing Chen:

| Dataset | Source | UCI DOI | UCI-stated license |
|---|---|---|---|
| Online Retail | [UCI dataset 352](https://archive.ics.uci.edu/dataset/352/online+retail) | [10.24432/C5BW33](https://doi.org/10.24432/C5BW33) | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) |
| Online Retail II | [UCI dataset 502](https://archive.ics.uci.edu/dataset/502/online+retail+ii) | [10.24432/C5CG6D](https://doi.org/10.24432/C5CG6D) | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) |

Suggested attribution:

> Chen, Daqing. *Online Retail* and *Online Retail II*. UCI Machine Learning Repository. https://doi.org/10.24432/C5BW33 and https://doi.org/10.24432/C5CG6D. Licensed under CC BY 4.0. Data accessed and analyzed with transformations documented in this repository.

The license information above is taken from the UCI dataset pages. Reusers should review the license terms and retain attribution. Dataset attribution does not imply that the original retailer endorses this project.

## Local files and integrity

Raw inputs are excluded from Git by `.gitignore` and must be acquired separately. The reviewed analysis expects these exact local files:

| Local path | Source rows | SHA-256 |
|---|---:|---|
| `data/raw/Online Retail.xlsx` | 541,909 | `43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d` |
| `data/raw/online_retail_II.csv` | 1,067,371 | `32569a66f3842a82b0d8c4d63b263c5d98a76bde5d1f65c6c01bf457e541d3a9` |

The Online Retail II UCI landing page currently offers an XLSX file, while the reviewed audit consumes a CSV. The exact XLSX-to-CSV extraction command and original CSV distribution used for the pinned file are not currently captured as a repository acquisition script. A different conversion may have a different byte hash or parser interpretation. Do not treat an arbitrary CSV conversion as the pinned input; confirm the hashes before running the evidence pipeline.

The corrected-V2 process removes only raw source rows `502938`–`525460` (zero-based, inclusive), the reviewed 22,523-row overlap block. It retains incidental exact repeated rows. Frozen source and category fingerprints are documented in `docs/recovery/`.

Additional pinned artifacts:

| Artifact | SHA-256 |
|---|---|
| Stock-code inventory | `0d507be1e2b062705ba9763507342db71a24663b0d76176b31a2b39e4f66175b` |
| Taxonomy seed | `7b4611c78ca22d108c2616076c84b7c1db2efb8453ee9a32faceb027bb181e4e` |
| Stage A source/classification references | `a96d2e9d5787dc1edd0e5c493e072ede4c342e845921e3242e90742625c8ba49` |
| Stage B2A occasion references | `4cf7b761a1b02cea853dbe577af7dddf8070fe65d0dcdfc7a71e2a064986f433` |
| Stage B2A bridge references | `765ff7a29530b4221ec3ab171fc2ed861fcb9247901ba84419d2ecf7e786e96d` |

## Customer-level and generated material

The public UCI source contains unique customer numbers and transaction-level dates, but no direct customer name or email field. The root `LICENSE` applies only to original project code; the UCI datasets remain under their separately stated CC BY 4.0 terms, and software dependencies retain their own licenses. Treat those records and derived customer-level tables as pseudonymous behavioral data. A prior tracked `data/bi_exports/repeat_timing.csv` contained 2,845 rows with pseudonymous customer identifiers and purchase timing fields (SHA-256 `c5133f40a1e593f912b1c72b0996ad51650980c04be5427ba21f1a328572ce0f`). That file and the notebooks that produced it are not part of this public repository. Earlier copies may persist outside this repository's control (for example in forks, caches or clones).

`data/raw/`, `data/processed/`, and `data/warehouse/` are ignored. The local processed directory includes customer-level scores, feature tables, and model artifacts; do not add these generated files to a release. The local `.venv/`, bytecode caches, logs, operating-system metadata, and editor preferences are also unsuitable for version control.

No secrets or credential files were found among the tracked current files or filenames in the bounded history scan.
