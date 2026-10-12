"""Repair data/derived/fearnleys_broker_comments.csv against the Fearnleys Hasura comment feed.

Three defects of the original harvest (scripts/fetch_fearnleys_comments.py before 2026-10-12):
  - newlines in the comment text were flattened to spaces, losing the paragraph breaks
    (~2,400 comments have them);
  - paging ordered by date alone is unstable across pages, so 11 comments were stored twice and
    11 others never fetched;
  - comments Fearnleys edited after the harvest keep their old wording.

Every stored comment takes the feed's current text (CRLF -> LF) and metadata; a stored id the feed
no longer has is kept as it is. Duplicate rows of one id collapse to the first. Comments the CSV
lacks are appended (oldest first), as the daily sync would append them. Row order and the other
columns are otherwise unchanged. Idempotent: a second run changes nothing.

    python scripts/fearnleys/repair_broker_comments_csv.py [--apply]
"""
from __future__ import annotations

import csv
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
CSV_PATH = ROOT / "data" / "derived" / "fearnleys_broker_comments.csv"
ENDPOINT = "https://pbrokerapp.hasura.app/v1/graphql"
HEADERS = {"Content-Type": "application/json",
           "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) FearnpulseHarvester/1.0"}
QUERY = """
query GetComments($limit: Int!, $offset: Int!) {
  comment(limit: $limit, offset: $offset, order_by: [{date: desc}, {id: desc}]) {
    id date text created_at comment_meta_id
    metadata { comment_type comment_subtype comment_name }
  }
}
"""
FIELDS = ["id", "date", "comment_type", "comment_subtype", "comment_name", "text", "created_at", "comment_meta_id"]


def feed():
    rows, offset = [], 0
    while True:
        r = requests.post(ENDPOINT, json={"query": QUERY, "variables": {"limit": 1000, "offset": offset}},
                          headers=HEADERS, timeout=120)
        r.raise_for_status()
        data = r.json()
        if "errors" in data:
            raise RuntimeError(f"GraphQL error: {data['errors']}")
        batch = data["data"]["comment"]
        rows.extend(batch)
        if len(batch) < 1000:
            return rows
        offset += 1000
        time.sleep(1.0)


def as_row(c):
    meta = c.get("metadata") or {}
    return {"id": c["id"], "date": c["date"] or "", "comment_type": meta.get("comment_type") or "",
            "comment_subtype": meta.get("comment_subtype") or "", "comment_name": meta.get("comment_name") or "",
            "text": (c["text"] or "").replace("\r\n", "\n"), "created_at": c["created_at"] or "",
            "comment_meta_id": "" if c["comment_meta_id"] is None else str(c["comment_meta_id"])}


def main():
    apply = "--apply" in sys.argv
    api = {c["id"]: as_row(c) for c in feed()}
    if len(api) < 10000:
        raise RuntimeError(f"feed returned only {len(api)} comments; refusing to repair against it")
    csv.field_size_limit(10 ** 9)
    with open(CSV_PATH, encoding="utf-8", newline="") as fh:
        old = list(csv.DictReader(fh))
    out, seen = [], set()
    stat = {"rows": len(old), "duplicates dropped": 0, "paragraphs restored": 0, "reworded upstream": 0,
            "not in feed (kept)": 0, "unchanged": 0}
    for r in old:
        if r["id"] in seen:
            stat["duplicates dropped"] += 1
            continue
        seen.add(r["id"])
        a = api.get(r["id"])
        if a is None:
            stat["not in feed (kept)"] += 1
            out.append(r)
            continue
        if a == {k: r.get(k, "") for k in FIELDS}:
            stat["unchanged"] += 1
        elif a["text"].replace("\n", " ") == r["text"]:
            stat["paragraphs restored"] += 1
        elif a["text"] != r["text"]:
            stat["reworded upstream"] += 1
        out.append(a)
    new = sorted((a for i, a in api.items() if i not in seen), key=lambda a: (a["date"], a["created_at"], a["id"]))
    stat["appended (missing from csv)"] = len(new)
    out.extend(new)
    stat["rows after"] = len(out)
    print(stat)
    if apply:
        with open(CSV_PATH, "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n")
            w.writeheader()
            w.writerows(out)
        print("(applied)")


if __name__ == "__main__":
    main()
