"""Tests for kb/c1_review.py — the C1 checkpoint packet generator."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "kb" / "reports" / "C1_REVIEW.md"

sys.path.insert(0, str(ROOT / "kb"))
import c1_review as C  # noqa: E402


def test_bakeoff_table_renders_a_missing_cost_as_unmeasured_not_zero():
    """Defect 19/17: a model row without `cost_usd` must not claim a booked `$0.0000`.

    `.get("cost_usd", 0)` fabricated a measured zero for a key nobody wrote. A row that *does* carry
    `0.0` (a free NIM route) stays a writer-declared `$0.0000` — the two states must differ.
    """
    row = {"precision": 0.9, "precision_ci95": [0.88, 0.92], "recall": 0.8, "f1": 0.85}
    table = C.bakeoff_table({"models": {"free": {**row, "cost_usd": 0.0},
                                        "unknown": dict(row)},
                             "roles": {"reference_models": []}})
    free, unknown = table.splitlines()[2:4]
    assert free.endswith("| $0.0000 | UNMEASURED |"), free
    assert unknown.endswith("| UNMEASURED | UNMEASURED |"), unknown


def test_generator_runs_and_writes_packet():
    r = subprocess.run([sys.executable, "-X", "utf8", "-u", str(ROOT / "kb" / "c1_review.py")],
                       capture_output=True, text=True, cwd=str(ROOT))
    assert r.returncode == 0, r.stderr[-2000:]
    assert DOC.exists() and DOC.stat().st_size > 20_000


def test_packet_has_all_c1_sections():
    t = DOC.read_text(encoding="utf-8")
    for head in ["# C1 review", "## 1. Bake-off table", "## 2. Models I chose",
                 "## 3. Projected full-build cost", "## 4. Thirty flagged gold-label items",
                 "## 5. Twenty-five sampled gold questions", "## 6. Thirty sampled entity merges",
                 "## 7. What happens on your reply"]:
        assert head in t, head


def test_packet_counts_and_gate_table():
    t = DOC.read_text(encoding="utf-8")
    # 30 flagged items numbered 1..30
    body = t[t.index("## 4. Thirty flagged"):t.index("## 5. Twenty-five")]
    assert len(re.findall(r"^\d+\. \*\*(?:KEEP|DROP)\*\*", body, re.M)) == 30
    # 25 gold questions in the packet
    gold = t[t.index("### C1 sample packet"):t.index("## 6. Thirty sampled")]
    assert len(re.findall(r"^G-\d{3}\t", gold, re.M)) == 25
    # 30 merge rows
    merges = t[t.index("## 6. Thirty sampled"):t.index("## 7. What happens")]
    assert len([l for l in merges.splitlines() if l.startswith("| `")]) == 30
    # every P4b gate row says PASS
    gates = t[t.index("| gate | measured |"):t.index("Gold set: 120 stratified")]
    assert gates.count("| PASS |") == 5 and "FAIL" not in gates


def test_packet_numbers_match_p4b_report():
    p4b = json.loads((ROOT / "kb" / "reports" / "p4b.json").read_text(encoding="utf-8"))
    t = DOC.read_text(encoding="utf-8")
    assert f"{p4b['selected']['precision']:.4f}" in t
    assert f"{p4b['selected']['f1']:.4f}" in t
    assert f"{p4b['spend']['total_usd']:.4f}" in t
    assert p4b["selected"]["model"] in t


def test_money_sum_is_unmeasured_when_any_term_is_unmeasured():
    """Defect 17/21: dropping an unknown term books the rest as if it were the total.

    `sum(v for v in vals if v is not None)` is exactly the bug — a projection that is missing its
    biggest component must read UNMEASURED, while a genuine measured `0.0` term must keep the total
    measured (the four states: known/known, unknown term, empty, exact zero).
    """
    assert C.money_sum(4.75, 35.0) == 39.75
    assert C.money_sum(4.75, 0.0) == 4.75
    assert C.money_sum(0.0, 0.0) == 0.0
    assert C.money_sum(4.75, None) is None
    assert C.money_sum(None, None) is None
    assert C.money_sum() == 0.0


def test_cap_and_bool_config_reads_are_unmeasured_not_one_dollar():
    """A `$` must never be glued to a value that may not exist.

    `cap_text(None)` -> `UNMEASURED`, and a config `pipeline_cap_usd: true` (readable YAML, not a
    number) must not become `$1` — `isinstance(True, int)` is True, so `bool` has to be excluded.
    """
    assert C.cap_text(82.0) == "$82"
    assert C.cap_text(82) == "$82"
    assert C.cap_text(None) == "UNMEASURED"
    assert C.cap_text(True) == "UNMEASURED"
    assert C.cap_text("82") == "UNMEASURED"
    assert C.cap_text(float("nan")) == "UNMEASURED"


def test_budget_bookings_come_from_config_and_residual_matches_the_approved_arithmetic():
    """The packet's denominators are authored once, in config, and read here — never typed.

    Row (a) of the projection table is the arithmetic the owner approved at C1 (`$4.75 + $35`), so the
    config-derived residual must still be 35.0: if config moves, this pin fails *and* the packet changes,
    which is the point (a stale literal would have silently kept the old number).
    """
    book = C.budget_bookings()
    assert book["pipeline_cap_usd"] == 82.0
    assert book["p4c_bulk_extraction"] == 31.25
    assert book["residual_phase_bookings"] == 35.0


def test_packet_renders_unmeasured_spend_as_unmeasured_and_never_as_zero():
    """End-to-end on the money path with an unmeasured ledger.

    Before the fix these seven fields were `"${v:.4f}"` f-strings: `None` raised a `TypeError` inside
    the generator instead of printing `UNMEASURED`, and a fabricated `0.0` would have printed a booked
    `$0.00` — the same defect class as the `bakeoff_table` `.get("cost_usd", 0)` case. Also pins the
    split of `build_packet` out of `main()` (a pure renderer the money path can be tested through
    without rewriting the committed packet).
    """
    fixtures = {n: json.loads((ROOT / "kb" / "reports" / n).read_text(encoding="utf-8"))
                for n in ("p4b.json", "p4b_flagged.json", "gold_set.json", "p3_owner_sample.json")}
    p4b = dict(fixtures["p4b.json"])
    p4b["spend"] = dict(p4b["spend"], total_usd=None)
    p4b["p4c_feasibility"] = dict(p4b["p4c_feasibility"], remaining_pipeline_usd=None)

    doc = C.build_packet(p4b, fixtures["p4b_flagged.json"], fixtures["gold_set.json"],
                         fixtures["p3_owner_sample.json"])
    line3 = [l for l in doc.splitlines() if l.startswith("82 tests pass")][0]
    # Spend is unknown -> it must not claim a measurement. "of the $82 cap" stays: the cap is config,
    # independent of the ledger, so it is still a legitimate measured policy number.
    assert "UNMEASURED" in line3, line3
    assert "$0.0000" not in line3, line3
    # The projection rows fall back to the config-derived total, never to a bare "$0.00".
    assert "| UNMEASURED |" in doc
    assert "budget right now: UNMEASURED" in doc


def test_packet_renders_a_tiny_nonzero_spend_without_flattening_it_to_zero():
    """A real sub-cent spend must not render as the measured-zero string `$0.0000` (Lesson 67).

    `$0.00001` *contains* `$0.0000`, so assert on the parsed cell/token, never with `not in`.
    """
    fixtures = {n: json.loads((ROOT / "kb" / "reports" / n).read_text(encoding="utf-8"))
                for n in ("p4b.json", "p4b_flagged.json", "gold_set.json", "p3_owner_sample.json")}
    p4b = dict(fixtures["p4b.json"])
    p4b["spend"] = dict(p4b["spend"], total_usd=0.000019)

    doc = C.build_packet(p4b, fixtures["p4b_flagged.json"], fixtures["gold_set.json"],
                         fixtures["p3_owner_sample.json"])
    line3 = [l for l in doc.splitlines() if l.startswith("82 tests pass")][0]
    # `fmt_usd` widens to 5 dp here: `$0.00002`, i.e. visibly nonzero. Assert the *token*, because the
    # flatten-to-zero string `$0.0000` is a prefix of `$0.00002` (never test this with `not in`).
    token = re.search(r"Spend so far (\S+) of the", line3).group(1)
    assert token != "$0.0000", line3
    assert float(token.lstrip("$")) != 0.0, line3
