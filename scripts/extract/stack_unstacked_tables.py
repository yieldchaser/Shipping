"""
Stack previously unstacked sidecar tables into master series CSVs:
1. advanced_shipping_newbuilding_series.csv
2. advanced_shipping_demo_sales_series.csv
3. advanced_shipping_secondhand_matrix_series.csv
4. xclusiv_newbuilding_orders_series.csv
5. xclusiv_newbuilding_prices_series.csv
6. star_asia_valuation_matrix_series.csv
"""

from __future__ import annotations

import csv
import glob
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
SERIES_DIR = ROOT / "data" / "extracted" / "series"
SERIES_DIR.mkdir(parents=True, exist_ok=True)


def _byte_duplicate_stems(pub: str) -> set:
    """Stems of corpus PDFs for `pub` that are BYTE-IDENTICAL to another PDF.

    A second collection route re-drops the same issue under a different filename
    (measured 2026-10-01: xclusiv 271 PDFs / 264 unique, advanced_shipping
    253/250, star_asia 199/197). Both copies have sidecars, so both get stacked
    and every duplicate issue double-counts. Keep the lexicographically-first
    stem and skip the rest - the sidecar name IS the pdf stem.
    """
    import hashlib
    root = ROOT / "corpus" / "01-brokers" / pub
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
            skip.update(q.stem for q in group[1:])
    return skip



def stack_advanced_shipping():
    _dup = _byte_duplicate_stems("advanced_shipping")
    sidecars = sorted(glob.glob(str(ROOT / "data" / "extracted" / "md" / "advanced_shipping" / "*.tables.json")))
    if _dup:
        _b = len(sidecars); sidecars = [f for f in sidecars if Path(f).name[: -len(".tables.json")] not in _dup]
        print(f"[dedup] advanced_shipping: skipped {_b - len(sidecars)} duplicate sidecar(s)")
    print(f"Processing {len(sidecars)} Advanced Shipping sidecars...")

    nb_rows = []
    demo_rows = []
    sh_rows = []

    for f in sidecars:
        d = json.load(open(f, encoding="utf-8"))
        for r in d.get("newbuilding", []):
            nb_rows.append(r)
        for r in d.get("demolition_sales", []):
            demo_rows.append(r)
        for r in d.get("indicative_secondhand_prices", []):
            sh_rows.append(r)

    # 1. Newbuilding Orders
    if nb_rows:
        nb_file = SERIES_DIR / "advanced_shipping_newbuilding_series.csv"
        fields = [
            "issue_date", "report_week", "section", "units", "capacity", "capacity_raw",
            "capacity_unit", "yard", "delivery", "price_raw", "price_usd_mill",
            "owner", "comments", "page", "source_file"
        ]
        with open(nb_file, "w", newline="", encoding="utf-8") as fp:
            writer = csv.DictWriter(fp, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(nb_rows)
        print(f"Exported {len(nb_rows)} rows to {nb_file.name}")

    # 2. Demolition Sales Fixtures
    if demo_rows:
        demo_file = SERIES_DIR / "advanced_shipping_demo_sales_series.csv"
        fields = [
            "issue_date", "report_week", "vessel_name", "vessel_type", "dwt", "ldt",
            "yob", "price_usd_per_ldt", "country", "comments", "page", "source_file"
        ]
        with open(demo_file, "w", newline="", encoding="utf-8") as fp:
            writer = csv.DictWriter(fp, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(demo_rows)
        print(f"Exported {len(demo_rows)} rows to {demo_file.name}")

    # 3. Secondhand Valuation Matrix
    if sh_rows:
        sh_file = SERIES_DIR / "advanced_shipping_secondhand_matrix_series.csv"
        fields = [
            "issue_date", "report_week", "sector", "vessel_class", "size_str",
            "age", "current_price_usd_mill", "prior_price_usd_mill", "change_pct", "source_file"
        ]
        with open(sh_file, "w", newline="", encoding="utf-8") as fp:
            writer = csv.DictWriter(fp, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(sh_rows)
        print(f"Exported {len(sh_rows)} rows to {sh_file.name}")


def stack_xclusiv():
    _dup = _byte_duplicate_stems("xclusiv")
    sidecars = sorted(glob.glob(str(ROOT / "data" / "extracted" / "md" / "xclusiv" / "*.tables.json")))
    if _dup:
        _b = len(sidecars); sidecars = [f for f in sidecars if Path(f).name[: -len(".tables.json")] not in _dup]
        print(f"[dedup] xclusiv: skipped {_b - len(sidecars)} duplicate sidecar(s)")
    print(f"Processing {len(sidecars)} Xclusiv sidecars...")

    nb_orders = []
    nb_prices = []

    for f in sidecars:
        d = json.load(open(f, encoding="utf-8"))
        for r in d.get("newbuilding_orders", []):
            nb_orders.append(r)
        for r in d.get("indicative_newbuilding_prices", []):
            nb_prices.append(r)

    # 1. Newbuilding Orders
    if nb_orders:
        orders_file = SERIES_DIR / "xclusiv_newbuilding_orders_series.csv"
        fields = [
            "issue_date", "report_week", "type", "units", "size", "yard",
            "buyer", "price", "delivery", "comments", "page", "source_file"
        ]
        with open(orders_file, "w", newline="", encoding="utf-8") as fp:
            writer = csv.DictWriter(fp, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(nb_orders)
        print(f"Exported {len(nb_orders)} rows to {orders_file.name}")

    # 2. Indicative Newbuilding Prices
    if nb_prices:
        prices_file = SERIES_DIR / "xclusiv_newbuilding_prices_series.csv"
        fields = [
            "issue_date", "report_week", "sector", "vessel_type",
            "price_usd_mill", "source_file"
        ]
        with open(prices_file, "w", newline="", encoding="utf-8") as fp:
            writer = csv.DictWriter(fp, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(nb_prices)
        print(f"Exported {len(nb_prices)} rows to {prices_file.name}")


def stack_star_asia():
    _dup = _byte_duplicate_stems("star_asia")
    sidecars = sorted(glob.glob(str(ROOT / "data" / "extracted" / "md" / "star_asia" / "*.tables.json")))
    if _dup:
        _b = len(sidecars); sidecars = [f for f in sidecars if Path(f).name[: -len(".tables.json")] not in _dup]
        print(f"[dedup] star_asia: skipped {_b - len(sidecars)} duplicate sidecar(s)")
    print(f"Processing {len(sidecars)} Star Asia sidecars...")

    matrix_rows = []

    for f in sidecars:
        tables = json.load(open(f, encoding="utf-8"))
        for t in tables:
            hdr = [str(h).strip().upper() for h in t.get("header", [])]
            if not ("5 YEARS" in hdr and ("NB CONTRACT" in hdr or "10 YEARS" in hdr)):
                continue

            issue_date = t.get("issue_date")
            report_week = t.get("report_week")
            source_file = t.get("source_file")

            # Determine sector (Dry Bulk, Tankers, Containers)
            first_col = hdr[0] if hdr else ""
            sector = "Dry Bulk"
            if "TANKER" in first_col:
                sector = "Tankers"
            elif "CONTAINER" in first_col:
                sector = "Containers"

            # Map column indices
            col_map = {}
            for idx, h in enumerate(hdr):
                if not h: continue
                if "TYPE" in h or "CONTAINER" in h or "TANKER" in h:
                    col_map["vessel_type"] = idx
                elif "DWT" in h or "GEARED" in h or "TEU" in h:
                    col_map["size_dwt_teu"] = idx
                elif "NB CONTRACT" in h or h == "NB":
                    col_map["nb_contract_usd_m"] = idx
                elif "PROMPT" in h:
                    col_map["nb_prompt_usd_m"] = idx
                elif re.search(r"\b15\s*YEAR|\b20\s*YEAR", h):
                    col_map["older_year_usd_m"] = idx
                elif re.search(r"\b10\s*YEAR", h):
                    col_map["ten_year_usd_m"] = idx
                elif re.search(r"\b5\s*YEAR", h):
                    col_map["five_year_usd_m"] = idx

            for r in t.get("rows", []):
                if not r or len(r) < 3:
                    continue
                v_type = r[col_map["vessel_type"]].strip() if "vessel_type" in col_map and col_map["vessel_type"] < len(r) else ""
                v_type = re.sub(r"\s*\*.*$", "", v_type).strip()
                if not v_type or v_type.upper() in ["TYPE", "TANKERS", "CONTAINERS", "DESTINATION"]:
                    continue

                size_val = r[col_map["size_dwt_teu"]].strip() if "size_dwt_teu" in col_map and col_map["size_dwt_teu"] < len(r) else ""
                
                # If sector is unknown, infer from v_type
                vt_u = v_type.upper()
                if any(x in vt_u for x in ["VLCC", "SUEZMAX", "AFRAMAX", "LR", "MR"]):
                    cur_sector = "Tankers"
                elif any(x in vt_u for x in ["CAPE", "KAMSARMAX", "PANAMAX", "SUPRA", "ULTRA", "HANDY"]):
                    cur_sector = "Dry Bulk"
                elif any(x in vt_u for x in ["CONTAINER", "TEU", "FEU"]) or "GEARED" in size_val.upper() or "GEARLESS" in size_val.upper():
                    cur_sector = "Containers"
                else:
                    cur_sector = sector

                def clean_num(val_str):
                    if not val_str: return None
                    s = str(val_str).replace("$", "").replace(",", "").replace("(E)", "").replace("*", "").strip()
                    m = re.search(r"\d+(?:\.\d+)?", s)
                    return float(m.group(0)) if m else None

                nb_c = clean_num(r[col_map["nb_contract_usd_m"]]) if "nb_contract_usd_m" in col_map and col_map["nb_contract_usd_m"] < len(r) else None
                nb_p = clean_num(r[col_map["nb_prompt_usd_m"]]) if "nb_prompt_usd_m" in col_map and col_map["nb_prompt_usd_m"] < len(r) else None
                five_y = clean_num(r[col_map["five_year_usd_m"]]) if "five_year_usd_m" in col_map and col_map["five_year_usd_m"] < len(r) else None
                ten_y = clean_num(r[col_map["ten_year_usd_m"]]) if "ten_year_usd_m" in col_map and col_map["ten_year_usd_m"] < len(r) else None
                older_y = clean_num(r[col_map["older_year_usd_m"]]) if "older_year_usd_m" in col_map and col_map["older_year_usd_m"] < len(r) else None

                matrix_rows.append({
                    "issue_date": issue_date,
                    "report_week": report_week,
                    "sector": cur_sector,
                    "vessel_type": v_type,
                    "size_dwt_teu": size_val,
                    "nb_contract_usd_m": nb_c,
                    "nb_prompt_usd_m": nb_p,
                    "five_year_usd_m": five_y,
                    "ten_year_usd_m": ten_y,
                    "older_year_usd_m": older_y,
                    "source_file": source_file,
                })

    if matrix_rows:
        mat_file = SERIES_DIR / "star_asia_valuation_matrix_series.csv"
        fields = [
            "issue_date", "report_week", "sector", "vessel_type", "size_dwt_teu",
            "nb_contract_usd_m", "nb_prompt_usd_m", "five_year_usd_m", "ten_year_usd_m",
            "older_year_usd_m", "source_file"
        ]
        with open(mat_file, "w", newline="", encoding="utf-8") as fp:
            writer = csv.DictWriter(fp, fieldnames=fields)
            writer.writeheader()
            writer.writerows(matrix_rows)
        print(f"Exported {len(matrix_rows)} rows to {mat_file.name}")


if __name__ == "__main__":
    stack_advanced_shipping()
    stack_xclusiv()
    stack_star_asia()
