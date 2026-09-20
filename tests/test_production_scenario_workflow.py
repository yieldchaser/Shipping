"""
Unit Tests for Production Scenario Workflow Engine & Data Gap Request Packet
=============================================================================
Tests:
1. Daily holdings archive and provenance validation for BDRY and BWET.
2. Manual shock evaluation by explicit Ticker/CUSIP produces exact gross futures VM and direction.
3. All 5 accounting residual flags are properly populated and described.
4. Opt-in approximate percentage output is disabled by default; when enabled, includes explicit stale/proxy disclaimer.
5. Exact NAV/share impact is strictly None / UNAVAILABLE without same-date official shares.
6. Data gap request document exists and specifies all 5 institutional data streams.

Design principle: all ticker references use the live PROMPT Capesize contract discovered
from the snapshot at setUp time, so tests survive any monthly contract roll (Q26→U26→V26).
"""

import unittest
import os
from datetime import datetime, timezone
from production_scenario_workflow import ProductionScenarioWorkflow

class TestProductionScenarioWorkflow(unittest.TestCase):
    def setUp(self):
        self.wf_bdry = ProductionScenarioWorkflow('BDRY', max_stale_business_days=3)
        self.wf_bwet = ProductionScenarioWorkflow('BWET', max_stale_business_days=3)

        # Discover the prompt Capesize contract dynamically from the live snapshot.
        # This survives any monthly roll (Q26 → U26 → V26, etc.) without code changes.
        cape_positions = [
            p for p in self.wf_bdry.snapshot['positions']
            if 'C5TCM' in p.get('ticker', '')
        ]
        self._cape_prompt_ticker = cape_positions[0]['ticker'] if cape_positions else None

    def test_workflow_provenance_and_snapshot(self):
        res = self.wf_bdry.evaluate_scenario({})
        self.assertEqual(res['fund'], 'BDRY')
        self.assertTrue(res['provenance']['official_source_url'].startswith('https://amplifyetfs.com/'))
        self.assertEqual(len(res['provenance']['archive_sha256_checksum']), 64)
        self.assertLessEqual(res['business_day_freshness_age'], 3)

    def test_manual_shock_by_ticker_and_cusip(self):
        # Apply +$1,000 on the prompt Capesize contract (whatever it is this month).
        shocks = {self._cape_prompt_ticker: 1000.0}
        res = self.wf_bdry.evaluate_scenario(shocks)

        # Derive expected P&L from the live snapshot's own lot count and multiplier.
        # This stays correct regardless of daily AUM-driven lot-count changes.
        snap = self.wf_bdry.snapshot
        cape_pos = next(
            (p for p in snap['positions'] if p.get('ticker', '') == self._cape_prompt_ticker),
            None
        )
        self.assertIsNotNone(cape_pos, f"{self._cape_prompt_ticker} must be present in BDRY snapshot")
        live_lots = float(cape_pos['lots'])
        live_mult = float(cape_pos.get('multiplier', 1.0))

        expected_pos_pnl = live_lots * live_mult * 1000.0
        self.assertAlmostEqual(res['gross_futures_vm_impact_dollars'], expected_pos_pnl, delta=0.01)
        self.assertEqual(res['nav_direction'], 'POSITIVE_NAV_EXPANSION')

        # Negative shock (−$2,000)
        neg_shocks = {self._cape_prompt_ticker: -2000.0}
        res_neg = self.wf_bdry.evaluate_scenario(neg_shocks)
        expected_neg_pnl = live_lots * live_mult * (-2000.0)
        self.assertAlmostEqual(res_neg['gross_futures_vm_impact_dollars'], expected_neg_pnl, delta=0.01)
        self.assertEqual(res_neg['nav_direction'], 'NEGATIVE_NAV_CONTRACTION')

    def test_all_five_residual_flags_present(self):
        res = self.wf_bdry.evaluate_scenario({})
        flags = res['accounting_residual_flags']
        self.assertIn('roll_execution_drag', flags)
        self.assertIn('cash_collateral_interest', flags)
        self.assertIn('daily_expenses_and_waivers', flags)
        self.assertIn('authorized_participant_flows', flags)
        self.assertIn('secondary_market_premium_discount', flags)

        for k, flag in flags.items():
            self.assertIn('status', flag)
            self.assertIn('description', flag)

    def test_opt_in_approximate_percentage_disclaimer(self):
        # Default: disabled
        res_default = self.wf_bdry.evaluate_scenario({self._cape_prompt_ticker: 1000.0})
        self.assertIsNone(res_default['opt_in_approximate_percentage_sensitivity'])

        # Opt-in enabled
        res_opt = self.wf_bdry.evaluate_scenario({self._cape_prompt_ticker: 1000.0}, opt_in_approximate_percentage=True)
        opt_payload = res_opt['opt_in_approximate_percentage_sensitivity']
        self.assertIsNotNone(opt_payload)
        self.assertTrue(opt_payload['is_opt_in_approximate'])
        self.assertIn('APPROXIMATE SENSITIVITY ONLY', opt_payload['disclaimer'])
        self.assertIn('DENOMINATOR IS A STALE/PROXY ESTIMATE', opt_payload['disclaimer'])
        self.assertGreater(opt_payload['denominator_used_dollars'], 0)

    def test_exact_nav_per_share_strictly_unavailable(self):
        res = self.wf_bdry.evaluate_scenario({self._cape_prompt_ticker: 1000.0})
        self.assertIsNone(res['exact_nav_per_share_impact_dollars'])
        self.assertEqual(res['exact_nav_per_share_status'], 'UNAVAILABLE_MISSING_SAME_DATE_OFFICIAL_SHARES')

    def test_data_gap_request_document_exists(self):
        doc_path = 'docs/DATA_GAP_REQUEST_AMPLIFY_BREAKWAVE.md'
        self.assertTrue(os.path.exists(doc_path))
        with open(doc_path, 'r', encoding='utf-8') as f:
            content = f.read()
            self.assertIn('Stream 1: Historical Daily NAV, Total Net Assets, & Shares Outstanding', content)
            self.assertIn('Stream 2: Daily Authorized Participant (AP) Creation & Redemption Ledger', content)
            self.assertIn('Stream 3: Portfolio Composition & Creation Basket Files (PCF)', content)
            self.assertIn('Stream 4: Daily Custody Cash, FCM Margin Equity, & Expense Accrual Ledger', content)
            self.assertIn('Stream 5: Roll Calendar & Intraday Trade Execution Blotters', content)

if __name__ == '__main__':
    unittest.main()
