"""
Progressive Year-by-Year Demolition PDF Extractor for 1,038 Hellenic GMS/Best Oasis Reports.
Extracts weekly recycling prices (dry bulk, tankers, containers across India, Bangladesh, Pakistan, Turkey).
Performs an additive, non-destructive upsert into data/derived/scrappage_prices.csv.
"""
import re
import os
import shutil
import time
from pathlib import Path
import pandas as pd
import pypdf

REPO_ROOT = Path(r"C:\Users\Dell\Github\Shipping")
DEMO_DIR = REPO_ROOT / "reports" / "hellenic" / "demolition" / "pdfs"
TARGET_CSV = REPO_ROOT / "data" / "derived" / "scrappage_prices.csv"
BACKUP_CSV = REPO_ROOT / "data" / "derived" / "scrappage_prices.csv.bak"

def parse_demolition_pdf(pdf_path: Path):
    m = re.match(r"^(\d{4}-\d{2}-\d{2})", pdf_path.name)
    if not m:
        return None
    date_str = m.group(1)

    record = {
        "date": date_str,
        "dry_india": None,
        "dry_bangla": None,
        "dry_pak": None,
        "dry_turkey": None,
        "tanker_india": None,
        "tanker_bangla": None,
        "tanker_pak": None,
        "container_india": None
    }

    try:
        if pdf_path.stat().st_size < 1000:
            return None
        with open(pdf_path, "rb") as fh:
            if fh.read(4) != b"%PDF":
                return None
            fh.seek(0)
            reader = pypdf.PdfReader(fh, strict=False)
            full_text = ""
            for p in reader.pages:
                full_text += p.extract_text() + "\n"
    except Exception:
        return None

    # Parse GMS / Best Oasis table patterns
    # Format:
    # 1 India Firming 410 / LDT 430 / LDT 440 / LDT
    # 2 Pakistan Steady 390 / LDT 410 / LDT 420 / LDT
    # 3 Bangladesh Weak 380 / LDT 400 / LDT 410 / LDT
    # 4 Turkey Steady 270 / LDT 280 / LDT 290 / LDT
    
    # 1. India
    m_ind = re.search(r"India\s*(?:Firming|Steady|Weak|Improving|Declining|Flat)?\s*(\d{3}(?:\.\d+)?)\s*(?:/\s*LDT)?\s+(\d{3}(?:\.\d+)?)\s*(?:/\s*LDT)?\s+(\d{3}(?:\.\d+)?)", full_text, re.IGNORECASE)
    if m_ind:
        try:
            d, t, c = float(m_ind.group(1)), float(m_ind.group(2)), float(m_ind.group(3))
            if 200 <= d <= 750 and 200 <= t <= 750:
                record["dry_india"] = d
                record["tanker_india"] = t
                record["container_india"] = c
        except Exception:
            pass

    # 2. Bangladesh
    m_ban = re.search(r"Bangladesh\s*(?:Firming|Steady|Weak|Improving|Declining|Flat)?\s*(\d{3}(?:\.\d+)?)\s*(?:/\s*LDT)?\s+(\d{3}(?:\.\d+)?)\s*(?:/\s*LDT)?\s+(\d{3}(?:\.\d+)?)", full_text, re.IGNORECASE)
    if m_ban:
        try:
            d, t, _ = float(m_ban.group(1)), float(m_ban.group(2)), float(m_ban.group(3))
            if 200 <= d <= 750 and 200 <= t <= 750:
                record["dry_bangla"] = d
                record["tanker_bangla"] = t
        except Exception:
            pass

    # 3. Pakistan
    m_pak = re.search(r"Pakistan\s*(?:Firming|Steady|Weak|Improving|Declining|Flat)?\s*(\d{3}(?:\.\d+)?)\s*(?:/\s*LDT)?\s+(\d{3}(?:\.\d+)?)\s*(?:/\s*LDT)?\s+(\d{3}(?:\.\d+)?)", full_text, re.IGNORECASE)
    if m_pak:
        try:
            d, t, _ = float(m_pak.group(1)), float(m_pak.group(2)), float(m_pak.group(3))
            if 200 <= d <= 750 and 200 <= t <= 750:
                record["dry_pak"] = d
                record["tanker_pak"] = t
        except Exception:
            pass

    # 4. Turkey
    m_tur = re.search(r"Turkey\s*(?:Firming|Steady|Weak|Improving|Declining|Flat)?\s*(\d{3}(?:\.\d+)?)\s*(?:/\s*LDT)?\s+(\d{3}(?:\.\d+)?)\s*(?:/\s*LDT)?\s+(\d{3}(?:\.\d+)?)", full_text, re.IGNORECASE)
    if m_tur:
        try:
            d, _, _ = float(m_tur.group(1)), float(m_tur.group(2)), float(m_tur.group(3))
            max_turkey_bound = 460 if any(yr_mo in date_str for yr_mo in ['2022-03', '2022-04', '2022-05', '2022-06']) else 360
            if 100 <= d <= max_turkey_bound:
                record["dry_turkey"] = d
        except Exception:
            pass

    return record

def upsert_scrappage_to_csv(extracted_records):
    df_old = pd.read_csv(TARGET_CSV)
    old_rows = len(df_old)
    old_dry_ind = int(df_old['dry_india'].notna().sum())

    if not BACKUP_CSV.exists():
        shutil.copy2(TARGET_CSV, BACKUP_CSV)

    merged_by_date = {}
    for _, row in df_old.iterrows():
        d_str = str(row['date']).strip()
        merged_by_date[d_str] = {
            "date": d_str,
            "dry_india": row.get('dry_india') if pd.notna(row.get('dry_india')) else None,
            "dry_bangla": row.get('dry_bangla') if pd.notna(row.get('dry_bangla')) else None,
            "dry_pak": row.get('dry_pak') if pd.notna(row.get('dry_pak')) else None,
            "dry_turkey": row.get('dry_turkey') if pd.notna(row.get('dry_turkey')) else None,
            "tanker_india": row.get('tanker_india') if pd.notna(row.get('tanker_india')) else None,
            "tanker_bangla": row.get('tanker_bangla') if pd.notna(row.get('tanker_bangla')) else None,
            "tanker_pak": row.get('tanker_pak') if pd.notna(row.get('tanker_pak')) else None,
            "container_india": row.get('container_india') if pd.notna(row.get('container_india')) else None
        }

    new_dates = 0
    for d_str, new_rec in extracted_records.items():
        if d_str not in merged_by_date:
            merged_by_date[d_str] = new_rec
            new_dates += 1
        else:
            curr = merged_by_date[d_str]
            for col in ["dry_india", "dry_bangla", "dry_pak", "dry_turkey", "tanker_india", "tanker_bangla", "tanker_pak", "container_india"]:
                if new_rec.get(col) is not None:
                    curr[col] = new_rec[col]

    sorted_dates = sorted(merged_by_date.keys())
    output_rows = [merged_by_date[d] for d in sorted_dates]
    df_new = pd.DataFrame(output_rows)
    cols = ["date", "dry_india", "dry_bangla", "dry_pak", "dry_turkey", "tanker_india", "tanker_bangla", "tanker_pak", "container_india"]
    df_new = df_new[cols]

    new_rows = len(df_new)
    new_dry_ind = int(df_new['dry_india'].notna().sum())

    print(f"\nScrappage Expansion Checkpoint:")
    print(f"  Total Rows: {old_rows} -> {new_rows} (+{new_rows - old_rows})")
    print(f"  dry_india non-null rows: {old_dry_ind} -> {new_dry_ind} (+{new_dry_ind - old_dry_ind})", flush=True)

    assert new_rows >= old_rows, f"FATAL: Dataset shrank! {old_rows} -> {new_rows}"
    assert new_dry_ind >= old_dry_ind, "FATAL: dry_india count decreased!"

    df_new.to_csv(TARGET_CSV, index=False)
    print(f"  [SAVED] Updated {TARGET_CSV.name} successfully!\n", flush=True)

def main():
    print("=" * 80, flush=True)
    print("  PROGRESSIVE DEMOLITION EXTRACTION PIPELINE (1,038 PDF REPORTS)", flush=True)
    print("=" * 80, flush=True)

    all_pdfs = sorted(list(DEMO_DIR.glob("*.pdf")))
    years = ["2026", "2025", "2024", "2023", "2022", "2021"]

    for yr in years:
        yr_pdfs = [p for p in all_pdfs if p.name.startswith(yr)]
        print(f"\n>>> EXTRACTING DEMOLITION YEAR {yr} ({len(yr_pdfs)} PDFs) <<<", flush=True)
        t_yr = time.time()
        yr_records = {}
        for idx, p in enumerate(yr_pdfs, 1):
            rec = parse_demolition_pdf(p)
            if rec and (rec["dry_india"] or rec["dry_bangla"] or rec["dry_pak"]):
                d = rec["date"]
                if d not in yr_records:
                    yr_records[d] = rec
                else:
                    for k, v in rec.items():
                        if v is not None and yr_records[d].get(k) is None:
                            yr_records[d][k] = v
            if idx % 25 == 0 or idx == len(yr_pdfs):
                print(f"  [{yr}] {idx}/{len(yr_pdfs)} parsed ({len(yr_records)} dates captured) in {time.time()-t_yr:.1f}s", flush=True)
        
        print(f"[OK] Completed Demolition Year {yr} in {time.time()-t_yr:.1f}s. Saving incremental checkpoint...", flush=True)
        upsert_scrappage_to_csv(yr_records)

    print("\n[SUCCESS] ALL DEMOLITION YEARS FULLY EXTRACTED AND UPSERTED INTO DATASET!", flush=True)

if __name__ == "__main__":
    main()
