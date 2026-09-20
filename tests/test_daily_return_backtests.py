"""
Unit Tests for Contract-Spec Registry, Dynamic Snapshot Loader, and Daily Return Engine
========================================================================================
Tests:
1. Strict explicit identifier resolution (SGX/CME rulebook citations, unknown contracts fail closed).
2. Dynamic snapshot loader loads verified on-disk snapshots and handles missing dated shares.
3. Multi-period SEC Form 10-Q cross-checks match CFTC monthly ledgers.
4. Daily Dollar-P&L decomposition flags interim daily sessions as DESCRIPTIVE_UNRECONCILED.
"""

import unittest
import pandas as pd
import numpy as np
from contract_spec_registry import resolve_contract_spec, UnknownContractSpecError, get_authoritative_multiplier
from current_book_manual_shock import load_latest_official_snapshot, calculate_manual_contract_shock
from cross_check_cftc_10q import run_cross_checks
from run_daily_return_backtests import run_daily_dollar_decomposition

class TestAccountingGovernanceAndDecomposition(unittest.TestCase):
    def test_contract_spec_registry_strict_fail_closed(self):
        # 1. Authoritative multipliers via explicit Ticker/CUSIP
        self.assertEqual(get_authoritative_multiplier("Capesize 5TC", ticker="C5TCM Q26 INDEX", cusip="C5TCM Q26", fund="BDRY"), 1.0)
        self.assertEqual(get_authoritative_multiplier("Panamax 4TC", ticker="P5TCM U26 INDEX", cusip="P5TCM U26", fund="BDRY"), 1.0)
        self.assertEqual(get_authoritative_multiplier("Supramax 10TC", ticker="S58FM M26 INDEX", cusip="S58FM M26", fund="BDRY"), 1.0)
        self.assertEqual(get_authoritative_multiplier("TD3C FFA", ticker="DD3CM Q26 INDEX", cusip="DD3CM Q26", fund="BWET"), 1000.0)
        self.assertEqual(get_authoritative_multiplier("TD20 FFA", ticker="DD20M N26 INDEX", cusip="DD20M N26", fund="BWET"), 1000.0)
        
        # 2. Unknown contract must fail closed (never default to 1.0)
        with self.assertRaises(UnknownContractSpecError):
            resolve_contract_spec("Arbitrary Unregistered Commodity", ticker="UNREG", cusip="UNREG", fund="BDRY")

    def test_dynamic_snapshot_loader_latest_holdings(self):
        # BDRY latest snapshot
        snap_bdry = load_latest_official_snapshot('BDRY', max_stale_business_days=3)
        self.assertEqual(snap_bdry['fund'], 'BDRY')
        self.assertGreaterEqual(snap_bdry['snapshot_date'], '2026-08-13')
        self.assertGreater(snap_bdry['positions_count'], 10)
        self.assertEqual(len(snap_bdry['provenance_record']['expected_sha256']), 64)
        
        # BWET latest snapshot
        snap_bwet = load_latest_official_snapshot('BWET', max_stale_business_days=3)
        self.assertEqual(snap_bwet['fund'], 'BWET')
        self.assertGreaterEqual(snap_bwet['snapshot_date'], '2026-08-13')
        self.assertGreater(snap_bwet['positions_count'], 5)
        
        # Run shock and assert per-share conversion is unavailable when dated shares missing
        res = calculate_manual_contract_shock(snap_bdry, {})
        self.assertEqual(res['share_conversion_status'], 'PER_SHARE_UNAVAILABLE_MISSING_SAME_DATE_SHARES')
        self.assertIsNone(res['delta_nav_per_share_dollars'])

    def test_multi_quarter_sec_10q_cross_checks(self):
        res = run_cross_checks()
        for key, v in res.items():
            self.assertTrue(v['passed'], f"Cross check failed for {key}")
            self.assertLessEqual(v['nav_diff_dollars'], 1.0)
            self.assertEqual(v['shares_diff'], 0)
            self.assertLess(v['nav_sh_diff'], 0.01)

    def test_daily_dollar_pnl_decomposition_and_gates(self):
        df_bdry, rep_bdry = run_daily_dollar_decomposition('BDRY')
        self.assertFalse(df_bdry.empty)
        self.assertIn('reconciliation_status', df_bdry.columns)
        self.assertIn('futures_vm_retained_dollars', df_bdry.columns)
        # Verify that interim days lacking total fund NAV are marked DESCRIPTIVE_UNRECONCILED
        self.assertGreater(rep_bdry['unreconciled_interim_sessions_count'], 20)
        self.assertEqual(rep_bdry['genuinely_reconciled_sessions_count'], 0)
        self.assertIn('NO_ACCURACY_VERDICT_ISSUED', rep_bdry['tracking_accuracy_verdict'])

if __name__ == '__main__':
    unittest.main()
