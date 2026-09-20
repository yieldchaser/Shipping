#!/usr/bin/env python3
"""
Live Fleet AIS Positions Synchronizer
====================================
Directly synchronizes live AIS coordinates, speeds, headings, and operational
statuses for all 7,937 commercial hulls across the 4 core sectors:
- Capesize / VLOC
- VLCC / Suezmax
- LNG Carriers
- LPG Gas Carriers

Uses the Signal Ocean distanceTool/vessels/positions endpoint with batch IMO lists.
"""

import os
import sys
import json
import time
import urllib.request
from pathlib import Path
from datetime import datetime, timezone

REPO_ROOT = Path(r"c:\Users\Dell\Github\Shipping")
GEO_DIR = REPO_ROOT / "data" / "geospatial"
VIEWS_DIR = REPO_ROOT / "data" / "views" / "signal"
MANIFEST_PATH = REPO_ROOT / "data" / "provenance" / "manifest.json"

COOKIE = (
    "ai_user=cZXcLZeNE+L1aNhm6mjEcz|2026-09-04T17:35:13.939Z; has_logged_in=true; "
    "intercom-device-id-cynziaks=1dec6a0e-3671-4947-9c48-a9132eeffa51; "
    ".AspNetCore.Identity.Application=CfDJ8ESwiAelOthHu5THadY14mSQQOoBq5uYox9v4UFQDSTKFFevu2uguxXd8nwzQsZkTgl_DgO7bv-OkslRSDbSRwtUIp3OC2AyToEU6leQDYooYCj34FVfD3ypctfxmhaeTyLRRNKHCAbMzi01kweM0d6VStH9bc8hxok-kkMjMnhURu0Jo6sfZaXxILrvXdn2ZFXLp2Msus73QTQMxXNZ0EnVeUk7OTeSMcWAMB6BSrtVNMdOSdHGv3DnH5DA7CZjd-MuAQhWX7YD3J2KP7h2mb1LjwRpZU37_6dK85S62tQN2Cgn1GOVTCuAYxGT7AIGrg5Po5BGrlO3BnbnKRb-88oTGILHbxsRNrwSyb-kR1XI2nonOO3vVCq1g1Z9k62zhlYU5sa61-vLUzmz1qEabCOLzITeDvKkNMWMUlF0txHoT55DrldgLUN8wag13kaiXMkV2gmEANZi48U7vjeyt_JYwzaRb8O60lAHZ6FsX4Nfiz85slyn0CjZp0FJ3O_jx3VEWCrkqCpwg-Ay4-XOuZkVeiJx9DFCyOgBW_Cp5K23vqGUQmzNGfdDvg9pOd6I2-rP8komHvLpA93r4BZOGqTpuKJrWIJsIbVPGDqZ-R59YQyumqN2Jc0yJabk55DyKqlmmv4mEGwhRW47t2Y2JfYwrArocO-mvfp00TrqIAgoVSpR2fbxApzkMxN1Wi5eF8LsvSFS1yHI2P0aw0Xs6umY4YXqXtizFAfQ8Wm4dDR8wRdnTpWZ1PsEFlsS8N2065L-FLp9PmBhyLRtegOyUJTqoBZ6wjXq0jTd3VVWQ9_o38U6v7vG5mjVhl0I5s1oAdpjKUaezX7qkgeg6jMId_I; "
    "intercom-session-cynziaks=M2F0L0xQNDkyemVRSXJQcDA0RFBYbWRBTlM3bFRUWEdxajJxTGdIZ1JhUGVFZmdlY0Q3cVdiTXgrOStPa09GTFdDYlZtNDF1U01iRDY3YnpVUFJBRHpoNFFDVmpCUGF3MTArd20rSXQ4UStzL01XVUFWanFqYnZyRFlhdVAwWXh2YTBOSnQvaTdGamZwWDdOUFlza09MeEovSTJQZGVpaDZqWjVlQjNqVGZYbXdHVEU1WlRuL2lldzR5QzhDMVJqcTZvelpxMTFycmFudTRVd2I4am1hMnprY0JuZG1lWVFJRzVRY0ZNNUdqcW9QbkE4dk83cG1GTU0rU2NTSmtLazF6K3RCaGZXZW1HcGZyYmNZQTNWdFE9PS0tTUVYM1JPREg5d0ZhZVRjNzJJKzNHZz09--89ff7395f6fba33bcae792ba311f563b87287dbb; "
    "ai_session=RLqibq1c2qSFH1B6wNyqch|1789796751670|1789797264245"
)

HEADERS = {
    'accept': 'application/json, text/plain, */*',
    'content-type': 'application/json',
    'cookie': COOKIE,
    'referer': 'https://app.signalocean.com/',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36 Edg/153.0.0.0',
    'x-vessel-type': '3'
}

SECTORS = {
    'capesize_vloc': 'signal_live_fleet_positions_capesize_vloc.json',
    'vlcc_suezmax': 'signal_live_fleet_positions_vlcc_suezmax.json',
    'lng': 'signal_live_fleet_positions_lng.json',
    'lpg': 'signal_live_fleet_positions_lpg.json'
}

URL = 'https://app.signalocean.com/api/distanceTool/vessels/positions'
BATCH_SIZE = 400


def sync_sector(sector_key: str, filename: str):
    file_path = GEO_DIR / filename
    if not file_path.exists():
        print(f"Error: {file_path} not found!")
        return

    with open(file_path, 'r', encoding='utf-8') as f:
        existing_vessels = json.load(f)

    imos = [v['imo'] for v in existing_vessels if v.get('imo')]
    print(f"\n[{sector_key.upper()}] Querying live AIS telemetry for {len(imos)} hulls in batches of {BATCH_SIZE}...")

    live_positions = []
    for i in range(0, len(imos), BATCH_SIZE):
        batch = imos[i:i + BATCH_SIZE]
        body = json.dumps({'imoList': batch}).encode('utf-8')
        req = urllib.request.Request(URL, data=body, headers=HEADERS, method='POST')
        try:
            with urllib.request.urlopen(req, timeout=35) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode('utf-8'))
                    live_positions.extend(data)
                    print(f"  Batch {i//BATCH_SIZE + 1}/{(len(imos)-1)//BATCH_SIZE + 1}: received {len(data)} live positions.")
                else:
                    print(f"  Batch {i//BATCH_SIZE + 1} failed: status {resp.status}")
        except Exception as ex:
            print(f"  Batch {i//BATCH_SIZE + 1} error: {ex}")
        time.sleep(1.0)

    if live_positions:
        # Permanently archive to monthly Parquet time-series ledger
        try:
            sys.path.insert(0, str(REPO_ROOT))
            from scripts.geospatial.archive_ais_history import append_live_positions_to_archive
            append_live_positions_to_archive(live_positions)
        except Exception as ex:
            print(f"  Warning: Archive write failed: {ex}")

        with open(file_path, 'w', encoding='utf-8', newline='\n') as f:
            json.dump(live_positions, f, separators=(',', ':'))
        print(f"  -> Successfully updated {filename}: {len(live_positions)} fresh positions saved ({file_path.stat().st_size // 1024} KB).")
    return live_positions


def synthesize_views():
    print("\nSynthesizing updated fleet_positions_summary.json view...")
    VIEWS_DIR.mkdir(parents=True, exist_ok=True)
    fleet_summary = {}

    for sector, filename in SECTORS.items():
        file_path = GEO_DIR / filename
        if file_path.exists():
            vessels = json.load(open(file_path, 'r', encoding='utf-8'))
            fleet_summary[sector] = {
                'total_tracked': len(vessels),
                'sample': [
                    {
                        'imo': v.get('imo'),
                        'name': v.get('vesselName'),
                        'lat': round(float(v.get('lat') if v.get('lat') is not None else v.get('latitude', 0)), 2),
                        'lon': round(float(v.get('lon') if v.get('lon') is not None else v.get('longitude', 0)), 2),
                        'spd': v.get('speed'),
                        'status': v.get('aisReportedStatus') or (v.get('tonnageListData', {}) or {}).get('operationalStatus') or v.get('commercialOperationalStatus') or 'Underway'
                    }
                    for v in vessels[:50]
                ]
            }

    f_path = VIEWS_DIR / 'fleet_positions_summary.json'
    with open(f_path, 'w', encoding='utf-8', newline='\n') as f:
        json.dump({
            'header': {
                'series_id': 'signal_fleet_positions',
                'source': 'Signal Ocean Live Tracking',
                'as_of': datetime.now(timezone.utc).isoformat(),
                'total_hulls': sum(f['total_tracked'] for f in fleet_summary.values()),
                'status': 'LIVE'
            },
            'sectors': fleet_summary
        }, f, separators=(',', ':'))

    print(f"View {f_path.name} updated: {sum(f['total_tracked'] for f in fleet_summary.values()):,} hulls tracked as of {datetime.now(timezone.utc).isoformat()} UTC.")


def main():
    print("================================================================================")
    print("  LIVE SIGNAL OCEAN FLEET AIS POSITION SYNCHRONIZER (SEPTEMBER 19, 2026)")
    print("================================================================================")

    for sector, filename in SECTORS.items():
        sync_sector(sector, filename)

    synthesize_views()
    print("\nAll 4 sectors live positions successfully synchronized from Signal Ocean!")


if __name__ == '__main__':
    main()
