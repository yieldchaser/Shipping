"""Tests for scripts/md_cleanup/intermodal_fix.py (targeted Intermodal MD fixer).

The fixture MD (tests/fixtures/intermodal/synthetic_report.md) is paired with a synthetic PDF
page layout built below, so the tests exercise the real geometry code without live MDs or PDFs.
"""
import hashlib
import json
from pathlib import Path

import pytest

pymupdf = pytest.importorskip("pymupdf")

from scripts.md_cleanup import intermodal_fix as fx  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "intermodal" / "synthetic_report.md"
LF = chr(10)
CRLF = chr(13) + chr(10)
PM = "±"
BS = chr(92)
FONT_SIZE = 8


def _w(text):
    return pymupdf.get_text_length(text, "helv", FONT_SIZE)


def sp(xc, yc, text, rot=False):
    w = _w(text)
    return {"x0": xc - w / 2, "x1": xc + w / 2, "y0": yc - 4.6, "y1": yc + 4.6, "xc": xc, "yc": yc,
            "text": text, "size": float(FONT_SIZE), "rot": rot}


def _row(y, cols):
    return [sp(x, y, t) for x, t in cols]


def page_nb_orders():
    spans = _row(100, [(40, "Units"), (90, "Type"), (152, "Size"), (230, "Yard"), (308, "Delivery"),
                       (385, "Buyer"), (468, "Price"), (550, "Comments")])
    rows = [(130, "1", "Bulker", "210,000 dwt", None, "2024", "Japanese (NYK Line)"),
            (160, "1", "Bulker", "210,000 dwt", None, "2024", "Japanese (K Line)"),
            (190, "1", "Bulker", "210,000 dwt", None, "2025", "Japanese (MOL)"),
            (220, "2", "Tanker", "50,000 dwt", "STX Offshore, S. Korea", "2022", "Greek (Steelships)")]
    for y, units, typ, size, yard, deliv, buyer in rows:
        spans += _row(y, [(40, units), (90, typ), (152, size), (308, deliv), (385, buyer)])
        if yard:
            spans.append(sp(230, y, yard))
    spans += [sp(230, 160, "Nihon, Japan"),                 # yard spans rows 1-3
              sp(468, 160, "$ 120.0m"),                      # price spans rows 1-3
              sp(550, 145, "Tier III"),                      # comment spans rows 1-2 only
              sp(468, 220, "$ 37.0m"), sp(550, 220, "LNG fuelled")]
    rules = [(112, 10, 590), (145, 10, 190), (145, 270, 425), (175, 10, 190), (175, 270, 425),
             (175, 510, 590), (205, 10, 590), (235, 10, 590)]
    return {"spans": spans, "rules": rules}


def page_sales():
    spans = _row(100, [(40, "Size"), (110, "Name"), (200, "Yard"), (300, "Price"), (400, "Buyers")])
    data = [(130, "PMAX", "WASHINGTON EXPRESS", "CSBC CORP, Taiwan", None, None),
            (160, "PMAX", "CHARLESTON EXPRESS", "CSBC CORP, Taiwan", None, None),
            (190, "FEEDER", "BANAK", "JIANGSU NEWYANGZI, China", None, "Greek"),
            (220, "FEEDER", "BALSA", "JIANGSU NEWYANGZI, China", None, "Turkish")]
    for y, size, name, yard, _, buyer in data:
        spans += _row(y, [(40, size), (110, name), (200, yard)])
        if buyer:
            spans.append(sp(400, y, buyer))
    spans += [sp(300, 145, "undisclosed"), sp(400, 145, "Greek (Lomar Shipping)"),
              sp(300, 205, "region $ 14.5m each")]
    rules = [(112, 10, 450), (145, 10, 250), (175, 10, 450), (205, 10, 250), (205, 350, 450), (235, 10, 450)]
    return {"spans": spans, "rules": rules}


def page_nb_prices(values_override=None):
    spans = [sp(150, 70, "Indicative Newbuilding Prices (million$)"), sp(62, 85, "Vessel"),
             sp(138, 85, "16/07/2021"), sp(185, 85, "09/07/2021"), sp(222, 85, PM + "%"),
             sp(244, 85, "2020"), sp(265, 85, "2019"), sp(287, 85, "2018")]
    rows = [(105, "Newcastlemax", "205k", ["62.5", "62.5", "0.0%", "51", "54", "51"]),
            (116, "Capesize", "180k", ["58.5", "58.5", "0.0%", "49", "52", "49"]),
            (127, "VLCC", "300k", ["100.5", "99.5", "1.0%", "88", "92", "88"]),
            (138, "LNG 174k cbm", None, ["193.0", "192.0", "0.5%", "187", "186", "181"]),
            (149, "LGC LPG 80k cbm", None, ["76.5", "75.5", "1.3%", "73", "73", "71"])]
    for y, vessel, size, vals in rows:
        spans.append(sp(45, y, vessel))
        if size:
            spans.append(sp(104, y, size))
        spans += [sp(x, y, v) for x, v in zip((138, 185, 222, 244, 265, 287), vals)]
    spans += [sp(18, 110.5, "Bulkers", rot=True), sp(18, 127, "Tankers", rot=True), sp(18, 143.5, "Gas", rot=True)]
    return {"spans": spans, "rules": []}


def page_demolition():
    spans = [sp(300, 80, "$/Ldt"), sp(300, 100, "$ 580.0m"), sp(300, 120, "$ 512.5m"), sp(300, 140, "$ 570/Ldt")]
    return {"spans": spans, "rules": []}


class FakePdf:
    def __init__(self, pages):
        self.pages = pages

    def __len__(self):
        return len(self.pages)

    def spans(self, i):
        return self.pages[i]["spans"]

    def rules(self, i):
        by_y = {}
        for y, x0, x1 in self.pages[i]["rules"]:
            by_y.setdefault(y, []).append((x0, x1))
        return [{"y": y, "ivs": sorted(iv)} for y, iv in sorted(by_y.items())]


def all_pages():
    return [page_nb_orders(), page_sales(), page_nb_prices(), page_demolition()]


def write_pdf(path, pages):
    doc = pymupdf.open()
    for pg in pages:
        page = doc.new_page(width=595, height=842)
        for s in pg["spans"]:
            if s["rot"]:
                page.insert_text((s["xc"] + 2.8, s["yc"] + _w(s["text"]) / 2), s["text"], fontsize=FONT_SIZE,
                                 fontname="helv", rotate=90)
            else:
                page.insert_text((s["x0"], s["yc"] + 2.83), s["text"], fontsize=FONT_SIZE, fontname="helv")
        for y, x0, x1 in pg["rules"]:
            page.draw_line((x0, y), (x1, y), color=(0.7, 0.7, 0.7), width=0.7)
    doc.save(str(path))
    doc.close()


@pytest.fixture
def source():
    return FIXTURE.read_text(encoding="utf-8")


def _fix(text, pages=None):
    return fx.fix_document(text, FakePdf(pages or all_pages()))


def _by_class(changes, cls):
    return [c for c in changes if c["class"] == cls]


def _line(text, startswith):
    return next(ln for ln in text.split(LF) if ln.startswith(startswith))


# ---------------------------------------------------------------- helpers
def test_split_join_roundtrip():
    line = "| 1 | Bulker | 210,000 dwt |  | 2024 |"
    assert fx.join_row(fx.split_row(line)) == line
    assert fx.is_sep("| --- | --- |") and not fx.is_sep("| a | b |")


def test_norm_pm_maps_replacement_glyph_but_not_words():
    assert fx.norm_pm("�%") == PM + "%" and fx.norm_pm(PM + "%") == PM + "%"
    assert fx.norm_pm("0.0%") == "0.0%" and fx.norm_pm("YTD") == "YTD"


# ---------------------------------------------------------------- class 1: fill-down
def test_fill_down_copies_anchor_text_into_spanned_rows(source):
    new, changes, unresolved = _fix(source)
    assert [u for u in unresolved if u["class"] == "fill_down"] == []
    out = new.split(LF)
    i = out.index("| 1 | Bulker | 210,000 dwt | Nihon, Japan | 2024 | Japanese (NYK Line) | $ 120.0m (en bloc) | Tier III |")
    assert out[i + 1] == "| 1 | Bulker | 210,000 dwt | Nihon, Japan | 2024 | Japanese (K Line) | $ 120.0m (en bloc) | Tier III |"
    assert out[i + 2].startswith("| 1 | Bulker | 210,000 dwt | Nihon, Japan | 2025 | Japanese (MOL) | $ 120.0m (en bloc) |")


def test_price_spanning_rows_gets_en_bloc_suffix_on_anchor_too(source):
    _, changes, _ = _fix(source)
    price = [c for c in _by_class(changes, "fill_down") if c["column"] == "Price" and "$ 120.0m" in c["new"]]
    assert sorted(c["old"] for c in price) == ["", "", "$ 120.0m"]
    assert all(c["new"] == "$ 120.0m (en bloc)" for c in price)
    assert [c["pdf_evidence"]["en_bloc_anchor"] for c in price].count(True) == 1


def test_undisclosed_is_filled_plain_and_each_price_is_not_en_bloc(source):
    new, changes, _ = _fix(source)
    assert _line(new, "| PMAX | WASHINGTON") == \
        "| PMAX | WASHINGTON EXPRESS | CSBC CORP, Taiwan | undisclosed | Greek (Lomar Shipping) |"
    assert _line(new, "| FEEDER | BALSA") == "| FEEDER | BALSA | JIANGSU NEWYANGZI, China | region $ 14.5m each | Turkish |"
    assert _line(new, "| FEEDER | BANAK").endswith("| region $ 14.5m each | Greek |")
    assert not any("en bloc" in c["new"] for c in changes if c.get("column") == "Price" and "each" in c["new"])


def test_no_fill_where_pdf_shows_a_separator_between_rows(source):
    new, _, _ = _fix(source)
    # comments span rows 1-2 only: a rule under row 2 separates row 3 whose comment is genuinely blank
    assert _line(new, "| 1 | Bulker | 210,000 dwt | Nihon, Japan | 2025").endswith("| $ 120.0m (en bloc) |  |")
    # same table, but the PDF draws full-width rules between all rows: nothing may be filled
    page = page_nb_orders()
    page["rules"] = [(112, 10, 590), (145, 10, 590), (175, 10, 590), (205, 10, 590), (235, 10, 590)]
    pages = [page] + all_pages()[1:]
    new2, changes2, _ = _fix(source, pages)
    assert [ln for ln in new2.split(LF) if ln.startswith("| 1 | Bulker")] == \
        [ln for ln in source.split(LF) if ln.startswith("| 1 | Bulker")]
    assert not [c for c in changes2 if c["class"] == "fill_down" and "Bulker" in c["new"]]
    assert not [c for c in changes2 if c.get("column") in ("Yard", "Comments")]


def test_text_not_inside_the_block_is_unresolved_not_guessed(source):
    page = page_nb_orders()
    page["spans"] = [s for s in page["spans"] if s["text"] != "Nihon, Japan"] + [sp(230, 160, "Osaka, Japan")]
    _, changes, unresolved = _fix(source, [page] + all_pages()[1:])
    assert any("differs from printed block text" in u["reason"] for u in unresolved)
    assert not [c for c in changes if c.get("column") == "Yard"]


def test_one_char_typo_in_pdf_text_layer_still_matches(source):
    page = page_sales()
    page["spans"] = [s for s in page["spans"] if s["text"] != "Greek (Lomar Shipping)"] + [sp(400, 145, "Greek (Lomar Shipping")]
    new, _, unresolved = _fix(source, [page_nb_orders(), page, page_nb_prices(), page_demolition()])
    assert "| undisclosed | Greek (Lomar Shipping) |" in _line(new, "| PMAX | WASHINGTON")
    assert [u for u in unresolved if u["class"] == "fill_down"] == []


def test_filled_text_is_the_anchor_cell_verbatim_not_the_pdf_text(source):
    md = source.replace("Greek (Lomar Shipping)", "Greek (Lomar " + BS + "&amp; Co) **x**")
    page = page_sales()
    page["spans"] = [s for s in page["spans"] if s["text"] != "Greek (Lomar Shipping)"] + [sp(400, 145, "Greek (Lomar & Co) x")]
    new, _, _ = _fix(md, [page_nb_orders(), page, page_nb_prices(), page_demolition()])
    assert _line(new, "| PMAX | WASHINGTON").endswith("| undisclosed | Greek (Lomar " + BS + "&amp; Co) **x** |")


def test_blocks_not_bounded_by_a_rule_below_are_not_filled(source):
    page = page_sales()
    page["rules"] = [r for r in page["rules"] if r[0] != 235]
    new, _, unresolved = _fix(source, [page_nb_orders(), page, page_nb_prices(), page_demolition()])
    assert "extent not provable" in " ".join(u["reason"] for u in unresolved)
    assert _line(new, "| FEEDER | BALSA").endswith("|  | Turkish |")


def test_wrapped_pdf_row_split_over_two_md_rows_is_not_filled():
    md = LF.join(["## Containers", "", "| Size | Name | Yard | Price | Buyers |", "| --- | --- | --- | --- | --- |",
                  "| SUB | MAERSK | KVAERNER, Germany | $ 8.0m | Greek |",
                  "| PMAX | PENANG |  |  |  |",
                  "| FEEDER | BANAK | JIANGSU, China | $ 1.0m | Turkish |", ""])
    spans = _row(100, [(40, "Size"), (110, "Name"), (200, "Yard"), (300, "Price"), (400, "Buyers")])
    spans += [sp(40, 125, "SUB"), sp(40, 137, "PMAX"), sp(110, 125, "MAERSK"), sp(110, 137, "PENANG"),
              sp(200, 131, "KVAERNER, Germany"), sp(300, 131, "$ 8.0m"), sp(400, 131, "Greek"),
              sp(40, 165, "FEEDER"), sp(110, 165, "BANAK"), sp(200, 165, "JIANGSU, China"),
              sp(300, 165, "$ 1.0m"), sp(400, 165, "Turkish")]
    rules = [(112, 10, 450), (150, 10, 450), (180, 10, 450)]
    new, changes, unresolved = fx.fix_document(md, FakePdf([{"spans": spans, "rules": rules}]))
    assert new == md and changes == []
    assert "not separated by ruling lines" in unresolved[0]["reason"]


# ---------------------------------------------------------------- class 2: NB prices
def test_nb_prices_rebuilt_to_single_schema_with_gas_rows_unshifted(source):
    new, changes, unresolved = _fix(source)
    assert [u for u in unresolved if u["class"] == "nb_prices"] == []
    out = new.split(LF)
    i = out.index("## Indicative Newbuilding Prices ($ Million)")
    assert out[i + 1] == ""
    assert out[i + 2] == f"| Sector | Vessel | Size | 16/07/2021 | 09/07/2021 | {PM}% | 2020 | 2019 | 2018 |"
    assert out[i + 3] == "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"
    assert out[i + 4:i + 9] == [
        "| Bulkers | Newcastlemax | 205k | 62.5 | 62.5 | 0.0% | 51 | 54 | 51 |",
        "| Bulkers | Capesize | 180k | 58.5 | 58.5 | 0.0% | 49 | 52 | 49 |",
        "| Tankers | VLCC | 300k | 100.5 | 99.5 | 1.0% | 88 | 92 | 88 |",
        "| Gas | LNG 174k cbm |  | 193.0 | 192.0 | 0.5% | 187 | 186 | 181 |",
        "| Gas | LGC LPG 80k cbm |  | 76.5 | 75.5 | 1.3% | 73 | 73 | 71 |"]
    assert "**" not in "\n".join(out[i + 2:i + 9])
    assert "## TC Rates" not in out[i - 1:i + 1] and out[i + 9] == ""
    nb = _by_class(changes, "nb_prices")
    assert len(nb) == 1 and nb[0]["pdf_evidence"]["sectors"] == {"Bulkers": 2, "Tankers": 1, "Gas": 2}
    assert nb[0]["pdf_evidence"]["page"] == 3


def test_nb_value_not_on_the_pdf_row_leaves_table_unchanged(source):
    bad = source.replace("| Capesize | **180k** | 58.5 | 58.5 |", "| Capesize | **180k** | 58.6 | 58.5 |")
    new, changes, unresolved = _fix(bad)
    assert not _by_class(changes, "nb_prices")
    assert any(u["class"] == "nb_prices" and "leading cells of the PDF row" in u["reason"] for u in unresolved)
    assert "| Capesize | **180k** | 58.6 | 58.5 |" in new and "## TC Rates" in new


def test_numeric_multiset_guard_refuses_a_bad_rebuild(source, monkeypatch):
    real = fx.parse_nb_old

    def lossy(t):
        rows = real(t)
        rows[0]["cells"] = rows[0]["cells"] + ["99.9"]       # a token the rebuilt table does not carry
        return rows
    monkeypatch.setattr(fx, "parse_nb_old", lossy)
    new, changes, unresolved = _fix(source)
    assert not _by_class(changes, "nb_prices")
    assert any("not all kept" in u["reason"] for u in unresolved)
    assert "## TC Rates" in new


def test_nb_old_values_that_are_a_leading_subset_are_completed_from_the_pdf(source):
    old = "| Capesize | **180k** | 58.5 | 58.5 | 0.0% | 49 | 52 | 49 |"
    bad = source.replace(old, "| Capesize | **180k** | 58.5 | 58.5 | 0.0% | 49 | 52 |")
    bad = bad.replace("| VLCC | **300k** | 100.5 | 99.5 | **1.0%** | 88 | 92 | 88 |", "| VLCC | **300k** | 100.5 | 99.5 | **1.0%** | 88 | 92 |")
    new, changes, unresolved = _fix(bad)
    assert [u for u in unresolved if u["class"] == "nb_prices"] == []
    assert "| Bulkers | Capesize | 180k | 58.5 | 58.5 | 0.0% | 49 | 52 | 49 |" in new
    assert "| Tankers | VLCC | 300k | 100.5 | 99.5 | 1.0% | 88 | 92 | 88 |" in new
    added = _by_class(changes, "nb_prices")[0]["pdf_evidence"]["added_from_pdf"]
    assert [(a["row"], a["col"], a["value"]) for a in added] == [("Capesize", "2018", "49"), ("VLCC", "2018", "88")]
    assert all(a["bbox"][0] < a["bbox"][2] and a["bbox"][1] < a["bbox"][3] for a in added)
    again, changes2, _ = _fix(new)
    assert not _by_class(changes2, "nb_prices") and again == new


def test_nb_missing_old_value_in_the_middle_is_refused(source):
    bad = source.replace("| Capesize | **180k** | 58.5 | 58.5 | 0.0% | 49 | 52 | 49 |",
                         "| Capesize | **180k** | 58.5 | 58.5 | 0.0% | 49 | 49 |")
    new, changes, unresolved = _fix(bad)
    assert not _by_class(changes, "nb_prices") and "## TC Rates" in new
    assert any("leading cells of the PDF row" in u["reason"] for u in unresolved)


def test_nb_misplaced_old_value_is_refused(source):
    bad = source.replace("| Capesize | **180k** | 58.5 | 58.5 | 0.0% | 49 | 52 | 49 |",
                         "| Capesize | **180k** | 58.5 | 58.5 | 0.0% | 52 | 49 | 49 |")
    new, changes, unresolved = _fix(bad)
    assert not _by_class(changes, "nb_prices") and "## TC Rates" in new
    assert any("another column" in u["reason"] for u in unresolved)


def test_nb_added_cells_must_align_in_one_pdf_column(source):
    bad = source.replace("| Capesize | **180k** | 58.5 | 58.5 | 0.0% | 49 | 52 | 49 |",
                         "| Capesize | **180k** | 58.5 | 58.5 | 0.0% | 49 | 52 |")
    bad = bad.replace("| VLCC | **300k** | 100.5 | 99.5 | **1.0%** | 88 | 92 | 88 |", "| VLCC | **300k** | 100.5 | 99.5 | **1.0%** | 88 | 92 |")
    page = page_nb_prices()
    for s_ in page["spans"]:
        if s_["text"] == "88" and s_["yc"] == 127 and s_["xc"] > 280:
            s_["xc"] += 40
            s_["x0"] += 40
            s_["x1"] += 40
    _, changes, unresolved = _fix(bad, [page_nb_orders(), page_sales(), page, page_demolition()])
    assert not _by_class(changes, "nb_prices")
    assert any("not aligned" in u["reason"] for u in unresolved)


def test_nb_sector_conflict_between_md_and_pdf_is_refused(source):
    bad = source.replace("| **Tankers** |  |", "| **Gas** |  |")
    _, changes, unresolved = _fix(bad)
    assert not _by_class(changes, "nb_prices")
    assert any("sector" in u["reason"] for u in unresolved)


def test_nb_header_group_words_prefix_leaf_cells_but_not_years():
    def w(xc, yc, text, width=20):
        return {"x0": xc - width / 2, "x1": xc + width / 2, "xc": xc, "yc": yc, "text": text}
    xs = (180, 235, 280, 316, 345, 375, 405, 442, 490, 547)
    info = [{"val_spans": [{"xc": x} for x in xs]}]
    words = [w(180, 281, "4-Aug-23", 40), w(235, 281, "28-J", 20), w(246, 281, "ul-23", 10), w(280, 281, "�%", 11),
             w(330, 275, "YTD", 18), w(390, 275, "5-year", 30), w(497, 275, "Average", 40),
             w(316, 292, "High"), w(345, 292, "Low"), w(375, 292, "High"), w(405, 292, "Low"),
             w(442, 292, "2022"), w(490, 292, "2021"), w(547, 292, "2020")]
    assert fx.nb_header(words, info, [], 10) == ["4-Aug-23", "28-Jul-23", PM + "%", "YTD High", "YTD Low",
                                                 "5-year High", "5-year Low", "Average 2022", "Average 2021", "Average 2020"]


def test_nb_header_unprovable_is_refused():
    info = [{"val_spans": [{"xc": 100}, {"xc": 150}]}]
    with pytest.raises(fx.FixError):
        fx.nb_header([], info, ["Sector", "Vessel Class", "Size", "Current", "Previous"], 2)


# ---------------------------------------------------------------- class 3: demolition
def test_demolition_million_notation_becomes_per_ldt(source):
    new, changes, unresolved = _fix(source)
    assert "| TANKER | $ 580/Ldt | Pakistani |" in new
    dem = _by_class(changes, "demolition_ldt")
    assert len(dem) == 1 and dem[0]["old"] == "$ 580.0m" and dem[0]["new"] == "$ 580/Ldt"
    assert "normalised per owner decision" in dem[0]["pdf_evidence"]["note"]
    assert dem[0]["pdf_evidence"]["page"] == 4 and len(dem[0]["pdf_evidence"]["bbox"]) == 4


def test_demolition_out_of_range_decimals_and_unprinted_values_are_left(source):
    new, _, unresolved = _fix(source)
    assert "| $ 512.5m | Indian |" in new            # other decimals
    assert "| $ 1600.0m | Indian |" in new           # above 1500
    assert "| $ 90.0m | Bangladeshi |" in new        # below 100
    assert "| $ 570/Ldt | Indian |" in new           # already per ldt
    assert "| $ 700.0m | Indian |" in new            # not printed on the PDF -> not normalised
    assert [u["class"] for u in unresolved] == ["demolition_ldt"] and "not found in the PDF" in unresolved[0]["reason"]


# ---------------------------------------------------------------- untouched material, idempotency
def test_prose_and_chart_tables_are_byte_identical(source):
    new, changes, _ = _fix(source)
    src, out = source.split(LF), new.split(LF)
    for needle in ("# Weekly Market Report", "Issue: Week 28", "Scrap prices reached $ 580.0m", "A combination of rising",
                   "### Bulk Carriers Newbuilding Prices (m$)", "| Date | Capesize | Kamsarmax | Ultramax | Handysize |",
                   "| 16/Jul/20 | 48 | 27 |  | 21 |", "| 16/Aug/20 | 48 | 27 | 26 |  |",
                   "Appetite for new orders resumed", "© Intermodal Research 20/07/2021 7"):
        assert any(ln.startswith(needle) for ln in src) and any(ln.startswith(needle) for ln in out)
    changed_src = {c["line"] - 1 for c in changes}
    changed_src |= {i for c in _by_class(changes, "nb_prices") for i in range(c["line"] - 1, c["line"] - 1 + len(c["old"]))}
    kept = [ln for i, ln in enumerate(src) if i not in changed_src]
    it = iter(out)
    assert all(any(ln == o for o in it) for ln in kept)       # every unchanged source line survives, in order


def test_fix_is_idempotent(source):
    first, changes, _ = _fix(source)
    assert changes
    second, changes2, _ = _fix(first)
    assert changes2 == [] and second == first


def test_already_target_schema_table_is_left_unchanged(source):
    first, _, _ = _fix(source)
    _, changes, _ = _fix(first)
    assert not _by_class(changes, "nb_prices")


# ---------------------------------------------------------------- driver
def _tree(tmp_path, monkeypatch, eol):
    monkeypatch.setattr(fx, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(fx, "MAIN_CHECKOUT", tmp_path)
    md_dir = tmp_path / fx.MD_ROOT_REL / "2021"
    md_dir.mkdir(parents=True)
    stem = "intermodal_2021_W28_synthetic"
    (md_dir / (stem + ".md")).write_bytes(FIXTURE.read_text(encoding="utf-8").replace(LF, eol).encode("utf-8"))
    pdf_dir = tmp_path / fx.PDF_ROOT_REL / "2021"
    pdf_dir.mkdir(parents=True)
    write_pdf(pdf_dir / (stem + ".pdf"), all_pages())
    return md_dir / (stem + ".md"), tmp_path / fx.STAGING_REL


def test_run_with_real_pdf_preserves_crlf_and_writes_changelog(tmp_path, monkeypatch):
    md, out = _tree(tmp_path, monkeypatch, CRLF)
    s = fx.run(None, None, False, out)
    assert s["files_changed"] == 1 and s["by_class"]["nb_prices"] == 1 and s["by_class"]["demolition_ldt"] == 1
    assert s["by_class"]["fill_down"] == 9 and s["by_year_class"]["2021"]["fill_down"] == 9
    staged = (out / "2021" / md.name).read_bytes()
    assert b"\r\n" in staged and staged.count(b"\n") == staged.count(b"\r\n")
    meta = json.loads((out / "2021" / (md.stem + ".changelog.json")).read_text(encoding="utf-8"))
    assert meta["source_sha256"] == hashlib.sha256(md.read_bytes()).hexdigest()
    ch = meta["changes"][0]
    assert {"line", "class", "old", "new", "pdf_evidence"} <= set(ch)
    fills = [c for c in meta["changes"] if c["class"] == "fill_down"]
    assert all("page" in c["pdf_evidence"] and len(c["pdf_evidence"]["bbox"]) == 4 for c in fills)


def test_run_preserves_lf_files(tmp_path, monkeypatch):
    md, out = _tree(tmp_path, monkeypatch, LF)
    fx.run(None, None, False, out)
    assert b"\r" not in (out / "2021" / md.name).read_bytes()


def test_detect_only_writes_nothing_and_reports_counts(tmp_path, monkeypatch):
    md, out = _tree(tmp_path, monkeypatch, LF)
    s = fx.run(None, None, True, out)
    assert not out.exists() and s["changes"] == s["by_class"]["fill_down"] + 2
    assert s["unresolved_by_class"] == {"demolition_ldt": 1}


def test_rerun_on_staged_output_yields_zero_changes(tmp_path, monkeypatch):
    md, out = _tree(tmp_path, monkeypatch, CRLF)
    fx.run(None, None, False, out)
    md.write_bytes((out / "2021" / md.name).read_bytes())
    s = fx.run(None, None, True, tmp_path / "staging2")
    assert s["changes"] == 0 and s["files_changed"] == 0


def test_missing_pdf_is_reported_not_fatal(tmp_path, monkeypatch):
    md, out = _tree(tmp_path, monkeypatch, LF)
    (tmp_path / fx.PDF_ROOT_REL / "2021" / (md.stem + ".pdf")).unlink()
    s = fx.run(None, None, True, out)
    assert s["no_pdf"] == [md.name] and s["changes"] == 0


def test_apply_is_dry_run_by_default_and_refuses_changed_target(tmp_path):
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
    assert r["refused"] and (md / "a.md").read_bytes() == b"edited meanwhile\r\n"


def test_apply_without_promote_is_rejected(monkeypatch):
    monkeypatch.setattr("sys.argv", ["intermodal_fix", "--apply"])
    with pytest.raises(SystemExit):
        fx.main()


def test_nb_prose_number_beside_one_row_is_not_taken_as_a_value_cell(source):
    page = page_nb_prices()
    page["spans"].append(sp(310, 105, "22"))                   # "22 units being ordered ..." printed right of row 1
    new, changes, unresolved = _fix(source, [page_nb_orders(), page_sales(), page, page_demolition()])
    assert [u for u in unresolved if u["class"] == "nb_prices"] == []
    assert _by_class(changes, "nb_prices")[0]["pdf_evidence"]["added_from_pdf"] == []
    assert "| Bulkers | Newcastlemax | 205k | 62.5 | 62.5 | 0.0% | 51 | 54 | 51 |" in new


def test_locate_token_requires_ldt_column_and_whole_number():
    head = sp(300, 80, "$/Ldt")
    other_col = FakePdf([{"spans": [head, sp(120, 100, "$ 580.0m")], "rules": []}])
    assert fx.locate_token(other_col, "580.0m") is None            # printed, but in another column
    longer = FakePdf([{"spans": [head, sp(300, 100, "$ 1580.0m")], "rules": []}])
    assert fx.locate_token(longer, "580.0m") is None               # inside a longer number
    no_head = FakePdf([{"spans": [sp(300, 100, "$ 580.0m")], "rules": []}])
    assert fx.locate_token(no_head, "580.0m") is None
    ok = FakePdf([{"spans": [head, sp(300, 100, "$ 580.0m")], "rules": []}])
    assert fx.locate_token(ok, "580.0m")[0] == 0
