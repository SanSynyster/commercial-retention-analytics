"""Stage B1 production purchase-occasion builder for corrected V2.

This is contract infrastructure only. It does not build cohorts, labels,
retention outcomes, or a revenue bridge.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
import hashlib
import json
import numbers
from pathlib import Path
import re
import struct
import sys

import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from COMMERCIAL_DS_002B_INTEGRATION import (build_report_and_classified_rows,
    validate_reference_pins, validate_actual_classified_frame,
    _load_reference_pins)
from COMMERCIAL_DS_002B_TAXONOMY import SEED_SHA256

OBSERVATION_START=date(2009,12,1)
OBSERVATION_END_EXCLUSIVE=date(2011,12,10)  # last observed day is 2011-12-09
DATA_END_TIMESTAMP=datetime(2011,12,9,12,50)
DATA_END_DATE=date(2011,12,9)
ACQUISITION_CUTOFF=date(2010,12,1)  # 12 calendar months after observation start
PRIMARY_REPEAT_DAYS=90
OCCASION_REFERENCE_FILE=HERE/"COMMERCIAL_DS_003_STAGE_B2A_REFERENCE_PINS.json"
OCCASION_REFERENCE_FILE_SHA256="4cf7b761a1b02cea853dbe577af7dddf8070fe65d0dcdfc7a71e2a064986f433"
_VALIDATION_TOKEN=object()


@dataclass(frozen=True)
class _ValidatedPurchaseInput:
    """Sealed source/taxonomy frame, minted only after frozen Stage A checks."""
    _frame: pd.DataFrame=field(repr=False,compare=False)
    _integrity_report: dict=field(repr=False,compare=False)
    _content_digest: str
    _token: object=field(repr=False,compare=False)


def _is_missing(value):
    if value is None or value is pd.NA or value is pd.NaT:
        return True
    if isinstance(value,str):
        return False
    try:
        result=pd.isna(value)
        return bool(result) if isinstance(result,(bool,np.bool_)) else False
    except (TypeError,ValueError):
        return False


def canonical_customer_id(value):
    """Return a positive canonical integer ID; never parse a text identifier."""
    if _is_missing(value):
        return None
    if isinstance(value,(bool,np.bool_)) or isinstance(value,str) or not isinstance(value,(numbers.Real,Decimal,np.integer,np.floating)):
        raise ValueError(f"ambiguous/non-numeric customer identifier: {value!r}")
    if isinstance(value,(float,np.floating)) and abs(value)>2**53:
        raise ValueError(f"customer identifier exceeds lossless numeric bound: {value!r}")
    try:
        number=Decimal(str(value))
    except (InvalidOperation,ValueError,TypeError):
        raise ValueError(f"invalid customer identifier: {value!r}") from None
    if not number.is_finite() or number!=number.to_integral_value():
        raise ValueError(f"customer identifier is not an integer: {value!r}")
    canonical=int(number)
    if canonical<=0:
        raise ValueError(f"customer identifier must be positive: {value!r}")
    return str(canonical)


def _decimal_source_value(value, field):
    if isinstance(value,(bool,np.bool_)) or isinstance(value,str) or _is_missing(value):
        raise ValueError(f"{field} must be a non-null numeric source value: {value!r}")
    try:
        result=Decimal(str(value))
    except (InvalidOperation,ValueError,TypeError):
        raise ValueError(f"invalid {field}: {value!r}") from None
    if not result.is_finite():
        raise ValueError(f"non-finite {field}: {value!r}")
    return result


def _invoice_id(value):
    if _is_missing(value):
        raise ValueError(f"missing invoice identifier: {value!r}")
    if not isinstance(value,str) or not re.fullmatch(r"(?:[0-9]+|[cC][0-9]+|A[0-9]+)",value):
        raise ValueError(f"invalid invoice identifier; expected digits, C+digits cancellation, or A+digits adjustment: {value!r}")
    return value


def _transaction_timestamp(value):
    if _is_missing(value):
        raise ValueError("missing transaction timestamp")
    if not isinstance(value,(pd.Timestamp,datetime)):
        raise TypeError(f"transaction timestamp must be a typed datetime, got {type(value).__name__}")
    stamp=pd.Timestamp(value)
    if pd.isna(stamp): raise ValueError("missing transaction timestamp")
    if stamp.tzinfo is not None: raise ValueError("timezone-aware transaction timestamp is unsupported")
    return stamp.to_pydatetime()


def _validate_source_ids(frame):
    if "source_row_number" not in frame.columns:
        raise ValueError("source_row_number is required; use the approved raw source loader")
    values=frame["source_row_number"].tolist()
    ids=[]
    for value in values:
        if isinstance(value,(bool,np.bool_)) or not isinstance(value,(numbers.Integral,np.integer)):
            raise ValueError(f"invalid source_row_number: {value!r}")
        n=int(value)
        if n<0: raise ValueError(f"negative source_row_number: {n}")
        ids.append(n)
    if len(ids)!=len(set(ids)):
        raise ValueError("duplicate source_row_number identities")
    return ids


def _build_purchase_occasions_for_test(classified_rows):
    """Explicitly non-production row constructor for synthetic fixtures only."""
    source_ids=_validate_source_ids(classified_rows)
    required={"category","CustomerID","InvoiceNo","InvoiceDate","Quantity","UnitPrice"}
    missing=required-set(classified_rows.columns)
    if missing: raise ValueError(f"missing occasion input columns: {sorted(missing)}")

    # Invoice/customer integrity spans all identified rows, not only eligible
    # merchandise rows. Distinct source numeric encodings of one integer ID
    # resolve to the same documented canonical customer key.
    invoice_customers=defaultdict(set);invoice_dates=defaultdict(set)
    normalized=[]
    for pos,row in enumerate(classified_rows.itertuples(index=False)):
        customer=canonical_customer_id(row.CustomerID)
        invoice=_invoice_id(row.InvoiceNo)
        timestamp=_transaction_timestamp(row.InvoiceDate)
        normalized.append((customer,invoice,timestamp))
        invoice_dates[invoice].add(timestamp.date())
        if customer is not None: invoice_customers[invoice].add(customer)
    collisions={invoice:sorted(ids) for invoice,ids in invoice_customers.items() if len(ids)>1}
    if collisions:
        raise ValueError(f"invoice has multiple identified customers: {next(iter(sorted(collisions.items())))}")
    date_conflicts={invoice:sorted(days) for invoice,days in invoice_dates.items() if len(days)>1}
    if date_conflicts:
        raise ValueError(f"invoice has inconsistent calendar dates: {next(iter(sorted(date_conflicts.items())))}")

    groups=defaultdict(list)
    exclusions=defaultdict(int)
    for pos,row in enumerate(classified_rows.itertuples(index=False)):
        customer,invoice,timestamp=normalized[pos]
        if row.category!="merchandise": exclusions["non_merchandise_category"]+=1;continue
        if invoice.startswith("A"): exclusions["administrative_invoice_id"]+=1;continue
        quantity=_decimal_source_value(row.Quantity,"quantity")
        price=_decimal_source_value(row.UnitPrice,"unit price")
        if quantity!=quantity.to_integral_value(): exclusions["non_integral_quantity"]+=1;continue
        if quantity<=0: exclusions["non_positive_quantity"]+=1;continue
        if price<=0: exclusions["non_positive_unit_price"]+=1;continue
        if customer is None: exclusions["missing_customer"]+=1;continue
        # Case-insensitive source prefix catches lowercase c; surrounding
        # whitespace has already failed validation rather than being stripped.
        if invoice[:1].casefold()=="c": exclusions["cancellation_invoice"]+=1;continue
        if timestamp.date()<OBSERVATION_START or timestamp>DATA_END_TIMESTAMP:
            exclusions["outside_observation_window"]+=1;continue
        groups[(customer,invoice)].append({"source_row_number":source_ids[pos],"date":timestamp.date(),
            "quantity":int(quantity),"unit_price":price,"line_gross":Decimal(int(quantity))*price})

    occasions=[]
    for (customer,invoice),lines in groups.items():
        days={line["date"] for line in lines}
        if len(days)!=1:
            raise ValueError(f"eligible lines in invoice {invoice} disagree on calendar date")
        lines.sort(key=lambda x:x["source_row_number"])
        occasions.append({"customer_id":customer,"invoice_id":invoice,"transaction_date":next(iter(days)).isoformat(),
            "qualifying_gross_merchandise":str(sum((line["line_gross"] for line in lines),Decimal(0))),
            "eligible_line_count":len(lines),"source_row_numbers":[line["source_row_number"] for line in lines]})
    occasions.sort(key=lambda x:(x["customer_id"],x["transaction_date"],x["invoice_id"]))
    summary={"occasion_count":len(occasions),"customer_count":len({o["customer_id"] for o in occasions}),
        "qualifying_line_count":sum(o["eligible_line_count"] for o in occasions),
        "qualifying_gross_merchandise":str(sum((Decimal(o["qualifying_gross_merchandise"]) for o in occasions),Decimal(0))),
        "excluded_rows_by_reason":dict(sorted(exclusions.items()))}
    return occasions,summary


def _frame_content_digest(frame):
    """Mutation guard for the sealed in-memory frame (separate from source pins)."""
    ordered=frame.sort_values("source_row_number",kind="mergesort").reset_index(drop=True)
    digest=hashlib.sha256()
    schema=json.dumps({"columns":[str(c) for c in ordered.columns],"dtypes":[str(t) for t in ordered.dtypes],"rows":len(ordered)},separators=(",",":"),sort_keys=True).encode()
    digest.update(struct.pack(">Q",len(schema)));digest.update(schema)
    hashed=pd.util.hash_pandas_object(ordered,index=False,categorize=True).to_numpy(dtype="uint64",copy=False).tobytes()
    digest.update(struct.pack(">Q",len(hashed)));digest.update(hashed)
    return digest.hexdigest()


def load_validated_purchase_input():
    """Only supported production constructor; validates frozen source/taxonomy first."""
    report,frame=build_report_and_classified_rows()
    if report["seed_sha256"]!=SEED_SHA256: raise AssertionError("validated input taxonomy seed mismatch")
    digest=_frame_content_digest(frame)
    return _ValidatedPurchaseInput(frame.copy(deep=True),report,digest,_VALIDATION_TOKEN)


def _validate_purchase_input(value):
    if not isinstance(value,_ValidatedPurchaseInput) or value._token is not _VALIDATION_TOKEN:
        raise TypeError("production purchase construction requires load_validated_purchase_input() output")
    if _frame_content_digest(value._frame)!=value._content_digest:
        raise AssertionError("validated source/taxonomy frame changed after validation")
    # A matching cached digest or forged report is not provenance. Recompute
    # the reviewed Stage A fingerprints from the actual rows consumed.
    validate_actual_classified_frame(value._frame)
    if value._integrity_report.get("seed_sha256")!=SEED_SHA256:
        raise AssertionError("validated input seed reference mismatch")
    validate_reference_pins(value._integrity_report)
    return value


def build_purchase_occasions(validated_input):
    """Production builder; arbitrary DataFrames cannot enter this boundary."""
    trusted=_validate_purchase_input(validated_input)
    return _build_trusted_purchase_occasions(trusted)


def _build_trusted_purchase_occasions(trusted):
    """Internal construction after the caller has crossed the production gate."""
    occasions,summary=_build_purchase_occasions_for_test(trusted._frame)
    _validate_occasions_against_frozen_reference(occasions,summary,trusted._integrity_report)
    return occasions,summary


def _records_fingerprint(records):
    digest=hashlib.sha256()
    for record in records:
        payload=json.dumps(record,ensure_ascii=False,separators=(",",":"),sort_keys=True).encode()
        digest.update(struct.pack(">Q",len(payload)));digest.update(payload)
    return digest.hexdigest()


def _occasion_fingerprints(occasions):
    normalized=[];lineage=[];all_sources=[]
    for occasion in occasions:
        item={key:occasion[key] for key in ("customer_id","invoice_id","transaction_date","qualifying_gross_merchandise","eligible_line_count","source_row_numbers")}
        ids=item["source_row_numbers"]
        if ids!=sorted(ids) or len(ids)!=len(set(ids)):
            raise AssertionError("occasion source-row lineage must be sorted and unique")
        normalized.append(item)
        for source_id in ids:
            all_sources.append(source_id)
            lineage.append({"customer_id":item["customer_id"],"invoice_id":item["invoice_id"],
                "transaction_date":item["transaction_date"],"source_row_number":source_id})
    if len(all_sources)!=len(set(all_sources)):
        raise AssertionError("qualifying source row appears in more than one occasion")
    return _records_fingerprint(normalized),_records_fingerprint(lineage),len(all_sources)


def _validate_occasions_against_frozen_reference(occasions,summary,integrity_report):
    pins=_load_reference_pins(OCCASION_REFERENCE_FILE,OCCASION_REFERENCE_FILE_SHA256)
    if pins["source_v2_sha256"]!=integrity_report["source_sha256"]["v2"]: raise AssertionError("occasion source reference mismatch")
    if pins["seed_sha256"]!=integrity_report["seed_sha256"]: raise AssertionError("occasion taxonomy reference mismatch")
    if pins["source_row_fingerprint"]!=integrity_report["row_identity"]["sha256"]: raise AssertionError("occasion source-row reference mismatch")
    expected=pins["summary"]
    for key in ("qualifying_line_count","occasion_count","customer_count","qualifying_gross_merchandise"):
        if summary[key]!=expected[key]: raise AssertionError(f"frozen occasion reference mismatch: {key}: {summary[key]} != {expected[key]}")
    occasion_hash,lineage_hash,line_count=_occasion_fingerprints(occasions)
    if line_count!=summary["qualifying_line_count"]: raise AssertionError("occasion lineage row count mismatch")
    if occasion_hash!=pins["occasion_fingerprint_sha256"]: raise AssertionError("frozen occasion fingerprint mismatch")
    if lineage_hash!=pins["lineage_fingerprint_sha256"]: raise AssertionError("frozen occasion lineage fingerprint mismatch")
    return {"occasion_fingerprint_sha256":occasion_hash,"lineage_fingerprint_sha256":lineage_hash,"lineage_rows":line_count}


def _validated_timestamp_input(value,name="timestamp"):
    if _is_missing(value): raise ValueError(f"{name} is missing")
    if not isinstance(value,(pd.Timestamp,datetime)):
        raise TypeError(f"{name} requires a typed timezone-naive timestamp, got {type(value).__name__}")
    stamp=pd.Timestamp(value)
    if pd.isna(stamp): raise ValueError(f"{name} is missing")
    if stamp.tzinfo is not None: raise ValueError(f"{name} must be timezone-naive")
    return stamp.to_pydatetime()


def summarize_repeat_purchases(occasions):
    """Deterministic 90-day date-level primary and invoice-level sensitivity."""
    by_customer=defaultdict(list)
    for item in occasions:
        stamp=_validated_timestamp_input(item["transaction_timestamp"],"occasion transaction_timestamp")
        lineage=tuple(item["source_row_numbers"])
        by_customer[str(item["customer_id"])].append((stamp.date(),str(item["invoice_id"]),lineage))
    date_repeat_customers=invoice_repeat_customers=0
    for customer,rows in by_customer.items():
        rows.sort(key=lambda x:(x[0],x[1],x[2]))
        days=sorted({row[0] for row in rows})
        if len(days)>1 and any(primary_later_day_repeat(datetime.combine(days[0],datetime.min.time()),datetime.combine(day,datetime.min.time())) for day in days[1:]):
            date_repeat_customers+=1
        first=rows[0]
        if any(invoice_level_repeat(datetime.combine(first[0],datetime.min.time()),first[1],
                datetime.combine(row[0],datetime.min.time()),row[1]) for row in rows[1:]):
            invoice_repeat_customers+=1
    return {"window_days":PRIMARY_REPEAT_DAYS,"primary_metric":"date_level_repeat_customers",
        "date_level_repeat_customers":date_repeat_customers,"invoice_level_sensitivity_repeat_customers":invoice_repeat_customers,
        "invoice_level_same_day_later_invoice_counts":True,"boundary":"[first occasion date, first date + 90 days)"}


def _calendar_day(value, name):
    stamp=_transaction_timestamp(value)
    return stamp.date()


def _anchor_day(value, name="anchor"):
    stamp=_transaction_timestamp(value)
    if stamp.time()!=datetime.min.time():
        raise ValueError(f"{name} must be normalized to local midnight")
    return stamp.date()


def _positive_days(value):
    if isinstance(value,(bool,np.bool_)) or not isinstance(value,(int,np.integer)) or int(value)<=0:
        raise ValueError("horizon/lookback must be a positive integer number of calendar days")
    return int(value)


def primary_later_day_repeat(first_timestamp, second_timestamp, horizon_days=PRIMARY_REPEAT_DAYS):
    """The primary repeat boundary is d1 < d2 < d1 + h local calendar days."""
    h=_positive_days(horizon_days)
    d1=_calendar_day(first_timestamp,"first timestamp");d2=_calendar_day(second_timestamp,"second timestamp")
    return d1<d2<d1+timedelta(days=h)


def invoice_level_repeat(first_timestamp, first_invoice_id, second_timestamp, second_invoice_id,
                         horizon_days=PRIMARY_REPEAT_DAYS):
    """Sensitivity; sort by local date and invoice ID. Later same-day IDs count."""
    h=_positive_days(horizon_days)
    if first_invoice_id==second_invoice_id: return False
    first_day=_calendar_day(first_timestamp,"first timestamp")
    second_day=_calendar_day(second_timestamp,"second timestamp")
    ordered=sorted(((first_day,str(first_invoice_id)),(second_day,str(second_invoice_id))))
    start=ordered[0][0];candidate=ordered[1][0]
    return start<=candidate<start+timedelta(days=h)


def label_is_mature(anchor_date, horizon_days=PRIMARY_REPEAT_DAYS):
    """Reviewed date-level maturity: anchor + h must not exceed data-end date."""
    anchor=_anchor_day(anchor_date)
    h=_positive_days(horizon_days)
    return anchor+timedelta(days=h)<=DATA_END_DATE


def feature_window_contains(transaction_date, anchor_date, lookback_days):
    """Half-open feature window [T-lookback, T); never includes anchor/future."""
    transaction=_calendar_day(transaction_date,"transaction timestamp");anchor=_anchor_day(anchor_date)
    lookback=_positive_days(lookback_days)
    start=anchor-timedelta(days=lookback)
    return start<=transaction<anchor


def rows_before_anchor(frame, anchor_timestamp):
    """Point-in-time guard: return only rows whose local transaction date is < T."""
    anchor=_anchor_day(anchor_timestamp)
    if "InvoiceDate" not in frame.columns: raise ValueError("InvoiceDate is required for point-in-time filtering")
    timestamps=[_transaction_timestamp(v) for v in frame["InvoiceDate"].tolist()]
    mask=[stamp.date()<anchor for stamp in timestamps]
    return frame.loc[mask].copy()


def build_real_data_report(validated_input=None):
    """Validated production entry point; does not accept arbitrary row frames."""
    validated=load_validated_purchase_input() if validated_input is None else _validate_purchase_input(validated_input)
    integrity=validated._integrity_report
    classified=validated._frame
    corrected=classified
    occasions,summary=_build_trusted_purchase_occasions(validated)
    occasion_hash,lineage_hash,lineage_rows=_occasion_fingerprints(occasions)
    occasion_integrity={"occasion_fingerprint_sha256":occasion_hash,
        "lineage_fingerprint_sha256":lineage_hash,"lineage_rows":lineage_rows}
    timestamped_occasions=[{**item,"transaction_timestamp":datetime.combine(date.fromisoformat(item["transaction_date"]),datetime.min.time())} for item in occasions]
    repeat_summary=summarize_repeat_purchases(timestamped_occasions)

    # Diagnostic only: do not publish a primary acquisition cohort without the
    # owner's explicit decision on prior identified non-merchandise activity.
    first_occasion_date={}
    for occasion in occasions:
        customer=occasion["customer_id"];day=date.fromisoformat(occasion["transaction_date"])
        first_occasion_date[customer]=min(day,first_occasion_date.get(customer,day))
    candidate_customers={customer for customer,day in first_occasion_date.items() if day>=ACQUISITION_CUTOFF}
    prior_identified_before_cutoff=set();prior_identified_before_first=set()
    for row in corrected.itertuples(index=False):
        day=pd.Timestamp(row.InvoiceDate).date()
        cid=canonical_customer_id(row.CustomerID)
        if cid is None: continue
        if day<ACQUISITION_CUTOFF: prior_identified_before_cutoff.add(cid)
        if cid in first_occasion_date and day<first_occasion_date[cid]: prior_identified_before_first.add(cid)
    fixed_cutoff_overlap=candidate_customers & prior_identified_before_cutoff
    first_occasion_overlap=candidate_customers & prior_identified_before_first
    acquisition_diagnostic={"cutoff_inclusive":ACQUISITION_CUTOFF.isoformat(),
        "merchandise_only_lookback_sensitivity_customers":len(candidate_customers),
        "fixed_cutoff_prior_identified_activity_customers":len(fixed_cutoff_overlap),
        "fixed_cutoff_adjusted_diagnostic_customers":len(candidate_customers-fixed_cutoff_overlap),
        "before_first_occasion_prior_identified_activity_customers":len(first_occasion_overlap),
        "before_first_occasion_adjusted_diagnostic_customers":len(candidate_customers-first_occasion_overlap),
        "primary_cohort_published":False,
        "approval_status":"PENDING_OWNER_APPROVAL"}
    return {"source_sha256":integrity["source_sha256"],"seed_sha256":integrity["seed_sha256"],
        "classification_row_fingerprint":integrity["row_identity"]["sha256"],"corrected_v2_rows":integrity["corrected_v2_rows"],
        "purchase_occasion_summary":summary,"purchase_occasion_integrity":occasion_integrity,
        "repeat_purchase_summary":repeat_summary,"acquisition_proxy_diagnostic":acquisition_diagnostic,
        "occasions":occasions}


def main():
    print(json.dumps(build_real_data_report(),sort_keys=True,indent=2,separators=(",",": ")))


if __name__=="__main__": main()
