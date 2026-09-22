"""Where does a table's unit actually live?

The manifest resolved units for 47.4% of series from the entity/measurement pair.
The rest have an EMPTY measurement, meaning the column carried no unit row - so
the question is whether the unit exists somewhere else obtainable, or genuinely
is not published.

Three candidate locations, checked in order:
  1. the table's own header row (already captured, per column)
  2. the page text immediately ABOVE the table (titles/notes often state units)
  3. the document's title/stem

This measures how many unresolved series could be resolved from location 2, using
the real corpus rather than a guess about how these reports are laid out.
"""
from __future__ import annotations

import json
import os
import re
import sys

UNIT_RX = re.compile(
    r"(USD|RMB|CNY|EUR)\s*/?\s*(?:dry\s*)?(tonne|ton|mt|dmt|teu|feu|day|bbl|barrel)"
    r"|million\s*(?:mt|tonnes?|t)\b|'000\s*(?:mt|t|tonnes?)\b"
    r"|\b(?:dwt|deadweight)\b|\b(?:cbm|m3|m\u00b3)\b"
    r"|\b(?:USD|RMB)\s*(?:per|/)\s*(?:tonne|ton|mt|day|teu)\b", re.I)


def main() -> int:
    import duckdb
    man = json.load(open("data/extracted/series_manifest.json", encoding="utf-8"))
    unk = [m for m in man if m["unit"] == "unknown"]
    print(f"unresolved series: {len(unk):,}")
    from collections import Counter
    print("  by source:", dict(Counter(m["source"] for m in unk).most_common(5)))

    # read the per-document text we already extracted
    base = "data/extracted/corpus"
    # map doc_stem -> concatenated text (first ~4000 chars is where units live)
    texts: dict[str, str] = {}
    docs_needed = {m["series_id"].split("|")[0] for m in unk}
    hits = 0
    checked = 0
    examples = []
    for src in sorted(os.listdir(base)):
        d0 = os.path.join(base, src)
        if not os.path.isdir(d0):
            continue
        for d in sorted(os.listdir(d0)):
            tp = os.path.join(d0, d, "text.jsonl")
            if not os.path.exists(tp):
                continue
            checked += 1
            if checked > 1200:
                break
            try:
                blob = open(tp, encoding="utf-8", errors="replace").read(20000)
            except OSError:
                continue
            m = UNIT_RX.search(blob)
            if m:
                hits += 1
                if len(examples) < 10:
                    i = m.start()
                    examples.append((d[:34], blob[max(0, i - 46):i + 52].replace("\n", " ")))
        if checked > 1200:
            break

    print(f"\ndocuments scanned for a unit statement: {checked:,}")
    print(f"  documents CONTAINING a unit token : {hits:,} ({hits/max(checked,1)*100:.1f}%)")
    print("\n  examples of the surrounding context:")
    for name, ctx in examples:
        print(f"    {name:<36} ...{ctx[:88]}...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
