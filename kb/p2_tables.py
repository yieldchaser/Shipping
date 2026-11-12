#!/usr/bin/env python3
"""GraphRAG phase P2 §4.2 — broker sale / demolition rows from `*.tables.json` sidecars.

The per-publisher extractors under `scripts/extract/publishers/` already normalise each printed
broker table into a `*.tables.json` sidecar whose row dicts carry the printed cells plus a parsed
price field.  This module consumes those sidecars deterministically: it maps a *row key signature*
(not cell values) onto a known deal layout and yields claims for the D9 clusterer in
`kb/p2_transactions.py`.

No LLM: every layout below was identified by inspecting the sidecars' row-key signatures
(see kb/reports/p2_tables.json `signatures`), so no header-classification call is needed.
Unknown signatures are logged, never guessed. The LLM never reads cells anywhere in this path.

`raw_cell` discipline: a claim's `printed` dict is the sidecar row verbatim (plus `__file`/`__row`
pointing back at the source sidecar row), so every stored raw cell can be re-found in the source
row by `kb/p2_report.py`.
"""
import json
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p2_series as P2  # noqa: E402  reuse to_number/parse_date/resolve_doc/sha16
import p2_transactions as TX  # noqa: E402  reuse vessel_key/get/norm_counterparty

ROOT = P2.ROOT
EXTRACTED = ROOT / "data" / "extracted"
REPORTS = P2.REPORTS


def _sig(keys):
    return "|".join(sorted(k.lower() for k in keys))


# ---------------------------------------------------------------------------
# known layouts: signature -> (label, spec)
# spec fields mirror p2_transactions.SPECS so vessel_key/get() work unchanged.
# ---------------------------------------------------------------------------
LAYOUTS = {
    # advanced_shipping weekly market report: NAME/TYPE/DWT/BUILT/PRICE/BUYERS
    _sig(["BUILT", "BUYERS", "CBM", "COMMENTS", "DWT", "GEAR", "M_E", "NAME", "PRICE",
          "PRICE_USD_MILL", "SS", "TEU", "TYPE", "YARD", "extra_json", "issue", "page",
          "report_week", "section", "source_file"]):
        ("advanced_shipping_sales", dict(kind="sale", price="PRICE_USD_MILL", unit="usd_m",
         buyers=["BUYERS"], name=["NAME"], imo=None, size=["DWT"], built=["BUILT"], date="issue")),
    # banchero_costa weekly: vessel/dwt/built/buyer/price_usd_m/imo
    _sig(["built", "buyer", "comments", "dwt", "imo", "issue_date", "price_usd_m",
          "report_week", "seller", "source_file", "vessel", "vessel_type", "yard"]):
        ("banchero_costa_sales", dict(kind="sale", price="price_usd_m", unit="usd_m",
         buyers=["buyer", "seller"], name=["vessel"], imo="imo", size=["dwt"], built=["built"],
         date="issue_date")),
    # xclusiv weekly: NAME/DWT/YEAR/COUNTRY/YARD/BUYERS/PRICE_USD_MILL
    _sig(["BUYERS", "COMMENTS", "COUNTRY", "DWT", "NAME", "PRICE", "PRICE_USD_MILL", "TYPE",
          "YARD", "YEAR", "issue_date", "page", "report_week", "section", "source_file"]):
        ("xclusiv_sales", dict(kind="sale", price="PRICE_USD_MILL", unit="usd_m",
         buyers=["BUYERS"], name=["NAME"], imo=None, size=["DWT"], built=["YEAR"],
         date="issue_date")),
    # gms week report reported_sales (demolition candidates sold for recycling)
    _sig(["issue_date", "ldt", "location", "price_reported", "report_week", "source_file",
          "terms_comments", "vessel_name", "vessel_type"]):
        ("gms_reported_sales", dict(kind="demolition", price="price_reported", unit="raw",
         buyers=["location"], name=["vessel_name"], imo=None, size=["ldt"], built=None,
         date="issue_date")),
    # clarksons bulletin (md/clarksons): vessel/price_usd_m + parsed dwt/built
    _sig(["BUILT", "BUYERS", "DWT", "NAME", "PRICE", "SS_DD", "YARD", "built_raw", "built_year",
          "buyer", "details", "dwt", "dwt_raw", "en_bloc", "en_bloc_group", "issue_date", "page",
          "price_qualifier", "price_raw", "price_scope", "price_usd_m", "price_usd_m_per_vessel",
          "report_week", "section", "source_file", "source_sha256", "ss_dd", "vessel", "yard"]):
        ("clarksons_sales", dict(kind="sale", price="price_usd_m", unit="usd_m",
         buyers=["buyer", "BUYERS"], name=["vessel", "NAME"], imo=None, size=["dwt", "DWT"],
         built=["built_year", "BUILT"], date="issue_date")),
    # clarksons sale-and-purchase sheet (hellenic/shipbuilding/clarksons): vessel_name/price_usd_m
    _sig(["built_yard", "built_year", "buyer", "bwts_fitted", "dd_due", "details", "dwt",
          "gear_cranes", "is_auction", "is_en_bloc", "issue_date", "price_raw", "price_usd_m",
          "report_week", "scrubber_fitted", "sector", "segment", "source_file",
          "special_coating", "ss_due", "vessel_name"]):
        ("clarksons_snp_sales", dict(kind="sale", price="price_usd_m", unit="usd_m",
         buyers=["buyer"], name=["vessel_name"], imo=None, size=["dwt"], built=["built_year"],
         date="issue_date")),
    # clarksons demolition (md/clarksons): vessel + ldt + price_usd_ldt
    _sig(["built_place", "built_raw", "built_year", "destination", "details", "dwt", "dwt_raw",
          "issue_date", "ldt", "page", "price_raw", "price_usd_ldt", "report_week", "section",
          "source_file", "source_sha256", "vessel"]):
        ("clarksons_demolition", dict(kind="demolition", price="price_usd_ldt", unit="usd_per_ldt",
         buyers=["destination"], name=["vessel"], imo=None, size=["dwt"], built=["built_year"],
         date="issue_date")),
    # clarksons demolition sales sheet (hellenic/shipbuilding/clarksons): vessel_name/price_usd_per_ldt
    _sig(["built", "delivery_location", "details", "dwt", "issue_date", "price_raw",
          "price_usd_per_ldt", "report_week", "source_file", "vessel_name"]):
        ("clarksons_demolition_sales", dict(kind="demolition", price="price_usd_per_ldt",
         unit="usd_per_ldt", buyers=["delivery_location"], name=["vessel_name"], imo=None,
         size=["dwt"], built=["built"], date="issue_date")),
}

# sidecar list keys that carry deal rows (chart/ranking keys are series, not deals)
DEAL_KEYS = ("reported_sales", "sales", "demolitions")
# keys that are market price quotes / rankings -> belong to series or text, never transactions
NON_DEAL_KEYS = ("indicative_demolition_prices", "newbuilding_prices", "charterer_rows",
                 "orderbook_age_rows")


def _num(v):
    if v is None or isinstance(v, (int, float)):
        return float(v) if v not in (None, "") else None
    return P2.to_number(str(v))


def iter_sidecars():
    """Yield (path, sidecar-dict) for every dict-shaped *.tables.json sidecar."""
    for p in sorted(EXTRACTED.rglob("*.tables.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            yield (p, None)
            continue
        yield (p, d)


def collect_claims(con, docmaps, report=None):
    """Return (groups, stats) where groups maps (label, kind) -> list[claim].

    `docmaps` is P2.load_doc_maps()'s 5-tuple. Claims are deduplicated on
    (kind, vessel_key, date, price, counterparties) because some bulletins are
    sidecar-extracted twice (md/clarksons + md/hellenic/shipbuilding/clarksons).
    """
    doc_by_source_file, doc_by_srcf_basename, doc_by_sf_stem, _doc_pub, stem_list = docmaps
    stats = Counter()
    sig_seen = Counter()
    unknown = Counter()
    groups = defaultdict(list)
    dedupe = set()
    for path, d in iter_sidecars():
        if d is None:
            stats["sidecar_unreadable"] += 1
            continue
        if not isinstance(d, dict):
            stats["sidecar_top_level_list"] += 1
            continue
        stats["sidecars"] += 1
        rel = str(path.relative_to(ROOT)).replace("\\", "/")
        for key in DEAL_KEYS:
            rows = d.get(key)
            if not (isinstance(rows, list) and rows):
                continue
            for row_ord, row in enumerate(rows):
                if not isinstance(row, dict):
                    stats["row_not_dict"] += 1
                    continue
                sg = _sig(row.keys())
                sig_seen[sg] += 1
                lay = LAYOUTS.get(sg)
                if lay is None:
                    unknown[sg] += 1
                    stats["row_unknown_signature"] += 1
                    continue
                label, spec = lay
                idx = TX.lc_index(list(row.keys()))
                dt = P2.parse_date(TX.get(row, idx, spec["date"]))
                if dt is None:
                    stats["row_nodate"] += 1
                    continue
                price_raw = TX.get(row, idx, spec.get("price"))
                price_val = _num(price_raw)
                if price_raw and price_val is None:
                    stats["row_nonnum_price"] += 1
                    continue
                if price_val is None:
                    stats["row_noprice"] += 1
                    continue
                vk = TX.vessel_key(row, idx, spec)
                name = TX.get(row, idx, spec.get("name"))
                cps = []
                for b in (spec.get("buyers") or []):
                    cps += TX.norm_counterparty(TX.get(row, idx, b))
                cps = sorted(set(cps))
                sf = TX.get(row, idx, "source_file")
                doc_id = P2.resolve_doc(sf, doc_by_source_file, doc_by_srcf_basename,
                                        doc_by_sf_stem, stem_list) if sf else None
                if sf and not doc_id:
                    stats["unresolved_doc"] += 1
                dk = (spec["kind"], vk, dt.isoformat(), price_val, tuple(cps))
                if dk in dedupe:
                    stats["row_duplicate"] += 1
                    continue
                dedupe.add(dk)
                printed = {k: ("" if v is None else str(v)) for k, v in row.items()
                           if v is not None and str(v).strip()}
                printed["__file"] = rel
                printed["__row"] = str(row_ord)
                printed["__key"] = key
                groups[(label, spec["kind"])].append({
                    "stem": f"tables:{label}", "row_ord": row_ord, "kind": spec["kind"],
                    "vessel_key": vk, "date": dt.isoformat(), "price_val": price_val,
                    "price_unit": spec["unit"], "price_raw": price_raw, "name": name,
                    "counterparties": cps, "doc_id": doc_id, "sidecar": rel,
                    "printed": printed,
                })
                stats["claims"] += 1
    if report is not None:
        report["signatures"] = {s: n for s, n in sig_seen.most_common(40)}
        report["unknown_signatures"] = {s: n for s, n in unknown.most_common(20)}
        report["layouts"] = sorted(LAYOUTS)
        report["non_deal_keys"] = list(NON_DEAL_KEYS)
    return groups, stats


def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    import duckdb
    con = duckdb.connect(str(P2.DB), read_only=True)
    con.execute("SET memory_limit='64MB'")
    con.execute("SET threads=1")
    docmaps = P2.load_doc_maps(con)
    con.close()
    report = {"phase": "P2_tables", "gate": "every stored raw_cell found verbatim in source row"}
    groups, stats = collect_claims(None, docmaps, report)
    report["stats"] = dict(stats)
    report["groups"] = {f"{lab}|{kind}": len(v) for (lab, kind), v in sorted(groups.items())}
    (REPORTS / "p2_tables.json").write_text(json.dumps(report, indent=1, ensure_ascii=False),
                                            encoding="utf-8")
    print(f"p2_tables: sidecars={stats['sidecars']:,} claims={stats['claims']:,} "
          f"groups={len(groups)} unknown_sig={stats['row_unknown_signature']:,} "
          f"dupes={stats['row_duplicate']:,} nodate={stats['row_nodate']:,} "
          f"nonnum_price={stats['row_nonnum_price']:,} unresolved_doc={stats['unresolved_doc']:,}")
    for (lab, kind), v in sorted(groups.items()):
        print(f"  {lab:<28}{kind:<14}{len(v):>7,}")
    for sg, n in list(report["unknown_signatures"].items())[:5]:
        print(f"  unknown sig [{n}] {sg[:120]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
