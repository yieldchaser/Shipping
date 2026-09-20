"""
Automated Unit Tests for Executive Macro Heat Radar Engine (v2)
Tests:
1. Backtest dataset schema/integrity
2. Pillar bounds [0,20] and total-score summation
3. Regime labels match evidence-based band boundaries
4. Contrarian predictive structure: troughs precede rebounds,
   overheated bands precede drawdowns; composite carries negative IC.
"""

import os
import unittest
import pandas as pd

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKTEST_CSV_PATH = os.path.join(WORKSPACE_DIR, 'data', 'derived', 'macro_health_score_backtest.csv')

REGIMES = {
    'Overheated - Reversal Risk': (75, 101),
    'Late-Cycle Strength': (60, 75),
    'Mid-Cycle Equilibrium': (45, 60),
    'Trough - Accumulation Zone': (-1, 45),
}


class TestMacroHeatRadarEngine(unittest.TestCase):

    def setUp(self):
        self.assertTrue(os.path.exists(BACKTEST_CSV_PATH), f"Backtest dataset missing: {BACKTEST_CSV_PATH}")
        self.df = pd.read_csv(BACKTEST_CSV_PATH)

    def test_01_dataset_schema_and_integrity(self):
        required_cols = [
            'date', 'bdi', 'bdry', 'p1_momentum', 'p2_term_structure',
            'p3_futures_basis', 'p4_port_restock', 'p5_asset_safety',
            'total_score', 'regime', 'bdi_fwd_1W', 'bdi_fwd_1M', 'bdi_fwd_3M', 'bdi_fwd_6M'
        ]
        for col in required_cols:
            self.assertIn(col, self.df.columns, f"Missing required column: {col}")
        self.assertGreater(len(self.df), 1000, "Historical sample size must span at least 1,000 trading days")

    def test_02_pillar_bounds_and_total_score_sum(self):
        for p in ['p1_momentum', 'p2_term_structure', 'p3_futures_basis', 'p4_port_restock', 'p5_asset_safety']:
            self.assertTrue((self.df[p] >= 0).all(), f"{p} has values < 0")
            self.assertTrue((self.df[p] <= 20).all(), f"{p} has values > 20")

        computed_total = (
            self.df['p1_momentum'] +
            self.df['p2_term_structure'] +
            self.df['p3_futures_basis'] +
            self.df['p4_port_restock'] +
            self.df['p5_asset_safety']
        )
        pd.testing.assert_series_equal(
            computed_total.round(1), self.df['total_score'].round(1), check_names=False
        )
        self.assertTrue((self.df['total_score'] >= 0).all())
        self.assertTrue((self.df['total_score'] <= 100).all())

    def test_03_regime_classification_consistency(self):
        """Verify regime assignments match exact score boundaries."""
        for _, row in self.df.iterrows():
            score = row['total_score']
            regime = row['regime']
            self.assertIn(regime, REGIMES, f"Unknown regime label: {regime}")
            lo, hi = REGIMES[regime]
            self.assertGreaterEqual(score, lo, f"{score} below {regime} floor")
            self.assertLess(score, hi, f"{score} at/above {regime} ceiling")

    def test_04_pillars_are_information_bearing(self):
        """v2 graded/percentile pillars must carry variance (no dead pillars).

        Regression guard: v1's P5 was constant (std=0) because its fixed
        sweet-spot anchors were unreachable with real margin levels.
        """
        for p in ['p1_momentum', 'p2_term_structure', 'p3_futures_basis', 'p4_port_restock', 'p5_asset_safety']:
            std = self.df.loc[self.df.index > 300, p].std()  # skip warm-up window
            self.assertGreater(std, 0.8, f"{p} is near-dead (std={std:.2f}) — scoring transform collapsed")

    def test_05_contrarian_predictive_structure(self):
        """Evidence-based cycle semantics must hold in the shipped dataset:

        - Trough band precedes strong positive forward BDI returns (> +20% avg 3M).
        - Overheated band precedes negative forward BDI returns (< 0% avg 3M).
        - Composite Spearman IC vs fwd 3M BDI is materially negative (< -0.20),
          i.e. the gauge reads as cycle heat / reversal risk, not momentum chase.
        """
        valid = self.df.dropna(subset=['bdi_fwd_3M'])
        trough_3m = valid[valid['regime'] == 'Trough - Accumulation Zone']['bdi_fwd_3M'].mean()
        hot_3m = valid[valid['regime'] == 'Overheated - Reversal Risk']['bdi_fwd_3M'].mean()
        ic = valid['total_score'].corr(valid['bdi_fwd_3M'], method='spearman')

        self.assertGreater(trough_3m, 20.0, "Trough band must precede strong rebounds")
        self.assertLess(hot_3m, 0.0, "Overheated band must precede drawdowns")
        self.assertLess(ic, -0.20, f"Composite IC collapsed to {ic:.3f} — re-validate engine")


if __name__ == '__main__':
    unittest.main()
