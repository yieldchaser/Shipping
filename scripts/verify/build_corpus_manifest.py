"""
build_corpus_manifest.py - the source registry for the corpus/ data layer.

Records, for every source group: what it is, how often it publishes, whether it
is still publishing, where its files live, how many there are, and its date
range. This is the file a processing pass should read first, so it never has to
be told which sources exist or guess which are current.

Liveness rule (owner's): a publisher whose newest content is older than
STALE_DAYS cannot extend a series forward. Those live under corpus/archive/ and
must not enter the live processing path.

Usage:
    python scripts/verify/build_corpus_manifest.py
    python scripts/verify/build_corpus_manifest.py --check
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CORPUS_ROOT = REPO_ROOT / "corpus"
OUT_PATH = CORPUS_ROOT / "_MANIFEST.json"
STALE_DAYS = 200
TODAY = date(2026, 9, 23)

# group -> (human name, cadence, publisher, notes)
SOURCES = {
    "01-brokers": ("Shipbroker weekly market reports", "weekly", "18 firms",
                   "Live broker tree; PDFs are the ground truth, _digests/ holds normalised .md"),
    "02-hellenic": ("Hellenic Shipping News streams", "daily-weekly", "Hellenic Shipping News",
                    "iron_ore (MMi, daily), demolition, shipbuilding, dry/tanker charter, vessel valuations + chart assets"),
    "03-breakwave": ("Breakwave Advisors research", "weekly-daily", "Breakwave Advisors",
                     "insights/ (near-daily html + charts), drybulk/ + tankers/ (weekly PDF)"),
    "04-poten": ("Poten & Partners tanker opinions", "weekly", "Poten & Partners",
                 "pdfs paired with .md opinions, 2005-2026"),
    "05-seabrokers": ("Seabrokers offshore market intelligence", "monthly", "Seabrokers",
                      "97 monthly PDFs (ground truth) + working .md extraction"),
    "06-drewry": ("Drewry maritime intelligence", "weekly", "Drewry",
                  "ais/ (AIS weekly PDFs), opinions/ (sector briefs)"),
    "07-signal": ("The Signal Group maritime intelligence", "weekly", "Signal Ocean/Maritime",
                  "monitors/, newsroom/, images/, html/, pdfs/"),
    "08-baltic": ("Baltic Exchange fixture archive", "weekly", "Baltic Exchange",
                  "HTML fixture circulars by category/year"),
    "09-ppa": ("Pilbara Ports Authority throughput", "monthly", "Pilbara Ports Authority",
               "Port Hedland + Dampier cargo statistics"),
    "11-other": ("Other / regional sources", "varies", "various",
                 "Panama Canal advisories and anything not fitting a named group"),
    "archive": ("ARCHIVED - publishers that stopped", "stopped", "various",
                "Historical/knowledge-extraction use ONLY; must not enter the live pipeline"),
    "books": ("Foundational maritime economics literature", "static", "various",
              "12 textbooks, reference corpus for the knowledge base"),
}

DATE_PATS = [
    (re.compile(r"(20\d{2})[-_](\d{2})[-_](\d{2})"), "ymd"),
    (re.compile(r"A(20\d{2})(\d{2})(\d{2})"), "ymd"),
    (re.compile(r"(\d{2})[-_](\d{2})[-_](20\d{2})"), "dmy"),
    (re.compile(r"(20\d{2})[-_]W(\d{2})", re.I), "yw"),
    (re.compile(r"Week[-_ ]?(\d{1,2})[-_ ]?(20\d{2})", re.I), "wy"),
]


def newest_date(root: Path) -> date | None:
    latest = None
    for f in root.rglob("*"):
        if not f.is_file():
            continue
        for pat, kind in DATE_PATS:
            m = pat.search(f.name)
            if not m:
                continue
            try:
                if kind == "ymd":
                    dt = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                elif kind == "dmy":
                    dt = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
                elif kind == "yw":
                    dt = date.fromisocalendar(int(m.group(1)), int(m.group(2)), 1)
                else:
                    dt = date.fromisocalendar(int(m.group(2)), int(m.group(1)), 1)
            except Exception:
                continue
            if latest is None or dt > latest:
                latest = dt
            break
    return latest


def build() -> dict:
    groups = []
    for name, (desc, cadence, publisher, notes) in SOURCES.items():
        root = CORPUS_ROOT / name
        if not root.is_dir():
            groups.append({"group": name, "exists": False, "description": desc})
            continue
        files = [f for f in root.rglob("*") if f.is_file()]
        by_ext: dict[str, int] = {}
        for f in files:
            by_ext[f.suffix.lower()] = by_ext.get(f.suffix.lower(), 0) + 1
        nd = newest_date(root)
        age = (TODAY - nd).days if nd else None
        archived = name == "archive"
        entry = {
            "group": name,
            "description": desc,
            "publisher": publisher,
            "cadence": cadence,
            "notes": notes,
            "path": f"corpus/{name}",
            "files": len(files),
            "by_extension": dict(sorted(by_ext.items(), key=lambda kv: -kv[1])),
            "newest_content_date": str(nd) if nd else None,
            "age_days": age,
            "status": ("ARCHIVED" if archived else
                       ("LIVE" if (age is not None and age <= STALE_DAYS) else
                        ("STALE" if age is not None else "UNKNOWN"))),
            "in_live_processing_path": (not archived) and (age is not None and age <= STALE_DAYS),
        }
        if name in ("01-brokers", "archive"):
            subs = sorted(p.name for p in root.iterdir()
                          if p.is_dir() and not p.name.startswith("_"))
            entry["members"] = subs
        groups.append(entry)
    return {
        "generated_for": str(TODAY),
        "stale_threshold_days": STALE_DAYS,
        "liveness_rule": ("A publisher whose newest content is older than the "
                          "threshold cannot extend a series forward; it belongs in "
                          "corpus/archive/ and must not enter the live pipeline."),
        "groups": groups,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    cur = build()
    if args.check:
        if not OUT_PATH.exists():
            print(f"FAIL: {OUT_PATH} missing")
            return 1
        old = json.loads(OUT_PATH.read_text(encoding="utf-8"))
        og = {g["group"]: g.get("files") for g in old.get("groups", [])}
        cg = {g["group"]: g.get("files") for g in cur["groups"]}
        drift = {k: (og.get(k), cg.get(k)) for k in set(og) | set(cg) if og.get(k) != cg.get(k)}
        if drift:
            print("FAIL: manifest drifted")
            for k, v in drift.items():
                print(f"  {k}: recorded={v[0]} on_disk={v[1]}")
            return 1
        print("OK: manifest matches on-disk counts")
        return 0
    OUT_PATH.write_text(json.dumps(cur, indent=2), encoding="utf-8")
    print(f"{'group':<14}{'files':>7}  {'newest':<12}{'age':>6}  status")
    for g in cur["groups"]:
        print(f"{g['group']:<14}{g.get('files',0):>7}  {str(g.get('newest_content_date')):<12}"
              f"{str(g.get('age_days')):>6}  {g.get('status')}")
    live = sum(1 for g in cur["groups"] if g.get("in_live_processing_path"))
    print(f"\nwrote {OUT_PATH.relative_to(REPO_ROOT)} - {live} groups in the live path")
    return 0


if __name__ == "__main__":
    sys.exit(main())
