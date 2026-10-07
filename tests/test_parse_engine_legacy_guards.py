"""Legacy Clarksons extractors must not run, the orchestrators must not route Clarksons to them, and the
Baltic box / heading hygiene / per-cell merged-row fixes hold."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pymupdf

from scripts.parse_engine import geom_table as gt
from scripts.parse_engine import prose

ROOT = Path(__file__).resolve().parents[1]


def _run(script: str) -> subprocess.CompletedProcess:
    import os
    env = {k: v for k, v in os.environ.items() if k != "ALLOW_LEGACY_CLARKSONS_EXTRACT"}
    return subprocess.run([sys.executable, str(ROOT / script)], capture_output=True, text=True, env=env, timeout=120)


def test_legacy_clarksons_extractors_refuse_to_run():
    for script in ("scripts/extract/publishers/run_clarksons.py",
                   "scripts/extract/publishers/run_clarksons_hellas_world_class.py"):
        res = _run(script)
        assert res.returncode != 0 and "scripts.parse_engine" in (res.stderr + res.stdout)


def test_orchestrate_pipeline_no_longer_runs_run_clarksons():
    lines = (ROOT / "scripts" / "orchestrate_pipeline.py").read_text(encoding="utf-8").splitlines()
    assert not [ln for ln in lines if "run_clarksons" in ln and not ln.strip().startswith("#")]


def test_incremental_ingest_skips_clarksons():
    text = (ROOT / "scripts" / "extract" / "orchestrate_incremental_ingest.py").read_text(encoding="utf-8")
    body = text.split("def process_single_pdf(")[1]
    guard = body.index('if pub == "clarksons":')
    assert guard < body.index("# 1. Specialized Publisher Delegation")
    assert '"skipped": True' in body[guard: guard + 600]


# ------------------------------------------------------------------------------------ B2: Baltic box
def test_drop_region_anchors_match_case_insensitively():
    doc = pymupdf.open()
    pg = doc.new_page()
    pg.insert_text((40, 80), "Commentary stays.", fontsize=10)
    pg.insert_text((40, 500), "BALTIC INDEX", fontsize=10)          # 2021 layout is upper case
    rule = {"anchor_any": ["Baltic Index", "Exchange Rate", "Bunker Prices"], "line_start": True,
            "max_line_chars": 40, "until": "page_end"}
    boxes = prose.drop_region_boxes(pg, [rule])
    assert len(boxes) == 1 and 480 < boxes[0][1] < 500


# ------------------------------------------------------------------------------------ heading hygiene
def test_consecutive_headings_nest_instead_of_dangling():
    from scripts.parse_engine.normalize import nest_headings_md
    md = ("# Recycling\n\n## Hot!\n\ntext\n\n# Demolition\n\n# Bulk Carriers\n\n| a |\n|---|\n| 1 |\n\n"
          "# Tankers\n\n| a |\n|---|\n| 1 |\n\n# Desk Talk\n\ntext\n")
    out = nest_headings_md(md)
    assert "## Hot!" in out                                    # a heading with text below is untouched
    assert "\n\n## Bulk Carriers\n\n" in out                  # pushed below its section heading
    assert "\n\n## Tankers\n\n" in out                       # sibling table title keeps the same level
    assert "\n\n# Desk Talk\n\n" in out                      # a new section is not touched


def test_table_titles_and_prose_headings_of_one_size_share_a_level():
    from scripts.parse_engine import prose as pr

    class T:                                   # minimal stand-in for a table with a printed title size
        def __init__(self, size):
            self.title_size, self.level = size, None
    para = pr.Para(lines=[pr.Line("Desk Talk", "Desk Talk", (0, 0, 1, 1), 16.0, True, True, False)], page=1, heading=1)
    sub = pr.Para(lines=[pr.Line("Dry Cargo", "Dry Cargo", (0, 0, 1, 1), 12.0, True, True, False)], page=1, heading=1)
    t1, t2 = T(12.0), T(12.0)
    pr.assign_heading_levels([para, sub], 10.0, [t1, t2])
    assert (para.heading, sub.heading, t1.level, t2.level) == (1, 2, 2, 2)


# ------------------------------------------------------------------------------------ per-cell merged rows
def test_cells_with_their_own_rulings_are_not_replicated_across_vessels(tmp_path):
    doc = pymupdf.open()
    pg = doc.new_page()
    pg.insert_text((40, 60), "Bulk Carriers", fontsize=11)
    xs = [40, 140, 200, 300, 400, 480]
    heads = ["Vessel", "DWT", "Built", "Details", "Price"]
    for x, h in zip(xs, heads):
        pg.insert_text((x + 4, 95), h, fontsize=9)
    # one ruled row (y 105-175) holding two vessels; the Vessel/Built/Details cells are split at y=140,
    # the DWT cell is merged (no rule), the Price cell is merged
    pg.insert_text((xs[0] + 4, 122), "ALPHA", fontsize=9)
    pg.insert_text((xs[0] + 4, 158), "BETA", fontsize=9)
    pg.insert_text((xs[1] + 4, 142), "57,937", fontsize=9)
    pg.insert_text((xs[2] + 4, 122), "2011", fontsize=9)
    pg.insert_text((xs[2] + 4, 158), "2012", fontsize=9)
    pg.insert_text((xs[3] + 4, 112), "MAN 6S50", fontsize=9)
    pg.insert_text((xs[3] + 4, 124), "BWTS fitted", fontsize=9)
    pg.insert_text((xs[3] + 4, 152), "MAN 6S50", fontsize=9)
    pg.insert_text((xs[4] + 4, 142), "USD 60 M en bloc", fontsize=9)
    for y in (80, 105, 175):
        pg.draw_line((40, y), (480, y), color=(0.5, 0.5, 0.5), width=0.6)
    for x in (40, 200):                                     # y=140 rule only over Vessel/Built/Details columns
        pass
    pg.draw_line((40, 140), (140, 140), color=(0.5, 0.5, 0.5), width=0.6)
    pg.draw_line((200, 140), (400, 140), color=(0.5, 0.5, 0.5), width=0.6)
    for x in xs:
        pg.draw_line((x, 80), (x, 175), color=(0.5, 0.5, 0.5), width=0.6)
    cfg = [{"name": "Bulk", "anchor": "^Bulk Carriers", "headers": heads, "key_column": 1,
            "row_start_pattern": "\\d", "span_columns": ["Price"], "per_vessel_columns": ["Vessel", "DWT"]}]
    t = gt.find_tables(doc[0], 1, cfg)[0]
    assert [r[0] for r in t.rows] == ["ALPHA", "BETA"]
    assert [r[2] for r in t.rows] == ["2011", "2012"]
    assert [r[3] for r in t.rows] == ["MAN 6S50 BWTS fitted", "MAN 6S50"]       # each vessel keeps its own lines
    assert [r[1] for r in t.rows] == ["57,937", "57,937"]                         # genuinely merged DWT is shared
    assert [r[4] for r in t.rows] == ["USD 60 M en bloc"] * 2


def test_bulletin_103_crested_eagle_merged_details_and_per_vessel_ss_dd(tmp_path):
    """Regression from 2024-01-12 bulletin-103: Details/Price/Buyer are one merged cell shared by both
    sister vessels, SS/DD has its own two-line block per vessel (geometry copied from the PDF)."""
    doc = pymupdf.open()
    pg = doc.new_page()
    pg.insert_text((28, 122), "Bulk Carriers", fontsize=11)
    xs = [29, 113, 156, 241, 354, 404, 489, 567]
    heads = ["Vessel", "DWT", "Built", "Details", "SS/DD", "Price", "Buyer"]
    for x, h in zip(xs, heads):
        pg.insert_text((x + 6, 150), h, fontsize=8)

    def t(x, y, text):
        pg.insert_text((x, y + 7), text, fontsize=8)      # y is the top of the printed line, as in the PDF

    t(40, 267.1, "CRESTED EAGLE"); t(121, 267.1, "55,989"); t(182, 267.1, "2008 IHI")
    t(40, 287.9, "STELLAR EAGLE"); t(121, 287.9, "55,989"); t(183, 287.9, "2008 IHI")
    t(247, 265.2, "WARTSILA 2-STROKE 6RT-"); t(285, 275.0, "FLEX"); t(272, 284.9, "BWTS fitted"); t(262, 294.7, "SCRUBBER fitted")
    t(359, 260.3, "SS 03/24"); t(357, 270.1, "DD 03/24"); t(359, 289.8, "SS 03/24"); t(357, 299.5, "DD 03/24")
    t(418, 275.0, "RGN USD 14 M"); t(434, 284.9, "EACH"); t(520, 280.0, "U/D")
    for y in (230, 260, 310):
        pg.draw_line((29, y), (567, y), color=(0.5, 0.5, 0.5), width=0.5)
    for x in xs:
        pg.draw_line((x, 230), (x, 310), color=(0.5, 0.5, 0.5), width=0.5)
    # a header row sits above the first rule
    cfg = [{"name": "Bulk Carriers", "anchor": "^Bulk Carriers", "headers": heads, "key_column": 1,
            "row_start_pattern": r"\d", "span_columns": ["Price", "Buyer"], "per_vessel_columns": ["Vessel", "DWT"],
            "vessel_count_column": "SS/DD", "vessel_count_pattern": r"\bSS\b"}]
    tables = gt.find_tables(doc[0], 1, cfg)
    rows = [r for tb in tables for r in tb.rows if r[0] in ("CRESTED EAGLE", "STELLAR EAGLE")]
    assert [r[0] for r in rows] == ["CRESTED EAGLE", "STELLAR EAGLE"]
    for r in rows:
        assert r[3] == "WARTSILA 2-STROKE 6RT-FLEX BWTS fitted SCRUBBER fitted"     # merged cell: full text to each
        assert r[4] == "SS 03/24 DD 03/24"                                           # per-vessel block, not doubled
        assert r[5].startswith("RGN USD 14 M EACH") and r[6] == "U/D"


def _continued_table_pdf() -> pymupdf.Document:
    doc = pymupdf.open()
    p1 = doc.new_page()
    p1.insert_text((28, 600), "Tankers", fontsize=11)
    xs = [29, 120, 200, 300, 400, 480, 567]
    heads = ["Vessel", "DWT", "Built", "Details", "Price", "Buyer"]
    for x, h in zip(xs, heads):
        p1.insert_text((x + 6, 630), h, fontsize=8)
    rules1 = (615, 650, 720, 790)
    for y in rules1:
        p1.draw_line((29, y), (567, y), color=(0.5, 0.5, 0.5), width=0.5)
    for x in xs:
        p1.draw_line((x, 615), (x, 790), color=(0.5, 0.5, 0.5), width=0.5)
    for y, row in ((675, ("ALPHA", "50,000", "2011 BOHAI", "MAN", "USD 10 M", "GREEK")),
                   (750, ("BETA", "30,000", "2012 IMABARI", "MAN", "USD 5 M", "TURKISH"))):
        for x, tx in zip(xs, row):
            p1.insert_text((x + 4, y), tx, fontsize=8)
    p2 = doc.new_page()                              # continuation: no title, no header row
    for y in (50, 100, 150):
        p2.draw_line((29, y), (567, y), color=(0.5, 0.5, 0.5), width=0.5)
    for x in xs:
        p2.draw_line((x, 50), (x, 150), color=(0.5, 0.5, 0.5), width=0.5)
    for y, row in ((80, ("GAMMA", "20,000", "2018 FUKUOKA", "MAN", "USD 35 M each", "GREEK")),
                   (130, ("DELTA", "20,001", "2019 FUKUOKA", "MAN", "USD 35 M each", "GREEK"))):
        for x, tx in zip(xs, row):
            p2.insert_text((x + 4, y), tx, fontsize=8)
    p2.insert_text((28, 200), "New Building", fontsize=12)
    p2.insert_text((28, 230), "In tankers this week a vessel was ordered.", fontsize=9)
    return doc


CONT_CFG = [{"name": "Tankers", "anchor": "^Tankers", "headers": ["Vessel", "DWT", "Built", "Details", "Price", "Buyer"],
             "key_column": 1, "row_start_pattern": r"\d", "headerless_ok": True}]
CONT_STOPS = ["^New Building"]


def test_table_continued_on_the_next_page_without_a_header_is_one_table():
    doc = _continued_table_pdf()
    memory: dict = {}
    t1 = gt.find_tables(doc[0], 1, CONT_CFG, CONT_STOPS, 45, memory)
    t2 = gt.find_tables(doc[1], 2, CONT_CFG, CONT_STOPS, 45, memory)
    assert [t.name for t in t1] == ["Tankers"]
    assert [r[0] for r in t1[0].rows] == ["ALPHA", "BETA", "GAMMA", "DELTA"]      # rows of page 2 appended
    assert t1[0].extra_regions and t1[0].extra_regions[0]["page"] == 2
    assert len(t2) == 1 and t2[0].hidden                                           # stub: excluded from prose only


def test_no_continuation_when_the_next_page_starts_with_prose():
    doc = _continued_table_pdf()
    prose_doc = pymupdf.open()
    prose_doc.insert_pdf(doc, from_page=0, to_page=0)
    prose_doc.new_page().insert_text((28, 80), "In tankers this week the market was calm.", fontsize=10)
    memory: dict = {}
    t1 = gt.find_tables(prose_doc[0], 1, CONT_CFG, CONT_STOPS, 45, memory)
    t2 = gt.find_tables(prose_doc[1], 2, CONT_CFG, CONT_STOPS, 45, memory)
    assert [r[0] for r in t1[0].rows] == ["ALPHA", "BETA"] and t2 == []      # prose is never read as table rows
