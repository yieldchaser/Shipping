"""
Notional-Weight Roll-Schedule Mechanics & Verification Suite
============================================================
Tests the documented 4-week quarterly roll schedule based on PROSPECTUS NOTIONAL WEIGHTS
(BDRY: 50% Cape / 40% Pana / 10% Supra; BWET: 90% VLCC TD3C / 10% Suezmax TD20),
utilizing actual contract sizing multipliers and discrete lot rounding rules.

Primary Sources:
- docs/Amplify_BDRY_Prospectus.pdf
- docs/Amplify_BWET_Prospectus.pdf
- Solactive Breakwave Dry Bulk / Tanker Index Methodologies
"""

import unittest
from typing import Dict, Any, List
import pandas as pd
import numpy as np

# Prospectus Contract Specifications
PROSPECTUS_NOTIONAL_WEIGHTS = {
    'BDRY': {
        'Capesize': {'target_weight': 0.50, 'multiplier': 1.0, 'unit': 'USD/day'},
        'Panamax': {'target_weight': 0.40, 'multiplier': 1.0, 'unit': 'USD/day'},
        'Supramax': {'target_weight': 0.10, 'multiplier': 1.0, 'unit': 'USD/day'}
    },
    'BWET': {
        'VLCC_TD3C': {'target_weight': 0.90, 'multiplier': 1000.0, 'unit': 'USD/MT'},
        'Suezmax_TD20': {'target_weight': 0.10, 'multiplier': 1000.0, 'unit': 'USD/MT'}
    }
}

def calculate_notional_roll_schedule(
    etf_key: str,
    fund_nav: float,
    prompt_prices: Dict[str, float],
    next_q_prices: Dict[str, float],
    roll_week: int
) -> Dict[str, Any]:
    """
    Computes theoretical target lot allocation during the 4-week roll window
    based on Prospectus target notional weights.
    roll_week in [1, 2, 3, 4]
    - Week 1: 25% of target notional shifted to next-Q strip
    - Week 2: 50% of target notional shifted to next-Q strip
    - Week 3: 75% of target notional shifted to next-Q strip
    - Week 4: 100% of target notional shifted to next-Q strip
    """
    if roll_week not in [1, 2, 3, 4]:
        raise ValueError(f"Roll week must be 1, 2, 3, or 4; got {roll_week}")
        
    weights_spec = PROSPECTUS_NOTIONAL_WEIGHTS[etf_key.upper()]
    next_q_pct = roll_week * 0.25
    prompt_pct = 1.0 - next_q_pct
    
    schedule = {}
    total_reconstructed_notional = 0.0
    
    for vessel_class, spec in weights_spec.items():
        w = spec['target_weight']
        mult = spec['multiplier']
        p_px = prompt_prices[vessel_class]
        n_px = next_q_prices[vessel_class]
        
        target_class_notional = fund_nav * w
        prompt_target_notional = target_class_notional * prompt_pct
        next_q_target_notional = target_class_notional * next_q_pct
        
        # Discrete lot sizing
        p_lots = round(prompt_target_notional / (p_px * mult)) if p_px > 0 else 0
        n_lots = round(next_q_target_notional / (n_px * mult)) if n_px > 0 else 0
        
        p_actual_notional = p_lots * p_px * mult
        n_actual_notional = n_lots * n_px * mult
        class_notional = p_actual_notional + n_actual_notional
        total_reconstructed_notional += class_notional
        
        schedule[vessel_class] = {
            'target_weight_pct': w * 100.0,
            'prompt_target_pct': prompt_pct * 100.0,
            'next_q_target_pct': next_q_pct * 100.0,
            'prompt_lots': p_lots,
            'next_q_lots': n_lots,
            'prompt_notional': p_actual_notional,
            'next_q_notional': n_actual_notional,
            'class_notional': class_notional
        }
        
    return {
        'etf': etf_key.upper(),
        'roll_week': roll_week,
        'fund_nav': fund_nav,
        'total_notional': total_reconstructed_notional,
        'schedule': schedule
    }

class TestNotionalRollSchedule(unittest.TestCase):
    def test_bdry_notional_roll_progression(self):
        nav = 43139969.00 # 10-Q March 31, 2026 BDRY Net Assets
        prompt_px = {'Capesize': 25929.0, 'Panamax': 17139.0, 'Supramax': 14357.0}
        next_q_px = {'Capesize': 29482.0, 'Panamax': 18554.0, 'Supramax': 15643.0}
        
        # Week 1: 25% roll
        res_w1 = calculate_notional_roll_schedule('BDRY', nav, prompt_px, next_q_px, 1)
        sched_w1 = res_w1['schedule']
        
        # Check Capesize notional allocation (50% target = $21.57M)
        cape_notional = sched_w1['Capesize']['class_notional']
        self.assertAlmostEqual(cape_notional / res_w1['total_notional'], 0.50, delta=0.03)
        # Week 1 Capesize prompt lots should be ~3x next_q lots (75% / 25%)
        ratio = sched_w1['Capesize']['prompt_notional'] / (sched_w1['Capesize']['next_q_notional'] or 1)
        self.assertAlmostEqual(ratio, 3.0, delta=0.2)
        
        # Week 4: 100% roll
        res_w4 = calculate_notional_roll_schedule('BDRY', nav, prompt_px, next_q_px, 4)
        sched_w4 = res_w4['schedule']
        self.assertEqual(sched_w4['Capesize']['prompt_lots'], 0)
        self.assertEqual(sched_w4['Panamax']['prompt_lots'], 0)
        self.assertEqual(sched_w4['Supramax']['prompt_lots'], 0)
        self.assertGreater(sched_w4['Capesize']['next_q_lots'], 0)

    def test_bwet_notional_roll_progression(self):
        nav = 56888799.00 # 10-Q March 31, 2026 BWET Net Assets
        prompt_px = {'VLCC_TD3C': 78.069, 'Suezmax_TD20': 49.860}
        next_q_px = {'VLCC_TD3C': 67.636, 'Suezmax_TD20': 37.855}
        
        # Week 2: 50% roll
        res_w2 = calculate_notional_roll_schedule('BWET', nav, prompt_px, next_q_px, 2)
        sched_w2 = res_w2['schedule']
        
        # Verify 90% VLCC notional weighting
        vlcc_notional = sched_w2['VLCC_TD3C']['class_notional']
        self.assertAlmostEqual(vlcc_notional / res_w2['total_notional'], 0.90, delta=0.03)
        # Week 2: prompt and next_q notional should be approximately equal (50% / 50%)
        p_notional = sched_w2['VLCC_TD3C']['prompt_notional']
        n_notional = sched_w2['VLCC_TD3C']['next_q_notional']
        self.assertAlmostEqual(p_notional / (p_notional + n_notional), 0.50, delta=0.03)

    def test_observed_snapshot_disclosures_unreconciled_trade_fills(self):
        # Confirm that daily CSV disclosures provide end-of-day marks, but lack intraday trade fill executions
        df = pd.read_csv('data/etf/bdry_holdings_history.csv')
        self.assertNotIn('fill_price', df.columns)
        self.assertNotIn('order_type', df.columns)
        self.assertNotIn('execution_time', df.columns)

if __name__ == '__main__':
    unittest.main()
