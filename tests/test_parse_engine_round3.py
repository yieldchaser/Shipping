"""Verifier round 3: series source filter, shared Details cells, multi-amount Price cells, small export fixes."""
from __future__ import annotations

import json
from pathlib import Path

from scripts.parse_engine import export_series as xs
from scripts.parse_engine import geom_table as gt
from scripts.parse_engine.config import load_profile


def _word(text: str, x: float, y: float) -> gt.Word:
    return gt.Word(x0=x, y0=y - 4, x1=x + 30, y1=y + 4, text=text)


def _cell(x: float, lines: list[tuple[float, str]]) -> list[gt.Word]:
    return [_word(t, x, y) for y, t in lines]


def test_series_ignores_other_publishers_files(tmp_path):
    cols = ["Vessel", "DWT", "Year", "Yard", "Details", "SS/DD", "Price", "Buyer"]
    table = {"name": "Bulk Carriers", "columns": cols, "empty": False, "en_bloc_rows": [],
             "rows": [["A", "50,000", "2011", "BOHAI", "MAN", "SS 01/25", "USD 10 M", "GREEKS"]]}
    d = tmp_path / "stage" / "2026"
    d.mkdir(parents=True)
    for stem, date in (("2026-05-15_clarksons-platou-hellas-snp-weekly-bulletin-1_x", "2026-05-15"),
                       ("2026-05-18_ssy-pacific-capesize-index-18-may-2026_x", "2026-05-18")):
        (d / f"{stem}.md").write_text(f"---\nissue_date: '{date}'\nsource_file: corpus/{stem}.pdf\n---\n\nbody\n",
                                      encoding="utf-8")
        (d / f"{stem}.tables.json").write_text(json.dumps({"schema": "parse_engine/v1", "tables": [table]}),
                                               encoding="utf-8")
    markers = tuple(load_profile("clarksons")["promotion"]["name_markers"])
    assert [md.name[:10] for md, _ in xs._iter_issues(tmp_path / "stage", markers)] == ["2026-05-15"]
    res = xs.export(tmp_path / "stage", tmp_path / "out", require_engine_schema=True, markers=markers)
    assert res["issues"] == 1 and len(res["sales"]) == 1


def test_details_cell_with_one_block_per_vessel_is_split():
    # TORM ESTRID / ISMINI: each vessel's comment is centred on its own line, not aligned with the key line
    words = _cell(300, [(384, "MAN B. & W. 6S60MC-C7.1"), (394, "BWTS fitted, CPP"), (414, "MAN B. & W. 6S60MC-C7.1"),
                        (424, "BWTS fitted"), (433, "SCRUBBER fitted, CPP")])
    key_ys = [392.0, 421.0]
    assert gt._split_column(words, key_ys, 6.5) is None
    parts = gt._split_column(words, key_ys, 6.5, centered=9.0)
    assert parts == ["MAN B. & W. 6S60MC-C7.1 BWTS fitted, CPP",
                     "MAN B. & W. 6S60MC-C7.1 BWTS fitted SCRUBBER fitted, CPP"]


def test_identical_per_vessel_details_are_not_concatenated():
    # HONOR / GLORY: the same engine line once per vessel must not end up twice in each row
    words = _cell(300, [(205, "MAN B.&W. 6S70MC-C7.2"), (214, "BWTS fitted"), (234, "MAN B.&W. 6S70MC-C7.2"),
                        (244, "BWTS fitted")])
    assert gt._split_column(words, [211.0, 232.0], 6.5, centered=9.0) == ["MAN B.&W. 6S70MC-C7.2 BWTS fitted"] * 2


def test_single_shared_comment_stays_shared():
    # one two-line comment sitting between two sisters belongs to both, whole
    words = _cell(300, [(400, "MAN-B&W 6S42MC7.2"), (410, "4 x 30 T BWTS fitted")])
    assert gt._split_column(words, [392.0, 421.0], 6.5, centered=9.0) is None


def test_expand_deal_gives_each_vessel_its_own_details_and_amount():
    ncols = 8
    cells = [[] for _ in range(ncols)]
    cells[0] = _cell(10, [(392, "TORM ESTRID"), (421, "TORM ISMINI")])
    cells[1] = _cell(140, [(392, "74,999"), (421, "74,999")])
    cells[3] = _cell(300, [(384, "MAN B. & W."), (394, "BWTS fitted, CPP"), (414, "MAN B. & W."), (424, "BWTS fitted"),
                           (433, "SCRUBBER fitted, CPP")])
    cells[6] = _cell(430, [(405, "USD 19.5 M USD 20.5 M"), (415, "(en bloc)")])
    merged = [gt._join_cell(c) for c in cells]
    out, _ = gt._expand_deal(cells, merged, 1, {6, 7}, r"\d", 0, None, {0, 1}, None, None, None, None,
                             {6}, {3})
    assert [r[0] for r in out] == ["TORM ESTRID", "TORM ISMINI"]
    assert [r[3] for r in out] == ["MAN B. & W. BWTS fitted, CPP", "MAN B. & W. BWTS fitted SCRUBBER fitted, CPP"]
    assert [xs.parse_price(r[6])["price_usd_m"] for r in out] == [19.5, 20.5]


def test_multi_amount_price_split_by_amounts():
    assert gt._split_by_amounts("USD 19.5 M USD 20.5 M (en bloc)", 2) == ["USD 19.5 M", "USD 20.5 M (en bloc)"]
    assert gt._split_by_amounts("USD 26 M EACH (en bloc)", 2) is None      # one amount for two vessels: stays shared


def test_clarksons_profile_enables_the_splits():
    for t in load_profile("clarksons")["geom"]["tables"]:
        if t["name"] in ("Bulk Carriers", "Tankers - Chemicals - LPG/LNGs"):
            assert t["centered_split_columns"] == ["Details"] and t["amount_split_columns"] == ["Price"]


def test_demolition_range_and_greek_homoglyphs():
    assert xs.parse_demo_price("USD 540-550/LDT") == "540-550"
    assert xs.parse_demo_price("530/LDT") == 530.0
    assert xs.latinize("ΑLPHΑ ΜΑRINE") == "ALPHA MARINE"


def test_shared_year_yard_cell_is_copied_to_every_sister_it_spans():
    # SFL SPEY / MEDWAY: the Built cell has no ruling between the two rows, so both get "2011 JIANGSU"
    cells = [[[] for _ in range(3)] for _ in range(3)]
    cells[0][0], cells[1][0], cells[2][0] = _cell(10, [(540, "SPEY")]), _cell(10, [(567, "MEDWAY")]), _cell(10, [(597, "TRENT")])
    cells[1][1] = _cell(100, [(552, "2011 JIANGSU")])
    cells[2][1] = _cell(100, [(612, "2012 JIANGSU")])
    intervals = [(531.0, 557.0), (557.0, 586.0), (586.0, 615.0)]
    bounds = [0.0, 80.0, 200.0, 300.0]
    hsegs = [gt.Segment(557.0, 0, 80), gt.Segment(586.0, 0, 300), gt.Segment(615.0, 0, 300)]   # none across column 1 at 557
    rows, flagged = gt._merged_rows(cells, intervals, hsegs, bounds, 0, 3, "rulings")
    assert [r[1] for r in rows] == ["2011 JIANGSU", "2011 JIANGSU", "2012 JIANGSU"]
    assert flagged == {0, 1}


def test_block_count_mismatch_is_flagged_and_text_kept_whole():
    # 2022-06-10: four vessels but three engine blocks: no guessed split, one shared text per row, flagged
    ncols = 4
    cells = [[] for _ in range(ncols)]
    cells[0] = _cell(10, [(392, "A"), (422, "B"), (451, "C"), (481, "D")])
    cells[1] = _cell(140, [(392, "1,000"), (422, "2,000"), (451, "3,000"), (481, "4,000")])
    cells[3] = _cell(300, [(383, "MAN 6S70"), (392, "3 Pumps"), (401, "BWTS fitted"), (427, "MAN 6S50"), (436, "12 Pumps"),
                           (446, "BWTS fitted"), (476, "MAN 6S50C"), (486, "Ice 1B")])
    merged = [gt._join_cell(c) for c in cells]
    mismatch: list[int] = []
    out, _ = gt._expand_deal(cells, merged, 1, set(), r"\d", 0, None, {0, 1}, None, None, None, None, None, {3}, mismatch)
    assert mismatch == [3]
    assert all(r[3] == merged[3] for r in out) and len(out) == 4
    res = gt.TableResult(name="n", title="", page=1, bbox=(0, 0, 1, 1), columns=[], rows=[], shared_cell_count_mismatch=1)
    assert res.to_json()["shared_cell_count_mismatch"] == 1
    assert gt._block_count(cells[3]) == 3


def test_expand_deal_cell_spanning_some_of_the_vessels_goes_to_each_of_them():
    # DONG-A OKNOS / ASTREA share "2010 HHI" (one cell), EOS has its own "2009 HHI": one ruling for three vessels
    cells = [[] for _ in range(3)]
    cells[0] = _cell(10, [(200, "OKNOS"), (230, "ASTREA"), (260, "EOS")])
    cells[1] = _cell(140, [(200, "179,329"), (230, "179,329"), (260, "179,329")])
    cells[2] = _cell(180, [(215, "2010 HHI"), (260, "2009 HHI")])
    merged = [gt._join_cell(c) for c in cells]
    out, _ = gt._expand_deal(cells, merged, 1, set(), r"\d", 0, None, {0, 1}, None, {2: [245.0]}, None, None, None, None, None)
    assert [r[2] for r in out] == ["2010 HHI", "2010 HHI", "2009 HHI"]

