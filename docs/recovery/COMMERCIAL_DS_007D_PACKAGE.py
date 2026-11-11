"""Render the accepted corrected-V2 aggregate outputs as a portfolio package.

This presentation script reads only accepted aggregate CSV/JSON outputs. It
does not load source transactions or customer-level tables and does not
recompute any 007B/007C metric.
"""
from __future__ import annotations

import argparse
import csv
from decimal import Decimal
from html import escape
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / "data/processed/corrected_v2_customer_analytics"
DEFAULT_OUTPUT = ROOT / "reports/corrected_v2"
PRE = "first_observed_before_2010-12-01"
POST = "first_observed_on_or_after_2010-12-01"
POPULATIONS = (PRE, POST)
INK = "#172B3A"
MUTED = "#5B6B78"
GRID = "#D8E0E5"
PAPER = "#FFFFFF"
TEAL = "#147D83"
BLUE = "#4472A1"
AMBER = "#D89A2B"
CORAL = "#C65D4B"
GREEN = "#31856E"
GRAY = "#AAB5BD"
RECENCY_COLORS = {
    "active_observed": GREEN,
    "inactive_60_89_days": AMBER,
    "no_observed_purchase_90_plus_days": CORAL,
}
FREQUENCIES = ("one_observed_purchase_day", "repeat_observed_purchase_days")
RECENCIES = tuple(RECENCY_COLORS)

INPUT_SCHEMAS = {
    "repeat_90d_by_first_observed_month.csv": (
        "population", "first_observed_month", "eligible_customer_count",
        "mature_customer_count", "repeat_numerator", "denominator",
        "conversion_fraction", "mature_repeat_timing_count",
        "median_days_to_second_purchase_among_mature_repeaters",
        "insufficient_follow_up_count",
    ),
    "first_observed_cohort_activity.csv": (
        "population", "cohort_month", "month_index", "activity_month",
        "cohort_size", "active_customers", "activity_fraction", "is_mature",
        "is_cohort_entry", "cell_status",
    ),
    "concentration_summary.csv": (
        "eligible_customer_count", "top_decile_customer_count",
        "top_decile_qualifying_gross", "identified_qualifying_gross_denominator",
        "top_decile_share", "ranking_rule", "monetary_measure",
        "unattributed_positive_merchandise_excluded",
    ),
    "signed_merchandise_sensitivity_summary.csv": (
        "view_label", "identified_customer_count", "qualifying_positive_merchandise_rows",
        "qualifying_positive_merchandise_amount", "identified_return_cancellation_rows",
        "identified_return_cancellation_signed_amount", "signed_merchandise_sensitivity_amount",
        "returns_only_customer_count", "negative_net_customer_count",
        "unattributed_return_cancellation_rows_excluded",
        "unattributed_return_cancellation_signed_amount_excluded", "manual_credits_included",
        "manual_credits_bridge_identifiable_amount_separate",
    ),
    "segment_summary.csv": (
        "purchase_frequency", "recency_state", "customer_count",
        "qualifying_gross_merchandise", "share_of_identified_qualifying_gross",
    ),
    "segment_flag_summary.csv": ("flag", "customer_count", "qualifying_gross_merchandise"),
    "reconciliation.json": (
        "all_customer_rows_have_unique_ids", "customer_count", "last_complete_activity_month",
        "maximum_cohort_month_index", "occasion_count", "occasion_reference_validated_by_production_api",
        "pooled_repeat_rate_published", "qualifying_gross_merchandise", "qualifying_line_count",
        "recency_reference_date", "recency_reference_date_is_partial", "recency_reference_timestamp",
        "repeat_rows_are_stratified_only",
    ),
    "value_segments_reconciliation.json": (
        "customer_count", "customer_level_outputs_local_only", "identified_returns_cancellations_signed",
        "manual_credits_identifiable_separate", "qualifying_gross_merchandise",
        "qualifying_occasion_count", "signed_bridge_validated_against_frozen_reference",
        "unattributed_positive_merchandise_excluded", "unattributed_returns_cancellations_excluded",
    ),
}


def read_csv(path: Path, fields: tuple[str, ...]) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != fields:
            raise ValueError(f"unexpected schema in {path.name}: {reader.fieldnames}")
        rows = list(reader)
    if not rows:
        raise ValueError(f"expected aggregate rows in {path.name}")
    if any("customer_id" in row for row in rows):
        raise ValueError(f"customer identifier found in aggregate table: {path.name}")
    return rows


def read_json(path: Path, fields: tuple[str, ...]) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if tuple(sorted(data)) != tuple(sorted(fields)):
        raise ValueError(f"unexpected schema in {path.name}: {sorted(data)}")
    return data


def dec(value: object) -> Decimal:
    return Decimal(str(value))


def fmt_money(value: object, decimals: int = 3) -> str:
    number = dec(value).quantize(Decimal(1).scaleb(-decimals))
    if number < 0:
        return f"−£{-number:,.{decimals}f}"
    return f"£{number:,.{decimals}f}"


def fmt_pct(value: object, decimals: int = 2) -> str:
    return f"{float(dec(value))*100:.{decimals}f}%"


def validate(inputs: dict) -> None:
    repeat = inputs["repeat_90d_by_first_observed_month.csv"]
    cohort = inputs["first_observed_cohort_activity.csv"]
    concentration = inputs["concentration_summary.csv"][0]
    signed = inputs["signed_merchandise_sensitivity_summary.csv"][0]
    segments = inputs["segment_summary.csv"]
    flags = inputs["segment_flag_summary.csv"]
    rec = inputs["reconciliation.json"]
    bridge_rec = inputs["value_segments_reconciliation.json"]

    if rec["pooled_repeat_rate_published"] or not rec["repeat_rows_are_stratified_only"]:
        raise ValueError("007B repeat output violates the no-pooled-rate contract")
    if len(repeat) != 25 or any(r["population"] not in POPULATIONS for r in repeat):
        raise ValueError("unexpected 90-day repeat strata")
    if any(r["first_observed_month"] == "ALL" for r in repeat):
        raise ValueError("pooled repeat row is not permitted")
    if sum(int(r["eligible_customer_count"]) for r in repeat) != int(rec["customer_count"]):
        raise ValueError("repeat strata eligible counts do not reconcile to customer count")
    if sum(int(r["denominator"]) for r in repeat) != 5256:
        raise ValueError("mature repeat denominators do not match accepted 007B result")
    if sum(int(r["insufficient_follow_up_count"]) for r in repeat) != 596:
        raise ValueError("immature repeat counts do not match accepted 007B result")
    for row in repeat:
        if int(row["denominator"]) != int(row["mature_customer_count"]):
            raise ValueError("repeat denominator differs from mature customer count")
        if int(row["repeat_numerator"]) > int(row["denominator"]):
            raise ValueError("repeat numerator exceeds denominator")
        if int(row["denominator"]) == 0 and row["conversion_fraction"]:
            raise ValueError("empty mature stratum must have a null conversion fraction")

    if len(cohort) != 625:
        raise ValueError("unexpected cohort grid size")
    for row in cohort:
        index = int(row["month_index"])
        if (row["is_cohort_entry"] == "True") != (index == 0):
            raise ValueError("cohort entry flag does not match month index")
        if index == 0 and row["is_mature"] == "True" and int(row["active_customers"]) != int(row["cohort_size"]):
            raise ValueError("mature month-0 cohort entry must equal cohort size")
        if row["is_mature"] != "True" and (row["active_customers"] != "" or row["activity_fraction"] != ""):
            raise ValueError("incomplete or future cohort cell must remain null")
    if rec["last_complete_activity_month"] != "2011-11":
        raise ValueError("unexpected last complete cohort activity month")

    customer_count = int(rec["customer_count"])
    gross = dec(rec["qualifying_gross_merchandise"])
    top_n = (customer_count + 9) // 10
    if int(concentration["eligible_customer_count"]) != customer_count:
        raise ValueError("concentration eligible customer count does not reconcile")
    if int(concentration["top_decile_customer_count"]) != top_n:
        raise ValueError("top-decile size does not follow the ceiling rule")
    if dec(concentration["identified_qualifying_gross_denominator"]) != gross:
        raise ValueError("concentration denominator differs from identified qualifying gross")
    if dec(concentration["top_decile_share"]) != dec(concentration["top_decile_qualifying_gross"]) / gross:
        raise ValueError("top-decile share does not equal its numerator over denominator")

    if dec(signed["qualifying_positive_merchandise_amount"]) != gross:
        raise ValueError("signed sensitivity positive component differs from qualifying gross")
    if dec(signed["qualifying_positive_merchandise_amount"]) + dec(signed["identified_return_cancellation_signed_amount"]) != dec(signed["signed_merchandise_sensitivity_amount"]):
        raise ValueError("signed sensitivity components do not reconcile")
    if signed["manual_credits_included"] != "False":
        raise ValueError("manual credits must remain outside signed merchandise sensitivity")
    if int(signed["returns_only_customer_count"]) != 23:
        raise ValueError("returns-only customer count differs from accepted result")

    expected_groups = {(f, r) for f in FREQUENCIES for r in RECENCIES}
    observed_groups = {(row["purchase_frequency"], row["recency_state"]) for row in segments}
    if len(segments) != 6 or observed_groups != expected_groups:
        raise ValueError("segment summary must contain exactly the six approved groups")
    if sum(int(row["customer_count"]) for row in segments) != customer_count:
        raise ValueError("segment customer counts do not reconcile")
    if sum((dec(row["qualifying_gross_merchandise"]) for row in segments), Decimal(0)) != gross:
        raise ValueError("segment gross values do not reconcile")
    if {row["flag"] for row in flags} != {"recent_first_observed_30d", "top_decile_qualifying_gross"}:
        raise ValueError("unexpected independent segment flags")
    if int(next(r for r in flags if r["flag"] == "recent_first_observed_30d")["customer_count"]) != 164:
        raise ValueError("recent-first-observed count differs from accepted 007C result")
    if int(next(r for r in flags if r["flag"] == "top_decile_qualifying_gross")["customer_count"]) != top_n:
        raise ValueError("top-decile flag count does not reconcile")
    if not bridge_rec["signed_bridge_validated_against_frozen_reference"]:
        raise ValueError("signed bridge validation is not recorded")
    if not bridge_rec["customer_level_outputs_local_only"]:
        raise ValueError("customer-level output safety is not recorded")


def svg_start(width: int, height: int, title: str, description: str) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        f'<title id="title">{escape(title)}</title>',
        f'<desc id="desc">{escape(description)}</desc>',
        f'<rect width="100%" height="100%" fill="{PAPER}"/>',
    ]


def rect(x, y, w, h, fill, rx=0, stroke="none", sw=1):
    return f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'


def line(x1, y1, x2, y2, color=GRID, width=1, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{color}" stroke-width="{width}"{d}/>'


def text(x, y, value, size=14, color=INK, anchor="start", weight=400, rotate=None):
    transform = f' transform="rotate({rotate} {x:.1f} {y:.1f})"' if rotate is not None else ""
    return f'<text x="{x:.1f}" y="{y:.1f}" font-family="Arial, Helvetica, sans-serif" font-size="{size}px" fill="{color}" text-anchor="{anchor}" font-weight="{weight}"{transform}>{escape(str(value))}</text>'


def save_svg(path: Path, elements: list[str]) -> None:
    path.write_text("\n".join(elements + ["</svg>", ""]), encoding="utf-8")


def repeat_figure(rows: list[dict], path: Path) -> None:
    width, height = 1500, 850
    e = svg_start(width, height, "Mature 90-day second-purchase conversion", "Monthly mature second-purchase conversion by first-observed population. Bars show mature denominators; incomplete outcomes are excluded.")
    e += [text(70, 55, "Mature 90-day second-purchase conversion", 28, weight=700),
          text(70, 84, "By first-observed month and cutoff population · mature denominator shown below each panel", 15, MUTED),
          text(70, 111, "Primary repeat: a qualifying purchase on a strictly later date, within the half-open 90-day window.", 13, MUTED)]
    for col, population in enumerate(POPULATIONS):
        x0 = 82 + col * 710
        panel_w = 640
        subset = sorted((r for r in rows if r["population"] == population), key=lambda r: r["first_observed_month"])
        # keep all months in the relevant population, including zero-maturity strata
        n = max(1, len(subset))
        plot_left, plot_right = x0 + 65, x0 + panel_w - 12
        plot_top, plot_bottom = 175, 455
        den_top, den_bottom = 555, 720
        e.append(text(x0 + panel_w / 2, 145, "First observed before 2010-12-01" if population == PRE else "First observed on/after 2010-12-01", 17, anchor="middle", weight=700))
        for tick in (0, 0.25, 0.5, 0.75, 1):
            y = plot_bottom - tick * (plot_bottom - plot_top)
            e.append(line(plot_left, y, plot_right, y))
            e.append(text(plot_left - 10, y + 5, f"{tick:.0%}", 11, MUTED, anchor="end"))
        max_den = max(1, max(int(r["denominator"]) for r in subset))
        coords = []
        for i, row in enumerate(subset):
            x = plot_left + (plot_right - plot_left) * (i / max(1, n - 1))
            denom = int(row["denominator"])
            num = int(row["repeat_numerator"])
            rate = None if denom == 0 else num / denom
            coords.append((x, None if rate is None else plot_bottom - rate * (plot_bottom - plot_top), row))
            bar_h = (denom / max_den) * (den_bottom - den_top)
            e.append(rect(x - 9, den_bottom - bar_h, 18, bar_h, "#A8CDD0", rx=2))
            # Label each denominator to make the eligibility visible even when a rate is missing.
            if n <= 16:
                e.append(text(x, den_bottom - bar_h - 7, str(denom), 10, MUTED, anchor="middle"))
            partial = int(row["insufficient_follow_up_count"]) > 0
            if i % 2 == 0 or i == n - 1 or partial:
                e.append(text(x, den_bottom + 22, row["first_observed_month"], 10, MUTED, anchor="middle"))
        # Draw fully mature observations as a line; partial strata remain hollow and unconnected.
        last = None
        for x, y, row in coords:
            if y is None:
                last = None
                continue
            if int(row["insufficient_follow_up_count"]) > 0:
                last = None
                e.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="7" fill="white" stroke="{CORAL}" stroke-width="3"/>')
                e.append(text(x - 10, y - 14, f"Partial follow-up: {row['denominator']}/{row['eligible_customer_count']} mature", 11, CORAL, anchor="end", weight=600))
                continue
            if last is not None:
                e.append(line(last[0], last[1], x, y, TEAL, 3))
            e.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{TEAL}" stroke="white" stroke-width="2"/>')
            last = (x, y)
        e += [text(plot_left - 48, (plot_top + plot_bottom) / 2, "Repeat conversion", 12, MUTED, anchor="middle", rotate=-90),
              text(plot_left, 505, "Monthly mature conversion (numerator / mature denominator)", 11, MUTED),
              text(plot_left, 755, "Mature denominator, n", 12, MUTED),
              text((plot_left + plot_right) / 2, 791, "First-observed month (YYYY-MM)", 12, MUTED, anchor="middle")]
    e += [text(70, 823, "Monthly numerators, denominators, eligible counts and immature counts are listed in the report. No pooled conversion is calculated.", 12, MUTED)]
    save_svg(path, e)


def heat_color(fraction: Decimal) -> str:
    start = (239, 245, 246)
    end = (20, 125, 131)
    f = max(0.0, min(1.0, float(fraction)))
    rgb = tuple(round(a + (b - a) * f) for a, b in zip(start, end))
    return "#%02x%02x%02x" % rgb


def cohort_figure(rows: list[dict], path: Path) -> None:
    width, height = 1550, 900
    e = svg_start(width, height, "Mature monthly activity by first-observed cohort", "Two heatmaps show observed active-customer fraction by first-observed cohort month and activity-month index. Complete month-zero cells are cohort entry. The partial December 2011 cohort month and later incomplete or future cells are gray and not treated as zero.")
    e += [text(65, 55, "First-observed purchase cohort activity", 28, weight=700),
          text(65, 83, "Cell value = customers with a qualifying purchase day in that complete calendar month ÷ first-observed cohort size", 14, MUTED),
          text(65, 108, "Index 0 is cohort entry (100% by construction when fully observed), not repeat retention. Gray cells are incomplete or not observed.", 13, MUTED)]
    cell_w, cell_h = 22, 27
    panel_xs = (155, 875)
    month_labels = ["2009-12" if i == 0 else "" for i in range(25)]
    for c, population in enumerate(POPULATIONS):
        data = [r for r in rows if r["population"] == population]
        cohorts = sorted({r["cohort_month"] for r in data})
        x0, y0 = panel_xs[c], 180
        e.append(text(x0 + 260, 145, "Pre-cutoff first-observed" if population == PRE else "On/after-cutoff first-observed", 16, anchor="middle", weight=700))
        lookup = {(r["cohort_month"], int(r["month_index"])): r for r in data}
        for ri, cohort in enumerate(cohorts):
            y = y0 + ri * cell_h
            e.append(text(x0 - 12, y + 18, cohort, 10, MUTED, anchor="end"))
            for k in range(25):
                x = x0 + k * cell_w
                row = lookup[(cohort, k)]
                if row["activity_fraction"] == "":
                    fill = "#E8ECEF"
                else:
                    fill = heat_color(dec(row["activity_fraction"]))
                stroke = INK if k == 0 else "white"
                sw = 1.4 if k == 0 else 0.7
                e.append(rect(x, y, cell_w - 1, cell_h - 1, fill, rx=1, stroke=stroke, sw=sw))
        for k in range(0, 25, 3):
            e.append(text(x0 + k * cell_w + cell_w / 2, y0 + len(cohorts) * cell_h + 20, str(k), 10, MUTED, anchor="middle"))
        e.append(text(x0 + 275, y0 + len(cohorts) * cell_h + 47, "Activity month index", 12, MUTED, anchor="middle"))
        e.append(text(x0, y0 - 14, "Cohort month", 10, MUTED))
    # Compact fixed color scale, with missingness shown separately.
    legend_x, legend_y = 430, 790
    for i in range(11):
        e.append(rect(legend_x + i * 28, legend_y, 28, 14, heat_color(Decimal(i) / 10)))
    e += [text(legend_x, legend_y + 34, "0%", 11, MUTED), text(legend_x + 280, legend_y + 34, "100%", 11, MUTED, anchor="end"),
          rect(790, legend_y, 20, 14, "#E8ECEF", stroke=GRID), text(817, legend_y + 12, "Incomplete / not observed (null)", 11, MUTED),
          text(65, 865, "Only fully observed calendar months through November 2011 are colored. The source ends partway through December 2011.", 12, MUTED)]
    save_svg(path, e)


def concentration_figure(row: dict[str, str], path: Path) -> None:
    width, height = 1120, 620
    e = svg_start(width, height, "Top-decile share of identified qualifying gross merchandise", "Top 586 identified customers contribute 63.8114 percent of identified qualifying gross merchandise. Remaining identified qualifying customers contribute the rest. Unattributed positive merchandise is excluded and disclosed separately.")
    top = dec(row["top_decile_qualifying_gross"])
    total = dec(row["identified_qualifying_gross_denominator"])
    rest = total - top
    top_n = int(row["top_decile_customer_count"])
    n = int(row["eligible_customer_count"])
    max_w, x0 = 650, 360
    e += [text(65, 58, "Top-decile concentration in qualifying gross", 27, weight=700),
          text(65, 88, "Customer ranking uses identified qualifying gross merchandise only", 14, MUTED)]
    for label, amount, count, y, color in (
        ("Top decile", top, top_n, 235, TEAL),
        ("Other identified customers", rest, n - top_n, 385, BLUE),
    ):
        fraction = amount / total
        w = max_w * float(fraction)
        e.append(text(70, y + 34, label, 17, INK, weight=700))
        e.append(text(70, y + 60, f"{count:,} customers", 13, MUTED))
        e.append(rect(x0, y, max_w, 55, "#F0F3F5", rx=7))
        e.append(rect(x0, y, w, 55, color, rx=7))
        e.append(text(x0 + w + 15, y + 25, fmt_money(amount), 16, INK, weight=700))
        e.append(text(x0 + w + 15, y + 47, fmt_pct(fraction, 2), 13, MUTED))
    e += [line(65, 500, 1055, 500),
          text(65, 535, f"Denominator: {fmt_money(total)} identified qualifying gross merchandise · top-decile size: ceil(10% × {n:,}) = {top_n}", 13, MUTED),
          text(65, 565, f"Excluded from customer ranking: {fmt_money(row['unattributed_positive_merchandise_excluded'])} other positive merchandise, unattributed in the frozen bridge.", 13, MUTED),
          text(65, 595, "Gross merchandise is not accounting net sales, margin or profit.", 12, MUTED)]
    save_svg(path, e)


def segment_figure(rows: list[dict], path: Path) -> None:
    width, height = 1420, 790
    e = svg_start(width, height, "Six descriptive purchase-frequency and recency groups", "Six mutually exclusive groups by distinct observed purchase days and recency as of the partial 2011-12-09 source end. Bars show customer counts and share of identified qualifying gross merchandise.")
    e += [text(65, 55, "Six descriptive frequency × recency groups", 27, weight=700),
          text(65, 84, "Recency is as of 2011-12-09, a partially observed final source date; labels are descriptive, not churn states.", 14, MUTED)]
    label_map = {
        ("one_observed_purchase_day", "active_observed"): "One purchase day · 0–59d",
        ("one_observed_purchase_day", "inactive_60_89_days"): "One purchase day · 60–89d",
        ("one_observed_purchase_day", "no_observed_purchase_90_plus_days"): "One purchase day · 90+d",
        ("repeat_observed_purchase_days", "active_observed"): "Repeat days · 0–59d",
        ("repeat_observed_purchase_days", "inactive_60_89_days"): "Repeat days · 60–89d",
        ("repeat_observed_purchase_days", "no_observed_purchase_90_plus_days"): "Repeat days · 90+d",
    }
    ordered = [next(r for r in rows if (r["purchase_frequency"], r["recency_state"]) == key) for key in ((f, s) for f in FREQUENCIES for s in RECENCIES)]
    left_x, right_x = 390, 1000
    max_count = max(int(r["customer_count"]) for r in ordered)
    top_y, gap = 165, 82
    for i, row in enumerate(ordered):
        y = top_y + i * gap
        label = label_map[(row["purchase_frequency"], row["recency_state"])]
        color = RECENCY_COLORS[row["recency_state"]]
        count = int(row["customer_count"])
        share = float(dec(row["share_of_identified_qualifying_gross"]))
        e.append(text(65, y + 26, label, 14, INK, weight=600))
        e.append(rect(left_x, y, 440, 32, "#F0F3F5", rx=5))
        bar = 440 * count / max_count if max_count else 0
        e.append(rect(left_x, y, bar, 32, color, rx=5))
        e.append(text(left_x + 450, y + 22, f"{count:,}", 13, INK, weight=700))
        e.append(rect(right_x, y, 300, 32, "#F0F3F5", rx=5))
        share_w = 300 * share
        e.append(rect(right_x, y, share_w, 32, color, rx=5))
        e.append(text(right_x + 310, y + 22, fmt_pct(share, 1), 13, INK, weight=700))
    e += [text(left_x, 137, "Customers", 13, MUTED, weight=700),
          text(right_x, 137, "Share of identified qualifying gross (0–100%)", 13, MUTED, weight=700),
          text(65, 700, "Frequency uses distinct purchase days; multiple same-day invoices remain one day. Group values reconcile to 5,852 customers and £17,123,740.997.", 12, MUTED),
          text(65, 729, "Recent-first-observed (inclusive 0–30 days) and top-decile flags are independent; neither is a targeting or predictive rule.", 12, MUTED),
          text(65, 758, "0–30 days is a descriptive implementation convention, not an owner-approved canonical threshold.", 12, MUTED)]
    save_svg(path, e)


def build_report(inputs: dict, figures: list[str]) -> str:
    rec = inputs["reconciliation.json"]
    b_rec = inputs["value_segments_reconciliation.json"]
    repeat = inputs["repeat_90d_by_first_observed_month.csv"]
    cohort = inputs["first_observed_cohort_activity.csv"]
    concentration = inputs["concentration_summary.csv"][0]
    signed = inputs["signed_merchandise_sensitivity_summary.csv"][0]
    segments = inputs["segment_summary.csv"]
    flags = inputs["segment_flag_summary.csv"]
    maturity_cells = sum(r["is_mature"] == "True" for r in cohort)
    nonmature_cells = len(cohort) - maturity_cells
    rows = [
        "# Corrected-V2 Customer Analytics: Scientific Results",
        "",
        "## Scope and data foundation",
        "",
        "This report presents the accepted corrected-V2 customer analytics only. It uses the frozen corrected-V2 source and taxonomy through the validated purchase-occasion API. A purchase occasion is a qualifying customer × invoice event; repeat behavior is measured by distinct qualifying purchase dates. Monetary values use exact Decimal amounts.",
        "",
        f"The corrected source contains 1,044,848 rows. The accepted qualification yields {int(rec['qualifying_line_count']):,} qualifying merchandise lines, {int(rec['occasion_count']):,} purchase occasions and {int(rec['customer_count']):,} identifiable customers. Identified qualifying gross merchandise is **{fmt_money(rec['qualifying_gross_merchandise'])}**.",
        "",
        f"Other positive merchandise of **{fmt_money(b_rec['unattributed_positive_merchandise_excluded'])}** is unattributed in the frozen bridge and is excluded from customer-level value and concentration. It is disclosed separately and is not allocated to customers. Qualifying gross merchandise is not accounting revenue, net sales, margin or profit.",
        "",
        "## 90-day second-purchase outcomes",
        "",
        "The event is a qualifying purchase on a strictly later calendar date, within the half-open 90-day window (day +89 included; day +90 excluded). A customer is mature only if first-observed date + 90 days is on or before 2011-12-09. Immature outcomes remain unknown, not non-repeat. Results are stratified by first-observed month and by the pre-/post-2010-12-01 first-observed split. These populations are not verified acquisition cohorts.",
        "",
        "No pooled 90-day repeat rate is reported. The table gives eligible customers, mature denominators, mature repeat numerators, conversion within mature strata, and insufficient-follow-up counts.",
        "",
        "| First-observed month | Population | Eligible | Mature denominator | Repeat numerator | Conversion among mature | Insufficient follow-up |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in sorted(repeat, key=lambda r: (0 if r["population"] == PRE else 1, r["first_observed_month"])):
        rate = "—" if not row["conversion_fraction"] else fmt_pct(row["conversion_fraction"], 2)
        population = "Pre-cutoff" if row["population"] == PRE else "On/after cutoff"
        rows.append(f"| {row['first_observed_month']} | {population} | {int(row['eligible_customer_count']):,} | {int(row['denominator']):,} | {int(row['repeat_numerator']):,} | {rate} | {int(row['insufficient_follow_up_count']):,} |")
    rows += [
        "",
        f"Across the month strata, {sum(int(r['denominator']) for r in repeat):,} customers are mature and {sum(int(r['insufficient_follow_up_count']) for r in repeat):,} have insufficient follow-up. Do not interpret first observation as acquisition.",
        "",
        f"![Monthly mature conversion by first-observed population](figures/{figures[0]})",
        "",
        "**Figure 1.** Conversion is plotted only where the mature denominator is nonzero; gaps are not imputed. Denominator bars are shown below each panel. Monthly numerators and denominators are in the table above.",
        "",
        "## First-observed cohort activity",
        "",
        f"Customers are assigned to the month of their first observed qualifying purchase, not an acquisition date. Each later cell is the fraction of that first-observed cohort with at least one qualifying purchase day in the full calendar activity month. The denominator is the cohort size. There are {maturity_cells} fully observed cells and {nonmature_cells} incomplete/future cells in the saved grid.",
        "",
        "Month 0 is cohort entry, not repeat retention; for fully observed month-0 cells the activity fraction is 100% by construction. The December 2011 cohort's month-0 cell remains null because that calendar month is incomplete. The final complete activity month is November 2011; December 2011 and future cells are null/not observed, never zero. The observation window starts on 2009-12-01, so earlier customer history is left-censored; first-observed cohorts are not acquisition cohorts.",
        "",
        f"![Maturity-aware first-observed cohort activity](figures/{figures[1]})",
        "",
        "**Figure 2.** Heatmap color shows activity only for fully observed calendar months through November 2011. Gray cells are incomplete or not observed. The month-index 0 column is explicitly marked as cohort entry; the incomplete December 2011 cohort's month-0 cell is also null.",
        "",
        "## Revenue concentration",
        "",
        f"The top **{int(concentration['top_decile_customer_count']):,} of {int(concentration['eligible_customer_count']):,}** customers by qualifying gross merchandise account for **{fmt_money(concentration['top_decile_qualifying_gross'])}** of **{fmt_money(concentration['identified_qualifying_gross_denominator'])}** identified qualifying gross, a **{fmt_pct(concentration['top_decile_share'], 4)}** share. The top-decile size is ceil(10% × eligible customers); rank order is gross descending with canonical customer ID ascending for ties.",
        "",
        f"Unattributed other positive merchandise (**{fmt_money(concentration['unattributed_positive_merchandise_excluded'])}**) is excluded from customer ranking and remains disclosed in the source bridge.",
        "",
        f"![Top-decile concentration in identified qualifying gross](figures/{figures[2]})",
        "",
        "**Figure 3.** The denominator contains identified qualifying gross merchandise only. Other positive merchandise is outside the customer ranking and is shown as an exclusion note.",
        "",
        "## Unlinked signed merchandise-line sensitivity",
        "",
        f"This separate sensitivity combines **{fmt_money(signed['qualifying_positive_merchandise_amount'])}** qualifying positive merchandise with **{fmt_money(signed['identified_return_cancellation_signed_amount'])}** of identified merchandise returns/cancellations, giving **{fmt_money(signed['signed_merchandise_sensitivity_amount'])}** across {int(signed['identified_customer_count']):,} identified customers. This includes {int(signed['returns_only_customer_count'])} returns-only customers, who are retained. Returns are summed by customer and are not linked to original purchase invoices.",
        "",
        f"The {int(signed['unattributed_return_cancellation_rows_excluded']):,} unattributed return/cancellation rows (signed value {fmt_money(signed['unattributed_return_cancellation_signed_amount_excluded'])}) are excluded from customer attribution. Manual credits are excluded and kept in a separate bridge category. This sensitivity is **not accounting net sales, CLV, profit or margin**.",
        "",
        "## Descriptive frequency and recency groups",
        "",
        "The six groups cross distinct observed purchase-day frequency with recency as of the partially observed 2011-12-09 source date: active observed (0–59 days), inactive 60–89 days, and no observed purchase 90+ days. Groups are mutually exclusive and exhaustive over the 5,852 qualifying customers.",
        "",
        "| Purchase frequency | Recency state | Customers | Qualifying gross merchandise | Share of identified gross |",
        "|---|---|---:|---:|---:|",
    ]
    for row in segments:
        freq = "One observed purchase day" if row["purchase_frequency"] == FREQUENCIES[0] else "Repeat observed purchase days"
        recency_label = {RECENCIES[0]: "Active observed (0–59d)", RECENCIES[1]: "Inactive (60–89d)", RECENCIES[2]: "No observed purchase (90+d)"}[row["recency_state"]]
        rows.append(f"| {freq} | {recency_label} | {int(row['customer_count']):,} | {fmt_money(row['qualifying_gross_merchandise'])} | {fmt_pct(row['share_of_identified_qualifying_gross'], 2)} |")
    recent = next(r for r in flags if r["flag"] == "recent_first_observed_30d")
    top_flag = next(r for r in flags if r["flag"] == "top_decile_qualifying_gross")
    rows += [
        "",
        f"Independent flags: `recent_first_observed_30d` is true for {int(recent['customer_count']):,} customers; it uses an inclusive 0–30-calendar-day descriptive implementation convention relative to 2011-12-09, including day 30. This is not an owner-approved canonical CRM threshold and is not validated for targeting or prediction. `top_decile_qualifying_gross` is true for {int(top_flag['customer_count']):,} customers; it is a retrospective full-period label, not a point-in-time feature. The flags do not override group membership.",
        "",
        f"![Six descriptive frequency and recency groups](figures/{figures[3]})",
        "",
        "**Figure 4.** Left bars show group customer counts; right bars show each group's share of identified qualifying gross. Segment labels describe observed history only; they are not validated churn states or CRM targeting rules.",
        "",
        "## Reproducibility and limitations",
        "",
        "This package is regenerated from the accepted 007B/007C aggregate outputs only. It does not load customer-level tables, source transactions, EXP-SIM data, historical V1 outputs, or restricted research evidence. The package script validates required schemas, maturity/null rules, no-pooled-repeat safeguards, and aggregate reconciliations before writing the charts and this report. See `README.md` for input schemas, commands and source commit references.",
        "",
        "All findings are descriptive of the corrected-V2 observation window. The final date is partial; right-censoring is handled by the accepted maturity rules and left-boundary customer history is unknown. These findings do not establish acquisition, campaign effectiveness, causal impact, predictive churn risk, or CRM treatment effects.",
        "",
    ]
    return "\n".join(rows)


def build_readme(input_dir: Path, output_dir: Path, inputs: dict) -> str:
    schemas = "\n".join(
        f"- `{name}` — `{', '.join(INPUT_SCHEMAS[name])}`"
        for name in INPUT_SCHEMAS
    )
    return f"""# Corrected-V2 Results Package — Reproduction

Regenerate the aggregate report and four SVG figures from the accepted aggregate outputs:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python docs/recovery/COMMERCIAL_DS_007D_PACKAGE.py \\
  --input-dir data/processed/corrected_v2_customer_analytics \\
  --output-dir reports/corrected_v2
```

The script reads only these 007B/007C aggregate inputs (no customer-level table):

{schemas}

It writes `corrected_v2_scientific_results.md` and the SVG files in `figures/`. Inputs must be generated by the accepted local 007B and 007C paths and remain under the ignored `data/processed/` directory.

## Source references

- 007B accepted implementation: commit `34fce9a8f8c2c800550e7a17fb6713bf76ae3ddd`.
- 007C accepted implementation: commit `eb2677e55de7a96e715cee92073352c186af341a`.
- Frozen definitions: `docs/recovery/COMMERCIAL_DS_002B_CONTRACT_SPECIFICATION.md`, `COMMERCIAL_DS_003_PURCHASE_OCCASIONS.py`, and `COMMERCIAL_DS_003_REVENUE_BRIDGE.py`.
- 007B and 007C independently reviewed results are recorded in their external closure and Claude review files dated 2026-11-11.

## Known limitations

The source ends partway through 2011-12-09. Only complete calendar activity months through November 2011 are plotted. First-observed month is not verified acquisition. Signed merchandise sensitivity does not link returns to original purchase invoices and excludes unattributed rows and manual credits. Segment labels and the inclusive 0–30-day flag are descriptive conventions, not validated prediction or targeting rules. This package does not recompute analytics.
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    inputs = {}
    for name, fields in INPUT_SCHEMAS.items():
        path = args.input_dir / name
        inputs[name] = read_json(path, fields) if name.endswith(".json") else read_csv(path, fields)
    validate(inputs)
    figures_dir = args.output_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)
    filenames = [
        "fig01_mature_90d_repeat_by_month.svg",
        "fig02_first_observed_cohort_activity.svg",
        "fig03_qualifying_gross_concentration.svg",
        "fig04_descriptive_frequency_recency_segments.svg",
    ]
    repeat_figure(inputs["repeat_90d_by_first_observed_month.csv"], figures_dir / filenames[0])
    cohort_figure(inputs["first_observed_cohort_activity.csv"], figures_dir / filenames[1])
    concentration_figure(inputs["concentration_summary.csv"][0], figures_dir / filenames[2])
    segment_figure(inputs["segment_summary.csv"], figures_dir / filenames[3])
    args.output_dir.mkdir(parents=True, exist_ok=True)
    report = build_report(inputs, filenames)
    (args.output_dir / "corrected_v2_scientific_results.md").write_text(report, encoding="utf-8")
    (args.output_dir / "README.md").write_text(build_readme(args.input_dir, args.output_dir, inputs), encoding="utf-8")
    print(json.dumps({"report": str(args.output_dir / "corrected_v2_scientific_results.md"), "figures": [str(figures_dir / n) for n in filenames], "aggregate_only_inputs": True, "customer_identifiers_in_outputs": False}, indent=2))


if __name__ == "__main__":
    main()
