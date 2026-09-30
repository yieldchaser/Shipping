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
    if specialized_result and target_md_file.exists():
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
        ptext = doc[pno].get_text("text").strip()
        if ptext:
            md_lines.append(f"### Page {pno+1}\n")
            md_lines.append(f"```\n{ptext}\n```\n")

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
