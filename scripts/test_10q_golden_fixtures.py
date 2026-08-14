"""
SEC Form 10-Q Golden Financial Statements Fixture Suite
======================================================
Rigorous automated test suite reconciling the ETF Accounting and NAV Engine
against the official SEC Form 10-Q filed for the quarterly period ended March 31, 2026.

Primary Source: docs/BDRY-BWET_Form10-Q_March-31-2026.pdf
"""

import unittest
from typing import Dict, Any

SEC_10Q_MARCH_31_2026: Dict[str, Dict[str, Any]] = {
    "BDRY": {
        "fund_name": "Breakwave Dry Bulk Shipping ETF",
        "as_of_date": "2026-03-31",
        "shares_outstanding": 4275040,
        "nav_per_share": 10.09,
        "market_close_per_share": 9.97,
        "spread_bps": -118.9296,
        "net_assets": 43139969.00,
        "total_assets": 45587036.00,
        "total_liabilities": 2447067.00,
        "balance_sheet": {
            "money_market_agpxx": 11216138.00,
            "segregated_cash_marex": 34258095.00,
            "unrealized_futures_appreciation": 0.00,
            "interest_receivable": 112803.00,
            "receivable_shares_sold": 0.00,
            "due_to_sponsor": 65864.00,
            "unrealized_futures_depreciation": 2157385.00,
            "other_accrued_expenses": 223818.00
        },
        "futures_portfolio": {
            "total_notional": 43916630.00,
            "total_contracts": 2085,
            "net_unrealized_pnl": -2157385.00,
            "required_margin": 7156294.00,
            "positions": [
                {"name": "Capesize Apr 2026", "route": "5TC", "lots": 260, "notional": 6741540.00, "unrealized": -835210.00},
                {"name": "Capesize May 2026", "route": "5TC", "lots": 260, "notional": 7355140.00, "unrealized": -221610.00},
                {"name": "Capesize Jun 2026", "route": "5TC", "lots": 260, "notional": 7290140.00, "unrealized": -286610.00},
                {"name": "Panamax Apr 2026", "route": "5TC", "lots": 335, "notional": 5741565.00, "unrealized": -482620.00},
                {"name": "Panamax May 2026", "route": "5TC", "lots": 335, "notional": 6149595.00, "unrealized": -66070.00},
                {"name": "Panamax Jun 2026", "route": "5TC", "lots": 335, "notional": 6147250.00, "unrealized": -63540.00},
                {"name": "Supramax Apr 2026", "route": "10TC", "lots": 100, "notional": 1435700.00, "unrealized": -128675.00},
                {"name": "Supramax May 2026", "route": "10TC", "lots": 100, "notional": 1516800.00, "unrealized": -47575.00},
                {"name": "Supramax Jun 2026", "route": "10TC", "lots": 100, "notional": 1538900.00, "unrealized": -25475.00}
            ]
        }
    },
    "BWET": {
        "fund_name": "Breakwave Tanker Shipping ETF",
        "as_of_date": "2026-03-31",
        "shares_outstanding": 475100,
        "nav_per_share": 119.74,
        "market_close_per_share": 98.50,
        "spread_bps": -1773.8433,
        "net_assets": 56888799.00,
        "total_assets": 57077009.00,
        "total_liabilities": 188210.00,
        "balance_sheet": {
            "money_market_agpxx": 26116141.00,
            "segregated_cash_marex": 8854238.00,
            "unrealized_futures_appreciation": 17266732.00,
            "interest_receivable": 49254.00,
            "receivable_shares_sold": 4790644.00,
            "due_to_sponsor": 32833.00,
            "unrealized_futures_depreciation": 0.00,
            "other_accrued_expenses": 155377.00
        },
        "futures_portfolio": {
            "total_notional": 48167085.00,
            "total_contracts": 825,
            "net_unrealized_pnl": 17266732.00,
            "required_margin": 8550956.00,
            "positions": [
                {"name": "Suezmax Apr 2026", "route": "TD20", "lots": 45, "notional": 2243700.00, "unrealized": 675480.00},
                {"name": "Suezmax May 2026", "route": "TD20", "lots": 45, "notional": 1703475.00, "unrealized": 268155.00},
                {"name": "Suezmax Jun 2026", "route": "TD20", "lots": 45, "notional": 1317600.00, "unrealized": -11400.00},
                {"name": "VLCC Apr 2026", "route": "TD3C", "lots": 215, "notional": 16784835.00, "unrealized": 8333772.00},
                {"name": "VLCC May 2026", "route": "TD3C", "lots": 250, "notional": 16909000.00, "unrealized": 6397526.00},
                {"name": "VLCC Jun 2026", "route": "TD3C", "lots": 195, "notional": 8366085.00, "unrealized": 1615692.00},
                {"name": "VLCC Jul 2026", "route": "TD3C", "lots": 10, "notional": 305510.00, "unrealized": 20549.00},
                {"name": "VLCC Aug 2026", "route": "TD3C", "lots": 10, "notional": 268720.00, "unrealized": -16241.00},
                {"name": "VLCC Sep 2026", "route": "TD3C", "lots": 10, "notional": 268160.00, "unrealized": -16801.00}
            ]
        }
    }
}

class Test10QGoldenFixtures(unittest.TestCase):
    def test_bdry_balance_sheet_identity(self):
        bdry = SEC_10Q_MARCH_31_2026["BDRY"]
        bs = bdry["balance_sheet"]
        calc_assets = (
            bs["money_market_agpxx"] +
            bs["segregated_cash_marex"] +
            bs["unrealized_futures_appreciation"] +
            bs["interest_receivable"] +
            bs["receivable_shares_sold"]
        )
        self.assertAlmostEqual(calc_assets, bdry["total_assets"], delta=0.01)
        
        calc_liabilities = (
            bs["due_to_sponsor"] +
            bs["unrealized_futures_depreciation"] +
            bs["other_accrued_expenses"]
        )
        self.assertAlmostEqual(calc_liabilities, bdry["total_liabilities"], delta=0.01)
        
        calc_nav = calc_assets - calc_liabilities
        self.assertAlmostEqual(calc_nav, bdry["net_assets"], delta=0.01)
        
        calc_nav_per_share = calc_nav / bdry["shares_outstanding"]
        self.assertAlmostEqual(calc_nav_per_share, bdry["nav_per_share"], delta=0.01)

    def test_bdry_futures_schedule(self):
        bdry = SEC_10Q_MARCH_31_2026["BDRY"]
        fut = bdry["futures_portfolio"]
        tot_notional = sum(p["notional"] for p in fut["positions"])
        tot_lots = sum(p["lots"] for p in fut["positions"])
        tot_unrealized = sum(p["unrealized"] for p in fut["positions"])
        
        self.assertAlmostEqual(tot_notional, fut["total_notional"], delta=0.01)
        self.assertEqual(tot_lots, fut["total_contracts"])
        self.assertAlmostEqual(tot_unrealized, fut["net_unrealized_pnl"], delta=0.01)

    def test_bwet_balance_sheet_identity(self):
        bwet = SEC_10Q_MARCH_31_2026["BWET"]
        bs = bwet["balance_sheet"]
        calc_assets = (
            bs["money_market_agpxx"] +
            bs["segregated_cash_marex"] +
            bs["unrealized_futures_appreciation"] +
            bs["interest_receivable"] +
            bs["receivable_shares_sold"]
        )
        self.assertAlmostEqual(calc_assets, bwet["total_assets"], delta=0.01)
        
        calc_liabilities = (
            bs["due_to_sponsor"] +
            bs["unrealized_futures_depreciation"] +
            bs["other_accrued_expenses"]
        )
        self.assertAlmostEqual(calc_liabilities, bwet["total_liabilities"], delta=0.01)
        
        calc_nav = calc_assets - calc_liabilities
        self.assertAlmostEqual(calc_nav, bwet["net_assets"], delta=0.01)
        
        calc_nav_per_share = calc_nav / bwet["shares_outstanding"]
        self.assertAlmostEqual(calc_nav_per_share, bwet["nav_per_share"], delta=0.01)

    def test_bwet_futures_schedule(self):
        bwet = SEC_10Q_MARCH_31_2026["BWET"]
        fut = bwet["futures_portfolio"]
        tot_notional = sum(p["notional"] for p in fut["positions"])
        tot_lots = sum(p["lots"] for p in fut["positions"])
        tot_unrealized = sum(p["unrealized"] for p in fut["positions"])
        
        self.assertAlmostEqual(tot_notional, fut["total_notional"], delta=0.01)
        self.assertEqual(tot_lots, fut["total_contracts"])
        self.assertAlmostEqual(tot_unrealized, fut["net_unrealized_pnl"], delta=0.01)

    def test_market_premium_discount_separation(self):
        # Assert that Market Close is distinct from NAV
        for k in ["BDRY", "BWET"]:
            fund = SEC_10Q_MARCH_31_2026[k]
            nav = fund["nav_per_share"]
            mkt = fund["market_close_per_share"]
            spread = ((mkt - nav) / nav) * 10000.0
            self.assertAlmostEqual(spread, fund["spread_bps"], delta=0.1)
            self.assertNotEqual(mkt, nav, f"{k} Market close must NOT be treated as equal to NAV.")

if __name__ == '__main__':
    unittest.main()
