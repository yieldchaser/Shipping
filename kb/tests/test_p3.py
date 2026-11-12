"""Unit tests for P3 identity helpers (pytest). Run: python -m pytest kb/tests -q"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from p3_names import (  # noqa: E402
    company_slug, corroboration, decide_tier, dwt_close, find_imo, imo_checksum_ok,
    is_distinctive_vessel_name, is_undisclosed, merge_sufficient, norm_company, norm_text,
    norm_vessel_name, norm_yard, parse_dwt, parse_year, precision_ok,
    strip_nationality, vessel_alias_ok, yard_similar,
)


def test_norm_text_basic():
    assert norm_text("  M/V  BORA & Co. ") == "BORA AND CO"
    assert norm_text(None) == ""


def test_norm_vessel_name():
    assert norm_vessel_name("M/V HOUHENG 6") == "HOUHENG 6"
    assert norm_vessel_name("M.T. BORA") == "BORA"
    assert norm_vessel_name("m.v.  Sea  Qingdao") == "SEA QINGDAO"
    assert norm_vessel_name("MV") == ""


def test_vessel_alias_ok():
    assert vessel_alias_ok("HOUHENG 6", 1)
    assert vessel_alias_ok("SEA QINGDAO", 3)
    assert not vessel_alias_ok("HUDONG ZHONGHUA", 42)   # shipyard / hull placeholder
    assert not vessel_alias_ok("1018", 1)               # numeric hull number
    assert not vessel_alias_ok("", 1)


def test_distinctive_name():
    assert is_distinctive_vessel_name("HOUHENG 6")
    assert is_distinctive_vessel_name("HIGHLAND")
    assert not is_distinctive_vessel_name("STAR")
    assert not is_distinctive_vessel_name("SEA")


def test_imo_check_digit():
    assert imo_checksum_ok("9744398")
    assert imo_checksum_ok(9339181)
    assert imo_checksum_ok("IMO 9744398")
    assert not imo_checksum_ok("9744399")
    assert not imo_checksum_ok("123456")
    assert find_imo("vessel IMO 9744398 sold") == "9744398"
    assert find_imo("no imo here 1234560") is None


def test_parse_dwt_and_year():
    assert parse_dwt("261,838") == 261838
    assert parse_dwt("DWT 180,000 approx") == 180000
    assert parse_dwt("180") == 180000
    assert parse_dwt("") is None
    assert parse_dwt("n/a") is None
    assert parse_dwt("12") is None
    assert parse_year("2017") == 2017
    assert parse_year("Built: 06/2014") == 2014
    assert parse_year("n/a") is None


def test_dwt_close():
    assert dwt_close(261838, 261761)
    assert not dwt_close(261838, 180000)
    assert not dwt_close(None, 261838)


def test_yard():
    assert norm_yard("Zhoushan Changhong Intl Shyd") == "ZHOUSHAN CHANGHONG"
    assert yard_similar("Guangzhou Shipyard Intl Co Ltd", "Guangzhou Shipyard International") >= 0.5
    assert yard_similar("", "Anything") == 0.0


def test_company_normalisation():
    assert norm_company("GREEK KASSIAN MARITIME") == "KASSIAN MARITIME"
    assert norm_company("BERMUDA BASED FRONTLINE") == "FRONTLINE"
    assert norm_company("Scorpio Tankers Inc.") == "SCORPIO TANKERS"
    # vessel-class words discriminate sister companies -> never stripped
    assert norm_company("Scorpio Bulkers") != norm_company("Scorpio Tankers Inc.")
    assert company_slug("Scorpio Tankers Inc.") == "scorpio_tankers"
    assert strip_nationality("GREEK") == ("GR", "")
    assert strip_nationality("UAE BASED") == ("AE", "")
    assert strip_nationality("MSC") == (None, "MSC")
    assert strip_nationality("CHINESE BUYERS") == ("CN", "")


def test_undisclosed():
    assert is_undisclosed("Undisclosed")
    assert is_undisclosed("")
    assert is_undisclosed("Unknown")
    assert not is_undisclosed("Bora")


def test_corroboration_and_tiers():
    n, detail = corroboration(261838, 261761, 2017, 2017, "Zhoushan Changhong", "ZHOUSHAN CHANGHONG INT",
                              1.0, True)
    assert n == 3 and detail["dwt_close"] and detail["year_close"] and detail["yard_match"]
    assert decide_tier(3, 1.0, True, 1, 9.0) == "auto"
    # near-miss spelling is never auto: "Grace Leo" / "Grace Leon" may be two ships
    assert decide_tier(3, 0.95, False, 1, 9.0) == "llm"
    # name only -> never auto
    n0, _ = corroboration(None, 261838, None, 2017, None, None, 1.0, True)
    assert n0 == 0
    assert decide_tier(0, 1.0, True, 1, 20.0) == "separate"
    # one corroborating attr -> judge
    assert decide_tier(1, 1.0, True, 1, 5.0) == "llm"
    # ambiguous candidates -> judge even with 2 attrs
    assert decide_tier(2, 1.0, True, 3, 8.0) == "llm"
    # dissimilar name -> separate regardless of weight
    assert decide_tier(3, 0.5, False, 1, 20.0) == "separate"


def test_merge_sufficiency():
    ok = {"dwt_conflict": False, "year_conflict": False}
    assert merge_sufficient(1.0, True, 2, ok)
    assert merge_sufficient(0.96, False, 1, ok)
    # name alone, no comparable attribute on both sides -> not enough
    assert not merge_sufficient(1.0, True, 0, ok)
    # contradiction on a hard attribute vetoes the merge
    assert not merge_sufficient(1.0, True, 2, {"dwt_conflict": True, "year_conflict": False})
    assert not merge_sufficient(1.0, True, 2, {"dwt_conflict": False, "year_conflict": True})
    # weak name similarity is never enough, even with agreement
    assert not merge_sufficient(0.90, False, 2, ok)


def test_precision_ok():
    assert precision_ok(99, 100)
    assert not precision_ok(97, 100)
    assert not precision_ok(0, 0)
