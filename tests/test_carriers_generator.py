"""Carriers generator (scripts/extract/publishers/run_carriers_complete.py) on synthetic pymupdf pages.

Carriers draws every sentiment arrow with the same up glyph and gives the direction by colour (green up, red down);
boxes that do not fit at the foot of a page continue at the top of the next one; the 2023 W46 - 2024 W11 tanker box
prints a seventh column (Baltic LPG). The arrows are drawn here with the 'china-s' font, which keeps the glyph in
the text layer.
"""
import sys
import unittest
from pathlib import Path

import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "extract" / "publishers"))

import run_carriers_complete as rcc  # noqa: E402

GREEN, RED = (0, 0.69, 0.31), (1, 0, 0)


def put(page, x, y, text, color=(0, 0, 0)):
    page.insert_text((x, y), text, fontsize=7, color=color)


def arrow(page, x, y, color):
    page.insert_text((x, y), "↑", fontsize=7, color=color, fontname="china-s")


def tanker_box(page, y, lpg, rows):
    put(page, 60, y, "Wet Baltic Indices & TCE Full Route plus Baltic LPG")
    put(page, 120, y + 12, "Baltic DIRTY")
    if lpg:
        put(page, 487, y + 12, "LPG")
        put(page, 503, y + 12, "Index")
    for i, (label, vals) in enumerate(rows):
        put(page, 70, y + 30 + 12 * i, label)
        for x, v in zip((120, 170, 230, 290, 340, 400, 490), vals):
            put(page, x, y + 30 + 12 * i, v)


class TestSentimentByColour(unittest.TestCase):
    def test_bspa_and_bda_arrow_colour(self):
        page = pymupdf.open().new_page(width=595, height=842)
        put(page, 45, 100, "VLCC")
        put(page, 150, 100, "305000")
        put(page, 200, 100, "96.42")
        arrow(page, 235, 100, RED)
        put(page, 300, 100, "TANKERS")
        put(page, 360, 100, "SUBCON")
        put(page, 420, 100, "15000 - 25000")
        put(page, 480, 100, "507.61")
        arrow(page, 530, 100, GREEN)
        bspa, bda = rcc.extract_bspa_and_bda(page, 90, 120, "2023-11-13", 46, "x.pdf")
        self.assertEqual((bspa[0]["price_raw"], bspa[0]["sentiment_arrow"]), ("96.42", "DOWN"))
        self.assertEqual(bda[0]["sentiment_arrow"], "UP")

    def test_two_index_boxes_on_one_line(self):
        page = pymupdf.open().new_page(width=595, height=842)
        put(page, 62, 100, "DSPA")
        put(page, 168, 100, "3.598")
        arrow(page, 188, 100, GREEN)
        put(page, 287, 100, "DSRA")
        put(page, 444, 100, "7.147")
        arrow(page, 464, 100, RED)
        put(page, 62, 112, "TSPA")
        put(page, 168, 112, "7.360(no change)")
        got = {r["index_name"]: (r["current_raw"], r["sentiment_arrow"])
               for r in rcc.extract_shipping_indices(page, 90, 120, "2025-07-21", 30, "x.pdf")}
        self.assertEqual(got["DSPA"], ("3.598", "UP"))
        self.assertEqual(got["DSRA"], ("7.147", "DOWN"))
        self.assertEqual(got["TSPA"], ("7.360", "STEADY"))
        self.assertEqual(got["BSPA"], (None, None))


class TestContinuation(unittest.TestCase):
    def test_index_values_on_the_next_page(self):
        doc = pymupdf.open()
        p1 = doc.new_page(width=595, height=842)
        put(p1, 45, 740, "Sale and Purchase Index")
        p2 = doc.new_page(width=595, height=842)
        put(p2, 62, 50, "DSPA")
        put(p2, 168, 50, "3.598")
        arrow(p2, 188, 50, GREEN)
        put(p2, 45, 120, "Dry BC Baltic Indices")
        data, pages = rcc.extract_document(doc, "x.pdf", "2024-03-11", 11)
        dspa = next(r for r in data["indices"] if r["index_name"] == "DSPA")
        self.assertEqual((dspa["current_raw"], dspa["sentiment_arrow"]), ("3.598", "UP"))
        self.assertEqual(pages, [1, 2])

    def test_tanker_previous_row_above_the_greek_equities(self):
        doc = pymupdf.open()
        p1 = doc.new_page(width=595, height=842)
        tanker_box(p1, 690, True, [("This WK", ["1310", "862", "31.586", "49.132", "55.536", "46.507", "15.095"]),
                                    ("Week Ch.", ["-63", "77", "6296", "-6360", "-12961", "11702", "329"])])
        p2 = doc.new_page(width=595, height=842)
        tanker_box(p2, 20, False, [("Previous", ["1373", "785", "25.290", "55.492", "68.497", "34.805", "14.766"])])
        put(p2, 60, 200, "Greek-Listed Companies Traded in the US Stock Exchange")
        put(p2, 200, 220, "11.15")
        data, pages = rcc.extract_document(doc, "x.pdf", "2023-11-20", 47)
        got = {r["metric_name"]: (r["current_raw"], r["change_raw"], r["prev_raw"]) for r in data["tanker_tce"]}
        self.assertEqual(got["Baltic DIRTY Tanker Index"], ("1310", "-63", "1373"))
        self.assertEqual(got["LPG Index"], ("15.095", "329", "14.766"))
        self.assertEqual(next(r for r in data["tanker_tce"] if r["metric_name"] == "LPG Index")["current_value"], 15095.0)
        self.assertEqual(pages, [1])  # the Greek equities page is not substantive

    def test_printed_placeholders(self):
        page = pymupdf.open().new_page(width=595, height=842)
        tanker_box(page, 100, False, [("This WK", ["2868", "1584", "388.612", "158.714", "66.893", "N/A"]),
                                      ("Week Ch.", ["192", "172", "43406", "30134", "1337", "-"]),
                                      ("Previous", ["2676", "1412", "345.206", "128.580", "65.556", "24.295"])])
        mr = next(r for r in rcc.extract_tanker_tce(page, 95, 180, "2026-09-07", 36, "x.pdf")
                  if r["metric_name"] == "MR ATLANTIC TC routes")
        self.assertEqual((mr["current_raw"], mr["change_raw"], mr["prev_raw"]), ("N/A", "-", "24.295"))
        self.assertIsNone(mr["current_value"])


class TestMarkdownRows(unittest.TestCase):
    MD = "\n".join([
        "## Second-hand Market Reported Sold", "",
        "| Name | Type | DWT | Built | Yard | Price ($M) | Buyers | Comments |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
        "| CP TIANJIN | BC | 63541 | 2016 | Chengxi Shipyard Jiangyin | 23.80 EACH | UNDISCLOSED |  |",
        "| CP GUANGZHOU | BC | 63527 | 2015 | Chengxi Shipyard Jiangyin | 23.80 EACH | UNDISCLOSED |  |",
        "| MBA GIOVANNI | BC | 93361 | 2010 | Jiangsu Newyangzi | INTEROCEAN | - |  |",
        "| QING MAY | BC | 206117 | 2012 | Shanghai Waigaoqiao Shbldg | WINNING SHIPPING | 73.00 EN BLOC |  |",
        "", "## Demolition Market", "", "*None Reported*", ""])

    def test_price_buyers_slip_swapped_back(self):
        md = rcc.unswap_price_buyers(self.MD)
        self.assertIn("| MBA GIOVANNI | BC | 93361 | 2010 | Jiangsu Newyangzi | - | INTEROCEAN |  |", md)
        self.assertIn("| 73.00 EN BLOC | WINNING SHIPPING |", md)
        self.assertIn("| 23.80 EACH | UNDISCLOSED |", md)

    def test_series_rows_follow_the_markdown(self):
        parsed = [{"issue_date": "2024-01-15", "report_week": 3, "section": "bulk_carriers", "page": 1,
                   "vessel_name": "CP TIANJIN", "source_file": "x.pdf"},
                  {"issue_date": "2024-01-15", "report_week": 3, "section": "tankers", "page": 2,
                   "vessel_name": "QING", "source_file": "x.pdf"}]
        data = {"sales": parsed, "demolition": [], "newbuilding": []}
        rcc.series_from_markdown(rcc.unswap_price_buyers(self.MD), data)
        rows = {r["vessel_name"]: r for r in data["sales"]}
        self.assertEqual(len(rows), 4)
        self.assertEqual((rows["CP GUANGZHOU"]["price_usd_mill"], rows["CP GUANGZHOU"]["section"]), (23.8, "bulk_carriers"))
        self.assertEqual((rows["QING MAY"]["price_usd_mill"], rows["QING MAY"]["page"]), (73.0, 2))
        self.assertEqual(rows["MBA GIOVANNI"]["buyers"], "INTEROCEAN")
        self.assertIsNone(rows["MBA GIOVANNI"]["price_usd_mill"])


if __name__ == "__main__":
    unittest.main()
