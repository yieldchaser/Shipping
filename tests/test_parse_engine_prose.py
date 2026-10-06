"""Tests for the prose engine, dropped regions, broken-sentence metric and table-layout variants."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pymupdf

from scripts.parse_engine import engine as eng
from scripts.parse_engine import geom_table as gt
from scripts.parse_engine import prose
from scripts.parse_engine import validate as val
from scripts.parse_engine.config import load_profile

CLARKSONS = load_profile("clarksons")
LONG_TEXT = ("Recycling commentary continues here with enough running text to be a real content page "
             "of the weekly bulletin. ") * 2


def _pdf(tmp_path: Path, pages: list[str], name: str = "doc.pdf") -> Path:
    doc = pymupdf.open()
    for text in pages:
        lines = [w for ln in text.split("\n") for w in (textwrap.wrap(ln, 70) or [""])]
        doc.new_page().insert_text((50, 80), "\n".join(lines), fontsize=11)
    path = tmp_path / name
    doc.save(path)
    return path


def test_blank_trailing_page_and_contacts_page_are_dropped(tmp_path):
    pdf = _pdf(tmp_path, [LONG_TEXT, LONG_TEXT, "Contacts Disclaimer Kifissias Avenue snp@clarksons.gr", "4"])
    plan = eng.plan_file(pdf, CLARKSONS)
    assert plan.pages == [1, 2]
    assert "trailing_boilerplate_dropped_p3" in plan.notes


def test_two_page_pdf_keeps_content_page2(tmp_path):
    plan = eng.plan_file(_pdf(tmp_path, [LONG_TEXT, LONG_TEXT]), CLARKSONS)
    assert plan.pages == [1, 2]
    assert any(n.startswith("two_page_content_kept") for n in plan.notes)


# ------------------------------------------------------------------------------------ prose engine
def _prose_pdf(tmp_path: Path) -> Path:
    doc = pymupdf.open()
    for n in range(2):
        pg = doc.new_page()
        pg.insert_text((40, 25), "Weekly Bulletin | 09 Feb 2024", fontsize=8)      # repeated running header
        pg.insert_text((540, 820), str(n + 1), fontsize=8)                           # page number
        pg.insert_text((40, 80), "New Building", fontsize=14, fontname="hebo")
        tw = pymupdf.TextWriter(pg.rect)
        pos = (40, 105)
        _, pos = tw.append(pos, "In tankers this week the VLCC ", font=pymupdf.Font("helv"), fontsize=10)
        _, pos = tw.append(pos, "SEAKING", font=pymupdf.Font("hebo"), fontsize=10)
        tw.append((40, 117), "was sold to clients of ADNOC at USD", font=pymupdf.Font("helv"), fontsize=10)
        tw.write_text(pg)
        pg.insert_text((40, 129), "175m, a scrub-", fontsize=10)
        pg.insert_text((40, 141), "ber-equipped unit. Sub-", fontsize=10)
        pg.insert_text((40, 153), "Continent demand 7S50MC-", fontsize=10)
        pg.insert_text((40, 165), "C7.1 is firm.", fontsize=10)
        pg.insert_text((40, 200), "Desolate!", fontsize=10, fontname="hebo")
        pg.insert_text((40, 220), "A separate paragraph follows here.", fontsize=10)
    path = tmp_path / "prose.pdf"
    doc.save(path)
    return path


def _render_prose(pdf: Path, pages=(1,), exclude=None) -> str:
    doc = pymupdf.open(pdf)
    body = prose.body_font_size(doc, list(pages))
    repeated = prose.repeated_band_texts(doc)
    paras = []
    for p in pages:
        paras += prose.page_prose(doc[p - 1], p, exclude or [], repeated, body)
    prose.assign_heading_levels(paras, body)
    return prose.render(prose.order_items(paras, []))


def test_prose_inline_bold_stays_inline_and_hyphens_are_repaired(tmp_path):
    md = _render_prose(_prose_pdf(tmp_path))
    blocks = md.split("\n\n")
    assert blocks[0] == "# New Building"
    assert blocks[1] == ("In tankers this week the VLCC **SEAKING** was sold to clients of ADNOC at USD 175m, "
                         "a scrubber-equipped unit. Sub-Continent demand 7S50MC-C7.1 is firm.")
    assert blocks[2] == "## Desolate!"
    assert blocks[3] == "A separate paragraph follows here."


def test_prose_drops_repeated_running_header_and_page_numbers(tmp_path):
    md = _render_prose(_prose_pdf(tmp_path), pages=(1, 2))
    assert "Weekly Bulletin" not in md
    assert not any(line.strip() in ("1", "2") for line in md.split("\n"))


def test_prose_excludes_boxes(tmp_path):
    md = _render_prose(_prose_pdf(tmp_path), exclude=[(0, 190, 600, 842)])
    assert "Desolate" not in md and "separate paragraph" not in md and "scrubber-equipped" in md


def test_prose_reads_two_columns_column_by_column_and_joins_flow(tmp_path):
    doc = pymupdf.open()
    pg = doc.new_page()
    left = [(100, "Left first paragraph is complete."), (112, "It has two lines in total."),
            (200, "The market was calm as owners"), (212, "waited for news and charterers"), (224, "held back until")]
    right = [(100, "the end of the week. Rates then"), (112, "improved sharply for all sizes."),
             (200, "Right second paragraph here."), (212, "It also has two lines.")]
    for y, text in left:
        pg.insert_text((40, y), text, fontsize=10)
    for y, text in right:
        pg.insert_text((320, y), text, fontsize=10)
    path = tmp_path / "cols.pdf"
    doc.save(path)
    blocks = _render_prose(path).split("\n\n")
    assert blocks[0] == "Left first paragraph is complete. It has two lines in total."
    assert blocks[1] == ("The market was calm as owners waited for news and charterers held back until the end of "
                         "the week. Rates then improved sharply for all sizes.")
    assert blocks[2] == "Right second paragraph here. It also has two lines."


# ------------------------------------------------------------------------------------ validator
def test_broken_sentences_metric():
    assert val.broken_sentences("The vessel was sold for\n\nusd 19m to buyers.") == 1
    assert val.broken_sentences("The vessel was sold.\n\nusd is a currency.") == 0
    assert val.broken_sentences("Sold for\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\nlower case table follow") == 0
    assert val.broken_sentences("# Heading\n\nlower case para") == 0
    assert val.broken_sentences("Says (see note)\n\nand more") == 0
    assert val.broken_sentences("**bold ending without stop**\n\nnext") == 1


def test_drop_region_box_from_first_anchor(tmp_path):
    doc = pymupdf.open()
    pg = doc.new_page()
    pg.insert_text((40, 80), "Commentary stays.", fontsize=10)
    pg.insert_text((100, 500), "Exchange Rate", fontsize=10)
    pg.insert_text((40, 500), "Baltic Index", fontsize=10)
    pg.insert_text((40, 600), "BDI 1249", fontsize=10)
    page = doc[0]
    boxes = prose.drop_region_boxes(page, CLARKSONS["drop_regions"])
    assert len(boxes) == 1 and 480 < boxes[0][1] < 500 and boxes[0][3] == page.rect.height
    assert prose.drop_region_boxes(page, [{"anchor_any": ["Nonexistent"], "until": "page_end"}]) == []
    assert prose.drop_region_boxes(page, None) == []


def test_validator_recall_ignores_dropped_regions(tmp_path):
    pdf = _pdf(tmp_path, ["Tanker earnings strengthened considerably"])
    assert val.text_recall(pdf, [1], "", [], [], [{"page": 1, "bbox": (0, 0, 600, 842)}])["text_recall"] is None


def test_sections_accept_alternative_spellings():
    assert val.sections_present("## Bulker Sales\n\nx", ["Bulk Carriers|Bulker Sales"]) == \
        {"Bulk Carriers|Bulker Sales": True}


# ------------------------------------------------------------------------------------ table variants
def test_header_alternatives_and_headerless_continuation(tmp_path):
    doc = pymupdf.open()
    p1 = doc.new_page()
    p1.insert_text((40, 60), "BULK CARRIERS", fontsize=11)
    xs = [40, 140, 200, 330, 420, 500]
    for x, h in zip(xs, ["VESSEL", "DWT", "BLT", "PRICE", "BUYER"]):
        p1.insert_text((x + 4, 95), h, fontsize=9)
    for x, t in zip(xs, ["ALPHA", "50,000", "2011 BOHAI", "USD 10 M", "GREEK"]):
        p1.insert_text((x + 4, 120), t, fontsize=9)
    p2 = doc.new_page()
    p2.insert_text((40, 60), "TANKER SALES", fontsize=11)          # continued table without a header row
    for x, t in zip(xs, ["BETA", "30,000", "2012 IMABARI", "USD 5 M", "TURKISH"]):
        p2.insert_text((x + 4, 100), t, fontsize=9)
    headers = ["Vessel", "DWT", "Built|BLT", "Price", "Buyer"]
    cfg = [{"name": "Bulk", "anchor": "(?i)^BULK CARRIERS", "headers": headers, "key_column": 1,
            "row_start_pattern": "\\d", "headerless_ok": True},
           {"name": "Tanker", "anchor": "(?i)^TANKER SALES", "headers": headers, "key_column": 1,
            "row_start_pattern": "\\d", "headerless_ok": True}]
    memory: dict = {}
    t1 = gt.find_tables(doc[0], 1, cfg, None, 45, memory)
    t2 = gt.find_tables(doc[1], 2, cfg, None, 45, memory)
    assert t1[0].columns == ["Vessel", "DWT", "Built", "Price", "Buyer"]
    assert t1[0].rows == [["ALPHA", "50,000", "2011 BOHAI", "USD 10 M", "GREEK"]]
    assert t2[0].rows == [["BETA", "30,000", "2012 IMABARI", "USD 5 M", "TURKISH"]]
    assert gt.find_tables(doc[1], 2, cfg, None, 45, None) == []     # no memory: a headerless table is not guessed


def test_year_yard_split_handles_quarter_ranges():
    pat = CLARKSONS["geom"]["tables"][0]["split_columns"][0]["pattern"]
    rows, cols, _ = gt._apply_splits(
        [{"column": "Built", "into": ["Year", "Yard"], "pattern": pat}], ["Built"],
        [["2Q-3Q 2026 + 1Q-2Q 2027 JINGJIANG NANYANG, CHINA"], ["2012 STX (JINHAE)"]], [])
    assert cols == ["Year", "Yard"]
    assert rows == [["2Q-3Q 2026 + 1Q-2Q 2027", "JINGJIANG NANYANG, CHINA"], ["2012", "STX (JINHAE)"]]


def test_line_start_anchor_ignores_prose_mentions(tmp_path):
    doc = pymupdf.open()
    pg = doc.new_page()
    pg.insert_text((40, 80), "The exchange rate and bunker prices moved this week.", fontsize=10)
    pg.insert_text((40, 500), "Baltic Index", fontsize=10)
    rule = {"anchor_any": ["Baltic Index", "Exchange Rate", "Bunker Prices"], "line_start": True,
            "max_line_chars": 40, "until": "page_end"}
    boxes = prose.drop_region_boxes(pg, [rule])
    assert len(boxes) == 1 and boxes[0][1] > 480                  # starts at the heading, not the prose mention
    assert prose.drop_region_boxes(pg, [dict(rule, line_start=False)])[0][1] < 100   # substring match would eat prose


def test_block_end_region_stops_at_the_gap_after_the_block(tmp_path):
    doc = pymupdf.open()
    pg = doc.new_page()
    pg.insert_text((40, 100), "Disclaimer", fontsize=8)
    for i in range(5):
        pg.insert_text((40, 112 + 8 * i), "The material and the information line %d" % i if i == 0 else "continued line %d" % i, fontsize=6)
    pg.insert_text((40, 200), "Recycling", fontsize=12)
    box = prose.drop_region_boxes(pg, [{"anchor_any": ["Disclaimer"], "line_start": True, "until": "block_end"}])[0]
    assert box[1] < 100 < box[3] < 160                              # stops before "Recycling" at y=200


def test_text_spanning_columns_stays_in_the_vessel_cell(tmp_path):
    doc = pymupdf.open()
    pg = doc.new_page()
    pg.insert_text((40, 60), "Tankers", fontsize=11)
    xs = [40, 100, 160, 230, 330, 400, 470]
    headers = ["Vessel", "DWT", "Built", "Details", "Price", "Buyer"]
    for x, h in zip(xs, headers):
        pg.insert_text((x + 4, 95), h, fontsize=9)
    pg.insert_text((xs[0] + 4, 125), "A huge transaction concerning modern eco VLCCs has been reported", fontsize=9)
    pg.insert_text((xs[4] + 4, 125), "USD 2.35 B", fontsize=9)
    pg.insert_text((xs[5] + 4, 125), "NORWEGIAN", fontsize=9)
    for y in (80, 105, 140):                                       # ruled rows, as in the real bulletin
        pg.draw_line((40, y), (470, y), color=(0.5, 0.5, 0.5), width=0.6)
    for x in xs:
        pg.draw_line((x, 80), (x, 140), color=(0.5, 0.5, 0.5), width=0.6)
    cfg = [{"name": "T", "anchor": "^Tankers", "headers": headers, "key_column": 1, "row_start_pattern": "\d"}]
    t = gt.find_tables(doc[0], 1, cfg)[0]
    assert t.rows == [["A huge transaction concerning modern eco VLCCs has been reported", "", "", "", "USD 2.35 B", "NORWEGIAN"]]
