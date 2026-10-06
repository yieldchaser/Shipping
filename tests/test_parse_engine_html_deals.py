"""Deal-line parser + HTML article extraction for the Hellenic VV weekly report (scripts/parse_engine_html)."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from scripts.parse_engine_html.deals import CLASS_RE, is_deal_candidate, parse_deal_line
from scripts.parse_engine_html.html_extract import decode_html, extract_article, parse_title_date

DASH = "–"


def ok(line: str, sector: str = "Bulkers"):
    res = parse_deal_line(line, sector)
    assert res.deal is not None, res.reason
    return res.deal


# --------------------------------------------------------------------------------------------- examples
def test_brief_example_handy_bc_multiword_class():
    d = ok(f"Handy BC Lancaster Strait (37,000 DWT, Jan 2013, Hyundai Mipo) sold to unknown German buyers for "
           f"USD 16.20 mil, VV Value USD 16.37 mil {DASH} Inc TC.")
    assert d.vessel_class == "Handy BC"
    assert d.vessel_name == "Lancaster Strait"
    assert (d.size, d.size_unit) == (37000, "DWT")
    assert d.built == "2013-01" and d.built_text == "Jan 2013"
    assert d.yard == "Hyundai Mipo"
    assert d.buyer == "unknown German buyers"
    assert d.price_usd_m == 16.20 and d.vv_value_usd_m == 16.37
    assert d.premium_pct == -1.04
    assert d.comments == "Inc TC"


def test_brief_example_small_clean_tanker_keeps_vessel_name():
    d = ok(f"Small Clean Tanker (Chem/Prod) Tradewind Passion (7,700 DWT, Apr 2008, Ningbo Xinle) sold to "
           f"undisclosed buyers for USD 5.60 mil, VV Value USD 7.04 mil {DASH} SS/DD Due.", "Tankers")
    assert d.vessel_class == "Small Clean Tanker (Chem/Prod)"
    assert d.vessel_name == "Tradewind Passion"
    assert d.comments == "SS/DD Due"
    assert d.premium_pct == -20.45
    assert d.buyer == "undisclosed buyers"


def test_brief_example_capesize():
    d = ok(f"Capesize Elizabeth II (180,200 DWT, Jan 2007, Imabari) sold to undisclosed buyers for USD 17.50 mil, "
           f"VV Value USD 18.41 mil {DASH} DD Due.")
    assert (d.vessel_class, d.vessel_name, d.comments) == ("Capesize", "Elizabeth II", "DD Due")
    assert d.premium_pct == -4.94


@pytest.mark.parametrize("dash", ["–", "—", "-", "�"])
def test_dash_variants_including_mojibake(dash):
    d = ok(f"MR2 Seamuse (48,700 DWT, Mar 2007, Iwagi Zosen) sold to undisclosed buyers for USD 21.00 mil, "
           f"VV Value USD 18.24 mil {dash} BWTS.", "Tankers")
    assert d.comments == "BWTS"


def test_mojibake_cp1252_bytes_decode_to_en_dash():
    raw = "<p>x â€“ y</p>".encode("utf-8")
    assert "–" in decode_html(raw)
    assert decode_html(b"a \x96 b") == "a – b"


@pytest.mark.parametrize("cls,expected_class,name", [
    ("MR2 (Chemical/Product) Gulf Elan", "MR2 (Chemical/Product)", "Gulf Elan"),
    ("MR2 (Chem/Procut) STI Tribeca", "MR2 (Chem/Procut)", "STI Tribeca"),
    ("MR1 (Chem / Product) Olympic Vision", "MR1 (Chem / Product)", "Olympic Vision"),
    ("Handy BC (Open Hatch) IVS Knot", "Handy BC (Open Hatch)", "IVS Knot"),
    ("Post Panamax BC Dyna Globe", "Post Panamax BC", "Dyna Globe"),
    ("Sub Panamax Container Hammonia Baltica", "Sub Panamax Container", "Hammonia Baltica"),
    ("Capesize (Newcastlemax) Azul Legenda", "Capesize (Newcastlemax)", "Azul Legenda"),
    ("J19 Stainless Steel Horin Trader", "J19 Stainless Steel", "Horin Trader"),
    ("Handy Container Hansa Rendsburg", "Handy Container", "Hansa Rendsburg"),
    ("Capesize BC Contamines", "Capesize BC", "Contamines"),          # 'Cont' must not eat the name
    ("Feedermax Contship Bee", "Feedermax", "Contship Bee"),
    ("CapesizeHemingway", "Capesize", "Hemingway"),                   # no space in the source
    ("Handy container Jett", "Handy container", "Jett"),
])
def test_class_vocabulary_longest_match(cls, expected_class, name):
    m = CLASS_RE.match(cls)
    assert m is not None
    assert m.group("cls") == expected_class
    assert cls[m.end():].strip() == name


def test_unknown_leading_text_is_not_a_class():
    assert CLASS_RE.match("Teekay sold Suezmax Tianlong Spirit") is None


# --------------------------------------------------------------------------------------------- odd cases
def test_inline_sale_terms_2025_style():
    d = ok("Panamax BC Ivestos 6 (76,600 DWT, Apr 2006, Imabari) sold DD Due to Unknown Vietnamese buyers for "
           "USD 9 mil, VV Value USD 10.12 mil")
    assert d.vessel_name == "Ivestos 6"
    assert d.buyer == "Unknown Vietnamese buyers"
    assert d.qualifiers == "DD Due"
    assert d.comments == "" and d.comments_all == "DD Due"
    assert d.price_usd_m == 9.0 and d.premium_pct == -11.07


def test_inc_tc_after_price_and_no_trailing_period_container():
    d = ok("Handy Container Mindoro (1,781 TEU, Dec 2022, Huanghai Shipyards) sold for USD 31.5 mil inc TC, "
           "VV Value USD 34 mil.", "Containers")
    assert (d.size, d.size_unit) == (1781, "TEU")
    assert d.qualifiers == "inc TC" and d.buyer == ""
    assert d.price_usd_m == 31.5 and d.vv_value_usd_m == 34.0


def test_seller_and_resale_flag():
    d = ok("Suezmax Hull 5122 (156,900 DWT, 2028, Daehan) sold (resale) to Delta Tankers for USD 107.0 mil, "
           "VV Value USD 106.04 mil.", "Tankers")
    assert d.buyer == "Delta Tankers" and d.qualifiers == "(resale)"
    assert d.built == "2028"
    d2 = ok("Handysize China Spirit (35,300 DWT, 2013, Dongzhe) sold by BoComm Leasing for USD 13 mil, "
            "VV Value USD 13.5 mil.")
    assert d2.seller == "BoComm Leasing" and d2.buyer == ""


def test_en_bloc_with_several_vessel_specs_is_one_row():
    d = ok("Capesizes Navios Bonavis (180,000 DWT, Jun 2009, Daewoo), Navios Ray (179,500 DWT, Mar 2012, "
           "Hanjin Subic) and Navios Azimuth (179,200 DWT, Feb 2011, Sungdong) sold to Navios Maritime Partners LP "
           f"in an en bloc deal for USD 88.00 mil, VV en bloc value USD 87.26 mil {DASH} Internal sale.")
    assert d.vessel_class == "Capesizes"
    assert d.vessel_name == "Navios Bonavis, Navios Ray, Navios Azimuth"
    assert d.n_vessels == 3 and "multi_spec" in d.flags and "en_bloc" in d.flags
    assert d.size is None and d.size_text == "180,000 / 179,500 / 179,200"
    assert d.buyer == "Navios Maritime Partners LP"
    assert d.comments == "Internal sale"
    assert d.premium_pct == 0.85


def test_count_prefix_without_vessel_name_and_size_range():
    d = ok("6 x MR2 (Chemical/Product) (46,000 DWT, 2016-2017, Hyundai Mipo) sold in an en bloc deal to Tsakos "
           "Energy Navigation for USD 192 mil, VV Value USD 196.9 mil", "Tankers")
    assert d.vessel_class == "MR2 (Chemical/Product)" and d.vessel_name == ""
    assert d.n_vessels == 6 and "no_vessel_name" in d.flags
    assert d.built is None and d.built_text == "2016-2017"
    assert d.buyer == "Tsakos Energy Navigation"


def test_billion_price_and_k_sizes():
    d = ok("9 x VLCC (300,000-320,000 DWT, 2014-2022) sold en bloc to Bahri for a total of USD 1 bil, "
           "VV Value USD 1.01 bil", "Tankers")
    assert d.price_usd_m == 1000.0 and d.vv_value_usd_m == 1010.0
    k = ok("LR2 Hesperia Tide (115k DWT, Jul 2025, Zhoushan Changhong) sold for USD 70 mil to New Shipping Ltd, "
           "VV value USD 68.56 mil", "Tankers")
    assert k.size == 115000 and k.buyer == "New Shipping Ltd" and k.price_usd_m == 70.0


def test_undisclosed_price_keeps_raw_text_and_no_premium():
    d = ok("Feedermax Tampa Trader (1,103 TEU, Mar 2016, Jiangsu New Yangzijian) sold by Lomar Shipping to Scion "
           "for undisclosed price, VV Value USD 18.60 mil", "Containers")
    assert d.price_usd_m is None and d.premium_pct is None
    assert d.price_raw == "for undisclosed price" and "price_undisclosed" in d.flags
    assert d.buyer == "Scion" and d.seller == "Lomar Shipping"


def test_unit_missing_flags_are_recorded_not_hidden():
    d = ok("Handy BC IVS Raffles (32,000 DWT, Jul 2013, Jiangmen Nanyang) sold to unknown Turkish buyers for "
           "USD 11.60, VV Value USD 12.07 mil")
    assert d.price_usd_m == 11.6 and "price_unit_assumed_mil" in d.flags
    c = ok("Sub Panamax Cardiff Trader (2,526, Mar 2003, Kvaerner Warnow Werft) sold to MSC for USD 30.00 mil, "
           "VV value USD 29.80 mil.", "Containers")
    assert c.size == 2526 and c.size_unit == "TEU" and "unit_inferred" in c.flags


def test_spec_with_yard_before_year_is_swapped_and_flagged():
    d = ok("Panamax Sofia I (5,100 TEU, Jiangnan Shanghai Changxing, 2010) sold to Chinese buyers for USD 40 mil "
           "inc TC, VV Value USD 39.5 mil.", "Containers")
    assert d.built == "2010" and d.yard == "Jiangnan Shanghai Changxing" and "spec_order_swapped" in d.flags


def test_period_before_dash_and_comment_without_dash():
    d = ok("Sub Panamax Vivaldi (2,504 TEU, Jan 2010, Jiangsu Yangzijiang) sold for USD 18.00 mil, VV value USD "
           f"48.98 mil. {DASH} low TC attached.", "Containers")
    assert d.comments == "low TC attached"
    e = ok("Handy BC (Open Hatch) Mount Adams (28,500 DWT, May 2002, Kanda) Sold to Undisclosed Buyers for USD "
           "9.8mil, VV Value USD 9.62mil BWTS Fitted.")
    assert e.comments == "BWTS Fitted" and "tail_without_dash" in e.flags and e.price_usd_m == 9.8


# --------------------------------------------------------------------------------------------- never dropped
@pytest.mark.parametrize("line,reason_part", [
    ("Torm acquired 4x LR1s ranging from 73,800 DWT to 75,000 DWT, built between Oct 2012 and Sep 2013 at STX "
     "Offshore, in an en bloc deal worth USD 140 mil, VV Value USD 139.75 mil.", "spec"),
    ("Panamax Oakland (4,890 TEU, Oct 2000, Hyundai HI) sold to unknown Chinese buyers for USD 11.90 mil, "
     "VV Value USD 11.29d", "VV value"),
    ("Handy Containers Galen and Garwood (1,840 TEU, 2007/2008, Hyundai Mipo) sold for USD 18.5 mil each, "
     "VV Values USD 19.5 mil and USD 19.6 mil respectively", "several VV values"),
    ("Teekay sold Suezmax Tianlong Spirit and LR2 Galway Spirit (159,000 DWT & 105,200 DWT, Jan 2009 & Jan 2007, "
     "Bohai Shipbuilding & Hyundai Heavy Ulsan) in an en bloc deal for USD 59 mil, VV enbloc value USD 61.28 mil.",
     "vocabulary"),
])
def test_unparseable_lines_fail_with_a_reason(line, reason_part):
    res = parse_deal_line(line)
    assert res.deal is None
    assert reason_part.lower() in res.reason.lower()


def test_is_deal_candidate():
    assert is_deal_candidate("X (1,000 DWT, 2010, Y) sold for USD 5 mil, VV value USD 5 mil")
    assert is_deal_candidate("Torm acquired LR1s (73,800 DWT) for USD 140 mil")           # priced sale, no VV text
    assert not is_deal_candidate("Tanker values have remained stable.")
    assert not is_deal_candidate("A sea of green can be seen on VVs matrix this week")


# --------------------------------------------------------------------------------------------- html extraction
def write_html(tmp_path: Path, name: str, title: str, body: str, wrap: str = "div") -> Path:
    inner = f"<{wrap}>{body}</{wrap}>" if wrap else body
    html = (f"<!DOCTYPE html><html><head><meta charset='UTF-8'><title>{title}</title>"
            f"<meta name='archive-date' content='08 March 2023'></head><body><h1>{title}</h1>"
            f"<section>{inner}</section></body></html>")
    p = tmp_path / name
    p.write_bytes(html.encode("utf-8"))
    return p


def test_title_date_parsing_variants():
    assert parse_title_date("Weekly Vessel Valuations Report, March 07 2023") == date(2023, 3, 7)
    assert parse_title_date("Weekly Vessel Valuations Report, September 8 2026") == date(2026, 9, 8)
    assert parse_title_date("nothing") is None


def test_extract_commentary_deals_and_unparsed(tmp_path):
    body = (
        "<p><strong>Bulkers</strong>: Handysize values have firmed, other BC types remained stable</p>"
        f"<p>Capesize Elizabeth II (180,200 DWT, Jan 2007, Imabari) sold to undisclosed buyers for USD 17.50 mil, "
        f"VV Value USD 18.41 mil {DASH} DD Due.</p>"
        "<p>Mystery line (1,000 DWT, 2010, Y) sold for USD 5 mil, VV Value USD 5.0d</p>"
        "<p><strong>Tankers:</strong>Tanker values have remained stable</p>"
        "<p>No reported sales this week.</p>"
        "<p><strong>Containers</strong></p><p>Container values have softened.</p>"
        "<p><img src='assets/x_img1_1.jpg'/></p>")
    p = write_html(tmp_path, "2023-03-08_weekly-vessel-valuations-report-march-07-2023.html",
                   "Weekly Vessel Valuations Report, March 07 2023", body)
    art = extract_article(p)
    assert art.issue_date == date(2023, 3, 7) and art.filename_date == date(2023, 3, 8)
    assert [s.name for s in art.sectors] == ["Bulkers", "Tankers", "Containers"]
    bulk, tank, cont = art.sectors
    assert bulk.commentary == ["Handysize values have firmed, other BC types remained stable"]
    assert bulk.header_style == "strong_colon_outside"
    assert len(bulk.deals) == 1 and bulk.deals[0].comments == "DD Due"
    assert len(bulk.unparsed) == 1 and bulk.unparsed[0][0].startswith("Mystery line")
    assert tank.header_style == "strong_colon_inside"
    assert tank.commentary == ["Tanker values have remained stable"]
    assert tank.notes == ["No reported sales this week."]
    assert cont.header_style == "strong_alone" and cont.commentary == ["Container values have softened."]
    assert art.n_deals == 1 and art.n_unparsed == 1
    assert art.image_refs == ["assets/x_img1_1.jpg"]


def test_em_tag_between_class_and_spec_and_ad_chrome(tmp_path):
    body = ("<p><strong>Tanker:</strong>Tanker values have remained stable.</p>"
            "<ins>Discover more Price Comparisons</ins>"
            f"<p>Aframax<em>Taurus Sun</em>(115,600 DWT, May 2007, Sasebo) sold to Westport Tankers for USD 17.20 "
            f"mil, VV value USD 17.02 mil {DASH} SS/DD Due.</p>")
    art = extract_article(write_html(tmp_path, "a.html", "Weekly Vessel Valuations Report, July 04 2023", body))
    deal = art.sectors[0].deals[0]
    assert (deal.vessel_class, deal.vessel_name) == ("Aframax", "Taurus Sun")
    assert art.sectors[0].name == "Tankers"
    assert all("Discover" not in c for c in art.sectors[0].commentary)


def test_plain_text_header_and_flat_section(tmp_path):
    body = ("<p>Tankers:VV Tanker values remain mostly stable this week</p>"
            "<p>MR2 Seamuse (48,700 DWT, Mar 2007, Iwagi Zosen) sold to undisclosed buyers for USD 21.00 mil, "
            "VV Value USD 18.24 mil.</p>")
    art = extract_article(write_html(tmp_path, "b.html", "Weekly Vessel Valuations Report, July 11 2023", body,
                                     wrap=""))
    assert art.container == "chrome_flat"
    assert art.sectors[0].header_style == "plain_colon"
    assert art.sectors[0].commentary == ["VV Tanker values remain mostly stable this week"]
    assert art.n_deals == 1


def test_image_only_issue_has_no_sectors_and_is_still_a_vv_report(tmp_path):
    art = extract_article(write_html(tmp_path, "c.html", "Weekly Vessel Valuations Report, October 15 2024",
                                     "<p><img src='assets/m.jpg'/></p>", wrap=""))
    assert art.is_vv_report and art.sectors == [] and art.image_refs == ["assets/m.jpg"]


def test_wordpress_fragment_with_comment_title(tmp_path):
    p = tmp_path / "2026-09-29_weekly-vessel-valuations-report-september-29-2026.html"
    p.write_text(
        "<!-- Title: Weekly Vessel Valuations Report, September 29 2026 | Date: 2026-09-29 | URL: x -->\n"
        "<p><strong>Bulkers</strong></p>\n"
        "<p>Bulker S&amp;P values held stable<!--more--> in response to soft pricing.</p>\n"
        "<p>Ultramax Indigo Breeze (60,400 DWT, Feb 2017, Mitsui Tamano) sold to Greek buyers for USD 30.5 mil, "
        "VV Value USD 31.61 mil.</p>\n", encoding="utf-8")
    art = extract_article(p)
    assert art.container == "wp_fragment" and art.issue_date == date(2026, 9, 29)
    assert art.sectors[0].commentary == ["Bulker S&P values held stable in response to soft pricing."]
    assert art.n_deals == 1


def test_non_vv_page_is_flagged(tmp_path):
    art = extract_article(write_html(tmp_path, "d.html", "Day of the Seafarer 2024", "<p>hello</p>"))
    assert not art.is_vv_report
