"""Grid reconstruction + cell normalisation for the VV Mini Matrix image (synthetic boxes, no OCR engine)."""
from __future__ import annotations

import pytest

from scripts.parse_engine_html.matrix import (AGES, COLUMNS, Box, Cell, GridError, MatrixResult, decode_refs,
                                              normalise_pct, normalise_ref, parse_image_date, reconstruct_grid,
                                              ref_value, validate_cells, vote)

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


def test_leading_digit_is_a_misread_sign_unless_ink_is_wide():
    val, note = normalise_pct("10.4%", "+", wide=False)
    assert (val, note) == ("+0.4%", "sign_glyph_read_as_digit")
    assert normalise_pct("11.4%", "+", wide=True)[0] == "+11.4%"


@pytest.mark.parametrize("text", ["", "abc", "+.0%", "1.45%", "0.5%6"])
def test_normalise_pct_rejects_garbage(text):
    assert normalise_pct(text, "+")[0] is None


def test_normalise_ref_and_value():
    assert normalise_ref("320k") == "320k" and normalise_ref("320K") == "320k"
    assert normalise_ref("7000") == "7000" and normalise_ref("N/A") == "N/A"
    assert normalise_ref("J250") is None and normalise_ref("/000") is None
    assert ref_value("320k") == 320000 and ref_value("7000") == 7000 and ref_value("N/A") is None


def test_vote_needs_agreement():
    assert vote(["+0.5%", "+0.5%", "+0.6%"]) == ("+0.5%", "")
    assert vote(["+0.5%"])[0] is None
    assert vote(["+0.5%", "+0.6%"])[0] is None
    assert vote([])[0] is None


def test_parse_image_date():
    assert str(parse_image_date("07 March 2023")) == "2023-03-07"
    assert str(parse_image_date("6 Sept 2022")) == "2022-09-06"
    assert parse_image_date("VV Mini Matrix") is None


def _cell(col, ref, reads):
    c = Cell(age=0, group="Tankers", column=col, pct_text="+0.5%", pct=0.5, ref_text=ref, ref_reads=reads)
    return c


def test_decode_refs_resolves_only_against_confirmed_lexicon():
    good = [MatrixResult("ok", "i", "s", cells=[_cell("VLCC", "320k", ["320k", "320k"]) for _ in range(8)])]
    odd = MatrixResult("ok", "j", "t", cells=[
        _cell("VLCC", "", ["/20k", "320k"]),          # one lexicon candidate -> resolved
        _cell("VLCC", "260k", ["260k", "260k"]),      # rare, no lexicon candidate -> dropped
        _cell("VLCC", "", ["/20k"]),                  # nothing -> stays empty
    ])
    stats = decode_refs(good + [odd])
    assert [c.ref_text for c in odd.cells] == ["320k", "", ""]
    assert stats["lexicon_resolved"] == 1 and stats["rare_dropped"] == 1 and stats["unresolved"] == 1


def test_validate_cells_reports_value_problems_not_benchmark_notes():
    ok_cell = Cell(age=0, group="Tankers", column="VLCC", pct_text="+0.5%", pct=0.5, ref_text="320k")
    bad = Cell(age=5, group="Tankers", column="Suez", problems=["value not read"])
    noted = Cell(age=10, group="Tankers", column="Afra", pct_text="-0.1%", pct=-0.1, notes=["benchmark not read"])
    errs = validate_cells([ok_cell, bad, noted])
    assert len(errs) == 1 and "age 5" in errs[0]


def test_column_layout_constants():
    assert len(COLUMNS) == 13 and len(AGES) == 6
    assert [g for g, _ in COLUMNS].count("Tankers") == 5
