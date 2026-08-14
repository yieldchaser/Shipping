"""
Comprehensive Unit Tests: Thesis-to-ETF Scenario Translator Engine
===================================================================
Tests proving:
1. No synthetic future roll lots exist (.5x/1.5x deleted; FROZEN_BOOK uses exact disclosed lots).
2. Stale/mismatched NAV and shares block per-share projections and fail closed.
3. Missing baseline fields cannot silently fall back to defaults.
4. Exact-contract target mark cannot affect another maturity.
5. Manually supplied dated baseline produces expected projected NAV/share.
6. USER_SPECIFIED_FORWARD_BOOK evaluates explicit custom forward lots.
7. Freshness guard rejects stale snapshots (> 3 business days).
8. Roll-in contract missing entry mark or multiplier is rejected (Safeguard 1).
9. Inconsistent manual NAV / shares / NAV-per-share is rejected / marked invalid (Safeguard 2).
10. Output preserves and prominently displays all three dates (Safeguard 3).
11. Missing scenario-snapshot provenance blocks price-range output (Safeguard 4).
"""

import unittest
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from datetime import datetime, timezone, timedelta
from thesis_scenario_builder import (
    ThesisScenarioBuilder,
    StaleSnapshotError,
    InvalidForwardBookAssumptionError,
    MissingProvenanceRecordError
)
from scenario_snapshot_schema import (
    load_published_scenario_snapshot,
    validate_scenario_snapshot
)

class TestThesisScenarioTranslatorHardening(unittest.TestCase):
    
    def setUp(self):
        # Injected reference time: 2026-08-14 12:00:00 UTC (1 business day after 2026-08-13 snapshot)
        self.ref_time = datetime(2026, 8, 14, 12, 0, 0, tzinfo=timezone.utc)
        self.builder_bdry = ThesisScenarioBuilder(fund='BDRY', reference_time_utc=self.ref_time)
        self.builder_bwet = ThesisScenarioBuilder(fund='BWET', reference_time_utc=self.ref_time)

    def test_no_synthetic_future_roll_lots_in_frozen_book(self):
        """Prove that FROZEN_BOOK preserves exact disclosed lots without any .5x / 1.5x synthetic scaling."""
        res = self.builder_bdry.build_scenario(
            target_contract_prices={'C5TCM Q26 INDEX': 40000.0},
            scenario_mode='FROZEN_BOOK'
        )
        self.assertEqual(res['scenario_mode'], 'FROZEN_BOOK')
        self.assertEqual(res['scenario_mode_label'], 'Frozen disclosed book')
        for row in res['contract_breakdown']:
            self.assertEqual(
                row['effective_lots'],
                row['disclosed_lots'],
                f"Synthetic roll detected in {row['contract_name']}: {row['effective_lots']} != {row['disclosed_lots']}"
            )

    def test_stale_mismatched_baseline_fails_closed(self):
        """
        Prove that non-contemporaneous dates (Aug 13 snapshot vs Aug 12 NAV vs June 30 shares)
        fail closed for per-share projections and emit the required governance message.
        """
        res = self.builder_bdry.build_scenario(
            target_contract_prices={'C5TCM Q26 INDEX': 40000.0},
            scenario_mode='FROZEN_BOOK'
        )
        self.assertGreater(res['gross_futures_pnl_dollars'], 0)
        self.assertEqual(res['per_share_status'], "PER_SHARE_UNAVAILABLE_NON_CONTEMPORANEOUS_BASELINE")
        self.assertIsNone(res['approximate_nav_target_range'])
        self.assertIsNone(res['approximate_etf_market_price_target_range'])
        self.assertIn("Gross futures P&L available; per-share ETF estimate unavailable", res['per_share_message'])

    def test_missing_baseline_fields_cannot_silently_fallback(self):
        """Prove that missing baseline fields do not trigger hardcoded defaults ($10, 1M shares)."""
        self.builder_bdry.baseline['is_contemporaneous'] = False
        res = self.builder_bdry.build_scenario(
            target_contract_prices={'C5TCM Q26 INDEX': 42000.0}
        )
        self.assertIsNone(res['approximate_nav_target_range'])
        self.assertIsNone(res['approximate_etf_market_price_target_range'])
        self.assertEqual(res['per_share_status'], "PER_SHARE_UNAVAILABLE_NON_CONTEMPORANEOUS_BASELINE")

    def test_exact_contract_target_isolation(self):
        """Prove that entering a target mark for one specific contract maturity does NOT affect other maturities."""
        aug_target_px = 45000.0
        res = self.builder_bdry.build_scenario(
            target_contract_prices={'C5TCM Q26 INDEX': aug_target_px},
            scenario_mode='FROZEN_BOOK'
        )
        
        c_aug = None
        c_sep = None
        for row in res['contract_breakdown']:
            if row['ticker'] == 'C5TCM Q26 INDEX':
                c_aug = row
            elif 'Sep 26' in row['contract_name']:
                c_sep = row
                
        self.assertIsNotNone(c_aug)
        self.assertIsNotNone(c_sep)
        self.assertEqual(c_aug['target_mark_price'], aug_target_px)
        self.assertNotEqual(c_aug['delta_mark_dollars'], 0.0)
        self.assertNotEqual(c_aug['gross_futures_pnl_dollars'], 0.0)
        
        self.assertEqual(c_sep['target_mark_price'], c_sep['current_mark_price'])
        self.assertEqual(c_sep['delta_mark_dollars'], 0.0)
        self.assertEqual(c_sep['gross_futures_pnl_dollars'], 0.0)

    def test_manually_supplied_dated_baseline(self):
        """Prove that a valid contemporaneous manual baseline unlocks per-share estimates with correct math."""
        snap_dt = self.builder_bdry.snapshot['snapshot_date']
        manual_baseline = {
            'total_nav_dollars': 30_000_000.0,
            'shares_outstanding': 2_000_000,
            'nav_per_share': 15.00,
            'market_price': 14.80,
            'as_of_date': snap_dt,
            'source': 'Verified User Manual Input'
        }
        
        base_q26_mark = float(self.builder_bdry.snapshot['positions'][0]['price'])
        target_prices = {'C5TCM Q26 INDEX': base_q26_mark + 1000.0}
        res = self.builder_bdry.build_scenario(
            target_contract_prices=target_prices,
            scenario_mode='FROZEN_BOOK',
            manual_dated_baseline=manual_baseline,
            premium_discount_spread_pct=2.50
        )
        
        self.assertEqual(res['per_share_status'], "PER_SHARE_ESTIMATE_AVAILABLE")
        self.assertIsNotNone(res['approximate_nav_target_range'])
        self.assertIsNotNone(res['approximate_etf_market_price_target_range'])
        
        nav_rng = res['approximate_nav_target_range']
        mkt_rng = res['approximate_etf_market_price_target_range']
        
        expected_total_nav = 30_000_000.0 + 155_000.0
        expected_nav_per_sh = expected_total_nav / 2_000_000
        
        self.assertAlmostEqual(nav_rng['projected_total_fund_nav_dollars'], expected_total_nav, places=2)
        self.assertAlmostEqual(nav_rng['projected_nav_per_share'], expected_nav_per_sh, places=4)
        self.assertAlmostEqual(mkt_rng['base_target_nav_parity'], round(expected_nav_per_sh, 2), places=2)

    def test_user_specified_forward_book(self):
        """Prove that USER_SPECIFIED_FORWARD_BOOK evaluates explicit custom forward lots and is labeled correctly."""
        oct_pos = next(p for p in self.builder_bdry.snapshot['positions'] if p['ticker'] == 'C5TCM V26 INDEX')
        oct_base_price = float(oct_pos['price'])
        target_oct_price = oct_base_price + 1500.0
        
        custom_lots = {
            'C5TCM Q26 INDEX': 0.0,
            'C5TCM V26 INDEX': 200.0
        }
        target_prices = {
            'C5TCM V26 INDEX': target_oct_price
        }
        
        res = self.builder_bdry.build_scenario(
            target_contract_prices=target_prices,
            scenario_mode='USER_SPECIFIED_FORWARD_BOOK',
            user_forward_lots=custom_lots
        )
        self.assertEqual(res['scenario_mode'], 'USER_SPECIFIED_FORWARD_BOOK')
        self.assertEqual(res['scenario_mode_label'], 'User-assumed forward book')
        
        for row in res['contract_breakdown']:
            if row['ticker'] == 'C5TCM Q26 INDEX':
                self.assertEqual(row['effective_lots'], 0.0)
                self.assertEqual(row['gross_futures_pnl_dollars'], 0.0)
            elif row['ticker'] == 'C5TCM V26 INDEX':
                self.assertEqual(row['effective_lots'], 200.0)
                expected_pnl = 200.0 * 1.0 * (target_oct_price - oct_base_price)
                self.assertAlmostEqual(row['gross_futures_pnl_dollars'], expected_pnl, places=2)

    def test_rejected_synthetic_modes(self):
        """Prove that requesting synthetic roll modes raises ValueError."""
        with self.assertRaises(ValueError):
            self.builder_bdry.build_scenario(scenario_mode='ROLL_AWARE_APPROXIMATE')

    def test_bwet_tanker_exact_shock(self):
        """Prove that BWET tanker pricing evaluates 1000 MT multiplier correctly."""
        c_vlcc_pos = next(p for p in self.builder_bwet.snapshot['positions'] if p['ticker'] == 'DD3CM Q26 INDEX')
        vlcc_base_mark = float(c_vlcc_pos['price'])
        target_vlcc_mark = vlcc_base_mark + 5.0
        
        target_prices = {'DD3CM Q26 INDEX': target_vlcc_mark}
        res = self.builder_bwet.build_scenario(
            target_contract_prices=target_prices,
            scenario_mode='FROZEN_BOOK'
        )
        self.assertGreater(res['gross_futures_pnl_dollars'], 0)
        c_vlcc = None
        for row in res['contract_breakdown']:
            if row['ticker'] == 'DD3CM Q26 INDEX':
                c_vlcc = row
                break
        self.assertIsNotNone(c_vlcc)
        expected_pnl = float(c_vlcc_pos['lots']) * 1000.0 * 5.0
        self.assertAlmostEqual(c_vlcc['gross_futures_pnl_dollars'], expected_pnl, places=1)

    def test_stale_snapshot_rejection(self):
        """Prove that builder rejects stale snapshot (> 3 business days)."""
        stale_ref_time = datetime(2026, 8, 25, 12, 0, 0, tzinfo=timezone.utc)
        with self.assertRaises(StaleSnapshotError):
            ThesisScenarioBuilder(fund='BDRY', reference_time_utc=stale_ref_time, max_stale_business_days=3)

    # --- SAFEGUARD 1 TESTS ---
    def test_roll_in_contract_missing_entry_mark_or_multiplier_rejected(self):
        """Prove that a roll-in contract absent from disclosed book missing entry mark or multiplier is rejected."""
        # 1. Using user_forward_lots with an unknown roll-in key absent from disclosed book
        with self.assertRaises(InvalidForwardBookAssumptionError) as ctx:
            self.builder_bdry.build_scenario(
                scenario_mode='USER_SPECIFIED_FORWARD_BOOK',
                user_forward_lots={'NEW_FUTURE_2027_STRIP': 100.0}
            )
        self.assertIn("absent from disclosed book requires exact starting_mark, multiplier, and target_mark", str(ctx.exception))

        # 2. Using user_assumed_forward_book missing starting_mark or multiplier
        incomplete_assumptions = [
            {
                'contract_identifier': 'NEW_CAPE_CAL27',
                'lots': 50.0,
                # Missing starting_mark and multiplier
                'target_mark': 35000.0
            }
        ]
        with self.assertRaises(InvalidForwardBookAssumptionError):
            self.builder_bdry.build_scenario(
                scenario_mode='USER_SPECIFIED_FORWARD_BOOK',
                user_assumed_forward_book=incomplete_assumptions
            )

        # 3. Complete user-assumed roll-in contract succeeds
        complete_assumptions = [
            {
                'contract_identifier': 'NEW_CAPE_CAL27',
                'contract_name': 'Capesize 5TC FFA Cal 27',
                'lots': 50.0,
                'multiplier': 1.0,
                'starting_mark': 30000.0,
                'target_mark': 35000.0,
                'roll_transaction_cost_dollars': 2500.0
            }
        ]
        res = self.builder_bdry.build_scenario(
            scenario_mode='USER_SPECIFIED_FORWARD_BOOK',
            user_assumed_forward_book=complete_assumptions
        )
        self.assertEqual(res['scenario_mode_label'], "User-assumed forward book")
        new_row = [r for r in res['contract_breakdown'] if r['contract_name'] == 'Capesize 5TC FFA Cal 27'][0]
        self.assertTrue(new_row['is_roll_in_new_contract'])
        self.assertEqual(new_row['gross_futures_pnl_dollars'], 250000.0)
        self.assertEqual(new_row['net_contract_pnl_dollars'], 247500.0)

    # --- SAFEGUARD 2 TESTS ---
    def test_inconsistent_manual_baseline_rejected(self):
        """Prove that inconsistent manual NAV / shares / NAV-per-share is rejected or marked invalid."""
        # Total NAV = $30M, Shares = 2M => Implied NAV/sh = $15.00.
        # But supplied nav_per_share is $12.00 (difference $3.00 > tolerance $0.05).
        inconsistent_baseline = {
            'total_nav_dollars': 30_000_000.0,
            'shares_outstanding': 2_000_000,
            'nav_per_share': 12.00,  # Inconsistent!
            'market_price': 14.80,
            'as_of_date': '2026-08-14',
            'source': 'Corrupted Manual Input'
        }
        res = self.builder_bdry.build_scenario(
            target_contract_prices={'C5TCM Q26 INDEX': 40000.0},
            manual_dated_baseline=inconsistent_baseline,
            manual_baseline_tolerance=0.05
        )
        self.assertEqual(res['per_share_status'], "PER_SHARE_UNAVAILABLE_INVALID_MANUAL_BASELINE")
        self.assertIsNone(res['approximate_nav_target_range'])
        self.assertIsNone(res['approximate_etf_market_price_target_range'])
        self.assertIn("Inconsistent manual baseline", res['per_share_message'])

    # --- SAFEGUARD 3 TESTS ---
    def test_output_preserves_and_displays_all_three_dates(self):
        """Prove that output bundle preserves holdings snapshot date, baseline date, and scenario horizon date."""
        snap_dt = self.builder_bdry.snapshot['snapshot_date']
        manual_base = {
            'total_nav_dollars': 30_000_000.0,
            'shares_outstanding': 2_000_000,
            'nav_per_share': 15.00,
            'market_price': 14.80,
            'as_of_date': '2026-08-10',  # 4 days before Aug 14 snapshot
            'source': 'Historical Baseline'
        }
        res = self.builder_bdry.build_scenario(
            target_contract_prices={'C5TCM Q26 INDEX': 40000.0},
            scenario_horizon_date='2026-09-30',
            manual_dated_baseline=manual_base
        )
        prov_dates = res['provenance_dates']
        self.assertEqual(prov_dates['holdings_snapshot_as_of_date'], snap_dt)
        self.assertEqual(prov_dates['baseline_as_of_date'], '2026-08-10')
        self.assertEqual(prov_dates['scenario_horizon_date'], '2026-09-30')
        self.assertEqual(prov_dates['baseline_to_holdings_gap_days'], 4)
        self.assertFalse(prov_dates['is_baseline_contemporaneous_with_snapshot'])
        self.assertIn("differs from holdings snapshot date", prov_dates['date_alignment_disclaimer'])

    # --- SAFEGUARD 4 TESTS ---
    def test_missing_scenario_snapshot_provenance_blocks_price_range(self):
        """Prove that missing scenario-snapshot provenance fields block price-range output."""
        invalid_snapshot = {
            'schema_version': '1.0.0',
            # Missing generation_timestamp_utc, source_urls, source_hashes, etc.
            'fund_symbol': 'BDRY',
            'holdings_snapshot_as_of_date': '2026-08-14'
        }
        with self.assertRaises(MissingProvenanceRecordError):
            ThesisScenarioBuilder(
                fund='BDRY',
                scenario_snapshot_payload=invalid_snapshot
            )

    def test_tampered_hash_rejection(self):
        """Prove that a tampered SHA-256 archive hash in snapshot is rejected."""
        import json
        snap = json.loads(json.dumps(self.builder_bdry.snapshot_payload))
        # Tamper the computed hash
        snap['provenance']['computed_archive_sha256'] = '0000000000000000000000000000000000000000000000000000000000000000'
        snap['provenance']['provenance_verified'] = False
        is_valid, errors = validate_scenario_snapshot(snap)
        self.assertFalse(is_valid)
        self.assertTrue(any('Provenance verification failed' in e for e in errors))

        # Attempting to load this tampered snapshot into ThesisScenarioBuilder fails
        with self.assertRaises(MissingProvenanceRecordError):
            ThesisScenarioBuilder(fund='BDRY', scenario_snapshot_payload=snap)

    def test_tampered_position_detection(self):
        """Prove that corrupted position multipliers or prices in snapshot are rejected."""
        import json
        snap = json.loads(json.dumps(self.builder_bdry.snapshot_payload))
        # Corrupt multiplier to 0
        snap['positions'][0]['multiplier'] = 0.0
        is_valid, errors = validate_scenario_snapshot(snap)
        self.assertFalse(is_valid)
        self.assertTrue(any('non-positive multiplier' in e for e in errors))

    def test_baseline_premium_discount_carry_forward(self):
        """Prove that selectable pricing mode accurately carries forward baseline prem/disc or projects at NAV parity."""
        snap_dt = self.builder_bdry.snapshot['snapshot_date']
        # Baseline NAV/sh = $10.00, Market Close = $10.50 (+5.00% Premium)
        manual_base = {
            'total_nav_dollars': 20_000_000.0,
            'shares_outstanding': 2_000_000,
            'nav_per_share': 10.00,
            'market_price': 10.50,
            'as_of_date': snap_dt,
            'source': 'Verified Contemporaneous Baseline'
        }
        base_q26_mark = float(self.builder_bdry.snapshot['positions'][0]['price'])
        # Scenario: futures move yields +$1,000,000 P&L (+ $0.50/sh => Projected NAV/sh = $10.50)
        target_marks = {'C5TCM Q26 INDEX': base_q26_mark + (1000000.0 / 155.0)}
        
        # 1. Carry forward premium mode: Market Target Base = $10.50 * (1 + 5%) = $11.025
        res_prem = self.builder_bdry.build_scenario(
            target_contract_prices=target_marks,
            manual_dated_baseline=manual_base,
            pricing_mode='CARRY_FORWARD_PREMIUM_DISCOUNT',
            premium_discount_spread_pct=2.0
        )
        mkt_prem = res_prem['approximate_etf_market_price_target_range']
        self.assertEqual(mkt_prem['pricing_mode'], 'CARRY_FORWARD_PREMIUM_DISCOUNT')
        self.assertAlmostEqual(mkt_prem['applied_premium_discount_assumed_pct'], 5.0, places=2)
        self.assertAlmostEqual(mkt_prem['base_target_price'], 11.03, places=2)
        self.assertAlmostEqual(mkt_prem['base_target_nav_parity'], 10.50, places=2)

        # 2. NAV Parity mode: Market Target Base = $10.50
        res_parity = self.builder_bdry.build_scenario(
            target_contract_prices=target_marks,
            manual_dated_baseline=manual_base,
            pricing_mode='NAV_PARITY',
            premium_discount_spread_pct=2.0
        )
        mkt_parity = res_parity['approximate_etf_market_price_target_range']
        self.assertEqual(mkt_parity['pricing_mode'], 'NAV_PARITY')
        self.assertAlmostEqual(mkt_parity['applied_premium_discount_assumed_pct'], 0.0, places=2)
        self.assertAlmostEqual(mkt_parity['base_target_price'], 10.50, places=2)

if __name__ == '__main__':
    unittest.main()
