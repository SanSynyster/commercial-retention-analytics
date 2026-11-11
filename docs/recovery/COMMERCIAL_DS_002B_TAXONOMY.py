"""Evidence-only deterministic classifier for approved 002B taxonomy policy."""
from __future__ import annotations
import csv
import hashlib
import math
from decimal import Decimal, InvalidOperation
from pathlib import Path

SEED = Path(__file__).with_name("COMMERCIAL_DS_002B_TAXONOMY_SEED.csv")
VERSION = "commercial-ds-002b-v1"
SEED_SHA256 = "7b4611c78ca22d108c2616076c84b7c1db2efb8453ee9a32faceb027bb181e4e"
VALID = {"merchandise", "shipping", "discount", "manual_adjustment", "standalone_manual_billing", "standalone_manual_credit", "standalone_manual_zero_value", "fee", "commission", "bad_debt", "sample", "gift_voucher", "test"}
WEAK_MERCHANDISE_CODES={"15002","20852","22126","23059","35643","35956","72038B","72732","72759","DCGS0067","DCGS0073"}

def normalize_code(raw):
    return "" if raw is None else str(raw).strip().upper()

def _is_null(raw):
    if raw is None or type(raw).__name__ == "NAType": return True
    if isinstance(raw, str): return False
    try: return bool(math.isnan(raw))
    except (TypeError, ValueError): return False

INVENTORY = Path(__file__).with_name("COMMERCIAL_DS_002A_STOCK_CODE_INVENTORY.csv")
def load_seed(path=SEED):
    with path.open(newline="", encoding="utf-8") as f:
        rows=list(csv.DictReader(f))
    keys=[r["stock_code_key"] for r in rows]
    if len(keys)!=len(set(keys)): raise ValueError("duplicate normalized seed key")
    if any(normalize_code(k)!=k for k in keys): raise ValueError("seed key is not canonical")
    if any(r["category"] not in VALID for r in rows): raise ValueError("invalid category")
    return {r["stock_code_key"]:r["category"] for r in rows}

def validate_seed(path=SEED):
    actual=sha256(path)
    if actual != SEED_SHA256: raise ValueError(f"authoritative seed SHA-256 mismatch: {actual}")
    return load_seed(path)

def classify(row, seed=None):
    seed=load_seed() if seed is None else seed
    code=normalize_code(row.get("StockCode"))
    price=row.get("UnitPrice")
    customer=row.get("CustomerID")
    if code in WEAK_MERCHANDISE_CODES:
        try: priced=Decimal(str(price)) != 0
        except (InvalidOperation, ValueError): priced=True
        if priced or not _is_null(customer):
            raise ValueError(f"weakly supported merchandise code has commercial exposure: {code!r}")
    # Approved zero-value stock movement exception. Admin descriptions are
    # enumerated from reviewed inventory evidence; this does not sweep ordinary
    # zero-price merchandise rows into the exception.
    try:
        zero_price = price is not None and price != "" and Decimal(str(price)) == 0
    except (InvalidOperation, ValueError):
        zero_price = False
    if zero_price and _is_null(customer) and (
        (code in U1_CODES and _is_null(row.get("Description")))
        or (code in INVENTORY_CONTEXT_CODES and _normalise_description(row.get("Description")) in {"", "adjustment", "re-adjustment", "found by jackie", "damages"})
        or (code, _normalise_description(row.get("Description"))) in ADMIN_CONTEXT
    ):
        return "non_commercial_stock_movement"
    category=seed.get(code, "unclassified")
    if category=="unclassified": raise ValueError(f"unclassified commercial code: {code!r}")
    if code=="M":
        context=row.get("invoice_has_merchandise")
        if type(context) is bool: embedded=context
        elif type(context).__name__ in {"bool_","bool"} and type(context).__module__.split(".")[0]=="numpy": embedded=bool(context)
        else: raise ValueError("M classification requires an explicit Python or NumPy boolean invoice_has_merchandise")
        if embedded: return "manual_adjustment"
        amount=_manual_line_amount(row)
        if amount>0: return "standalone_manual_billing"
        if amount<0: return "standalone_manual_credit"
        return "standalone_manual_zero_value"
    return category

# Filled from the reviewed CSV at module import; these keys are not mapped.
def _u1_codes():
    import csv
    p=Path(__file__).with_name("COMMERCIAL_DS_002A_STOCK_CODE_INVENTORY.csv")
    with p.open(newline="",encoding="utf-8") as f:
        return {r["stock_code"] for r in csv.DictReader(f) if r["proposed_category"]=="unclassified"}
U1_CODES=_u1_codes()
INVENTORY_CONTEXT_CODES={"23595","35600A","35605A","35978","84641"}

def _normalise_description(value):
    return "" if _is_null(value) else " ".join(str(value).strip().lower().split())

def _admin_context():
    p=Path(__file__).with_name("COMMERCIAL_DS_002A_STOCK_CODE_INVENTORY.csv")
    out=set()
    with p.open(newline="",encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["description_exception_required"] == "yes":
                for desc in r["description_exception_examples"].split(" | "):
                    if desc:
                        out.add((normalize_code(r["stock_code"]),_normalise_description(desc)))
    return out
ADMIN_CONTEXT=_admin_context()

def _manual_line_amount(row):
    try:
        quantity=Decimal(str(row.get("Quantity")))
        price=Decimal(str(row.get("UnitPrice")))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("M classification requires exact numeric Quantity and UnitPrice")
    if not quantity.is_finite() or not price.is_finite():
        raise ValueError("M classification requires finite Quantity and UnitPrice")
    return quantity*price

MAP={"merchandise":"merchandise", "merchandise_with_description_exceptions":"merchandise", "shipping":"shipping",
     "discount":"discount", "manual_adjustment":"manual_adjustment", "fee":"fee", "fee_commission":"commission",
     "bad_debt":"bad_debt", "sample":"sample", "gift_voucher":"gift_voucher", "test":"test"}

def generate_seed(inventory=INVENTORY, output=SEED):
    grouped={}
    with inventory.open(newline="",encoding="utf-8") as f:
        for row in csv.DictReader(f): grouped.setdefault(normalize_code(row["stock_code"]),[]).append(row)
    result=[]
    for key, variants in sorted(grouped.items()):
        cats={MAP[r["proposed_category"]] for r in variants if r["proposed_category"] in MAP}
        if not cats: continue
        if len(cats)!=1: raise ValueError(f"conflicting evidence categories for {key}: {sorted(cats)}")
        result.append({"seed_version":VERSION,"stock_code_key":key,"category":cats.pop(),
                       "raw_variants":" | ".join(sorted({r["stock_code"] for r in variants})),
                       "evidence":"COMMERCIAL_DS_002A_STOCK_CODE_INVENTORY.csv"})
    with output.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(result[0])); w.writeheader(); w.writerows(result)
    return result

def sha256(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
