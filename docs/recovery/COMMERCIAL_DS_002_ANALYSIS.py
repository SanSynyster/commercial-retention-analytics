"""Fail-closed, read-only evidence generator for COMMERCIAL-DS-002/002A.

Reads the immutable sources, validates bytes and V2 block structure, builds
overlap-corrected V2 in memory, and prints JSON. It writes no data or outputs.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from decimal import Decimal
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
V1_PATH = ROOT / "data/raw/Online Retail.xlsx"
V2_PATH = ROOT / "data/raw/online_retail_II.csv"
EXPECTED_V1_SHA256 = "43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d"
EXPECTED_V2_SHA256 = "32569a66f3842a82b0d8c4d63b263c5d98a76bde5d1f65c6c01bf457e541d3a9"
EXPECTED_V1_ROWS, EXPECTED_V2_ROWS = 541_909, 1_067_371
EXPECTED_RESET_INDEX, EXPECTED_OVERLAP_ROWS, EXPECTED_CORRECTED_ROWS = 525_461, 22_523, 1_044_848
D_START, V1_START = pd.Timestamp("2009-12-01"), pd.Timestamp("2010-12-01")
D_END, OVERLAP_END = pd.Timestamp("2011-12-09 12:50:00"), pd.Timestamp("2010-12-10")
CANONICAL_COLUMNS = ["InvoiceNo", "StockCode", "Description", "Quantity", "InvoiceDate", "UnitPrice", "CustomerID", "Country"]

# Retained solely to reproduce the reviewed DS-002 baseline; not canonical.
DS002_NON_PRODUCT_CODES = {"POST", "DOT", "M", "C2", "BANK CHARGES", "AMAZONFEE", "PADS", "D", "S", "B", "CRUK"}

# Evidence proposals only; none is owner-approved by this script.
EXPLICIT_CODE_CATEGORIES = {
    "ADJUST": ("manual_adjustment", "Adjustment code and descriptions", "high", True),
    "ADJUST2": ("manual_adjustment", "Adjustment code and descriptions", "high", True),
    "AMAZONFEE": ("fee", "Amazon fee", "high", True),
    "B": ("bad_debt", "Adjust bad debt", "high", True),
    "BANK CHARGES": ("fee", "Bank charges", "high", True),
    "C2": ("shipping", "Carriage", "high", True),
    "C3": ("unclassified", "Zero-value row without description", "low", True),
    "CRUK": ("fee_commission", "CRUK commission", "high", True),
    "D": ("discount", "Discount", "high", True),
    "DOT": ("shipping", "Dotcom postage", "high", True),
    "GIFT": ("unclassified", "Zero-value row without description", "low", True),
    "M": ("manual_adjustment", "Manual", "high", True),
    "PADS": ("merchandise", "Pads to match cushions", "medium", True),
    "POST": ("shipping", "Postage", "high", True),
    "S": ("sample", "Samples", "high", True),
    "TEST001": ("test", "This is a test product", "high", True),
    "TEST002": ("test", "This is a test product", "high", True),
    "22016": ("gift_voucher", "Dotcomgiftshop gift voucher GBP 100", "high", True),
    "23444": ("shipping", "Numeric code; Next Day Carriage", "high", True),
    "SP1002": ("merchandise", "Kid's chalkboard/easel", "high", False),
}
ADMIN_DESCRIPTION = re.compile(
    r"\b(adjust(?:ment|ed)?|re-?adjust|amazon|dotcom|ebay|allocate stock|sold as set|damages?|samples?|showroom|temp(?:orary)? fix|quick fix|write off|wrongly|missing|found|stock check|counted|crushed|wet|broken)\b",
    re.IGNORECASE,
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def assign_source_row_numbers(frame: pd.DataFrame) -> pd.DataFrame:
    """Assign immutable zero-based data-row identities at raw ingestion."""
    if "source_row_number" in frame.columns:
        raise ValueError("source_row_number already exists; refusing to reassign identity")
    result=frame.copy()
    result.insert(0,"source_row_number",pd.RangeIndex(start=0,stop=len(result),step=1,dtype="int64"))
    return result


def load_sources() -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    hashes = {"v1": sha256(V1_PATH), "v2": sha256(V2_PATH)}
    require(hashes["v1"] == EXPECTED_V1_SHA256, "V1 SHA-256 mismatch")
    require(hashes["v2"] == EXPECTED_V2_SHA256, "V2 SHA-256 mismatch")
    with V2_PATH.open("rb") as handle:
        physical_lines = sum(1 for _ in handle)
    require(physical_lines - 1 == EXPECTED_V2_ROWS, "V2 physical data-line count mismatch")
    v1 = pd.read_excel(V1_PATH)
    # Materialise raw V2 identity at ingestion, before rename, block slicing,
    # overlap removal, sorting or filtering. This ID is never recomputed later.
    v2 = pd.read_csv(V2_PATH)
    require(list(v2.columns) == ["Invoice", "StockCode", "Description", "Quantity", "InvoiceDate", "Price", "Customer ID", "Country"], "Unexpected raw V2 schema/order")
    v2 = assign_source_row_numbers(v2)
    v2 = v2.rename(columns={"Invoice": "InvoiceNo", "Price": "UnitPrice", "Customer ID": "CustomerID"})
    require(list(v1.columns) == CANONICAL_COLUMNS, "Unexpected V1 schema/order")
    require(list(v2.columns) == ["source_row_number", *CANONICAL_COLUMNS], "Unexpected V2 schema/order")
    require(len(v1) == EXPECTED_V1_ROWS and len(v2) == EXPECTED_V2_ROWS, "Unexpected source row count")
    for frame in (v1, v2):
        frame["InvoiceDate"] = pd.to_datetime(frame["InvoiceDate"])
        frame["InvoiceNo"] = frame["InvoiceNo"].astype(str)
        frame["StockCode"] = frame["StockCode"].astype(str)
    require(v2.InvoiceDate.min().normalize() == D_START and v2.InvoiceDate.max() == D_END, "Unexpected V2 date bounds")
    require(v2.source_row_number.tolist() == list(range(EXPECTED_V2_ROWS)), "Raw V2 source-row identity is not contiguous at ingestion")
    return v1.copy(), v2.copy(), {**hashes, "v2_physical_lines": physical_lines}


def comparable_tuples(frame: pd.DataFrame) -> list[tuple]:
    copy = frame[CANONICAL_COLUMNS].copy()
    for column in ("InvoiceNo", "StockCode", "Description", "Country"):
        copy[column] = copy[column].astype("string").fillna("<NA>")
    copy["CustomerID"] = copy["CustomerID"].astype("Float64").fillna(-1.0)
    copy["Quantity"] = copy["Quantity"].astype("int64")
    copy["UnitPrice"] = copy["UnitPrice"].astype("float64")
    copy["InvoiceDate"] = pd.to_datetime(copy["InvoiceDate"])
    return list(copy.itertuples(index=False, name=None))


def compare_multisets(left: pd.DataFrame, right: pd.DataFrame) -> dict:
    a, b = Counter(comparable_tuples(left)), Counter(comparable_tuples(right))
    only_a, only_b = a - b, b - a
    return {"left_rows": len(left), "right_rows": len(right), "exact_multiset_equal": a == b,
            "rows_only_in_left_by_multiplicity": sum(only_a.values()), "rows_only_in_right_by_multiplicity": sum(only_b.values()),
            "distinct_rows_with_different_multiplicity": len(set(only_a) | set(only_b))}


def decimal_line(row) -> Decimal:
    return Decimal(str(int(row.Quantity))) * Decimal(str(row.UnitPrice))


def decimal_sum(frame: pd.DataFrame, mask=None) -> Decimal:
    subset = frame if mask is None else frame.loc[mask]
    return sum((decimal_line(row) for row in subset.itertuples()), Decimal("0"))


def flags(frame: pd.DataFrame) -> pd.DataFrame:
    data = frame.copy()
    data["line_revenue"] = data.Quantity * data.UnitPrice
    data["cancelled"] = data.InvoiceNo.str.startswith("C")
    data["positive_purchase"] = (data.Quantity > 0) & (data.UnitPrice > 0) & ~data.cancelled
    data["identified"] = data.CustomerID.notna()
    data["valid_current"] = data.positive_purchase & data.identified
    data["non_product"] = data.StockCode.str.upper().isin(DS002_NON_PRODUCT_CODES)
    data["valid_product"] = data.valid_current & ~data.non_product
    data["refund_or_return"] = (data.Quantity < 0) | data.cancelled
    return data


def dataset_metrics(frame: pd.DataFrame) -> dict:
    data = flags(frame); current, product = data[data.valid_current], data[data.valid_product]
    refunds = data[data.refund_or_return & data.identified & ~data.non_product]
    return {"rows": len(data), "date_min": str(data.InvoiceDate.min()), "date_max": str(data.InvoiceDate.max()),
            "full_row_duplicate_excess_rows": int(data.duplicated(CANONICAL_COLUMNS).sum()),
            "current_valid_lines": int(data.valid_current.sum()), "current_valid_orders": int(current.InvoiceNo.nunique()),
            "current_valid_customers": int(current.CustomerID.nunique()), "product_valid_orders": int(product.InvoiceNo.nunique()),
            "product_valid_customers": int(product.CustomerID.nunique()),
            "gross_positive_revenue_all": str(decimal_sum(data, data.positive_purchase)),
            "refund_cancel_revenue_all": str(decimal_sum(data, data.refund_or_return)),
            "net_transactional_revenue_all": str(decimal_sum(data, data.positive_purchase | data.refund_or_return)),
            "identifiable_gross_revenue_current": str(decimal_sum(data, data.valid_current)),
            "identifiable_non_product_revenue": str(decimal_sum(data, data.valid_current & data.non_product)),
            "identifiable_gross_product_revenue": str(decimal_sum(data, data.valid_product)),
            "identifiable_product_refund_revenue": str(decimal_sum(refunds)),
            "identifiable_net_product_revenue": str(decimal_sum(product) + decimal_sum(refunds))}


def build_orders(frame: pd.DataFrame) -> pd.DataFrame:
    data = flags(frame); valid = data[data.valid_product].copy()
    orders = valid.groupby(["CustomerID", "InvoiceNo"], as_index=False).agg(order_date=("InvoiceDate", "min"), order_revenue=("line_revenue", "sum"))
    return orders[orders.order_revenue > 0].sort_values(["CustomerID", "order_date", "InvoiceNo"]).reset_index(drop=True)


def source_block_evidence(v1: pd.DataFrame, v2: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    require("source_row_number" in v2.columns, "V2 source-row identity missing at ingestion")
    require(v2.source_row_number.is_unique, "Raw V2 source-row identity collision")
    resets = v2.index[v2.InvoiceDate.diff() < pd.Timedelta(0)].tolist()
    require(resets == [EXPECTED_RESET_INDEX], f"Unexpected chronological resets: {resets}")
    first, second = v2.iloc[:EXPECTED_RESET_INDEX].copy(), v2.iloc[EXPECTED_RESET_INDEX:].copy()
    require(len(first) == 525_461 and len(second) == 541_910, "Unexpected source-block sizes")
    require((first.InvoiceDate >= OVERLAP_END).sum() == 0 and (second.InvoiceDate < V1_START).sum() == 0, "Source-block boundary failure")
    fover = first[(first.InvoiceDate >= V1_START) & (first.InvoiceDate < OVERLAP_END)]
    sover = second[(second.InvoiceDate >= V1_START) & (second.InvoiceDate < OVERLAP_END)]
    vover = v1[(v1.InvoiceDate >= V1_START) & (v1.InvoiceDate < OVERLAP_END)]
    require(len(fover) == len(sover) == len(vover) == EXPECTED_OVERLAP_ROWS, "Overlap row count mismatch")
    comparisons = {"first_block_vs_v1": compare_multisets(fover, vover), "second_block_vs_v1": compare_multisets(sover, vover),
                   "first_vs_second_block": compare_multisets(fover, sover), "second_block_full_vs_v1_full": compare_multisets(second, v1)}
    for name in ("first_block_vs_v1", "second_block_vs_v1", "first_vs_second_block"):
        require(comparisons[name]["exact_multiset_equal"], f"Fail-closed multiset check failed: {name}")
    full = comparisons["second_block_full_vs_v1_full"]
    require(full["rows_only_in_left_by_multiplicity"] == 1 and full["rows_only_in_right_by_multiplicity"] == 0, "Second block must differ from V1 by one row")
    corrected = pd.concat([first[first.InvoiceDate < V1_START], second], ignore_index=True)
    require(len(corrected) == EXPECTED_CORRECTED_ROWS, "Corrected V2 row count mismatch")
    source_ids=corrected.source_row_number.tolist()
    expected_source_ids=list(range(EXPECTED_RESET_INDEX-EXPECTED_OVERLAP_ROWS))+list(range(EXPECTED_RESET_INDEX,EXPECTED_V2_ROWS))
    require(source_ids == expected_source_ids, "Corrected V2 source-row lineage differs from approved overlap removal")
    extra_counter = Counter(comparable_tuples(second)) - Counter(comparable_tuples(v1))
    require(sum(extra_counter.values()) == 1, "Expected exactly one extra second-block row")
    extra = next(iter(extra_counter))
    expected = ("581587", "POST", "POSTAGE", 1, pd.Timestamp("2011-12-09 12:50:00"), 18.0, 12680.0, "France")
    require(extra == expected, f"Unexpected extra row: {extra}")
    return corrected, {"reset_indices_zero_based": resets, "first_block_rows": len(first), "second_block_rows": len(second),
                       "overlap_rows_each": EXPECTED_OVERLAP_ROWS, "comparisons": comparisons,
                       "removed_raw_source_row_start": EXPECTED_RESET_INDEX-EXPECTED_OVERLAP_ROWS,
                       "removed_raw_source_row_end_inclusive": EXPECTED_RESET_INDEX-1,
                       "extra_post_row": dict(zip(CANONICAL_COLUMNS, map(str, extra)))}


def duplicate_diagnostics(v1: pd.DataFrame, corrected: pd.DataFrame) -> dict:
    def repeated(frame: pd.DataFrame) -> dict:
        data = flags(frame); repeat = data.duplicated(CANONICAL_COLUMNS); valid_repeat = repeat & data.valid_current
        tuples = comparable_tuples(data)
        adjacent = sum(a == b for a, b in zip(tuples, tuples[1:]))
        positions: dict[tuple, list[int]] = {}
        for pos, key in enumerate(tuples): positions.setdefault(key, []).append(pos)
        gaps = [b - a for values in positions.values() for a, b in zip(values, values[1:])]
        return {"all_repeat_excess_rows": int(repeat.sum()), "valid_repeat_excess_rows": int(valid_repeat.sum()),
                "valid_repeat_excess_revenue": str(decimal_sum(data, valid_repeat)), "adjacent_repeat_rows": adjacent,
                "repeat_gap_min": min(gaps), "repeat_gap_median": float(pd.Series(gaps).median()), "repeat_gap_max": max(gaps)}
    a, b = repeated(v1), repeated(corrected)
    require((a["all_repeat_excess_rows"], a["valid_repeat_excess_rows"], Decimal(a["valid_repeat_excess_revenue"])) == (5268, 5192, Decimal("24199.01")), "V1 repeat invariant failed")
    require(b["all_repeat_excess_rows"] == 11812 and b["adjacent_repeat_rows"] == 1685, "Corrected repeat invariant failed")
    return {"v1": a, "corrected_v2": b}


def financial_reconciliation(corrected: pd.DataFrame) -> dict:
    metrics = dataset_metrics(corrected)
    expected = {"gross_positive_revenue_all": "20533741.918", "refund_cancel_revenue_all": "-1465303.66",
                "net_transactional_revenue_all": "19068438.258", "identifiable_gross_revenue_current": "17431551.178",
                "identifiable_non_product_revenue": "302114.628", "identifiable_gross_product_revenue": "17129436.550",
                "identifiable_product_refund_revenue": "-714532.55", "identifiable_net_product_revenue": "16414904.000"}
    for key, wanted in expected.items(): require(Decimal(metrics[key]) == Decimal(wanted), f"Financial reconciliation failed: {key}")
    places = corrected.UnitPrice.map(lambda x: max(0, -Decimal(str(x)).as_tuple().exponent))
    require(int((places > 2).sum()) == 18 and int(places.max()) == 3, "Unexpected monetary precision profile")
    return {"metrics": metrics, "unit_price_rows_over_2dp": 18, "maximum_unit_price_decimal_places": 3,
            "required_storage": "exact decimal with at least 3 fractional decimal places"}


def history_policy(orders: pd.DataFrame) -> dict:
    first = orders.groupby("CustomerID").order_date.min().rename("first_observed")
    ranked = orders.copy(); ranked["rank"] = ranked.groupby("CustomerID").cumcount() + 1
    second = ranked[ranked["rank"] == 2].set_index("CustomerID").order_date.rename("second_observed")
    dates = pd.concat([first, second], axis=1); rows = []
    for months in (3, 6, 9, 12):
        cutoff = D_START + pd.DateOffset(months=months); eligible = dates[dates.first_observed >= cutoff]
        row = {"lookback_months": months, "cutoff": str(cutoff.date()), "eligible_customers": len(eligible),
               "eligible_cohort_months": int(eligible.first_observed.dt.to_period("M").nunique())}
        for horizon in (60, 90, 180):
            mature = eligible[eligible.first_observed.dt.normalize() + pd.Timedelta(days=horizon) <= D_END.normalize()]
            repeated = mature.second_observed.notna() & (mature.second_observed < mature.first_observed + pd.Timedelta(days=horizon))
            row[f"second_purchase_{horizon}d_mature_customers"] = len(mature); row[f"second_purchase_{horizon}d_customers"] = int(repeated.sum())
            row[f"second_purchase_{horizon}d_rate_pct"] = float(repeated.mean() * 100)
        rows.append(row)
    require(rows[-1]["second_purchase_60d_mature_customers"] == 1258 and rows[-1]["second_purchase_90d_mature_customers"] == 1016, "Date-level maturity invariant failed")
    return {"date_level_maturity": True, "policies": rows}


def pseudo_boundary(orders: pd.DataFrame) -> list[dict]:
    rows = []
    for hidden, lookback in ((3, 12), (6, 12), (9, 12), (6, 6), (6, 9)):
        pseudo_start = D_START + pd.DateOffset(months=hidden)
        first = orders[orders.order_date >= pseudo_start].groupby("CustomerID").order_date.min()
        eligible = first[first >= pseudo_start + pd.DateOffset(months=lookback)]
        hidden_customers = set(orders[(orders.order_date >= D_START) & (orders.order_date < pseudo_start)].CustomerID)
        returning = len(set(eligible.index) & hidden_customers)
        rows.append({"hidden_history_months": hidden, "lookback_months": lookback, "eligible_acquisition_proxies": len(eligible),
                     "actually_returning_lower_bound": returning, "misclassification_lower_bound_pct": 100 * returning / len(eligible)})
    require([(x["eligible_acquisition_proxies"], x["actually_returning_lower_bound"]) for x in rows] == [(1381, 42), (1031, 88), (727, 99), (1872, 260), (1514, 175)], "Pseudo-boundary invariant failed")
    return rows


def active_windows_and_return_recency(orders: pd.DataFrame) -> dict:
    anchors = pd.date_range("2010-06-01", "2011-09-01", freq="MS"); active_rows, observations = [], []
    for anchor in anchors:
        prior = orders[(orders.order_date >= anchor - pd.Timedelta(days=365)) & (orders.order_date < anchor)]
        active_rows.append({"anchor": str(anchor.date()), "history_available_days": min(365, (anchor - D_START).days),
                            "active_365_product_customers": int(prior.CustomerID.nunique()), "active_window_complete": bool(anchor >= V1_START),
                            "label_90d_mature": bool(anchor.normalize() + pd.Timedelta(days=90) <= D_END.normalize())})
        if anchor >= V1_START:
            last = orders[orders.order_date < anchor].groupby("CustomerID").order_date.max()
            future = set(orders[(orders.order_date >= anchor) & (orders.order_date < anchor + pd.Timedelta(days=90))].CustomerID)
            # Reviewer diagnostic uses whole elapsed 24-hour periods at the
            # midnight anchor, matching the proposed recency definition.
            observations.extend(((anchor - date).days, customer in future) for customer, date in last.items())
    selected = {x["anchor"]: x["active_365_product_customers"] for x in active_rows}
    require([selected[x] for x in ("2010-06-01", "2010-09-01", "2010-11-01", "2010-12-01")] == [2695, 3309, 3923, 4249], "Active-window invariant failed")
    require(sum(x["active_window_complete"] and x["label_90d_mature"] for x in active_rows) == 10, "Complete mature anchor invariant failed")
    bins = [(0, 90, "0-90"), (91, 180, "91-180"), (181, 270, "181-270"), (271, 365, "271-365"), (366, 450, "366-450"), (451, 10_000, "451+")]
    recency = []
    for low, high, label in bins:
        values = [returned for days, returned in observations if low <= days <= high]
        recency.append({"recency_days": label, "customer_anchors": len(values), "returns_next_90d": sum(values), "return_rate_pct": 100 * sum(values) / len(values)})
    observed_counts = [x["customer_anchors"] for x in recency]
    require(observed_counts == [21027, 9880, 6951, 5043, 2398, 2006], f"Return-recency invariant failed: {observed_counts}")
    return {"anchor_completeness": active_rows, "return_probability_by_recency": recency}


def same_day_sensitivity(orders: pd.DataFrame) -> list[dict]:
    first = orders.groupby("CustomerID").order_date.min().rename("first")
    ranked = orders.copy(); ranked["rank"] = ranked.groupby("CustomerID").cumcount() + 1
    second = ranked[ranked["rank"] == 2].set_index("CustomerID").order_date.rename("second")
    dates = pd.concat([first, second], axis=1); rows = []
    for lookback in (12, 3):
        eligible = dates[dates["first"] >= D_START + pd.DateOffset(months=lookback)]
        mature = eligible[eligible["first"].dt.normalize() + pd.Timedelta(days=90) <= D_END.normalize()]
        repeat = mature.second.notna() & (mature.second < mature["first"] + pd.Timedelta(days=90))
        same = repeat & (mature.second.dt.normalize() == mature["first"].dt.normalize())
        rows.append({"lookback_months": lookback, "mature_customers": len(mature), "invoice_repeaters_90d": int(repeat.sum()),
                     "same_day_second_invoice": int(same.sum()), "invoice_rate_pct": 100 * repeat.mean(),
                     "rate_excluding_same_day_pct": 100 * (repeat.sum() - same.sum()) / len(mature)})
    require([(r["mature_customers"], r["invoice_repeaters_90d"], r["same_day_second_invoice"]) for r in rows] == [(1016, 430, 29), (3556, 1476, 154)], "Same-day invariant failed")
    return rows


def returns_and_population(corrected: pd.DataFrame) -> dict:
    data = flags(corrected); current, product = data[data.valid_current], data[data.valid_product]
    refunds = data[data.refund_or_return & data.identified & ~data.non_product]
    returns_only = refunds[~refunds.CustomerID.isin(set(product.CustomerID))]
    net: dict[float, Decimal] = {}
    for row in pd.concat([product, refunds]).itertuples():
        net[row.CustomerID] = net.get(row.CustomerID, Decimal("0")) + decimal_line(row)
    first_three = refunds[(refunds.InvoiceDate >= D_START) & (refunds.InvoiceDate < D_START + pd.DateOffset(months=3))]
    result = {"current_customers": int(current.CustomerID.nunique()), "current_orders": int(current.InvoiceNo.nunique()),
              "product_customers": int(product.CustomerID.nunique()), "product_orders": int(product.InvoiceNo.nunique()),
              "returns_only_customers": int(returns_only.CustomerID.nunique()), "returns_only_revenue": str(decimal_sum(returns_only)),
              "negative_net_product_customers": sum(value < 0 for value in net.values()), "first_three_month_product_return_revenue": str(decimal_sum(first_three))}
    require((result["current_customers"], result["current_orders"], result["product_customers"], result["product_orders"]) == (5878, 36969, 5861, 36639), "Population bridge invariant failed")
    observed_returns = (result["returns_only_customers"], Decimal(result["returns_only_revenue"]), result["negative_net_product_customers"], Decimal(result["first_three_month_product_return_revenue"]))
    require(observed_returns == (33, Decimal("-1643.28"), 37, Decimal("-39466.28")), f"Return invariant failed: {observed_returns}")
    return result


def inventory_source(frame: pd.DataFrame) -> dict[str, dict]:
    """Collect per-code evidence in one source pass (including exact Decimal)."""
    result: dict[str, dict] = {}
    for row in frame.itertuples():
        code = str(row.StockCode).upper()
        item = result.setdefault(code, {"variants": set(), "descriptions": set(), "rows": 0,
                                       "positive": 0, "negative": 0, "zero": 0,
                                       "identified_positive": Decimal("0"), "negative_revenue": Decimal("0")})
        item["variants"].add(str(row.StockCode))
        if pd.notna(row.Description): item["descriptions"].add(str(row.Description))
        item["rows"] += 1
        revenue = decimal_line(row)
        item["positive" if revenue > 0 else "negative" if revenue < 0 else "zero"] += 1
        cancelled = str(row.InvoiceNo).startswith("C")
        if row.Quantity > 0 and row.UnitPrice > 0 and not cancelled and pd.notna(row.CustomerID):
            item["identified_positive"] += revenue
        if revenue < 0: item["negative_revenue"] += revenue
    return result


def classify_code(code: str, descs: list[str]) -> tuple[str, str, str, bool, bool, str]:
    if code in EXPLICIT_CODE_CATEGORIES:
        category, rationale, confidence, approval = EXPLICIT_CODE_CATEGORIES[code]
        return category, rationale, confidence, approval, code == "23444", "Next Day Carriage" if code == "23444" else ""
    if code.startswith("GIFT_0001_"): return "gift_voucher", "Gift-voucher code family and descriptions", "high", True, False, ""
    if code.startswith("DCGS"):
        return ("merchandise", "Dotcomgiftshop item descriptions; family meaning remains ambiguous", "medium", True, False, "") if descs else ("unclassified", "No description or value evidence", "low", True, False, "")
    admin = [d for d in descs if ADMIN_DESCRIPTION.search(d)]; ordinary = [d for d in descs if d not in admin]
    if admin and ordinary: return "merchandise_with_description_exceptions", "Product descriptions mixed with administrative descriptions", "medium", True, True, " | ".join(admin)
    if admin: return "inventory_adjustment", "Only administrative/adjustment descriptions observed", "medium", True, True, " | ".join(admin)
    if not descs: return "unclassified", "No observed description", "low", True, False, ""
    return "merchandise", "Descriptions are merchandise-like; evidence-based, not numeric-default", "medium", False, False, ""


def taxonomy_inventory(v1: pd.DataFrame, corrected: pd.DataFrame) -> tuple[list[dict], dict]:
    left, right = inventory_source(v1), inventory_source(corrected)
    inventories = []; codes = sorted(set(left) | set(right))
    for code in codes:
        blank = {"variants": set(), "descriptions": set(), "rows": 0, "positive": 0, "negative": 0, "zero": 0,
                 "identified_positive": Decimal("0"), "negative_revenue": Decimal("0")}
        a, b = left.get(code, blank), right.get(code, blank)
        d1, d2 = sorted(a["descriptions"]), sorted(b["descriptions"]); all_desc = sorted(set(d1) | set(d2))
        category, rationale, confidence, approval, exception, examples = classify_code(code, all_desc)
        variants = sorted(a["variants"] | b["variants"])
        row = {"stock_code": code, "observed_code_variants": " | ".join(variants), "v1_descriptions": " | ".join(d1), "corrected_v2_descriptions": " | ".join(d2)}
        for prefix, source in (("v1", a), ("corrected_v2", b)):
            row.update({f"{prefix}_row_count": source["rows"], f"{prefix}_positive_value_count": source["positive"],
                        f"{prefix}_negative_value_count": source["negative"], f"{prefix}_zero_value_count": source["zero"],
                        f"{prefix}_identifiable_positive_revenue": str(source["identified_positive"]),
                        f"{prefix}_negative_revenue": str(source["negative_revenue"])})
        row.update({"proposed_category": category, "classification_rationale": rationale, "confidence": confidence,
                    "ambiguity": "yes" if confidence != "high" else "no", "owner_approval_required": "yes" if approval else "no",
                    "description_exception_required": "yes" if exception else "no", "description_exception_examples": examples})
        inventories.append(row)
    require(classify_code("UNSEEN_FIXTURE", [])[0] == "unclassified", "Unknown code must fail closed")
    categories = Counter(x["proposed_category"] for x in inventories)
    summary = {"observed_union_codes": len(inventories), "v1_codes": int(v1.StockCode.str.upper().nunique()),
               "corrected_v2_codes": int(corrected.StockCode.str.upper().nunique()), "category_code_counts": dict(categories),
               "corrected_v2_unclassified_rows": sum(x["corrected_v2_row_count"] for x in inventories if x["proposed_category"] == "unclassified"),
               "unknown_code_fixture_category": "unclassified", "future_contract_rule": "fail validation if any row remains unclassified"}
    return inventories, summary


def main() -> None:
    v1, v2, integrity = load_sources(); corrected, block = source_block_evidence(v1, v2); orders = build_orders(corrected)
    inventory, taxonomy_summary = taxonomy_inventory(v1, corrected)
    evidence = {"methodology": {"classification": "read-only evidence; proposals are not approvals", "window_convention": "half-open; date-level maturity",
                                "fixed_source_start": str(D_START.date()), "fixed_source_end": str(D_END)},
                "source_integrity": integrity, "source_blocks_and_overlap": block, "corrected_v2": dataset_metrics(corrected),
                "duplicate_and_gap_diagnostics": duplicate_diagnostics(v1, corrected), "financial_reconciliation": financial_reconciliation(corrected),
                "customer_history_date_level": history_policy(orders), "pseudo_boundary_sensitivity": pseudo_boundary(orders),
                "active_windows_and_return_recency": active_windows_and_return_recency(orders),
                "same_day_second_invoice_sensitivity": same_day_sensitivity(orders), "population_and_return_diagnostics": returns_and_population(corrected),
                "taxonomy_summary": taxonomy_summary, "stock_code_inventory": inventory}
    print(json.dumps(evidence, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
