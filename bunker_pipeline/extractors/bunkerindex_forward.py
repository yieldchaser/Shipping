#!/usr/bin/env python3
"""
Bunker Index 12-Month Forward Curves Extractor & Synthetic Projection Engine
1. Harvests genuine forward delivery matrices across 12 rolling forward contract months
   for 6 unmasked global hubs: Busan, Fujairah, Hong Kong, Kaohsiung, Rotterdam, Singapore.
2. For masked/paywalled ports (Hamburg, New York, Panama Canal, Houston, Zhoushan, Gibraltar, Off Malta),
   projects forward curves by mapping regional spot basis differentials and benchmark forward slopes.
"""

import os
import re
import logging
from datetime import date
from bs4 import BeautifulSoup
import pandas as pd
from bunker_pipeline.utils.http_client import CLIENT
from bunker_pipeline.utils.normalizer import validate_price

logger = logging.getLogger("BunkerIndexForward")

TARGET_HUBS = ["Busan", "Fujairah", "Hong Kong", "Kaohsiung", "Rotterdam", "Singapore"]

# Regional basis anchors for projecting forward curves on masked ports
MASKED_PORT_ANCHORS = {
    "Hamburg": {"country": "DE", "anchor_hub": "Rotterdam", "region": "NWE"},
    "Gibraltar": {"country": "GI", "anchor_hub": "Rotterdam", "region": "MED"},
    "Off Malta": {"country": "MT", "anchor_hub": "Rotterdam", "region": "MED"},
    "Houston": {"country": "US", "anchor_hub": "Rotterdam", "region": "USG"},
    "New York": {"country": "US", "anchor_hub": "Rotterdam", "region": "USAC"},
    "Panama Canal": {"country": "PA", "anchor_hub": "Houston", "region": "CEN"},
    "Zhoushan": {"country": "CN", "anchor_hub": "Singapore", "region": "EA"},
    "Las Palmas": {"country": "ES", "anchor_hub": "Rotterdam", "region": "ATL"},
    "Istanbul": {"country": "TR", "anchor_hub": "Rotterdam", "region": "MED"},
}

def get_contract_month_label(month_offset: int, as_of: date = None) -> str:
    """Computes YYYY-MM label for a forward month offset (1 = prompt next month)."""
    base = as_of or date.today()
    target_year = base.year
    target_month = base.month + month_offset
    while target_month > 12:
        target_month -= 12
        target_year += 1
    return f"{target_year:04d}-{target_month:02d}"

def fetch_forward_month(month_offset: int, as_of_date_str: str = None) -> pd.DataFrame:
    """
    Fetches the forward prices table for month M (1 to 12).
    Returns a pandas DataFrame of genuine unmasked prices.
    """
    url = f"https://www.bunkerindex.com/center_table_forward_prices_month_{month_offset}_home.php"
    as_of = date.today().strftime("%Y-%m-%d") if not as_of_date_str else as_of_date_str
    contract_month = get_contract_month_label(month_offset)
    
    records = []
    try:
        resp = CLIENT.get(url, timeout=12)
        if resp.status_code != 200:
            logger.error(f"Failed to fetch forward month {month_offset}: HTTP {resp.status_code}")
            return pd.DataFrame()
            
        soup = BeautifulSoup(resp.text, "html.parser")
        for tr in soup.find_all("tr"):
            cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
            if not cells or len(cells) < 7:
                continue
                
            cell0 = cells[0]
            matched_hub = None
            for hub in TARGET_HUBS:
                if cell0.startswith(hub) or hub in cell0:
                    matched_hub = hub
                    break
                    
            if not matched_hub:
                continue
                
            # Discard paywalled rows
            if "Subscribe" in cells[2] or "Subscribe" in cells[4] or "Subscribe" in cells[6]:
                continue
                
            try:
                ifo380 = float(cells[2].replace(",", ""))
                vlsfo = float(cells[4].replace(",", ""))
                mgo = float(cells[6].replace(",", ""))
            except (ValueError, IndexError):
                continue
                
            if not (validate_price(ifo380) and validate_price(vlsfo) and validate_price(mgo)):
                continue
                
            records.append({
                "as_of_date": as_of,
                "port": matched_hub,
                "month_offset": month_offset,
                "contract_month": contract_month,
                "ifo380_usd": ifo380,
                "vlsfo_usd": vlsfo,
                "mgo_usd": mgo,
                "source": "BunkerIndex_Forward"
            })
            
    except Exception as e:
        logger.error(f"Error fetching forward month {month_offset}: {e}")
        
    return pd.DataFrame(records)

def generate_synthetic_projections(unmasked_fwd_df: pd.DataFrame, master_csv_path: str = "bunker_master_historical.csv") -> pd.DataFrame:
    """
    Projects 12-month forward curves for masked ports using regional anchor forward term structure slopes.
    """
    if unmasked_fwd_df.empty:
        return pd.DataFrame()
    if not os.path.exists(master_csv_path):
        alt_path = "data/bunkers/bunker_master_historical.csv"
        if os.path.exists(alt_path):
            master_csv_path = alt_path
        else:
            return pd.DataFrame()
        
    try:
        master_df = pd.read_csv(master_csv_path)
        # Get latest spot price per port and grade
        latest_spots = master_df.sort_values("observation_date").groupby(["port_code", "grade"]).last().reset_index()
    except Exception as e:
        logger.error(f"Could not load master store for forward projection: {e}")
        return pd.DataFrame()

    port_code_map = {
        "Singapore": "SG SIN",
        "Rotterdam": "NL RTM",
        "Houston": "US HOU",
        "New York": "US NYC",
        "Gibraltar": "GI GIB",
        "Zhoushan": "CN ZOS",
        "Panama Canal": "PA BLB",
        "Hamburg": "DE HAM",
        "Off Malta": "MT MLT",
        "Las Palmas": "ES LPA",
        "Istanbul": "TR IST",
    }

    def get_latest_spot(port_name: str, grade_name: str) -> float:
        code = port_code_map.get(port_name)
        if not code:
            sub = latest_spots[latest_spots["port_name"].str.contains(port_name, case=False, na=False)]
        else:
            sub = latest_spots[latest_spots["port_code"] == code]
        sub_grade = sub[sub["grade"] == grade_name]
        if not sub_grade.empty and pd.notna(sub_grade["price_usd"].iloc[0]):
            return float(sub_grade["price_usd"].iloc[0])
        return None

    # Calculate baseline prompt spot for anchor hubs
    anchor_spots = {}
    for hub in TARGET_HUBS:
        anchor_spots[hub] = {
            "IFO380": get_latest_spot(hub, "IFO380") or unmasked_fwd_df[unmasked_fwd_df["port"] == hub]["ifo380_usd"].iloc[0],
            "VLSFO": get_latest_spot(hub, "VLSFO") or unmasked_fwd_df[unmasked_fwd_df["port"] == hub]["vlsfo_usd"].iloc[0],
            "MGO": get_latest_spot(hub, "MGO") or unmasked_fwd_df[unmasked_fwd_df["port"] == hub]["mgo_usd"].iloc[0],
        }

    as_of = unmasked_fwd_df["as_of_date"].iloc[0] if not unmasked_fwd_df.empty else date.today().strftime("%Y-%m-%d")
    projected_rows = []

    for masked_port, info in MASKED_PORT_ANCHORS.items():
        anchor_hub = info["anchor_hub"]
        anchor_base = anchor_spots.get(anchor_hub)
        if not anchor_base:
            continue
            
        port_spot_ifo = get_latest_spot(masked_port, "IFO380") or (anchor_base["IFO380"] * 0.98)
        port_spot_vlsfo = get_latest_spot(masked_port, "VLSFO") or (anchor_base["VLSFO"] * 0.98)
        port_spot_mgo = get_latest_spot(masked_port, "MGO") or (anchor_base["MGO"] * 0.98)

        hub_fwd_rows = unmasked_fwd_df[unmasked_fwd_df["port"] == anchor_hub].sort_values("month_offset")

        for _, f_row in hub_fwd_rows.iterrows():
            m_offset = int(f_row["month_offset"])
            c_month = f_row["contract_month"]

            # Multiplier slope = Anchor_Fwd / Anchor_Spot
            slope_ifo = f_row["ifo380_usd"] / anchor_base["IFO380"] if anchor_base["IFO380"] else 1.0
            slope_vlsfo = f_row["vlsfo_usd"] / anchor_base["VLSFO"] if anchor_base["VLSFO"] else 1.0
            slope_mgo = f_row["mgo_usd"] / anchor_base["MGO"] if anchor_base["MGO"] else 1.0

            projected_ifo = round(port_spot_ifo * slope_ifo, 2)
            projected_vlsfo = round(port_spot_vlsfo * slope_vlsfo, 2)
            projected_mgo = round(port_spot_mgo * slope_mgo, 2)

            projected_rows.append({
                "as_of_date": as_of,
                "port": masked_port,
                "month_offset": m_offset,
                "contract_month": c_month,
                "ifo380_usd": projected_ifo,
                "vlsfo_usd": projected_vlsfo,
                "mgo_usd": projected_mgo,
                "source": f"Synthetic_Projection_{anchor_hub}"
            })

    proj_df = pd.DataFrame(projected_rows)
    logger.info(f"Synthesized {len(proj_df)} forward curve points across {len(MASKED_PORT_ANCHORS)} masked ports.")
    return proj_df

def fetch_all_forward_curves(include_projections: bool = True) -> pd.DataFrame:
    """Fetches all 12 forward months across unmasked hubs and synthesizes projected curves."""
    frames = []
    for m in range(1, 13):
        df_m = fetch_forward_month(m)
        if not df_m.empty:
            frames.append(df_m)
            
    if not frames:
        return pd.DataFrame()
        
    unmasked_df = pd.concat(frames, ignore_index=True)
    logger.info(f"Retrieved {len(unmasked_df)} unmasked forward curve points across {len(unmasked_df['port'].unique())} hubs.")

    if include_projections:
        proj_df = generate_synthetic_projections(unmasked_df)
        if not proj_df.empty:
            combined = pd.concat([unmasked_df, proj_df], ignore_index=True)
            return combined
            
    return unmasked_df

if __name__ == "__main__":
    df = fetch_all_forward_curves(include_projections=True)
    print("Combined Forward Curves (Unmasked + Projected):")
    print(df.groupby(["port", "source"]).size())
