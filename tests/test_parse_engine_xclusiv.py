"""Tests for the Xclusiv 2021-2023 template parser (profile `xclusiv`, module scripts/parse_engine/xclusiv.py)."""
from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import pymupdf
import pytest

from scripts.parse_engine import engine as eng
from scripts.parse_engine import export_series, xclusiv
from scripts.parse_engine import validate as val
from scripts.parse_engine.config import MAIN_CHECKOUT, REPO_ROOT, load_profile, select_pages
from scripts.parse_engine.dates import parse_issue_date

PROFILE = load_profile("xclusiv")
XS = [29, 125, 164, 202, 253, 346, 450, 510, 752]          # column rules of the sales tables


def _text(page: pymupdf.Page, x: float, y: float, text: str, size: float = 6.5) -> None:
    page.insert_text((x, y), text, fontsize=size)


def _sales_page(*, merge_buyers: bool, year_rule_missing: bool = False) -> pymupdf.Page:
    """A sales table drawn like the source PDFs: per-cell rules; the buyer cell of rows B and C is one cell."""
    doc = pymupdf.open()
    page = doc.new_page(width=780, height=540)
    ys = [60, 72, 84, 96, 108, 120, 132]
    for y in ys:
        for c in range(8):
            skip = (merge_buyers and y == 108 and c == 5) or (year_rule_missing and y in (96, 108) and c == 2)
            if not skip:
                page.draw_line((XS[c], y), (XS[c + 1], y), width=0.6)
    for x in XS:
        page.draw_line((x, 60), (x, 132), width=0.6)
    _text(page, 360, 69, "BULK CARRIER SALES")
    for x, h in zip(XS, ["NAME", "DWT", "YEAR", "COUNTRY", "YARD", "BUYERS", "PRICE (usd mills)", "NOTES/ COMMENTS"]):
        _text(page, x + 3, 81, h)
    rows = [("ALPHA", "81,922", "2017", "CHINA", "YARD A", "HOA PHAT", "rgn 35", "BWTS FTD"),
            ("BRAVO", "82,937", "2013", "JAPAN", "YARD B", "BELSHIPS" if merge_buyers else "BUYER B", "$28", "SS/DD: 10/2021"),
            ("CHARLIE", "77,111", "2015", "JAPAN", "YARD C", "" if merge_buyers else "BUYER C", "$28", "SS/DD: 12/2021"),
            ("DELTA", "79,457", "2011", "CHINA", "YARD D", "TMS", "low 17", "")]
    for r, row in enumerate(rows):
        for c, cell in enumerate(row):
            if cell:
                _text(page, XS[c] + 3, ys[r + 2] + 9, cell)
    return page


def test_sales_table_reads_rows_and_carries_a_merged_buyer_to_every_vessel():
    tables, problems, _ = xclusiv.sales_tables(_sales_page(merge_buyers=True), 4, None)
    assert problems == []
    assert len(tables) == 1 and tables[0]["sales_title"] == "BULK CARRIER SALES"
    rows = tables[0]["rows"]
    assert [r[0] for r in rows] == ["ALPHA", "BRAVO", "CHARLIE", "DELTA"]
    assert [r[5] for r in rows] == ["HOA PHAT", "BELSHIPS", "BELSHIPS", "TMS"]
    assert rows[0][6] == "rgn 35" and rows[3][6] == "low 17"        # price text is kept as printed
    assert rows[3][7] == ""                                          # an empty cell stays empty


def test_per_vessel_columns_are_never_merged_even_when_a_rule_is_missing():
    tables, _, _ = xclusiv.sales_tables(_sales_page(merge_buyers=False, year_rule_missing=True), 4, None)
    assert [r[2] for r in tables[0]["rows"]] == ["2017", "2013", "2015", "2011"]


def test_sales_rows_md_is_the_2024_layout_without_derived_columns():
    tables, _, _ = xclusiv.sales_tables(_sales_page(merge_buyers=False), 4, None)
    cols, rows = xclusiv.sales_rows_md(tables[0], True)
    assert cols == ["Section", "Name", "DWT", "Year", "Country", "Yard", "Buyers", "Price ($M)", "Comments"]
    assert rows[0][:3] == ["Bulk Carriers", "ALPHA", "81,922"]
    cols_o, rows_o = xclusiv.sales_rows_md({**tables[0], "sales_title": "GAS SALES", "unit": "CBM"}, False)
    assert cols_o[2:4] == ["Size", "Size Unit"] and rows_o[0][:4] == ["Gas", "ALPHA", "81,922", "CBM"]


def _panel_page() -> pymupdf.Page:
    doc = pymupdf.open()
    page = doc.new_page(width=780, height=540)
    page.draw_rect(pymupdf.Rect(426, 65, 766, 76), fill=(0.9, 0.9, 0.9))
    y = 72

    def row(label: str, nums: list[str], dy: float = 11) -> None:
        nonlocal y
        y += dy
        _text(page, 430, y, label)
        for i, n in enumerate(nums):
            _text(page, 470 + 26 * i, y, n)

    _text(page, 520, y, "BALTIC DRY INDICES")
    row("BALTIC INDICES Week 26 Week 25", ["+/-%"])
    row("2022", ["2021", "2020"])
    row("BDI", ["2,214", "2,331", "-5.0%", "2,284", "2,943", "1,064"])
    row("BCI", ["2,381", "2,396", "-0.6%", "2,190", "4,015", "1,752"])
    y += 14
    _text(page, 500, y, "DRY NEWBUILDING PRICES (in USD mills)")
    row("Size Segment Jul/22 Jul/21", ["+/-%"])
    row("2022", ["2021", "2020"])
    row("Capesize", ["$", "64.0", "$", "59.3", "8%", "$", "61.8", "$", "56.0", "$", "47.6"])
    y += 14
    _text(page, 500, y, "DEMOLITION PRICES (in USD/ldt)")
    row("Demo Country Week 26 Week 25 Change", [])
    row("INDIA", ["570", "580", "-10", "575", "585", "(10)"])
    row("TURKEY", ["310", "315", "-", "320", "325", "-5"])
    return page


def test_panel_tables_read_indices_prices_and_demolition_from_word_rows():
    page = _panel_page()
    x0 = xclusiv.panel_x0(page)
    assert x0 == pytest.approx(426, abs=1)
    tables, problems = xclusiv.panel_tables(page, 1, x0, 500)
    assert problems == []
    by = {t["name"]: t for t in tables}
    assert by["Baltic Dry Indices"]["rows"][0] == ["BDI", "2,214", "2,331", "-5.0%", "2022: 2,284 / 2021: 2,943 / 2020: 1,064"]
    nb = by["Dry Newbuilding Prices"]["rows"][0]
    assert nb[:4] == ["Dry", "Capesize", "$64.0M", "$59.3M"] and nb[5].startswith("2022: 61.8")      # "$" printed as its own word
    demo = by["Demolition Prices"]["rows"]
    assert ["Bulkers", "India", "$570", "$580", "-10"] in demo and ["Tankers", "India", "$575", "$585", "(10)"] in demo
    assert ["Bulkers", "Turkey", "$310", "$315", "-"] in demo       # a lone dash is a printed cell


def test_panel_row_with_wrong_cell_count_is_reported_not_guessed():
    page = _panel_page()
    _text(page, 430, 300, "BHSI")
    _text(page, 490, 300, "1,276")
    tables, problems = xclusiv.panel_tables(page, 1, xclusiv.panel_x0(page), 500)
    assert problems and "rows_with_unexpected_cells" in problems[0]
    assert all(r[0] != "BHSI" for t in tables for r in t["rows"])


def test_overprinted_words_keep_only_the_visible_top_word():
    doc = pymupdf.open()
    page = doc.new_page(width=780, height=540)
    _text(page, 50, 100, "SHUANG")
    _text(page, 50, 100, "XIN")                 # printed over the first one: the visible word
    _text(page, 50, 140, "SAME")
    _text(page, 50.5, 140.4, "SAME")            # exact repeat
    assert [w[4] for w in xclusiv._words(page)] == ["XIN", "SAME"]


# ------------------------------------------------------------------------------------ text helpers
def test_glyph_repair_restores_apostrophes_and_quotes():
    assert xclusiv.fix_glyphs("It�s the �Van Continent� - 74K") == "It’s the “Van Continent” - 74K"
    assert xclusiv.fix_glyphs("plain text") == "plain text"


def test_negative_figure_wrapped_after_its_sign_is_rejoined():
    assert xclusiv._plain("trip is USD -\n10,867/day") == "trip is USD -10,867/day"
    assert xclusiv._plain("pages 5 - 6") == "pages 5 - 6"


def test_hyphen_at_line_end_is_dropped_only_for_words_printed_whole(monkeypatch):
    xclusiv.set_vocabulary({"scrubber", "transatlantic"})
    try:
        assert xclusiv.glue("the Scrub-", "ber fitted") == "the Scrubber fitted"
        assert xclusiv.glue("the de-", "escalate talks") == "the de-escalate talks"
        assert xclusiv.glue("a pre-", "pandemic level") == "a pre-pandemic level"
        assert xclusiv.glue("ended.", "Next") == "ended. Next"
    finally:
        xclusiv.set_vocabulary(None)


def test_sp_commentary_is_split_into_dry_then_wet_paragraphs():
    paras = ["The dry S&P market had more activity than wet. The Capesize “A” was sold for USD 20 mills.",
             "In the VLCC sector the “B” changed hands for USD 60 mills.",
             "On the Handysize side the “C” was sold."]
    dry, wet = xclusiv.split_sp_commentary(paras)
    assert dry == paras[:1] and wet == paras[1:]
    dry, wet = xclusiv.split_sp_commentary(["Similarly to the dry firm S&P, the tanker S&P activity was strong with tankers sold."])
    assert dry == [] and len(wet) == 1
    dry, wet = xclusiv.split_sp_commentary(["Only a dry paragraph about the Capesize sector."])
    assert wet == [] and len(dry) == 1


def test_paragraph_without_gap_is_split_after_a_short_sentence_final_line():
    def ln(text: str, x1: float, y: float):
        return SimpleNamespace(text=text, plain=text, bbox=(30, y, x1, y + 8))

    lines = [ln("The dry market was firm and the Capesize sector was busy this week.", 400, 100),
             ln("Capesize deals were reported at the end of the week.", 330, 110),
             ln("On the tanker side, Hafnia acquired two vessels and the rest followed.", 400, 120)]
    para = SimpleNamespace(lines=lines, heading=0, bbox=(30, 100, 400, 128), text="")
    pieces = xclusiv.split_paragraph(para)
    assert [p[1] for p in pieces] == [" ".join(l.text for l in lines[:2]), lines[2].text]


def test_section_label_and_other_sales_title():
    assert [xclusiv.section_label(t) for t in ("BULK CARRIER SALES", "TANKER SALES ", "GAS SALES", "OBO SALES",
                                               "GENERAL CARGO SALES")] == ["Bulk Carriers", "Tankers", "Gas", "OBO", "General Cargo"]


# ------------------------------------------------------------------------------------ profile and engine hooks
def test_profile_reads_first_five_pages_of_six_and_seven_page_reports():
    rule = PROFILE["pages"]
    assert select_pages(6, rule, 2021) == [1, 2, 3, 4, 5]
    assert select_pages(7, rule, 2023) == [1, 2, 3, 4, 5]
    assert select_pages(3, rule, 2022) == [1, 2, 3]


def test_issue_date_is_the_printed_date_line_not_a_date_mentioned_in_commentary():
    header = ("Market Commentary:\nSpecifically, on 7th October 2021 the BDI attained 5,650 points.\n"
              "Page 1\n18th October 2021\n")
    iso, source, conflict, head = parse_issue_date(PROFILE["date_patterns"], header, "xclusiv_2021_xclusiv_weekly_2021_10_18.pdf",
                                                   PROFILE["header_text_chars"], folder_year=2021)
    assert (iso, source, conflict, head) == ("2021-10-18", "header", False, "2021-10-18")
    assert parse_issue_date(PROFILE["date_patterns"], "no date", "xclusiv_2021_xclusiv_weekly_2021_10_4.pdf",
                            folder_year=2021)[0] == "2021-10-04"


def test_numeric_recall_ignores_only_the_profile_label_tokens(tmp_path):
    doc = pymupdf.open()
    page = doc.new_page(width=780, height=540)
    _text(page, 100, 100, "Resale 5y 10y Oct/21 64.0 777")
    pdf = tmp_path / "t.pdf"
    doc.save(pdf)
    reg = [{"page": 1, "name": "t", "bbox": [90, 90, 400, 110]}]
    strict = val.table_numeric_recall(reg, pdf, "| 64.0 |")
    lenient = val.table_numeric_recall(reg, pdf, "| 64.0 |", PROFILE["numeric_recall_ignore"])
    assert {m["token"] for m in strict["table_numeric_missing"]} == {"5y", "10y", "Oct/21", "777"}
    assert {m["token"] for m in lenient["table_numeric_missing"]} == {"777"}


def test_sidecar_can_skip_the_clarksons_vessel_row_flattening():
    tables = [{"name": "Bulk Carrier Sales", "page": 4, "empty": False, "columns": ["Section", "Name", "DWT"],
               "rows": [["Bulk Carriers", "ALPHA", "81,922"]]}]
    plain = export_series.sidecar_payload(tables, "2022-07-01", "x.pdf", "sha", vessel_rows=False)
    assert plain["sales_count"] == 0 and plain["demo_count"] == 0 and plain["tables"] == tables


def test_vocabulary_is_built_from_the_corpus_folder_and_is_lowercase(tmp_path):
    doc = pymupdf.open()
    _text(doc.new_page(), 50, 100, "Scrubber FITTED well-known 123")
    (tmp_path / "2022").mkdir()
    doc.save(tmp_path / "2022" / "a.pdf")
    xclusiv.set_vocabulary(None)
    old = xclusiv._VOCAB_DIR
    xclusiv._VOCAB_DIR = tmp_path
    try:
        assert xclusiv.vocabulary() == {"scrubber", "fitted"}
    finally:
        xclusiv._VOCAB_DIR = old
        xclusiv.set_vocabulary(None)


# ------------------------------------------------------------------------------------ real PDFs (local-only corpus)
SAMPLES = {
    2021: "corpus/01-brokers/xclusiv/2021/xclusiv_2021_xclusiv_weekly_2021_10_18.pdf",
    2022: "corpus/01-brokers/xclusiv/2022/xclusiv_2022_xclusiv_weekly_2022_07_01.pdf",
    2023: "corpus/01-brokers/xclusiv/2023/xclusiv_2023_xclusiv_weekly_2023_07_03.pdf",
}


def _sample(year: int) -> Path:
    for root in (REPO_ROOT, MAIN_CHECKOUT):
        p = root / SAMPLES[year]
        if p.exists():
            return p
    pytest.skip("Xclusiv corpus PDFs are local-only (gitignored)")


@pytest.mark.parametrize("year", [2021, 2022, 2023])
def test_real_report_has_the_2024_sections_dry_wet_separation_and_passes_validation(year, tmp_path):
    pdf = _sample(year)
    plan = eng.plan_file(pdf, PROFILE)
    assert plan.pages == [1, 2, 3, 4, 5] and plan.issue_date and plan.issue_date.startswith(str(year))
    row = eng.run_file(plan, PROFILE, "xclusiv", tmp_path, "pymupdf_table", None, None, {"spent": 0, "max_credits": 0})
    assert row["passed"], row["flags"]
    assert row["table_numeric_recall"] == 1.0 and row["text_recall"] >= 0.98
    md = Path(row["output"]).read_text(encoding="utf-8")
    for heading in ("## Market Overview", "### Baltic Exchange Freight Indices", "### Dry Bulk Freight", "### Tanker Freight",
                    "### Indicative Newbuilding Prices ($ mills)", "### Dry Secondhand Prices ($ mills)", "### Bulk Carrier Sales",
                    "### Tanker Secondhand Prices ($ mills)", "### Tanker Sales", "### Indicative Demolition Scrap Prices ($/LDT)"):
        assert heading in md
    dry = md.split("### Dry Bulk Freight")[1].split("### Tanker Freight")[0]
    wet = md.split("### Tanker Freight")[1].split("## Newbuilding Market")[0]
    assert not re.search(r"\b(VLCC|Suezmax|Aframax|T/CE)\b", dry) and re.search(r"\bVLCC\b", wet)
    assert not re.search(r"\b(Capesize|Panamax|Supramax|Handysize)\b", wet)
    assert "�" not in md and "Research" not in md
    sidecar = Path(row["output"]).with_suffix(".tables.json").read_text(encoding="utf-8")
    assert '"sales_count": 0' in sidecar


def test_real_2022_report_values_match_the_printed_page(tmp_path):
    pdf = _sample(2022)
    plan = eng.plan_file(pdf, PROFILE)
    row = eng.run_file(plan, PROFILE, "xclusiv", tmp_path, "pymupdf_table", None, None, {"spent": 0, "max_credits": 0})
    md = Path(row["output"]).read_text(encoding="utf-8")
    assert "| BDI | 2,214 | 2,331 | -5.0% | 2022: 2,284 / 2021: 2,943 / 2020: 1,064 |" in md
    assert "| Bulk Carriers | SDTR JULIA | 84,800 | 2022 | CHINA | SHANHAIGUAN | CHINESE | 35.18 | SOLD AT AUCTION |" in md
    assert "| Bulkers | India | $570 | $580 | -10 |" in md
    sd = md.split("### Dry S&P Activity Commentary")[1].split("### Bulk Carrier Sales")[0]
    ts = md.split("### Tanker S&P Activity Commentary")[1].split("### Tanker Sales")[0]
    assert "HNA Technology" in sd and "A Symphony" not in sd and "A Symphony" in ts


def test_real_2021_report_keeps_the_commentary_tables_and_merged_buyers(tmp_path):
    pdf = _sample(2021)
    plan = eng.plan_file(pdf, PROFILE)
    row = eng.run_file(plan, PROFILE, "xclusiv", tmp_path, "pymupdf_table", None, None, {"spent": 0, "max_credits": 0})
    md = Path(row["output"]).read_text(encoding="utf-8")
    assert "| Period | MR2 5y Avg ($m) | MR2 10y Avg ($m) | MR2 15y Avg ($m) |" in md
    assert "| Tankers | NAVIG8 PROVIDENCE | 110,928 | 2018 | CHINA | NEW TIMES | JP MORGAN | rgn 48 |" in md
    assert "| Tankers | AMERICAS SPIRIT | 111,920 | 2003 | S. KOREA | HHI | WINSON | 11.7 |" in md
