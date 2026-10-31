"""Rendering fixes found by the 2026-11 readiness gate: Affinity TCE cells keep printed decimals (TC8 is quoted per
tonne, "58.85" had become "$59"), and Signal headings keep inline runs apart and acronyms as printed ("TC14 38k" had
become "Tc1438k", "U.S." had become "U.s.")."""
from __future__ import annotations

import sys

from scripts.parse_engine.config import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts/extract/publishers"))
import polish_affinity_markdown as aff  # noqa: E402
import run_baltic as bal  # noqa: E402
import run_breakwave_insights as bwi  # noqa: E402
import run_signal as sig  # noqa: E402


def test_affinity_rate_keeps_printed_decimals():
    assert aff.format_rate_cell("58.85", 58.85) == "$58.85"
    assert aff.format_rate_cell("$58.70", 58.7) == "$58.70"
    assert aff.format_rate_cell("-1.25", -1.25) == "-$1.25"


def test_affinity_rate_whole_dollars_unchanged():
    assert aff.format_rate_cell("32,500", 32500.0) == "$32,500"
    assert aff.format_rate(32500.0) == "$32,500"
    assert aff.format_rate(58.85) == "$58.85"
    assert aff.format_rate(None) == "-"


def test_signal_heading_keeps_acronyms_and_digits():
    h = "TC1 75k Middle East Gulf to Japan | TC5 55k Middle East Gulf to Japan| TC14 38k US Gulf to Japan"
    assert sig.format_heading(h) == h
    assert sig.format_heading("CLEAN TCE$/DAY") == "CLEAN TCE$/DAY"
    assert sig.format_heading("U.S. exporting more crude oil to Europe") == "U.S. Exporting More Crude Oil to Europe"
    assert sig.format_heading("flows in the 1Q stay low") == "Flows in the 1Q Stay Low"


def test_inline_runs_keep_word_boundaries():
    # Breakwave source: "declared<em>force majeure</em>at"; Baltic source: "rates<b> </b>followed suit"
    for m in (bal, bwi):
        assert m._join(["has declared", m._wrap("force majeure", "*", "*"), "at the"]) == "has declared *force majeure* at the"
        assert m._join(["rates", m._wrap(" ", "**", "**"), "followed suit"]) == "rates followed suit"
        assert m._wrap("rates ", "**", "**") == "**rates** "
        # intraword emphasis stays one word
        assert m._join(["**Capesize Q3 2020 Contrac**", "t"]) == "**Capesize Q3 2020 Contrac**t"
        assert m._join(["US$", "**5**"]) == "US$**5**"
