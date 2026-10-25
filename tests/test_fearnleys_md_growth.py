import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "extract" / "publishers"))
import run_fearnleys_md_growth as g  # noqa: E402

DOC = """## Capesize/Newcastlemax

In the last 6 weeks, total South Atlantic shipment volumes were up 1.1% compared to the corresponding weeks last year.
**Top right chart:** Shipment volumes were 6.3% higher than last year through week 14. Supply growth is at 1.5%.

## Panamax/Kamsarmax

Through week 42, growth was 2.9%, compared to DWT supply growth of 4.7%. Over the last 10 weeks, volume growth was 1.4% compared to the same period last year.
**Top left chart:** Shipment volumes were up 2.8% year on year through week 41. In the last ten weeks, volumes were down +0.3% compared to the same period last year. Supply growth was 4.2% at the latest reading.
Volume growth is below supply growth (4.8% vs 5.2%). Supply growth is slightly over 4%.

## Handysize

Through week 41, Handysize shipment volumes were 0.7% lower year on year. In the last eight weeks, volumes were down 1.8%.
"""


def _rows():
    return {(r["segment"], r["metric"], r["through_week"], r["last_weeks"]): r["value_pct"]
            for r in g.rows_of(DOC, "2026-10-22", "x.md")}


def test_volume_and_supply_kept_apart():
    rows = _rows()
    assert rows[("Panamax", g.YTD, "42", "")] == "2.9"
    supply = [r["value_pct"] for r in g.rows_of(DOC, "2026-10-22", "x.md")
              if r["segment"] == "Panamax" and r["metric"] == g.SUPPLY]
    assert supply == ["4.7", "4.2"]
    assert rows[("Panamax", g.YTD, "41", "")] == "2.8"
    assert rows[("Capesize", g.YTD, "14", "")] == "6.3"
    assert rows[("Capesize", g.SUPPLY, "", "")] == "1.5"


def test_last_weeks_and_direction():
    rows = _rows()
    assert rows[("Panamax", g.LAST, "", "10")] == "1.4"
    assert rows[("Handysize", g.LAST, "", "8")] == "-1.8"
    assert rows[("Handysize", g.YTD, "41", "")] == "-0.7"


def test_skips_sub_trades_contradictions_and_approximations():
    vals = [r for r in g.rows_of(DOC, "2026-10-22", "x.md")]
    assert not any(r["value_pct"] in ("1.1", "0.3", "-0.3", "4.8", "5.2", "4") for r in vals)
    assert len(vals) == 9
