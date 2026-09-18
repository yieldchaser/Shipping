"""Live FFA recorder: stores every change against the SGX settlement, offline."""

import importlib
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "clarksons"))
rec_mod = importlib.import_module("ffa_live_recorder")


def snap(ts, cape_sep, settle=51157.0):
    tenors = lambda base: [{"name": "Sep", "price": base, "settle": settle}]
    return {"fetched_at_utc": ts, "unit": "USD/day", "price_basis": "x", "settle_basis": "y",
            "segments": [{"key": "cape", "label": "CAPESIZE", "tenors": tenors(cape_sep)}]}


def test_records_only_changes_and_session_stats(tmp_path, monkeypatch):
    r = rec_mod.Recorder(tmp_path)
    assert r.record(snap("2026-09-14T07:00:00Z", 51250)) is True      # first read of the day
    assert r.record(snap("2026-09-14T07:02:00Z", 51250)) is False     # unchanged: no tick
    assert r.record(snap("2026-09-14T07:04:00Z", 50625)) is True
    assert r.record(snap("2026-09-14T07:06:00Z", 51500)) is True

    ticks = rec_mod.read_csv(tmp_path / "ticks" / "2026-09.csv")
    assert [t["price"] for t in ticks] == ["51250", "50625", "51500"]
    daily = rec_mod.read_csv(tmp_path / "daily.csv")
    assert len(daily) == 1
    d = daily[0]
    assert (d["open"], d["high"], d["low"], d["last"], d["reads"]) == ("51250", "51500", "50625", "51500", "4")

    latest = json.loads((tmp_path / "latest.json").read_text())
    t = latest["segments"][0]["tenors"][0]
    assert t["settle"] == 51157.0 and t["price"] == 51500
    assert [p[1] for p in t["path"]] == [51250, 50625, 51500]


def test_settlement_roll_and_new_day(tmp_path, monkeypatch):
    r = rec_mod.Recorder(tmp_path)
    r.record(snap("2026-09-14T07:00:00Z", 51000, settle=51157))
    assert r.record(snap("2026-09-14T13:00:00Z", 51000, settle=50800)) is True   # settle rolled
    d = rec_mod.read_csv(tmp_path / "daily.csv")[0]
    assert d["settle"] == "50800" and d["settle_changes"] == "1"
    assert r.record(snap("2026-09-15T07:00:00Z", 51000, settle=50800)) is True   # new day opens with a tick
    assert len(rec_mod.read_csv(tmp_path / "daily.csv")) == 2


def test_push_refuses_outside_actions(monkeypatch):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.setattr(sys, "argv", ["x", "--once", "--push"])
    try:
        rec_mod.main()
    except SystemExit as e:
        assert e.code == 2
    else:
        raise AssertionError("--push must refuse to run outside GitHub Actions")


def test_recorder_workflow_covers_london_session_and_pages_reads_raw():
    wf = yaml.safe_load((ROOT / ".github/workflows/ffa_live_recorder.yml").read_text(encoding="utf-8"))
    on = wf.get("on") or wf.get(True)
    crons = [c["cron"] for c in on["schedule"]]
    assert crons and all(c.endswith("* * 1-5") for c in crons)
    # GitHub starts crons hours late, so runs chain (waiting overnight) and the clock sets the window.
    hours = sorted(int(c.split()[1]) for c in crons)
    assert hours[0] == 2 and all(b - a <= 3 for a, b in zip(hours, hours[1:]))
    steps = wf["jobs"]["record"]["steps"]
    run = json.dumps(steps)
    assert "--interval 120" in run and "--push" in run
    env = next(s for s in steps if s.get("name") == "Record session")["env"]
    assert env["WINDOW_START"] == "02:30" and env["WINDOW_END"] == "18:30"
    assert "gh workflow run ffa_live_recorder.yml" in run
    assert wf["permissions"]["actions"] == "write"
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    assert "raw.githubusercontent.com/yieldchaser/Shipping/main/" in html
    assert "ffaLiveFetch('data/ffa_live/latest.json')" in html
    assert "FFA_LIVE_ALERT_PCT = 3" in html


def test_backs_off_and_stops_when_refused(monkeypatch, tmp_path):
    calls, sleeps = [], []

    def refused():
        calls.append(1)
        raise rec_mod.Blocked("HTTP 429")

    monkeypatch.setattr(rec_mod, "fetch", refused)
    monkeypatch.setattr(rec_mod, "OUT_DIR", tmp_path)
    monkeypatch.setattr(rec_mod.Recorder.__init__, "__defaults__", (tmp_path,))
    monkeypatch.setattr(rec_mod.time, "sleep", lambda s: sleeps.append(s))
    monkeypatch.setattr(sys, "argv", ["x", "--until", "23:59"])
    assert rec_mod.main() == 1
    assert len(calls) == 3 and sleeps == [900, 900]


def test_page_has_no_settle_scorecard():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    assert "CALL THE SETTLE" not in html and "ffaLiveHistory" not in html
