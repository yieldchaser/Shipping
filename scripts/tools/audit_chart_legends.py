"""Read chart legend labels off the PDF PAGE, and classify them against what we hold.

The per-document .charts.json keys its series by STROKE COLOUR, so the series NAME is
never in the file - it is printed on the page, positioned beside its own swatch. So this
reads the page: for each legend swatch (a short horizontal stroke with a distinct colour)
take the word immediately to its right. That word is the series name, and it is the only
honest way to know whether the chart is worth extracting.

THE USER'S RULE, made checkable
--------------------------------
Baltic Dry / Capesize / Panamax / Supramax / Handysize / Tanker Dry / Clean Tanker and
the 1-, 5- and 7-year time-charter averages are ALREADY HELD. Chart work on them restates
what we have - this is the same reason the Fearnleys Hasura API was skipped and the same
reason BDI/BDTI were not built. What is worth extracting is the PROPRIETARY series nobody
publishes as an index: newbuilding prices, S&P prices, demolition values, asset
valuations, forward curves on named routes or vessels.

So this script only CLASSIFIES. It does not extract. Every HOLD cites the file that
already holds the value, because an uncited skip is indistinguishable from laziness.

Run:  python3 -B scripts/tools/audit_chart_legends.py [--per-source N]
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
from collections import defaultdict
from pathlib import Path

import pymupdf

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "data" / "derived" / "chart_legend_audit.json"

# The held set, each entry citing the artefact that already carries the value.
HELD = {
    "b.d.i": "data/extracted/series/intermodal_baltic_tc_series.csv (2,189 pts 2020-2026)",
    "bci": "data/extracted/series/intermodal_baltic_tc_series.csv",
    "b.c.i": "data/extracted/series/intermodal_baltic_tc_series.csv",
    "bpi": "data/extracted/series/intermodal_baltic_tc_series.csv",
    "b.p.i": "data/extracted/series/intermodal_baltic_tc_series.csv",
    "bsi": "data/extracted/series/intermodal_baltic_tc_series.csv",
    "b.s.i": "data/extracted/series/intermodal_baltic_tc_series.csv",
    "bhsi": "data/extracted/series/intermodal_baltic_tc_series.csv",
    "b.h.s.i": "data/extracted/series/intermodal_baltic_tc_series.csv",
    "5tc bpi": "data/extracted/series/intermodal_baltic_tc_series.csv",
    "7tc bhsi": "data/extracted/series/intermodal_baltic_tc_series.csv",
    "10tc bsi": "data/extracted/series/intermodal_baltic_tc_series.csv",
    "1y tc": "intermodal + Hellenic dry_charter (held)",
    "1 year t/c": "intermodal + Hellenic dry_charter (held)",
    "5y tc": "intermodal_baltic_tc_series.csv AVR 5TC BPI",
    "7y tc": "intermodal_baltic_tc_series.csv AVR 7TC BHSI",
    "10y tc": "intermodal_baltic_tc_series.csv AVR 10TC BSI",
}

# Words that mark a series as NOVEL - proprietary, not a public index.
NOVEL = re.compile(
    r"newbuild|new\s*building|newbuilding|"
    r"s&p|sale|purchase|resale|demolition|scrap|scrapping|"
    r"valuation|value|asset|"
    r"steel|plate|"
    r"orderbook|order\s*book|fleet|"
    r"concession|pool|"
    r"cape(vessel)?|kamsar|panamax|supramax|handysize|"
    r"(52|56|58|63|64|68|69|70|74|76|77|82|86|96|98)\s*k",
    re.I)


def norm(s):
    return re.sub(r"[^a-z0-9]+", "", str(s).lower())


def legend_pairs(page):
    """(colour, label) for every legend swatch on a page.

    A swatch is a short horizontal stroke (~10-25pt wide, <2pt tall) with a stroke colour,
    drawn just LEFT of its own label. Taking the nearest word to the right of the swatch's
    own baseline is what ties a name to a colour; taking the nearest word in reading order
    would fuse adjacent legends.
    """
    words = [w for w in page.get_text("words")
             if w[4].strip() and not w[4].strip().isdigit()]
    out = []
    for d in page.get_drawings():
        r = d["rect"]
        if not (8 <= r.width <= 28) or r.height > 3.0:
            continue
        col = d.get("color") or d.get("fill")
        if not col:
            continue
        # label = the word whose left edge is just right of the swatch, same baseline
        cands = [w for w in words
                 if r.x1 - 1 <= w[0] <= r.x1 + 14
                 and abs(w[1] - r.y0) < 5]
        if not cands:
            continue
        lbl = min(cands, key=lambda w: w[0])[4].strip()
        out.append((tuple(round(c, 3) for c in col), lbl, round(r.x0, 1),
                    round(r.y0, 1)))
    return out


def classify(label, held_norm=None, class_only=None):
    """HOLD / NOVEL / UNKNOWN, with the held test using NORMALISED keys on both sides."""
    n = norm(label)
    held_norm = held_norm if held_norm is not None else {norm(k): v for k, v in HELD.items()}
    class_only = class_only if class_only is not None else re.compile(r"$^")
    if n in held_norm:
        return "HOLD", held_norm[n]
    for k, v in held_norm.items():
        if n.startswith(k) or k.startswith(n):
            return "HOLD", v
    if class_only.match(label):
        # a bare class name, optionally with a T/C horizon - both held
        return "HOLD", "vessel-class T/C / index label (held: intermodal_baltic_tc_series.csv)"
    if NOVEL.search(label):
        return "NOVEL", ""
    return "UNKNOWN", ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-source", type=int, default=8,
                    help="documents to sample per source (spread across years)")
    ap.add_argument("--source", default=None)
    args = ap.parse_args()

    srcs = [args.source] if args.source else [
        "advanced_shipping", "affinity", "agora", "fearnleys", "ism",
        "star_asia", "xclusiv", "ssy", "intermodal", "carriers", "lion",
        "banchero_costa", "clarksons"]
    # normalise the held keys ONCE. Comparing norm(label) against a RAW key meant
    # 'B.D.I' -> 'bdi' never matched the key 'b.d.i', so the most clearly held series in
    # the corpus fell through to UNKNOWN. A lookup table whose keys are never put through
    # its own normaliser is not a lookup table.
    held_norm = {norm(k): v for k, v in HELD.items()}
    # a bare vessel-class name is NOT novel. 'Capesize', 'Kamsarmax' and 'Handysize' are
    # the labels the Baltic charts use for the indices we already hold, so treating them
    # as proprietary would have marked the largest held set in the corpus as the top
    # build target - exactly the mistake this audit exists to prevent. A class name only
    # counts as novel when a proprietary MEASURE is attached to it ('Capesize 1Y TC' is a
    # held average; 'Capesize S&P' is a price series nobody publishes as an index).
    CLASS_ONLY = re.compile(
        r"^\s*(cape(size)?|panamax|kamsar(max)?|supra(max)?|handy(size|max)?|"
        r"aframax|suez(max)?|vlcc|ulcv|gc|lr1?|mr1?|tanker|dry|bulk(er)?)"
        r"[\s,./-]*\d{0,2}\s*(tc|t/c|time\s*charter|1y|5y|7y|10y)?\s*$", re.I)
    result = {}
    for src in srcs:
        pdfs = sorted(glob.glob(str(REPO / "corpus" / "01-brokers" / src / "**" / "*.pdf"),
                                recursive=True))
        if not pdfs:
            continue
        # spread the sample across the source's span, never only the newest or oldest
        n = min(args.per_source, len(pdfs))
        step = max(1, len(pdfs) // n)
        sample = pdfs[::step][:n]
        hold, novel, unknown = defaultdict(int), defaultdict(int), defaultdict(int)
        n_pairs = 0
        for p in sample:
            try:
                with pymupdf.open(p) as d:
                    for pg in d:
                        for col, lbl, x, y in legend_pairs(pg):
                            n_pairs += 1
                            kind, cite = classify(lbl, held_norm, CLASS_ONLY)
                            if kind == "HOLD":
                                hold[lbl] += 1
                            elif kind == "NOVEL":
                                novel[lbl] += 1
                            else:
                                unknown[lbl] += 1
            except Exception as e:                              # noqa: BLE001
                print(f"  {Path(p).name}: {str(e)[:80]}")
        result[src] = {
            "sampled": len(sample), "of": len(pdfs), "legend_pairs": n_pairs,
            "HOLD": dict(sorted(hold.items())),
            "NOVEL": dict(sorted(novel.items())),
            "UNKNOWN": dict(sorted(unknown.items())),
        }
        h, nv, uk = len(hold), len(novel), len(unknown)
        if nv and not h and not uk:
            verdict = f"CONSTRUCT - {nv} proprietary"
        elif h and not nv and not uk:
            verdict = "SKIP - every chart is a held index"
        elif h and nv:
            verdict = f"PARTIAL - {nv} proprietary, {h} held"
        else:
            verdict = f"REVIEW - {uk} unnamed labels"
        print(f"{src:<20} {len(sample):>3}/{len(pdfs):<5} swatches={n_pairs:<5} "
              f"HOLD={h:<3} NOVEL={nv:<3} UNK={uk:<3} {verdict}")
        for lbl, k in sorted(novel.items())[:6]:
            print(f"      NOVEL : {lbl[:64]} (x{k})")
        for lbl, k in sorted(unknown.items())[:6]:
            print(f"      ?      : {lbl[:64]} (x{k})")
    OUT.write_text(json.dumps(result, indent=1), encoding="utf-8")
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
