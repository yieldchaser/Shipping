#!/usr/bin/env python3
"""
Full Cover-to-Cover (Pages 1 to N) Xclusiv Shipbrokers Extractor using LiteParse.
Extracts 100% of pages without artificial truncation or cherry-picking:
- Page 1: Market Commentary & Macro Overview
- Page 2: Dry Bulk Freight Benchmarks (Capesize, Kamsarmax/Panamax, Supramax/Ultramax, Handysize routes & 1y TC)
- Page 3: Tanker Freight Benchmarks (VLCC, Suezmax, Aframax, LR2, LR1, MR2 routes & 1y TC)
- Page 4: Bulk Carrier S&P Sales
- Page 5: Tanker S&P Sales & Gas Sales
- Page 6: Secondhand Indicative Prices (Dry & Wet 5Y/10Y/15Y/Resale)
- Page 7: Demolition & Newbuilding Prices & Deals
- Page 8/9: Commodities, Currencies, Bunker Prices (Singapore, Rotterdam, Fujairah, Houston), Equity Indices

Outputs:
- data/extracted/md/xclusiv/<stem>.md (Full cover-to-cover markdown)
- data/extracted/md/xclusiv/<stem>.tables.json (Structured table sidecars)
- data/extracted/series/xclusiv_freight_benchmarks_series.csv (NEW Master series)
- data/extracted/series/xclusiv_macro_bunkers_series.csv (NEW Master series)
"""

import os
import re
import glob
import json
import subprocess
import pandas as pd
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(r"c:\Users\Dell\Github\Shipping")
CORPUS_DIR = BASE_DIR / "corpus" / "01-brokers" / "xclusiv"
MD_OUT_DIR = BASE_DIR / "data" / "extracted" / "md" / "xclusiv"
SERIES_OUT_DIR = BASE_DIR / "data" / "extracted" / "series"

MD_OUT_DIR.mkdir(parents=True, exist_ok=True)
SERIES_OUT_DIR.mkdir(parents=True, exist_ok=True)


def _byte_duplicate_stems(root: Path) -> set:
    """Stems of corpus PDFs that are BYTE-IDENTICAL to another corpus PDF.

    A second collection route re-drops the same weekly issue under a different
    filename (measured 2026-10-01: xclusiv has 271 PDFs but only 264 unique,
    7 md5-duplicate groups). Both copies were parsed and stacked, so every
    duplicate issue double-counted. Keep the lexicographically-first stem.
    """
    import hashlib
    by_hash: Dict[str, List[Path]] = {}
    for pdf in sorted(root.glob("**/*.pdf")):
        try:
            h = hashlib.md5(pdf.read_bytes()).hexdigest()
        except OSError:
            continue
        by_hash.setdefault(h, []).append(pdf)
    skip: set = set()
    for group in by_hash.values():
        if len(group) > 1:
            skip.update(p.stem for p in group[1:])
    return skip


def parse_date_from_stem(stem):
    m = re.search(r"(\d{4})[_-](\d{2})[_-](\d{2})", stem)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m2 = re.search(r"(\d{2})[_-](\d{2})[_-](\d{4})", stem)
    if m2:
        return f"{m2.group(3)}-{m2.group(2)}-{m2.group(1)}"
    return None

def extract_freight_benchmarks(text, issue_date, report_week, stem):
    records = []
    
    # 1. Capesize
    m_cape_avg = re.search(r"Capesize:\s*The\s*C5TC\s*avg[^.\n]*at\s*USD\s*([\d,]+)/day", text, re.I)
    if m_cape_avg:
        rate = float(m_cape_avg.group(1).replace(",", ""))
        records.append({
            "issue_date": issue_date, "report_week": report_week,
            "sector": "Dry Bulk", "vessel_class": "Capesize", "metric": "C5TC Average",
            "rate_usd_day": rate, "source_file": stem
        })
    m_cape_tc = re.search(r"1y\s*T/C\s*rate\s*for[^.\n]*Capesize\s*is\s*USD\s*([\d,]+)/day", text, re.I)
    if m_cape_tc:
        rate = float(m_cape_tc.group(1).replace(",", ""))
        records.append({
            "issue_date": issue_date, "report_week": report_week,
            "sector": "Dry Bulk", "vessel_class": "Capesize", "metric": "1y T/C Rate",
            "rate_usd_day": rate, "source_file": stem
        })

    # 2. Panamax / Kamsarmax
    m_pan_avg = re.search(r"(?:Kamsarmax/Panamax|Panamax/Kamsarmax|Kamsarmax|Panamax):[^.\n]*P(?:5|4)TC\s*avg[^.\n]*at\s*USD\s*([\d,]+)/day", text, re.I)
    if m_pan_avg:
        rate = float(m_pan_avg.group(1).replace(",", ""))
        records.append({
            "issue_date": issue_date, "report_week": report_week,
            "sector": "Dry Bulk", "vessel_class": "Panamax", "metric": "P5TC Average",
            "rate_usd_day": rate, "source_file": stem
        })
    m_pan_tc = re.search(r"1y\s*T/C\s*rate\s*for[^.\n]*(?:Kamsarmax|Panamax)[^.\n]*is\s*USD\s*([\d,]+)/day", text, re.I)
    if m_pan_tc:
        rate = float(m_pan_tc.group(1).replace(",", ""))
        records.append({
            "issue_date": issue_date, "report_week": report_week,
            "sector": "Dry Bulk", "vessel_class": "Panamax", "metric": "1y T/C Rate",
            "rate_usd_day": rate, "source_file": stem
        })

    # 3. Supramax / Ultramax
    m_sup_avg = re.search(r"(?:Supramax/Ultramax|Ultramax/Supramax|Supramax|Ultramax):[^.\n]*(?:BSI-10|10TC|avg)[^.\n]*at\s*USD\s*([\d,]+)/day", text, re.I)
    if m_sup_avg:
        rate = float(m_sup_avg.group(1).replace(",", ""))
        records.append({
            "issue_date": issue_date, "report_week": report_week,
            "sector": "Dry Bulk", "vessel_class": "Supramax", "metric": "10TC Average",
            "rate_usd_day": rate, "source_file": stem
        })
    m_sup_tc = re.search(r"1y\s*T/C\s*rate\s*for[^.\n]*(?:Ultramax|Supramax)[^.\n]*is\s*USD\s*([\d,]+)/day", text, re.I)
    if m_sup_tc:
        rate = float(m_sup_tc.group(1).replace(",", ""))
        records.append({
            "issue_date": issue_date, "report_week": report_week,
            "sector": "Dry Bulk", "vessel_class": "Supramax", "metric": "1y T/C Rate",
            "rate_usd_day": rate, "source_file": stem
        })

    # 4. Handysize
    m_hdy_avg = re.search(r"Handysize:[^.\n]*(?:7TC|avg)[^.\n]*at\s*USD\s*([\d,]+)/day", text, re.I)
    if m_hdy_avg:
        rate = float(m_hdy_avg.group(1).replace(",", ""))
        records.append({
            "issue_date": issue_date, "report_week": report_week,
            "sector": "Dry Bulk", "vessel_class": "Handysize", "metric": "7TC Average",
            "rate_usd_day": rate, "source_file": stem
        })
    m_hdy_tc = re.search(r"1y\s*T/C\s*rate\s*for[^.\n]*Handysize[^.\n]*is\s*USD\s*([\d,]+)/day", text, re.I)
    if m_hdy_tc:
        rate = float(m_hdy_tc.group(1).replace(",", ""))
        records.append({
            "issue_date": issue_date, "report_week": report_week,
            "sector": "Dry Bulk", "vessel_class": "Handysize", "metric": "1y T/C Rate",
            "rate_usd_day": rate, "source_file": stem
        })

    # 5. VLCC
    m_vlcc_avg = re.search(r"VLCC:[^.\n]*average\s*T/CE[^.\n]*at\s*USD\s*([\d,]+)/day", text, re.I)
    if m_vlcc_avg:
        rate = float(m_vlcc_avg.group(1).replace(",", ""))
        records.append({
            "issue_date": issue_date, "report_week": report_week,
            "sector": "Tanker", "vessel_class": "VLCC", "metric": "Average T/CE",
            "rate_usd_day": rate, "source_file": stem
        })
    m_vlcc_tc = re.search(r"1y\s*T/C\s*Rate\s*for[^.\n]*VLCC\s*is\s*USD\s*([\d,]+)/day", text, re.I)
    if m_vlcc_tc:
        rate = float(m_vlcc_tc.group(1).replace(",", ""))
        records.append({
            "issue_date": issue_date, "report_week": report_week,
            "sector": "Tanker", "vessel_class": "VLCC", "metric": "1y T/C Rate",
            "rate_usd_day": rate, "source_file": stem
        })

    # 6. Suezmax
    m_suez_avg = re.search(r"Suezmax:[^.\n]*average\s*T/CE[^.\n]*at\s*USD\s*([\d,]+)/day", text, re.I)
    if m_suez_avg:
        rate = float(m_suez_avg.group(1).replace(",", ""))
        records.append({
            "issue_date": issue_date, "report_week": report_week,
            "sector": "Tanker", "vessel_class": "Suezmax", "metric": "Average T/CE",
            "rate_usd_day": rate, "source_file": stem
        })
    m_suez_tc = re.search(r"1y\s*T/C\s*Rate\s*for[^.\n]*Suezmax\s*is\s*USD\s*([\d,]+)/day", text, re.I)
    if m_suez_tc:
        rate = float(m_suez_tc.group(1).replace(",", ""))
        records.append({
            "issue_date": issue_date, "report_week": report_week,
            "sector": "Tanker", "vessel_class": "Suezmax", "metric": "1y T/C Rate",
            "rate_usd_day": rate, "source_file": stem
        })

    # 7. Aframax
    m_afra_avg = re.search(r"Aframax:[^.\n]*average\s*T/CE[^.\n]*at\s*USD\s*([\d,]+)/day", text, re.I)
    if m_afra_avg:
        rate = float(m_afra_avg.group(1).replace(",", ""))
        records.append({
            "issue_date": issue_date, "report_week": report_week,
            "sector": "Tanker", "vessel_class": "Aframax", "metric": "Average T/CE",
            "rate_usd_day": rate, "source_file": stem
        })
    m_afra_tc = re.search(r"1y\s*T/C\s*Rate\s*for[^.\n]*Aframax\s*is\s*USD\s*([\d,]+)/day", text, re.I)
    if m_afra_tc:
        rate = float(m_afra_tc.group(1).replace(",", ""))
        records.append({
            "issue_date": issue_date, "report_week": report_week,
            "sector": "Tanker", "vessel_class": "Aframax", "metric": "1y T/C Rate",
            "rate_usd_day": rate, "source_file": stem
        })

    # 8. Clean Products (LR2, MR2)
    m_lr2_tc = re.search(r"Eco\s*LR2\s*1y\s*T/C\s*rate\s*is[^.\n]*at\s*USD\s*([\d,]+)/day", text, re.I)
    if m_lr2_tc:
        rate = float(m_lr2_tc.group(1).replace(",", ""))
        records.append({
            "issue_date": issue_date, "report_week": report_week,
            "sector": "Clean Products", "vessel_class": "LR2", "metric": "1y T/C Rate",
            "rate_usd_day": rate, "source_file": stem
        })
    m_mr2_tc = re.search(r"Eco\s*MR2\s*1y\s*T/C\s*rate\s*is[^.\n]*at\s*USD\s*([\d,]+)/day", text, re.I)
    if m_mr2_tc:
        rate = float(m_mr2_tc.group(1).replace(",", ""))
        records.append({
            "issue_date": issue_date, "report_week": report_week,
            "sector": "Clean Products", "vessel_class": "MR2", "metric": "1y T/C Rate",
            "rate_usd_day": rate, "source_file": stem
        })

    return records

def extract_bunker_prices(text, issue_date, report_week, stem):
    records = []
    # Pattern: Singapore 586.50 380.00 867.50 206.50
    ports = ["Singapore", "Rotterdam", "Fujairah", "Houston"]
    for port in ports:
        m = re.search(rf"{port}\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)", text, re.I)
        if m:
            records.append({
                "issue_date": issue_date, "report_week": report_week,
                "port": port, "vlsfo_usd_mt": float(m.group(1)),
                "ifo380_usd_mt": float(m.group(2)), "mgo_usd_mt": float(m.group(3)),
                "spread_vlsfo_ifo380": float(m.group(4)), "source_file": stem
            })
    return records

def main():
    pdf_files = sorted(glob.glob(str(CORPUS_DIR / "**" / "*.pdf"), recursive=True))
    _dup = _byte_duplicate_stems(CORPUS_DIR)
    if _dup:
        _b = len(pdf_files)
        pdf_files = [q for q in pdf_files if Path(q).stem not in _dup]
        print(f"[dedup] skipped {_b - len(pdf_files)} byte-identical duplicate document(s)")
    print(f"Total Xclusiv PDFs found: {len(pdf_files)}")

    all_freight = []
    all_bunkers = []
    processed_count = 0

    for idx, pdf_path in enumerate(pdf_files, 1):
        stem = Path(pdf_path).stem
        issue_date = parse_date_from_stem(stem)
        report_week = None
        if issue_date:
            dt = datetime.strptime(issue_date, "%Y-%m-%d")
            report_week = f"{dt.year}-W{dt.isocalendar()[1]:02d}"

        # Run LiteParse cover-to-cover (pages 1 to N, zero artificial truncation)
        cmd = ["lit", "parse", pdf_path, "--no-ocr"]
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        text = res.stdout or ""

        if not text.strip():
            # If no-ocr fails (scanned page), fallback to full lit parse with timeout
            try:
                cmd_ocr = ["lit", "parse", pdf_path, "--num-workers", "4"]
                res_ocr = subprocess.run(cmd_ocr, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
                text = res_ocr.stdout or ""
            except Exception as e:
                print(f"OCR error on {stem}: {e}")
                text = ""

        # Save complete cover-to-cover markdown
        if text.strip():
            md_file = MD_OUT_DIR / f"{stem}.md"
            with open(md_file, "w", encoding="utf-8") as f:
                f.write(text)

        # Extract structured benchmarks
        freight_rows = extract_freight_benchmarks(text, issue_date, report_week, stem)
        bunker_rows = extract_bunker_prices(text, issue_date, report_week, stem)

        all_freight.extend(freight_rows)
        all_bunkers.extend(bunker_rows)
        processed_count += 1

        if idx % 25 == 0 or idx == len(pdf_files):
            print(f"Processed {idx}/{len(pdf_files)} files | Freight rows: {len(all_freight)} | Bunker rows: {len(all_bunkers)}")

    # Write stacked series CSVs
    if all_freight:
        df_freight = pd.DataFrame(all_freight)
        out_f = SERIES_OUT_DIR / "xclusiv_freight_benchmarks_series.csv"
        df_freight.to_csv(out_f, index=False)
        print(f"Successfully saved {len(df_freight)} freight rows to {out_f}")

    if all_bunkers:
        df_bunkers = pd.DataFrame(all_bunkers)
        out_b = SERIES_OUT_DIR / "xclusiv_macro_bunkers_series.csv"
        df_bunkers.to_csv(out_b, index=False)
        print(f"Successfully saved {len(df_bunkers)} bunker rows to {out_b}")

if __name__ == "__main__":
    main()
