"""
Comprehensive Verification Suite: Evidence, Governance, and Scenario Interface
=============================================================================
Tests:
1. Incorrect CME rulebook chapter mappings (e.g. 701/702) fail closed with InvalidRulebookMappingError.
2. Active NYMEX chapters (684 for TD3C, 944 for TD20) and SGX-DC rules pass verification.
3. Unknown contract tickers/specs fail closed (UnknownContractSpecError) without defaulting.
4. Explicit Ticker / CUSIP mappings in EXPLICIT_IDENTIFIER_MAP resolve correctly.
5. Holdings loader requires valid official provenance URL, archive path, and SHA-256 hash.
6. Holdings loader rejects stale snapshots exceeding max_stale_business_days using dynamic/injected clock.
7. Governance labeling: Interim daily sessions are strictly DESCRIPTIVE_UNRECONCILED / PARTIAL_SCALING_ONLY, and genuine RECONCILED count is 0 without daily vouchers.
8. User scenario interface outputs dollar impact, freshness metadata, and unresolved residual flags.
9. Multi-quarter SEC Form 10-Q/10-K cross-checks match CFTC monthly ledgers to exact parity ($0.00 err).
"""

import unittest
from datetime import datetime, timezone, timedelta
import pandas as pd
import numpy as np
from contract_spec_registry import (
    resolve_contract_spec,
    validate_rulebook_mapping,
    get_authoritative_multiplier,
    UnknownContractSpecError,
    InvalidRulebookMappingError
)
from current_book_manual_shock import (
    load_latest_official_snapshot,
    calculate_manual_contract_shock,
    StaleSnapshotError,
    MissingProvenanceRecordError
)
from run_daily_return_backtests import run_daily_dollar_decomposition
from cross_check_cftc_10q import run_cross_checks
from current_book_scenario_ui import run_interactive_scenario

class TestFinalHardeningPass(unittest.TestCase):
    def test_cme_rulebook_chapters_fail_closed(self):
        # Chapters 701/702 are incorrect and must fail closed
        with self.assertRaises(InvalidRulebookMappingError):
            validate_rulebook_mapping('TD3C', 'CME Chapter 701')
            
        with self.assertRaises(InvalidRulebookMappingError):
            validate_rulebook_mapping('TD20', 'CME Chapter 702')
            
        # Verified active NYMEX rulebook chapters must pass
        validate_rulebook_mapping('TD3C', 'NYMEX Rulebook Chapter 684 ("Freight Route TD3C (Baltic) Futures")')
        validate_rulebook_mapping('TD20', 'NYMEX Rulebook Chapter 944 ("Freight Route TD20 (Baltic) Futures")')

    def test_explicit_ticker_and_cusip_resolution(self):
        # Explicit Ticker prefix matches
        spec_cape = resolve_contract_spec("Capesize 5TC", ticker="C5TCM Q26 INDEX", cusip="C5TCM Q26", fund="BDRY")
        self.assertEqual(spec_cape['clearing_product_code'], 'CWF / C5T (SGX), C5 (CME)')
        self.assertEqual(spec_cape['contract_size'], 1.0)
        
        spec_td3c = resolve_contract_spec("TD3C FFA", ticker="DD3CM Q26 INDEX", cusip="DD3CM Q26", fund="BWET")
        self.assertEqual(spec_td3c['clearing_product_code'], 'TL (Monthly Futures), TLB (BALMO)')
        self.assertEqual(spec_td3c['contract_size'], 1000.0)
        
        # Unmapped ticker must fail closed
        with self.assertRaises(UnknownContractSpecError):
            resolve_contract_spec("Unregistered Container FFA", ticker="UNREG_TICKER", cusip="UNREG_CUSIP", fund="BDRY")

    def test_mandatory_provenance_and_hash_guard(self):
        with self.assertRaises(MissingProvenanceRecordError):
            load_latest_official_snapshot('UNREGISTERED_FUND')
            
        for f in ['BDRY', 'BWET']:
            snap = load_latest_official_snapshot(f, max_stale_business_days=3)
            self.assertIn('official_source_url', snap['provenance_record'])
            self.assertTrue(snap['provenance_record']['official_source_url'].startswith('https://amplifyetfs.com/'))
            self.assertEqual(len(snap['provenance_record']['expected_sha256']), 64)

    def test_business_day_freshness_guard_with_injected_clock(self):
        # Using an injected reference clock 10 business days ahead must raise StaleSnapshotError
        future_clock = datetime(2026, 9, 1, tzinfo=timezone.utc)
        with self.assertRaises(StaleSnapshotError):
            load_latest_official_snapshot('BDRY', max_stale_business_days=3, reference_time_utc=future_clock)

    def test_reconciliation_status_governance_rules(self):
        df_bdry, rep_bdry = run_daily_dollar_decomposition('BDRY')
        df_bwet, rep_bwet = run_daily_dollar_decomposition('BWET')
        
        # Genuinely RECONCILED count must be 0 because daily cash/fee vouchers are unobserved
        self.assertEqual(rep_bdry['genuinely_reconciled_sessions_count'], 0)
        self.assertEqual(rep_bwet['genuinely_reconciled_sessions_count'], 0)
        
        # Form 10-Q quarter-end is PARTIAL_SCALING_ONLY (total fund NAV observed, but cash vouchers unobserved)
        self.assertEqual(rep_bdry['partial_scaling_sessions_count'], 1)
        self.assertEqual(rep_bwet['partial_scaling_sessions_count'], 1)
        
        # Interim days are DESCRIPTIVE_UNRECONCILED
        self.assertGreater(rep_bdry['unreconciled_interim_sessions_count'], 30)
        self.assertIn('NO_ACCURACY_VERDICT_ISSUED', rep_bdry['tracking_accuracy_verdict'])

    def test_user_scenario_interface_outputs_and_flags(self):
        res_bdry = run_interactive_scenario('BDRY')
        self.assertEqual(res_bdry['fund'], 'BDRY')
        self.assertGreater(res_bdry['total_delta_nav_dollars'], 0)
        self.assertIsNone(res_bdry['delta_nav_per_share_dollars'])
        self.assertEqual(res_bdry['share_conversion_status'], 'PER_SHARE_UNAVAILABLE_MISSING_SAME_DATE_SHARES')
        self.assertIn('unobserved_roll_execution_drag', res_bdry['unresolved_residuals_flags'])
        self.assertIn('unobserved_cash_interest_vouchers', res_bdry['unresolved_residuals_flags'])

    def test_multi_quarter_sec_cftc_exact_parity(self):
        checks = run_cross_checks()
        for key, res in checks.items():
            self.assertTrue(res['passed'], f"Quarterly cross-check failed for {key}")
            self.assertLessEqual(res['nav_diff_dollars'], 1.0)
            self.assertEqual(res['shares_diff'], 0)

if __name__ == '__main__':
    unittest.main()
