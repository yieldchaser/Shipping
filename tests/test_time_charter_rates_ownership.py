"""One column = one source in data/derived/time_charter_rates.csv.

Guards the two 2026-10-25 defects: the Alibra dry archive (a 4/6-month series)
written into the *_1y_atl/pac columns, and the 2021 ULTRAMAX grid row folded
into the supramax columns.
"""

import csv
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import update_derived_tc_rates as tc  # noqa: E402

TC_CSV = ROOT / "data" / "derived" / "time_charter_rates.csv"
DRY_TENORS = ("4_6m", "1y", "2y")


def _read(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


@pytest.fixture(scope="module")
def derived():
    return {r["date"]: r for r in _read(TC_CSV)}


def test_dry_class_mapping_keeps_ultramax_out_of_supramax():
    assert tc.norm_dry_class("SUPRAMAX") == "supramax"
    assert tc.norm_dry_class("SMAX/ULTRA") == "supramax"
    assert tc.norm_dry_class("ULTRAMAX") is None
    assert tc.norm_dry_class("HANDY (38k dwt)") == "handysize"
    assert tc.norm_dry_class("HANDY (30K dwt)") is None
    assert tc.norm_dry_class("PANA/KMAX") == "panamax"
    with pytest.raises(ValueError):
        tc.norm_dry_class("KAMSARMAX II")


def test_tenor_mapping_is_strict():
    assert tc.norm_dry_tenor("6 MOS") == "4_6m"
    assert tc.norm_dry_tenor("4/6 MOS") == "4_6m"
    assert tc.norm_dry_tenor("1 YR") == "1y"
    with pytest.raises(ValueError):
        tc.norm_dry_tenor("3 YR")
    assert tc.norm_wet_class("MR IMO3") == "mr"
    assert tc.norm_wet_class("LR2 (115K dwt cpp & dpp)") == "lr2"
    assert tc.norm_wet_class("AFRA (115k dwt)") == "aframax"


def test_compose_ownership():
    printed = {"2023-01-04": {"capesize_1y_atl": 13500.0}}
    fearnleys = {"2019-01-02": {"capesize_1y_avg": 9000.0}, "2019-01-09": {"capesize_1y_avg": 9100.0}}
    archive = {
        "2023-01-04": {"capesize_4_6m_atl": 12000.0},
        "2019-01-09": {"capesize_4_6m_atl": 8000.0, "capesize_4_6m_avg": 8000.0},
        "2019-01-10": {"capesize_4_6m_pac": 7000.0},
    }
    rows = {r["date"]: r for r in tc.compose(printed, fearnleys, archive)}
    # printed date: archive never writes into it
    assert rows["2023-01-04"]["source"] == "alibra_ocr"
    assert rows["2023-01-04"]["capesize_1y_atl"] == 13500.0
    assert rows["2023-01-04"]["capesize_4_6m_atl"] == ""
    assert rows["2019-01-02"]["source"] == "fearnleys"
    assert rows["2019-01-09"]["source"] == "fearnleys+alibra_archive"
    assert rows["2019-01-09"]["capesize_1y_avg"] == 9100.0
    assert rows["2019-01-09"]["capesize_4_6m_atl"] == 8000.0
    assert rows["2019-01-10"]["source"] == "alibra_archive"
    assert rows["2019-01-10"]["capesize_1y_avg"] == ""


def test_archive_drops_dates_printed_twice_with_different_values(tmp_path):
    f = tmp_path / "a.csv"
    f.write_text(
        "BULK CARRIER,Date,HANDYSIZE,SMAX/ULTRA,PANAMAX,CAPESIZE,\n"
        "Week 27,03 Jul 2019,9000,10000,14000,20000,Week 27|2019-07-03\n"
        "Week 28,10 Jul 2019,9500,10750,14500,20500,Week 28|2019-07-10\n"
        "Week 29,10 Jul 2019,9500,11750,16750,27000,Week 29|2019-07-10\n"
        "Week 1,04 Jan 2023,11500,14000,18500,12000,Week 1|2023-01-04\n"
        "Week 1,04 Jan 2023,11500,14000,18500,12000,Week 1|2023-01-04\n",
        encoding="utf-8",
    )
    got = tc.parse_archive_file(f)
    assert set(got) == {"2019-07-03", "2023-01-04"}
    assert got["2023-01-04"]["capesize"] == 12000.0


def test_derived_equals_printed_grid_on_every_cell(derived):
    checked = 0
    for r in _read(tc.DRY_SERIES):
        seg = tc.norm_dry_class(r["vessel_class"])
        if seg is None:
            continue
        col = f"{seg}_{tc.norm_dry_tenor(r['tenor'])}_{tc.norm_dry_basin(r['basin'])}"
        row = derived[r["issue_date"]]
        assert row["source"] == "alibra_ocr"
        assert float(row[col]) == float(r["rate_usd_pdpr"]), (r["issue_date"], col)
        checked += 1
    for r in _read(tc.WET_SERIES):
        col = f"{tc.norm_wet_class(r['vessel_class'])}_{tc.norm_wet_tenor(r['tenor'])}"
        assert float(derived[r["issue_date"]][col]) == float(r["rate_usd_pdpr"]), (r["issue_date"], col)
        checked += 1
    assert checked > 13000


def test_2021_supramax_columns_hold_supramax_not_ultramax(derived):
    # 2021-07-07 image: SUPRAMAX 6 MOS ATL 33,000 / ULTRAMAX 34,500
    assert float(derived["2021-07-07"]["supramax_4_6m_atl"]) == 33000.0
    assert float(derived["2021-07-07"]["supramax_1y_atl"]) == 25500.0


def test_one_year_columns_never_carry_archive_values(derived):
    # 2023-01-04 image: CAPESIZE 4/6 MOS ATL 12,000 (archive) vs 1 YR ATL 13,500
    assert float(derived["2023-01-04"]["capesize_1y_atl"]) == 13500.0
    assert float(derived["2023-01-04"]["capesize_4_6m_atl"]) == 12000.0
    for d, row in derived.items():
        if row["source"] == "alibra_ocr":
            continue
        for seg in tc.DRY_SEGMENTS:
            for col in (f"{seg}_1y_atl", f"{seg}_1y_pac", f"{seg}_2y_atl", f"{seg}_2y_pac", f"{seg}_2y_avg"):
                assert row[col] == "", (d, col)
            if "fearnleys" not in row["source"]:
                assert row[f"{seg}_1y_avg"] == "", (d, seg)


def test_fearnleys_cells_equal_fearnleys_file(derived):
    first_printed = min(d for d, r in derived.items() if r["source"] == "alibra_ocr")
    fear = tc.load_fearnleys(end_before=first_printed)
    assert len(fear) > 1000
    for d, cells in fear.items():
        assert "fearnleys" in derived[d]["source"]
        for col, v in cells.items():
            assert float(derived[d][col]) == v, (d, col)


def test_sources_and_schema(derived):
    allowed = {"alibra_ocr", "fearnleys", "alibra_archive", "fearnleys+alibra_archive"}
    assert {r["source"] for r in derived.values()} <= allowed
    with open(TC_CSV, encoding="utf-8") as f:
        assert f.readline().strip().split(",") == tc.TC_COLS


def test_committed_file_is_the_rebuild(tmp_path):
    out = tmp_path / "tc.csv"
    tc.build_time_charter_rates(out_path=out)
    assert out.read_bytes().replace(b"\r\n", b"\n") == TC_CSV.read_bytes().replace(b"\r\n", b"\n")
