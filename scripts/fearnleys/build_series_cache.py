#!/usr/bin/env python3
"""Per-label monthly series cache for the Fearnleys desk tab.

Reads scripts/fearnleys_rates_full.csv (real Hasura-sourced long history:
label, rate_type, rate_subtype, route, unit, date, rate) and emits
data/derived/fearnleys_series_monthly.json:

  {label: {type, subtype, route, unit, n, first, last, latest, prev,
           chg_pct, ath, atl, ath_date, pct_rank, m: [[yyyymm, avg], ...]}}

- monthly means (rounded 2dp), sorted ascending; idempotent rebuilds.
- pct_rank = percentile rank of latest vs full monthly history (0-100).
- chg_pct = latest vs previous month (null when <2 months).
- No synthesis: labels with <1 month are skipped; gaps left as gaps.

The browser cannot load the 22MB full file; this ~2MB cache carries
everything the desk charts need. Catalog breadth (356 ids) vs cached
labels is reported in meta for the coverage note.
"""
import json
import os

import pandas as pd

SRC = os.path.join("data", "derived", "fearnpulse_rates_full.csv") if os.path.exists(os.path.join("data", "derived", "fearnpulse_rates_full.csv")) else os.path.join("scripts", "fearnpulse_rates_full.csv")
CATALOG = os.path.join("data", "derived", "fearnleys_catalog.csv")
OUT = os.path.join("data", "derived", "fearnleys_series_monthly.json")
UNIT_RANK = {"ws": 0, "tce": 1, "usd": 2}
UNIT_LABEL = {"ws": "WS", "tce": "TCE", "usd": "USD"}


def main():
    print(f"Loading {SRC}...")
    df = pd.read_csv(SRC, usecols=["label", "rate_type", "rate_subtype",
                                   "route", "unit", "date", "rate"])
    df["label"] = df["label"].astype(str).str.strip()
    df["date"] = df["date"].astype(str).str.strip()
    df["rate"] = pd.to_numeric(df["rate"], errors="coerce")
    df = df.dropna(subset=["label", "rate"])
    df = df[df["label"] != ""]
    df["ym"] = df["date"].str.slice(0, 7)

    # One series per (label, unit). The source switched many tanker routes
    # from TCE ($/day) to Worldscale/USD in 2023-05 under the SAME label;
    # grouping by label alone averaged WS points with $/day in overlap months
    # and then continued in a different unit (VLCC MEG/FEAST: 23,679 in
    # 2023-04, 47.36 in 2023-05, all tagged 'tce'). Same branch rule as
    # build_tanker_routes_daily.py: ws, then tce, then usd keeps the base
    # code; further units take a _WS/_TCE/_USD suffix, so the monthly and
    # daily caches share codes.
    df["unit"] = df["unit"].astype(str).str.strip()
    meta_rows = df.drop_duplicates(["label", "unit"]).set_index(["label", "unit"])
    # Exact-zero prints are feed debris on days without an assessment (the
    # daily builder drops them too). Averaged in, they diluted real months:
    # VLCC MEG/FEAST TCE 2019-03 had 7 zero days among ~$30k prints. Drop a
    # zero only when its month also has a real print, so all-zero months (and
    # the placeholder series the frontend flags) stay as published.
    grp_keys = ["label", "unit", "ym"]
    has_real = df.assign(_nz=df["rate"] != 0).groupby(grp_keys)["_nz"].transform("any")
    df = df[(df["rate"] != 0) | (~has_real)]
    monthly = df.groupby(grp_keys)["rate"].mean().round(2)
    units_by_label = {}
    for (lab, unit) in monthly.index.droplevel(2).unique():
        units_by_label.setdefault(lab, []).append(unit)
    code_of = {}
    for lab, units in units_by_label.items():
        units.sort(key=lambda u: (UNIT_RANK.get(u, 9), u))
        for i, u in enumerate(units):
            code_of[(lab, u)] = lab if i == 0 else f"{lab}_{UNIT_LABEL.get(u, u.upper())}"

    labels = {}
    for (label, unit), grp in monthly.groupby(level=[0, 1]):
        pts = sorted((ym, float(v)) for ym, v in grp.droplevel([0, 1]).items())
        vals = [v for _, v in pts]
        meta = meta_rows.loc[(label, unit)]
        code = code_of[(label, unit)]
        latest, prev = vals[-1], (vals[-2] if len(vals) > 1 else None)
        lo, hi = min(vals), max(vals)
        below = sum(1 for v in vals if v < latest)
        labels[str(code)] = {
            "type": str(meta["rate_type"]),
            "subtype": str(meta["rate_subtype"]),
            "route": str(meta["route"]),
            "unit": str(unit),
            "n": len(pts),
            "first": pts[0][0],
            "last": pts[-1][0],
            "latest": latest,
            "prev": prev,
            "chg_pct": round((latest - prev) / abs(prev) * 100, 2) if prev else None,
            "ath": hi,
            "atl": lo,
            "ath_date": pts[vals.index(hi)][0],
            "pct_rank": round(below / len(vals) * 100, 1),
            "m": [[ym, v] for ym, v in pts],
        }
        if code != label:
            labels[str(code)]["twin_of"] = str(label)

    try:
        cat = pd.read_csv(CATALOG, usecols=["id"])
        catalog_ids = int(len(cat))
    except Exception:
        catalog_ids = None

    payload = {
        "meta": {
            "source": SRC,
            "labels_cached": len(labels),
            "catalog_ids": catalog_ids,
            "monthly_points": int(sum(v["n"] for v in labels.values())),
        },
        "labels": labels,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(payload, f, separators=(",", ":"))
    kb = round(os.path.getsize(OUT) / 1024, 1)
    print(f"Generated {OUT}: {len(labels)} labels ({kb} KB).")


if __name__ == "__main__":
    main()
