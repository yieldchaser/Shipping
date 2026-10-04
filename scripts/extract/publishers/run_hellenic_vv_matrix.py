"""Hellenic VesselsValue Weekly Matrix Image & Valuation Extraction Runner.

Extracts weekly vessel valuation reports published by VesselsValue in corpus/02-hellenic/vessel_valuations/:
- 272 weekly reports spanning 2021 to 2026
- Authoritative mini-matrix graphic (_img2.jpg / _img2.jpeg / _img2.png) converted to PDF and parsed via LlamaParse
- Structured parsing of the 13 vessel classes across 6 age profiles (0Y, 5Y, 10Y, 15Y, 20Y, 25Y):
  * Tankers: VLCC, Suezmax, Aframax, LR1, MR
  * Bulkers: Capesize, Panamax, Supramax, Handysize
  * Containers: Post Panamax, Panamax, Handy, Feedermax
- Extraction of benchmark secondhand sale transactions with both commercial sale price and proprietary VV Value
- Produces:
  data/extracted/md/hellenic/vessel_valuations/<year>/vv_<date>.md + .tables.json
  data/extracted/series/hellenic_vv_matrix_series.csv
  data/extracted/series/hellenic_vv_benchmark_sales_series.csv
"""

from __future__ import annotations

import asyncio
import csv
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pymupdf
from bs4 import BeautifulSoup
from llama_parse import LlamaParse

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from scripts.extract.llama_manager import manager as key_manager

INPUT_DIR = ROOT / "corpus" / "02-hellenic" / "vessel_valuations"
OUT_MD_DIR = ROOT / "data" / "extracted" / "md" / "hellenic" / "vessel_valuations"
OUT_SERIES_DIR = ROOT / "data" / "extracted" / "series"
CACHE_DIR = ROOT / "data" / "extracted" / "cache_hellenic_vv"
STATE_FILE = ROOT / "data" / "extracted" / "md" / "hellenic" / "_vv_run_state.json"


def clean_num(val_str: Any) -> Optional[float]:
    if val_str is None:
        return None
    cleaned = str(val_str).strip().replace(",", "").replace("$", "").replace("%", "").replace("*", "").replace("+", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def clean_text(s: str) -> str:
    if not s:
        return ""
    s = s.replace("\ufffd", "'")
    s = s.replace("\u2019", "'").replace("\u2018", "'")
    s = s.replace("\u201c", '"').replace("\u201d", '"')
    s = s.replace("`", "'")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def find_companion_image(h_path: Path) -> Optional[Path]:
    """Locate the canonical mini matrix image companion for an HTML report."""
    stem = h_path.stem
    parent = h_path.parent

    # Check _img2 in parent dir (most common for matrix graphic)
    for cand_name in [f"{stem}_img2.jpeg", f"{stem}_img2.jpg", f"{stem}_img2.png"]:
        p = parent / cand_name
        if p.exists() and p.stat().st_size > 15000:
            return p

    # Check assets directory
    assets_dir = parent / "assets"
    if assets_dir.exists():
        for cand in assets_dir.glob(f"{stem}*.*"):
            if cand.suffix.lower() in [".jpg", ".jpeg", ".png"] and cand.stat().st_size > 15000:
                # avoid small icons or logos
                if "img1" not in cand.name.lower() or cand.stat().st_size > 30000:
                    return cand

    # Check links/images referenced in HTML body
    try:
        content = h_path.read_text(encoding="utf-8", errors="ignore")
        soup = BeautifulSoup(content, "html.parser")
        for tag in soup.find_all("img"):
            src = tag.get("src")
            if src and any(src.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png"]):
                cand = parent / src
                if cand.exists() and cand.stat().st_size > 15000 and "img1" not in cand.name.lower():
                    return cand
    except Exception:
        pass

    return None


async def get_or_parse_image_async(img_path: Path, sem: asyncio.Semaphore) -> str:
    """Retrieve cached LlamaParse markdown or submit image via LlamaParse async with automatic failover."""
    stem = img_path.stem
    cache_file = CACHE_DIR / f"{stem}.md"
    if cache_file.exists() and cache_file.stat().st_size > 50:
        return cache_file.read_text(encoding="utf-8")

    async with sem:
        img_doc = pymupdf.open(img_path)
        pdf_bytes = img_doc.convert_to_pdf()
        img_doc.close()

        tmp_pdf = CACHE_DIR / f"tmp_{stem}_{os.getpid()}.pdf"
        tmp_pdf.write_bytes(pdf_bytes)

        try:
            for attempt in range(4):
                current_key = key_manager.get_current_key()
                parser = LlamaParse(
                    api_key=current_key,
                    result_type="markdown",
                    tier="cost_effective",
                    version="latest",
                    verbose=False
                )
                try:
                    docs = await parser.aload_data(str(tmp_pdf))
                    md_text = "\n\n".join(d.text for d in docs)
                    cache_file.write_text(md_text, encoding="utf-8")
                    key_manager.record_success(1)
                    return md_text
                except Exception as e:
                    err_msg = str(e).lower()
                    if "429" in err_msg or "quota" in err_msg or "payment required" in err_msg or "credit" in err_msg:
                        print(f"  [!] Key exhausted on {stem}, swapping key: {e}")
                        key_manager.mark_key_exhausted(str(e))
                        continue
                    if attempt == 3:
                        raise e
                    await asyncio.sleep(2 * (attempt + 1))
            return ""
        finally:
            if tmp_pdf.exists():
                tmp_pdf.unlink()


def parse_vv_matrix_markdown(md_text: str, issue_date: str, source_file: str) -> List[Dict[str, Any]]:
    """Parse LlamaParse markdown tables for VesselsValue weekly change matrix, handling multi-table sections."""
    records: List[Dict[str, Any]] = []
    lines = md_text.splitlines()
    i = 0
    current_section = "Unknown"

    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#"):
            sec_candidate = line.lstrip("#").strip()
            for s in ["Tankers", "Bulkers", "Containers", "Gas"]:
                if s.lower() in sec_candidate.lower():
                    current_section = s
                    break
            i += 1
            continue

        if line.startswith("|") and i + 1 < len(lines) and "---" in lines[i + 1]:
            header_line = line
            sep_line = lines[i + 1]
            table_lines = [header_line, sep_line]
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i].strip())
                i += 1

            h_parts = [h.strip() for h in table_lines[0].strip("|").split("|")]
            col_meta = []

            for h in h_parts[1:]:
                h_clean = h.replace("<br/>", " ").replace("<br>", " ").strip()
                vclass = h_clean
                sec = current_section
                if sec == "Unknown":
                    if any(k in vclass.lower() for k in ["vlcc", "suez", "afra", "lr1", "lr2", "mr"]):
                        sec = "Tankers"
                    elif any(k in vclass.lower() for k in ["cape", "pmax", "panamax", "supra", "supramax", "handy"]):
                        sec = "Bulkers"
                    elif any(k in vclass.lower() for k in ["container", "post pmax", "fmax", "feeder"]):
                        sec = "Containers"
                col_meta.append((sec, vclass))

            current_age = None
            pct_row_vals = None

            for t_line in table_lines[2:]:
                parts = [p.strip() for p in t_line.strip("|").split("|")]
                if len(parts) < 2:
                    continue
                age_label = parts[0].strip().replace("*", "")
                row_vals = parts[1:]

                is_pct = any("%" in v for v in row_vals) or any(re.search(r"^[+-]?\d+\.\d+%", v) for v in row_vals)

                if is_pct:
                    if age_label:
                        current_age = age_label
                    pct_row_vals = row_vals
                elif current_age is not None and pct_row_vals is not None:
                    size_row_vals = row_vals
                    for idx, (sec, vclass) in enumerate(col_meta):
                        pct_str = pct_row_vals[idx] if idx < len(pct_row_vals) else ""
                        size_str = size_row_vals[idx] if idx < len(size_row_vals) else ""

                        pct_val = clean_num(pct_str)
                        if pct_val is not None:
                            records.append({
                                "issue_date": issue_date,
                                "sector": sec,
                                "vessel_class": vclass,
                                "benchmark_size": size_str.replace("*", "").strip(),
                                "age_years": current_age,
                                "pct_change_weekly": pct_val,
                                "source_file": source_file,
                            })
                    current_age = None
                    pct_row_vals = None
        else:
            i += 1

    return records


def parse_vv_commentary_and_sales(soup: BeautifulSoup, issue_date: str, source_file: str) -> Tuple[str, List[Dict[str, Any]]]:
    """Extract editorial commentary and reported benchmark sales with VV values."""
    paras = []
    sales = []

    for p in soup.find_all("p"):
        txt = clean_text(p.get_text(" ", strip=True))
        if not txt or txt.startswith("Linked asset:") or txt.startswith("http"):
            continue
        paras.append(txt)

        # Detect sales transactions: e.g. "sold by ... for USD ... VV Value USD ..."
        if "sold by" in txt.lower() and "vv value" in txt.lower():
            # Regex match
            m = re.search(
                r"^([A-Za-z0-9\s\(\)/]+?)\s+([A-Za-z0-9\s\-]+?)\s*\((.*?)\)\s+sold by\s+(.*?)\s+for\s+USD\s+([0-9\.]+)\s*mil.*?(?:VV Value|VV value)\s+USD\s+([0-9\.]+)\s*mil",
                txt, re.IGNORECASE
            )
            if m:
                sales.append({
                    "issue_date": issue_date,
                    "vessel_class": m.group(1).strip(),
                    "vessel_name": m.group(2).strip(),
                    "vessel_specs": m.group(3).strip(),
                    "seller": m.group(4).strip(),
                    "sale_price_usd_m": clean_num(m.group(5)),
                    "vv_value_usd_m": clean_num(m.group(6)),
                    "raw_transaction": txt,
                    "source_file": source_file,
                })
            else:
                # Broader fallback match
                m_price = re.search(r"for USD\s+([0-9\.]+)\s*mil", txt, re.IGNORECASE)
                m_vv = re.search(r"VV Value\s+USD\s+([0-9\.]+)\s*mil", txt, re.IGNORECASE)
                if m_price and m_vv:
                    sales.append({
                        "issue_date": issue_date,
                        "vessel_class": "Unknown",
                        "vessel_name": txt[:40],
                        "vessel_specs": "",
                        "seller": "",
                        "sale_price_usd_m": clean_num(m_price.group(1)),
                        "vv_value_usd_m": clean_num(m_vv.group(1)),
                        "raw_transaction": txt,
                        "source_file": source_file,
                    })

    commentary = "\n\n".join(paras)
    return commentary, sales


async def process_vv_item_async(h_path: Path, sem: asyncio.Semaphore) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]]]:
    fname = h_path.name
    m_date = re.match(r"^(\d{4}-\d{2}-\d{2})", fname)
    filename_date = m_date.group(1) if m_date else ""

    content = h_path.read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(content, "html.parser")
    # The page's own report date wins; the filename prefix is the crawl date.
    issue_date = _title_iso_date(page_title(h_path)) or filename_date or "UNKNOWN"
    year = issue_date[:4]
    title = soup.title.string.strip() if soup.title and soup.title.string else f"Weekly Vessel Valuations Report - {issue_date}"

    commentary, sales = parse_vv_commentary_and_sales(soup, issue_date, fname)

    img_cand = find_companion_image(h_path)
    matrix_records: List[Dict[str, Any]] = []

    if img_cand:
        try:
            table_md = await get_or_parse_image_async(img_cand, sem)
            matrix_records = parse_vv_matrix_markdown(table_md, issue_date, fname)
        except Exception as e:
            print(f"  [!] Failed parsing image for {fname}: {e}")

    stem = f"vv_{issue_date}"
    year_dir = OUT_MD_DIR / year
    year_dir.mkdir(parents=True, exist_ok=True)

    # Build clean markdown
    md_lines = [
        f"# {title}",
        "",
        f"- **Issue Date**: {issue_date}",
        f"- **Publisher**: VesselsValue",
        f"- **Source**: `corpus/02-hellenic/vessel_valuations/{year}/{fname}`",
        "",
        "## Market Commentary & S&P Activity",
        "",
        commentary if commentary else "*No editorial commentary.*",
        "",
    ]

    if matrix_records:
        md_lines.extend([
            "## Weekly Value Change Matrix (%)",
            "",
            "| Sector | Vessel Class | Benchmark Size | Age (Years) | Weekly Change (%) |",
            "|---|---|---|---|---|",
        ])
        for r in matrix_records:
            chg_sign = f"+{r['pct_change_weekly']:.1f}%" if r['pct_change_weekly'] > 0 else f"{r['pct_change_weekly']:.1f}%"
            md_lines.append(f"| {r['sector']} | {r['vessel_class']} | {r['benchmark_size']} | {r['age_years']} | {chg_sign} |")
        md_lines.append("")

    if sales:
        md_lines.extend([
            "## Benchmark Reported Sales vs VV Value",
            "",
            "| Class | Vessel Name | Specifications | Seller | Sale Price ($M) | VV Value ($M) | Difference ($M) |",
            "|---|---|---|---|---|---|---|",
        ])
        for s in sales:
            diff = (s['sale_price_usd_m'] - s['vv_value_usd_m']) if (s['sale_price_usd_m'] is not None and s['vv_value_usd_m'] is not None) else None
            diff_str = f"${diff:+.2f}M" if diff is not None else "-"
            md_lines.append(f"| {s['vessel_class']} | {s['vessel_name']} | {s['vessel_specs']} | {s['seller']} | ${s['sale_price_usd_m']}M | ${s['vv_value_usd_m']}M | {diff_str} |")
        md_lines.append("")

    md_lines.extend([
        "## Disclaimer",
        "",
        "> *Valuations and data provided by VesselsValue. For informational purposes only.*",
        ""
    ])

    md_path = year_dir / f"{stem}.md"
    with open(md_path, "w", encoding="utf-8") as mf:
        mf.write("\n".join(md_lines))

    # JSON sidecar
    json_path = year_dir / f"{stem}.tables.json"
    with open(json_path, "w", encoding="utf-8") as jf:
        json.dump({
            "issue_date": issue_date,
            "year": year,
            "title": title,
            "source_file": fname,
            "matrix_observations_count": len(matrix_records),
            "benchmark_sales_count": len(sales),
            "matrix_records": matrix_records,
            "benchmark_sales": sales,
        }, jf, indent=2, ensure_ascii=False)

    summary = {
        "issue_date": issue_date,
        "year": year,
        "filename": fname,
        "matrix_count": len(matrix_records),
        "sales_count": len(sales),
    }

    return summary, matrix_records, sales



_MONTH_NAMES = ("january", "february", "march", "april", "may", "june", "july",
                "august", "september", "october", "november", "december")


def page_title(h_path: Path) -> str:
    """The report page's own <title>, or "" - an identity the filename lacks."""
    try:
        text = h_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""
    m = re.search(r"<title>([^<]*)", text)
    return m.group(1).strip() if m else ""


def _title_date_token(title: str) -> str:
    """'Weekly Vessel Valuations Report, February 17 2026' -> 'february-17-2026'."""
    m = re.search(r"Report,?\s*([A-Za-z]+)\s+(\d{1,2})\s+(\d{4})", title or "")
    if not m:
        return ""
    month = m.group(1).lower()
    if month not in _MONTH_NAMES:
        return ""
    return "%s-%02d-%s" % (month, int(m.group(2)), m.group(3))


def _title_iso_date(title: str) -> str:
    """'Weekly Vessel Valuations Report, September 15 2026' -> '2026-09-15'.

    The page's OWN report date. The filename prefix is the next-day CRAWL date
    (measured: 78 of 261 pages differ, -1d x69, -2d x8, +10d x1), so the page
    title is authoritative and the filename is only the fallback.
    """
    token = _title_date_token(title)
    m = re.match(r"([a-z]+)-(\d{2})-(\d{4})$", token)
    if not m or m.group(1) not in _MONTH_NAMES:
        return ""
    return "%s-%02d-%02d" % (m.group(3), _MONTH_NAMES.index(m.group(1)) + 1, int(m.group(2)))


def dedupe_report_copies(html_files: List[Path]) -> List[Path]:
    """One file per report page, keyed on the publisher's own title.

    The collector stores the SAME report several times under different names.
    Measured 2026-10-03: of 261 VV report pages, 6 are such copies - three
    copies of the February 17 2026 report (all saved 2026-02-19) and five of
    the March 31 2026 report (all saved 2026-04-01). No two of a group are
    byte-identical (each fetch rewrites the asset paths), so a hash dedup
    misses them, and each copy was parsed independently - which put one
    report's table into the series 3x and 5x. Delivered
    `hellenic_vv_matrix_series.csv` holds 234 rows on issue_date 2026-02-19
    against 78 for the modal week (156 excess = 2 extra copies x 78), and
    `hellenic_vv_benchmark_sales_series.csv` holds 15 rows for that date
    where a single copy yields 5.

    Keeps, per title, the copy whose own filename names that report - so the
    file that OWNS the companion matrix image wins, and the fetch-date
    duplicates (which carry no image and would otherwise adopt another
    report's image through the <img src> fallback in find_companion_image)
    are dropped. The date CONVENTION is deliberately untouched: the kept copy
    keeps the issue_date the runner already derives from its filename.
    """
    best: Dict[str, Tuple[Path, bool]] = {}
    for hp in html_files:
        title = page_title(hp)
        key = title or hp.name
        token = _title_date_token(title)
        owns = bool(token) and token in hp.stem.lower().replace("_", "-")
        cur = best.get(key)
        if cur is None or (owns and not cur[1]):
            best[key] = (hp, owns)
    return sorted(hp for hp, _owns in best.values())


async def run_all_async(limit: Optional[int] = None) -> Dict[str, Any]:
    OUT_MD_DIR.mkdir(parents=True, exist_ok=True)
    OUT_SERIES_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    sem = asyncio.Semaphore(4)

    html_files = sorted(list(INPUT_DIR.glob("**/*weekly-vessel-valuations-report*.html")))
    n_input = len(html_files)
    html_files = dedupe_report_copies(html_files)
    if len(html_files) != n_input:
        print(f"[VV] dropped {n_input - len(html_files)} duplicate copies of the "
              f"same report page ({n_input} -> {len(html_files)})", flush=True)
    if limit:
        html_files = html_files[:limit]

    print(f"[VV] Starting extraction of {len(html_files)} weekly reports...", flush=True)

    tasks = [process_vv_item_async(hp, sem) for hp in html_files]
    results_raw = await asyncio.gather(*tasks, return_exceptions=True)

    all_matrix: List[Dict[str, Any]] = []
    all_sales: List[Dict[str, Any]] = []
    summaries: List[Dict[str, Any]] = []

    for item in results_raw:
        if isinstance(item, Exception):
            print(f"  [ERROR in VV batch item]: {item}", flush=True)
            continue
        summary, matrix_rows, sales_rows = item
        all_matrix.extend(matrix_rows)
        all_sales.extend(sales_rows)
        summaries.append(summary)

    print(f"[VV] Completed {len(summaries)} reports -> {len(all_matrix)} matrix observations, {len(all_sales)} benchmark sales.", flush=True)

    # Write master series
    matrix_csv = OUT_SERIES_DIR / "hellenic_vv_matrix_series.csv"
    matrix_cols = ["issue_date", "sector", "vessel_class", "benchmark_size", "age_years", "pct_change_weekly", "source_file"]
    with open(matrix_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=matrix_cols)
        writer.writeheader()
        for r in sorted(all_matrix, key=lambda x: (x["issue_date"], x["sector"], x["vessel_class"], str(x["age_years"]))):
            writer.writerow(r)
    print(f"Written {len(all_matrix)} rows to {matrix_csv}", flush=True)

    sales_csv = OUT_SERIES_DIR / "hellenic_vv_benchmark_sales_series.csv"
    sales_cols = ["issue_date", "vessel_class", "vessel_name", "vessel_specs", "seller", "sale_price_usd_m", "vv_value_usd_m", "raw_transaction", "source_file"]
    with open(sales_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=sales_cols)
        writer.writeheader()
        for s in sorted(all_sales, key=lambda x: (x["issue_date"], x["vessel_name"])):
            writer.writerow(s)
    print(f"Written {len(all_sales)} rows to {sales_csv}", flush=True)

    # Save state
    state = {
        "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "reports_processed": len(summaries),
        "matrix_observations": len(all_matrix),
        "benchmark_sales_observations": len(all_sales),
    }
    with open(STATE_FILE, "w", encoding="utf-8") as sf:
        json.dump(state, sf, indent=2)

    return state


if __name__ == "__main__":
    limit_arg = int(sys.argv[1]) if len(sys.argv) > 1 else None
    asyncio.run(run_all_async(limit=limit_arg))
