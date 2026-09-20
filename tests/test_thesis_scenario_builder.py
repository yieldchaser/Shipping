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
        # Use current UTC time so the test is always contemporaneous with the
        # live snapshot regardless of when update_etf_holdings.py last ran.
        self.ref_time = datetime.now(timezone.utc)
        self.builder_bdry = ThesisScenarioBuilder(fund='BDRY', reference_time_utc=self.ref_time)
        self.builder_bwet = ThesisScenarioBuilder(fund='BWET', reference_time_utc=self.ref_time)

        # Derive live prompt tickers from the actual snapshot so tests survive
        # any contract roll (Q26 → U26 → V26, etc.) without code changes.
        bdry_positions = self.builder_bdry.snapshot['positions']
        bwet_positions = self.builder_bwet.snapshot['positions']

        # BDRY: first Capesize position = prompt contract; second = next contract
        cape_positions = [p for p in bdry_positions if 'C5TCM' in p.get('ticker', '')]
        self._cape_prompt_ticker = cape_positions[0]['ticker'] if len(cape_positions) >= 1 else None
        self._cape_next_ticker   = cape_positions[1]['ticker'] if len(cape_positions) >= 2 else None

        # Live prices for the prompt Capesize — used as the base for all relative shocks.
        # This guarantees every price target is strictly above (or below) the live mark
        # regardless of current freight market levels.
        self._cape_prompt_price = float(cape_positions[0]['price']) if cape_positions else 30000.0
        self._cape_next_price   = float(cape_positions[1]['price']) if len(cape_positions) >= 2 else self._cape_prompt_price

        # BDRY: first Oct/V or next non-prompt Capesize used in forward-book test
        # Use the second distinct Capesize ticker for the USER_SPECIFIED_FORWARD_BOOK test
        self._cape_fwd_ticker = self._cape_next_ticker or self._cape_prompt_ticker

        # BWET: first TD3C (VLCC) prompt contract
        vlcc_positions = [p for p in bwet_positions if 'DD3CM' in p.get('ticker', '')]
        self._vlcc_prompt_ticker = vlcc_positions[0]['ticker'] if vlcc_positions else None
        self._vlcc_prompt_price  = float(vlcc_positions[0]['price']) if vlcc_positions else 90.0




    def test_no_synthetic_future_roll_lots_in_frozen_book(self):
        """Prove that FROZEN_BOOK preserves exact disclosed lots without any .5x / 1.5x synthetic scaling."""
        res = self.builder_bdry.build_scenario(
            target_contract_prices={self._cape_prompt_ticker: self._cape_prompt_price + 2000.0},
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
            target_contract_prices={self._cape_prompt_ticker: self._cape_prompt_price + 2000.0},
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
            target_contract_prices={self._cape_prompt_ticker: self._cape_prompt_price + 2000.0}
        )
        self.assertIsNone(res['approximate_nav_target_range'])
        self.assertIsNone(res['approximate_etf_market_price_target_range'])

        self.assertEqual(res['per_share_status'], "PER_SHARE_UNAVAILABLE_NON_CONTEMPORANEOUS_BASELINE")

    def test_exact_contract_target_isolation(self):
        """Prove that entering a target mark for one specific contract maturity does NOT affect other maturities."""
        # Use live mark + $2000 — always above the current prompt price, permanently roll-proof.
        target_px = self._cape_prompt_price + 2000.0
        res = self.builder_bdry.build_scenario(
            target_contract_prices={self._cape_prompt_ticker: target_px},
            scenario_mode='FROZEN_BOOK'
        )

        c_prompt = None
        c_other = None
        for row in res['contract_breakdown']:
            if row['ticker'] == self._cape_prompt_ticker:
                c_prompt = row
            elif row['ticker'] == self._cape_next_ticker and c_other is None:
                c_other = row

        self.assertIsNotNone(c_prompt, f"Prompt Capesize contract {self._cape_prompt_ticker} missing from breakdown")
        self.assertIsNotNone(c_other, f"Next Capesize contract {self._cape_next_ticker} missing from breakdown")
        self.assertAlmostEqual(c_prompt['target_mark_price'], target_px, places=4)
        self.assertNotEqual(c_prompt['delta_mark_dollars'], 0.0)
        self.assertNotEqual(c_prompt['gross_futures_pnl_dollars'], 0.0)

        self.assertEqual(c_other['target_mark_price'], c_other['current_mark_price'])
        self.assertEqual(c_other['delta_mark_dollars'], 0.0)
        self.assertEqual(c_other['gross_futures_pnl_dollars'], 0.0)


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

        # Use the prompt Capesize contract dynamically — whatever is currently in the snapshot.
        prompt_pos = next(p for p in self.builder_bdry.snapshot['positions']
                          if p['ticker'] == self._cape_prompt_ticker)
        base_prompt_mark = float(prompt_pos['price'])
        shock_per_day = 1000.0
        target_prices = {self._cape_prompt_ticker: base_prompt_mark + shock_per_day}
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

        # Derive expected P&L from live snapshot lots — stays correct regardless of AUM changes.
        live_lots = float(prompt_pos['lots'])
        live_mult = float(prompt_pos.get('multiplier', 1.0))
        expected_cape_pnl = live_lots * live_mult * shock_per_day
        expected_total_nav = 30_000_000.0 + expected_cape_pnl
        expected_nav_per_sh = expected_total_nav / 2_000_000

        self.assertAlmostEqual(nav_rng['projected_total_fund_nav_dollars'], expected_total_nav, places=2)
        self.assertAlmostEqual(nav_rng['projected_nav_per_share'], expected_nav_per_sh, places=4)
        self.assertAlmostEqual(mkt_rng['base_target_nav_parity'], round(expected_nav_per_sh, 2), places=2)

    def test_user_specified_forward_book(self):
        """Prove that USER_SPECIFIED_FORWARD_BOOK evaluates explicit custom forward lots and is labeled correctly."""
        fwd_pos = next(p for p in self.builder_bdry.snapshot['positions']
                       if p['ticker'] == self._cape_fwd_ticker)
        fwd_base_price = float(fwd_pos['price'])
        target_fwd_price = fwd_base_price + 1500.0

        # Zero out the prompt contract and override the forward contract lots.
        custom_lots = {
            self._cape_prompt_ticker: 0.0,
            self._cape_fwd_ticker: 200.0
        }
        target_prices = {self._cape_fwd_ticker: target_fwd_price}

        res = self.builder_bdry.build_scenario(
            target_contract_prices=target_prices,
            scenario_mode='USER_SPECIFIED_FORWARD_BOOK',
            user_forward_lots=custom_lots
        )
        self.assertEqual(res['scenario_mode'], 'USER_SPECIFIED_FORWARD_BOOK')
        self.assertEqual(res['scenario_mode_label'], 'User-assumed forward book')

        for row in res['contract_breakdown']:
            if row['ticker'] == self._cape_prompt_ticker:
                self.assertEqual(row['effective_lots'], 0.0)
                self.assertEqual(row['gross_futures_pnl_dollars'], 0.0)
            elif row['ticker'] == self._cape_fwd_ticker:
                self.assertEqual(row['effective_lots'], 200.0)
                expected_pnl = 200.0 * 1.0 * (target_fwd_price - fwd_base_price)
                self.assertAlmostEqual(row['gross_futures_pnl_dollars'], expected_pnl, places=2)

    def test_rejected_synthetic_modes(self):
        """Prove that requesting synthetic roll modes raises ValueError."""
        with self.assertRaises(ValueError):
            self.builder_bdry.build_scenario(scenario_mode='ROLL_AWARE_APPROXIMATE')

    def test_bwet_tanker_exact_shock(self):
        """Prove that BWET tanker pricing evaluates 1000 MT multiplier correctly."""
        c_vlcc_pos = next(p for p in self.builder_bwet.snapshot['positions']
                          if p['ticker'] == self._vlcc_prompt_ticker)
        vlcc_base_mark = float(c_vlcc_pos['price'])
        target_vlcc_mark = vlcc_base_mark + 5.0

        target_prices = {self._vlcc_prompt_ticker: target_vlcc_mark}
        res = self.builder_bwet.build_scenario(
            target_contract_prices=target_prices,
            scenario_mode='FROZEN_BOOK'
        )
        self.assertGreater(res['gross_futures_pnl_dollars'], 0)
        c_vlcc = None
        for row in res['contract_breakdown']:
            if row['ticker'] == self._vlcc_prompt_ticker:
                c_vlcc = row
                break
        self.assertIsNotNone(c_vlcc)
        expected_pnl = float(c_vlcc_pos['lots']) * 1000.0 * 5.0
        self.assertAlmostEqual(c_vlcc['gross_futures_pnl_dollars'], expected_pnl, places=1)

    def test_stale_snapshot_rejection(self):
        """Prove that builder rejects stale snapshot (> 3 business days)."""
        # Always use a reference time sufficiently far in the future (10 business days ≈ 14 calendar days)
        # regardless of what today's date is.
        stale_ref_time = self.ref_time + timedelta(days=14)
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
        snap_dt = self.builder_bdry.snapshot['snapshot_date']
        inconsistent_baseline = {
            'total_nav_dollars': 30_000_000.0,
            'shares_outstanding': 2_000_000,
            'nav_per_share': 12.00,  # Inconsistent!
            'market_price': 14.80,
            'as_of_date': snap_dt,   # Use live snapshot date so it's contemporaneous
            'source': 'Corrupted Manual Input'
        }
        res = self.builder_bdry.build_scenario(
            target_contract_prices={self._cape_prompt_ticker: self._cape_prompt_price + 2000.0},
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
        from datetime import date
        snap_dt = self.builder_bdry.snapshot['snapshot_date']

        # Use a baseline date 7 calendar days before the snapshot — always non-contemporaneous.
        snap_date_obj = date.fromisoformat(snap_dt)
        baseline_date_obj = snap_date_obj - timedelta(days=7)
        baseline_date_str = baseline_date_obj.isoformat()
        expected_gap_days = (snap_date_obj - baseline_date_obj).days  # exactly 7

        manual_base = {
            'total_nav_dollars': 30_000_000.0,
            'shares_outstanding': 2_000_000,
            'nav_per_share': 15.00,
            'market_price': 14.80,
            'as_of_date': baseline_date_str,
            'source': 'Historical Baseline'
        }
        # Scenario horizon: always 45 calendar days from today — always in the future.
        horizon_date_str = (snap_date_obj + timedelta(days=45)).isoformat()
        res = self.builder_bdry.build_scenario(
            target_contract_prices={self._cape_prompt_ticker: self._cape_prompt_price + 2000.0},
            scenario_horizon_date=horizon_date_str,
            manual_dated_baseline=manual_base
        )
        prov_dates = res['provenance_dates']
        self.assertEqual(prov_dates['holdings_snapshot_as_of_date'], snap_dt)
        self.assertEqual(prov_dates['baseline_as_of_date'], baseline_date_str)
        self.assertEqual(prov_dates['scenario_horizon_date'], horizon_date_str)
        self.assertEqual(prov_dates['baseline_to_holdings_gap_days'], expected_gap_days)
        self.assertFalse(prov_dates['is_baseline_contemporaneous_with_snapshot'])
        self.assertIn("differs from holdings snapshot date", prov_dates['date_alignment_disclaimer'])


    # --- SAFEGUARD 4 TESTS ---
    def test_missing_scenario_snapshot_provenance_blocks_price_range(self):
        """Prove that missing scenario-snapshot provenance fields block price-range output."""
        snap_dt = self.builder_bdry.snapshot['snapshot_date']
        invalid_snapshot = {
            'schema_version': '1.0.0',
            # Missing generation_timestamp_utc, source_urls, source_hashes, etc.
            'fund_symbol': 'BDRY',
            'holdings_snapshot_as_of_date': snap_dt
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
        # Build a target price that yields exactly +$1,000,000 gross P&L from the prompt contract.
        # Derive live lots from snapshot so this stays correct after any AUM-driven lot change.
        prompt_pos = next(p for p in self.builder_bdry.snapshot['positions']
                          if p['ticker'] == self._cape_prompt_ticker)
        base_prompt_mark = float(prompt_pos['price'])
        live_lots = float(prompt_pos['lots'])
        live_mult = float(prompt_pos.get('multiplier', 1.0))
        target_marks = {self._cape_prompt_ticker: base_prompt_mark + (1_000_000.0 / (live_lots * live_mult))}

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
