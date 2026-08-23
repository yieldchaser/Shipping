"""
Progressive Year-by-Year Iron Ore PDF Extractor with frequent (every 10 files) progress reporting.
Processes each year sequentially, updating the CSV after each year.
"""
import re
import os
import shutil
import time
from pathlib import Path
import pandas as pd
import pypdf

REPO_ROOT = Path(r"C:\Users\Dell\Github\Shipping")
PDF_DIR = REPO_ROOT / "reports" / "hellenic" / "iron_ore" / "pdfs"
TARGET_CSV = REPO_ROOT / "data" / "derived" / "iron_ore_restocking.csv"
BACKUP_CSV = REPO_ROOT / "data" / "derived" / "iron_ore_restocking.csv.bak"

def parse_iron_ore_pdf(pdf_path: Path):
    m = re.match(r"^(\d{4}-\d{2}-\d{2})", pdf_path.name)
    if not m:
        return None
    date_str = m.group(1)

    rec = {
        "date": date_str,
        "cfr_62": None,
        "cfr_65": None,
        "port_stock_62": None,
        "port_stock_65": None,
        "port_inventory_mt": None,
        "steel_inventory_mt": None
    }

    try:
        if pdf_path.stat().st_size < 1000:
            return None
        with open(pdf_path, "rb") as fh:
            if fh.read(4) != b"%PDF":
                return None
            fh.seek(0)
            reader = pypdf.PdfReader(fh, strict=False)
            pages_text = []
            for p in reader.pages:
                pages_text.append(p.extract_text() or "")
            combined = "\n".join(pages_text)
    except Exception:
        return None

    lines = [l.strip() for l in combined.splitlines() if l.strip()]

    # 1. IOSI 62% Fe Daily Settlement
    for line in lines:
        if "IOSI62" in line.upper():
            if re.search(r'\b(february|march|april|may|june|july|august|september|october|november|december|spread|equivalent)\b', line, re.I):
                continue
            m_p = re.search(r'IOSI62\s*(?:62%?\s*Fe\s*Fines)?\s*([0-9]{2,3}\.[0-9]{1,2})\b', line, re.I)
            if m_p:
                val = float(m_p.group(1))
                if 40.0 <= val <= 250.0 and val not in [58.0, 61.0, 62.0, 62.5, 65.0]:
                    rec["cfr_62"] = val
                    break

    # 2. IOSI 65% Fe Daily Settlement
    for line in lines:
        if "IOSI65" in line.upper():
            if re.search(r'\b(february|march|april|may|june|july|august|september|october|november|december|spread|equivalent)\b', line, re.I):
                continue
            m_p = re.search(r'IOSI65\s*(?:65%?\s*Fe\s*Fines)?\s*([0-9]{2,3}\.[0-9]{1,2})\b', line, re.I)
            if m_p:
                val = float(m_p.group(1))
                if 50.0 <= val <= 300.0 and val not in [58.0, 61.0, 62.0, 62.5, 65.0]:
                    rec["cfr_65"] = val
                    break

    # 3. IOPI 62% Port Stock Price (RMB/wt)
    for line in lines:
        if "IOPI62" in line.upper():
            if re.search(r'\b(february|march|april|may|june|july|august|september|october|november|december|spread|equivalent)\b', line, re.I):
                continue
            m_p = re.search(r'IOPI62\s*(?:62%?\s*Fe\s*Fines)?\s*([0-9]{3,4})\b', line, re.I)
            if m_p:
                val = float(m_p.group(1))
                if 350.0 <= val <= 1800.0:
                    rec["port_stock_62"] = val
                    break

    # 4. IOPI 65% Port Stock Price (RMB/wt)
    for line in lines:
        if "IOPI65" in line.upper():
            if re.search(r'\b(february|march|april|may|june|july|august|september|october|november|december|spread|equivalent)\b', line, re.I):
                continue
            m_p = re.search(r'IOPI65\s*(?:65%?\s*Fe\s*Fines)?\s*([0-9]{3,4})\b', line, re.I)
            if m_p:
                val = float(m_p.group(1))
                if 400.0 <= val <= 2000.0:
                    rec["port_stock_65"] = val
                    break

    # 5. Total (35 Ports) Inventory in Mt
    for line in lines:
        if "TOTAL (35 PORTS)" in line.upper() or "35 PORTS" in line.upper():
            m_inv = re.search(r'Total\s*\(\s*35\s*Ports\s*\)\s*([0-9]{2,3}\.[0-9]{1,2})\b', line, re.I)
            if not m_inv:
                m_inv = re.search(r'35\s*major\s*ports\s*stood\s*at\s*([0-9]{2,3}\.[0-9]{1,2})\s*million', line, re.I)
            if not m_inv:
                m_inv = re.search(r'Inventory\s*at\s*Chinese\s*Ports\s*\([0-9]+\)\s*(?:million\s*tonnes\s*)?([0-9]{2,3}\.[0-9]{1,2})', line, re.I)
            if m_inv:
                val = float(m_inv.group(1))
                if 50.0 <= val <= 220.0:
                    rec["port_inventory_mt"] = val
                    break

    # 6. Steel Inventory in China
    m_steel = re.search(r"Steel\s*Inventory\s*in\s*China\s*(?:million\s*tonnes\s*)?(\d{1,2}\.\d{1,2})", combined, re.IGNORECASE)
    if m_steel:
        try:
            val = float(m_steel.group(1))
            if 2.0 <= val <= 40.0:
                rec["steel_inventory_mt"] = val
        except ValueError:
            pass

    return rec

def upsert_to_csv(extracted_records):
    df_old = pd.read_csv(TARGET_CSV)
    old_rows = len(df_old)
    old_cfr65 = int(df_old['cfr_65'].notna().sum())
    old_inv = int(df_old['inventories_mt'].notna().sum()) if 'inventories_mt' in df_old.columns else 0

    if not BACKUP_CSV.exists():
        shutil.copy2(TARGET_CSV, BACKUP_CSV)

    merged_by_date = {}
    for _, row in df_old.iterrows():
        d_str = str(row['date']).strip()
        merged_by_date[d_str] = {
            "date": d_str,
            "cfr_62": row.get('cfr_62') if pd.notna(row.get('cfr_62')) else None,
            "cfr_65": row.get('cfr_65') if pd.notna(row.get('cfr_65')) else None,
            "port_stock_62": row.get('port_stock_62') if pd.notna(row.get('port_stock_62')) else None,
            "port_stock_65": row.get('port_stock_65') if pd.notna(row.get('port_stock_65')) else None,
            "inventories_mt": row.get('inventories_mt') if pd.notna(row.get('inventories_mt')) else None,
            "steel_production_mt": row.get('steel_production_mt') if pd.notna(row.get('steel_production_mt')) else None,
            "steel_inventories_mt": row.get('steel_inventories_mt') if pd.notna(row.get('steel_inventories_mt')) else None
        }

    new_dates = 0
    updated_points = 0
    for d_str, new_rec in extracted_records.items():
        if d_str not in merged_by_date:
            merged_by_date[d_str] = {
                "date": d_str,
                "cfr_62": new_rec.get("cfr_62"),
                "cfr_65": new_rec.get("cfr_65"),
                "port_stock_62": new_rec.get("port_stock_62"),
                "port_stock_65": new_rec.get("port_stock_65"),
                "inventories_mt": new_rec.get("port_inventory_mt"),
                "steel_production_mt": None,
                "steel_inventories_mt": new_rec.get("steel_inventory_mt")
            }
            new_dates += 1
        else:
            curr = merged_by_date[d_str]
            if new_rec.get("cfr_62") is not None:
                curr["cfr_62"] = new_rec["cfr_62"]
                updated_points += 1
            if new_rec.get("cfr_65") is not None:
                curr["cfr_65"] = new_rec["cfr_65"]
                updated_points += 1
            if new_rec.get("port_stock_62") is not None:
                curr["port_stock_62"] = new_rec["port_stock_62"]
            if new_rec.get("port_stock_65") is not None:
                curr["port_stock_65"] = new_rec["port_stock_65"]
            if new_rec.get("port_inventory_mt") is not None and curr.get("inventories_mt") is None:
                curr["inventories_mt"] = new_rec["port_inventory_mt"]
            if new_rec.get("steel_inventory_mt") is not None and curr.get("steel_inventories_mt") is None:
                curr["steel_inventories_mt"] = new_rec["steel_inventory_mt"]

    sorted_dates = sorted(merged_by_date.keys())
    output_rows = [merged_by_date[d] for d in sorted_dates]
    df_new = pd.DataFrame(output_rows)
    cols = ["date", "cfr_62", "cfr_65", "port_stock_62", "port_stock_65", "inventories_mt", "steel_production_mt", "steel_inventories_mt"]
    df_new = df_new[cols]

    new_rows = len(df_new)
    new_cfr65 = int(df_new['cfr_65'].notna().sum())
    new_inv = int(df_new['inventories_mt'].notna().sum())

    print(f"\nExpansion Checkpoint:")
    print(f"  Total Rows: {old_rows} -> {new_rows} (+{new_rows - old_rows})")
    print(f"  cfr_65 non-null rows: {old_cfr65} -> {new_cfr65} (+{new_cfr65 - old_cfr65})")
    print(f"  inventories_mt non-null: {old_inv} -> {new_inv} (+{new_inv - old_inv})", flush=True)

    assert new_rows >= old_rows, f"FATAL: Dataset shrank! {old_rows} -> {new_rows}"
    assert new_cfr65 >= old_cfr65, "FATAL: cfr_65 count decreased!"

    df_new.to_csv(TARGET_CSV, index=False)
    print(f"  [SAVED] Updated {TARGET_CSV.name} successfully!\n", flush=True)

def main():
    print("=" * 80, flush=True)
    print("  PROGRESSIVE IRON ORE EXTRACTION PIPELINE (ALL YEARS 2021-2026)", flush=True)
    print("=" * 80, flush=True)

    all_pdfs = sorted(list(PDF_DIR.glob("*.pdf")))
    years = ["2026", "2025", "2024", "2023", "2022", "2021"]

    for yr in years:
        yr_pdfs = [p for p in all_pdfs if p.name.startswith(yr)]
        print(f"\n>>> EXTRACTING YEAR {yr} ({len(yr_pdfs)} PDFs) <<<", flush=True)
        t_yr = time.time()
        yr_records = {}
        for idx, p in enumerate(yr_pdfs, 1):
            rec = parse_iron_ore_pdf(p)
            if rec and (rec["cfr_62"] or rec["cfr_65"] or rec["port_stock_62"]):
                d = rec["date"]
                if d not in yr_records:
                    yr_records[d] = rec
                else:
                    for k, v in rec.items():
                        if v is not None and yr_records[d].get(k) is None:
                            yr_records[d][k] = v
            if idx % 25 == 0 or idx == len(yr_pdfs):
                print(f"  [{yr}] {idx}/{len(yr_pdfs)} parsed ({len(yr_records)} dates captured) in {time.time()-t_yr:.1f}s", flush=True)
        
        # Save after each year!
        print(f"[OK] Completed Year {yr} in {time.time()-t_yr:.1f}s. Saving incremental checkpoint to CSV...", flush=True)
        upsert_to_csv(yr_records)

    print("\n[SUCCESS] ALL YEARS (2021-2026) FULLY EXTRACTED AND UPSERTED INTO DATASET!", flush=True)

if __name__ == "__main__":
    main()
