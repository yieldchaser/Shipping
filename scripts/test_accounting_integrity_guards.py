"""
Accounting Engine Integrity Guards Test Suite
=============================================
Automated unit tests asserting:
1. Zero look-ahead or backward fill in NAV lookups (returns NaN on missing dates).
2. Zero fabricated share-count defaults (returns NaN when dated ledger is absent).
3. Zero false FULLY_RECONCILED rows without every required voucher.
4. Complete decoupling of market-close availability from NAV accounting status.
"""

import unittest
import numpy as np
import pandas as pd
from etf_true_waterfall_engine import (
    get_exact_official_nav,
    load_official_flows,
    run_fund_level_nav_reconstruction
)

class TestAccountingIntegrityGuards(unittest.TestCase):
    def setUp(self):
        self.bdry_flows = load_official_flows('bdry')
        self.bwet_flows = load_official_flows('bwet')

    def test_no_nav_lookahead_or_backfill(self):
        # 2026-06-21 is a Sunday. Exact lookup must return NaN without looking ahead to Monday June 22.
        sunday_nav = get_exact_official_nav('2026-06-21', self.bdry_flows)
        self.assertTrue(np.isnan(sunday_nav), "Sunday 2026-06-21 must be NaN; look-ahead forward/backward search is prohibited.")
        
        # A missing unobserved date must return NaN without backward-filling previous dates.
        missing_nav = get_exact_official_nav('2099-01-01', self.bdry_flows)
        self.assertTrue(np.isnan(missing_nav), "Missing date 2099-01-01 must be NaN; backward search is prohibited.")

    def test_no_estimated_shares_in_reconstruction(self):
        res = run_fund_level_nav_reconstruction('bdry')
        tl = res['timeline']
        # Assert all reconstructed_nav, shares_outstanding, and total_nav_dollars are NaN (no synthetic defaults)
        for _, row in tl.iterrows():
            self.assertTrue(np.isnan(row['shares_outstanding']), "Shares outstanding must be NaN when dated ledger is unobserved.")
            self.assertTrue(np.isnan(row['reconstructed_nav']), "Reconstructed NAV must be NaN when share ledger and vouchers are unobserved.")
            self.assertTrue(np.isnan(row['total_nav_dollars']), "Total NAV dollars must be NaN when share ledger is unobserved.")

    def test_zero_fully_reconciled_without_vouchers(self):
        for k in ['bdry', 'bwet']:
            res = run_fund_level_nav_reconstruction(k)
            counts = res['counts']
            self.assertEqual(counts['fully_reconciled'], 0, f"{k.upper()} must have 0 FULLY_RECONCILED rows without daily bank/FCM vouchers.")
            self.assertGreater(counts['partial_unreconciled'], 30)

    def test_market_close_decoupled_from_nav(self):
        res = run_fund_level_nav_reconstruction('bdry')
        tl = res['timeline']
        # On 2026-08-11, official NAV ($13.79) was published
        aug11_rows = tl[tl['date'] == '2026-08-11']
        self.assertEqual(len(aug11_rows), 1)
        r = aug11_rows.iloc[0]
        self.assertIn(r['market_status'], ['AVAILABLE', 'MARKET_CLOSED'])
        self.assertAlmostEqual(r['official_nav'], 13.79, places=2)
        # Assert that presence/absence of market close does NOT force reconciliation_status to MISSING_INPUT
        self.assertEqual(r['reconciliation_status'], 'PARTIAL_DISCLOSURE_UNRECONCILED')

if __name__ == '__main__':
    unittest.main()
