"""Verification script for Singletons extraction."""

import json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]

def verify_all():
    print("=== VERIFYING SINGLETONS EXTRACTION ===")
    
    # 1. Check general_broker files
    gen_md = ROOT / "data" / "extracted" / "md" / "general_broker" / "general_broker_21_09_2026_carriers_sales_purchase_market_report_week_38.md"
    gen_json = ROOT / "data" / "extracted" / "md" / "general_broker" / "general_broker_21_09_2026_carriers_sales_purchase_market_report_week_38.tables.json"
    
    assert gen_md.exists(), f"Missing {gen_md}"
    assert gen_json.exists(), f"Missing {gen_json}"
    
    with open(gen_json, "r", encoding="utf-8") as f:
        gen_records = json.load(f)
        
    print(f"General Broker JSON records: {len(gen_records)}")
    assert all(r["issue_date"] == "2026-09-21" for r in gen_records), "All general_broker records must have issue_date 2026-09-21"
    
    # Check section breakdown
    gen_sections = {}
    for r in gen_records:
        sec = r["section"]
        gen_sections[sec] = gen_sections.get(sec, 0) + 1
    print("General Broker Sections:", gen_sections)
    assert gen_sections.get("Bulk Carriers Reported Sold") == 13
    assert gen_sections.get("Tankers / LPG Vessels Reported Sold") == 9
    assert gen_sections.get("Container / Ro-Ro / General Cargo Vessels Reported Sold") == 1
    assert gen_sections.get("Demolition Market") == 2
    assert gen_sections.get("Newbuilding Market") == 3
    assert gen_sections.get("BSPA as reported (5 years old Vessels)") == 6

    # 2. Check bancosta files
    ban_md = ROOT / "data" / "extracted" / "md" / "bancosta" / "bancosta_23_09_2026_banchero_costa_weekly_market_report_week_38_2026.md"
    ban_json = ROOT / "data" / "extracted" / "md" / "bancosta" / "bancosta_23_09_2026_banchero_costa_weekly_market_report_week_38_2026.tables.json"
    
    assert ban_md.exists(), f"Missing {ban_md}"
    assert ban_json.exists(), f"Missing {ban_json}"
    
    with open(ban_json, "r", encoding="utf-8") as f:
        ban_records = json.load(f)
        
    print(f"Bancosta JSON records: {len(ban_records)}")
    assert all(r["issue_date"] == "2026-09-23" for r in ban_records), "All bancosta records must have issue_date 2026-09-23"
    
    ban_sections = {}
    for r in ban_records:
        sec = r["section"]
        ban_sections[sec] = ban_sections.get(sec, 0) + 1
    print("Bancosta Sections:", ban_sections)
    assert ban_sections.get("Reported Sales - Bulk") == 13
    assert ban_sections.get("Reported Sales - Tank") == 10
    assert ban_sections.get("Newbuilding Orders") == 7
    assert ban_sections.get("Indicative Newbuilding Prices (Chinese Shipyards)") == 8
    assert ban_sections.get("Baltic Secondhand Assessments") == 7
    assert ban_sections.get("Ship Recycling Assessments (Baltic Exchange)") == 6

    # 3. Check series files
    carriers_series = ROOT / "data" / "extracted" / "series" / "carriers_sales_series.csv"
    assert carriers_series.exists()
    df_car = pd.read_csv(carriers_series)
    w38_car = df_car[df_car["issue"] == "2026-W38"]
    print(f"Carriers series 2026-W38 rows: {len(w38_car)}")
    assert len(w38_car) == 23, f"Expected 23 rows for 2026-W38 in carriers series, got {len(w38_car)}"
    
    bancosta_series = ROOT / "data" / "extracted" / "series" / "bancosta_sales_series.csv"
    assert bancosta_series.exists()
    df_ban = pd.read_csv(bancosta_series)
    print(f"Bancosta dedicated series rows: {len(df_ban)}")
    assert len(df_ban) == 23, f"Expected 23 rows in bancosta sales series, got {len(df_ban)}"
    assert (df_ban["IMO"].notna()).all(), "All Bancosta sales must have IMO numbers"
    
    # 4. Check banchero_deals.parquet
    parquet_path = ROOT / "data" / "extracted" / "banchero_deals.parquet"
    df_parq = pd.read_parquet(parquet_path)
    w38_parq = df_parq[df_parq["report_date"] == "2026-09-23"]
    print(f"banchero_deals.parquet 2026-09-23 rows: {len(w38_parq)}")
    assert len(w38_parq) == 23, f"Expected 23 rows for 2026-09-23 in banchero_deals.parquet, got {len(w38_parq)}"

    # 5. Cross-Verification of key deals between Bancosta, Carriers, and Clarksons
    print("\n--- Cross-Verification Across Broker Sources ---")
    highland_car = df_car[(df_car["issue"] == "2026-W38") & (df_car["NAME"] == "HIGHLAND")].iloc[0]
    highland_ban = df_ban[df_ban["NAME"] == "Highland"].iloc[0]
    print(f"HIGHLAND: Carriers Price={highland_car['PRICE']}, Bancosta Price={highland_ban['PRICE']}, IMO={highland_ban['IMO']}")
    assert highland_ban["IMO"] == 9339181
    assert "25" in str(highland_car["PRICE"]) and "25" in str(highland_ban["PRICE"])

    bora_car = df_car[(df_car["issue"] == "2026-W38") & (df_car["NAME"] == "BORA")].iloc[0]
    bora_ban = df_ban[df_ban["NAME"] == "Bora"].iloc[0]
    print(f"BORA: Carriers Price={bora_car['PRICE']} (Buyer: {bora_car['BUYERS']}), Bancosta Price={bora_ban['PRICE']} (Buyer: {bora_ban['BUYERS']}), IMO={bora_ban['IMO']}")
    assert bora_ban["IMO"] == 9607112
    assert "22" in str(bora_car["PRICE"]) and "22" in str(bora_ban["PRICE"])

    amalfi_car = df_car[(df_car["issue"] == "2026-W38") & (df_car["NAME"] == "VIENNA WOOD")].iloc[0]
    amalfi_ban = df_ban[df_ban["NAME"] == "PS Amalfi"].iloc[0]
    print(f"PS AMALFI: Bancosta Price={amalfi_ban['PRICE']}, Buyer={amalfi_ban['BUYERS']}, IMO={amalfi_ban['IMO']}")
    assert amalfi_ban["IMO"] == 9439395

    print("\nALL VERIFICATIONS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    verify_all()
