"""Hellenic GMS Weekly Demolition Rankings Image & Intelligence Extraction Runner.

Extracts weekly GMS demolition reports published in corpus/02-hellenic/demolition/:
- 271 GMS weekly reports spanning 2021 to 2026
- Authoritative Market Rankings table (_img2.jpg / assets/*.jpg) converted to PDF and parsed via LlamaParse
- Structured parsing of the 4 recycling locations across 3 vessel sectors:
  * Locations: India, Pakistan, Bangladesh, Turkey
  * Sectors: Dry Bulk ($/LDT), Tankers ($/LDT), Containers ($/LDT)
  * Sentiments: Firming, Steady, Weak, Declining, etc.
- Complete editorial market commentary prose
- Produces:
  data/extracted/md/hellenic/demolition/<year>/gms_<date>.md + .tables.json
  data/extracted/series/hellenic_gms_demolition_series.csv
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

INPUT_DIR = ROOT / "corpus" / "02-hellenic" / "demolition"
OUT_MD_DIR = ROOT / "data" / "extracted" / "md" / "hellenic" / "demolition"
OUT_SERIES_DIR = ROOT / "data" / "extracted" / "series"
CACHE_DIR = ROOT / "data" / "extracted" / "cache_hellenic_gms"
STATE_FILE = ROOT / "data" / "extracted" / "md" / "hellenic" / "_gms_demolition_run_state.json"


def clean_num(val_str: Any) -> Optional[float]:
    if val_str is None:
        return None
    cleaned = str(val_str).strip().replace(",", "").replace("$", "").replace("%", "").replace("*", "").replace("/ LDT", "").replace("/LDT", "").strip()
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
    """Locate canonical GMS market rankings table image."""
    stem = h_path.stem
    parent = h_path.parent

    # 1. Prefer _img2 in parent dir
    for cand_name in [f"{stem}_img2.jpg", f"{stem}_img2.jpeg", f"{stem}_img2.png"]:
        p = parent / cand_name
        if p.exists() and p.stat().st_size > 15000:
            return p

    # 2. Check assets dir for img2 or large img1
    assets_dir = parent / "assets"
    if assets_dir.exists():
        for cand in assets_dir.glob(f"{stem}*.*"):
            if cand.suffix.lower() in [".jpg", ".jpeg", ".png"]:
                if "img2" in cand.name.lower() and cand.stat().st_size > 15000:
                    return cand
                if "img1" in cand.name.lower() and cand.stat().st_size > 25000:
                    return cand

    # 3. Check _img1 in parent dir (if large enough to be a table)
    for cand_name in [f"{stem}_img1.jpg", f"{stem}_img1.jpeg", f"{stem}_img1.png"]:
        p = parent / cand_name
        if p.exists() and p.stat().st_size > 25000:
            return p

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


def parse_gms_rankings_markdown(md_text: str, issue_date: str, source_file: str) -> List[Dict[str, Any]]:
    """Parse LlamaParse markdown table for GMS weekly market rankings."""
    records: List[Dict[str, Any]] = []
    lines = [l.strip() for l in md_text.strip().split("\n") if l.strip().startswith("|")]
    if len(lines) < 3:
        return records

    # Look for table containing Location/Sentiment/Dry Bulk/Tankers
    header_idx = -1
    for i, line in enumerate(lines):
        line_up = line.upper()
        if "LOCATION" in line_up or "DRY BULK" in line_up or "TANKER" in line_up:
            header_idx = i
            break

    if header_idx == -1:
        return records

    for line in lines[header_idx + 2:]:
        parts = [p.strip() for p in line.strip("|").split("|")]
        if len(parts) < 5:
            continue

        rank_str = re.sub(r"[*_]", "", parts[0]).strip()
        loc_str = re.sub(r"[*_]", "", parts[1]).strip()
        sentiment_str = re.sub(r"[*_]", "", parts[2]).strip()
        dry_str = re.sub(r"[*_]", "", parts[3]).strip()
        wet_str = re.sub(r"[*_]", "", parts[4]).strip()
        cont_str = re.sub(r"[*_]", "", parts[5]).strip() if len(parts) > 5 else ""

        loc_clean = re.sub(r"[\~\\\\/]", "", loc_str).strip().title()
        canonical_loc = None
        for target in ["India", "Pakistan", "Bangladesh", "Turkey"]:
            if target.lower() in loc_clean.lower():
                canonical_loc = target
                break
        if not canonical_loc:
            continue
        loc_clean = canonical_loc

        records.append({
            "issue_date": issue_date,
            "rank": clean_num(rank_str),
            "location": loc_clean,
            "sentiment": sentiment_str.title(),
            "dry_bulk_usd_ldt": clean_num(dry_str),
            "tankers_usd_ldt": clean_num(wet_str),
            "containers_usd_ldt": clean_num(cont_str),
            "source_file": source_file,
        })

    return records


async def process_gms_item_async(h_path: Path, sem: asyncio.Semaphore) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    fname = h_path.name
    m_date = re.match(r"^(\d{4}-\d{2}-\d{2})", fname)
    issue_date = m_date.group(1) if m_date else "UNKNOWN"
    year = issue_date[:4]

    if issue_date == "UNKNOWN" or year == "0000" or "unknown" in [p.lower() for p in h_path.parts]:
        raise ValueError(f"Skipping undated or 0000 stub file: {h_path}")

    content = h_path.read_text(encoding="utf-8", errors="ignore")
    if any(err in content for err in ("Error code 520", "Cloudflare Ray ID", "This site can\u2019t be reached", "This site can't be reached")):
        raise ValueError(f"Skipping Cloudflare/DNS error HTML page: {h_path}")

    soup = BeautifulSoup(content, "html.parser")
    title = soup.title.string.strip() if soup.title and soup.title.string else f"GMS Weekly Demolition Report - {issue_date}"

    # Extract editorial commentary
    paras = []
    for p in soup.find_all("p"):
        txt = clean_text(p.get_text(" ", strip=True))
        if not txt or txt.startswith("Linked asset:") or txt.startswith("http"):
            continue
        paras.append(txt)
    commentary = "\n\n".join(paras)

    img_cand = find_companion_image(h_path)
    rankings: List[Dict[str, Any]] = []

    if img_cand:
        try:
            table_md = await get_or_parse_image_async(img_cand, sem)
            rankings = parse_gms_rankings_markdown(table_md, issue_date, fname)
        except Exception as e:
            print(f"  [!] Failed parsing image for {fname}: {e}")

    stem = f"gms_{issue_date}"
    year_dir = OUT_MD_DIR / year
    year_dir.mkdir(parents=True, exist_ok=True)

    # Build clean markdown
    md_lines = [
        f"# {title}",
        "",
        f"- **Issue Date**: {issue_date}",
        f"- **Publisher**: GMS Leadership",
        f"- **Source**: `corpus/02-hellenic/demolition/{year}/{fname}`",
        "",
        "## Market Commentary",
        "",
        commentary if commentary else "*No editorial commentary.*",
        "",
    ]

    if rankings:
        md_lines.extend([
            "## GMS Market Rankings ($/LDT)",
            "",
            "| Rank | Location | Sentiment | Dry Bulk ($/LDT) | Tankers ($/LDT) | Containers ($/LDT) |",
            "|---|---|---|---|---|---|",
        ])
        for r in rankings:
            dry = f"${r['dry_bulk_usd_ldt']:.0f}" if r['dry_bulk_usd_ldt'] is not None else "-"
            wet = f"${r['tankers_usd_ldt']:.0f}" if r['tankers_usd_ldt'] is not None else "-"
            cont = f"${r['containers_usd_ldt']:.0f}" if r['containers_usd_ldt'] is not None else "-"
            rank_val = int(r['rank']) if r['rank'] is not None else "-"
            md_lines.append(f"| {rank_val} | {r['location']} | {r['sentiment']} | {dry} | {wet} | {cont} |")
        md_lines.append("")

    md_lines.extend([
        "## Disclaimer",
        "",
        "> *Rankings and price estimates provided by GMS Leadership. For informational purposes only.*",
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
            "rankings_count": len(rankings),
            "rankings": rankings,
        }, jf, indent=2, ensure_ascii=False)

    summary = {
        "issue_date": issue_date,
        "year": year,
        "filename": fname,
        "rankings_count": len(rankings),
    }

    return summary, rankings


async def run_all_async(limit: Optional[int] = None) -> Dict[str, Any]:
    OUT_MD_DIR.mkdir(parents=True, exist_ok=True)
    OUT_SERIES_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    sem = asyncio.Semaphore(4)

    html_files = sorted([h for h in INPUT_DIR.glob("**/*.html") if "gms" in h.name.lower()])
    if limit:
        html_files = html_files[:limit]

    print(f"[GMS] Starting extraction of {len(html_files)} weekly reports...", flush=True)

    tasks = [process_gms_item_async(hp, sem) for hp in html_files]
    results_raw = await asyncio.gather(*tasks, return_exceptions=True)

    all_rankings: List[Dict[str, Any]] = []
    summaries: List[Dict[str, Any]] = []

    for item in results_raw:
        if isinstance(item, Exception):
            print(f"  [ERROR in GMS batch item]: {item}", flush=True)
            continue
        summary, rankings_rows = item
        all_rankings.extend(rankings_rows)
        summaries.append(summary)

    print(f"[GMS] Completed {len(summaries)} reports -> {len(all_rankings)} ranking observations.", flush=True)

    # Write master series
    # 2026-10-04: DO NOT write the canonical path. hellenic_gms_demolition_series.csv is
    # OWNED by run_gms_demolition.py (audit: 1,092 rows, the full PDF+HTML union). This
    # LlamaParse-based runner is a duplicate that last-clobbered it with an 8-col slice
    # (last-writer-wins). Write the diagnostic copy instead.
    rankings_csv = OUT_SERIES_DIR / "hellenic_gms_demolition_series.LP-SIDECAR.csv"
    rankings_cols = ["issue_date", "rank", "location", "sentiment", "dry_bulk_usd_ldt", "tankers_usd_ldt", "containers_usd_ldt", "source_file"]
    with open(rankings_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rankings_cols)
        writer.writeheader()
        for r in sorted(all_rankings, key=lambda x: (x["issue_date"], x["location"])):
            writer.writerow(r)
    print(f"Written {len(all_rankings)} rows to {rankings_csv}", flush=True)

    # Save state
    state = {
        "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "reports_processed": len(summaries),
        "rankings_observations": len(all_rankings),
    }
    with open(STATE_FILE, "w", encoding="utf-8") as sf:
        json.dump(state, sf, indent=2)

    return state


if __name__ == "__main__":
    limit_arg = int(sys.argv[1]) if len(sys.argv) > 1 else None
    asyncio.run(run_all_async(limit=limit_arg))
