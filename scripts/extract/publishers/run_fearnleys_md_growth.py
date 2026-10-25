"""
Fearnleys Dry Bulk Weekly: the shipment-volume and fleet-supply growth figures printed in the text.

The weekly's charts (shipment volumes, tightness indicators, composite models) are raster images with no
embedded data, so nothing is read off them. Since 2026 the commentary prints the figures behind the
volume charts per segment, e.g. "Shipment volumes were up 2.8% year on year through week 41" or
"DWT supply growth remains at 3.2%". Those printed numbers are the series.

An earlier prose regex mixed up volume and supply growth and was deleted (see run_fearnleys_md_full_power).
So every pattern here reads one clause in which the metric words sit directly before or around the
number; a figure is never taken from a neighbouring clause. Approximate wording ("around 0%", "under 3%",
"slightly over 4%") is not a figure and is skipped; so is a direction word that contradicts the printed
sign ("down +0.3%"). The segment is the report section (## Capesize/Newcastlemax ...) the clause is in;
clauses about sub-trades ("South Atlantic shipment volumes", "Iron ore shipments from Brazil") do not
match. Each row keeps the clause it was read from. An issue can print two figures for one metric (the
commentary and a chart note carried over from an earlier week, e.g. supply growth 5.2% and 5.1% on
2026-08-12); both are kept as printed, each with its clause.

Output (rebuilt from the MDs on every run): data/extracted/series/fearnleys_drybulk_growth_series.csv
  issue_date, segment, metric, through_week, last_weeks, value_pct, clause, source_file
  metric: volume_growth_ytd_pct (year to date vs the same weeks last year, through_week = the printed week)
          volume_growth_last_weeks_pct (last N weeks vs the same weeks last year, last_weeks = N)
          supply_growth_pct (DWT fleet supply growth, year on year, latest reading)
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MD_DIR = ROOT / "data" / "extracted" / "md" / "fearnleys-md"
OUT = ROOT / "data" / "extracted" / "series" / "fearnleys_drybulk_growth_series.csv"
FIELDS = ["issue_date", "segment", "metric", "through_week", "last_weeks", "value_pct", "clause", "source_file"]

SEGMENTS = {"capesize": "Capesize", "panamax": "Panamax", "supramax": "Supramax", "handysize": "Handysize"}
SEG_NAMES = r"(?:Capesize|Newcastlemax|Panamax|Kamsarmax|Supramax|Ultramax|Handysize|total) "
NUM = r"([+-]?\d+(?:\.\d+)?)%"
WEEK = r"week (\d{1,2})"
N_WEEKS = r"(\d{1,2}|two|four|six|eight|ten|twelve)"
WORDS = {"two": 2, "four": 4, "six": 6, "eight": 8, "ten": 10, "twelve": 12}
YOY = r"(?:year[ -]on[ -]year|than last year|than the same period (?:in|of) (?:20\d\d|last year)|compared to last year)"

YTD, LAST, SUPPLY = "volume_growth_ytd_pct", "volume_growth_last_weeks_pct", "supply_growth_pct"
# (metric, pattern); named groups: week, n, val, dir (up|down|higher|lower, applied to an unsigned number)
PATTERNS = [
    (YTD, r"[Tt]hrough " + WEEK.replace("(", "(?P<week>", 1) + r", (?:" + SEG_NAMES + r")?shipment volumes were "
          r"(?:(?P<dir>up|down) )?" + NUM.replace("(", "(?P<val>", 1) + r"(?: (?P<dir2>higher|lower))?(?: " + YOY + r")?"),
    (YTD, r"[Tt]hrough " + WEEK.replace("(", "(?P<week>", 1) + r", (?:" + SEG_NAMES + r")?shipment volumes? grew by "
          r"(?:an estimated )?" + NUM.replace("(", "(?P<val>", 1)),
    (YTD, r"[Tt]hrough " + WEEK.replace("(", "(?P<week>", 1) + r", (?:shipment )?volume growth (?:was|grew by)"
          r"(?: an estimated)? " + NUM.replace("(", "(?P<val>", 1)),
    (YTD, r"[Tt]hrough " + WEEK.replace("(", "(?P<week>", 1) + r", growth was " + NUM.replace("(", "(?P<val>", 1)
          + r"(?=, compared to (?:DWT )?supply growth)"),
    (YTD, r"(?<![a-z] )[Ss]hipment volumes were (?:(?P<dir>up|down) )?" + NUM.replace("(", "(?P<val>", 1)
          + r"(?: (?P<dir2>higher|lower))? " + YOY + r" through " + WEEK.replace("(", "(?P<week>", 1)),
    (YTD, r"(?<![a-z] )[Ss]hipment volume growth was " + NUM.replace("(", "(?P<val>", 1) + r" through "
          + WEEK.replace("(", "(?P<week>", 1)),
    (LAST, r"(?:[Oo]ver|[Ii]n) the last " + N_WEEKS.replace("(", "(?P<n>", 1) + r" weeks, (?:shipment )?volume growth "
           r"was (?:also )?" + NUM.replace("(", "(?P<val>", 1)),
    (LAST, r"(?:[Oo]ver|[Ii]n) the last " + N_WEEKS.replace("(", "(?P<n>", 1) + r" weeks, (?:shipment )?volumes were "
           r"(?P<dir>up|down) " + NUM.replace("(", "(?P<val>", 1)),
    (LAST, r"[Cc]omparing the last " + N_WEEKS.replace("(", "(?P<n>", 1) + r" weeks (?:with|to) the same (?:weeks|period) "
           r"last year, shipment volume growth was (?:(?P<dir>up|down) )?" + NUM.replace("(", "(?P<val>", 1)),
    (SUPPLY, r"(?:DWT )?[Ss]upply [Gg]rowth (?:was|is|remains|continues)(?: at)?(?: just)? "
             + NUM.replace("(", "(?P<val>", 1)),
    (SUPPLY, r"(?:DWT )?[Ss]upply growth(?: rate)? of " + NUM.replace("(", "(?P<val>", 1)),
]
PATTERNS = [(m, re.compile(p)) for m, p in PATTERNS]
DIRECTION = {"up": 1, "higher": 1, "down": -1, "lower": -1}


def _value(m: re.Match) -> str | None:
    """The printed figure with the direction word applied; None when the word contradicts a printed sign."""
    raw = m.group("val")
    d = m.groupdict().get("dir") or m.groupdict().get("dir2")
    if d is None:
        return raw.lstrip("+")
    if raw[0] in "+-":
        return None if (raw[0] == "-") != (DIRECTION[d] < 0) else raw.lstrip("+")
    return ("-" + raw) if DIRECTION[d] < 0 else raw


def rows_of(text: str, issue_date: str, source: str) -> list[dict]:
    rows, seg = [], None
    for line in text.splitlines():
        if line.startswith("## "):
            head = line[3:].lower()
            seg = next((v for k, v in SEGMENTS.items() if k in head), None)
            continue
        if seg is None or line.startswith("!["):
            continue
        taken: list[tuple[int, int]] = []
        for metric, rx in PATTERNS:
            for m in rx.finditer(line):
                if any(a < m.end() and m.start() < b for a, b in taken):
                    continue
                val = _value(m)
                if val is None:
                    continue
                taken.append((m.start(), m.end()))
                g = m.groupdict()
                n = g.get("n")
                rows.append({
                    "issue_date": issue_date, "segment": seg, "metric": metric,
                    "through_week": g.get("week") or "",
                    "last_weeks": str(WORDS.get(n, n)) if n else "",
                    "value_pct": val, "clause": m.group(0), "source_file": source,
                })
    # the same figure printed twice in one issue (commentary and chart note) is one row
    seen, out = set(), []
    for r in rows:
        key = (r["segment"], r["metric"], r["through_week"], r["last_weeks"], r["value_pct"])
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


def build() -> list[dict]:
    rows = []
    for f in sorted(MD_DIR.glob("*/*dry-bulk-weekly*.md")):
        issue_date = f.name[:10]
        rows += rows_of(f.read_text(encoding="utf-8"), issue_date, f.relative_to(ROOT).as_posix())
    return rows


def main() -> int:
    rows = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="\n") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"fearnleys dry bulk growth: {len(rows)} rows from "
          f"{len({r['issue_date'] for r in rows})} issues -> {OUT.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
