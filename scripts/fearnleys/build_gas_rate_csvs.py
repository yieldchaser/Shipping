#!/usr/bin/env python3
"""build_gas_rate_csvs.py - LNG / LPG rate CSVs rebuilt from the Fearnleys catalog.

data/derived/lng_charter_rates.csv, lpg_charter_rates.csv and lpg_spot_rates.csv
had no writer: they were committed once and froze at 2026-08-05 while the Broker
Desk kept reading them. This rebuilds all three from data/derived/fearnpulse_rates_full.csv,
which daily_fearnleys_sync.py keeps current, so they refresh with the daily job.

Column -> Fearnleys (rate_type, rate_subtype, route). Checked 2026-09-13: every value
in the old files equals the catalog value on the same date (LNG 2,173 of 2,173).
lngc_174k_nb_price is new; without it no same-size price/charter pair existed.

Only published values are written: no interpolation, no fill, gaps stay gaps.

Usage:
    python scripts/fearnleys/build_gas_rate_csvs.py            # build
    python scripts/fearnleys/build_gas_rate_csvs.py --verify   # also re-check against the catalog
"""
import argparse
import csv
import os
import sys
from collections import defaultdict

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC = os.path.join(BASE_DIR, "data", "derived", "fearnpulse_rates_full.csv")
DERIVED = os.path.join(BASE_DIR, "data", "derived")

FILES = {
    "lng_charter_rates.csv": [
        ("lngc_174k_7y_tc", ("LNG", "BROKER", "7 years TC Rate Modern 174km3 LNGC")),
        ("lngc_174k_10y_tc", ("LNG", "CALCULATED", "10 year TC Rate Newbuilding 174km3 LNGC")),
        ("lngc_80k_nb_price", ("LNG", "BROKER", "80km3 LNGC NB Price")),
        ("lngc_30k_nb_price", ("LNG", "BROKER", "30km3 LNGC NB Price")),
        ("lngc_7k_nb_price", ("LNG", "BROKER", "7.5km3 LNGC NB Price")),
        ("lngc_174k_nb_price", ("LNG", "BROKER", "NB Cost 174k MEGI/XDF")),
    ],
    "lpg_charter_rates.csv": [
        ("vlgc_84k_tc", ("LPG", "TC", "VLGC 84 000 cbm")),
        ("mgc_38k_tc", ("LPG", "TC", "MGC 38 000 cbm")),
        ("hdy_22k_tc", ("LPG", "TC", "HDY S/R 20-22 000 cbm")),
    ],
    "lpg_spot_rates.csv": [
        ("vlgc_spot", ("LPG", "SPOT", "VLGC (84 000 cbm)")),
        ("mgc_spot", ("LPG", "SPOT", "MGC (38 000 cbm)")),
    ],
}


def load_catalog():
    wanted = {key: col for spec in FILES.values() for col, key in spec}
    series = defaultdict(dict)
    with open(SRC, "r", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            key = (r["rate_type"], r["rate_subtype"], r["route"])
            col = wanted.get(key)
            if col is None or r["unit"] != "usd":
                continue
            try:
                series[col][r["date"][:10]] = float(r["rate"])
            except ValueError:
                continue
    missing = [c for c in wanted.values() if not series.get(c)]
    if missing:
        raise SystemExit(f"catalog has no rows for {missing} in {SRC}")
    return series


def build(series):
    for fname, spec in FILES.items():
        cols = [c for c, _ in spec]
        dates = sorted({d for c in cols for d in series[c]})
        path = os.path.join(DERIVED, fname)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(["date"] + cols)
            for d in dates:
                w.writerow([d] + [repr(series[c][d]) if d in series[c] else "" for c in cols])
        print(f"  {fname}: {len(dates)} rows, {dates[0]} -> {dates[-1]}")


def verify(series):
    bad = 0
    for fname, spec in FILES.items():
        with open(os.path.join(DERIVED, fname), "r", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                for c, _ in spec:
                    if r[c] and abs(float(r[c]) - series[c][r["date"]]) > 1e-9:
                        bad += 1
    if bad:
        raise SystemExit(f"{bad} values differ from the catalog")
    print("  verify: every value equals the catalog")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args()
    s = load_catalog()
    build(s)
    if args.verify:
        verify(s)
