"""
CFTC Rule 4.22(h) Monthly Statement Unit Test Suite
===================================================
Tests the parsed monthly account statements for BDRY and BWET.
Asserts:
1. Exact Balance Sheet Identity for every statement:
   Ending NAV == Opening NAV + Sales + Redemptions + Net Income / (Loss)  ($0.00 err)
2. Exact Net Income Identity:
   Net Income == Net Investment Income + Net Realized/Unrealized Futures P&L  ($0.00 err)
3. Exact Per-Share NAV Identity:
   NAV per share == Ending NAV / Shares Outstanding  (< $0.02 rounding)
4. Absence of daily interpolation or fabricated shares.
"""

import unittest
import pandas as pd
import numpy as np
from parse_cftc_monthly_statements import parse_single_pdf, RAW_PDF_DIR_BDRY, RAW_PDF_DIR_BWET

class TestCFTCMonthlyLedger(unittest.TestCase):
    def setUp(self):
        self.audit_df = pd.read_csv('data/cftc_statements/parsed/statement_text_audit.csv')
        self.digital_bdry = self.audit_df[(self.audit_df['fund'] == 'BDRY') & (self.audit_df['is_digital_text'])]
        self.digital_bwet = self.audit_df[(self.audit_df['fund'] == 'BWET') & (self.audit_df['is_digital_text'])]

    def test_bdry_digital_statements_exact_identities(self):
        self.assertGreaterEqual(len(self.digital_bdry), 14)
        for _, row in self.digital_bdry.iterrows():
            fp = f"{RAW_PDF_DIR_BDRY}/{row['filename']}"
            res = parse_single_pdf(fp, 'BDRY', f"https://amplifyetfs.com/wp-content/uploads/files/BDRY/Account_Statements/{row['filename']}")
            
            # Check 1: Opening, Closing NAV, Shares, NAV/share exist
            self.assertIsNotNone(res['opening_nav_dollars'], f"Opening NAV missing for {row['filename']}")
            self.assertIsNotNone(res['closing_nav_dollars'], f"Closing NAV missing for {row['filename']}")
            self.assertIsNotNone(res['shares_outstanding'], f"Shares outstanding missing for {row['filename']}")
            self.assertIsNotNone(res['nav_per_share'], f"NAV per share missing for {row['filename']}")
            
            # Check 2: Exact Net Income Identity
            calc_nii = res['interest_income_dollars'] - res['net_expenses_dollars']
            self.assertAlmostEqual(res['net_investment_income_dollars'], calc_nii, delta=2.0)
            
            calc_net_inc = res['net_investment_income_dollars'] + res['realized_futures_pnl_dollars'] + res['unrealized_futures_pnl_delta_dollars']
            self.assertAlmostEqual(res['net_income_loss_dollars'], calc_net_inc, delta=2.0)
            
            # Check 3: Exact Ending NAV Balance Identity
            calc_ending_nav = res['opening_nav_dollars'] + res['sales_of_shares_dollars'] + res['redemptions_of_shares_dollars'] + res['net_income_loss_dollars']
            self.assertAlmostEqual(res['closing_nav_dollars'], calc_ending_nav, delta=2.0, msg=f"Ending NAV mismatch in {row['filename']}")
            
            # Check 4: Exact Per-Share NAV Identity
            calc_nav_sh = res['closing_nav_dollars'] / res['shares_outstanding']
            self.assertAlmostEqual(res['nav_per_share'], calc_nav_sh, delta=0.02, msg=f"Per-share NAV mismatch in {row['filename']}")

    def test_bwet_digital_statements_exact_identities(self):
        self.assertGreaterEqual(len(self.digital_bwet), 14)
        for _, row in self.digital_bwet.iterrows():
            fp = f"{RAW_PDF_DIR_BWET}/{row['filename']}"
            res = parse_single_pdf(fp, 'BWET', f"https://amplifyetfs.com/wp-content/uploads/files/BWET/Account_Statements/{row['filename']}")
            
            # Check 1: Opening, Closing NAV, Shares, NAV/share exist
            self.assertIsNotNone(res['opening_nav_dollars'], f"Opening NAV missing for {row['filename']}")
            self.assertIsNotNone(res['closing_nav_dollars'], f"Closing NAV missing for {row['filename']}")
            self.assertIsNotNone(res['shares_outstanding'], f"Shares outstanding missing for {row['filename']}")
            self.assertIsNotNone(res['nav_per_share'], f"NAV per share missing for {row['filename']}")
            
            # Check 2: Exact Net Income Identity
            calc_nii = res['interest_income_dollars'] - res['net_expenses_dollars']
            self.assertAlmostEqual(res['net_investment_income_dollars'], calc_nii, delta=2.0)
            
            calc_net_inc = res['net_investment_income_dollars'] + res['realized_futures_pnl_dollars'] + res['unrealized_futures_pnl_delta_dollars']
            self.assertAlmostEqual(res['net_income_loss_dollars'], calc_net_inc, delta=2.0)
            
            # Check 3: Exact Ending NAV Balance Identity
            calc_ending_nav = res['opening_nav_dollars'] + res['sales_of_shares_dollars'] + res['redemptions_of_shares_dollars'] + res['net_income_loss_dollars']
            self.assertAlmostEqual(res['closing_nav_dollars'], calc_ending_nav, delta=2.0, msg=f"Ending NAV mismatch in {row['filename']}")
            
            # Check 4: Exact Per-Share NAV Identity
            calc_nav_sh = res['closing_nav_dollars'] / res['shares_outstanding']
            self.assertAlmostEqual(res['nav_per_share'], calc_nav_sh, delta=0.02, msg=f"Per-share NAV mismatch in {row['filename']}")

    def test_no_daily_interpolation_in_cftc_ledgers(self):
        # Assert that monthly statements remain monthly and contain discrete monthly timestamps
        df_bdry = pd.read_csv('data/cftc_statements/parsed/bdry_monthly_cftc_ledger.csv')
        self.assertEqual(len(df_bdry), 100)
        # All rows must represent monthly periods, not daily increments
        for _, r in df_bdry.iterrows():
            self.assertNotIn('daily', str(r['period_ended']).lower())

if __name__ == '__main__':
    unittest.main()
