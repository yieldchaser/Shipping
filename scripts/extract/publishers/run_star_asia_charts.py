"""
Star Asia LDT Comparison and Regional Visual Chart Pipeline.

Uses LlamaParse (agentic tier) to extract embedded image charts:
  - Page with "COMPARISON OF TOTAL LIGHT DISPLACEMENT TONNAGE (LDT) SOLD 5 YEARS"
  - Location: Alang, Chattogram, Pakistan across 2022-2026
  - Insights Alang narrative commentary

Outputs:
  - data/extracted/llamaparse_star_asia/<stem>.md
  - data/extracted/series/star_asia_ldt_comparison_series.csv
"""

from __future__ import annotations

import csv
import glob
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pymupdf
from llama_parse import LlamaParse

ROOT = Path(__file__).resolve().parents[3]
PUB = "star_asia"
CORPUS_DIR = ROOT / "corpus" / "01-brokers" / PUB
OUT_DIR = ROOT / "data" / "extracted" / "llamaparse_star_asia"
OUT_SERIES = ROOT / "data" / "extracted" / "series"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_SERIES.mkdir(parents=True, exist_ok=True)

SERIES_CSV = OUT_SERIES / "star_asia_ldt_comparison_series.csv"
STATE_FILE = OUT_DIR / "_run_state.json"
API_KEY = os.environ.get("LLAMA_CLOUD_API_KEY", "llx-AVMBvb0UULqQGzWhFFJScQpwhrTM8hSVMZvjz4PEGQ9utg1P")


def load_state() -> Dict[str, Any]:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"done": {}, "failed": {}, "pages_parsed": 0, "credits_estimated": 0}


def save_state(state: Dict[str, Any]):
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def extract_meta(doc: pymupdf.Document, pdf_path: Path) -> Tuple[int, str]:
    fn = pdf_path.stem
    m_wk = re.search(r"week[_\-\s]*(\d{1,2})", fn, re.I) or re.search(r"W(\d{1,2})", fn, re.I)
    wk = int(m_wk.group(1)) if m_wk else 0

    p1 = doc[0].get_text()
    MONTHS = {
        "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
        "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
    }
    dt = None
    for line in p1.splitlines()[:25]:
        cleaned = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", line, flags=re.I)
        m = re.search(r"([A-Za-z]+)\s+(\d{1,2}),?\s+(202\d)", cleaned)
        if m and m.group(1).lower() in MONTHS:
            mo = MONTHS[m.group(1).lower()]
            da = int(m.group(2))
            yr = int(m.group(3))
            dt = f"{yr:04d}-{mo:02d}-{da:02d}"
            break
        m2 = re.search(r"(\d{1,2})\s+([A-Za-z]+),?\s+(202\d)", cleaned)
        if m2 and m2.group(2).lower() in MONTHS:
            da = int(m2.group(1))
            mo = MONTHS[m2.group(2).lower()]
            yr = int(m2.group(3))
            dt = f"{yr:04d}-{mo:02d}-{da:02d}"
            break

    if not dt:
        m_dt = re.search(r"(\d{2})_(\d{2})_(202\d)", fn)
        if m_dt:
            d, m, y = int(m_dt.group(1)), int(m_dt.group(2)), int(m_dt.group(3))
            dt = f"{y:04d}-{m:02d}-{d:02d}"
        else:
            dt = "2026-00-00"
    return wk, dt


def parse_ldt_table_from_md(md_text: str, issue_date: str, report_week: int, source_file: str) -> List[Dict[str, Any]]:
    rows = []
    lines = md_text.splitlines()
    in_table = False
    header = []

    for l in lines:
        line = l.strip()
        if not line:
            continue
        if "|" in line:
            parts = [p.strip() for p in line.split("|")[1:-1]]
            if not parts:
                continue
            if any(k in p.upper() for k in ["LOCATION", "REGION", "CATEGORY"] for p in parts) or any(re.search(r"\b202\d\b", p) for p in parts):
                if not header and sum(1 for p in parts if re.search(r"\b202\d\b", p)) >= 3:
                    header = [p.strip().upper() for p in parts]
                    in_table = True
                    continue
            if in_table and set(line.replace("|", "").strip()) <= {"-", ":", " "}:
                continue
            if in_table and len(parts) >= 2:
                loc = parts[0].strip().upper()
                if not any(loc_kw in loc for loc_kw in ["ALANG", "CHATTOGRAM", "PAKISTAN", "BANGLADESH", "INDIA"]):
                    if "LOCATION" in loc or "---" in loc:
                        continue
                    in_table = False
                    continue
                # Map years from header
                for col_idx in range(1, min(len(parts), len(header))):
                    yr_m = re.search(r"(202\d)", header[col_idx])
                    if yr_m:
                        yr_val = int(yr_m.group(1))
                        num_clean = re.sub(r"[^\d.]", "", parts[col_idx])
                        if num_clean:
                            val = float(num_clean)
                            rows.append({
                                "issue_date": issue_date,
                                "report_week": report_week,
                                "location": loc,
                                "year": yr_val,
                                "ldt_tonnage": val,
                                "source_file": source_file,
                            })

    return rows


def run_all(limit: int = 0):
    files = sorted(glob.glob(str(CORPUS_DIR / "2026" / "*.pdf")))
    print(f"Targeting {len(files)} Star Asia 2026 reports for chart extraction...")

    state = load_state()
    parser = LlamaParse(
        api_key=API_KEY,
        result_type="markdown",
        tier="agentic",
        version="latest",
        verbose=False,
    )

    all_series_rows = []
    processed_count = 0

    for pdf_str in files:
        if limit and processed_count >= limit:
            break
        pdf_path = Path(pdf_str)
        doc = pymupdf.open(pdf_path)
        stem = pdf_path.stem
        wk, dt = extract_meta(doc, pdf_path)
        # Find Alang page (which contains the 5Y LDT Comparison bar chart)
        target_pno = None
        for pno, pg in enumerate(doc):
            t = pg.get_text()
            if "Insights" in t and "Alang" in t:
                target_pno = pno
                break
        if target_pno is None:
            continue

        out_md = OUT_DIR / f"{stem}.md"
        md_text = ""

        if stem in state["done"] and out_md.exists() and out_md.stat().st_size > 100:
            md_text = out_md.read_text(encoding="utf-8")
        else:
            try:
                parser.target_pages = str(target_pno)
                docs = parser.load_data(str(pdf_path))
                if docs:
                    md_text = docs[0].text
                    out_md.write_text(md_text, encoding="utf-8")
                    state["done"][stem] = {
                        "page": target_pno + 1,
                        "bytes": len(md_text),
                        "status": "ok",
                    }
                    state["pages_parsed"] += 1
                    state["credits_estimated"] += 25
                    save_state(state)
                    processed_count += 1
                    print(f"[{processed_count}] Parsed {stem} p.{target_pno+1} ({len(md_text)} chars)")
            except Exception as e:
                err_str = str(e)
                print(f"Error on {stem}: {err_str[:120]}")
                state["failed"][stem] = err_str[:200]
                save_state(state)
                if any(k in err_str.lower() for k in ["429", "quota", "credit", "payment", "rate limit"]):
                    print("LlamaParse credit limit reached! Stopping.")
                    break

        # Parse extracted markdown table
        if md_text:
            extracted_rows = parse_ldt_table_from_md(md_text, dt, wk, pdf_path.name)
            all_series_rows.extend(extracted_rows)

    print(f"Total LDT comparison rows extracted: {len(all_series_rows)}")

    if all_series_rows:
        fields = ["issue_date", "report_week", "location", "year", "ldt_tonnage", "source_file"]
        with open(SERIES_CSV, "w", newline="", encoding="utf-8") as fp:
            writer = csv.DictWriter(fp, fieldnames=fields)
            writer.writeheader()
            writer.writerows(all_series_rows)
        print(f"Exported {len(all_series_rows)} rows to {SERIES_CSV.name}")


if __name__ == "__main__":
    run_all()
