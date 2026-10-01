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
import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
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
    # date sanity - accept a capitalised spelling ("Date") too. The checker
    # previously reported "no date column" and SKIPPED 4 of its own targets
    # whose header was merely capitalised (measured 2026-10-01).
    date_col = next((c for c in df.columns if str(c).strip().lower() == "date"), None)
    if date_col is None:
        warnings.append(f"{rel}: no 'date' column (may be intentional)")
        return
    d = pd.to_datetime(df[date_col], errors="coerce")
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


def scan_json(rel: str):
    """Validate a NON-CSV (JSON) frontend-bound view.

    The safeFetch audit collects EVERY data/ + knowledge/ target, and
    data/views/signals/cape_ffa_distribution.json is one of them. Reading it
    with pd.read_csv produced a phantom "DUPLICATE COLUMNS / ZERO DATA ROWS"
    CRITICAL - an instrument bug, not a data defect (measured 2026-10-01).
    """
    path = ROOT / rel
    if not path.exists():
        critical.append(f"{rel}: FILE MISSING (frontend binds it)")
        return
    size = path.stat().st_size
    if size < 200:
        warnings.append(f"{rel}: only {size} bytes - likely empty")
    try:
        obj = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception as e:  # noqa: BLE001
        critical.append(f"{rel}: UNPARSEABLE JSON ({e})")
        return
    if not obj:
        critical.append(f"{rel}: EMPTY JSON payload - frontend renders blank")
        return
    n = len(obj) if isinstance(obj, (dict, list)) else 1
    print(f"OK   {rel:55s} json keys={n:>6} bytes={size}")


def main():
    html = INDEX.read_text(encoding="utf-8", errors="replace")
    targets = sorted(set(re.findall(r"safeFetch\('((?:data|knowledge)/[^']+)'", html)))
    csv_targets = [t for t in targets if not t.lower().endswith(".json")]
    json_targets = [t for t in targets if t.lower().endswith(".json")]
    print(f"{len(targets)} frontend-bound data files "
          f"({len(csv_targets)} csv / {len(json_targets)} json)")
    for t in csv_targets:
        try:
            scan_csv(t)
        except Exception as e:  # noqa: BLE001
            critical.append(f"{t}: scanner error {e}")
    for t in json_targets:
        try:
            scan_json(t)
        except Exception as e:  # noqa: BLE001
            critical.append(f"{t}: scanner error {e}")

    print()
    print("==== WARNINGS ====")
    for w in warnings:
        print(" -", w)
    print()
    print("==== CRITICAL ====")
    for c in critical:
        print(" !", c)
    if critical:
        sys.exit(1)
    print()
    print("All frontend-bound datasets pass integrity checks.")


if __name__ == "__main__":
    main()
