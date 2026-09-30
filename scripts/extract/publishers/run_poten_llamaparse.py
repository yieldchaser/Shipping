"""run_poten_llamaparse.py

LlamaParse pipeline for Poten & Partners reports with chart tick spam / unformatted charts.
Converts vector chart ticks into clean structured Markdown tables and preserves 100% of prose.
Synchronizes to:
  - data/extracted/md/poten/<year>/ (.md and .tables.json)
  - corpus/04-poten/<year>/ (.md)
Updates master series:
  - data/extracted/series/poten_top_charterers_series.csv
  - data/extracted/series/poten_fixtures_series.csv
  - data/extracted/series/poten_opinions_metadata.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import re
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True, encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(line_buffering=True, encoding="utf-8")

from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import pymupdf

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "extract"))
sys.path.insert(0, str(ROOT))

import llama_manager
from llama_manager import manager, execute_with_auto_rotate

SRC_DIR = ROOT / "corpus" / "04-poten" / "pdfs"
CORPUS_DIR = ROOT / "corpus" / "04-poten"
OUT_MD_DIR = ROOT / "data" / "extracted" / "md" / "poten"
OUT_LLAMA_DIR = ROOT / "data" / "extracted" / "llamaparse_poten"
OUT_SERIES_DIR = ROOT / "data" / "extracted" / "series"
STATE_FILE = OUT_LLAMA_DIR / "_run_state.json"

CHARTERERS_CSV = OUT_SERIES_DIR / "poten_top_charterers_series.csv"
FIXTURES_CSV = OUT_SERIES_DIR / "poten_fixtures_series.csv"
METADATA_CSV = OUT_SERIES_DIR / "poten_opinions_metadata.csv"

KNOWN_VESSEL_SIZES = {
    'handymax', 'small', 'panamax', 'aframax', 'suezmax', 'vlcc', 'u/vlcc',
    'ulcc', 'mr', 'lr1', 'lr2', 'other', 'capesize', 'supramax', 'handysize'
}

TICK_DATE_PAT = re.compile(r'^(?:#+\s*)?(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[-‐\'\s]?\d{2,4}$', re.M | re.I)
TICK_DOLLAR_PAT = re.compile(r'^(?:#+\s*)?[-‐]?\$\d+', re.M)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def load_state() -> Dict[str, Any]:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"done": {}, "failed": {}, "pages_parsed": 0, "total_tables": 0}


def save_state(state: Dict[str, Any]):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


DATE_HEADER_PAT = re.compile(
    r"^(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}$",
    re.I
)


def polish_poten_markdown(raw_md: str, title: str, issue_date_str: str) -> str:
    """Strips repeating headers, footers, and boilerplate, preserving 100% of prose and tables."""
    text = raw_md.replace("\r\n", "\n").replace("\r", "\n")

    # 1. Strip repeating headers, running headers, and running footers line-by-line
    line_patterns = [
        r"(?im)^#+\s*Weekly\s+Tanker\s+Opinion\s*$",
        r"(?im)^POTEN\s*&\s*PARTNERS\s*$",
        r"(?im)^#+\s*POTEN\s*&\s*PARTNERS\s*$",
        r"(?im)^<?Poten\s*&\s*Partners\s*\|.*$",
        r"(?im)^www\.poten\.com(?:\s+[A-Za-z]+\s+\d{1,2},?\s+\d{4})?\s*$",
        r"(?im)^Poten\s+Tanker\s+Opinion\s*$",
        r"(?im)^WEEKLY\s+TANKER\s+OPINION\s*$",
        r"(?im)^Email:\s*tankerresearch@poten\.com.*$",
        r"(?im)^NEW YORK\s+LONDON\s+PERTH\s+ATHENS\s+HOUSTON\s+SINGAPORE.*$",
        r"(?im)^----+[ \t]*$",
        r"(?im)^\d+\s*$",
    ]
    for pat in line_patterns:
        text = re.sub(pat, "", text)

    # 2. Strip closing disclaimer block at the very end of the file
    text = re.sub(r"(?is)\*?Poten Tanker Market Opinions are published by the Marine Projects & Consulting department.*$", "", text)
    text = re.sub(r"(?is)Disclaimer:\s*Poten & Partners, Inc\. makes no representation or warranty.*$", "", text)

    # 3. Clean leading duplicate title/date lines (STRICT length check: only short headers)
    text = text.strip()
    title_clean = re.sub(r"[^\w\s]", "", title).strip().lower()

    while text:
        first_line = text.split("\n", 1)[0].strip("#* \t")
        if not first_line:
            text = text.split("\n", 1)[1].strip() if "\n" in text else ""
            continue
        first_clean = re.sub(r"[^\w\s]", "", first_line).strip().lower()
        is_exact_title = (first_clean == title_clean or first_clean == f"weekly tanker opinion {title_clean}" or first_clean == "weekly tanker opinion")
        is_date_header = (len(first_line) < 40 and bool(DATE_HEADER_PAT.match(first_line)))

        if is_exact_title or is_date_header:
            text = text.split("\n", 1)[1].strip() if "\n" in text else ""
        else:
            break

    # 4. Normalize paragraph newlines
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    # 5. Prepend standard title block
    header = f"# Weekly Tanker Opinion: {title}\n**{issue_date_str}**\n\n"
    return header + text + "\n"


def parse_markdown_tables(md_text: str) -> List[Dict[str, Any]]:
    """Extracts all markdown and HTML tables from markdown text."""
    tables = []

    # 1. Standard markdown pipe tables
    lines = md_text.splitlines()
    in_table = False
    table_lines = []
    current_heading = "Table"

    for line in lines:
        if line.startswith("#"):
            current_heading = line.lstrip("#").strip()

        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            if not in_table:
                in_table = True
                table_lines = [stripped]
            else:
                table_lines.append(stripped)
        else:
            if in_table:
                in_table = False
                if len(table_lines) >= 3:
                    hdr = [c.strip() for c in table_lines[0].strip("|").split("|")]
                    data_rows = []
                    for row_str in table_lines[2:]:
                        cells = [c.strip() for c in row_str.strip("|").split("|")]
                        if any(cells):
                            data_rows.append(cells)
                    if data_rows:
                        tables.append({
                            "heading": current_heading,
                            "headers": hdr,
                            "rows": data_rows
                        })
                table_lines = []

    if in_table and len(table_lines) >= 3:
        hdr = [c.strip() for c in table_lines[0].strip("|").split("|")]
        data_rows = []
        for row_str in table_lines[2:]:
            cells = [c.strip() for c in row_str.strip("|").split("|")]
            if any(cells):
                data_rows.append(cells)
        if data_rows:
            tables.append({
                "heading": current_heading,
                "headers": hdr,
                "rows": data_rows
            })

    # 2. HTML <table> blocks
    html_tables = re.findall(r"<table>(.*?)</table>", md_text, re.DOTALL | re.I)
    for ht in html_tables:
        rows = re.findall(r"<tr>(.*?)</tr>", ht, re.DOTALL | re.I)
        if not rows:
            continue
        hdr = []
        th_cells = re.findall(r"<th>(.*?)</th>", rows[0], re.DOTALL | re.I)
        if th_cells:
            hdr = [re.sub(r"<[^>]+>", "", c).strip() for c in th_cells]
        data_rows = []
        for r in rows[1:] if th_cells else rows:
            td_cells = re.findall(r"<t[dh]>(.*?)</t[dh]>", r, re.DOTALL | re.I)
            if td_cells:
                clean_cells = [re.sub(r"<[^>]+>", "", c).strip() for c in td_cells]
                if any(clean_cells):
                    data_rows.append(clean_cells)
        if data_rows:
            tables.append({
                "heading": current_heading,
                "headers": hdr if hdr else [f"col_{i+1}" for i in range(len(data_rows[0]))],
                "rows": data_rows
            })

    return tables


def extract_top_charterers_from_tables(
    tables: List[Dict[str, Any]],
    issue_date: str,
    year: int,
    source_file: str,
    doc_title: str
) -> List[Dict[str, Any]]:
    """Detects and standardizes Top Charterers rows from parsed tables."""
    out_rows = []
    is_clean = "clean" in doc_title.lower()
    cargo_type = "Clean" if is_clean else "Dirty"
    is_midterm = any(k in doc_title.lower() for k in ["midterm", "halftime", "mid-year"])
    default_period = f"{year} H1" if is_midterm else str(year - 1)

    for tbl in tables:
        heading = tbl.get("heading", "")
        headers = [h.lower() for h in tbl.get("headers", [])]
        rows = tbl.get("rows", [])

        seg = "Overall"
        for candidate_seg in ["VLCC", "Suezmax", "Aframax", "Panamax", "Handymax", "Small"]:
            if candidate_seg.lower() in heading.lower():
                seg = candidate_seg
                break

        has_charterer = any("charterer" in h or "company" in h for h in headers)
        has_rank = any("rank" in h for h in headers)
        has_fixtures = any("fixture" in h or "count" in h or "#" in h for h in headers)

        if has_charterer and (has_rank or has_fixtures or len(rows) >= 5):
            ch_idx = next((i for i, h in enumerate(headers) if "charterer" in h or "company" in h), 1 if len(headers) > 1 else 0)
            rk_idx = next((i for i, h in enumerate(headers) if "rank" in h), None)
            fix_idx = next((i for i, h in enumerate(headers) if "fixture" in h or "count" in h or "#" in h), None)
            pct_idx = next((i for i, h in enumerate(headers) if "%" in h and "cum" not in h), None)
            prk_idx = next((i for i, h in enumerate(headers) if "prev" in h or "200" in h), None)

            current_rank = 1
            for r in rows:
                if len(r) <= ch_idx:
                    continue
                charterer_name = re.sub(r"[\*\#]", "", r[ch_idx]).strip()
                if not charterer_name or charterer_name.lower() in ["total", "others", "sum", "average", "top 20", "top 10"]:
                    continue

                rank_val = r[rk_idx].strip() if rk_idx is not None and len(r) > rk_idx else str(current_rank)
                m_rk = re.search(r"^\d+", rank_val)
                rk = int(m_rk.group(0)) if m_rk else current_rank

                fixtures_val = r[fix_idx].strip() if fix_idx is not None and len(r) > fix_idx else ""
                fixtures_clean = re.sub(r"[^\d]", "", fixtures_val)

                pct_val = r[pct_idx].strip() if pct_idx is not None and len(r) > pct_idx else ""
                prev_rk_val = r[prk_idx].strip() if prk_idx is not None and len(r) > prk_idx else ""

                out_rows.append({
                    "issue_date": issue_date,
                    "year": year,
                    "report_period": default_period,
                    "cargo_type": cargo_type,
                    "segment": seg,
                    "rank": rk,
                    "charterer": charterer_name,
                    "cargo_mt_000s": "",
                    "pct_total_cargo": "",
                    "fixtures_count": fixtures_clean,
                    "pct_fixtures": pct_val,
                    "prev_rank": prev_rk_val,
                    "source_file": source_file
                })
                current_rank += 1

    return out_rows


def extract_fixtures_by_size(
    tables: List[Dict[str, Any]],
    issue_date: str,
    year: int,
    source_file: str,
    doc_title: str
) -> List[Dict[str, Any]]:
    """Detects fixtures by vessel size breakdown tables."""
    out_rows = []
    is_clean = "clean" in doc_title.lower()
    cargo_type = "Clean" if is_clean else "Dirty"

    for tbl in tables:
        heading = tbl.get("heading", "")
        headers = [h.lower() for h in tbl.get("headers", [])]
        rows = tbl.get("rows", [])

        has_size = any("vessel" in h or "size" in h for h in headers)
        if has_size or any(v in str(rows).lower() for v in ["handymax", "panamax", "aframax", "suezmax", "vlcc"]):
            m_period = re.search(r"(20\d{2})", heading + " " + " ".join(headers))
            period = m_period.group(1) if m_period else str(year - 1)

            for r in rows:
                if len(r) < 2:
                    continue
                v_name = re.sub(r"[\*\#]", "", r[0]).strip()
                v_fix = re.sub(r"[^\d]", "", r[1]).strip()
                if v_name.lower() in KNOWN_VESSEL_SIZES and v_fix.isdigit():
                    out_rows.append({
                        "issue_date": issue_date,
                        "year": year,
                        "report_period": period,
                        "cargo_type": cargo_type,
                        "vessel_size": v_name.capitalize(),
                        "fixtures_count": int(v_fix),
                        "source_file": source_file
                    })

    return out_rows


def sync_to_extracted_md(
    year: int,
    issue_date: str,
    doc_title: str,
    source_ref: str,
    num_pages: int,
    polished_md: str,
    parsed_tables: List[Dict[str, Any]],
    ch_rows: List[Dict[str, Any]],
    fix_rows: List[Dict[str, Any]]
):
    """Synchronizes markdown and tables.json to data/extracted/md/poten/ and corpus/04-poten/."""
    year_dir = OUT_MD_DIR / str(year)
    year_dir.mkdir(parents=True, exist_ok=True)

    matches = list(year_dir.glob(f"poten_{issue_date}_*.md"))
    if matches:
        target_md = matches[0]
        target_json = matches[0].with_suffix(".tables.json")
    else:
        slug = re.sub(r"[^\w\s-]", "", doc_title.lower())
        slug = re.sub(r"[\s_-]+", "-", slug).strip("-")[:50] or "opinion"
        target_md = year_dir / f"poten_{issue_date}_{slug}.md"
        target_json = year_dir / f"poten_{issue_date}_{slug}.tables.json"

    # Prepend YAML frontmatter
    yaml_header = (
        "---\n"
        f"title: \"{doc_title}\"\n"
        "subtitle: \"Weekly Tanker Opinion\"\n"
        f"issue_date: \"{issue_date}\"\n"
        f"year: {year}\n"
        "author: \"Poten & Partners\"\n"
        "source: \"poten\"\n"
        "category: \"tankers\"\n"
        f"pages: {num_pages}\n"
        f"source_file: \"{source_ref}\"\n"
        f"tables_count: {len(parsed_tables)}\n"
        "parser: \"LlamaParse cost_effective\"\n"
        "---\n\n"
    )
    full_content = yaml_header + polished_md
    target_md.write_text(full_content, encoding="utf-8")

    sidecar = {
        "issue_date": issue_date,
        "year": year,
        "title": doc_title,
        "source_file": source_ref,
        "pages": num_pages,
        "tables_count": len(parsed_tables),
        "top_charterers_rows": len(ch_rows),
        "fixtures_rows": len(fix_rows),
        "parser": "LlamaParse cost_effective",
        "tables": parsed_tables
    }
    target_json.write_text(json.dumps(sidecar, indent=2, ensure_ascii=False), encoding="utf-8")

    # Also synchronize to corpus/04-poten/<year>/
    corpus_year_dir = CORPUS_DIR / str(year)
    corpus_year_dir.mkdir(parents=True, exist_ok=True)
    corpus_target_md = corpus_year_dir / target_md.name

    # Remove any old stubs for this PDF
    pdf_name = Path(source_ref).name
    for old_f in corpus_year_dir.glob("*.md"):
        if old_f != corpus_target_md:
            try:
                txt = old_f.read_text(encoding="utf-8", errors="ignore")
                if pdf_name in txt and ("unknown-01-01" in old_f.name or len(txt) < 1500):
                    old_f.unlink()
            except Exception:
                pass

    corpus_target_md.write_text(full_content, encoding="utf-8")


def parse_pdf_llamaparse(pdf_path: Path) -> str:
    """Calls LlamaParse with automatic key failover across the key pool."""
    def _call(api_key: str) -> str:
        from llama_parse import LlamaParse
        parser = LlamaParse(
            api_key=api_key,
            tier="cost_effective",
            version="latest",
            result_type="markdown",
            verbose=False
        )
        docs = parser.load_data(str(pdf_path))
        text = "\n\n".join(d.text for d in docs)
        if not text or len(text.strip()) < 150:
            raise RuntimeError(f"Empty or truncated output ({len(text)} chars)")
        return text

    return execute_with_auto_rotate(_call)


def get_broken_targets() -> List[Tuple[Path, Path, int, int, str, str]]:
    """Identifies files in data/extracted/md/poten/ containing chart tick spam."""
    targets = []
    md_files = sorted(OUT_MD_DIR.glob("*/*.md"))

    for p in md_files:
        txt = p.read_text(encoding="utf-8")
        if 'parser: "LlamaParse"' in txt:
            continue

        t_matches = TICK_DATE_PAT.findall(txt)
        d_matches = TICK_DOLLAR_PAT.findall(txt)

        if len(t_matches) >= 3 or len(d_matches) >= 3:
            m_src = re.search(r'source_file:\s*"([^"]+)"', txt)
            if not m_src:
                continue
            pdf_rel = m_src.group(1)
            pdf_path = ROOT / pdf_rel
            if not pdf_path.exists():
                continue

            # Extract year, issue_date, doc_title from existing frontmatter
            m_date = re.search(r'issue_date:\s*"([^"]+)"', txt)
            issue_date = m_date.group(1) if m_date else "2011-01-01"

            m_title = re.search(r'title:\s*"([^"]+)"', txt)
            doc_title = m_title.group(1) if m_title else pdf_path.stem

            y_str = p.parent.name
            year = int(y_str) if y_str.isdigit() else 2011

            try:
                doc = pymupdf.open(pdf_path)
                pages = len(doc)
                doc.close()
            except Exception:
                pages = 1

            targets.append((p, pdf_path, year, pages, issue_date, doc_title))

    return targets


def run_pipeline(limit: int = 0, broken_only: bool = True, start_year: int = 2004, end_year: int = 2014):
    state = load_state()
    OUT_LLAMA_DIR.mkdir(parents=True, exist_ok=True)
    OUT_SERIES_DIR.mkdir(parents=True, exist_ok=True)

    if broken_only:
        targets = get_broken_targets()
        print(f"Discovered {len(targets)} Poten reports with chart tick spam needing LlamaParse.")
    else:
        all_pdfs = sorted(SRC_DIR.glob("*/*.pdf"))
        targets = []
        for p in all_pdfs:
            y_str = p.parent.name
            if not y_str.isdigit():
                continue
            y = int(y_str)
            if start_year <= y <= end_year:
                try:
                    doc = pymupdf.open(p)
                    pages = len(doc)
                    doc.close()
                    if pages > 1:
                        # Find corresponding md
                        m_date = re.search(r"(\d{4})(\d{2})(\d{2})", p.name)
                        i_date = f"{m_date.group(1)}-{m_date.group(2)}-{m_date.group(3)}" if m_date else f"{y}-01-01"
                        targets.append((Path("dummy"), p, y, pages, i_date, p.stem))
                except Exception:
                    pass
        print(f"Discovered {len(targets)} multi-page Poten PDFs across {start_year}-{end_year}.")

    # Filter out files that already have LlamaParse in data/extracted/md/poten/
    todo = []
    for item in targets:
        orig_md, pdf_path, year, num_pages, issue_date, doc_title = item
        if orig_md.exists():
            try:
                md_head = orig_md.read_text(encoding="utf-8", errors="ignore")[:400]
                if 'parser: "LlamaParse"' in md_head:
                    continue
            except Exception:
                pass
        todo.append(item)

    print(f"Remaining broken documents to parse/sync: {len(todo)}")

    if limit > 0:
        todo = todo[:limit]
        print(f"Limiting execution to first {len(todo)} documents.")

    if not todo:
        print("All target documents are already processed!")
        return

    # Load existing series
    existing_charterers = []
    if CHARTERERS_CSV.exists():
        with open(CHARTERERS_CSV, "r", encoding="utf-8") as f:
            existing_charterers = list(csv.DictReader(f))

    existing_fixtures = []
    if FIXTURES_CSV.exists():
        with open(FIXTURES_CSV, "r", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r.get("vessel_size", "").lower() in KNOWN_VESSEL_SIZES:
                    existing_fixtures.append(r)

    new_charterer_rows = []
    new_fixture_rows = []

    print(f"Starting LlamaParse batch on {len(todo)} reports with active account: {manager.get_current_account_info()['name']}")

    for idx, (orig_md, pdf_path, year, num_pages, issue_date, doc_title) in enumerate(todo, 1):
        fn = pdf_path.name
        rel_src = pdf_path.resolve().relative_to(ROOT).as_posix()
        t0 = time.time()
        print(f"\n[{idx}/{len(todo)}] Processing {fn} ({num_pages}pp, year {year}, date {issue_date})...")

        try:
            year_llama_dir = OUT_LLAMA_DIR / str(year)
            cached_raw = year_llama_dir / f"{pdf_path.stem}.raw.md"
            cached_md = year_llama_dir / f"{pdf_path.stem}.md"

            if cached_raw.exists() and len(cached_raw.read_text(encoding="utf-8")) > 150:
                print(f"  -> Using cached raw LlamaParse text from {cached_raw.name}")
                raw_md = cached_raw.read_text(encoding="utf-8")
            elif cached_md.exists() and len(cached_md.read_text(encoding="utf-8")) > 150:
                print(f"  -> Using cached LlamaParse text from {cached_md.name}")
                raw_md = cached_md.read_text(encoding="utf-8")
            else:
                raw_md = parse_pdf_llamaparse(pdf_path)
                manager.record_success(num_pages=num_pages)
                year_llama_dir.mkdir(parents=True, exist_ok=True)
                cached_raw.write_text(raw_md, encoding="utf-8")

            # Format issue date string e.g. "January 28, 2011"
            try:
                dt = datetime.strptime(issue_date, "%Y-%m-%d")
                issue_date_str = dt.strftime("%B %d, %Y")
            except Exception:
                issue_date_str = issue_date

            # Polish markdown
            polished_md = polish_poten_markdown(raw_md, doc_title, issue_date_str)
            parsed_tables = parse_markdown_tables(polished_md)

            ch_rows = extract_top_charterers_from_tables(parsed_tables, issue_date, year, rel_src, doc_title)
            fix_rows = extract_fixtures_by_size(parsed_tables, issue_date, year, rel_src, doc_title)

            new_charterer_rows.extend(ch_rows)
            new_fixture_rows.extend(fix_rows)

            # Save to extracted and corpus
            sync_to_extracted_md(
                year, issue_date, doc_title, rel_src, num_pages,
                polished_md, parsed_tables, ch_rows, fix_rows
            )

            elapsed = time.time() - t0
            state["done"][fn] = {
                "pages": num_pages,
                "tables": len(parsed_tables),
                "charterers": len(ch_rows),
                "fixtures": len(fix_rows),
                "secs": round(elapsed, 1),
                "date": issue_date,
                "title": doc_title
            }
            state["pages_parsed"] += num_pages
            state["total_tables"] += len(parsed_tables)

            print(f"  -> SUCCESS in {elapsed:.1f}s | {len(parsed_tables)} tables, {len(ch_rows)} charterers, {len(fix_rows)} fixtures")

        except Exception as e:
            err_msg = str(e)
            print(f"  -> ERROR on {fn}: {err_msg[:120]}")
            state["failed"][fn] = err_msg[:250]

        save_state(state)

    # Update series files
    if new_charterer_rows:
        ch_fieldnames = [
            "issue_date", "year", "report_period", "cargo_type", "segment", "rank",
            "charterer", "cargo_mt_000s", "pct_total_cargo", "fixtures_count",
            "pct_fixtures", "prev_rank", "source_file"
        ]
        for r in existing_charterers:
            r.setdefault("cargo_type", "Dirty")

        all_charterers = existing_charterers + new_charterer_rows
        with open(CHARTERERS_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=ch_fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(all_charterers)
        print(f"Updated {CHARTERERS_CSV}: total {len(all_charterers)} rows (+{len(new_charterer_rows)} new)")

    if new_fixture_rows or existing_fixtures:
        fix_fieldnames = [
            "issue_date", "year", "report_period", "cargo_type", "vessel_size",
            "fixtures_count", "source_file"
        ]
        all_fixtures = existing_fixtures + new_fixture_rows
        with open(FIXTURES_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fix_fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(all_fixtures)
        print(f"Updated {FIXTURES_CSV}: total {len(all_fixtures)} rows (+{len(new_fixture_rows)} new)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Poten LlamaParse Pipeline")
    parser.add_argument("--limit", type=int, default=0, help="Max documents to parse")
    parser.add_argument("--all", action="store_true", help="Process all multi-page archive PDFs instead of only broken ones")
    parser.add_argument("--start-year", type=int, default=2004, help="Start year")
    parser.add_argument("--end-year", type=int, default=2014, help="End year")
    args = parser.parse_args()

    run_pipeline(
        limit=args.limit,
        broken_only=not args.all,
        start_year=args.start_year,
        end_year=args.end_year
    )
