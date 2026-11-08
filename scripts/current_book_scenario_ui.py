"""
User-Facing Current-Book Scenario Interface
===========================================
Interactive scenario interface for evaluated funds (BDRY and BWET):
Consumes verified dated constituent book + user-supplied contract mark shocks ->
Outputs exact dollar NAV impact, official source date, business-day freshness,
and explicit unresolved accounting residual flags.

GOVERNANCE STANDARD:
- Per-share NAV impact remains strictly UNAVAILABLE without same-date official shares.
- Predictive alpha, automated forecasts, and trading signals are strictly disabled.
"""

import sys
import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from current_book_manual_shock import load_latest_official_snapshot, calculate_manual_contract_shock

def format_currency(val: Optional[float]) -> str:
    if val is None:
        return "UNAVAILABLE"
    return f"${val:,.2f}"

def render_scenario_summary(res: Dict[str, Any]) -> str:
    lines = []
    lines.append("====================================================================================================")
    lines.append(f"  BREAKWAVE CURRENT-BOOK MANUAL SCENARIO SENSITIVITY INTERFACE: {res['fund']}")
    lines.append("====================================================================================================")
    lines.append(f"  Classification       : {res['classification']}")
    lines.append(f"  Official Snapshot Date: {res['snapshot_date']} (Evaluated: {res['evaluation_date']}, Freshness: {res['snapshot_age_bdays']} bdays / limit {res['freshness_limit_bdays']} bdays)")
    lines.append(f"  Source URL Origin    : {res['source_url']}")
    lines.append(f"  Archive SHA-256 Hash : {res['sha256_checksum'][:32]}... ({res['provenance_status']})")
    lines.append("----------------------------------------------------------------------------------------------------")
    lines.append(f"  Active Positions     : {res['total_positions']} constituent futures contracts")
    lines.append(f"  Base Futures Notional: {format_currency(res['total_base_notional_dollars'])}")
    lines.append(f"  Total Delta NAV ($)  : {format_currency(res['total_delta_nav_dollars'])} ({'+' if res['total_delta_nav_dollars'] >= 0 else ''}{res['total_delta_nav_dollars']:,.2f})")
    lines.append(f"  Same-Date Shares     : {res['dated_official_shares'] if res['dated_official_shares'] else 'UNAVAILABLE (Unobserved on interim snapshot dates)'}")
    # PEP 701 only: the nested f-string below reuses its enclosing quote type and is a
    # SyntaxError on Python <= 3.11.  Computed into a plain variable instead.
    _dns = res['delta_nav_per_share_dollars']
    _dns_txt = f"${_dns:+.4f}/sh" if _dns is not None else 'UNAVAILABLE (Strictly Excluded without dated shares)'
    lines.append(f"  Per-Share NAV Impact : {_dns_txt}")
    lines.append(f"  Share Status Flag    : {res['share_conversion_status']}")
    lines.append("----------------------------------------------------------------------------------------------------")
    lines.append("  EXPLICIT UNRESOLVED RESIDUAL FLAGS:")
    for k, flag_desc in res['unresolved_residuals_flags'].items():
        lines.append(f"    * [{k}] {flag_desc}")
    lines.append("----------------------------------------------------------------------------------------------------")
    lines.append("  CONSTITUENT POSITION SHOCKS BREAKDOWN:")
    lines.append(f"  {'Contract / Strip':<40} | {'Lots':<6} | {'Multiplier':<14} | {'Base Price':<11} | {'Delta Mark':<11} | {'Dollar Impact':<15}")
    lines.append("  " + "-" * 96)
    
    for pos in res['position_breakdown']:
        mult_str = f"{pos['multiplier']:,.0f} {pos['multiplier_unit'].split()[0]}"
        lines.append(
            f"  {pos['name'][:40]:<40} | {pos['lots']:<6.1f} | {mult_str:<14} | "
            f"${pos['base_price']:<10,.2f} | ${pos['delta_mark_dollars']:+10,.2f} | "
            f"${pos['contract_dollar_impact']:+14,.2f}"
        )
    lines.append("====================================================================================================\n")
    return "\n".join(lines)

def run_interactive_scenario(fund: str = 'BDRY', manual_shocks: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    snapshot = load_latest_official_snapshot(fund, max_stale_business_days=3)
    
    # Default demonstration shocks (percent, as calculate_manual_contract_shock reads them): +5% on the prompt strip, i.e. the three nearest contract months the book holds.
    # (This was hardcoded to 'Jul'/'Aug'/'Sep'; once the book rolled past September the shock was $0.)
    if manual_shocks is None:
        import re
        from datetime import datetime as _dt
        names = [p.get('contract_name') or p.get('name') or p.get('ticker') for p in snapshot['positions']]

        def _month(name):
            m = re.search(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s*'?(\d{2,4})\b", name or "")
            if not m:
                return None
            yr = int(m.group(2)) % 100
            return _dt.strptime(f"{m.group(1)} {yr:02d}", "%b %y")

        prompt = sorted({mo for mo in map(_month, names) if mo})[:3]
        manual_shocks = {}
        for p, c_name in zip(snapshot['positions'], names):
            manual_shocks[c_name] = 5.0 if _month(c_name) in prompt else 0.0  # percent
                
    result = calculate_manual_contract_shock(snapshot, manual_shocks)
    output_text = render_scenario_summary(result)
    print(output_text)
    return result

if __name__ == '__main__':
    target_fund = sys.argv[1] if len(sys.argv) > 1 else 'BDRY'
    run_interactive_scenario(target_fund)
    if len(sys.argv) <= 1:
        run_interactive_scenario('BWET')
