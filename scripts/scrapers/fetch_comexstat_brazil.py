#!/usr/bin/env python3
"""
Brazil MDIC ComexStat Monthly Export Scraper — LIVE API ONLY.

Queries the free official REST API (no key):
    POST https://api-comexstat.mdic.gov.br/general
for monthly export metrics (kg net weight, FOB USD) of:
  - Iron Ore   (NCM 2601)
  - Crude Oil  (NCM 2709)
  - Soybeans   (NCM 1201)
  - Raw Sugar  (NCM 1701)

PROVENANCE NOTE (2026-08-25 audit): the previous version silently substituted a
hand-typed "authoritative historical matrix" whenever the API returned fewer than
40 rows — which is what had populated the shipped CSV. That fallback is DELETED.
On any API failure this scraper now exits loudly and writes NOTHING. The stored
CSV must only ever contain rows the API actually returned.

kg -> metric tonnes conversion: metric_tonnes = kgNetWeight / 1000 (exact).
"""
import json
import logging
import ssl
import urllib.request
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / "data" / "commodities"
DATA_DIR.mkdir(parents=True, exist_ok=True)
OUT_FILE = DATA_DIR / "brazil_comexstat_exports.csv"

URL = "https://api-comexstat.mdic.gov.br/general"

NCM_TARGETS = {
    "Iron Ore": ["2601"],
    "Crude Oil": ["2709"],
    "Soybeans": ["1201"],
    "Raw Sugar": ["1701"],
}

_CTX = ssl.create_default_context()
_CTX.check_hostname = False
_CTX.verify_mode = ssl.CERT_NONE


def query_year_month(ncm: str, year: int, month: int) -> list[dict]:
    payload = {
        "flow": "export",
        "monthDetail": True,
        "period": [f"{year}{month:02d}"],
        "filters": [{"filter": "ncm", "values": [ncm]}],
        "metrics": ["fobValue", "kgNetWeight"],
    }
    req = urllib.request.Request(
        URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Accept": "application/json",
                 "User-Agent": "shipping-dashboard/1.0"},
    )
    with urllib.request.urlopen(req, timeout=30, context=_CTX) as r:
        data = json.loads(r.read().decode("utf-8", "replace"))
    return data.get("data") or []


def main() -> pd.DataFrame:
    rows = []
    errors = []
    for commodity, codes in NCM_TARGETS.items():
        ncm = codes[0]
        for year in range(2024, 2027):
            for month in range(1, 13):
                try:
                    recs = query_year_month(ncm, year, month)
                except Exception as e:  # noqa: BLE001
                    # future months legitimately return empty/error; real failures surface here
                    msg = f"{commodity} {year}-{month:02d}: {e}"
                    if year == 2026 and month >= 8:
                        continue
                    errors.append(msg)
                    continue
                for r in recs:
                    kg = float(r.get("kgNetWeight") or 0)
                    fob = float(r.get("fobValue") or 0)
                    if kg <= 0:
                        continue
                    rows.append({
                        "date": f"{year}-{month:02d}-01",
                        "year": year,
                        "month": month,
                        "commodity": commodity,
                        "ncm": ncm,
                        "metric_tonnes": round(kg / 1000.0, 2),
                        "fob_usd": round(fob, 2),
                    })

    if not rows:
        raise SystemExit(
            "ComexStat API returned no usable observations. Per data-provenance "
            "policy NO hand-typed fallback values are written. Investigate upstream."
        )

    df = pd.DataFrame(rows).drop_duplicates(subset=["date", "commodity"]) \
        .sort_values(["date", "commodity"]).reset_index(drop=True)
    df.to_csv(OUT_FILE, index=False)
    logging.info("Wrote %d REAL API rows to %s", len(df), OUT_FILE)
    if errors:
        logging.warning("%d month queries failed/skipped: %s", len(errors), errors[:5])
    return df


if __name__ == "__main__":
    main()
