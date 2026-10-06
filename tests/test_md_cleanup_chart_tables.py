"""Unit tests for scripts/md_cleanup/chart_tables. Synthetic MD + fake text layers; no corpus access."""
from __future__ import annotations

from scripts.md_cleanup import chart_tables as ct

PROSE = "The market was firm and the rates of the week were in line with the trend of the last few weeks " * 4


def info_for(text: str) -> dict:
    return ct.build_text_info(PROSE + " " + text)


def run(md: str, text: str | None, guard: bool = False):
    info = None if text is None else info_for(text)
    return ct.clean_markdown(md, lambda: info, guard)


def run_no_layer(md: str):
    return ct.clean_markdown(md, lambda: ct.build_text_info(""), False)


CHART_MD = """# Report

## CAPESIZE FORWARD CURVE (USD/DAY)

| Date | Value |
| --- | --- |
| Mar-24 | 28000 |
| Apr-24 | 30000 |
| May-24 | 31000 |
| Jun-24 | 33000 |

Prose stays.
"""

SUPRAMAX_MD = (
    "## SUPRAMAX\n\n| Tenor | Unit | 6-Jun |\n| - | - | - |\n| BSI 63 | usd/day | 11,796 |\n"
    "| BSI 58 | usd/day | 9,762 |\n| P1 | usd/day | 14,895 |\n| P2 | usd/day | 15,545 |\n"
)


def test_num_candidates_separator_variants():
    assert ct.num_candidates("33,0") == ct.num_candidates("33.0")
    assert 1234.0 in ct.num_candidates("1.234")
    assert 1234.0 in ct.num_candidates("1,234")
    assert ct.num_candidates("1,234.5") == frozenset({1234.5})
    assert ct.num_candidates("1.234,5") == frozenset({1234.5})
    assert ct.num_candidates("12,345,678") == frozenset({12345678.0})
    assert ct.num_candidates("abc") == frozenset()


def test_cell_numeric_normalisation_and_ignores():
    assert 12500.0 in ct.cell_numeric("$12,500")
    assert 1250.0 in ct.cell_numeric("£1,250")
    assert ct.cell_numeric("-3.2%") == frozenset({3.2})
    assert ct.cell_numeric("2021") is None
    assert ct.cell_numeric("1989") == frozenset({1989.0})
    assert ct.cell_numeric("23/Dec/21") is None
    assert ct.cell_numeric("Feb-25") is None
    assert ct.cell_numeric("Date") is None


def test_unprinted_chart_table_is_replaced_and_heading_kept():
    new, recs = run(CHART_MD, "nothing relevant 5 6 7")
    assert recs[0]["cls"] == "GUESSED"
    assert "## CAPESIZE FORWARD CURVE (USD/DAY)" in new
    assert ("> Figure: CAPESIZE FORWARD CURVE (USD/DAY) — chart values not transcribed "
            "(not printed in the source; visual estimates removed).") in new
    assert "| Mar-24 |" not in new
    assert "Prose stays." in new


def test_printed_data_labels_are_kept():
    new, recs = run(CHART_MD, "labels 28,000 30,000 31,000 33,000")
    assert recs[0]["cls"] == "KEEP_VERIFIED"
    assert recs[0]["printed_ratio"] == 1.0
    assert new == CHART_MD


def test_threshold_boundary():
    md = "## Prices\n\n| A | B |\n| - | - |\n| x | 11 |\n| y | 22 |\n| z | 33 |\n| w | 44 |\n| v | 55 |\n"
    _, recs = run(md, "11 22 33")
    assert recs[0]["printed_ratio"] == 0.6 and recs[0]["cls"] == "KEEP_VERIFIED"
    _, recs = run(md, "11 22")
    assert recs[0]["cls"] == "GUESSED"


def test_small_tables_never_removed():
    md = "## Prices\n\n| A | B |\n| - | - |\n| x | 11 |\n| y | 22 |\n"
    new, recs = run(md, "unrelated")
    assert recs[0]["cls"] == "KEEP_SMALL" and new == md


def test_no_text_layer_uses_title_list():
    new, recs = run_no_layer(CHART_MD)
    assert recs[0]["cls"] == "GUESSED" and recs[0]["reason"] == "no_text_layer+chart_title"
    other = CHART_MD.replace("CAPESIZE FORWARD CURVE (USD/DAY)", "Fleet Statistics")
    new, recs = run_no_layer(other)
    assert recs[0]["cls"] == "KEEP_UNVERIFIABLE" and new == other


def test_missing_source_uses_title_list():
    _, recs = run(CHART_MD, None)
    assert recs[0]["cls"] == "GUESSED" and recs[0]["reason"].startswith("no_source")
    other = CHART_MD.replace("CAPESIZE FORWARD CURVE (USD/DAY)", "Fleet Statistics")
    new, recs = run(other, None)
    assert recs[0]["cls"] == "KEEP_UNVERIFIABLE" and new == other


def test_ciphered_text_layer_is_not_usable():
    garbage = " ".join(f"xq{i}zv" for i in range(200))
    assert ct.build_text_info(garbage)["usable"] is False
    assert ct.build_text_info("too few words")["usable"] is False


def test_html_table_replaced():
    md = ("## 1-Year Forward WS Rates - Clean\n\n<table>\n<tr><th>Date</th><th>WS</th></tr>\n"
          "<tr><td>Jan</td><td>100</td></tr>\n<tr><td>Feb</td><td>110</td></tr>\n"
          "<tr><td>Mar</td><td>120</td></tr>\n<tr><td>Apr</td><td>130</td></tr>\n</table>\n\nafter\n")
    new, recs = run(md, "empty 5")
    assert recs[0]["kind"] == "html" and recs[0]["cls"] == "GUESSED"
    assert "<table>" not in new and "after" in new
    assert "> Figure: 1-Year Forward WS Rates - Clean" in new


def test_real_table_with_printed_values_is_kept():
    md = ("## Spot rates\n\n| Route | Rate |\n| - | - |\n| A | £12,500 |\n| B | £11,250 |\n"
          "| C | £10,000 |\n| D | £9,750 |\n")
    new, recs = run(md, "Rates 12 500 or 11.250 10,000 9,750")
    assert recs[0]["cls"] == "KEEP_VERIFIED" and new == md


def test_frontmatter_is_not_touched_and_tables_after_it_found():
    md = "---\ntitle: x\nsource_file: \"a.pdf\"\n---\n\n" + CHART_MD
    new, recs = run(md, "nothing 5")
    assert new.startswith("---\ntitle: x\n") and len(recs) == 1


def test_guard_published_keeps_non_time_series_low_ratio():
    _, recs = run(SUPRAMAX_MD, "nothing 5", guard=False)
    assert recs[0]["cls"] == "GUESSED" and recs[0]["time_series"] is False
    new, recs = run(SUPRAMAX_MD, "nothing 5", guard=True)
    assert recs[0]["cls"] == "KEEP_UNVERIFIABLE" and new == SUPRAMAX_MD
    _, recs = run(CHART_MD, "nothing 5", guard=True)
    assert recs[0]["cls"] == "GUESSED"


def test_structural_flags_on_kept_table():
    md = ("## Misc\n\n| Date | A |\n| - | - |\n| Jan | 100 |\n| Feb | 110 |\n| Mar | 120 |\n| Apr | 130 |\n"
          "| Date | A |\n")
    new, recs = run(md, "100 110 120 130")
    assert recs[0]["cls"] == "KEEP_VERIFIED"
    assert "arith_progression_col" in recs[0]["flags"] and "duplicate_header_row" in recs[0]["flags"]
    assert new == md


def test_resolve_source_prefers_frontmatter_then_stem(tmp_path):
    root = tmp_path / "main"
    pdf = root / "corpus" / "x" / "a.pdf"
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(b"%PDF")
    md = tmp_path / "a.md"
    assert ct.resolve_source(md, "corpus/x/a.pdf", [root]) == pdf
    assert ct.resolve_source(md, "corpus/missing/a.pdf", [root], {"a": pdf}) == pdf
    assert ct.resolve_source(md, None, [root], {}) is None


def test_html_source_text_is_visible_text(tmp_path):
    h = tmp_path / "s.html"
    h.write_text("<html><script>var x=999999;</script><body><p>Rate 4,321 today</p></body></html>",
                 encoding="utf-8")
    keys = ct.text_numeric_keys(ct.load_source_text(h))
    assert 4321.0 in keys and 999999.0 not in keys


def test_process_file_writes_only_changed_copy(tmp_path, monkeypatch):
    monkeypatch.setattr(ct, "_STEM_INDEX", {})
    md = tmp_path / "repo" / "data" / "extracted" / "md" / "pub" / "r.md"
    md.parent.mkdir(parents=True)
    md.write_text(CHART_MD, encoding="utf-8")
    out = tmp_path / "out"
    res = ct.process_file((str(md), "data/extracted/md/pub/r.md", "pub", [str(tmp_path / "none")],
                           str(out), True, False))
    assert res["changed"] is True
    assert "chart values not transcribed" in (out / "data/extracted/md/pub/r.md").read_text(encoding="utf-8")
    assert "| Mar-24 |" in md.read_text(encoding="utf-8")


def test_is_time_series_shapes():
    assert ct.is_time_series([["Week", "2024"], ["1", "0.8"], ["10", "1.1"]])
    assert ct.is_time_series([["x", "y"], ["Jul 2024", "1"], ["Jan 2025", "2"]])
    assert not ct.is_time_series([["Tenor", "Unit"], ["BSI 63", "usd/day"], ["BSI 58", "usd/day"]])



def test_vector_engine_sections_are_never_removed():
    md = ("## Freight Indicators & Vector Charts\n\n### Capesize 5TC\n\n"
          "| Date | Value |\n| - | - |\n| Jan-24 | 11 |\n| Feb-24 | 12 |\n| Mar-24 | 13 |\n| Apr-24 | 15 |\n")
    new, recs = run(md, "nothing 5", guard=True)
    assert recs[0]["cls"] == "KEEP_VECTOR" and new == md
    own = md.replace("## Freight Indicators & Vector Charts\n\n### Capesize 5TC", "## Vector chart: Capesize 5TC")
    new, recs = run(own, "nothing 5", guard=True)
    assert recs[0]["cls"] == "KEEP_VECTOR" and new == own
    after = md + "\n## Other\n\n" + CHART_MD.split("\n\n", 2)[2]
    _, recs = run(after, "nothing 5", guard=True)
    assert [r["cls"] for r in recs] == ["KEEP_VECTOR", "GUESSED"]


def test_guard_is_default_and_ism_scope_excluded():
    new, recs = ct.clean_markdown(SUPRAMAX_MD, lambda: info_for("nothing 5"))
    assert recs[0]["cls"] == "KEEP_UNVERIFIABLE" and new == SUPRAMAX_MD
    assert "ism" not in ct.SCOPES
