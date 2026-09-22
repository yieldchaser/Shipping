"""Build the tagged series manifest: the handoff artefact for the processing phase.

The audit showed 4,947 of 5,115 series (96.7%) have no confidently identified
unit. Units are the precondition for linking a series across sources - 570 RMB/t
and 92 USD/dmt are the same iron ore, and without units nothing can say so.

Resolution strategy, in order of trust, with the confidence RECORDED so a
downstream consumer can filter rather than guess:

  1. EXPLICIT   the unit appears in the measurement/header text itself
                ("RMB/tonne (excluding tax)", "million mt", "USD/DMT")
  2. STRUCTURAL derived from what the series IS by source and measurement:
                mineral specifications (Fe/Alumina/Silica/Phos/Moisture/Sulphur
                on a brand row) are %, port-stock rows are million mt, Baltic
                indices are dimensionless points, FX pairs are ratios
  3. ASSUMED    a source-wide default, flagged as assumed, never presented as
                measured

A unit is never invented: where none of the three applies the entry is left
"unknown" with a reason, and the count is reported.

Also carries value_class (proprietary / source-unique / feed-covered) from the
corpus audit, plus date span and point count, so the manifest is self-describing.
"""
from __future__ import annotations

import argparse
import json
import re
import sys

# --- 1. explicit: unit literally present in the text
EXPLICIT = [
    (re.compile(r"\bRMB\s*/\s*(?:tonne|ton|mt|t)\b", re.I), "RMB/t"),
    (re.compile(r"\bUSD\s*/\s*(?:dry\s*)?(?:tonne|ton|mt|dmt|t)\b", re.I), "USD/t"),
    (re.compile(r"\bUSD\s*/\s*(?:teu|feu)\b", re.I), "USD/TEU"),
    (re.compile(r"\bUSD\s*/\s*(?:day|d|pd|per day)\b", re.I), "USD/day"),
    (re.compile(r"\b(?:WS|Worldscale)\b", re.I), "Worldscale"),
    (re.compile(r"\bUSD\s*/\s*(?:bbl|barrel)\b", re.I), "USD/bbl"),
    (re.compile(r"\bmillion\s*(?:mt|t|tonnes?)\b", re.I), "million mt"),
    (re.compile(r"\b(?:000|'000|k)\s*(?:mt|t|tonnes?|bbl|teu)\b", re.I), "000 units"),
    (re.compile(r"\b(?:dwt|deadweight)\b", re.I), "DWT"),
    (re.compile(r"\b(?:cbm|m3|m\u00b3)\b", re.I), "cbm"),
    (re.compile(r"\b(?:percent|pct|percentage)\b", re.I), "%"),
]

# --- 2. structural: what the series IS
SPEC_MEASUREMENTS = {"fe", "alumina", "silica", "silica%", "phos", "phosphorus %",
                     "moisture", "moisture %", "sulphur %", "1% fe", "1% silica"}
PORT_ENTITIES = {"caofeidian", "jingtang", "qingdao", "rizhao", "tianjin",
                 "beilun", "bayuquan", "dalian", "shandong", "hebei", "liaoning",
                 "total (35 ports)"}
DIMENSIONLESS_PREFIX = ("bci", "bdi", "bpi", "bsi", "bhsi", "bcti", "bdti",
                        "bai", "blng", "blpg")
FX_RE = re.compile(r"^[A-Za-z]{3}\s*/\s*[A-Za-z]{3}$")

# --- 2b. conventions: derived from what the source's series MEAN, verified
# against value ranges rather than assumed. Recorded as confidence="convention"
# so a consumer can tell them apart from a unit stated in the text.
MMI_INDEX = re.compile(r"^IO(?:PI|SI|PLI)\d*", re.I)
COUNTRY_ENTITY = {
    "turkey", "india", "bangladesh", "pakistan", "brazil", "china", "greece",
    "russia", "s.africa", "usa", "japan", "south korea", "vietnam", "egypt",
    "indonesia", "malaysia", "thailand", "taiwan",
}
VESSEL_CLASS = {
    "capesize", "panamax", "kamsarmax", "supramax", "ultramax", "handysize",
    "handymax", "vlcc", "suezmax", "aframax", "lr1", "lr2", "mr", "vlGC",
    "vlgc", "lnGC", "lngc", "vlcc/vl", "panamax 82k", "capesize 180k",
}
CHANGE_RE = re.compile(r"^(?:mom|yoy|y-o-y|w-o-w|change|delta)\b|change in", re.I)

# --- 3. assumed: source-wide defaults, always flagged
ASSUMED = {
    "baltic": ("dimensionless index", "baltic publishes indices as points"),
}


# A column that reports a DELTA must not be given a level unit. The unit
# validator caught this: `SUEZMAX` ranged -2,372..160,000 and `Qingdao/SGX Front
# Month` -12..111, i.e. changes were being labelled as rates and stocks. The
# measurement column, not the entity, decides.
DELTA_RE = re.compile(
    r"^(?:change|delta|diff(?:erence)?|mom|yoy|y-o-y|w-o-w|qoq|qtd|ytd|mtd|"
    r"\+/?-\s*\(?%?\)?|\u00b1|\u00b1\s*\(%\)|%\s*change|var)\b"
    r"|change\s*in|^\s*[+\-]?\s*\(?%\s*\)?", re.I)


def resolve(source: str, entity: str, measurement: str) -> tuple[str, str, str]:
    """Return (unit, confidence, reason)."""
    me = f"{entity} {measurement}"
    # deltas first: their unit is "delta of X", never a level
    if DELTA_RE.search((measurement or "").strip()):
        return "delta", "structural", \
               "measurement reports a change, not a level"
    for rx, u in EXPLICIT:
        if rx.search(me):
            return u, "explicit", "unit stated in the source text"

    m = (measurement or "").strip().lower()
    e = (entity or "").strip().lower()
    if m in SPEC_MEASUREMENTS:
        return "%", "structural", "mineral specification is a percentage"
    if e in PORT_ENTITIES and ("stock" in m or "inventor" in m or m == ""):
        return "million mt", "structural", "port stock inventory"
    if m == "million mt" or m.startswith("million"):
        return "million mt", "structural", "measurement names the unit"
    if any(e.startswith(p) for p in DIMENSIONLESS_PREFIX):
        return "index points", "structural", "published index level"
    if FX_RE.match((entity or "").strip()):
        return "ratio", "structural", "FX pair"
    # --- conventions, each verified against observed value ranges
    if MMI_INDEX.match((entity or "").strip()):
        # The measurement decides: the same entity carries both a seaborne USD
        # price and a China domestic RMB equivalent. The unit validator caught
        # IOPI62/PRICE ranging 82-227, which is USD/dmt, not RMB/t.
        if (entity or "").upper().startswith("IOSI"):
            return "USD/dmt", "convention", "MMi seaborne index (USD basis)"
        if re.search(r"equivalent|domestic|RMB", measurement or "", re.I):
            return "RMB/t", "convention", "MMi China domestic RMB equivalent"
        if re.search(r"price|USD|seaborne", measurement or "", re.I):
            return "USD/dmt", "convention", "MMi seaborne price column"
        return "RMB/t", "convention", "MMi port index (domestic default)"
    if e in PORT_ENTITIES:
        return "million mt", "convention", "Chinese port stock inventory"
    if e in COUNTRY_ENTITY:
        return "million mt", "convention", "country trade flow volume"
    if e in {v.lower() for v in VESSEL_CLASS}:
        return "USD/day", "convention", "vessel class rate (timecharter)"
    if CHANGE_RE.search(measurement or "") or CHANGE_RE.search(entity or ""):
        return "%", "convention", "period change"
    if m in ("ytd", "mtd", "y-o-y", "w-o-w", "change", "diff to iosi62", "this week",
             "last week", "high \u00b2", "low \u00b2"):
        return "unknown", "unknown", "period aggregate or delta of an unknown basis"
    if source in ASSUMED:
        u, why = ASSUMED[source]
        return u, "assumed", why
    return "unknown", "unknown", "no unit stated or inferable"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/extracted/series_manifest.json")
    a = ap.parse_args()

    import duckdb
    from collections import Counter
    con = duckdb.connect("data/extracted/corpus/db/corpus.duckdb", read_only=True)

    rows = con.execute("""
        select series_id, source, entity, measurement, points, first_date, last_date
        from series order by source, entity, measurement""").fetchall()

    # value classes from the corpus audit
    vclass = {}
    try:
        aud = json.load(open("data/extracted/corpus_audit.json", encoding="utf-8"))
        for t in aud.get("series_tags", []):
            vclass[t["series_id"]] = t.get("value_class")
    except Exception:
        pass

    manifest = []
    for sid, src, ent, meas, pts, f0, f1 in rows:
        unit, conf, why = resolve(src or "", ent or "", meas or "")
        manifest.append({
            "series_id": sid, "source": src, "entity": ent, "measurement": meas,
            "unit": unit, "unit_confidence": conf, "unit_reason": why,
            "value_class": vclass.get(sid, "unclassified"),
            "points": pts, "first_date": str(f0), "last_date": str(f1),
        })

    c_unit = Counter(m["unit"] for m in manifest)
    c_conf = Counter(m["unit_confidence"] for m in manifest)
    print(f"series in manifest: {len(manifest):,}")
    print("\nunit resolution:")
    for k, v in c_unit.most_common():
        print(f"   {k:<20}{v:>6}  ({v/len(manifest)*100:5.1f}%)")
    print("\nconfidence:")
    for k, v in c_conf.most_common():
        print(f"   {k:<20}{v:>6}  ({v/len(manifest)*100:5.1f}%)")

    known = sum(v for k, v in c_conf.items()
                if k in ("explicit", "structural", "convention"))
    print(f"\nresolved with stated/inferred evidence: {known:,} "
          f"({known/len(manifest)*100:.1f}%)  was 3.3% before this pass")

    json.dump(manifest, open(a.out, "w", encoding="utf-8"), indent=1)
    print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
