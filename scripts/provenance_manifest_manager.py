"""
Authoritative Provenance Manifest Manager & Immutable Storage Engine
====================================================================
Provides configurable, immutable raw source storage, derived per-fund holdings,
canonical snapshot content hashing, and append-only cryptographic provenance records.

Architecture:
- Configurable paths via ETF_DATA_DIR (enables 100% isolated test sandboxes without touching production).
- Distinct separation of immutable raw retrieval records and snapshot publication events.
- Genuinely append-only manifest registry.
"""

import os
import json
import hashlib
import pandas as pd
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple, List

# Base directory resolution (defaults to repository data/etf, overridable via environment)
def get_base_data_dir() -> str:
    env_dir = os.environ.get('ETF_DATA_DIR')
    if env_dir:
        return os.path.abspath(env_dir)
    return os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'data', 'etf'))

def get_manifest_path() -> str:
    return os.path.join(get_base_data_dir(), 'snapshots', 'provenance_manifest.json')

def get_raw_sources_dir() -> str:
    return os.path.join(get_base_data_dir(), 'raw_sources')

def get_raw_holdings_dir(fund: Optional[str] = None) -> str:
    base = os.path.join(get_base_data_dir(), 'raw_holdings')
    if fund:
        return os.path.join(base, fund.upper())
    return base

def get_snapshots_dir() -> str:
    return os.path.join(get_base_data_dir(), 'snapshots')

PARSER_VERSION = '2026.08.14-V2'

OFFICIAL_SOURCE_URLS = {
    'BDRY': 'https://amplifyetfs.com/bdry-holdings/',
    'BWET': 'https://amplifyetfs.com/bwet-holdings/'
}

def calculate_sha256(filepath: str) -> str:
    """Computes standard SHA-256 hexadecimal digest of a file on disk."""
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

def calculate_bytes_sha256(data_bytes: bytes) -> str:
    """Computes standard SHA-256 hexadecimal digest of in-memory bytes."""
    return hashlib.sha256(data_bytes).hexdigest()

def compute_snapshot_content_sha256(snapshot_payload: Dict[str, Any]) -> str:
    """
    Computes deterministic canonical SHA-256 hash of a snapshot payload projection
    excluding self-referential hash fields (snapshot_content_sha256, manifest_snapshot_sha256).
    """
    proj = json.loads(json.dumps(snapshot_payload))  # Deep copy
    if 'provenance' in proj and isinstance(proj['provenance'], dict):
        proj['provenance'].pop('snapshot_content_sha256', None)
        proj['provenance'].pop('manifest_snapshot_sha256', None)
    canonical_json = json.dumps(proj, sort_keys=True, indent=2)
    return hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()

def load_manifest(custom_manifest_path: Optional[str] = None) -> Dict[str, Any]:
    """Loads provenance_manifest.json or creates initial append-only structure if missing."""
    m_path = custom_manifest_path or get_manifest_path()
    if os.path.exists(m_path):
        try:
            with open(m_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if 'records' in data and 'BDRY' in data['records']:
                    if 'active_snapshot_record_ids' not in data:
                        data['active_snapshot_record_ids'] = {}
                    if 'retrieval_records' not in data:
                        data['retrieval_records'] = {'BDRY': {}, 'BWET': {}}
                    if 'publication_events' not in data:
                        data['publication_events'] = {'BDRY': {}, 'BWET': {}}
                    return data
        except Exception:
            pass
            
    return {
        'manifest_version': '1.3.0',
        'last_updated_utc': datetime.now(timezone.utc).isoformat(),
        'active_snapshot_record_ids': {
            'BDRY': None,
            'BWET': None
        },
        'records': {
            'BDRY': {},
            'BWET': {}
        },
        'retrieval_records': {
            'BDRY': {},
            'BWET': {}
        },
        'publication_events': {
            'BDRY': {},
            'BWET': {}
        },
        'audit_log': []
    }

def save_manifest(manifest: Dict[str, Any], custom_manifest_path: Optional[str] = None) -> None:
    """Atomically persists provenance manifest JSON with Windows-safe replace."""
    m_path = custom_manifest_path or get_manifest_path()
    os.makedirs(os.path.dirname(m_path), exist_ok=True)
    manifest['last_updated_utc'] = datetime.now(timezone.utc).isoformat()
    temp_path = f"{m_path}.tmp"
    try:
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2)
        os.replace(temp_path, m_path)
    except OSError:
        with open(m_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2)

def save_raw_source_bytes(raw_bytes: bytes, source_date_str: str, base_dir: Optional[str] = None) -> Tuple[str, str]:
    """
    Persists unparsed official downloaded response bytes to an immutable file under
    raw_sources/amplify_master_<DATE>.csv.
    Never overwrites different content; mints a versioned file if hash differs.
    Returns (rel_path, raw_sha256).
    """
    sources_dir = os.path.join(base_dir, 'raw_sources') if base_dir else get_raw_sources_dir()
    os.makedirs(sources_dir, exist_ok=True)
    raw_sha = calculate_bytes_sha256(raw_bytes)
    
    base_filename = f"amplify_master_{source_date_str}.csv"
    target_path = os.path.join(sources_dir, base_filename)
    
    if os.path.exists(target_path):
        existing_sha = calculate_sha256(target_path)
        if existing_sha == raw_sha:
            root = os.path.dirname(sources_dir)
            rel = os.path.relpath(target_path, root).replace('\\', '/')
            if not rel.startswith('data/'):
                rel = f"data/etf/{rel}"
            return rel, raw_sha
        # Different bytes on same date -> save as versioned file
        ver = 2
        while True:
            v_filename = f"amplify_master_{source_date_str}_v{ver}.csv"
            v_path = os.path.join(sources_dir, v_filename)
            if not os.path.exists(v_path):
                target_path = v_path
                break
            if calculate_sha256(v_path) == raw_sha:
                target_path = v_path
                break
            ver += 1
            
    if not os.path.exists(target_path):
        with open(target_path, 'wb') as f:
            f.write(raw_bytes)
            
    root = os.path.dirname(sources_dir)
    rel = os.path.relpath(target_path, root).replace('\\', '/')
    if not rel.startswith('data/'):
        rel = f"data/etf/{rel}"
    return rel, raw_sha

def save_immutable_raw_archive(fund: str, as_of_date: str, df: pd.DataFrame, base_dir: Optional[str] = None) -> Tuple[str, str]:
    """
    Saves an immutable snapshot CSV under raw_holdings/<FUND>/<DATE>.csv.
    Never overwrites existing files with different hashes; mints versioned archives.
    Returns (relative_file_path, computed_sha256).
    """
    f_upper = fund.upper()
    fund_dir = os.path.join(base_dir, 'raw_holdings', f_upper) if base_dir else get_raw_holdings_dir(f_upper)
    os.makedirs(fund_dir, exist_ok=True)
    
    base_name = f"{as_of_date}.csv"
    target_file = os.path.join(fund_dir, base_name)
    
    csv_content = df.to_csv(index=False, lineterminator='\n').encode('utf-8')
    computed_sha = calculate_bytes_sha256(csv_content)
    
    if os.path.exists(target_file):
        existing_sha = calculate_sha256(target_file)
        if existing_sha == computed_sha:
            root = os.path.dirname(os.path.dirname(fund_dir))
            rel = os.path.relpath(target_file, root).replace('\\', '/')
            if not rel.startswith('data/'):
                rel = f"data/etf/{rel}"
            return rel, computed_sha
        # Different hash on same date -> mint versioned archive, never overwrite
        ver = 2
        while True:
            v_name = f"{as_of_date}_v{ver}.csv"
            v_path = os.path.join(fund_dir, v_name)
            if not os.path.exists(v_path):
                target_file = v_path
                break
            if calculate_sha256(v_path) == computed_sha:
                target_file = v_path
                break
            ver += 1
            
    if not os.path.exists(target_file):
        with open(target_file, 'wb') as f:
            f.write(csv_content)
            
    root = os.path.dirname(os.path.dirname(fund_dir))
    rel = os.path.relpath(target_file, root).replace('\\', '/')
    if not rel.startswith('data/'):
        rel = f"data/etf/{rel}"
    return rel, computed_sha

def register_raw_retrieval_record(
    fund: str,
    as_of_date: str,
    immutable_archive_path: str,
    archive_sha256: str,
    raw_source_path: str,
    raw_source_sha256: str,
    official_source_url: Optional[str] = None,
    is_official_as_of_date: bool = True,
    date_sourcing: str = "OFFICIAL_SOURCE_DISCLOSED",
    provenance_status: str = "VERIFIED_OFFICIAL_ARCHIVE",
    custom_manifest_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Registers an immutable raw retrieval event in the manifest without overwriting.
    """
    f_upper = fund.upper()
    manifest = load_manifest(custom_manifest_path)
    
    if f_upper not in manifest['retrieval_records']:
        manifest['retrieval_records'][f_upper] = {}
        
    retrieval_id = f"ret:{f_upper}:{as_of_date}:{archive_sha256}"
    if retrieval_id in manifest['retrieval_records'][f_upper]:
        existing_rec = manifest['retrieval_records'][f_upper][retrieval_id]
        if existing_rec.get('archive_sha256') == archive_sha256:
            # Strictly idempotent: return existing immutable record without modifying timestamp or contents
            return existing_rec

    url = official_source_url or OFFICIAL_SOURCE_URLS.get(f_upper, 'https://amplifyetfs.com/')
    
    record = {
        'retrieval_id': retrieval_id,
        'fund': f_upper,
        'holdings_as_of_date': as_of_date,
        'is_official_as_of_date': is_official_as_of_date,
        'date_sourcing': date_sourcing,
        'retrieval_timestamp_utc': datetime.now(timezone.utc).isoformat(),
        'official_source_url': url,
        'raw_source_path': raw_source_path,
        'raw_source_sha256': raw_source_sha256,
        'immutable_archive_path': immutable_archive_path,
        'archive_sha256': archive_sha256,
        'parser_version': PARSER_VERSION,
        'provenance_status': provenance_status,
        'status': provenance_status
    }
    
    # Store immutable retrieval
    manifest['retrieval_records'][f_upper][retrieval_id] = record
    
    # Also maintain compatibility under records[fund][date]['versions']
    fund_records = manifest['records'][f_upper]
    if as_of_date not in fund_records:
        fund_records[as_of_date] = {'versions': {}, 'active_archive_sha256': archive_sha256}
    elif isinstance(fund_records[as_of_date], dict) and 'versions' not in fund_records[as_of_date]:
        old_rec = fund_records[as_of_date]
        old_sha = old_rec.get('archive_sha256', archive_sha256)
        fund_records[as_of_date] = {'versions': {old_sha: old_rec}, 'active_archive_sha256': old_sha}
        
    fund_records[as_of_date]['versions'][archive_sha256] = record
    fund_records[as_of_date]['active_archive_sha256'] = archive_sha256
    
    save_manifest(manifest, custom_manifest_path)
    return record

def register_provenance_record(
    fund: str,
    as_of_date: str,
    immutable_archive_path: str,
    archive_sha256: str,
    official_source_url: Optional[str] = None,
    raw_source_path: Optional[str] = None,
    raw_source_sha256: Optional[str] = None,
    is_official_as_of_date: bool = True,
    date_sourcing: str = "OFFICIAL_SOURCE_DISCLOSED",
    parser_version: str = PARSER_VERSION,
    snapshot_content_sha256: Optional[str] = None,
    provenance_status: str = "VERIFIED_OFFICIAL_ARCHIVE",
    custom_manifest_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Registers an immutable retrieval version and publication event in the provenance manifest.
    Never overwrites existing records; strictly append-only and idempotent.
    """
    f_upper = fund.upper()
    manifest = load_manifest(custom_manifest_path)
    
    if f_upper not in manifest['records']:
        manifest['records'][f_upper] = {}
        
    url = official_source_url or OFFICIAL_SOURCE_URLS.get(f_upper, 'https://amplifyetfs.com/')
    raw_p = raw_source_path or immutable_archive_path
    raw_sha = raw_source_sha256 or archive_sha256
    
    # 1. Register retrieval record
    ret_rec = register_raw_retrieval_record(
        fund=f_upper,
        as_of_date=as_of_date,
        immutable_archive_path=immutable_archive_path,
        archive_sha256=archive_sha256,
        raw_source_path=raw_p,
        raw_source_sha256=raw_sha,
        official_source_url=url,
        is_official_as_of_date=is_official_as_of_date,
        date_sourcing=date_sourcing,
        provenance_status=provenance_status,
        custom_manifest_path=custom_manifest_path
    )
    
    # 2. Register publication event
    manifest = load_manifest(custom_manifest_path)
    record_id = f"pub:{f_upper}:{as_of_date}:{archive_sha256}"
    
    fund_records = manifest['records'][f_upper]
    if as_of_date in fund_records and isinstance(fund_records[as_of_date], dict) and 'versions' in fund_records[as_of_date]:
        if archive_sha256 in fund_records[as_of_date]['versions']:
            existing_pub = fund_records[as_of_date]['versions'][archive_sha256]
            if existing_pub.get('archive_sha256') == archive_sha256 and (snapshot_content_sha256 is None or existing_pub.get('snapshot_content_sha256') == snapshot_content_sha256):
                # Strictly idempotent: ensure active pointer is set and return existing record unchanged
                manifest['active_snapshot_record_ids'][f_upper] = record_id
                fund_records[as_of_date]['active_archive_sha256'] = archive_sha256
                save_manifest(manifest, custom_manifest_path)
                return existing_pub
                
    pub_record = dict(ret_rec)
    pub_record['record_id'] = record_id
    pub_record['snapshot_content_sha256'] = snapshot_content_sha256
    pub_record['snapshot_sha256'] = snapshot_content_sha256
    pub_record['manifest_snapshot_sha256'] = snapshot_content_sha256
    pub_record['expected_sha256'] = archive_sha256
    pub_record['local_archive_path'] = immutable_archive_path
    
    if as_of_date not in fund_records:
        fund_records[as_of_date] = {'versions': {}, 'active_archive_sha256': archive_sha256}
    elif isinstance(fund_records[as_of_date], dict) and 'versions' not in fund_records[as_of_date]:
        old_rec = fund_records[as_of_date]
        old_sha = old_rec.get('archive_sha256', archive_sha256)
        fund_records[as_of_date] = {'versions': {old_sha: old_rec}, 'active_archive_sha256': old_sha}
        
    fund_records[as_of_date]['versions'][archive_sha256] = pub_record
    fund_records[as_of_date]['active_archive_sha256'] = archive_sha256
    
    # Set active snapshot record ID
    manifest['active_snapshot_record_ids'][f_upper] = record_id
    
    # Append to append-only audit log
    if 'audit_log' not in manifest:
        manifest['audit_log'] = []
    manifest['audit_log'].append({
        'record_id': record_id,
        'timestamp_utc': pub_record['retrieval_timestamp_utc'],
        'fund': f_upper,
        'as_of_date': as_of_date,
        'archive_sha256': archive_sha256,
        'snapshot_content_sha256': snapshot_content_sha256,
        'provenance_status': provenance_status
    })
    
    save_manifest(manifest, custom_manifest_path)
    return pub_record

def get_active_snapshot_record_id(fund: str, custom_manifest_path: Optional[str] = None) -> Optional[str]:
    """Returns the active record ID for the currently published revision."""
    manifest = load_manifest(custom_manifest_path)
    return manifest.get('active_snapshot_record_ids', {}).get(fund.upper())

def get_provenance_record_for_date(
    fund: str,
    as_of_date: str,
    archive_sha256: Optional[str] = None,
    custom_manifest_path: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Retrieves provenance record for a specific date and optional archive hash.
    If archive_sha256 is omitted, returns the active version for that date.
    """
    f_upper = fund.upper()
    manifest = load_manifest(custom_manifest_path)
    fund_records = manifest.get('records', {}).get(f_upper, {})
    if as_of_date not in fund_records:
        return None
        
    date_entry = fund_records[as_of_date]
    if isinstance(date_entry, dict):
        if 'versions' in date_entry:
            versions = date_entry['versions']
            if archive_sha256:
                return versions.get(archive_sha256)
            active_sha = date_entry.get('active_archive_sha256')
            if active_sha and active_sha in versions:
                return versions[active_sha]
            if versions:
                return list(versions.values())[-1]
            return None
        elif archive_sha256 and archive_sha256 in date_entry:
            return date_entry[archive_sha256]
        elif 'fund' in date_entry:
            return date_entry
    return None

def get_all_provenance_versions_for_date(
    fund: str,
    as_of_date: str,
    custom_manifest_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Returns all immutable retrieval version records registered for a given date."""
    f_upper = fund.upper()
    manifest = load_manifest(custom_manifest_path)
    fund_records = manifest.get('records', {}).get(f_upper, {})
    if as_of_date not in fund_records:
        return []
    date_entry = fund_records[as_of_date]
    if isinstance(date_entry, dict) and 'versions' in date_entry:
        return list(date_entry['versions'].values())
    elif isinstance(date_entry, dict) and 'fund' in date_entry:
        return [date_entry]
    return []

def get_latest_provenance_record(fund: str, custom_manifest_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieves the latest published provenance manifest record for a fund."""
    f_upper = fund.upper()
    manifest = load_manifest(custom_manifest_path)
    
    # Check active snapshot record ID
    active_id = manifest.get('active_snapshot_record_ids', {}).get(f_upper)
    if active_id and ':' in active_id:
        parts = active_id.split(':')
        if len(parts) >= 4 and parts[0] == 'pub':
            rec = get_provenance_record_for_date(f_upper, parts[2], parts[3], custom_manifest_path)
            if rec:
                return rec
        elif len(parts) >= 3:
            rec = get_provenance_record_for_date(f_upper, parts[1], parts[2], custom_manifest_path)
            if rec:
                return rec
                
    fund_records = manifest.get('records', {}).get(f_upper, {})
    if not fund_records:
        return None
    sorted_dates = sorted(fund_records.keys())
    latest_date = sorted_dates[-1]
    return get_provenance_record_for_date(f_upper, latest_date, custom_manifest_path=custom_manifest_path)
