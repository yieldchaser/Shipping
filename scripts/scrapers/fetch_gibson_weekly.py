"""
Gibson Shipbrokers Weekly Freight Rate & Intelligence Harvester.

Fetches latest weekly online reports from gibsons.co.uk, extracts the rolling
330-day Chart.js wpDataCharts freight rate curves, and appends new daily observations
to data/clarksons/gibson_tanker_rates_continuous_daily.csv and .json.
"""

import os
import re
import csv
import json
import requests
from pathlib import Path
from datetime import datetime

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = REPO_ROOT / "data" / "clarksons"
CSV_PATH = DATA_DIR / "gibson_tanker_rates_continuous_daily.csv"
JSON_PATH = DATA_DIR / "gibson_tanker_rates_continuous_daily.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
}

ROUTE_SLUG_MAP = {
    "Mid East/China 270kt": "vlcc_mideast_china_270kt",
    "Mid East/Singapore 80kt": "aframax_mideast_singapore_80kt",
    "Baltic/UKC 100kt": "aframax_baltic_ukc_100kt",
    "Cross-Med 80kt": "aframax_cross_med_80kt",
    "WA/UKC 130kt": "suezmax_wa_ukc_130kt",
    "Caribbean/USAC 70kt": "aframax_caribbean_usac_70kt",
    "Mid East/Japan 75kt": "lr2_mideast_japan_75kt",
    "Mid East/Japan 55kt": "lr1_mideast_japan_55kt",
    "Mid East/UKC 90kt": "lr2_mideast_ukc_90kt",
    "Cont/USAC 37kt": "mr_cont_usac_37kt",
    "USG/Cont 38kt": "mr_usg_cont_38kt",
    "Cross-UKC 30kt": "handy_cross_ukc_30kt",
    "Cross-Med 30kt": "handy_cross_med_30kt",
    "Caribs/USG 38kt": "mr_caribs_usg_38kt",
    "Singapore/E Aus 35kt": "mr_singapore_e_aus_35kt",
    "USG/Brazil 38kt": "mr_usg_brazil_38kt",
    "Mid East/Red Sea 80kt": "aframax_mideast_red_sea_80kt",
    "USG/UKC 70kt": "aframax_usg_ukc_70kt",
    "Cross-Med 130kt": "suezmax_cross_med_130kt",
    "SKorea/USWC 50kt": "mr_skorea_uswc_50kt",
    "UKC/USAC 60kt": "panamax_ukc_usac_60kt",
    "USG/Caribs 38kt": "mr_usg_caribs_38kt",
    "USG/ECSA 38kt": "mr_usg_ecsa_38kt",
    "USG/WCSA 38kt": "mr_usg_wcsa_38kt",
    "USG/Chile 38kt": "mr_usg_chile_38kt",
    "USG/POrt 38kt": "mr_usg_port_38kt",
    "USG/Japan 38kt": "mr_usg_japan_38kt"
}

def load_existing_dataset():
    date_map = {}
    existing_cols = ["Date"]
    if CSV_PATH.exists():
        with open(CSV_PATH, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            existing_cols = list(reader.fieldnames) if reader.fieldnames else ["Date"]
            for row in reader:
                d = row.get("Date") or row.get("date")
                if not d:
                    continue
                cleaned_row = {}
                for k, v in row.items():
                    if k in ("Date", "date"):
                        cleaned_row["Date"] = v
                    else:
                        try:
                            cleaned_row[k] = float(v) if v and v.strip() else None
                        except ValueError:
                            cleaned_row[k] = v
                date_map[d] = cleaned_row
    return date_map, existing_cols

def parse_date_gibson(dstr):
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d %b %Y"):
        try:
            return datetime.strptime(dstr.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return dstr.strip()

def fetch_latest_gibson_rates():
    print("Fetching latest Gibson reports...")
    api_url = "https://www.gibsons.co.uk/wp-json/wp/v2/report?per_page=3"
    try:
        r = requests.get(api_url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            print(f"Gibson API error: HTTP {r.status_code}")
            return
        reports = r.json()
    except Exception as e:
        print(f"Error calling Gibson API: {e}")
        return

    date_map, existing_cols = load_existing_dataset()
    initial_count = len(date_map)
    new_obs = 0
    all_cols_set = set(existing_cols)

    for rep in reports:
        link = rep.get("link")
        title = rep.get("title", {}).get("rendered", "")
        print(f"Checking report: {title} ({link})")
        try:
            r_page = requests.get(link, headers=HEADERS, timeout=25)
            if r_page.status_code != 200:
                continue
            html = r_page.text
        except Exception as e:
            print(f"  Error fetching page: {e}")
            continue

        parts = html.split("wpDataCharts[")
        for p in parts[1:]:
            cid_match = re.match(r"^(\d+)\]\s*=\s*", p)
            if not cid_match:
                continue
            script_end = p.find("</script>")
            if script_end == -1:
                continue
            block = p[cid_match.end():script_end].strip().rstrip(";")
            
            labels_m = re.search(r'\"labels\":(\[[^\]]+\])', block)
            if not labels_m:
                continue
            try:
                raw_labels = json.loads(labels_m.group(1))
            except Exception:
                continue
            iso_dates = [parse_date_gibson(l) for l in raw_labels]

            ds_pattern = re.compile(r'\"label\":\"([^\"]+)\".+?\"data\":(\[[^\]]+\])')
            datasets = ds_pattern.findall(block)
            
            for ds_lbl, ds_raw in datasets:
                col_name = ds_lbl.strip()
                all_cols_set.add(col_name)
                try:
                    vals = json.loads(ds_raw)
                except Exception:
                    continue
                for d, val in zip(iso_dates, vals):
                    if d not in date_map:
                        date_map[d] = {"Date": d}
                    if val is not None and str(val).strip() != "":
                        try:
                            date_map[d][col_name] = float(val)
                            new_obs += 1
                        except (ValueError, TypeError):
                            pass

    if date_map:
        sorted_dates = sorted(date_map.keys())
        cols = ["Date"] + [c for c in existing_cols if c != "Date"] + [c for c in sorted(all_cols_set) if c not in existing_cols and c != "Date"]
        final_rows = []
        for d in sorted_dates:
            row = {"Date": d}
            for c in cols[1:]:
                row[c] = date_map[d].get(c)
            final_rows.append(row)

        with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=cols)
            writer.writeheader()
            writer.writerows(final_rows)

        with open(JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(final_rows, f, indent=2)

        print(f"Gibson update finished: {len(final_rows)} total dates (from {initial_count}, added/updated {new_obs} rate points).")

if __name__ == "__main__":
    fetch_latest_gibson_rates()
