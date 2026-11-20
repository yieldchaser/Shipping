"""Regression guards for the November 2026 data/UI clean-up.

Each test pins one bug that shipped silently:
- Solactive futures closes stamped a day early (UTC read of Berlin midnight)
- a batch close not replacing an evening live quote on the same date
- the one-shot repair script shifting the history a second time
- future-dated Amplify premium/discount rows
- the cargo freshness guard failing every week on one-cycle publisher lag
- the cargo flagship corridors frozen at a literal "2026-09"
"""
import importlib
import json
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]


def _ui():
    return importlib.import_module("update_indices")


def test_solactive_batch_date_is_berlin_local(monkeypatch):
    ui = _ui()
    # Monday 2026-11-16 00:00 Europe/Berlin == Sunday 23:00 UTC
    ts = int(pd.Timestamp("2026-11-16 00:00", tz="Europe/Berlin").value // 10**6)
    payload = [[1], {"timestamp": 2, "value": 3}, ts, 2519.0]

    class R:
        def raise_for_status(self):
            pass

        def json(self):
            return payload

    monkeypatch.setattr(ui._SESSION, "post", lambda *a, **k: R())
    row = ui.fetch_latest_solactive("DE000SLA4BY3")
    assert row["date"].iloc[0] == pd.Timestamp("2026-11-16"), row


def test_solactive_batch_overwrites_live_quote_and_keeps_format(tmp_path):
    ui = _ui()
    f = tmp_path / "ff.csv"
    f.write_text("date,value\n13-11-2026,2582.77\n16-11-2026,2500.00\n")
    ui.update_solactive_csv(str(f), pd.DataFrame([{"date": pd.Timestamp("2026-11-16"), "value": 2519.0}]))
    out = pd.read_csv(f)
    assert list(out["date"]) == ["13-11-2026", "16-11-2026"]
    assert out["value"].iloc[-1] == 2519.0
    ui.update_solactive_csv(str(f), pd.DataFrame([{"date": pd.Timestamp("2026-11-17"), "value": 2551.47}]))
    out = pd.read_csv(f)
    assert list(out["date"]) == ["13-11-2026", "16-11-2026", "17-11-2026"]


def test_futures_histories_have_no_weekend_rows():
    for name in ("bdryff_history.csv", "bwetff_history.csv"):
        d = pd.read_csv(ROOT / "data" / "futures" / name)
        dt = pd.to_datetime(d["date"], format="%d-%m-%Y")
        assert (dt.dt.dayofweek < 5).all(), f"{name} has weekend-dated rows"
        assert dt.is_monotonic_increasing and dt.is_unique, name


def test_repair_script_is_idempotent(tmp_path, monkeypatch):
    mod = importlib.import_module("repair.fix_solactive_dates")
    f = tmp_path / "x.csv"
    # pre-boundary Sun..Thu rows (the bug's signature), then a live Fri + a Sun/Mon duplicate
    rows = []
    for d in pd.date_range("2025-01-05", "2026-03-12"):
        if d.dayofweek in (6, 0, 1, 2, 3):
            rows.append((d, 100.0 + len(rows)))
    rows += [(pd.Timestamp("2026-03-13"), 1.0), (pd.Timestamp("2026-03-15"), 2.0), (pd.Timestamp("2026-03-16"), 2.5)]
    pd.DataFrame({"date": [r[0].strftime("%d-%m-%Y") for r in rows], "value": [r[1] for r in rows]}).to_csv(f, index=False)
    assert mod.repair(f, dry_run=False) is True
    once = f.read_text()
    assert mod.repair(f, dry_run=False) is False
    assert f.read_text() == once
    d = pd.read_csv(f)
    dt = pd.to_datetime(d["date"], format="%d-%m-%Y")
    assert (dt.dt.dayofweek < 5).all()
    # Sunday batch print (2.0) wins over the Monday live quote (2.5)
    assert d.loc[d["date"] == "16-03-2026", "value"].item() == 2.0


def test_amplify_merge_drops_future_rows(tmp_path):
    ui = _ui()
    f = tmp_path / "p.csv"
    f.write_text("Rate Date,Premium/Discount\n2026-11-16,0.36\n")
    new = pd.DataFrame({"Rate Date": [pd.Timestamp("2026-11-17"), pd.Timestamp(date.today()) + pd.Timedelta(days=20)],
                        "Premium/Discount": [0.37, 9.9]})
    ui.update_amplify_csv(str(f), new)
    out = pd.read_csv(f)
    assert pd.to_datetime(out["Rate Date"]).max() <= pd.Timestamp(date.today()) + pd.Timedelta(days=1)
    assert 0.37 in out["Premium/Discount"].values


def test_freshness_guard_one_cycle_late_is_lag_not_stale():
    m = importlib.import_module("verify.check_data_freshness")
    today = date(2026, 11, 19)
    res = m.apply_grace([
        {"name": "w", "category": "Weekly", "rule": "Within 10 days of today", "latest_stored": "2026-11-06", "expected": "", "is_fresh": False},
        {"name": "w2", "category": "Weekly", "rule": "Within 10 days of today", "latest_stored": "2026-10-20", "expected": "", "is_fresh": False},
        {"name": "m", "category": "Monthly", "rule": "", "latest_stored": "2026-08", "expected": "2026-09", "is_fresh": False},
        {"name": "m2", "category": "Monthly", "rule": "", "latest_stored": "2026-06", "expected": "2026-09", "is_fresh": False},
        {"name": "jan", "category": "Monthly", "rule": "", "latest_stored": "2025-12", "expected": "2026-01", "is_fresh": False},
        {"name": "ok", "category": "Monthly", "rule": "", "latest_stored": "2026-09", "expected": "2026-09", "is_fresh": True},
    ], today)
    st = {r["name"]: r["status"] for r in res}
    assert st == {"w": "LAG", "w2": "STALE", "m": "LAG", "m2": "STALE", "jan": "LAG", "ok": "FRESH"}


def test_cargo_flagship_pairs_not_frozen():
    d = json.loads((ROOT / "data" / "cargo" / "cargo_frontend_summary.json").read_text())
    months = d["flagship_pairs"]["brazil_c3"]["months"]
    assert months[-1] > "2026-09", f"flagship corridor still stops at {months[-1]}"
    src = (ROOT / "scripts" / "cargo" / "build_cargo_cache.py").read_text()
    assert 'max_ym="2026-09"' not in src


def test_monthly_series_never_mix_units():
    """A route whose source switched TCE -> WS/USD in 2023-05 must not keep one
    key across both units (VLCC MEG/FEAST read 23,679 then 47.36 as 'tce')."""
    d = json.loads((ROOT / "data" / "derived" / "fearnleys_series_monthly.json").read_text())
    L = d["labels"]
    ws = L["TANK_VLCC_MEG_FEAST"]
    tce = L["TANK_VLCC_MEG_FEAST_TCE"]
    assert ws["unit"] == "ws" and tce["unit"] == "tce"
    assert tce["last"] <= "2023-04" and tce["twin_of"] == "TANK_VLCC_MEG_FEAST"
    # no WS-sized value inside a TCE series and vice versa
    assert min(v for _, v in tce["m"] if v) > 1000
    assert max(v for _, v in ws["m"]) < 5000
