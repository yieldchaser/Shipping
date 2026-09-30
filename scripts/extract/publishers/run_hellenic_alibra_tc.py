"""Hellenic Alibra Time Charter Estimates Extraction Runner.

Extracts weekly Dry and Tanker Time Charter Estimates reports published by Alibra Shipping:
- Dry Charter: 240+ weekly reports spanning 2021 to 2026
- Tanker Charter: 240+ weekly reports spanning 2021 to 2026
- Ingests HTML narrative commentary and converts table graphics via LlamaParse async
- Caches all LlamaParse outputs locally in data/extracted/cache_alibra/
- Replaces raw emoji trend markers with clean standard tokens ('up', 'down', 'flat')
- Produces:
  data/extracted/md/hellenic/dry_charter/<year>/alibra_dry_<date>.md + .tables.json
  data/extracted/md/hellenic/tanker_charter/<year>/alibra_tanker_<date>.md + .tables.json
  data/extracted/series/hellenic_alibra_dry_tc_series.csv
  data/extracted/series/hellenic_alibra_tanker_tc_series.csv
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
DRY_DIR = ROOT / "corpus" / "02-hellenic" / "dry_charter"
WET_DIR = ROOT / "corpus" / "02-hellenic" / "tanker_charter"
OUT_DRY_MD = ROOT / "data" / "extracted" / "md" / "hellenic" / "dry_charter"
OUT_WET_MD = ROOT / "data" / "extracted" / "md" / "hellenic" / "tanker_charter"
OUT_SERIES = ROOT / "data" / "extracted" / "series"
CACHE_DIR = ROOT / "data" / "extracted" / "cache_alibra"
STATE_FILE = ROOT / "data" / "extracted" / "md" / "hellenic" / "_alibra_run_state.json"

LLAMA_KEY = os.environ.get("LLAMA_CLOUD_API_KEY", "llx-g8p7UzojxIQocFBeWgvRDUpaQR6U56RK3nWniAtWuBksFjiD")


def clean_text(s: str) -> str:
    """Normalize whitespace and fix unicode artifacts."""
    if not s:
        return ""
    s = s.replace("\ufffd", "'")
    s = s.replace("\u2019", "'").replace("\u2018", "'")
    s = s.replace("\u201c", '"').replace("\u201d", '"')
    s = s.replace("`", "'")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def parse_cell(cell: str) -> Tuple[Optional[int], str]:
    """Extract numeric day-rate and standard trend string without emojis."""
    trend = "flat"
    if any(u in cell for u in ["▲", "🔺", "^", "+", "🟢"]):
        trend = "up"
    elif any(d in cell for d in ["▼", "🔻", "v", "-", "🔴"]):
        trend = "down"
    elif any(e in cell for e in ["=", "—", "–", "~"]):
        trend = "flat"

    m = re.search(r"[\d,]+", cell)
    rate = int(m.group(0).replace(",", "")) if m else None
    return rate, trend


def parse_dry_table(md_text: str, issue_date: str, source_file: str) -> List[Dict[str, Any]]:
    """Parse Alibra Dry Time Charter table into structured rows."""
    rows = []
    lines = [l.strip() for l in md_text.strip().split("\n") if l.strip().startswith("|")]
    if len(lines) < 3:
        return rows

    col_specs = [
        ("6 MOS", "ATL"), ("6 MOS", "PAC"),
        ("1 YR", "ATL"), ("1 YR", "PAC"),
        ("2 YR", "ATL"), ("2 YR", "PAC"),
    ]

    for l in lines[2:]:
        parts = [p.strip() for p in l.strip("|").split("|")]
        if len(parts) < 7:
            continue
        size = re.sub(r"[*_]", "", parts[0]).strip()
        if not size or size.upper() in ["SIZE", "PERIOD", "PERIOD/SIZE"] or "PERIOD" in size.upper():
            continue
        for idx, (tenor, basin) in enumerate(col_specs):
            if idx + 1 < len(parts):
                rate, trend = parse_cell(parts[idx + 1])
                if rate is not None:
                    rows.append({
                        "issue_date": issue_date,
                        "vessel_class": size,
                        "tenor": tenor,
                        "basin": basin,
                        "rate_usd_pdpr": rate,
                        "trend": trend,
                        "source_file": source_file,
                    })
    return rows


def parse_tanker_table(md_text: str, issue_date: str, source_file: str) -> List[Dict[str, Any]]:
    """Parse Alibra Tanker Time Charter table into structured rows."""
    rows = []
    lines = [l.strip() for l in md_text.strip().split("\n") if l.strip().startswith("|")]
    if len(lines) < 3:
        return rows

    col_specs = [
        ("1 YR", False),
        ("2 YR", False),
        ("3 YR", True),
        ("5 YR", True),
    ]

    for l in lines[2:]:
        parts = [p.strip() for p in l.strip("|").split("|")]
        if len(parts) < 5:
            continue
        size = re.sub(r"[*_]", "", parts[0]).strip()
        if not size or size.upper() in ["SIZE", "PERIOD"] or "PERIOD" in size.upper():
            continue
        for idx, (tenor, eco) in enumerate(col_specs):
            if idx + 1 < len(parts):
                rate, trend = parse_cell(parts[idx + 1])
                if rate is not None:
                    rows.append({
                        "issue_date": issue_date,
                        "vessel_class": size,
                        "tenor": tenor,
                        "rate_usd_pdpr": rate,
                        "eco_scrubber": eco,
                        "trend": trend,
                        "source_file": source_file,
                    })
    return rows


def find_companion_image(h_path: Path) -> Optional[Path]:
    """Locate the canonical table image companion for an HTML report."""
    stem = h_path.stem
    parent = h_path.parent

    # Standard companions in current directory
    for cand_name in [f"{stem}_img2.jpg", f"{stem}_img2.png", f"{stem}_img1.jpg", f"{stem}_img1.png"]:
        p = parent / cand_name
        if p.exists() and p.stat().st_size > 20000:
            return p

    # Check assets directory by stem match
    assets_dir = parent / "assets"
    if assets_dir.exists():
        for cand in assets_dir.glob(f"{stem}*.*"):
            if cand.suffix.lower() in [".jpg", ".jpeg", ".png"] and cand.stat().st_size > 20000:
                return cand

    # Check links/images referenced in HTML body
    try:
        content = h_path.read_text(encoding="utf-8", errors="ignore")
        soup = BeautifulSoup(content, "html.parser")
        for tag in soup.find_all(["img", "a"]):
            src = tag.get("src") or tag.get("href")
            if src and any(src.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png"]):
                cand = parent / src
                if cand.exists() and cand.stat().st_size > 20000:
                    return cand
    except Exception:
        pass

    return None


async def get_or_parse_image_async(img_path: Path, parser: LlamaParse, sem: asyncio.Semaphore) -> str:
    """Retrieve cached LlamaParse markdown or submit image via LlamaParse async."""
    stem = img_path.stem
    cache_file = CACHE_DIR / f"{stem}.md"
    if cache_file.exists() and cache_file.stat().st_size > 50:
        return cache_file.read_text(encoding="utf-8")

    async with sem:
        # Convert image to single-page PDF
        img_doc = pymupdf.open(img_path)
        pdf_bytes = img_doc.convert_to_pdf()
        img_doc.close()

        tmp_pdf = CACHE_DIR / f"tmp_{stem}_{os.getpid()}.pdf"
        tmp_pdf.write_bytes(pdf_bytes)

        try:
            for attempt in range(3):
                try:
                    docs = await parser.aload_data(str(tmp_pdf))
                    md_text = "\n\n".join(d.text for d in docs)
                    cache_file.write_text(md_text, encoding="utf-8")
                    return md_text
                except Exception as e:
                    if attempt == 2:
                        raise e
                    await asyncio.sleep(2 * (attempt + 1))
            return ""
        finally:
            if tmp_pdf.exists():
                tmp_pdf.unlink()


async def process_item_async(cat: str, corpus_dir: Path, out_md_dir: Path,
                             h_path: Path, parser: LlamaParse, sem: asyncio.Semaphore) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    fname = h_path.name
    m_date = re.match(r"^(\d{4}-\d{2}-\d{2})", fname)
    issue_date = m_date.group(1) if m_date else "UNKNOWN"
    year = issue_date[:4]

    content = h_path.read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(content, "html.parser")
    title = soup.title.string.strip() if soup.title and soup.title.string else f"Weekly Time Charter Estimates - {issue_date}"

    # Extract commentary paragraphs
    paras = []
    for p in soup.find_all("p"):
        txt = clean_text(p.get_text(" ", strip=True))
        if txt and not txt.startswith("Linked asset:") and not txt.startswith("http"):
            paras.append(txt)
    commentary = "\n\n".join(paras)

    # Companion image
    img_cand = find_companion_image(h_path)

    table_md = ""
    table_rows: List[Dict[str, Any]] = []
    if img_cand:
        try:
            table_md = await get_or_parse_image_async(img_cand, parser, sem)
            if cat == "dry":
                table_rows = parse_dry_table(table_md, issue_date, fname)
            else:
                table_rows = parse_tanker_table(table_md, issue_date, fname)
        except Exception as e:
            print(f"  [!] Failed parsing image for {fname}: {e}")

    # Build clean markdown
    md_lines = [
        f"# {title}",
        "",
        f"- **Issue Date**: {issue_date}",
        f"- **Publisher**: Alibra Shipping Limited",
        f"- **Sector**: {'Dry Bulk' if cat == 'dry' else 'Tanker'}",
        f"- **Source**: `corpus/02-hellenic/{corpus_dir.name}/{year}/{fname}`",
        "",
        "## Market Commentary",
        "",
        commentary if commentary else "*No editorial commentary.*",
        "",
        "## Time Charter Estimates ($/pdpr)",
        "",
    ]

    if table_rows:
        if cat == "dry":
            md_lines.extend([
                "| Size | Tenor | Basin | Rate ($/day) | Trend |",
                "|---|---|---|---|---|",
            ])
            for r in table_rows:
                md_lines.append(f"| {r['vessel_class']} | {r['tenor']} | {r['basin']} | ${r['rate_usd_pdpr']:,} | {r['trend']} |")
        else:
            md_lines.extend([
                "| Size | Tenor | Rate ($/day) | Eco / Scrubber | Trend |",
                "|---|---|---|---|---|",
            ])
            for r in table_rows:
                eco_str = "Yes" if r["eco_scrubber"] else "Standard"
                md_lines.append(f"| {r['vessel_class']} | {r['tenor']} | ${r['rate_usd_pdpr']:,} | {eco_str} | {r['trend']} |")
    else:
        md_lines.append("*Table estimates not available.*")
    md_lines.append("")

    md_lines.extend([
        "## Contact & Source",
        "",
        "> *Estimates provided by Alibra Shipping Limited for general information purposes only. Rates in $/pdpr.*",
        ""
    ])

    summary = {
        "issue_date": issue_date,
        "year": year,
        "filename": fname,
        "title": title,
        "observations_count": len(table_rows),
    }

    stem = f"alibra_{cat}_{issue_date}"
    year_dir = out_md_dir / year
    year_dir.mkdir(parents=True, exist_ok=True)

    # Write .md
    md_path = year_dir / f"{stem}.md"
    with open(md_path, "w", encoding="utf-8") as mf:
        mf.write("\n".join(md_lines))

    # Write .tables.json
    json_path = year_dir / f"{stem}.tables.json"
    with open(json_path, "w", encoding="utf-8") as jf:
        json.dump({
            "issue_date": issue_date,
            "year": year,
            "title": title,
            "source_file": fname,
            "records_count": len(table_rows),
            "records": table_rows
        }, jf, indent=2, ensure_ascii=False)

    return summary, table_rows


async def process_collection_async(cat: str, corpus_dir: Path, out_md_dir: Path,
                                  parser: LlamaParse, sem: asyncio.Semaphore,
                                  limit: Optional[int] = None) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Process all weekly reports for a specific charter sector asynchronously with semaphore."""
    html_files = sorted(list(corpus_dir.glob("**/*weekly-*-time-charter-estimates*.html")))
    if limit:
        html_files = html_files[:limit]
    print(f"[{cat.upper()}] Starting extraction of {len(html_files)} weekly HTML reports...")

    tasks = [process_item_async(cat, corpus_dir, out_md_dir, hp, parser, sem) for hp in html_files]
    results_raw = await asyncio.gather(*tasks, return_exceptions=True)

    all_series_rows: List[Dict[str, Any]] = []
    report_summaries: List[Dict[str, Any]] = []
    for item in results_raw:
        if isinstance(item, Exception):
            print(f"  [ERROR in {cat} batch item]: {item}", flush=True)
            continue
        summary, rows = item
        all_series_rows.extend(rows)
        report_summaries.append(summary)

    print(f"[{cat.upper()}] Completed {len(report_summaries)} reports -> {len(all_series_rows)} observations.", flush=True)
    return all_series_rows, report_summaries


async def run_all_async(limit: Optional[int] = None) -> Dict[str, Any]:
    """Execute complete Alibra extraction workflow across Dry and Wet charter."""
    OUT_DRY_MD.mkdir(parents=True, exist_ok=True)
    OUT_WET_MD.mkdir(parents=True, exist_ok=True)
    OUT_SERIES.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    parser = LlamaParse(
        api_key=LLAMA_KEY,
        result_type="markdown",
        tier="cost_effective",
        version="latest",
        verbose=False
    )
    sem = asyncio.Semaphore(4)

    t0 = time.time()
    print("=== Starting Alibra Dry Time Charter Extraction ===", flush=True)
    dry_rows, dry_summaries = await process_collection_async("dry", DRY_DIR, OUT_DRY_MD, parser, sem, limit=limit)

    # Immediately write data/extracted/series/hellenic_alibra_dry_tc_series.csv
    dry_cols = ["issue_date", "vessel_class", "tenor", "basin", "rate_usd_pdpr", "trend", "source_file"]
    dry_csv = OUT_SERIES / "hellenic_alibra_dry_tc_series.csv"
    with open(dry_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=dry_cols)
        writer.writeheader()
        for r in sorted(dry_rows, key=lambda x: (x["issue_date"], x["vessel_class"], x["tenor"], x["basin"])):
            writer.writerow(r)
    print(f"\nWritten {len(dry_rows)} total rows to {dry_csv}", flush=True)

    print("\n=== Starting Alibra Tanker Time Charter Extraction ===", flush=True)
    wet_rows, wet_summaries = await process_collection_async("wet", WET_DIR, OUT_WET_MD, parser, sem, limit=limit)

    # Write data/extracted/series/hellenic_alibra_tanker_tc_series.csv
    wet_cols = ["issue_date", "vessel_class", "tenor", "rate_usd_pdpr", "eco_scrubber", "trend", "source_file"]
    wet_csv = OUT_SERIES / "hellenic_alibra_tanker_tc_series.csv"
    with open(wet_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=wet_cols)
        writer.writeheader()
        for r in sorted(wet_rows, key=lambda x: (x["issue_date"], x["vessel_class"], x["tenor"])):
            writer.writerow(r)
    print(f"Written {len(wet_rows)} total rows to {wet_csv}")

    state = {
        "dry_reports": len(dry_summaries),
        "dry_observations": len(dry_rows),
        "wet_reports": len(wet_summaries),
        "wet_observations": len(wet_rows),
        "elapsed_seconds": round(time.time() - t0, 1)
    }
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

    return state


if __name__ == "__main__":
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else None
    state = asyncio.run(run_all_async(limit=lim))
    print("Alibra Extraction Complete. State:", json.dumps(state, indent=2))
