"""2024+ Xclusiv generator (scripts/extract/publishers/run_xclusiv_tables.py): the word-geometry parsers of the
newbuilding and secondhand boxes, the last-week demolition column, the split demolition-sale name, and the
newbuilding activity prose. Expected values are read off the page render. Corpus PDFs are local-only."""
from __future__ import annotations

import sys
from pathlib import Path

import pymupdf
import pytest

from scripts.parse_engine.config import MAIN_CHECKOUT, REPO_ROOT
from scripts.parse_engine.export_series import sidecar_payload

sys.path.insert(0, str(REPO_ROOT / "scripts/extract/publishers"))
import run_xclusiv_tables as x  # noqa: E402

DIR = "corpus/01-brokers/xclusiv/2024/xclusiv_2024_xclusiv-2024_{}.pdf"


def _doc(stamp: str) -> pymupdf.Document:
    for root in (REPO_ROOT, MAIN_CHECKOUT):
        p = root / DIR.format(stamp)
        if p.exists():
            return pymupdf.open(p)
    pytest.skip("Xclusiv corpus PDFs are local-only (gitignored)")


@pytest.mark.parametrize("stamp,vlcc", [("01_29", 127.7), ("03_19", 130.0)])
def test_newbuilding_box_reads_the_printed_vlcc_price(stamp, vlcc):
    # the nearest-number fallback stored 114.0 (01-29, a prose order) and 23 (03-19) for these
    rows = x.extract_newbuilding_prices(_doc(stamp), "x", 0, "x")
    assert len(rows) == 9
    assert {r["vessel_type"]: r["price_usd_mill"] for r in rows}["VLCC"] == vlcc


def test_newbuilding_box_recovers_all_nine_rows_when_the_legend_precedes_the_box():
    rows = x.extract_newbuilding_prices(_doc("02_19"), "x", 0, "x")
    assert len(rows) == 9 and all(len(r["printed_vals"]) == 6 for r in rows)


def test_demolition_sale_name_split_over_two_lines_is_one_vessel():
    rows = x.extract_demo_sales_tables(_doc("07_22"), "x", 0, "x")
    names = [r.get("NAME") or r.get("vessel_name") for r in rows]
    assert "WATERMARK ST. GEORGE" in names
    assert "WATERMARK ST." not in names and "GEORGE" not in names


def test_demolition_prices_carry_last_weeks_printed_column():
    dp = x.extract_indicative_demolition(_doc("08_26"), "x", 0, "x")
    assert {r["prev_week"] for r in dp} == {"Week 33"}
    india = next(r for r in dp if r["segment"] == "Bulkers" and r["country"] == "India")
    assert (india["price_usd_per_ldt"], india["prev_price_usd_per_ldt"]) == (505.0, 510.0)
    assert x.render_demolition_prices(dp)[0] == "| Segment | Country | Price ($/LDT) | Week 33 ($/LDT) |"


def test_newbuilding_activity_prose_is_kept():
    assert x.extract_newbuilding_activity(_doc("01_08")).startswith("2024 starts with great momentum on the NB market.")


def test_engine_sidecar_takes_the_printed_week_over_the_iso_week():
    # Xclusiv dated 2021-08-09 prints "Week 31"; its ISO week is 32
    tables = [{"name": "Baltic Dry Indices", "weeks": ["31", "30"]}]
    assert sidecar_payload(tables, "2021-08-09", "f.pdf", "0", vessel_rows=False)["report_week"] == 31
    assert sidecar_payload([], "2021-08-09", "f.pdf", "0", vessel_rows=False)["report_week"] == 32
