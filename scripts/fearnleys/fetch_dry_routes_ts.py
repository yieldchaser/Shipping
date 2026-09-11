#!/usr/bin/env python3
"""
fetch_dry_routes_ts.py — Fearnleys market-data service (fearnpulse.com/api/marketapi/TS)
daily dry-route assessment harvest (Capesize / Panamax / Supramax routes).

This is a SEPARATE source from the Hasura GraphQL sync (daily_fearnleys_sync.py):
these tsIds are the Baltic dry route assessments published on the Fearnleys
Weekly Report tiles, served by fearnpulse's own market-data REST endpoint.

Endpoint (no auth):
    GET https://fearnpulse.com/api/marketapi/TS[?last=N][&id=TSID][&date_to=YYYY-MM-DD]
Response: {"columns": [...], "index": [...], "data": [[tsid, value, epoch_ms, seq], ...]}
Row order: OLDEST-FIRST when fetched without `last`, NEWEST-FIRST when `last` is
given — the normalizer detects order by comparing the first/last epochs, so both
shapes land chronological.

Outputs (both appended/merged, never rewritten from scratch):
  data/derived/fearnpulse_dry_routes_full.csv    long archival layer
      columns: tsid,label,klass,route,unit,date,value,raw_pair_meta
  data/derived/fearnleys_dry_routes_daily.json   compact UI bundle
      {meta:{source, fetched_utc, date_to, notes}, series:{CODE:{...pts:[[epoch_ms,value],...]}}}

Derived series SUPRAMAX_TRANSATLANTIC_RV_AVG is transparent arithmetic, not a
fabricated assessment: per day, value = round_half_up((TS120132 + TS120133) / 2) —
the same midpoint formula the Fearnleys Weekly Report tiles publish for the
Supramax Transatlantic RV display. Its rows carry raw_pair_meta recording both
raw inputs.

Merge semantics (both modes): dedupe by (series, date) with latest fetch winning,
rows kept strictly chronological per series, LF line endings on every write.

Usage:
    python scripts/fearnleys/fetch_dry_routes_ts.py --backfill   # full history, all series
    python scripts/fearnleys/fetch_dry_routes_ts.py --refresh    # last ~20 obs days, merge
"""

import argparse
import csv
import io
import json
import os
import sys
import time
from datetime import datetime, timezone

import requests

TS_URL = "https://fearnpulse.com/api/marketapi/TS"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ShippingRepoDryRoutesTS/1.0",
    "Origin": "https://fearnpulse.com",
    "Referer": "https://fearnpulse.com/",
}
PACING_S = 0.6  # polite pacing between series requests
MAX_RETRIES = 3
REFRESH_LAST = 20  # obs-day rows to pull on refresh (~14+ calendar days over weekends)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DERIVED_DIR = os.path.join(BASE_DIR, "data", "derived")
CSV_PATH = os.path.join(DERIVED_DIR, "fearnpulse_dry_routes_full.csv")
JSON_PATH = os.path.join(DERIVED_DIR, "fearnleys_dry_routes_daily.json")

CSV_COLUMNS = ["tsid", "label", "klass", "route", "unit", "date", "value", "raw_pair_meta"]

# tsid -> (code, label, klass, route, unit)
SERIES = {
    10001: ("CAPESIZE_TUBARAO_QINGDAO", "Capesize Tubarao/Qingdao (C3)", "Capesize", "Tubarao / Qingdao", "usd/tonne"),
    120655: ("CAPESIZE_TCE_CONT_FAR_EAST", "Capesize TCE Cont/Far East", "Capesize", "Cont / Far East", "usd/day"),
    10002: ("CAPESIZE_AUSTRALIA_CHINA", "Capesize Australia/China", "Capesize", "Australia / China", "usd/tonne"),
    10003: ("CAPESIZE_NEWCASTLE_QINGDAO", "Capesize Newcastle/Qingdao Coal", "Capesize", "Newcastle / Qingdao", "usd/tonne"),
    120654: ("CAPESIZE_PACIFIC_RV", "Capesize Pacific RV", "Capesize", "Pacific Round Voyage", "usd/day"),
    10010: ("PANAMAX_TRANSATLANTIC_RV", "Panamax Transatlantic RV", "Panamax", "Transatlantic Round Voyage", "usd/day"),
    10011: ("PANAMAX_TCE_CONT_FAR_EAST", "Panamax TCE Cont/Far East", "Panamax", "Cont / Far East", "usd/day"),
    10013: ("PANAMAX_TCE_FAR_EAST_CONT", "Panamax TCE Far East/Cont", "Panamax", "Far East / Cont", "usd/day"),
    10012: ("PANAMAX_TCE_FAR_EAST_RV", "Panamax TCE Far East RV", "Panamax", "Far East Round Voyage", "usd/day"),
    120132: ("SUPRAMAX_TRANSATLANTIC_RV_A", "Supramax Transatlantic RV (raw A)", "Supramax", "Transatlantic Round Voyage", "usd/day"),
    120133: ("SUPRAMAX_TRANSATLANTIC_RV_B", "Supramax Transatlantic RV (raw B)", "Supramax", "Transatlantic Round Voyage", "usd/day"),
    120129: ("SUPRAMAX_US_GULF_CHINA_SJ", "Supramax US Gulf - China/South Japan", "Supramax", "US Gulf / China-South Japan", "usd/day"),
    120137: ("SUPRAMAX_SOUTH_CHINA_INDONESIA_RV", "Supramax South China - Indonesia RV", "Supramax", "South China / Indonesia RV", "usd/day"),
}
AVG_CODE = "SUPRAMAX_TRANSATLANTIC_RV_AVG"
AVG_PAIR = (120132, 120133)
SOURCE = "Fearnleys market-data service (fearnpulse.com/api/marketapi/TS) \u00b7 Baltic dry route assessments as published on Fearnleys Weekly Report tiles"


def tsid_for_code(code):
    """Numeric tsid for a canonical series code; empty string for the derived avg."""
    if code == AVG_CODE:
        return ""
    for tsid, (c, _l, _k, _r, _u) in SERIES.items():
        if c == code:
            return tsid
    return ""


def round_half_up(x):
    """Midpoint rounding as published: .5 rounds up (values are positive usd/day)."""
    import math
    return int(math.floor(x + 0.5))


def fetch_series(tsid, last=None, timeout=60):
    """Fetch one series; return list of (epoch_ms, value) chronological, deduped latest-wins."""
    params = {"id": tsid}
    if last:
        params["last"] = int(last)
    last_err = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(TS_URL, headers=HEADERS, params=params, timeout=timeout)
            if resp.status_code in (429, 500, 502, 503, 504):
                time.sleep(2.0 * (attempt + 1))
                continue
            resp.raise_for_status()
            payload = resp.json()
            data = payload.get("data") or []
            by_date = {}
            if data:
                # Normalize either row order to chronological.
                if data[0][2] > data[-1][2]:
                    data = list(reversed(data))
                for row in data:
                    epoch, value = int(row[2]), row[1]
                    if value is None:
                        continue
                    by_date[epoch] = value  # latest fetch wins within this payload
            return sorted(by_date.items())
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(2.0 * (attempt + 1))
    raise RuntimeError(f"tsid {tsid} fetch failed after {MAX_RETRIES} attempts: {last_err}")


def label_to_code_map():
    """Map CSV `label` values back to canonical series codes (incl. derived avg)."""
    m = {label: code for _tsid, (code, label, _k, _r, _u) in SERIES.items()}
    m[AVG_CODE] = AVG_CODE
    return m


def load_csv_rows(path):
    """Read existing archive (handles LF or CRLF); return {(code,date): (value, raw_pair_meta)}."""
    merged = {}
    l2c = label_to_code_map()
    if not os.path.exists(path):
        return merged
    with open(path, "rb") as f:
        text = f.read().decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        code = l2c.get((row.get("label") or "").strip(), (row.get("label") or "").strip())
        date = (row.get("date") or "").strip()
        if not code or not date:
            continue
        merged[(code, date)] = (
            (row.get("value") or "").strip(),
            (row.get("raw_pair_meta") or "").strip(),
        )
    return merged


def compute_avg(merged):
    """Recompute the Supramax Transatlantic RV average from the two raw series.

    Returns {(AVG_CODE, date): (value, raw_pair_meta)} for days where BOTH raw
    series have a value. Called after every merge so the derived series always
    reflects the merged raw pair.
    """
    out = {}
    a = {d: v for (c, d), (v, _) in merged.items() if c == "SUPRAMAX_TRANSATLANTIC_RV_A"}
    b = {d: v for (c, d), (v, _) in merged.items() if c == "SUPRAMAX_TRANSATLANTIC_RV_B"}
    for d in sorted(set(a) & set(b)):
        try:
            va, vb = float(a[d]), float(b[d])
        except ValueError:
            continue
        avg = round_half_up((va + vb) / 2.0)
        meta = f"mean(120132:{a[d]},120133:{b[d]})"
        out[(AVG_CODE, d)] = (str(avg), meta)
    return out


def write_csv(merged, path):
    """Write long archive, LF endings, rows grouped per series chronological."""
    by_code = {}
    for (code, date), (value, raw_meta) in merged.items():
        by_code.setdefault(code, []).append((date, value, raw_meta))
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    for code in sorted(by_code):
        info = None
        for _tsid, (c, label, klass, route, unit) in SERIES.items():
            if c == code:
                info = (label, klass, route, unit)
                break
        if info is None:
            info = (code, "Supramax", "Transatlantic Round Voyage", "usd/day")
        label, klass, route, unit = info
        for date, value, raw_meta in sorted(by_code[code]):
            writer.writerow([tsid_for_code(code), label, klass, route, unit, date, value, raw_meta])
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        f.write(buf.getvalue())
    os.replace(tmp, path)


def write_json(merged, fetched_utc, path):
    """Write the compact UI bundle per the DATA SHAPE spec."""
    by_code = {}
    for (code, date), (value, _raw) in merged.items():
        by_code.setdefault(code, []).append((date, value))
    series = {}
    for code in sorted(by_code):
        rows = sorted(by_code[code])
        pts = []
        for date, value in rows:
            epoch = int(datetime.strptime(date, "%Y-%m-%d")
                        .replace(tzinfo=timezone.utc).timestamp() * 1000)
            try:
                fv = float(value)
            except ValueError:
                continue
            pts.append([epoch, int(fv) if fv == int(fv) else fv])
        if not pts:
            continue
        entry = {
            "tsid": None,
            "label": code,
            "route": "",
            "klass": "",
            "unit": "usd/day",
            "pts": pts,
            "first": rows[0][0],
            "last": rows[-1][0],
            "n": len(pts),
        }
        for tsid, (c, label, klass, route, unit) in SERIES.items():
            if c == code:
                entry.update({"tsid": tsid, "label": label, "route": route,
                              "klass": klass, "unit": unit})
                break
        if code == AVG_CODE:
            entry.update({
                "tsid": None,
                "label": "Supramax Transatlantic RV (published avg)",
                "route": "Transatlantic Round Voyage",
                "klass": "Supramax",
                "unit": "usd/day",
                "derivation": "mean of TS 120132 + TS 120133, published-midpoint formula",
            })
        series[code] = entry
    raw_lasts = [s["last"] for c, s in series.items() if c != AVG_CODE]
    date_to = max(raw_lasts) if raw_lasts else fetched_utc[:10]
    payload = {
        "meta": {
            "source": SOURCE,
            "fetched_utc": fetched_utc,
            "date_to": date_to,
            "notes": (
                "SUPRAMAX_TRANSATLANTIC_RV_AVG is transparent arithmetic: per day, "
                "value = midpoint of raw TS 120132 and TS 120133, rounded half-up — the same "
                "midpoint the Fearnleys Weekly Report tiles publish for Supramax Transatlantic RV. "
                "Raw pair rows in the CSV carry raw_pair_meta with both inputs. "
                "Fetched WITHOUT last param for full depth on --backfill; --refresh pulls ~20 obs days "
                "and merges latest-wins by (series, date). Series depth differs because Fearnleys "
                "launched these assessments at different dates (Panamax 2018, Supramax 2023, "
                "Capesize RV/TCE 2024, Capesize Australia/China 1999). Stale Market Brief series "
                "(bunker fuels 303/304/306/307, FX 5001/5002/5003, SOFR 12100, Brent 316) are NOT "
                "harvested here — several are months stale on the source."
            ),
        },
        "series": series,
    }
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        json.dump(payload, f, separators=(",", ":"))
        f.write("\n")
    os.replace(tmp, path)


def run(mode):
    fetched_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    merged = load_csv_rows(CSV_PATH)
    pre_rows = len(merged)
    print(f"[{mode}] existing rows: {pre_rows}", flush=True)
    for tsid, (code, label, _klass, _route, _unit) in SERIES.items():
        pts = fetch_series(tsid, last=None if mode == "backfill" else REFRESH_LAST)
        if pts:
            dates = [datetime.fromtimestamp(e / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
                     for e, _v in pts]
            for d, (_e, v) in zip(dates, pts):
                merged[(code, d)] = (repr(float(v)) if isinstance(v, (int, float)) and
                                     isinstance(v, float) else str(v), "")
            print(f"  tsid {tsid} {code}: +{len(pts)} rows "
                  f"({dates[0]}..{dates[-1]})", flush=True)
        else:
            print(f"  tsid {tsid} {code}: EMPTY response", flush=True)
        time.sleep(PACING_S)
    merged.update(compute_avg(merged))
    write_csv(merged, CSV_PATH)
    write_json(merged, fetched_utc, JSON_PATH)
    print(f"[{mode}] merged rows: {len(merged)} (was {pre_rows})", flush=True)
    print(f"[{mode}] wrote {CSV_PATH} ({os.path.getsize(CSV_PATH)} bytes)", flush=True)
    print(f"[{mode}] wrote {JSON_PATH} ({os.path.getsize(JSON_PATH)} bytes)", flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--backfill", action="store_true",
                   help="fetch FULL history for all series (no last param) and merge")
    g.add_argument("--refresh", action="store_true",
                   help="fetch last ~20 obs days per series and merge latest-wins")
    args = ap.parse_args()
    run("backfill" if args.backfill else "refresh")


if __name__ == "__main__":
    main()
