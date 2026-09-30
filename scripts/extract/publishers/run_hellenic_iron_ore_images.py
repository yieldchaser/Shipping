"""Hellenic MMi Daily Iron Ore Index Image Extraction Runner.

Extracts daily Iron Ore index dashboards published by Metals Market Index (MMi) in corpus/02-hellenic/iron_ore/:
- 1,173 daily reports spanning 2021 to 2026
- Converts authoritative table dashboards (_img2.jpg / assets/*.jpg) via LlamaParse async
- Caches all LlamaParse outputs locally in data/extracted/cache_mmi_iron_ore/
- Extracts granular index values:
  * IOPI (62%, 58%, 65% FOT Qingdao & CFR Qingdao Equivalent)
  * IOSI (62%, 65% CFR Qingdao Seaborne)
  * IOPLI (62.5% Lump FOT & CFR)
  * Market Commentary desk prose
- Produces:
  data/extracted/md/hellenic/iron_ore/<year>/mmi_<date>.md + .tables.json
  data/extracted/series/hellenic_iron_ore_table_series.csv
  data/extracted/series/hellenic_iron_ore_commentary_series.csv
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
import uuid

import pymupdf
from bs4 import BeautifulSoup
from llama_parse import LlamaParse

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from scripts.extract.llama_manager import manager as key_manager

INPUT_DIR = ROOT / "corpus" / "02-hellenic" / "iron_ore"
OUT_MD_DIR = ROOT / "data" / "extracted" / "md" / "hellenic" / "iron_ore"
OUT_SERIES_DIR = ROOT / "data" / "extracted" / "series"
CACHE_DIR = ROOT / "data" / "extracted" / "cache_mmi_iron_ore"
STATE_FILE = ROOT / "data" / "extracted" / "md" / "hellenic" / "_mmi_iron_ore_run_state.json"


def clean_num(val_str: Any) -> Optional[float]:
    if val_str is None:
        return None
    cleaned = str(val_str).strip().replace(",", "").replace("$", "").replace("%", "").replace("*", "").replace("~", "")
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

        tmp_pdf = CACHE_DIR / f"tmp_{stem}_{os.getpid()}_{uuid.uuid4().hex[:6]}.pdf"
        tmp_pdf.write_bytes(pdf_bytes)

        try:
            for attempt in range(5):
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
                    if not md_text.strip() or len(md_text.strip()) < 50:
                        raise RuntimeError(f"LlamaParse returned empty or truncated output (length {len(md_text.strip())})")
                    cache_file.write_text(md_text, encoding="utf-8")
                    key_manager.record_success(1, used_key=current_key)
                    return md_text
                except Exception as e:
                    err_msg = str(e).lower()
                    if any(term in err_msg for term in ["429", "quota", "payment required", "credit", "empty or truncated", "plan"]):
                        print(f"  [!] Key exhausted on {stem}, swapping key: {e}")
                        key_manager.mark_key_exhausted(reason=str(e), failed_key=current_key)
                        continue
                    if attempt == 4:
                        raise e
                    await asyncio.sleep(2 * (attempt + 1))
            return ""
        finally:
            if tmp_pdf.exists():
                try:
                    tmp_pdf.unlink()
                except Exception:
                    pass


def parse_mmi_iron_ore_markdown(md_text: str, issue_date: str, source_file: str) -> Tuple[List[Dict[str, Any]], str]:
    records: List[Dict[str, Any]] = []

    # 1. Commentary
    commentary = ""
    m_comm = re.search(r"##\s*MARKET COMMENTARY\s*\n\n(.*?)(?=\n##|\n<table|\Z)", md_text, re.DOTALL | re.IGNORECASE)
    if m_comm:
        commentary = clean_text(m_comm.group(1))
    else:
        soup_comm = BeautifulSoup(md_text, "html.parser")
        for tr in soup_comm.find_all("tr"):
            for td in tr.find_all(["td", "th"]):
                txt = td.get_text(" ", strip=True)
                if "MARKET COMMENTARY" in txt.upper() and len(txt) > 30:
                    commentary = clean_text(re.sub(r"MARKET COMMENTARY", "", txt, flags=re.IGNORECASE))
                    break
            if not commentary:
                tds = tr.find_all(["td", "th"])
                for i, td in enumerate(tds):
                    if "MARKET COMMENTARY" in td.get_text(strip=True).upper():
                        next_tr = tr.find_next_sibling("tr")
                        if next_tr:
                            comm_tds = next_tr.find_all("td")
                            if comm_tds:
                                commentary = clean_text(comm_tds[-1].get_text(" ", strip=True))
                                break
            if commentary:
                break

    # 2. IOPI (Port Stock Index)
    for line in md_text.splitlines():
        if re.search(r"\|\s*\*{0,2}IOPI?\d{2}\*{0,2}\s*\|", line, re.IGNORECASE):
            parts = [p.strip() for p in line.strip("|").split("|")]
            if len(parts) >= 16:
                idx_code = re.sub(r"[*_]", "", parts[0]).upper()
                fe_grade = parts[1]
                fot_price = clean_num(parts[2])
                fot_chg = clean_num(parts[3])
                fot_chg_pct = clean_num(parts[4])
                fot_mtd = clean_num(parts[5])
                fot_ytd = clean_num(parts[6])
                fot_low = clean_num(parts[7])
                fot_high = clean_num(parts[8])

                cfr_price = clean_num(parts[9])
                cfr_chg = clean_num(parts[10])
                cfr_chg_pct = clean_num(parts[11])
                cfr_mtd = clean_num(parts[12])
                cfr_ytd = clean_num(parts[13])
                cfr_low = clean_num(parts[14])
                cfr_high = clean_num(parts[15])

                records.append({
                    "issue_date": issue_date,
                    "index_family": "IOPI",
                    "index_code": idx_code,
                    "fe_grade": fe_grade,
                    "fot_rmb_wmt": fot_price,
                    "fot_change": fot_chg,
                    "fot_change_pct": fot_chg_pct,
                    "fot_mtd": fot_mtd,
                    "fot_ytd": fot_ytd,
                    "fot_low": fot_low,
                    "fot_high": fot_high,
                    "cfr_usd_dmt": cfr_price,
                    "cfr_change": cfr_chg,
                    "cfr_change_pct": cfr_chg_pct,
                    "cfr_mtd": cfr_mtd,
                    "cfr_ytd": cfr_ytd,
                    "cfr_low": cfr_low,
                    "cfr_high": cfr_high,
                    "source_file": source_file,
                })

    # 3. HTML table structures (IOSI and IOPLI)
    soup = BeautifulSoup(md_text, "html.parser")
    for tr in soup.find_all("tr"):
        tds = [td.get_text(strip=True) for td in tr.find_all("td")]
        if tds and any("IOSI" in td.upper() for td in tds):
            idx_code = tds[0].replace("*", "").upper()
            fe_grade = tds[1] if len(tds) > 1 else ""
            price = clean_num(tds[2]) if len(tds) > 2 else None
            chg = clean_num(tds[3]) if len(tds) > 3 else None
            chg_pct = clean_num(tds[4]) if len(tds) > 4 else None
            mtd = clean_num(tds[5]) if len(tds) > 5 else None
            ytd = clean_num(tds[6]) if len(tds) > 6 else None
            low = clean_num(tds[7]) if len(tds) > 7 else None
            high = clean_num(tds[8]) if len(tds) > 8 else None
            records.append({
                "issue_date": issue_date,
                "index_family": "IOSI",
                "index_code": idx_code,
                "fe_grade": fe_grade,
                "fot_rmb_wmt": None,
                "fot_change": None,
                "fot_change_pct": None,
                "fot_mtd": None,
                "fot_ytd": None,
                "fot_low": None,
                "fot_high": None,
                "cfr_usd_dmt": price,
                "cfr_change": chg,
                "cfr_change_pct": chg_pct,
                "cfr_mtd": mtd,
                "cfr_ytd": ytd,
                "cfr_low": low,
                "cfr_high": high,
                "source_file": source_file,
            })
        elif tds and any("IOPLI" in td.upper() for td in tds):
            idx_code = tds[0].replace("*", "").upper()
            fe_grade = tds[1] if len(tds) > 1 else ""
            fot_price = clean_num(tds[2]) if len(tds) > 2 else None
            fot_chg = clean_num(tds[3]) if len(tds) > 3 else None
            fot_chg_pct = clean_num(tds[4]) if len(tds) > 4 else None
            fot_mtd = clean_num(tds[5]) if len(tds) > 5 else None
            fot_ytd = clean_num(tds[6]) if len(tds) > 6 else None
            fot_low = clean_num(tds[7]) if len(tds) > 7 else None
            fot_high = clean_num(tds[8]) if len(tds) > 8 else None

            cfr_price = clean_num(tds[9]) if len(tds) > 9 else None
            cfr_chg = clean_num(tds[10]) if len(tds) > 10 else None
            cfr_chg_pct = clean_num(tds[11]) if len(tds) > 11 else None
            cfr_mtd = clean_num(tds[12]) if len(tds) > 12 else None
            cfr_ytd = clean_num(tds[13]) if len(tds) > 13 else None
            cfr_low = clean_num(tds[14]) if len(tds) > 14 else None
            cfr_high = clean_num(tds[15]) if len(tds) > 15 else None
            records.append({
                "issue_date": issue_date,
                "index_family": "IOPLI",
                "index_code": idx_code,
                "fe_grade": fe_grade,
                "fot_rmb_wmt": fot_price,
                "fot_change": fot_chg,
                "fot_change_pct": fot_chg_pct,
                "fot_mtd": fot_mtd,
                "fot_ytd": fot_ytd,
                "fot_low": fot_low,
                "fot_high": fot_high,
                "cfr_usd_dmt": cfr_price,
                "cfr_change": cfr_chg,
                "cfr_change_pct": cfr_chg_pct,
                "cfr_mtd": cfr_mtd,
                "cfr_ytd": cfr_ytd,
                "cfr_low": cfr_low,
                "cfr_high": cfr_high,
                "source_file": source_file,
            })

    return records, commentary


async def process_iron_ore_item_async(h_path: Path, sem: asyncio.Semaphore) -> Tuple[Dict[str, Any], List[Dict[str, Any]], str]:
    fname = h_path.name
    m_date = re.match(r"^(\d{4}-\d{2}-\d{2})", fname)
    issue_date = m_date.group(1) if m_date else "UNKNOWN"
    year = issue_date[:4]

    content = h_path.read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(content, "html.parser")
    title = soup.title.string.strip() if soup.title and soup.title.string else f"MMi Daily Iron Ore Index Report - {issue_date}"

    img_cand = find_companion_image(h_path)
    records: List[Dict[str, Any]] = []
    commentary = ""

    if img_cand:
        try:
            table_md = await get_or_parse_image_async(img_cand, sem)
            records, commentary = parse_mmi_iron_ore_markdown(table_md, issue_date, fname)
        except Exception as e:
            print(f"  [!] Failed parsing image for {fname}: {e}")

    # Fallback to HTML body commentary if image commentary was missing
    if not commentary:
        paras = []
        for p in soup.find_all("p"):
            txt = clean_text(p.get_text(" ", strip=True))
            if txt and not txt.startswith("Linked asset:") and not txt.startswith("http") and not txt.startswith("Download PDF"):
                paras.append(txt)
        commentary = "\n\n".join(paras)

    stem = f"mmi_{issue_date}"
    year_dir = OUT_MD_DIR / year
    year_dir.mkdir(parents=True, exist_ok=True)

    # Write clean Markdown document
    md_lines = [
        f"# {title}",
        "",
        f"- **Issue Date**: {issue_date}",
        f"- **Publisher**: Metals Market Index (MMi)",
        f"- **Commodity**: Iron Ore (Fines & Lump)",
        f"- **Source**: `corpus/02-hellenic/iron_ore/{year}/{fname}`",
        "",
        "## Market Commentary",
        "",
        commentary if commentary else "*No editorial commentary.*",
        "",
        "## MMi Index Summary",
        "",
        "| Index | Grade | Family | FOT Qingdao (RMB/wmt) | CFR Qingdao Eq (USD/dmt) | Change | MTD | YTD | 52w Low | 52w High |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in records:
        fot_str = f"¥{r['fot_rmb_wmt']:,.2f}" if r["fot_rmb_wmt"] is not None else "-"
        cfr_str = f"${r['cfr_usd_dmt']:,.2f}" if r["cfr_usd_dmt"] is not None else "-"
        chg_str = f"{r['cfr_change']:+.2f}" if r["cfr_change"] is not None else (f"{r['fot_change']:+.2f}" if r["fot_change"] is not None else "-")
        mtd_str = f"{r['cfr_mtd']:.2f}" if r["cfr_mtd"] is not None else (f"{r['fot_mtd']:.2f}" if r["fot_mtd"] is not None else "-")
        ytd_str = f"{r['cfr_ytd']:.2f}" if r["cfr_ytd"] is not None else (f"{r['fot_ytd']:.2f}" if r["fot_ytd"] is not None else "-")
        low_str = f"{r['cfr_low']:.2f}" if r["cfr_low"] is not None else (f"{r['fot_low']:.2f}" if r["fot_low"] is not None else "-")
        high_str = f"{r['cfr_high']:.2f}" if r["cfr_high"] is not None else (f"{r['fot_high']:.2f}" if r["fot_high"] is not None else "-")
        md_lines.append(f"| {r['index_code']} | {r['fe_grade']} | {r['index_family']} | {fot_str} | {cfr_str} | {chg_str} | {mtd_str} | {ytd_str} | {low_str} | {high_str} |")
    md_lines.append("")

    with open(year_dir / f"{stem}.md", "w", encoding="utf-8") as mf:
        mf.write("\n".join(md_lines))

    # Write .tables.json sidecar
    with open(year_dir / f"{stem}.tables.json", "w", encoding="utf-8") as jf:
        json.dump({
            "issue_date": issue_date,
            "year": year,
            "title": title,
            "source_file": fname,
            "records_count": len(records),
            "records": records
        }, jf, indent=2, ensure_ascii=False)

    summary = {
        "issue_date": issue_date,
        "year": year,
        "filename": fname,
        "records_count": len(records),
    }
    return summary, records, commentary


async def run_all_async(limit: Optional[int] = None) -> Dict[str, Any]:
    OUT_MD_DIR.mkdir(parents=True, exist_ok=True)
    OUT_SERIES_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    sem = asyncio.Semaphore(8)

    html_files = sorted(list(INPUT_DIR.glob("**/*mmi-daily-iron-ore-index-report*.html")))
    if limit:
        html_files = html_files[:limit]
    print(f"=== Starting MMi Daily Iron Ore Extraction ({len(html_files)} reports) ===", flush=True)

    t0 = time.time()
    counter = 0
    total = len(html_files)

    async def worker(hp):
        nonlocal counter
        res = await process_iron_ore_item_async(hp, sem)
        counter += 1
        if counter % 10 == 0 or counter == total:
            print(f"[{counter}/{total}] ({counter/total*100:.1f}%) Processed {hp.name} in {round(time.time() - t0, 1)}s", flush=True)
        return res

    tasks = [worker(hp) for hp in html_files]
    results = await asyncio.gather(*tasks)

    all_table_records: List[Dict[str, Any]] = []
    all_commentaries: List[Dict[str, Any]] = []
    report_summaries: List[Dict[str, Any]] = []

    for summary, recs, comm in results:
        all_table_records.extend(recs)
        if comm:
            all_commentaries.append({
                "issue_date": summary["issue_date"],
                "commentary": comm,
                "source_file": summary["filename"]
            })
        report_summaries.append(summary)

    # Write data/extracted/series/hellenic_iron_ore_table_series.csv
    cols = [
        "issue_date", "index_family", "index_code", "fe_grade",
        "fot_rmb_wmt", "fot_change", "fot_change_pct", "fot_mtd", "fot_ytd", "fot_low", "fot_high",
        "cfr_usd_dmt", "cfr_change", "cfr_change_pct", "cfr_mtd", "cfr_ytd", "cfr_low", "cfr_high",
        "source_file"
    ]
    table_csv = OUT_SERIES_DIR / "hellenic_iron_ore_table_series.csv"
    with open(table_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        for r in sorted(all_table_records, key=lambda x: (x["issue_date"], x["index_family"], x["index_code"])):
            writer.writerow(r)
    print(f"\nWritten {len(all_table_records)} total rows to {table_csv}")

    # Write data/extracted/series/hellenic_iron_ore_commentary_series.csv
    comm_csv = OUT_SERIES_DIR / "hellenic_iron_ore_commentary_series.csv"
    with open(comm_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["issue_date", "commentary", "source_file"])
        writer.writeheader()
        for c in sorted(all_commentaries, key=lambda x: x["issue_date"]):
            writer.writerow(c)
    print(f"Written {len(all_commentaries)} total commentaries to {comm_csv}")

    state = {
        "reports_processed": len(report_summaries),
        "table_observations": len(all_table_records),
        "commentaries_count": len(all_commentaries),
        "elapsed_seconds": round(time.time() - t0, 1)
    }
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

    return state


if __name__ == "__main__":
    lim = None
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == "--limit" and len(sys.argv) > 2:
            lim = int(sys.argv[2])
        elif arg.isdigit():
            lim = int(arg)
    state = asyncio.run(run_all_async(limit=lim))
    print("MMi Iron Ore Extraction Complete. State:", json.dumps(state, indent=2))
