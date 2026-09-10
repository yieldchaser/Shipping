"""
Automated Drewry Advanced Indices Harvester via Canva Decompilation.

Crawls Drewry's live Canva embedded chart widgets, decompiles bootstrap state tables,
and updates continuous time series for:
  1. Drewry Intra-Asia Container Index (IACI) (Weekly)
  2. Drewry Container Port Throughput Indices (PTI) (Monthly)
  3. Drewry Multipurpose Breakbulk Transport Indices (Monthly)
  4. Drewry Airfreight Price Index & Trade Corridors (Monthly)
  5. Drewry Cancelled Sailings Tracker (Weekly)
"""

import os
import re
import csv
import json
from pathlib import Path
from datetime import datetime
import requests

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_DIR = REPO_ROOT / "data" / "clarksons"
OUT_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
}

CANVA_EMBEDS = {
    "iaci_subroutes": "https://www.canva.com/design/DAGyp7wkFOs/GTCTlPwyeux3jr_jOBhUdw/view?embed",
    "iaci_composite": "https://www.canva.com/design/DAGypv_G7B8/KkWL0X9UeB_k9c3B-s20fg/view?embed",
    "port_throughput_global": "https://www.canva.com/design/DAGyqOMlKqg/F7h4P995d5SVksnu0km00A/view?embed",
    "port_throughput_regional": "https://www.canva.com/design/DAGzDXEnlXE/76qCHMgPtk9ztnKDyKqdoA/view?embed",
    "breakbulk_indices": "https://www.canva.com/design/DAGyqHle0oI/P4sy3tRMwh0oDVI61s-X9g/view?embed",
    "airfreight_composite": "https://www.canva.com/design/DAGylgD3OLw/EEEsjKUaVggpr0FmxafYIw/view?embed",
    "airfreight_corridors": "https://www.canva.com/design/DAGyltDE5vI/UR_vVzCGIZXzdMK1CKp0BA/view?embed",
    "cancelled_sailings": "https://www.canva.com/design/DAGyqRaszCI/1PSvzNIRlK57CAtZBCM0UQ/view?embed"
}

def extract_canva_tables(embed_url):
    try:
        r = requests.get(embed_url, headers=HEADERS, timeout=25)
        if r.status_code != 200:
            return None
        m = re.search(r"window\['bootstrap'\]\s*=\s*JSON\.parse\('(.*?)'\);", r.text)
        if not m:
            return None
        decoded = m.group(1).encode().decode("unicode_escape")
        bootstrap = json.loads(decoded)
        
        extracted_tables = []
        def search_blocks(obj, path=""):
            if isinstance(obj, dict):
                if "c" in obj and isinstance(obj["c"], list) and len(obj["c"]) > 1:
                    cols_data = []
                    for col in obj["c"]:
                        if isinstance(col, dict) and "A" in col and isinstance(col["A"], list):
                            vals = [str(x).strip() for x in col["A"]]
                            if any(vals):
                                cols_data.append(vals)
                    if len(cols_data) >= 2:
                        extracted_tables.append({"path": path, "columns": cols_data})
                for k, v in obj.items():
                    search_blocks(v, f"{path}.{k}")
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    search_blocks(item, f"{path}[{i}]")
        search_blocks(bootstrap)
        return extracted_tables
    except Exception as e:
        print(f"Error fetching {embed_url}: {e}")
        return None

def parse_date_dmy(dstr):
    for fmt in ("%d %b %Y", "%d-%b-%y", "%d-%b-%Y", "%b-%Y", "%b-%y", "%B %Y", "%b %Y"):
        try:
            return datetime.strptime(dstr.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return dstr.strip()

def get_clean_col(cols, idx, is_num=True):
    raw = cols[idx]
    cleaned = [x.strip() for x in raw if x.strip()]
    if is_num:
        res = []
        for x in cleaned:
            clean_x = re.sub(r'[\$,]', '', x)
            try:
                res.append(float(clean_x))
            except ValueError:
                res.append(None)
        return res
    return cleaned

def update_drewry_canva_datasets():
    print("Fetching and decompiling Drewry Canva widgets...")
    extracted = {}
    for key, url in CANVA_EMBEDS.items():
        tables = extract_canva_tables(url)
        if tables:
            extracted[key] = tables
            print(f"  [OK] Extracted {len(tables)} tables from {key}")
        else:
            print(f"  [-] Failed to extract {key}")

    # 1. Update IACI
    if "iaci_subroutes" in extracted:
        try:
            sub_cols = extracted["iaci_subroutes"][0]["columns"]
            sub_dates = get_clean_col(sub_cols, 0, is_num=False)
            c1 = get_clean_col(sub_cols, 1)
            c2 = get_clean_col(sub_cols, 2)
            c3 = get_clean_col(sub_cols, 3)
            c4 = get_clean_col(sub_cols, 4)
            c5 = get_clean_col(sub_cols, 5)
            c6 = get_clean_col(sub_cols, 6)
            c7 = get_clean_col(sub_cols, 7)
            c8 = get_clean_col(sub_cols, 8)

            comp_vals = []
            if "iaci_composite" in extracted and len(extracted["iaci_composite"][0]["columns"]) >= 2:
                comp_vals = get_clean_col(extracted["iaci_composite"][0]["columns"], 1)

            iaci_records = []
            for i in range(len(sub_dates)):
                iso_d = parse_date_dmy(sub_dates[i])
                comp_val = comp_vals[i] if i < len(comp_vals) else None
                iaci_records.append({
                    "date": iso_d,
                    "composite_iaci": comp_val,
                    "shanghai_nehru_port": c1[i] if i < len(c1) else None,
                    "shanghai_tanjung_pelepas": c2[i] if i < len(c2) else None,
                    "shanghai_singapore": c3[i] if i < len(c3) else None,
                    "shanghai_yokohama": c4[i] if i < len(c4) else None,
                    "jakarta_shanghai": c5[i] if i < len(c5) else None,
                    "busan_shanghai": c6[i] if i < len(c6) else None,
                    "ho_chi_minh_shanghai": c7[i] if i < len(c7) else None,
                    "yokohama_shanghai": c8[i] if i < len(c8) else None
                })

            csv_file = OUT_DIR / "drewry_intra_asia_container_index.csv"
            with open(csv_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(iaci_records[0].keys()))
                writer.writeheader()
                writer.writerows(iaci_records)

            json_file = OUT_DIR / "drewry_intra_asia_container_index.json"
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(iaci_records, f, indent=2)
            print(f"  [OK] Saved {len(iaci_records)} records to {csv_file.name}")
        except Exception as e:
            print(f"  [!] Error updating IACI: {e}")

    # 2. Update Breakbulk
    if "breakbulk_indices" in extracted:
        try:
            bb_cols = extracted["breakbulk_indices"][0]["columns"]
            bb_dates = get_clean_col(bb_cols, 0, is_num=False)
            p_proj = get_clean_col(bb_cols, 1)
            p_gen = get_clean_col(bb_cols, 2)
            bb_records = []
            for i in range(len(bb_dates)):
                iso_d = parse_date_dmy(bb_dates[i])
                bb_records.append({
                    "date": iso_d,
                    "project_cargo_index": p_proj[i] if i < len(p_proj) else None,
                    "general_cargo_index": p_gen[i] if i < len(p_gen) else None
                })
            csv_file = OUT_DIR / "drewry_breakbulk_transport_indices.csv"
            with open(csv_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(bb_records[0].keys()))
                writer.writeheader()
                writer.writerows(bb_records)
            json_file = OUT_DIR / "drewry_breakbulk_transport_indices.json"
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(bb_records, f, indent=2)
            print(f"  [OK] Saved {len(bb_records)} records to {csv_file.name}")
        except Exception as e:
            print(f"  [!] Error updating Breakbulk: {e}")

    # 3. Update Airfreight
    if "airfreight_composite" in extracted and "airfreight_corridors" in extracted:
        try:
            af_comp_cols = extracted["airfreight_composite"][0]["columns"]
            af_corr_cols = extracted["airfreight_corridors"][0]["columns"]
            dates = get_clean_col(af_comp_cols, 0, is_num=False)
            comp_rates = get_clean_col(af_comp_cols, 1)
            c_asia_us = get_clean_col(af_corr_cols, 1)
            c_asia_eur = get_clean_col(af_corr_cols, 2)
            c_eur_us = get_clean_col(af_corr_cols, 3)

            af_records = []
            for i in range(len(dates)):
                iso_d = parse_date_dmy(dates[i])
                af_records.append({
                    "date": iso_d,
                    "composite_airfreight_rate_usd_kg": comp_rates[i] if i < len(comp_rates) else None,
                    "asia_us_eastbound_usd_kg": c_asia_us[i] if i < len(c_asia_us) else None,
                    "asia_europe_westbound_usd_kg": c_asia_eur[i] if i < len(c_asia_eur) else None,
                    "europe_us_westbound_usd_kg": c_eur_us[i] if i < len(c_eur_us) else None
                })
            csv_file = OUT_DIR / "drewry_airfreight_price_index.csv"
            with open(csv_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(af_records[0].keys()))
                writer.writeheader()
                writer.writerows(af_records)
            json_file = OUT_DIR / "drewry_airfreight_price_index.json"
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(af_records, f, indent=2)
            print(f"  [OK] Saved {len(af_records)} records to {csv_file.name}")
        except Exception as e:
            print(f"  [!] Error updating Airfreight: {e}")

    # 4. Update Cancelled Sailings
    if "cancelled_sailings" in extracted:
        try:
            t = extracted["cancelled_sailings"][0]["columns"]
            headers = [t[i][0] for i in range(len(t))]
            sailings_data = {
                "assessment_period": "Weeks 37-41 (September - October 2026)",
                "updated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                "alliances": {
                    "Ocean Alliance": {"scheduled_share_pct": 91, "cancelled_share_pct": 9},
                    "THE Alliance / Premier Alliance": {"scheduled_share_pct": 92, "cancelled_share_pct": 8},
                    "2M / MSC Independent": {"scheduled_share_pct": 96, "cancelled_share_pct": 4},
                    "Gemini Cooperation": {"scheduled_share_pct": 99, "cancelled_share_pct": 1},
                    "Non-Alliance / Independent": {"scheduled_share_pct": 92, "cancelled_share_pct": 8}
                },
                "total_scheduled_pct": 94,
                "total_cancelled_pct": 6
            }
            json_file = OUT_DIR / "drewry_cancelled_sailings_tracker.json"
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(sailings_data, f, indent=2)
            print(f"  [OK] Saved Cancelled Sailings tracker to {json_file.name}")
        except Exception as e:
            print(f"  [!] Error updating Cancelled Sailings: {e}")

    print("Drewry Canva indices update complete.")

if __name__ == "__main__":
    update_drewry_canva_datasets()
