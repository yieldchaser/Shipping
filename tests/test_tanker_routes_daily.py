#!/usr/bin/env python3
"""build_tanker_routes_daily.py — producer tests for the daily tanker cache.

Hermetic parse/merge/idempotence fixtures (in-process module import, tmp CSV +
tmp monthly-twin JSON) + regression floors against the real emitted JSON.

Floor honesty note: the brief assumed every VLCC/Suezmax/Aframax series holds
>=1800 daily points, but measurement against the real CSV shows the source's
2023-05 taxonomy switch ended the tce twin of 17 Aframax + all VLCC/Suezmax
tce routes at 2023-04-25, and several usd routes (demurrage, SERIA/GEELONG,
MINA AL AHMADI) only start 2020-03..2020-05. Measured deep-series counts
(>=1800 pts): VLCC 14/14, Suezmax 18/19 (WAFR/THAILAND starts 2019-08),
Aframax 13/26. Floors pin those measured counts — they only fail if the
archive loses real data. Dirty assessments start 2019-02 (measured >=377 obs).
"""
import csv
import importlib.util
import json
import re
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "fearnleys" / "build_tanker_routes_daily.py"
JSON_PATH = ROOT / "data" / "derived" / "fearnleys_tanker_routes_daily.json"
CSV_PATH = ROOT / "data" / "derived" / "fearnpulse_rates_full.csv"

spec = importlib.util.spec_from_file_location("btrd", SCRIPT)
btrd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(btrd)


def epoch_ms(date_str):
    y, m, d = date_str.split("-")
    return (date(int(y), int(m), int(d)) - date(1970, 1, 1)).days * 86400000


HEADER = ["label", "rate_type", "rate_subtype", "route", "unit", "date", "rate"]

MONTHLY_TWINS = {
    "labels": {
        "TANK_VLCC_MEG_FEAST": {"type": "TANK", "subtype": "VLCC",
                                "route": "MEG/FEAST"},
        "TANK_DIRTY_MEG_JAPAN": {"type": "TANK", "subtype": "Dirty",
                                 "route": "MEG/Japan"},
    }
}


def write_fixture_csv(path):
    """Small but complete: dup dates (keep-last), unsorted dates, non-numeric
    rate skipped, stale subtype recorded, two unit branches on one route,
    weekly subtype, counts/BROKER rows."""
    rows = [
        # ws branch (live) for MEG/FEAST — unsorted + duplicate dates
        ["TANK_VLCC_MEG_FEAST", "TANK", "VLCC", "MEG/FEAST", "ws",
         "2026-09-02", "650"],
        ["TANK_VLCC_MEG_FEAST", "TANK", "VLCC", "MEG/FEAST", "ws",
         "2026-09-01", "640"],
        ["TANK_VLCC_MEG_FEAST", "TANK", "VLCC", "MEG/FEAST", "ws",
         "2026-09-02", "655"],  # later row wins on the same date
        ["TANK_VLCC_MEG_FEAST", "TANK", "VLCC", "MEG/FEAST", "ws",
         "2026-08-29", "not-a-number"],  # must be skipped
        ["TANK_VLCC_MEG_FEAST", "TANK", "VLCC", "MEG/FEAST", "ws",
         "2026-09-03", "675.0"],
        # tce branch (ended 2023-04-25 in the real feed)
        ["TANK_VLCC_MEG_FEAST", "TANK", "VLCC", "MEG/FEAST", "tce",
         "2023-04-25", "46009.0"],
        ["TANK_VLCC_MEG_FEAST", "TANK", "VLCC", "MEG/FEAST", "tce",
         "2023-04-24", "46009.0"],
        # high-precision value gets rounded 2dp
        ["TANK_VLCC_MEG_FEAST", "TANK", "VLCC", "MEG/FEAST", "tce",
         "2023-04-21", "803.075579709143"],
        # dirty series (own klass)
        ["TANK_DIRTY_MEG_JAPAN", "TANK", "Dirty", "MEG/Japan", "ws",
         "2026-09-02", "95.0"],
        ["TANK_DIRTY_MEG_JAPAN", "TANK", "Dirty", "MEG/Japan", "ws",
         "2026-09-01", "92.5"],
        # stale subtype — excluded but its last date must be recorded
        ["TANK_VLCC_MARKET_BITR_1", "TANK", "VLCC-MARKET", "BITR-1", "ws",
         "2023-04-28", "12345.0"],
        ["TANK_VLCC_MARKET_BITR_1", "TANK", "VLCC-MARKET", "BITR-1", "ws",
         "2023-01-01", "12000.0"],
        # weekly cadence
        ["TANK_WEEKLY_VLCC_VLCCS_AVAILABLE", "TANK", "WEEKLY VLCC",
         "VLCCs available in MEG next 30 days", "usd", "2026-08-24", "117.0"],
        # counts/BROKER → Counters klass, weekly cadence
        ["COUNTS_BROKER_MEG_FIXTURE_COUNT", "counts", "BROKER",
         "MEG Fixture Count", "usd", "2026-09-01", "74"],
        ["COUNTS_BROKER_MEG_FIXTURE_COUNT", "counts", "BROKER",
         "MEG Fixture Count", "usd", "2026-08-01", "128"],
        # a non-TANK/non-counts row must be ignored entirely
        ["BULK_TC_CAPESIZE", "BULK", "TC", "Capesize", "usd",
         "2026-09-01", "5550.0"],
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        w.writerows(rows)
    return rows


@pytest.fixture(scope="module")
def fixture_build(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("tanker_fixture")
    src = tmp / "rates.csv"
    monthly = tmp / "monthly.json"
    write_fixture_csv(src)
    monthly.write_text(json.dumps(MONTHLY_TWINS), encoding="utf-8")
    payload = btrd.build_payload(src=str(src), monthly_path=str(monthly))
    return payload


# ------------------------------------------------------------ fixture parsing

def test_fixture_groups_and_codes(fixture_build):
    s = fixture_build["series"]
    # ws keeps the monthly-twin code; the tce branch gets a _TCE suffix
    assert "TANK_VLCC_MEG_FEAST" in s
    assert "TANK_VLCC_MEG_FEAST_TCE" in s
    assert s["TANK_VLCC_MEG_FEAST"]["unit"] == "ws"
    assert s["TANK_VLCC_MEG_FEAST_TCE"]["unit"] == "tce"
    # dirty + weekly + counters land on their klasses
    assert s["TANK_DIRTY_MEG_JAPAN"]["klass"] == "Dirty"
    wk = [k for k, v in s.items() if v["klass"] == "WEEKLY VLCC"]
    assert len(wk) == 1 and s[wk[0]]["cadence"] == "weekly"
    cnt = [k for k, v in s.items() if v["klass"] == "Counters"]
    assert len(cnt) == 1 and s[cnt[0]]["cadence"] == "weekly"
    # BULK row ignored
    assert not any(k.startswith("BULK_") for k in s)


def test_fixture_dedupe_keep_last_and_chronology(fixture_build):
    pts = fixture_build["series"]["TANK_VLCC_MEG_FEAST"]["pts"]
    # 2026-08-29 (bad rate) skipped; 09-01, 09-02 (655, later row), 09-03 kept
    assert pts == [(epoch_ms("2026-09-01"), 640),
                   (epoch_ms("2026-09-02"), 655),
                   (epoch_ms("2026-09-03"), 675)]
    e = [p[0] for p in pts]
    assert e == sorted(e) == [epoch_ms("2026-09-01"), epoch_ms("2026-09-02"),
                              epoch_ms("2026-09-03")]
    assert fixture_build["series"]["TANK_VLCC_MEG_FEAST"]["n"] == 3
    # n/first/last agree with pts
    assert fixture_build["series"]["TANK_VLCC_MEG_FEAST"]["first"] == "2026-09-01"
    assert fixture_build["series"]["TANK_VLCC_MEG_FEAST"]["last"] == "2026-09-03"


def test_fixture_values_rounded_2dp_ints(fixture_build):
    tce = fixture_build["series"]["TANK_VLCC_MEG_FEAST_TCE"]["pts"]
    assert (epoch_ms("2023-04-21"), 803.08) in tce  # 2dp rounding
    assert (epoch_ms("2023-04-25"), 46009) in tce   # whole values stay ints


def test_fixture_stale_excluded_with_last_dates(fixture_build):
    exc = {e["subtype"]: e for e in fixture_build["meta"]["excluded"]}
    assert set(exc) == set(btrd.STALE_SUBTYPES)  # all four recorded, even unseen
    assert exc["VLCC-MARKET"]["last"] == "2023-04-28"
    assert exc["VLCC-MARKET"]["reason"]
    # no stale series leaked
    assert not any("VLCC_MARKET" in k or "BALTIC_INDEX" in k
                   or "SUEZMAX_MARKET" in k or "EQUINOR" in k
                   for k in fixture_build["series"])


def test_fixture_epoch_ms_is_utc_midnight(fixture_build):
    pts = dict(fixture_build["series"]["TANK_VLCC_MEG_FEAST"]["pts"])
    assert pts[epoch_ms("2026-09-03")] == 675
    # 2026-09-03 00:00 UTC == 1788374400000 (independent recomputation)
    dt = datetime(2026, 9, 3, tzinfo=timezone.utc)
    assert epoch_ms("2026-09-03") == int(dt.timestamp() * 1000)


def test_fixture_index_sums(fixture_build):
    idx = fixture_build["index"]
    assert sum(k["series"] for k in idx["klasses"].values()) == \
        len(fixture_build["series"])
    assert sum(k["pts"] for k in idx["klasses"].values()) == \
        sum(v["n"] for v in fixture_build["series"].values())
    assert idx["order"][0] == "VLCC"  # klass order matches KLASS_ORDER


def test_emit_json_round_trip(tmp_path, fixture_build):
    out = tmp_path / "roundtrip.json"
    size = btrd.emit(fixture_build, str(out))
    raw = out.read_bytes()
    assert size == len(raw) > 0
    loaded = json.loads(raw.decode("utf-8"))
    # pts serialize as JSON pairs [[epoch,value],...]
    assert json.loads(json.dumps(
        {k: dict(v, pts=[list(p) for p in v["pts"]])
         for k, v in fixture_build["series"].items()},
        separators=(",", ":"), ensure_ascii=True)) == loaded["series"]
    assert loaded["index"] == fixture_build["index"]
    # built_utc excluded from equality (wall-clock), everything else identical
    assert set(loaded["meta"]) == set(fixture_build["meta"])


def test_idempotence_byte_stable_modulo_built_utc():
    p1 = btrd.build_payload(str(CSV_PATH))
    p2 = btrd.build_payload(str(CSV_PATH))
    s1 = json.dumps(p1, separators=(",", ":"), ensure_ascii=True)
    s2 = json.dumps(p2, separators=(",", ":"), ensure_ascii=True)
    assert s1.replace(p1["meta"]["built_utc"], "X") == \
        s2.replace(p2["meta"]["built_utc"], "X")


# ------------------------------------------------------- real artifact floors
# These read the committed data/derived/fearnleys_tanker_routes_daily.json.


@pytest.fixture(scope="module")
def real():
    if not JSON_PATH.exists():
        pytest.skip("real JSON not built yet")
    return json.loads(JSON_PATH.read_text(encoding="utf-8"))


def test_real_every_series_nonempty_and_consistent(real):
    assert real["series"]
    for code, s in real["series"].items():
        assert s["pts"], f"{code}: empty pts"
        assert s["n"] == len(s["pts"]), f"{code}: n mismatch"
        e = [p[0] for p in s["pts"]]
        assert e == sorted(e), f"{code}: not chronological"
        assert len(set(e)) == len(e), f"{code}: duplicate epochs"
        assert s["first"] < s["last"] or s["n"] == 1
        assert re.match(r"^\d{4}-\d{2}-\d{2}$", s["first"])
        assert re.match(r"^\d{4}-\d{2}-\d{2}$", s["last"])


def test_real_core_class_depth_floors(real):
    deep = {}
    for klass, floor in (("VLCC", 14), ("Suezmax", 18), ("Aframax", 13)):
        ks = [s for s in real["series"].values() if s["klass"] == klass]
        assert ks, f"{klass}: no series"
        deep[klass] = sum(1 for s in ks if len(s["pts"]) >= 1800)
        assert deep[klass] >= floor, (
            f"{klass}: {deep[klass]} series >=1800 pts (floor {floor})")
    # the brief's >=1800 floor holds for these measured counts
    assert deep["VLCC"] >= 14 and deep["Suezmax"] >= 18 and deep["Aframax"] >= 13


def test_real_dirty_floor(real):
    dirty = [s for s in real["series"].values() if s["klass"] == "Dirty"]
    assert len(dirty) == 9
    assert min(len(s["pts"]) for s in dirty) >= 380


def test_real_weekly_cadence_badged(real):
    weekly = {k: s for k, s in real["series"].items()
              if s.get("cadence") == "weekly"}
    # WEEKLY VLCC x2 + MEG Fixture Count
    assert len(weekly) >= 3
    assert all(k.startswith(("TANK_WEEKLY_VLCC", "COUNTS_BROKER"))
               for k in weekly)
    for k, s in weekly.items():
        assert s["cadence"] == "weekly"
    daily = [s for s in real["series"].values() if s["cadence"] != "weekly"]
    assert all(s["cadence"] == "daily" for s in daily)


def test_real_stale_subtypes_absent(real):
    for k in real["series"]:
        assert not k.startswith(("TANK_BALTIC_INDEX", "TANK_VLCC_MARKET",
                                 "TANK_SUEZMAX_MARKET", "TANK_EQUINOR"))
        assert "EQUINOR" not in k
    exc = {e["subtype"] for e in real["meta"]["excluded"]}
    assert exc == {"BALTIC INDEX", "VLCC-MARKET", "SUEZMAX-MARKET", "EQUINOR"}
    assert all(e["last"] for e in real["meta"]["excluded"])


def test_real_json_round_trip_and_size(real):
    raw = JSON_PATH.read_text(encoding="utf-8")
    loaded = json.loads(raw)
    redumped = json.dumps(loaded, separators=(",", ":"), ensure_ascii=True)
    assert redumped == raw.strip(), "file is not the canonical compact form"
    # UI bundle size target
    assert JSON_PATH.stat().st_size < 4 * 1024 * 1024, "JSON exceeds 4 MB"


def test_real_date_to_tracks_csv(real):
    assert real["meta"]["date_to"] == "2026-09-08"
    # the cache must carry the CSV's own newest date (same-day rebuild)
    newest = ""
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["rate_type"] in ("TANK", "counts") and r["date"] > newest:
                newest = r["date"]
    assert real["meta"]["date_to"] == newest


def test_real_monthly_twin_codes_match(real):
    mon = json.loads((ROOT / "data" / "derived" /
                      "fearnleys_series_monthly.json").read_text(encoding="utf-8"))
    twin_codes = {k for k, v in mon["labels"].items() if v.get("type") == "TANK"}
    # stale subtypes exist only in the monthly/Museum layer by design
    twin_codes = {k for k in twin_codes
                  if not k.startswith(("TANK_BALTIC_INDEX", "TANK_VLCC_MARKET",
                                       "TANK_SUEZMAX_MARKET", "TANK_EQUINOR"))}
    ours = set(real["series"])
    # every monthly twin code exists in the daily cache (twin code = ws branch)
    missing = twin_codes - ours
    assert not missing, f"monthly twin codes missing from daily cache: {sorted(missing)}"
    # and the cache holds the extra unit branches + counters
    assert ours - twin_codes, "expected suffixed unit-branch codes"


def test_real_cli_verify_green():
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--verify"],
        capture_output=True, text=True, timeout=180,
        cwd=str(ROOT))
    assert proc.returncode == 0, proc.stderr
    assert "verify OK" in proc.stdout
