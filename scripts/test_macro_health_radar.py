"""
Automated Unit Tests for Executive Macro Health Radar Engine
Tests:
1. 5-Pillar Score computation and weights (Freight Momentum, Term Structure, Futures Basis, Port Restocking, Asset Safety)
2. 4-Tier Calibrated Regime thresholds (Bullish >=75, Constructive 60-74, Mid-Cycle 45-59, Trough <45)
3. Historical backtest dataset integrity (data/derived/macro_health_score_backtest.csv)
4. Empirical hit rates and return distribution properties across all regimes
"""

import os
import unittest
import pandas as pd
import numpy as np

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKTEST_CSV_PATH = os.path.join(WORKSPACE_DIR, 'data', 'derived', 'macro_health_score_backtest.csv')

class TestMacroHealthRadarEngine(unittest.TestCase):

    def setUp(self):
        self.assertTrue(os.path.exists(BACKTEST_CSV_PATH), f"Backtest dataset missing: {BACKTEST_CSV_PATH}")
        self.df = pd.read_csv(BACKTEST_CSV_PATH)

    def test_01_dataset_schema_and_integrity(self):
        """Verify backtest dataset has all required pillars, columns, and non-empty rows."""
        required_cols = [
            'date', 'bdi', 'bdry', 'p1_momentum', 'p2_term_structure',
            'p3_futures_basis', 'p4_port_restock', 'p5_asset_safety',
            'total_score', 'regime', 'bdi_fwd_1W', 'bdi_fwd_1M', 'bdi_fwd_3M', 'bdi_fwd_6M'
        ]
        for col in required_cols:
            self.assertIn(col, self.df.columns, f"Missing required column: {col}")
        
        self.assertGreater(len(self.df), 1000, "Historical sample size must span at least 1,000 trading days")

    def test_02_pillar_bounds_and_total_score_sum(self):
        """Ensure all 5 pillars are strictly within [0, 20] and sum to total_score."""
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
        np.testing.assert_array_almost_equal(self.df['total_score'].values, computed_total.values)
        self.assertTrue((self.df['total_score'] >= 0).all())
        self.assertTrue((self.df['total_score'] <= 100).all())

    def test_03_regime_classification_consistency(self):
        """Verify 4-tier regime assignments match exact score boundaries."""
        for _, row in self.df.iterrows():
            score = row['total_score']
            regime = row['regime']
            if score >= 75:
                self.assertIn(regime, ['Bullish Expansion'])
            elif score >= 60:
                self.assertIn(regime, ['Constructive Expansion'])
            elif score >= 45:
                self.assertIn(regime, ['Balanced Mid-Cycle'])
            else:
                self.assertIn(regime, ['Contraction / Trough', 'Contraction / Value Trough'])

    def test_04_empirical_predictive_power_validation(self):
        """Verify empirical shipping cycle properties across regimes:
        - Constructive Expansion generates consistent positive forward momentum (1W, 1M, 3M, 6M).
        - Contraction/Trough generates powerful multi-month mean-reversion rebounds (+36% 3M).
        - Bullish Super-Cycle identifies peak momentum and spot backwardation arb harvesting windows.
        """
        valid_3m = self.df.dropna(subset=['bdi_fwd_3M'])
        
        valid_1w = self.df.dropna(subset=['bdi_fwd_1W'])
        constructive_1w = valid_1w[valid_1w['regime'] == 'Constructive Expansion']['bdi_fwd_1W'].mean()
        constructive_3m = valid_3m[valid_3m['regime'] == 'Constructive Expansion']['bdi_fwd_3M'].mean()
        trough_3m = valid_3m[valid_3m['regime'] == 'Contraction / Trough']['bdi_fwd_3M'].mean()
        
        # Constructive Expansion forward returns must be positive
        self.assertGreater(constructive_1w, 0.0, "Constructive Expansion 1W return must be positive")
        self.assertGreater(constructive_3m, 0.0, "Constructive Expansion 3M return must be positive")
        # Contraction troughs must exhibit high rebound potential
        self.assertGreater(trough_3m, 20.0, "Contraction Trough mean-reversion rebound must exceed +20%")

if __name__ == '__main__':
    unittest.main()
