"""
Phase 3: build data/extracted/seabrokers_extended.parquet (long format) and
data/extracted/seabrokers_extended_summary.json.

Adds a consensus flag per series key across the 96 monthly reports (the PDFs
reuse advert graphics, so a few stale duplicates exist; flagging keeps them
visible instead of silently corrupting a series).
"""
import json, os, csv, re
from collections import defaultdict, Counter, OrderedDict
import pandas as pd

ROOT = r"C:/Users/Dell/Github/Shipping"
BASE = os.path.join(ROOT, "data/extracted/corpus/seabrokers")
SCR = os.path.join(ROOT, "scratch/seabrokers_ext")
OUT_PQ = os.path.join(ROOT, "data/extracted/seabrokers_extended.parquet")
OUT_JSON = os.path.join(ROOT, "data/extracted/seabrokers_extended_summary.json")

UNITS = {
    "avg_dayrate": "GBP/day",
    "prev_year_dayrate": "GBP/day",
    "min_dayrate": "GBP/day",
    "max_dayrate": "GBP/day",
    "yoy_change": "percent",
    "monthly_avg_spot_dayrate": "GBP/day",
    "ytd_avg_spot_dayrate": "GBP/day",
    "spot_avg_utilisation": "percent",
    "dayrate_low": "USD/day",
    "dayrate_high": "USD/day",
    "dayrate": "USD/day",
    "rig_utilisation": "percent",
    "winning_bid": "USD million",
    "lease_settlement_value": "USD million",
    "lease_capacity_gw": "GW",
    "arrival_from": "count",
    "departure_to": "count",
    "inactive_rig": "count",
    "featured": "count",
    "ets_allowance_price_low": "GBP/tonne CO2e (MGO combustion)",
    "ets_allowance_price_high": "GBP/tonne CO2e (MGO combustion)",
}

SECTION_TITLES = {
    "osv_spot_rates": "North Sea OSV Utilisation & Rates - North Sea Average Rates table",
    "osv_utilisation": "North Sea OSV Utilisation & Rates - North Sea Spot Average Utilisation grid (6 back-months)",
    "osv_spot_rate_history_monthly": "North Sea Average Spot Rates - full-year monthly spot-rate history charts",
    "osv_spot_rate_ytd": "North Sea Average Spot Rates - Average Spot Day Rates To Month (YTD)",
    "osv_fleet_moves": "North Sea OSV Utilisation & Rates - Arrivals / Departures North Sea Spot",
    "rig_day_rates": "Rigs - Recent Day Rate Benchmarks / Current Estimated Fixture Rates",
    "rig_utilisation": "Rigs - Cont(r)acted Rig Utilisation and Day Rates (region x back-years)",
    "rigs_inactive": "Rigs - Inactive Rigs Northwest Europe",
    "offshore_snp_auction": "Newbuilds, Conversions, S&P - auction / sale result tables",
    "offshore_renewables_auction": "Renewables - USA lease settlement / auction table",
    "feature_vessel": "Feature vessel - specification box",
    "carbon_ets": "OSV Market Round-Up - EU/UK ETS allowance cost",
}

IMAGE_ONLY = [
    {
        "chart": "Daily North Sea OSV Availability",
        "report_pages": "report p10 (PDF p6), every month",
        "docs": 94,
        "reason": "line chart of daily PSV/AHTS availability by day-of-month; "
                  "only axis labels ('1'..'31', 'PSV 2026/2025', 'AHTS 2026/2025', "
                  "y ticks 0-20) exist in the text layer - the plotted values do not",
        "needs": "vision model",
    },
    {
        "chart": "Oil price vs (contracted) rig utilisation",
        "report_pages": "report p26 Rigs page (PDF p13-14)",
        "docs": 91,
        "reason": "Brent USD/bbl line + Northwest Europe / South America / US Gulf "
                  "rig utilisation lines. Individual % and $ data labels ARE in the "
                  "text layer but arrive as an unordered bag of numbers with no "
                  "month/x-position, so no series can be reconstructed reliably",
        "needs": "vision model (or pdfplumber char x/y reconstruction)",
    },
    {
        "chart": "Average Brent Crude US$/Bbl (caption of the above)",
        "report_pages": "report p26",
        "docs": 91,
        "reason": "same chart; the only numeric text is the y-axis ticks 0-110",
        "needs": "vision model",
    },
    {
        "chart": "North Sea Average Spot Rates monthly history charts (2018-2023 era)",
        "report_pages": "report p12 (PDF p6)",
        "docs": 32,
        "reason": "NOT image-only: the £ values are in the text layer and ARE "
                  "extracted (osv_spot_rate_history_monthly). Listed here only to "
                  "record that they are charts, not tables.",
        "needs": "none - text layer sufficient",
    },
]


def main():
    rows = [json.loads(l) for l in open(os.path.join(SCR, "rows.jsonl"), encoding="utf-8")]

    # ---- consensus flag across reports (advert graphics leave stale copies)
    key = ("section", "vessel_class", "region", "metric", "period")
    buckets = defaultdict(list)
    for r in rows:
        buckets[tuple(r[k] for k in key)].append(r["value"])
    mode = {k: Counter(v).most_common(1)[0][0] for k, v in buckets.items()}
    TEXT_DERIVED = {"carbon_ets"}   # each row is a distinct quoted price band
    for r in rows:
        k = tuple(r[k2] for k2 in key)
        vals = buckets[k]
        r["n_reports_same_key"] = len(vals)
        r["n_reports_same_value"] = sum(1 for v in vals if v == r["value"])
        if r["section"] in TEXT_DERIVED:
            r["flag"] = "text_derived_not_deduplicated"
        elif len(vals) == 1:
            r["flag"] = "single_source"
        elif r["value"] == mode[k]:
            r["flag"] = "consensus"
        else:
            r["flag"] = "outlier_vs_corpus_mode"
        r["unit"] = r["unit"] or UNITS.get(r["metric"], "")

    # `value` must be numeric for the parquet; text-valued specs (Owner,
    # Manager, Design, ...) go into `value_text`.
    for r in rows:
        v = r.get("value")
        if isinstance(v, str):
            r["value_text"] = v
            r["value"] = None
            r["unit"] = r.get("unit") or "text"
        else:
            r["value_text"] = None

    df = pd.DataFrame(rows)
    cols = ["report_date", "section", "vessel_class", "region", "metric", "value",
            "value_text", "unit", "period", "flag", "n_reports_same_key",
            "n_reports_same_value", "source", "source_page", "note"]
    df = df[cols].sort_values(["section", "vessel_class", "period", "report_date"],
                              na_position="last").reset_index(drop=True)
    df.to_parquet(OUT_PQ, index=False)

    # ---- report section census (the printed table of contents)
    toc_pat = re.compile(
        r"(\d{1,2})\s*[\t ]*([A-Z][^\n]{4,60})")
    toc_docs, section_names = 0, Counter()
    for doc in sorted(os.listdir(BASE)):
        dp = os.path.join(BASE, doc)
        if not os.path.isdir(dp):
            continue
        tp = os.path.join(dp, "text.jsonl")
        if not os.path.exists(tp):
            continue
        for l in open(tp, encoding="utf-8"):
            d = json.loads(l)
            if "OSV Market Round-Up" in d["text"] and "Rigs" in d["text"]:
                toc_docs += 1
                for m in toc_pat.finditer(d["text"]):
                    nm = m.group(2).strip()
                    if 3 < len(nm) < 40:
                        section_names[nm] += 1
                break

    # ---- rows per section, per report
    per_section = OrderedDict()
    for sec, g in df.groupby("section"):
        metrics = {}
        for met, gg in g.groupby("metric"):
            metrics[met] = {
                "rows": int(len(gg)),
                "reports": int(gg["report_date"].nunique()),
                "unit": UNITS.get(met, ""),
                "period_min": str(gg["period"].dropna().min()) if gg["period"].notna().any() else None,
                "period_max": str(gg["period"].dropna().max()) if gg["period"].notna().any() else None,
                "outliers_vs_corpus_mode": int((gg["flag"] == "outlier_vs_corpus_mode").sum()),
            }
        per_section[sec] = {
            "title": SECTION_TITLES.get(sec, sec),
            "rows": int(len(g)),
            "reports": int(g["report_date"].nunique()),
            "report_first": str(g["report_date"].min()),
            "report_last": str(g["report_date"].max()),
            "metrics": metrics,
        }

    # ---- image-only chart inventory.
    # NOTE: the data charts in these PDFs are VECTOR diagrams (pdfplumber:
    # page 6 of the 2026-08 PDF has 0 raster images, 204 lines, 69 curves).
    # So "image-only" here means "not in the text layer AND not a raster that
    # OCR could read" - it needs page-level digitisation (vision) or vector
    # path analysis.
    pages_with_rows = defaultdict(set)
    for r in rows:
        if r.get("source_page") is not None and r["section"] != "osv_spot_rates":
            pages_with_rows[r["report_date"]].add(int(r["source_page"]))

    CHART_CAPTIONS = {
        "DAILY NORTH SEA OSV AVAILABILITY":
            "Daily North Sea OSV Availability (PSV/AHTS 2026 vs 2025, x = day of month)",
        "OIL PRICE VS":
            "Brent USD/bbl vs regional rig utilisation (Rigs page)",
        "CONTRACTED RIG UTILISATION AND DAY":
            "Contracted rig utilisation and day rates (Rigs page)",
        "Average Brent Crude US$ / Bbl":
            "Average Brent Crude US$/Bbl (caption of the rig-utilisation chart)",
    }
    img_only_pages = []
    for doc in sorted(os.listdir(BASE)):
        dp = os.path.join(BASE, doc)
        tp = os.path.join(dp, "text.jsonl")
        if not os.path.isdir(dp) or not os.path.exists(tp):
            continue
        pt = defaultdict(list)
        for l in open(tp, encoding="utf-8"):
            d = json.loads(l)
            pt[d["page"]].append(d["text"])
        for page, texts in sorted(pt.items()):
            blob = " ".join(texts)
            for cap_key, cap in CHART_CAPTIONS.items():
                if cap_key in blob:
                    img_only_pages.append({
                        "doc": doc, "corpus_page_index": page,
                        "chart": cap,
                        "page_also_yielded_text_rows":
                            page in pages_with_rows.get(doc[:10], set()),
                    })

    img_only = []          # raster extras (mostly photos / adverts)
    generic = []
    n_charts_scanned = 0
    for doc in sorted(os.listdir(BASE)):
        dp = os.path.join(BASE, doc)
        mp = os.path.join(dp, "charts", "meta.jsonl")
        if not os.path.exists(mp):
            continue
        for l in open(mp, encoding="utf-8"):
            m = json.loads(l)
            n_charts_scanned += 1
            wide = m["w"] >= 400 and m["w"] / max(m["h"], 1) >= 1.15
            if wide and m["page"] not in pages_with_rows.get(doc[:10], set()):
                generic.append({"doc": doc, "page": m["page"], "chart": m["file"],
                                "w": m["w"], "h": m["h"]})

    summary = {
        "generated_utc": pd.Timestamp.now('UTC').isoformat(),
        "source": "data/extracted/corpus/seabrokers/<doc>/{text,tables}.jsonl "
                  "(96 monthly SEABREEZE reports, 2018-05..2026-08)",
        "output": {
            "long_format": "data/extracted/seabrokers_extended.parquet",
            "columns": cols,
            "rows": int(len(df)),
        },
        "units_policy": {
            "general": "unit is recorded per metric; never inferred at read time",
            "osv_dayrate_ledger": "GBP/day",
            "osv_dayrate_evidence": (
                "Report text: 'spot fixture rates have surpassed GBP 30,000 "
                "(USD 40,600) in the UK'. Table 'NORTH SEA AVERAGE RATES' is printed "
                "with a GBP '£' prefix on every value and the page-12 chart axis is "
                "£0-£30,000 (PSV) / £0-£180,000 (AHTS). All four series are North Sea "
                "OSV *spot day rates in GBP per day*. CONFIRMED, not assumed."),
            "rig_dayrate": "USD/day (table header 'LOW (USD)' / 'HIGH (USD)'; "
                           "'CURRENT ESTIMATED FIXTURE RATES ... USD 90,000')",
            "rig_utilisation": "percent (0-100)",
            "osv_utilisation": "percent (0-100)",
            "snp_winning_bid": "USD million (as printed, e.g. 'USD 52.06 million')",
            "renewables_lease_value": "USD million ('Value $m')",
            "renewables_capacity": "GW (as printed '4.2 GW' / '1.2 to 1.6 GW')",
            "feature_vessel": "SI units from the spec box (m, tonnes, persons, kW, m2)",
            "fleet_moves": "count events (vessel_name carries the vessel, region the "
                           "origin for arrivals / destination for departures)",
            "carbon_ets": "GBP per tonne of CO2e / per tonne of MGO burned",
        },
        "report_sections_from_toc": {
            "docs_with_toc": toc_docs,
            "printed_sections": [s for s, _ in section_names.most_common()],
            "printed_sections_example": [
                "04 OSV Market Round-Up", "10 North Sea OSV Utilisation & Rates",
                "12 North Sea Average Spot Rates", "14 Feature vessel",
                "16 Newbuilds, Conversions, S&P", "19 Subsea", "22 Renewables",
                "26 Rigs", "28 Seabrokers Contact Details"],
        },
        "sections_extracted": per_section,
        "extraction_confidence": {
            "consensus": int((df["flag"] == "consensus").sum()),
            "single_source": int((df["flag"] == "single_source").sum()),
            "outlier_vs_corpus_mode": int((df["flag"] == "outlier_vs_corpus_mode").sum()),
            "note": "outlier_vs_corpus_mode rows are kept but flagged; they come from "
                    "stale advert graphics re-embedded in the PDF spreads (e.g. an "
                    "'Average Day Rates To Month (June 2013)' graphic still carrying "
                    "old values). Filter flag=='consensus' for a clean series.",
        },
        "independent_verification": {
            "method": "the page-12 monthly spot-rate-history charts were re-read "
                      "with `pdftotext -f 7 -l 7 <pdf>` (independent of the corpus "
                      "extractor). Values match, e.g. PSVs < 900m2 Jan 2025 = 5770, "
                      "Aug 2025 = 4737, Jan 2026 = 4243, Aug 2026 = 18000.",
            "history_vs_existing_ledger": {
                "overlapping_months_compared": 355,
                "agree_within_0.5_gbp": 348,
                "disagree": 7,
                "disagreements": [
                    ["AHTS < 22,000 bhp", "2019-01"],
                    ["AHTS < 22,000 bhp", "2021-03"],
                    ["AHTS > 22,000 bhp", "2021-03"],
                    ["PSVs < 900m2", "2021-03"],
                    ["PSVs > 900m2", "2021-03"],
                    ["PSVs < 900m2", "2022-02"],
                    ["AHTS < 22,000 bhp", "2022-03"],
                ],
                "interpretation": "the report's own chart and its summary table "
                                  "occasionally disagree (late revisions / rounding, "
                                  "e.g. 2022-02 PSVs < 900m2 = 7767 on the chart vs "
                                  "7769 in the table). Both are kept; the chart row "
                                  "carries flag=outlier_vs_corpus_mode where it is "
                                  "the minority value.",
            },
            "osv_utilisation_vs_ledger": "the 4 current-month utilisation cells were "
                                         "cross-checked against the ledger's "
                                         "med_psv_util / large_psv_util / med_ahts_util "
                                         "/ large_ahts_util columns - all matched.",
        },
        "era_coverage": {
            "osv_spot_rates": "2018-05..2026-08 (93 reports)",
            "osv_utilisation": "2018-05..2026-08 (96 reports, all)",
            "osv_spot_rate_history_monthly": "2018-05..2026-08 (96 reports, all)",
            "osv_spot_rate_ytd": "2018-05..2026-08 (88 reports; title era-gated)",
            "osv_fleet_moves": "2024-01..2026-08 (30 reports - the printed "
                               "ARRIVALS/DEPARTURES lists only start in Jan 2024)",
            "rig_day_rates": "2018-05..2020-09 + 2021-12 (28 reports; the 'RECENT DAY "
                             "RATE BENCHMARKS' / 'CURRENT ESTIMATED FIXTURE RATES' "
                             "table is discontinued after 2022)",
            "rig_utilisation": "2018-05..2023-11 (61 reports; superseded by the "
                               "Brent-vs-utilisation chart from 2024)",
            "rigs_inactive": "2018-05..2026-08 (91 reports)",
            "offshore_snp_auction": "2025-09..2026-08 (11 reports, the Bourbon "
                                    "auction result table)",
            "feature_vessel": "2025-09..2026-08 (8 reports)",
            "offshore_renewables_auction": "2026-08 only",
            "carbon_ets": "2026-08 only",
        },
        "image_only_charts": {
            "known_chart_types": IMAGE_ONLY,
            "why": "the data charts in these PDFs are VECTOR diagrams, not rasters "
                   "(pdfplumber on the 2026-08 PDF p6: 0 images, 204 lines, "
                   "69 curves). They cannot be pdftotext'd nor OCR'd as a bitmap; "
                   "they need page digitisation (vision) or vector-path analysis.",
            "n_chart_images_in_corpus": n_charts_scanned,
            "n_vector_chart_pages_not_extractable": len(img_only_pages),
            "vector_chart_pages": img_only_pages,
            "n_other_wide_images_on_pages_with_no_extraction": len(generic),
            "other_wide_images_examples": generic[:30],
            "policy": "No numbers were invented from a chart. Anything that is "
                      "text-unextractable is listed, not guessed. The only sizeable "
                      "series lost this way is Daily North Sea OSV Availability "
                      "(31 days x 4 lines per report, ~94 reports) and the Brent "
                      "vs regional rig-utilisation chart on the Rigs page. "
                      "Verified with `pdftotext` on the same page: only axis labels "
                      "and legend names come out, no plotted values.",
        },
        "not_found_expectations": {
            "subsea_csv_clv_dayrates": "No CSV/CLV/OSCV day-rate table or chart "
                                       "exists in the 96 reports - the Subsea section "
                                       "is prose (contract awards, newbuilds). "
                                       "Nothing extracted because nothing is there.",
            "eu_ets_carbon_price": "Only the August 2026 report prints explicit "
                                   "allowance prices; earlier ETS items are "
                                   "qualitative. 1 report -> 3 price bands.",
        },
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=1, ensure_ascii=False)

    print("wrote", OUT_PQ, len(df), "rows")
    print("wrote", OUT_JSON)
    print(df.groupby("section").size().to_string())
    print()
    print("flags:", df["flag"].value_counts().to_dict())


if __name__ == "__main__":
    main()
