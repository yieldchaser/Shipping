"""
Gibson Shipbrokers research catalogue harvester.

Reads both Gibson publication types from the site's public WordPress REST API
(https://www.gibsons.co.uk/wp-json/wp/v2/report and /report_downloads), and
rewrites data/clarksons/gibson_all_reports_catalog.json with every entry the
site lists. Entries are keyed by WordPress id; an entry already stored is kept
if the site stops listing it, so the catalogue never shrinks on a bad page.

Exits non-zero if either feed cannot be read, so a scheduled run turns red
instead of silently leaving the Broker Voice panel stale.
"""

import html
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CATALOG = REPO_ROOT / "data" / "clarksons" / "gibson_all_reports_catalog.json"
API = "https://www.gibsons.co.uk/wp-json/wp/v2/{kind}"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
}
FEEDS = {"online_reports": "report", "report_downloads": "report_downloads"}


def fetch_kind(kind):
    rows, page, pages = [], 1, 1
    while page <= pages:
        for attempt in range(3):
            try:
                r = requests.get(
                    API.format(kind=kind),
                    params={"per_page": 100, "page": page, "_fields": "id,date,title,slug,link"},
                    headers=HEADERS,
                    timeout=40,
                )
                r.raise_for_status()
                break
            except requests.RequestException as exc:
                if attempt == 2:
                    raise RuntimeError(f"{kind} page {page}: {exc}") from exc
                time.sleep(3 * (attempt + 1))
        pages = int(r.headers.get("X-WP-TotalPages", "1"))
        for item in r.json():
            rows.append({
                "id": item["id"],
                "date": item["date"],
                "title": html.unescape((item.get("title") or {}).get("rendered", "")).strip(),
                "slug": item["slug"],
                "link": item["link"],
            })
        page += 1
        time.sleep(1)
    return rows


def merge(existing, fresh):
    by_id = {r["id"]: r for r in existing}
    for r in fresh:
        by_id[r["id"]] = r
    return sorted(by_id.values(), key=lambda r: (r["date"], r["id"]), reverse=True)


def main():
    old = json.loads(CATALOG.read_text(encoding="utf-8")) if CATALOG.exists() else {}
    out = {"harvested_at": datetime.now(timezone.utc).isoformat()}
    added = 0
    for key, kind in FEEDS.items():
        fresh = fetch_kind(kind)
        if not fresh:
            raise RuntimeError(f"{kind}: the site returned no entries")
        before = old.get(key, [])
        merged = merge(before, fresh)
        added += len(merged) - len(before)
        out[key] = merged
    out["online_reports_count"] = len(out["online_reports"])
    out["report_downloads_count"] = len(out["report_downloads"])
    out["total_reports"] = out["online_reports_count"] + out["report_downloads_count"]
    out = {k: out[k] for k in ("harvested_at", "total_reports", "online_reports_count",
                               "report_downloads_count", "online_reports", "report_downloads")}
    CATALOG.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    latest = out["online_reports"][0]
    print(f"Gibson catalogue: {out['total_reports']} entries (+{added} new); latest {latest['date'][:10]} {latest['title']}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 - surface any failure as a red run
        print(f"Gibson catalogue harvest FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
