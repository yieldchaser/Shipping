"""Resolve units from the VALUE's own formatting, not from guessed conventions.

Why this is better: the previous pass inferred a unit from the series' entity and
measurement strings and was wrong ~17% of the time, because two short labels often
do not determine a unit. But the raw cell strings carry the unit themselves:

    "$30,487"   "$52,696"   "$1,300,000"   "-$120"     -> USD in the value
    "725"       "12.5"                                 -> bare number
    "62.49%"    "0.055%"                               -> percent
    "280'"                                             -> thousands marker

and the label supplies the basis:

    "1 Year T/C Crude" / "1 Year T/C Dry Bulk" / "TCE Far East/Cont"  -> USD/day
    "...USD/dry tonne" / "CFR Qingdao Equivalent"                     -> USD/t
    "RMB/tonne" / "China domestic"                                    -> RMB/t

Evidence tiers, recorded per series:
    value-symbol  a currency or percent marker appears in the raw values
    label-unit    the unit is named in the label text
    basis-mix     symbol gives the currency, label gives the basis (/day, /t)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict

# markers found inside the raw value strings
VAL_USD = re.compile(r"[$]|USD")
VAL_RMB = re.compile(r"RMB|CNY|[\u00a5\u5143]")
VAL_EUR = re.compile(r"\u20ac|EUR")
VAL_PCT = re.compile(r"%")
VAL_THOUSANDS = re.compile(r"'|\b000\b")
VAL_WS = re.compile(r"\bWS\b|worldscale", re.I)

# basis named in the label
LBL_PER_DAY = re.compile(r"\bT/?C\b|\bTCE\b|time\s*charter|per\s*day|/day|\bdaily\b", re.I)
LBL_PER_TONNE = re.compile(r"/\s*(?:dry\s*)?(?:tonne|ton|mt|dmt)\b|per\s*tonne|RMB/tonne|USD/dmt", re.I)
LBL_TEU = re.compile(r"teu|feu", re.I)
LBL_BBL = re.compile(r"bbl|barrel", re.I)
LBL_PCT = re.compile(r"\bpercent|pct\b", re.I)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/extracted/unit_resolution.json")
    a = ap.parse_args()

    import duckdb
    con = duckdb.connect("data/extracted/corpus/db/corpus.duckdb", read_only=True)
    man = {m["series_id"]: m for m in
           json.load(open("data/extracted/series_manifest.json", encoding="utf-8"))}

    # raw value strings per (source, entity_key, measurement_key) - the same key
    # construction the series table used
    rows = con.execute("""
        select c.source,
               lower(trim(l.value)) as entity_key,
               lower(coalesce(h.header,'')) as measurement_key,
               c.value
        from cells c
        join cells l
          on l.doc=c.doc and l.page=c.page and l.engine=c.engine
         and l.table_idx=c.table_idx and l.row_idx=c.row_idx and l.col_idx=0
         and not l.is_numeric
        left join (
            select c2.doc, c2.page, c2.table_idx, c2.engine, c2.col_idx,
                   string_agg(trim(c2.value), ' ') as header
            from cells c2
            where not c2.is_numeric and c2.value is not null
              and length(trim(c2.value)) between 1 and 40
            group by 1,2,3,4,5
        ) h on h.doc=c.doc and h.page=c.page and h.table_idx=c.table_idx
           and h.engine=c.engine and h.col_idx=c.col_idx
        where c.is_numeric and c.col_idx > 0
          and length(trim(l.value)) between 2 and 60
    """).fetchall()

    per_key: dict[tuple, Counter] = defaultdict(Counter)
    for src, ek, mk, val in rows:
        v = str(val or "")
        c = per_key[(src, ek, mk)]
        if VAL_USD.search(v):
            c["usd"] += 1
        elif VAL_RMB.search(v):
            c["rmb"] += 1
        elif VAL_EUR.search(v):
            c["eur"] += 1
        if VAL_PCT.search(v):
            c["pct"] += 1
        if VAL_THOUSANDS.search(v):
            c["thousands"] += 1

    print(f"series keys with raw-value evidence: {len(per_key):,}")

    resolved = {}
    stats = Counter()
    for sid, m in man.items():
        parts = sid.split("|")
        if len(parts) < 3:
            continue
        key = (parts[0], parts[1], parts[2])
        c = per_key.get(key)
        label = f"{m['entity']} {m['measurement']}"
        if not c:
            stats["no value evidence"] += 1
            continue
        basis = None
        if LBL_PER_DAY.search(label):
            basis = "/day"
        elif LBL_TEU.search(label):
            basis = " TEU"
        elif LBL_BBL.search(label):
            basis = "/bbl"
        elif LBL_PER_TONNE.search(label):
            basis = "/t"

        if c["pct"] and c["pct"] > max(c["usd"], c["rmb"], c["eur"]):
            resolved[sid] = ("%", "value-symbol",
                             "percent marker in the raw values")
            stats["%"] += 1
        elif c["usd"]:
            unit = "USD" + basis if basis else ("USD/day" if basis is None
                   and LBL_PER_DAY.search(label) else "USD")
            if basis is None:
                unit = "USD (basis unclear)"
            else:
                unit = "USD" + basis
            resolved[sid] = (unit, "value-symbol", "currency marker in the raw values")
            stats[unit] += 1
        elif c["rmb"]:
            resolved[sid] = ("RMB" + (basis or ""), "value-symbol",
                             "currency marker in the raw values")
            stats["RMB"] += 1
        elif c["eur"]:
            resolved[sid] = ("EUR", "value-symbol", "currency marker in the raw values")
            stats["EUR"] += 1
        else:
            stats["bare numbers only"] += 1

    print(f"\nresolved from value formatting: {len(resolved):,}")
    for k, v in stats.most_common(12):
        print(f"   {k:<28}{v:>6}")

    # upgrade the manifest
    n_up = 0
    for sid, m in man.items():
        if sid in resolved:
            u, conf, why = resolved[sid]
            m["unit"] = u
            m["unit_confidence"] = conf
            m["unit_reason"] = why
            n_up += 1
    # man is keyed by series_id, so iterate values (an earlier version iterated
    # the dict itself and indexed each string key, which raised TypeError)
    series = list(man.values())
    conf = Counter(m.get("unit_confidence", "unknown") for m in series)
    print("\nfinal confidence mix:")
    for k, v in conf.most_common():
        print(f"   {k:<20}{v:>6}  ({v/len(series)*100:5.1f}%)")
    known = sum(v for k, v in conf.items() if k != "unknown")
    print(f"\nresolved: {known:,}/{len(series):,} = {known/len(series)*100:.1f}%")

    json.dump(series, open(a.out, "w", encoding="utf-8"), indent=1)
    print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
