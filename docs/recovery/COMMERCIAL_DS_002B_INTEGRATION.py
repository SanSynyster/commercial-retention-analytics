"""Deterministic corrected-V2 row-level taxonomy integration evidence."""
from __future__ import annotations
import hashlib, json, sys, struct
from collections import defaultdict
from decimal import Decimal
import numbers
from pathlib import Path

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import COMMERCIAL_DS_002_ANALYSIS as audit
from COMMERCIAL_DS_002B_TAXONOMY import classify, validate_seed, normalize_code, U1_CODES, ADMIN_CONTEXT, _normalise_description, _is_null, SEED_SHA256

EXPECTED_ROWS=1_044_848
FIVE_CODES={"23595","35600A","35605A","35978","84641"}
WEAK_MERCHANDISE={"15002","20852","22126","23059","35643","35956","72038B","72732","72759","DCGS0067","DCGS0073"}
REFERENCE_FILE=HERE/"COMMERCIAL_DS_003_STAGE_A_REFERENCE_PINS.json"
REFERENCE_FILE_SHA256="a96d2e9d5787dc1edd0e5c493e072ede4c342e845921e3242e90742625c8ba49"
CLASSIFIED_FRAME_COLUMNS=frozenset({"source_row_number","StockCode","InvoiceNo","Description","Country","CustomerID","Quantity","UnitPrice","InvoiceDate","category"})
EXPECTED={
"merchandise":(1038222,"19699671.127","-719677.94","18979993.187","16410709.747","2569283.44"),
"shipping":(3869,"450162.53","-15567.02","434595.51","135700.87","298894.64"),
"standalone_manual_billing":(330,"334379.51","0","334379.51","146916.08","187463.43"),
"standalone_manual_credit":(470,"0","-421770.38","-421770.38","-336332.43","-85437.95"),
"standalone_manual_zero_value":(2,"0","0","0","0","0"),
"manual_adjustment":(671,"15252.98","-3231.39","12021.59","6860.04","5161.55"),
"fee":(136,"20987.041","-277989.79","-257002.749","330.001","-257332.75"),
"bad_debt":(6,"11062.06","-158676.14","-147614.08","0","-147614.08"),
"discount":(173,"397.89","-13277.52","-12879.63","-12785.34","-94.29"),
"commission":(16,"0","-7933.43","-7933.43","-7933.43","0"),
"sample":(102,"136.85","-6137.70","-6000.85","0","-6000.85"),
"gift_voucher":(103,"1839.50","-69.56","1769.94","0","1769.94"),
"test":(17,"226.0","-22.5","203.5","203.5","0"),
"non_commercial_stock_movement":(731,"0","0","0","0","0")}

def dec(v):
    if v is None or str(v)=="nan": return Decimal(0)
    return Decimal(str(v))

def exact_integer_quantity(value, *, field="Quantity"):
    """Return an exact integer quantity; never silently truncate source data."""
    if isinstance(value,(str,bytes,bool)) or type(value).__name__ in {"bool_","bytes_"} or not isinstance(value,(numbers.Number,Decimal)):
        raise ValueError(f"{field} must be an exact integer, got {value!r}")
    try:
        number=Decimal(str(value))
    except (ValueError,TypeError,ArithmeticError):
        raise ValueError(f"{field} must be an exact integer, got {value!r}") from None
    if not number.is_finite() or number!=number.to_integral_value():
        raise ValueError(f"{field} must be an exact integer, got {value!r}")
    return int(number)

def _load_reference_pins(path, expected_sha256):
    """Hash and parse one immutable byte buffer for a frozen JSON reference."""
    reference_bytes=path.read_bytes()
    actual=hashlib.sha256(reference_bytes).hexdigest()
    if actual!=expected_sha256:
        raise AssertionError(f"reference pin file SHA-256 mismatch: {actual}")
    return json.loads(reference_bytes)

def _validate_classified_frame_schema(frame):
    """Require exactly the approved source-plus-category columns, in any order."""
    columns=list(frame.columns)
    if len(columns)!=len(set(columns)):
        raise AssertionError("validated frame contains duplicated column labels")
    actual_columns=set(columns)
    missing=CLASSIFIED_FRAME_COLUMNS-actual_columns
    unexpected=actual_columns-CLASSIFIED_FRAME_COLUMNS
    if missing or unexpected:
        raise AssertionError(f"validated frame schema mismatch: missing={sorted(missing)}, unexpected={sorted(unexpected)}")

def _stable_hash(records):
    h=hashlib.sha256()
    for record in records:
        b=json.dumps(record,ensure_ascii=False,separators=(",",":"),sort_keys=True).encode()
        h.update(struct.pack(">Q",len(b)));h.update(b)
    return h.hexdigest()

ROW_FINGERPRINT_FIELDS=("source_sha256","source_row_number","stock_code","invoice","customer_missing","customer_id","quantity","unit_price","date","country","category")
SOURCE_FINGERPRINT_FIELDS=("source_sha256","source_row_number","raw_stock_code","invoice","description","quantity","date","unit_price","customer_missing","customer_id","country")
LEGACY_ROW_FIELDS=("source_sha256","source_row_number","stock_code","invoice","customer_missing","customer_id","quantity","unit_price","date","category")

def integrity_fingerprints(records, expected_rows=None):
    rows=sorted(records,key=lambda r:r["source_row_number"])
    ids=[r["source_row_number"] for r in rows]
    if len(ids)!=len(set(ids)): raise ValueError("duplicate source row identity")
    if expected_rows is not None and len(rows)!=expected_rows: raise ValueError("source row count mismatch")
    by_customer=defaultdict(lambda:{"rows":0,"amount":Decimal(0),"source_rows":[]})
    for r in rows:
        if r["customer_missing"]: continue
        c=by_customer[r["customer_id"]];c["rows"]+=1
        c["amount"]+=Decimal(r["quantity"])*Decimal(r["unit_price"]);c["source_rows"].append(r["source_row_number"])
    summaries=[{"customer_id":k,"rows":v["rows"],"signed_amount":str(v["amount"]),"source_rows":v["source_rows"]} for k,v in sorted(by_customer.items())]
    row_records=[{k:r[k] for k in ROW_FINGERPRINT_FIELDS} for r in rows]
    legacy_records=[{k:r[k] for k in LEGACY_ROW_FIELDS} for r in rows]
    source_records=[{k:r[k] for k in SOURCE_FINGERPRINT_FIELDS} for r in rows]
    return {"row":_stable_hash(row_records),"legacy_row":_stable_hash(legacy_records),"source_content":_stable_hash(source_records),"customer":_stable_hash(summaries)},summaries

def validate_actual_classified_frame(frame):
    """Recompute Stage A integrity from the rows about to be consumed.

    This deliberately ignores reports, digests and provenance fields supplied
    by callers. The V2 source digest is an external constant in the frozen
    Stage A pin file; the row content and assignments are reconstructed here.
    """
    pins=_load_reference_pins(REFERENCE_FILE,REFERENCE_FILE_SHA256)
    if audit.sha256(audit.V1_PATH)!=pins["source_v1_sha256"] or audit.sha256(audit.V2_PATH)!=pins["source_v2_sha256"]:
        raise AssertionError("raw source bytes differ from frozen Stage A references")
    if audit.sha256(HERE/"COMMERCIAL_DS_002B_TAXONOMY_SEED.csv")!=pins["seed_sha256"]:
        raise AssertionError("authoritative taxonomy seed differs from frozen Stage A reference")
    if len(frame)!=EXPECTED_ROWS:
        raise AssertionError(f"source row count mismatch: {len(frame)}")
    _validate_classified_frame_schema(frame)
    rows=[]
    for row in frame.itertuples(index=False):
        source_id=row.source_row_number
        if isinstance(source_id,(bool,)) or not isinstance(source_id,numbers.Integral):
            raise AssertionError(f"invalid actual source-row identity: {source_id!r}")
        source_id=int(source_id)
        customer_missing=_is_null(row.CustomerID)
        if customer_missing: customer_id=None
        else:
            value=Decimal(str(row.CustomerID))
            if not value.is_finite() or value!=value.to_integral_value():
                raise AssertionError(f"invalid source customer identifier at row {source_id}")
            customer_id=str(int(value))
        if _is_null(row.InvoiceDate): raise AssertionError(f"missing source date at row {source_id}")
        try: quantity=exact_integer_quantity(row.Quantity,field=f"Quantity at row {source_id}")
        except ValueError as exc: raise AssertionError(str(exc)) from None
        if isinstance(row.UnitPrice,(str,bytes,bool)) or type(row.UnitPrice).__name__ in {"bool_","bytes_"} or not isinstance(row.UnitPrice,(numbers.Number,Decimal)):
            raise AssertionError(f"UnitPrice at row {source_id} must be numeric")
        try: unit_price=Decimal(str(row.UnitPrice))
        except (ValueError,TypeError,ArithmeticError):
            raise AssertionError(f"UnitPrice at row {source_id} must be numeric") from None
        if not unit_price.is_finite(): raise AssertionError(f"UnitPrice at row {source_id} must be finite")
        rows.append({"source_sha256":pins["source_v2_sha256"],"source_row_number":source_id,
            "raw_stock_code":str(row.StockCode),"stock_code":normalize_code(row.StockCode),
            "invoice":str(row.InvoiceNo),"description":None if _is_null(row.Description) else str(row.Description),
            "country":None if _is_null(row.Country) else str(row.Country),"customer_missing":customer_missing,
            "customer_id":customer_id,"quantity":quantity,"unit_price":str(unit_price),
            "date":row.InvoiceDate.isoformat(),"category":str(row.category)})
    fingerprints,_=integrity_fingerprints(rows,EXPECTED_ROWS)
    expected={"row":pins["row_fingerprint"],"legacy_row":pins["legacy_row_fingerprint"],
        "source_content":pins["source_content_fingerprint"],"customer":pins["customer_fingerprint"]}
    for field,value in expected.items():
        if fingerprints[field]!=value:
            raise AssertionError(f"actual classified frame {field} fingerprint mismatch: {fingerprints[field]}")
    # Category totals are also checked explicitly for legible failures.
    categories=defaultdict(lambda:{"rows":0,"positive":Decimal(0),"negative":Decimal(0),"identified":Decimal(0),"unattributed":Decimal(0)})
    for row in rows:
        amount=Decimal(row["quantity"])*Decimal(row["unit_price"])
        item=categories[row["category"]];item["rows"]+=1
        item["positive"]+=max(amount,Decimal(0));item["negative"]+=min(amount,Decimal(0))
        item["identified" if not row["customer_missing"] else "unattributed"]+=amount
    for name,expected_values in EXPECTED.items():
        item=categories[name]
        actual=(item["rows"],item["positive"],item["negative"],item["identified"],item["unattributed"])
        reference=(expected_values[0],Decimal(expected_values[1]),Decimal(expected_values[2]),Decimal(expected_values[4]),Decimal(expected_values[5]))
        if actual!=reference: raise AssertionError(f"actual classified category reference mismatch for {name}: {actual} != {reference}")
    if set(categories)!=set(EXPECTED): raise AssertionError(f"unexpected taxonomy category set: {sorted(categories)}")
    return fingerprints

def row_customer_fingerprints(records, expected_rows=None):
    hashes,summaries=integrity_fingerprints(records,expected_rows)
    return hashes["row"],hashes["customer"],summaries

def classify_corrected_rows(corrected, seed=None):
    """Return a copy of corrected V2 with classifier output; never mutates source."""
    seed=seed or validate_seed(HERE/"COMMERCIAL_DS_002B_TAXONOMY_SEED.csv")
    keys=corrected.StockCode.map(normalize_code)
    is_merch=keys.map(lambda c: seed.get(c)=="merchandise")
    admin_mask=corrected.apply(lambda r: (normalize_code(r.StockCode),_normalise_description(r.Description)) in ADMIN_CONTEXT
                               and dec(r.UnitPrice)==0 and _is_null(r.CustomerID),axis=1)
    line_amount=corrected.Quantity*corrected.UnitPrice
    cancellation=corrected.InvoiceNo.astype(str).str.startswith("C")
    qualifies=is_merch & ~admin_mask & ((~cancellation & (line_amount>0)) | (cancellation & (line_amount!=0)))
    merchandise_invoices=set(corrected.loc[qualifies,"InvoiceNo"].astype(str))
    result=corrected.copy()
    categories=[]
    for row in corrected.itertuples(index=False):
        categories.append(classify({"StockCode":row.StockCode,"Description":row.Description,"Quantity":row.Quantity,
            "UnitPrice":row.UnitPrice,"CustomerID":row.CustomerID,
            "invoice_has_merchandise":str(row.InvoiceNo) in merchandise_invoices},seed))
    result["category"]=categories
    return result

def assert_integrity(records, expected_rows, expected_row_hash, expected_customer_hash, expected_source_hash=None):
    hashes,_=integrity_fingerprints(records,expected_rows)
    if hashes["row"]!=expected_row_hash: raise AssertionError("source-row integrity fingerprint mismatch")
    if hashes["customer"]!=expected_customer_hash: raise AssertionError("customer-attribution fingerprint mismatch")
    if expected_source_hash is not None and hashes["source_content"]!=expected_source_hash: raise AssertionError("source-content fingerprint mismatch")

def _calculate_report(seed_path=None, include_classified=False):
    seed=validate_seed(seed_path or HERE/"COMMERCIAL_DS_002B_TAXONOMY_SEED.csv")
    v1,v2,integrity=audit.load_sources()
    corrected,block=audit.source_block_evidence(v1,v2)
    if len(corrected)!=EXPECTED_ROWS: raise AssertionError(f"corrected row count {len(corrected)}")
    # Shared row-classifier is also consumed by the production occasion builder.
    classified_frame=classify_corrected_rows(corrected,seed)
    merch_invoices=set(classified_frame.loc[(corrected.StockCode.map(normalize_code)=="M") & (classified_frame.category=="manual_adjustment"),"InvoiceNo"].astype(str))
    keys=corrected.StockCode.map(normalize_code)
    category=defaultdict(lambda:{"rows":0,"signed_amount":"0","identifiable_rows":0,"identifiable_amount":"0","unattributed_rows":0,"unattributed_amount":"0","positive_rows":0,"negative_rows":0,"zero_rows":0})
    classified=[]; seed_rows=context_rows=0; row_records=[]; m_positive_negative=defaultdict(Decimal)
    for row,cat in zip(corrected.itertuples(index=False),classified_frame.category.tolist()):
        code=normalize_code(row.StockCode)
        contextual=cat=="non_commercial_stock_movement" or code=="M"
        context_rows += int(contextual); seed_rows += int(not contextual)
        amount=dec(row.Quantity)*dec(row.UnitPrice); identified=not _is_null(row.CustomerID)
        d=category[cat]; d["rows"]+=1
        d["signed_amount"]=str(Decimal(d["signed_amount"])+amount)
        field="identifiable" if identified else "unattributed"
        d[f"{field}_rows"]+=1; d[f"{field}_amount"]=str(Decimal(d[f"{field}_amount"])+amount)
        positive=max(amount,Decimal(0));negative=min(amount,Decimal(0))
        d["positive_rows"]+=int(amount>0);d["negative_rows"]+=int(amount<0);d["zero_rows"]+=int(amount==0)
        d["positive_amount"]=str(Decimal(d.get("positive_amount","0"))+positive)
        d["negative_amount"]=str(Decimal(d.get("negative_amount","0"))+negative)
        source_row=int(row.source_row_number)
        customer_id=None if not identified else str(int(row.CustomerID))
        quantity=exact_integer_quantity(row.Quantity,field=f"Quantity at row {source_row}")
        row_records.append({"source_sha256":integrity["v2"],"source_row_number":source_row,"raw_stock_code":str(row.StockCode),"stock_code":normalize_code(row.StockCode),"invoice":str(row.InvoiceNo),"description":None if _is_null(row.Description) else str(row.Description),"country":None if _is_null(row.Country) else str(row.Country),"customer_missing":customer_id is None,"customer_id":customer_id,"quantity":quantity,"unit_price":str(dec(row.UnitPrice)),"date":row.InvoiceDate.isoformat(),"category":cat})
        if code=="M":
            group="embedded" if str(row.InvoiceNo) in merch_invoices else "standalone"
            sign="positive" if amount>0 else "negative" if amount<0 else "zero"
            m_positive_negative[f"{group}_{sign}"]+=amount
        classified.append(cat)
    # Stable amount serialization and category ordering.
    categories={k:category[k] for k in sorted(category)}
    # Category-sensitive frozen reference check; never derived via classify().
    for name,expected in EXPECTED.items():
        d=categories[name]
        actual=(d["rows"],d["positive_amount"],d["negative_amount"],d["signed_amount"],d["identifiable_amount"],d["unattributed_amount"])
        if actual[0]!=expected[0] or tuple(map(Decimal,actual[1:]))!=tuple(map(Decimal,expected[1:])):
            raise AssertionError(f"category reference mismatch for {name}: {actual} != {expected}")
    bycode=defaultdict(lambda:{"rows":0,"amount":"0"})
    weak=defaultdict(lambda:{"rows":0,"signed_amount":Decimal(0),"identifiable_rows":0,"positive_rows":0,"negative_rows":0,"categories":defaultdict(int)})
    m_sign=defaultdict(lambda:{"rows":0,"invoices":set(),"customers":set(),"positive_amount":Decimal(0),"negative_amount":Decimal(0),"zero_rows":0,"identifiable_amount":Decimal(0),"unattributed_amount":Decimal(0)})
    m={"standalone":{"rows":0,"invoices":set(),"customers":set(),"amount":Decimal(0)},"embedded":{"rows":0,"invoices":set(),"customers":set(),"amount":Decimal(0)}}
    admin_count=0; u1_rows=0
    for row,cat in zip(corrected.itertuples(index=False),classified):
        code=normalize_code(row.StockCode); amount=dec(row.Quantity)*dec(row.UnitPrice)
        if code in U1_CODES:u1_rows+=1
        if code in FIVE_CODES:
            x=bycode[code];x["rows"]+=1;x["amount"]=str(Decimal(x["amount"])+amount)
        if code in WEAK_MERCHANDISE:
            x=weak[code];x["rows"]+=1;x["signed_amount"]+=amount;x["identifiable_rows"]+=int(not _is_null(row.CustomerID));x["positive_rows"]+=int(amount>0);x["negative_rows"]+=int(amount<0);x["categories"][cat]+=1
        if cat=="non_commercial_stock_movement" and code not in U1_CODES and code not in FIVE_CODES: admin_count+=1
        if code=="M":
            kind="embedded" if str(row.InvoiceNo) in merch_invoices else "standalone"
            x=m[kind];x["rows"]+=1;x["invoices"].add(str(row.InvoiceNo));x["amount"]+=amount
            if not _is_null(row.CustomerID):x["customers"].add(str(int(row.CustomerID)))
            sign="positive" if amount>0 else "negative" if amount<0 else "zero"
            ms=m_sign[f"{kind}_{sign}"];ms["rows"]+=1;ms["invoices"].add(str(row.InvoiceNo))
            if not _is_null(row.CustomerID):ms["customers"].add(str(int(row.CustomerID)));ms["identifiable_amount"]+=amount
            else:ms["unattributed_amount"]+=amount
            if amount>0:ms["positive_amount"]+=amount
            elif amount<0:ms["negative_amount"]+=amount
            else:ms["zero_rows"]+=1
    m_out={k:{"rows":v["rows"],"invoices":len(v["invoices"]),"customers":len(v["customers"]),"signed_amount":str(v["amount"])} for k,v in m.items()}
    row_records.sort(key=lambda r:r["source_row_number"])
    fingerprints,customer_records=integrity_fingerprints(row_records,EXPECTED_ROWS)
    unclassified_rows=sum(cat=="unclassified" for cat in classified)
    unclassified_commercial=sum(1 for row,cat in zip(corrected.itertuples(index=False),classified)
        if cat=="unclassified" and (dec(row.Quantity)*dec(row.UnitPrice)!=0 or not _is_null(row.CustomerID)))
    report={"source_sha256":integrity,"inventory_sha256":audit.sha256(HERE/"COMMERCIAL_DS_002A_STOCK_CODE_INVENTORY.csv"),"seed_sha256":audit.sha256(HERE/"COMMERCIAL_DS_002B_TAXONOMY_SEED.csv"),"seed_version":"commercial-ds-002b-v1",
       "corrected_v2_rows":len(corrected),"overlap_rows_removed":block["overlap_rows_each"],"overlap_removed_raw_source_rows":[block["removed_raw_source_row_start"],block["removed_raw_source_row_end_inclusive"]],"seed_classified_rows":seed_rows,"context_classified_rows":context_rows,"unclassified_rows":unclassified_rows,"unclassified_commercially_relevant_rows":unclassified_commercial,
       "category_totals":categories,"canonical_key_coverage":{"observed":len(set(keys)),"seed_mapped":len(set(keys)&set(seed)),"context_only_unmapped":len(set(keys)-set(seed)),"coverage_fraction":str(Decimal(len(set(keys)&set(seed)))/Decimal(len(set(keys))) )},
       "u1":{"codes":len(U1_CODES),"rows":u1_rows},"inventory_adjustment_codes":{k:bycode[k] for k in sorted(FIVE_CODES)},"administrative_description_exception_rows":admin_count,"manual_invoice_context":m_out,
       "weak_merchandise_codes":{k:{"rows":v["rows"],"signed_amount":str(v["signed_amount"]),"identifiable_rows":v["identifiable_rows"],"positive_rows":v["positive_rows"],"negative_rows":v["negative_rows"],"categories":dict(sorted(v["categories"].items()))} for k,v in sorted(weak.items())},
       "manual_M_positive_negative":{k:str(v) for k,v in sorted(m_positive_negative.items())},
       "manual_M_categories":{k:{"rows":v["rows"],"invoices":len(v["invoices"]),"customers":len(v["customers"]),"positive_amount":str(v["positive_amount"]),"negative_amount":str(v["negative_amount"]),"signed_amount":str(v["positive_amount"]+v["negative_amount"]),"zero_rows":v["zero_rows"],"identifiable_amount":str(v["identifiable_amount"]),"unattributed_amount":str(v["unattributed_amount"])} for k,v in sorted(m_sign.items())},
       "row_identity":{"rows":len(row_records),"sha256":fingerprints["row"],"legacy_sha256":fingerprints["legacy_row"],"source_row_min":row_records[0]["source_row_number"],"source_row_max":row_records[-1]["source_row_number"]},
       "source_content_integrity":{"sha256":fingerprints["source_content"],"includes":["source_row_number","raw_stock_code","invoice","description","quantity","date","unit_price","customer/null status","country"]},
       "customer_integrity":{"identified_customers":len(customer_records),"sha256":fingerprints["customer"],"identified_rows":sum(x["rows"] for x in customer_records),"identified_signed_amount":str(sum((Decimal(x["signed_amount"]) for x in customer_records),Decimal(0)))},
       "source_reconciliation":{"row_count_exact":len(corrected)==EXPECTED_ROWS,"category_rows_sum":sum(v["rows"] for v in categories.values()),"rows_reconcile":sum(v["rows"] for v in categories.values())==len(corrected),"signed_amount_all":str(sum((Decimal(v["signed_amount"]) for v in categories.values()),Decimal(0))),"identifiable_signed_amount":str(sum((Decimal(v["identifiable_amount"]) for v in categories.values()),Decimal(0))),"unattributed_signed_amount":str(sum((Decimal(v["unattributed_amount"]) for v in categories.values()),Decimal(0)))} }
    return (report,classified_frame) if include_classified else report

def validate_reference_pins(report):
    pins=_load_reference_pins(REFERENCE_FILE,REFERENCE_FILE_SHA256)
    pairs={"source_v1_sha256":report["source_sha256"]["v1"],"source_v2_sha256":report["source_sha256"]["v2"],
           "seed_sha256":report["seed_sha256"],"row_fingerprint":report["row_identity"]["sha256"],
           "legacy_row_fingerprint":report["row_identity"]["legacy_sha256"],"source_content_fingerprint":report["source_content_integrity"]["sha256"],
           "customer_fingerprint":report["customer_integrity"]["sha256"]}
    for key,value in pairs.items():
        if pins.get(key)!=value: raise AssertionError(f"frozen reference mismatch: {key}: {value}")
    if pins.get("corrected_v2_rows")!=report["corrected_v2_rows"]: raise AssertionError("frozen reference mismatch: corrected_v2_rows")
    if pins.get("overlap_removed_raw_source_rows_zero_based_inclusive")!=report["overlap_removed_raw_source_rows"]: raise AssertionError("frozen reference mismatch: overlap source-row interval")
    return report

def build_report(seed_path=None):
    return validate_reference_pins(_calculate_report(seed_path))

def build_report_and_classified_rows():
    """Same frozen-pin validation as build_report plus the classified source frame."""
    report,frame=_calculate_report(include_classified=True)
    validate_reference_pins(report)
    return report,frame

if __name__=="__main__": print(json.dumps(build_report(),sort_keys=True,indent=2))
