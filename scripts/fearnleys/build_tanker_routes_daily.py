#!/usr/bin/env python3
"""build_tanker_routes_daily.py — daily tanker-routes UI cache (Broker Desk S3).

Reads data/derived/fearnpulse_rates_full.csv (the FULL Fearnleys Hasura
catalog, refreshed daily by scripts/fearnleys/daily_fearnleys_sync.py inside
the data_expansion.yml Fearnleys step) and emits
data/derived/fearnleys_tanker_routes_daily.json:

  {meta:{source, built_utc, date_to, excluded:[{subtype,reason,last},...],
         derivation_notes},
   index:{order:[klass,...], klasses:{klass:{series,pts,first,last}}},
   series:{CODE:{label, klass, route, unit, cadence, pts:[[epoch_ms,value],...],
                 first, last, n}}}

- CODE matches the monthly cache convention TANK_<SUBTYPE-SLUG>_<ROUTE-SLUG>
  exactly where a monthly twin exists (read from fearnleys_series_monthly.json)
  so the UI can cross-reference daily vs monthly views. When a route carries
  two live unit branches (ws + tce/usd since the source's 2023-05 taxonomy
  switch), the ws branch keeps the twin code and the second branch takes a
  _WS/_TCE/_USD suffix.
- klass grouping: 'VLCC' | 'Suezmax' | 'Aframax' | 'Dirty' | '1 Year T/C' |
  'Fuel Oil' | 'WEEKLY VLCC' | 'Counters'.
- Stale archived subtypes (BALTIC INDEX, VLCC-MARKET, SUEZMAX-MARKET,
  EQUINOR) are EXCLUDED and recorded in meta.excluded with their last dates;
  the Museum section covers them.
- WEEKLY VLCC and the counts/BROKER MEG Fixture Count carry an honest
  cadence:'weekly' badge; everything else is cadence:'daily'.
- Chronological pts, dedupe keep-last (file order wins on equal dates),
  epoch ms at UTC midnights. No synthesis, no interpolation; gaps stay gaps.
- values rounded to 2dp (published precision, same as the monthly cache);
  whole values emitted as ints. Disclosed in derivation_notes.

Usage:
    python scripts/fearnleys/build_tanker_routes_daily.py --build
    python scripts/fearnleys/build_tanker_routes_daily.py --verify
"""
import argparse
import csv
import json
import os
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timezone

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SRC = os.path.join(BASE_DIR, "data", "derived", "fearnpulse_rates_full.csv")
MONTHLY = os.path.join(BASE_DIR, "data", "derived", "fearnleys_series_monthly.json")
OUT = os.path.join(BASE_DIR, "data", "derived", "fearnleys_tanker_routes_daily.json")

SOURCE = ("Fearnleys Hasura harvest (fearnpulse_rates_full.csv) \u00b7 "
          "per-route tanker assessments as published by Fearnleys")

# Archived subtypes: excluded from the daily cache (Museum section covers them).
STALE_SUBTYPES = {
    "BALTIC INDEX": ("archived pre-2023-05 composite index series; superseded "
                     "by the per-route ws/tce assessments kept here"),
    "VLCC-MARKET": ("archived BITR market-brief series, last published "
                    "2023-04; superseded by the live VLCC ws/usd routes"),
    "SUEZMAX-MARKET": ("archived BITR market-brief series, last published "
                       "2023-05; superseded by the live Suezmax ws/usd routes"),
    "EQUINOR": ("archived EQUINOR fuel-series feed, last published 2023-04; "
                "no longer maintained on the source"),
}
WEEKLY_SUBTYPES = {"WEEKLY VLCC"}
KLASS_BY_SUBTYPE = {
    "VLCC": "VLCC",
    "Suezmax": "Suezmax",
    "Aframax": "Aframax",
    "Dirty": "Dirty",
    "1 Year T/C": "1 Year T/C",
    "Fuel Oil SUEZ": "Fuel Oil",
    "Fuel Oil VLCC": "Fuel Oil",
    "WEEKLY VLCC": "WEEKLY VLCC",
}
KLASS_ORDER = ["VLCC", "Suezmax", "Aframax", "Dirty", "1 Year T/C",
               "Fuel Oil", "WEEKLY VLCC", "Counters"]
UNIT_RANK = {"ws": 0, "tce": 1, "usd": 2}
UNIT_LABEL = {"ws": "WS", "tce": "TCE", "usd": "USD"}

# Per-klass minimum count of series with >= 1800 pts (trading-day depth check).
# Measured 2026-09-09 vs the real CSV: VLCC 14/14, Suezmax 18/19 (WAFR/THAILAND
# starts 2019-08), Aframax 13/26 (17 Aframax routes lost their tce twin in the
# source's 2023-05 taxonomy switch; usd demurrage/entsoe routes start 2020-03+).
CORE_MIN_DEEP = {"VLCC": 14, "Suezmax": 18, "Aframax": 13}
# Dirty assessments start 2019-02 at weekly-ish depth (measured 377+ obs).
DIRTY_MIN_PTS = 380


def slugify(s):
    return re.sub(r"[^A-Za-z0-9]+", "_", str(s)).strip("_").upper()


def epoch_ms(ds):
    y, m, d = ds.split("-")
    return (date(int(y), int(m), int(d)) - date(1970, 1, 1)).days * 86400000


def load_monthly_twins(path=MONTHLY):
    """(subtype, route) -> monthly-cache code, for label-key parity."""
    try:
        with open(path, encoding="utf-8") as f:
            mon = json.load(f)
    except Exception:
        return {}
    return {(v.get("subtype"), v.get("route")): k
            for k, v in mon.get("labels", {}).items()
            if v.get("type") == "TANK"}


def load_rows(src):
    """Stream the CSV; return (series_groups, counts_rows, stale_last, max_date).

    series_groups: (subtype, route, unit) -> [(date_str, rate_str)] in file order.
    counts_rows: the counts/BROKER MEG Fixture Count rows (rate_type='counts').
    stale_last: subtype -> last date seen among excluded rows.
    """
    groups = defaultdict(list)
    counts_rows = []
    stale_last = {}
    max_date = ""
    with open(src, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rt = r.get("rate_type") or ""
            ds = r.get("date") or ""
            if not ds:
                continue
            if ds > max_date:
                max_date = ds
            if rt == "TANK":
                st = r.get("rate_subtype") or ""
                if st in STALE_SUBTYPES:
                    if ds > stale_last.get(st, ""):
                        stale_last[st] = ds
                    continue
                groups[(st, r.get("route") or "", r.get("unit") or "")].append(
                    (ds, r.get("rate") or ""))
            elif rt == "counts" and r.get("rate_subtype") == "BROKER":
                counts_rows.append((ds, r.get("rate") or ""))
    return groups, counts_rows, stale_last, max_date


def build_points(raw):
    """[(date_str, rate_str)] -> (sorted [(epoch_ms, value)], kept date strings).

    Dedupe keep-last (later file rows win on the same date); rows whose rate
    fails to parse are dropped entirely (they never existed for the UI).
    """
    by_date = {}
    for ds, rate in raw:
        try:
            v = round(float(rate), 2)
        except (TypeError, ValueError):
            continue
        if v != v or v in (float("inf"), float("-inf")):
            continue
        if v == int(v):
            v = int(v)
        by_date[ds] = v  # later file rows win (keep-last)
    kept = sorted(by_date)
    return [(epoch_ms(ds), by_date[ds]) for ds in kept], kept


def human_label(subtype, route, unit):
    """Route codes stay as the market's own vocabulary; unit gets a human tag."""
    u = UNIT_LABEL.get(unit, str(unit).upper())
    if subtype == "Dirty":
        return f"{route} (dirty) \u00b7 {u}"
    if subtype == "1 Year T/C":
        return f"1Y TC {route} \u00b7 {u}"
    if subtype.startswith("Fuel Oil"):
        return f"{subtype} {route} \u00b7 {u}"
    if subtype == "WEEKLY VLCC":
        return f"{route} (weekly) \u00b7 {u}"
    return f"{route} \u00b7 {u}"


def series_code(subtype, route, twins):
    key = (subtype, route)
    if key in twins:
        return twins[key]
    if subtype == "Dirty":
        return f"TANK_{slugify(subtype)}_{slugify(route)}"
    return f"TANK_{slugify(subtype)}_{slugify(route)}"


def build_payload(src=SRC, monthly_path=MONTHLY):
    twins = load_monthly_twins(monthly_path)
    groups, counts_rows, stale_last, max_date = load_rows(src)

    series = {}
    # (klass_order, route, unit_rank) for deterministic, stable ordering.
    order_key = {}
    # (subtype, route) may carry two live unit branches (ws + tce/usd since the
    # source's 2023-05 taxonomy switch). The first (by UNIT_RANK: ws, tce, usd)
    # keeps the monthly-twin code; later branches take a _WS/_TCE/_USD suffix.
    branch_seen = defaultdict(int)
    for (st, route, unit), raw in sorted(groups.items(),
                                        key=lambda kv: (kv[0][0], kv[0][1],
                                                        UNIT_RANK.get(kv[0][2], 9))):
        klass = KLASS_BY_SUBTYPE.get(st, st)
        pts, kept = build_points(raw)
        if not pts:
            continue
        cadence = "weekly" if st in WEEKLY_SUBTYPES else "daily"
        base = series_code(st, route, twins)
        idx = branch_seen[(st, route)]
        branch_seen[(st, route)] += 1
        code = base if idx == 0 else f"{base}_{UNIT_LABEL.get(unit, slugify(unit))}"
        series[code] = {
            "label": human_label(st, route, unit),
            "klass": klass,
            "route": route,
            "unit": unit,
            "cadence": cadence,
            "pts": pts,
            "first": kept[0],
            "last": kept[-1],
            "n": len(pts),
        }
        order_key[code] = (KLASS_ORDER.index(klass), route, UNIT_RANK.get(unit, 9))

    if counts_rows:
        pts, kept = build_points(counts_rows)
        if pts:
            code = "COUNTS_BROKER_MEG_FIXTURE_COUNT"
            series[code] = {
                "label": "MEG Fixture Count",
                "klass": "Counters",
                "route": "MEG Fixture Count",
                "unit": "count",
                "cadence": "weekly",
                "pts": pts,
                "first": kept[0],
                "last": kept[-1],
                "n": len(pts),
            }
            order_key[code] = (KLASS_ORDER.index("Counters"), "MEG Fixture Count", 9)

    ordered = {}
    for code in sorted(series, key=lambda c: order_key[c]):
        ordered[code] = series[code]

    # Compact per-klass index for the UI group tabs.
    klasses = {}
    for code, s in ordered.items():
        k = klasses.setdefault(s["klass"], {"series": 0, "pts": 0,
                                            "first": s["first"], "last": s["last"]})
        k["series"] += 1
        k["pts"] += s["n"]
        k["first"] = min(k["first"], s["first"])
        k["last"] = max(k["last"], s["last"])
    index = {
        "order": [k for k in KLASS_ORDER if k in klasses],
        "klasses": {k: klasses[k] for k in KLASS_ORDER if k in klasses},
    }

    excluded = [{"subtype": st, "reason": reason, "last": stale_last.get(st, "")}
                for st, reason in STALE_SUBTYPES.items()]

    payload = {
        "meta": {
            "source": SOURCE,
            "built_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "date_to": max_date,
            "excluded": excluded,
            "derivation_notes": (
                "Daily points pass through uninterpolated: gaps stay gaps, no "
                "weekend synthesis. Dedupe by date with the latest CSV row "
                "winning (keep-last); strictly chronological. Epoch ms at UTC "
                "midnights. Values rounded to 2dp (published precision, same as "
                "the monthly cache); whole values emitted as ints. codes reuse "
                "the monthly-cache TANK_<SUBTYPE>_<ROUTE> convention exactly "
                "where a monthly twin exists so the UI can cross-reference. "
                "Source-side taxonomy switch in 2023-05: the tce twin of many "
                "VLCC/Suezmax/Aframax routes ends 2023-04-25 while the ws/usd "
                "twin continues live \u2014 both kept as separate series. "
                "WEEKLY VLCC and the counts/BROKER MEG Fixture Count are "
                "honestly badged cadence:'weekly'; MEG Fixture Count is a "
                "fixture count (rate_type 'counts'), not a rate. BALTIC INDEX, "
                "VLCC-MARKET, SUEZMAX-MARKET and EQUINOR subtypes are archived "
                "and excluded (see meta.excluded; Museum section covers them)."),
        },
        "index": index,
        "series": ordered,
    }
    return payload


def emit(payload, out=OUT):
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, separators=(",", ":"), ensure_ascii=True)
    return os.path.getsize(out)


def check_floors(payload):
    """Assert the regression floors; return a report dict (raises AssertionError)."""
    series = payload["series"]
    assert series, "no series emitted"

    for code, s in series.items():
        assert s["pts"], f"{code}: empty pts"
        assert s["n"] == len(s["pts"]), f"{code}: n != len(pts)"
        assert s["first"] and s["last"], f"{code}: missing first/last"
        epochs = [p[0] for p in s["pts"]]
        assert epochs == sorted(epochs), f"{code}: pts not chronological"
        assert len(set(epochs)) == len(epochs), f"{code}: duplicate epochs"
        assert all(isinstance(p[0], int) and isinstance(p[1], (int, float))
                   for p in s["pts"]), f"{code}: bad pt types"

    def klass_series(klass):
        return [s for s in series.values() if s["klass"] == klass]

    for klass in ("VLCC", "Suezmax", "Aframax"):
        ks = klass_series(klass)
        deep = [s for s in ks if len(s["pts"]) >= 1800]
        assert len(deep) >= CORE_MIN_DEEP[klass], (
            f"{klass}: only {len(deep)} series with >=1800 pts "
            f"(floor {CORE_MIN_DEEP[klass]})")

    dirty = klass_series("Dirty")
    assert dirty, "no Dirty series"
    assert min(len(s["pts"]) for s in dirty) >= DIRTY_MIN_PTS, (
        f"Dirty: series below {DIRTY_MIN_PTS} pts")

    weekly = [s for s in series.values() if s["cadence"] == "weekly"]
    assert len(weekly) >= 3, "weekly-cadence series missing (WEEKLY VLCC x2 + MEG count)"
    for code, s in series.items():
        if s["cadence"] == "weekly":
            assert code.startswith(("TANK_WEEKLY_VLCC", "COUNTS_BROKER")), (
                f"{code}: unexpected weekly badge")

    stale_codes = {"TANK_BALTIC_INDEX", "TANK_VLCC_MARKET", "TANK_SUEZMAX_MARKET"}
    for code in series:
        assert code not in stale_codes, f"{code}: stale subtype leaked into cache"
        assert "EQUINOR" not in code, f"{code}: stale EQUINOR leaked into cache"
    assert len(payload["meta"]["excluded"]) == 4, "meta.excluded must list 4 subtypes"
    for exc in payload["meta"]["excluded"]:
        assert exc.get("last"), f"meta.excluded {exc['subtype']}: missing last date"

    idx = payload["index"]
    assert sum(k["series"] for k in idx["klasses"].values()) == len(series), (
        "index/klasses series counts do not add up")
    assert sum(k["pts"] for k in idx["klasses"].values()) == \
        sum(s["n"] for s in series.values()), "index/klasses pts totals mismatch"

    return {
        "series": len(series),
        "pts": sum(s["n"] for s in series.values()),
        "deep_core": {k: sum(1 for s in klass_series(k) if len(s["pts"]) >= 1800)
                      for k in ("VLCC", "Suezmax", "Aframax")},
        "klass_counts": {k: len(klass_series(k))
                         for k in KLASS_ORDER if klass_series(k)},
        "date_to": payload["meta"]["date_to"],
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--build", action="store_true", help="rebuild from current CSV")
    ap.add_argument("--verify", action="store_true", help="assert floors on the JSON")
    args = ap.parse_args()
    if not (args.build or args.verify):
        ap.error("nothing to do: pass --build and/or --verify")

    if args.build:
        payload = build_payload(SRC)
        size = emit(payload, OUT)
        report = check_floors(json.load(open(OUT, encoding="utf-8")))
        print(f"built {OUT}: {size} bytes "
              f"({round(size / 1024 / 1024, 2)} MB), "
              f"{report['series']} series / {report['pts']} pts, "
              f"date_to {report['date_to']}")
    if args.verify:
        with open(OUT, encoding="utf-8") as f:
            payload = json.load(f)
        report = check_floors(payload)
        print("verify OK:",
              json.dumps(report, separators=(",", ":")))


if __name__ == "__main__":
    main()
