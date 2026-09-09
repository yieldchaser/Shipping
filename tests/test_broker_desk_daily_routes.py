#!/usr/bin/env python3
"""Broker Desk daily-routes UI (Phase 2) — marker tests over index.html + fixtures.

Pins the S3 'Tanker Routes' daily-native rewrite and the S4 'Dry Routes'
benchmark grid in index.html:
  - both daily caches are FETCHED at data-load time (never inlined);
  - S3 no longer touches fearnpulse_rates_full.csv (the monthly-compressed
    defect dies) while S9's museum references stay intact;
  - live/frozen classification cutoff and the taxonomy-switch disclosure come
    from the cache meta, not invented;
  - day-over-day delta math (rehearsed against trimmed real cache samples);
  - tooltip markers on tiles, tabs, charts, selects and badges.

Fixtures are TRIMMED REAL cache samples (strided + tail) from
data/derived/fearnleys_tanker_routes_daily.json and
data/derived/fearnleys_dry_routes_daily.json — values are source data, not
invented; only the sampling stride is ours.
"""
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HTML = ROOT / "index.html"
TANKER_JSON = ROOT / "data" / "derived" / "fearnleys_tanker_routes_daily.json"
DRY_JSON = ROOT / "data" / "derived" / "fearnleys_dry_routes_daily.json"

with open(HTML, "r", encoding="utf-8") as f:
    C = f.read()


def epoch_iso(ms):
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


# ------------------------------------------------- trimmed real cache samples
# (strided head + full tail; metadata recomputed for the trimmed pts)

FIXTURE_SERIES = {
    'TANK_VLCC_MEG_FEAST': {
        'label': 'MEG/FEAST · WS',
        'klass': 'VLCC',
        'route': 'MEG/FEAST',
        'unit': 'ws',
        'cadence': 'daily',
        'pts': [[1526601600000, 38], [1554336000000, 37.5], [1583366400000, 47.5], [1611619200000, 32.38], [1641168000000, 41.64], [1670544000000, 81.32], [1701907200000, 66.5], [1733702400000, 42.5], [1764547200000, 130], [1787702400000, 600], [1787788800000, 600], [1787875200000, 600], [1788134400000, 600], [1788220800000, 650], [1788307200000, 650], [1788393600000, 675], [1788480000000, 660], [1788739200000, 660], [1788825600000, 700]],
        'first': '2018-05-18',
        'last': '2026-09-08',
        'n': 19,
    },
    'TANK_VLCC_MEG_FEAST_TCE': {
        'label': 'MEG/FEAST · TCE',
        'klass': 'VLCC',
        'route': 'MEG/FEAST',
        'unit': 'tce',
        'cadence': 'daily',
        'pts': [[1526601600000, 0], [1554336000000, 8700], [1583366400000, 18600], [1611619200000, 2058], [1641168000000, 2044], [1670544000000, 49113], [1681344000000, 56017], [1681430400000, 55395], [1681689600000, 56070], [1681776000000, 57033], [1681862400000, 56220], [1681948800000, 47108], [1682035200000, 48232], [1682121600000, 48232], [1682294400000, 46009], [1682380800000, 46009]],
        'first': '2018-05-18',
        'last': '2023-04-25',
        'n': 16,
    },
    'TANK_VLCC_CEYHAN_USG': {
        'label': 'CEYHAN/USG · WS',
        'klass': 'VLCC',
        'route': 'CEYHAN/USG',
        'unit': 'ws',
        'cadence': 'daily',
        'pts': [[1526601600000, 45], [1554336000000, 55], [1583366400000, 50], [1611619200000, 37.5], [1641168000000, 45], [1670544000000, 82.5], [1703203200000, 58], [1736812800000, 62.5], [1767830400000, 62.5], [1787702400000, 217.5], [1787788800000, 215], [1787875200000, 212.5], [1788134400000, 212.5], [1788220800000, 215], [1788307200000, 217.5], [1788393600000, 230], [1788480000000, 235], [1788739200000, 240], [1788825600000, 250]],
        'first': '2018-05-18',
        'last': '2026-09-08',
        'n': 19,
    },
    'TANK_DIRTY_MEG_JAPAN': {
        'label': 'MEG/Japan (dirty) · WS',
        'klass': 'Dirty',
        'route': 'MEG/Japan',
        'unit': 'ws',
        'cadence': 'daily',
        'pts': [[1549238400000, 44], [1703635200000, 55], [1782864000000, 275], [1783468800000, 320], [1784073600000, 400], [1784678400000, 385], [1785283200000, 385], [1785888000000, 400], [1786492800000, 500], [1787097600000, 510], [1787702400000, 600], [1788307200000, 650]],
        'first': '2019-02-04',
        'last': '2026-09-02',
        'n': 12,
    },
    'TANK_WEEKLY_VLCC_VLCCS_AVAILABLE_IN_MEG_NEXT_30_DAYS': {
        'label': 'VLCCs available in MEG next 30 days (weekly) · USD',
        'klass': 'WEEKLY VLCC',
        'route': 'VLCCs available in MEG next 30 days',
        'unit': 'usd',
        'cadence': 'weekly',
        'pts': [[1549238400000, 130], [1702425600000, 175], [1782864000000, 123], [1783468800000, 110], [1784073600000, 99], [1784678400000, 101], [1785283200000, 113], [1785888000000, 120], [1786492800000, 112], [1787097600000, 103], [1787702400000, 90], [1788307200000, 80]],
        'first': '2019-02-04',
        'last': '2026-09-02',
        'n': 12,
    },
    'COUNTS_BROKER_MEG_FIXTURE_COUNT': {
        'label': 'MEG Fixture Count',
        'klass': 'Counters',
        'route': 'MEG Fixture Count',
        'unit': 'count',
        'cadence': 'weekly',
        'pts': [[1654041600000, 152], [1764547200000, 146], [1767225600000, 157], [1769904000000, 153], [1772323200000, 128], [1775001600000, 65], [1777593600000, 73], [1780272000000, 117], [1782864000000, 160], [1785542400000, 128], [1788220800000, 74]],
        'first': '2022-06-01',
        'last': '2026-09-01',
        'n': 11,
    },
    'TANK_1_YEAR_T_C_VLCC': {
        'label': '1Y TC VLCC · USD',
        'klass': '1 Year T/C',
        'route': 'VLCC',
        'unit': 'usd',
        'cadence': 'daily',
        'pts': [[1499644800000, 40500], [1684886400000, 42500], [1782864000000, 105000], [1783468800000, 115000], [1784073600000, 120000], [1784678400000, 115000], [1785283200000, 115000], [1785888000000, 117000], [1786492800000, 117000], [1787097600000, 120000], [1787702400000, 120000], [1788307200000, 130000]],
        'first': '2017-07-10',
        'last': '2026-09-02',
        'n': 12,
    },
    'TANK_FUEL_OIL_VLCC_SKAW_SPORE': {
        'label': 'Fuel Oil VLCC SKAW/SPORE · USD',
        'klass': 'Fuel Oil',
        'route': 'SKAW/SPORE',
        'unit': 'usd',
        'cadence': 'daily',
        'pts': [[1526601600000, 3], [1554422400000, 3.8], [1583452800000, 4.8], [1611705600000, 3], [1641254400000, 3.75], [1670803200000, 8.4], [1703203200000, 5.7], [1736726400000, 5.2], [1767744000000, 6.5], [1787702400000, 22.75], [1787788800000, 22.5], [1787875200000, 22.5], [1788134400000, 22.5], [1788220800000, 22.6], [1788307200000, 22.7], [1788393600000, 25.5], [1788480000000, 27], [1788739200000, 27], [1788825600000, 27.5]],
        'first': '2018-05-18',
        'last': '2026-09-08',
        'n': 19,
    },
    'DRY_CAPESIZE_TCE_CONT_FAR_EAST': {
        'label': 'Capesize TCE Cont/Far East',
        'klass': 'Capesize',
        'route': 'Cont / Far East',
        'unit': 'usd/day',
        'pts': [[1725235200000, 57571], [1756771200000, 47156], [1787616000000, 75944], [1787702400000, 79333], [1787788800000, 79556], [1787875200000, 80417], [1788220800000, 82167], [1788307200000, 89167], [1788393600000, 91389], [1788480000000, 93111], [1788739200000, 93139], [1788825600000, 90833]],
        'first': '2024-09-02',
        'last': '2026-09-08',
        'n': 12,
        'tsid': 120655,
    },
    'DRY_CAPESIZE_AUSTRALIA_CHINA': {
        'label': 'Capesize Australia/China',
        'klass': 'Capesize',
        'route': 'Australia / China',
        'unit': 'usd/tonne',
        'pts': [[920246400000, 3.1], [951782400000, 6.15], [982886400000, 5.644], [1014336000000, 4.061], [1046131200000, 7.243], [1077667200000, 17.133], [1109203200000, 17.478], [1140739200000, 11.8], [1172448000000, 16.205], [1203984000000, 26.105], [1235520000000, 8.841], [1267056000000, 9.083], [1298592000000, 6.588], [1330387200000, 7.918], [1362009600000, 7.214], [1393545600000, 9.5], [1425254400000, 4.432], [1456790400000, 2.936], [1488326400000, 5.421], [1519862400000, 6.423], [1551398400000, 4.841], [1583107200000, 5.123], [1614643200000, 7.418], [1646179200000, 10.436], [1678060800000, 8.09], [1710115200000, 14.535], [1741651200000, 10.06], [1773187200000, 11.67], [1787616000000, 14.47], [1787702400000, 15.245], [1787788800000, 15.545], [1787875200000, 16.18], [1788220800000, 15.34], [1788307200000, 16.505], [1788393600000, 17.98], [1788480000000, 18.958], [1788739200000, 18.21], [1788825600000, 18.52]],
        'first': '1999-03-01',
        'last': '2026-09-08',
        'n': 38,
        'tsid': 10002,
    },
    'DRY_SUPRAMAX_TRANSATLANTIC_RV_AVG': {
        'label': 'Supramax Transatlantic RV (published avg)',
        'klass': 'Supramax',
        'route': 'Transatlantic Round Voyage',
        'unit': 'usd/day',
        'pts': [[1682985600000, 16554], [1714521600000, 16806], [1746057600000, 11279], [1777593600000, 19079], [1787616000000, 22492], [1787702400000, 22513], [1787788800000, 22532], [1787875200000, 22575], [1788220800000, 22544], [1788307200000, 22652], [1788393600000, 22929], [1788480000000, 23133], [1788739200000, 23186], [1788825600000, 23338]],
        'first': '2023-05-02',
        'last': '2026-09-08',
        'n': 14,
        'derivation': 'mean of TS 120132 + TS 120133, published-midpoint formula',
    },
}


@pytest.fixture(scope="module")
def tank_series():
    return FIXTURE_SERIES["TANK_VLCC_MEG_FEAST"]


@pytest.fixture(scope="module")
def frozen_series():
    return FIXTURE_SERIES["TANK_VLCC_MEG_FEAST_TCE"]


def day_delta(s):
    pts = s["pts"]
    return pts[-1][1] - pts[-2][1], pts[-2], pts[-1]


# ------------------------------------------------------------------ markers

def test_both_daily_caches_fetched_at_load_time():
    # wired into loadAllData exactly like the other caches (fetch, not embed)
    assert "data/derived/fearnleys_tanker_routes_daily.json" in C
    assert "data/derived/fearnleys_dry_routes_daily.json" in C
    assert "tankerRoutesDailyPromise" in C and "dryRoutesDailyPromise" in C
    # no inline embedding of the big JSON payloads (size safety)
    assert '"pts":[[' not in C


def test_no_rates_full_csv_in_tanker_routes_section():
    # the S3 render function must not reference the monthly CSV at all
    m = re.search(r"function renderFearnTank\(\).*?\nfunction setFearnTankKlass", C, re.S)
    assert m, "renderFearnTank block not found"
    block = m.group(0)
    assert "fearnpulse_rates_full" not in block
    assert "fearnSeriesCache()" not in block  # monthly cache untouchable in S3
    # S3 renders the DAILY cache
    assert "fearnleysTankerRoutesDaily" in block
    # global refcount: S9 museum + S1 overview tooltips keep their monthly-cache
    # notes, but the count must not grow back into S3
    assert C.count("fearnpulse_rates_full") < 5


def test_per_klass_tab_group_and_tiles():
    for klass in ["VLCC", "Suezmax", "Aframax", "Dirty", "1 Year T/C", "Fuel Oil", "WEEKLY VLCC", "Counters"]:
        assert f'data-tt-klass="{klass}"' in C or "'data-tklass'" in C
    assert "fearnTankKlassTabs" in C
    assert "fearnTankKlassSeries" in C
    # tiles carry label + unit + last + delta + first/last + live/frozen badge
    assert "fearn-tank-tile" in C
    assert "fearnStatusBadgeLive" in C
    assert "'LIVE'" in C and "'FROZEN'" in C


def test_live_frozen_classification_cutoff_is_labeled():
    m = re.search(r"var FROZEN_CUTOFF_MS = (\d+);[^\n]*", C)
    assert m, "FROZEN_CUTOFF_MS design constant missing"
    ms = int(m.group(1))
    # design constant: 2026-08-01 UTC midnight
    dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    assert (dt.year, dt.month, dt.day) == (2026, 8, 1)
    assert "design constant" in m.group(0)
    # frozen reason comes from the cache meta, verbatim channel
    assert "derivation_notes" in C
    assert "FDESK_TANKER_META.notes" in C


def test_taxonomy_switch_disclosure_from_cache_meta():
    # the UI must surface the cache's own wording (2023-05 taxonomy switch ->
    # tce twins end 2023-04-25), never invent another reason
    assert "derivation_notes" in C
    # live/frozen tooltip explains frozen state via the meta notes
    m = re.search(r"fearn-route-state", C)
    assert m
    assert "FDESK_TANKER_META" in C


def test_day_delta_math_on_real_fixture(tank_series, frozen_series):
    # live MEG/FEAST WS: real cache ends 660 (2026-09-07) -> 700 (2026-09-08)
    d, prev, last = day_delta(tank_series)
    assert prev[1] == 660 and last[1] == 700 and d == 40
    assert epoch_iso(last[0]) == "2026-09-08" and epoch_iso(prev[0]) == "2026-09-07"
    # frozen tce twin ends 0 -> 0 on 2023-04-24/25 (source publishes zeros)
    d2, prev2, last2 = day_delta(frozen_series)
    assert d2 == 0 and epoch_iso(last2[0]) == "2023-04-25"
    # negative delta rehearsal from the dry fixture
    dry = FIXTURE_SERIES["DRY_CAPESIZE_TCE_CONT_FAR_EAST"]
    d3, prev3, last3 = day_delta(dry)
    assert prev3[1] == 93139 and last3[1] == 90833
    assert d3 == last3[1] - prev3[1] == -2306


def test_dry_grid_series_and_first_dates():
    assert "renderFearnDryGrid" in C
    assert "fearnleysDryRoutesDaily" in C
    # per-series first dates render in tile meta (never imply uniform depth)
    assert "since ' + escapeHtml(String(s.first || ''))" in C
    assert "launch dates differ per series" in C
    # derived Supramax avg discloses its derivation channel
    assert "s.derivation" in C
    assert "derivation" in FIXTURE_SERIES["DRY_SUPRAMAX_TRANSATLANTIC_RV_AVG"]


def test_section_framework_flow_preserved():
    # 12 sub-sections; Newbuilding relocated to its own id 12
    assert "{ id: 12, name: 'Newbuilding' }" in C
    assert "{ id: 4,  name: 'Dry Routes' }" in C
    assert "id=\"fearnSec12\"" in C
    assert "if (id === 12)" in C
    # hide/show loop covers all 12
    assert "for (var i = 1; i <= 12; i++)" in C


def test_error_state_not_fabricated():
    assert "fearnErrorState" in C
    assert "no fabricated values are shown" in C


def test_click_through_daily_chart_and_hover_tooltips():
    assert "openFearnTankChart" in C and "drawFearnTankChart" in C
    assert "openFearnDryChart" in C and "drawFearnDryChart" in C
    # chart tooltips: date title + labeled value, honest no-interpolation note
    assert "title: function (c)" in C
    assert "daily print, no interpolation" in C
    # decimation is render-only: pointRadius 0 keeps the data daily
    assert "pointRadius: 0" in C


def test_tooltip_markers_on_every_new_element():
    # tiles + klass tabs + chart wraps + selects + state badges
    for marker in ["fearn-tank-tile", "fearn-dry-tile", "fearn-tank-klass-tab",
                   "fearn-tank-chart", "fearn-dry-chart",
                   "fearn-tank-chart-select", "fearn-dry-chart-select",
                   "fearn-route-state"]:
        assert f'data-tt-type="{marker}"' in C or f"'{marker}'" in C
    # tooltip bus branches render labeled rows (Last / Day Delta / First / Last
    # / Observations / Cadence / Unit) + the source line with built_utc
    for label in ["Last", "Day Delta", "First Obs", "Last Obs",
                  "Observations", "Cadence", "Unit", "State"]:
        assert f">{label}</span>" in C, f"tooltip row label missing: {label}"
    assert "fetched ' + escapeHtml(String(built))" in C or "fetched " in C
    # Phase 2c: the source line is one compact line, no endpoint, no click hint
    assert "Fearnleys daily assessments" in C
    assert "Fearnleys via fearnpulse market-api" not in C
    # Phase 2c: education-first interpretation rows on tiles + charts
    for row_label in ["What it is", "What moves it", "What it feeds"]:
        assert f">{row_label}</span>" in C, f"KB interpretation row missing: {row_label}"
    # the extracted tooltip renderer carries zero em dashes (house voice rule)
    m = re.search(r"function getCalculatedTooltip\(.*?\n      \}", C, re.S)
    assert m, "getCalculatedTooltip not found"
    assert chr(0x2014) not in m.group(0), "em dash inside getCalculatedTooltip"


def test_coverage_restamp_after_subsection_render():
    # sub-sections render late; renderFearnSection re-stamps coverage idempotently
    assert "annotateCoverageGaps('fearnleys')" in C


def test_no_hardcoded_route_values_in_new_code():
    # scan the new S3/S4 JS for baked-in data numerals from the fixtures
    m = re.search(r"function renderFearnTank\(\).*?function renderFearnDryGrid", C, re.S)
    assert m
    block = m.group(0)
    # every displayed number must flow from the cache: the tile value slot and
    # delta slot must use the formatter on parsed points, not literals
    assert "fearnFmtVal(d.last)" in block
    assert "fearnFmtVal(d.d)" in block
    # fixture numerals must not appear as data assignments (CSS weights/sizes
    # such as font-weight:700 or font-size:19px are design constants)
    for lit in ["660", "90833", "93139", "23338", "23186", "46009"]:
        pat = "(?<![\\w:.])" + lit + "(?![\\w;\"'])"
        assert not re.search(pat, block), \
            f"hardcoded data value {lit} leaked into new code"


def test_fixture_caches_match_real_files_when_present():
    if not TANKER_JSON.exists():
        pytest.skip("tanker daily cache not built yet")
    real = json.loads(TANKER_JSON.read_text(encoding="utf-8"))
    mv = real["series"]["TANK_VLCC_MEG_FEAST"]
    # Floor + recency, never equality: the daily harvest appends new prints,
    # so the tail moves every day (was [2026-09-08, 700] at snapshot time).
    assert mv["pts"][-1][0] >= 1788825600000  # on/after 2026-09-08
    assert mv["pts"][-2][0] < mv["pts"][-1][0]  # strictly chronological tail
    assert isinstance(mv["pts"][-1][1], (int, float)) and mv["pts"][-1][1] > 0
    frozen = real["series"]["TANK_VLCC_MEG_FEAST_TCE"]
    assert frozen["last"] == "2023-04-25"
    if DRY_JSON.exists():
        d = json.loads(DRY_JSON.read_text(encoding="utf-8"))
        cape = d["series"]["CAPESIZE_TCE_CONT_FAR_EAST"]
        assert cape["first"] == "2024-09-02"
        assert d["series"]["CAPESIZE_AUSTRALIA_CHINA"]["first"] == "1999-03-01"
        assert d["series"]["SUPRAMAX_TRANSATLANTIC_RV_AVG"].get("derivation")


# ------------------------------------------------- Phase 2c: education-first route tooltips
# The route knowledge base (FDESK_ROUTE_KB) must carry an entry for EVERY
# distinct (klass, route) pair in BOTH daily caches, so no tile ever falls back
# to a bare source line. Verified against the local caches at build time here.

def fn_region():
    m = re.search(r"function getCalculatedTooltip\(.*?\n      \}", C, re.S)
    assert m, "getCalculatedTooltip not found"
    return m.group(0)


def test_no_harvest_window_anywhere():
    assert "harvest window" not in C


def test_no_marketapi_in_index_html():
    assert "marketapi/TS" not in C
    assert "fearnpulse market-api" not in C


def test_no_click_the_tile_filler():
    assert "Click the tile" not in C
    assert "Click a tile for its full daily chart" not in C


def test_no_as_published_on_wording():
    assert "as published on" not in C


def test_kb_present_and_covered_by_caches():
    assert "var FDESK_ROUTE_KB" in C
    keys = set(re.findall(r"'([^']+)'(?=:\s*\{\s*what:)", C))
    assert len(keys) >= 80, f"route KB suspiciously small: {len(keys)}"
    pairs = set()
    for path in (TANKER_JSON, DRY_JSON):
        assert path.exists(), f"missing cache: {path}"
        data = json.loads(path.read_text(encoding="utf-8"))
        for s in data["series"].values():
            pairs.add((s.get("klass", ""), s.get("route", "")))
    missing = {(k, r) for k, r in pairs if f"{k}|{r}" not in keys}
    assert not missing, f"cache routes missing from KB: {sorted(missing)}"


def test_kb_entries_are_qualitative_three_part():
    # every KB entry defines what / drivers / affects, and entries never embed
    # numeric rate values (KB is qualitative; numbers come only from the cache)
    m = re.search(r"var FDESK_ROUTE_KB = \{(.*?)\n\};", C, re.S)
    assert m
    entries = re.findall(r"'[^']+'\s*:\s*\{\s*what:(.*?)\}", m.group(1), re.S)
    assert len(entries) >= 80
    for body in entries:
        for field in ("drivers:", "affects:"):
            assert field in body, f"KB entry missing {field}"


def test_klass_notes_cover_all_klasses():
    m = re.search(r"var FDESK_KLASS_NOTES = \{(.*?)\n\};", C, re.S)
    assert m, "FDESK_KLASS_NOTES missing"
    keys = set(re.findall(r"'([^']+)'(?=\s*:\s*')", m.group(1)))
    klasses = set()
    for path in (TANKER_JSON, DRY_JSON):
        data = json.loads(path.read_text(encoding="utf-8"))
        for s in data["series"].values():
            klasses.add(s.get("klass", ""))
    missing = klasses - keys
    assert not missing, f"klasses missing a plain note: {sorted(missing)}"


def test_state_values_plain_language():
    assert "Live: assessed daily, still publishing" in C
    assert "Frozen: source stopped publishing, history preserved" in C
    assert "LIVE — publishes into the current harvest window" not in C
    assert "FROZEN — last print predates the current harvest window" not in C


def test_frozen_tooltip_keeps_taxonomy_meta_wording():
    # frozen series keep the cache's own derivation_notes wording (verbatim)
    m = re.search(r"else if \(type === 'fearn-route-state'\) \{(.*?)\n        \}", C, re.S)
    assert m
    b = m.group(0)
    assert "FDESK_TANKER_META.notes" in b
    assert "metaNotes" in b


def test_klass_tab_tooltip_has_plain_group_sentence():
    m = re.search(r"else if \(type === 'fearn-tank-klass-tab'\) \{(.*?)\n        \}", C, re.S)
    assert m
    b = m.group(0)
    assert "FDESK_KLASS_NOTES" in b
    assert "shown" in b  # shown/archived counts retained
    assert "cache" not in b.lower()


def test_picker_tooltips_purpose_only():
    # the LAST occurrence of each marker is the tooltip-bus branch; read from there
    for marker, note in [("fearn-tank-chart-select", "Pick any route to replot its daily chart on the tanker panel."),
                         ("fearn-dry-chart-select", "Pick any dry route benchmark to replot its daily chart.")]:
        b = re.search(r"else if \(type === '" + marker + r"'\) \{(.*?)\n        \}", C, re.S)
        assert b, f"picker branch missing: {marker}"
        assert note in b.group(0)
        assert "cache" not in b.group(0).lower()


def test_source_line_compact_no_endpoint():
    assert "fearnpulse.com/api" not in C
    # fetched line kept
    assert "Fearnleys daily assessments" in C


def test_fn_zero_em_dash():
    assert chr(0x2014) not in fn_region()


# ------------------------------------------------- Phase 2b: all-zero exclusion
# Real trimmed sample of an all-zero branch: TANK_VLCC_CEYHAN_FEAST is all-zero
# over its FULL history (n=1353, every published value 0 — the source never
# published values in this branch; its USD/WS twin carries the real rate). The
# two points below are the real first + last rows of that branch.

ZERO_SERIES = {
    'TANK_VLCC_CEYHAN_FEAST': {
        'label': 'CEYHAN/FEAST · TCE',
        'klass': 'VLCC',
        'route': 'CEYHAN/FEAST',
        'unit': 'tce',
        'cadence': 'daily',
        'pts': [[1526601600000, 0], [1682380800000, 0]],  # trimmed: real first + last
        'first': '2018-05-18',
        'last': '2023-04-25',
        'n': 2,
    },
}


def js_is_all_zero(s):
    """Mirror of index.html fearnSeriesIsAllZero: true only when EVERY pt is 0."""
    return all(v == 0 for _, v in s["pts"])


def js_badge_state(s):
    """Mirror of index.html fearnBadgeState: zero | live | frozen."""
    if js_is_all_zero(s):
        return "zero"
    return "live" if (s["last"] >= "2026-08-01") else "frozen"


def test_zero_series_fixture_is_truly_all_zero():
    s = ZERO_SERIES["TANK_VLCC_CEYHAN_FEAST"]
    assert js_is_all_zero(s) is True
    # cross-check against the real cache when present: the branch is all-zero
    # over its FULL history there too (not just the trimmed sample)
    if TANKER_JSON.exists():
        real = json.loads(TANKER_JSON.read_text(encoding="utf-8"))
        full = real["series"]["TANK_VLCC_CEYHAN_FEAST"]
        assert len(full["pts"]) > 1000
        assert js_is_all_zero(full) is True


def test_all_zero_exclusion_logic_on_fixtures():
    zero = ZERO_SERIES["TANK_VLCC_CEYHAN_FEAST"]
    frozen = FIXTURE_SERIES["TANK_VLCC_MEG_FEAST_TCE"]
    live = FIXTURE_SERIES["TANK_VLCC_MEG_FEAST"]
    # exclusion decision mirrors fearnTankKlassSeries' filter
    keep = {k for k, s in (list(ZERO_SERIES.items()) + list(FIXTURE_SERIES.items()))
            if not js_is_all_zero(s)}
    assert "TANK_VLCC_CEYHAN_FEAST" not in keep      # all-zero -> excluded
    assert "TANK_VLCC_MEG_FEAST_TCE" in keep          # real frozen -> shown
    assert "TANK_VLCC_MEG_FEAST" in keep              # live -> shown
    # classification of the three shapes
    assert js_badge_state(zero) == "zero"
    assert js_badge_state(frozen) == "frozen"
    assert js_badge_state(live) == "live"


def test_real_cache_series_split_zero_frozen_live():
    if not TANKER_JSON.exists():
        pytest.skip("tanker daily cache not built yet")
    real = json.loads(TANKER_JSON.read_text(encoding="utf-8"))
    zero, frozen, live = [], [], []
    for k, s in real["series"].items():
        st = js_badge_state(s)
        {"zero": zero, "frozen": frozen, "live": live}[st].append(k)
    # measured Phase 2b reality: 126 series = 39 all-zero + 8 frozen-real + 79 live
    assert len(zero) == 39
    assert len(frozen) == 8
    assert len(live) == 79
    assert len(zero) + len(frozen) + len(live) == len(real["series"]) == 126
    # FROZEN badge only ever lands on series with real values that stopped
    # before the live window (the 2023-05 taxonomy-switch tce twins)
    for k in frozen:
        s = real["series"][k]
        assert s["last"] < "2026-08-01"
        assert any(v != 0 for _, v in s["pts"])
    # every frozen-real branch ends at the taxonomy switch date
    assert all(real["series"][k]["last"] == "2023-04-25" for k in frozen)


def test_s3_renderer_excludes_all_zero_series():
    m = re.search(r"function fearnTankKlassSeries\(klass\) \{.*?\n\}", C, re.S)
    assert m, "fearnTankKlassSeries block not found"
    assert "!fearnSeriesIsAllZero(s)" in m.group(0)
    # the exclusion helper is computed from loaded cache pts, not a list
    m2 = re.search(r"function fearnSeriesIsAllZero\(s\) \{.*?\n\}", C, re.S)
    assert m2, "fearnSeriesIsAllZero block not found"
    b = m2.group(0)
    assert "s.pts" in b
    assert "!== 0" in b


def test_s3_footer_discloses_archived_zero_series():
    # the honest footer line, verbatim
    assert ("archived route series not shown: the source published no values "
            "in these branches; the USD/WS twins of these routes are shown.") in C
    # computed from the cache at render time, not hardcoded
    assert "fearnTankArchivedCount" in C
    assert "fearnTankKlassZeroCount" in C
    assert "fearnTankArchived" in C


def test_badge_semantics_split_marker():
    m = re.search(r"function fearnBadgeState\(s\) \{.*?\n\}", C, re.S)
    assert m, "fearnBadgeState block not found"
    b = m.group(0)
    assert "fearnSeriesIsAllZero(s)" in b
    assert "fearnIsLive(s)" in b
    # the badge renders through the split, not raw fearnIsLive
    m2 = re.search(r"function fearnStatusBadgeLive\(s\) \{.*?\n\}", C, re.S)
    assert m2 and "fearnBadgeState(s)" in m2.group(0)
    # FROZEN tooltip keeps the taxonomy-switch wording from the cache meta
    assert "FDESK_TANKER_META.notes" in C


def test_klass_tab_counts_match_shown_series():
    # tab label counts = fearnTankKlassSeries(k).length (shown after exclusion),
    # not the cache index's all-inclusive kk.series count
    m = re.search(r"function renderFearnTank\(\).*?\nfunction setFearnTankKlass", C, re.S)
    assert m
    block = m.group(0)
    assert "var shown = fearnTankKlassSeries(k).length;" in block
    assert "kk.series != null" not in block


def test_dry_grid_all_zero_guard():
    m = re.search(r"function renderFearnDryGrid\(\).*?\nfunction openFearnDryChart", C, re.S)
    assert m
    block = m.group(0)
    assert "fearnSeriesIsAllZero" in block  # the guard is applied
    # dry note appends the same honest disclosure when any all-zero appear
    assert "dryArchived" in block
    # dry cache reality: 12/12 series carry real values (guard stays dormant)
    if DRY_JSON.exists():
        d = json.loads(DRY_JSON.read_text(encoding="utf-8"))
        zero = [k for k, s in d["series"].items() if js_is_all_zero(s)]
        assert zero == []


# =====================================================================
# Phase 2E: Indices-style 52W stats + range slider + zero-tile honesty
# =====================================================================

# ------------------------------------------------- 52W stat strip math
def js_fearn52_compute(pts, monthly=False):
    """Mirror of index.html fearn52Compute: 52W high/low, position %, YTD %,
    drawdown from the trailing-year peak, upside from the trough. The window
    anchors on the series' OWN last point (cache-derived), never wall-clock;
    full=true only when the trailing window actually spans ~a year."""
    DAY = 86400000
    vals = [(k, v) for k, v in pts if v is not None]
    if not vals:
        return None
    last_k, last_v = vals[-1]
    last_t = (datetime.strptime(last_k + "-01", "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000) if monthly else last_k
    win = []
    for k, v in vals:
        t = (datetime.strptime(k + "-01", "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000) if monthly else k
        if t >= last_t - 365 * DAY:
            win.append((k, v, t))
    hi = max(v for _, v, _ in win)
    lo = min(v for _, v, _ in win)
    span = last_t - win[0][2]
    full = span >= 300 * DAY
    denom = hi - lo
    pos = ((last_v - lo) / denom * 100) if (full and denom > 0) else None
    year = datetime.fromtimestamp(last_t / 1000, tz=timezone.utc).year
    jan1 = datetime(year, 1, 1, tzinfo=timezone.utc).timestamp() * 1000
    ytd_base = None
    for k, v in reversed(vals):
        t = (datetime.strptime(k + "-01", "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000) if monthly else k
        if t < jan1:
            ytd_base = v
            break
    ytd = ((last_v - ytd_base) / ytd_base * 100) if ytd_base else None
    dd = ((last_v - hi) / abs(hi) * 100) if (full and hi != 0) else None
    up = ((last_v - lo) / abs(lo) * 100) if (full and lo != 0) else None
    return {"high": hi, "low": lo, "pos": pos, "ytd": ytd, "dd": dd, "up": up,
            "full": full, "last": last_v, "n_win": len(win)}


def test_52w_stats_on_fixture_with_known_values():
    # Dense daily fixture ending 2026-09-08 with a known 2025 baseline print:
    # mirrors the real daily cache shape (~365 pts in the trailing year).
    DAY = 86400000
    base = 1788825600000  # 2026-09-08 UTC midnight (same epoch family as caches)
    # 401 daily pts whose LAST print lands exactly on the anchor date; the
    # trailing-year window (t >= last - 365d) then covers indices 35..400.
    pts = [[base - (401 - i) * DAY, 100.0 + i] for i in range(401)]
    pts[-1][1] = 700.0
    pts[35][1] = 675.0   # the last print before Jan 1 2026 in this layout
    st = js_fearn52_compute(pts)
    assert st is not None
    assert st["last"] == 700.0
    in_win = [(k, v) for k, v in pts if k >= base - 365 * DAY]
    assert st["high"] == max(v for _, v in in_win)
    assert st["low"] == min(v for _, v in in_win)
    assert st["full"] is True
    denom = st["high"] - st["low"]
    assert abs(st["pos"] - (700 - st["low"]) / denom * 100) < 1e-9
    # YTD base = last print before Jan 1 of the last point's year
    # (in this layout that is index 150 = 2025-12-31, value 250)
    assert abs(st["ytd"] - (700 - 250.0) / 250.0 * 100) < 1e-9
    # drawdown from the trailing-year peak: 700 is the peak, so 0.0
    assert abs(st["dd"]) < 1e-9
    # upside from the trough
    assert abs(st["up"] - (700 - st["low"]) / abs(st["low"]) * 100) < 1e-9
    # the real MEG/FEAST WS fixture (strided) agrees on the window math itself:
    # its trailing-year window starts at the first print within 365d of the end
    s = FIXTURE_SERIES["TANK_VLCC_MEG_FEAST"]
    st2 = js_fearn52_compute(s["pts"])
    assert st2["last"] == 700
    in_win2 = [(k, v) for k, v in s["pts"] if k >= 1788825600000 - 365 * DAY]
    assert st2["high"] == max(v for _, v in in_win2)
    assert st2["low"] == min(v for _, v in in_win2)


def test_52w_stats_young_series_honest_n_a():
    # A series with < ~300d of history (DRY_CAPESIZE_TCE_CONT_FAR_EAST starts
    # 2024-09-02 but its last-year window covers it fully -> full) vs a truly
    # young trimmed sample: n/a paths must come from full=False, not crashes.
    young = {"pts": [[1782864000000, 120], [1785542400000, 130], [1788825600000, 125]]}
    st = js_fearn52_compute(young["pts"])
    assert st["full"] is False
    assert st["pos"] is None and st["dd"] is None and st["up"] is None
    # the strip renders the honest 'n/a' (no em dash) for those cells
    html = fearn52_strip_html(st)
    assert "n/a" in html
    assert chr(0x2014) not in html
    # 52W High/Low also degrade to n/a when the year window is not real
    assert "n/a / n/a" in html


def fearn52_strip_html(st):
    """Mirror of index.html fearn52StripHtml structure (labels + values)."""
    def f(v, signed=False, pct=False):
        if v is None:
            return "n/a"
        s = f"{v:.1f}%" if pct else f"{v:,}"
        return ("+" + s) if (signed and v > 0) else s
    hl = f"{f(st['high'])} / {f(st['low'])}" if st["full"] else "n/a / n/a"
    pos = f"{st['pos']:.1f}%" if st["pos"] is not None else "n/a"
    ytd = f(st["ytd"], True, True) if st["ytd"] is not None else "n/a"
    up = f(st["up"], True, True) if st["up"] is not None else "n/a"
    dd = f(st["dd"], True, True) if st["dd"] is not None else "n/a"
    return f"{hl}|{pos}|{ytd}|{up}|{dd}"


def test_52w_strip_labels_and_honest_n_a():
    # dense full-stats case
    DAY = 86400000
    base = 1788825600000
    pts = [[base - (400 - i) * DAY, 100.0 + i] for i in range(400)]
    pts[-1][1] = 700.0
    st = js_fearn52_compute(pts)
    row = fearn52_strip_html(st).split("|")
    assert len(row) == 5
    assert row[1].endswith("%")
    assert row[2].startswith(("+", "-"))
    # every value cell numeric or the honest n/a; never an em dash placeholder
    for cell in row:
        assert cell == "n/a" or cell[0] in "+-0123456789n"
    # labels exist in index.html for all five tiles with plain-language tooltips
    for label in ["52W High / Low", "52W Position", "YTD %", "From 52W Low", "From 52W High"]:
        assert label in C


def test_52w_marker_and_strip_wired_on_all_five_panels():
    # HTML anchors: one strip + one slider per big chart
    for el in ["fearnTcStats", "fearnTankStats", "fearnDryStats",
               "fearnLngStats52", "fearnLpgStats52"]:
        assert f'id="{el}"' in C, f"missing stat strip anchor {el}"
    for pfx in ["fearnTcRange", "fearnTankRange", "fearnDryRange",
                "fearnLngRange", "fearnLpgRange"]:
        assert f'id="{pfx}Start"' in C and f'id="{pfx}End"' in C
        assert f'id="{pfx}Fill"' in C and f'id="{pfx}Label"' in C
    # JS engine: compute + strip + slider + reference-line helpers all present
    for fn in ["function fearn52Compute(", "function fearn52StripHtml(",
               "function fearnRangeInit(", "function fearnRangeSetWin(",
               "function fearn52RefDatasets("]:
        assert fn in C
    # each renderer feeds its own strip + slider
    m = re.search(r"function drawFearnTankChart\(\).*?\n\}", C, re.S)
    assert m and "fearn52Compute(pts" in m.group(0) and "fearnRangeInit('fearnTankRange'" in m.group(0)
    m = re.search(r"function drawFearnDryChart\(\).*?\n\}", C, re.S)
    assert m and "fearn52Compute(pts" in m.group(0) and "fearnRangeInit('fearnDryRange'" in m.group(0)
    m = re.search(r"function renderFearnTc\(\).*?\nfunction onFearnTcClass", C, re.S)
    assert m and "fearnRangeInit('fearnTcRange'" in m.group(0)
    m = re.search(r"function renderFearnGas\(kind\).*?\nfunction onFearnGasSel", C, re.S)
    assert m and "fearnRangeInit(prefix" in m.group(0)
    # default window is 1Y per brief
    assert "'1Y'" in C and "FDESK_WIN_DEFS" in C
    assert "['1M', 30], ['3M', 91], ['6M', 182], ['YTD', 'ytd'], ['1Y', 365], ['2Y', 730], ['Max', 'max']" in C


def test_52w_reference_lines_dashed_not_in_tooltips_or_legend_noise():
    # dashed constant datasets exist; hidden from legends where they'd clutter
    m = re.search(r"function fearn52RefDatasets\([\s\S]*?\n\}", C)
    assert m
    b = m.group(0)
    assert "borderDash" in b
    assert "52W high (trailing year)" in b and "52W low (trailing year)" in b
    # they must NOT emit tooltip rows: every chart filters 52W datasets out of
    # the tooltip (or only allows datasetIndex 0)
    assert "filter: function (item) { return item.datasetIndex === 0; }" in C
    assert "item.text.indexOf('52W') !== 0" in C or "item.dataset.label.indexOf('52W') !== 0" in C
    # no em dash in the ref-line labels
    assert chr(0x2014) not in b


# ------------------------------------------------- range slider (view-only)
def js_slider_window(rows_ms, mode, ytd_year, day=86400000):
    """Mirror of the fearnRangeInit window math: returns (startIdx, endIdx)."""
    last = rows_ms[-1]
    if mode == "Max":
        return 0, len(rows_ms) - 1
    if mode == "YTD":
        start_ms = datetime(ytd_year, 1, 1, tzinfo=timezone.utc).timestamp() * 1000
    else:
        days = {"1M": 30, "3M": 91, "6M": 182, "1Y": 365, "2Y": 730}[mode]
        start_ms = last - days * day
    s = next((i for i, ms in enumerate(rows_ms) if ms >= start_ms), len(rows_ms) - 1)
    return s, len(rows_ms) - 1


def test_slider_view_window_logic_no_pts_mutation():
    # 120 weekly pts ending 2026-09-08 (deterministic, cache-epoch family)
    DAY = 86400000
    last = 1788825600000  # 2026-09-08
    rows = [(last - (119 - i) * 7 * DAY, 100.0 + i) for i in range(120)]
    ms = [r[0] for r in rows]
    before = list(rows)
    s, e = js_slider_window(ms, "1Y", 2026)
    assert e == len(rows) - 1
    assert s == next(i for i, m0 in enumerate(ms) if m0 >= ms[-1] - 365 * DAY)
    # view slice only: rows untouched (no data mutation, just a view)
    vis = rows[s:e + 1]
    assert rows == before and len(vis) < len(rows)
    # Max = everything, YTD = from Jan 1 of the last point's year
    s2, e2 = js_slider_window(ms, "Max", 2026)
    assert (s2, e2) == (0, len(rows) - 1)
    s3, e3 = js_slider_window(ms, "YTD", 2026)
    assert s3 >= 0 and e3 == len(rows) - 1
    assert ms[s3] >= datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp() * 1000
    # engine slices via Array.slice (a view), never splices the source rows
    m = re.search(r"function fearnWindowSlice\([\s\S]*?\n\}", C)
    assert m and ".slice(" in m.group(0) and "splice" not in m.group(0)
    # the five renderers plot from a sliced window; the underlying pts arrays
    # are only ever read (slice/map), never written
    for fn_name in ["drawFearnTankChart", "drawFearnDryChart"]:
        m = re.search(r"function " + fn_name + r"\([\s\S]*?\n\}", C)
        assert m
        assert ".splice(" not in m.group(0) and ".push(" not in m.group(0)
    # dual-handle crossing is normalized (start<=end) inside the engine
    m = re.search(r"function fearnRangeInit\([\s\S]*?function fearnRangeSetWin", C, re.S)
    assert m and "if (s > e)" in m.group(0)


# ------------------------------------------------- zero-tile honesty (2D)
def js_epoch_to_iso(ms):
    """Mirror of fearnEpochToIso in index.html."""
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


def js_trailing_zero_tail(pts):
    tail = 0
    for _, v in reversed(pts):
        if v == 0:
            tail += 1
        else:
            break
    return tail


def js_badge_state_2e(s):
    """Mirror of the 2E fearnBadgeState: zero | discontinued | live | frozen."""
    if js_is_all_zero(s):
        return "zero"
    tail = js_trailing_zero_tail(s["pts"])
    if 0 < tail >= 20:
        return "discontinued"
    return "live" if (s["last"] >= "2026-08-01") else "frozen"


DISC_FIXTURE = {
    "TANK_TEST_DISC": {
        "label": "TEST Disc · WS", "klass": "Aframax", "route": "TEST/DISC",
        "unit": "ws", "cadence": "daily",
        "pts": [[1651363200000, 250], [1651449600000, 245]]
        + [[1651536000000 + i * 86400000, 0] for i in range(25)],
        "first": "2022-05-01", "last": "2022-05-30", "n": 27,
    },
}


def test_trailing_zero_badge_classification():
    live = FIXTURE_SERIES["TANK_VLCC_MEG_FEAST"]           # real tail values
    frozen = FIXTURE_SERIES["TANK_VLCC_MEG_FEAST_TCE"]     # real values, ended
    disc = DISC_FIXTURE["TANK_TEST_DISC"]                   # 25 trailing zeros
    zero = ZERO_SERIES["TANK_VLCC_CEYHAN_FEAST"]            # all-zero
    assert js_badge_state_2e(live) == "live"
    assert js_badge_state_2e(frozen) == "frozen"
    assert js_badge_state_2e(disc) == "discontinued"
    assert js_badge_state_2e(zero) == "zero"
    # short zero runs (normal pauses between assessments) never flip the state:
    # a 5-zero gap inside a current series must still classify live (real
    # values follow and the last print reaches the live week), and a 2-zero
    # tail must stay live-by-date (tail below the discontinued threshold).
    short = {k: dict(v) if isinstance(v, list) else v for k, v in disc.items()}
    aug1 = 1785542400000  # 2026-08-01 UTC midnight = FROZEN_CUTOFF_MS
    short["pts"] = (
        [(aug1, 250.0)]
        + [(aug1 + (1 + i) * 86400000, 0) for i in range(5)]
        + [(aug1 + (6 + i) * 86400000, 260.0 + i) for i in range(25)]
    )
    short["last"] = js_epoch_to_iso(short["pts"][-1][0])
    assert js_badge_state_2e(short) == "live"
    short2 = dict(short)
    short2["pts"] = short["pts"] + [(aug1 + 31 * 86400000, 0), (aug1 + 32 * 86400000, 0)]
    short2["last"] = js_epoch_to_iso(short2["pts"][-1][0])
    assert js_badge_state_2e(short2) == "live"
    # index.html uses a render-time detector (no hardcoded series list)
    assert "function fearnTrailingZeroTail(" in C
    assert "FDESK_DISC_MIN_TAIL" in C
    m = re.search(r"function fearnDiscontinuedOf\(s\)[\s\S]*?\n\}", C)
    assert m and "fearnTrailingZeroTail" in m.group(0)
    # badge emits DISCONTINUED (grey = muted family, same styling as FROZEN)
    m = re.search(r"function fearnStatusBadgeLive\(s\)[\s\S]*?\n\}", C)
    assert m and "DISCONTINUED" in m.group(0) and "var(--text-muted)" in m.group(0)


def test_real_cache_discontinued_census_matches_2d():
    """The render-time detector must flag exactly the 2D-census six series
    (long trailing-zero tails) and nothing else in either daily cache."""
    expected = {
        "TANK_SUEZMAX_NOVO_USG",
        "TANK_AFRAMAX_PRIMORSK_USAC",
        "TANK_AFRAMAX_PRIMORSK_UKC",
        "TANK_AFRAMAX_PRIMORSK_MED",
        "TANK_AFRAMAX_DEMURRAGE_BALTIC",
        "TANK_AFRAMAX_KOZMINO_NORTH_CHINA_USD",
    }
    for path in (TANKER_JSON, DRY_JSON):
        if not path.exists():
            pytest.skip(f"{path.name} not built yet")
        data = json.loads(path.read_text(encoding="utf-8"))
        flagged = set()
        for code, s in data["series"].items():
            if js_is_all_zero(s):
                continue
            tail = js_trailing_zero_tail(s["pts"])
            if tail >= 20:
                flagged.add(code)
        if path == TANKER_JSON:
            assert flagged == expected, (
                f"discontinued census drift: {sorted(flagged ^ expected)}")
            # each flagged tile shows the last REAL print, not a zero placeholder
            for code in expected:
                s = data["series"][code]
                tail = js_trailing_zero_tail(s["pts"])
                lnz = s["pts"][len(s["pts"]) - tail - 1]
                assert lnz[1] > 0


def test_discontinued_tile_and_tooltip_copy():
    # tile value + 'as of' sub-line instead of a zero Last and a fake delta
    assert "fearnFmtVal(disc.lastVal)" in C
    assert "as of ' + escapeHtml(disc.lastDate)" in C
    # day-delta excluded: the tile branch swaps in the as-of line, the tooltip
    # marks Day Delta n/a for discontinued series
    assert "n/a (no live values in the recent rows)" in C
    # tooltip note: education-first, no em dash, no QC/jargon narration
    assert "The source stopped publishing this assessment: since " in C
    assert "the rows it sends carry no values" in C
    assert "this route's USD or Worldscale twin is still published" in C
    for banned in ["inference tested", "fit disclosure QC", "R2 gate narration"]:
        assert banned not in C
    # badge tooltip branch explains discontinued honestly
    assert "Discontinued Series" in C
    assert "Day-to-day change is not shown because the recent rows carry no live values" in C
    # no em dashes in any of the new discontinued copy
    for marker in ["n/a (no live values in the recent rows)",
                   "The source stopped publishing this assessment: since ",
                   "Day-to-day change is not shown"]:
        i = C.find(marker)
        assert i >= 0
        window = C[max(0, i - 400): i + 400]
        assert chr(0x2014) not in window, f"em dash near {marker!r}"


def test_frozen_tile_tooltips_and_wording_unchanged():
    # 2c frozen-tile education-first wording must survive the 2E additions
    assert "Frozen: source stopped publishing, history preserved" in C
    assert "The source stopped publishing this assessment (last print " in C
    assert "this route's USD or Worldscale twin is still published" in C
    # 2b all-zero exclusion still in force on both grids
    m = re.search(r"function fearnTankKlassSeries\(klass\) \{.*?\n\}", C, re.S)
    assert m and "!fearnSeriesIsAllZero(s)" in m.group(0)
    m = re.search(r"function renderFearnDryGrid\(\).*?\nfunction openFearnDryChart", C, re.S)
    assert m and "fearnSeriesIsAllZero" in m.group(0)
    # 8 skipped derivations surface only as the frozen-tile note (no QC narration added)
    assert "skipped_with_reason" not in C or C.count("skipped_with_reason") <= 1


def test_no_code_speak_in_visible_copy():
    """Standing gate: banned identifiers/paths must not appear in visible HTML
    (script + style content stripped) or in the JS strings that render into
    the DOM for the fixed defects."""
    body = re.sub(r"<script(?![^>]*\bsrc=)[^>]*>.*?</script>", "", C, flags=re.S)
    body = re.sub(r"<style[^>]*>.*?</style>", "", body, flags=re.S)
    for banned in ["editorial_estimate_diagnostic", "portwatch_port_congestion.csv",
                   "chokepoint_transit_metrics.csv", "generate_ton_mile_matrix.py",
                   "fearnpulse_rates_full.csv", "macro_health_score_backtest.csv",
                   "bdry_liquidity.csv", "bwet_liquidity.csv",
                   "port_lineups_active.csv"]:
        assert banned not in body, f"code-speak in visible copy: {banned}"
    # gas_extra jargon gone from the LNG/LPG panel title
    assert "gas_extra overlay on right axis" not in C
    # the two deal tables never print undefined/nan: fixed renderers guard them
    assert "String(x).trim().toLowerCase() === 'nan'" in C
    assert "Number.isFinite(Number(FEARNLEYS_CONTROLLER.snpPage))" in C
    # crisis callout speaks human: the stable invariant is the honest
    # "editorial estimate" attribution in the Red Sea callout region (the
    # exact sentence copy is free to evolve; the estimate provenance is not).
    callout = re.search(r"Red Sea Rerouting Crisis.{0,600}", C, re.S)
    assert callout, "Red Sea crisis callout missing"
    assert "editorial estimate" in callout.group(0).lower()
    assert "editorial estimate" in C  # JS-side estimate provenance string too

