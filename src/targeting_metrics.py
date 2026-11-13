"""Pure table preparation for the frozen targeting comparison."""
from __future__ import annotations
import pandas as pd

def policy_comparison(bundle: dict, capacity: float) -> pd.DataFrame:
    chosen = next((v for v in bundle["capacities"].values() if v["capacity"] == capacity), None)
    if chosen is None: raise ValueError("capacity must be exactly 5%, 10% or 20%")
    labels=bundle["definitions"]["policy_labels"]
    return pd.DataFrame([{"Policy":labels[p],"Selected customer-month snapshots":r["selected_snapshots"],"Precision":r["precision"],"Purchase capture":r["capture"],"Lift vs random":r["lift"]} for p,r in chosen["policies"].items()])

def pairwise_comparison(bundle: dict, capacity: float) -> pd.DataFrame:
    chosen=next(v for v in bundle["capacities"].values() if v["capacity"]==capacity)
    rows=[]
    for p, comp in chosen["model_c_differences"].items():
        label=bundle["definitions"]["policy_labels"][p]
        for metric, values in comp.items():
            rows.append({"Comparison":"Model C − "+label,"Metric":metric.title(),"Difference (percentage points)":values["estimate"]*100,"95% interval lower":values["interval"][0]*100,"95% interval upper":values["interval"][1]*100})
    return pd.DataFrame(rows)
