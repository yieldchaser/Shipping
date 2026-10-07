"""Unit tests for scripts/parse_engine. No network, no paid calls."""
from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pymupdf
import pytest

from scripts.parse_engine import cache as pcache
from scripts.parse_engine import engine as eng
from scripts.parse_engine import geom_table as gt
from scripts.parse_engine import normalize as nz
from scripts.parse_engine import validate as val
from scripts.parse_engine.config import (load_profile, pages_to_spec, resolve_pdf, select_pages,
                                         spec_to_pages)
from scripts.parse_engine.dates import parse_issue_date
from scripts.parse_engine.keys import KeyPool, key_id, mask
from scripts.parse_engine.llama import build_v2_configuration, estimate_credits

CLARKSONS = load_profile("clarksons")
LONG_TEXT = "Recycling commentary continues here with enough running text to be a real content page of the weekly bulletin. " * 2


# ------------------------------------------------------------------------------------ page rules
def test_drop_last_default():
    assert select_pages(3, {"drop_last": 1}) == [1, 2]


def test_drop_first_and_last():
    assert select_pages(5, {"drop_first": 1, "drop_last": 1}) == [2, 3, 4]


def test_year_conditional_rule():
    rule = [{"until_year": 2023, "drop_last": 2}, {"from_year": 2024, "drop_last": 1}]
    assert select_pages(5, rule, 2022) == [1, 2, 3]
    assert select_pages(5, rule, 2023) == [1, 2, 3]
    assert select_pages(5, rule, 2024) == [1, 2, 3, 4]
    assert select_pages(5, rule, None) == [1, 2, 3, 4, 5]  # unknown year: no conditional rule applies


def test_rule_never_returns_empty():
    assert select_pages(1, {"drop_last": 1}) == [1]


def test_page_spec_roundtrip():
    assert pages_to_spec([1, 2, 3, 5, 7, 8]) == "1-3,5,7-8"
    assert spec_to_pages("1-3,5,7-8") == [1, 2, 3, 5, 7, 8]
    assert pages_to_spec([4]) == "4"


def _pdf(tmp_path: Path, pages: list[str], name: str = "doc.pdf") -> Path:
    doc = pymupdf.open()
    for text in pages:
        lines = [w for ln in text.split("\n") for w in (textwrap.wrap(ln, 70) or [""])]
        doc.new_page().insert_text((50, 80), "\n".join(lines), fontsize=11)
    path = tmp_path / name
    doc.save(path)
    return path


def test_two_page_pdf_keeps_page2_when_not_boilerplate(tmp_path):
    pdf = _pdf(tmp_path, ["Weekly Bulletin 19 August 2022 " + LONG_TEXT, LONG_TEXT])
    plan = eng.plan_file(pdf, CLARKSONS)
    assert plan.pages == [1, 2]
    assert any(n.startswith("two_page_content_kept") for n in plan.notes)


def test_two_page_pdf_drops_contacts_page(tmp_path):
    pdf = _pdf(tmp_path, ["Weekly Bulletin 19 August 2022 " + LONG_TEXT, "Contacts Disclaimer Kifissias Avenue snp@clarksons.gr"])
    plan = eng.plan_file(pdf, CLARKSONS)
    assert plan.pages == [1]
    assert plan.issue_date == "2022-08-19"


def test_resolve_pdf_absolute_and_corpus_root(tmp_path, monkeypatch):
    (tmp_path / "corpus" / "x").mkdir(parents=True)
    f = tmp_path / "corpus" / "x" / "a.pdf"
    f.write_bytes(b"%PDF")
    monkeypatch.setenv("CORPUS_ROOT", str(tmp_path))
    assert resolve_pdf("corpus/x/a.pdf") == f
    assert resolve_pdf(str(f)) == f


# ------------------------------------------------------------------------------------ issue_date
DATE_PATTERNS = CLARKSONS["date_patterns"]


def test_date_from_header_text():
    assert parse_issue_date(DATE_PATTERNS, "SALE\nClarksons Hellas Weekly Bulletin\n 19 August 2022", "x.pdf") == \
        ("2022-08-19", "header", False, "2022-08-19")


def test_date_from_filename_variants():
    assert parse_issue_date(DATE_PATTERNS, "", "clarksons_02_10_2026_clarksons_hellas_snp_weekly.pdf")[:2] == \
        ("2026-10-02", "filename")
    assert parse_issue_date(DATE_PATTERNS, "", "clarksons_2026_Weekly-Sales-04th-Sept-2026.pdf")[:2] == \
        ("2026-09-04", "filename")
    assert parse_issue_date(DATE_PATTERNS, "", "2023-06-16_clarksons-bulletin-74_report-16-06-2023_ab.pdf")[:2] == \
        ("2023-06-16", "filename")


def test_week_only_header_does_not_invent_a_date():
    intermodal = load_profile("intermodal")["date_patterns"]
    assert parse_issue_date(intermodal, "Weekly Report Week 10 2024", "intermodal_2024_W10_Report-Week-10-2024.pdf") \
        == (None, None, False, None)
    assert parse_issue_date(DATE_PATTERNS, "Week 32 2022 bulletin", "no-date.pdf") == (None, None, False, None)


def test_impossible_date_is_rejected():
    assert parse_issue_date(DATE_PATTERNS, "31 February 2023", "x.pdf")[0] is None


def test_stale_header_earlier_by_1_to_7_days_loses_to_filename():
    fn = "2021-07-09_clarkson-platou-hellas-sp-weekly-bulletin-108_report-09-07-2021_a.pdf"
    assert parse_issue_date(DATE_PATTERNS, "Weekly Bulletin 7 July 2021", fn) ==         ("2021-07-09", "filename_over_stale_header", True, "2021-07-07")
    one = parse_issue_date(DATE_PATTERNS, "8 July 2021", fn)
    assert (one[0], one[2], one[3]) == ("2021-07-09", True, "2021-07-08")
    seven = parse_issue_date(DATE_PATTERNS, "2 July 2021", fn)
    assert seven[0] == "2021-07-09"


def test_header_wins_when_later_or_more_than_7_days_earlier():
    fn = "2022-08-19_x_report-19-08-2022_a.pdf"
    assert parse_issue_date(DATE_PATTERNS, "20 August 2022", fn) == ("2022-08-20", "header", True, "2022-08-20")
    assert parse_issue_date(DATE_PATTERNS, "11 August 2022", fn) == ("2022-08-11", "header", True, "2022-08-11")
    assert parse_issue_date(DATE_PATTERNS, "19 August 2022", fn)[2] is False


# ------------------------------------------------------------------------------------ cache
def test_cache_miss_then_hit(tmp_path):
    assert pcache.cache_get("abc", "llamaparse", "agentic", "2026-01-16", "1-2", root=tmp_path) is None
    path = pcache.cache_put("abc", "llamaparse", "agentic", "2026-01-16", "1-2", {"markdown": "x"}, root=tmp_path)
    assert path == tmp_path / "abc" / "llamaparse_agentic_2026-01-16_1-2.json"
    assert pcache.cache_get("abc", "llamaparse", "agentic", "2026-01-16", "1-2", root=tmp_path) == {"markdown": "x"}
    # a different tier / pages is a different entry
    assert pcache.cache_get("abc", "llamaparse", "fast", "2026-01-16", "1-2", root=tmp_path) is None
    assert pcache.cache_get("abc", "llamaparse", "agentic", "2026-01-16", "1,3", root=tmp_path) is None


class _FakeClient:
    def __init__(self):
        self.calls = 0

    def parse(self, pdf, tier, version, pages, prompt, merge):
        self.calls += 1
        return {"api": "v2", "markdown": "## Heading\n\ntext", "version_resolved": version, "parsed_at_epoch": 1,
                "job_id": "j"}


def test_run_llama_uses_cache_and_budget(tmp_path, monkeypatch):
    monkeypatch.setenv("PARSE_CACHE_DIR", str(tmp_path / "cache"))
    pdf = _pdf(tmp_path, [LONG_TEXT, LONG_TEXT, "Contacts Disclaimer snp@clarksons.gr"])
    plan = eng.plan_file(pdf, CLARKSONS, "llamaparse")
    assert plan.est_credits == 20 and plan.pages == [1, 2]
    client, budget = _FakeClient(), {"spent": 0, "max_credits": 15}
    with pytest.raises(eng.BudgetExceeded):
        eng.run_llama(plan, CLARKSONS, client, budget)
    assert client.calls == 0
    budget = {"spent": 0, "max_credits": 20}
    first = eng.run_llama(plan, CLARKSONS, client, budget)
    assert (client.calls, first["credits_used"], budget["spent"]) == (1, 20, 20)
    second = eng.run_llama(plan, CLARKSONS, client, budget)
    assert (client.calls, second["credits_used"], second["cache_hit"]) == (1, 0, True)


def test_credit_table_and_v2_configuration():
    assert [estimate_credits(t, 1) for t in ("fast", "cost_effective", "agentic", "agentic_plus")] == [1, 3, 10, 45]
    cfg = build_v2_configuration("agentic", "2026-01-16", "1-2", "prompt", True)
    assert cfg["tier"] == "agentic" and cfg["version"] == "2026-01-16"
    assert cfg["page_ranges"] == {"target_pages": "1-2"}
    assert cfg["agentic_options"] == {"custom_prompt": "prompt"}
    assert cfg["output_options"]["markdown"]["tables"]["merge_continued_tables"] is True
    assert "agentic_options" not in build_v2_configuration("fast", "latest", "1", "prompt", False)


def test_key_pool_marks_exhausted_and_never_prints_full_key(tmp_path):
    keys = ["llx-AAAAAAAAAAAA", "llx-BBBBBBBBBBBB"]
    pool = KeyPool(keys, tmp_path / "state.json")
    assert pool.current() == keys[0]
    pool.mark_exhausted(keys[0])
    assert pool.current() == keys[1]
    assert KeyPool(keys, tmp_path / "state.json").current() == keys[1]  # persisted
    state = (tmp_path / "state.json").read_text()
    assert keys[0] not in state and mask(keys[0]) in state and key_id(keys[0]) in state
    assert mask(keys[0]) == "llx-AAA..."


# ------------------------------------------------------------------------------------ validator
GOOD = """---
title: t
---

## New Building

text here about newbuilding orders

| A | B |
|---|---|
| 1 | 2 |
"""


def test_validator_table_metrics():
    md = ("## T\n\n| A | B |\n|---|---|\n\n| A | B | C |\n|---|---|---|\n| 1 | 2 |\n| 3 | 4 | 5 |\n\n"
          "| A | B |\n|---|---|\n| 1 | 2 |\n")
    stats = val.table_stats(val.find_tables(md))
    assert stats == {"tables": 3, "header_only_tables": 1, "ragged_tables": 1}


def test_validator_axis_runs_and_garbage():
    axis = "\n".join(["120", "100", "80", "60", "40", "20"])
    assert val.numeric_runs(f"text\n\n{axis}\n\nmore") == 1
    assert val.numeric_runs("1\n2\n3\n\ntext") == 0
    assert val.numeric_runs("| 1 |\n| 2 |\n| 3 |\n| 4 |\n| 5 |\n| 6 |") == 0  # table rows are not axis dumps
    assert len(val.GARBAGE_RE.findall("bad � and (cid:12) here")) == 2


def test_validator_sections():
    present = val.sections_present("# New Building\n\n**Recycling**\n\ntext", ["New Building", "Recycling", "Desk Talk"])
    assert present == {"New Building": True, "Recycling": True, "Desk Talk": False}


def test_text_recall_ignores_boilerplate(tmp_path):
    pdf = _pdf(tmp_path, ["Tanker earnings strengthened considerably\nwww.example.com Disclaimer applies"])
    full = val.text_recall(pdf, [1], "Tanker earnings strengthened considerably", [], [])
    assert full["text_recall"] == 1.0
    partial = val.text_recall(pdf, [1], "Tanker earnings", [], [])
    assert partial["text_recall"] == pytest.approx(0.5)
    assert "strengthened" in partial["recall_missing_sample"]


def test_table_numeric_recall(tmp_path):
    pdf = _pdf(tmp_path, ["Vessel 31,842 2002 USD 11"])
    region = [{"page": 1, "name": "T", "bbox": (0, 0, 600, 800)}]
    ok = val.table_numeric_recall(region, pdf, "| X | 31,842 | 2002 | USD 11 M |")
    assert ok["table_numeric_recall"] == 1.0
    bad = val.table_numeric_recall(region, pdf, "| X | 31,842 | 2002 |")
    assert bad["table_numeric_recall"] < 1.0 and bad["table_numeric_missing"][0]["token"] == "11"


def test_validate_output_flags_null_issue_date(tmp_path):
    pdf = _pdf(tmp_path, ["New Building orders placed this week"])
    rep = val.validate_output("## New Building\n\nNew Building orders placed this week\n", pdf, [1], {"expected_sections": [{"required": ["New Building"]}]}, None, None, None)
    assert "issue_date_null" in rep["problems"] and rep["sections_missing"] == []
    assert rep["passed"] is True


# ------------------------------------------------------------------------------------ normalise
def test_html_table_rowspan_is_repeated_and_en_bloc_marked():
    html = ("<table><tr><td>Vessel</td><td>Price</td><td>Buyer</td></tr>"
            "<tr><td>A</td><td rowspan=\"2\">USD 10 M</td><td rowspan=\"2\">GREEK</td></tr>"
            "<tr><td>B</td></tr></table>")
    out = nz.html_tables_to_gfm(html)
    rows = [l for l in out.split("\n") if l.startswith("|")]
    assert rows[2] == "| A | USD 10 M (en bloc) | GREEK |"
    assert rows[3] == "| B | USD 10 M (en bloc) | GREEK |"


def test_html_empty_table_becomes_no_reported_sales():
    html = "<table><tr><th>Vessel</th><th>DWT</th></tr><tr><td>-</td><td>-</td></tr></table>"
    assert "| No reported sales |  |" in nz.html_tables_to_gfm(html)


def test_clean_markdown_strips_banners_images_and_spaces_tables():
    md = ("![](img_p1_1.png)\n\nPage 2\n\nSale & Purchase | Clarksons Hellas Weekly Bulletin | 19 Aug. 22\n\n"
          "## Recycling\ntext\n| A | B |\n|---|---|\n| 1 | 2 |\nafter table\n\n"
          "Sale & Purchase | Clarksons Hellas Weekly Bulletin | 19 Aug. 22\n\n"
          "The material and the information contained herein are provided by Clarkson Hellas Ltd")
    out = nz.clean_markdown(md, CLARKSONS)
    assert "img_p1" not in out and "Page 2" not in out and "Weekly Bulletin" not in out
    assert "The material and the information" not in out
    assert "text\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\nafter table" in out


def test_frontmatter_has_required_fields():
    fm = nz.build_frontmatter({"title": "T", "publisher": "P", "source": "s", "issue_date": None, "year": None,
                               "source_file": "corpus/a.pdf", "source_sha256": "x", "pages_total": 3,
                               "pages_parsed": "1-2", "parser": "p", "parsed_at": "now"})
    assert "issue_date: null" in fm and fm.startswith("---\n") and fm.rstrip().endswith("---")


# ------------------------------------------------------------------------------------ geometry
def _table_pdf(tmp_path: Path, rulings: bool) -> Path:
    doc = pymupdf.open()
    pg = doc.new_page()
    pg.insert_text((40, 60), "Bulk Carriers", fontsize=11)
    xs = [40, 140, 200, 330, 420, 500]
    heads = ["Vessel", "DWT", "Details", "Price", "Buyer"]
    for x, h in zip(xs, heads):
        pg.insert_text((x + 4, 95), h, fontsize=9)
    rows = [("ALPHA", "50,000", "MAN 6S50", None, None, 120), ("BETA", "50,100", "MAN 6S50", None, None, 150),
            ("GAMMA", "30,000", "WARTSILA", "USD 5 M", "TURKISH", 180)]
    for name, dwt, det, price, buyer, y in rows:
        pg.insert_text((xs[0] + 4, y), name, fontsize=9)
        pg.insert_text((xs[1] + 4, y), dwt, fontsize=9)
        pg.insert_text((xs[2] + 4, y), det, fontsize=9)
        if price:
            pg.insert_text((xs[3] + 4, y), price, fontsize=9)
            pg.insert_text((xs[4] + 4, y), buyer, fontsize=9)
    # the merged price/buyer cell of ALPHA+BETA is vertically centred between the two vessel lines
    pg.insert_text((xs[3] + 4, 138), "USD 10 M", fontsize=9)
    pg.insert_text((xs[4] + 4, 138), "GREEK", fontsize=9)
    if rulings:
        for y in (80, 105, 135, 165, 195):
            # price/buyer cells of the first two rows are merged: no ruling between them there
            segs = [(xs[0], xs[3])] if y == 135 else [(xs[0], xs[-1])]
            if y == 135:
                segs = [(xs[0], xs[3])]
            for a, b in segs:
                pg.draw_line((a, y), (b, y), color=(0.5, 0.5, 0.5), width=0.6)
        for x in xs:
            pg.draw_line((x, 80), (x, 195), color=(0.5, 0.5, 0.5), width=0.6)
    path = tmp_path / ("ruled.pdf" if rulings else "plain.pdf")
    doc.save(path)
    return path


CFG = [{"name": "Bulk Carriers", "anchor": "^Bulk Carriers", "headers": ["Vessel", "DWT", "Details", "Price", "Buyer"],
        "key_column": 1, "row_start_pattern": "\\d", "span_columns": ["Price", "Buyer"]}]


def test_geometric_table_with_rulings_flags_merged_cells(tmp_path):
    pdf = _table_pdf(tmp_path, rulings=True)
    tables = gt.find_tables(pymupdf.open(pdf)[0], 1, CFG)
    assert len(tables) == 1
    t = tables[0]
    assert t.boundary_source == "rulings" and t.row_source == "rulings"
    assert t.columns == ["Vessel", "DWT", "Details", "Price", "Buyer"]
    assert t.rows[0] == ["ALPHA", "50,000", "MAN 6S50", "USD 10 M (en bloc)", "GREEK"]
    assert t.rows[1] == ["BETA", "50,100", "MAN 6S50", "USD 10 M (en bloc)", "GREEK"]
    assert t.rows[2] == ["GAMMA", "30,000", "WARTSILA", "USD 5 M", "TURKISH"]
    assert t.en_bloc_rows == [0, 1]


def test_geometric_table_without_rulings_uses_header_midpoints(tmp_path):
    pdf = _table_pdf(tmp_path, rulings=False)
    t = gt.find_tables(pymupdf.open(pdf)[0], 1, CFG)[0]
    assert t.boundary_source == "header-midpoints" and t.row_source == "key-column"
    assert [r[0] for r in t.rows] == ["ALPHA", "BETA", "GAMMA"]
    assert t.rows[2][3:] == ["USD 5 M", "TURKISH"]
    assert t.rows[0][1] == "50,000"  # numbers are verbatim


def test_geometric_table_markdown_and_json_shape(tmp_path):
    t = gt.find_tables(pymupdf.open(_table_pdf(tmp_path, rulings=True))[0], 1, CFG)[0]
    md = t.to_markdown(2)
    assert md.startswith("## Bulk Carriers\n\n| Vessel | DWT |")
    js = t.to_json()
    assert set(js) >= {"name", "columns", "rows", "bbox", "page"}
    json.dumps(js)


def test_missing_headers_means_no_table(tmp_path):
    cfg = [dict(CFG[0], headers=["Vessel", "Nonexistent"])]
    assert gt.find_tables(pymupdf.open(_table_pdf(tmp_path, rulings=True))[0], 1, cfg) == []


def test_split_columns_year_yard():
    rows, cols, _ = gt._apply_splits(
        [{"column": "Built", "into": ["Year", "Yard"], "pattern": "^((?:19|20)\\d{2})\\s*(.*)$"}],
        ["Vessel", "Built"], [["A", "2002 HAKODATE"], ["B", "unknown"]], [])
    assert cols == ["Vessel", "Year", "Yard"]
    assert rows == [["A", "2002", "HAKODATE"], ["B", "unknown", ""]]


def test_merge_removes_table_blocks_and_orders_by_position(tmp_path):
    pdf = _table_pdf(tmp_path, rulings=True)
    page = pymupdf.open(pdf)[0]
    t = gt.find_tables(page, 1, CFG)
    md = "Intro paragraph before.\n\n# Bulk Carriers\n\n| Vessel | DWT |\n|---|---|\n| ALPHA | 50,000 |\n\nTrailing paragraph."
    out = gt.merge_prose_and_tables(md, t, gt.page_words(page), 2)
    assert out.startswith("Intro paragraph before.")
    assert out.count("ALPHA") == 1  # LiteParse fragment dropped, geometric row kept
    assert "| ALPHA | 50,000 | MAN 6S50 | USD 10 M (en bloc) | GREEK |" in out
    assert "Trailing paragraph." in out


def test_broken_glyph_repair():
    assert gt.repair_word("�") == "–"
    assert gt.repair_word("vessel�s") == "vessel’s"
    assert gt.repair_word("�as") == "“as"
    assert gt.repair_word("plain") == "plain"


def test_year_typo_in_header_loses_to_filename_when_filename_year_is_folder_year():
    fn = "2022-01-21_clarksons-platou-hellas-snp-weekly-bulletin-5_report-21-01-2021_a3fb3f45981f.pdf"
    r = parse_issue_date(DATE_PATTERNS, "Weekly Bulletin 21 January 2021", fn, folder_year=2022)
    assert r == ("2022-01-21", "filename_over_header_year_typo", True, "2021-01-21")
    # without a matching folder year the typo rule does not apply (the second filename date then corroborates the header)
    assert parse_issue_date(DATE_PATTERNS, "21 January 2021", fn, folder_year=2021)[1] != "filename_over_header_year_typo"


def test_header_wins_when_a_second_filename_date_equals_it():
    fn = "2022-04-22_clarksons-platou-hellas-snp-weekly-bulletin-15_report-23-04-2022_59c9d2476238.pdf"
    r = parse_issue_date(DATE_PATTERNS, "Hellas S&P Weekly Bulletin 23 April 2022", fn, folder_year=2022)
    assert r == ("2022-04-23", "header", False, "2022-04-23")     # printed report-23-04-2022 date is primary
    fn2 = "2022-10-28_clarksons-platou-hellas-snp-weekly-bulletin-42_report-29-10-2022_d88997c2e5f4.pdf"
    assert parse_issue_date(DATE_PATTERNS, "29 October 2022", fn2, folder_year=2022)[0] == "2022-10-29"


def test_lowercase_weekly_sales_name_gives_the_printed_date_not_the_crawl_prefix():
    fn = "2026-03-07_clarksons-platou-hellas-snp-weekly-bulletin-124_weekly-sales-06th-mar-2026_aaaaaaaaaaaa.pdf"
    assert parse_issue_date(DATE_PATTERNS, "", fn, folder_year=2026)[:2] == ("2026-03-06", "filename")
    fn2 = "clarksons_2026_Weekly-Sales-2nd-October-2026.pdf"
    assert parse_issue_date(DATE_PATTERNS, "", fn2)[0] == "2026-10-02"
    fn3 = "2025-10-24_clarksons-platou-hellas-snp-weekly-bulletin-111_weekly-sales-24th-oct-2025_e721320e3ba1.pdf"
    assert parse_issue_date(DATE_PATTERNS, "", fn3)[0] == "2025-10-24"


def test_year_typo_still_picks_the_prefix_when_the_report_date_repeats_the_typo():
    fn = "2022-01-21_clarksons-platou-hellas-snp-weekly-bulletin-5_report-21-01-2021_a3fb3f45981f.pdf"
    r = parse_issue_date(DATE_PATTERNS, "21 January 2021", fn, folder_year=2022)
    assert r[:2] == ("2022-01-21", "filename_over_header_year_typo")
