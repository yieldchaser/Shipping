#!/usr/bin/env python3
"""Build complete commercial vessel registry and instant search index.

Extracts all 57,256 commercial vessels across Dry Bulk, Tankers, LNG, and LPG
1. data/views/signal/vessel_lookup.json - Indexed dictionary with full particulars
2. data/views/signal/vessel_search_index.json - Compact array for client-side search
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

VESSEL_FILES = [
    ROOT / "data" / "geospatial" / "signal_vessels_dry_bulk.json",
    ROOT / "data" / "geospatial" / "signal_vessels_tankers.json",
    ROOT / "data" / "geospatial" / "signal_vessels_lng.json",
    ROOT / "data" / "geospatial" / "signal_vessels_lpg.json"
]

OUT_LOOKUP = ROOT / "data" / "views" / "signal" / "vessel_lookup.json"
OUT_SEARCH = ROOT / "data" / "views" / "signal" / "vessel_search_index.json"

def main():
    print("Extracting Signal Ocean commercial vessel registry...")
    lookup = {}
    search_index = []

    for fpath in VESSEL_FILES:
        if not fpath.exists():
            print(f"Warning: {fpath} not found, skipping.")
            continue
        print(f"Reading {fpath.name}...")
        with open(fpath, "r", encoding="utf-8") as f:
            vessels = json.load(f)
            for v in vessels:
                imo = v.get("imo")
                if not imo or str(imo) == "0":
                    continue
                imo_str = str(imo)
                name = (v.get("vesselName") or "").strip()
                vclass = (v.get("vesselClass") or "").strip()
                dwt = int(v.get("deadweight") or 0)
                built = int(v.get("yearBuilt") or 0)
                op = (v.get("companyName") or "Unknown").strip()
                if op == "Unknown" and v.get("synonyms"):
                    op = v.get("synonyms").strip()
                scrubbers = bool(v.get("scrubbers"))
                vtype = v.get("vesselTypeId") or 0
                liq_cap = int(v.get("liquidCapacity") or 0)

                if imo_str in lookup:
                    existing = lookup[imo_str]
                    if existing.get("op") in ("Unknown", "", "—") and op not in ("Unknown", "", "—"):
                        existing["op"] = op
                    if not existing.get("name") and name:
                        existing["name"] = name
                    continue

                rec = {
                    "name": name,
                    "class": vclass,
                    "dwt": dwt,
                    "built": built,
                    "op": op,
                    "scrubbers": scrubbers,
                    "type": vtype
                }
                if liq_cap > 0:
                    rec["liquidCap"] = liq_cap

                lookup[imo_str] = rec

    print(f"Total unique commercial vessels compiled: {len(lookup):,}")

    for imo_str, info in lookup.items():
        search_index.append([
            int(imo_str),
            info["name"],
            info["class"],
            info["dwt"],
            info["op"]
        ])

    search_index.sort(key=lambda x: (x[1].lower() if x[1] else "zzzz", x[0]))

    OUT_LOOKUP.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_LOOKUP, "w", encoding="utf-8") as f:
        json.dump(lookup, f, separators=(",", ":"))
    print(f"Wrote {OUT_LOOKUP} ({OUT_LOOKUP.stat().st_size:,} bytes)")

    with open(OUT_SEARCH, "w", encoding="utf-8") as f:
        json.dump(search_index, f, separators=(",", ":"))
    print(f"Wrote {OUT_SEARCH} ({OUT_SEARCH.stat().st_size:,} bytes)")

if __name__ == "__main__":
    main()
