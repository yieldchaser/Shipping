#!/usr/bin/env python3
"""
Unit tests for fetch_live_etf_quotes.py
"""

import unittest
import os
import json
import tempfile
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fetch_live_etf_quotes


class TestFetchLiveETFQuotes(unittest.TestCase):

    def test_01_schema_structure(self):
        """Verify the generated schema has expected structure and keys."""
        bundle = fetch_live_etf_quotes.run_pipeline(dry_run=True)
        self.assertIn("schema_version", bundle)
        self.assertIn("updated_at_utc", bundle)
        self.assertIn("quotes", bundle)

    @patch("fetch_live_etf_quotes.fetch_quote_with_fallback")
    def test_02_pipeline_mocked_success(self, mock_fetch):
        """Verify pipeline execution with mocked quotes."""
        mock_fetch.side_effect = lambda ticker: {
            "symbol": ticker,
            "price": 15.25 if ticker == "BDRY" else 410.50,
            "previous_close": 15.00 if ticker == "BDRY" else 400.00,
            "change": 0.25 if ticker == "BDRY" else 10.50,
            "change_percent": 1.6667 if ticker == "BDRY" else 2.625,
            "source": "test_mock"
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = os.path.join(tmpdir, "live_quotes.json")
            with patch("fetch_live_etf_quotes.OUTPUT_PATH", out_file):
                bundle = fetch_live_etf_quotes.run_pipeline(dry_run=False)
                self.assertTrue(os.path.exists(out_file))
                with open(out_file, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                self.assertIn("BDRY", saved["quotes"])
                self.assertIn("BWET", saved["quotes"])
                self.assertEqual(saved["quotes"]["BDRY"]["price"], 15.25)
                self.assertEqual(saved["quotes"]["BWET"]["price"], 410.50)


if __name__ == "__main__":
    unittest.main()
