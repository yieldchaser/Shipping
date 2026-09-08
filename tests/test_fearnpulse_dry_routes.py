#!/usr/bin/env python3
"""Fearnleys dry-route TS harvest (fearnpulse /api/marketapi/TS) — producer tests.

Hermetic parse/merge/idempotence fixtures (in-process module import, requests
stubbed) + regression floors against the real archive files.

Floor honesty note: the brief assumed ~2k obs for every backfilled series, but
measurement shows the source itself starts these assessments at different dates
(Panamax 2018-01, Supramax 2023-05, Capesize RV/TCE 2024-09, Capesize
Australia/China 1999-03). Floors are set at measured-count minus headroom —
they only fail if the archive loses real data.
"""
import csv
import hashlib
import importlib.util
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "fearnleys" / "fetch_dry_routes_ts.py"
CSV_PATH = ROOT / "data" / "derived" / "fearnpulse_dry_routes_full.csv"
JSON_PATH = ROOT / "data" / "derived" / "fearnleys_dry_routes_daily.json"

spec = importlib.util.spec_from_file_location("fdrt", SCRIPT)
fdrt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fdrt)


def epoch(date_str):
    return int(datetime.strptime(date_str, "%Y-%m-%d")
               .replace(tzinfo=timezone.utc).timestamp() * 1000)


def payload(rows):
    class FakeResp:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"columns": ["tsid", "value", "date", "jobid"],
                    "index": None, "data": rows}
    return FakeResp()


def day_rows(tsid, days, values):
    """rows for one series; values keyed by date string."""
    return [[tsid, values[d], epoch(d), i] for i, d in enumerate(days)]


# ---------------------------------------------------------------- parse tests

def test_parse_normalizes_both_row_orders(monkeypatch):
    days = ["2026-09-01", "2026-09-02", "2026-09-03"]
    vals = {"2026-09-01": 100.0, "2026-09-02": 101.0, "2026-09-03": 102.0}
    # newest-first (as served with last=N)
    rows_nf = list(reversed(day_rows(10010, days, vals)))
    # oldest-first (as served without last)
    rows_of = day_rows(10010, days, vals)
    calls = []

    def fake_get(url, headers=None, params=None, timeout=None):
        calls.append(dict(params))
        return payload(rows_nf if params.get("last") else rows_of)

    monkeypatch.setattr(fdrt.requests, "get", fake_get)
    got_last = fdrt.fetch_series(10010, last=20)
    got_full = fdrt.fetch_series(10010, last=None)
    assert calls[0].get("last") == 20 and calls[0].get("id") == 10010
    assert "last" not in calls[1]
    assert [e for e, _ in got_last] == sorted(e for e, _ in got_last)
    assert [e for e, _ in got_full] == sorted(e for e, _ in got_full)
    assert got_last == got_full
    assert [v for _, v in got_last] == [100.0, 101.0, 102.0]


def test_parse_dedupes_duplicate_dates_keep_last(monkeypatch):
    rows = [[10010, 50.0, epoch("2026-09-01"), 0],
            [10010, 55.0, epoch("2026-09-01"), 1],
            [10010, 60.0, epoch("2026-09-02"), 2]]

    def fake_get(url, headers=None, params=None, timeout=None):
        return payload(rows)

    monkeypatch.setattr(fdrt.requests, "get", fake_get)
    got = fdrt.fetch_series(10010)
    assert got == [(epoch("2026-09-01"), 55.0), (epoch("2026-09-02"), 60.0)]


# ------------------------------------------------------- merge / idempotence

@pytest.fixture()
def sandbox(monkeypatch, tmp_path):
    csvp = tmp_path / "fearnpulse_dry_routes_full.csv"
    jsonp = tmp_path / "fearnleys_dry_routes_daily.json"
    monkeypatch.setattr(fdrt, "CSV_PATH", str(csvp))
    monkeypatch.setattr(fdrt, "JSON_PATH", str(jsonp))
    return csvp, jsonp


def _stub_fetch(monkeypatch, series_values, missing="empty"):
    """series_values: {tsid: {date: value}} served oldest-first without last.
    Unstubbed tsIds serve an empty payload (excluded from merge)."""
    def fake_get(url, headers=None, params=None, timeout=None):
        tsid = params["id"]
        if tsid not in series_values:
            return payload([]) if missing == "empty" else payload(
                [[tsid, None, epoch("2026-09-01"), 0]])
        vals = series_values[tsid]
        days = sorted(vals)
        return payload(day_rows(tsid, days, vals))

    monkeypatch.setattr(fdrt.requests, "get", fake_get)


def test_merge_latest_wins_and_idempotent(sandbox, monkeypatch):
    csvp, jsonp = sandbox
    base = {
        120132: {"2026-09-01": 32000.0, "2026-09-02": 32100.0},
        120133: {"2026-09-01": 14000.0, "2026-09-02": 14100.0},
        10010: {"2026-09-01": 20000.0, "2026-09-02": 20100.0},
    }
    _stub_fetch(monkeypatch, base)
    fdrt.run("refresh")
    rows1 = list(csv.DictReader(csvp.read_text(encoding="utf-8").splitlines()))
    assert len(rows1) == 6 + 2  # 3 series x 2 days + 2 avg rows
    avg = {r["date"]: r for r in rows1
           if r["label"] == "SUPRAMAX_TRANSATLANTIC_RV_AVG"}
    assert avg["2026-09-01"]["value"] == "23000"  # (32000+14000)/2 exact
    assert avg["2026-09-01"]["raw_pair_meta"] == "mean(120132:32000.0,120133:14000.0)"

    # Revised print for an existing date -> latest fetch must win, no dup rows.
    revised = {**base, 10010: {"2026-09-01": 99999.0, "2026-09-02": 20100.0}}
    _stub_fetch(monkeypatch, revised)
    fdrt.run("refresh")
    rows2 = list(csv.DictReader(csvp.read_text(encoding="utf-8").splitlines()))
    assert len(rows2) == len(rows1)
    p10 = [r for r in rows2 if r["label"] == "Panamax Transatlantic RV"
           and r["date"] == "2026-09-01"]
    assert len(p10) == 1 and p10[0]["value"] == "99999.0"

    # Re-run with identical source -> CSV byte-identical; JSON identical
    # modulo the fetched_utc wall-clock stamp.
    _stub_fetch(monkeypatch, revised)
    h_csv = hashlib.sha256(csvp.read_bytes()).hexdigest()
    j_bytes = jsonp.read_bytes()
    fdrt.run("refresh")
    assert hashlib.sha256(csvp.read_bytes()).hexdigest() == h_csv
    j1 = json.loads(j_bytes); j2 = json.loads(jsonp.read_bytes())
    del j1["meta"]["fetched_utc"]; del j2["meta"]["fetched_utc"]
    assert j1 == j2


def test_avg_rounds_half_up_and_needs_both_raws(sandbox, monkeypatch):
    csvp, jsonp = sandbox
    vals = {
        120132: {"2026-09-01": 32001.0},          # (32001+14000)/2 = 23000.5 -> 23001
        120133: {"2026-09-01": 14000.0, "2026-09-02": 15000.0},  # 09-02 has no A partner
    }
    _stub_fetch(monkeypatch, vals)
    fdrt.run("refresh")
    rows = list(csv.DictReader(csvp.read_text(encoding="utf-8").splitlines()))
    avg = {r["date"]: r for r in rows if r["label"] == "SUPRAMAX_TRANSATLANTIC_RV_AVG"}
    assert set(avg) == {"2026-09-01"}          # day missing one raw pair -> no avg row
    assert avg["2026-09-01"]["value"] == "23001"
    j = json.loads(jsonp.read_text(encoding="utf-8"))
    entry = j["series"]["SUPRAMAX_TRANSATLANTIC_RV_AVG"]
    assert entry["tsid"] is None
    assert "120132" in entry["derivation"] and "120133" in entry["derivation"]


# ------------------------------------------------- regression floors (real)

def _real_rows():
    with open(CSV_PATH, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_real_archive_series_floors():
    rows = _real_rows()
    by_label = {}
    for r in rows:
        by_label.setdefault(r["label"], []).append(r["date"])
    # floors = measured source depth minus headroom (see module docstring)
    floors = {
        "Panamax Transatlantic RV": 2000,          # tsid 10010, measured 2167
        "Panamax TCE Cont/Far East": 1900,         # 10011, 2167
        "Panamax TCE Far East/Cont": 1900,         # 10013, 2167
        "Panamax TCE Far East RV": 1900,           # 10012, 2167
        "Capesize Australia/China": 6000,          # 10002, 6875
        "Capesize TCE Cont/Far East": 450,         # 120655, 505 (2024-09 launch)
        "Capesize Pacific RV": 450,                # 120654, 505
        "Supramax Transatlantic RV (raw A)": 750,  # 120132, 840 (2023-05 launch)
        "Supramax Transatlantic RV (raw B)": 750,  # 120133, 840
        "Supramax US Gulf - China/South Japan": 750,   # 120129, 840
        "Supramax South China - Indonesia RV": 760,    # 120137, 855
        "SUPRAMAX_TRANSATLANTIC_RV_AVG": 750,      # derived, 840
    }
    assert set(by_label) == set(floors), f"series set drifted: {sorted(by_label)}"
    for label, floor in floors.items():
        n = len(by_label[label])
        assert n >= floor, f"{label}: {n} < floor {floor}"
        ds = sorted(by_label[label])
        assert all(ds[i] < ds[i + 1] for i in range(len(ds) - 1)), \
            f"{label}: dates not strictly monotonic"


def test_json_csv_round_trip():
    rows = _real_rows()
    j = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    meta = j["meta"]
    assert meta["source"].startswith("Fearnleys market-data service")
    assert meta["date_to"] == max(r["date"] for r in rows)
    csv_counts = {}
    for r in rows:
        csv_counts.setdefault(r["label"], {})[r["date"]] = r["value"]
    assert set(j["series"]) == {
        "CAPESIZE_TCE_CONT_FAR_EAST", "CAPESIZE_AUSTRALIA_CHINA",
        "CAPESIZE_PACIFIC_RV", "PANAMAX_TRANSATLANTIC_RV",
        "PANAMAX_TCE_CONT_FAR_EAST", "PANAMAX_TCE_FAR_EAST_CONT",
        "PANAMAX_TCE_FAR_EAST_RV", "SUPRAMAX_TRANSATLANTIC_RV_A",
        "SUPRAMAX_TRANSATLANTIC_RV_B", "SUPRAMAX_US_GULF_CHINA_SJ",
        "SUPRAMAX_SOUTH_CHINA_INDONESIA_RV", "SUPRAMAX_TRANSATLANTIC_RV_AVG",
    }
    for code, entry in j["series"].items():
        csv_label = code if code == "SUPRAMAX_TRANSATLANTIC_RV_AVG" else entry["label"]
        per_day = csv_counts[csv_label]
        assert entry["n"] == len(per_day), f"{code}: n mismatch"
        assert entry["first"] == min(per_day) and entry["last"] == max(per_day)
        epochs = [p[0] for p in entry["pts"]]
        assert epochs == sorted(epochs), f"{code}: pts not chronological"
        for e, v in entry["pts"]:
            d = datetime.fromtimestamp(e / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
            assert d in per_day
            assert abs(float(per_day[d]) - float(v)) < 1e-9, f"{code} {d}"
    # avg entry spot-check against the raw pair on the latest shared day
    raw_a = csv_counts["Supramax Transatlantic RV (raw A)"]
    raw_b = csv_counts["Supramax Transatlantic RV (raw B)"]
    shared = sorted(set(raw_a) & set(raw_b))[-1]
    expected = int((float(raw_a[shared]) + float(raw_b[shared])) / 2 + 0.5)
    got = dict((datetime.fromtimestamp(e / 1000, tz=timezone.utc).strftime("%Y-%m-%d"), v)
               for e, v in j["series"]["SUPRAMAX_TRANSATLANTIC_RV_AVG"]["pts"])[shared]
    assert got == expected, f"avg mismatch on {shared}: {got} != {expected}"
