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
import re
import glob
from datetime import datetime, timezone
import pandas as pd

# Hard ceiling per view manifest (Rule: Target <= 250 KB)
MAX_MANIFEST_BYTES = 250 * 1024

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
            try:
                v = round(float(row[vcol]), 2)
            except (ValueError, TypeError):
                continue
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
    
    # 4. Build port calls summary
    build_port_calls_summary(prov_map)

    # 5. Build ETF summary
    build_etf_summary(prov_map)
    
    print("\nAll view manifests successfully built and validated under 250 KB target.")
    stamp_all_views()

if __name__ == '__main__':
    main()
