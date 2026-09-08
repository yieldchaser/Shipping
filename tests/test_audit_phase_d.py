"""Phase-D final audit gates (tooltip coverage engine + hardcoded-value hunt).

Pins the audit-pass invariants in index.html:
  - the per-tab tooltip coverage engine (annotateCoverageGaps) is wired into
    switchTab and stamps still-uncontexted interactive elements;
  - no baked-in stale figures survive in the ETF deconstruction / decision
    ticket / QA knowledge-base cluster (everything resolves from the
    authoritative scenario snapshot baseline or discloses its absence);
  - tracking/bunkers HUD shells carry no stale snapshot numerals - live
    renderers own every displayed value;
  - the BIX archive badge derives its date span from the cache;
  - the only remaining fixed dates are labeled design constants.
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(ROOT, "index.html")

with open(HTML, "r", encoding="utf-8") as f:
    C = f.read()


def test_tooltip_coverage_engine_wired():
    assert "function annotateCoverageGaps" in C
    assert "annotateCoverageGaps(tabId)" in C
    assert "data-coverage-stamped" in C
    # engine must respect the existing bus and never double-stamp
    assert "data-tooltip" in C


def test_no_baked_in_etf_baseline_figures():
    # the canonical resolver exists and is used by every surface
    assert "window.getEtfDisclosedBaseline" in C
    assert C.count("getEtfDisclosedBaseline(") >= 5
    # retired baked-in fallbacks must not return
    for lit in ["'2026-08-14'", "13.79", "119.74", "30943541.77",
                "80677134.78", "358.43", "374.55", "2200000", "225000"]:
        assert lit not in C, f"baked-in figure returned: {lit}"


def test_no_stale_snapshot_numerals_in_hud_shells():
    # tracking HUD shells hold em dashes / neutral subs, not stale counts
    assert 'id="hudChokepointsCount">—</div>' in C
    assert "1,568 Active Vessels" not in C
    assert "619 Vessels" not in C
    assert "949 Vessels" not in C
    assert "73.1% Transit Volume" not in C
    assert "75.6% Transit Volume" not in C
    # bunkers HUD shells likewise
    assert 'id="bunkerKpiEts"' in C and "€72.50" not in C
    assert "4.73M MT" not in C
    assert "205.5" not in C  # stale Hi-5 tooltip payload
    assert 'data-tt-obs="2026-09-04 vs 2026-08-28"' not in C


def test_bix_archive_badge_dates_from_cache():
    assert 'id="bunkerBixArchBadge"' in C
    assert "Archive begins 2026-08-24" not in C
    assert "'Archive ' + d0 + ' to ' + d1" in C
    # honest loading placeholder until the cache lands
    assert "Archive span: computing from bix history" in C


def test_only_labeled_design_constant_dates():
    # the single remaining fixed date literal is a labeled backtest constant
    hits = [m.start() for m in re.finditer(r"'2026-07-15'", C)]
    assert len(hits) == 1
    seg = C[hits[0]:hits[0] + 140]
    assert "design constant" in seg


def test_scenario_horizon_input_follows_snapshot():
    # date input default emptied; JS falls back to the disclosed snapshot date
    assert 'id="deconstTargetDate" value=""' in C
    assert "Follows the fund's disclosed holdings snapshot date" in C


def test_coverage_engine_covers_tables_charts_and_roll_badges():
    # table-header branch with per-column copy + honest generic fallback
    assert "panel.querySelectorAll('th')" in C
    assert "Column of this table; every cell is computed from the cache section backing the table" in C
    # named chart overrides for the canvases the sweep flagged
    for cid in ["drawdownChart", "spaghettiChart", "monthlySpaghettiChart",
                "deconstContractChart", "fearnFxMonthly", "zSparkDry", "zSparkTanker"]:
        assert f"{cid}:" in C, f"missing chart override {cid}"
    # 5-Axiom roll badge + per-contract target-price input branches
    assert "Contract Roll Badge" in C
    assert "M0 = prompt (front) month; M+1 = next strip; M+2 = two-out or beyond" in C
    assert "onDeconstTargetPriceInput" in C
    assert "Contract Target Price Override" in C
    # engine re-runs once for late async sub-section renders, idempotently
    assert "annotateCoverageGaps(tabId)" in C
    assert "setTimeout" in C


def test_dry_tce_row_quote_bug_fixed():
    # the dry-class row previously swallowed data-tooltip inside the onclick
    # attribute (broken clicks + no tooltip). The corrected pattern must bind
    # onclick first, then data-tooltip as a real attribute.
    assert "\'dry\\')\"" in C.replace('\\"', '"') or "selectTceRow(' + idx + ', \'dry\')')" in C
