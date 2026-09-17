#!/usr/bin/env python3
"""
Target 5 — China Demand Side (GACC / chinadata.live) Ingestion Engine
====================================================================
Fetches official monthly China customs import/export data for primary shipping commodities:
1. Iron ore (HS 2601) — Capesize demand (#1 driver, C3 Brazil vs C5 Australia split)
2. Coal (HS 2701) — Panamax / Supramax
3. Bauxite (HS 26060000) — Capesize / Supramax (validates Guinea mirror from demand side)
4. Alumina (HS 28182000) — Handymax / Supramax
5. Soybeans (HS 1201) — Panamax grain (Brazil vs US harvest swing)
6. Crude oil (HS 2709) — VLCC demand
7. LNG / LPG (HS 2711) — Gas carrier demand
8. Mineral / Nitrogenous Fertiliser (HS 3102) — Handysize / Supramax
9. NPK Fertilisers (HS 3105) — Handysize / Supramax
10. Steel products (HS 72, flow=export) — Supramax outbound volume

Source: General Administration of Customs of the People's Republic of China (GACC)
Endpoint: https://chinadata.live/api/v2
Outputs:
- data/commodities/china_customs_monthly_imports.csv
- data/commodities/china_customs_partners_summary.json
"""

import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
COMMODITIES_DIR = REPO_ROOT / "data" / "commodities"
COMMODITIES_DIR.mkdir(parents=True, exist_ok=True)
OUT_CSV = COMMODITIES_DIR / "china_customs_monthly_imports.csv"
OUT_PARTNERS_JSON = COMMODITIES_DIR / "china_customs_partners_summary.json"
MANIFEST_FILE = REPO_ROOT / "data" / "provenance" / "manifest.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

COMMODITY_SPECS = [
    {
        "hs_code": "2601",
        "commodity": "Iron ore",
        "flow": "import",
        "shipping_class": "Capesize",
        "rationale": "Primary Capesize driver; captures Australia C5 vs Brazil C3 origin split",
    },
    {
        "hs_code": "2701",
        "commodity": "Coal",
        "flow": "import",
        "shipping_class": "Panamax / Supramax",
        "rationale": "Key Panamax/Supramax lane; Indonesia & Australia thermal/coking coal imports",
    },
    {
        "hs_code": "26060000",
        "commodity": "Bauxite",
        "flow": "import",
        "shipping_class": "Capesize / Supramax",
        "rationale": "Validates Guinea mirror from demand side; Guinea SMB/Chalco destination",
    },
    {
        "hs_code": "28182000",
        "commodity": "Alumina",
        "flow": "import",
        "shipping_class": "Handymax / Supramax",
        "rationale": "Pairs with bauxite; smelter feed imports",
    },
    {
        "hs_code": "1201",
        "commodity": "Soybeans",
        "flow": "import",
        "shipping_class": "Panamax",
        "rationale": "Major Panamax agricultural demand; Brazil vs US seasonal swing",
    },
    {
        "hs_code": "2709",
        "commodity": "Crude oil",
        "flow": "import",
        "shipping_class": "VLCC",
        "rationale": "Key VLCC driver; Arabian Gulf & Atlantic Basin flows into China",
    },
    {
        "hs_code": "2711",
        "commodity": "LNG / LPG",
        "flow": "import",
        "shipping_class": "Gas carrier",
        "rationale": "Seaborne LNG and LPG import demand from Australia, Qatar, US",
    },
    {
        "hs_code": "3102",
        "commodity": "Fertiliser (Nitrogenous)",
        "flow": "import",
        "shipping_class": "Handysize / Supramax",
        "rationale": "Minor bulk chemical fertilisers",
    },
    {
        "hs_code": "3105",
        "commodity": "Fertilisers (NPK)",
        "flow": "import",
        "shipping_class": "Handysize / Supramax",
        "rationale": "Minor bulk compound fertilisers",
    },
    {
        "hs_code": "72",
        "commodity": "Steel products",
        "flow": "export",
        "shipping_class": "Supramax / Handysize",
        "rationale": "China seaborne steel export outbound driver for geared bulkers",
    },
]


def fetch_commodity(spec):
    """Fetch monthly time series and partner share distributions from chinadata.live API."""
    hs = spec["hs_code"]
    flow = spec["flow"]
    url = f"https://chinadata.live/api/v2/trade/hs/{hs}?flow={flow}&period=all"
    logging.info("Fetching %s (HS %s, %s) from %s", spec["commodity"], hs, flow, url)

    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    payload = r.json()

    if not payload.get("success"):
        logging.warning("API returned success=False for HS %s: %s", hs, payload)

    return payload, url


def process_all_commodities():
    """Download all commodity targets, generate consolidated CSV and partners summary."""
    all_rows = []
    partners_summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "General Administration of Customs of the People's Republic of China (GACC)",
        "api_provider": "chinadata.live / api/v2",
        "commodities": {},
    }

    for spec in COMMODITY_SPECS:
        hs = spec["hs_code"]
        commodity_name = spec["commodity"]
        flow = spec["flow"]
        shipping_class = spec["shipping_class"]

        try:
            payload, source_url = fetch_commodity(spec)
        except Exception as e:
            logging.error("Failed fetching HS %s: %s", hs, e)
            continue

        coverage = payload.get("coverage", {})
        monthly_pts = payload.get("monthly", [])
        top_partners = payload.get("top_partners", [])
        latest_partners = payload.get("latest_partners", [])

        # Build partner summary strings
        p1 = f"{top_partners[0]['partner_name']} ({top_partners[0]['share']*100:.1f}%)" if len(top_partners) > 0 else ""
        p2 = f"{top_partners[1]['partner_name']} ({top_partners[1]['share']*100:.1f}%)" if len(top_partners) > 1 else ""
        p3 = f"{top_partners[2]['partner_name']} ({top_partners[2]['share']*100:.1f}%)" if len(top_partners) > 2 else ""

        # Format partner breakdown for JSON catalog
        partners_summary["commodities"][hs] = {
            "commodity": commodity_name,
            "flow": flow,
            "shipping_class": shipping_class,
            "rationale": spec["rationale"],
            "coverage": coverage,
            "total_monthly_points": len(monthly_pts),
            "latest_month": coverage.get("latest_month"),
            "top_partners_all_time": [
                {
                    "partner": p.get("partner_name"),
                    "share_pct": round(p.get("share", 0) * 100, 2),
                    "value_usd": p.get("value_usd"),
                }
                for p in top_partners[:10]
            ],
            "latest_partners": [
                {
                    "partner": p.get("partner_name"),
                    "share_pct": round(p.get("share", 0) * 100, 2),
                    "value_usd": p.get("value_usd"),
                    "rank": p.get("partner_rank"),
                }
                for p in latest_partners[:10]
            ],
            "source_url": source_url,
        }

        # Monthly series rows
        for pt in monthly_pts:
            month_str = pt.get("month", "")
            value_usd = None
            if month_str and re.match(r"^\d{4}-\d{2}$", str(month_str)):
                month_str = str(month_str)
                try:
                    value_usd = float(pt.get("value_usd", 0.0))
                except (ValueError, TypeError):
                    pass
            elif "year" in pt and "month" in pt:
                try:
                    y = int(pt["year"])
                    m = int(pt["month"])
                    month_str = f"{y:04d}-{m:02d}"
                    val = pt.get("exports") if flow == "export" else pt.get("imports")
                    if val is None:
                        val = pt.get("value_usd")
                    value_usd = float(val) if val is not None else None
                except (ValueError, TypeError):
                    continue

            if not month_str or value_usd is None or value_usd <= 0:
                continue

            date_val = f"{month_str}-01"
            partner_count = pt.get("partner_count", 0)

            all_rows.append({
                "date": date_val,
                "hs_code": hs,
                "commodity": commodity_name,
                "flow": flow,
                "shipping_class": shipping_class,
                "value_usd": float(value_usd),
                "partner_count": int(partner_count),
                "top_partner_1": p1,
                "top_partner_2": p2,
                "top_partner_3": p3,
                "source_url": source_url,
                "publisher": "General Administration of Customs (GACC) / chinadata.live",
                "method": "GACC Official Release (chinadata.live API v2)",
            })

    if not all_rows:
        logging.error("No data rows acquired!")
        sys.exit(1)

    df_new = pd.DataFrame(all_rows)
    if OUT_CSV.exists():
        df_old = pd.read_csv(OUT_CSV)
        df_old = df_old[df_old["date"].astype(str).str.match(r"^\d{4}-\d{2}-\d{2}$")]
        df_old = df_old[pd.to_numeric(df_old["value_usd"], errors="coerce") > 0]
        key = ["date", "commodity", "flow"]
        df = pd.concat([df_old[~df_old.set_index(key).index.isin(df_new.set_index(key).index)], df_new])
    else:
        df = df_new

    df.sort_values(by=["commodity", "date"], inplace=True)
    df.to_csv(OUT_CSV, index=False, lineterminator="\n")
    logging.info("Saved %d verified monthly records to %s", len(df), OUT_CSV)

    with open(OUT_PARTNERS_JSON, "w", encoding="utf-8", newline="\n") as f:
        json.dump(partners_summary, f, indent=2)
    logging.info("Saved partner distribution metadata to %s", OUT_PARTNERS_JSON)

    update_manifest(df)


def update_manifest(df):
    """Update data/provenance/manifest.json with live metadata."""
    if not MANIFEST_FILE.exists():
        logging.warning("Manifest file not found: %s", MANIFEST_FILE)
        return

    with open(MANIFEST_FILE, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    latest_date = df["date"].max()
    manifest["china_customs_monthly_imports"] = {
        "source": "General Administration of Customs (GACC) / chinadata.live",
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "latest_observation": latest_date,
        "rows_count": len(df),
        "status": "LIVE",
    }

    with open(MANIFEST_FILE, "w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, indent=2)
    logging.info("Updated provenance manifest.")


def main():
    process_all_commodities()


if __name__ == "__main__":
    main()
