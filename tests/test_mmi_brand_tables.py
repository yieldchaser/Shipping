"""MMi brand spot price tables read from the PDF text layer (mmi_text_tables.read_brands) and the
MD patch that fills the template's placeholder / "-" sides (iron_ore_text_tables_patch.patch_brands).

On a Chinese holiday a HOLIDAY box is drawn over the port stock side; the numbers under it are in the
text layer but not on the page, so they must stay "-". The template dropped the side the page does show.
"""

import sys
import unittest
from pathlib import Path

import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.extract.publishers.mmi_text_tables import read_brands
from scripts.md_cleanup.iron_ore_text_tables_patch import (B58_HEADING, B62_HEADING, BENCH_HEADING, FREIGHT_HEADING,
                                                         patch_brands, patch_freight)

ROWS62 = [("Roy Hill", "811", "0", "-54", "118.45", "0.00", "-3.75"),
          ("Carajas Fines", "1028", "0", "163", "152.50", "0.00", "30.30")]
ROWS58 = [("SSF", "610", "0", "-1"), ("Yandi", "607", "0", "-4")]


def make_doc(holiday):
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    put = lambda x, y, t: page.insert_text((x, y), t, fontsize=7)
    put(145, 262, "Price"); put(197, 262, "Change"); put(243, 262, "Diff to IOPI62")
    put(425, 262, "Price"); put(478, 262, "Change"); put(524, 262, "Diff to IOSI62")
    y = 273
    for b, p, c, d, sp, sc, sd in ROWS62:
        put(18, y, b); put(147, y, p); put(208, y, c); put(261, y, d)
        put(298, y, b); put(421, y, sp); put(483, y, sc); put(538, y, sd)
        y += 11
    put(145, 300, "Price"); put(198, 300, "Change"); put(244, 300, "Diff to IOPI58")
    y = 311
    for b, p, c, d in ROWS58:
        put(18, y, b); put(147, y, p); put(209, y, c); put(265, y, d)
        y += 11
    put(62, 340, "Port Stock Index Product Differentials (RMB/wet tonne)")
    put(18, 352, "Bayuquan"); put(147, 352, "-100.00"); put(209, 352, "0.00"); put(265, 352, "0.00")
    if holiday:
        for top, bottom in ((265, 292), (303, 330)):
            page.draw_rect(pymupdf.Rect(130, top, 290, bottom), color=(0, 0, 0), fill=(1, 1, 1))
            put(195, (top + bottom) / 2, "HOLIDAY")
    return doc


def template_md(t62, t58):
    return f"x\n\n{B62_HEADING}\n{t62}\n\n{B58_HEADING}\n{t58}\n\n## Next\n"


class TestReadBrands(unittest.TestCase):
    def test_plain_issue(self):
        got = read_brands(make_doc(False))
        self.assertEqual(got["62"][0], (("Roy Hill", ["811", "0", "-54"]), ("Roy Hill", ["118.45", "0.00", "-3.75"])))
        self.assertEqual([r[0] for r in got["58"]], ["SSF", "Yandi"])   # stops before the differentials

    def test_holiday_box_hides_port_side(self):
        got = read_brands(make_doc(True))
        self.assertEqual([p for p, _ in got["62"]], [None, None])
        self.assertEqual(got["62"][1][1], ("Carajas Fines", ["152.50", "0.00", "30.30"]))
        self.assertEqual(got["58"], [])


class TestPatchBrands(unittest.TestCase):
    def test_holiday_placeholder_gets_shown_side_only(self):
        md = template_md("_No 62% Fe brand assessments reported for this session._",
                         "_No 58% Fe brand assessments reported for this session._")
        new, done = patch_brands(md, make_doc(True))
        self.assertEqual(done, [B62_HEADING])
        self.assertIn("| **-** | - | - | - | **Carajas Fines** | 152.50 | +0.00 | +30.30 |", new)
        self.assertIn("_No 58% Fe brand assessments reported for this session._", new)

    def test_dash_side_filled_when_printed(self):
        hdr = ("| Port Stock Brand | Price (RMB/wmt) | Change | Diff to IOPI62 | Seaborne Brand | Price (USD/dmt) | Change | Diff to IOSI62 |\n"
               "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n")
        t62 = hdr + ("| **Roy Hill** | 811.00 | +0.00 | -54.00 | **-** | - | - | - |\n"
                     "| **Carajas Fines** | 1,028.00 | +0.00 | +163.00 | **-** | - | - | - |")
        new, done = patch_brands(template_md(t62, "_No 58% Fe brand assessments reported for this session._"),
                                 make_doc(False))
        self.assertEqual(done, [B62_HEADING, B58_HEADING])
        self.assertIn("| **Roy Hill** | 811.00 | +0.00 | -54.00 | **Roy Hill** | 118.45 | +0.00 | -3.75 |", new)
        self.assertIn("| **Yandi** | 58% Fe Fines | Port Stock (FOT Qingdao) | RMB/wmt | 607.00 | +0.00 | -4.00 |", new)

    def test_disagreeing_cell_leaves_table(self):
        hdr = ("| Port Stock Brand | Price (RMB/wmt) | Change | Diff to IOPI62 | Seaborne Brand | Price (USD/dmt) | Change | Diff to IOSI62 |\n"
               "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n")
        t62 = hdr + "| **Roy Hill** | 999.00 | +0.00 | -54.00 | **-** | - | - | - |"
        md = template_md(t62, "x")
        new, done = patch_brands(md, make_doc(False))
        self.assertNotIn(B62_HEADING, done)


class TestPatchFreight(unittest.TestCase):
    def doc(self):
        doc = pymupdf.open()
        page = doc.new_page(width=595, height=842)
        put = lambda x, y, t: page.insert_text((x, y), t, fontsize=7)
        put(338, 646, "Route"); put(392, 646, "Designation")
        for y, route, des, vals in ((661, "W. Australia - Qingdao", "C5", ("10.56", "-0.63", "-5.59%", "3.57", "16.77")),
                                    (673, "Tubarao - Qingdao", "C3", ("28.31", "3.32", "13.27%", "6.70", "36.40"))):
            put(338, y, route); put(402, y, des)
            for x, v in zip((424, 451, 480, 519, 553), vals):
                put(x, y, v)
        return doc

    def test_inserted_under_benchmarks(self):
        md = f"{BENCH_HEADING}\n| a |\n| :--- |\n| **IOSI65** |\n\n## Next\n"
        new, done = patch_freight(md, self.doc())
        self.assertEqual(done, [FREIGHT_HEADING])
        self.assertIn("| **IOSI65** |\n\n" + FREIGHT_HEADING + "\n", new)
        self.assertIn("| **C3, Tubarao - Qingdao** | Capesize Spot | 28.31 USD/t | +3.32 | +13.27% | 6.70 | 36.40 |", new)
        self.assertEqual(patch_freight(new, self.doc()), (new, []))


if __name__ == "__main__":
    unittest.main()
