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
