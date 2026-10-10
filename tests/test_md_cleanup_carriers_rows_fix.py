"""Tests for scripts/md_cleanup/carriers_rows_fix.py (row-level Carriers table repair).

The fixture MD (tests/fixtures/carriers_rows/synthetic_report.md) is paired with a synthetic PDF
drawn below with pymupdf (ruled tables, filled header cells, wrapped and merged cells), so the tests
exercise the real geometry code without live MDs or PDFs.
"""
import hashlib
import json
from pathlib import Path

import pytest

pymupdf = pytest.importorskip("pymupdf")

from scripts.md_cleanup import carriers_rows_fix as fx  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "carriers_rows" / "synthetic_report.md"
LF = chr(10)
CRLF = chr(13) + chr(10)
FONT = 7
PITCH = 9

SALES_COLS = [(20, 110), (110, 150), (150, 195), (195, 235), (235, 345), (345, 410), (410, 490), (490, 570)]
SALES_HDR = ["NAME", "TYPE", "DWT", "BUILT", "YARD", "PRICE", "BUYERS", "COMMENTS"]
DEMO_COLS = [(20, 100), (100, 140), (140, 185), (185, 225), (225, 265), (265, 355), (355, 415), (415, 480), (480, 570)]
DEMO_HDR = ["NAME", "TYPE", "DWT", "LDT", "BUILT", "YARD", "PRICE/LDT", "BUYERS", "COMMENTS"]
NB_COLS = [(20, 90), (90, 130), (130, 210), (210, 290), (290, 350), (350, 410), (410, 500), (500, 570)]
NB_HDR = ["TYPE", "NO", "SIZE", "YARD", "DEL", "MIL$", "OWNERS", "COMMENTS"]


# ---------------------------------------------------------------- synthetic PDF
def put(page, xc, yc, text):
    w = pymupdf.get_text_length(text, "helv", FONT)
    page.insert_text((xc - w / 2, yc + 2.3), text, fontsize=FONT, fontname="helv")


def block(page, col, cols, y0, y1, lines):
    mid, n = (y0 + y1) / 2, len(lines)
    xc = (cols[col][0] + cols[col][1]) / 2
    for i, ln in enumerate(lines):
        put(page, xc, mid + (i - (n - 1) / 2) * PITCH, ln)


def rule(page, y, segments):
    for x0, x1 in segments:
        page.draw_rect(pymupdf.Rect(x0, y, x1, y + 0.5), color=None, fill=(0, 0, 0))


def header(page, cols, names, top):
    for (x0, x1), name in zip(cols, names):
        page.draw_rect(pymupdf.Rect(x0, top, x1 - 0.5, top + 14), color=None, fill=(0.5, 0.5, 0.5))
        put(page, (x0 + x1) / 2, top + 7, name)
    return top + 14


def table(page, cols, names, top, rows, seps):
    """rows: [(y0, y1, {col: [lines]})]; seps: [(y, skipped_cols)] horizontal rules (a skipped column's
    cell is merged over the rule)."""
    header(page, cols, names, top)
    for y0, y1, cells in rows:
        for c, lines in cells.items():
            block(page, c, cols, y0, y1, lines)
    for y, skip in seps:
        segs, start = [], None
        for c, (x0, x1) in enumerate(cols):
            if c in skip:
                if start is not None:
                    segs.append((start, cols[c - 1][1]))
                    start = None
            elif start is None:
                start = x0
        if start is not None:
            segs.append((start, cols[-1][1]))
        rule(page, y, segs)


def sales_row(y0, y1, name, typ, dwt, built, yard, price, buyers, comments=None):
    cells = {0: name, 1: [typ], 2: [dwt], 3: [built], 4: yard, 5: [price], 6: [buyers]}
    if comments:
        cells[7] = comments
    return (y0, y1, {c: v for c, v in cells.items() if v and v != [""]})


def page_one(page, variant=None):
    """Bulk sales (merged price/buyers over three rows), Tankers, an empty Container table, Demolition."""
    rows = [sales_row(114, 126, ["AGIS"], "BC", "181,500", "2023", ["Namura, Japan"], "68.00", "UNDISCLOSED"),
            sales_row(126, 150, ["AP LOVRIJENAC", "(Hull Ht82-278)"], "BC", "82,000", "1/2004",
                      ["ex Jiangsu New Hantong"], "37.00", "NNC"),
            sales_row(150, 162, ["THISSEAS"], "BC", "75,200", "2012", ["Penglai Zhongbai"], "", ""),
            sales_row(162, 174, ["ICARUS"], "BC", "75,200", "2012", ["Penglai Zhongbai"], "", ""),
            sales_row(174, 186, ["ATLAS"], "BC", "75,124", "2012", ["Penglai Zhongbai"], "", ""),
            sales_row(186, 198, ["STAR GOAL"], "BC", "55,989", "2010", ["IHI Marine United"], "15.50", "VIETNAMESE")]
    price_lines = ["52.50 EN BLOC"] if variant == "printed_en_bloc" else ["52.50"]
    rows[2][2][5] = price_lines
    rows[2][2][6] = ["BRIGHT", "NAVIGATION"]
    table(page, SALES_COLS, SALES_HDR, 100, rows,
          [(126, ()), (150, ()), (162, (5, 6)), (174, (5, 6)), (186, ()), (198, ())])
    table(page, SALES_COLS, SALES_HDR, 230,
          [sales_row(244, 256, ["CONCORD EXPRESS"], "TANKER", "111,920", "2003", ["Hyundai Heavy Inds"], "26.00", "UAE")],
          [(256, ())])
    header(page, SALES_COLS, SALES_HDR, 280)
    put(page, 290, 300, "NONE REPORTED")
    rule(page, 306, [(20, 570)])
    demo = [(354, 402, {0: ["WU YANG GODDESS"], 1: ["BC"], 2: ["45,700"], 3: ["7,481"], 4: ["1995"],
                        5: ["Hashihama", "Shipbuilding"], 6: ["480"], 7: ["UNDISCLOSED"],
                        8: ["AS IS CHINA", "(500 tons", "bunkers", "included)"]}),
            (402, 450, {0: ["BONTRUP MALDIVES"], 1: ["CV"], 2: ["9,303"], 3: ["10,820"], 4: ["1984"],
                        5: ["Hyundai Heavy", "Industries"], 6: ["547"], 7: ["INDIA"],
                        8: ["HKC green", "recycling", "(350 tons", "bunkers", "included)"]})]
    table(page, DEMO_COLS, DEMO_HDR, 340, demo, [(402, ()), (450, ())])


def page_two(page):
    nb = [(114, 126, {0: ["TANKER"], 1: ["2"], 2: ["158,000 DWT"], 3: ["HYUNDAI HI"], 4: ["6/2026"],
                      5: ["85.25 EACH"], 6: ["Arcadia"]})]
    table(page, NB_COLS, NB_HDR, 100, nb, [(126, ())])


def page_labels(page, third_label="TESS 58K"):
    """Column-oriented weighted-average table: size labels on top, This WK / Week Ch. / Prev. WK rows below."""
    put(page, 190, 100, "Dry BC Baltic Time Charter Weighted Average routes")
    cols = [(120, "CAPE 180K", ["24759", "1402", "23357"]), (190, "TESS 82K", ["15919", "789", "15130"]),
            (343, third_label, ["12396", "316", "12080"]), (470, "HANDY 38K", ["12858", "-147", "13005"])]
    for xc, label, vals in cols:
        put(page, xc, 131, label)
        for y, v in zip((151, 163, 175), vals):
            put(page, xc, y, v)
    for y, t in ((151, "This WK"), (163, "Week Ch,"), (175, "Prev, WK")):
        put(page, 60, y, t)
    put(page, 190, 200, "Dry BC Time Charter Period indicative ideas (on Average)")


def make_doc(variant=None, labels=False):
    doc = pymupdf.open()
    page_one(doc.new_page(width=595, height=842), variant)
    page_two(doc.new_page(width=595, height=842))
    if labels:
        page_labels(doc.new_page(width=595, height=842), "TESS 58K" if labels is True else labels)
    return doc


LABEL_MD = LF.join([
    "", "## Dry BC Baltic Time Charter Weighted Average routes", "",
    "| Route / Class | This WK ($/day) | Week Ch. ($/day) | Prev. WK ($/day) |", "| --- | --- | --- | --- |",
    "| CAPE 180K | 24759 | 1402 | 23357 |", "| TESS 82K | 15919 | 789 | 15130 |",
    "| LME 74K |  |  |  |", "| SUPRA 63K | 12396.0 | 316.0 | 12080.0 |", "| HANDY 38K | 12858 | -147 | 13005 |", "",
    "## Dry BC Time Charter Period indicative ideas (on Average)", "",
    "| Vessel Class | Tenor | Rate ($/day) | Rate Raw |", "| --- | --- | --- | --- |",
    "| SUPRA TESS 58k | SHORT |  | ATL 15,000 PAC 15,250 |", ""])


@pytest.fixture
def source():
    return FIXTURE.read_text(encoding="utf-8")


def _fix(text, doc=None):
    return fx.fix_document(text, fx.Pdf(doc or make_doc()))


def _by_class(changes, cls):
    return [c for c in changes if c["class"] == cls]


def _lines(text, startswith):
    return [ln for ln in text.split(LF) if ln.startswith(startswith)]


# ---------------------------------------------------------------- helpers
def test_norm_cell_strips_thousands_only_for_dwt_and_ldt():
    assert fx.norm_cell("181,500", "dwt") == "181500" and fx.norm_cell("7,481", "ldt") == "7481"
    assert fx.norm_cell("1,284 TEU", "comments") == "1,284 TEU" and fx.norm_cell("11,80", "price") == "11,80"
    assert fx.norm_cell("158,000 DWT", "size") == "158,000 DWT"


def test_strict_part_is_prefix_or_word_substring_never_equal_or_unrelated():
    assert fx.strict_part("AP LOVRIJENAC", "AP LOVRIJENAC (Hull Ht82-278)")
    assert fx.strict_part("NAVIGATION", "BRIGHT NAVIGATION")
    assert not fx.strict_part("NAV", "BRIGHT NAVIGATION")
    assert not fx.strict_part("BRIGHT", "BRIGHT") and not fx.strict_part("99.00", "68.00")


def test_header_geometry_reads_columns_from_header_fills():
    pdf = fx.Pdf(make_doc())
    regs = fx.locate_tables(pdf)
    assert [len(regs[k]) for k in ("sales", "demolition", "newbuilding")] == [3, 1, 1]
    assert [round(a) for a, _ in regs["sales"][0]["cols"]] == [a for a, _ in SALES_COLS]
    assert regs["newbuilding"][0]["page"] == 1


# ---------------------------------------------------------------- class: wrapped text lost
def test_wrapped_name_is_extended_and_blank_built_is_filled(source):
    new, changes, unresolved = _fix(source)
    assert unresolved == []
    assert _lines(new, "| AP LOVRIJENAC")[0] == \
        "| AP LOVRIJENAC (Hull Ht82-278) | BC | 82000 | 1/2004 | ex Jiangsu New Hantong | 37.00 | NNC |  |"
    ext = [c for c in _by_class(changes, "cell_extended") if c["column"] == "Name"]
    assert ext[0]["old"] == "AP LOVRIJENAC" and ext[0]["new"] == "AP LOVRIJENAC (Hull Ht82-278)"
    filled = [c for c in _by_class(changes, "cell_filled") if c["column"] == "Built"]
    assert filled[0]["old"] == "" and filled[0]["new"] == "1/2004"
    for c in (ext[0], filled[0]):
        assert c["pdf_evidence"]["page"] == 1 and len(c["pdf_evidence"]["bbox"]) == 4
        assert 126 <= c["pdf_evidence"]["bbox"][1] < c["pdf_evidence"]["bbox"][3] <= 151


def test_dwt_keeps_the_md_convention_without_thousands_separators(source):
    new, changes, _ = _fix(source)
    assert "| AGIS | BC | 181500 | 2023 |" in _lines(new, "| AGIS")[0]
    assert not [c for c in changes if c.get("column") == "DWT"]


# ---------------------------------------------------------------- class: demolition realign
def test_demolition_shift_is_realigned_from_the_pdf(source):
    new, changes, unresolved = _fix(source)
    assert _lines(new, "| WU YANG")[0] == (
        "| WU YANG GODDESS | BC | 45700 | 7481 | 1995 | Hashihama Shipbuilding | 480 | UNDISCLOSED "
        "| AS IS CHINA (500 tons bunkers included) |")
    assert _lines(new, "| BONTRUP")[0] == (
        "| BONTRUP MALDIVES | CV | 9303 | 10820 | 1984 | Hyundai Heavy Industries | 547 | INDIA "
        "| HKC green recycling (350 tons bunkers included) |")
    realign = _by_class(changes, "demolition_realign")
    assert len(realign) == 1 and realign[0]["old"][5] == "Hashihama Shipbuilding Hyundai Heavy"
    assert realign[0]["new"][8] == "AS IS CHINA (500 tons bunkers included)"
    assert realign[0]["pdf_evidence"]["page"] == 1
    assert {c["class"] for c in changes if c["table"] == "Demolition Market"} == {"demolition_realign", "cell_extended"}
    assert unresolved == []


def test_demolition_shift_that_loses_or_invents_words_is_refused(source):
    md = source.replace("(500 tons bunkers included) HKC green recycling", "(500 tons bunkers included) NOT IN PDF")
    new, changes, unresolved = _fix(md)
    reason = [u for u in unresolved if u["class"] == "demolition"][0]["reason"]
    assert "words absent from the PDF" in reason and "pdf" in reason
    assert _lines(new, "| WU YANG") == _lines(md, "| WU YANG") and not [c for c in changes if c["table"] == "Demolition Market"]


def test_shifted_demolition_row_with_glued_type_and_comma_dwt_maps_by_name_and_numbers(source):
    md = source.replace(
        "| WU YANG GODDESS | BC | 45700 | 7481 | 1995 | Hashihama Shipbuilding Hyundai Heavy | 480 | UNDISCLOSED "
        "| (500 tons bunkers included) HKC green recycling |",
        "| WU YANG BC | 45,700 | 7481 |  | 1995 | Hashihama 480 |  |  |  |")
    new, changes, unresolved = _fix(md)
    assert [u for u in unresolved if u["class"] == "demolition"] == []
    assert _lines(new, "| WU YANG GODDESS")[0].startswith("| WU YANG GODDESS | BC | 45700 | 7481 | 1995 | Hashihama Shipbuilding | 480 |")


# ---------------------------------------------------------------- class: row added
def test_missing_pdf_row_is_added_at_its_pdf_position(source):
    new, changes, _ = _fix(source)
    out = new.split(LF)
    i = next(n for n, ln in enumerate(out) if ln.startswith("| ATLAS"))
    assert out[i + 1] == "| STAR GOAL | BC | 55989 | 2010 | IHI Marine United | 15.50 | VIETNAMESE |  |"
    assert out[i + 2].startswith("| CONCORD EXPRESS")
    added = _by_class(changes, "row_added")
    assert len(added) == 1 and added[0]["new"][0] == "STAR GOAL" and added[0]["old"] is None
    assert added[0]["pdf_evidence"]["page"] == 1 and 186 <= added[0]["pdf_evidence"]["bbox"][1] <= 187


def test_none_reported_row_is_never_written(source):
    new, changes, _ = _fix(source)
    assert "NONE REPORTED" not in new.upper()
    assert [c["new"][0] for c in _by_class(changes, "row_added")] == ["STAR GOAL"]


# ---------------------------------------------------------------- class: en bloc
def test_price_merged_over_rows_gets_en_bloc_on_every_spanned_row(source):
    new, changes, _ = _fix(source)
    for name in ("THISSEAS", "ICARUS", "ATLAS"):
        assert "| Penglai Zhongbai | 52.50 (en bloc) | BRIGHT NAVIGATION |  |" in _lines(new, "| " + name)[0]
    eb = _by_class(changes, "en_bloc")
    assert sorted((c["old"], c["new"]) for c in eb) == [("", "52.50 (en bloc)"), ("52.50", "52.50 (en bloc)"),
                                                        ("52.50", "52.50 (en bloc)")]
    assert all(c["pdf_evidence"]["page"] == 1 for c in eb)
    buyers = [c for c in changes if c.get("column") == "Buyers"]
    assert sorted(c["class"] for c in buyers) == ["cell_extended", "cell_extended", "cell_filled"]


def test_printed_en_bloc_text_is_not_suffixed_again(source):
    new, changes, _ = _fix(source, make_doc("printed_en_bloc"))
    assert "52.50 EN BLOC (en bloc)" not in new
    assert "| Penglai Zhongbai | 52.50 EN BLOC | BRIGHT NAVIGATION |  |" in _lines(new, "| ICARUS")[0]
    assert not _by_class(changes, "en_bloc") or all("(en bloc)" not in c["new"] for c in _by_class(changes, "en_bloc"))


def test_each_price_spanning_rows_is_not_en_bloc():
    assert not fx.price_en_bloc("85.25 EACH") and not fx.price_en_bloc("84.00 EN BLOC")
    assert fx.price_en_bloc("52.50") and fx.price_en_bloc("Low 11.00") and fx.price_en_bloc("82-83")
    assert not fx.price_en_bloc("1.05 BILLION OF WHICH 585 MILLION IN CASH")


def test_en_bloc_label_printed_on_the_following_row_marks_both_rows():
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    rows = [sales_row(114, 126, ["CAPE HERON"], "BC", "177,656", "2005", ["Mitsui"], "30.00", "CHINESE"),
            sales_row(126, 138, ["CAPE HAWK"], "BC", "176,996", "2006", ["Namura"], "EN BLOC", "CHINESE")]
    table(page, SALES_COLS, SALES_HDR, 100, rows, [(126, ()), (138, ())])
    md = LF.join(["## Second-hand Market Reported Sold", "",
                  "| Name | Type | DWT | Built | Yard | Price ($M) | Buyers | Comments |", "| --- | --- | --- | --- | --- | --- | --- | --- |",
                  "| CAPE HERON | BC | 177656 | 2005 | Mitsui | 30.00 | CHINESE |  |",
                  "| CAPE HAWK | BC | 176996 | 2006 | Namura |  | CHINESE |  |", ""])
    new, changes, unresolved = fx.fix_document(md, fx.Pdf(doc))
    assert unresolved == []
    assert "| CAPE HERON | BC | 177656 | 2005 | Mitsui | 30.00 EN BLOC | CHINESE |  |" in new
    assert "| CAPE HAWK | BC | 176996 | 2006 | Namura | 30.00 EN BLOC | CHINESE |  |" in new
    assert [c["class"] for c in changes] == ["en_bloc", "en_bloc"]


# ---------------------------------------------------------------- refusals
def test_conflicting_value_refuses_that_table_only(source):
    md = source.replace("| AGIS | BC | 181500 | 2023 | Namura, Japan | 68.00 |", "| AGIS | BC | 181500 | 2023 | Namura, Japan | 99.00 |")
    new, changes, unresolved = _fix(md)
    sales = [u for u in unresolved if u["class"] == "sales"]
    assert len(sales) == 1 and "words absent from the PDF: 9900" in sales[0]["reason"]
    assert [ln for ln in new.split(LF) if ln.startswith("| AGIS") or ln.startswith("| AP LOV")] == \
        [ln for ln in md.split(LF) if ln.startswith("| AGIS") or ln.startswith("| AP LOV")]
    assert not [c for c in changes if c["table"] == "Second-hand Market Reported Sold"]
    assert _by_class(changes, "demolition_realign")        # the other tables are still repaired


def test_sales_shift_is_realigned_when_every_old_word_is_on_the_pdf(source):
    md = source.replace("| AGIS | BC | 181500 | 2023 | Namura, Japan | 68.00 | UNDISCLOSED |  |",
                        "| AGIS | BC | 181500 | 2023 | Namura, Japan | 68.00 UNDISCLOSED |  |  |")
    new, changes, unresolved = _fix(md)
    assert unresolved == []
    assert "| AGIS | BC | 181500 | 2023 | Namura, Japan | 68.00 | UNDISCLOSED |  |" in new.split(LF)
    sh = _by_class(changes, "shift_realign")
    assert len(sh) == 1 and sh[0]["old"][5] == "68.00 UNDISCLOSED" and sh[0]["new"][6] == "UNDISCLOSED"
    assert sh[0]["pdf_evidence"]["page"] == 1 and len(sh[0]["pdf_evidence"]["bbox"]) == 4
    assert not _by_class(changes, "demolition_realign") or all(c["table"] == "Demolition Market" for c in _by_class(changes, "demolition_realign"))


def test_sales_shift_that_loses_or_invents_words_is_refused(source):
    md = source.replace("| AGIS | BC | 181500 | 2023 | Namura, Japan | 68.00 | UNDISCLOSED |  |",
                        "| AGIS | BC | 181500 | 2023 | Namura, Japan | 68.00 PHANTOM |  |  |")
    new, changes, unresolved = _fix(md)
    reason = [u for u in unresolved if u["class"] == "sales"][0]["reason"]
    assert "words absent from the PDF: phantom" in reason
    assert "PHANTOM" in new and not [c for c in changes if c["table"] == "Second-hand Market Reported Sold"]


def test_newbuilding_shift_is_a_shift_realign(source):
    md = source.replace("| HYUNDAI HI | 6/2026 |", "| HYUNDAI HI 6/2026 |  |")
    new, changes, unresolved = _fix(md)
    assert unresolved == []
    assert "| TANKER | 2 | 158,000 DWT | HYUNDAI HI | 6/2026 | 85.25 EACH | Arcadia |  |" in new.split(LF)
    assert [c["table"] for c in _by_class(changes, "shift_realign")] == ["Newbuilding Market"]


def test_old_row_not_on_the_pdf_refuses_the_table(source):
    md = source.replace("| CONCORD EXPRESS |", "| GHOST SHIP |")
    new, _, unresolved = _fix(md)
    assert "does not map to a PDF row" in [u for u in unresolved if u["class"] == "sales"][0]["reason"]
    assert "GHOST SHIP" in new and "STAR GOAL" not in new


def test_md_block_without_a_table_but_pdf_rows_is_reported_not_created(source):
    nb = LF.join(["| Type | Units | Size | Yard | Delivery | Price ($M) | Owners | Comments |", "| --- | --- | --- | --- | --- | --- | --- | --- |",
                  "| TANKER | 2 | 158,000 DWT | HYUNDAI HI | 6/2026 | 85.25 EACH | Arcadia |  |"])
    assert nb in source
    md = source.replace(nb, "*None Reported*")
    new, _, unresolved = _fix(md)
    assert "MD block has no table but the PDF prints 1 row" in [u for u in unresolved if u["class"] == "newbuilding"][0]["reason"]
    assert "*None Reported*" in new


def test_unsupported_layouts_are_reported():
    md = LF.join(["## Second-hand Market (page 1)", "", "| a |", "| --- |", "| b |", ""])
    new, changes, unresolved = fx.fix_document(md, fx.Pdf(make_doc()))
    assert new == md and changes == [] and unresolved[0]["class"] == "layout"
    other = pymupdf.open()
    other.new_page(width=595, height=842)
    md2 = LF.join(["## Second-hand Market Reported Sold", "", "| Name | Type |", "| --- | --- |", "| X | BC |", ""])
    _, _, un2 = fx.fix_document(md2, fx.Pdf(other))
    assert "table header not found in the PDF" in un2[0]["reason"]


# ---------------------------------------------------------------- label_fix
def test_label_fix_changes_only_the_label_cell_when_the_numbers_match_the_pdf_column(source):
    md = source + LABEL_MD
    new, changes, unresolved = _fix(md, make_doc(labels=True))
    lf = _by_class(changes, "label_fix")
    assert len(lf) == 1 and lf[0]["old"] == "SUPRA 63K" and lf[0]["new"] == "TESS 58K"
    assert lf[0]["pdf_evidence"]["page"] == 3 and len(lf[0]["pdf_evidence"]["bbox"]) == 4
    assert lf[0]["pdf_evidence"]["values"] == [12396.0, 316.0, 12080.0]
    assert "| TESS 58K | 12396.0 | 316.0 | 12080.0 |" in new.split(LF)
    assert "| SUPRA 63K |" not in new
    # the one exception to "other lines byte-identical": everything outside the three blocks except that row
    old_lines, new_lines = md.split(LF), new.split(LF)
    tail = old_lines.index("## BSPA Secondhand Market Assessments (5 Years Old)")
    old_tail, new_tail = old_lines[tail:], new_lines[len(new_lines) - (len(old_lines) - tail):]
    diff = [(a, b) for a, b in zip(old_tail, new_tail) if a != b]
    assert diff == [("| SUPRA 63K | 12396.0 | 316.0 | 12080.0 |", "| TESS 58K | 12396.0 | 316.0 | 12080.0 |")]
    assert new_lines[:tail - 0 and old_lines.index("## Second-hand Market Reported Sold")] == old_lines[:old_lines.index("## Second-hand Market Reported Sold")]


def test_label_fix_leaves_placeholder_rows_and_other_tables_and_reports(source):
    new, changes, unresolved = _fix(source + LABEL_MD, make_doc(labels=True))
    assert "| LME 74K |  |  |  |" in new.split(LF)
    assert "| SUPRA TESS 58k | SHORT |  | ATL 15,000 PAC 15,250 |" in new.split(LF)
    lab = [u for u in unresolved if u["class"] == "label"]
    assert len(lab) == 1 and lab[0]["row"] == "LME 74K" and "placeholder" in lab[0]["reason"]


def test_label_fix_requires_the_numbers_to_match(source):
    md = (source + LABEL_MD).replace("| SUPRA 63K | 12396.0 | 316.0 | 12080.0 |", "| SUPRA 63K | 12396.0 | 999.0 | 12080.0 |")
    new, changes, _ = _fix(md, make_doc(labels=True))
    assert not _by_class(changes, "label_fix") and "| SUPRA 63K | 12396.0 | 999.0 | 12080.0 |" in new.split(LF)


def test_label_fix_is_a_noop_when_the_pdf_prints_the_md_label(source):
    new, changes, _ = _fix(source + LABEL_MD, make_doc(labels="SUPRA 63K"))
    assert not _by_class(changes, "label_fix") and "| SUPRA 63K | 12396.0 | 316.0 | 12080.0 |" in new.split(LF)


def test_label_fix_is_idempotent(source):
    new, _, _ = _fix(source + LABEL_MD, make_doc(labels=True))
    again, changes, _ = _fix(new, make_doc(labels=True))
    assert again == new and changes == []


# ---------------------------------------------------------------- tables without row rules
def test_table_printed_without_row_rules_is_read_from_the_anchor_cells():
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    rows = [sales_row(114, 126, ["AGIS"], "BC", "181,500", "2023", ["Namura, Japan"], "68.00", "UNDISCLOSED"),
            sales_row(126, 150, ["AP LOVRIJENAC", "(Hull Ht82-278)"], "BC", "82,000", "1/2004", ["ex Jiangsu New Hantong"], "37.00", "NNC"),
            sales_row(150, 162, ["CHOW"], "BC", "181,146", "2016", ["SWS"], "43.10", "GENCO")]
    table(page, SALES_COLS, SALES_HDR, 100, rows, [(162, ())])
    md = LF.join(["## Second-hand Market Reported Sold", "",
                  "| Name | Type | DWT | Built | Yard | Price ($M) | Buyers | Comments |", "| --- | --- | --- | --- | --- | --- | --- | --- |",
                  "| AGIS | BC | 181500 | 2023 | Namura, Japan | 68.00 | UNDISCLOSED |  |",
                  "| AP LOVRIJENAC | BC | 82000 |  | ex Jiangsu New Hantong | 37.00 | NNC |  |",
                  "| CHOW | BC | 181146 | 2016 | SWS | 43.10 | GENCO |  |", ""])
    new, changes, unresolved = fx.fix_document(md, fx.Pdf(doc))
    assert unresolved == []
    assert "| AP LOVRIJENAC (Hull Ht82-278) | BC | 82000 | 1/2004 |" in new
    assert sorted(c["class"] for c in changes) == ["cell_extended", "cell_filled"]


# ---------------------------------------------------------------- everything else
def test_prose_and_other_tables_are_byte_identical(source):
    new, _, _ = _fix(source)
    old_lines, new_lines = source.split(LF), new.split(LF)
    for marker in ("---", "title:", "# Carriers Market Report", "Hand-perfected prose", "## BSPA", "| Tankers | Vlcc",
                   "| Sector |", "Closing prose line"):
        assert [ln for ln in new_lines if marker in ln and not ln.startswith("| ---")] == \
            [ln for ln in old_lines if marker in ln and not ln.startswith("| ---")]
    head = old_lines.index("## Second-hand Market Reported Sold")
    assert new_lines[:head] == old_lines[:head]
    tail = old_lines.index("## BSPA Secondhand Market Assessments (5 Years Old)")
    assert new_lines[-(len(old_lines) - tail):] == old_lines[tail:]
    assert [ln for ln in new_lines if ln.startswith("## ")] == [ln for ln in old_lines if ln.startswith("## ")]


def test_fix_is_idempotent(source):
    new, changes, _ = _fix(source)
    assert changes
    again, changes2, unresolved2 = _fix(new)
    assert again == new and changes2 == [] and unresolved2 == []


def test_newbuilding_matching_table_is_left_unchanged(source):
    new, changes, _ = _fix(source)
    assert _lines(new, "| TANKER | 2 |") == _lines(source, "| TANKER | 2 |")
    assert not [c for c in changes if c["table"] == "Newbuilding Market"]


# ---------------------------------------------------------------- driver
def _tree(tmp_path, monkeypatch, eol):
    monkeypatch.setattr(fx, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(fx, "MAIN_CHECKOUT", tmp_path)
    md_dir = tmp_path / fx.MD_ROOT_REL / "2023"
    md_dir.mkdir(parents=True)
    stem = "carriers_2023_W46_synthetic"
    (md_dir / (stem + ".md")).write_bytes(FIXTURE.read_text(encoding="utf-8").replace(LF, eol).encode("utf-8"))
    pdf_dir = tmp_path / fx.PDF_ROOT_REL / "2023"
    pdf_dir.mkdir(parents=True)
    doc = make_doc()
    doc.save(str(pdf_dir / (stem + ".pdf")))
    doc.close()
    return md_dir / (stem + ".md"), tmp_path / fx.STAGING_REL


def test_run_with_real_pdf_preserves_crlf_and_writes_changelog(tmp_path, monkeypatch):
    md, out = _tree(tmp_path, monkeypatch, CRLF)
    s = fx.run(None, None, False, out)
    assert s["files_changed"] == 1
    assert s["by_class"] == {"cell_extended": 5, "cell_filled": 2, "en_bloc": 3, "demolition_realign": 1, "row_added": 1}
    assert s["by_year_class"]["2023"]["row_added"] == 1
    staged = (out / "2023" / md.name).read_bytes()
    assert b"\r\n" in staged and staged.count(b"\n") == staged.count(b"\r\n")
    meta = json.loads((out / "2023" / (md.stem + ".changelog.json")).read_text(encoding="utf-8"))
    assert meta["source_sha256"] == hashlib.sha256(md.read_bytes()).hexdigest()
    assert meta["staged_sha256"] == hashlib.sha256(staged).hexdigest()
    assert all({"line", "class", "old", "new", "pdf_evidence"} <= set(c) for c in meta["changes"])
    assert all("page" in c["pdf_evidence"] and len(c["pdf_evidence"]["bbox"]) == 4 for c in meta["changes"])


def test_run_preserves_lf_files(tmp_path, monkeypatch):
    md, out = _tree(tmp_path, monkeypatch, LF)
    fx.run(None, None, False, out)
    assert b"\r" not in (out / "2023" / md.name).read_bytes()


def test_run_wipes_stale_staged_files_of_a_processed_file(tmp_path, monkeypatch):
    md, out = _tree(tmp_path, monkeypatch, LF)
    fx.run(None, None, False, out)
    md.write_bytes((out / "2023" / md.name).read_bytes())          # now nothing is left to fix
    fx.run(None, None, False, out)
    assert not (out / "2023" / md.name).exists() and not (out / "2023" / (md.stem + ".changelog.json")).exists()


def test_detect_only_writes_nothing_and_reports_counts(tmp_path, monkeypatch):
    md, out = _tree(tmp_path, monkeypatch, LF)
    s = fx.run(None, None, True, out)
    assert not out.exists() and s["changes"] == 12 and s["unresolved"] == []


def test_rerun_on_staged_output_yields_zero_changes(tmp_path, monkeypatch):
    md, out = _tree(tmp_path, monkeypatch, CRLF)
    fx.run(None, None, False, out)
    md.write_bytes((out / "2023" / md.name).read_bytes())
    s = fx.run(None, None, True, tmp_path / "staging2")
    assert s["changes"] == 0 and s["files_changed"] == 0


def test_missing_pdf_is_reported_not_fatal(tmp_path, monkeypatch):
    md, out = _tree(tmp_path, monkeypatch, LF)
    (tmp_path / fx.PDF_ROOT_REL / "2023" / (md.stem + ".pdf")).unlink()
    s = fx.run(None, None, True, out)
    assert s["no_pdf"] == [md.name] and s["changes"] == 0


def test_apply_is_dry_run_by_default_and_refuses_changed_target_or_tampered_staged(tmp_path):
    md = tmp_path / fx.MD_ROOT_REL / "2025"
    st = tmp_path / fx.STAGING_REL / "2025"
    md.mkdir(parents=True)
    st.mkdir(parents=True)
    (md / "a.md").write_bytes(b"old\r\n")
    (md / "b.md").write_bytes(b"untouched\r\n")
    (st / "a.md").write_bytes(b"new\r\n")
    (st / "b.md").write_bytes(b"stray staged file without changelog\r\n")
    (st / "a.changelog.json").write_text(json.dumps({
        "md": str(fx.MD_ROOT_REL / "2025" / "a.md"), "changes": [{"line": 1}],
        "source_sha256": hashlib.sha256(b"old\r\n").hexdigest(),
        "staged_sha256": hashlib.sha256(b"new\r\n").hexdigest()}))
    staging = tmp_path / fx.STAGING_REL
    (st / "a.md").write_bytes(b"tampered\r\n")
    r = fx.apply_staged(staging, True, tmp_path)
    assert not r["applied"] and "staged file differs" in r["refused"][0]["reason"]
    (st / "a.md").write_bytes(b"new\r\n")
    r = fx.apply_staged(staging, False, tmp_path)
    assert r["dry_run"] and len(r["applied"]) == 1 and (md / "a.md").read_bytes() == b"old\r\n"
    fx.apply_staged(staging, True, tmp_path)
    assert (md / "a.md").read_bytes() == b"new\r\n" and (md / "b.md").read_bytes() == b"untouched\r\n"
    (md / "a.md").write_bytes(b"edited meanwhile\r\n")
    r = fx.apply_staged(staging, True, tmp_path)
    assert "target changed" in r["refused"][0]["reason"] and (md / "a.md").read_bytes() == b"edited meanwhile\r\n"


def test_apply_without_promote_is_rejected(monkeypatch):
    monkeypatch.setattr("sys.argv", ["carriers_rows_fix", "--apply"])
    with pytest.raises(SystemExit):
        fx.main()


def test_multi_word_placeholders_are_not_vessels():
    for text in ("NONE REPORTED", "NONE REPORTED SOLD", "no reported sales", "No Sales Reported"):
        assert fx.NONE_RE.match(fx.compact(text)), text


def test_numeric_cell_is_not_extended_by_a_longer_number():
    assert not fx.strict_part("79.52", "79.520")
    assert fx.strict_part("AP LOVRIJENAC", "AP LOVRIJENAC (Hull Ht82-278)")


def test_label_fix_only_rewrites_supra_63k_to_tess_58k(source):
    md = (source + LABEL_MD).replace("| SUPRA 63K | 12396.0 | 316.0 | 12080.0 |", "| HANDY 38K | 12396.0 | 316.0 | 12080.0 |")
    new, changes, unresolved = _fix(md, make_doc(labels=True))
    assert not _by_class(changes, "label_fix") and "| HANDY 38K | 12396.0 | 316.0 | 12080.0 |" in new.split(LF)
    assert any("only SUPRA 63K -> TESS 58K" in u.get("reason", "") for u in unresolved)
