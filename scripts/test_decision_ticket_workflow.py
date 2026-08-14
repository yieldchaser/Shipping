"""
Unit & Integration Test Suite: Decision-Ticket Workflow Engine
==============================================================
Validates:
1. Inputs: Current verified ETF book, exact target marks, % shocks, horizon, forward book, manual contemporaneous baseline.
2. Outputs: Gross futures P&L by contract and route, NAV dollar & % change, per-share NAV (strictly gated on valid denominator), 4-regime market price range, disclosures, and known vs assumed book separation.
3. Immutability: Enforces strict READ-ONLY execution. Zero mutation of production manifests, snapshots, or history.
"""

import os
import sys
import json
import hashlib
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))

from decision_ticket_workflow import (
    generate_decision_ticket,
    format_decision_ticket_text
)
from thesis_scenario_builder import (
    InvalidForwardBookAssumptionError,
    InconsistentManualBaselineError
)

PROD_FILES_TO_MONITOR = [
    'data/etf/snapshots/provenance_manifest.json',
    'data/etf/snapshots/bdry_scenario_snapshot.json',
    'data/etf/snapshots/bwet_scenario_snapshot.json',
    'data/etf/snapshots/scenario_snapshots.js',
    'data/etf/bdry_holdings_history.csv',
    'data/etf/bwet_holdings_history.csv',
    'data/etf/bdry_liquidity.csv',
    'data/etf/bwet_liquidity.csv'
]

class TestDecisionTicketWorkflow(unittest.TestCase):
    
    def _compute_prod_hashes(self):
        hashes = {}
        for rel_p in PROD_FILES_TO_MONITOR:
            full_p = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', rel_p))
            if os.path.exists(full_p):
                with open(full_p, 'rb') as f:
                    hashes[rel_p] = hashlib.sha256(f.read()).hexdigest()
        return hashes

    def setUp(self):
        self.ref_time = datetime(2026, 8, 14, 15, 0, 0, tzinfo=timezone.utc)
        self.pre_test_hashes = self._compute_prod_hashes()

    def tearDown(self):
        post_test_hashes = self._compute_prod_hashes()
        for rel_p, pre_sha in self.pre_test_hashes.items():
            post_sha = post_test_hashes.get(rel_p)
            self.assertEqual(
                post_sha,
                pre_sha,
                f"Production file {rel_p} was mutated during decision ticket test execution! (Pre: {pre_sha}, Post: {post_sha})"
            )
        
    def test_01_bdry_frozen_book_exact_contract_shock(self):
        """Test BDRY Decision Ticket with single contract shock in frozen book mode."""
        ticket = generate_decision_ticket(
            fund='BDRY',
            target_contract_prices={'C5TCM Q26 INDEX': 42000.0},
            scenario_horizon_date='2026-08-14',
            reference_time_utc=self.ref_time,
            manual_dated_baseline={
                'total_nav_dollars': 30000000.0,
                'shares_outstanding': 2169200,
                'nav_per_share': 13.83,
                'market_price': 13.79,
                'as_of_date': '2026-08-14',
                'source': 'Manual Contemporaneous Baseline'
            }
        )
        
        # Verify identification & metadata
        self.assertTrue(ticket['ticket_id'].startswith('DT-BDRY-20260814-'))
        self.assertEqual(ticket['fund_symbol'], 'BDRY')
        self.assertEqual(ticket['provenance_and_dates']['holdings_snapshot_as_of_date'], '2026-08-14')
        self.assertEqual(ticket['book_classification']['scenario_mode'], 'FROZEN_BOOK')
        
        # Verify P&L and Route Attribution
        # Base mark is 39200, target is 42000 => Delta = +2800 * 155 lots * 1.0 = +434,000.00
        pnl = ticket['futures_pnl_summary']
        self.assertEqual(pnl['total_gross_futures_pnl_dollars'], 434000.00)
        self.assertEqual(pnl['net_scenario_pnl_dollars'], 434000.00)
        
        routes = ticket['route_level_attribution']
        self.assertIn('Capesize', routes)
        self.assertIn('Panamax', routes)
        self.assertIn('Supramax', routes)
        self.assertEqual(routes['Capesize']['gross_futures_pnl_dollars'], 434000.00)
        self.assertEqual(routes['Panamax']['gross_futures_pnl_dollars'], 0.00)
        self.assertEqual(routes['Supramax']['gross_futures_pnl_dollars'], 0.00)
        
        # Verify NAV & Per-Share
        per_sh = ticket['per_share_nav_impact']
        self.assertTrue(per_sh['is_denominator_valid'])
        self.assertEqual(per_sh['shares_outstanding'], 2169200)
        # Expected per share delta = 434,000 / 2,169,200 = 0.2000737...
        self.assertAlmostEqual(per_sh['per_share_nav_delta_dollars'], 0.2001, places=3)
        self.assertAlmostEqual(per_sh['projected_nav_per_share'], 14.0301, places=2)
        
        # Verify Market Price Regimes
        mkt = ticket['secondary_market_price_ranges']
        self.assertEqual(mkt['status'], 'AVAILABLE')
        regimes = mkt['regimes']
        self.assertIn('unchanged_baseline_prem_disc', regimes)
        self.assertIn('normal_market_band', regimes)
        self.assertIn('stressed_market_band', regimes)
        self.assertIn('nav_parity_benchmark', regimes)
        
        # Verify Book Separation
        sep = ticket['book_separation']
        self.assertGreater(len(sep['known_disclosed_book']), 0)
        self.assertEqual(len(sep['user_assumed_future_book']), 0)

    def test_02_bwet_frozen_book_tanker_multipliers_and_routes(self):
        """Test BWET Decision Ticket with VLCC and Suezmax 1,000 MT multiplier handling."""
        ticket = generate_decision_ticket(
            fund='BWET',
            target_contract_prices={
                'DD3CM Q26 INDEX': 105.167,  # +10.00 $/MT on 160 lots * 1000 MT = +$1,600,000
                'DD20M Q26 INDEX': 43.507    # +5.00 $/MT on 30 lots * 1000 MT = +$150,000
            },
            scenario_horizon_date='2026-08-14',
            reference_time_utc=self.ref_time,
            manual_dated_baseline={
                'total_nav_dollars': 15000000.0,
                'shares_outstanding': 44200,
                'nav_per_share': 339.37,
                'market_price': 357.33,
                'as_of_date': '2026-08-14',
                'source': 'Manual Contemporaneous Baseline'
            }
        )
        
        pnl = ticket['futures_pnl_summary']
        self.assertEqual(pnl['total_gross_futures_pnl_dollars'], 1750000.00)
        
        routes = ticket['route_level_attribution']
        self.assertIn('VLCC', routes)
        self.assertIn('Suezmax', routes)
        self.assertEqual(routes['VLCC']['gross_futures_pnl_dollars'], 1600000.00)
        self.assertEqual(routes['Suezmax']['gross_futures_pnl_dollars'], 150000.00)
        
        per_sh = ticket['per_share_nav_impact']
        self.assertTrue(per_sh['is_denominator_valid'])
        self.assertAlmostEqual(per_sh['per_share_nav_delta_dollars'], 39.5893, places=3)
        self.assertAlmostEqual(per_sh['projected_nav_per_share'], 378.9593, places=2)

    def test_03_non_contemporaneous_baseline_locks_per_share_denominator(self):
        """Test that per-share impact and market price range fail closed when baseline is non-contemporaneous."""
        ticket = generate_decision_ticket(
            fund='BDRY',
            target_contract_prices={'C5TCM Q26 INDEX': 42000.0},
            scenario_horizon_date='2026-08-14',
            reference_time_utc=self.ref_time
            # Omit manual_dated_baseline => default non-contemporaneous baseline
        )
        
        # Gross futures P&L and route attribution are available
        self.assertEqual(ticket['futures_pnl_summary']['total_gross_futures_pnl_dollars'], 434000.00)
        self.assertIn('Capesize', ticket['route_level_attribution'])
        
        # Per-share outputs are strictly locked
        per_sh = ticket['per_share_nav_impact']
        self.assertFalse(per_sh['is_denominator_valid'])
        self.assertIsNone(per_sh['shares_outstanding'])
        self.assertIsNone(per_sh['projected_nav_per_share'])
        self.assertEqual(per_sh['status'], "PER_SHARE_UNAVAILABLE_NON_CONTEMPORANEOUS_BASELINE")
        
        # Secondary market price range is strictly locked
        mkt = ticket['secondary_market_price_ranges']
        self.assertEqual(mkt['status'], "UNAVAILABLE_LOCKED")
        self.assertIsNone(mkt['regimes'])

    def test_04_invalid_manual_baseline_fails_closed(self):
        """Test that inconsistent total_nav / shares != nav_per_share is rejected and fails closed."""
        ticket = generate_decision_ticket(
            fund='BDRY',
            target_contract_prices={'C5TCM Q26 INDEX': 42000.0},
            scenario_horizon_date='2026-08-14',
            reference_time_utc=self.ref_time,
            manual_dated_baseline={
                'total_nav_dollars': 30000000.0,
                'shares_outstanding': 2169200, # implied = 13.83
                'nav_per_share': 25.00,        # mismatched!
                'market_price': 13.79,
                'as_of_date': '2026-08-14',
                'source': 'Bad Input'
            }
        )
        per_sh = ticket['per_share_nav_impact']
        self.assertFalse(per_sh['is_denominator_valid'])
        self.assertEqual(per_sh['status'], "PER_SHARE_UNAVAILABLE_INVALID_MANUAL_BASELINE")
        self.assertIn("differs from supplied nav_per_share", per_sh['explanation_or_lock_reason'])

    def test_05_user_specified_forward_book_with_roll_in_legs(self):
        """Test USER_SPECIFIED_FORWARD_BOOK mode with roll-in contract and roll costs."""
        ticket = generate_decision_ticket(
            fund='BDRY',
            scenario_mode='USER_SPECIFIED_FORWARD_BOOK',
            user_assumed_forward_book=[
                {
                    'contract_identifier': 'Capesize 5TC FFA 180kt Timecharter Average M Jan 27',
                    'contract_name': 'Capesize 5TC FFA 180kt Timecharter Average M Jan 27',
                    'ticker': 'C5TCM F27 INDEX',
                    'cusip': 'C5TCM F27',
                    'lots': 60.0,
                    'multiplier': 1.0,
                    'starting_mark': 32000.0,
                    'target_mark': 36000.0, # +4000 on 60 lots = +240,000
                    'roll_transaction_cost_dollars': 5000.0
                }
            ],
            scenario_horizon_date='2026-08-14',
            reference_time_utc=self.ref_time,
            manual_dated_baseline={
                'total_nav_dollars': 30000000.0,
                'shares_outstanding': 2169200,
                'nav_per_share': 13.83,
                'market_price': 13.79,
                'as_of_date': '2026-08-14',
                'source': 'Manual Contemporaneous Baseline'
            }
        )
        
        self.assertEqual(ticket['book_classification']['scenario_mode'], 'USER_SPECIFIED_FORWARD_BOOK')
        self.assertEqual(ticket['confidence_and_disclosures']['data_confidence_rating'], 'CAUTION_USER_ASSUMED_FORWARD_BOOK')
        
        # P&L check: 240,000 gross P&L - 5,000 roll cost = 235,000 net
        pnl = ticket['futures_pnl_summary']
        self.assertEqual(pnl['total_gross_futures_pnl_dollars'], 240000.00)
        self.assertEqual(pnl['total_user_roll_costs_dollars'], 5000.00)
        self.assertEqual(pnl['net_scenario_pnl_dollars'], 235000.00)
        
        # Book separation check
        sep = ticket['book_separation']
        self.assertGreater(len(sep['known_disclosed_book']), 0)
        self.assertGreater(len(sep['user_assumed_future_book']), 0)
        
        # Find roll in leg
        roll_in = next(r for r in sep['user_assumed_future_book'] if r['is_roll_in_new_contract'])
        self.assertEqual(roll_in['ticker'], 'C5TCM F27 INDEX')
        self.assertEqual(roll_in['roll_transaction_cost_dollars'], 5000.0)

    def test_06_format_decision_ticket_text_output(self):
        """Test formatting of text decision ticket."""
        ticket = generate_decision_ticket(
            fund='BDRY',
            target_contract_prices={'C5TCM Q26 INDEX': 42000.0},
            scenario_horizon_date='2026-08-14',
            reference_time_utc=self.ref_time,
            manual_dated_baseline={
                'total_nav_dollars': 30000000.0,
                'shares_outstanding': 2169200,
                'nav_per_share': 13.83,
                'market_price': 13.79,
                'as_of_date': '2026-08-14',
                'source': 'Manual Contemporaneous Baseline'
            }
        )
        txt = format_decision_ticket_text(ticket)
        self.assertIn("INSTITUTIONAL ETF SCENARIO DECISION TICKET: BDRY", txt)
        self.assertIn("GROSS FUTURES P&L & ROUTE ATTRIBUTION", txt)
        self.assertIn("Capesize 5TC", txt)
        self.assertIn("SECONDARY MARKET ETF PRICE PROJECTIONS", txt)
        self.assertIn("Normal Band +/-2%", txt)
        self.assertIn("Stressed Band +/-5%", txt)

    def test_07_live_snapshot_decision_ticket_preserves_production_provenance(self):
        """Regression Test: Generate decision tickets from live published snapshots and assert 100% untouched production provenance."""
        # 1. Run live BDRY Decision Ticket
        ticket_bdry = generate_decision_ticket(
            fund='BDRY',
            route_percentage_shocks={'Capesize': 5.0, 'Panamax': -2.0, 'Supramax': 1.0},
            scenario_horizon_date='2026-08-14',
            reference_time_utc=self.ref_time
        )
        self.assertIsNotNone(ticket_bdry['ticket_id'])
        self.assertEqual(ticket_bdry['fund_symbol'], 'BDRY')

        # 2. Run live BWET Decision Ticket
        ticket_bwet = generate_decision_ticket(
            fund='BWET',
            route_percentage_shocks={'VLCC': 4.0, 'Suezmax': -1.5},
            scenario_horizon_date='2026-08-14',
            reference_time_utc=self.ref_time
        )
        self.assertIsNotNone(ticket_bwet['ticket_id'])
        self.assertEqual(ticket_bwet['fund_symbol'], 'BWET')

        # 3. Assert all production artifact hashes are unchanged
        post_hashes = self._compute_prod_hashes()
        self.assertEqual(self.pre_test_hashes, post_hashes)

        # 4. Verify complete production artifact integrity audit passes with 0 errors
        from verify_production_artifact_integrity import verify_production_integrity
        is_valid, errors, summary = verify_production_integrity(verbose=False)
        self.assertTrue(is_valid, f"Production artifact integrity audit must pass 100%! Errors: {errors}")
        self.assertEqual(len(errors), 0)

if __name__ == '__main__':
    unittest.main()
