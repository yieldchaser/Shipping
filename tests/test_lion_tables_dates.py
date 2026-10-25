import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "extract" / "publishers"))
import run_lion_tables as r  # noqa: E402

DEMO = """LION'S DEMOMETER (USD $ / LT)
COUNTRY
BULKER
TANKER
CONT/TWEEN
TREND
TURKEY
290
300
310
stable
BANGLADESH
500
525 - 530
540 - 550
very firm

Representative Sales
"""


def test_week_and_date_on_separate_lines():
    text = "W E E K L Y M A R K E T R E P O R T\nWeek 43\n23 October 2026\n\n" + DEMO
    x = r.extract_full_report(text, "corpus/01-brokers/lion/2026/lion_x.pdf", 4)
    assert (x["issue_date"], x["report_week"]) == ("2026-10-23", 43)


def test_ci_file_name_fallback():
    x = r.extract_full_report(DEMO, "lion_23_10_2026_lion_shipbrokers_weekly_market_report_week_43_2026.pdf", 4)
    assert (x["issue_date"], x["report_week"]) == ("2026-10-23", 43)


def test_trend_kept_as_printed():
    table, _ = r.parse_demometer_block(DEMO, "2026-10-23", 43)
    trends = {row["country"]: row["trend"] for row in table}
    assert trends["Turkey"] == "Stable"
    assert trends["Bangladesh"] == "Very firm"


W43_DEALS = """Week 43
23 October 2026
REPRESENTATIVE SALES
B U L K E R S
M/V AM PRESTIGE (31,956 dwt, blt 2014 Guangzhou Wenchong/China) - Sold for $ 12.5 mill.

  L I O N S H I P B R O K E R S
W E E K L Y M A R K E T R E P O R T
\u00a9 Lion Research & Valuations 2026 \u2013 All rights reserved.
3
T A N K E R S
M/T KASTOS (115,000 dwt, blt 2010 Samsung/Korea) - Sold for $ 40 mill.
DEMOLITION
L P G
M/T BAI HUA YUAN (LDT 2,214, 3,338 dwt, blt 1997 Japan) - Demo for $ 372 per LT to CHINA.
L E G A L D I S C L AI M E R
This report has been produced on information collected from a variety of market sources.
"""


def test_letter_spaced_layout_sections():
    x = r.extract_full_report(W43_DEALS, "lion_23_10_2026_lion_shipbrokers_weekly_market_report_week_43_2026.pdf", 4)
    deals = {d["vessel"]: d for d in x["all_deals"]}
    assert deals["AM PRESTIGE"]["comments"] == "Sold for $ 12.5 mill."
    assert deals["KASTOS"]["section"] == "TANKERS"
    assert (deals["BAI HUA YUAN"]["tag"], deals["BAI HUA YUAN"]["sub_section"]) == ("M/T", "LPG")
    assert deals["BAI HUA YUAN"]["comments"] == "Demo for $ 372 per LT to CHINA."
