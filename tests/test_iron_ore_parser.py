"""
Unit tests for the Hellenic MMI iron-ore parser hardening.

Regression context: OCR-mangled IOSI tags (IOSI6S, 10162, lOSIB), Fe-grade
tokens merged into data rows and monthly-average tables sharing the same tags
froze cfr_62 at exactly 62.5 for 52 straight trading days (Jun-Aug 2026).
These tests pin the fuzzy tag matcher, grade-token exclusion, continuity gate
and summary-row rejection that prevent each failure class.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import process_knowledge as pk


class TestMatchIosiTag(unittest.TestCase):

    def test_exact_tags_match(self):
        self.assertEqual(pk._match_iosi_tag("IOSI62 62% Fe Fines 99.95 -1.70"), "cfr_62")
        self.assertEqual(pk._match_iosi_tag("IOSI65 65% Fe Fines 119.30 -2.05"), "cfr_65")

    def test_ocr_mangled_tags_match(self):
        self.assertEqual(pk._match_iosi_tag("losi62 62% FeFines| 99.95 -1.70"), "cfr_62")
        self.assertEqual(pk._match_iosi_tag("10s162 62% FeFines 97.10"), "cfr_62")
        self.assertEqual(pk._match_iosi_tag("10162 62% FeFines 97.10"), "cfr_62")
        self.assertEqual(pk._match_iosi_tag("IOSI6S 65%FeFines 116.15"), "cfr_65")
        self.assertEqual(pk._match_iosi_tag("1lOSI65 65% Fe Fines, 262.50"), "cfr_65")

    def test_iopi_and_prose_do_not_match(self):
        self.assertIsNone(pk._match_iosi_tag("IOPI62 62% Fe Fines 748 -5"))
        self.assertIsNone(pk._match_iosi_tag("The DCE iron ore futures trended weaker today"))
        self.assertIsNone(pk._match_iosi_tag(""))

    def test_multi_tag_header_matches_preferred_series(self):
        line = "IOSI61 61% Fe Fines USD/dmt IOSI65 65% Fe Fines USD/dmt IOPLI 62.5% Fe Lump RMB/t"
        self.assertEqual(pk._match_iosi_tag(line), "cfr_65")


class TestIsIoSummaryRow(unittest.TestCase):

    def test_unit_legend_rows_rejected(self):
        self.assertTrue(pk._is_io_summary_row(
            "IOSI61 61% Fe Fines USD/dmt IOSI65 65% Fe Fines USD/dmt IOPLI 62.5% Fe Lump RMB/t"))

    def test_freight_contaminated_rows_rejected(self):
        self.assertTrue(pk._is_io_summary_row(
            "IOSI62 62% Fe Fines 169.25 178.57 W. Australia - Qingdao C5 10.87 -0.29%"))

    def test_period_average_headers_rejected(self):
        self.assertTrue(pk._is_io_summary_row("Index Fe Content February March April May MTD QTD YTD Route Designation"))

    def test_daily_price_rows_with_prose_accepted(self):
        self.assertFalse(pk._is_io_summary_row(
            "IOSI62 62% Fe Fines 100.85 -13.90 -12.11% 114.02 prices may soften in late July window"))
        self.assertFalse(pk._is_io_summary_row(
            "IOSI65 65% Fe Fines 119.30 -2.05 -1.69% 116.82"))


class TestPickCfrValue(unittest.TestCase):

    def test_skips_grade_tokens_then_takes_first_real_price(self):
        self.assertEqual(pk._pick_cfr_value([62.0, 99.95, -1.7, 103.84], None), 99.95)

    def test_header_trap_all_grades_returns_none(self):
        self.assertIsNone(pk._pick_cfr_value([5.0, 65.0, 62.5], None))

    def test_out_of_range_junk_skipped(self):
        self.assertEqual(pk._pick_cfr_value([98000.0, 0.1, 0.1, 103.45], None), 103.45)

    def test_continuity_gate_rejects_far_candidates(self):
        self.assertIsNone(pk._pick_cfr_value([214.8], 100.0))

    def test_continuity_gate_falls_back_to_near_candidate(self):
        self.assertEqual(pk._pick_cfr_value([190.0, 104.0, 108.0], 100.0), 104.0)

    def test_first_observation_without_prev_takes_first_candidate(self):
        self.assertEqual(pk._pick_cfr_value([62.0, 119.3, 116.82], None), 119.3)

    def test_range_bounds_enforced(self):
        self.assertIsNone(pk._pick_cfr_value([39.0, 260.0], None))


class TestFreezeSignatureConstants(unittest.TestCase):

    def test_spread_limit_market_plausible(self):
        self.assertEqual(pk._IO_CFR_SPREAD_LIMIT, 40.0)

    def test_known_grade_tokens_cover_freeze_signature(self):
        for token in (62.5, 65.0, 62.0):
            self.assertIn(token, pk._IO_PRICE_GRADE_TOKENS)


if __name__ == "__main__":
    unittest.main()
