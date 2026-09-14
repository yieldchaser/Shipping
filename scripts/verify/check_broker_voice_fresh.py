"""
Broker Voice end-to-end freshness check.

Asks each live source for its newest items and fails if any item published more
than GRACE_HOURS ago is missing from the files the Broker Desk panel reads:

  Fearnleys desk comments  -> data/derived/fearnleys_broker_comments.csv,
                              data/derived/fearnleys_comments_*.json (archive chunks),
                              data/derived/fearnleys_summary.json (recent comments)
  Fearnleys research PDFs  -> data/reports/fearnleys_reports_catalog.json
  Gibson research          -> data/clarksons/gibson_all_reports_catalog.json
  Seabrokers Seabreeze     -> data/reports/seabrokers_catalog.json (latest month)

Exit code 1 lists every gap, so a scheduled run turns red instead of the panel
quietly going stale.
"""

import csv
import glob
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent.parent
GRACE_HOURS = 14
HASURA = "https://pbrokerapp.hasura.app/v1/graphql"
H_HASURA = {"Content-Type": "application/json", "Origin": "https://fearnpulse.com",
            "User-Agent": "Mozilla/5.0 FearnpulseFreshnessCheck/1.0"}
H_WEB = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128 Safari/537.36"}
NOW = datetime.now(timezone.utc)
CUTOFF = NOW - timedelta(hours=GRACE_HOURS)
problems = []


def ts(value):
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def hasura(query):
    r = requests.post(HASURA, json={"query": query}, headers=H_HASURA, timeout=40)
    r.raise_for_status()
    body = r.json()
    if "errors" in body:
        raise RuntimeError(body["errors"])
    return body["data"]


def check_fearnleys():
    comments = hasura("{comment(limit:60,order_by:[{created_at:desc}]){id date created_at}}")["comment"]
    stored = {}
    with open(ROOT / "data/derived/fearnleys_broker_comments.csv", encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            stored[str(row["id"])] = row
    due = [c for c in comments if ts(c["created_at"]) < CUTOFF]
    missing = [c for c in due if str(c["id"]) not in stored]
    if missing:
        problems.append(f"Fearnleys comments: {len(missing)} published comments not stored, e.g. {missing[0]['date']} id {missing[0]['id']}")

    newest_csv = max((r.get("date") or "") for r in stored.values())
    newest_chunk = max(max((r.get("d") or "") for r in json.load(open(p, encoding="utf-8")))
                       for p in glob.glob(str(ROOT / "data/derived/fearnleys_comments_*.json")))
    if newest_chunk < newest_csv:
        problems.append(f"Fearnleys archive chunks stop at {newest_chunk}, comments CSV has {newest_csv} (build_comment_chunks.py not run)")
    summary = json.load(open(ROOT / "data/derived/fearnleys_summary.json", encoding="utf-8"))
    newest_summary = max((c.get("date") or "") for c in summary["broker_sentiment"]["recent_comments"])
    if newest_summary < newest_csv:
        problems.append(f"Fearnleys summary recent comments stop at {newest_summary}, comments CSV has {newest_csv} (build_fearnleys_cache.py not run)")

    reports = hasura("{custom_report(limit:20,order_by:[{created_at:desc}]){id date title created_at status}}")["custom_report"]
    catalog = {str(r["id"]) for r in json.load(open(ROOT / "data/reports/fearnleys_reports_catalog.json", encoding="utf-8"))}
    for r in reports:
        if r.get("status") == "published" and ts(r["created_at"]) < CUTOFF and str(r["id"]) not in catalog:
            problems.append(f"Fearnleys report missing from catalogue: {r['date']} {r['title'].strip()}")


def check_gibson():
    cat = json.load(open(ROOT / "data/clarksons/gibson_all_reports_catalog.json", encoding="utf-8"))
    for key, kind in (("online_reports", "report"), ("report_downloads", "report_downloads")):
        r = requests.get(f"https://www.gibsons.co.uk/wp-json/wp/v2/{kind}",
                         params={"per_page": 10, "_fields": "id,date_gmt,slug"}, headers=H_WEB, timeout=40)
        r.raise_for_status()
        have = {e["id"] for e in cat.get(key, [])}
        for e in r.json():
            if ts(e["date_gmt"]) < CUTOFF and e["id"] not in have:
                problems.append(f"Gibson {kind} missing from catalogue: {e['date_gmt'][:10]} {e['slug']}")


def check_seabrokers():
    cat = json.load(open(ROOT / "data/reports/seabrokers_catalog.json", encoding="utf-8"))
    newest = max(r["date"] for r in cat)
    # Seabreeze reports cover the previous month and appear during the following month.
    y, m = NOW.year, NOW.month - 2
    if m <= 0:
        y, m = y - 1, m + 12
    if newest < f"{y:04d}-{m:02d}-01":
        problems.append(f"Seabrokers catalogue stops at {newest}; expected {y:04d}-{m:02d} or later")


def main():
    for name, fn in (("Fearnleys", check_fearnleys), ("Gibson", check_gibson), ("Seabrokers", check_seabrokers)):
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            problems.append(f"{name}: check could not run: {exc}")
    if problems:
        print("Broker Voice freshness check FAILED:")
        for p in problems:
            print("  - " + p)
        return 1
    print(f"Broker Voice freshness check passed ({NOW:%Y-%m-%d %H:%M} UTC, grace {GRACE_HOURS}h).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
