"""
Decision-Ticket Workflow Engine for BDRY & BWET
================================================
Authoritative institutional decision-ticket engine translating freight market theses,
exact contract target marks, percentage shocks, forward roll assumptions, and contemporaneous
baselines into a structured, verifiable Decision Ticket.

INPUTS:
- Current verified ETF book (official verified snapshot & archive SHA-256)
- Exact target marks ($/day or $/MT) or % shocks by contract
- Scenario evaluation horizon (date or days)
- Optional user-specified forward/roll book (USER_SPECIFIED_FORWARD_BOOK schema)
- Optional manual contemporaneous NAV, shares, and market price baseline

OUTPUTS:
- Gross futures P&L by contract and aggregated by vessel route class
- Fund NAV change in dollars and percent
- Per-share NAV impact strictly gated on a valid denominator (shares > 0) and contemporaneous baseline
- Secondary market price range across 4 distinct regimes: Unchanged, Normal (+/-2%), Stressed (+/-5%), and NAV Parity
- Comprehensive disclosures: roll drag, collateral yield, management fee, and data-confidence rating
- Strict "Known Current Book vs. User-Assumed Future Book" structural separation
"""

import os
import json
import hashlib
from datetime import datetime, timezone, date, timedelta
from typing import Dict, Any, List, Optional, Tuple, Union

from contract_spec_registry import resolve_contract_spec, get_authoritative_multiplier
from current_book_manual_shock import load_latest_official_snapshot, StaleSnapshotError, MissingProvenanceRecordError
from scenario_snapshot_schema import validate_scenario_snapshot, load_published_scenario_snapshot
from thesis_scenario_builder import ThesisScenarioBuilder, InvalidForwardBookAssumptionError, InconsistentManualBaselineError


def generate_decision_ticket(
    fund: str = 'BDRY',
    target_contract_prices: Optional[Dict[str, float]] = None,
    route_percentage_shocks: Optional[Dict[str, float]] = None,
    contract_percentage_shocks: Optional[Dict[str, float]] = None,
    scenario_horizon_date: Optional[str] = None,
    horizon_days: Optional[int] = None,
    scenario_mode: str = 'FROZEN_BOOK',
    user_assumed_forward_book: Optional[List[Dict[str, Any]]] = None,
    user_forward_lots: Optional[Dict[str, float]] = None,
    manual_dated_baseline: Optional[Dict[str, Any]] = None,
    manual_baseline_tolerance: float = 0.05,
    pricing_mode: str = 'AUTO',
    normal_spread_pct: float = 2.00,
    stressed_spread_pct: float = 5.00,
    reference_time_utc: Optional[datetime] = None,
    max_stale_business_days: int = 3
) -> Dict[str, Any]:
    """
    Generates an authoritative, complete Decision Ticket structure for BDRY or BWET.
    """
    ref_time = reference_time_utc or datetime.now(timezone.utc)
    eval_date_str = ref_time.strftime('%Y-%m-%d')
    fund_code = fund.upper()
    
    if fund_code not in ['BDRY', 'BWET']:
        raise ValueError(f"Unknown fund '{fund}'. Must be 'BDRY' or 'BWET'.")
        
    # 1. Initialize underlying verified thesis scenario engine
    builder = ThesisScenarioBuilder(
        fund=fund_code,
        max_stale_business_days=max_stale_business_days,
        reference_time_utc=ref_time
    )
    
    # 2. Resolve horizon date if horizon_days is given
    target_horizon_date = scenario_horizon_date
    if not target_horizon_date and horizon_days is not None:
        target_horizon_date = (ref_time + timedelta(days=horizon_days)).strftime('%Y-%m-%d')
    if not target_horizon_date:
        target_horizon_date = eval_date_str
        
    # 3. Merge contract percentage shocks into target contract prices if supplied
    merged_target_prices = dict(target_contract_prices or {})
    if contract_percentage_shocks:
        for pos in builder.snapshot['positions']:
            ident_candidates = [
                pos.get('contract_name'),
                pos.get('name'),
                pos.get('ticker'),
                pos.get('cusip')
            ]
            for cand in ident_candidates:
                if cand and cand in contract_percentage_shocks and cand not in merged_target_prices:
                    pct = float(contract_percentage_shocks[cand])
                    base_mark = float(pos['price'])
                    merged_target_prices[cand] = base_mark * (1.0 + (pct / 100.0))
                    
    # 4. Run underlying verified scenario builder
    scenario_res = builder.build_scenario(
        target_contract_prices=merged_target_prices,
        route_percentage_shocks=route_percentage_shocks,
        scenario_mode=scenario_mode,
        scenario_horizon_date=target_horizon_date,
        user_forward_lots=user_forward_lots,
        user_assumed_forward_book=user_assumed_forward_book,
        manual_dated_baseline=manual_dated_baseline,
        manual_baseline_tolerance=manual_baseline_tolerance,
        pricing_mode=pricing_mode,
        premium_discount_spread_pct=normal_spread_pct
    )
    
    # 5. Route-Level Attribution Aggregation
    route_groups = {
        'Capesize': {'name': 'Capesize 5TC', 'pnl': 0.0, 'notional': 0.0, 'roll_cost': 0.0, 'contracts': []},
        'Panamax': {'name': 'Panamax 5TC', 'pnl': 0.0, 'notional': 0.0, 'roll_cost': 0.0, 'contracts': []},
        'Supramax': {'name': 'Supramax 58TC', 'pnl': 0.0, 'notional': 0.0, 'roll_cost': 0.0, 'contracts': []},
        'VLCC': {'name': 'VLCC TD3C (MEG-China)', 'pnl': 0.0, 'notional': 0.0, 'roll_cost': 0.0, 'contracts': []},
        'Suezmax': {'name': 'Suezmax TD20 (WAF-Cont)', 'pnl': 0.0, 'notional': 0.0, 'roll_cost': 0.0, 'contracts': []}
    }
    
    for row in scenario_res['contract_breakdown']:
        name_u = row['contract_name'].upper()
        ticker_u = row['ticker'].upper()
        
        r_key = None
        if 'CAPE' in name_u or 'C5TC' in ticker_u:
            r_key = 'Capesize'
        elif 'PANA' in name_u or 'P5TC' in ticker_u:
            r_key = 'Panamax'
        elif 'SUPRA' in name_u or 'S58F' in ticker_u or 'S10TC' in ticker_u:
            r_key = 'Supramax'
        elif 'VLCC' in name_u or 'TD3' in ticker_u or 'DD3C' in ticker_u:
            r_key = 'VLCC'
        elif 'SUEZ' in name_u or 'TD20' in ticker_u or 'DD20' in ticker_u:
            r_key = 'Suezmax'
            
        if r_key:
            route_groups[r_key]['pnl'] += row['gross_futures_pnl_dollars']
            route_groups[r_key]['notional'] += row['contract_base_notional_dollars']
            route_groups[r_key]['roll_cost'] += row['roll_transaction_cost_dollars']
            route_groups[r_key]['contracts'].append(row['contract_name'])

    # Filter active route classes for the given fund
    active_routes = {}
    expected_routes = ['Capesize', 'Panamax', 'Supramax'] if fund_code == 'BDRY' else ['VLCC', 'Suezmax']
    tot_base_notional = scenario_res['total_base_futures_notional_dollars']
    tot_gross_pnl = scenario_res['gross_futures_pnl_dollars']
    
    for r in expected_routes:
        info = route_groups[r]
        r_notional = info['notional']
        r_pnl = info['pnl']
        r_ret_pct = (r_pnl / r_notional * 100.0) if r_notional > 0 else 0.0
        r_pnl_contrib_pct = (r_pnl / tot_gross_pnl * 100.0) if tot_gross_pnl != 0 else 0.0
        active_routes[r] = {
            'route_class_name': info['name'],
            'gross_futures_pnl_dollars': round(r_pnl, 2),
            'base_notional_dollars': round(r_notional, 2),
            'return_on_notional_pct': round(r_ret_pct, 2),
            'contribution_to_total_pnl_pct': round(r_pnl_contrib_pct, 2),
            'contract_count': len(info['contracts']),
            'contracts': info['contracts']
        }
        
    # 6. Book Separation: Known Disclosed Book vs. User-Assumed Future Book
    known_disclosed_book = []
    user_assumed_future_book = []
    
    for pos in builder.snapshot['positions']:
        pos_name = pos.get('contract_name') or pos.get('name') or pos.get('ticker', '')
        known_disclosed_book.append({
            'contract_name': pos_name,
            'ticker': pos.get('ticker', ''),
            'cusip': pos.get('cusip', ''),
            'disclosed_lots': float(pos['lots']),
            'multiplier': float(pos['multiplier']),
            'multiplier_unit': pos.get('multiplier_unit', '1 Calendar Day'),
            'current_mark_price': float(pos['price']),
            'base_notional_dollars': round(float(pos['lots']) * float(pos['multiplier']) * float(pos['price']), 2),
            'rulebook_ref': pos.get('rulebook_ref', ''),
            'source_as_of_date': builder.snapshot['snapshot_date']
        })
        
    if scenario_mode == 'USER_SPECIFIED_FORWARD_BOOK':
        for row in scenario_res['contract_breakdown']:
            user_assumed_future_book.append({
                'contract_name': row['contract_name'],
                'ticker': row['ticker'],
                'cusip': row['cusip'],
                'effective_lots': row['effective_lots'],
                'disclosed_lots': row['disclosed_lots'],
                'lot_delta': row['effective_lots'] - row['disclosed_lots'],
                'starting_mark_price': row['starting_mark_price'],
                'target_mark_price': row['target_mark_price'],
                'delta_mark_dollars': row['delta_mark_dollars'],
                'multiplier': row['multiplier'],
                'multiplier_unit': row['multiplier_unit'],
                'roll_transaction_cost_dollars': row['roll_transaction_cost_dollars'],
                'gross_futures_pnl_dollars': round(row['gross_futures_pnl_dollars'], 2),
                'is_roll_in_new_contract': row['is_roll_in_new_contract'],
                'assumption_type': "NEW_ROLL_IN_LEG" if row['is_roll_in_new_contract'] else ("MODIFIED_LOTS" if row['effective_lots'] != row['disclosed_lots'] else "PRESERVED_DISCLOSED_LOTS")
            })
            
    # 7. Fund NAV & Per-Share Denominator Validation
    nav_rng = scenario_res['approximate_nav_target_range']
    mkt_rng = scenario_res['approximate_etf_market_price_target_range']
    is_per_share_valid = (nav_rng is not None and mkt_rng is not None)
    
    net_futures_pnl_dollars = scenario_res['gross_futures_pnl_dollars'] - scenario_res['total_roll_transaction_costs_dollars']
    
    if is_per_share_valid:
        base_nav_dollars = nav_rng['baseline_total_fund_nav_dollars']
        proj_nav_dollars = nav_rng['projected_total_fund_nav_dollars']
        nav_change_pct = ((proj_nav_dollars - base_nav_dollars) / base_nav_dollars) * 100.0 if base_nav_dollars > 0 else 0.0
        
        shares = nav_rng['baseline_shares_outstanding']
        base_nav_sh = nav_rng['baseline_nav_per_share']
        proj_nav_sh = nav_rng['projected_nav_per_share']
        per_share_nav_delta = proj_nav_sh - base_nav_sh
        per_share_return_pct = (per_share_nav_delta / base_nav_sh) * 100.0 if base_nav_sh > 0 else 0.0
        
        nav_impact_section = {
            'status': "AVAILABLE",
            'dollar_nav_change': round(net_futures_pnl_dollars, 2),
            'percent_nav_change': round(nav_change_pct, 4),
            'baseline_total_fund_nav_dollars': base_nav_dollars,
            'projected_total_fund_nav_dollars': proj_nav_dollars,
            'baseline_as_of_date': nav_rng['baseline_as_of_date'],
            'baseline_source': nav_rng['baseline_source_description']
        }
        
        per_share_section = {
            'status': "PER_SHARE_ESTIMATE_AVAILABLE",
            'is_denominator_valid': True,
            'shares_outstanding': shares,
            'baseline_nav_per_share': base_nav_sh,
            'per_share_nav_delta_dollars': round(per_share_nav_delta, 4),
            'projected_nav_per_share': proj_nav_sh,
            'projected_nav_return_pct': round(per_share_return_pct, 4),
            'explanation_or_lock_reason': "Valid contemporaneous shares denominator and baseline verified."
        }
        
        # 8. 4-Regime Secondary Market Price Projections
        base_mkt_px = mkt_rng['baseline_market_price']
        base_prem_disc_pct = mkt_rng['baseline_premium_discount_pct']
        
        # Regime 1: Unchanged Baseline Prem/Disc
        px_unchanged = proj_nav_sh * (1.0 + (base_prem_disc_pct / 100.0))
        
        # Regime 2: Normal Market Band (+/- normal_spread_pct)
        px_norm_low = proj_nav_sh * (1.0 + ((base_prem_disc_pct - normal_spread_pct) / 100.0))
        px_norm_high = proj_nav_sh * (1.0 + ((base_prem_disc_pct + normal_spread_pct) / 100.0))
        
        # Regime 3: Stressed Market Band (+/- stressed_spread_pct)
        px_stress_low = proj_nav_sh * (1.0 + ((base_prem_disc_pct - stressed_spread_pct) / 100.0))
        px_stress_high = proj_nav_sh * (1.0 + ((base_prem_disc_pct + stressed_spread_pct) / 100.0))
        
        # Regime 4: NAV Parity Benchmark
        px_parity = proj_nav_sh
        
        secondary_market_section = {
            'status': "AVAILABLE",
            'baseline_market_price': base_mkt_px,
            'baseline_premium_discount_pct': round(base_prem_disc_pct, 4),
            'regimes': {
                'unchanged_baseline_prem_disc': {
                    'regime_name': "Unchanged Baseline Premium/Discount",
                    'assumed_prem_disc_pct': round(base_prem_disc_pct, 2),
                    'projected_market_price': round(px_unchanged, 2),
                    'projected_market_return_pct': round(((px_unchanged - base_mkt_px) / base_mkt_px) * 100.0, 2)
                },
                'normal_market_band': {
                    'regime_name': f"Normal Historical Dispersion (+/-{normal_spread_pct:.1f}%)",
                    'low_price': round(px_norm_low, 2),
                    'base_price': round(px_unchanged, 2),
                    'high_price': round(px_norm_high, 2),
                    'spread_band_pct': normal_spread_pct
                },
                'stressed_market_band': {
                    'regime_name': f"Stressed Liquidity / Gap Risk (+/-{stressed_spread_pct:.1f}%)",
                    'low_price': round(px_stress_low, 2),
                    'base_price': round(px_unchanged, 2),
                    'high_price': round(px_stress_high, 2),
                    'spread_band_pct': stressed_spread_pct
                },
                'nav_parity_benchmark': {
                    'regime_name': "NAV Parity Benchmark (0.00% Prem/Disc)",
                    'assumed_prem_disc_pct': 0.00,
                    'projected_market_price': round(px_parity, 2),
                    'projected_market_return_pct': round(((px_parity - base_mkt_px) / base_mkt_px) * 100.0, 2)
                }
            }
        }
    else:
        nav_impact_section = {
            'status': "DOLLAR_CHANGE_ONLY_NON_CONTEMPORANEOUS_BASELINE",
            'dollar_nav_change': round(net_futures_pnl_dollars, 2),
            'percent_nav_change': None,
            'baseline_total_fund_nav_dollars': None,
            'projected_total_fund_nav_dollars': None,
            'notice': "Percent NAV change unavailable: baseline total NAV is not contemporaneous with holdings."
        }
        per_share_section = {
            'status': scenario_res['per_share_status'],
            'is_denominator_valid': False,
            'shares_outstanding': None,
            'baseline_nav_per_share': None,
            'per_share_nav_delta_dollars': None,
            'projected_nav_per_share': None,
            'projected_nav_return_pct': None,
            'explanation_or_lock_reason': scenario_res['per_share_message']
        }
        secondary_market_section = {
            'status': "UNAVAILABLE_LOCKED",
            'baseline_market_price': None,
            'regimes': None,
            'lock_reason': "Secondary market price projections locked: contemporaneous per-share baseline required."
        }

    # 9. Data Confidence & Disclosures Rating
    if is_per_share_valid and scenario_mode == 'FROZEN_BOOK':
        confidence_rating = "HIGH_CONFIDENCE_CONTEMPORANEOUS"
        confidence_summary = "Official verified holdings snapshot and contemporaneous baseline verified. No forward book assumptions."
    elif is_per_share_valid and scenario_mode == 'USER_SPECIFIED_FORWARD_BOOK':
        confidence_rating = "CAUTION_USER_ASSUMED_FORWARD_BOOK"
        confidence_summary = "Evaluates user-specified hypothetical forward legs. Not an official fund roll projection."
    else:
        confidence_rating = "MODERATE_CONFIDENCE_P_AND_L_ONLY"
        confidence_summary = "Gross futures P&L is verified against official disclosed archive. Per-share estimates locked due to non-contemporaneous baseline."

    # 10. Construct Final Ticket Payload
    ticket_id = f"DT-{fund_code}-{scenario_res['official_snapshot_as_of_date'].replace('-', '')}-{hashlib.sha256(json.dumps(scenario_res['contract_breakdown'], default=str).encode('utf-8')).hexdigest()[:8].upper()}"
    
    return {
        'ticket_id': ticket_id,
        'ticket_title': f"INSTITUTIONAL ETF SCENARIO DECISION TICKET: {fund_code}",
        'fund_symbol': fund_code,
        'generation_time_utc': ref_time.isoformat(),
        'provenance_and_dates': {
            'holdings_snapshot_as_of_date': scenario_res['official_snapshot_as_of_date'],
            'baseline_as_of_date': scenario_res['provenance_dates']['baseline_as_of_date'],
            'scenario_horizon_date': target_horizon_date,
            'baseline_to_holdings_gap_days': scenario_res['provenance_dates']['baseline_to_holdings_gap_days'],
            'is_baseline_contemporaneous': scenario_res['provenance_dates']['is_baseline_contemporaneous_with_snapshot'],
            'date_alignment_summary': scenario_res['provenance_dates']['date_alignment_summary'],
            'date_alignment_disclaimer': scenario_res['provenance_dates']['date_alignment_disclaimer'],
            'archive_sha256': builder.snapshot.get('provenance_record', {}).get('expected_sha256', ''),
            'provenance_status': builder.snapshot.get('provenance_record', {}).get('provenance_status', 'VERIFIED_OFFICIAL_ARCHIVE')
        },
        'book_classification': {
            'scenario_mode': scenario_mode,
            'scenario_mode_label': scenario_res['scenario_mode_label'],
            'governance_warning': (
                "HYPOTHETICAL USER FORWARD BOOK ASSUMPTION — NOT AN ETF ROLL GUIDANCE/PREDICTION"
                if scenario_mode == 'USER_SPECIFIED_FORWARD_BOOK' else "OFFICIAL VERIFIED DISCLOSED BOOK"
            )
        },
        'book_separation': {
            'known_disclosed_book': known_disclosed_book,
            'user_assumed_future_book': user_assumed_future_book
        },
        'futures_pnl_summary': {
            'total_gross_futures_pnl_dollars': round(tot_gross_pnl, 2),
            'total_user_roll_costs_dollars': round(scenario_res['total_roll_transaction_costs_dollars'], 2),
            'net_scenario_pnl_dollars': round(net_futures_pnl_dollars, 2),
            'total_base_futures_notional_dollars': round(tot_base_notional, 2),
            'return_on_futures_notional_pct': round((tot_gross_pnl / tot_base_notional * 100.0) if tot_base_notional > 0 else 0.0, 2),
            'pnl_direction': scenario_res['pnl_direction']
        },
        'route_level_attribution': active_routes,
        'contract_level_breakdown': scenario_res['contract_breakdown'],
        'fund_nav_impact': nav_impact_section,
        'per_share_nav_impact': per_share_section,
        'secondary_market_price_ranges': secondary_market_section,
        'confidence_and_disclosures': {
            'data_confidence_rating': confidence_rating,
            'confidence_summary': confidence_summary,
            'roll_execution_drag_disclosure': "Intraday roll executions, spread slippage, and exchange execution fees are unobserved and may cause drag.",
            'collateral_and_cash_yield_disclosure': "Daily cash collateral interest yield on AGPXX and margin repo sweeps between disclosure dates are unobserved.",
            'management_fee_drag_disclosure': "Advisory fee (0.95% annualized = approx 0.0026%/day) and administrative OpEx accrue continuously.",
            'ap_basket_creation_redemption_disclosure': "Authorized Participant (AP) unit creation and redemption share movements alter future share counts.",
            'secondary_market_prem_disc_disclosure': "Secondary ETF market trades at dynamic premiums/discounts to intraday NAV based on authorized participant arbitrage bounds."
        }
    }


def format_decision_ticket_text(ticket: Dict[str, Any]) -> str:
    """Formats the Decision Ticket as an institutional plain-text report."""
    prov = ticket['provenance_and_dates']
    pnl = ticket['futures_pnl_summary']
    nav_sec = ticket['fund_nav_impact']
    per_sh = ticket['per_share_nav_impact']
    mkt_sec = ticket['secondary_market_price_ranges']
    
    lines = []
    lines.append("=" * 95)
    lines.append(f"          {ticket['ticket_title']} ({ticket['ticket_id']})          ")
    lines.append("=" * 95)
    lines.append(f"  Holdings As-Of Date   : {prov['holdings_snapshot_as_of_date']} (Archive SHA: {prov['archive_sha256'][:12]}...)")
    lines.append(f"  Baseline As-Of Date   : {prov['baseline_as_of_date']} (Gap: {prov['baseline_to_holdings_gap_days'] or 0}d | Contemporaneous: {prov['is_baseline_contemporaneous']})")
    lines.append(f"  Scenario Horizon Date : {prov['scenario_horizon_date']}")
    lines.append(f"  Book Mode             : {ticket['book_classification']['scenario_mode_label']}")
    lines.append(f"  Confidence Rating     : {ticket['confidence_and_disclosures']['data_confidence_rating']}")
    lines.append("-" * 95)
    
    lines.append("1. GROSS FUTURES P&L & ROUTE ATTRIBUTION:")
    lines.append(f"  Gross Futures P&L     : ${pnl['total_gross_futures_pnl_dollars']:+,.2f} ({pnl['pnl_direction']})")
    lines.append(f"  Base Futures Notional : ${pnl['total_base_futures_notional_dollars']:,.2f}")
    lines.append(f"  Futures Return (%)    : {pnl['return_on_futures_notional_pct']:+.2f}%")
    if pnl['total_user_roll_costs_dollars'] > 0:
        lines.append(f"  User Roll Costs       : -${pnl['total_user_roll_costs_dollars']:,.2f}")
        lines.append(f"  Net Scenario P&L      : ${pnl['net_scenario_pnl_dollars']:+,.2f}")
        
    lines.append("  Route Class Breakdown :")
    for r_k, r_v in ticket['route_level_attribution'].items():
        lines.append(f"    - {r_v['route_class_name']:<24}: P&L ${r_v['gross_futures_pnl_dollars']:>+12,.2f} | Notional ${r_v['base_notional_dollars']:>10,.2f} ({r_v['return_on_notional_pct']:>+6.2f}%)")
        
    lines.append("-" * 95)
    lines.append("2. FUND NAV & PER-SHARE IMPACT:")
    if per_sh['is_denominator_valid']:
        lines.append(f"  Baseline NAV/Share    : ${per_sh['baseline_nav_per_share']:.2f} (Total NAV: ${nav_sec['baseline_total_fund_nav_dollars']:,.2f} | Shares: {per_sh['shares_outstanding']:,})")
        lines.append(f"  Projected NAV/Share   : ${per_sh['projected_nav_per_share']:.2f} (Change: {per_sh['per_share_nav_delta_dollars']:+,.4f}/sh | {per_sh['projected_nav_return_pct']:+.2f}%)")
        lines.append(f"  Projected Total NAV   : ${nav_sec['projected_total_fund_nav_dollars']:,.2f} (NAV Change: {nav_sec['percent_nav_change']:+.2f}%)")
    else:
        lines.append(f"  Per-Share Impact      : LOCKED / UNAVAILABLE ({per_sh['status']})")
        lines.append(f"  Reason                : {per_sh['explanation_or_lock_reason']}")
        lines.append(f"  Net Dollar NAV Delta  : ${nav_sec['dollar_nav_change']:+,.2f}")
        
    lines.append("-" * 95)
    lines.append("3. SECONDARY MARKET ETF PRICE PROJECTIONS:")
    if mkt_sec['status'] == 'AVAILABLE':
        reg = mkt_sec['regimes']
        unchanged = reg['unchanged_baseline_prem_disc']
        norm = reg['normal_market_band']
        stress = reg['stressed_market_band']
        parity = reg['nav_parity_benchmark']
        lines.append(f"  Baseline Market Close : ${mkt_sec['baseline_market_price']:.2f} (Prem/Disc: {mkt_sec['baseline_premium_discount_pct']:+.2f}%)")
        lines.append(f"  [Unchanged Prem/Disc] : ${unchanged['projected_market_price']:.2f} ({unchanged['projected_market_return_pct']:+.2f}% ETF Return)")
        lines.append(f"  [Normal Band +/-2%]   : Low ${norm['low_price']:.2f}  |  Base ${norm['base_price']:.2f}  |  High ${norm['high_price']:.2f}")
        lines.append(f"  [Stressed Band +/-5%] : Low ${stress['low_price']:.2f}  |  Base ${stress['base_price']:.2f}  |  High ${stress['high_price']:.2f}")
        lines.append(f"  [NAV Parity (0% P/D)] : ${parity['projected_market_price']:.2f}")
    else:
        lines.append(f"  Price Projections     : {mkt_sec['lock_reason']}")
        
    lines.append("-" * 95)
    lines.append("4. BOOK SEPARATION & GOVERNANCE:")
    lines.append(f"  Disclosed Positions   : {len(ticket['book_separation']['known_disclosed_book'])} contracts verified against official archive.")
    if ticket['book_classification']['scenario_mode'] == 'USER_SPECIFIED_FORWARD_BOOK':
        lines.append(f"  User-Assumed Legs     : {len(ticket['book_separation']['user_assumed_future_book'])} hypothetical forward positions.")
        lines.append(f"  WARNING               : {ticket['book_classification']['governance_warning']}")
    else:
        lines.append("  Frozen Book Mode      : Preserves exact disclosed constituent holdings and lots.")
        
    lines.append("=" * 95)
    return "\n".join(lines)


if __name__ == '__main__':
    print("Testing Decision Ticket Workflow in Python...")
    ticket = generate_decision_ticket(
        fund='BDRY',
        target_contract_prices={'C5TCM Q26 INDEX': 42000.0},
        scenario_horizon_date='2026-08-14',
        manual_dated_baseline={
            'total_nav_dollars': 30000000.0,
            'shares_outstanding': 2169200,
            'nav_per_share': 13.83,
            'market_price': 13.79,
            'as_of_date': '2026-08-14',
            'source': 'Manual Contemporaneous Baseline'
        }
    )
    print(format_decision_ticket_text(ticket))
