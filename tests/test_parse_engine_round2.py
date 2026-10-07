"""Verifier round 2: dash placeholders, continuation with letterhead, shared Built cells, DD next to a
bracketed note, series aliases, LDT without a unit, new-only incremental mode, legacy-script guards."""
from __future__ import annotations

import csv
import json
import py_compile
import re
import subprocess
import sys
from pathlib import Path

import pymupdf
import pytest

from scripts.parse_engine import cli
from scripts.parse_engine import export_series as xs
from scripts.parse_engine import geom_table as gt
from scripts.parse_engine import promote
from scripts.parse_engine.config import load_profile

ROOT = Path(__file__).resolve().parents[1]
CLARKSONS = load_profile("clarksons")
COLS = ["Vessel", "DWT", "Year", "Yard", "Details", "SS/DD", "Price", "Buyer"]


# ------------------------------------------------------------------------------------ 1. "--" rows
def test_dash_placeholder_rows_are_an_empty_table():
    assert gt.EMPTY_CELL_RE.match("--") and gt.EMPTY_CELL_RE.match("–") and gt.EMPTY_CELL_RE.match("")
    assert not gt.EMPTY_CELL_RE.match("-A")
    tables = [{"name": "Tankers - Chemicals - LPG/LNGs", "columns": COLS, "empty": False, "en_bloc_rows": [],
               "rows": [["--", "-", "-", "-", "-", "-", "-", "-"]]},
             {"name": "Demolition - Tankers", "columns": ["Vessel", "DWT", "Built", "Details", "Price", "Delivery"],
              "empty": False, "rows": [["--", "-", "-", "-", "-", "-"]]}]
    sales, demo = xs.issue_rows(tables, {"issue_date": "2022-01-28"})
    assert sales == [] and demo == []


def test_dash_only_geometric_table_renders_no_reported_sales():
    doc = pymupdf.open()
    pg = doc.new_page()
    pg.insert_text((40, 60), "Tankers", fontsize=11)
    xs_ = [40, 120, 200, 300, 400, 480]
    heads = ["Vessel", "DWT", "Built", "Details", "Price"]
    for x, h in zip(xs_, heads):
        pg.insert_text((x + 4, 95), h, fontsize=9)
    for x in xs_[:5]:
        pg.insert_text((x + 4, 125), "--", fontsize=9)
    for y in (80, 105, 140):
        pg.draw_line((40, y), (480, y), color=(0.5, 0.5, 0.5), width=0.6)
    for x in xs_:
        pg.draw_line((x, 80), (x, 140), color=(0.5, 0.5, 0.5), width=0.6)
    cfg = [{"name": "T", "anchor": "^Tankers", "headers": heads, "key_column": 1, "row_start_pattern": r"\d"}]
    t = gt.find_tables(doc[0], 1, cfg)[0]
    assert t.empty and t.rows[0][0] == "No reported sales"


# ------------------------------------------------------------------------------------ 2. continuation + letterhead
def test_continuation_skips_letterhead_lines_and_does_not_need_the_table_to_reach_the_footer():
    doc = pymupdf.open()
    p1 = doc.new_page()
    p1.insert_text((40, 100), "Bulker Sales", fontsize=11)
    xs_ = [40, 120, 200, 300, 400, 480, 560]
    heads = ["Vessel", "DWT", "Built", "Details", "Price", "Buyer"]
    for x, h in zip(xs_, heads):
        p1.insert_text((x + 4, 130), h, fontsize=9)
    for y in (115, 150, 200):
        p1.draw_line((40, y), (560, y), color=(0.5, 0.5, 0.5), width=0.6)
    for x in xs_:
        p1.draw_line((x, 115), (x, 200), color=(0.5, 0.5, 0.5), width=0.6)
    for x, tx in zip(xs_, ["ALPHA", "50,000", "2011 BOHAI", "MAN", "USD 10 M", "GREEK"]):
        p1.insert_text((x + 4, 175), tx, fontsize=8)
    p2 = doc.new_page()
    p2.insert_text((40, 130), "Clarkson Hellas Ltd.", fontsize=11)          # letterhead repeated on every page
    for y in (150, 200):
        p2.draw_line((40, y), (560, y), color=(0.5, 0.5, 0.5), width=0.6)
    for x in xs_:
        p2.draw_line((x, 150), (x, 200), color=(0.5, 0.5, 0.5), width=0.6)
    for x, tx in zip(xs_, ["BETA", "30,000", "2012 IMABARI", "MAN", "USD 5 M", "TURKISH"]):
        p2.insert_text((x + 4, 180), tx, fontsize=8)
    cfg = [{"name": "Bulk", "anchor": "^Bulker Sales", "headers": heads, "key_column": 1,
            "row_start_pattern": r"\d", "headerless_ok": True}]
    ignore = CLARKSONS["geom"]["continuation_ignore"]
    memory: dict = {}
    t1 = gt.find_tables(doc[0], 1, cfg, None, 45, memory, ignore)
    t2 = gt.find_tables(doc[1], 2, cfg, None, 45, memory, ignore)
    assert [r[0] for r in t1[0].rows] == ["ALPHA", "BETA"] and t2[0].hidden


def test_continuation_is_not_attempted_when_text_follows_the_table_on_the_page():
    doc = pymupdf.open()
    p1 = doc.new_page()
    p1.insert_text((40, 100), "Bulker Sales", fontsize=11)
    xs_ = [40, 120, 200, 300, 400, 480, 560]
    heads = ["Vessel", "DWT", "Built", "Details", "Price", "Buyer"]
    for x, h in zip(xs_, heads):
        p1.insert_text((x + 4, 130), h, fontsize=9)
    for x, tx in zip(xs_, ["ALPHA", "50,000", "2011 BOHAI", "MAN", "USD 10 M", "GREEK"]):
        p1.insert_text((x + 4, 175), tx, fontsize=8)
    for y in (115, 150, 200):
        p1.draw_line((40, y), (560, y), color=(0.5, 0.5, 0.5), width=0.6)
    for x in xs_:
        p1.draw_line((x, 115), (x, 200), color=(0.5, 0.5, 0.5), width=0.6)
    p1.insert_text((40, 400), "Commentary below the table.", fontsize=10)
    p2 = doc.new_page()
    for x, tx in zip(xs_, ["BETA", "30,000", "2012 IMABARI", "MAN", "USD 5 M", "TURKISH"]):
        p2.insert_text((x + 4, 80), tx, fontsize=8)
    cfg = [{"name": "Bulk", "anchor": "^Bulker Sales", "headers": heads, "key_column": 1,
            "row_start_pattern": r"\d", "headerless_ok": True}]
    memory: dict = {}
    t1 = gt.find_tables(doc[0], 1, cfg, None, 45, memory)
    assert gt.find_tables(doc[1], 2, cfg, None, 45, memory) == [] and len(t1[0].rows) == 1


# ------------------------------------------------------------------------------------ 3. shared Built cell
def test_shared_built_cell_is_copied_not_split_between_sisters():
    doc = pymupdf.open()
    pg = doc.new_page()
    pg.insert_text((28, 122), "Bulk Carriers", fontsize=11)
    xs_ = [29, 113, 156, 241, 354, 404, 489, 567]
    heads = ["Vessel", "DWT", "Built", "Details", "SS/DD", "Price", "Buyer"]
    for x, h in zip(xs_, heads):
        pg.insert_text((x + 6, 150), h, fontsize=8)

    def t(x, y, text):
        pg.insert_text((x, y + 7), text, fontsize=8)

    # AQUAHAHA / AQUATONKA: Built is ONE cell "2012 HHIC-PHILIPPINES (SUBIC SHIPYARD)" (3 evenly spaced lines)
    t(40, 267.1, "AQUAHAHA"); t(121, 267.1, "179,023")
    t(40, 287.9, "AQUATONKA"); t(121, 287.9, "179,004")
    t(180, 262, "2012"); t(180, 272, "HHIC"); t(180, 282, "(SUBIC SY)")
    t(359, 260.3, "SS 02/27"); t(357, 270.1, "DD 05/25"); t(359, 289.8, "SS 03/27"); t(357, 299.5, "DD 05/25")
    t(418, 275.0, "RGN USD 28 M"); t(520, 280.0, "DANISH")
    for y in (140, 230, 260, 310):
        pg.draw_line((29, y), (567, y), color=(0.5, 0.5, 0.5), width=0.5)
    for x in xs_:
        pg.draw_line((x, 140), (x, 310), color=(0.5, 0.5, 0.5), width=0.5)
    cfg = [{"name": "Bulk Carriers", "anchor": "^Bulk Carriers", "headers": heads, "key_column": 1,
            "row_start_pattern": r"\d", "span_columns": ["Price", "Buyer"], "per_vessel_columns": ["Vessel", "DWT"],
            "vessel_count_column": "SS/DD", "vessel_count_pattern": r"\bSS\b",
            "split_part_patterns": CLARKSONS["geom"]["tables"][0]["split_part_patterns"]}]
    rows = [r for tb in gt.find_tables(doc[0], 1, cfg) for r in tb.rows if r[0].startswith("AQUA")]
    assert [r[2] for r in rows] == ["2012 HHIC (SUBIC SY)"] * 2
    assert [r[4] for r in rows] == ["SS 02/27 DD 05/25", "SS 03/27 DD 05/25"]


# ------------------------------------------------------------------------------------ 5. DD next to a bracketed note
def test_dd_date_stays_in_ss_dd_when_a_note_follows_it_in_the_price_column():
    doc = pymupdf.open()
    pg = doc.new_page()
    pg.insert_text((28, 122), "Bulk Carriers", fontsize=11)
    xs_ = [14, 128, 165, 284, 385, 420, 498, 578]
    heads = ["Vessel", "DWT", "Built", "Details", "SS/DD", "Price", "Buyer"]
    for x, h in zip(xs_, heads):
        pg.insert_text((x + 8, 150), h, fontsize=8)
    for y in (140, 230, 280):
        pg.draw_line((14, y), (578, y), color=(0.5, 0.5, 0.5), width=0.5)
    for x in xs_:
        pg.draw_line((x, 140), (x, 280), color=(0.5, 0.5, 0.5), width=0.5)
    def t(x, y, text):
        pg.insert_text((x, y + 7), text, fontsize=8)
    t(47, 253, "KING COTTON"); t(139, 253, "33,622"); t(185, 253, "2011 SHIN KURUSHIMA")
    t(293, 238, "MITSUBISHI 6UEC45LSE"); t(323, 247, "4 x 30 T")
    t(390, 238, "SS 10/21"); t(390, 247, "DD 08/21")
    t(430, 239, "RGN/XS USD 14 M"); t(426, 248, "(BWTS ordered)"); t(533, 253, "U/D")
    cfg = [{"name": "Bulk", "anchor": "^Bulk Carriers", "headers": heads, "key_column": 1, "row_start_pattern": r"\d",
            "span_columns": ["Price", "Buyer"]}]
    row = gt.find_tables(doc[0], 1, cfg)[0].rows[0]
    assert row[4] == "SS 10/21 DD 08/21" and row[5] == "RGN/XS USD 14 M (BWTS ordered)"


# ------------------------------------------------------------------------------------ 6. LDT without unit
def test_parse_ldt_bare_number_only_in_demolition_context():
    assert xs.parse_ldt("9,200") == ""                        # a sale's Details cell: not LDT
    assert xs.parse_ldt("9,200", bare_ok=True) == 9200
    assert xs.parse_ldt("9,543 LDT", bare_ok=True) == 9543 and xs.parse_ldt("8.895", bare_ok=True) == 8895
    demo = {"name": "Demolition - Bulk Carriers GCs", "columns": ["Vessel", "DWT", "Built", "Details", "Price", "Delivery"],
            "empty": False, "rows": [["BROTHER GLORY", "70,529", "1998", "9,200", "530/LDT", "BANGLADESH"]]}
    _, d = xs.issue_rows([demo], {"issue_date": "2024-02-09"})
    assert d[0]["ldt"] == 9200


# ------------------------------------------------------------------------------------ 7. series aliases / week39 guard
def test_series_csv_keeps_the_legacy_columns(tmp_path):
    stage = tmp_path / "stage" / "2022"
    stage.mkdir(parents=True)
    stem = "2022-08-19_clarksons_x_aaaaaaaaaaaa"
    t = {"name": "Bulk Carriers", "page": 1, "columns": COLS, "empty": False, "en_bloc_rows": [],
         "rows": [["A", "50,000", "2011", "BOHAI", "MAN", "SS 01/25 DD 02/25", "USD 10 M", "GREEKS"]]}
    (stage / f"{stem}.md").write_text("---\nissue_date: '2022-08-19'\nsource_file: corpus/x.pdf\nsource_sha256: abc\n---\n\nbody\n",
                                      encoding="utf-8")
    (stage / f"{stem}.tables.json").write_text(json.dumps(xs.sidecar_payload([t], "2022-08-19", "corpus/x.pdf", "abc")),
                                               encoding="utf-8")
    xs.export(tmp_path / "stage", tmp_path / "out", require_engine_schema=True)
    with open(tmp_path / "out" / "clarksons_sales_series.csv", encoding="utf-8") as fh:
        row = next(csv.DictReader(fh))
    assert row["issue"] == "2022-08-19" == row["issue_date"] and row["NAME"] == "A" and row["DWT"] == "50,000"
    assert row["PRICE"] == "USD 10 M" and row["BUYERS"] == "GREEKS" and row["SS_DD"] == "SS 01/25 DD 02/25"
    assert json.loads(row["extra_json"])["stem"] == "x"


def test_series_refuses_legacy_sidecars_when_the_engine_schema_is_required(tmp_path):
    stage = tmp_path / "md" / "2022"
    stage.mkdir(parents=True)
    (stage / "x.md").write_text("---\nissue_date: '2022-08-19'\n---\n\nbody\n", encoding="utf-8")
    (stage / "x.tables.json").write_text(json.dumps({"issue_date": "2022-08-19", "sales": []}), encoding="utf-8")
    with pytest.raises(SystemExit):
        xs.export(tmp_path / "md", tmp_path / "out", require_engine_schema=True)


def test_week39_supplement_script_refuses_the_new_series_schema():
    text = (ROOT / "scripts" / "extract" / "publishers" / "extract_week39_supplements.py").read_text(encoding="utf-8")
    assert "source_sha256" in text and "refusing to overwrite" in text
    py_compile.compile(str(ROOT / "scripts" / "extract" / "publishers" / "extract_week39_supplements.py"), doraise=True)


def test_hellas_world_class_series_writes_are_guarded():
    text = (ROOT / "scripts" / "extract" / "publishers" / "run_clarksons_hellas_world_class.py").read_text(encoding="utf-8")
    for var in ("p_sales", "p_comm", "p_demo", "p_macro"):
        assert re.search(rf"_refuse_legacy_clarksons_write\({var}\)\s+with open\({var}", text)


# ------------------------------------------------------------------------------------ 8. new-only
def _staged(staging: Path, year: str, stem: str, issue_date: str) -> None:
    d = staging / "clarksons" / year
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{stem}.md").write_text(f"---\nissue_date: '{issue_date}'\nsource_file: corpus/{stem}.pdf\n---\n\nbody\n", encoding="utf-8")
    (d / f"{stem}.tables.json").write_text("{}", encoding="utf-8")
    (d / f"{stem}.validation.json").write_text(json.dumps({"flags": []}), encoding="utf-8")


def test_new_only_promotes_only_missing_issues_and_never_removes_or_overwrites(tmp_path):
    staging, dest = tmp_path / "stage", tmp_path / "data" / "clarksons"
    old_stem, new_stem = "2022-08-19_clarksons_a_aaaaaaaaaaaa", "2022-08-26_clarksons_b_bbbbbbbbbbbb"
    _staged(staging, "2022", old_stem, "2022-08-19")
    _staged(staging, "2022", new_stem, "2022-08-26")
    existing = dest / "2022" / (old_stem + ".md")
    existing.parent.mkdir(parents=True)
    existing.write_text("---\nissue_date: '2022-08-19'\n---\n\nOLD\n", encoding="utf-8")
    plan = promote.build_plan("clarksons", staging, dest, [dest], set(), date_patterns=CLARKSONS["date_patterns"],
                              repo_root=tmp_path, new_only=True)
    actions = {Path(r["new_path"]).stem: r["action"] for r in plan.rows}
    assert actions == {old_stem: "skip_existing", new_stem: "promote"}
    assert plan.remove == [] and plan.overwrite == []
    promote.apply_plan(plan, dest, repo_root=tmp_path, allowed_dirs=[dest])
    assert "OLD" in existing.read_text(encoding="utf-8") and (dest / "2022" / (new_stem + ".md")).exists()


def test_new_only_matches_an_existing_issue_by_date_or_pdf_hash(tmp_path):
    dest = tmp_path / "data" / "clarksons"
    (dest / "2023").mkdir(parents=True)
    (dest / "2023" / "2023-07-21_clarksons-x_cebb0332bb75.md").write_text("---\nissue_date: '2023-07-21'\n---\n\nx\n", encoding="utf-8")
    index = promote.existing_index([dest], CLARKSONS["date_patterns"], ("clarkson", "weekly-sales"))
    assert promote.is_existing("2023-07-21_other_zzzzzzzzzzzz", "2023-07-21", index)           # same issue date
    assert promote.is_existing("2023-07-24_clarksons-dup_cebb0332bb75", "2023-07-24", index)    # same PDF hash
    assert not promote.is_existing("2023-07-28_clarksons-y_4ebb2ad1d8f6", "2023-07-28", index)


def test_workflows_run_the_new_only_clarksons_ingest():
    for wf in ("report_ingest.yml", "broker_reports_weekly.yml"):
        text = (ROOT / ".github" / "workflows" / wf).read_text(encoding="utf-8")
        assert "scripts.parse_engine run --source clarksons --new-only" in text
        assert "scripts.parse_engine promote --source clarksons --new-only --apply" in text
        assert "run_clarksons.py" not in text


# ------------------------------------------------------------------------------------ 2b. fragment gate
def test_table_fragment_patterns_catch_leaked_row_text():
    pats = [re.compile(p) for p in CLARKSONS["table_fragment_patterns"]]
    leaked = ["B. & W. 6S50MC-C8.2 **SKY KNIGHT** 58,078 2012 SK ONISHI", "SS 04/30 USD 21.5 M U/D DD 02/28",
              "C:4X30.5T", "**LUZON** 55,657 2010 MITSUI"]
    clean = ["In the Supramax sector, the **SKY KNIGHT** (ABT 58K DWT, 2012, ONISHI) after inviting offers.",
             "Tanker rates remain at or near record highs as hopes of a reopening faded."]
    assert all(any(p.search(x) for p in pats) for x in leaked[:3])
    assert not any(p.search(x) for x in clean for p in pats)
