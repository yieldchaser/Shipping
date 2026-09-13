#!/usr/bin/env python3
"""
scripts/build_views.py — Tier 1 View Manifests Generator

Pre-aggregates and compresses frontend view payloads into small, deterministic
JSON files under data/views/ (<= 250 KB per file) with embedded provenance headers.

Also handles:
- Normalization of all date columns repo-wide to ISO YYYY-MM-DD on read (reporting repaired count)
- Sorting USDA FAS export sales ascending by date on read
- Pre-aggregation of port_calls_daily_expanded.csv into a compact summary view (replacing 53.65 MB boot load)
"""

import os
import sys
import json
import csv
import re
import glob
from datetime import datetime, timezone
import pandas as pd

# Hard ceiling per view manifest (Rule: Target <= 250 KB)
MAX_MANIFEST_BYTES = 250 * 1024

def parse_number(val):
    """Parses a numeric cell that may carry thousands separators or stray symbols.

    Baltic index CSVs quote values above a thousand as "2,325" while values below
    it are bare. float() raises on the former, so a plain float()/continue loop
    silently keeps only the years the index happened to trade below 1,000 - which
    is exactly what happened to cape/panama/suprama: 62% of their history was
    dropped, the surviving sample was biased low, and every percentile computed
    from it read far too high. Returns None when the cell genuinely is not a number.
    """
    if val is None:
        return None
    if isinstance(val, (int, float)):
        try:
            if val != val:  # NaN
                return None
        except TypeError:
            return None
        return float(val)
    txt = str(val).strip().replace(",", "").replace("%", "").replace("$", "")
    if not txt or txt in ("-", "--", "n/a", "N/A", "nan", "NaN", "None"):
        return None
    try:
        return float(txt)
    except ValueError:
        return None


def normalize_date_str(val):
    """Normalize dates to ISO YYYY-MM-DD. Returns (normalized_str, was_repaired_bool)."""
    if val is None or pd.isna(val):
        return None, False
    s = str(val).strip()
    if len(s) >= 10 and s[4] == '-' and s[7] == '-':
        return s[:10], False
    if len(s) == 10 and s[2] == '-' and s[5] == '-':
        parts = s.split('-')
        return f"{parts[2]}-{parts[1]}-{parts[0]}", True
    if '/' in s:
        parts = s.split('/')
        if len(parts) == 3 and len(parts[2]) == 4:
            return f"{parts[2]}-{int(parts[0]):02d}-{int(parts[1]):02d}", True
    return s[:10], False

def load_provenance_map():
    manifest_path = 'data/provenance/manifest.json'
    if not os.path.exists(manifest_path):
        return {}
    with open(manifest_path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)
    return {item['output_file']: item for item in manifest.get('series', [])}

def get_prov_header(prov_map, file_path, default_id="", fallback_source=""):
    rel = file_path.replace('\\', '/')
    item = prov_map.get(rel, {})
    return {
        "series_id": item.get('series_id', default_id),
        "source": item.get('source_name', fallback_source or "Market Feeds"),
        "as_of": item.get('last_fetched_utc', datetime.now(timezone.utc).isoformat()),
        "row_count": item.get('row_count', 0),
        "status": item.get('status', "LIVE")
    }

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")


def _today_iso():
    import datetime as _dt
    return _dt.date.today().isoformat()


def _max_observed_date(obj):
    """Newest date in the payload that is not in the future.

    Forward curves carry contract expiry dates years ahead; those describe the
    instrument, not how current the data is. as_of means 'data through'.
    """
    today = _today_iso()
    best = _max_date_in(obj)
    if best and best <= today:
        return best
    # Walk again keeping only non-future dates.
    return _max_date_in_capped(obj, today)


def _max_date_in_capped(obj, today, best=""):
    if isinstance(obj, str):
        if _ISO_DATE_RE.match(obj) and obj[:10] <= today:
            return max(best, obj[:10])
        return best
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str) and _ISO_DATE_RE.match(k) and k[:10] <= today:
                best = max(best, k[:10])
            best = _max_date_in_capped(v, today, best)
        return best
    if isinstance(obj, (list, tuple)):
        for v in obj:
            best = _max_date_in_capped(v, today, best)
    return best


def _max_date_in(obj, best=""):
    """Deepest ISO date present anywhere in the payload.

    Used to stamp a view's as_of from its OWN data. Never uses the clock: a view
    built today from data that ends last week is as_of last week, and must say so.
    """
    if isinstance(obj, str):
        if _ISO_DATE_RE.match(obj):
            return max(best, obj[:10])
        return best
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str) and _ISO_DATE_RE.match(k):
                best = max(best, k[:10])
            best = _max_date_in(v, best)
        return best
    if isinstance(obj, (list, tuple)):
        for v in obj:
            best = _max_date_in(v, best)
        return best
    return best


def write_view_manifest(target_file, payload, report_name):
    """Write deterministic JSON and verify <= 250 KB limit."""
    os.makedirs(os.path.dirname(target_file), exist_ok=True)
    # Stamp as_of from the payload's own newest date so freshness is checkable.
    if isinstance(payload, dict):
        as_of = _max_observed_date(payload)
        hdr = payload.get("header")
        target = hdr if isinstance(hdr, dict) else payload
        if as_of:
            target["as_of"] = as_of
            target.pop("freshness", None)
        else:
            # No date anywhere in the payload: this is a static lookup table
            # (vessel/port registries). Say so explicitly rather than stamping a
            # date the data does not support.
            target["as_of"] = None
            target["freshness"] = "static-lookup"
    raw_str = json.dumps(payload, sort_keys=True, separators=(',', ':'))
    raw_bytes = raw_str.encode('utf-8')
    size_bytes = len(raw_bytes)
    
    with open(target_file, 'wb') as f:
        f.write(raw_bytes)
    
    size_kb = size_bytes / 1024.0
    print(f"  [VIEW] {report_name:<35} -> {target_file:<42} ({size_kb:6.1f} KB)")
    if size_bytes > MAX_MANIFEST_BYTES:
        raise ValueError(
            f"ERROR: View manifest {target_file} exceeds 250 KB limit! "
            f"Actual size: {size_kb:.1f} KB ({size_bytes} bytes)."
        )
    return size_bytes

def report_repaired_dates(prov_map):
    """Normalize date columns across all SGX futures files on read and report repaired counts."""
    sgx_files = sorted(glob.glob('data/futures/sgx_*_futures_history.csv'))
    print("\n--- Date Normalization Audit (SGX Futures) ---")
    total_repaired = 0
    results = {}
    for fpath in sgx_files:
        df = pd.read_csv(fpath)
        dcol = 'date' if 'date' in df.columns else df.columns[0]
        rep_count = 0
        for d in df[dcol]:
            _, was_rep = normalize_date_str(d)
            if was_rep:
                rep_count += 1
        rel_path = fpath.replace('\\', '/')
        results[rel_path] = rep_count
        total_repaired += rep_count
        print(f"  {rel_path:<48}: {rep_count:>6} rows repaired (of {len(df)} rows)")
    print(f"  Total rows repaired across SGX history: {total_repaired}")
    return results

def sort_usda_sales_on_read():
    """Verify sorting USDA FAS export sales ascending by date on read."""
    usda_path = 'data/commodities/usda_fas_outstanding_export_sales.csv'
    if not os.path.exists(usda_path):
        return
    print("\n--- USDA FAS Outstanding Export Sales Sort Audit ---")
    df = pd.read_csv(usda_path, low_memory=False)
    dcol = 'date' if 'date' in df.columns else df.columns[0]
    df['norm_date'] = df[dcol].apply(lambda x: normalize_date_str(x)[0])
    df_sorted = df.sort_values('norm_date', ascending=True)
    first_date = df_sorted['norm_date'].iloc[0]
    last_date = df_sorted['norm_date'].iloc[-1]
    print(f"  Sorted {len(df_sorted)} rows on read: {first_date} -> {last_date}")

def build_indices_and_dashboard_master(prov_map):
    """Build dashboard_master.json (5Y aligned primary index window) and per-series indices views."""
    print("\n--- Building Tier 1: Dashboard Master & Indices Views ---")
    index_files = {
        'bdiy': 'data/indices/bdiy_historical.csv',
        'cape': 'data/indices/cape_historical.csv',
        'panama': 'data/indices/panama_historical.csv',
        'suprama': 'data/indices/suprama_historical.csv',
        'handysize': 'data/indices/handysize_historical.csv',
        'dirtytanker': 'data/indices/dirtytanker_historical.csv',
        'cleantanker': 'data/indices/cleantanker_historical.csv',
        'bdryff': 'data/futures/bdryff_history.csv',
        'bwetff': 'data/futures/bwetff_history.csv',
        'clmi': 'data/indices/capital_link_maritime_clmi.csv',
        'cldbi': 'data/indices/capital_link_drybulk_cldbi.csv',
        'clti': 'data/indices/capital_link_tanker_clti.csv',
        'clci': 'data/indices/capital_link_container_clci.csv',
        'cllg': 'data/indices/capital_link_lng_lpg_cllg.csv',
        'clmfi': 'data/indices/capital_link_mixed_fleet_clmfi.csv',
        'clmlp': 'data/indices/capital_link_mlp_clmlp.csv'
    }

    dates_dict = {}
    per_series_dates = {k: [] for k in index_files}
    per_series_values = {k: [] for k in index_files}

    for key, fpath in index_files.items():
        if not os.path.exists(fpath):
            continue
        df = pd.read_csv(fpath)
        dcol = 'date' if 'date' in df.columns else df.columns[0]
        vcol = 'value' if 'value' in df.columns else ('close' if 'close' in df.columns else df.columns[1])
        
        series_points = []
        for _, row in df.iterrows():
            d_norm, _ = normalize_date_str(row[dcol])
            if not d_norm or len(d_norm) != 10:
                continue
            parsed = parse_number(row[vcol])
            if parsed is None:
                continue
            v = round(parsed, 2)
            series_points.append((d_norm, v))
        
        series_points.sort(key=lambda x: x[0])
        for d, v in series_points:
            if d not in dates_dict:
                dates_dict[d] = {}
            dates_dict[d][key] = v
            per_series_dates[key].append(d)
            per_series_values[key].append(v)
        
        # Build individual per-series view manifest
        header = get_prov_header(prov_map, fpath, default_id=f"index_{key}", fallback_source="Baltic Exchange")
        header["row_count"] = len(series_points)
        if series_points:
            header["as_of"] = series_points[-1][0]
        per_series_payload = {
            "header": header,
            "dates": per_series_dates[key],
            "values": per_series_values[key]
        }
        write_view_manifest(f"data/views/indices/{key}.json", per_series_payload, f"Index {key}")

    all_sorted_dates = sorted(dates_dict.keys())
    
    # Dashboard master: 5-year primary window (from 2021-01-01 to latest)
    dates_5y = [d for d in all_sorted_dates if d >= '2021-01-01']
    master_header = {
        "series_id": "dashboard_master",
        "source": "Baltic Exchange / Solactive / Capital Link",
        "as_of": all_sorted_dates[-1] if all_sorted_dates else "",
        "row_count": len(dates_5y),
        "status": "LIVE"
    }
    
    # Build compact aligned table: dates list + dict of series arrays
    master_payload = {
        "header": master_header,
        "dates": dates_5y,
        "series": {k: [dates_dict[d].get(k, None) for d in dates_5y] for k in index_files}
    }
    write_view_manifest("data/views/dashboard_master.json", master_payload, "Dashboard Master (5Y)")

# ---------------------------------------------------------------------------
# Route cards for the Indices tab (Dry Routes / Tanker Routes)
# ---------------------------------------------------------------------------
# Every series below was checked against its source on 2026-09-13:
#   * Fearnpulse TS endpoint (dry routes): the local copy holds the full
#     series the endpoint returns with no `last` limit, row for row.
#   * Fearnleys Hasura catalog (tanker routes): local fearnpulse_rates_full.csv
#     matches the API's count and first date for all 356 non-empty series. The
#     per-route tanker assessments start 2018-05-18 at the source.
# Baltic codes are attached to a tanker series only where its values track the
# Gibson series published under that code (median relative gap, shared days):
#   TD3C  VLCC MEG/FEAST      1.7%  (965)
#   TD20  Suezmax WAFR/UKC    2.2%  (837)
#   TD25  Aframax USG/UKCM    1.3%  (960)
# A print of 0 means the route was not assessed that day (Fearnleys quotes
# Primorsk/UKC as 0 from 2022-12-16 on, after the Russian crude embargo), so
# non-positive values are dropped rather than plotted as a rate. Primorsk/UKC
# itself is left out: it has not had a real print since 2022-12-15.
# Fearnleys tsIds 1-9 are NOT used: they stopped on 2023-05-22, and the codes the
# repo attached to them fail that check (tsId 4 "TD20" sits 37% away from TD20,
# tsId 1 "TD3C" 46% away from MEG/FEAST).
# Dry routes come from the daily-refreshed Fearnpulse bundle (data_expansion.yml runs
# fetch_dry_routes_ts.py --refresh), matched on tsId.
ROUTE_DRY_JSON = "data/derived/fearnleys_dry_routes_daily.json"
ROUTE_TANKER_JSON = "data/derived/fearnleys_tanker_routes_daily.json"
FEARNPULSE_SRC = "Fearnleys route assessments"
FEARNLEYS_TANK_SRC = "Fearnleys daily tanker assessments"
GIBSON_SRC = "E.A. Gibson daily tanker rates"

ROUTE_CARDS = [
    # group, card id, Baltic code, title, vessel class, unit, precision, source kind, source key
    ("dry", "C3", "C3", "Tubarao to Qingdao", "Capesize", "usd/tonne", 2, "dry", 10001),
    ("dry", "C5", "C5", "West Australia to Qingdao", "Capesize", "usd/tonne", 2, "dry", 10002),
    ("dry", "C9_182", "C9_182", "Continent/Mediterranean trip China-Japan", "Capesize", "usd/day", 0, "dry", 120655),
    ("dry", "C10_182", "C10_182", "China-Japan transpacific round voyage", "Capesize", "usd/day", 0, "dry", 120654),
    ("dry", "P1A_82", "P1A_82", "Skaw-Gib transatlantic round voyage", "Panamax", "usd/day", 0, "dry", 10010),
    ("dry", "P2A_82", "P2A_82", "Skaw-Gib trip HK-S Korea incl Taiwan", "Panamax", "usd/day", 0, "dry", 10011),
    ("dry", "P3A_82", "P3A_82", "Hong Kong-South Korea transpacific round voyage", "Panamax", "usd/day", 0, "dry", 10012),
    ("dry", "P4_82", "P4_82", "Hong Kong-South Korea trip to Skaw-Passero", "Panamax", "usd/day", 0, "dry", 10013),
    ("dry", "S1C", "S1C", "US Gulf trip to China-south Japan", "Supramax", "usd/day", 0, "dry", 120129),
    ("dry", "S4A", "S4A", "US Gulf trip to Skaw-Passero", "Supramax", "usd/day", 0, "dry", 120132),
    ("dry", "S4B", "S4B", "Skaw-Passero trip to US Gulf", "Supramax", "usd/day", 0, "dry", 120133),
    ("dry", "S10", "S10", "South China trip via Indonesia to south China", "Supramax", "usd/day", 0, "dry", 120137),
    ("tanker", "TD3C", "TD3C", "Middle East Gulf to China", "VLCC", "worldscale", 1, "fearn", "TANK_VLCC_MEG_FEAST"),
    ("tanker", "VLCC_WAFR_FEAST", None, "West Africa to Far East", "VLCC", "worldscale", 1, "fearn", "TANK_VLCC_WAFR_FEAST"),
    ("tanker", "VLCC_MEG_USG", None, "Middle East Gulf to US Gulf", "VLCC", "worldscale", 1, "fearn", "TANK_VLCC_MEG_USG"),
    ("tanker", "TD20", "TD20", "West Africa to UK-Continent", "Suezmax", "worldscale", 1, "fearn", "TANK_SUEZMAX_WAFR_UKC"),
    ("tanker", "SUEZ_BLSEA_MED", None, "Black Sea to Mediterranean", "Suezmax", "worldscale", 1, "fearn", "TANK_SUEZMAX_BLSEA_MED"),
    ("tanker", "TD25", "TD25", "US Gulf to A-R-A", "Aframax", "worldscale", 1, "fearn", "TANK_AFRAMAX_USG_UKCM"),
    ("tanker", "AFRA_CEYHAN_MED", None, "Ceyhan to Mediterranean", "Aframax", "worldscale", 1, "fearn", "TANK_AFRAMAX_CEYHAN_MED"),
    ("tanker", "AFRA_CBS_USG", None, "Caribbean to US Gulf", "Aframax", "worldscale", 1, "fearn", "TANK_AFRAMAX_CBS_USG"),
    ("tanker", "TC1", "TC1", "Middle East Gulf to Japan (CPP, UNL, naphtha condensate)", "LR2 clean (75kt)", "worldscale", 1, "gibson", "GIBSON_TC1"),
    ("tanker", "TC5", "TC5", "Middle East Gulf to Japan (CPP, UNL, naphtha condensate)", "LR1 clean (55kt)", "worldscale", 1, "gibson", "GIBSON_TC5"),
]

ROUTE_NOTES = {
    "TD3C": ("Fearnleys' VLCC MEG/Far East assessment. Tracks the Gibson TD3C print within 1.7% "
             "(median, 965 shared days). The Baltic redefined TD3C from MEG-Japan to MEG-China in 2019-20."),
    "TD20": "Fearnleys' Suezmax WAFR/UKC assessment. Tracks the Gibson TD20 print within 2.2% (median, 837 shared days).",
    "TD25": "Fearnleys' Aframax USG/UKC-Med assessment (Gibson quotes TD25 as USG/UKC 70kt). Tracks the Gibson TD25 print within 1.3% (median, 960 shared days).",
}


def _route_points_dry(dry_series, tsid):
    s = next((v for v in dry_series.values() if v.get("tsid") == tsid), None)
    if not s:
        raise ValueError(f"route tsId {tsid} missing from {ROUTE_DRY_JSON}")
    return _route_pts_to_dates(s["pts"])


def _route_pts_to_dates(pts):
    out = []
    for ms, v in pts:
        if v is None or v <= 0:
            continue
        out.append((datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d"), float(v)))
    return out


def _route_points_tanker(series_all, key):
    s = series_all.get(key)
    if not s:
        raise ValueError(f"route series {key} missing from {ROUTE_TANKER_JSON}")
    if s.get("derived"):
        raise ValueError(f"route series {key} is derived; route cards show source assessments only")
    return _route_pts_to_dates(s["pts"])


def build_route_views():
    """Per-route views for the Indices tab plus a small catalog the page reads first."""
    print("\n--- Building Tier 1: Indices Route Cards ---")
    with open(ROUTE_DRY_JSON, "r", encoding="utf-8") as f:
        dry_series = json.load(f).get("series", {})
    tanker_series = {}
    if os.path.exists(ROUTE_TANKER_JSON):
        with open(ROUTE_TANKER_JSON, "r", encoding="utf-8") as f:
            tanker_series = json.load(f).get("series", {})

    catalog = []
    for group, cid, code, title, vclass, unit, precision, kind, key in ROUTE_CARDS:
        if kind == "dry":
            pts = _route_points_dry(dry_series, key)
            source = FEARNPULSE_SRC
        else:
            pts = _route_points_tanker(tanker_series, key)
            source = FEARNLEYS_TANK_SRC if kind == "fearn" else GIBSON_SRC
        # dedupe keep-last, chronological
        dedup = {}
        for d, v in pts:
            dedup[d] = round(v, 2)
        dates = sorted(dedup)
        if not dates:
            raise ValueError(f"route card {cid} has no points")
        header = {
            "series_id": f"route_{cid}",
            "card_id": cid,
            "code": code,
            "title": title,
            "vessel_class": vclass,
            "group": group,
            "unit": unit,
            "precision": precision,
            "source": source,
            "source_key": key,
            "note": ROUTE_NOTES.get(cid),
            "first": dates[0],
            "last": dates[-1],
            "row_count": len(dates),
            "status": "LIVE",
        }
        write_view_manifest(f"data/views/routes/{cid}.json",
                            {"header": header, "dates": dates, "values": [dedup[d] for d in dates]},
                            f"Route {cid}")
        catalog.append({k: header[k] for k in ("card_id", "code", "title", "vessel_class", "group",
                                               "unit", "precision", "source", "note", "first",
                                               "last", "row_count")})
    write_view_manifest("data/views/routes/catalog.json",
                        {"header": {"series_id": "route_catalog", "source": "Fearnleys / E.A. Gibson",
                                    "row_count": len(catalog), "status": "LIVE"},
                         "routes": catalog},
                        "Route catalog")


def build_port_calls_summary(prov_map):
    """Pre-aggregate port_calls_daily_expanded.csv (53.65 MB) into a compact <= 250 KB summary view."""
    print("\n--- Building Tier 1: Port Calls Summary View ---")
    fpath = 'data/congestion/port_calls_daily_expanded.csv'
    if not os.path.exists(fpath):
        print(f"  Warning: {fpath} not found.")
        return

    df = pd.read_csv(fpath, usecols=[
        'date', 'portid', 'portname', 'country', 'portcalls',
        'portcalls_tanker', 'portcalls_dry_bulk', 'portcalls_container',
        'portcalls_general_cargo', 'portcalls_roro'
    ])

    by_port = {}
    by_date = {}
    ytd_calls = {}

    for _, row in df.iterrows():
        pid = str(row['portid']).strip()
        d_norm, _ = normalize_date_str(row['date'])
        if not d_norm or not pid:
            continue
        
        def safe_int(val):
            if pd.isna(val) or val is None or str(val).strip() == '':
                return 0
            try:
                return int(float(val))
            except:
                return 0

        calls = safe_int(row['portcalls'])
        t_calls = safe_int(row['portcalls_tanker'])
        db_calls = safe_int(row['portcalls_dry_bulk'])
        c_calls = safe_int(row['portcalls_container'])
        gc_calls = safe_int(row['portcalls_general_cargo'])
        ro_calls = safe_int(row['portcalls_roro'])

        if pid not in by_port:
            by_port[pid] = {
                'name': str(row['portname']).strip(),
                'country': str(row['country']).strip(),
                'tanker': 0, 'dry_bulk': 0, 'container': 0, 'general_cargo': 0, 'roro': 0
            }
        by_port[pid]['tanker'] += t_calls
        by_port[pid]['dry_bulk'] += db_calls
        by_port[pid]['container'] += c_calls
        by_port[pid]['general_cargo'] += gc_calls
        by_port[pid]['roro'] += ro_calls

        ytd_calls[pid] = ytd_calls.get(pid, 0) + calls
        by_date[d_norm] = by_date.get(d_norm, 0) + calls

    dates_sorted = sorted(by_date.keys())
    latest_date = dates_sorted[-1] if dates_sorted else None
    last7_dates = dates_sorted[-7:] if dates_sorted else []
    avg7 = round(sum(by_date[d] for d in last7_dates) / len(last7_dates), 2) if last7_dates else 0

    # Sector totals
    sector_totals = {
        "all": {"total": 0, "nPorts": 0},
        "Tankers": {"total": 0, "nPorts": 0},
        "Dry Bulk": {"total": 0, "nPorts": 0},
        "Container": {"total": 0, "nPorts": 0},
        "General Cargo": {"total": 0, "nPorts": 0},
        "RoRo": {"total": 0, "nPorts": 0}
    }
    
    # Store ports in compact list: [pid, name, country, tanker, dry_bulk, container, general_cargo, roro, ytd]
    ports_compact = []
    for pid, p in by_port.items():
        ytd = ytd_calls.get(pid, 0)
        tot = p['tanker'] + p['dry_bulk'] + p['container'] + p['general_cargo'] + p['roro']
        sector_totals["all"]["total"] += tot
        if tot > 0:
            sector_totals["all"]["nPorts"] += 1
        if p['tanker'] > 0:
            sector_totals["Tankers"]["total"] += p['tanker']
            sector_totals["Tankers"]["nPorts"] += 1
        if p['dry_bulk'] > 0:
            sector_totals["Dry Bulk"]["total"] += p['dry_bulk']
            sector_totals["Dry Bulk"]["nPorts"] += 1
        if p['container'] > 0:
            sector_totals["Container"]["total"] += p['container']
            sector_totals["Container"]["nPorts"] += 1
        if p['general_cargo'] > 0:
            sector_totals["General Cargo"]["total"] += p['general_cargo']
            sector_totals["General Cargo"]["nPorts"] += 1
        if p['roro'] > 0:
            sector_totals["RoRo"]["total"] += p['roro']
            sector_totals["RoRo"]["nPorts"] += 1
        
        # Include port if it has at least 1 call or is named
        ports_compact.append([
            pid, p['name'], p['country'],
            p['tanker'], p['dry_bulk'], p['container'], p['general_cargo'], p['roro'],
            ytd
        ])

    header = get_prov_header(prov_map, fpath, default_id="port_calls_expanded_summary", fallback_source="IMF PortWatch")
    header["row_count"] = len(df)
    header["as_of"] = latest_date or header["as_of"]

    summary_payload = {
        "header": header,
        "kpis": {
            "latestDate": latest_date,
            "latestCalls": by_date.get(latest_date, 0) if latest_date else 0,
            "avg7": avg7,
            "datesCount": len(dates_sorted),
            "totalCalls": sum(by_date.values())
        },
        "sector_totals": sector_totals,
        "by_date": by_date,
        "ports": ports_compact
    }

    write_view_manifest("data/views/port_calls_summary.json", summary_payload, "Port Calls Summary (replacing 53.65 MB)")

def build_etf_summary(prov_map):
    """Build compact etf_summary.json with holdings and liquidity summary."""
    print("\n--- Building Tier 1: ETF Summary View ---")
    bdry_holdings = []
    bwet_holdings = []
    if os.path.exists('data/etf/bdry_holdings.csv'):
        df = pd.read_csv('data/etf/bdry_holdings.csv')
        bdry_holdings = df.to_dict(orient='records')
    if os.path.exists('data/etf/bwet_holdings.csv'):
        df = pd.read_csv('data/etf/bwet_holdings.csv')
        bwet_holdings = df.to_dict(orient='records')
    
    quotes = {}
    if os.path.exists('data/etf/live_quotes.json'):
        with open('data/etf/live_quotes.json', 'r', encoding='utf-8') as f:
            quotes = json.load(f)

    header = get_prov_header(prov_map, 'data/etf/bdry_holdings.csv', default_id="etf_summary", fallback_source="Breakwave Advisors")
    payload = {
        "header": header,
        "bdry_holdings": bdry_holdings,
        "bwet_holdings": bwet_holdings,
        "quotes": quotes
    }
    write_view_manifest("data/views/etf_summary.json", payload, "ETF Summary View")



def build_signal_base_rates(out_path="data/views/signal_base_rates.json"):
    """Forward-return base rates for the dashboard signal ladder.

    The banner used to carry these as typed strings ("-1.1% avg fwd 3M vs +7.5%
    unconditional"). They were correct when written, but nothing recomputed them,
    so they would drift as history grew. This derives them from the BDI series
    itself on every build. Nothing here is assumed: if the file is missing or too
    short, we emit no numbers and the UI shows its empty state.
    """
    import statistics as _stats
    src = "data/indices/bdiy_historical.csv"
    if not os.path.exists(src):
        print("  [SIGNAL] %s absent - base rates not built" % src)
        return None
    rows = []
    with open(src, "r", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            v = r.get("Index")
            d = r.get("Date")
            if d and v not in (None, "", "NaN"):
                try:
                    rows.append((d, float(v)))
                except ValueError:
                    continue
    rows.sort()
    vals = [v for _, v in rows]
    FWD, W5 = 63, 1260          # ~3 months of sessions; 5Y percentile window
    if len(vals) < W5 + FWD + 1:
        print("  [SIGNAL] only %d rows - too short for a 5Y base rate" % len(vals))
        return None

    buckets = {
        "overheated": [],
        "stretched": [],
        "elevated": [],
        "mid_range": [],
        "accumulate": [],
        "soft": [],
        "depressed": [],
        "deep_distress": [],
        "unconditional": [],
    }
    for i in range(W5, len(vals) - FWD):
        window = vals[i - W5:i + 1]
        pctl = sum(1 for x in window if x <= vals[i]) / len(window)
        fwd = (vals[i + FWD] - vals[i]) / vals[i] * 100.0
        buckets["unconditional"].append(fwd)
        # Five disjoint bands, one per label the banner can show, so the statistic
        # quoted under a label is drawn from exactly the sessions that label
        # describes. 'soft' must NOT swallow the sub-0.2 sessions: the banner
        # already shows those as Depressed, and pooling them made the Soft base
        # rate look better than the zone it names.
        if pctl > 0.8:
            buckets["stretched"].append(fwd)
            buckets["overheated"].append(fwd)      # legacy key, same band
        elif pctl >= 0.6:
            buckets["elevated"].append(fwd)
        elif pctl >= 0.4:
            buckets["mid_range"].append(fwd)
        elif pctl >= 0.2:
            buckets["soft"].append(fwd)
            buckets["accumulate"].append(fwd)      # legacy key, same band
        else:
            buckets["depressed"].append(fwd)
            buckets["deep_distress"].append(fwd)   # legacy key, same band

    def summarise(series):
        if len(series) < 30:
            return None
        return {
            "n": len(series),
            "mean_pct": round(_stats.mean(series), 2),
            "median_pct": round(_stats.median(series), 2),
            "win_rate_pct": round(sum(1 for x in series if x > 0) / len(series) * 100, 1),
        }

    payload = {
        "header": {
            "source": src,
            "as_of": rows[-1][0],
            "method": ("Forward %d-session (~3 month) return of the BDI, bucketed by the "
                       "index's own percentile within a trailing %d-session (~5 year) window. "
                       "Base rates, not forecasts." % (FWD, W5)),
            "series_start": rows[0][0],
            "series_end": rows[-1][0],
            "first_measurable": rows[W5][0],
        },
        "buckets": {k: summarise(v) for k, v in buckets.items()},
    }
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, sort_keys=True, separators=(",", ":"))
    oh = payload["buckets"]["overheated"]
    un = payload["buckets"]["unconditional"]
    print("  [SIGNAL] base rates -> %s (overheated n=%s mean=%s%% vs uncond mean=%s%%)"
          % (out_path, oh and oh["n"], oh and oh["mean_pct"], un and un["mean_pct"]))
    return payload


def stamp_all_views(views_root="data/views"):
    """Stamp as_of on every view under data/views/, whoever wrote it.

    write_view_manifest stamps the views this script builds, but several views
    (data/views/signal/*, data/views/signals/*) are written by other scripts.
    This pass runs last so no view can ship without declaring its own freshness.
    The date always comes from the file's own content - never from the clock.
    """
    stamped = 0
    for path in sorted(glob.glob(os.path.join(views_root, "**", "*.json"), recursive=True)):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        hdr = data.get("header")
        target = hdr if isinstance(hdr, dict) else data
        as_of = _max_observed_date(data)
        if as_of:
            if target.get("as_of") == as_of and "freshness" not in target:
                continue
            target["as_of"] = as_of
            target.pop("freshness", None)
        else:
            if target.get("as_of") is None and target.get("freshness") == "static-lookup":
                continue
            target["as_of"] = None
            target["freshness"] = "static-lookup"
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, sort_keys=True, separators=(",", ":"))
        stamped += 1
    print(f"  [STAMP] as_of written on {stamped} view(s)")
    return stamped


def main():
    print("=================================================================")
    print("scripts/build_views.py — Building Tier 1 View Manifests")
    print("=================================================================")
    prov_map = load_provenance_map()
    
    # 1. Report date normalization for SGX
    report_repaired_dates(prov_map)
    
    # 2. Sort USDA FAS sales on read
    sort_usda_sales_on_read()
    
    # 3. Build dashboard master and indices
    build_indices_and_dashboard_master(prov_map)
    build_route_views()

    # 4. Build port calls summary
    build_port_calls_summary(prov_map)

    # 5. Build ETF summary
    build_etf_summary(prov_map)
    
    print("\nAll view manifests successfully built and validated under 250 KB target.")
    build_signal_base_rates()
    stamp_all_views()

if __name__ == '__main__':
    main()
