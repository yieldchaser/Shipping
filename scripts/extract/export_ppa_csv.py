#!/usr/bin/env python3
"""Rebuild the PPA deliverable CSVs from their JSONL checkpoints.

The PPA extractor (scripts/extract/publishers/run_ppa.py) writes an append-only
JSONL checkpoint, one record per parsed document, each carrying the document's
extracted rows.  The deliverable CSVs are built from that checkpoint by
de-duplicating on the value columns (the corpus holds byte-identical duplicate
documents under different filenames) and keeping the FIRST occurrence, so the
row order follows the extractor's file order.

Usage:
    python3 scripts/extract/export_ppa_csv.py --family hedland
    python3 scripts/extract/export_ppa_csv.py --family dampier
"""
import argparse, csv, json
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTDIR = ROOT / "data" / "extracted" / "ppa"

SPEC = {
    "hedland": {
        "jsonl": "hedland_rows.jsonl",
        "csv": "ppa_hedland_trade_series.csv",
        "cols": ["date", "port", "direction", "commodity", "country", "tonnes", "source_file"],
        "key": ["date", "port", "direction", "commodity", "country", "tonnes"],
    },
    "dampier": {
        "jsonl": "dampier_rows.jsonl",
        "csv": "ppa_dampier_fy_series.csv",
        "cols": ["date", "fy", "month_label", "port", "metric", "value", "source_file"],
        "key": ["date", "fy", "month_label", "port", "metric", "value"],
    },
}


def build(family):
    spec = SPEC[family]
    seen = OrderedDict()
    with (OUTDIR / spec["jsonl"]).open(encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            rec = json.loads(line)
            for row in rec["rows"]:
                k = tuple(str(row[c]) for c in spec["key"])
                if k not in seen:
                    seen[k] = row
    out = OUTDIR / spec["csv"]
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=spec["cols"])
        w.writeheader()
        for row in seen.values():
            w.writerow({c: row[c] for c in spec["cols"]})
    return len(seen), out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--family", choices=sorted(SPEC), required=True)
    args = ap.parse_args()
    n, out = build(args.family)
    print("%s: wrote %d rows -> %s" % (args.family, n, out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
