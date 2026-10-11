"""The no-LlamaParse path of run_drewry_ais: plain PyMuPDF text must still yield the KPI cards and commentary."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "extract" / "publishers"))
import run_drewry_ais as A  # noqa: E402

P2 = ("Week\n10\n2026\nHigher fleet utilisation and tonne-mile demand support\nHandysize rates despite easing congestion\n1\n"
      "content_summary\n●\nHandysize utilisation increased further, reflecting stronger fleet employment and\n"
      "firmer regional rates.\n●\nVessel capacity at anchor fell 4.1% MoM in the west.\nUtilisation vs Baltic rates\n85%\n")
P3 = ("87.5\nCurrent tonne-miles\nindex\n▼ 22.2%\nYoY change in tonne-\nmiles index\n▲ 3.3%\nMoM change in bunker\nprice\n"
      "$866\nper tonne price of\nbunker at the end of\nthe week\n")


def test_plain_text_fallback_reads_cards_and_commentary():
    r = A.extract_metrics_from_pages([{"page": 1, "text": "x"}, {"page": 2, "text": P2}, {"page": 3, "text": P3}],
                                     "Drewry_AIS_Drybulk_Handysize_Week40_2026.pdf", "Drybulk_Handysize")
    assert r["tonne_miles_index"] == 87.5
    assert r["tonne_miles_yoy_pct"] == -22.2
    assert r["bunker_price_usd_per_t"] == 866.0
    assert r["commentary_title"] == "Higher fleet utilisation and tonne-mile demand support Handysize rates despite easing congestion"
    assert r["commentary_summary"].endswith("4.1% MoM in the west.")
    assert "Utilisation vs" not in r["commentary_summary"]


def test_markdown_is_not_rewrapped():
    md = "**87.5**\n**Current tonne-miles index**\n\n## Title\n\nsome text\nmore text"
    assert A._unwrap_plain_text(md) == md
