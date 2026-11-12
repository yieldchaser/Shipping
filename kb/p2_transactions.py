#!/usr/bin/env python3
"""
GraphRAG phase P2 — canonical deals (D9 clustering), docs/GRAPHRAG_BUILD_PLAN.md §4.4.

Reads the per-row vessel deal/transaction CSVs that p2_series.py defers, and writes
`transaction` + `mention` (and provisional vessel `entity` rows) into kb/state/kb.duckdb.

Clustering keys (PLAN §4.4): vessel key (IMO; else normalised name + size + built year),
kind, ±45-day window, counterparties. A price consistent within 2% across claims becomes
the consensus value; otherwise status=conflicting and every claim is kept.

Streaming csv.reader; deterministic + idempotent (DELETE + rebuild of txn/mention).
No LLM. SEC XBRL is a separate loader.
Usage: python kb/p2_transactions.py
"""
import csv
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path

import duckdb
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p2_series as P2  # reuse to_number/parse_date/load_doc_maps/resolve_doc/sha16

ROOT = P2.ROOT
DB = P2.DB
SERIES = P2.SERIES
MAP = P2.MAP
REPORTS = P2.REPORTS

# ---------------------------------------------------------------------------
# per-stem spec: (kind, price_col, price_unit, buyer_cols, name_cols, imo_col,
#                 size_cols, built_cols, date_col, kind_col_for_deal_tables)
# ---------------------------------------------------------------------------
# price_unit is one of usd_m | usd_per_ldt | usd_per_lt | usd_per_day | raw
def _u(field):  # case-insensitive multi-name lookup helper (built inline below)
    return field

SPECS = {
    "singletons_sales_series":            dict(kind="sale", price="price_usd_m", unit="usd_m",
        buyers=["buyers"], name=["vessel_name"], imo="imo", size=["dwt"], built=["built"], date="issue_date"),
    "advanced_shipping_sales_series":     dict(kind="sale", price="PRICE_USD_MILL", unit="usd_m",
        buyers=["BUYERS"], name=["NAME"], imo=None, size=["DWT"], built=["BUILT"], date="issue_date"),
    "advanced_shipping_newbuilding_series": dict(kind="newbuild_order", price="price_usd_mill", unit="usd_m",
        buyers=["owner"], name=None, imo=None, size=["capacity"], built=None, date="issue_date"),
    "advanced_shipping_demo_sales_series": dict(kind="demolition", price="price_usd_per_ldt", unit="usd_per_ldt",
        buyers=None, name=["vessel_name"], imo=None, size=["dwt"], built=["yob"], date="issue_date"),
    "clarksons_sales_series":             dict(kind="sale", price="price_usd_m", unit="usd_m",
        buyers=["buyer", "BUYERS"], name=["vessel", "NAME"], imo=None, size=["dwt", "DWT"], built=["built_year", "BUILT"], date="issue_date"),
    "clarksons_snp_sales_series":         dict(kind="sale", price="price_usd_m", unit="usd_m",
        buyers=["buyer"], name=["vessel_name"], imo=None, size=["dwt"], built=["built_year"], date="issue_date"),
    "clarksons_demolition_series":        dict(kind="demolition", price="price_usd_ldt", unit="usd_per_ldt",
        buyers=["destination", "DELIVERY"], name=["vessel", "NAME"], imo=None, size=["dwt", "DWT"], built=["built_year", "BUILT"], date="issue_date"),
    "clarksons_demolition_sales_series":  dict(kind="demolition", price="price_usd_per_ldt", unit="usd_per_ldt",
        buyers=["delivery_location"], name=["vessel_name"], imo=None, size=["dwt"], built=["built"], date="issue_date"),
    "intermodal_sales_series":            dict(kind="sale", price="price_usd_m", unit="usd_m",
        buyers=["buyers"], name=["vessel_name"], imo=None, size=["dwt"], built=["year_built"], date="issue_date"),
    "intermodal_demo_sales_series":       dict(kind="demolition", price="price_usd_per_ldt", unit="usd_per_ldt",
        buyers=["buyer_breakers"], name=["vessel_name"], imo=None, size=["dwt"], built=["year_built"], date="issue_date"),
    "bancosta_sales_series":              dict(kind="sale", price="price_usd_m", unit="usd_m",
        buyers=["buyers"], name=["vessel_name"], imo="imo", size=["dwt"], built=["built"], date="issue_date"),
    "bancosta_container_fixtures_series": dict(kind="fixture", price="rate_usd_day", unit="usd_per_day",
        buyers=["account"], name=["vessel_name"], imo=None, size=["teu"], built=["built"], date="issue_date"),
    "carriers_demolition_series":         dict(kind="demolition", price="price_usd_per_ldt", unit="usd_per_ldt",
        buyers=["buyers"], name=["vessel_name"], imo=None, size=["dwt"], built=["built"], date="issue_date"),
    "carriers_sales_series":              dict(kind="sale", price="price_usd_mill", unit="usd_m",
        buyers=["buyers"], name=["vessel_name"], imo=None, size=["dwt"], built=["built"], date="issue_date"),
    "carriers_newbuilding_series":        dict(kind="newbuild_order", price="price_usd_mill", unit="usd_m",
        buyers=["owners"], name=None, imo=None, size=["size"], built=None, date="issue_date"),
    "gms_demolition_sales_series":        dict(kind="demolition", price="price_reported", unit="raw",
        buyers=["location"], name=["vessel_name"], imo=None, size=None, built=None, date="issue_date"),
    "hellenic_best_oasis_deals_series":   dict(kind="demolition", price="price_usd_ldt", unit="usd_per_ldt",
        buyers=["delivery_location"], name=["vessel_name"], imo="imo", size=["ldt"], built=["year_built"], date="issue_date"),
    "hellenic_vv_benchmark_sales_series": dict(kind="sale", price="sale_price_usd_m", unit="usd_m",
        buyers=["seller"], name=["vessel_name"], imo=None, size=None, built=None, date="issue_date"),
    "hellenic_vv_sales_series":           dict(kind="sale", price="price_usd_m", unit="usd_m",
        buyers=["buyer"], name=["vessel_name"], imo=None, size=["dwt_spec"], built=["built_iso", "built_date"], date="issue_date"),
    "lion_deals_series":                  dict(kind="deal", price="price_usd_m", unit="usd_m",
        buyers=["buyer", "destination"], name=["vessel"], imo=None, size=["dwt"], built=["built_year"], date="issue_date", kind_col="deal_kind"),
    "lion_demo_sales_series":             dict(kind="demolition", price="price_usd_per_lt", unit="usd_per_lt",
        buyers=["destination"], name=["vessel"], imo=None, size=["dwt"], built=["built_year"], date="issue_date"),
    "lion_sales_series":                  dict(kind="sale", price="price_usd_m", unit="usd_m",
        buyers=["buyer"], name=["vessel"], imo=None, size=["dwt"], built=["built_year"], date="issue_date"),
    "star_asia_deals_series":             dict(kind="demolition", price="price_usd_per_ldt", unit="usd_per_ldt",
        buyers=["destination_yard", "buyer_comments"], name=["vessel_name"], imo=None, size=["ldt"], built=["built", "year_built"], date="issue_date", kind_col="deal_type"),
    "star_asia_snp_sales_series":         dict(kind="sale", price="price_usd_mill", unit="usd_m",
        buyers=["buyers_comments"], name=["vessel_name"], imo=None, size=["dwt"], built=["year_built"], date="issue_date"),
    "xclusiv_sales_series":               dict(kind="sale", price="PRICE_USD_MILL", unit="usd_m",
        buyers=["BUYERS"], name=["NAME"], imo=None, size=["DWT"], built=["YEAR"], date="issue_date"),
    "xclusiv_demo_sales_series":          dict(kind="demolition", price="PRICE_USD_PER_LDT", unit="usd_per_ldt",
        buyers=["BUYERS"], name=["NAME"], imo=None, size=["DWT"], built=["YEAR"], date="issue_date"),
}

# stems deferred by p2_series that are NOT row transactions -> logged, skipped here.
NON_TXN_SKIP = {
    "seabrokers_fleet_moves_series": "categorical metric value_text, no transaction",
    "hellenic_gms_port_positions_series": "vessel demolition positioning (ldt, no price term)",
}


def lc_index(header):
    return {h.strip().lower(): h for h in header}


def get(row, idx, names, default=""):
    if names is None:
        return default
    if isinstance(names, str):
        names = [names]
    for n in names:
        k = idx.get(n.lower())
        if k and str(row.get(k, "")).strip():
            return str(row[k]).strip()
    return default


def norm_name(s):
    s = re.sub(r"[^a-z0-9 ]", " ", s.lower())
    s = re.sub(r"\s+", " ", s).strip()
    return s


def norm_counterparty(s):
    """Split a counterparty cell into normalized tokens."""
    if not s:
        return []
    parts = re.split(r"[;/,&]|\band\b", s, flags=re.IGNORECASE)
    toks = []
    for p in parts:
        n = norm_name(p)
        if n and n not in ("tbd", "unknown", "n a", "n/a"):
            toks.append(n)
    return toks


def vessel_key(row, idx, spec):
    imo = get(row, idx, spec["imo"]) if spec.get("imo") else ""
    imo_digits = re.sub(r"\D", "", imo)
    if imo_digits:
        return "imo:" + imo_digits
    name = norm_name(get(row, idx, spec.get("name")))
    size = ""
    for s in (spec.get("size") or []):
        v = get(row, idx, s)
        if v:
            size = re.sub(r"[^0-9.]", "", v)
            break
    built = get(row, idx, spec.get("built"))
    built_digits = re.sub(r"\D", "", built)
    sig = f"{name}|{size}|{built_digits}"
    return "prov:" + hashlib.sha256(sig.encode()).hexdigest()[:16]


def kind_from_cell(v, default):
    s = (v or "").lower()
    if any(t in s for t in ("demo", "scrap", "recycl", "break")):
        return "demolition"
    if "newbuild" in s or "new build" in s or s.startswith("nb"):
        return "newbuild_order"
    if any(t in s for t in ("chart", "fixture", "tc ", "time charter")):
        return "fixture"
    if any(t in s for t in ("sale", "snp", "s&p", "sale and purchase")):
        return "sale"
    return default


def parse_pub(row, idx, spec):
    d = get(row, idx, spec.get("date", "issue_date"))
    return P2.parse_date(d)


def cluster_emit(con, claims, unit, stats, bufs, txn_batch=2000):
    """D9-cluster `claims` (PLAN §4.4) and append rows to bufs.

    bufs = {"txn": [], "mention": [], "entity": [], "seen": set()} so the same buffers are
    flushed across every claim source (per-row CSVs and `*.tables.json` sidecars).
    """
    txn_rows, mention_rows, entity_rows = bufs["txn"], bufs["mention"], bufs["entity"]
    seen_entities = bufs["seen"]
    groups = {}
    for c in claims:
        groups.setdefault((c["kind"], c["vessel_key"]), []).append(c)
    clusters = []
    for (gk, gvessel), cs in groups.items():
        cs_sorted = sorted(cs, key=lambda c: c["date"])
        buckets = []  # list of dicts
        for c in cs_sorted:
            d = date.fromisoformat(c["date"])
            placed = False
            for b in buckets:
                overlap = (set(c["counterparties"]) & set(b["cps"])) or \
                          (not c["counterparties"] and not b["cps"])
                if not overlap:
                    continue
                # ±45-day window (PLAN §4.4): the whole cluster must fit, not just the last step,
                # otherwise a chain of 45-day steps walks a deal across a year.
                delta = (d - b["max_date"]).days if b["max_date"] else 0
                span = (d - b["min_date"]).days if b["min_date"] else 0
                if delta <= 45 and span <= 45:
                    b["claims"].append(c)
                    b["cps"] = sorted(set(b["cps"]) | set(c["counterparties"]))
                    b["max_date"] = max(b["max_date"], d) if b["max_date"] else d
                    b["min_date"] = min(b["min_date"], d) if b["min_date"] else d
                    placed = True
                    break
            if not placed:
                buckets.append({"claims": [c], "cps": list(c["counterparties"]),
                                "min_date": d, "max_date": d})
        clusters += buckets

    stats["clusters"] += len(clusters)
    # ---- emit one transaction per cluster + consent price ----
    for ci, b in enumerate(clusters):
        prices = [c["price_val"] for c in b["claims"] if c["price_val"] is not None]
        claim_units = {c["price_unit"] for c in b["claims"] if c["price_unit"]}
        cl_unit = unit if unit else (claim_units.pop() if len(claim_units) == 1 else "mixed")
        consensus = None
        status = "reported"
        if len(prices) >= 2:
            lo, hi = min(prices), max(prices)
            if lo and abs(hi - lo) / lo <= 0.02:
                consensus = sum(prices) / len(prices)
            else:
                status = "conflicting"
                stats["conflicting"] += 1
        elif len(prices) == 1:
            consensus = prices[0]
        vessel_claim = b["claims"][0]
        name = vessel_claim["name"]
        vid = None
        if vessel_claim["vessel_key"].startswith("imo:"):
            vid = "vessel:" + vessel_claim["vessel_key"]
        elif name:
            vid = "vessel:prov:" + P2.sha16(norm_name(name))
        txn_id = "t:" + P2.sha16(
            f"{vessel_claim['kind']}|{vessel_claim['vessel_key']}|{b['min_date'].isoformat()}"
            f"|{b['max_date'].isoformat()}|{'|'.join(b['cps'])}")
        # The same printed deal is reachable from two claim sources (per-row CSVs generated by
        # p2_series and the *.tables.json sidecars of the same bulletin). First source wins so
        # the deterministic txn_id stays unique; the duplicate is counted, never silently lost.
        if txn_id in bufs["txn_ids"]:
            stats["cross_source_dupe"] = stats.get("cross_source_dupe", 0) + 1
            continue
        bufs["txn_ids"].add(txn_id)
        terms = {
            "price": consensus, "price_unit": cl_unit,
            "counterparties": b["cps"],
            "vessel": {"name": name, "key": vessel_claim["vessel_key"]},
            "claims": [{"value": c["price_val"], "unit": c["price_unit"],
                        "raw": c["price_raw"], "doc_id": c["doc_id"],
                        "date": c["date"], "src": c.get("sidecar") or c.get("stem")}
                       for c in b["claims"]],
        }
        txn_rows.append((txn_id, vessel_claim["kind"], vid, json.dumps(b["cps"]),
                         b["min_date"], b["max_date"],
                         json.dumps(terms, ensure_ascii=False), status))
        seen_mentions = set()
        for c in b["claims"]:
            # one mention per (doc, printed row): the same printed deal can be re-claimed inside a
            # cluster by a second claim source with a different counterparty spelling
            mkey = (c["doc_id"], c["row_ord"])
            if mkey in seen_mentions:
                stats["dupe_mentions"] = stats.get("dupe_mentions", 0) + 1
                continue
            seen_mentions.add(mkey)
            # store the whole claim (printed cells verbatim + parsed deal fields) so the P2 gate can
            # re-resolve the printed row and re-check price/kind/counterparties independently.
            mention_rows.append((txn_id, c["doc_id"], 0, c["row_ord"], None, None,
                                 date.fromisoformat(c["date"]),
                                 json.dumps(c, ensure_ascii=False)))
        if vid and vid not in seen_entities:
            seen_entities.add(vid)
            entity_rows.append((vid, "vessel", name or vid,
                                json.dumps({"vessel_key": vessel_claim["vessel_key"]}),
                                "provisional", "p2_transactions"))
            stats["vessel_entities"] += 1
        if len(txn_rows) >= txn_batch:
            con.executemany("INSERT OR IGNORE INTO transaction VALUES (?,?,?,?,?,?,?,?)", txn_rows)
            del txn_rows[:]
            con.executemany(
                "INSERT INTO mention (txn_id, doc_id, table_ord, row_ord, chunk_id, sids, published_at, claimed) "
                "VALUES (?,?,?,?,?,?,?,?)", mention_rows)
            del mention_rows[:]
            con.executemany(
                "INSERT OR IGNORE INTO entity (entity_id, type, canonical_name, attrs, status, created_by) "
                "VALUES (?,?,?,?,?,?)", entity_rows)
            del entity_rows[:]
            con.commit()


def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    meta = yaml.safe_load(MAP.read_text(encoding="utf-8"))
    entries = {e.get("stem"): e for e in meta["series"]}
    con = duckdb.connect(str(DB))
    con.execute("SET memory_limit='128MB'")
    con.execute("SET checkpoint_threshold='16MB'")
    con.execute("SET threads=1")
    # rebuild-only scope: txn + mention + provisional vessel entities
    con.execute("DELETE FROM mention")
    con.execute("DELETE FROM transaction")
    # keep any confirmed entities; we only (re)insert provisional vessel entities we own
    doc_by_source_file, doc_by_srcf_basename, doc_by_sf_stem, doc_pub, stem_list = P2.load_doc_maps(con)

    stats = {"rows": 0, "skipped_nodate": 0, "skipped_nonnum_price": 0,
             "non_txn_skipped": 0, "clusters": 0, "conflicting": 0, "mentions": 0,
             "vessel_entities": 0, "unresolved_doc": 0, "defects": 0}
    defects = []

    txn_rows = []
    mention_rows = []
    entity_rows = []
    seen_entities = set()
    txn_batch = 2000
    bufs = {"txn": txn_rows, "mention": mention_rows, "entity": entity_rows,
            "seen": seen_entities, "txn_ids": set()}

    for stem, spec in SPECS.items():
        if stem in NON_TXN_SKIP:
            stats["non_txn_skipped"] += 1
            defects.append({"stem": stem, "issue": NON_TXN_SKIP[stem]})
            continue
        if not entries.get(stem):
            continue
        e = entries[stem]
        csv_path = SERIES / f"{stem}.csv"
        if not csv_path.exists():
            defects.append({"stem": stem, "issue": "csv_missing"})
            continue
        kind = spec["kind"]
        kind_col = spec.get("kind_col")
        # collect claims for this stem, then cluster
        claims = []
        with open(csv_path, newline="", encoding="utf-8-sig", errors="replace") as fh:
            header = next(csv.reader(fh), None)
            if header is None:
                defects.append({"stem": stem, "issue": "csv_empty"})
                continue
            idx = lc_index(header)
            for row_ord, rec in enumerate(csv.reader(fh)):
                if not rec:
                    continue
                row = {c: (rec[i] if i < len(rec) else "") for i, c in enumerate(header)}
                pub = parse_pub(row, idx, spec)
                if pub is None:
                    stats["skipped_nodate"] += 1
                    continue
                k = kind if not kind_col else kind_from_cell(get(row, idx, kind_col), kind)
                vk = vessel_key(row, idx, spec)
                price_raw = get(row, idx, spec.get("price"))
                price_val = P2.to_number(price_raw) if price_raw else None
                if price_raw and price_val is None:
                    stats["skipped_nonnum_price"] += 1
                sf = get(row, idx, "source_file")
                doc_id = P2.resolve_doc(sf, doc_by_source_file, doc_by_srcf_basename, doc_by_sf_stem, stem_list)
                if sf and not doc_id:
                    stats["unresolved_doc"] += 1
                name = get(row, idx, spec.get("name"))
                cps = []
                for b in (spec.get("buyers") or []):
                    cps += norm_counterparty(get(row, idx, b))
                claim = {
                    "stem": stem, "row_ord": row_ord, "kind": k, "vessel_key": vk,
                    "date": pub.isoformat(), "price_val": price_val,
                    "price_unit": spec["unit"], "price_raw": price_raw,
                    "name": name, "counterparties": sorted(set(cps)),
                    "doc_id": doc_id,
                    "printed": {k2: v2 for k2, v2 in row.items() if str(v2).strip()},
                }
                claims.append(claim)
                stats["rows"] += 1
        stats["mentions"] += len(claims)
        cluster_emit(con, claims, spec["unit"], stats, bufs, txn_batch)

    # ---- §4.2 second claim source: per-publisher *.tables.json sidecars ----
    sidecar_report = {}
    try:
        import p2_tables
        sidecar_groups, sidecar_stats = p2_tables.collect_claims(
            con, (doc_by_source_file, doc_by_srcf_basename, doc_by_sf_stem, doc_pub, stem_list),
            sidecar_report)
    except Exception as exc:  # never let the sidecar pass lose the CSV deal path
        sidecar_groups, sidecar_stats = {}, {"error": repr(exc)}
        defects.append({"stem": "tables.json", "issue": f"sidecar_pass_failed: {exc!r}"})
    stats["sidecar_claims"] = int(sidecar_stats.get("claims", 0) or 0)
    stats["sidecar_sidecars"] = int(sidecar_stats.get("sidecars", 0) or 0)
    for (label, skind), claims in sorted(sidecar_groups.items()):
        stats["rows"] += len(claims)
        stats["mentions"] += len(claims)
        cluster_emit(con, claims, None, stats, bufs, txn_batch)

    # final flush
    if txn_rows:
        con.executemany("INSERT OR IGNORE INTO transaction VALUES (?,?,?,?,?,?,?,?)", txn_rows)
        txn_rows = []
    if mention_rows:
        con.executemany(
            "INSERT INTO mention (txn_id, doc_id, table_ord, row_ord, chunk_id, sids, published_at, claimed) "
            "VALUES (?,?,?,?,?,?,?,?)", mention_rows)
        mention_rows = []
    if entity_rows:
        con.executemany(
            "INSERT OR IGNORE INTO entity (entity_id, type, canonical_name, attrs, status, created_by) "
            "VALUES (?,?,?,?,?,?)", entity_rows)
        entity_rows = []
    con.commit()

    n_txn = con.execute("SELECT count(*) FROM transaction").fetchone()[0]
    n_mention = con.execute("SELECT count(*) FROM mention").fetchone()[0]
    con.close()

    report = {"phase": "P2_transactions", "stats": stats,
              "actual_transactions": n_txn, "actual_mentions": n_mention, "defects": defects}
    (REPORTS / "p2_transactions.json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"p2_transactions: transactions={n_txn:,} mentions={n_mention:,} rows={stats['rows']:,} "
          f"clusters={stats['clusters']:,} conflicting={stats['conflicting']:,} vessel_entities={stats['vessel_entities']:,}")
    print(f"  skipped_nodate={stats['skipped_nodate']:,} nonnum_price={stats['skipped_nonnum_price']:,} "
          f"unresolved_doc={stats['unresolved_doc']:,} non_txn={stats['non_txn_skipped']}")
    for d in defects[:30]:
        print("  defect:", d)
    return 0


if __name__ == "__main__":
    sys.exit(main())
