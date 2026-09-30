"""What does the corpus ALREADY hold outside 01-brokers? Measure before building.

The user has been explicit: do not rebuild what the database already carries. So the
question for each remaining corpus group is not "can we extract it" but "is it already
ours, in the feeds, or on a dashboard tab".

Three baselines, per the extraction doctrine:
  1. the live feeds        data/**/*.csv
  2. our own extraction   data/extracted/**, corpus series outputs
  3. what the app renders grep the dashboard for its fetch() paths

The output is a CONSTRUCT / REVIEW / SKIP verdict per group, and it is evidence, not a
prior. A group that is already held is not a target no matter how many files it has.

Run:  python3 -B scripts/tools/survey_outside_brokers.py
"""
from __future__ import annotations

import glob
import json
import os
import re
import subprocess
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "data" / "derived" / "outside_brokers_survey.json"

GROUPS = ["02-hellenic", "03-breakwave", "04-poten", "05-seabrokers",
          "06-drewry", "07-signal", "08-baltic", "09-ppa", "archive", "books"]


def file_counts(group):
    base = REPO / "corpus" / group
    if not base.is_dir():
        return {}
    out = {}
    for root, _dirs, files in os.walk(base):
        rel = Path(root).relative_to(base)
        c = defaultdict(int)
        for f in files:
            ext = Path(f).suffix.lower().lstrip(".")
            c[ext or "none"] += 1
        if c:
            out[str(rel)] = dict(c)
    return out


def extracted_for(group):
    """What we have already extracted for this group, wherever it lives."""
    hits = defaultdict(int)
    for pat in (f"data/extracted/**/*{group.split('-')[-1]}*",
                f"data/extracted/series/*{group.split('-')[-1]}*",
                f"data/derived/*{group.split('-')[-1]}*"):
        for f in glob.glob(str(REPO / pat), recursive=True):
            hits[pat.split("*")[-1][:12]] += 1
    return dict(hits)


def feed_keywords():
    """Distinctive words from the feed filenames, to test membership cheaply."""
    names = []
    for f in glob.glob(str(REPO / "data" / "**" / "*.csv"), recursive=True):
        names.append(os.path.basename(f).lower())
    return names


def app_fetches():
    idx = REPO / "index.html"
    if not idx.exists():
        return []
    txt = idx.read_text(encoding="utf-8", errors="replace")
    return sorted(set(re.findall(r"""['"]([^'"]+\.(?:csv|json|parquet))['"]""", txt)))


def main():
    feeds = feed_keywords()
    fetches = app_fetches()
    print(f"live feed csv files : {len(feeds)}")
    print(f"app-rendered files  : {len(fetches)}")
    print()
    rows = []
    for g in GROUPS:
        counts = file_counts(g)
        tot = defaultdict(int)
        for d in counts.values():
            for k, v in d.items():
                tot[k] += v
        n = sum(tot.values())
        if not n:
            continue
        subs = sorted(counts)
        ex = extracted_for(g)
        # does any feed filename mention this group?
        key = g.split("-")[-1]
        in_feeds = [f for f in feeds if key in f]
        # does the app render anything from this group?
        in_app = [f for f in fetches if key in f.lower()]
        rows.append({"group": g, "files": dict(sorted(tot.items())), "total": n,
                     "subdirs": subs, "extracted": ex,
                     "feed_matches": in_feeds[:5], "app_matches": in_app[:5]})
    hdr = f"{'group':<16}{'files':>8}  {'extracted?':<10} {'in feeds?':<11} verdict"
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        nf = len(r["feed_matches"])
        na = len(r["app_matches"])
        ex = bool(r["extracted"])
        if ex or nf or na:
            v = "ALREADY HELD - review only"
        elif r["files"].get("pdf", 0) > 0:
            v = "CONSTRUCT candidate"
        else:
            v = "CONSTRUCT (html)"
        ext_s = "yes" if ex else "-"
        feed_s = f"{nf}" if nf else "-"
        print(f"{r['group']:<16}{r['total']:>8}  {ext_s:<10} {feed_s:<11} {v}")
        if r["feed_matches"]:
            print(f"    feeds: {r['feed_matches']}")
        if r["app_matches"]:
            print(f"    app  : {r['app_matches']}")
    OUT.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
