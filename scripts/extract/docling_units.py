"""Harvest UNIT ANNOTATIONS with Docling, at sample scale.

Why this and not bulk extraction: the probe measured Docling at 129 s/page, i.e.
3,590 CPU-hours per 100k pages - ~150 days for this corpus. It cannot be a bulk
engine, and it drops cells anyway (its own log: "1 of 102 pdf cells matched
neither a row nor a column band ... and were dropped").

But its output annotates values with units INLINE, which is exactly the gap that
left 39.2% of our series unitless:

    SGX Iron Ore (CFR Qingdao) 62% Fe Fines    August 25 USD/dmt
    DCE Iron Ore 62% Fines                      I2509 (September) RMB/t (3pm close)

So the job is to run it on a bounded sample of the HIGH-VALUE tables - the
proprietary MMi index/brand tables and Chinese port-stock tables - harvest
"entity -> unit" pairs, and project those onto the matching corpus series.

The converter is built ONCE and reused: model load is ~5 minutes on this box, so
per-document invocation would be dominated by startup.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
import time

# entity (as it appears in the report) -> unit, harvested from Docling markdown
UNIT_AFTER = re.compile(
    r"(?P<entity>[A-Za-z][A-Za-z0-9%&/\-\.' ]{2,60}?)\s+"
    r"(?P<value>[\d,]+(?:\.\d+)?)\s*"
    r"(?P<unit>USD\s*/\s*(?:dmt|dry\s*tonne|t|tonne|teu|day)|RMB\s*/\s*(?:t|tonne|mt)|"
    r"USD|RMB|%|million\s*mt)", re.I)

UNIT_NEAR = re.compile(
    r"(?P<entity>[A-Za-z][A-Za-z0-9%&/\-\.' ]{2,60}?)"
    r"[^\n]{0,80}?(?P<unit>USD\s*/\s*(?:dmt|dry\s*tonne|t|tonne|teu|day)|"
    r"RMB\s*/\s*(?:t|tonne|mt)|million\s*mt)", re.I)

DEFAULT_SAMPLE = [
    # a spread across the high-value proprietary tables
    "reports/hellenic/iron_ore/pdfs/*mmi-daily-iron-ore-index-report-july-24-2025*.pdf",
    "reports/hellenic/iron_ore/pdfs/*mmi-daily-iron-ore-index-report-august-26-2025*.pdf",
    "reports/hellenic/iron_ore/pdfs/*mmi-daily-iron-ore-index-report-september-10-2025*.pdf",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=2, help="pages per doc (cost control)")
    ap.add_argument("--out", default="data/extracted/docling_units.json")
    ap.add_argument("--sample-file", default=None)
    a = ap.parse_args()

    paths = []
    if a.sample_file:
        paths = [p.strip() for p in open(a.sample_file) if p.strip()]
    else:
        for pat in DEFAULT_SAMPLE:
            paths += sorted(glob.glob(pat))[:1]
    paths = [p for p in paths if os.path.exists(p)]
    print(f"docs to process: {len(paths)} (pages/doc capped at {a.pages})")
    for p in paths:
        print(f"   {os.path.basename(p)[:76]}")

    t0 = time.time()
    from docling.document_converter import DocumentConverter
    conv = DocumentConverter()
    print(f"converter built in {time.time()-t0:.0f}s (model load, paid once)")

    harvested: dict[str, dict] = {}
    per_doc = []
    for i, p in enumerate(paths, 1):
        t1 = time.time()
        try:
            res = conv.convert(p, page_range=(1, a.pages))
            md = res.document.export_to_markdown()
        except Exception as e:
            print(f"  [{i}] FAILED {os.path.basename(p)[:50]}: {type(e).__name__} {str(e)[:90]}")
            continue
        dt = time.time() - t1
        found = 0
        for rx in (UNIT_AFTER, UNIT_NEAR):
            for m in rx.finditer(md):
                ent = re.sub(r"\s+", " ", m.group("entity")).strip(" .-|")
                unit = re.sub(r"\s+", " ", m.group("unit")).strip()
                if len(ent) < 3 or len(ent) > 60:
                    continue
                key = ent.lower()
                if key not in harvested:
                    harvested[key] = {"entity": ent, "unit": unit, "docs": 1}
                    found += 1
        per_doc.append({"doc": os.path.basename(p), "secs": round(dt, 1),
                        "markdown": len(md), "units_found": found})
        print(f"  [{i}] {os.path.basename(p)[:50]:<52} {dt:6.0f}s  units={found}")

    print(f"\n=== distinct entity->unit annotations: {len(harvested):,}")
    for k, v in list(harvested.items())[:30]:
        print(f"   {v['entity'][:44]:<46} {v['unit']}")

    json.dump({"per_doc": per_doc, "units": list(harvested.values())},
              open(a.out, "w", encoding="utf-8"), indent=1)
    print(f"\nwrote {a.out}")
    tot = sum(d["secs"] for d in per_doc)
    print(f"total conversion time: {tot:.0f}s for {len(per_doc)} docs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
