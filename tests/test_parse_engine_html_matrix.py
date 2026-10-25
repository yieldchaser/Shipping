"""Grid reconstruction + cell normalisation for the VV Mini Matrix image (synthetic boxes, no OCR engine)."""
from __future__ import annotations

import pytest

from scripts.parse_engine_html.matrix import (AGES, COLUMNS, REF_CELL_RE, BandRead, Box, Cell, GridError,
                                              MatrixResult, cells_from_bands, decide_band, decide_date, finalize,
                                              normalise_pct, normalise_ref, parse_image_date, reconstruct_grid,
                                              ref_in_range, ref_value, validate_cells, vote)

COL_X = [110 + 44 * i + (6 if i >= 5 else 0) + (6 if i >= 9 else 0) for i in range(13)]


def synthetic_boxes(header=True, n_cols=13, drop_line=None, jitter=2, merged_last=False):
    boxes = [Box(60, 60, 250, 70, "Tankers"), Box(300, 60, 460, 70, "Bulkers")]   # group titles: few boxes
    y = 100.0
    if header:
        boxes += [Box(x - 14, y - 5, x + 14, y + 5, "HDR") for x in COL_X[:n_cols]]
        boxes.append(Box(30, y - 5, 50, y + 5, "Age"))
    y = 120.0
    lines = []
    for r in range(6):
        lines.append((y, True))
        lines.append((y + 12, False))
        y += 24.5
    for k, (ly, is_val) in enumerate(lines):
        if k == drop_line:
            continue
        for i, x in enumerate(COL_X[:n_cols]):
            dx = jitter if i % 2 else -jitter
            b = Box(x + dx - 15, ly - 5, x + dx + 15, ly + 5, "+0.5%" if is_val else "320k", coloured=is_val)
            boxes.append(b)
        if is_val:     # age label between the two lines of its row (far left)
            boxes.append(Box(36, ly + 1, 46, ly + 9, str(AGES[k // 2])))
    if merged_last:
        boxes.append(Box(COL_X[11] - 15, 270, COL_X[12] + 15, 280, "+22.4%+6.3%", coloured=True))
    return boxes


def test_reconstruct_grid_with_header_line():
    g = reconstruct_grid(synthetic_boxes())
    assert g.n_cols == 13 and g.n_rows == 6
    assert g.header_y == pytest.approx(100.0)
    assert g.val_y[0] == pytest.approx(120.0) and g.ref_y[0] == pytest.approx(132.0)
    assert g.val_y[5] == pytest.approx(120.0 + 5 * 24.5)
    assert g.col_pitch == pytest.approx(44, abs=8)
    for got, want in zip(g.col_x, COL_X):
        assert got == pytest.approx(want, abs=3)


def test_reconstruct_grid_without_header_line():
    g = reconstruct_grid(synthetic_boxes(header=False))
    assert g.header_y is None and g.n_rows == 6 and g.n_cols == 13


def test_age_labels_and_group_titles_do_not_become_columns_or_lines():
    g = reconstruct_grid(synthetic_boxes())
    assert min(g.col_x) > 90


def test_merged_box_is_ignored_for_geometry():
    g = reconstruct_grid(synthetic_boxes(merged_last=True))
    assert g.n_cols == 13


def test_twelve_columns_is_refused():
    with pytest.raises(GridError):
        reconstruct_grid(synthetic_boxes(n_cols=12))


def test_missing_text_line_is_refused():
    with pytest.raises(GridError):
        reconstruct_grid(synthetic_boxes(drop_line=5))


def test_uncoloured_percentage_lines_are_refused():
    boxes = synthetic_boxes()
    for b in boxes:
        b.coloured = False
    with pytest.raises(GridError):
        reconstruct_grid(boxes)


def test_too_few_boxes_is_refused():
    with pytest.raises(GridError):
        reconstruct_grid([Box(0, 0, 10, 10, "x")] * 5)


# --------------------------------------------------------------------------------------- normalisation
@pytest.mark.parametrize("text,sign,expected", [
    ("+0.5%", "+", "+0.5%"), ("-1.4%", "-", "-1.4%"), ("0.5%", "+", "+0.5%"), ("0.0%", "", "0.0%"),
    ("*1.1%", "+", "+1.1%"), (":0.4%", "+", "+0.4%"), ("N/A", "", "N/A"), ("NVA", "", "N/A"),
    ("+11.4%", "+", "+11.4%"), ("0,5%", "+", "+0.5%"),
])
def test_normalise_pct_accepts(text, sign, expected):
    assert normalise_pct(text, sign)[0] == expected


def test_sign_comes_from_colour_and_contradiction_is_rejected():
    assert normalise_pct("-0.5%", "+")[0] is None
    assert normalise_pct("0.5%", "-")[0] == "-0.5%"


def test_leading_digit_is_never_repaired_only_accepted_when_ink_is_wide():
    assert normalise_pct("10.4%", "+", wide=False)[0] is None          # could be a mis-read '+' glyph: reject
    assert normalise_pct("11.4%", "+", wide=True)[0] == "+11.4%"       # as wide as a genuine two-digit value
    assert normalise_pct("+10.4%", "+", wide=False)[0] == "+10.4%"     # explicit sign glyph read: genuine


def test_zero_keeps_a_printed_minus_only():
    assert normalise_pct("-0.0%", "-")[0] == "-0.0%"
    assert normalise_pct("0.0%", "")[0] == "0.0%"
    assert normalise_pct("+0.0%", "+")[0] == "0.0%"
    assert normalise_pct("0.0%", "")[0] == "0.0%"


@pytest.mark.parametrize("text", ["", "abc", "+.0%", "1.45%", "0.5%6"])
def test_normalise_pct_rejects_garbage(text):
    assert normalise_pct(text, "+")[0] is None


def test_normalise_ref_and_value():
    assert normalise_ref("320k") == "320k" and normalise_ref("320K") == "320k"
    assert normalise_ref("7000") == "7000" and normalise_ref("N/A") == "N/A"
    assert normalise_ref("J250") is None and normalise_ref("/000") is None
    assert normalise_ref("100") is None and normalise_ref("119") is None      # bare 3-digit sizes are not valid
    assert ref_value("320k") == 320000 and ref_value("7000") == 7000 and ref_value("N/A") is None
    assert REF_CELL_RE.match("110k") and not REF_CELL_RE.match("100")


@pytest.mark.parametrize("group,col,ref,ok", [
    ("Tankers", "Afra", "110k", True), ("Tankers", "Afra", "710k", False), ("Tankers", "Afra", "770k", False),
    ("Tankers", "VLCC", "310k", True), ("Tankers", "VLCC", "370k", False),
    ("Containers", "Fmax", "1100", True), ("Containers", "Fmax", "100", False),
    ("Containers", "Handy", "1750", True), ("Containers", "Handy", "7750", False),
    ("Bulkers", "Handy", "38k", True), ("Bulkers", "Handy", "380k", False), ("Tankers", "LR1", "N/A", True),
])
def test_benchmark_range_check(group, col, ref, ok):
    assert ref_in_range(group, col, ref) is ok


def _band(kind, texts, sign="", group="Tankers", col="Afra", wide=False):
    return BandRead(0, group, col, kind, sign, wide, [["raw", 5, t] for t in texts])


def test_benchmark_needs_two_agreeing_renders_and_range():
    assert decide_band(_band("ref", ["110k", "110k", "110k", "710k"]))[0] == "110k"
    assert decide_band(_band("ref", ["110k", "110k", "710k"]))[0] is None           # only 1 vote ahead
    assert decide_band(_band("ref", ["710k", "710k", "710k"]))[0] is None            # agreed but impossible
    assert decide_band(_band("ref", ["110k"]))[0] is None                          # single render: no size
    assert decide_band(_band("ref", ["110k", "710k"]))[0] is None                  # disagreement: no size
    assert decide_band(_band("ref", ["N/A", "N/A", "N/A", "11k"]))[0] == "N/A"


def test_value_needs_two_agreeing_renders():
    assert decide_band(_band("val", ["+0.5%", "+0.5%"], sign="+"))[0] == "+0.5%"
    assert decide_band(_band("val", ["+0.5%"], sign="+"))[0] is None
    assert decide_band(_band("val", ["+0.5%", "+0.6%"], sign="+"))[0] is None
    assert decide_band(_band("val", ["10.4%", "10.4%"], sign="+"))[0] is None       # no leading-digit repair
    assert decide_band(_band("val", ["0.5%", "0.5%"], sign=""))[0] is None          # non-zero but neutral colour


def test_blank_benchmark_does_not_fail_the_image_but_blank_value_does():
    bands = []
    for age in AGES:
        for g, c in COLUMNS:
            lo = {"Tankers": "320k"}.get(g, None)
            bands.append(BandRead(age, g, c, "val", "+", False, [["raw", 5, "+0.5%"], ["stretch", 5, "+0.5%"]]))
            bands.append(BandRead(age, g, c, "ref", "", False, [["raw", 5, "9999"]]))   # unreadable benchmark
    cells = cells_from_bands(bands)
    assert len(cells) == 78 and all(c.pct_text == "+0.5%" and c.ref_text == "" for c in cells)
    assert validate_cells(cells) == []
    bands[0].reads = [["raw", 5, "+0.5%"]]
    assert len(validate_cells(cells_from_bands(bands))) == 1


def _result(date_reads, image_date_reads_ok=True):
    bands = []
    for age in AGES:
        for g, c in COLUMNS:
            bands.append(BandRead(age, g, c, "val", "+", False, [["raw", 5, "+0.5%"], ["stretch", 5, "+0.5%"]]))
            bands.append(BandRead(age, g, c, "ref", "", False, [["raw", 5, "N/A"], ["raw", 4, "N/A"]]))
    return MatrixResult("failed", "img.jpg", "sha", date_reads=date_reads, bands=bands, n_rows=6, n_cols=13)


def test_ok_matrix_requires_image_date_equal_to_article_date():
    assert finalize(_result(["07 March 2023", "07 March 2023"]), "2023-03-07").status == "ok"
    other = finalize(_result(["07 March 2023", "07 March 2023"]), "2023-03-14")
    assert other.status == "ok" and other.image_date == "2023-03-07" and "differs from the issue date" in other.warnings[0]
    wrong = finalize(_result(["07 March 2023"]), "2023-03-14")
    assert wrong.status == "failed" and "could not be read" in wrong.errors[0]
    empty = finalize(_result([]), "2023-03-07")
    assert empty.status == "failed" and "None" in empty.errors[0]
    bad_year = finalize(_result(["06 May 7075", "06 May 7075"]), "2025-05-06")
    assert bad_year.status == "failed"            # '7075' is an OCR error, never accepted as a date


def test_differing_label_is_accepted_only_as_whole_weeks_stale():
    def fin(label, article):
        return finalize(_result([label, label]), article)
    stale = fin("27 May 2025", "2025-06-03")                         # genuine one-week-stale image
    assert stale.status == "ok" and stale.image_date == "2025-05-27" and stale.warnings
    assert fin("20 May 2025", "2025-06-03").status == "ok"            # two weeks
    assert fin("13 May 2025", "2025-06-03").status == "failed"        # three weeks: not accepted
    for label, article in (("07 May 2025", "2025-05-27"),            # day digit 27 -> 7
                           ("08 August 2021", "2023-08-08"),         # year misread
                           ("03 March 2026", "2026-03-31"),
                           ("03 October 2023", "2023-10-31")):      # 28 days: a misread, never a stale image
        res = fin(label, article)
        assert res.status == "failed" and any("date label unreliable" in e for e in res.errors), (label, res.errors)
    assert fin("01 August 2025", "2025-08-12").status == "failed"
    assert fin("04 April 2025", "2025-06-03").status == "failed"       # 60 days: more than 8 weeks


def test_date_label_fields_are_voted_separately():
    # the tiny label loses a different field in each render (real reads of the 2025-06-17 image)
    reads = ["17 June: 7075", "17 Jne: 7075", "17 June 7075", "17 2025", "172025", "17 kv 2025", "17k2025"]
    assert decide_date(reads) == "2025-06-17"
    assert decide_date(["17 June 7075", "17 2025"]) is None            # one vote per field is not agreement
    assert decide_date(["17 June 2025", "17 June 2025", "17 May 2025", "17 May 2025"]) is None


def test_decide_date_prefers_plausible_year_among_renders():
    assert decide_date(["06 May 7075", "06 May 2025", "06 May 2025"]) == "2025-05-06"
    assert decide_date(["nothing"]) is None


def test_vote_needs_agreement():
    assert vote(["+0.5%", "+0.5%", "+0.5%", "+0.6%"]) == ("+0.5%", "")
    assert vote(["+0.5%", "+0.5%", "+0.6%"])[0] is None            # winner must be 2 votes ahead
    assert "+0.6%" not in vote(["+0.5%", "+0.6%"])[1]                 # reasons never carry readings
    assert vote(["+0.5%"])[0] is None
    assert vote(["+0.5%", "+0.6%"])[0] is None
    assert vote([])[0] is None


def test_parse_image_date():
    assert str(parse_image_date("07 March 2023")) == "2023-03-07"
    assert str(parse_image_date("6 Sept 2022")) == "2022-09-06"
    assert parse_image_date("VV Mini Matrix") is None


def test_validate_cells_reports_value_problems_not_benchmark_notes():
    ok_cell = Cell(age=0, group="Tankers", column="VLCC", pct_text="+0.5%", pct=0.5, ref_text="320k")
    bad = Cell(age=5, group="Tankers", column="Suez", problems=["value not read"])
    noted = Cell(age=10, group="Tankers", column="Afra", pct_text="-0.1%", pct=-0.1, notes=["benchmark not read"])
    errs = validate_cells([ok_cell, bad, noted])
    assert len(errs) == 1 and "age 5" in errs[0]


def test_column_layout_constants():
    assert len(COLUMNS) == 13 and len(AGES) == 6
    assert [g for g, _ in COLUMNS].count("Tankers") == 5


def _v2(texts, sign="+"):
    return BandRead(0, "Tankers", "VLCC", "val", sign, False, [["raw", 5, t] for t in texts])


def test_value_policy2_needs_three_of_five_and_no_1_7_twin():
    from scripts.parse_engine_html.matrix import decide_value2
    assert decide_value2(_v2(["+0.5%", "0.5%", "+0.5%", "+0.5%", "+0.8%"]))[0] is None       # a dissent
    assert decide_value2(_v2(["+0.5%", "0.5%", "+0.5%", "x", "y"]))[0] == "+0.5%"
    assert decide_value2(_v2(["+0.5%", "0.5%", "+0.3%", "+0.3%", "+0.8%"]))[0] is None       # 2 votes only
    # 2026-04-07 Fmax: printed +0.1%, most renders read +0.7% -> a single 1-reading anywhere blanks the cell
    seven = ["+0.7%", "0.7%", "+0.7%", "0.7%", "+0.7%"] + ["+0.7%"] * 7 + ["0.1%"]
    top, why = decide_value2(_v2(seven))
    assert top is None and "different value" in why
    assert decide_value2(_v2(["+1.2%"] * 5 + ["+1.2%"] * 8))[0] == "+1.2%"


def _result2(val_texts):
    bands = []
    for i, (age, (g, c)) in enumerate([(a, gc) for a in AGES for gc in COLUMNS]):
        bands.append(BandRead(age, g, c, "val", "+", False, [["raw", 5, t] for t in val_texts(i)]))
        bands.append(BandRead(age, g, c, "ref", "", False, [["raw", 5, "N/A"], ["raw", 4, "N/A"]]))
    return MatrixResult("failed", "img.jpg", "sha", date_reads=["07 March 2026"] * 2, bands=bands, n_rows=6,
                        n_cols=13, val_policy=2)


def test_partial_matrix_keeps_read_cells_and_blanks_the_rest():
    res = finalize(_result2(lambda i: ["+0.4%"] * 5 if i % 10 else ["+0.4%", "+0.9%", "+0.3%", "+0.9%", "+0.4%"]), "2026-03-07")
    assert res.status == "partial"
    assert sum(1 for c in res.cells if not c.pct_text) == 8 and all(c.pct == 0.4 for c in res.cells if c.pct_text)
    worse = finalize(_result2(lambda i: ["+0.4%"] * 5 if i % 3 == 0 else ["+0.4%", "+0.9%", "+0.3%", "+0.9%", "+0.4%"]), "2026-03-07")
    assert worse.status == "failed"                      # under half the values read: the image is not trusted
    old = _result2(lambda i: ["+0.4%"] * 5 if i % 10 else ["+0.4%", "+0.9%", "+0.3%", "+0.9%", "+0.4%"])
    old.val_policy = 1                                     # a result cached by reader 2.0.0 keeps its old verdict
    assert finalize(old, "2026-03-07").status == "failed"


def test_undated_table_filed_only_when_it_differs_from_its_neighbours():
    from scripts.parse_engine_html.matrix import accept_by_neighbours, date_only_failure
    res = finalize(_result2(lambda i: [f"+{i % 9}.{i % 7}%"] * 5), "2026-03-20")      # label 07 March: not 1-2 weeks off
    assert res.status == "failed" and date_only_failure(res)
    mine = {(c.group, c.column, c.age): c.pct for c in res.cells}
    other = {k: v + 0.1 for k, v in mine.items()}
    assert accept_by_neighbours(res, "2026-03-20", {}).status == "failed"            # nothing to compare with
    stale = finalize(_result2(lambda i: [f"+{i % 9}.{i % 7}%"] * 5), "2026-03-20")
    assert accept_by_neighbours(stale, "2026-03-20", {"2026-03-13": dict(mine)}).status == "failed"
    assert "re-published" in stale.errors[-1]
    good = accept_by_neighbours(res, "2026-03-20", {"2026-03-13": other})
    assert good.status == "ok" and good.image_date == "2026-03-20" and "date label not read" in good.warnings[-1]


def test_value_policy2_narrow_two_digit_reading_is_a_dissent():
    from scripts.parse_engine_html.matrix import decide_value2
    # 2026-10-20 Afra age 10: printed +7.1%, most renders '2.1', one '47.1' (sign glyph read as 4)
    reads = ["*2.1%", "21%", "*2.1%", "2.1%", "47.1%", "2.1%", "41%", ".1%", "*2.1%", "2.1%", "*2.1%", "2.1%"]
    assert decide_value2(_v2(reads))[0] is None
    assert decide_value2(_v2(["63,1%"] * 13))[0] is None                       # two digits in a narrow cell


_NACE_MD = """# VesselsValue

| 07 March 2026 | VV Mini Matrix - Weekly Change | VV Mini Matrix - Weekly Change |
| --- | --- | --- |
|  | Tankers | Tankers | Tankers | Tankers | Tankers | Bulkers | Bulkers | Bulkers | Bulkers | Containers | Containers | Containers | Containers |
| Year | VLCC | Suez | Afra | LRI | MR | Cape | Pmax | Supra | Handy | Post Pmax | Pmax | Handy | Fmax |
""" + "".join(
    f"| {a} | " + " | ".join(["+0.4%"] * 12 + ["N/A"]) + " |\n"
    f"| {a} | " + " | ".join(["320k"] * 13) + " |\n" for a in AGES)


def test_second_reader_table_and_date():
    from scripts.parse_engine_html.matrix import nace_date, nace_values
    vals = nace_values(_NACE_MD)
    assert len(vals) == 78 and vals[(0, "Tankers", "LR1")] == "+0.4%" and vals[(25, "Containers", "Fmax")] == "N/A"
    assert nace_date(_NACE_MD) == "2026-03-07"
    # one misspelt header word is tolerated (the layout is fixed); a table that is not the matrix is not used
    assert nace_values(_NACE_MD.replace("| Afra |", "| Afro |")) == vals
    assert nace_values(_NACE_MD.replace("| VLCC | Suez | Afra | LRI |", "| A | B | C | D |")) == {}
    # rows take the ages by position; a garbled age label is ignored, a wrong age refuses the table
    assert nace_values(_NACE_MD.replace("| 0 | +0.4%", "| # | +0.4%")) == vals
    assert nace_values(_NACE_MD.replace("| 5 | +0.4%", "| 10 | +0.4%")) == {}
    assert nace_values(_NACE_MD.replace("+0.4%", "+0,4%")) == vals                # decimal comma
    # an empty trailing column is ignored
    assert nace_values(_NACE_MD.replace(" |\n", " |  |\n")) == vals


def test_value_policy3_second_reader_needs_two_local_renders():
    from scripts.parse_engine_html.matrix import decide_value3
    assert decide_value3(_v2(["+0.4%", "x", "+0.4%", "y", "z"]), "+0.4%")[0] == "+0.4%"
    # the serif '+7.1' every render read as '2.1': the second reader's value is not confirmed -> blank, never 2.1
    assert decide_value3(_v2(["+2.1%"] * 4 + ["+7.1%"]), "+7.1%")[0] is None
    # sign must be the colour's
    assert decide_value3(_v2(["-0.4%"] * 5, "-"), "+0.4%")[0] is None
    # without a second-reader value: policy 2
    assert decide_value3(_v2(["+0.5%"] * 5), None)[0] == "+0.5%"


def test_second_reader_fills_cells_the_renders_left_blank():
    res = _result2(lambda i: ["+0.4%", "+0.9%", "+0.4%", "+0.9%", "x"])     # policy 2: no value has 3 votes
    assert finalize(res, "2026-03-07").status == "failed"
    res.nace_md, res.nace_v = _NACE_MD, 1
    res = finalize(res, "2026-03-07")
    assert res.status == "partial"        # Fmax: the second reader says N/A, the renders do not
    assert all(c.pct == 0.4 for c in res.cells if c.column != "Fmax" or c.group != "Containers")
    assert all(not c.pct_text for c in res.cells if (c.group, c.column) == ("Containers", "Fmax"))


def test_eye_verified_corrections_replace_or_blank_cells():
    from scripts.parse_engine_html.matrix import CORRECTED, apply_corrections
    res = finalize(_result2(lambda i: ["+0.4%"] * 5), "2026-03-07")
    res.image_sha256 = "abc"
    fixes = {"abc": {"note": "test", "cells": {"10/Containers/Post Pmax": "+0.8%", "0/*/*": None}}}
    apply_corrections(res, fixes)
    by = {(c.age, c.group, c.column): c for c in res.cells}
    assert by[(10, "Containers", "Post Pmax")].pct == 0.8
    assert all(not c.pct_text and c.notes[-1].startswith(CORRECTED) for c in res.cells if c.age == 0)
    assert by[(5, "Tankers", "VLCC")].pct == 0.4
    assert not validate_cells(res.cells)            # a corrected blank is not an 'empty value' error
    apply_corrections(res, {})                      # another image: nothing changes
    assert by[(10, "Containers", "Post Pmax")].pct == 0.8
