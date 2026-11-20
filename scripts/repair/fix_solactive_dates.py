#!/usr/bin/env python3
"""
One-shot repair of the Solactive freight-futures histories
(data/futures/bdryff_history.csv, data/futures/bwetff_history.csv).

What went wrong
---------------
Solactive's getDayHistoryChartData stamps each daily close at 00:00
Europe/Berlin. update_indices.py converted that with
``pd.to_datetime(ms, unit='ms')`` - i.e. in UTC - which is 22:00/23:00 on the
PREVIOUS calendar day. Every batch-sourced row therefore sat one day early:
Monday's close was stored on Sunday, Friday's on Thursday, and the files had
~780 Sundays and no Fridays at all before March 2026.

On 2026-03-13 the same-day live fallback (getIndexPerformance, converted in
Berlin time) started appending correctly dated rows. From then on the batch
row for Monday kept landing on Sunday and the live row landed on Monday, so
every week carried a Sunday duplicate.

Effects in the dashboard: the BDRYFF/BWETFF columns of every correlation
matrix read ~0.0 against the spot indices (same-day returns were really
"tomorrow vs today"), and every chart drew a weekend point.

Repair rule (deterministic, verified against the weekday histogram)
-------------------------------------------------------------------
* rows dated on/before the last all-batch day (2026-03-12): move +1 day
* later Sunday rows: they are the batch print of the following Monday; move
  them to Monday and, where the live Monday row also exists, keep the batch
  value (the official close rather than an evening live quote)
* duplicates created by the shift (the 2026-03-12 batch row becomes 03-13,
  which the first live row already holds) collapse to one row, batch first.

The script refuses to run unless the pre-boundary section still has the
signature of the bug (Sundays present, no Fridays), so running it twice is a
no-op rather than a second shift.

Usage:  python scripts/repair/fix_solactive_dates.py [--dry-run]
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
FILES = [ROOT / "data/futures/bdryff_history.csv", ROOT / "data/futures/bwetff_history.csv"]
LAST_ALL_BATCH_DAY = pd.Timestamp("2026-03-12")


def repair(path: Path, dry_run: bool) -> bool:
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"], format="%d-%m-%Y")
    pre = df[df["date"] <= LAST_ALL_BATCH_DAY]
    dows = pre["date"].dt.dayofweek
    if not ((dows == 6).sum() > 50 and (dows == 4).sum() == 0):
        print(f"{path.name}: no shifted-date signature (Sundays={int((dows == 6).sum())}, "
              f"Fridays={int((dows == 4).sum())}) - already repaired, nothing to do")
        return False

    before = df["date"].dt.dayofweek.value_counts().sort_index().to_dict()
    is_pre = df["date"] <= LAST_ALL_BATCH_DAY
    is_sun = df["date"].dt.dayofweek == 6
    batch = is_pre | is_sun
    df.loc[batch, "date"] = df.loc[batch, "date"] + pd.Timedelta(days=1)
    df["_batch"] = batch.astype(int)
    # batch (official close) wins over the live quote when both hit one date
    df = (df.sort_values(["date", "_batch"], ascending=[True, False])
            .drop_duplicates("date", keep="first")
            .drop(columns="_batch")
            .sort_values("date")
            .reset_index(drop=True))
    after = df["date"].dt.dayofweek.value_counts().sort_index().to_dict()
    weekend = int((df["date"].dt.dayofweek >= 5).sum())
    print(f"{path.name}: weekday histogram {before} -> {after}; weekend rows left: {weekend}")
    if weekend:
        print(f"{path.name}: refusing to write, weekend rows remain", file=sys.stderr)
        return False
    if not dry_run:
        out = df.copy()
        out["date"] = out["date"].dt.strftime("%d-%m-%Y")
        out.to_csv(path, index=False, lineterminator="\n")
        print(f"{path.name}: written ({len(out)} rows)")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    for f in FILES:
        repair(f, a.dry_run)


if __name__ == "__main__":
    main()
