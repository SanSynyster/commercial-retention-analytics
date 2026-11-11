# COMMERCIAL-DS-002B — Approved Taxonomy and Purchase-Occasion Contract

**Status:** formal Stage A specification; reference semantics are tested by `test_COMMERCIAL_DS_003_CONTRACT.py`. This document defines the contract only. It does not create a production producer, revenue bridge, cohort analysis, retention analysis or model.

## 1. Authority and scope

This specification applies to overlap-corrected V2 (`v2c`) and the approved Milestone 1C taxonomy. Owner decisions O-1 through O-9 and the O-5 amendment in `COMMERCIAL_DS_001_DECISION_LOG.md` govern. The `COMMERCIAL_DS_002B_INTEGRATION.py` merchandise-bearing invoice set is used only to disambiguate `M`; it is **not** the purchase-occasion population.

## 2. Source-line identity and lineage

At raw V2 ingestion, assign zero-based `source_row_number` to every data row (header excluded), before renaming, filtering, overlap correction, sorting, or other transformation. The immutable source key is `(source_sha256, source_row_number)`. The V2 source hash is `32569a66f3842a82b0d8c4d63b263c5d98a76bde5d1f65c6c01bf457e541d3a9`.

The approved correction removes raw V2 source rows 502,938 through 525,460 inclusive (22,523 rows), exactly the first copy of the V1 overlap. Keep source-row identity on all remaining rows. Retain incidental exact repeats and their distinct row identities. Corrected V2 must contain 1,044,848 rows; source-row IDs must be unique and equal the raw source positions after removing exactly that interval. A row ID is never regenerated after filtering or sorting.

A canonical line ID may be a deterministic encoding/hash of `(source_sha256, source_row_number)`; it must not replace or obscure that pair. Any output occasion carries the sorted source-row IDs of its qualifying lines. Source hashes, source-row counts, overlap interval, and row identities fail closed on mismatch.

## 3. Taxonomy context versus purchase eligibility

Classification precedence remains: approved row-context rules, then canonical seed mapping, then fail closed as unclassified. The authoritative seed SHA-256 is `7b4611c78ca22d108c2616076c84b7c1db2efb8453ee9a32faceb027bb181e4e`. Unknown or commercially relevant unclassified rows are errors.

The following never qualify as merchandise purchase lines: shipping; standalone manual billing; standalone manual credits; standalone zero-value manual lines; embedded manual adjustments; fees and commissions; discounts; bad debt; samples; gift vouchers; test lines; non-commercial stock movements; returns; cancellation-invoice lines; zero/negative-quantity or zero/negative-price rows; and rows without a valid customer identifier. They remain available in their own taxonomy category for source-value reconciliation, with the approved O-5 treatments. They cannot create purchase occasions, repeat events, retention events, or behavioral customer-value features.

## 4. Qualifying merchandise purchase line (binding C-1)

A source row qualifies if and only if all conditions hold:

1. Its final frozen taxonomy category is exactly `merchandise`.
2. `Quantity` is an exact finite Decimal strictly greater than zero.
3. `UnitPrice` is an exact finite Decimal strictly greater than zero.
4. `CustomerID` is present and losslessly represents a canonical integer customer key. Missing (`None`, pandas/NumPy nulls, NaN) or malformed/fractional customer identifiers fail validation; they are not imputed.
5. `InvoiceNo` is present as a non-empty string and does not begin with the source cancellation prefix `C`.
6. The line's `InvoiceDate` is present and valid.

Line revenue is exact `Decimal(Quantity) × Decimal(UnitPrice)`; no binary-float accumulation or rounding is permitted. Duplicate source lines remain separate contributing rows because their source-row IDs differ.

This row predicate is intentionally stricter than the `M` invoice-context rule. In particular, an unattributed merchandise line, a cancellation merchandise return, or any manually classified row can never make an invoice a purchase occasion.

## 5. Purchase occasion grain and amounts

An atomic purchase occasion is one `(customer_id, invoice_id)` group with at least one qualifying merchandise purchase line. Require an invoice to map to only one customer. A multi-customer invoice is a data-integrity failure, not two occasions.

For an eligible group:

- `customer_id` is the validated canonical source customer key.
- `invoice_id` is the source invoice string.
- `occasion_date` is the local source calendar date of its qualifying merchandise lines. All rows in one invoice must agree on the calendar date; inconsistent invoice dates fail closed.
- `merchandise_revenue` is the exact Decimal sum over qualifying lines only.
- `source_row_numbers` is the sorted unique list of contributing source V2 row IDs; duplicate business lines remain represented by separate IDs.

Shipping/manual/fee/etc. rows on the same invoice do not contribute revenue, eligibility, or source-line lineage to the merchandise occasion. They remain separate transaction lines in the complete classification/reconciliation layer.

## 6. Repeat-purchase definitions (O-9)

Primary later-calendar-day definition:

- Sort a customer's occasions by `(occasion_date, invoice_id)`.
- The first observed occasion is the earliest occasion date.
- A second purchase occasion exists only if the customer has a qualifying occasion on a **strictly later calendar date** than the first. Its date is the earliest such later date. Multiple invoices on the first date do not create a second primary occasion.
- Subsequent primary occasion dates are distinct later calendar dates. At most one primary occasion is counted for a customer on a given calendar date.

Invoice-level sensitivity:

- Keep each eligible customer × invoice occasion as a distinct event.
- Sort by `(occasion_date, invoice_id)` and report invoice-level repeat separately; two invoices on the same calendar date may count as a second invoice in this sensitivity.
- Never substitute this sensitivity for the later-day primary definition.

For deterministic implementation, occasion ordering uses `(customer_id, local calendar date, invoice_id, sorted source_row_numbers)`; source-row lineage is the final stable tie-breaker. The primary 90-day repeat count collapses all invoices on each customer-day before applying `d1 < d2 < d1 + 90 days`. The invoice-level sensitivity sorts distinct invoices by `(local calendar date, invoice_id, sorted lineage)` and counts a later same-day invoice as a sensitivity repeat. The 90-day end boundary is exclusive for both measures.

No horizon, censoring, acquisition eligibility, cohort, label, or model is implemented by this specification. Those belong to later approved analysis stages.

## 7. `M` invoice-context definition (separate from C-1)

This section clarifies the existing approved O-5 context and does not reclassify any row.

- On a non-cancellation invoice, a seed-merchandise line that is not a row-context administrative movement qualifies as merchandise context when its signed line value is strictly positive.
- On a cancellation invoice, a nonzero merchandise return line qualifies as merchandise context. This preserves the independently reviewed embedded treatment for the 64 negative `M` rows on cancellation invoices that also contain merchandise returns: 52 invoices, 47 customers, GBP −1,168.70 in total. These remain `manual_adjustment`; context does not claim the `M` value refunds or links to those returned merchandise rows.
- Otherwise, an `M` row is standalone and is classified by its own exact signed line amount: positive `standalone_manual_billing`, negative `standalone_manual_credit`, zero `standalone_manual_zero_value`.

The M context set contains cancellations and can include unattributed merchandise lines; therefore it must never be reused as the purchase-occasion set. The cancellation rule is the independent review's accepted interpretation of the approved O-5 invoice-context definition. No further owner decision is required for the 64 rows under that interpretation; any future change to the context rule requires a separate owner decision and new independent review.

## 8. Required invariants and failure behavior

Every producer implementing this contract must assert:

- Input source SHA and schema match frozen pins.
- Exactly the approved 22,523 raw V2 rows are removed and all other raw source-row IDs remain unique and unchanged.
- Corrected-V2 count is 1,044,848; incidental duplicates remain.
- Taxonomy seed hash/version and category-sensitive frozen references match.
- Every source line has exactly one category; unknown descriptions/codes never default to merchandise.
- No non-merchandise category or invalid line can create an occasion.
- Each occasion key is unique at customer × invoice; one invoice maps to at most one customer.
- Occasion revenue equals exact Decimal sum of its eligible merchandise lines; occasion lineage equals those rows' source IDs.
- Primary repeat dates are strictly later calendar days; invoice-repeat sensitivity is separately computed.
- Global and category revenue, identified/unattributed amounts, row/source identities, and customer attribution reconcile exactly to frozen references.
- Classification, source-content and customer fingerprints validate against the separately frozen Stage A reference pins. Expected pins are not generated or rewritten by normal runs.

Any failed invariant stops the run with an actionable error. No partial occasion output is accepted as canonical.

## 9. Temporal contract (Stage B1)

These are date-level rules over the corrected-V2 observation. All dates are interpreted in the source's timezone-naive local calendar; timezone-aware transaction timestamps are invalid for this contract and are excluded from occasion eligibility. Timestamp ordering is not used to split occasions: the occasion date is the calendar date, and eligible lines on one customer/invoice must agree on that date.

| Symbol | Definition |
|---|---|
| `D_start` | `2009-12-01`, first calendar day in corrected V2. |
| `D_end_timestamp` | `2011-12-09 12:50:00`, maximum source timestamp. |
| `D_end_date` | `2011-12-09`, final observed calendar date; treated as the last observed date for date-level maturity. |
| `D_end_exclusive` | `2011-12-10` for date-grain half-open windows. The last day is only partially observed, through 12:50; the date-window notation does not mean that timestamps after the maximum source timestamp were observed. |
| Acquisition cutoff | `2010-12-01`, the twelve-calendar-month boundary after `D_start`. |

All date windows are half-open `[start, end)`: include the start date and exclude the end date. Calendar-date comparisons use the timezone-naive local dates from source timestamps; timestamps are validated as typed values and never parsed from strings in temporal helpers. Source transaction rows occurring on anchor date `T` are not historical features. Feature windows of length `L` are `[T-L, T)`. Feature and occasion summaries must be constructed only from transactions with calendar date `< T`; neither an anchor-day transaction nor a future transaction may enter historical features.

For source-window validation, timestamps must lie between `2009-12-01 00:00:00` inclusive and the observed maximum `2011-12-09 12:50:00` inclusive, in the source's timezone-naive local time. Thus the date-level observation interval is `[2009-12-01, 2011-12-10)`, but timestamps later than the actual observed maximum are not treated as observed data.

For a mature 90-day outcome anchored at `T`, the outcome window is `[T, T+90 days)`. The outcome boundary date exactly `T+90` is excluded. Maturity is date-level and holds iff `T + 90 calendar days <= D_end_date`; otherwise the anchor is immature and cannot receive a negative/no-repeat label. Observations at or beyond `D_end_exclusive` are invalid. These definitions do not make labels or cohorts in Stage B1.

For date-level repeat purchases, sort a customer's occasions by `(occasion_date, invoice_id)`. Same-day distinct invoices are one date-level purchase day. A qualifying second purchase date `d2` must satisfy `d1 < d2 < d1 + 90 calendar days` for the 90-day repeat outcome; exactly `d1 + 90` is outside the outcome. The primary repeat-event rule independent of a 90-day outcome remains strictly later calendar day. Invoice-level sensitivity retains distinct customer × invoice occasions, so two same-day invoices can count separately. Always label these metrics explicitly as date-level or invoice-level.


### Temporal boundary fixtures

- Feature transaction on `T-1 day`: included if within `[T-L,T)`; on `T`: excluded; on `T+1`: excluded.
- Outcome repeat on `T+89 days`: inside `[T,T+90)`; on `T+90`: excluded.
- Mature anchor where `T+90 == 2011-12-09`: mature; where `T+90 == 2011-12-10`: immature.
- Occasion on `2010-12-01`: included at the acquisition cutoff; on `2010-11-30`: before cutoff.
- Two invoices on one date: one date-level purchase day, two events in invoice-level sensitivity.

## 10. Invalid purchase-line values and source ingestion

The Stage B1 builder consumes only the approved `COMMERCIAL_DS_002_ANALYSIS.load_sources()` and overlap correction path, with the frozen taxonomy integration. It rejects an input lacking `source_row_number`, non-integral/negative/duplicate source identities, non-positive or non-integral customer IDs, numeric customer IDs outside the exact 2⁵³ bound, ambiguous text customer IDs, malformed invoice strings, and non-numeric/non-finite quantity or price values. Missing customers, non-positive/fractional quantities, non-positive prices and cancellations are explicitly excluded from occasions with reason counts. Missing or wrong-typed timestamps, timezone-aware timestamps, missing/malformed invoice IDs, negative/zero IDs and conflicting invoice dates/customers fail the data validation boundary rather than being silently dropped. Invoice identifiers follow observed source grammar: digits for ordinary invoices, `C` + digits (case-insensitive `c`) for cancellations, and `A` + digits for adjustment invoices. An `A` invoice cannot create a purchase occasion even if a caller relabels its line as merchandise. Leading/trailing invoice whitespace is rejected rather than trimmed. No string customer identifier is parsed as a number, including whitespace-padded or exponent-form strings. Invoice/customer uniqueness and single-calendar-date checks span every row in an invoice, including non-merchandise rows.

## 11. Acquisition-proxy approval status

The independent review found 11 of 1,613 merchandise-only observed-acquisition candidates with identified activity before the fixed cutoff, and 12 with identified activity before their first qualifying occasion (one additional customer has activity between cutoff and first occasion). The adjusted counts, 1,602 and 1,601, are diagnostics. The owner has not selected a primary rule. Until explicit approval is recorded, do not publish a primary cohort. Absence of earlier observed activity is not evidence of true acquisition.

## 12. Commercial revenue bridge

The source-line bridge is a signed revenue reconciliation, not a complete profit-and-loss statement. Each corrected source row belongs to exactly one bridge leaf, retains its `source_row_number`, and contributes its exact Decimal `Quantity × UnitPrice` amount. Leaves distinguish qualifying positive merchandise purchases; negative merchandise returns/cancellations; other positive merchandise not qualifying as a customer purchase; shipping/delivery; standalone manual billing; standalone manual credits; embedded manual `M` adjustments; other manual adjustment codes; fees; commissions; bad debt; discounts; samples; gift vouchers; test entries; non-commercial stock movements; and zero-value entries, with zero-value taxonomy subcategories retained.

Every leaf reports row count, positive, negative and signed amounts, identified/unattributed row counts and signed amounts, and source-row lineage. Identifiable plus unattributed line values must equal each leaf's signed value. Leaf rows and signed values must reconcile to all 1,044,848 corrected source rows and GBP 18,909,762.118 signed. Standalone manual credits remain separate from merchandise returns; embedded adjustments remain separate from standalone billing/credits. Zero-valued rows are represented in the zero-value leaf and carry their taxonomy subcategory. Do not label this bridge profit, margin, cash or a full P&L.

Qualifying purchase gross is a subset of positive merchandise value. In the reviewed corrected V2, positive merchandise is GBP 19,699,671.127; qualifying gross purchases are GBP 17,123,740.997; the GBP 2,575,930.130 difference is other positive merchandise activity, all 226,881 lines unattributed to a valid customer. The difference is reconciled explicitly and is not forced into customer purchases.
