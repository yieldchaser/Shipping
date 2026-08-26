"""EU ETS backfill: ICAP Allowance Price Explorer (official ICAP dataset) has the full
EU ETS daily price series 2019-01 -> 2026-06 in /api/systems (id=34, from-2019 series;
id=33 covers until 2018). Values are EUR/t [primary_market_price, secondary_low, ...].
Write them into eu_ets_carbon_daily.csv as REAL historical observations."""
import json
import ssl
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(r"C:\Users\Dell\Github\Shipping")
OUT = ROOT / "data" / "derived" / "eu_ets_carbon_daily.csv"

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

req = urllib.request.Request(
    "https://allowancepriceexplorer.icapcarbonaction.com/api/systems",
    headers={"User-Agent": "Mozilla/5.0"})
systems = json.loads(urllib.request.urlopen(req, timeout=90, context=ctx).read())

rows = {}
for sid in (33, 34):   # 33 = EU ETS until 2018, 34 = from 2019
    s = [x for x in systems if x.get("id") == sid]
    if not s:
        continue
    prim = (s[0].get("values") or {}).get("primary") or {}
    for day, vals in prim.items():
        try:
            # first element = primary-market price (EEX auction/settlement), EUR/t
            px = float(vals[0])
        except (TypeError, ValueError, IndexError):
            continue
        if px <= 0:
            continue
        rows[str(day)[:10]] = max(px, rows.get(str(day)[:10], 0))

print("ICAP days:", len(rows), "| span:", min(rows), "->", max(rows))

# merge with existing file (live OilPriceAPI rows win — they're the same metric)
existing = pd.DataFrame(columns=["date"])
if OUT.exists():
    try:
        existing = pd.read_csv(OUT)
    except Exception:  # noqa: BLE001
        existing = pd.DataFrame(columns=["date"])

live = existing[existing.get("eua_carbon_price_eur_tco2", pd.Series(dtype=float)).notna()] \
    if "eua_carbon_price_eur_tco2" in existing.columns else existing.iloc[0:0]
live_dates = set(live["date"].astype(str))

backfill = []
for d, p in sorted(rows.items()):
    if d in live_dates:
        continue
    backfill.append({
        "date": d,
        "eua_carbon_price_eur_tco2": round(p, 2),
        "source_created_at": "",
        "singapore_vlsfo_usd_mt": "", "singapore_hsfo_usd_mt": "",
        "singapore_hi5_spread_usd_mt": "", "rotterdam_hi5_spread_usd_mt": "",
        "houston_hi5_spread_usd_mt": "", "capesize_scrubber_savings_usd_day": "",
        "vlcc_scrubber_savings_usd_day": "", "capesize_eu_ets_surcharge_usd_day": "",
        "provenance": "icap_ape_eu_ets_daily",
    })

cols = list(existing.columns) if len(existing.columns) else None
bf = pd.DataFrame(backfill)
if cols:
    bf = bf.reindex(columns=cols + ["provenance"], fill_value="")
combined = pd.concat([existing, bf], ignore_index=True) \
    .sort_values("date").drop_duplicates(subset="date", keep="last").reset_index(drop=True)
combined.to_csv(OUT, index=False)
print(f"wrote {len(combined)} rows ({len(bf)} backfilled from ICAP) -> {OUT.name}")
print(combined.tail(3)[["date", "eua_carbon_price_eur_tco2"]].to_string(index=False))