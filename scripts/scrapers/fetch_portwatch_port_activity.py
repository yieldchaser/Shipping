#!/usr/bin/env python3
"""
IMF PortWatch Port Activity - hub-port slice (REAL DATA ONLY)
Builds data/congestion/portwatch_port_congestion.csv (the 43 hub ports the dashboard charts) from
data/congestion/port_calls_daily.csv, which scripts/expansion_portwatch.py keeps current from the IMF PortWatch
Daily_Ports_Data FeatureServer (https://portwatch.imf.org/, Daily_Ports_Data).

Why no network call here (2026-11-01): this script used to re-download every hub port's full history from 2019
in date order. The FeatureServer now times out on the third page of such a query and answers with an error JSON,
which was read as "0 records", so the newest rows were never reached: the file stopped at 2026-09-11 while the
step logged success, and the weekly run hit its 15-minute limit. port_calls_daily.csv already holds the same
service rows for all 2,065 PortWatch ports (fetched incrementally, ObjectId-keyset paging), so the hub slice is
cut from it instead.

IMPORTANT PROVENANCE NOTE (2026-08-25 audit):
An earlier version of this file SYNTHESIZED waiting-time and anchorage-queue series
with a seeded random walk (np.random AR(1)). That output was removed from the
platform: waiting-days / vessels-at-anchorage are NOT published in the open
PortWatch feature service and are NOT fabricated here anymore. This engine
writes only measured fields served by IMF PortWatch.

Upsert: rows already stored are kept; rows present in port_calls_daily.csv replace them (PortWatch revises the
latest weeks). Exit 1 when the source has nothing newer than 14 days, so a stalled feed fails the step.
"""
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = ROOT / "data" / "congestion"
SOURCE = DATA_DIR / "port_calls_daily.csv"
OUT = DATA_DIR / "portwatch_port_congestion.csv"
MAX_LAG_DAYS = 14      # PortWatch publishes weekly (Tuesdays) with a few days' lag

# the dashboard's core hubs; every other portid already in the output file is kept as well
KNOWN_HUBS = {
    "port1069": "Qingdao Port", "port824": "Ningbo", "port955": "Port Hedland", "port816": "Newcastle",
    "port1201": "Singapore", "port1114": "Rotterdam", "port481": "Houston (US-TX)", "port1328": "Tubarao",
    "port458": "Hay Point", "port1072": "Qinhuangdao", "port1105": "Rizhao", "port1160": "Santos",
}
RENAME = {
    "portcalls": "daily_port_calls_total",
    "portcalls_dry_bulk": "daily_port_calls_dry_bulk",
    "portcalls_tanker": "daily_port_calls_tanker",
    "portcalls_container": "daily_port_calls_container",
}
COLS = ["date", "portid", "portname", "country", "hub_code",
        "daily_port_calls_total", "daily_port_calls_dry_bulk",
        "daily_port_calls_tanker", "daily_port_calls_container",
        "import_dry_bulk_kt", "export_dry_bulk_kt",
        "import_tanker_kt", "export_tanker_kt"]


def main() -> int:
    prev = pd.read_csv(OUT, dtype={"portid": str}) if OUT.exists() else pd.DataFrame(columns=COLS)
    hubs = set(KNOWN_HUBS) | set(prev["portid"].dropna())

    usecols = ["date", "portid", "portname", "country", *RENAME, "import_dry_bulk", "export_dry_bulk",
               "import_tanker", "export_tanker"]
    src = pd.read_csv(SOURCE, dtype={"portid": str}, usecols=usecols)
    src = src[src["portid"].isin(hubs)].rename(columns=RENAME)
    if src.empty:
        logging.error("No hub-port rows in %s", SOURCE.name)
        return 1
    src["hub_code"] = src["portid"]
    # tonnages come as metric tons; report kilotonnes for chart scale
    for c in ("import_dry_bulk", "export_dry_bulk", "import_tanker", "export_tanker"):
        src[c + "_kt"] = (pd.to_numeric(src[c], errors="coerce") / 1000.0).round(2)
    src = src[COLS]

    out = (pd.concat([prev[COLS], src], ignore_index=True)
           .drop_duplicates(subset=["portid", "date"], keep="last")
           .sort_values(["portid", "date"]))
    out.to_csv(OUT, index=False, lineterminator="\n")

    latest = src["date"].max()
    stale = sorted(p for p, d in src.groupby("portid")["date"].max().items() if d < latest)
    logging.info("Wrote %d rows for %d ports to %s (latest %s, previous file ended %s)", len(out),
                 out["portid"].nunique(), OUT.name, latest, prev["date"].max() if len(prev) else "-")
    if stale:
        logging.warning("Ports behind %s: %s", latest, ", ".join(stale))
    missing = sorted(hubs - set(src["portid"]))
    if missing:
        logging.warning("Hub ports absent from %s: %s", SOURCE.name, ", ".join(missing))
    if date.fromisoformat(latest) < date.today() - timedelta(days=MAX_LAG_DAYS):
        logging.error("%s ends %s (> %d days old): the PortWatch collector is not updating", SOURCE.name,
                      latest, MAX_LAG_DAYS)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
