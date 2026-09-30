"""
Star Asia Demolition and S&P Table Extraction Pipeline.

Extracts weekly market tables from Star Asia Shipbroking reports across 2022-2026:
1. Indicative Demolition Prices ($/LDT) across Bangladesh, India, Pakistan, Turkey
   for Tankers, Bulkers, General Cargo (MPP), Containers (resolving the Gaddani/Turkey boundary merge).
2. Demolition Deals:
   - Reported Demolition Sales / Fixtures (Vessel Name, Type, LDT, Price $/LDT, Built, Commercial Terms)
   - Anchorage & Beaching Deals (Vessel Name, Type, LDT, Arrival Date, Beaching Date, Yard/Country)
3. Second-Hand S&P Sales (Dry Bulk, Tankers, Containers)

Outputs:
  - Updates table sidecars in data/extracted/md/star_asia/<stem>.tables.json with stamped
    issue_date, report_week, source_file, and clean 4-destination indicative tables.
  - data/extracted/series/star_asia_demolition_series.csv
  - data/extracted/series/star_asia_deals_series.csv
  - data/extracted/series/star_asia_snp_sales_series.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pymupdf

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "extract" / "publishers"))
import star_asia as S
import star_asia_dates as SAD

PUB = "star_asia"
CORPUS_DIR = ROOT / "corpus" / "01-brokers" / PUB
OUT_MD = ROOT / "data" / "extracted" / "md" / PUB
OUT_SERIES = ROOT / "data" / "extracted" / "series"

DEMO_SERIES_CSV = OUT_SERIES / "star_asia_demolition_series.csv"
DEALS_SERIES_CSV = OUT_SERIES / "star_asia_deals_series.csv"
SNP_SERIES_CSV = OUT_SERIES / "star_asia_snp_sales_series.csv"

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}

KNOWN_TYPES = {
    "CAPE", "CAPESIZE", "VLCC", "SUEZMAX", "AFRAMAX", "PANAMAX", "KAMSARMAX",
    "HANDY", "HANDYSIZE", "SUPRAMAX", "ULTRAMAX", "BULKER", "TANKER",
    "CONTAINER", "REEFER", "RORO", "RO-RO", "LPG", "LNG", "LNGC",
    "CHEMICAL TANKER", "PROD / CHEM", "OFFSHORE", "WOODCHIP", "TUG", "BARGE",
    "GENERAL CARGO", "GEN. CARGO", "FSO", "FPSO", "CRUISE", "PASSENGER",
    "FISHING", "CEMENT", "CAR CARRIER", "VEHICLE", "PCC", "LPG TANKER", "RIG",
}


def clean_ord(s: str) -> str:
    """Strip ordinal suffixes like 1st, 2nd, 3rd, 4th."""
    return re.sub(r"(\d+)(st|nd|rd|th)", r"\1", s, flags=re.I)


def extract_meta(doc: pymupdf.Document, pdf_path: Path) -> Tuple[int, str]:
    """Extract report week integer and ISO issue_date (YYYY-MM-DD)."""
    p1 = doc[0].get_text()
    m_wk = re.search(r"WEEK\s*(\d{1,2})", p1, re.I)
    week = int(m_wk.group(1)) if m_wk else None
    if week is None:
        m_fn_wk = re.search(r"week[_\-\s]*(\d{1,2})", pdf_path.name, re.I) or re.search(r"W(\d{1,2})", pdf_path.name, re.I)
        if m_fn_wk:
            week = int(m_fn_wk.group(1))

    dt = None
    for line in p1.splitlines()[:25]:
        cleaned = clean_ord(line)
        # Month Day, Year
        m = re.search(r"([A-Za-z]+)\s+(\d{1,2}),?\s+(202\d)", cleaned)
        if m and m.group(1).lower() in MONTHS:
            mo = MONTHS[m.group(1).lower()]
            da = int(m.group(2))
            yr = int(m.group(3))
            dt = f"{yr:04d}-{mo:02d}-{da:02d}"
            break
        # Day Month Year
        m2 = re.search(r"(\d{1,2})\s+([A-Za-z]+),?\s+(202\d)", cleaned)
        if m2 and m2.group(2).lower() in MONTHS:
            da = int(m2.group(1))
            mo = MONTHS[m2.group(2).lower()]
            yr = int(m2.group(3))
            dt = f"{yr:04d}-{mo:02d}-{da:02d}"
            break
        # DD.MM.YYYY
        m3 = re.search(r"(\d{1,2})[./\-](\d{1,2})[./\-](202\d)", cleaned)
        if m3:
            da, mo, yr = int(m3.group(1)), int(m3.group(2)), int(m3.group(3))
            if 1 <= mo <= 12 and 1 <= da <= 31:
                dt = f"{yr:04d}-{mo:02d}-{da:02d}"
                break

    if dt is None:
        m_fn_dt = re.search(r"(\d{2})_(\d{2})_(202\d)", pdf_path.name)
        if m_fn_dt:
            da, mo, yr = int(m_fn_dt.group(1)), int(m_fn_dt.group(2)), int(m_fn_dt.group(3))
            dt = f"{yr:04d}-{mo:02d}-{da:02d}"

    # Edge cases (e.g. misplaced ISM reports)
    if dt is None and "2024_W05_ISM" in pdf_path.name:
        dt, week = "2024-02-02", 5
    elif dt is None and "2024_W10_ISM" in pdf_path.name:
        dt, week = "2024-03-08", 10

    return week or 0, dt or "2026-00-00"


def parse_price_range(cell_str: Any) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """Parse a scrap price cell string into (low, high, mid).
    
    Star Asia formats: '540 ~ 550', '$500-510', '$520 - 530', '520 ~530', '485', etc.
    """
    if not cell_str:
        return None, None, None
    s = str(cell_str).replace(",", "")
    nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", s)]
    prices = [n for n in nums if 150 <= n <= 1000]
    if len(prices) >= 2:
        return prices[0], prices[1], round((prices[0] + prices[1]) / 2.0, 2)
    elif len(prices) == 1:
        return prices[0], prices[0], prices[0]
    return None, None, None


def parse_clean_num(v: Any) -> Optional[float]:
    """Parse generic US/ISO numeric cell."""
    if v is None:
        return None
    s = str(v).replace("$", "").replace("US", "").replace("/LDT", "").replace("MT", "").replace(",", "").strip()
    m = re.search(r"\d+(?:\.\d+)?", s)
    return float(m.group(0)) if m else None


def parse_year_built(s: Any) -> Tuple[Optional[int], Optional[str]]:
    """Parse 'YEAR / BUILT' cell like '1999 / JAPAN' or '1992'."""
    if not s:
        return None, None
    s = str(s).strip()
    parts = s.split("/")
    m_yr = re.search(r"(19\d\d|20\d\d)", parts[0])
    yr = int(m_yr.group(0)) if m_yr else None
    cty = parts[1].strip() if len(parts) > 1 else None
    return yr, cty


def extract_indicative_scrap_table(
    doc: pymupdf.Document, issue_date: str, report_week: int, pdf_name: str
) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Extract indicative scrap prices for all 4 destinations.
    
    Resolves the Gaddani / Turkey boundary defect cleanly.
    Returns:
      (series_records, clean_table_dict_for_sidecar)
    """
    records = []
    clean_table = None

    DEST_SPECS = [
        ("India", "Alang, India", ["ALANG", "INDIA"]),
        ("Bangladesh", "Chattogram, Bangladesh", ["CHATTOGRAM", "BANGLADESH"]),
        ("Pakistan", "Gaddani, Pakistan", ["GADDANI", "GADANI", "PAKISTAN"]),
        ("Turkey", "Aliaga, Turkey", ["TURKEY", "ALIAGA"]),
    ]
    SEGMENTS = ["Tankers", "Bulkers", "General Cargo", "Containers"]

    for pg in doc:
        txt = pg.get_text()
        if any(k in txt.upper() for k in ["SHIP RECYCLING MARKET SNAPSHOT", "CURRENT MARKET SNAPSHOT"]):
            for tab in pg.find_tables():
                ext = tab.extract()
                rows_by_dest: Dict[str, Tuple[str, List[Tuple[float, float, float]], str]] = {}
                
                for r in ext:
                    if not r:
                        continue
                    row_txt = " ".join(str(c or "") for c in r).upper()
                    
                    matched_dest = None
                    for cty, full_dest, keywords in DEST_SPECS:
                        if cty in rows_by_dest:
                            continue
                        if any(kw in row_txt for kw in keywords) and "DESTINATION" not in row_txt:
                            matched_dest = (cty, full_dest)
                            break
                    
                    if matched_dest:
                        cty, full_dest = matched_dest
                        # Parse prices and sentiment
                        price_triplets = []
                        sentiment = ""
                        for cell in r:
                            if not cell:
                                continue
                            cs = str(cell).strip()
                            pl, ph, pm = parse_price_range(cs)
                            if pl is not None:
                                price_triplets.append((pl, ph, pm))
                            for s_word in ["STABLE", "WEAK", "IMPROVING", "FIRM", "BULLISH", "SLOW", "DULL"]:
                                if s_word in cs.upper() and not sentiment:
                                    sentiment = s_word
                        
                        if len(price_triplets) >= 4:
                            rows_by_dest[cty] = (full_dest, price_triplets[:4], sentiment)
                
                if len(rows_by_dest) == 4:
                    # Successfully parsed all 4 destinations!
                    sidecar_rows = []
                    for cty, full_dest, _ in DEST_SPECS:
                        fdest, triplets, sent = rows_by_dest[cty]
                        row_cells = [fdest]
                        for idx, seg in enumerate(SEGMENTS):
                            pl, ph, pm = triplets[idx]
                            p_str = f"${int(pl)}-{int(ph)}" if pl != ph else f"${int(pl)}"
                            row_cells.append(p_str)
                            records.append({
                                "issue_date": issue_date,
                                "report_week": report_week,
                                "destination": fdest,
                                "country": cty,
                                "segment": seg,
                                "price_low": pl,
                                "price_high": ph,
                                "price_usd_per_ldt": pm,
                                "sentiment": sent or "STABLE",
                                "source_file": pdf_name,
                            })
                        row_cells.append(sent or "STABLE /")
                        sidecar_rows.append(row_cells)

                    clean_table = {
                        "issue_date": issue_date,
                        "report_week": report_week,
                        "source_file": pdf_name,
                        "table_type": "indicative_scrap_prices",
                        "title": "Ship Recycling Market Snapshot (USD / LDT)",
                        "header": ["DESTINATION", "TANKERS", "BULKERS", "MPP/GENERAL CARGO", "CONTAINERS", "OUTLOOK / SENTIMENTS"],
                        "rows": sidecar_rows,
                        "repaired": True,
                    }
                    return records, clean_table

    return records, clean_table


def extract_demolition_deals(
    doc: pymupdf.Document, issue_date: str, report_week: int, pdf_name: str
) -> List[Dict[str, Any]]:
    """Extract Demolition Fixture Sales and Anchorage/Beaching Deals."""
    deals = []

    for pno, pg in enumerate(doc, 1):
        txt = pg.get_text()

        # 1. Reported Sales / Ships Sold for Recycling (Fixtures)
        if any(k in txt.upper() for k in ["SHIPS SOLD FOR RECYCLING", "REPORTED SALES"]) and "SECOND" not in txt.upper() and "DRY BULK" not in txt.upper() and "TANKER VALUES" not in txt.upper():
            for t in pg.find_tables():
                ext = t.extract()
                hdr_passed = False
                for r in ext:
                    if not r:
                        continue
                    r_str = " ".join(str(c or "") for c in r).upper()
                    if "VESSEL" in r_str and ("LDT" in r_str or "PRICE" in r_str):
                        hdr_passed = True
                        continue
                    if hdr_passed:
                        non_empty = [c for c in r if c and str(c).strip()]
                        if len(non_empty) >= 4 and any(ch.isalpha() for ch in str(non_empty[0])):
                            vsl = str(non_empty[0]).strip().replace("\n", " ")
                            if any(w in vsl.upper() for w in ["VESSEL", "PAGE", "TOTAL", "SOURCE", "PRICE", "5-YEAR", "HISTORICAL"]):
                                continue
                            
                            v_type = ""
                            v_ldt = None
                            v_yr = None
                            v_cty = ""
                            v_price = None
                            v_comments = ""

                            if len(non_empty) == 6:
                                v_comments = str(non_empty[5]).strip().replace("\n", " ")
                                v_price = parse_clean_num(non_empty[4])
                                middle = non_empty[1:4]
                                for m_cell in middle:
                                    ms = str(m_cell).strip().replace("\n", " ")
                                    mu = ms.upper()
                                    if re.search(r"\b(19\d\d|20\d\d)\b", ms) and ("/" in ms or len(ms) <= 6):
                                        v_yr, v_cty = parse_year_built(ms)
                                    elif any(t == mu or t in mu.split("/") for t in KNOWN_TYPES):
                                        v_type = ms
                                    else:
                                        num_val = parse_clean_num(ms)
                                        if num_val and num_val > 100:
                                            v_ldt = num_val
                                        elif not v_type:
                                            v_type = ms
                            elif len(non_empty) == 4:
                                v_ldt = parse_clean_num(non_empty[1])
                                v_yr, v_cty = parse_year_built(non_empty[2])
                                v_type = str(non_empty[3]).strip().replace("\n", " ")

                            # Destination yard inferred from comments if present
                            dest_yard = ""
                            comm_u = v_comments.upper()
                            if "CHATTOGRAM" in comm_u or "BANGLADESH" in comm_u:
                                dest_yard = "Chattogram, Bangladesh"
                            elif "ALANG" in comm_u or "INDIA" in comm_u:
                                dest_yard = "Alang, India"
                            elif "GADDANI" in comm_u or "PAKISTAN" in comm_u:
                                dest_yard = "Gaddani, Pakistan"
                            elif "ALIAGA" in comm_u or "TURKEY" in comm_u:
                                dest_yard = "Aliaga, Turkey"

                            deals.append({
                                "issue_date": issue_date,
                                "report_week": report_week,
                                "deal_type": "Reported Sale",
                                "vessel_name": vsl,
                                "vessel_type": v_type,
                                "ldt": v_ldt,
                                "price_usd_per_ldt": v_price,
                                "destination_yard": dest_yard,
                                "year_built": v_yr or "",
                                "built_country": v_cty or "",
                                "arrival_date": "",
                                "beaching_date": "",
                                "terms_comments": v_comments,
                                "source_file": pdf_name,
                            })

        # 2. Anchorage & Beaching Position
        if any(k in txt.upper() for k in ["BEACHING POSITION", "ANCHORAGE & BEACHING"]):
            cur_yard = ""
            for y in ["CHATTOGRAM, BANGLADESH", "CHATTOGRAM", "ALANG, INDIA", "ALANG", "GADDANI, PAKISTAN", "GADDANI", "ALIAGA, TURKEY", "ALIAGA"]:
                if y in txt.upper():
                    cur_yard = y.title()
                    if "Chattogram" in cur_yard: cur_yard = "Chattogram, Bangladesh"
                    elif "Alang" in cur_yard: cur_yard = "Alang, India"
                    elif "Gaddani" in cur_yard: cur_yard = "Gaddani, Pakistan"
                    elif "Aliaga" in cur_yard: cur_yard = "Aliaga, Turkey"
                    break

            for t in pg.find_tables():
                ext = t.extract()
                hdr_idx = None
                for idx, r in enumerate(ext):
                    if not r:
                        continue
                    r_str = " ".join(str(c or "") for c in r).upper()
                    if ("VESSEL" in r_str or "NAME" in r_str) and ("BEACHING" in r_str or "ARRIVAL" in r_str):
                        hdr_idx = idx
                        break
                if hdr_idx is not None:
                    for r in ext[hdr_idx + 1:]:
                        non_empty = [c for c in r if c and str(c).strip()]
                        if len(non_empty) >= 3:
                            vsl = str(non_empty[0]).strip().replace("\n", " ")
                            if any(ch.isalpha() for ch in vsl) and not any(w in vsl.upper() for w in ["VESSEL", "PAGE", "TOTAL", "BUNKER", "EXCHANGE", "PRICE"]):
                                v_type = str(non_empty[1]).strip().replace("\n", " ") if len(non_empty) > 1 else ""
                                v_ldt = parse_clean_num(non_empty[2]) if len(non_empty) > 2 else None
                                v_arr = str(non_empty[3]).strip().replace("\n", " ") if len(non_empty) > 3 else ""
                                v_beach = str(non_empty[4]).strip().replace("\n", " ") if len(non_empty) > 4 else ""
                                
                                deals.append({
                                    "issue_date": issue_date,
                                    "report_week": report_week,
                                    "deal_type": "Beaching / Arrival",
                                    "vessel_name": vsl,
                                    "vessel_type": v_type,
                                    "ldt": v_ldt,
                                    "price_usd_per_ldt": "",
                                    "destination_yard": cur_yard,
                                    "year_built": "",
                                    "built_country": "",
                                    "arrival_date": v_arr,
                                    "beaching_date": v_beach,
                                    "terms_comments": "",
                                    "source_file": pdf_name,
                                })

    return deals


def extract_snp_sales(
    tables_data: Any, issue_date: str, report_week: int, pdf_name: str
) -> List[Dict[str, Any]]:
    """Extract S&P Secondhand Sales from existing table sidecars."""
    snp_sales = []
    if isinstance(tables_data, dict):
        tables_data = tables_data.get("tables", [])
    if not isinstance(tables_data, list):
        return snp_sales
    for t in tables_data:
        if not isinstance(t, dict):
            continue
        hdr = [str(c).upper().strip() for c in t.get("header", [])]
        hdr_str = " ".join(hdr)
        if ("VESSEL NAME" in hdr_str or "VESSEL" in hdr_str) and "DWT" in hdr_str and ("PRICE" in hdr_str or "BUYER" in hdr_str):
            sec = t.get("title") or "Secondhand Sales"
            col_map = {}
            for idx, h in enumerate(hdr):
                if "VESSEL" in h: col_map["vsl"] = idx
                elif "TYPE" in h: col_map["type"] = idx
                elif "DWT" in h: col_map["dwt"] = idx
                elif "YEAR" in h: col_map["year"] = idx
                elif "BUILT" in h: col_map["built"] = idx
                elif "PRICE" in h: col_map["price"] = idx
                elif "BUYER" in h or "COMMENT" in h: col_map["comments"] = idx

            for r in t.get("rows", []):
                if not r or not any(r):
                    continue
                vsl = str(r[col_map["vsl"]] or "").strip().replace("\n", " ") if "vsl" in col_map and col_map["vsl"] < len(r) else ""
                if not vsl or not any(ch.isalpha() for ch in vsl) or any(w in vsl.upper() for w in ["VESSEL", "PAGE", "TOTAL", "SOURCE"]):
                    continue
                
                v_type = str(r[col_map["type"]] or "").strip().replace("\n", " ") if "type" in col_map and col_map["type"] < len(r) else ""
                v_dwt = parse_clean_num(r[col_map["dwt"]]) if "dwt" in col_map and col_map["dwt"] < len(r) else None
                v_yr = None
                if "year" in col_map and col_map["year"] < len(r):
                    m_yr = re.search(r"\b(19\d\d|20\d\d)\b", str(r[col_map["year"]]))
                    if m_yr: v_yr = int(m_yr.group(0))
                v_cty = str(r[col_map["built"]] or "").strip().replace("\n", " ") if "built" in col_map and col_map["built"] < len(r) else ""
                v_price = parse_clean_num(r[col_map["price"]]) if "price" in col_map and col_map["price"] < len(r) else None
                v_comm = str(r[col_map["comments"]] or "").strip().replace("\n", " ") if "comments" in col_map and col_map["comments"] < len(r) else ""

                snp_sales.append({
                    "issue_date": issue_date,
                    "report_week": report_week,
                    "section": sec,
                    "vessel_name": vsl,
                    "vessel_type": v_type,
                    "dwt": v_dwt,
                    "year_built": v_yr or "",
                    "built_country": v_cty,
                    "price_usd_mill": v_price,
                    "buyers_comments": v_comm,
                    "source_file": pdf_name,
                })
    return snp_sales


def classify_table_type(t: Dict[str, Any]) -> str:
    """Classify the functional purpose of a table."""
    hdr = " ".join(str(c).upper() for c in t.get("header", []))
    title = str(t.get("title") or "").upper()
    comb = hdr + " " + title
    if "RECYCLING MARKET SNAPSHOT" in comb or ("DESTINATION" in comb and "TANKER" in comb and "BULKER" in comb):
        return "indicative_scrap_prices"
    if "SHIPS SOLD FOR RECYCLING" in comb or ("VESSEL" in comb and "LDT" in comb and "PRICE" in comb and "DWT" not in comb):
        return "demolition_sales"
    if "BEACHING" in comb or "ANCHORAGE" in comb:
        return "beaching_position"
    if "5-YEAR" in comb and ("RECYCLING" in comb or "AVERAGE HISTORICAL" in comb):
        return "historical_scrap_prices"
    if ("VESSEL" in comb or "VESSEL NAME" in comb) and "DWT" in comb and ("PRICE" in comb or "BUYER" in comb):
        return "secondhand_sales"
    if "BUNKER" in comb or ("VLSFO" in comb and "MGO" in comb):
        return "bunkers"
    if "EXCHANGE" in comb or "CURRENCY" in comb:
        return "exchange_rates"
    if "COMMODITY" in comb or "IRON ORE" in comb:
        return "commodities"
    if "INDICES" in comb or "BDI" in comb or "BDTI" in comb:
        return "indices"
    return "market_data"


def process_star_asia_corpus() -> Dict[str, Any]:
    """Process all Star Asia reports, update sidecars, and stack series."""
    OUT_SERIES.mkdir(parents=True, exist_ok=True)
    OUT_MD.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(CORPUS_DIR.rglob("*.pdf"))
    print(f"Starting Star Asia extraction across {len(pdfs)} PDFs...")

    all_indicative_series: List[Dict[str, Any]] = []
    all_deals_series: List[Dict[str, Any]] = []
    all_snp_series: List[Dict[str, Any]] = []

    sidecars_updated = 0
    indicative_tables_repaired = 0

    for idx, pdf in enumerate(pdfs, 1):
        stem = pdf.stem
        year_str = pdf.parent.name if pdf.parent.name.isdigit() else "2026"
        target_dir = OUT_MD / year_str
        sidecar_path = target_dir / f"{stem}.tables.json"
        if not sidecar_path.exists() and (OUT_MD / f"{stem}.tables.json").exists():
            sidecar_path = OUT_MD / f"{stem}.tables.json"
        
        with pymupdf.open(pdf) as doc:
            report_week, issue_date = extract_meta(doc, pdf)

            # 1. Extract indicative scrap prices
            ind_records, clean_ind_table = extract_indicative_scrap_table(doc, issue_date, report_week, pdf.name)
            all_indicative_series.extend(ind_records)

            # 2. Extract demolition deals (fixtures & beachings)
            deals = extract_demolition_deals(doc, issue_date, report_week, pdf.name)
            all_deals_series.extend(SAD.normalise_deal_dates(d) for d in deals)

            # 3. Load and update existing sidecars
            tables_data = []
            if sidecar_path.exists():
                try:
                    loaded = json.loads(sidecar_path.read_text(encoding="utf-8"))
                    if isinstance(loaded, list):
                        tables_data = loaded
                    elif isinstance(loaded, dict) and "tables" in loaded:
                        tables_data = loaded["tables"]
                    elif isinstance(loaded, dict):
                        tables_data = [loaded]
                except Exception:
                    tables_data = []

            # 4. Extract S&P sales
            snp_records = extract_snp_sales(tables_data, issue_date, report_week, pdf.name)
            all_snp_series.extend(snp_records)

            # 5. Stamp metadata and repair sidecar tables
            new_tables = []
            has_indicative = False
            for t in tables_data:
                if not isinstance(t, dict):
                    continue
                t_type = classify_table_type(t)
                t["issue_date"] = issue_date
                t["report_week"] = report_week
                t["source_file"] = pdf.name
                t["table_type"] = t_type
                
                if t_type == "indicative_scrap_prices":
                    if clean_ind_table:
                        # Replace with clean 4-destination repaired table
                        new_tables.append(clean_ind_table)
                        indicative_tables_repaired += 1
                        has_indicative = True
                    else:
                        new_tables.append(t)
                else:
                    new_tables.append(t)

            if not has_indicative and clean_ind_table:
                new_tables.append(clean_ind_table)
                indicative_tables_repaired += 1

            # Save updated sidecar
            sidecar_path.parent.mkdir(parents=True, exist_ok=True)
            sidecar_path.write_text(json.dumps(new_tables, indent=2, ensure_ascii=False), encoding="utf-8")
            sidecars_updated += 1

        if idx % 25 == 0 or idx == len(pdfs):
            print(f"Processed {idx:>3}/{len(pdfs)} documents...")

    # Write Indicative Scrap Series CSV
    ind_headers = [
        "issue_date", "report_week", "destination", "country", "segment",
        "price_low", "price_high", "price_usd_per_ldt", "sentiment", "source_file"
    ]
    with open(DEMO_SERIES_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=ind_headers)
        writer.writeheader()
        writer.writerows(all_indicative_series)

    # Write Demolition Deals Series CSV
    deals_headers = [
        "issue_date", "report_week", "deal_type", "vessel_name", "vessel_type",
        "ldt", "price_usd_per_ldt", "destination_yard", "year_built", "built_country",
        "arrival_date", "beaching_date", "terms_comments", "source_file",
        "arrival_date_raw", "arrival_date_status", "arrival_date_note",
        "beaching_date_raw", "beaching_date_status", "beaching_date_note",
    ]
    with open(DEALS_SERIES_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=deals_headers)
        writer.writeheader()
        writer.writerows(all_deals_series)

    # Write S&P Secondhand Sales Series CSV
    snp_headers = [
        "issue_date", "report_week", "section", "vessel_name", "vessel_type",
        "dwt", "year_built", "built_country", "price_usd_mill", "buyers_comments", "source_file"
    ]
    with open(SNP_SERIES_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=snp_headers)
        writer.writeheader()
        writer.writerows(all_snp_series)

    summary = {
        "total_documents": len(pdfs),
        "sidecars_updated": sidecars_updated,
        "indicative_tables_repaired": indicative_tables_repaired,
        "indicative_series_rows": len(all_indicative_series),
        "deals_series_rows": len(all_deals_series),
        "snp_sales_rows": len(all_snp_series),
    }

    print("=" * 60)
    print("STAR ASIA TABLE EXTRACTION COMPLETE")
    print("=" * 60)
    for k, v in summary.items():
        print(f"  {k:<30}: {v}")

    return summary


def main():
    parser = argparse.ArgumentParser(description="Extract Star Asia demolition and market tables.")
    args = parser.parse_args()
    process_star_asia_corpus()


if __name__ == "__main__":
    main()
