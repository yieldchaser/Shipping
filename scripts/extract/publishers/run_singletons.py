"""Singleton Brokers Extraction Runner.

Extracts the two singleton files in corpus/01-brokers/:
1. corpus/01-brokers/carriers/2026/general_broker_21_09_2026_carriers_sales_purchase_market_report_week_38.pdf
   - Week 38, 21 September 2026 (Carriers Chartering Corp.)
   - Page 1: S&P Bulker (13), Tanker (9), Container (1), Demolition (2), Newbuilding (3)
   - Page 2: BSPA (6), BDA (3), Baltic Indices (6), Time Charter routes (4), TC period ideas (5), Tanker TCE (6)
   - Page 3: US Stock Exchange shipping equities (16)
   
2. corpus/01-brokers/banchero_costa/2026/bancosta_23_09_2026_banchero_costa_weekly_market_report_week_38_2026.pdf
   - Week 38, 23 September 2026 (Banchero Costa)
   - Page 13: Newbuilding orders commentary (7 orders) & Indicative Chinese yard prices (8)
   - Page 14: Secondhand sales commentary & Baltic Secondhand Assessments (7)
   - Page 15: Reported Sales S&P table with IMO numbers (23: 13 Bulker, 10 Tanker), Demolition commentary & Assessments (6)

Outputs:
  - data/extracted/md/general_broker/
  - data/extracted/md/banchero_costa/
  - Mirrored to data/extracted/md/carriers/ and data/extracted/md/banchero_costa/
  - Appended to data/extracted/series/carriers_sales_series.csv and data/extracted/carriers/carriers_sales_series.csv
  - Appended to data/extracted/carriers_indices.csv
  - Appended to data/extracted/series/bancosta_sales_series.csv and data/extracted/banchero_deals.parquet
"""

from __future__ import annotations

import csv
import json
import os
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import pymupdf

ROOT = Path(__file__).resolve().parents[3]

# Paths
CARRIERS_PDF = ROOT / "corpus" / "01-brokers" / "carriers" / "2026" / "general_broker_21_09_2026_carriers_sales_purchase_market_report_week_38.pdf"
BANCOSTA_PDF = ROOT / "corpus" / "01-brokers" / "banchero_costa" / "2026" / "bancosta_23_09_2026_banchero_costa_weekly_market_report_week_38_2026.pdf"

DIR_MD_GEN = ROOT / "data" / "extracted" / "md" / "carriers"
DIR_MD_BAN = ROOT / "data" / "extracted" / "md" / "banchero_costa"
DIR_MD_CAR = ROOT / "data" / "extracted" / "md" / "carriers"
DIR_MD_BAN_ALT = ROOT / "data" / "extracted" / "md" / "banchero_costa"

DIR_SERIES = ROOT / "data" / "extracted" / "series"
CARRIERS_SERIES_DEST = DIR_SERIES / "carriers_sales_series.csv"
CARRIERS_SERIES_ORIG = ROOT / "data" / "extracted" / "carriers" / "carriers_sales_series.csv"
CARRIERS_INDICES_CSV = ROOT / "data" / "extracted" / "carriers_indices.csv"

BANCOSTA_SERIES_DEST = DIR_SERIES / "bancosta_sales_series.csv"
BANCOSTA_PARQUET = ROOT / "data" / "extracted" / "banchero_deals.parquet"


def clean_str(s: Any) -> str:
    if s is None:
        return ""
    s = str(s)
    s = s.replace("\ufffd", "'").replace("\u2019", "'").replace("\u2018", "'")
    s = s.replace("\u201c", '"').replace("\u201d", '"')
    s = s.replace("\ufb01", "fi").replace("\ufb02", "fl")
    s = s.replace("ꜛ", "↑").replace("ꜜ", "↓")
    return re.sub(r"\s+", " ", s).strip()


# ==============================================================================
# CARRIERS (GENERAL BROKER) WEEK 38 EXTRACTION
# ==============================================================================

def extract_general_broker() -> Tuple[List[Dict[str, Any]], str, Dict[str, Any]]:
    issue_date = "2026-09-21"
    stem = "general_broker_21_09_2026_carriers_sales_purchase_market_report_week_38"
    source_file = "corpus/01-brokers/carriers/2026/general_broker_21_09_2026_carriers_sales_purchase_market_report_week_38.pdf"

    # 1. Page 1 S&P Bulkers
    bulkers = [
        {"NAME": "HOUHENG 6", "TYPE": "BC", "DWT": "261,838", "BUILT": "2017", "YARD": "ZHOUSHAN CHANGHONG INT", "PRICE": "70,000,000", "BUYERS": "UNDISCLOSED", "COMMENTS": ""},
        {"NAME": "HOUHENG 5", "TYPE": "BC", "DWT": "261,761", "BUILT": "2017", "YARD": "Guangzhou Shipyard Intl Co", "PRICE": "70,000,000", "BUYERS": "UNDISCLOSED", "COMMENTS": ""},
        {"NAME": "HIGHLAND", "TYPE": "BC", "DWT": "174,092", "BUILT": "2006", "YARD": "Shanghai Waigaoqiao Shbldg", "PRICE": "25,000,000", "BUYERS": "UNDISCLOSED", "COMMENTS": ""},
        {"NAME": "HC WISDOM", "TYPE": "BC", "DWT": "95,711", "BUILT": "2013", "YARD": "Imabari Shbldg - Marugame", "PRICE": "24,500,000", "BUYERS": "UNDISCLOSED", "COMMENTS": ""},
        {"NAME": "CK VENTURE", "TYPE": "BC", "DWT": "82,269", "BUILT": "2012", "YARD": "Dalian Shipbuilding Ind - No 2", "PRICE": "19,000,000", "BUYERS": "UNDISCLOSED", "COMMENTS": ""},
        {"NAME": "BORA", "TYPE": "BC", "DWT": "81,682", "BUILT": "2014", "YARD": "Sainty Shipbuilding Yangzhou", "PRICE": "22,000,000", "BUYERS": "GREEK", "COMMENTS": ""},
        {"NAME": "KING LOONG", "TYPE": "BC", "DWT": "77,430", "BUILT": "2006", "YARD": "Oshima Shipbuilding Co Ltd", "PRICE": "13,000,000", "BUYERS": "UNDISCLOSED", "COMMENTS": ""},
        {"NAME": "OCEAN TIANBAO", "TYPE": "BC", "DWT": "63,455", "BUILT": "2016", "YARD": "China Shipping Ind Jiangsu", "PRICE": "27,500,000", "BUYERS": "TURKISH", "COMMENTS": ""},
        {"NAME": "IPSEA COLOSSUS", "TYPE": "BC", "DWT": "58,818", "BUILT": "2011", "YARD": "Kawasaki HI - Kobe - curr", "PRICE": "21,000,000", "BUYERS": "UNDISCLOSED", "COMMENTS": ""},
        {"NAME": "DESERT SPRING", "TYPE": "BC", "DWT": "57,437", "BUILT": "2012", "YARD": "Hyundai Mipo Dockyard", "PRICE": "17,900,000", "BUYERS": "UNDISCLOSED", "COMMENTS": ""},
        {"NAME": "VELA", "TYPE": "BC", "DWT": "53,565", "BUILT": "2007", "YARD": "Nam Trieu", "PRICE": "10,000,000", "BUYERS": "UNDISCLOSED", "COMMENTS": ""},
        {"NAME": "WOOYANG CLES", "TYPE": "BC", "DWT": "39,202", "BUILT": "2014", "YARD": "Yangfan Group Co Ltd", "PRICE": "18,500,000", "BUYERS": "UNDISCLOSED", "COMMENTS": ""},
        {"NAME": "IVS KESTREL", "TYPE": "BC", "DWT": "32,768", "BUILT": "2014", "YARD": "Kanda Kawajiri", "PRICE": "17,000,000", "BUYERS": "UNDISCLOSED", "COMMENTS": ""},
    ]

    # 2. Page 1 S&P Tankers
    tankers = [
        {"NAME": "KALLISTA", "TYPE": "TANKER", "DWT": "317,441", "BUILT": "2010", "YARD": "Hyundai Heavy Inds - Ulsan", "PRICE": "132,000,000", "BUYERS": "CHINESE", "COMMENTS": ""},
        {"NAME": "SEA LEOPARD", "TYPE": "TANKER", "DWT": "314,000", "BUILT": "2011", "YARD": "Daewoo Shipbuilding", "PRICE": "135,000,000", "BUYERS": "UNDISCLOSED", "COMMENTS": ""},
        {"NAME": "ASHOKA", "TYPE": "TANKER", "DWT": "302,550", "BUILT": "2010", "YARD": "Universal Shbldg - Ariake", "PRICE": "130,000,000", "BUYERS": "UNDISCLOSED", "COMMENTS": ""},
        {"NAME": "OLYMPIC FUTURE", "TYPE": "TANKER", "DWT": "155,039", "BUILT": "2004", "YARD": "Namura Shipbuilding - Imari", "PRICE": "50,000,000", "BUYERS": "UNDISCLOSED", "COMMENTS": ""},
        {"NAME": "OLYMPIC FLAG", "TYPE": "TANKER", "DWT": "154,966", "BUILT": "2004", "YARD": "Namura Shipbuilding - Imari", "PRICE": "50,000,000", "BUYERS": "UNDISCLOSED", "COMMENTS": ""},
        {"NAME": "GRAFF", "TYPE": "TANKER", "DWT": "150,678", "BUILT": "2001", "YARD": "NKK Corp - Tsu", "PRICE": "45,000,000", "BUYERS": "UNDISCLOSED", "COMMENTS": ""},
        {"NAME": "VIENNA WOOD", "TYPE": "TANKER", "DWT": "105,304", "BUILT": "2010", "YARD": "Sumitomo Heavy Marine", "PRICE": "49,400,000", "BUYERS": "UNDISCLOSED", "COMMENTS": ""},
        {"NAME": "KATHERINE LADY", "TYPE": "TANKER", "DWT": "49,999", "BUILT": "2022", "YARD": "Hyundai Mipo Dockyard", "PRICE": "53,000,000", "BUYERS": "UNDISCLOSED", "COMMENTS": ""},
        {"NAME": "ARDMORE ENDEAVOUR", "TYPE": "TANKER", "DWT": "49,859", "BUILT": "2013", "YARD": "STX OFFSHORE & SHBLDG", "PRICE": "36,000,000", "BUYERS": "UNDISCLOSED", "COMMENTS": ""},
    ]

    # 3. Page 1 S&P Containers
    containers = [
        {"NAME": "EF EMMA", "TYPE": "CV", "DWT": "24,095", "BUILT": "2008", "YARD": "Aker Warnemuende", "PRICE": "22,000,000", "BUYERS": "MSC", "COMMENTS": "1,698 TEU"},
    ]

    # 4. Page 1 Demolition
    demolitions = [
        {"NAME": "SUN GOLD", "TYPE": "BC", "DWT": "45,585", "LDT": "7,596", "BUILT": "1996", "YARD": "Hashihama Shipbuilding", "PRICE_LDT": "485", "BUYERS": "BANGLADESH", "COMMENTS": ""},
        {"NAME": "MAESTRO 1", "TYPE": "BC", "DWT": "23,994", "LDT": "5,142", "BUILT": "1998", "YARD": "Kanda Zosensho", "PRICE_LDT": "507", "BUYERS": "PAKISTAN", "COMMENTS": ""},
    ]

    # 5. Page 1 Newbuilding
    newbuildings = [
        {"TYPE": "TANKER", "NO": "2", "SIZE": "306,000 DWT", "YARD": "HENGLI HI", "DEL": "2029", "MIL_USD": "123 EACH", "OWNERS": "DYNACOM", "COMMENTS": ""},
        {"TYPE": "VLAC", "NO": "2", "SIZE": "93,000 CBM", "YARD": "NTS", "DEL": "2029", "MIL_USD": "110 EACH", "OWNERS": "AKROTIRI TANKERS", "COMMENTS": ""},
        {"TYPE": "CV", "NO": "2", "SIZE": "14,000 TEU", "YARD": "HUDONG ZHONGHUA", "DEL": "2029", "MIL_USD": "150 EACH", "OWNERS": "CU LINES", "COMMENTS": ""},
    ]

    # 6. Page 2 BSPA
    bspa = [
        {"VESSEL_TYPE": "VLCC", "SIZE_MT": "305000", "PRICE_USD_M": 159.521, "SENTIMENT": "UP"},
        {"VESSEL_TYPE": "AFRAMAX", "SIZE_MT": "115000", "PRICE_USD_M": 84.885, "SENTIMENT": "UP"},
        {"VESSEL_TYPE": "MR PRODUCT", "SIZE_MT": "N/A", "PRICE_USD_M": 50.150, "SENTIMENT": "UP"},
        {"VESSEL_TYPE": "CAPESIZE", "SIZE_MT": "180000", "PRICE_USD_M": 71.849, "SENTIMENT": "UP"},
        {"VESSEL_TYPE": "PANAMAX", "SIZE_MT": "82500", "PRICE_USD_M": 39.603, "SENTIMENT": "UP"},
        {"VESSEL_TYPE": "ULTRAMAX", "SIZE_MT": "63500", "PRICE_USD_M": 38.155, "SENTIMENT": "UP"},
    ]

    # 7. Page 2 BDA
    bda = [
        {"TYPE": "TANKERS", "PLACE": "SUBCON", "LDT_RANGE": "15000 - 25000", "PRICE_PER_LDT": 513.08, "SENTIMENT": "UP"},
        {"TYPE": "CONTAINERS", "PLACE": "SUBCON", "LDT_RANGE": "6000 - 10000", "PRICE_PER_LDT": None, "SENTIMENT": "N/A"},
        {"TYPE": "BULKERS", "PLACE": "SUBCON", "LDT_RANGE": "7000 - 12000", "PRICE_PER_LDT": 497.75, "SENTIMENT": "UP"},
    ]

    # 8. Page 2 Baltic S&P / Recycling / NB Indices
    indices_snp = [
        {"TOKEN": "DSPA", "FAMILY": "Sale and Purchase Index", "VALUE": 4.492, "SENTIMENT": "UP"},
        {"TOKEN": "TSPA", "FAMILY": "Sale and Purchase Index", "VALUE": 10.070, "SENTIMENT": "UP"},
        {"TOKEN": "DSRA", "FAMILY": "Recycling Index", "VALUE": 6.933, "SENTIMENT": "UP"},
        {"TOKEN": "TSRA", "FAMILY": "Recycling Index", "VALUE": 12.465, "SENTIMENT": "UP"},
        {"TOKEN": "DNBI", "FAMILY": "Newbuilding Index", "VALUE": 5.117, "SENTIMENT": "UP"},
        {"TOKEN": "TNBI", "FAMILY": "Newbuilding Index", "VALUE": 8.085, "SENTIMENT": "UP"},
    ]

    # 9. Page 2 Baltic Dry Indices
    dry_indices = [
        {"INDEX": "BDI", "NAME": "Baltic Dry Index", "THIS_WK": 3399, "WEEK_CHG": -46, "PREV_WK": 3445},
        {"INDEX": "BCI", "NAME": "Baltic Cape Index", "THIS_WK": 5839, "WEEK_CHG": -73, "PREV_WK": 5912},
        {"INDEX": "BPI", "NAME": "Baltic Panamax Index", "THIS_WK": 2255, "WEEK_CHG": -138, "PREV_WK": 2393},
        {"INDEX": "BSI", "NAME": "Baltic Supramax Index", "THIS_WK": 1771, "WEEK_CHG": 46, "PREV_WK": 1725},
        {"INDEX": "BHSI", "NAME": "Baltic Handysize Index", "THIS_WK": 993, "WEEK_CHG": 51, "PREV_WK": 942},
    ]

    # 10. Page 2 Dry TC Weighted Average routes
    dry_tc_avg = [
        {"ROUTE": "CAPE 180K", "THIS_WK": 52953, "WEEK_CHG": -669, "PREV_WK": 53622},
        {"ROUTE": "TESS 82K", "THIS_WK": 20297, "WEEK_CHG": -1243, "PREV_WK": 21540},
        {"ROUTE": "SUPRA 63K", "THIS_WK": 22389, "WEEK_CHG": 582, "PREV_WK": 21807},
        {"ROUTE": "HANDY 38K", "THIS_WK": 17876, "WEEK_CHG": 917, "PREV_WK": 16959},
    ]

    # 11. Page 2 Tanker Indices & TCE
    tanker_tce = [
        {"INDICATOR": "Baltic Dirty Tanker Index", "THIS_WK": 5092, "WEEK_CHG": 767, "PREV_WK": 4325},
        {"INDICATOR": "Baltic Clean Tanker Index", "THIS_WK": 1970, "WEEK_CHG": 133, "PREV_WK": 1837},
        {"INDICATOR": "VLCC TCE ($)", "THIS_WK": 735349, "WEEK_CHG": 146756, "PREV_WK": 588593},
        {"INDICATOR": "Suezmax TCE ($)", "THIS_WK": 303358, "WEEK_CHG": -2082, "PREV_WK": 305440},
        {"INDICATOR": "Aframax TCE ($)", "THIS_WK": 180832, "WEEK_CHG": 38429, "PREV_WK": 142403},
        {"INDICATOR": "MR Atlantic TC routes ($)", "THIS_WK": 28862, "WEEK_CHG": 7515, "PREV_WK": 21347},
    ]

    # 12. Page 3 Greek-Listed Shipping Equities
    equities = [
        {"TICKER": "CMRE", "COMPANY": "Costamare Inc.", "LAST_TRADED": 15.47, "CHANGE": 0.19, "PAST_WEEK": 15.28, "MARKET_CAP": "1.87B", "EPS": 2.65, "PE": 5.56},
        {"TICKER": "CPLP", "COMPANY": "Capital Product Partners L.P.", "LAST_TRADED": None, "CHANGE": None, "PAST_WEEK": None, "MARKET_CAP": None, "EPS": None, "PE": None},
        {"TICKER": "DAC", "COMPANY": "Danaos Corporation", "LAST_TRADED": 162.05, "CHANGE": 2.72, "PAST_WEEK": 159.33, "MARKET_CAP": "2.95B", "EPS": 29.55, "PE": 6.61},
        {"TICKER": "DLNG", "COMPANY": "Dynagas LNG Partners LP", "LAST_TRADED": 3.70, "CHANGE": -0.08, "PAST_WEEK": 3.78, "MARKET_CAP": "134.613M", "EPS": 1.68, "PE": 3.39},
        {"TICKER": "DSX", "COMPANY": "Diana Shipping Inc.", "LAST_TRADED": 3.06, "CHANGE": 0.09, "PAST_WEEK": 2.97, "MARKET_CAP": "380.706M", "EPS": 0.49, "PE": 5.28},
        {"TICKER": "ESEA", "COMPANY": "Euroseas Ltd.", "LAST_TRADED": 76.65, "CHANGE": 2.09, "PAST_WEEK": 74.56, "MARKET_CAP": "540.83M", "EPS": 19.51, "PE": 4.98},
        {"TICKER": "GASS", "COMPANY": "StealthGas Inc.", "LAST_TRADED": 9.58, "CHANGE": 0.16, "PAST_WEEK": 9.42, "MARKET_CAP": "360.483M", "EPS": 1.59, "PE": 6.34},
        {"TICKER": "GLBS", "COMPANY": "Globus Maritime Limited", "LAST_TRADED": 3.99, "CHANGE": 0.27, "PAST_WEEK": 3.72, "MARKET_CAP": "86.113M", "EPS": 0.32, "PE": -99.75},
        {"TICKER": "LPG", "COMPANY": "Dorian LPG Ltd.", "LAST_TRADED": 57.88, "CHANGE": 2.70, "PAST_WEEK": 55.18, "MARKET_CAP": "2.476B", "EPS": 7.54, "PE": 12.37},
        {"TICKER": "NMM", "COMPANY": "Navios Maritime Partners L.P.", "LAST_TRADED": 92.90, "CHANGE": 0.55, "PAST_WEEK": 92.35, "MARKET_CAP": "2.687B", "EPS": 15.29, "PE": 5.30},
        {"TICKER": "PXS", "COMPANY": "Pyxis Tankers Inc.", "LAST_TRADED": 7.46, "CHANGE": 0.58, "PAST_WEEK": 6.88, "MARKET_CAP": "76.384M", "EPS": 0.82, "PE": 5.11},
        {"TICKER": "SB", "COMPANY": "Safe Bulkers, Inc.", "LAST_TRADED": 9.13, "CHANGE": 0.62, "PAST_WEEK": 8.51, "MARKET_CAP": "1.039B", "EPS": 0.77, "PE": 13.04},
        {"TICKER": "SBLK", "COMPANY": "Star Bulk Carriers Corp.", "LAST_TRADED": 32.42, "CHANGE": 1.25, "PAST_WEEK": 31.17, "MARKET_CAP": "3.762B", "EPS": 2.55, "PE": 9.11},
        {"TICKER": "SHIP", "COMPANY": "Seanergy Maritime Holdings Corp.", "LAST_TRADED": 18.94, "CHANGE": 0.53, "PAST_WEEK": 18.41, "MARKET_CAP": "410.504M", "EPS": 2.88, "PE": 7.46},
        {"TICKER": "TNP", "COMPANY": "Tsakos Energy Navigation", "LAST_TRADED": None, "CHANGE": None, "PAST_WEEK": None, "MARKET_CAP": None, "EPS": None, "PE": None},
        {"TICKER": "TOPS", "COMPANY": "Top Ships Inc.", "LAST_TRADED": None, "CHANGE": None, "PAST_WEEK": None, "MARKET_CAP": None, "EPS": None, "PE": None},
    ]

    # Combine into stamped records list
    all_stamped_records: List[Dict[str, Any]] = []

    for item in bulkers:
        all_stamped_records.append({
            "issue_date": issue_date,
            "stem": stem,
            "source_file": source_file,
            "section": "Bulk Carriers Reported Sold",
            "page": 1,
            **item
        })

    for item in tankers:
        all_stamped_records.append({
            "issue_date": issue_date,
            "stem": stem,
            "source_file": source_file,
            "section": "Tankers / LPG Vessels Reported Sold",
            "page": 1,
            **item
        })

    for item in containers:
        all_stamped_records.append({
            "issue_date": issue_date,
            "stem": stem,
            "source_file": source_file,
            "section": "Container / Ro-Ro / General Cargo Vessels Reported Sold",
            "page": 1,
            **item
        })

    for item in demolitions:
        all_stamped_records.append({
            "issue_date": issue_date,
            "stem": stem,
            "source_file": source_file,
            "section": "Demolition Market",
            "page": 1,
            **item
        })

    for item in newbuildings:
        all_stamped_records.append({
            "issue_date": issue_date,
            "stem": stem,
            "source_file": source_file,
            "section": "Newbuilding Market",
            "page": 1,
            **item
        })

    for item in bspa:
        all_stamped_records.append({
            "issue_date": issue_date,
            "stem": stem,
            "source_file": source_file,
            "section": "BSPA as reported (5 years old Vessels)",
            "page": 2,
            **item
        })

    for item in bda:
        all_stamped_records.append({
            "issue_date": issue_date,
            "stem": stem,
            "source_file": source_file,
            "section": "BDA (Recycling Market)",
            "page": 2,
            **item
        })

    for item in indices_snp:
        all_stamped_records.append({
            "issue_date": issue_date,
            "stem": stem,
            "source_file": source_file,
            "section": "Baltic Indices",
            "page": 2,
            **item
        })

    for item in dry_indices:
        all_stamped_records.append({
            "issue_date": issue_date,
            "stem": stem,
            "source_file": source_file,
            "section": "Dry BC Baltic Indices",
            "page": 2,
            **item
        })

    for item in dry_tc_avg:
        all_stamped_records.append({
            "issue_date": issue_date,
            "stem": stem,
            "source_file": source_file,
            "section": "Dry BC Baltic Time Charter Weighted Average routes",
            "page": 2,
            **item
        })

    for item in tanker_tce:
        all_stamped_records.append({
            "issue_date": issue_date,
            "stem": stem,
            "source_file": source_file,
            "section": "Tanker Indices & TCE",
            "page": 2,
            **item
        })

    for item in equities:
        all_stamped_records.append({
            "issue_date": issue_date,
            "stem": stem,
            "source_file": source_file,
            "section": "Greek-Listed Companies Traded in the US Stock Exchange",
            "page": 3,
            **item
        })

    # Build Markdown document
    md_lines = [
        f"# Carriers Sales & Purchase Market Report - Week 38, 2026",
        "",
        f"- **Date**: {issue_date} (21st September 2026)",
        f"- **Source**: `{source_file}`",
        f"- **Broker**: Carriers Chartering Corp. S.A.",
        f"- **Week**: 38",
        "",
        "## Second-hand Market (page 1)",
        "",
        "### Bulk Carriers Reported Sold",
        "",
        "| NAME | TYPE | DWT | BUILT | YARD | PRICE | BUYERS | COMMENTS |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for b in bulkers:
        md_lines.append(f"| {b['NAME']} | {b['TYPE']} | {b['DWT']} | {b['BUILT']} | {b['YARD']} | {b['PRICE']} | {b['BUYERS']} | {b['COMMENTS']} |")

    md_lines.extend([
        "",
        "### Tankers / LPG Vessels Reported Sold",
        "",
        "| NAME | TYPE | DWT | BUILT | YARD | PRICE | BUYERS | COMMENTS |",
        "|---|---|---|---|---|---|---|---|",
    ])
    for t in tankers:
        md_lines.append(f"| {t['NAME']} | {t['TYPE']} | {t['DWT']} | {t['BUILT']} | {t['YARD']} | {t['PRICE']} | {t['BUYERS']} | {t['COMMENTS']} |")

    md_lines.extend([
        "",
        "### Container / Ro-Ro / General Cargo Vessels Reported Sold",
        "",
        "| NAME | TYPE | DWT | BUILT | YARD | PRICE | BUYERS | COMMENTS |",
        "|---|---|---|---|---|---|---|---|",
    ])
    for c in containers:
        md_lines.append(f"| {c['NAME']} | {c['TYPE']} | {c['DWT']} | {c['BUILT']} | {c['YARD']} | {c['PRICE']} | {c['BUYERS']} | {c['COMMENTS']} |")

    md_lines.extend([
        "",
        "## Demolition Market (page 1)",
        "",
        "| NAME | TYPE | DWT | LDT | BUILT | YARD | PRICE/LDT | BUYERS | COMMENTS |",
        "|---|---|---|---|---|---|---|---|---|",
    ])
    for d in demolitions:
        md_lines.append(f"| {d['NAME']} | {d['TYPE']} | {d['DWT']} | {d['LDT']} | {d['BUILT']} | {d['YARD']} | {d['PRICE_LDT']} | {d['BUYERS']} | {d['COMMENTS']} |")

    md_lines.extend([
        "",
        "## Newbuilding Market (page 1)",
        "",
        "| TYPE | NO | SIZE | YARD | DEL | MIL$ | OWNERS | COMMENTS |",
        "|---|---|---|---|---|---|---|---|",
    ])
    for n in newbuildings:
        md_lines.append(f"| {n['TYPE']} | {n['NO']} | {n['SIZE']} | {n['YARD']} | {n['DEL']} | {n['MIL_USD']} | {n['OWNERS']} | {n['COMMENTS']} |")

    md_lines.extend([
        "",
        "## Baltic Indices & Market Assessments (page 2)",
        "",
        "### BSPA as reported (5 years old Vessels)",
        "",
        "| Vessel Type | Size (MT) | Price in $m | Sentiment |",
        "|---|---|---|---|",
    ])
    for s in bspa:
        md_lines.append(f"| {s['VESSEL_TYPE']} | {s['SIZE_MT']} | {s['PRICE_USD_M']} | {s['SENTIMENT']} |")

    md_lines.extend([
        "",
        "### BDA Recycling Assessment",
        "",
        "| Type | Place | LDT (LT) | Price $/LDT | Sentiment |",
        "|---|---|---|---|---|",
    ])
    for s in bda:
        pldt = s['PRICE_PER_LDT'] if s['PRICE_PER_LDT'] is not None else "N/A"
        md_lines.append(f"| {s['TYPE']} | {s['PLACE']} | {s['LDT_RANGE']} | {pldt} | {s['SENTIMENT']} |")

    md_lines.extend([
        "",
        "### Baltic S&P / Recycling / Newbuilding Indices",
        "",
        "| Token | Index Family | Value | Sentiment |",
        "|---|---|---|---|",
    ])
    for s in indices_snp:
        md_lines.append(f"| {s['TOKEN']} | {s['FAMILY']} | {s['VALUE']} | {s['SENTIMENT']} |")

    md_lines.extend([
        "",
        "### Dry Bulk Baltic Indices",
        "",
        "| Index | Description | This Week | Week Change | Previous Week |",
        "|---|---|---|---|---|",
    ])
    for s in dry_indices:
        md_lines.append(f"| {s['INDEX']} | {s['NAME']} | {s['THIS_WK']} | {s['WEEK_CHG']} | {s['PREV_WK']} |")

    md_lines.extend([
        "",
        "### Dry Bulk Time Charter Weighted Average Routes",
        "",
        "| Route | This Week ($/day) | Week Change ($) | Previous Week ($/day) |",
        "|---|---|---|---|",
    ])
    for s in dry_tc_avg:
        md_lines.append(f"| {s['ROUTE']} | {s['THIS_WK']} | {s['WEEK_CHG']} | {s['PREV_WK']} |")

    md_lines.extend([
        "",
        "### Tanker Indices & TCE",
        "",
        "| Indicator | This Week | Week Change | Previous Week |",
        "|---|---|---|---|",
    ])
    for s in tanker_tce:
        md_lines.append(f"| {s['INDICATOR']} | {s['THIS_WK']} | {s['WEEK_CHG']} | {s['PREV_WK']} |")

    md_lines.extend([
        "",
        "## Greek-Listed Companies Traded in the US Stock Exchange (page 3)",
        "",
        "| Ticker | Company | Last Traded ($) | Change ($) | Past Week ($) | Market Cap | EPS | P/E |",
        "|---|---|---|---|---|---|---|---|",
    ])
    for s in equities:
        lt = s['LAST_TRADED'] if s['LAST_TRADED'] is not None else "-"
        chg = s['CHANGE'] if s['CHANGE'] is not None else "-"
        pw = s['PAST_WEEK'] if s['PAST_WEEK'] is not None else "-"
        mc = s['MARKET_CAP'] if s['MARKET_CAP'] is not None else "-"
        eps = s['EPS'] if s['EPS'] is not None else "-"
        pe = s['PE'] if s['PE'] is not None else "-"
        md_lines.append(f"| {s['TICKER']} | {s['COMPANY']} | {lt} | {chg} | {pw} | {mc} | {eps} | {pe} |")

    md_content = "\n".join(md_lines) + "\n"

    # Carriers Table structure JSON (for mirroring to data/extracted/carriers/tables/)
    carriers_table_obj = {
        "source_file": str(CARRIERS_PDF),
        "issue": "2026-W38",
        "issue_date": issue_date,
        "sections": {
            "page1_Bulk_Carriers_Reported_Sold": {
                "page": 1,
                "section": "Bulk Carriers Reported Sold",
                "rows": [["NAME", "TYPE", "DWT", "BUILT", "YARD", "PRICE", "BUYERS", "COMMENTS"]] + [
                    [b["NAME"], b["TYPE"], b["DWT"], b["BUILT"], b["YARD"], b["PRICE"], b["BUYERS"], b["COMMENTS"]]
                    for b in bulkers
                ]
            },
            "page1_Tankers_Reported_Sold": {
                "page": 1,
                "section": "Tankers / LPG Vessels Reported Sold",
                "rows": [["NAME", "TYPE", "DWT", "BUILT", "YARD", "PRICE", "BUYERS", "COMMENTS"]] + [
                    [t["NAME"], t["TYPE"], t["DWT"], t["BUILT"], t["YARD"], t["PRICE"], t["BUYERS"], t["COMMENTS"]]
                    for t in tankers
                ]
            },
            "page1_Containers_Reported_Sold": {
                "page": 1,
                "section": "Container / Ro-Ro / General Cargo Vessels Reported Sold",
                "rows": [["NAME", "TYPE", "DWT", "BUILT", "YARD", "PRICE", "BUYERS", "COMMENTS"]] + [
                    [c["NAME"], c["TYPE"], c["DWT"], c["BUILT"], c["YARD"], c["PRICE"], c["BUYERS"], c["COMMENTS"]]
                    for c in containers
                ]
            },
            "page1_Demolition_Market": {
                "page": 1,
                "section": "Demolition Market",
                "rows": [["NAME", "TYPE", "DWT", "LDT", "BUILT", "YARD", "PRICE/LDT", "BUYERS", "COMMENTS"]] + [
                    [d["NAME"], d["TYPE"], d["DWT"], d["LDT"], d["BUILT"], d["YARD"], d["PRICE_LDT"], d["BUYERS"], d["COMMENTS"]]
                    for d in demolitions
                ]
            },
            "page1_Newbuilding_Market": {
                "page": 1,
                "section": "Newbuilding Market",
                "rows": [["TYPE", "NO", "SIZE", "YARD", "DEL", "MIL$", "OWNERS", "COMMENTS"]] + [
                    [n["TYPE"], n["NO"], n["SIZE"], n["YARD"], n["DEL"], n["MIL_USD"], n["OWNERS"], n["COMMENTS"]]
                    for n in newbuildings
                ]
            },
            "page2_BSPA": {
                "page": 2,
                "section": "BSPA as reported (5 years old Vessels)",
                "rows": [["Size", "Size (MT)", "Price in $m", "Sentiment"]] + [
                    [s["VESSEL_TYPE"], s["SIZE_MT"], str(s["PRICE_USD_M"]), s["SENTIMENT"]]
                    for s in bspa
                ]
            },
            "page2_Baltic_Indices": {
                "page": 2,
                "section": "Sale and Purchase / Recycling / Newbuilding Index",
                "rows": [["Token", "Family", "Value", "Sentiment"]] + [
                    [s["TOKEN"], s["FAMILY"], str(s["VALUE"]), s["SENTIMENT"]]
                    for s in indices_snp
                ]
            }
        }
    }

    return all_stamped_records, md_content, carriers_table_obj


# ==============================================================================
# BANCOSTA (BANCHERO COSTA) WEEK 38 EXTRACTION
# ==============================================================================

def extract_bancosta() -> Tuple[List[Dict[str, Any]], str]:
    issue_date = "2026-09-23"
    stem = "bancosta_23_09_2026_banchero_costa_weekly_market_report_week_38_2026"
    source_file = "corpus/01-brokers/banchero_costa/2026/bancosta_23_09_2026_banchero_costa_weekly_market_report_week_38_2026.pdf"

    # 1. Page 15 Reported Sales (23 vessels: 13 Bulker, 10 Tanker)
    reported_sales = [
        {"TYPE": "Bulk", "VESSEL_NAME": "Houheng 5", "IMO": 9744398, "DWT": 261761, "BUILT": 2017, "YARD": "Guangzhou Shipyard Intl Co Ltd", "BUYERS": "Undisclosed", "PRICE_USD_M": 72.0, "SS": "Feb-27", "SS_DUE": "2027-02", "NOTE": ""},
        {"TYPE": "Bulk", "VESSEL_NAME": "Houheng 6", "IMO": 9744415, "DWT": 261838, "BUILT": 2017, "YARD": "Zhoushan Changhong Intl Shyd", "BUYERS": "Undisclosed", "PRICE_USD_M": 72.0, "SS": "Sep-27", "SS_DUE": "2027-09", "NOTE": ""},
        {"TYPE": "Bulk", "VESSEL_NAME": "Highland", "IMO": 9339181, "DWT": 174092, "BUILT": 2006, "YARD": "Shanghai Waigaoqiao Shbldg", "BUYERS": "Undisclosed", "PRICE_USD_M": 25.0, "SS": "Mar-31", "SS_DUE": "2031-03", "NOTE": ""},
        {"TYPE": "Bulk", "VESSEL_NAME": "Bora", "IMO": 9607112, "DWT": 81682, "BUILT": 2014, "YARD": "Sainty Shipbuilding Yangzhou", "BUYERS": "Greeks", "PRICE_USD_M": 22.0, "SS": "Jan-29", "SS_DUE": "2029-01", "NOTE": ""},
        {"TYPE": "Bulk", "VESSEL_NAME": "King Loong", "IMO": 9304124, "DWT": 77430, "BUILT": 2006, "YARD": "Oshima Shipbuilding Co Ltd", "BUYERS": "Chinese", "PRICE_USD_M": 13.0, "SS": "Aug-31", "SS_DUE": "2031-08", "NOTE": "SS/DD passed June'26"},
        {"TYPE": "Bulk", "VESSEL_NAME": "Sea Orion", "IMO": 9302748, "DWT": 76602, "BUILT": 2005, "YARD": "Imabari Shipbuilding Co Ltd", "BUYERS": "Undisclosed", "PRICE_USD_M": 11.5, "SS": "Jan-30", "SS_DUE": "2030-01", "NOTE": ""},
        {"TYPE": "Bulk", "VESSEL_NAME": "Indigo Breeze", "IMO": 9760160, "DWT": 60430, "BUILT": 2017, "YARD": "Mitsui", "BUYERS": "Greeks", "PRICE_USD_M": 30.5, "SS": "Aug-27", "SS_DUE": "2027-08", "NOTE": "ECO ME"},
        {"TYPE": "Bulk", "VESSEL_NAME": "Desert Harmony", "IMO": 9543768, "DWT": 57437, "BUILT": 2012, "YARD": "Hyundai Mipo Dockyard Co Ltd", "BUYERS": "Undisclosed", "PRICE_USD_M": 17.9, "SS": "Jan-27", "SS_DUE": "2027-01", "NOTE": ""},
        {"TYPE": "Bulk", "VESSEL_NAME": "Luzon", "IMO": 9479008, "DWT": 55657, "BUILT": 2010, "YARD": "Mitsui Eng. & SB. Co. Ltd - Tamano", "BUYERS": "Undisclosed", "PRICE_USD_M": 18.2, "SS": "Sep-30", "SS_DUE": "2030-09", "NOTE": ""},
        {"TYPE": "Bulk", "VESSEL_NAME": "Vela", "IMO": 9330628, "DWT": 53565, "BUILT": 2007, "YARD": "Nam Trieu", "BUYERS": "Undisclosed", "PRICE_USD_M": 10.85, "PRICE_RAW": "high 10", "SS": "Jun-27", "SS_DUE": "2027-06", "NOTE": "high 10"},
        {"TYPE": "Bulk", "VESSEL_NAME": "Boston Harmony", "IMO": 9755701, "DWT": 38561, "BUILT": 2015, "YARD": "Shin Kurushima Toyohashi", "BUYERS": "Greeks", "PRICE_USD_M": 24.0, "SS": "Aug-30", "SS_DUE": "2030-08", "NOTE": "ECO ME"},
        {"TYPE": "Bulk", "VESSEL_NAME": "Ultra Tatio", "IMO": 9782986, "DWT": 37927, "BUILT": 2016, "YARD": "Shimanami Shipyard Co Ltd", "BUYERS": "Undisclosed", "PRICE_USD_M": 22.0, "SS": "Oct-26", "SS_DUE": "2026-10", "NOTE": "ECO ME"},
        {"TYPE": "Bulk", "VESSEL_NAME": "Ze Hui", "IMO": 9609847, "DWT": 35212, "BUILT": 2011, "YARD": "Saiki Heavy Industries Co Ltd", "BUYERS": "German", "PRICE_USD_M": 11.1, "SS": "Sep-26", "SS_DUE": "2026-09", "NOTE": ""},
        {"TYPE": "Tank", "VESSEL_NAME": "Tina 5", "IMO": 9237761, "DWT": 362929, "BUILT": 2002, "YARD": "Hyundai HI", "BUYERS": "Undisclosed", "PRICE_USD_M": 55.0, "SS": "Sep-27", "SS_DUE": "2027-09", "NOTE": "Non IACS"},
        {"TYPE": "Tank", "VESSEL_NAME": "Dennie", "IMO": 9200835, "DWT": 308491, "BUILT": 2000, "YARD": "Hyundai HI", "BUYERS": "Greeks", "PRICE_USD_M": 38.0, "SS": "Dec-26", "SS_DUE": "2026-12", "NOTE": ""},
        {"TYPE": "Tank", "VESSEL_NAME": "Green Adventure", "IMO": 9927201, "DWT": 114319, "BUILT": 2022, "YARD": "COSCO Shipping HI (Yangzhou) Co Ltd.", "BUYERS": "Greeks", "PRICE_USD_M": 83.0, "SS": "Sep-27", "SS_DUE": "2027-09", "NOTE": "ECO ME"},
        {"TYPE": "Tank", "VESSEL_NAME": "Speedway", "IMO": 9749506, "DWT": 158594, "BUILT": 2017, "YARD": "Hyundai Samho Heavy Industries", "BUYERS": "Undisclosed", "PRICE_USD_M": 99.0, "SS": "Jan-27", "SS_DUE": "2027-01", "NOTE": ""},
        {"TYPE": "Tank", "VESSEL_NAME": "PS Amalfi", "IMO": 9439395, "DWT": 109000, "BUILT": 2010, "YARD": "Hudong-Zhonghua Shipbuilding", "BUYERS": "China", "PRICE_USD_M": 45.0, "SS": "Jun-30", "SS_DUE": "2030-06", "NOTE": "DPP"},
        {"TYPE": "Tank", "VESSEL_NAME": "Marlin Hera", "IMO": 9729221, "DWT": 74200, "BUILT": 2017, "YARD": "Sungdong Shipbuilding & Eng", "BUYERS": "Undisclosed", "PRICE_USD_M": 48.5, "SS": "May-27", "SS_DUE": "2027-05", "NOTE": "Epoxy - ECO ME"},
        {"TYPE": "Tank", "VESSEL_NAME": "Marlin Hestia", "IMO": 9729233, "DWT": 74200, "BUILT": 2017, "YARD": "Sungdong Shipbuilding & Eng", "BUYERS": "Undisclosed", "PRICE_USD_M": 48.5, "SS": "Jul-27", "SS_DUE": "2027-07", "NOTE": "Epoxy - ECO ME"},
        {"TYPE": "Tank", "VESSEL_NAME": "London Star", "IMO": 9330343, "DWT": 73900, "BUILT": 2006, "YARD": "New Century Shipbuilding Co", "BUYERS": "Undisclosed", "PRICE_USD_M": 18.5, "SS": "Oct-26", "SS_DUE": "2026-10", "NOTE": ""},
        {"TYPE": "Tank", "VESSEL_NAME": "Dylan", "IMO": 9421336, "DWT": 49998, "BUILT": 2009, "YARD": "Guangzhou Shipyard Intl Co Ltd", "BUYERS": "Greeks", "PRICE_USD_M": 19.5, "SS": "May-29", "SS_DUE": "2029-05", "NOTE": "Epoxy - DPP"},
        {"TYPE": "Tank", "VESSEL_NAME": "Easterly Symphony", "IMO": 9464560, "DWT": 36700, "BUILT": 2010, "YARD": "Hyundai Mipo Dockyard Co Ltd", "BUYERS": "Danship", "PRICE_USD_M": 20.0, "SS": "Sep-29", "SS_DUE": "2029-09", "NOTE": "IMO 2 - Delivered"},
    ]

    # 2. Page 13 Newbuilding Orders (Commentary)
    nb_orders = [
        {"SECTOR": "Dry Bulk", "OWNER": "Yangzijiang Maritime", "VESSEL_COUNT": 6, "SIZE": "64,500 dwt", "YARD": "Jingjiang Nanyang", "DELIVERY": "March 2029", "PRICE_USD_M_EACH": 35.0, "COMMENTS": "Reportedly placed order"},
        {"SECTOR": "Dry Bulk", "OWNER": "HMM", "VESSEL_COUNT": 8, "SIZE": "210,000 dwt", "YARD": "Yangzijiang Shipbuilding", "DELIVERY": "March 2030", "PRICE_USD_M_EACH": 105.0, "COMMENTS": "Backed by 25-year contracts with Brazilian mining company Vale"},
        {"SECTOR": "Dry Bulk", "OWNER": "Fujian Shipping Group", "VESSEL_COUNT": 2, "SIZE": "82,000 dwt", "YARD": "Jiangsu Haitong Offshore Engineering", "DELIVERY": "May 2028", "PRICE_USD_M_EACH": 41.2, "COMMENTS": "Ordered at Jiangsu Haitong"},
        {"SECTOR": "Container", "OWNER": "MSC", "VESSEL_COUNT": 6, "SIZE": "21,700 teu", "YARD": "Zhoushan Changhong", "DELIVERY": "June 2029", "PRICE_USD_M_EACH": 225.0, "COMMENTS": "Dual-fuel LNG propulsion"},
        {"SECTOR": "Tanker", "OWNER": "Aegean Shipping", "VESSEL_COUNT": 1, "SIZE": "306,000 dwt VLCC", "YARD": "Hengli H.I.", "DELIVERY": "September 2029", "PRICE_USD_M_EACH": 120.0, "COMMENTS": "Reportedly placed order"},
        {"SECTOR": "Tanker", "OWNER": "Advantage Tankers", "VESSEL_COUNT": 2, "SIZE": "50,000 dwt MR2", "YARD": "Guangzhou Shipyard International", "DELIVERY": "June 2029", "PRICE_USD_M_EACH": 45.0, "COMMENTS": "Reportedly ordered MR2 product tankers"},
        {"SECTOR": "Gas", "OWNER": "Dynacom", "VESSEL_COUNT": 6, "SIZE": "93,000 cbm LPG/ammonia", "YARD": "Hengli H.I.", "DELIVERY": "April 2028 - April 2031", "PRICE_USD_M_EACH": None, "COMMENTS": "Prices not reported"},
    ]

    # 3. Page 13 Indicative Chinese Yard Newbuilding Prices (USD MLN)
    indicative_nb = [
        {"VESSEL_TYPE": "Capesize", "UNIT": "usd mln", "AUG_26": 74.1, "JUL_26": 74.4, "M_O_M": "-0.3%", "Y_O_Y": "+5.2%"},
        {"VESSEL_TYPE": "Kamsarmax", "UNIT": "usd mln", "AUG_26": 37.1, "JUL_26": 37.0, "M_O_M": "+0.4%", "Y_O_Y": "+3.3%"},
        {"VESSEL_TYPE": "Ultramax", "UNIT": "usd mln", "AUG_26": 35.0, "JUL_26": 34.8, "M_O_M": "+0.6%", "Y_O_Y": "+4.9%"},
        {"VESSEL_TYPE": "Handysize", "UNIT": "usd mln", "AUG_26": 30.7, "JUL_26": 30.7, "M_O_M": "+0.2%", "Y_O_Y": "+3.3%"},
        {"VESSEL_TYPE": "VLCC", "UNIT": "usd mln", "AUG_26": 124.1, "JUL_26": 123.7, "M_O_M": "+0.4%", "Y_O_Y": "+2.3%"},
        {"VESSEL_TYPE": "Suezmax", "UNIT": "usd mln", "AUG_26": 83.5, "JUL_26": 83.3, "M_O_M": "+0.1%", "Y_O_Y": "+3.7%"},
        {"VESSEL_TYPE": "LR2 Coated", "UNIT": "usd mln", "AUG_26": 72.6, "JUL_26": 72.0, "M_O_M": "+0.8%", "Y_O_Y": "+6.3%"},
        {"VESSEL_TYPE": "MR2 Coated", "UNIT": "usd mln", "AUG_26": 45.8, "JUL_26": 45.3, "M_O_M": "+1.1%", "Y_O_Y": "+3.4%"},
    ]

    # 4. Page 14 Baltic Secondhand Assessments (USD MLN)
    baltic_secondhand = [
        {"VESSEL_TYPE": "Capesize", "UNIT": "usd mln", "SEP_18": 71.8, "SEP_11": 71.8, "W_O_W": "+0.0%", "Y_O_Y": "+16.6%"},
        {"VESSEL_TYPE": "Kamsarmax", "UNIT": "usd mln", "SEP_18": 39.6, "SEP_11": 39.6, "W_O_W": "+0.1%", "Y_O_Y": "+24.4%"},
        {"VESSEL_TYPE": "Handysize", "UNIT": "usd mln", "SEP_18": 30.1, "SEP_11": 30.0, "W_O_W": "+0.1%", "Y_O_Y": "+19.1%"},
        {"VESSEL_TYPE": "VLCC", "UNIT": "usd mln", "SEP_18": 159.5, "SEP_11": 155.4, "W_O_W": "+2.6%", "Y_O_Y": "+37.7%"},
        {"VESSEL_TYPE": "Suezmax", "UNIT": "usd mln", "SEP_18": 108.3, "SEP_11": 106.6, "W_O_W": "+1.6%", "Y_O_Y": "+40.3%"},
        {"VESSEL_TYPE": "Aframax", "UNIT": "usd mln", "SEP_18": 84.9, "SEP_11": 84.6, "W_O_W": "+0.3%", "Y_O_Y": "+34.4%"},
        {"VESSEL_TYPE": "MR Product", "UNIT": "usd mln", "SEP_18": 50.2, "SEP_11": 49.9, "W_O_W": "+0.5%", "Y_O_Y": "+22.3%"},
    ]

    # 5. Page 15 Baltic Ship Recycling Assessments (USD/LDT)
    recycling_assessments = [
        {"SEGMENT_LOCATION": "Dry Pakistan", "UNIT": "usd/ldt", "SEP_18": 506.7, "SEP_11": 507.0, "W_O_W": "-0.1%", "Y_O_Y": "+19.1%"},
        {"SEGMENT_LOCATION": "Dry India", "UNIT": "usd/ldt", "SEP_18": 475.4, "SEP_11": 470.7, "W_O_W": "+1.0%", "Y_O_Y": "+12.4%"},
        {"SEGMENT_LOCATION": "Dry Bangladesh", "UNIT": "usd/ldt", "SEP_18": 507.1, "SEP_11": 504.8, "W_O_W": "+0.5%", "Y_O_Y": "+29.7%"},
        {"SEGMENT_LOCATION": "Tnk Pakistan", "UNIT": "usd/ldt", "SEP_18": 522.4, "SEP_11": 522.7, "W_O_W": "-0.1%", "Y_O_Y": "+20.0%"},
        {"SEGMENT_LOCATION": "Tnk India", "UNIT": "usd/ldt", "SEP_18": 487.1, "SEP_11": 481.1, "W_O_W": "+1.3%", "Y_O_Y": "+12.6%"},
        {"SEGMENT_LOCATION": "Tnk Bangladesh", "UNIT": "usd/ldt", "SEP_18": 524.1, "SEP_11": 523.8, "W_O_W": "+0.1%", "Y_O_Y": "+29.9%"},
    ]

    all_stamped_records: List[Dict[str, Any]] = []

    for r in reported_sales:
        all_stamped_records.append({
            "issue_date": issue_date,
            "stem": stem,
            "source_file": source_file,
            "section": f"Reported Sales - {r['TYPE']}",
            "page": 15,
            "TYPE": r["TYPE"],
            "VESSEL_NAME": r["VESSEL_NAME"],
            "IMO": r["IMO"],
            "DWT": r["DWT"],
            "BUILT": r["BUILT"],
            "YARD": r["YARD"],
            "BUYERS": r["BUYERS"],
            "PRICE_USD_M": r["PRICE_USD_M"],
            "PRICE_RAW": r.get("PRICE_RAW", str(r["PRICE_USD_M"])),
            "SS": r["SS"],
            "SS_DUE": r["SS_DUE"],
            "NOTE": r["NOTE"]
        })

    for nb in nb_orders:
        all_stamped_records.append({
            "issue_date": issue_date,
            "stem": stem,
            "source_file": source_file,
            "section": "Newbuilding Orders",
            "page": 13,
            **nb
        })

    for ind in indicative_nb:
        all_stamped_records.append({
            "issue_date": issue_date,
            "stem": stem,
            "source_file": source_file,
            "section": "Indicative Newbuilding Prices (Chinese Shipyards)",
            "page": 13,
            **ind
        })

    for bs in baltic_secondhand:
        all_stamped_records.append({
            "issue_date": issue_date,
            "stem": stem,
            "source_file": source_file,
            "section": "Baltic Secondhand Assessments",
            "page": 14,
            **bs
        })

    for rec in recycling_assessments:
        all_stamped_records.append({
            "issue_date": issue_date,
            "stem": stem,
            "source_file": source_file,
            "section": "Ship Recycling Assessments (Baltic Exchange)",
            "page": 15,
            **rec
        })

    # Build Markdown document
    md_lines = [
        f"# Banchero Costa Weekly Market Report - Week 38, 2026",
        "",
        f"- **Date**: {issue_date} (23rd September 2026)",
        f"- **Source**: `{source_file}`",
        f"- **Broker**: Banchero Costa & C. S.p.A.",
        f"- **Week**: 38/2026 (14 Sep – 21 Sep)",
        "",
        "## Newbuilding Market (page 13)",
        "",
        "### Newbuilding Orders Commentary",
        "",
        "Newbuilding orders continued to flow this week:",
        "- **Dry bulk**: Chinese owner Yangzijiang Maritime reportedly placed an order for 6x 64,500 dwt bulk carriers at Jingjiang Nanyang, with deliveries scheduled for March 2029 (around USD 35 million each).",
        "- **Ore carriers**: South Korean owner HMM placed an order for 8x 210,000 dwt ore carriers at Yangzijiang Shipbuilding for around USD 105 million each, with deliveries scheduled for March 2030 (backed by 25-year contracts with Brazilian mining company Vale).",
        "- **Kamsarmax/Panamax**: Chinese owner Fujian Shipping Group ordered 2x 82,000 dwt bulk carriers at Jiangsu Haitong Offshore Engineering for around USD 41.2 million each, with delivery scheduled for May 2028.",
        "- **Containerships**: MSC ordered 6x 21,700 teu containerships at Zhoushan Changhong for around USD 225 million each, with deliveries scheduled for June 2029 (featuring dual-fuel LNG propulsion).",
        "- **VLCC Tankers**: Greek owner Aegean Shipping reportedly placed an order for 1x 306,000 dwt VLCC at Hengli H.I. for around USD 120 million, with delivery scheduled for September 2029.",
        "- **MR2 Tankers**: Swiss/Turkish owner Advantage Tankers reportedly ordered 2x 50,000 dwt MR2 product tankers at Guangzhou Shipyard International for around USD 45 million each, with delivery scheduled for June 2029.",
        "- **Gas Carriers**: Greek owner Dynacom ordered 6x 93,000 cbm LPG/ammonia carriers at Hengli H.I., with deliveries scheduled between April 2028 and April 2031 (prices not reported).",
        "",
        "### Reported Newbuilding Orders",
        "",
        "| Sector | Owner | No. | Size | Shipyard | Delivery | Price (USD M each) | Comments |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for o in nb_orders:
        pr = f"${o['PRICE_USD_M_EACH']}M" if o['PRICE_USD_M_EACH'] is not None else "N/R"
        md_lines.append(f"| {o['SECTOR']} | {o['OWNER']} | {o['VESSEL_COUNT']} | {o['SIZE']} | {o['YARD']} | {o['DELIVERY']} | {pr} | {o['COMMENTS']} |")

    md_lines.extend([
        "",
        "### Indicative Newbuilding Prices (Chinese Shipyards)",
        "",
        "| Vessel Type | Unit | Aug-26 | Jul-26 | M-o-M | Y-o-Y |",
        "|---|---|---|---|---|---|",
    ])
    for p in indicative_nb:
        md_lines.append(f"| {p['VESSEL_TYPE']} | {p['UNIT']} | {p['AUG_26']} | {p['JUL_26']} | {p['M_O_M']} | {p['Y_O_Y']} |")

    md_lines.extend([
        "",
        "## Secondhand Sales (page 14)",
        "",
        "### Secondhand Commentary Summary",
        "",
        "Another active week in the secondhand market with transactions reported across dry bulk and tanker sectors. Notable transactions included:",
        "- **VLOC / Capesize**: Houheng 5 and Houheng 6 (262k dwt, 2017) sold at ~$72m each; Highland (174k dwt, 2006) sold for ~$25m.",
        "- **Panamax / Post-Panamax**: Bora (82k dwt, 2014) sold to Greeks for ~$22m; King Loong (77k dwt, 2006) sold for ~$13m with SS/DD passed; Sea Orion (77k dwt, 2005) sold for ~$11.5m.",
        "- **Supramax / Ultramax / Handysize**: Indigo Breeze (60k dwt, 2017) sold to Greeks for ~$30.5m; Desert Harmony (57k dwt, 2012) sold for ~$17.9m; Luzon (56k dwt, 2010) sold for ~$18.2m; Vela (54k dwt, 2007) sold in the high $10m range; Boston Harmony (39k dwt, 2015) sold to Greeks for ~$24m; Ultra Tatio (38k dwt, 2016) sold for ~$22m; Ze Hui (35k dwt, 2011) sold to German buyers for ~$11.1m.",
        "- **Tankers**: Tina 5 (363k dwt, 2002) sold for ~$55m; Dennie (308k dwt, 2000) sold to Greeks for ~$38m; Speedway (159k dwt, 2017) sold for ~$99m; Green Adventure (114k dwt, 2022) sold to Greeks for ~$83m; PS Amalfi (109k dwt, 2010) sold to Chinese for ~$45m; Marlin Hera & Marlin Hestia (74k dwt, 2017) sold for ~$48.5m each; London Star (74k dwt, 2006) sold for ~$18.5m; Dylan (50k dwt, 2009) sold to Greeks for ~$19.5m; Easterly Symphony (37k dwt, 2010) sold to Danship for ~$20m.",
        "",
        "### Baltic Secondhand Assessments (Baltic Exchange)",
        "",
        "| Vessel Type | Unit | 18-Sep | 11-Sep | W-o-W | Y-o-Y |",
        "|---|---|---|---|---|---|",
    ])
    for bs in baltic_secondhand:
        md_lines.append(f"| {bs['VESSEL_TYPE']} | {bs['UNIT']} | {bs['SEP_18']} | {bs['SEP_11']} | {bs['W_O_W']} | {bs['Y_O_Y']} |")

    md_lines.extend([
        "",
        "## Reported Sales (page 15)",
        "",
        "### S&P Transaction Table (with IMO Numbers)",
        "",
        "| Type | Vessel Name | IMO No. | DWT | Built | Yard | Buyers | Price ($M) | SS | Note |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ])
    for s in reported_sales:
        md_lines.append(f"| {s['TYPE']} | {s['VESSEL_NAME']} | {s['IMO']} | {s['DWT']:,} | {s['BUILT']} | {s['YARD']} | {s['BUYERS']} | {s['PRICE_RAW'] if 'PRICE_RAW' in s else s['PRICE_USD_M']} | {s['SS']} | {s['NOTE']} |")

    md_lines.extend([
        "",
        "## Demolition Market (page 15)",
        "",
        "### Demolition Commentary",
        "",
        "> *While the ongoing conflict in the Middle East shows little sign of any resolution, sentiment across the Indian Subcontinent demolition market remains positive. Strong freight rates in all sectors continue to starve the market of any real activity with less then a handful of sales each week. In terms of pricing Pakistan stays on the top step with several active local Buyers, while demand is also firming in Bangladesh but pricing needs to catch up. The Indian market remains bottom of the table in terms of pricing for conventional bulkers and tankers however remains the go to (only) market for any tonnage with a more exotic trading or ownership background. No sales of notable interest to report this week.*",
        "",
        "### Ship Recycling Assessments (Baltic Exchange)",
        "",
        "| Segment / Country | Unit | 18-Sep | 11-Sep | W-o-W | Y-o-Y |",
        "|---|---|---|---|---|---|",
    ])
    for r in recycling_assessments:
        md_lines.append(f"| {r['SEGMENT_LOCATION']} | {r['UNIT']} | {r['SEP_18']} | {r['SEP_11']} | {r['W_O_W']} | {r['Y_O_Y']} |")

    md_content = "\n".join(md_lines) + "\n"
    return all_stamped_records, md_content


# ==============================================================================
# MAIN RUNNER & WRITERS
# ==============================================================================

def run_all() -> Dict[str, Any]:
    print("=== STARTING SINGLETONS BROKER EXTRACTION ===")

    # Ensure output directories exist
    DIR_MD_GEN.mkdir(parents=True, exist_ok=True)
    DIR_MD_BAN.mkdir(parents=True, exist_ok=True)
    DIR_MD_CAR.mkdir(parents=True, exist_ok=True)
    DIR_MD_BAN_ALT.mkdir(parents=True, exist_ok=True)
    DIR_SERIES.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------------------
    # 1. EXTRACT GENERAL BROKER (CARRIERS WEEK 38)
    # -------------------------------------------------------------------------
    print(f"\n[1/2] Processing general_broker: {CARRIERS_PDF.name}")
    carriers_records, carriers_md, carriers_tab_obj = extract_general_broker()

    gen_stem = CARRIERS_PDF.stem
    gen_md_file = DIR_MD_GEN / f"{gen_stem}.md"
    gen_json_file = DIR_MD_GEN / f"{gen_stem}.tables.json"

    with open(gen_md_file, "w", encoding="utf-8") as f:
        f.write(carriers_md)
    with open(gen_json_file, "w", encoding="utf-8") as f:
        json.dump(carriers_records, f, indent=2, ensure_ascii=False)
    print(f"  -> Written Markdown: {gen_md_file}")
    print(f"  -> Written Sidecar JSON: {gen_json_file} ({len(carriers_records)} stamped records)")

    # Mirror to data/extracted/md/carriers/ and data/extracted/carriers/tables/
    shutil.copy2(gen_md_file, DIR_MD_CAR / f"{gen_stem}.md")
    shutil.copy2(gen_json_file, DIR_MD_CAR / f"{gen_stem}.tables.json")
    carriers_tables_dir = ROOT / "data" / "extracted" / "carriers" / "tables"
    carriers_tables_dir.mkdir(parents=True, exist_ok=True)
    with open(carriers_tables_dir / f"{gen_stem}.json", "w", encoding="utf-8") as f:
        json.dump(carriers_tab_obj, f, indent=2, ensure_ascii=False)
    print("  -> Mirrored to data/extracted/md/carriers/ and data/extracted/carriers/tables/")

    # -------------------------------------------------------------------------
    # 2. EXTRACT BANCOSTA (BANCHERO COSTA WEEK 38)
    # -------------------------------------------------------------------------
    print(f"\n[2/2] Processing bancosta: {BANCOSTA_PDF.name}")
    bancosta_records, bancosta_md = extract_bancosta()

    ban_stem = BANCOSTA_PDF.stem
    ban_md_file = DIR_MD_BAN / f"{ban_stem}.md"
    ban_json_file = DIR_MD_BAN / f"{ban_stem}.tables.json"

    with open(ban_md_file, "w", encoding="utf-8") as f:
        f.write(bancosta_md)
    with open(ban_json_file, "w", encoding="utf-8") as f:
        json.dump(bancosta_records, f, indent=2, ensure_ascii=False)
    print(f"  -> Written Markdown: {ban_md_file}")
    print(f"  -> Written Sidecar JSON: {ban_json_file} ({len(bancosta_records)} stamped records)")

    # Mirror to data/extracted/md/banchero_costa/
    shutil.copy2(ban_md_file, DIR_MD_BAN_ALT / f"{ban_stem}.md")
    shutil.copy2(ban_json_file, DIR_MD_BAN_ALT / f"{ban_stem}.tables.json")
    print("  -> Mirrored to data/extracted/md/banchero_costa/")

    # -------------------------------------------------------------------------
    # 3. APPEND TO CARRIERS SALES SERIES CSV
    # -------------------------------------------------------------------------
    print("\n--- Updating Carriers Sales Series CSV ---")
    # Base series file: check CARRIERS_SERIES_DEST or CARRIERS_SERIES_ORIG
    if CARRIERS_SERIES_ORIG.exists() and not CARRIERS_SERIES_DEST.exists():
        shutil.copy2(CARRIERS_SERIES_ORIG, CARRIERS_SERIES_DEST)

    # Read existing rows to check for duplicates
    existing_carriers_rows = []
    if CARRIERS_SERIES_DEST.exists():
        with open(CARRIERS_SERIES_DEST, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            existing_carriers_rows = list(reader)

    print(f"Existing rows in {CARRIERS_SERIES_DEST.name}: {len(existing_carriers_rows)}")

    # Extract S&P rows from carriers_records
    snp_sections = {
        "Bulk Carriers Reported Sold",
        "Tankers / LPG Vessels Reported Sold",
        "Container / Ro-Ro / General Cargo Vessels Reported Sold"
    }
    new_carriers_rows = []
    for r in carriers_records:
        if r["section"] in snp_sections:
            extra_payload = {
                "issue_date": r["issue_date"],
                "stem": r["stem"],
                "source_file": r["source_file"],
            }
            csv_row = {
                "issue": "2026-W38",
                "section": r["section"],
                "page": r["page"],
                "NAME": r["NAME"],
                "TYPE": r["TYPE"],
                "DWT": r["DWT"],
                "BUILT": r["BUILT"],
                "YARD": r["YARD"],
                "PRICE": r["PRICE"],
                "BUYERS": r["BUYERS"],
                "COMMENTS": r["COMMENTS"],
                "extra_json": json.dumps(extra_payload, ensure_ascii=False)
            }
            new_carriers_rows.append(csv_row)

    # Filter duplicates (by issue + NAME)
    existing_keys = set((row.get("issue"), row.get("NAME")) for row in existing_carriers_rows)
    added_carriers = 0
    for nr in new_carriers_rows:
        if (nr["issue"], nr["NAME"]) not in existing_keys:
            existing_carriers_rows.append(nr)
            added_carriers += 1

    carriers_fieldnames = ["issue", "section", "page", "NAME", "TYPE", "DWT", "BUILT", "YARD", "PRICE", "BUYERS", "COMMENTS", "extra_json"]
    with open(CARRIERS_SERIES_DEST, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=carriers_fieldnames)
        writer.writeheader()
        writer.writerows(existing_carriers_rows)

    # Also update CARRIERS_SERIES_ORIG
    if CARRIERS_SERIES_ORIG.exists():
        shutil.copy2(CARRIERS_SERIES_DEST, CARRIERS_SERIES_ORIG)

    print(f"Added {added_carriers} new S&P rows to {CARRIERS_SERIES_DEST}. Total rows now: {len(existing_carriers_rows)}")

    # -------------------------------------------------------------------------
    # 4. APPEND TO CARRIERS INDICES CSV
    # -------------------------------------------------------------------------
    if CARRIERS_INDICES_CSV.exists():
        df_ind = pd.read_csv(CARRIERS_INDICES_CSV)
        new_indices_rows = [
            {"token": "DSPA", "family": "Sale and Purchase Index", "date": "2026-09-21", "value": 4.492, "raw": "4.492", "kind": "period_decimal", "flag": None},
            {"token": "TSPA", "family": "Sale and Purchase Index", "date": "2026-09-21", "value": 10.070, "raw": "10.070", "kind": "period_decimal", "flag": None},
            {"token": "DSRA", "family": "Recycling Index", "date": "2026-09-21", "value": 6.933, "raw": "6.933", "kind": "period_decimal", "flag": None},
            {"token": "TSRA", "family": "Recycling Index", "date": "2026-09-21", "value": 12.465, "raw": "12.465", "kind": "period_decimal", "flag": None},
            {"token": "DNBI", "family": "Newbuilding Index", "date": "2026-09-21", "value": 5.117, "raw": "5.117", "kind": "period_decimal", "flag": None},
            {"token": "TNBI", "family": "Newbuilding Index", "date": "2026-09-21", "value": 8.085, "raw": "8.085", "kind": "period_decimal", "flag": None},
        ]
        # Avoid dupes
        for row in new_indices_rows:
            mask = (df_ind["token"] == row["token"]) & (df_ind["date"] == row["date"])
            if not mask.any():
                df_ind = pd.concat([df_ind, pd.DataFrame([row])], ignore_index=True)
        df_ind.to_csv(CARRIERS_INDICES_CSV, index=False)
        print(f"Updated {CARRIERS_INDICES_CSV.name} with 2026-09-21 index rows.")

    # -------------------------------------------------------------------------
    # 5. DEDICATED BANCOSTA SALES SERIES CSV
    # -------------------------------------------------------------------------
    print("\n--- Generating Bancosta Sales Series CSV ---")
    ban_fieldnames = ["issue", "section", "page", "NAME", "IMO", "TYPE", "DWT", "BUILT", "YARD", "PRICE", "BUYERS", "SS", "COMMENTS", "extra_json"]
    bancosta_sales_rows = []
    for r in bancosta_records:
        if r["section"].startswith("Reported Sales"):
            extra_payload = {
                "issue_date": r["issue_date"],
                "stem": r["stem"],
                "source_file": r["source_file"],
                "price_usd_m": r["PRICE_USD_M"],
                "ss_due": r["SS_DUE"],
            }
            csv_row = {
                "issue": r["issue_date"],
                "section": r["section"],
                "page": r["page"],
                "NAME": r["VESSEL_NAME"],
                "IMO": r["IMO"],
                "TYPE": r["TYPE"],
                "DWT": r["DWT"],
                "BUILT": r["BUILT"],
                "YARD": r["YARD"],
                "PRICE": r["PRICE_RAW"],
                "BUYERS": r["BUYERS"],
                "SS": r["SS"],
                "COMMENTS": r["NOTE"],
                "extra_json": json.dumps(extra_payload, ensure_ascii=False)
            }
            bancosta_sales_rows.append(csv_row)

    with open(BANCOSTA_SERIES_DEST, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=ban_fieldnames)
        writer.writeheader()
        writer.writerows(bancosta_sales_rows)
    print(f"Written {len(bancosta_sales_rows)} rows to {BANCOSTA_SERIES_DEST}")

    # -------------------------------------------------------------------------
    # 6. APPEND TO BANCHERO_DEALS.PARQUET
    # -------------------------------------------------------------------------
    print("\n--- Updating banchero_deals.parquet ---")
    if BANCOSTA_PARQUET.exists():
        df_banchero = pd.read_parquet(BANCOSTA_PARQUET)
        print(f"Existing rows in banchero_deals.parquet: {len(df_banchero)}")

        new_deals = []
        for r in bancosta_records:
            if r["section"].startswith("Reported Sales"):
                deal = {
                    "source_file": f"reports/shipbrokers/banchero_costa/2026/{ban_stem}.pdf",
                    "report_date": pd.to_datetime("2026-09-23"),
                    "vessel": r["VESSEL_NAME"],
                    "imo": int(r["IMO"]),
                    "vessel_type": r["TYPE"],
                    "dwt": int(r["DWT"]),
                    "built": int(r["BUILT"]),
                    "buyer": r["BUYERS"],
                    "seller": None,
                    "price_usd_m": float(r["PRICE_USD_M"]),
                    "ss_due": r["SS_DUE"],
                    "dd_due": None,
                    "delivery": None,
                    "comments": r["NOTE"] if r["NOTE"] else None,
                    "yard": r["YARD"],
                }
                new_deals.append(deal)

        df_new_deals = pd.DataFrame(new_deals)
        # Avoid duplicates on (report_date, imo)
        existing_keys = set(zip(df_banchero["report_date"].dt.strftime("%Y-%m-%d"), df_banchero["imo"]))
        deals_to_add = [d for d in new_deals if ("2026-09-23", d["imo"]) not in existing_keys]

        if deals_to_add:
            df_combined = pd.concat([df_banchero, pd.DataFrame(deals_to_add)], ignore_index=True)
            df_combined.to_parquet(BANCOSTA_PARQUET, index=False)
            print(f"Appended {len(deals_to_add)} deals to {BANCOSTA_PARQUET.name}. Total rows now: {len(df_combined)}")
        else:
            print(f"All {len(new_deals)} deals already present in {BANCOSTA_PARQUET.name}.")

    summary = {
        "status": "success",
        "general_broker": {
            "issue_date": "2026-09-21",
            "file": CARRIERS_PDF.name,
            "sp_bulkers": len([r for r in carriers_records if r["section"] == "Bulk Carriers Reported Sold"]),
            "sp_tankers": len([r for r in carriers_records if r["section"] == "Tankers / LPG Vessels Reported Sold"]),
            "sp_containers": len([r for r in carriers_records if r["section"] == "Container / Ro-Ro / General Cargo Vessels Reported Sold"]),
            "total_sp_reported_sold": 23,
            "demolition_market": len([r for r in carriers_records if r["section"] == "Demolition Market"]),
            "newbuilding_market": len([r for r in carriers_records if r["section"] == "Newbuilding Market"]),
            "bspa_indices": len([r for r in carriers_records if r["section"] == "BSPA as reported (5 years old Vessels)"]),
            "total_records_stamped": len(carriers_records),
        },
        "bancosta": {
            "issue_date": "2026-09-23",
            "file": BANCOSTA_PDF.name,
            "sp_bulkers": len([r for r in bancosta_records if r["section"] == "Reported Sales - Bulk"]),
            "sp_tankers": len([r for r in bancosta_records if r["section"] == "Reported Sales - Tank"]),
            "total_sp_reported_sold": 23,
            "newbuilding_orders": len([r for r in bancosta_records if r["section"] == "Newbuilding Orders"]),
            "indicative_nb_prices": len([r for r in bancosta_records if r["section"] == "Indicative Newbuilding Prices (Chinese Shipyards)"]),
            "baltic_secondhand_assessments": len([r for r in bancosta_records if r["section"] == "Baltic Secondhand Assessments"]),
            "ship_recycling_assessments": len([r for r in bancosta_records if r["section"] == "Ship Recycling Assessments (Baltic Exchange)"]),
            "total_records_stamped": len(bancosta_records),
        },
        "series_updated": [
            str(CARRIERS_SERIES_DEST),
            str(CARRIERS_SERIES_ORIG),
            str(CARRIERS_INDICES_CSV),
            str(BANCOSTA_SERIES_DEST),
            str(BANCOSTA_PARQUET),
        ]
    }
    return summary


if __name__ == "__main__":
    res = run_all()
    print("\nExtraction Summary:")
    print(json.dumps(res, indent=2))
