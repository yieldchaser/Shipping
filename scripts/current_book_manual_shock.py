"""
Breakwave ETF Current-Book Manual Scenario Sensitivity Engine
============================================================
Provides an explicit, immutable manual scenario shock interface for BDRY & BWET.
Features strict fail-closed governance:
- Rejects future-dated snapshots relative to evaluation date.
- Requires verified immutable raw archives and valid provenance manifest records.
- Zero runtime bootstrap/registration.
- Supports configurable base data directories for isolated testing.
"""

import os
import re
import json
import hashlib
import numpy as np
import pandas as pd
from datetime import datetime, date, timezone
from typing import Dict, Any, Optional, List, Tuple

from contract_spec_registry import (
    resolve_contract_spec,
    get_authoritative_multiplier,
    UnknownContractSpecError
)
from provenance_manifest_manager import (
    calculate_sha256,
    get_provenance_record_for_date,
    get_latest_provenance_record,
    get_base_data_dir,
    OFFICIAL_SOURCE_URLS
)

class MissingProvenanceRecordError(Exception):
    """Raised when an authoritative snapshot lacks required provenance records."""
    pass

class StaleSnapshotError(Exception):
    """Raised when an official snapshot exceeds the maximum allowed business-day age limit."""
    pass

class FutureDatedSnapshotError(Exception):
    """Raised when a snapshot as-of date is in the future relative to evaluation date."""
    pass

def compute_business_days_between(d1: date, d2: date) -> int:
    """Calculates number of business days (Monday-Friday) between two dates."""
    if d1 > d2:
        return 0
    current = d1
    business_days = 0
    while current < d2:
        current = current + pd.Timedelta(days=1)
        if current.weekday() < 5:  # Monday = 0, Friday = 4
            business_days += 1
    return business_days

def load_latest_official_snapshot(
    fund: str,
    max_stale_business_days: int = 3,
    reference_time_utc: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Loads and validates the latest dated holdings snapshot from immutable raw archive.
    Fails closed if provenance record is missing, hash mismatches, if snapshot is future-dated,
    or if snapshot exceeds the business-day freshness limit.
    """
    f_upper = fund.upper()
    f_lower = fund.lower()
    
    if f_upper not in OFFICIAL_SOURCE_URLS:
        raise MissingProvenanceRecordError(f"No official provenance record registered for fund '{fund}'.")
        
    # Determine evaluation date
    if reference_time_utc is None:
        eval_dt = datetime.now(timezone.utc).date()
        ref_iso = datetime.now(timezone.utc).isoformat()
    else:
        eval_dt = reference_time_utc.date() if isinstance(reference_time_utc, datetime) else reference_time_utc
        ref_iso = reference_time_utc.isoformat() if isinstance(reference_time_utc, datetime) else f"{reference_time_utc}T00:00:00+00:00"

    # 1. Determine latest date from raw holdings or history CSV
    base_dir = get_base_data_dir()
    history_file = os.path.join(base_dir, f"{f_lower}_holdings_history.csv")
    if not os.path.exists(history_file):
        raise MissingProvenanceRecordError(f"Holdings history file not found: {history_file}")
        
    df_hist = pd.read_csv(history_file)
    if df_hist.empty:
        raise ValueError(f"Holdings history dataset is empty: {history_file}")
        
    df_hist['date_dt'] = pd.to_datetime(df_hist['date'], errors='coerce')
    latest_dt = df_hist['date_dt'].max().date()
    latest_date_str = latest_dt.strftime('%Y-%m-%d')
    
    # 2. Reject Future-Dated Snapshots
    if latest_dt > eval_dt:
        raise FutureDatedSnapshotError(
            f"Holdings snapshot for {fund} as-of {latest_date_str} is in the future relative to evaluation date {eval_dt.strftime('%Y-%m-%d')}. Translation locked."
        )

    # 3. Lookup provenance manifest record and resolve immutable archive (Fail-Closed, Zero Bootstrap)
    manifest_rec = get_provenance_record_for_date(f_upper, latest_date_str)
    if not manifest_rec:
        raise MissingProvenanceRecordError(
            f"Provenance manifest record missing for {f_upper} on as-of date {latest_date_str}. "
            f"Runtime bootstrap/registration is disabled. Run explicit historical migration if needed."
        )
        
    raw_archive_rel = manifest_rec.get('immutable_archive_path')
    if not raw_archive_rel:
        raise MissingProvenanceRecordError(
            f"Manifest record for {f_upper} ({latest_date_str}) missing 'immutable_archive_path'."
        )
        
    # Resolve relative archive path against base_dir first, then repo root
    if os.path.isabs(raw_archive_rel):
        raw_archive_full = raw_archive_rel
    else:
        rel_clean = raw_archive_rel
        if rel_clean.startswith('data/etf/'):
            rel_clean = rel_clean[len('data/etf/'):]
        elif rel_clean.startswith('data/'):
            rel_clean = rel_clean[len('data/'):]
            
        base_cand = os.path.normpath(os.path.join(base_dir, rel_clean))
        root_cand = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', raw_archive_rel))
        
        if os.path.exists(base_cand):
            raw_archive_full = base_cand
        elif os.path.exists(root_cand):
            raw_archive_full = root_cand
        else:
            raw_archive_full = os.path.join(base_dir, 'raw_holdings', f_upper, os.path.basename(raw_archive_rel))
            
    if not os.path.exists(raw_archive_full):
        raise MissingProvenanceRecordError(
            f"Immutable raw archive file missing for {f_upper} ({latest_date_str}) at {raw_archive_rel}. "
            f"Runtime generation is disabled."
        )
        
    # 4. Read and cryptographically verify immutable archive
    computed_archive_sha = calculate_sha256(raw_archive_full)
    if computed_archive_sha != manifest_rec.get('archive_sha256'):
        raise MissingProvenanceRecordError(
            f"Provenance archive hash mismatch for {fund} ({latest_date_str}): "
            f"Expected {manifest_rec.get('archive_sha256')}, got {computed_archive_sha}"
        )
        
    # 5. Verify raw source link if present
    raw_source_rel = manifest_rec.get('raw_source_path')
    if raw_source_rel:
        if os.path.isabs(raw_source_rel):
            raw_source_full = raw_source_rel
        else:
            rel_clean = raw_source_rel
            if rel_clean.startswith('data/etf/'):
                rel_clean = rel_clean[len('data/etf/'):]
            elif rel_clean.startswith('data/'):
                rel_clean = rel_clean[len('data/'):]
                
            base_cand = os.path.normpath(os.path.join(base_dir, rel_clean))
            root_cand = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', raw_source_rel))
            if os.path.exists(base_cand):
                raw_source_full = base_cand
            elif os.path.exists(root_cand):
                raw_source_full = root_cand
            else:
                raw_source_full = os.path.join(base_dir, 'raw_sources', os.path.basename(raw_source_rel))
                
        if not os.path.exists(raw_source_full):
            raise MissingProvenanceRecordError(
                f"Parent raw source file missing for {f_upper} ({latest_date_str}) at {raw_source_rel}."
            )
        computed_raw_sha = calculate_sha256(raw_source_full)
        if computed_raw_sha != manifest_rec.get('raw_source_sha256'):
            raise MissingProvenanceRecordError(
                f"Parent raw source hash mismatch for {fund} ({latest_date_str}): "
                f"Expected {manifest_rec.get('raw_source_sha256')}, got {computed_raw_sha}"
            )
        
    # 6. Check Business-Day Freshness
    age_bdays = compute_business_days_between(latest_dt, eval_dt)
    if age_bdays > max_stale_business_days:
        raise StaleSnapshotError(
            f"Holdings snapshot for {fund} as-of {latest_date_str} is {age_bdays} business days old "
            f"(evaluated against {eval_dt.strftime('%Y-%m-%d')}), exceeding the freshness limit of {max_stale_business_days} business days."
        )
        
    # 7. Load positions from immutable raw archive
    df_raw = pd.read_csv(raw_archive_full)
    snapshot_df = df_raw.copy()
    snapshot_df['Lots'] = pd.to_numeric(snapshot_df['Lots'].astype(str).str.replace(',', '').str.strip(), errors='coerce').fillna(0.0)
    snapshot_df['Price'] = pd.to_numeric(snapshot_df['Price'].astype(str).str.replace(',', '').str.strip(), errors='coerce').fillna(0.0)
    
    # Filter out cash/invesco collateral to isolate derivative contracts
    derivatives_df = snapshot_df[~snapshot_df['Name'].astype(str).str.lower().str.contains('cash|invesco', regex=True)].copy()
    
    positions = []
    total_futures_notional = 0.0
    
    for idx, row in derivatives_df.iterrows():
        c_name = str(row['Name']).strip()
        ticker = str(row.get('Ticker', '')).strip()
        cusip = str(row.get('CUSIP', '')).strip()
        lots = float(row['Lots'])
        price = float(row['Price'])
        
        spec = resolve_contract_spec(
            identifier=c_name,
            ticker=ticker,
            cusip=cusip,
            fund=fund
        )
        
        multiplier = float(spec['contract_size'])
        position_notional = lots * price * multiplier
        total_futures_notional += position_notional
        
        positions.append({
            'contract_name': c_name,
            'ticker': ticker,
            'cusip': cusip,
            'lots': lots,
            'price': price,
            'multiplier': multiplier,
            'multiplier_unit': spec['contract_size_unit'],
            'product_code': spec['clearing_product_code'],
            'rulebook_ref': spec['rulebook_reference'],
            'route_class': spec['vessel_class'],
            'exchange': spec['exchange_clearing_venue'],
            'position_notional': position_notional
        })
        
    return {
        'fund': f_upper,
        'snapshot_date': latest_date_str,
        'is_official_as_of_date': manifest_rec.get('is_official_as_of_date', True),
        'date_sourcing': manifest_rec.get('date_sourcing', 'OFFICIAL_SOURCE_DISCLOSED'),
        'reference_time_utc': ref_iso,
        'business_day_age': age_bdays,
        'max_stale_limit_bdays': max_stale_business_days,
        'is_fresh': True,
        'provenance_record': manifest_rec,
        'raw_archive_path': raw_archive_rel,
        'computed_archive_sha256': computed_archive_sha,
        'provenance_verified': True,
        'provenance_status': manifest_rec.get('provenance_status', 'VERIFIED_OFFICIAL_ARCHIVE'),
        'positions_count': len(positions),
        'total_futures_notional': total_futures_notional,
        'positions': positions
    }

def calculate_manual_contract_shock(
    snapshot: Dict[str, Any],
    contract_shocks: Dict[str, float],
    shares_outstanding: Optional[int] = None,
    contemporaneous_nav_dollars: Optional[float] = None
) -> Dict[str, Any]:
    """
    Evaluates gross futures dollar P&L and optional per-share impact on the verified snapshot book.
    """
    positions = snapshot['positions']
    total_dollar_impact = 0.0
    position_breakdowns = []
    
    for pos in positions:
        c_name = pos['contract_name']
        lots = pos['lots']
        base_px = pos['price']
        multiplier = pos['multiplier']
        
        shock_pct = float(contract_shocks.get(c_name, 0.0))
        delta_price = base_px * (shock_pct / 100.0)
        sim_price = base_px + delta_price
        dollar_impact = lots * delta_price * multiplier
        total_dollar_impact += dollar_impact
        
        position_breakdowns.append({
            'name': c_name,
            'contract_name': c_name,
            'ticker': pos['ticker'],
            'cusip': pos['cusip'],
            'lots': lots,
            'multiplier': multiplier,
            'multiplier_unit': pos.get('multiplier_unit', 'Units'),
            'base_price': base_px,
            'shock_pct': shock_pct,
            'delta_price': delta_price,
            'delta_mark_dollars': delta_price,
            'sim_price': sim_price,
            'dollar_impact': dollar_impact,
            'contract_dollar_impact': dollar_impact
        })
        
    delta_nav_per_share = None
    share_conversion_status = "PER_SHARE_UNAVAILABLE_MISSING_SAME_DATE_SHARES"
    
    if shares_outstanding is not None and shares_outstanding > 0:
        delta_nav_per_share = total_dollar_impact / float(shares_outstanding)
        share_conversion_status = "PER_SHARE_CALCULATED_MANUAL_SHARES"

    residual_flags = {
        'unobserved_roll_execution_drag': 'Intraday roll and contract expiry trade executions are unobserved.',
        'unobserved_cash_interest_vouchers': 'Daily overnight bank sweep interest credits are unobserved.',
        'unobserved_daily_advisory_fees': 'Daily advisory fee accruals and fee waivers are unobserved.',
        'unobserved_ap_share_creations': 'Authorized participant creation/redemption share movements are unobserved.',
        'secondary_market_premium_discount': 'Secondary market prices trade at a variable premium/discount to NAV.'
    }
        
    return {
        'fund': snapshot['fund'],
        'classification': "PARTIAL: CURRENT-BOOK MANUAL SENSITIVITY — NOT A PREDICTION",
        'snapshot_date': snapshot['snapshot_date'],
        'evaluation_date': snapshot.get('reference_time_utc', '')[:10],
        'snapshot_age_bdays': snapshot.get('business_day_age', 0),
        'freshness_limit_bdays': snapshot.get('max_stale_limit_bdays', 3),
        'source_url': snapshot.get('provenance_record', {}).get('official_source_url', ''),
        'sha256_checksum': snapshot.get('computed_archive_sha256', ''),
        'is_official_as_of_date': snapshot['is_official_as_of_date'],
        'date_sourcing': snapshot['date_sourcing'],
        'provenance_status': snapshot['provenance_status'],
        'total_positions': len(positions),
        'total_base_notional_dollars': snapshot['total_futures_notional'],
        'base_futures_notional': snapshot['total_futures_notional'],
        'total_delta_nav_dollars': total_dollar_impact,
        'total_dollar_impact': total_dollar_impact,
        'dated_official_shares': shares_outstanding,
        'delta_nav_per_share_dollars': delta_nav_per_share,
        'share_conversion_status': share_conversion_status,
        'unresolved_residuals_flags': residual_flags,
        'position_breakdown': position_breakdowns,
        'position_breakdowns': position_breakdowns
    }
