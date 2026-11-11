"""Exact-Decimal commercial line bridge for corrected V2; not a P&L."""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, InvalidOperation
import json
import hashlib
import struct
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import pandas as pd

from COMMERCIAL_DS_003_PURCHASE_OCCASIONS import (
    _validate_purchase_input, _build_trusted_purchase_occasions,
    canonical_customer_id, load_validated_purchase_input,
)
from COMMERCIAL_DS_002B_INTEGRATION import _load_reference_pins
from COMMERCIAL_DS_002B_TAXONOMY import normalize_code

EXPECTED_SOURCE_ROWS=1_044_848
EXPECTED_SOURCE_SIGNED=Decimal("18909762.118")
EXPECTED_IDENTIFIABLE_SIGNED=Decimal("16343669.038")
EXPECTED_UNATTRIBUTED_SIGNED=Decimal("2566093.08")
BRIDGE_REFERENCE_FILE=HERE/"COMMERCIAL_DS_003_STAGE_B2A_BRIDGE_REFERENCE_PINS.json"
BRIDGE_REFERENCE_FILE_SHA256="765ff7a29530b4221ec3ab171fc2ed861fcb9247901ba84419d2ecf7e786e96d"


def _amount(quantity,unit_price):
    try:
        q=Decimal(str(quantity));p=Decimal(str(unit_price))
    except (InvalidOperation,ValueError,TypeError):
        raise ValueError(f"invalid source amount components: {quantity!r} × {unit_price!r}") from None
    if not q.is_finite() or not p.is_finite(): raise ValueError("non-finite source amount components")
    return q*p


def _membership_fingerprint(source_ids):
    """Collision-safe digest of canonical, sorted raw source-row identities."""
    digest=hashlib.sha256()
    for source_id in sorted(source_ids):
        payload=json.dumps(int(source_id),separators=(",",":" )).encode()
        digest.update(struct.pack(">Q",len(payload)));digest.update(payload)
    return digest.hexdigest()


def _validate_bridge_against_frozen_references(leaves, source_reconciliation):
    pins=_load_reference_pins(BRIDGE_REFERENCE_FILE,BRIDGE_REFERENCE_FILE_SHA256)
    if set(leaves)!=set(pins["categories"]):
        raise AssertionError("bridge category set differs from frozen references")
    for name,reference in pins["categories"].items():
        actual=leaves[name]
        fields=("rows","positive_rows","negative_rows","zero_rows","positive_amount","negative_amount",
            "signed_amount","identifiable_rows","identifiable_amount","unattributed_rows","unattributed_amount",
            "source_row_membership_sha256")
        for field in fields:
            if field in {"positive_amount","negative_amount","signed_amount","identifiable_amount","unattributed_amount"}:
                matches=Decimal(actual[field])==Decimal(reference[field])
            else:
                matches=actual[field]==reference[field]
            if not matches:
                raise AssertionError(f"bridge category reference mismatch for {name}.{field}: {actual[field]} != {reference[field]}")
    for field,value in pins["reconciliation"].items():
        if source_reconciliation.get(field)!=value:
            raise AssertionError(f"bridge reconciliation reference mismatch for {field}")


def _bridge_leaf(row,amount,eligible_ids):
    category=row.category
    if amount==0: return "zero_value_entries"
    if category=="merchandise":
        if amount<0: return "merchandise_returns_cancellations"
        return "qualifying_gross_merchandise_purchases" if int(row.source_row_number) in eligible_ids else "other_positive_merchandise_activity"
    if category=="shipping": return "shipping_delivery_income"
    if category=="standalone_manual_billing": return "standalone_manual_billing"
    if category=="standalone_manual_credit": return "standalone_manual_credits"
    if category=="standalone_manual_zero_value": raise AssertionError("zero manual rows must enter zero-value leaf")
    if category=="manual_adjustment":
        return "embedded_manual_adjustments" if normalize_code(row.StockCode)=="M" else "other_manual_adjustment_codes"
    return {"fee":"fees","commission":"commissions","bad_debt":"bad_debt",
        "discount":"discounts","sample":"samples","gift_voucher":"gift_vouchers",
        "test":"test_entries","non_commercial_stock_movement":"non_commercial_stock_movements"}.get(category)


def build_revenue_bridge(validated_input):
    """Build disjoint line-level bridge leaves from a validated real-data object."""
    trusted=_validate_purchase_input(validated_input)
    occasions,occasion_summary=_build_trusted_purchase_occasions(trusted)
    eligible_ids={source_id for occasion in occasions for source_id in occasion["source_row_numbers"]}
    frame=trusted._frame
    leaves=defaultdict(lambda:{"rows":0,"positive_rows":0,"negative_rows":0,"zero_rows":0,
        "positive_amount":Decimal(0),"negative_amount":Decimal(0),
        "signed_amount":Decimal(0),"identifiable_rows":0,"identifiable_amount":Decimal(0),
        "unattributed_rows":0,"unattributed_amount":Decimal(0),"source_row_numbers":[]})
    zero_subcategories=defaultdict(lambda:{"rows":0,"identifiable_rows":0,"unattributed_rows":0,"source_row_numbers":[]})
    source_signed=identified_signed=unattributed_signed=Decimal(0)
    positive_merchandise=Decimal(0)
    classified_category_rows=defaultdict(int)
    for row in frame.itertuples(index=False):
        source_id=int(row.source_row_number)
        amount=_amount(row.Quantity,row.UnitPrice)
        customer=canonical_customer_id(row.CustomerID)
        leaf=_bridge_leaf(row,amount,eligible_ids)
        if leaf is None: raise ValueError(f"unknown taxonomy category in bridge: {row.category!r}")
        item=leaves[leaf];item["rows"]+=1;item["signed_amount"]+=amount;item["source_row_numbers"].append(source_id)
        if amount>0: item["positive_rows"]+=1;item["positive_amount"]+=amount
        elif amount<0: item["negative_rows"]+=1;item["negative_amount"]+=amount
        else: item["zero_rows"]+=1
        if customer is None:
            item["unattributed_rows"]+=1;item["unattributed_amount"]+=amount
            if leaf=="zero_value_entries":
                z=zero_subcategories[row.category];z["rows"]+=1;z["unattributed_rows"]+=1;z["source_row_numbers"].append(source_id)
            unattributed_signed+=amount
        else:
            item["identifiable_rows"]+=1;item["identifiable_amount"]+=amount
            if leaf=="zero_value_entries":
                z=zero_subcategories[row.category];z["rows"]+=1;z["identifiable_rows"]+=1;z["source_row_numbers"].append(source_id)
            identified_signed+=amount
        if row.category=="merchandise" and amount>0: positive_merchandise+=amount
        source_signed+=amount
        classified_category_rows[row.category]+=1

    if sum(x["rows"] for x in leaves.values())!=len(frame): raise AssertionError("bridge leaf row reconciliation failed")
    if source_signed!=EXPECTED_SOURCE_SIGNED: raise AssertionError(f"full signed source total mismatch: {source_signed}")
    if identified_signed!=EXPECTED_IDENTIFIABLE_SIGNED: raise AssertionError(f"identifiable source total mismatch: {identified_signed}")
    if unattributed_signed!=EXPECTED_UNATTRIBUTED_SIGNED: raise AssertionError(f"unattributed source total mismatch: {unattributed_signed}")
    if source_signed!=identified_signed+unattributed_signed: raise AssertionError("attribution totals do not reconcile")
    if len(frame)!=EXPECTED_SOURCE_ROWS: raise AssertionError("bridge source row count mismatch")

    serialized={}
    for name,item in sorted(leaves.items()):
        if item["source_row_numbers"]!=sorted(item["source_row_numbers"]):
            item["source_row_numbers"].sort()
        item["source_row_membership_sha256"]=_membership_fingerprint(item["source_row_numbers"])
        serialized[name]={k:(str(v) if isinstance(v,Decimal) else v) for k,v in item.items()}
    zero_categories={k:{**v,"source_row_numbers":sorted(v["source_row_numbers"])} for k,v in sorted(zero_subcategories.items())}
    qualifying=Decimal(serialized["qualifying_gross_merchandise_purchases"]["signed_amount"])
    other_positive=Decimal(serialized["other_positive_merchandise_activity"]["signed_amount"])
    difference=positive_merchandise-qualifying
    if difference!=other_positive: raise AssertionError("positive merchandise minus eligible purchases does not equal other positive merchandise")

    result={"basis":"corrected V2 source lines; signed commercial reconciliation, not a complete profit-and-loss statement",
        "source_v2_sha256":trusted._integrity_report["source_sha256"]["v2"],"seed_sha256":trusted._integrity_report["seed_sha256"],
        "source_row_fingerprint":trusted._integrity_report["row_identity"]["sha256"],"source_rows":len(frame),
        "occasion_summary":occasion_summary,"bridge_leaves":serialized,"zero_value_taxonomy_subcategories":zero_categories,
        "merchandise_positive_reconciliation":{"all_positive_merchandise":str(positive_merchandise),
            "qualifying_gross_purchases":str(qualifying),"other_positive_nonqualifying_merchandise":str(other_positive),
            "difference":str(difference)},
        "source_reconciliation":{"signed_total":str(source_signed),"identifiable_signed":str(identified_signed),
            "unattributed_signed":str(unattributed_signed),"leaf_rows":sum(x["rows"] for x in leaves.values()),
            "rows_reconcile":sum(x["rows"] for x in leaves.values())==len(frame),
            "leaf_signed_amount":str(sum((Decimal(x["signed_amount"]) for x in serialized.values()),Decimal(0))),
            "all_source_row_ids_unique":len({source_id for x in leaves.values() for source_id in x["source_row_numbers"]})==len(frame)},
        "taxonomy_category_rows":dict(sorted(classified_category_rows.items()))}
    _validate_bridge_against_frozen_references(serialized,result["source_reconciliation"])
    return result


def build_real_data_bridge():
    return build_revenue_bridge(load_validated_purchase_input())


def main():
    print(json.dumps(build_real_data_bridge(),sort_keys=True,indent=2,separators=(",",": ")))


if __name__=="__main__": main()
