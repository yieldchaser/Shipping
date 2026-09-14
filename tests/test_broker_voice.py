"""
Broker Voice & Research Repository pipeline (Broker Desk tab).

Offline tests for the failures found on 2026-09-14:
  * daily_fearnleys_sync.py crashed importing fetch_fearnleys_reports, so a new
    Fearnleys report was seen but never saved, and the rest of the step was skipped;
  * it wrote the catalogue to reports/ while the site reads data/reports/;
  * comments, S&P and reports were read from a single 50/50/5-row page, and fixtures
    from a single 500-row page, so any larger backlog was lost;
  * nothing refreshed the Gibson catalogue;
  * the Broker Voice feeds had no scheduled job that fails when they go stale.
"""

import importlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"


@pytest.fixture
def sync(monkeypatch):
    sys.path.insert(0, str(ROOT / "scripts" / "fearnleys"))
    try:
        mod = importlib.import_module("daily_fearnleys_sync")
        importlib.reload(mod)
        monkeypatch.setattr(mod.time, "sleep", lambda s: None)
        yield mod
    finally:
        sys.path.remove(str(ROOT / "scripts" / "fearnleys"))


def test_sync_can_import_its_helpers_from_any_cwd(tmp_path):
    code = (
        "import runpy, sys; sys.argv=['x'];"
        f"g = runpy.run_path(r'{ROOT / 'scripts' / 'fearnleys' / 'daily_fearnleys_sync.py'}', run_name='not_main');"
        "import fetch_fearnleys_reports, build_fearnleys_cache;"
        "print('ok')"
    )
    out = subprocess.run([sys.executable, "-c", code], cwd=tmp_path, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert "ok" in out.stdout


def test_sync_writes_the_catalogue_the_site_reads(sync):
    assert Path(sync.REPORTS_CATALOG) == ROOT / "data" / "reports" / "fearnleys_reports_catalog.json"
    assert Path(sync.REPORTS_CATALOG) in [Path(p) for p in sync.REPORTS_CATALOG_COPIES]
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    assert "fetch('data/reports/fearnleys_reports_catalog.json'" in html


def test_fetch_unseen_pages_past_a_backlog(sync, monkeypatch):
    stored = {str(i) for i in range(0, 30)}
    api = [{"id": i} for i in range(200, -1, -1)]  # newest first, ids 200..0

    def fake_post(payload, **kw):
        v = payload["variables"]
        return {"comment": api[v["offset"]:v["offset"] + v["limit"]]}

    monkeypatch.setattr(sync, "post_graphql_with_retry", fake_post)
    unseen = sync.fetch_unseen("GetRecentComments", sync.COMMENTS_QUERY, "comment", stored)
    assert {r["id"] for r in unseen} == set(range(30, 201))


def test_fetch_unseen_raises_when_api_fails(sync, monkeypatch):
    monkeypatch.setattr(sync, "post_graphql_with_retry", lambda payload, **kw: None)
    with pytest.raises(RuntimeError):
        sync.fetch_unseen("GetRecentReports", sync.REPORTS_QUERY, "custom_report", set())


def test_every_paged_query_takes_limit_and_offset(sync):
    for q in (sync.COMMENTS_QUERY, sync.REPORTS_QUERY, sync.SNP_QUERY):
        assert "$limit" in q and "$offset" in q


def test_gibson_catalogue_merge_keeps_old_entries_and_unescapes_titles(monkeypatch):
    sys.path.insert(0, str(ROOT / "scripts" / "scrapers"))
    try:
        mod = importlib.import_module("fetch_gibson_catalog")
    finally:
        sys.path.remove(str(ROOT / "scripts" / "scrapers"))
    monkeypatch.setattr(mod.time, "sleep", lambda s: None)

    class Resp:
        def __init__(self, items):
            self._items = items
            self.headers = {"X-WP-TotalPages": "1"}

        def raise_for_status(self):
            pass

        def json(self):
            return self._items

    def fake_get(url, params=None, headers=None, timeout=None):
        return Resp([{"id": 2, "date": "2026-09-11T16:38:53", "slug": "a", "link": "https://www.gibsons.co.uk/report/a/",
                      "title": {"rendered": "Africa&#8217;s Refining Pipeline"}}])

    monkeypatch.setattr(mod.requests, "get", fake_get)
    fresh = mod.fetch_kind("report")
    assert fresh[0]["title"] == "Africa’s Refining Pipeline"
    merged = mod.merge([{"id": 1, "date": "2026-09-04T00:00:00", "title": "Old", "slug": "o", "link": "x"}], fresh)
    assert [r["id"] for r in merged] == [2, 1]


def test_broker_voice_workflow_runs_daily_and_fails_loudly():
    wf = yaml.safe_load((WORKFLOWS / "broker_voice_sync.yml").read_text(encoding="utf-8"))
    on = wf.get("on") or wf.get(True)
    crons = [c["cron"] for c in on["schedule"]]
    assert crons and all(c.split()[-1] == "*" for c in crons), "must run every day"
    steps = wf["jobs"]["sync"]["steps"]
    text = json.dumps(steps)
    for script in ("daily_fearnleys_sync.py", "build_comment_chunks.py", "fetch_gibson_catalog.py",
                   "check_broker_voice_fresh.py"):
        assert script in text
    assert not any(s.get("continue-on-error") for s in steps)
    assert "|| true" not in text
    add = next(s["run"] for s in steps if "git add" in s.get("run", ""))
    for path in ("data/reports/fearnleys_reports_catalog.json", "data/clarksons/gibson_all_reports_catalog.json",
                 "data/derived/fearnleys_comments_snp.json", "data/derived/fearnleys_summary.json"):
        assert path in add


def test_pages_redeploys_after_every_scheduled_writer():
    pages = yaml.safe_load((WORKFLOWS / "pages.yml").read_text(encoding="utf-8"))
    on = pages.get("on") or pages.get(True)
    watched = set(on["workflow_run"]["workflows"])
    skip = {"Live ETF Quotes Poller (BDRY/BWET)"}  # every 30 min; deploys ride on the next writer
    for f in WORKFLOWS.glob("*.yml"):
        wf = yaml.safe_load(f.read_text(encoding="utf-8"))
        wf_on = wf.get("on") or wf.get(True) or {}
        body = f.read_text(encoding="utf-8")
        if isinstance(wf_on, dict) and "schedule" in wf_on and "git push" in body and wf["name"] not in skip:
            assert wf["name"] in watched, f"{f.name} pushes data but Pages never redeploys after it"


def test_source_dropdown_counts_are_not_typed():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    for typed in ("(548 reports)", "(175 reports)", "(97 reports)", "11,709"):
        assert typed not in html
