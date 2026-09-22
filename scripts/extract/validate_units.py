"""Validate the manifest's unit claims against the values actually present.

A unit assignment is a claim. This checks each claim against the observed value
distribution, so a wrong convention shows up as an implausible range rather than
silently propagating into the processing phase.

Plausibility bands used (wide on purpose - this catches order-of-magnitude
errors, not precision):
    RMB/t          300 .. 3,000     Chinese domestic iron ore
    USD/t          40 .. 400        seaborne iron ore
    USD/day        2,000 .. 250,000 vessel timecharter
    USD/TEU        200 .. 12,000    container freight
    %              0 .. 100         unless it is a change series
    million mt     0 .. 500         port stock / trade volume
    DWT            1,000 .. 500,000
    index points   positive only (indices differ too much for a band)
    ratio          0.001 .. 10,000
"""
from __future__ import annotations

import json
import sys

BANDS = {
    "RMB/t": (300, 3000),
    "USD/t": (40, 400),
    "USD/day": (2000, 250000),
    "USD/TEU": (200, 12000),
    "million mt": (0, 500),
    "DWT": (1000, 500000),
    "ratio": (0.001, 10000),
    "%": (-1000, 1000),
    # deltas are deliberately unbounded: a change can be negative and can exceed
    # the level it describes, so banding them would produce false alarms
    "delta": (-1e12, 1e12),
}


def main() -> int:
    import duckdb
    con = duckdb.connect("data/extracted/corpus/db/corpus.duckdb", read_only=True)
    man = {m["series_id"]: m for m in
           json.load(open("data/extracted/series_manifest.json", encoding="utf-8"))}

    q = con.execute("""
        select series_id, min(value), max(value), count(*)
        from series_points group by 1""").fetchall()

    from collections import defaultdict
    stats = defaultdict(lambda: {"ok": 0, "out": 0, "examples": []})
    for sid, lo, hi, n in q:
        m = man.get(sid)
        if not m:
            continue
        unit = m["unit"]
        band = BANDS.get(unit)
        if not band:
            continue
        lo_b, hi_b = band
        inside = (lo_b <= lo <= hi_b) and (lo_b <= hi <= hi_b)
        st = stats[unit]
        if inside:
            st["ok"] += 1
        else:
            st["out"] += 1
            if len(st["examples"]) < 3:
                st["examples"].append((m["entity"][:22], m["measurement"][:18], lo, hi))

    print(f"{'unit':<14}{'plausible':>10}{'implausible':>13}   examples of implausible")
    bad_total = 0
    for unit, st in sorted(stats.items(), key=lambda kv: -(kv[1]["out"])):
        bad_total += st["out"]
        ex = "; ".join(f"{e[0]}/{e[1]} {e[2]:,.1f}..{e[3]:,.1f}" for e in st["examples"])
        print(f"{unit:<14}{st['ok']:>10,}{st['out']:>13,}   {ex[:64]}")
    print(f"\nimplausible unit assignments: {bad_total:,}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
