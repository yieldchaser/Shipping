"""
Hellenic Iron Ore & Capesize Freight Daily Extraction Pipeline.

Extracts daily MMi & SMM Iron Ore Index Reports from corpus/02-hellenic/iron_ore/pdfs/:
  - 1,171 unbroken business days spanning July 2021 through September 2026.
  - Physical iron ore spot prices (FOT Qingdao RMB/wmt): IOPI 62%/61%, IOPI 65%, IOPI 58%.
  - Seaborne iron ore indices (CFR Qingdao USD/dmt): IOSI 62%/61%, IOSI 65%, IOPLI 62.5% Lump.
  - Exchange futures closing prices: DCE Iron Ore (I contract), SGX Iron Ore (62% CFR), SHFE Rebar.
  - Key Baltic Capesize iron ore freight routes: C3 (Tubarao-Qingdao) and C5 (W. Australia-Qingdao).
  - Domestic Chinese steel prices: Rebar & HRC (RMB/t).
  - Port & mill inventories: 35-port iron ore stocks (Mt) & Chinese steel inventory (Mt).
  - Full daily desk market commentary on Chinese mills, steel demand, and port trades.

Produces:
  1. Clean daily Markdown files: data/extracted/md/hellenic/iron_ore/<year>/hellenic_iron_ore_<date>.md
  2. Structured JSON sidecars: data/extracted/md/hellenic/iron_ore/<year>/hellenic_iron_ore_<date>.tables.json
  3. Master stacked daily series: data/extracted/series/hellenic_iron_ore_daily_series.csv
  4. Capesize freight series: data/extracted/series/hellenic_capesize_c3_c5_series.csv
"""

import os
import sys
import re
import json
import logging
from pathlib import Path
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import pymupdf

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("HellenicIronOre")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
PDF_DIR = REPO_ROOT / "corpus" / "02-hellenic" / "iron_ore" / "pdfs"
MD_BASE_DIR = REPO_ROOT / "data" / "extracted" / "md" / "hellenic" / "iron_ore"
SERIES_DIR = REPO_ROOT / "data" / "extracted" / "series"

COLS = [(0, 190), (190, 380), (380, 580)]

ROW_VAL_BANDS = [
    (190, 222, ["iopi_bench_rmb_wmt", "iopi65_rmb_wmt", "iopi58_rmb_wmt"]),
    (295, 328, ["iosi_bench_usd_dmt", "iosi65_usd_dmt", "iopli_lump_rmb_wmt"]),
    (430, 465, ["dce_iron_ore_rmb_t", "sgx_iron_ore_usd_dmt", "shfe_rebar_rmb_t"]),
    (565, 600, ["c3_tubarao_qingdao_usd_t", "c5_waust_qingdao_usd_t", "steel_rebar_domestic_rmb_t"]),
    (705, 740, ["port_iron_ore_inventory_mt", "steel_inventory_china_mt", "steel_hrc_domestic_rmb_t"])
]

ROW_CHG_BANDS = [
    (220, 245, ["iopi_bench_chg_rmb", "iopi65_chg_rmb", "iopi58_chg_rmb"]),
    (328, 355, ["iosi_bench_chg_usd", "iosi65_chg_usd", "iopli_lump_chg_rmb"]),
    (465, 490, ["dce_chg_rmb", "sgx_chg_usd", "shfe_rebar_chg_rmb"]),
    (600, 625, ["c3_chg_usd", "c5_chg_usd", "steel_rebar_chg_rmb"]),
    (740, 765, ["port_inv_chg_mt", "steel_inv_chg_mt", "steel_hrc_chg_rmb"])
]


def extract_date_from_filename(filename: str) -> str:
    m = re.search(r"(\d{4}-\d{2}-\d{2})", filename)
    return m.group(1) if m else None


def parse_mmi_report(doc: pymupdf.Document, pdf_name: str, date_iso: str) -> dict:
    p1 = doc[0]
    blocks = p1.get_text("blocks")

    # Determine benchmark Fe grade (62% vs 61%)
    p1_hdr = " ".join([b[4] for b in blocks if 165 <= (b[1]+b[3])/2 < 190 and (b[0]+b[2])/2 < 190])
    bench_grade = 61.0 if "61%" in p1_hdr else 62.0

    record = {
        "date": date_iso,
        "year": int(date_iso[:4]),
        "month": int(date_iso[5:7]),
        "benchmark_fe_grade": bench_grade,
        "iopi_bench_rmb_wmt": None,
        "iopi65_rmb_wmt": None,
        "iopi58_rmb_wmt": None,
        "iosi_bench_usd_dmt": None,
        "iosi65_usd_dmt": None,
        "iopli_lump_rmb_wmt": None,
        "dce_iron_ore_rmb_t": None,
        "sgx_iron_ore_usd_dmt": None,
        "shfe_rebar_rmb_t": None,
        "c3_tubarao_qingdao_usd_t": None,
        "c5_waust_qingdao_usd_t": None,
        "steel_rebar_domestic_rmb_t": None,
        "port_iron_ore_inventory_mt": None,
        "steel_inventory_china_mt": None,
        "steel_hrc_domestic_rmb_t": None,
        "iopi_bench_chg_rmb": None,
        "iopi65_chg_rmb": None,
        "iopi58_chg_rmb": None,
        "iosi_bench_chg_usd": None,
        "iosi65_chg_usd": None,
        "iopli_lump_chg_rmb": None,
        "c3_chg_usd": None,
        "c5_chg_usd": None,
        "commentary": "",
        "source_file": pdf_name
    }

    # Extract values
    for ymin, ymax, labels in ROW_VAL_BANDS:
        for (xmin, xmax), label in zip(COLS, labels):
            cell = [b for b in blocks if xmin <= (b[0]+b[2])/2 < xmax and ymin <= (b[1]+b[3])/2 < ymax]
            txt = " ".join([b[4].strip() for b in cell])
            nums = re.findall(r"-?\d+(?:\.\d+)?", txt)
            if nums:
                record[label] = float(nums[0])

    # Extract changes
    for ymin, ymax, labels in ROW_CHG_BANDS:
        for (xmin, xmax), label in zip(COLS, labels):
            cell = [b for b in blocks if xmin <= (b[0]+b[2])/2 < xmax and ymin <= (b[1]+b[3])/2 < ymax]
            txt = " ".join([b[4].strip() for b in cell])
            nums = re.findall(r"-?\d+(?:\.\d+)?", txt)
            if nums:
                record[label] = float(nums[0])

    # Extract Page 2 Commentary
    if len(doc) > 1:
        p2_text = doc[1].get_text("text")
        m_c = re.search(r"MARKET\s+COMMENTARY[\s\S]*?(?=\n\n[A-Z\s]{4,}|\Z)", p2_text, re.I)
        if m_c:
            lines = [l.strip() for l in m_c.group(0).splitlines() if l.strip()]
            record["commentary"] = " ".join(lines[1:])
    
    return record


def parse_smm_report(doc: pymupdf.Document, pdf_name: str, date_iso: str) -> dict:
    p1 = doc[0]
    txt = p1.get_text("text")

    record = {
        "date": date_iso,
        "year": int(date_iso[:4]),
        "month": int(date_iso[5:7]),
        "benchmark_fe_grade": 62.0,
        "iopi_bench_rmb_wmt": None,
        "iopi65_rmb_wmt": None,
        "iopi58_rmb_wmt": None,
        "iosi_bench_usd_dmt": None,
        "iosi65_usd_dmt": None,
        "iopli_lump_rmb_wmt": None,
        "dce_iron_ore_rmb_t": None,
        "sgx_iron_ore_usd_dmt": None,
        "shfe_rebar_rmb_t": None,
        "c3_tubarao_qingdao_usd_t": None,
        "c5_waust_qingdao_usd_t": None,
        "steel_rebar_domestic_rmb_t": None,
        "port_iron_ore_inventory_mt": None,
        "steel_inventory_china_mt": None,
        "steel_hrc_domestic_rmb_t": None,
        "iopi_bench_chg_rmb": None,
        "iopi65_chg_rmb": None,
        "iopi58_chg_rmb": None,
        "iosi_bench_chg_usd": None,
        "iosi65_chg_usd": None,
        "iopli_lump_chg_rmb": None,
        "c3_chg_usd": None,
        "c5_chg_usd": None,
        "commentary": "",
        "source_file": pdf_name
    }

    m_sgx = re.search(r"SGX Iron Ore Most-traded[^\n]*\n+Daily\s+([\d\.]+)\s+USD/dmt", txt, re.I)
    if m_sgx:
        record["sgx_iron_ore_usd_dmt"] = float(m_sgx.group(1))

    m_dce = re.search(r"DCE Iron Ore Most-traded[^\n]*\n+Daily\s+([\d\.]+)\s+yuan/mt", txt, re.I)
    if m_dce:
        record["dce_iron_ore_rmb_t"] = float(m_dce.group(1))

    m_smm62 = re.search(r"SMM 62% Iron Ore Index[^\n]*\n+([\d\.]+)\s+USD/dmt", txt, re.I)
    if m_smm62:
        record["iosi_bench_usd_dmt"] = float(m_smm62.group(1))

    m_comm = re.search(r"Commentary[\s\S]*?(?=\n\n|\Z)", txt, re.I)
    if m_comm:
        record["commentary"] = m_comm.group(0).strip()

    return record


def generate_markdown(record: dict, doc: pymupdf.Document) -> str:
    md_lines = [
        "---",
        f"title: \"MMi Daily Iron Ore Index & Freight Report - {record['date']}\"",
        f"date: \"{record['date']}\"",
        f"year: {record['year']}",
        f"source: \"hellenic/mmi\"",
        f"benchmark_fe_grade: \"{record['benchmark_fe_grade']}%\product\"",
        f"iosi_bench_usd_dmt: {record.get('iosi_bench_usd_dmt')}",
        f"iopi_bench_rmb_wmt: {record.get('iopi_bench_rmb_wmt')}",
        f"c3_tubarao_qingdao_usd_t: {record.get('c3_tubarao_qingdao_usd_t')}",
        f"c5_waust_qingdao_usd_t: {record.get('c5_waust_qingdao_usd_t')}",
        f"source_file: \"{record['source_file']}\"",
        "---",
        "",
        f"# MMi Daily Iron Ore Index Report — {record['date']}",
        "",
        "## Daily Pricing & Freight Assessment Dashboard",
        "",
        "| Metric | Value | Unit | Daily Change |",
        "| :--- | :---: | :---: | :---: |",
        f"| **Seaborne Benchmark ({record['benchmark_fe_grade']}%)** | {record.get('iosi_bench_usd_dmt', 'N/A')} | USD/dmt (CFR Qingdao) | {record.get('iosi_bench_chg_usd', 'N/A')} |",
        f"| **Seaborne 65% Fe Fines** | {record.get('iosi65_usd_dmt', 'N/A')} | USD/dmt (CFR Qingdao) | {record.get('iosi65_chg_usd', 'N/A')} |",
        f"| **Port Stock Benchmark ({record['benchmark_fe_grade']}%)** | {record.get('iopi_bench_rmb_wmt', 'N/A')} | RMB/wet tonne (FOT) | {record.get('iopi_bench_chg_rmb', 'N/A')} |",
        f"| **Port Stock 65% Fe Fines** | {record.get('iopi65_rmb_wmt', 'N/A')} | RMB/wet tonne (FOT) | {record.get('iopi65_chg_rmb', 'N/A')} |",
        f"| **Port Stock 58% Fe Fines** | {record.get('iopi58_rmb_wmt', 'N/A')} | RMB/wet tonne (FOT) | {record.get('iopi58_chg_rmb', 'N/A')} |",
        f"| **Port Stock 62.5% Fe Lump** | {record.get('iopli_lump_rmb_wmt', 'N/A')} | RMB/wet tonne (FOT) | {record.get('iopli_lump_chg_rmb', 'N/A')} |",
        f"| **DCE Iron Ore Futures (Front)** | {record.get('dce_iron_ore_rmb_t', 'N/A')} | RMB/t | - |",
        f"| **SGX Iron Ore Futures (Front)** | {record.get('sgx_iron_ore_usd_dmt', 'N/A')} | USD/dmt | - |",
        f"| **SHFE Rebar Futures (Front)** | {record.get('shfe_rebar_rmb_t', 'N/A')} | RMB/t | - |",
        f"| **Capesize C3 Tubarao–Qingdao** | {record.get('c3_tubarao_qingdao_usd_t', 'N/A')} | USD/t | {record.get('c3_chg_usd', 'N/A')} |",
        f"| **Capesize C5 W.Aus–Qingdao** | {record.get('c5_waust_qingdao_usd_t', 'N/A')} | USD/t | {record.get('c5_chg_usd', 'N/A')} |",
        f"| **Domestic Chinese Rebar** | {record.get('steel_rebar_domestic_rmb_t', 'N/A')} | RMB/t | - |",
        f"| **Domestic Chinese HRC** | {record.get('steel_hrc_domestic_rmb_t', 'N/A')} | RMB/t | - |",
        f"| **Chinese 35-Port Iron Ore Inventory** | {record.get('port_iron_ore_inventory_mt', 'N/A')} | Million Tonnes | - |",
        f"| **Chinese Steel Inventory** | {record.get('steel_inventory_china_mt', 'N/A')} | Million Tonnes | - |",
        "",
        "## Daily Market Commentary",
        "",
        record.get("commentary", "No desk commentary available for this date.")
    ]
    return "\n".join(md_lines)


def process_single_date(date_iso: str, pdf_candidates: list) -> dict:
    # Pick the largest candidate file (most complete)
    best_pdf = sorted(pdf_candidates, key=lambda f: f.stat().st_size, reverse=True)[0]
    try:
        doc = pymupdf.open(best_pdf)
        p1_txt = doc[0].get_text("text")[:300]
        
        if "SMM" in p1_txt:
            record = parse_smm_report(doc, best_pdf.name, date_iso)
        else:
            record = parse_mmi_report(doc, best_pdf.name, date_iso)

        # Save Markdown and Sidecar JSON
        year_str = date_iso[:4]
        out_dir = MD_BASE_DIR / year_str
        out_dir.mkdir(parents=True, exist_ok=True)
        
        md_content = generate_markdown(record, doc)
        md_path = out_dir / f"hellenic_iron_ore_{date_iso}.md"
        md_path.write_text(md_content, encoding="utf-8")

        sidecar_path = out_dir / f"hellenic_iron_ore_{date_iso}.tables.json"
        sidecar_path.write_text(json.dumps(record, indent=2), encoding="utf-8")

        return {"date": date_iso, "record": record, "success": True}
    except Exception as e:
        logger.error(f"Error processing {date_iso} ({best_pdf.name}): {e}")
        return {"date": date_iso, "error": str(e), "success": False}


def run_pipeline():
    logger.info("Scanning Hellenic Iron Ore PDFs...")
    all_pdfs = sorted(list(PDF_DIR.glob("*.pdf")))
    logger.info(f"Found {len(all_pdfs)} total PDFs.")

    by_date = defaultdict(list)
    for p in all_pdfs:
        d = extract_date_from_filename(p.name)
        if d:
            by_date[d].append(p)

    logger.info(f"Grouped into {len(by_date)} unique daily dates.")
    unique_dates = sorted(list(by_date.keys()))

    all_records = []
    success_count = 0

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(process_single_date, d, by_date[d]): d for d in unique_dates}
        for fut in as_completed(futures):
            res = fut.result()
            if res.get("success"):
                all_records.append(res["record"])
                success_count += 1
            else:
                logger.warning(f"Failed on {res.get('date')}: {res.get('error')}")

    logger.info(f"Successfully processed {success_count} / {len(unique_dates)} dates!")

    if all_records:
        df = pd.DataFrame(all_records)
        df = df.sort_values(by="date").reset_index(drop=True)

        # 1. Master Iron Ore Daily Series
        main_csv = SERIES_DIR / "hellenic_iron_ore_daily_series.csv"
        df.to_csv(main_csv, index=False)
        logger.info(f"Wrote {len(df)} rows to {main_csv.name}!")

        # 2. Dedicated Capesize C3 / C5 Freight Series
        freight_cols = [
            "date", "year", "month",
            "c3_tubarao_qingdao_usd_t", "c3_chg_usd",
            "c5_waust_qingdao_usd_t", "c5_chg_usd",
            "source_file"
        ]
        df_freight = df[freight_cols].dropna(subset=["c3_tubarao_qingdao_usd_t", "c5_waust_qingdao_usd_t"], how="all").reset_index(drop=True)
        freight_csv = SERIES_DIR / "hellenic_capesize_c3_c5_series.csv"
        df_freight.to_csv(freight_csv, index=False)
        logger.info(f"Wrote {len(df_freight)} rows to {freight_csv.name}!")


if __name__ == "__main__":
    run_pipeline()
