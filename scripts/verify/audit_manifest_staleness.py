#!/usr/bin/env python3
"""Census: does data/provenance/manifest.json agree with the files on disk?

Reuses the manifest generator's OWN inspect_file() so the comparison is
apples-to-apples with what a regeneration would write. Read-only.

Run this after ANY job that rewrites a file under data/ that index.html fetches:
the registry is a hand-off artefact and does not update itself. Measured
2026-09-30: exactly 1 of 112 entries (indices_drewry_wci_historical) was stale
by 37 rows and 2 years of start date, because the WCI run grew its CSV and
never regenerated the registry.

  python3 scripts/verify/audit_manifest_staleness.py [--json OUT]
"""
import argparse
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
GEN = ROOT / "scripts" / "verify" / "build_provenance_manifest.py"


def load_generator():
    spec = importlib.util.spec_from_file_location("bpm", GEN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def census():
    bpm = load_generator()
    man = json.load(open(ROOT / "data/provenance/manifest.json", encoding="utf-8"))
    stale_rows, stale_span, missing, noprov, agree, skipped = [], [], [], [], 0, 0
    for e in man["series"]:
        sid, out = e.get("series_id"), e.get("output_file")
        if not out:
            noprov.append((sid, "NO output_file"))
            continue
        if not (ROOT / out).exists():
            missing.append((sid, out))
            continue
        if out.endswith(".parquet"):
            skipped += 1          # generator hardcodes row_count=1 for parquet
            continue
        info = bpm.inspect_file(out)
        dr = e.get("row_count") != info["row_count"]
        ds = (e.get("date_span") or None) != (info["date_span"] or None)
        if dr:
            stale_rows.append((sid, out, e.get("row_count"), info["row_count"]))
        if ds:
            stale_span.append((sid, out, e.get("date_span"), info["date_span"]))
        if not dr and not ds:
            agree += 1
    return {
        "total": len(man["series"]),
        "generated_at": man.get("generated_at"),
        "agree": agree,
        "stale_rows": stale_rows,
        "stale_span": stale_span,
        "missing": missing,
        "noprov": noprov,
        "parquet_skipped": skipped,
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=None, help="write the census as JSON here")
    a = ap.parse_args()
    c = census()
    print(f"manifest entries : {c['total']} (generated_at {c['generated_at']})")
    print(f"AGREE rows+span  : {c['agree']}")
    print(f"parquet skipped  : {c['parquet_skipped']}")
    print(f"STALE row_count  : {len(c['stale_rows'])}")
    for r in c["stale_rows"]:
        print("   ", r)
    print(f"STALE date_span  : {len(c['stale_span'])}")
    for r in c["stale_span"]:
        print("   ", r)
    print(f"MISSING file     : {len(c['missing'])}")
    for r in c["missing"]:
        print("   ", r)
    print(f"NO output_file   : {len(c['noprov'])}")
    for r in c["noprov"]:
        print("   ", r)
    if a.json:
        json.dump(c, open(a.json, "w"), indent=1)
    raise SystemExit(1 if (c["stale_rows"] or c["stale_span"] or c["missing"]) else 0)
