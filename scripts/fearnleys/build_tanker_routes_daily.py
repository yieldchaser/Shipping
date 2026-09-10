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
- WS-to-TCE continuation: each frozen-real tce branch (real values that ended
  2023-04-25) is tested against its live ws twin via OLS TCE = a + b*WS on the
  shared window. A derived series TANK_<KLASS>_<ROUTE>_TCE_D (real pts
  unchanged + a+b*ws strictly after the tce branch's last date) is emitted
  ONLY when fit R2 >= 0.90; otherwise the pair is recorded in
  meta.skipped_with_reason with its measured diagnostics. Derived series
  carry derived:true and are never presented as source assessments.
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
               "Fuel Oil", "WEEKLY VLCC", "Gibson (9 Routes)", "Counters"]
UNIT_RANK = {"ws": 0, "tce": 1, "usd": 2}
UNIT_LABEL = {"ws": "WS", "tce": "TCE", "usd": "USD"}

# WS-to-TCE continuation (user directive: frozen tce with a live ws twin).
# Derived series are emitted ONLY when the overlap fit is honest (R2 >= gate).
DERIVED_SUFFIX = "_TCE_D"
DERIVED_R2_MIN = 0.90
# Suffix codes of the frozen-real tce branches (real values, ended 2023-04-25).
FROZEN_TCE_SUFFIX = "_TCE"
# The source's 2023-05 taxonomy switch ended the daily tce branches here.
TCE_FROZEN_LAST = "2023-04-25"

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


def ols_fit(xs, ys):
    """OLS y = a + b*x. Returns (a, b, r2, rmse) or None if degenerate."""
    n = len(xs)
    if n < 2:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    if sxx <= 0:
        return None
    b = sxy / sxx
    a = my - b * mx
    ss_res = sum((y - (a + b * x)) ** 2 for x, y in zip(xs, ys))
    ss_tot = sum((y - my) ** 2 for y in ys)
    if ss_tot <= 0:
        return None
    r2 = 1.0 - ss_res / ss_tot
    rmse = (ss_res / n) ** 0.5
    return a, b, r2, rmse


def fit_tce_vs_ws(tce_pts, ws_pts, tce_last):
    """Fit TCE = a + b*WS over the shared window (both series have values).

    Overlap = dates present in BOTH point maps with non-zero values on both
    sides (zero pts are feed debris, not assessments; see derivation_notes).
    The fit window is the shared history BEFORE tce_last; continuation will
    start strictly after it.
    Returns (fit_dict, None) or (None, skip_reason).
    """
    tce = {p[0]: p[1] for p in tce_pts}
    ws = {p[0]: p[1] for p in ws_pts}
    overlap = sorted(e for e in tce if e in ws and tce[e] != 0 and ws[e] != 0)
    fit = ols_fit([ws[e] for e in overlap], [tce[e] for e in overlap])
    if fit is None:
        return None, "degenerate fit (insufficient overlap variation)"
    a, b, r2, rmse = fit
    diag = {"a": round(a, 4), "b": round(b, 6), "r2": round(r2, 4),
            "rmse": round(rmse, 2), "overlap_n": len(overlap),
            "overlap_first": epoch_ms_to_date(min(overlap)),
            "overlap_last": epoch_ms_to_date(max(overlap))}
    if r2 < DERIVED_R2_MIN:
        return None, (
            "overlap fit R2 {:.4f} < {:.2f} gate; measured a={:.4f}, b={:.6f}, "
            "rmse={:.2f}, n={} ({} to {})".format(
                r2, DERIVED_R2_MIN, a, b, rmse, len(overlap),
                diag["overlap_first"], diag["overlap_last"]))
    return diag, None


def epoch_ms_to_date(e):
    d = date(1970, 1, 1).fromordinal(date(1970, 1, 1).toordinal() + e // 86400000)
    return d.isoformat()


def build_derived_series(tce_series, ws_series, fit):
    """Continuation of a frozen-real tce branch from its live ws twin.

    pts = the tce branch's real pts unchanged + a + b*ws for every ws date
    strictly after the tce branch's last date; dedupe keep-last; chronological.
    """
    a, b = fit["a"], fit["b"]
    tce_map = {p[0]: p[1] for p in tce_series["pts"]}
    cont = []
    for e, v in ws_series["pts"]:
        if v == 0 or e <= epoch_ms(tce_series["last"]):
            continue
        val = round(a + b * v, 2)
        if val != int(val):
            val = round(val, 2)
        else:
            val = int(val)
        tce_map[e] = val  # keep-last: a real pt on that date would win anyway
    cont = [(e, tce_map[e]) for e in sorted(tce_map)]
    return cont


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
            "subtype": st,
        }
        order_key[code] = (KLASS_ORDER.index(klass), route,
                           UNIT_RANK.get(unit, 9), code)

    # --- WS-to-TCE continuation (user directive) -----------------------------
    # For every frozen-real tce branch (real values that ended at/around the
    # 2023-04-25 taxonomy cut) with a live ws twin: fit TCE = a + b*WS on the
    # shared window and continue it from the twin ONLY when the fit clears
    # the R2 gate. The real tce branches stay in the cache untouched; derived
    # series are model estimates and never presented as source assessments.
    skipped_with_reason = {}
    for code in [c for c in series if c.endswith(FROZEN_TCE_SUFFIX)]:
        s = series[code]
        base_code = code[: -len(FROZEN_TCE_SUFFIX)]
        ws = series.get(base_code)
        if (ws is None or ws["unit"] != "ws" or s["unit"] != "tce"
                or s["last"] > TCE_FROZEN_LAST
                or not any(v != 0 for _, v in s["pts"])):
            continue  # not a frozen-real tce branch with a live ws twin
        fit, reason = fit_tce_vs_ws(s["pts"], ws["pts"], s["last"])
        if fit is None:
            skipped_with_reason[code] = reason
            continue
        dcode = base_code + DERIVED_SUFFIX
        pts = build_derived_series(s, ws, fit)
        series[dcode] = {
            "label": f"{human_label(s['subtype'], s['route'], 'tce')} "
                     "(WS-continued)",
            "klass": s["klass"],
            "route": s["route"],
            "unit": "tce",
            "cadence": s["cadence"],
            "subtype": s["subtype"],
            "derived": True,
            "derivation": (
                "TCE continued from the live Worldscale twin via a fitted "
                "TCE-vs-WS mapping over the shared window (fit {} to {}, "
                "n={}, R2={:.4f}); real assessments preserved unchanged "
                "before the source stopped publishing them".format(
                    fit["overlap_first"], fit["overlap_last"],
                    fit["overlap_n"], fit["r2"])),
            "fit": dict(fit, ws_twin_code=base_code),
            "pts": pts,
            "first": epoch_ms_to_date(pts[0][0]),
            "last": epoch_ms_to_date(pts[-1][0]),
            "n": len(pts),
        }
        order_key[dcode] = (KLASS_ORDER.index(s["klass"]), s["route"], 1, dcode)

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

    # Wire Gibson Tanker Rates (9 benchmark continuous daily routes)
    gibson_csv = os.path.join(BASE_DIR, "data", "clarksons", "gibson_tanker_rates_continuous_daily.csv")
    if os.path.exists(gibson_csv):
        gibson_routes_meta = [
            ("Mid East/China 270kt", "GIBSON_TD3C", "VLCC TD3C", "MEG / China 270kt", "WS"),
            ("WA/UKC 130kt", "GIBSON_TD20", "Suezmax TD20", "West Africa / UKC 130kt", "WS"),
            ("USG/UKC 70kt", "GIBSON_TD25", "Aframax TD25", "US Gulf / UKC 70kt", "WS"),
            ("Mid East/Japan 75kt", "GIBSON_TC1", "LR2 Clean TC1", "MEG / Japan 75kt", "WS"),
            ("Mid East/Japan 55kt", "GIBSON_TC5", "LR1 Clean TC5", "MEG / Japan 55kt", "WS"),
            ("USG/Brazil 38kt", "GIBSON_MR_USG_BRAZIL", "MR Clean USG/Brazil", "US Gulf / Brazil 38kt", "WS"),
            ("Spore/Australia 35kt", "GIBSON_HANDY_SPORE_AUS", "Handy Clean Spore/Aus", "Singapore / Australia 35kt", "WS"),
            ("Med/Med 30kt", "GIBSON_DIRTY_CROSS_MED", "Dirty Cross-Med 30kt", "Cross Med 30kt", "WS"),
            ("UKC/UKC 30kt", "GIBSON_DIRTY_NORTH_SEA", "Dirty North Sea 30kt", "UK Cont 30kt", "WS"),
        ]
        import pandas as _pd
        gdf = _pd.read_csv(gibson_csv)
        gdf = gdf[gdf["Date"].str.match(r"^\d{4}-\d{2}-\d{2}$", na=False)].sort_values("Date")
        for gcol, gcode, glabel, groute, gunit in gibson_routes_meta:
            if gcol in gdf.columns:
                gsub = gdf[["Date", gcol]].dropna(subset=[gcol])
                gpts = []
                for _, grow in gsub.iterrows():
                    gd_str = grow["Date"]
                    gval = round(float(grow[gcol]), 2)
                    gdt = datetime.strptime(gd_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                    gpts.append([int(gdt.timestamp() * 1000), gval])
                if gpts:
                    series[gcode] = {
                        "label": f"{glabel} ({groute})",
                        "klass": "Gibson (9 Routes)",
                        "route": groute,
                        "unit": gunit,
                        "cadence": "daily",
                        "pts": gpts,
                        "first": gsub["Date"].min(),
                        "last": gsub["Date"].max(),
                        "n": len(gpts),
                    }
                    order_key[gcode] = (KLASS_ORDER.index("Gibson (9 Routes)"), groute, 0, gcode)

    ordered = {}
    for code in sorted(series, key=lambda c: order_key[c]):
        ordered[code] = series[code]

    # Compact per-klass index for the UI group tabs.
    klasses = {}
    for code, s in ordered.items():
        bucket = "derived" if s.get("derived") else s["klass"]
        k = klasses.setdefault(bucket, {"series": 0, "pts": 0,
                                        "first": s["first"], "last": s["last"]})
        k["series"] += 1
        k["pts"] += s["n"]
        k["first"] = min(k["first"], s["first"])
        k["last"] = max(k["last"], s["last"])
    index = {
        "order": [k for k in KLASS_ORDER if k in klasses]
                 + (["derived"] if "derived" in klasses else []),
        "klasses": {k: klasses[k] for k in KLASS_ORDER if k in klasses},
    }
    if "derived" in klasses:
        index["klasses"]["derived"] = klasses["derived"]

    excluded = [{"subtype": st, "reason": reason, "last": stale_last.get(st, "")}
                for st, reason in STALE_SUBTYPES.items()]

    meta = {
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
            "and excluded (see meta.excluded; Museum section covers them). "
            "Zero pts are feed debris, not assessments: the source "
            "occasionally publishes 0 where no assessment exists (e.g. "
            "single-day 0 inside live runs, early-history 0 blocks), so "
            "overlap fits use non-zero pairs only and derived continuations "
            "skip ws dates whose value is 0."),
    }
    if skipped_with_reason:
        meta["skipped_with_reason"] = skipped_with_reason
        meta["derivation_notes"] += (
            " WS-to-TCE continuation pairs were fitted but NOT emitted when "
            "the overlap fit missed the R2 >= {:.2f} gate; each skipped pair "
            "is recorded in meta.skipped_with_reason with its measured "
            "diagnostics (see also per-klass 'derived' index bucket when "
            "pairs do clear the gate).".format(DERIVED_R2_MIN))

    payload = {
        "meta": meta,
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

    # --- derived (WS-to-TCE continuation) gates -------------------------------
    derived = {c: s for c, s in series.items() if s.get("derived")}
    skipped = payload["meta"].get("skipped_with_reason", {})
    for code, s in derived.items():
        assert code.endswith(DERIVED_SUFFIX), f"{code}: derived code without suffix"
        assert s.get("derivation") and s.get("fit"), f"{code}: missing derivation/fit"
        assert s["fit"]["r2"] >= DERIVED_R2_MIN, (
            f"{code}: fit R2 {s['fit']['r2']} below gate")
        assert isinstance(s["fit"].get("ws_twin_code"), str), (
            f"{code}: fit.ws_twin_code missing")
        real_branch = series.get(s["fit"]["ws_twin_code"] + FROZEN_TCE_SUFFIX)
        assert real_branch is not None and real_branch.get("unit") == "tce", (
            f"{code}: real tce branch missing")
        assert series.get(s["fit"]["ws_twin_code"], {}).get("unit") == "ws", (
            f"{code}: ws twin missing or not a ws series")
        prev_e = None
        for e, v in s["pts"]:
            assert (isinstance(v, (int, float)) and v == v
                    and v not in (float("inf"), float("-inf"))), (
                f"{code}: non-finite pt at {e}")
            if prev_e is not None:
                assert e > prev_e, f"{code}: pts not strictly chronological"
            prev_e = e
        # continuation portion must start strictly after the real branch's end
        cut = epoch_ms(real_branch["last"])
        cont = [(e, v) for e, v in s["pts"] if e > cut]
        real = [(e, v) for e, v in s["pts"] if e <= cut]
        assert real and cont, f"{code}: must carry real pts AND continuation pts"
        assert all(e > cut for e, _ in cont), (
            f"{code}: continuation date not strictly after {real_branch['last']}")
        # every real pt must byte-match the untouched tce branch
        tce_map = {p[0]: p[1] for p in real_branch["pts"]}
        assert all(tce_map.get(e) == v for e, v in real), (
            f"{code}: real pts were altered")
        # every continuation value must reproduce a + b*ws
        a, b = s["fit"]["a"], s["fit"]["b"]
        ws_map = {p[0]: p[1] for p in series[s["fit"]["ws_twin_code"]]["pts"]}
        for e, v in cont:
            wsv = ws_map.get(e)
            assert wsv not in (None, 0), (
                f"{code}: continuation pt at {e} without ws value")
            expect = round(a + b * wsv, 2)
            expect = int(expect) if expect == int(expect) else expect
            assert v == expect, f"{code}: pt {e} != a+b*ws ({v} vs {expect})"
    # every frozen-real tce branch with a live ws twin must be EITHER emitted
    # as a derived series OR recorded in meta.skipped_with_reason
    frozen_pairs = []
    for c in series:
        if not c.endswith(FROZEN_TCE_SUFFIX) or c.endswith(DERIVED_SUFFIX):
            continue
        s = series[c]
        ws = series.get(c[: -len(FROZEN_TCE_SUFFIX)])
        if (ws is not None and ws.get("unit") == "ws" and s.get("unit") == "tce"
                and s["last"] <= TCE_FROZEN_LAST
                and any(v != 0 for _, v in s["pts"])):
            frozen_pairs.append(c)
    assert len(derived) + len(skipped) == len(frozen_pairs), (
        f"derived({len(derived)}) + skipped({len(skipped)}) must cover all "
        f"{len(frozen_pairs)} frozen-real tce/ws pairs")

    idx = payload["index"]
    n_derived = sum(1 for s in series.values() if s.get("derived"))
    assert (sum(k["series"] for k in idx["klasses"].values()) + n_derived
            == len(series)), "index/klasses series counts do not add up"
    pts_in_klasses = sum(k["pts"] for k in idx["klasses"].values())
    pts_derived = sum(s["n"] for s in series.values() if s.get("derived"))
    assert pts_in_klasses + pts_derived == sum(s["n"] for s in series.values()), (
        "index/klasses pts totals mismatch")

    return {
        "series": len(series),
        "pts": sum(s["n"] for s in series.values()),
        "derived": len(derived),
        "skipped_with_reason": len(skipped),
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
