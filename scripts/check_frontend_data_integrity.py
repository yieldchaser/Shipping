#!/usr/bin/env python3
"""
Repo-wide blank-chart / data-integrity scanner.

Checks every CSV the frontend binds to (safeFetch targets in index.html):
  1. file exists and is non-trivial (header-only files flagged)
  2. no duplicate column names (pandas ".1" twins) — the PapaParse shadowing bug
  3. required date column parses and spans recent history where applicable
  4. numeric payload columns are not 100% empty

Exit non-zero if any CRITICAL finding exists. Designed for CI.
"""
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(r"C:\Users\Dell\Github\Shipping")
INDEX = ROOT / "index.html"

critical = []
warnings = []


def scan_csv(rel: str):
    path = ROOT / rel
    if not path.exists():
        critical.append(f"{rel}: FILE MISSING (frontend binds it)")
        return
    size = path.stat().st_size
    if size < 200:
        warnings.append(f"{rel}: only {size} bytes — likely header-only/empty")
    try:
        df = pd.read_csv(path, nrows=500_000)
    except Exception as e:  # noqa: BLE001
        critical.append(f"{rel}: UNPARSEABLE ({e})")
        return

    # duplicate columns
    dupes = [c for c in df.columns if str(c).endswith(".1") or list(df.columns).count(c) > 1]
    base_dupes = sorted({str(c)[:-2] for c in df.columns if str(c).endswith(".1")})
    if dupes:
        critical.append(f"{rel}: DUPLICATE COLUMNS {base_dupes} — frontend sees shadowed empties")

    if len(df) == 0:
        critical.append(f"{rel}: ZERO DATA ROWS (header only)")
        return

    # date sanity
    if "date" not in df.columns:
        warnings.append(f"{rel}: no 'date' column (may be intentional)")
        return
    d = pd.to_datetime(df["date"], errors="coerce")
    n_bad = int(d.isna().sum())
    if n_bad:
        warnings.append(f"{rel}: {n_bad} unparseable dates")
    span = (d.min(), d.max())

    # numeric payload emptiness: any fully-empty numeric col is a warning;
    # ALL numeric cols empty is critical
    num_cols = df.select_dtypes("number").columns.tolist()
    filled = []
    for c in num_cols:
        s = pd.to_numeric(df[c], errors="coerce")
        if s.notna().any():
            filled.append(c)
    if num_cols and not filled:
        critical.append(f"{rel}: EVERY numeric column is empty — chart will render blank")
    elif len(filled) < max(1, len(num_cols) // 3):
        warnings.append(f"{rel}: most numeric columns empty ({len(filled)}/{len(num_cols)} filled)")

    print(f"OK   {rel:55s} rows={len(df):>6} span={span[0].date()}..{span[1].date()} "
          f"digits={len(filled)}/{len(num_cols)}")


def main():
    html = INDEX.read_text(encoding="utf-8", errors="replace")
    targets = sorted(set(re.findall(r"safeFetch\('((?:data|knowledge)/[^']+)'", html)))
    print(f"{len(targets)} frontend-bound data files\n")
    for t in targets:
        try:
            scan_csv(t)
        except Exception as e:  # noqa: BLE001
            critical.append(f"{t}: scanner error {e}")

    print("\n==== WARNINGS ====")
    for w in warnings:
        print(" -", w)
    print("\n==== CRITICAL ====")
    for c in critical:
        print(" !", c)
    if critical:
        sys.exit(1)
    print("\nAll frontend-bound datasets pass integrity checks.")


if __name__ == "__main__":
    main()
