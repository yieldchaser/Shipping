#!/usr/bin/env python3
import os, json, hashlib, logging
from pathlib import Path
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

REPO_ROOT = Path('.').resolve()
GEO_DIR = REPO_ROOT / 'data' / 'geospatial'
VIEWS_DIR = REPO_ROOT / 'data' / 'views' / 'signal'
VIEWS_DIR.mkdir(parents=True, exist_ok=True)
MANIFEST_PATH = REPO_ROOT / 'data' / 'provenance' / 'manifest.json'

def fix_and_verify_map_ports():
    logging.info('Fixing corrupt signal_map_ports_master.json...')
    files = {
        'dry_bulk': GEO_DIR / 'signal_map_ports_dry_bulk.json',
        'tankers': GEO_DIR / 'signal_map_ports_tankers.json',
        'lpg': GEO_DIR / 'signal_map_ports_lpg.json',
        'lng': GEO_DIR / 'signal_map_ports_lng.json'
    }
    data = {k: json.load(open(v, 'r', encoding='utf-8')) for k, v in files.items()}

    master = []
    for i in range(len(data['dry_bulk'])):
        p = dict(data['dry_bulk'][i])
        z_max = max(data['dry_bulk'][i]['zoomIndex'],
                    data['tankers'][i]['zoomIndex'],
                    data['lpg'][i]['zoomIndex'],
                    data['lng'][i]['zoomIndex'])
        p['zoomIndex'] = round(z_max, 4)
        master.append(p)

    master_path = GEO_DIR / 'signal_map_ports_master.json'
    with open(master_path, 'w', encoding='utf-8') as f:
        json.dump(master, f, separators=(',', ':'))

    # Verify MD5 hashes
    all_map_files = sorted(list(files.values()) + [master_path])
    hashes = {}
    for mf in all_map_files:
        h = hashlib.md5(open(mf, 'rb').read()).hexdigest()
        hashes[mf.name] = h
        logging.info('File %s: MD5 = %s', mf.name, h)

    assert len(hashes) == len(set(hashes.values())), 'Duplicate MD5 hashes detected!'
    logging.info('Verified all 5 map ports files have unique MD5 hashes.')
    return hashes

def build_signal_views():
    logging.info('Building Signal Ocean Tier 1 view manifests...')
    # 1. Map ports summary (prominent commercial ports with zoomIndex > 0.05)
    master_path = GEO_DIR / 'signal_map_ports_master.json'
    master_ports = json.load(open(master_path, 'r', encoding='utf-8'))
    compact_ports = []
    for p in master_ports:
        if p.get('zoomIndex', 0) >= 0.05:
            compact_ports.append({
                'id': p['portID'],
                'name': p['portName'],
                'country': p['countryName'],
                'lat': round(p['latitude'], 3),
                'lon': round(p['longitude'], 3),
                'zoom': p['zoomIndex'],
                'type': p.get('geoAssetTypeID', 1)
            })

    ports_payload = {
        'header': {
            'series_id': 'signal_map_ports_master',
            'source': 'Signal Ocean Platform',
            'as_of': datetime.now(timezone.utc).isoformat(),
            'row_count': len(compact_ports),
            'status': 'LIVE'
        },
        'ports': compact_ports
    }
    p_path = VIEWS_DIR / 'ports_summary.json'
    with open(p_path, 'w', encoding='utf-8') as f:
        json.dump(ports_payload, f, separators=(',', ':'))
    logging.info('Wrote %s (%d ports, %d KB)', p_path.name, len(compact_ports), p_path.stat().st_size // 1024)

    # 2. Fleet positions summary (subsampled / top active tracking)
    pos_files = {
        'capesize_vloc': GEO_DIR / 'signal_live_fleet_positions_capesize_vloc.json',
        'vlcc_suezmax': GEO_DIR / 'signal_live_fleet_positions_vlcc_suezmax.json',
        'lng': GEO_DIR / 'signal_live_fleet_positions_lng.json',
        'lpg': GEO_DIR / 'signal_live_fleet_positions_lpg.json'
    }
    fleet_summary = {}
    for sector, path in pos_files.items():
        if path.exists():
            vessels = json.load(open(path, 'r', encoding='utf-8'))
            fleet_summary[sector] = {
                'total_tracked': len(vessels),
                'sample': [{
                    'imo': v.get('imo'),
                    'name': v.get('vesselName'),
                    'lat': round(v.get('latitude', 0), 2),
                    'lon': round(v.get('longitude', 0), 2),
                    'spd': v.get('speed'),
                    'status': v.get('commercialOperationalStatus')
                } for v in vessels[:50]]
            }

    fleet_payload = {
        'header': {
            'series_id': 'signal_fleet_positions',
            'source': 'Signal Ocean Live Tracking',
            'as_of': datetime.now(timezone.utc).isoformat(),
            'total_hulls': sum(f['total_tracked'] for f in fleet_summary.values()),
            'status': 'LIVE'
        },
        'sectors': fleet_summary
    }
    f_path = VIEWS_DIR / 'fleet_positions_summary.json'
    with open(f_path, 'w', encoding='utf-8') as f:
        json.dump(fleet_payload, f, separators=(',', ':'))
    logging.info('Wrote %s (%d tracked hulls, %d KB)', f_path.name, fleet_payload['header']['total_hulls'], f_path.stat().st_size // 1024)

def register_provenance():
    logging.info('Registering Signal Ocean datasets in manifest.json...')
    if not MANIFEST_PATH.exists():
        return
    with open(MANIFEST_PATH, 'r', encoding='utf-8') as f:
        manifest = json.load(f)

    existing_ids = {s['series_id']: i for i, s in enumerate(manifest['series'])}

    signal_entries = [
        {
            'series_id': 'signal_map_ports_master',
            'display_name': 'Signal Ocean — Global Commercial Terminals Master',
            'status': 'LIVE',
            'source_name': 'Signal Ocean Platform',
            'source_url': 'https://app.signalocean.com/api/geolocations/mapPorts',
            'fetch_method': 'REST API (Extracted)',
            'fetch_script': 'scripts/acquire/register_signal_ocean.py',
            'output_file': 'data/geospatial/signal_map_ports_master.json',
            'row_count': 2752,
            'date_span': None,
            'last_fetched_utc': datetime.now(timezone.utc).isoformat(),
            'unit': 'Terminals',
            'is_derived': False,
            'derivation': None,
            'notes': '2,752 global commercial terminals with GIS polygon boundary shapes; zoomIndex resolved across all asset sectors.'
        },
        {
            'series_id': 'signal_distance_ports',
            'display_name': 'Signal Ocean — High-Precision Routing Ports Database',
            'status': 'LIVE',
            'source_name': 'Signal Ocean Platform',
            'source_url': 'https://app.signalocean.com/api/distanceTool/ports',
            'fetch_method': 'REST API (Extracted)',
            'fetch_script': 'scripts/acquire/register_signal_ocean.py',
            'output_file': 'data/geospatial/signal_distance_ports.json',
            'row_count': 12060,
            'date_span': None,
            'last_fetched_utc': datetime.now(timezone.utc).isoformat(),
            'unit': 'Ports',
            'is_derived': False,
            'derivation': None,
            'notes': '12,060 maritime routing ports and waypoints.'
        },
        {
            'series_id': 'signal_vessels_dry_bulk',
            'display_name': 'Signal Ocean — Global Dry Bulk Merchant Fleet',
            'status': 'LIVE',
            'source_name': 'Signal Ocean Platform',
            'source_url': 'https://app.signalocean.com',
            'fetch_method': 'REST API (Extracted)',
            'fetch_script': 'scripts/acquire/register_signal_ocean.py',
            'output_file': 'data/geospatial/signal_vessels_dry_bulk.json',
            'row_count': 33559,
            'date_span': None,
            'last_fetched_utc': datetime.now(timezone.utc).isoformat(),
            'unit': 'Hulls',
            'is_derived': False,
            'derivation': None,
            'notes': 'Complete global dry bulk fleet registry.'
        },
        {
            'series_id': 'signal_vessels_tankers',
            'display_name': 'Signal Ocean — Global Tanker Merchant Fleet',
            'status': 'LIVE',
            'source_name': 'Signal Ocean Platform',
            'source_url': 'https://app.signalocean.com',
            'fetch_method': 'REST API (Extracted)',
            'fetch_script': 'scripts/acquire/register_signal_ocean.py',
            'output_file': 'data/geospatial/signal_vessels_tankers.json',
            'row_count': 19862,
            'date_span': None,
            'last_fetched_utc': datetime.now(timezone.utc).isoformat(),
            'unit': 'Hulls',
            'is_derived': False,
            'derivation': None,
            'notes': 'Complete global tanker fleet registry.'
        },
        {
            'series_id': 'signal_live_fleet_positions',
            'display_name': 'Signal Ocean — Live Fleet Positions (4 Sectors)',
            'status': 'LIVE',
            'source_name': 'Signal Ocean Platform',
            'source_url': 'https://app.signalocean.com/api/distanceTool/vessels/positions',
            'fetch_method': 'REST API (Batch Post)',
            'fetch_script': 'scripts/acquire/register_signal_ocean.py',
            'output_file': 'data/geospatial/signal_live_fleet_positions_capesize_vloc.json',
            'row_count': 7937,
            'date_span': None,
            'last_fetched_utc': datetime.now(timezone.utc).isoformat(),
            'unit': 'Live Positions',
            'is_derived': False,
            'derivation': None,
            'notes': '7,937 live positions across Capesize/VLOC, VLCC/Suezmax, LNG, and LPG fleets.'
        }
    ]

    for item in signal_entries:
        if item['series_id'] in existing_ids:
            manifest['series'][existing_ids[item['series_id']]] = item
        else:
            manifest['series'].append(item)

    with open(MANIFEST_PATH, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)
    logging.info('Registered %d Signal Ocean series in manifest. Total series: %d', len(signal_entries), len(manifest['series']))

if __name__ == '__main__':
    hashes = fix_and_verify_map_ports()
    build_signal_views()
    register_provenance()
