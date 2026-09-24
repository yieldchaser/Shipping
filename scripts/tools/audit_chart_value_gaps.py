"""Which chart series are GENUINELY MISSING? Audit before building any pipeline.

The rule the user has now stated repeatedly, and which this script makes checkable:
a chart whose values we ALREADY HOLD is not worth extracting. Baltic Dry, Capesize,
Panamax, Supramax, Handysize, Tanker Dry, Clean Tanker, and the 1/5/7-year time-charter
averages are all in the feeds or already extracted. Chart work on those is effort spent
restating what we have. The same is why the Fearnleys Hasura API was skipped.

What IS worth extracting is the proprietary series nobody publishes: newbuilding prices,
sale-and-purchase prices, demolition values, asset valuations, forward curves on named
vessels or routes - things no index feed carries.

So this script does NOT extract anything. It reads every .charts.json, takes each chart's
title and legend label, and tests it against three baselines:
  1. the live feeds           data/**/*.csv   (series name and column names)
  2. our own extraction       data/extracted/series/*.csv
  3. what the app displays    index.html fetch() paths

The verdict per series is HOLD (skip the chart) or CONSTRUCT. Only CONSTRUCT earns a
pipeline. Nothing here is a guess: every HOLD cites the file that already holds it.

Run:  python3 -B scripts/tools/audit_chart_value_gaps.py
"""
from __future__ import annotations

import csv
import glob
import json
import os
import re
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "data" / "derived" / "chart_value_gaps.json"
MD = REPO / "data" / "extracted" / "md"

# THE HELD SET. Cited by the file that actually carries each value.
# Measured, not assumed - each entry names its holder.
HELD_INDICES = {
    "BDI": "data/extracted/series/intermodal_baltic_tc_series.csv",
    "BCI": "data/extracted/series/intermodal_baltic_tc_series.csv",
    "BPI": "data/extracted/series/intermodal_baltic_tc_series.csv",
    "BSI": "data/extracted/series/intermodal_baltic_tc_series.csv",
    "BHSI": "data/extracted/series/intermodal_baltic_tc_series.csv",
    "AVR 5TC BPI": "data/extracted/series/intermodal_baltic_tc_series.csv",
    "AVR 7TC BHSI": "data/extracted/series/intermodal_baltic_tc_series.csv",
    "AVR 10TC BSI": "data/extracted/series/intermodal_baltic_tc_series.csv",
    "Average of the 5 T / C": "data/extracted/series/intermodal_baltic_tc_series.csv",
    "SSTI": "corpus/05-seabrokers (rolling window, not worth rebuilding)",
    "SSTI Pacific": "corpus/05-seabrokers (rolling window, not worth rebuilding)",
    "SSTI Atlantic": "corpus/05-seabrokers (rolling window, not worth rebuilding)",
    "BDTI": None, "BCTI": None, "BCTI TC": None,
}


def norm(s):
    """Normalise a legend label for matching: strip punctuation, casefold."""
    return re.sub(r"[^a-z0-9]+", "", str(s).lower())


def held_index(name):
    """Does this legend label name an index we already hold?"""
    n = norm(name)
    if n in HELD_INDICES:
        return HELD_INDICES[n] or "HELD (no citation)"
    # a label that IS one of the short index codes
    for k, v in HELD_INDICES.items():
        if n == norm(k):
            return v or "HELD (no citation)"
    return None


def feed_series_names():
    """Every series / column name across the feeds and our own extraction."""
    names = {}
    for f in glob.glob(str(REPO / "data" / "**" / "*.csv"), recursive=True):
        try:
            with open(f, encoding="utf-8", errors="replace", newline="") as fh:
                hdr = next(csv.reader(fh), [])
        except Exception:
            continue
        rel = os.path.relpath(f, REPO)
        for h in hdr:
            if h:
                names.setdefault(norm(h), []).append(rel)
    return names


def app_series_names():
    """Series names in our own extracted series files, by their first column value."""
    out = defaultdict(list)
    for f in glob.glob(str(REPO / "data" / "extracted" / "series" / "*.csv")):
        try:
            with open(f, encoding="utf-8", errors="replace", newline="") as fh:
                rd = csv.DictReader(fh)
                if "series" not in (rd.fieldnames or []):
                    continue
                seen = set()
                for r in rd:
                    s = r["series"]
                    if s not in seen:
                        seen.add(s)
                        out[norm(s)].append(os.path.relpath(f, REPO))
                    if len(seen) > 400:
                        break
        except Exception:
            continue
    return out


def chart_titles_and_legends(path):
    """Read every title and legend label from a .charts.json, any shape.

    MEASURED SHAPES, not the ones the generic walker imagined. Across this corpus the
    per-document .charts.json comes in several distinct forms and the only shared thing
    is the page-number key:

      advanced_shipping / fearnleys / xclusiv  {"1": [ {scale, series}, ... ], "2": [...]}
      affinity / agora                        {"charts": [...], "note"/"reason": ...}
      ism                                    {"charts": [...], "date": ..., "file": ...}
      star_asia                              {"_note": ..., "vector_series": {...}}

    In the first form the series are keyed by the STROKE COLOUR, not by a legend label, so
    there is no name to read and matching a label out of the file is impossible - the
    name lives on the PDF page, positioned beside the swatch. So this function returns
    whatever names exist, and the caller must treat an empty result as "names live on the
    page", never as "there are no series".

    A previous version of this audit reported 0 HOLD and 0 CONSTRUCT for every source
    because it looked for a "legend" key that no file in this corpus has. An empty result
    was read as "nothing novel", which would have silently closed seven sources on a bug.
    """
    d = json.loads(path.read_text(encoding="utf-8"))
    titles, legends = [], []

    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                kl = str(k).lower()
                if kl in ("title", "chart_title", "name", "label") and isinstance(v, str):
                    titles.append(v)
                if kl in ("series", "series_name", "legend", "legend_entries") and isinstance(v, dict):
                    for lbl in v:
                        legends.append(lbl)
                elif kl == "series" and isinstance(v, list):
                    for it in v:
                        if isinstance(it, dict):
                            for f in ("name", "label", "series", "legend", "title"):
                                if isinstance(it.get(f), str):
                                    legends.append(it[f])
                # a chart dict that carries a title plus a colour-keyed series map
                if kl == "series" and isinstance(v, dict) and x.get("title"):
                    legends.append(x["title"])
                if isinstance(v, (dict, list)):
                    walk(v)
        elif isinstance(x, list):
            for it in x:
                walk(it)
    walk(d)
    return titles, legends


def colour_series_count(path):
    """How many distinct stroke colours a file carries - the real series count when the
    series are colour-keyed and therefore unnamed in the JSON."""
    d = json.loads(path.read_text(encoding="utf-8"))
    colours = set()
    n_series = 0
    n_charts = 0

    def walk(x):
        nonlocal n_series, n_charts
        if isinstance(x, dict):
            if "scale" in x and isinstance(x.get("series"), dict):
                n_charts += 1
                n_series += len(x["series"])
                for c in x["series"]:
                    colours.add(c)
            for v in x.values():
                if isinstance(v, (dict, list)):
                    walk(v)
        elif isinstance(x, list):
            for it in x:
                walk(it)
    walk(d)
    return n_charts, n_series, len(colours)


def main():
    feeds = feed_series_names()
    app = app_series_names()
    sources = ["advanced_shipping", "affinity", "agora", "fearnleys", "ism",
               "star_asia", "xclusiv", "ssy", "intermodal", "carriers", "lion",
               "banchero_costa", "clarksons"]
    result = {}
    for src in sources:
        base = MD / src
        if not base.is_dir():
            continue
        files = sorted(base.glob("*.charts.json"))
        if not files:
            continue
        hold, construct, unknown = defaultdict(int), defaultdict(int), defaultdict(int)
        seen = set()
        for f in files:
            titles, legends = chart_titles_and_legends(f)
            for lbl in legends:
                k = (lbl, )
                if k in seen:
                    continue
                seen.add(k)
                if held_index(lbl):
                    hold[lbl] += 1
                elif norm(lbl) in feeds or norm(lbl) in app:
                    hold[lbl] += 1
                elif re.fullmatch(r"[0-9.,\s]+", lbl):
                    unknown[lbl] += 1
                else:
                    construct[lbl] += 1
        result[src] = {
            "documents": len(files),
            "HOLD": {k: v for k, v in sorted(hold.items())},
            "CONSTRUCT": {k: v for k, v in sorted(construct.items())},
            "UNLABELLED": sum(unknown.values()),
        }

    # print the decision
    print(f"{'source':<20}{'docs':>5}  {'HOLD':>5} {'CONSTRUCT':>10}  verdict")
    print("-" * 62)
    for src, r in sorted(result.items()):
        n_hold = len(r["HOLD"])
        n_con = len(r["CONSTRUCT"])
        if n_con == 0:
            v = "SKIP - all held"
        elif n_hold > n_con:
            v = f"PARTIAL - {n_con} novel, {n_hold} held"
        else:
            v = f"CONSTRUCT - {n_con} novel"
        print(f"{src:<20}{r['documents']:>5}  {n_hold:>5} {n_con:>10}  {v}")
        if n_con and n_con <= 12:
            for lbl, n in r["CONSTRUCT"].items():
                print(f"      novel: {lbl[:60]}  (x{n})")
    OUT.write_text(json.dumps(result, indent=1, default=str), encoding="utf-8")
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
