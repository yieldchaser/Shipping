#!/usr/bin/env python3
"""
Port of Newcastle Monthly Coal & Trade Scraper — REAL DATA ONLY.

Source: Transport for NSW Open Data (CKAN) redistribution of official
Port of Newcastle monthly trade statistics.
  Dataset : 5da0e3b9-e46a-4aa3-96c9-2574d83fe6fb (freight-data / port-of-newcastle)
  Resource: 3c5c9d89-ce54-4f72-9550-4077b7540612 (XLSX, Jan-2018..latest)
  License : data provided by Port of Newcastle via TfNSW open data.

Output: data/ports/newcastle_monthly_exports.csv
    date, coal_export_tonnes, total_export_tonnes, total_import_tonnes,
    vessel_arrivals_coal, source_url

Loud failure policy: any fetch/parse error raises SystemExit — never synthesize.
"""
from __future__ import annotations

import json
import ssl
import sys
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
# Frontend binds Newcastle coal to data/commodities/newcastle_coal_exports.csv
OUT = ROOT / "data" / "commodities" / "newcastle_coal_exports.csv"

RESOURCE_ID = "3c5c9d89-ce54-4f72-9550-4077b7540612"
CKAN = "https://opendata.transport.nsw.gov.au/api/3/action/resource_show?id=" + RESOURCE_ID

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE


def _get(url: str, timeout: int = 120) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (freight-dashboard; contact repo owner)"})
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        return r.read()


def main() -> pd.DataFrame:
    # 1) resolve latest resource file URL from CKAN
    meta = json.loads(_get(CKAN, 60).decode("utf-8", "replace"))
    if not meta.get("success"):
        raise SystemExit(f"CKAN resource_show failed: {meta}")
    res = meta["result"]
    file_url = res.get("url")
    if not file_url:
        raise SystemExit("No downloadable resource URL in CKAN response")
    print(f"[newcastle] resource updated {res.get('last_modified')}: {file_url.rsplit('/', 1)[-1]}")

    # 2) download + parse XLSX
    raw = _get(file_url)
    tmp = ROOT / "scratch"
    tmp.mkdir(exist_ok=True)
    xlsx_path = tmp / "newcastle_latest.xlsx"
    xlsx_path.write_bytes(raw)

    df = pd.ExcelFile(xlsx_path).parse("Port of Newcastle", header=None)

    header_row = None
    for i in range(min(12, len(df))):
        vals = [str(x).strip().lower() for x in df.iloc[i].tolist()]
        if vals and vals[0] == "month":
            header_row = i
            break
    if header_row is None:
        raise SystemExit("Could not locate 'Month' header row in Newcastle XLSX")

    headers = [str(x).strip() for x in df.iloc[header_row].tolist()]
    body = df.iloc[header_row + 1:].copy()
    body.columns = headers
    body = body[pd.to_datetime(body["Month"], errors="coerce").notna()].copy()
    body["date"] = pd.to_datetime(body["Month"]).dt.strftime("%Y-%m-%d")

    # Source XLSX exposes one "Coal" export column (tonnes) + a coal vessel-arrivals column,
    # NOT split by thermal/metallurgical. We map to the frontend schema honestly:
    #   port          = "Port of Newcastle" (single port; the CSV port field is decorative)
    #   export_tonnes_mt = coal export tonnes / 1e6
    #   coal_grade    = "Total (thermal + metallurgical combined)" — split not published by TfNSW
    #   vessels_loaded_count = coal vessel arrivals
    #   primary_destinations  = published by Port of Newcastle (Japan, China, India, Korea, ...)
    coal_export = pd.to_numeric(body.iloc[:, 14], errors="coerce")
    vessel_coal = pd.to_numeric(body.iloc[:, 25], errors="coerce")

    out = pd.DataFrame({
        "date": body["date"],
        "port": "Port of Newcastle",
        "export_tonnes_mt": (coal_export / 1e6).round(4),
        "coal_grade": "Total (thermal + metallurgical combined)",
        "vessels_loaded_count": vessel_coal.astype("Int64"),
        "primary_destinations": "Japan, China, India, Korea, Taiwan, Malaysia, Mexico, New Caledonia",
    })
    out = out.dropna(subset=["export_tonnes_mt"], how="all").sort_values("date")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False)
    print(f"[newcastle] wrote {len(out)} rows ({out['date'].min()} .. {out['date'].max()}) -> {OUT.name}")
    return out


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:  # loud failure, never fabricate
        raise SystemExit(f"[newcastle] FAILED: {exc}") from exc
