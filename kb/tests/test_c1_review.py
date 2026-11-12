"""Tests for kb/c1_review.py — the C1 checkpoint packet generator."""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "kb" / "reports" / "C1_REVIEW.md"


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
