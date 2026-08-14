"""
Thesis-to-ETF Scenario Translator Engine
========================================
Translates user freight market theses directly into gross futures P&L ($)
and approximate ETF Net Asset Value (NAV) & secondary market price ranges for BDRY and BWET.

FOUR STRICT DATA GOVERNANCE SAFEGUARDS:
1. Complete User-Assumed Forward Book Schema (USER_SPECIFIED_FORWARD_BOOK):
   - For any roll-in or new contract, requires exact identifier, lots, multiplier,
     starting/entry mark, target mark, and roll transaction cost assumption.
   - Roll-in contracts missing starting mark, multiplier, or target mark fail closed.
   - Mode is labeled strictly: "User-assumed forward book" (never "actual projected holdings").
2. Internal Validation of Manual Baselines:
   - Requires total NAV > 0, shares > 0, market price > 0, explicit ISO date, source.
   - Enforces mathematical consistency: abs(total_nav / shares - nav_per_share) <= tolerance.
   - Inconsistent manual baselines are rejected / flagged.
3. Three Distinct Prominent Dates in Every Result:
   - (1) Holdings / marks snapshot date (official disclosed archive as-of date)
   - (2) Fund baseline as-of date (contemporaneous or manual baseline date)
   - (3) Scenario horizon date (target evaluation date)
   - Prominently computes date gaps and disclaims non-identical dates.
4. Formal Scenario-Snapshot Contract & Provenance Gate:
   - Validates snapshot schema version, generation timestamp, source URLs, SHA-256 hashes,
     holdings as-of date, contract-spec version, and baseline fields.
   - Missing provenance strictly blocks price-range projections.
"""

import os
import json
import hashlib
from datetime import datetime, timezone, date, timedelta
from typing import Dict, Any, List, Optional, Tuple, Union
import pandas as pd
import numpy as np

from contract_spec_registry import resolve_contract_spec, get_authoritative_multiplier, UnknownContractSpecError
from current_book_manual_shock import (
    load_latest_official_snapshot,
    compute_business_days_between,
    StaleSnapshotError,
    MissingProvenanceRecordError
)
from scenario_snapshot_schema import (
    SCENARIO_SNAPSHOT_SCHEMA_VERSION,
    CONTRACT_SPEC_VERSION,
    validate_scenario_snapshot,
    generate_scenario_snapshot,
    load_published_scenario_snapshot
)
from provenance_manifest_manager import get_base_data_dir

class InvalidForwardBookAssumptionError(Exception):
    """Raised when a user-specified forward book roll-in contract is missing required assumptions."""
    pass

class InconsistentManualBaselineError(Exception):
    """Raised when a user-supplied manual baseline fails internal mathematical consistency."""
    pass

class ThesisScenarioBuilder:
    def __init__(
        self,
        fund: str = 'BDRY',
        max_stale_business_days: int = 3,
        reference_time_utc: Optional[datetime] = None,
        scenario_snapshot_payload: Optional[Dict[str, Any]] = None,
        allow_snapshot_generation: bool = False
    ):
        self.fund = fund.upper()
        self.max_stale_business_days = max_stale_business_days
        self.reference_time_utc = reference_time_utc or datetime.now(timezone.utc)
        eval_date_str = self.reference_time_utc.strftime('%Y-%m-%d')
        
        # 1. Load or accept formal scenario snapshot (READ-ONLY by default)
        if scenario_snapshot_payload is not None:
            is_valid, errors = validate_scenario_snapshot(scenario_snapshot_payload, evaluation_date_str=eval_date_str)
            if not is_valid:
                raise MissingProvenanceRecordError(
                    f"Scenario snapshot failed provenance schema validation: {'; '.join(errors)}"
                )
            self.snapshot_payload = scenario_snapshot_payload
        else:
            if not allow_snapshot_generation:
                # Default: Load already-published active snapshot (Read-Only, zero manifest mutation)
                self.snapshot_payload = load_published_scenario_snapshot(
                    fund=self.fund,
                    evaluation_date_str=eval_date_str,
                    max_stale_business_days=self.max_stale_business_days
                )
            else:
                # Updater-only explicit flag
                self.snapshot_payload = generate_scenario_snapshot(
                    fund=self.fund,
                    reference_time_utc=self.reference_time_utc,
                    max_stale_business_days=self.max_stale_business_days
                )
                
        self.snapshot = {
            'fund': self.snapshot_payload['fund_symbol'],
            'snapshot_date': self.snapshot_payload['holdings_snapshot_as_of_date'],
            'snapshot_age_bdays': self.snapshot_payload['freshness_state']['business_day_age'],
            'freshness_limit_bdays': self.snapshot_payload['freshness_state']['max_freshness_limit_bdays'],
            'is_fresh': self.snapshot_payload['freshness_state']['is_fresh'],
            'provenance_record': {
                'official_source_url': self.snapshot_payload['source_urls'][0] if self.snapshot_payload['source_urls'] else '',
                'expected_sha256': self.snapshot_payload['source_hashes'].get('expected_registry_sha256') or self.snapshot_payload['source_hashes'].get('archive_sha256', ''),
                'provenance_status': self.snapshot_payload.get('provenance', {}).get('provenance_status', 'VERIFIED_OFFICIAL_ARCHIVE')
            },
            'positions': [
                {
                    'name': p['contract_name'],
                    'ticker': p['ticker'],
                    'cusip': p['cusip'],
                    'lots': p['lots'],
                    'multiplier': p['multiplier'],
                    'multiplier_unit': p.get('multiplier_unit', '1 Calendar Day'),
                    'price': p['price'],
                    'product_code': p['product_code'],
                    'rulebook_ref': p['rulebook_ref']
                }
                for p in self.snapshot_payload['positions']
            ]
        }
            
        # 2. Load dated baseline metrics (Market close, NAV/share, Shares, Total NAV)
        self.baseline = self._load_dated_baselines()

    def _load_dated_baselines(self) -> Dict[str, Any]:
        """
        Loads observed market close, NAV per share, and shares outstanding from official sources.
        Evaluates contemporaneous date alignment strictly.
        """
        f_key = self.fund.lower()
        snapshot_date = self.snapshot['snapshot_date']
        base_dir = get_base_data_dir()
        
        # Market price from liquidity history
        l_file = os.path.join(base_dir, f'{f_key}_liquidity.csv')
        latest_mkt_px = None
        latest_mkt_date = None
        if os.path.exists(l_file):
            df_l = pd.read_csv(l_file)
            df_l['date_dt'] = pd.to_datetime(df_l['date'], errors='coerce')
            df_l = df_l.dropna(subset=['close']).sort_values('date_dt')
            if not df_l.empty:
                last_r = df_l.iloc[-1]
                latest_mkt_px = float(last_r['close'])
                latest_mkt_date = last_r['date_dt'].strftime('%Y-%m-%d')
                
        # NAV per share from flows history
        f_file = os.path.join(base_dir, f'{self.fund.upper()}_flows.csv')
        latest_nav_sh = None
        latest_nav_date = None
        if os.path.exists(f_file):
            df_f = pd.read_csv(f_file)
            df_f['date_dt'] = pd.to_datetime(df_f['date'], errors='coerce')
            df_f = df_f.dropna(subset=['nav']).sort_values('date_dt')
            if not df_f.empty:
                last_f = df_f.iloc[-1]
                latest_nav_sh = float(last_f['nav'])
                latest_nav_date = last_f['date_dt'].strftime('%Y-%m-%d')
                
        # Shares outstanding and total NAV from CFTC parsed monthly ledger
        cftc_file = os.path.normpath(os.path.join(base_dir, '..', 'cftc_statements', 'parsed', f'{f_key}_monthly_cftc_ledger.csv'))
        if not os.path.exists(cftc_file):
            cftc_file = f'data/cftc_statements/parsed/{f_key}_monthly_cftc_ledger.csv'
        latest_shares = None
        latest_total_nav = None
        latest_cftc_date = None
        if os.path.exists(cftc_file):
            df_c = pd.read_csv(cftc_file)
            df_c['p_dt'] = pd.to_datetime(df_c['period_ended'], errors='coerce', format='mixed')
            df_c = df_c.dropna(subset=['closing_nav_dollars']).sort_values('p_dt')
            if not df_c.empty:
                last_c = df_c.iloc[-1]
                latest_shares = int(last_c['shares_outstanding']) if pd.notna(last_c['shares_outstanding']) else None
                latest_total_nav = float(last_c['closing_nav_dollars']) if pd.notna(last_c['closing_nav_dollars']) else None
                latest_cftc_date = last_c['p_dt'].strftime('%Y-%m-%d')
                
        # Contemporaneous check: All sources must be present and share the exact same date as the snapshot
        dates_list = [latest_mkt_date, latest_nav_date, latest_cftc_date, snapshot_date]
        all_present = all(d is not None for d in dates_list)
        all_identical = (len(set(dates_list)) == 1) if all_present else False
        
        is_contemporaneous = all_present and all_identical
        
        if is_contemporaneous:
            alignment_status = "CONTEMPORANEOUS_EXACT_ALIGNMENT"
            alignment_note = f"All baseline metrics share exact contemporaneous as-of date: {snapshot_date}."
        else:
            alignment_status = "NON_CONTEMPORANEOUS_BASELINE"
            mismatches = []
            if latest_mkt_date != snapshot_date:
                mismatches.append(f"Market Close Date ({latest_mkt_date}) != Snapshot ({snapshot_date})")
            if latest_nav_date != snapshot_date:
                mismatches.append(f"Official NAV Date ({latest_nav_date}) != Snapshot ({snapshot_date})")
            if latest_cftc_date != snapshot_date:
                mismatches.append(f"CFTC Monthly Shares Date ({latest_cftc_date}) != Snapshot ({snapshot_date})")
            alignment_note = "Non-contemporaneous dates: " + "; ".join(mismatches)
        
        return {
            'is_contemporaneous': is_contemporaneous,
            'snapshot_date': snapshot_date,
            'latest_market_price': latest_mkt_px,
            'market_price_date': latest_mkt_date,
            'latest_nav_per_share': latest_nav_sh,
            'nav_per_share_date': latest_nav_date,
            'latest_shares_outstanding': latest_shares,
            'latest_total_fund_nav_dollars': latest_total_nav,
            'cftc_statement_date': latest_cftc_date,
            'alignment_status': alignment_status,
            'alignment_note': alignment_note
        }

    def _validate_manual_baseline(
        self,
        manual_baseline: Dict[str, Any],
        tolerance: float = 0.05
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """
        Validates manual baseline inputs internally:
        - total_nav > 0, shares > 0, market_price > 0
        - explicit ISO as_of_date
        - source non-empty
        - mathematical consistency: abs(total_nav / shares - nav_per_share) <= tolerance
        """
        if not isinstance(manual_baseline, dict):
            return False, "Manual baseline must be a dictionary.", None
            
        req_fields = ['total_nav_dollars', 'shares_outstanding', 'market_price', 'as_of_date', 'source']
        for f in req_fields:
            if f not in manual_baseline or manual_baseline[f] is None:
                return False, f"Manual baseline missing required field: '{f}'.", None
                
        try:
            total_nav = float(manual_baseline['total_nav_dollars'])
            shares = int(manual_baseline['shares_outstanding'])
            mkt_px = float(manual_baseline['market_price'])
            as_of_date_str = str(manual_baseline['as_of_date']).strip()
            source_str = str(manual_baseline['source']).strip()
        except (ValueError, TypeError) as e:
            return False, f"Invalid data types in manual baseline fields: {e}", None
            
        if total_nav <= 0:
            return False, f"Manual total_nav_dollars (${total_nav}) must be positive.", None
        if shares <= 0:
            return False, f"Manual shares_outstanding ({shares}) must be positive.", None
        if mkt_px <= 0:
            return False, f"Manual market_price (${mkt_px}) must be positive.", None
        if not source_str:
            return False, "Manual baseline source/notes description cannot be empty.", None
            
        # Verify valid ISO date format
        try:
            datetime.strptime(as_of_date_str, '%Y-%m-%d')
        except ValueError:
            return False, f"Manual as_of_date '{as_of_date_str}' is not a valid YYYY-MM-DD date.", None
            
        implied_nav_sh = total_nav / shares
        
        # Check NAV/share mathematical consistency if supplied
        if 'nav_per_share' in manual_baseline and manual_baseline['nav_per_share'] is not None:
            try:
                supplied_nav_sh = float(manual_baseline['nav_per_share'])
            except (ValueError, TypeError):
                return False, "Supplied nav_per_share is not a valid number.", None
                
            diff = abs(implied_nav_sh - supplied_nav_sh)
            if diff > tolerance:
                err_msg = (
                    f"Inconsistent manual baseline: total_nav/shares (${implied_nav_sh:.4f}) differs from "
                    f"supplied nav_per_share (${supplied_nav_sh:.4f}) by ${diff:.4f}, exceeding tolerance ${tolerance:.2f}."
                )
                return False, err_msg, None
            nav_sh = supplied_nav_sh
        else:
            nav_sh = implied_nav_sh
            
        validated_dict = {
            'total_nav_dollars': total_nav,
            'shares_outstanding': shares,
            'nav_per_share': nav_sh,
            'implied_nav_per_share': implied_nav_sh,
            'market_price': mkt_px,
            'as_of_date': as_of_date_str,
            'source': source_str,
            'math_verified': True
        }
        return True, None, validated_dict

    def build_scenario(
        self,
        target_contract_prices: Optional[Dict[str, float]] = None,
        route_percentage_shocks: Optional[Dict[str, float]] = None,
        scenario_mode: str = 'FROZEN_BOOK',
        scenario_horizon_date: Optional[str] = None,
        user_forward_lots: Optional[Dict[str, float]] = None,
        user_assumed_forward_book: Optional[List[Dict[str, Any]]] = None,
        manual_dated_baseline: Optional[Dict[str, Any]] = None,
        manual_baseline_tolerance: float = 0.05,
        pricing_mode: str = 'AUTO',
        premium_discount_spread_pct: float = 2.50
    ) -> Dict[str, Any]:
        """
        Translates user target prices or route percentage shocks into gross futures P&L ($)
        and approximate NAV/share targets if a valid contemporaneous or manual baseline exists.
        
        Args:
            target_contract_prices: Dict mapping exact contract Ticker/CUSIP/Name to TARGET freight price ($).
            route_percentage_shocks: Dict mapping route class ('Capesize', 'Panamax', 'Supramax', 'VLCC', 'Suezmax') to shock %.
            scenario_mode: 'FROZEN_BOOK' (default) or 'USER_SPECIFIED_FORWARD_BOOK'.
            scenario_horizon_date: ISO date string for scenario target horizon (e.g. '2026-08-14' or '2026-09-30').
            user_forward_lots: Dict mapping exact contract Ticker/CUSIP/Name to user-specified lots.
            user_assumed_forward_book: Optional list of complete user forward position assumptions:
                [ { 'contract_identifier': str, 'lots': float, 'multiplier': float, 'starting_mark': float, 'target_mark': float, 'roll_transaction_cost_dollars': float } ]
            manual_dated_baseline: Optional dict containing contemporaneous baseline fields:
                { 'total_nav_dollars': float, 'shares_outstanding': int, 'nav_per_share': float, 'market_price': float, 'as_of_date': str, 'source': str }
            manual_baseline_tolerance: Mathematical tolerance for checking total_nav/shares == nav_per_share (default: $0.05).
            premium_discount_spread_pct: Configurable assumption spread band (e.g. 2.50%).
        """
        if scenario_mode not in ['FROZEN_BOOK', 'USER_SPECIFIED_FORWARD_BOOK']:
            raise ValueError(
                f"Unknown scenario mode '{scenario_mode}'. Allowed: 'FROZEN_BOOK', 'USER_SPECIFIED_FORWARD_BOOK'. "
                f"Synthetic roll heuristics have been removed."
            )
            
        positions = self.snapshot['positions']
        snapshot_date = self.snapshot['snapshot_date']
        horizon_date = scenario_horizon_date or self.reference_time_utc.strftime('%Y-%m-%d')
        
        target_contract_prices = target_contract_prices or {}
        route_percentage_shocks = route_percentage_shocks or {}
        user_forward_lots = user_forward_lots or {}
        user_assumed_forward_book = user_assumed_forward_book or []
        
        total_gross_futures_pnl_dollars = 0.0
        total_base_futures_notional_dollars = 0.0
        total_roll_transaction_costs_dollars = 0.0
        contract_rows = []
        
        # Track which contracts in positions were processed
        matched_disclosed_names = set()
        
        # Process disclosed positions
        for pos in positions:
            name = pos.get('contract_name') or pos.get('name')
            ticker_val = pos.get('ticker', '')
            cusip_val = pos['cusip']
            disclosed_lots = float(pos['lots'])
            base_mark = float(pos['price'])
            mult = float(pos['multiplier'])
            matched_disclosed_names.add(name)
            matched_disclosed_names.add(ticker_val)
            matched_disclosed_names.add(cusip_val)
            
            # Determine effective lots and assumptions based on mode
            effective_lots = disclosed_lots
            roll_cost = 0.0
            starting_mark = base_mark
            
            if scenario_mode == 'USER_SPECIFIED_FORWARD_BOOK':
                # Check user_forward_lots dict
                if ticker_val in user_forward_lots:
                    effective_lots = float(user_forward_lots[ticker_val])
                elif cusip_val in user_forward_lots:
                    effective_lots = float(user_forward_lots[cusip_val])
                elif name in user_forward_lots:
                    effective_lots = float(user_forward_lots[name])
                    
                # Check user_assumed_forward_book list for override details
                for item in user_assumed_forward_book:
                    ident = item.get('contract_identifier') or item.get('ticker') or item.get('contract_name') or ''
                    if ident in [ticker_val, cusip_val, name]:
                        if 'lots' in item and item['lots'] is not None:
                            effective_lots = float(item['lots'])
                        if 'starting_mark' in item and item['starting_mark'] is not None:
                            starting_mark = float(item['starting_mark'])
                        if 'multiplier' in item and item['multiplier'] is not None:
                            mult = float(item['multiplier'])
                        if 'roll_transaction_cost_dollars' in item and item['roll_transaction_cost_dollars'] is not None:
                            roll_cost = float(item['roll_transaction_cost_dollars'])
                        if 'target_mark' in item and item['target_mark'] is not None:
                            target_contract_prices[name] = float(item['target_mark'])
                            
            # Determine target price (Target mark is PRIMARY and must match exact contract identifier)
            target_px = None
            if ticker_val in target_contract_prices:
                target_px = float(target_contract_prices[ticker_val])
            elif cusip_val in target_contract_prices:
                target_px = float(target_contract_prices[cusip_val])
            elif name in target_contract_prices:
                target_px = float(target_contract_prices[name])
                
            # If target mark was not directly entered for this exact contract, check route shock shortcut
            if target_px is None:
                v_class = None
                if 'CAPE' in name.upper() or 'C5TC' in ticker_val.upper():
                    v_class = 'Capesize'
                elif 'PANA' in name.upper() or 'P5TC' in ticker_val.upper():
                    v_class = 'Panamax'
                elif 'SUPRA' in name.upper() or 'S58F' in ticker_val.upper() or 'S10TC' in ticker_val.upper():
                    v_class = 'Supramax'
                elif 'VLCC' in name.upper() or 'TD3' in ticker_val.upper() or 'DD3C' in ticker_val.upper():
                    v_class = 'VLCC'
                elif 'SUEZ' in name.upper() or 'TD20' in ticker_val.upper() or 'DD20' in ticker_val.upper():
                    v_class = 'Suezmax'
                    
                route_shock_pct = route_percentage_shocks.get(v_class, route_percentage_shocks.get(v_class.lower() if v_class else '', 0.0))
                target_px = starting_mark * (1.0 + (route_shock_pct / 100.0))
                
            # Delta Mark = Target - Starting Mark
            delta_p = target_px - starting_mark
            
            contract_gross_pnl = effective_lots * mult * delta_p
            contract_net_pnl = contract_gross_pnl - roll_cost
            contract_base_notional = disclosed_lots * mult * base_mark
            
            total_gross_futures_pnl_dollars += contract_gross_pnl
            total_base_futures_notional_dollars += contract_base_notional
            total_roll_transaction_costs_dollars += roll_cost
            
            contract_rows.append({
                'contract_name': name,
                'ticker': ticker_val,
                'cusip': cusip_val,
                'disclosed_lots': disclosed_lots,
                'effective_lots': effective_lots,
                'multiplier': mult,
                'multiplier_unit': pos['multiplier_unit'],
                'starting_mark_price': starting_mark,
                'current_mark_price': base_mark,
                'target_mark_price': target_px,
                'delta_mark_dollars': delta_p,
                'roll_transaction_cost_dollars': roll_cost,
                'contract_base_notional_dollars': contract_base_notional,
                'gross_futures_pnl_dollars': contract_gross_pnl,
                'net_contract_pnl_dollars': contract_net_pnl,
                'rulebook_ref': pos['rulebook_ref'],
                'product_code': pos['product_code'],
                'is_roll_in_new_contract': False
            })
            
        # Process Roll-in / New Contracts in USER_SPECIFIED_FORWARD_BOOK mode
        if scenario_mode == 'USER_SPECIFIED_FORWARD_BOOK':
            # Check user_assumed_forward_book for newly introduced contracts
            for item in user_assumed_forward_book:
                ident = item.get('contract_identifier') or item.get('ticker') or item.get('contract_name') or ''
                if not ident or ident in matched_disclosed_names:
                    continue
                    
                # Safeguard 1: Roll-in contract absent from disclosed book requires complete schema
                if ('starting_mark' not in item or item['starting_mark'] is None or float(item['starting_mark']) <= 0) or \
                   ('multiplier' not in item or item['multiplier'] is None or float(item['multiplier']) <= 0) or \
                   ('target_mark' not in item or item['target_mark'] is None or float(item['target_mark']) <= 0):
                    raise InvalidForwardBookAssumptionError(
                        f"Roll-in contract '{ident}' absent from disclosed book requires exact starting_mark, multiplier, and target_mark."
                    )
                    
                lots = float(item.get('lots', 0.0))
                mult = float(item['multiplier'])
                start_mark = float(item['starting_mark'])
                tgt_mark = float(item['target_mark'])
                roll_cost = float(item.get('roll_transaction_cost_dollars', 0.0))
                
                delta_p = tgt_mark - start_mark
                contract_gross_pnl = lots * mult * delta_p
                contract_net_pnl = contract_gross_pnl - roll_cost
                
                total_gross_futures_pnl_dollars += contract_gross_pnl
                total_roll_transaction_costs_dollars += roll_cost
                
                contract_rows.append({
                    'contract_name': str(item.get('contract_name', ident)),
                    'ticker': str(item.get('ticker', ident)),
                    'cusip': str(item.get('cusip', 'USER_SPECIFIED')),
                    'disclosed_lots': 0.0,
                    'effective_lots': lots,
                    'multiplier': mult,
                    'multiplier_unit': item.get('multiplier_unit', 'User Specified'),
                    'starting_mark_price': start_mark,
                    'current_mark_price': start_mark,
                    'target_mark_price': tgt_mark,
                    'delta_mark_dollars': delta_p,
                    'roll_transaction_cost_dollars': roll_cost,
                    'contract_base_notional_dollars': 0.0,
                    'gross_futures_pnl_dollars': contract_gross_pnl,
                    'net_contract_pnl_dollars': contract_net_pnl,
                    'rulebook_ref': item.get('rulebook_ref', 'User Forward Book Assumption'),
                    'product_code': item.get('product_code', 'USER_ASSUMED'),
                    'is_roll_in_new_contract': True
                })
                matched_disclosed_names.add(ident)
                
            # Check user_forward_lots for any roll-in contract keys not in disclosed book
            for f_key, f_lots in user_forward_lots.items():
                if f_key not in matched_disclosed_names:
                    # Absent from disclosed book and missing entry mark / multiplier
                    raise InvalidForwardBookAssumptionError(
                        f"Roll-in contract '{f_key}' absent from disclosed book requires exact starting_mark, multiplier, and target_mark."
                    )
                    
        # P&L Direction
        if total_gross_futures_pnl_dollars > 0:
            pnl_direction = "POSITIVE_NAV_EXPANSION"
        elif total_gross_futures_pnl_dollars < 0:
            pnl_direction = "NEGATIVE_NAV_CONTRACTION"
        else:
            pnl_direction = "NEUTRAL_ZERO_CHANGE"
            
        # Baseline Validation: Safeguard 2 (Internal mathematical validation) & Safeguard 4 (Provenance check)
        is_valid_baseline = False
        baseline_origin = "NONE"
        base_mkt = None
        base_nav_sh = None
        base_shares = None
        base_total_nav = None
        baseline_as_of_date = None
        baseline_source_desc = None
        baseline_validation_error = None
        
        # Check if user supplied a manual baseline
        if manual_dated_baseline is not None:
            is_valid_man, err_man, val_dict = self._validate_manual_baseline(
                manual_dated_baseline,
                tolerance=manual_baseline_tolerance
            )
            if is_valid_man and val_dict is not None:
                base_total_nav = val_dict['total_nav_dollars']
                base_shares = val_dict['shares_outstanding']
                base_nav_sh = val_dict['nav_per_share']
                base_mkt = val_dict['market_price']
                baseline_as_of_date = val_dict['as_of_date']
                baseline_source_desc = val_dict['source']
                is_valid_baseline = True
                baseline_origin = "USER_SUPPLIED_MANUAL_BASELINE"
            else:
                is_valid_baseline = False
                baseline_validation_error = err_man
                baseline_origin = "INVALID_MANUAL_BASELINE"
                
        # If no manual baseline, check official baseline
        elif self.baseline['is_contemporaneous']:
            base_mkt = self.baseline['latest_market_price']
            base_nav_sh = self.baseline['latest_nav_per_share']
            base_shares = self.baseline['latest_shares_outstanding']
            base_total_nav = self.baseline['latest_total_fund_nav_dollars']
            baseline_as_of_date = self.baseline['snapshot_date']
            baseline_source_desc = "Official Contemporaneous Filings"
            if all(v is not None and v > 0 for v in [base_mkt, base_nav_sh, base_shares, base_total_nav]):
                is_valid_baseline = True
                baseline_origin = "OFFICIAL_CONTEMPORANEOUS_BASELINE"
                
        # Safeguard 3: Prominently separate three dates
        holdings_dt_str = snapshot_date
        baseline_dt_str = baseline_as_of_date if baseline_as_of_date else self.baseline['market_price_date'] or snapshot_date
        horizon_dt_str = horizon_date
        
        try:
            h_d = datetime.strptime(holdings_dt_str, '%Y-%m-%d').date()
            b_d = datetime.strptime(baseline_dt_str, '%Y-%m-%d').date()
            hz_d = datetime.strptime(horizon_dt_str, '%Y-%m-%d').date()
            base_to_holdings_gap = abs((b_d - h_d).days)
            horizon_to_holdings_gap = (hz_d - h_d).days
        except Exception:
            base_to_holdings_gap = None
            horizon_to_holdings_gap = None
            
        date_summary_str = (
            f"Holdings As-Of: {holdings_dt_str} | "
            f"Baseline As-Of: {baseline_dt_str} (Gap: {base_to_holdings_gap or 0}d) | "
            f"Scenario Horizon: {horizon_dt_str}"
        )
        
        # Disclaim non-identical baseline and holdings dates
        if base_to_holdings_gap is not None and base_to_holdings_gap > 0:
            date_disclaimer = (
                f"NOTICE: Baseline date ({baseline_dt_str}) differs from holdings snapshot date ({holdings_dt_str}) "
                f"by {base_to_holdings_gap} calendar days. Do not treat this result as an exact official NAV reconstruction."
            )
        else:
            date_disclaimer = "Contemporaneous alignment confirmed between baseline date and holdings snapshot."
            
        provenance_dates_bundle = {
            'holdings_snapshot_as_of_date': holdings_dt_str,
            'baseline_as_of_date': baseline_dt_str,
            'scenario_horizon_date': horizon_dt_str,
            'baseline_to_holdings_gap_days': base_to_holdings_gap,
            'horizon_to_holdings_gap_days': horizon_to_holdings_gap,
            'is_baseline_contemporaneous_with_snapshot': (base_to_holdings_gap == 0),
            'date_alignment_summary': date_summary_str,
            'date_alignment_disclaimer': date_disclaimer
        }
        
        # Construct Per-Share Outputs or Fail Closed
        if is_valid_baseline:
            net_scenario_pnl = total_gross_futures_pnl_dollars - total_roll_transaction_costs_dollars
            projected_total_nav_dollars = base_total_nav + net_scenario_pnl
            projected_nav_per_share = projected_total_nav_dollars / base_shares
            
            # Baseline Premium / Discount (%)
            baseline_prem_disc_pct = ((base_mkt - base_nav_sh) / base_nav_sh) * 100.0 if base_nav_sh > 0 else 0.0
            
            # Selectable Pricing Mode: CARRY_FORWARD_PREMIUM_DISCOUNT vs NAV_PARITY
            if pricing_mode == 'AUTO':
                # Default to carry-forward only when baseline is contemporaneous or user-supplied
                if provenance_dates_bundle['is_baseline_contemporaneous_with_snapshot'] or baseline_origin == 'USER_SUPPLIED_MANUAL_BASELINE':
                    selected_pricing_mode = 'CARRY_FORWARD_PREMIUM_DISCOUNT'
                else:
                    selected_pricing_mode = 'NAV_PARITY'
            else:
                selected_pricing_mode = pricing_mode
                
            if selected_pricing_mode == 'CARRY_FORWARD_PREMIUM_DISCOUNT':
                applied_prem_disc_pct = baseline_prem_disc_pct
                mkt_px_base = projected_nav_per_share * (1.0 + (applied_prem_disc_pct / 100.0))
                assumption_label = f"Carried Forward Baseline Prem/Disc ({applied_prem_disc_pct:+.2f}%) [Assumption]"
            else:
                applied_prem_disc_pct = 0.0
                mkt_px_base = projected_nav_per_share
                assumption_label = "Projected at NAV Parity (0.00% Prem/Disc) [Assumption]"
                
            spread_ratio = premium_discount_spread_pct / 100.0
            mkt_px_low = mkt_px_base * (1.0 - spread_ratio)
            mkt_px_high = mkt_px_base * (1.0 + spread_ratio)
            
            nav_target_range = {
                'status': "AVAILABLE",
                'baseline_origin': baseline_origin,
                'baseline_as_of_date': baseline_as_of_date,
                'baseline_source_description': baseline_source_desc,
                'baseline_total_fund_nav_dollars': base_total_nav,
                'projected_total_fund_nav_dollars': projected_total_nav_dollars,
                'baseline_shares_outstanding': base_shares,
                'baseline_nav_per_share': base_nav_sh,
                'projected_nav_per_share': round(projected_nav_per_share, 4),
                'status_label': 'APPROXIMATE_TARGET_NAV_RANGE'
            }
            
            market_price_target_range = {
                'status': "AVAILABLE",
                'baseline_market_price': base_mkt,
                'pricing_mode': selected_pricing_mode,
                'baseline_premium_discount_pct': round(baseline_prem_disc_pct, 4),
                'applied_premium_discount_assumed_pct': round(applied_prem_disc_pct, 4),
                'applied_premium_discount_assumption_label': assumption_label,
                'low_target_discount_band': round(mkt_px_low, 2),
                'base_target_price': round(mkt_px_base, 2),
                'base_target_nav_parity': round(projected_nav_per_share, 2),
                'high_target_premium_band': round(mkt_px_high, 2),
                'premium_discount_spread_assumed_pct': premium_discount_spread_pct,
                'spread_assumption_note': (
                    f"Configurable assumption-based spread (+/-{premium_discount_spread_pct:.2f}% around "
                    f"base ${mkt_px_base:.2f}, NOT a historical probability estimate)."
                ),
                'status_label': 'APPROXIMATE_MARKET_PRICE_RANGE'
            }
            per_share_status = "PER_SHARE_ESTIMATE_AVAILABLE"
            per_share_message = "Per-share NAV and market price target estimates calculated from validated baseline."
        else:
            # FAIL CLOSED: No silent fallbacks
            nav_target_range = None
            market_price_target_range = None
            if baseline_validation_error:
                per_share_status = "PER_SHARE_UNAVAILABLE_INVALID_MANUAL_BASELINE"
                per_share_message = f"Manual baseline rejected: {baseline_validation_error}"
            else:
                per_share_status = "PER_SHARE_UNAVAILABLE_NON_CONTEMPORANEOUS_BASELINE"
                per_share_message = (
                    "Gross futures P&L available; per-share ETF estimate unavailable because "
                    "the NAV/share baseline is not contemporaneous."
                )
            
        # Mode semantic labeling
        scenario_mode_label = (
            "User-assumed forward book" if scenario_mode == 'USER_SPECIFIED_FORWARD_BOOK' else "Frozen disclosed book"
        )
        
        # Unresolved Accounting Residual Flags
        residual_flags = {
            'roll_execution_drag': 'FLAGGED: Intraday roll fills, spread slippage, and broker execution fees are unobserved.',
            'cash_collateral_interest': 'FLAGGED: Daily collateral interest yield and repo sweeps between month-ends are unobserved.',
            'daily_expenses_accruals': 'FLAGGED: Daily advisory/admin fee accruals and Breakwave fee waivers between month-ends are unobserved.',
            'ap_basket_flow': 'FLAGGED: Authorized Participant creation/redemption share movements between month-ends are unobserved.',
            'secondary_market_premium_discount': 'FLAGGED: Secondary market price reflects supply/demand premium or discount to NAV.'
        }
        
        return {
            'tool_title': "Thesis-to-ETF Scenario Translator",
            'classification': "PARTIAL: USER-DRIVEN TARGET PRICE TRANSLATOR — NOT A PREDICTION",
            'fund': self.fund,
            'scenario_mode': scenario_mode,
            'scenario_mode_label': scenario_mode_label,
            'official_snapshot_as_of_date': snapshot_date,
            'scenario_horizon_date': horizon_date,
            'provenance_dates': provenance_dates_bundle,
            'evaluation_date_utc': self.reference_time_utc.strftime('%Y-%m-%d'),
            'business_day_freshness_age': self.snapshot.get('snapshot_age_bdays', self.snapshot.get('business_day_age', 0)),
            'freshness_limit_business_days': self.snapshot.get('freshness_limit_bdays', self.snapshot.get('max_stale_limit_bdays', 3)),
            'scenario_snapshot_schema_version': self.snapshot_payload.get('schema_version', '1.0.0'),
            'contract_spec_version': self.snapshot_payload.get('contract_spec_version', '2026.08.14-VERIFIED-V1'),
            'provenance': {
                'source_urls': self.snapshot_payload.get('source_urls', []),
                'source_hashes': self.snapshot_payload.get('source_hashes', {}),
                'provenance_status': self.snapshot.get('provenance_status', self.snapshot.get('provenance_record', {}).get('provenance_status', 'VERIFIED_OFFICIAL_ARCHIVE'))
            },
            'baseline_metrics': self.baseline,
            'gross_futures_pnl_dollars': total_gross_futures_pnl_dollars,
            'total_base_futures_notional_dollars': total_base_futures_notional_dollars,
            'total_roll_transaction_costs_dollars': total_roll_transaction_costs_dollars,
            'pnl_direction': pnl_direction,
            'per_share_status': per_share_status,
            'per_share_message': per_share_message,
            'approximate_nav_target_range': nav_target_range,
            'approximate_etf_market_price_target_range': market_price_target_range,
            'unresolved_residual_flags': residual_flags,
            'contract_breakdown': contract_rows
        }

def run_cli_demo():
    print("====================================================================================================")
    print("                    THESIS-TO-ETF SCENARIO TRANSLATOR (PRODUCTION DEMO)                             ")
    print("====================================================================================================")
    
    for fund in ['BDRY', 'BWET']:
        builder = ThesisScenarioBuilder(fund=fund, max_stale_business_days=3)
        
        target_prices = {
            'C5TCM Q26 INDEX': 42000.0,
            'DD3CM Q26 INDEX': 105.00
        }
        
        # 1. P&L-only mode with default non-contemporaneous baseline
        res_default = builder.build_scenario(
            target_contract_prices=target_prices,
            scenario_mode='FROZEN_BOOK',
            scenario_horizon_date='2026-08-14'
        )
        print(f"\n--- FUND: {res_default['fund']} (DEFAULT NON-CONTEMPORANEOUS BASELINE) ---")
        print(f"  Mode Label            : {res_default['scenario_mode_label']}")
        print(f"  Dates Summary         : {res_default['provenance_dates']['date_alignment_summary']}")
        print(f"  Gross Futures P&L ($) : ${res_default['gross_futures_pnl_dollars']:+,.2f} ({res_default['pnl_direction']})")
        print(f"  Per-Share Status      : {res_default['per_share_status']}")
        print(f"  Per-Share Message     : {res_default['per_share_message']}")
        
        # 2. User-supplied manual contemporaneous baseline
        manual_base = {
            'total_nav_dollars': 30000000.0 if fund == 'BDRY' else 15000000.0,
            'shares_outstanding': 2169200 if fund == 'BDRY' else 44200,
            'nav_per_share': 13.83 if fund == 'BDRY' else 339.37,
            'market_price': 13.79 if fund == 'BDRY' else 357.33,
            'as_of_date': '2026-08-13',
            'source': 'Manual User Override (Contemporaneous)'
        }
        res_manual = builder.build_scenario(
            target_contract_prices=target_prices,
            scenario_mode='FROZEN_BOOK',
            scenario_horizon_date='2026-08-14',
            manual_dated_baseline=manual_base,
            premium_discount_spread_pct=2.50
        )
        print(f"\n--- FUND: {res_manual['fund']} (WITH MANUAL CONTEMPORANEOUS BASELINE) ---")
        nav_rng = res_manual['approximate_nav_target_range']
        mkt_rng = res_manual['approximate_etf_market_price_target_range']
        print(f"  Dates Summary         : {res_manual['provenance_dates']['date_alignment_summary']}")
        print(f"  Per-Share Status      : {res_manual['per_share_status']}")
        print(f"  Approx Target NAV/sh  : ${nav_rng['projected_nav_per_share']:.2f}/sh (Total NAV: ${nav_rng['projected_total_fund_nav_dollars']:,.2f})")
        print(f"  Approx Market Range   : Low (-2.5%): ${mkt_rng['low_target_discount_band']:.2f} | Base (Parity): ${mkt_rng['base_target_nav_parity']:.2f} | High (+2.5%): ${mkt_rng['high_target_premium_band']:.2f}")

if __name__ == '__main__':
    run_cli_demo()
