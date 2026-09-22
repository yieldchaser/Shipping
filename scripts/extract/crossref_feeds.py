"""Cross-reference extracted series against the live feeds.

Two jobs in one, which is why it is worth doing rather than inferring:
  1. UNIT     if our extracted "Capesize" series tracks the feed's Cape TCE, the
              unit is confirmed by evidence instead of asserted by convention.
  2. TRUTH    if it does NOT track, that is a finding about our extraction - a
              mislabelled row, a misparsed column, or a wrong series - which no
              internal check can surface, because internally the series is
              self-consistent.

Method: align on date, then compare the two value series. A near-constant RATIO
means the same quantity in a different unit (so the unit is identified by the ratio
itself, e.g. ratio ~1 -> identical units). A high Pearson correlation with a
wandering ratio means same shape, different basis. Neither means no match.
"""
from __future__ import annotations

import csv
import glob
import json
import os
import re
import sys


def load_feed(path: str) -> dict[str, float]:
    """Feed CSV -> {date: value}; uses the first date-ish column and first numeric."""
    out: dict[str, float] = {}
    try:
        with open(path, encoding="utf-8", errors="replace", newline="") as f:
            rdr = csv.reader(f)
            head = next(rdr, None)
            if not head:
                return out
            di = next((i for i, h in enumerate(head)
                       if re.search(r"date|day|period", h, re.I)), 0)
            vi = next((i for i, h in enumerate(head)
                       if re.search(r"value|price|rate|close|level|tce|index", h, re.I)), None)
            for row in rdr:
                if len(row) <= max(di, vi or 0):
                    continue
                m = re.search(r"(19|20)\d\d-[01]\d-[0-3]\d", row[di] or "")
                if not m:
                    continue
                idx = vi if vi is not None else (di + 1)
                if idx >= len(row):
                    continue
                try:
                    out[m.group(0)] = float(str(row[idx]).replace(",", ""))
                except ValueError:
                    pass
    except OSError:
        pass
    return out


def corr(a: list[float], b: list[float]) -> float:
    n = len(a)
    if n < 5:
        return float("nan")
    ma, mb = sum(a) / n, sum(b) / n
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((x - mb) ** 2 for x in b)
    if va == 0 or vb == 0:
        return float("nan")
    cov = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    return cov / (va ** 0.5 * vb ** 0.5)


DELTA_NAME = re.compile(
    r"y-o-y|yoy|w-o-w|mom|qoq|ytd|mtd|qtd|change|delta|diff|variance|%|5 years|"
    r"10 years|20 years|average|avg|dwt|million mt|\bno\b|count",
    re.I)


def nearest_align(a: dict[str, float], b: dict[str, float], tol: int = 3):
    """Match dates allowing a small offset: these reports are weekly while the
    feeds are daily, so exact-date intersection throws away most of the overlap."""
    import datetime as dt
    bd = {}
    for k in b:
        try:
            bd[dt.date.fromisoformat(k)] = b[k]
        except ValueError:
            continue
    keys = sorted(bd)
    if not keys:
        return []
    pairs = []
    for k, v in a.items():
        try:
            d = dt.date.fromisoformat(k)
        except ValueError:
            continue
        best = min(keys, key=lambda x: abs((x - d).days))
        if abs((best - d).days) <= tol:
            pairs.append((v, bd[best]))
    return pairs


def main() -> int:
    import duckdb
    con = duckdb.connect("data/extracted/corpus/db/corpus.duckdb", read_only=True)

    # candidate feed files: named rates/indices
    feeds = []
    for pat in ("data/indices/*historical*.csv", "data/indices/*.csv",
                "data/clarksons/*continuous*.csv", "data/futures/*history*.csv"):
        feeds += glob.glob(pat)
    print(f"feed files: {len(feeds)}")

    # candidate extracted series, by keyword
    CANDS = {
        "cape": ("cape", "capesize"), "panamax": ("panamax",), "supramax": ("supramax",),
        "handysize": ("handysize",), "bdi": ("bdi",), "bpi": ("bpi",),
        "bci": ("bci",), "bsi": ("bsi",), "vlcc": ("vlcc",), "suezmax": ("suezmax",),
        "aframax": ("aframax",),
    }

    rows = con.execute("""
        select series_id, entity, measurement, points from series
        where points >= 30 order by points desc limit 1500""").fetchall()
    print(f"extracted series considered: {len(rows)}")

    results = []
    for fpath in feeds:
        fname = os.path.basename(fpath).lower()
        for key, pats in CANDS.items():
            if not any(p in fname for p in pats):
                continue
            feed = load_feed(fpath)
            if len(feed) < 30:
                continue
            for sid, ent, meas, pts in rows:
                blob = f"{ent} {meas}".lower()
                if not any(p in blob for p in pats):
                    continue
                # levels only: a change series compared against a level produces
                # a meaningless correlation and poisons the ranking
                if DELTA_NAME.search(f"{ent} {meas}"):
                    continue
                series = con.execute(
                    "select date, value from series_points where series_id=?",
                    [sid]).fetchall()
                sv = {str(d): v for d, v in series}
                pairs = nearest_align(sv, feed)
                if len(pairs) < 20:
                    continue
                a = [x for x, _ in pairs]
                b = [y for _, y in pairs]
                common = list(range(len(pairs)))
                ratios = [x / y for x, y in zip(a, b) if y]
                if not ratios:
                    continue
                ratios.sort()
                med = ratios[len(ratios) // 2]
                spread = (ratios[-1] - ratios[0]) / med if med else 9e9
                r = corr(a, b)
                results.append({
                    "feed_file": os.path.basename(fpath), "series_id": sid,
                    "entity": ent, "measurement": meas, "overlap_days": len(common),
                    "corr": round(r, 4) if r == r else None,
                    "median_ratio": round(med, 4), "ratio_spread": round(spread, 3),
                })

    results.sort(key=lambda x: -(x["corr"] or -2))
    print(f"\ncomparable pairs: {len(results)}")
    print(f"\n{'corr':>7}{'ratio':>9}{'spread':>8}{'days':>6}  feed -> extracted")
    for r in results[:24]:
        c = f"{r['corr']:.3f}" if r["corr"] is not None else "  n/a"
        print(f"{c:>7}{r['median_ratio']:>9}{r['ratio_spread']:>8}{r['overlap_days']:>6}  "
              f"{r['feed_file'][:26]:<28}{str(r['entity'])[:18]}/{str(r['measurement'])[:16]}")

    confirmed = [r for r in results if (r["corr"] or 0) > 0.95]
    print(f"\nHIGH-CONFIDENCE unit confirmations (corr>0.95): {len(confirmed)}")
    for r in confirmed[:10]:
        print(f"   ratio {r['median_ratio']:.3f} (spread {r['ratio_spread']:.3f})  "
              f"{r['entity'][:20]} vs {r['feed_file'][:30]}")

    json.dump(results, open("data/extracted/feed_crossref.json", "w", encoding="utf-8"),
              indent=1)
    print("\nwrote data/extracted/feed_crossref.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
