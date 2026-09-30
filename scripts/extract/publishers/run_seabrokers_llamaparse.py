"""
Seabrokers Seabreeze Monthly Reports Full LlamaParse Extraction Pipeline.

Extracts all 97 monthly SEABREEZE offshore market intelligence reports (2018-2026)
cover-to-cover using LlamaParse with publication-grade Markdown normalization,
high-fidelity structured table sidecars, and automated multi-account failover.

Deliverables:
  - Publication-grade Markdown with YAML frontmatter and cleaned headings/tables:
      data/extracted/md/seabrokers/<year>/<stem>.md
  - Structured Table JSON sidecars:
      data/extracted/md/seabrokers/<year>/<stem>.tables.json
  - Master Catalog Series:
      data/extracted/series/seabrokers_catalog_metadata.csv
  - Master Series CSVs (already exported):
      data/extracted/series/seabrokers_osv_spot_rates_series.csv
      data/extracted/series/seabrokers_osv_monthly_history_series.csv
      data/extracted/series/seabrokers_osv_utilisation_series.csv
      data/extracted/series/seabrokers_rigs_market_series.csv
      data/extracted/series/seabrokers_snp_auctions_series.csv
      data/extracted/series/seabrokers_fleet_moves_series.csv
      data/extracted/series/seabrokers_feature_vessels_series.csv
      data/extracted/series/seabrokers_renewables_and_ets_series.csv
"""

import os
import sys
import re
import json
import time
import glob
import logging
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd

# Add repo root to pythonpath
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.extract.llama_manager import manager, get_active_parser

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("SeabrokersLlama")

PDF_DIR = REPO_ROOT / "corpus" / "05-seabrokers" / "pdfs"
MD_BASE_DIR = REPO_ROOT / "data" / "extracted" / "md" / "seabrokers"
CACHE_DIR = REPO_ROOT / "data" / "extracted" / "llamaparse_seabrokers"
SERIES_DIR = REPO_ROOT / "data" / "extracted" / "series"
STATE_FILE = CACHE_DIR / "_run_state.json"

MD_BASE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)
SERIES_DIR.mkdir(parents=True, exist_ok=True)

MONTH_NAMES = {
    1: "January", 2: "February", 3: "March", 4: "April",
    5: "May", 6: "June", 7: "July", 8: "August",
    9: "September", 10: "October", 11: "November", 12: "December"
}


def load_run_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"done": {}, "failed": {}}


def save_run_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def parse_date_from_filename(filename: str):
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})_', filename)
    if m:
        yr = int(m.group(1))
        mo = int(m.group(2))
        day = int(m.group(3))
        iso_date = f"{yr:04d}-{mo:02d}-{day:02d}"
        return iso_date, yr, mo
    return "2026-01-01", 2026, 1


def normalize_seabrokers_content(text: str) -> str:
    """Publication-grade normalizer for Seabrokers Seabreeze reports.

    - Strips running headers ('Seabreeze — Month Year')
    - Strips isolated running page numbers ('10 11', '14 15', '26 27')
    - Strips repetitive corporate office directories, phone/email lists, and ISO 9001 boilerplate
    - Structures Table of Contents into a clean Markdown list
    - Structures North Sea Spot Arrivals & Departures into clean bulleted sections
    - Structures Page 1 headline teasers into Executive Highlights
    - Strips stray question marks and excess whitespace
    """
    text = text.replace('\r\n', '\n')

    # Format Table of Contents
    def _toc_repl(m):
        raw_items = m.group(1).strip()
        items = re.findall(r'(\d{1,2})\s+([A-Za-z][A-Za-z0-9&,\s/–-]+?)(?=\s+\d{1,2}\b|\Z)', raw_items)
        if items:
            toc = ['## Contents', '']
            for page, title in items:
                t = title.strip()
                if 'Contact Details' not in t and 'Seabrokers Group' not in t:
                    toc.append(f'- **{t}** *(p. {page})*')
            return '\n'.join(toc) + '\n\n'
        return m.group(0)

    text = re.sub(r'(?is)\bContents\s*\n((?:\d{1,2}\s+[A-Za-z][A-Za-z0-9&,\s/–-]+\s*)+)', _toc_repl, text)

    # Format Executive Highlights / Teasers on Page 1
    def _teaser_repl(m):
        raw_block = m.group(0).strip()
        lines = [l.strip() for l in raw_block.split('\n') if l.strip()]
        out = ['## Executive Highlights', '']
        for l in lines:
            tm = re.match(r'^(.*?)\s*/\s*(\d{1,2})$', l)
            if tm:
                out.append(f'- **{tm.group(1).strip()}** *(p. {tm.group(2)})*')
            else:
                out.append(f'- {l}')
        return '\n'.join(out) + '\n\n'

    text = re.sub(r'(?m)^(?:[A-Z0-9][A-Za-z0-9\s,&–-]+?\s*/\s*\d{1,2}\n?){2,}', _teaser_repl, text)

    # Remove running headers like 'Seabreeze — Month Year' or 'Seabreeze Month Year'
    text = re.sub(r'(?im)^[ \t]*Seabreeze\s*[-–—]?\s*(?:January|February|March|April|May|June|July|August|September|October|November|December)\s*\d{4}[ \t]*$', '', text)

    # Remove running page numbers
    text = re.sub(r'(?m)^\s*\d{1,2}\s+\d{1,2}\s*$', '', text)
    text = re.sub(r'(?m)^\s*\d{1,2}\s*$', '', text)

    # Format Arrivals & Departures
    def _arr_dep_repl(m):
        arr_part = m.group(1).strip()
        dep_part = m.group(2).strip()
        out = ['### North Sea Spot Arrivals & Departures', '']
        out.append('**Arrivals:**')
        for l in arr_part.split('\n'):
            l = l.strip()
            if not l:
                continue
            items = re.split(r'\s{2,}|(?<=SEA)\s+|(?<=AMERICA)\s+', l)
            for it in items:
                it = it.strip()
                if not it:
                    continue
                pts = re.split(r'\s+EX\s+', it, flags=re.IGNORECASE)
                if len(pts) == 2:
                    out.append(f'- **{pts[0].strip().title()}:** ex {pts[1].strip().title()}')
                else:
                    out.append(f'- **{it.strip().title()}**')
        out.append('')
        out.append('**Departures:**')
        for l in dep_part.split('\n'):
            l = l.strip()
            if not l:
                continue
            items = re.split(r'\s{2,}|(?<=AFRICA)\s+|(?<=CARIBBEAN)\s+', l)
            for it in items:
                it = it.strip()
                if not it:
                    continue
                out.append(f'- **{it.strip().title()}**')
        out.append('')
        out.append('*Note: Vessels arriving in or departing from the North Sea term/layup market are excluded.*')
        return '\n'.join(out) + '\n\n'

    text = re.sub(r'(?is)ARRIVALS NORTH SEA SPOT\s*\*?\s*\n(.*?)\nDEPARTURES NORTH SEA SPOT\s*\*?\s*\n(.*?)(?=\*Vessels|\n\n|\Z)', _arr_dep_repl, text)
    text = re.sub(r'(?i)\*Vessels arriving in or departing from the North Sea term/layup market are not included here\.?', '', text)

    # Strip corporate directory and repetitive office address boilerplate at footers / page breaks
    text = re.sub(r'(?is)\n(?:#+\s*)?SEABROKERS GROUP\b.*?(?:ISO\s*9001:2015|seabrokers\.com\.br|chartering@seabrokers\.\w+).*?$', '', text)
    text = re.sub(r'(?is)Seabrokers\s+(?:Fundamentering|Heavy Machinery|Head Office|Chartering\s*-\s*Stavanger).*?(?=\n\n|\Z)', '', text)
    text = re.sub(r'(?is)Production & Administration.*?(?:ISO 9001:2015|\.co\.uk)\.?', '', text)
    text = re.sub(r'(?is)SEABROKERS GROUP:\s*Over the last 40\+ years.*?(?=\n\n|\Z)', '', text)
    text = re.sub(r'(?i)^[ \t]*seabrokers\.no[ \t]*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'(?i)^[ \t]*SEABREEZE\s*©\s*Seabrokers Group.*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'(?i)^[ \t]*Seabreeze,\s*email:\s*chartering@seabrokers\.co\.uk.*$', '', text, flags=re.MULTILINE)

    # Remove stray lone question marks or empty dividers
    text = re.sub(r'(?m)^\s*\?\s*$', '', text)
    text = re.sub(r'(?m)^---[ \t]*\n(?:---[ \t]*\n)+', '---\n', text)

    # Normalize multiple blank lines
    text = re.sub(r'\n{3,}', '\n\n', text).strip()
    return text


def parse_markdown_tables(md_text: str):
    """Parses all Markdown pipe tables into structured dictionaries."""
    lines = md_text.split('\n')
    tables = []
    current_table = []
    current_header = 'Table'
    in_table = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith('#'):
            if not in_table:
                current_header = stripped.lstrip('#').strip()
        if '|' in stripped and stripped.startswith('|') and stripped.endswith('|'):
            in_table = True
            current_table.append(stripped)
        else:
            if in_table and len(current_table) >= 2:
                tbl = _build_table_dict(current_header, current_table)
                if tbl:
                    tables.append(tbl)
            current_table = []
            in_table = False

    if in_table and len(current_table) >= 2:
        tbl = _build_table_dict(current_header, current_table)
        if tbl:
            tables.append(tbl)

    return tables


def _build_table_dict(header_title: str, table_lines: list):
    try:
        header_row = [c.strip() for c in table_lines[0].split('|')[1:-1]]
        data_rows = []
        for r in table_lines[2:]:  # skip separator line
            cells = [c.strip() for c in r.split('|')[1:-1]]
            if len(cells) == len(header_row):
                data_rows.append(dict(zip(header_row, cells)))
            elif cells:
                data_rows.append(cells)
        return {
            "title": header_title,
            "columns": header_row,
            "row_count": len(data_rows),
            "rows": data_rows
        }
    except Exception:
        return None


def process_single_report(pdf_path: Path):
    stem = pdf_path.stem
    iso_date, year, month = parse_date_from_filename(pdf_path.name)
    month_name = MONTH_NAMES.get(month, f"Month {month}")
    report_title = f"Seabreeze Monthly Offshore Market Report - {month_name} {year}"

    target_md_dir = MD_BASE_DIR / str(year)
    target_md_dir.mkdir(parents=True, exist_ok=True)
    target_md_path = target_md_dir / f"{stem}.md"
    target_tables_path = target_md_dir / f"{stem}.tables.json"
    cache_json = CACHE_DIR / f"{stem}.json"

    raw_text = None
    pages_count = 0

    # 1. Check valid cache first
    if cache_json.exists():
        try:
            cached_data = json.loads(cache_json.read_text(encoding="utf-8"))
            cached_text = cached_data.get("full_text", "")
            if len(cached_text.strip()) > 0:
                raw_text = cached_text
                pages_count = cached_data.get("pages", 16)
        except Exception:
            pass

    # 2. Call LlamaParse if not cached
    if not raw_text:
        max_retries = 8
        for attempt in range(max_retries):
            try:
                parser = get_active_parser(result_type="markdown", tier="cost_effective")
                docs = parser.load_data(str(pdf_path))
                if not docs:
                    raise RuntimeError("LlamaParse returned 0 docs (upload timed out or dropped)")
                parsed_text = "\n\n---\n\n".join(d.text for d in docs)
                if not parsed_text.strip():
                    raise RuntimeError("LlamaParse returned empty text")
                pages_count = len(docs)
                raw_text = parsed_text
                # Save cache immediately
                cache_json.write_text(json.dumps({
                    "stem": stem,
                    "pages": pages_count,
                    "full_text": raw_text
                }, indent=2), encoding="utf-8")
                break
            except Exception as e:
                err_str = str(e).lower()
                if any(k in err_str for k in ["429", "402", "quota", "credit", "empty", "0 docs", "exhausted", "timed out", "dropped"]):
                    logger.warning(f"Rotating key due to quota error on {stem}: {e}")
                    manager.mark_key_exhausted(reason=err_str)
                else:
                    wait_time = (attempt + 1) * 4
                    logger.warning(f"Attempt {attempt+1}/{max_retries} failed for {stem}: {e}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                if attempt == max_retries - 1:
                    raise e

    if not raw_text:
        raise RuntimeError(f"Failed to extract text for {stem}")

    # 3. Publication-grade Normalization
    clean_text = normalize_seabrokers_content(raw_text)

    # 4. Parse structured tables
    tables = parse_markdown_tables(clean_text)

    word_count = len(clean_text.split())

    # 5. Format Frontmatter
    frontmatter = f"""---
title: "{report_title}"
issue_date: "{iso_date}"
year: {year}
month: {month}
publisher: "Seabrokers Chartering"
source: "seabrokers"
category: "Offshore"
pages: {pages_count}
source_file: "corpus/05-seabrokers/pdfs/{pdf_path.name}"
tables_count: {len(tables)}
word_count: {word_count}
tags:
  - Offshore
  - OSV
  - PSV
  - AHTS
  - Subsea
  - Rigs
  - Renewables
---

"""
    full_markdown = f"{frontmatter}{clean_text}\n"
    target_md_path.write_text(full_markdown, encoding="utf-8")

    # 6. Save structured table sidecar
    table_sidecar = {
        "title": report_title,
        "issue_date": iso_date,
        "year": year,
        "month": month,
        "source_file": f"corpus/05-seabrokers/pdfs/{pdf_path.name}",
        "tables_count": len(tables),
        "tables": tables
    }
    target_tables_path.write_text(json.dumps(table_sidecar, indent=2), encoding="utf-8")

    return {
        "stem": stem,
        "issue_date": iso_date,
        "year": year,
        "month": month,
        "title": report_title,
        "pages": pages_count,
        "tables_count": len(tables),
        "word_count": word_count,
        "source_file": f"corpus/05-seabrokers/pdfs/{pdf_path.name}",
        "extracted_file": f"data/extracted/md/seabrokers/{year}/{stem}.md",
        "tables_file": f"data/extracted/md/seabrokers/{year}/{stem}.tables.json"
    }


def update_offshore_summary_json():
    """Enriches data/derived/offshore_summary.json with md_url and tables_count

    Preserves 100% of all existing keys to guarantee zero frontend breaks and
    100% pass on tests/test_offshore_and_port_stress.py.
    """
    summary_path = REPO_ROOT / "data" / "derived" / "offshore_summary.json"
    if not summary_path.exists():
        return
    try:
        data = json.loads(summary_path.read_text(encoding="utf-8"))
        reports = data.get("reports", [])
        for rep in reports:
            slug = rep.get("slug")
            date_str = rep.get("date")
            yr = rep.get("year")
            # Match to extracted md file
            md_cand = list((MD_BASE_DIR / str(yr)).glob(f"{date_str}_*.md"))
            if md_cand:
                rep["md_path"] = f"data/extracted/md/seabrokers/{yr}/{md_cand[0].name}"
                tables_cand = list((MD_BASE_DIR / str(yr)).glob(f"{date_str}_*.tables.json"))
                if tables_cand:
                    rep["tables_path"] = f"data/extracted/md/seabrokers/{yr}/{tables_cand[0].name}"
        summary_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        logger.info(f"[+] Enriched {summary_path} with md_path and tables_path references.")
    except Exception as e:
        logger.error(f"Failed to enrich offshore_summary.json: {e}")


def run_pipeline():
    logger.info("=== STARTING SEABROKERS FULL LLAMAPARSE EXTRACTION PIPELINE ===")

    pdf_files = sorted(list(PDF_DIR.glob("*.pdf")))
    logger.info(f"Found {len(pdf_files)} Seabrokers PDFs to process.")

    state = load_run_state()
    done = state.get("done", {})
    failed = state.get("failed", {})

    # Re-normalize all already cached reports immediately
    results = []
    pending_pdfs = []

    junk = state.get("junk", {})

    for p in pdf_files:
        # Route junk explicitly: LlamaParse rejects non-PDF bytes with HTTP 415
        # ("File content does not match its '.pdf' extension"), which the retry
        # loop would otherwise burn 8 attempts on.
        try:
            magic = p.open("rb").read(5)
        except Exception as e:
            magic = b""
        if not magic.startswith(b"%PDF-"):
            junk[p.stem] = f"JUNK: not a PDF (magic={magic[:5]!r})"
            logger.warning(f"[junk] {p.name} is not a PDF (magic={magic[:5]!r}) - excluded")
            continue
        cache_f = CACHE_DIR / f"{p.stem}.json"
        if cache_f.exists():
            try:
                cd = json.loads(cache_f.read_text(encoding="utf-8"))
                if len(cd.get("full_text", "").strip()) > 0:
                    res = process_single_report(p)
                    done[p.stem] = res
                    results.append(res)
                    continue
            except Exception:
                pass
        pending_pdfs.append(p)

    state["done"] = done
    state["failed"] = failed
    state["junk"] = junk
    save_run_state(state)

    logger.info(f"Loaded and re-normalized {len(results)} cached reports. Pending fresh LlamaParse: {len(pending_pdfs)}")

    # Process pending files with max_workers=2 to prevent network timeouts/drops
    if pending_pdfs:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {executor.submit(process_single_report, p): p for p in pending_pdfs}
            for fut in as_completed(futures):
                p = futures[fut]
                try:
                    res = fut.result()
                    done[p.stem] = res
                    results.append(res)
                    logger.info(f"[+] Completed {p.name}: {res['pages']} pages, {res['tables_count']} tables, {res['word_count']} words")
                except Exception as e:
                    logger.error(f"[!] Failed {p.name}: {e}")
                    failed[p.stem] = str(e)
                state["done"] = done
                state["failed"] = failed
                save_run_state(state)

    logger.info(f"Successfully processed {len(results)} of {len(pdf_files)} Seabreeze reports.")

    # Save master metadata catalog
    results.sort(key=lambda x: (x["issue_date"], x["stem"]))
    df_cat = pd.DataFrame(results)
    csv_cat = SERIES_DIR / "seabrokers_catalog_metadata.csv"
    df_cat.to_csv(csv_cat, index=False)
    logger.info(f"[+] Saved master Seabrokers catalog metadata: {csv_cat} ({len(df_cat)} rows)")

    # Enrich offshore_summary.json without breaking any existing contracts
    update_offshore_summary_json()

    logger.info("=== SEABROKERS LLAMAPARSE PIPELINE COMPLETE ===")


if __name__ == "__main__":
    run_pipeline()
