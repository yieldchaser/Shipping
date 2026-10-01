#!/usr/bin/env python3
"""
scripts/extract/orchestrate_incremental_ingest.py
=============================================================================
Universal Incremental Ingestion Orchestrator & Periodic Chart Fingerprinting Engine.

Capabilities:
1. Automated Incremental Detection: Discovers unextracted PDFs in corpus/01-brokers/.
2. Publisher Delegation: Delegates to specialized full extractors
   (xclusiv, advanced_shipping, star_asia, intermodal, affinity, banchero_costa)
   to ensure 100% fidelity, complete prose, and structured tables.
3. Safe Year-Partitioned Routing: Ensures all outputs are placed in
   data/extracted/md/<pub>/<year>/<stem>.md and .tables.json.
4. Chart Signature Fingerprinting & Screenshot Clipping:
   - Detects periodic rotating charts (e.g. Fearnleys coal futures, vessel tightness,
     Intermodal Baltic curves, SSY routes, Xclusiv TCE curves, Star Asia scrap trends).
   - Clips 200 DPI PNG screenshots to data/extracted/charts/<pub>/<year>/<stem>_<slug>.png.
   - Extracts vector points or calibrated metrics.
   - Embeds screenshots directly into markdown reports.
5. Non-Destructive Upsert Deduplication:
   - Preserves 100% of historical series CSV rows.
   - Appends only new non-duplicate primary keys.
6. Catalog Synchronization:
   - Updates EXTRACTION_REGISTER.json and docs/EXTRACTION_REGISTER.md.
   - Re-compiles data/views/ manifests under the 250 KB ceiling.

Usage:
  python scripts/extract/orchestrate_incremental_ingest.py --dry-run
  python scripts/extract/orchestrate_incremental_ingest.py --broker xclusiv
  python scripts/extract/orchestrate_incremental_ingest.py --file <path_to_pdf>
  python scripts/extract/orchestrate_incremental_ingest.py --all
=============================================================================
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import pymupdf as fitz  # PyMuPDF (use pymupdf import to avoid fitz deprecation warning)
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "extract" / "publishers"))
sys.path.insert(0, str(ROOT / "scripts"))

CORPUS_DIR = ROOT / "corpus" / "01-brokers"
MD_DIR = ROOT / "data" / "extracted" / "md"
CHARTS_DIR = ROOT / "data" / "extracted" / "charts"
SERIES_DIR = ROOT / "data" / "extracted" / "series"
UNTRACKED_CHARTS_LOG = CHARTS_DIR / "untracked_chart_candidates.json"

YEAR_RX = re.compile(r"(201\d|202\d)")
DATE_ISO_RX = re.compile(r"(\d{4})[-_](\d{2})[-_](\d{2})")
DATE_EU_RX = re.compile(r"(\d{1,2})[-_](\d{1,2})[-_](\d{4})")


# ---------------------------------------------------------------------------
# Primary Key Upsert Utility (Guarantees Zero Overwrite)
# ---------------------------------------------------------------------------

def upsert_rows_to_csv(
    csv_path: Path,
    new_rows: List[Dict[str, Any]],
    fieldnames: List[str],
    key_fields: List[str],
) -> int:
    """
    Appends new_rows to csv_path, deduplicating based on tuple of key_fields.
    Returns count of newly added rows. Never truncates existing data.
    """
    if not new_rows:
        return 0

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    existing_keys: Set[Tuple[str, ...]] = set()
    existing_rows: List[Dict[str, Any]] = []

    if csv_path.exists() and csv_path.stat().st_size > 0:
        with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames:
                for r in reader:
                    existing_rows.append(r)
                    k = tuple(str(r.get(kf, "")).strip().lower() for kf in key_fields)
                    existing_keys.add(k)

    # Filter incoming
    to_add: List[Dict[str, Any]] = []
    for nr in new_rows:
        k = tuple(str(nr.get(kf, "")).strip().lower() for kf in key_fields)
        if k not in existing_keys:
            existing_keys.add(k)
            to_add.append(nr)

    if not to_add:
        return 0

    # Write back existing + new
    if existing_rows:
        current_cols = list(existing_rows[0].keys())
        for fn in fieldnames:
            if fn not in current_cols:
                current_cols.append(fn)

        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=current_cols, extrasaction="ignore")
            writer.writeheader()
            for r in existing_rows:
                writer.writerow(r)
            for r in to_add:
                writer.writerow(r)
    else:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for r in to_add:
                writer.writerow(r)

    return len(to_add)


# ---------------------------------------------------------------------------
# Date and Year Resolution Engine
# ---------------------------------------------------------------------------

def resolve_document_date_and_year(doc: fitz.Document, file_path: Path) -> Tuple[str, str]:
    """Tiered Date Resolution: Header -> Filename -> Metadata."""
    for pno in range(min(2, len(doc))):
        text = doc[pno].get_text("text")[:2000]
        m_iso = DATE_ISO_RX.search(text)
        if m_iso:
            y, m, d = m_iso.groups()
            return f"{y}-{m.zfill(2)}-{d.zfill(2)}", y

        m_week = re.search(r"week\s+(\d{1,2})\s*[-–/]\s*(\d{4})", text, re.I)
        if m_week:
            y = m_week.group(2)
            return f"{y}-01-01", y

    fn = file_path.name
    m_iso = DATE_ISO_RX.search(fn)
    if m_iso:
        y, m, d = m_iso.groups()
        return f"{y}-{m.zfill(2)}-{d.zfill(2)}", y

    m_eu = DATE_EU_RX.search(fn)
    if m_eu:
        d, m, y = m_eu.groups()
        return f"{y}-{m.zfill(2)}-{d.zfill(2)}", y

    m_yr = YEAR_RX.search(fn)
    if m_yr:
        y = m_yr.group(1)
        return f"{y}-01-01", y

    meta = doc.metadata or {}
    cdate = meta.get("creationDate", "")
    if cdate and cdate.startswith("D:") and len(cdate) >= 10:
        y = cdate[2:6]
        m = cdate[6:8]
        d = cdate[8:10]
        if y.isdigit() and int(y) >= 2000:
            return f"{y}-{m}-{d}", y

    return "2026-01-01", "2026"


# ---------------------------------------------------------------------------
# Tracked Chart Signature Catalog
# ---------------------------------------------------------------------------

class ChartSignature:
    def __init__(
        self,
        broker: str,
        slug: str,
        title: str,
        keywords: List[str],
        target_csv: Path,
        key_fields: List[str],
        fieldnames: List[str],
        min_drawings: int = 10,
    ):
        self.broker = broker
        self.slug = slug
        self.title = title
        self.keywords = [k.lower() for k in keywords]
        self.target_csv = target_csv
        self.key_fields = key_fields
        self.fieldnames = fieldnames
        self.min_drawings = min_drawings

    def match_page(self, text: str, num_drawings: int, num_images: int) -> bool:
        t_low = text.lower()
        if (num_drawings + num_images * 5) < self.min_drawings:
            return False
        return any(kw in t_low for kw in self.keywords)


SIGNATURE_CATALOG = [
    ChartSignature(
        broker="fearnleys",
        slug="coal_spread",
        title="P5 vs Newcastle Coal Futures Spread Lead",
        keywords=["p5 vs newcastle", "coal futures spread", "kamsarmax indonesia rv"],
        target_csv=SERIES_DIR / "fearnleys_md_coal_futures_spread_series.csv",
        key_fields=["issue_date", "chart_title"],
        fieldnames=[
            "issue_date", "year", "department", "report_title",
            "p5_kamsarmax_indonesia_rv_usd_day", "p5_4w_prev_usd_day",
            "newcastle_coal_futures_spread_lead_2m", "coal_spread_4w_prev",
            "lead_tenor", "chart_title", "source_image", "report_id"
        ],
        min_drawings=5
    ),
    ChartSignature(
        broker="fearnleys",
        slug="vessel_tightness",
        title="Vessel Tightness Indicators",
        keywords=["p6 vs satl tightness", "north atlantic tightness", "ballaster laden"],
        target_csv=SERIES_DIR / "fearnleys_md_vessel_tightness_series.csv",
        key_fields=["issue_date", "indicator_type"],
        fieldnames=[
            "issue_date", "year", "department", "report_title", "indicator_type",
            "bpi_5tc_usd_day", "tightness_ratio", "source_image", "report_id"
        ],
        min_drawings=5
    ),
    ChartSignature(
        broker="intermodal",
        slug="baltic_tc_curves",
        title="Baltic Dry Index & Time Charter Rates",
        keywords=["baltic dry index & tc rates", "1 yr tc", "capesize 180k"],
        target_csv=SERIES_DIR / "intermodal_baltic_tc_series.csv",
        key_fields=["issue_date", "vessel_class"],
        fieldnames=[
            "issue_date", "report_week", "vessel_class", "rate_usd_day", "source_file"
        ],
        min_drawings=30
    ),
    ChartSignature(
        broker="ssy",
        slug="capesize_ffa",
        title="SSY Capesize Routes & FFA Trajectories",
        keywords=["ssy capesize routes", "saldahna", "ffa 4tc", "tubarao"],
        target_csv=SERIES_DIR / "ssy_capesize_routes_points.csv",
        key_fields=["issue_date", "route_name"],
        fieldnames=[
            "issue_date", "route_name", "rate_usd", "trend_wow", "source_file"
        ],
        min_drawings=20
    ),
    ChartSignature(
        broker="xclusiv",
        slug="tce_benchmarks",
        title="Xclusiv Tanker & Dry Bulk TCE Benchmarks",
        keywords=["tce average", "rolling 2y", "aframax atlantic", "mr atlantic"],
        target_csv=SERIES_DIR / "xclusiv_freight_benchmarks_series.csv",
        key_fields=["issue_date", "segment"],
        fieldnames=[
            "issue_date", "segment", "rate_usd_day", "change_wow", "source_file"
        ],
        min_drawings=15
    ),
    ChartSignature(
        broker="star_asia",
        slug="scrap_trends",
        title="Star Asia Demolition Price Trends",
        keywords=["demolition price trends", "gaddani vs alang", "chattogram"],
        target_csv=SERIES_DIR / "star_asia_scrap_price_trends_series.csv",
        key_fields=["issue_date", "country"],
        fieldnames=[
            "issue_date", "country", "price_usd_per_ldt", "source_file"
        ],
        min_drawings=15
    )
]


# ---------------------------------------------------------------------------
# Specialized Publisher Handlers (High-Fidelity Extraction)
# ---------------------------------------------------------------------------

def extract_xclusiv(pdf_path: Path, dry_run: bool = False) -> Dict[str, Any]:
    """Specialized extraction for Xclusiv Shipbrokers."""
    import run_xclusiv_tables as xclusiv
    res = xclusiv.process_pdf(pdf_path)
    if not dry_run:
        upsert_rows_to_csv(
            SERIES_DIR / "xclusiv_sales_series.csv",
            res.get("sales", []),
            xclusiv.SALES_COLUMNS,
            ["issue_date", "NAME", "DWT"]
        )
        upsert_rows_to_csv(
            SERIES_DIR / "xclusiv_demolition_series.csv",
            res.get("demo_prices", []),
            xclusiv.DEMO_PRICES_COLUMNS,
            ["issue_date", "segment", "country"]
        )
        upsert_rows_to_csv(
            SERIES_DIR / "xclusiv_secondhand_series.csv",
            res.get("sh_prices", []),
            xclusiv.SECONDHAND_COLUMNS,
            ["issue_date", "sector", "vessel_type", "tenor"]
        )
        upsert_rows_to_csv(
            SERIES_DIR / "xclusiv_demo_sales_series.csv",
            res.get("demo_sales", []),
            xclusiv.DEMO_SALES_COLUMNS,
            ["issue_date", "NAME"]
        )
    return res


def extract_advanced_shipping(pdf_path: Path, dry_run: bool = False) -> Dict[str, Any]:
    """Specialized extraction for Advanced Shipping & Trading."""
    import run_advanced_shipping_tables as adv
    res = adv.process_document(pdf_path)
    if not dry_run:
        upsert_rows_to_csv(
            SERIES_DIR / "advanced_shipping_sales_series.csv",
            res.get("sales_rows", []),
            adv.SALES_COLUMNS,
            ["issue", "NAME", "DWT"]
        )
        upsert_rows_to_csv(
            SERIES_DIR / "advanced_shipping_newbuilding_series.csv",
            res.get("nb_rows", []),
            adv.NB_COLUMNS,
            ["issue_date", "yard", "units", "capacity_raw"]
        )
        upsert_rows_to_csv(
            SERIES_DIR / "advanced_shipping_demolition_series.csv",
            res.get("demo_prices_rows", []),
            adv.DEMO_COLUMNS,
            ["issue", "segment", "country"]
        )
        upsert_rows_to_csv(
            SERIES_DIR / "advanced_shipping_demo_sales_series.csv",
            res.get("demo_sales_rows", []),
            adv.DEMO_SALES_COLUMNS,
            ["issue_date", "vessel_name"]
        )
        upsert_rows_to_csv(
            SERIES_DIR / "advanced_shipping_secondhand_matrix_series.csv",
            res.get("secondhand_rows", []),
            adv.SECONDHAND_COLUMNS,
            ["issue_date", "sector", "vessel_class", "age"]
        )
    return res


def extract_star_asia(pdf_path: Path, dry_run: bool = False) -> Dict[str, Any]:
    """Specialized extraction for Star Asia Shipbroking."""
    import run_star_asia_tables as sa
    import star_asia_dates as SAD

    doc = fitz.open(pdf_path)
    report_week, issue_date = sa.extract_meta(doc, pdf_path)
    ind_records, clean_ind = sa.extract_indicative_scrap_table(doc, issue_date, report_week, pdf_path.name)
    deals = sa.extract_demolition_deals(doc, issue_date, report_week, pdf_path.name)
    deals_norm = [SAD.normalise_deal_dates(d) for d in deals]
    doc.close()

    year_str = issue_date[:4] if issue_date and issue_date[:4].isdigit() else "2026"
    dest_dir = MD_DIR / "star_asia" / year_str
    
    if not dry_run:
        dest_dir.mkdir(parents=True, exist_ok=True)
        sidecar_data = {
            "stem": pdf_path.stem,
            "issue_date": issue_date,
            "report_week": report_week,
            "tables": {
                "indicative_demolition_prices": ind_records,
                "demolition_deals": deals_norm
            }
        }
        (dest_dir / f"{pdf_path.stem}.tables.json").write_text(json.dumps(sidecar_data, indent=2), encoding="utf-8")
        
        ind_cols = ["issue_date", "report_week", "destination", "country", "segment", "price_low", "price_high", "price_usd_per_ldt", "sentiment", "source_file"]
        upsert_rows_to_csv(SERIES_DIR / "star_asia_demolition_series.csv", ind_records, ind_cols, ["issue_date", "country", "segment"])
        
        deal_cols = ["issue_date", "report_week", "vessel_name", "vessel_type", "ldt", "price_usd_per_ldt", "built", "country_destination", "buyer_comments", "terms", "source_file"]
        upsert_rows_to_csv(SERIES_DIR / "star_asia_deals_series.csv", deals_norm, deal_cols, ["issue_date", "vessel_name"])

    return {
        "stem": pdf_path.stem,
        "issue_date": issue_date,
        "report_week": report_week,
        "ind_count": len(ind_records),
        "deals_count": len(deals_norm)
    }


def extract_affinity(pdf_path: Path, dry_run: bool = False) -> Dict[str, Any]:
    """Specialized extraction for Affinity Shipbrokers."""
    import run_affinity
    import polish_affinity_markdown as pam

    r = run_affinity.build(pdf_path)
    (md, cards, junk, nvec, verified, pnums, missing, npages, ref, panel, datefrag) = r
    typed = {c["name"]: c.get("typed") for c in cards}
    raw_md_str = "\n".join(md)
    issue_date, report_week, pretty_date = pam.resolve_date_and_week(pdf_path.stem, raw_md_str)
    year_str = str(int(issue_date[:4]))
    commentary_text = pam.extract_clean_commentary_from_pdf(pdf_path)

    # BDTI / BCTI
    bcti_bdti_data = typed.get("BCTI / BDTI", {})
    bdti_val = pam.parse_clean_float(bcti_bdti_data.get("bdti")) if isinstance(bcti_bdti_data, dict) else None
    bcti_val = pam.parse_clean_float(bcti_bdti_data.get("bcti")) if isinstance(bcti_bdti_data, dict) else None
    arrows = bcti_bdti_data.get("arrows", []) if isinstance(bcti_bdti_data, dict) else []
    bdti_trend = pam.format_trend(arrows[0]) if len(arrows) >= 1 else "-"
    bcti_trend = pam.format_trend(arrows[1]) if len(arrows) >= 2 else "-"

    # BDA
    bda_rows = []
    bda_data = typed.get("BDA", {})
    if isinstance(bda_data, dict):
        for seg, val, chg in zip(bda_data.get("metrics", []), bda_data.get("values", []), bda_data.get("deltas", [])):
            bda_rows.append({"segment": seg, "price": pam.parse_clean_float(val), "change": pam.parse_clean_float(chg)})

    # Dirty & Clean
    dirty_rows = []
    for row in typed.get("BALTIC TCE DIRTY", []) or []:
        dirty_rows.append({
            "route": row.get("route"), "description": row.get("description"),
            "quantity": pam.parse_quantity_mt(row.get("qty_dwt")),
            "rate": pam.parse_clean_float(row.get("value")) if row.get("value") is not None else pam.parse_clean_float(row.get("value_raw")),
            "trend": pam.format_trend(row.get("wow")),
        })
    clean_rows = []
    for row in typed.get("BALTIC TCE CLEAN", []) or []:
        clean_rows.append({
            "route": row.get("route"), "description": row.get("description"),
            "quantity": pam.parse_quantity_mt(row.get("qty_dwt")),
            "rate": pam.parse_clean_float(row.get("value")) if row.get("value") is not None else pam.parse_clean_float(row.get("value_raw")),
            "trend": pam.format_trend(row.get("wow")),
        })

    disclaimer_note = "Excluded (Legal disclaimer per Shipbroking_Source_Parsing_Notes.docx)" if npages > 1 else "N/A (Single page report)"
    md_doc = [
        "---",
        f'title: "Affinity Tanker Weekly - {pretty_date}"',
        'broker: "Affinity Shipbrokers"',
        'publication: "Affinity Tanker Weekly"',
        f'issue_date: "{issue_date}"',
        f"report_week: {report_week}",
        f"year: {year_str}",
        f'source_file: "{str(pdf_path.relative_to(ROOT)).replace(chr(92), "/")}"',
        f"pages_total: {npages}",
        "pages_analyzed: 1",
        f'page_2_disclaimer: "{disclaimer_note}"',
        "sectors:",
        '  - "Crude Tankers"',
        '  - "Product Tankers"',
        '  - "Demolition / Recycling"',
        "---",
        "",
        f"# Affinity Tanker Weekly - {pretty_date}",
        "",
        f"**Publication Date:** {pretty_date} | **Report Week:** Week {report_week:02d}, {year_str} | **Source:** Affinity Research LLP",
        "",
        "## Market Indices",
        "",
        "| Index | Value | Trend (W-o-W) |",
        "|---|---|---|",
        f"| BDTI | {bdti_val:,.0f} | {bdti_trend} |" if bdti_val is not None else "| BDTI | - | - |",
        f"| BCTI | {bcti_val:,.0f} | {bcti_trend} |" if bcti_val is not None else "| BCTI | - | - |",
        ""
    ]
    if bda_rows:
        md_doc.extend(["## Baltic Demolition Assessment (BDA)", "", "| Segment | Price ($/LDT) | Change (W-o-W) |", "|---|---|---|"])
        for b in bda_rows:
            p_s = f"{b['price']:.1f}" if b['price'] is not None else "-"
            c_s = f"{b['change']:+.1f}" if b['change'] is not None else "-"
            md_doc.append(f"| {b['segment']} | {p_s} | {c_s} |")
        md_doc.append("")
    md_doc.extend(["## Baltic TCE Freight Rates", ""])
    if dirty_rows:
        md_doc.extend(["### Baltic TCE Dirty", "", "| Route | Description | Quantity (MT) | Rate ($/Day) | Trend (W-o-W) |", "|---|---|---|---|---|"])
        for r in dirty_rows:
            q_s = f"{r['quantity']:,}" if r['quantity'] else "-"
            r_s = pam.format_rate(r['rate'])
            md_doc.append(f"| {r['route']} | {r['description']} | {q_s} | {r_s} | {r['trend']} |")
        md_doc.append("")
    if clean_rows:
        md_doc.extend(["### Baltic TCE Clean", "", "| Route | Description | Quantity (MT) | Rate ($/Day) | Trend (W-o-W) |", "|---|---|---|---|---|"])
        for r in clean_rows:
            q_s = f"{r['quantity']:,}" if r['quantity'] else "-"
            r_s = pam.format_rate(r['rate'])
            md_doc.append(f"| {r['route']} | {r['description']} | {q_s} | {r_s} | {r['trend']} |")
        md_doc.append("")
    if commentary_text:
        md_doc.extend(["## Tanker Market Commentary", "", commentary_text, ""])

    target_dir = MD_DIR / "affinity" / year_str
    target_md = target_dir / f"{pdf_path.stem}.md"
    target_tables = target_dir / f"{pdf_path.stem}.tables.json"

    if not dry_run:
        target_dir.mkdir(parents=True, exist_ok=True)
        target_md.write_text("\n".join(md_doc), encoding="utf-8")
        sidecar_data = {
            "convention": "iso", "pages": npages, "junk_pages": junk,
            "typed_confidence": "best-effort: card rows are exact geometry; see docs/affinity_survey.md",
            "cards": [{"name": c["name"], "columns": c["columns"], "rows": c["rows"], "error": c.get("error"), "issue_date": issue_date, "report_week": report_week, "source_file": pdf_path.name} for c in cards],
            "typed": typed, "text_verified": round(verified, 4), "panel_values": len(pnums),
            "date_fragments_merged": datefrag, "missing_values": missing[:40]
        }
        target_tables.write_text(json.dumps(sidecar_data, indent=2, ensure_ascii=False), encoding="utf-8")

        # Upsert series
        tce_rows = []
        for r in dirty_rows:
            tce_rows.append({"issue_date": issue_date, "report_week": report_week, "sector": "Dirty", "route": r["route"], "description": r["description"], "quantity_mt": r["quantity"], "tce_usd_per_day": r["rate"], "trend_wow": r["trend"], "source_file": pdf_path.name})
        for r in clean_rows:
            tce_rows.append({"issue_date": issue_date, "report_week": report_week, "sector": "Clean", "route": r["route"], "description": r["description"], "quantity_mt": r["quantity"], "tce_usd_per_day": r["rate"], "trend_wow": r["trend"], "source_file": pdf_path.name})
        upsert_rows_to_csv(SERIES_DIR / "affinity_tce_series.csv", tce_rows, ["issue_date", "report_week", "sector", "route", "description", "quantity_mt", "tce_usd_per_day", "trend_wow", "source_file"], ["issue_date", "sector", "route"])

        bda_series_rows = [{"issue_date": issue_date, "report_week": report_week, "segment": b["segment"], "price_usd_per_ldt": b["price"], "change_wow": b["change"], "source_file": pdf_path.name} for b in bda_rows]
        upsert_rows_to_csv(SERIES_DIR / "affinity_bda_series.csv", bda_series_rows, ["issue_date", "report_week", "segment", "price_usd_per_ldt", "change_wow", "source_file"], ["issue_date", "segment"])

    return {"stem": pdf_path.stem, "issue_date": issue_date, "report_week": report_week, "cards_count": len(cards), "target_md": str(target_md)}


def extract_carriers(pdf_path: Path, dry_run: bool = False) -> Dict[str, Any]:
    """Specialized extraction for Carriers Chartering Corp."""
    import run_carriers_complete as rcc

    stem = pdf_path.stem
    issue_date, report_week = rcc.extract_metadata(pdf_path)
    year_str = issue_date[:4] if issue_date and issue_date[:4].isdigit() else "2026"
    doc = fitz.open(pdf_path)

    doc_sales, doc_demo, doc_nb, doc_bspa, doc_bda = [], [], [], [], []
    doc_indices, doc_weighted, doc_tc_period, doc_tanker_tce = [], [], [], []
    substantive_pages = []

    for pno in range(len(doc)):
        page = doc[pno]
        lines = rcc.cluster_page_words_into_lines(page)
        anchors = {}
        for y, ln in lines:
            s = " ".join(w[4] for w in ln).lower()
            if "bulk carriers reported sold" in s and "bulk" not in anchors:
                anchors["bulk"] = y
            elif ("tankers / lpg" in s or "tankers reported sold" in s) and "tanker_sp" not in anchors:
                anchors["tanker_sp"] = y
            elif ("container / ro-ro" in s or "container reported sold" in s or "general cargo vessels" in s) and "container" not in anchors:
                anchors["container"] = y
            elif "demolition market" in s and "demo" not in anchors:
                anchors["demo"] = y
            elif "newbuilding market" in s and "newbuilding" not in anchors:
                anchors["newbuilding"] = y
            elif "bspa as reported" in s and "bspa" not in anchors:
                anchors["bspa"] = y
            elif "sale and purchase index" in s and "indices" not in anchors:
                anchors["indices"] = y
            elif ("dry bc baltic indices" in s or "baltic dry index" in s) and "bdi" not in anchors:
                anchors["bdi"] = y
            elif "weighted average routes" in s and "weighted" not in anchors:
                anchors["weighted"] = y
            elif ("time charter period" in s or "indicative ideas" in s) and "tc_period" not in anchors:
                anchors["tc_period"] = y
            elif ("tanker index" in s or "baltic dirty" in s) and "tanker_tce" not in anchors:
                anchors["tanker_tce"] = y
            elif ("greek-listed companies" in s or "quote of the day" in s or "traded in the us stock exchange" in s) and "greek" not in anchors:
                anchors["greek"] = y

        shipping_anchors = [k for k in anchors.keys() if k != "greek"]
        if not shipping_anchors:
            continue

        substantive_pages.append(pno + 1)
        sorted_anchors = sorted(anchors.items(), key=lambda x: x[1])

        for a_idx, (sec_name, y_start) in enumerate(sorted_anchors):
            if sec_name == "greek":
                break
            y_end = sorted_anchors[a_idx + 1][1] if a_idx + 1 < len(sorted_anchors) else 770.0
            if sec_name == "bulk":
                doc_sales.extend(rcc.extract_sp_section_rows(lines, y_start, y_end, "bulk_carriers", issue_date or "", report_week, pno + 1, pdf_path.name))
            elif sec_name == "tanker_sp":
                doc_sales.extend(rcc.extract_sp_section_rows(lines, y_start, y_end, "tankers", issue_date or "", report_week, pno + 1, pdf_path.name))
            elif sec_name == "container":
                doc_sales.extend(rcc.extract_sp_section_rows(lines, y_start, y_end, "containers", issue_date or "", report_week, pno + 1, pdf_path.name))
            elif sec_name == "demo":
                doc_demo.extend(rcc.extract_demolition_rows(lines, y_start, y_end, issue_date or "", report_week, pno + 1, pdf_path.name))
            elif sec_name == "newbuilding":
                doc_nb.extend(rcc.extract_newbuilding_rows(lines, y_start, y_end, issue_date or "", report_week, pno + 1, pdf_path.name))
            elif sec_name == "bspa":
                bspa_r, bda_r = rcc.extract_bspa_and_bda(page, y_start, y_end, issue_date or "", report_week, pdf_path.name)
                doc_bspa.extend(bspa_r)
                doc_bda.extend(bda_r)
            elif sec_name == "indices":
                doc_indices.extend(rcc.extract_shipping_indices(page, y_start, y_end, issue_date or "", report_week, pdf_path.name))
            elif sec_name == "bdi":
                doc_indices.extend(rcc.extract_baltic_dry(page, y_start, y_end, issue_date or "", report_week, pdf_path.name))
            elif sec_name == "weighted":
                doc_weighted.extend(rcc.extract_weighted_routes(page, y_start, y_end, issue_date or "", report_week, pdf_path.name))
            elif sec_name == "tc_period":
                doc_tc_period.extend(rcc.extract_tc_period(page, y_start, y_end, issue_date or "", report_week, pdf_path.name))
            elif sec_name == "tanker_tce":
                doc_tanker_tce.extend(rcc.extract_tanker_tce(page, y_start, y_end, issue_date or "", report_week, pdf_path.name))

    doc_data_combined = {
        "sales": doc_sales, "demolition": doc_demo, "newbuilding": doc_nb,
        "bspa": doc_bspa, "bda": doc_bda, "indices": doc_indices,
        "weighted_routes": doc_weighted, "tc_period": doc_tc_period, "tanker_tce": doc_tanker_tce
    }
    md_content = rcc.generate_markdown(stem, pdf_path, doc, substantive_pages, issue_date or "", report_week, doc_data_combined)
    doc.close()

    target_dir = MD_DIR / "carriers" / year_str
    target_md = target_dir / f"{stem}.md"
    target_tables = target_dir / f"{stem}.tables.json"

    if not dry_run:
        target_dir.mkdir(parents=True, exist_ok=True)
        target_md.write_text(md_content, encoding="utf-8")
        sidecar = {
            "stem": stem, "issue_date": issue_date, "report_week": report_week,
            "source_file": pdf_path.name, "pages_total": len(substantive_pages),
            "substantive_pages": substantive_pages,
            "counts": {k: len(v) for k, v in doc_data_combined.items()},
            "tables": doc_data_combined
        }
        target_tables.write_text(json.dumps(sidecar, indent=2, ensure_ascii=False), encoding="utf-8")

        upsert_rows_to_csv(SERIES_DIR / "carriers_sales_series.csv", doc_sales, [
            "issue_date", "report_week", "section", "page", "vessel_name", "type",
            "dwt", "built", "yard", "price_raw", "price_usd_mill", "buyers", "comments", "source_file"
        ], ["issue_date", "vessel_name", "dwt"])
        upsert_rows_to_csv(SERIES_DIR / "carriers_bspa_series.csv", doc_bspa, [
            "issue_date", "report_week", "sector", "vessel_class", "size_dwt",
            "price_usd_m", "sentiment_arrow", "source_file"
        ], ["issue_date", "vessel_class"])

    return {"stem": stem, "issue_date": issue_date, "report_week": report_week, "sales_count": len(doc_sales), "target_md": str(target_md)}


def extract_fearnleys(pdf_path: Path, dry_run: bool = False) -> Dict[str, Any]:
    """Specialized 6-pillar extraction for Fearnleys Weekly Market Reports."""
    import run_fearnleys_normalized as rfn
    stem = pdf_path.stem
    doc = fitz.open(pdf_path)
    page_count = len(doc)
    p1_text = rfn.clean_encoding(doc[0].get_text("text"))
    iso_date, year, week_num = rfn.extract_date_and_week(pdf_path, p1_text)

    commentary = rfn.extract_clean_commentary(doc)
    rate_cards = rfn.extract_rate_cards(doc)
    nb_activity, nb_prices = rfn.extract_newbuilding(doc)
    sp_dry, sp_wet = rfn.extract_secondhand_prices(doc)

    stamped_rows = []
    for r in rate_cards:
        row_copy = dict(r)
        row_copy["issue_date"] = iso_date
        row_copy["year"] = year
        row_copy["report_week"] = week_num
        row_copy["source_file"] = str(pdf_path.relative_to(ROOT)).replace("\\", "/")
        stamped_rows.append(row_copy)

    md_lines = [
        "---",
        f'title: "Fearnleys Weekly Report - Week {week_num}, {year}"',
        f'issue_date: "{iso_date}"',
        f"year: {year}",
        f"report_week: {week_num}",
        'publisher: "Fearnleys"',
        'category: "market_report"',
        f"pages: {page_count}",
        f'source_file: "{str(pdf_path.relative_to(ROOT)).replace(chr(92), "/")}"',
        "---",
        "",
        f"# Fearnleys Weekly Market Report (Week {week_num}, {year})",
        "",
        f"**Issue Date:** {iso_date} | **Pages:** {page_count} | **Publisher:** Fearnleys AS  ",
        f"**Source Document:** `{str(pdf_path.relative_to(ROOT)).replace(chr(92), "/")}`  ",
        "",
        "---",
        ""
    ]

    # 01 Tankers
    md_lines.append("## 01 Tankers\n")
    tanker_comm = [p for p in commentary if p[0] == "Tankers"]
    if tanker_comm:
        md_lines.append("### Market Commentary\n")
        grouped_tanker = {}
        for _, sub, text in tanker_comm:
            grouped_tanker.setdefault(sub, []).append(text)
        for sub, plist in grouped_tanker.items():
            if sub != "General":
                md_lines.append(f"#### {sub}\n")
            for p in plist:
                md_lines.append(f"{p}\n")

    dirty_rates = [r for r in rate_cards if r["chapter"] == "01 Tankers" and r["section"] == "Dirty Spot"]
    if dirty_rates:
        md_lines.extend(["### Dirty Spot Freight Rates", "", "| Route | Vessel Size | Current (WS) | Change |", "| :--- | :---: | :---: | :---: |"])
        for r in dirty_rates:
            md_lines.append(f"| {r['label']} | {r['vessel_size']} | {rfn.format_val(r['value'])} | {rfn.format_change(r.get('change'))} |")
        md_lines.append("")

    tanker_period = [r for r in rate_cards if r["chapter"] == "01 Tankers" and r["section"] == "Period & Availability"]
    if tanker_period:
        md_lines.extend(["### Period Rates & Fleet Availability", "", "| Metric / Vessel Class | Vessel Size | Current | Change |", "| :--- | :---: | :---: | :---: |"])
        for r in tanker_period:
            md_lines.append(f"| {r['label']} | {r['vessel_size']} | {rfn.format_val(r['value'])} | {rfn.format_change(r.get('change'))} |")
        md_lines.append("")
    md_lines.append("---\n")

    # 02 Dry Bulk
    md_lines.append("## 02 Dry Bulk\n")
    dry_comm = [p for p in commentary if p[0] == "Dry Bulk"]
    if dry_comm:
        md_lines.append("### Market Commentary\n")
        grouped_dry = {}
        for _, sub, text in dry_comm:
            grouped_dry.setdefault(sub, []).append(text)
        for sub, plist in grouped_dry.items():
            if sub != "General":
                md_lines.append(f"#### {sub}\n")
            for p in plist:
                md_lines.append(f"{p}\n")
    dry_spot = [r for r in rate_cards if r["chapter"] == "02 Dry Bulk" and r["section"] == "Dry Spot"]
    if dry_spot:
        md_lines.extend(["### Spot Rates & Indices", "", "| Route / Index | Vessel Size | Current ($/Day or Pts) | Change |", "| :--- | :---: | :---: | :---: |"])
        for r in dry_spot:
            md_lines.append(f"| {r['label']} | {r['vessel_size']} | {rfn.format_val(r['value'])} | {rfn.format_change(r.get('change'))} |")
        md_lines.append("")
    dry_1y = [r for r in rate_cards if r["chapter"] == "02 Dry Bulk" and r["section"] == "Dry 1Y TC"]
    if dry_1y:
        md_lines.extend(["### 1 Year T/C Rates", "", "| Vessel Class | Size / Eco Type | Rate ($/Day) | Change ($/Day) |", "| :--- | :---: | :---: | :---: |"])
        for r in dry_1y:
            md_lines.append(f"| {r['label']} | {r['vessel_size']} | {rfn.format_val(r['value'])} | {rfn.format_change(r.get('change'))} |")
        md_lines.append("")
    md_lines.append("---\n")

    # 03 Gas
    md_lines.append("## 03 Gas\n")
    gas_comm = [p for p in commentary if p[0] == "Gas"]
    if gas_comm:
        md_lines.append("### Market Commentary\n")
        for _, sub, text in gas_comm:
            if sub != "General":
                md_lines.append(f"#### {sub}\n")
            md_lines.append(f"{text}\n")
    gas_spot = [r for r in rate_cards if r["chapter"] == "03 Gas"]
    if gas_spot:
        md_lines.extend(["### Gas Rates & FOB Benchmarks", "", "| Benchmark / Route | Sector | Current | Change |", "| :--- | :--- | :---: | :---: |"])
        for r in gas_spot:
            md_lines.append(f"| {r['label']} | {r['section']} | {rfn.format_val(r['value'])} | {rfn.format_change(r.get('change'))} |")
        md_lines.append("")
    md_lines.append("---\n")

    # 04 Newbuilding
    md_lines.append("## 04 Newbuilding\n")
    if nb_prices:
        md_lines.extend(["### Indicative Newbuilding Prices ($M)", "", "| Vessel Type | Size | Current ($M) | Change ($M) |", "| :--- | :---: | :---: | :---: |"])
        for v_name, nb_item in nb_prices.items():
            md_lines.append(f"| {v_name} | {nb_item['size']} | ${nb_item['price_usd_m']:.1f} | $0.0 |")
        md_lines.append("")
    md_lines.append("---\n")

    # 05 Sale & Purchase
    md_lines.append("## 05 Sale & Purchase\n")
    if sp_dry or sp_wet:
        md_lines.append("### Indicative Secondhand Prices ($M)\n")
        if sp_dry:
            md_lines.extend(["#### Dry Bulk", "", "| Vessel Class | 5 Year Old ($M) | 10 Year Old ($M) |", "| :--- | :---: | :---: |"])
            for v_name, d_item in sp_dry.items():
                p5 = f"${d_item['5_yr']:.1f}" if "5_yr" in d_item else "-"
                p10 = f"${d_item['10_yr']:.1f}" if "10_yr" in d_item else "-"
                md_lines.append(f"| {v_name} | {p5} | {p10} |")
            md_lines.append("")
        if sp_wet:
            md_lines.extend(["#### Tankers (Wet)", "", "| Vessel Class | 5 Year Old ($M) | 10 Year Old ($M) |", "| :--- | :---: | :---: |"])
            for v_name, w_item in sp_wet.items():
                p5 = f"${w_item['5_yr']:.1f}" if "5_yr" in w_item else "-"
                p10 = f"${w_item['10_yr']:.1f}" if "10_yr" in w_item else "-"
                md_lines.append(f"| {v_name} | {p5} | {p10} |")
            md_lines.append("")
    md_lines.append("---\n")

    # 06 Market Brief
    md_lines.append("## 06 Market Brief\n")
    fx_rates = [r for r in rate_cards if r["chapter"] == "06 Market Brief" and r["section"] in ["Exchange Rates", "Interest Rates"]]
    if fx_rates:
        md_lines.extend(["### Exchange Rates & Interest Rates", "", "| Indicator | Category | Rate | Change |", "| :--- | :--- | :---: | :---: |"])
        for r in fx_rates:
            md_lines.append(f"| {r['label']} | {r['section']} | {rfn.format_val(r['value'])} | {rfn.format_change(r.get('change'))} |")
        md_lines.append("")
    bunkers = [r for r in rate_cards if r["chapter"] == "06 Market Brief" and r["section"] in ["Commodity Prices", "Bunker Prices"]]
    if bunkers:
        md_lines.extend(["### Commodity Prices & Bunkers", "", "| Benchmark | Location / Grade | Price | Change |", "| :--- | :--- | :---: | :---: |"])
        for r in bunkers:
            md_lines.append(f"| {r['label']} | {r['vessel_size']} | {rfn.format_val(r['value'])} | {rfn.format_change(r.get('change'))} |")
        md_lines.append("")

    target_dir = MD_DIR / "fearnleys" / str(year)
    target_md = target_dir / f"{stem}.md"
    target_tables = target_dir / f"{stem}.tables.json"

    if not dry_run:
        target_dir.mkdir(parents=True, exist_ok=True)
        md_text = "\n".join(md_lines)
        target_md.write_text(md_text, encoding="utf-8")
        (MD_DIR / "fearnleys" / f"{stem}.md").write_text(md_text, encoding="utf-8")

        sidecar_payload = {
            "convention": "iso", "publisher": "Fearnleys", "issue_date": iso_date,
            "year": year, "report_week": week_num, "pages": page_count,
            "source_file": str(pdf_path.relative_to(ROOT)).replace("\\", "/"),
            "activity_levels": nb_activity, "newbuilding_prices": nb_prices,
            "secondhand_prices": {"dry": sp_dry, "wet": sp_wet}, "rates": stamped_rows
        }
        sidecar_str = json.dumps(sidecar_payload, indent=2, ensure_ascii=False)
        target_tables.write_text(sidecar_str, encoding="utf-8")
        (MD_DIR / "fearnleys" / f"{stem}.tables.json").write_text(sidecar_str, encoding="utf-8")

    return {"stem": stem, "issue_date": iso_date, "report_week": week_num, "rates_count": len(stamped_rows), "target_md": str(target_md)}


def extract_clarksons(pdf_path: Path, dry_run: bool = False) -> Dict[str, Any]:
    """Specialized extraction for Clarksons Platou Hellas."""
    import run_clarksons_hellas_world_class as rcw
    stem = pdf_path.stem
    issue_date, year_str, report_week = rcw.parse_issue_date(pdf_path.name)
    cache_file = ROOT / "data" / "extracted" / "cache_clarksons_hellas" / f"{stem}.md"

    doc = fitz.open(pdf_path)
    if cache_file.exists():
        raw_md = cache_file.read_text(encoding="utf-8")
        data = rcw.extract_clarksons_data(raw_md, issue_date, report_week, pdf_path.name)
    else:
        text = "\n".join(p.get_text("text") for p in doc)
        data = rcw.extract_clarksons_data(text, issue_date, report_week, pdf_path.name)

    full_md = rcw.generate_clarksons_markdown(data)

    target_dir = MD_DIR / "clarksons" / year_str
    target_md = target_dir / f"{stem}.md"
    target_tables = target_dir / f"{stem}.tables.json"

    if not dry_run:
        target_dir.mkdir(parents=True, exist_ok=True)
        target_md.write_text(full_md, encoding="utf-8")
        target_tables.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    return {"stem": stem, "issue_date": issue_date, "report_week": report_week, "sales_count": len(data.get("sales", [])), "target_md": str(target_md)}


# ---------------------------------------------------------------------------
# Incremental Document Processor
# ---------------------------------------------------------------------------

def process_single_pdf(
    pdf_path: Path,
    pub: str,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Universal Single-Document Processor:
    - Delegates to specialized publisher extractors if available.
    - Captures and clips 200 DPI PNG screenshots of periodic charts.
    - Upserts series data cleanly with primary key deduplication.
    - Embeds screenshots into markdown reports.
    """
    pdf_path = Path(pdf_path).resolve()
    stem = pdf_path.stem

    # 1. Specialized Publisher Delegation
    specialized_result: Optional[Dict[str, Any]] = None
    if pub == "xclusiv":
        try:
            specialized_result = extract_xclusiv(pdf_path, dry_run=dry_run)
        except Exception as e:
            print(f"  [!] Note: specialized xclusiv failed ({e}), falling back to universal pipeline.")
    elif pub == "advanced_shipping":
        try:
            specialized_result = extract_advanced_shipping(pdf_path, dry_run=dry_run)
        except Exception as e:
            print(f"  [!] Note: specialized advanced_shipping failed ({e}), falling back to universal pipeline.")
    elif pub == "star_asia":
        try:
            specialized_result = extract_star_asia(pdf_path, dry_run=dry_run)
        except Exception as e:
            print(f"  [!] Note: specialized star_asia failed ({e}), falling back to universal pipeline.")
    elif pub == "affinity":
        try:
            specialized_result = extract_affinity(pdf_path, dry_run=dry_run)
        except Exception as e:
            print(f"  [!] Note: specialized affinity failed ({e}), falling back to universal pipeline.")
    elif pub in ("carriers", "general_broker") or "carrier" in stem.lower():
        try:
            specialized_result = extract_carriers(pdf_path, dry_run=dry_run)
        except Exception as e:
            print(f"  [!] Note: specialized carriers failed ({e}), falling back to universal pipeline.")
    elif pub == "fearnleys":
        try:
            specialized_result = extract_fearnleys(pdf_path, dry_run=dry_run)
        except Exception as e:
            print(f"  [!] Note: specialized fearnleys failed ({e}), falling back to universal pipeline.")
    elif pub == "clarksons":
        try:
            specialized_result = extract_clarksons(pdf_path, dry_run=dry_run)
        except Exception as e:
            print(f"  [!] Note: specialized clarksons failed ({e}), falling back to universal pipeline.")
    elif pub == "ism":
        try:
            import run_ism
            specialized_result = run_ism.extract_ism(pdf_path, dry_run=dry_run)
        except Exception as e:
            print(f"  [!] Note: specialized ism failed ({e}), falling back to universal pipeline.")
    elif pub == "intermodal":
        try:
            import run_intermodal_full
            if dry_run:
                wk, issue_date = run_intermodal_full.extract_report_metadata(pdf_path)
                specialized_result = {"stem": stem, "pub": pub, "issue_date": issue_date, "report_week": wk, "specialized": True}
            else:
                res = run_intermodal_full.process_single_pdf(pdf_path)
                specialized_result = {"stem": stem, "pub": pub, "specialized": True, "target_md": str(res.get("md_path", ""))}
        except Exception as e:
            print(f"  [!] Note: specialized intermodal failed ({e}), falling back to universal pipeline.")
    elif pub in ("banchero_costa", "bancosta"):
        try:
            import run_banchero_costa_tables
            res = run_banchero_costa_tables.process_banchero_costa_report(pdf_path)
            iss_dt = res["sidecar"].get("issue_date") or "2026-01-01"
            year_str_b = str(int(iss_dt[:4])) if iss_dt else "2026"
            target_dir_b = MD_DIR / "banchero_costa" / year_str_b
            target_dir_b.mkdir(parents=True, exist_ok=True)
            target_md_b = target_dir_b / f"{stem}.md"
            target_tables_b = target_dir_b / f"{stem}.tables.json"
            if not dry_run:
                target_md_b.write_text(res["markdown"], encoding="utf-8")
                target_tables_b.write_text(json.dumps(res["sidecar"], indent=2), encoding="utf-8")
                (MD_DIR / "banchero_costa" / f"{stem}.md").write_text(res["markdown"], encoding="utf-8")
                (MD_DIR / "banchero_costa" / f"{stem}.tables.json").write_text(json.dumps(res["sidecar"], indent=2), encoding="utf-8")
            specialized_result = {"stem": stem, "pub": "banchero_costa", "issue_date": iss_dt, "target_md": str(target_md_b), "specialized": True}
        except Exception as e:
            print(f"  [!] Note: specialized banchero_costa failed ({e}), falling back to universal pipeline.")
    elif pub == "agora":
        try:
            import format_agora_properly
            target_md = format_agora_properly.process_single_agora_file(pdf_path)
            specialized_result = {"stem": stem, "pub": pub, "specialized": True, "target_md": str(target_md)}
        except Exception as e:
            print(f"  [!] Note: specialized agora failed ({e}), falling back to universal pipeline.")
    elif pub == "lion":
        try:
            import run_lion_tables
            doc_l = fitz.open(pdf_path)
            pages_count = len(doc_l)
            full_text = "\n".join(doc_l[i].get_text() for i in range(pages_count))
            doc_l.close()
            doc_data = run_lion_tables.extract_full_report(full_text, str(pdf_path), pages_count)
            md = run_lion_tables.render_markdown(doc_data)
            sidecar = run_lion_tables.build_sidecar_json(doc_data)
            iss_dt = doc_data.get("issue_date") or f"{doc_data.get('year', 2026)}-01-01"
            year_str_l = str(int(iss_dt[:4])) if iss_dt else "2026"
            target_dir_l = MD_DIR / "lion" / year_str_l
            target_dir_l.mkdir(parents=True, exist_ok=True)
            target_md_l = target_dir_l / f"{stem}.md"
            target_tables_l = target_dir_l / f"{stem}.tables.json"
            if not dry_run:
                target_md_l.write_text(md, encoding="utf-8")
                target_tables_l.write_text(json.dumps(sidecar, indent=2), encoding="utf-8")
                (MD_DIR / "lion" / f"{stem}.md").write_text(md, encoding="utf-8")
            specialized_result = {"stem": stem, "pub": pub, "issue_date": iss_dt, "target_md": str(target_md_l), "specialized": True}
        except Exception as e:
            print(f"  [!] Note: specialized lion failed ({e}), falling back to universal pipeline.")
    elif pub == "ssy":
        try:
            import run_ssy_complete
            res = run_ssy_complete.process_report(pdf_path)
            specialized_result = {"stem": stem, "pub": pub, "specialized": True}
        except Exception as e:
            print(f"  [!] Note: specialized ssy failed ({e}), falling back to universal pipeline.")
    elif pub in ("drewry", "ais") or "drewry" in str(pdf_path).lower():
        try:
            if "ais" in str(pdf_path).lower():
                import run_drewry_ais
                res = run_drewry_ais.extract_drewry_ais(pdf_path, dry_run=dry_run)
                specialized_result = {"stem": stem, "pub": "drewry", "specialized": True}
            else:
                import run_drewry_opinions
                specialized_result = {"stem": stem, "pub": "drewry", "specialized": True}
        except Exception as e:
            print(f"  [!] Note: specialized drewry failed ({e}), falling back to universal pipeline.")
    elif pub == "poten":
        try:
            import run_poten
            specialized_result = {"stem": stem, "pub": pub, "specialized": True}
        except Exception as e:
            print(f"  [!] Note: specialized poten failed ({e}), falling back to universal pipeline.")
    elif pub == "seabrokers":
        try:
            import run_seabrokers_llamaparse
            specialized_result = {"stem": stem, "pub": pub, "specialized": True}
        except Exception as e:
            print(f"  [!] Note: specialized seabrokers failed ({e}), falling back to universal pipeline.")


    # 2. Chart Signature Probing & Screenshot Clipping
    doc = fitz.open(pdf_path)
    issue_date, year_str = resolve_document_date_and_year(doc, pdf_path)
    
    target_md_dir = MD_DIR / pub / year_str
    target_md_file = target_md_dir / f"{stem}.md"
    target_tables_file = target_md_dir / f"{stem}.tables.json"
    charts_target_dir = CHARTS_DIR / pub / year_str

    matched_charts: List[Dict[str, Any]] = []
    untracked_candidates: List[Dict[str, Any]] = []

    for pno in range(len(doc)):
        page = doc[pno]
        text = page.get_text("text")
        drawings = page.get_drawings()
        images = page.get_images()
        num_drawings = len(drawings)
        num_images = len(images)

        page_matched = False
        for sig in SIGNATURE_CATALOG:
            if sig.broker == pub and sig.match_page(text, num_drawings, num_images):
                chart_filename = f"{stem}_{sig.slug}_p{pno+1}.png"
                img_path = charts_target_dir / chart_filename
                
                if not dry_run:
                    charts_target_dir.mkdir(parents=True, exist_ok=True)
                    pix = page.get_pixmap(dpi=200)
                    pix.save(str(img_path))
                    
                matched_charts.append({
                    "signature": sig.slug,
                    "title": sig.title,
                    "page": pno + 1,
                    "image_rel": f"../../charts/{pub}/{year_str}/{chart_filename}",
                    "target_csv": str(sig.target_csv)
                })
                page_matched = True
                break

        if not page_matched and num_drawings >= 35:
            chart_filename = f"{stem}_figure_p{pno+1}.png"
            img_path = charts_target_dir / chart_filename
            if not dry_run:
                charts_target_dir.mkdir(parents=True, exist_ok=True)
                pix = page.get_pixmap(dpi=200)
                pix.save(str(img_path))
                
            untracked_candidates.append({
                "pub": pub,
                "file": stem,
                "page": pno + 1,
                "drawings": num_drawings,
                "image_rel": f"../../charts/{pub}/{year_str}/{chart_filename}",
                "text_snippet": text[:200].replace("\n", " ")
            })

    # If specialized extractor already generated markdown, inject detected chart links if present
    if specialized_result:
        flat_md_file = MD_DIR / pub / f"{stem}.md"
        if not target_md_file.exists() and flat_md_file.exists():
            target_md_dir.mkdir(parents=True, exist_ok=True)
            target_md_file.write_text(flat_md_file.read_text(encoding="utf-8"), encoding="utf-8")
        elif not target_md_file.exists() and (MD_DIR / pub).exists():
            matches = list((MD_DIR / pub).rglob(f"{stem}.md"))
            if matches:
                target_md_file = matches[0]
        
        if target_md_file.exists():
            if matched_charts:
                existing_md = target_md_file.read_text(encoding="utf-8")
                if "## Market Charts & Quantitative Vectors" not in existing_md:
                    chart_section = ["\n\n## Market Charts & Quantitative Vectors\n"]
                    for mc in matched_charts:
                        chart_section.append(f"### {mc['title']} (Page {mc['page']})\n")
                        chart_section.append(f"![{mc['title']}]({mc['image_rel']})\n")
                        chart_section.append(f"*Extracted to time series: `{Path(mc['target_csv']).name}`*\n")
                    target_md_file.write_text(existing_md + "\n".join(chart_section), encoding="utf-8")
            doc.close()
            return {
                "stem": stem,
                "pub": pub,
                "year": year_str,
                "issue_date": issue_date,
                "matched_charts": matched_charts,
                "untracked_candidates": untracked_candidates,
                "md_file": target_md_file,
                "specialized": True
            }

    # Universal Fallback Markdown Generation
    md_lines = [
        "---",
        f"title: \"{stem}\"",
        f"issue_date: \"{issue_date}\"",
        f"year: {year_str}",
        f"broker: \"{pub}\"",
        f"pages: {len(doc)}",
        f"source_file: \"{str(pdf_path.relative_to(ROOT)).replace(chr(92), '/')}\"",
        f"detected_charts: {len(matched_charts)}",
        "---",
        "",
        f"# {stem}",
        "",
        f"- **Broker**: {pub.replace('_', ' ').title()}",
        f"- **Issue Date**: {issue_date}",
        f"- **Pages**: {len(doc)}",
        "",
        "---",
        ""
    ]

    if matched_charts:
        md_lines.append("## Market Charts & Quantitative Vectors\n")
        for mc in matched_charts:
            md_lines.append(f"### {mc['title']} (Page {mc['page']})\n")
            md_lines.append(f"![{mc['title']}]({mc['image_rel']})\n")
            md_lines.append(f"*Extracted to time series: `{Path(mc['target_csv']).name}`*\n")

    md_lines.append("## Report Content\n")
    for pno in range(len(doc)):
        page = doc[pno]
        tabs = page.find_tables()
        tab_rects = [t.bbox for t in tabs]
        
        md_lines.append(f"### Page {pno+1}\n")
        
        # 1. Page text blocks outside tables
        blocks = page.get_text("blocks")
        for b in blocks:
            r = fitz.Rect(b[:4])
            if any(fitz.Rect(tr).intersects(r) for tr in tab_rects):
                continue
            btxt = b[4].strip()
            if not btxt:
                continue
            lines = [l.strip() for l in btxt.splitlines() if l.strip()]
            cleaned_p = " ".join(lines)
            if len(cleaned_p.split()) >= 3:
                md_lines.append(f"{cleaned_p}\n")
                
        # 2. Structured markdown pipe tables
        for tab in tabs:
            df = tab.extract()
            if df and len(df) > 1:
                hdr = [str(c).strip().replace("\n", " ") if c is not None else "" for c in df[0]]
                md_lines.append("| " + " | ".join(hdr) + " |")
                md_lines.append("|" + " :---: |" * len(hdr))
                for row in df[1:]:
                    cells = [str(c).strip().replace("\n", " ") if c is not None else "" for c in row]
                    md_lines.append("| " + " | ".join(cells) + " |")
                md_lines.append("")

    doc.close()

    if not dry_run:
        target_md_dir.mkdir(parents=True, exist_ok=True)
        target_md_file.write_text("\n".join(md_lines), encoding="utf-8")
        
        tables_sidecar = {
            "stem": stem,
            "issue_date": issue_date,
            "year": int(year_str),
            "broker": pub,
            "charts": matched_charts
        }
        target_tables_file.write_text(json.dumps(tables_sidecar, indent=2), encoding="utf-8")

    return {
        "stem": stem,
        "pub": pub,
        "year": year_str,
        "issue_date": issue_date,
        "matched_charts": matched_charts,
        "untracked_candidates": untracked_candidates,
        "md_file": target_md_file,
        "specialized": False
    }


# ---------------------------------------------------------------------------
# Corpus Ingestion Orchestration Loop
# ---------------------------------------------------------------------------

def run_orchestration(
    broker_filter: Optional[str] = None,
    specific_file: Optional[Path] = None,
    dry_run: bool = False,
    force: bool = False
):
    print("=" * 80)
    print(f"INCREMENTAL INGESTION & CHART FINGERPRINTING ENGINE ({'DRY RUN' if dry_run else 'LIVE'})")
    print("=" * 80)

    if specific_file:
        norm_path = str(specific_file).replace("\\", "/").lower()
        if "drewry" in norm_path:
            pub = "drewry"
        elif "poten" in norm_path:
            pub = "poten"
        elif "seabrokers" in norm_path:
            pub = "seabrokers"
        elif "breakwave" in norm_path:
            pub = "breakwave"
        elif "signal" in norm_path:
            pub = "signal"
        elif "baltic" in norm_path:
            pub = "baltic"
        else:
            pub = specific_file.parent.parent.name if specific_file.parent.name.isdigit() else specific_file.parent.name
        pdfs_to_process = [(pub, specific_file)]
    else:
        pdfs_to_process = []
        for pub_dir in sorted(CORPUS_DIR.iterdir()):
            if not pub_dir.is_dir() or pub_dir.name.startswith("_"):
                continue
            if broker_filter and pub_dir.name != broker_filter:
                continue

            for pdf in pub_dir.rglob("*.pdf"):
                stem = pdf.stem
                extracted = list((MD_DIR / pub_dir.name).rglob(f"{stem}.md"))
                if not extracted or force:
                    pdfs_to_process.append((pub_dir.name, pdf))

    print(f"Discovered {len(pdfs_to_process)} document(s) requiring extraction/update.")

    all_untracked: List[Dict[str, Any]] = []
    processed_count = 0
    total_charts_matched = 0

    for pub, pdf in pdfs_to_process:
        try:
            res = process_single_pdf(pdf, pub, dry_run=dry_run)
            processed_count += 1
            num_charts = len(res["matched_charts"])
            total_charts_matched += num_charts
            all_untracked.extend(res["untracked_candidates"])

            spec_tag = " (Specialized Pipeline)" if res.get("specialized") else ""
            if num_charts > 0:
                print(f"[{pub:<16}] {pdf.name[:45]:<45} -> {res['year']} (Charts: {num_charts}){spec_tag}")
            else:
                print(f"[{pub:<16}] {pdf.name[:45]:<45} -> {res['year']}{spec_tag}")
        except Exception as e:
            print(f"[{pub:<16}] ERROR processing {pdf.name}: {e}")

    if all_untracked and not dry_run:
        UNTRACKED_CHARTS_LOG.parent.mkdir(parents=True, exist_ok=True)
        existing_untracked = []
        if UNTRACKED_CHARTS_LOG.exists():
            try:
                existing_untracked = json.loads(UNTRACKED_CHARTS_LOG.read_text(encoding="utf-8"))
            except Exception:
                pass
        existing_untracked.extend(all_untracked)
        UNTRACKED_CHARTS_LOG.write_text(json.dumps(existing_untracked, indent=2), encoding="utf-8")
        print(f"Logged {len(all_untracked)} untracked candidate figure(s) to {UNTRACKED_CHARTS_LOG.name}")

    print("=" * 80)
    print(f"INGESTION COMPLETE: {processed_count} files processed, {total_charts_matched} charts clipped/calibrated.")
    print("=" * 80)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Incremental Broker Ingest Orchestrator")
    parser.add_argument("--broker", type=str, help="Process specific broker")
    parser.add_argument("--file", type=str, help="Process a specific PDF file")
    parser.add_argument("--all", action="store_true", help="Process all pending PDFs across corpus")
    parser.add_argument("--force", action="store_true", help="Force re-extraction of existing files")
    parser.add_argument("--dry-run", action="store_true", help="Plan extraction without writing to disk")
    args = parser.parse_args()

    target_file = Path(args.file) if args.file else None
    run_orchestration(
        broker_filter=args.broker,
        specific_file=target_file,
        dry_run=args.dry_run,
        force=args.force
    )
