#!/usr/bin/env python3
"""GraphRAG phase P2 gate report (docs/GRAPHRAG_BUILD_PLAN.md 4.1-4.6, kb/gates.yaml P2).

Reads kb/state/kb.duckdb + the P2 artefacts and writes:

  kb/reports/p2.json   gate report JSON (sample_seed follows the gates.yaml seed rule)
  kb/reports/p2.md     human-readable gate report

Gates (gates.yaml P2):
  - raw_cell_found_sample: 2000   -> stratified (publisher x doc_type x year) sample of
    `observation` rows; every stored `raw_cell` must be found VERBATIM in the source CSV at
    (stem, row_ord, col_ord). No agent-chosen cells: the sample is hash-ordered inside strata
    and round-robin trimmed, seed = seed_for("P2").
  - raw_cell_found_all_sec: true  -> every SEC numeric fact in `observation` traceable to the
    source XBRL. SEC XBRL is SKIPPED (SEC_USER_AGENT unset, AGENT_TASK L123), so this gate is
    satisfied by the fact that zero sec:* observations exist; the skip is recorded.
  - raw_cell_found_rate: 1.0      -> found / sampled.
  - known_values_exact: 40        -> re-verify every proof in kb/reports/p2_known_values.json:
    the number in the chunk text at [char_start,char_end) reparses to the observation value.
  - known_values_exact_rate: 1.0  -> exact / proofs demanded.
  - transaction_cluster_audit: 50 -> stratified (kind) sample of `transaction` clusters.
  - transaction_cluster_precision: 0.96 -> per-cluster independent audit: dates inside the
    +/-45 day window, consensus price = mean of in-2% claims else NULL + status=conflicting,
    counterparties = union of claim counterparties, every mention's `claimed` printed row found
    verbatim in its source (CSV row or *.tables.json row), vessel entity present.

Read-only: never edits corpus/, data/, scripts/ or any MD source.
"""
import csv
import hashlib
import json
import random
import re
import sys
from datetime import date, datetime
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "kb" / "state" / "kb.duckdb"
REPORTS = ROOT / "kb" / "reports"
SERIES = ROOT / "data" / "extracted" / "series"

PHASE = "P2"
TARGET_RAW = 2000
PER_STRATUM = 25
TARGET_KNOWN = 40
TARGET_TXN = 50
TXN_PRECISION = 0.96
VIEWS = ["v_rate", "v_tc_assessment", "v_fixture", "v_sale", "v_demolition",
         "v_newbuilding", "v_company_fin", "v_commodity_flow", "v_series", "v_gaps"]


def seed_for(phase: str) -> int:
    return int(hashlib.sha256(f"{phase}|kb-gates-v1".encode()).hexdigest()[:8], 16)


SEED = seed_for(PHASE)


def to_number(raw):
    """Parse a printed numeric cell the way p2_series.to_number does (comma decimals etc.)."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    s = s.replace("\u2212", "-").replace("\u2013", "-")
    sign = -1.0 if s.startswith("-") else 1.0
    s = s.strip("+-")
    # keep digits, separators
    if not re.search(r"\d", s):
        return None
    s = re.sub(r"[^0-9.,]", "", s)
    if not s:
        return None
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):  # 1.234,56
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        parts = s.split(",")
        if len(parts) == 2 and len(parts[1]) in (1, 2):
            s = parts[0] + "." + parts[1]
        else:
            s = "".join(parts)
    try:
        return sign * float(s)
    except ValueError:
        return None


def connect():
    con = duckdb.connect(str(DB), read_only=True)
    con.execute("SET memory_limit='400MB'")
    con.execute("SET threads=1")
    return con


# ---------------------------------------------------------------- raw_cell gate
def sample_raw_cells(con, rng):
    q = """
    WITH base AS (
      SELECT o.obs_id, o.raw_cell, o.row_ord, o.col_ord, o.value,
             s.definition->>'stem' AS stem, s.definition->>'mode' AS mode,
             COALESCE(d.publisher_id, s.definition->>'source') AS publisher,
             COALESCE(d.doc_type, 'unknown') AS doc_type,
             COALESCE(strftime(o.published_at, '%Y'), 'unknown') AS yr
      FROM observation o
      JOIN series s ON s.series_id = o.series_id
      LEFT JOIN document d ON d.doc_id = o.doc_id
      WHERE s.definition->>'mode' IN ('wide', 'long')
        AND o.raw_cell IS NOT NULL
    ), rk AS (
      SELECT *, row_number() OVER (PARTITION BY publisher, doc_type, yr
                                   ORDER BY hash(obs_id)) AS rn
      FROM base
    )
    SELECT obs_id, stem, mode, publisher, doc_type, yr, row_ord, col_ord, raw_cell, value
    FROM rk WHERE rn <= ?
    """
    rows = con.execute(q, [PER_STRATUM]).fetchall()
    cols = ["obs_id", "stem", "mode", "publisher", "doc_type", "yr", "row_ord", "col_ord",
            "raw_cell", "value"]
    strata = {}
    for r in rows:
        rec = dict(zip(cols, r))
        strata.setdefault((rec["publisher"], rec["doc_type"], rec["yr"]), []).append(rec)
    keys = sorted(strata, key=lambda k: tuple("" if x is None else str(x) for x in k))
    for k in keys:
        rng.shuffle(strata[k])
    sample = []
    depth = 0
    while len(sample) < TARGET_RAW:
        added = False
        for k in keys:
            if depth < len(strata[k]):
                sample.append(strata[k][depth])
                added = True
                if len(sample) >= TARGET_RAW:
                    break
        if not added:
            break
        depth += 1
    available = sum(len(v) for v in strata.values())
    return sample, len(strata), available


def verify_raw_cells(sample):
    by_stem = {}
    for rec in sample:
        by_stem.setdefault(rec["stem"], {}).setdefault(rec["row_ord"], []).append(rec)
    results = []
    for stem in sorted(by_stem):
        want = by_stem[stem]
        path = SERIES / f"{stem}.csv"
        if not path.exists():
            for ro, recs in want.items():
                for rec in recs:
                    results.append({"obs_id": rec["obs_id"], "stem": stem, "row_ord": ro,
                                    "col_ord": rec["col_ord"], "ok": False, "issue": "csv_missing"})
            continue
        seen = set()
        last_ro = -1
        with open(path, newline="", encoding="utf-8-sig", errors="replace") as fh:
            rd = csv.reader(fh)
            header = next(rd, None)
            if header is None:
                for ro, recs in want.items():
                    for rec in recs:
                        results.append({"obs_id": rec["obs_id"], "stem": stem, "row_ord": ro,
                                        "col_ord": rec["col_ord"], "ok": False,
                                        "issue": "csv_empty"})
                continue
            for ro, row in enumerate(rd):
                last_ro = ro
                if ro not in want:
                    continue
                seen.add(ro)
                for rec in want[ro]:
                    co = rec["col_ord"]
                    if co is None or co < 0 or co >= len(row):
                        results.append({"obs_id": rec["obs_id"], "stem": stem, "row_ord": ro,
                                        "col_ord": co, "ok": False,
                                        "issue": "col_out_of_range" if row else "row_empty",
                                        "row_len": len(row)})
                        continue
                    got = row[co]
                    ok = got == rec["raw_cell"]
                    item = {"obs_id": rec["obs_id"], "stem": stem, "row_ord": ro, "col_ord": co,
                            "ok": ok}
                    if not ok:
                        # secondary check: is the cell verbatim somewhere else in the row?
                        elsewhere = [i for i, v in enumerate(row) if v == rec["raw_cell"]]
                        item["issue"] = ("verbatim_in_row_other_col" if elsewhere
                                         else "raw_cell_not_in_row")
                        item["col_matches"] = elsewhere[:5]
                        item["want"] = rec["raw_cell"]
                        item["got"] = got
                    results.append(item)
        for ro, recs in want.items():
            if ro in seen:
                continue
            for rec in recs:
                results.append({"obs_id": rec["obs_id"], "stem": stem, "row_ord": ro,
                                "col_ord": rec["col_ord"], "ok": False,
                                "issue": "row_missing", "csv_rows": last_ro + 1})
    return results


def gate_raw_cells(con, rng):
    sample, n_strata, n_available = sample_raw_cells(con, rng)
    results = verify_raw_cells(sample)
    found = sum(1 for r in results if r["ok"])
    n = len(results)
    issues = {}
    for r in results:
        if not r["ok"]:
            issues[r["issue"]] = issues.get(r["issue"], 0) + 1
    strata_cov = sorted({(r.get("stem"),) for r in []})  # placeholder, kept for clarity
    sec_n = con.execute(
        "SELECT count(*) FROM observation WHERE provenance = 'xbrl' OR series_id LIKE 'sec:%'"
    ).fetchone()[0]
    sec_ok = sec_n == 0
    sec_note = ("SEC_USER_AGENT unset -> SEC XBRL ingestion skipped (AGENT_TASK L123); "
                "0 sec:* observations stored, so every stored SEC fact is vacuously traceable")
    out = {
        "sample_requested": TARGET_RAW,
        "sample_size": n,
        "strata": n_strata,
        "strata_available_rows": n_available,
        "found": found,
        "rate": (found / n) if n else 0.0,
        "mismatch_issues": issues,
        "mismatches_sample": [r for r in results if not r["ok"]][:20],
        "sec_observations": sec_n,
        "sec_all_found": sec_ok,
        "sec_note": sec_note,
        "sample_seed": SEED,
    }
    out["passed"] = (n >= TARGET_RAW and found == n and sec_ok)
    return out


# ------------------------------------------------------------ known-values gate
def gate_known_values(con):
    path = REPORTS / "p2_known_values.json"
    out = {"source": "kb/reports/p2_known_values.json", "target": TARGET_KNOWN}
    if not path.exists():
        out.update({"records": 0, "exact": 0, "rate": 0.0, "passed": False,
                    "error": "p2_known_values.json missing (run kb/p2_known_values.py first)"})
        return out
    data = json.loads(path.read_text(encoding="utf-8"))
    records = data.get("records") or []
    exact = 0
    checks = []
    for rec in records:
        cid = rec.get("chunk_id")
        body_row = con.execute("SELECT body FROM chunk WHERE chunk_id = ?", [cid]).fetchone()
        if not body_row:
            checks.append({"obs_id": rec.get("obs_id"), "ok": False, "issue": "chunk_missing"})
            continue
        body = body_row[0]
        a, b = rec.get("char_start"), rec.get("char_end")
        if not isinstance(a, int) or not isinstance(b, int) or a < 0 or b > len(body):
            checks.append({"obs_id": rec.get("obs_id"), "ok": False, "issue": "char_range_bad"})
            continue
        token = body[a:b]
        token_num = to_number(token)
        obs_row = con.execute("SELECT value FROM observation WHERE obs_id = ?",
                              [rec.get("obs_id")]).fetchone()
        if obs_row is None:
            checks.append({"obs_id": rec.get("obs_id"), "ok": False, "issue": "obs_missing"})
            continue
        ok = (token_num is not None and obs_row[0] is not None
              and abs(token_num - obs_row[0]) <= 1e-9 * max(1.0, abs(obs_row[0])))
        if token_num is None:
            issue = "token_not_numeric"
        elif not ok:
            issue = "value_mismatch"
        else:
            issue = None
        checks.append({"obs_id": rec.get("obs_id"), "chunk_id": cid, "token": token,
                       "token_num": token_num, "obs_value": obs_row[0], "ok": ok, "issue": issue})
        if ok:
            exact += 1
    publishers = sorted({r.get("publisher") for r in records if r.get("publisher")})
    out.update({
        "records": len(records),
        "exact": exact,
        "rate": (exact / len(records)) if records else 0.0,
        "publishers": publishers,
        "n_publishers": len(publishers),
        "failures": [c for c in checks if not c["ok"]][:20],
        "checks_sample": checks[:5],
        "declared_passed": bool(data.get("passed")),
    })
    out["passed"] = (len(records) >= TARGET_KNOWN and exact == len(records)
                     and len(publishers) >= 8)
    return out


# ---------------------------------------------------------- transaction audit gate
def load_sidecar(rel, cache):
    if rel in cache:
        return cache[rel]
    p = ROOT / rel
    d = json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
    cache[rel] = d
    return d


def load_csv_rows(stem, cache):
    if stem in cache:
        return cache[stem]
    p = SERIES / f"{stem}.csv"
    rows = None
    if p.exists():
        with open(p, newline="", encoding="utf-8-sig", errors="replace") as fh:
            rd = csv.reader(fh)
            header = next(rd, None)
            if header is not None:
                rows = (header, list(rd))
    cache[stem] = rows
    return rows


def verify_printed(claimed, side_cache, csv_cache):
    """True if the claim's `printed` row (or its cells) is found verbatim in its source."""
    printed = claimed.get("printed") or {}
    cells = {k: v for k, v in printed.items() if not k.startswith("__")}
    if claimed.get("sidecar"):
        d = load_sidecar(claimed["sidecar"], side_cache)
        if not isinstance(d, dict):
            return False, "sidecar_missing"
        key = printed.get("__key")
        rows = d.get(key)
        try:
            ro = int(printed.get("__row"))
        except (TypeError, ValueError):
            return False, "sidecar_row_bad"
        if not isinstance(rows, list) or ro >= len(rows) or not isinstance(rows[ro], dict):
            return False, "sidecar_row_missing"
        src = rows[ro]
        for k, v in cells.items():
            if k not in src:
                return False, "sidecar_key_missing"
            if str(src[k]) != v:
                return False, "sidecar_cell_mismatch"
        return True, None
    stem = claimed.get("stem")
    if not stem or stem.startswith("tables:"):
        return False, "claim_source_unknown"
    rows = load_csv_rows(stem, csv_cache)
    if rows is None:
        return False, "csv_missing"
    header, body = rows
    try:
        ro = int(claimed.get("row_ord"))
    except (TypeError, ValueError):
        return False, "csv_row_bad"
    if ro >= len(body):
        return False, "csv_row_missing"
    rec = body[ro]
    idx = {h: i for i, h in enumerate(header)}
    for k, v in cells.items():
        i = idx.get(k)
        if i is None:
            return False, "csv_col_missing"
        got = rec[i] if i < len(rec) else None
        if got != v:
            return False, "csv_cell_mismatch"
    return True, None


def audit_cluster(con, row, side_cache, csv_cache, claim_cache):
    tid, kind, vid, cps_json, dfrom, dto, terms_json, status = row
    fails = []
    try:
        terms = json.loads(terms_json) if terms_json else {}
        cps = sorted(json.loads(cps_json) if cps_json else [])
    except (TypeError, ValueError):
        return ["terms_json_bad"], {}
    claims = terms.get("claims") or []
    if not claims:
        fails.append("no_claims")
    if dfrom is None or dto is None:
        fails.append("no_dates")
    else:
        if dto < dfrom:
            fails.append("dates_reversed")
        if (dto - dfrom).days > 45:
            fails.append("span_gt_45d")
    for c in claims:
        try:
            d = date.fromisoformat(c.get("date"))
        except (TypeError, ValueError):
            fails.append("claim_date_bad")
            continue
        if dfrom is not None and dto is not None and not (dfrom <= d <= dto):
            fails.append("claim_date_outside_window")
        if c.get("value") is not None:
            rp = to_number(c.get("raw"))
            if rp is None or abs(rp - c["value"]) > 1e-9 * max(1.0, abs(c["value"])):
                fails.append("claim_value_reparse")
    # consensus recompute (PLAN 4.4 / p2_transactions.cluster_emit rule)
    prices = [c["value"] for c in claims if c.get("value") is not None]
    exp_status, exp_price = "reported", None
    if len(prices) >= 2:
        lo, hi = min(prices), max(prices)
        if lo and abs(hi - lo) / lo <= 0.02:
            exp_price = sum(prices) / len(prices)
        else:
            exp_status = "conflicting"
    elif len(prices) == 1:
        exp_price = prices[0]
    if status != exp_status:
        fails.append("status_mismatch")
    got_price = terms.get("price")
    if exp_price is None:
        if got_price is not None:
            fails.append("price_should_be_null")
    elif got_price is None or abs(got_price - exp_price) > 1e-9 * max(1.0, abs(exp_price)):
        fails.append("price_mismatch")
    # mentions + printed-row provenance
    mentions = claim_cache.get(tid)
    if mentions is None:
        mentions = con.execute(
            "SELECT doc_id, row_ord, claimed, sids, chunk_id FROM mention WHERE txn_id = ?",
            [tid]).fetchall()
        claim_cache[tid] = mentions
    if not mentions:
        fails.append("no_mentions")
    union = set()
    n_verified = 0
    for m in mentions:
        try:
            claimed = json.loads(m[2]) if m[2] else None
        except (TypeError, ValueError):
            claimed = None
        if not isinstance(claimed, dict) or not claimed.get("printed"):
            fails.append("claimed_bad")
            continue
        union |= set(claimed.get("counterparties") or [])
        if claimed.get("kind") and claimed["kind"] != kind:
            fails.append("claim_kind_mismatch")
        if claimed.get("price_raw"):
            rp = to_number(claimed["price_raw"])
            if rp is None or claimed.get("price_val") is None or \
                    abs(rp - claimed["price_val"]) > 1e-9 * max(1.0, abs(claimed["price_val"])):
                fails.append("claimed_price_reparse")
        ok, why = verify_printed(claimed, side_cache, csv_cache)
        if ok:
            n_verified += 1
        else:
            fails.append(why or "printed_row_missing")
    if sorted(union) != cps:
        fails.append("counterparties_mismatch")
    if vid:
        n = con.execute("SELECT count(*) FROM entity WHERE entity_id = ?", [vid]).fetchone()[0]
        if not n:
            fails.append("vessel_entity_missing")
    return sorted(set(fails)), {"mentions": len(mentions), "verified_rows": n_verified,
                                "price": got_price, "status": status}


def gate_transactions(con, rng):
    out = {"target": TARGET_TXN, "precision_required": TXN_PRECISION}
    rows = con.execute(
        "SELECT txn_id, kind, vessel_id, counterparties, date_from, date_to, terms, status "
        "FROM transaction").fetchall()
    out["clusters_total"] = len(rows)
    if not rows:
        out.update({"sample_size": 0, "passed": [], "precision": 0.0, "passed_gate": False})
        out["passed"] = False
        return out
    by_kind = {}
    for r in rows:
        by_kind.setdefault(r[1], []).append(r)
    total = len(rows)
    kinds = sorted(by_kind)
    alloc = {}
    for k in kinds:
        alloc[k] = max(1, int(TARGET_TXN * len(by_kind[k]) / total))
    # trim / top-up to exactly TARGET_TXN
    while sum(alloc.values()) > TARGET_TXN:
        k = max(alloc, key=lambda x: alloc[x] - TARGET_TXN * len(by_kind[x]) / total)
        if alloc[k] > 1:
            alloc[k] -= 1
        else:
            break
    while sum(alloc.values()) < TARGET_TXN:
        k = max(kinds, key=lambda x: len(by_kind[x]) - alloc[x])
        if alloc[k] >= len(by_kind[k]):
            break
        alloc[k] += 1
    sample = []
    for k in kinds:
        pool = list(by_kind[k])
        rng.shuffle(pool)
        sample.extend(pool[:alloc[k]])
    sample = sample[:TARGET_TXN]
    side_cache, csv_cache, claim_cache = {}, {}, {}
    checks = []
    n_pass = 0
    verified_rows = 0
    for r in sample:
        fails, info = audit_cluster(con, r, side_cache, csv_cache, claim_cache)
        verified_rows += info.get("verified_rows", 0)
        ok = not fails
        n_pass += 1 if ok else 0
        checks.append({"txn_id": r[0], "kind": r[1], "ok": ok, "fails": fails, **info})
    precision = (n_pass / len(sample)) if sample else 0.0
    out.update({
        "allocation": alloc,
        "kinds": {k: len(v) for k, v in by_kind.items()},
        "sample_size": len(sample),
        "passed_clusters": n_pass,
        "precision": precision,
        "printed_rows_verified": verified_rows,
        "failures": [c for c in checks if not c["ok"]][:20],
        "checks_sample": checks[:5],
    })
    out["passed"] = (len(sample) >= TARGET_TXN and precision >= TXN_PRECISION)
    return out


# ----------------------------------------------------------------- db + views
def db_summary(con):
    out = {}
    for t in ("document", "section", "chunk", "observation", "series", "mention",
              "transaction", "entity", "corpus_known_gaps"):
        try:
            out[t] = con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        except Exception as exc:  # table missing in this DB
            out[t] = f"error: {exc!r}"[:120]
    views = {}
    for v in VIEWS:
        try:
            views[v] = con.execute(f"SELECT count(*) FROM {v}").fetchone()[0]
        except Exception as exc:
            views[v] = f"error: {exc!r}"[:120]
    out["views"] = views
    out["views_present"] = sum(1 for v in views.values() if isinstance(v, int))
    return out


def main() -> int:
    started = datetime.now()
    REPORTS.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)
    con = connect()
    db = db_summary(con)
    raw = gate_raw_cells(con, rng)
    known = gate_known_values(con)
    txn = gate_transactions(con, rng)
    con.close()

    gates = {
        "raw_cell_found_sample": raw["sample_size"],
        "raw_cell_found_all_sec": bool(raw["sec_all_found"]),
        "raw_cell_found_rate": round(raw["rate"], 6),
        "known_values_exact": known["exact"],
        "known_values_exact_rate": round(known["rate"], 6),
        "transaction_cluster_audit": txn["sample_size"],
        "transaction_cluster_precision": round(txn["precision"], 6),
    }
    checks = {
        "raw_cell_found_sample": raw["sample_size"] >= TARGET_RAW,
        "raw_cell_found_all_sec": bool(raw["sec_all_found"]),
        "raw_cell_found_rate": raw["rate"] == 1.0,
        "known_values_exact": known["exact"] >= TARGET_KNOWN,
        "known_values_exact_rate": known["rate"] == 1.0,
        "transaction_cluster_audit": txn["sample_size"] >= TARGET_TXN,
        "transaction_cluster_precision": txn["precision"] >= TXN_PRECISION,
    }
    result = "PASSED" if all(checks.values()) else "FAILED"
    report = {
        "phase": PHASE,
        "sample_seed": SEED,
        "result": result,
        "gate_metrics": gates,
        "gate_checks": checks,
        "db": db,
        "raw_cell": raw,
        "known_values": known,
        "transactions": txn,
        "duration_s": round((datetime.now() - started).total_seconds(), 1),
    }
    (REPORTS / "p2.json").write_text(json.dumps(report, indent=1, ensure_ascii=False),
                                     encoding="utf-8")
    md = [
        "# P2 gate report", "",
        f"- result: **{result}**",
        f"- sample_seed: `{SEED}` (seed_for('P2'))",
        f"- generated: {started.isoformat(timespec='seconds')}",
        f"- duration: {report['duration_s']}s", "",
        "## Gates", "",
        "| gate | value | required | pass |", "| --- | --- | --- | --- |",
        f"| raw_cell_found_sample | {gates['raw_cell_found_sample']} | 2000 | "
        f"{checks['raw_cell_found_sample']} |",
        f"| raw_cell_found_all_sec | {gates['raw_cell_found_all_sec']} | true | "
        f"{checks['raw_cell_found_all_sec']} |",
        f"| raw_cell_found_rate | {gates['raw_cell_found_rate']} | 1.0 | "
        f"{checks['raw_cell_found_rate']} |",
        f"| known_values_exact | {gates['known_values_exact']} | 40 | "
        f"{checks['known_values_exact']} |",
        f"| known_values_exact_rate | {gates['known_values_exact_rate']} | 1.0 | "
        f"{checks['known_values_exact_rate']} |",
        f"| transaction_cluster_audit | {gates['transaction_cluster_audit']} | 50 | "
        f"{checks['transaction_cluster_audit']} |",
        f"| transaction_cluster_precision | {gates['transaction_cluster_precision']} | 0.96 | "
        f"{checks['transaction_cluster_precision']} |", "",
        "## raw_cell audit (PLAN 4.1/4.2)", "",
        f"- sample {raw['sample_size']} observations from {raw['strata']} strata "
        f"(publisher x doc_type x year, {raw['strata_available_rows']} rows available at cap "
        f"{PER_STRATUM}/stratum)",
        f"- found verbatim at (stem, row_ord, col_ord): {raw['found']}/{raw['sample_size']}",
        f"- mismatch issues: {raw['mismatch_issues'] or 'none'}",
        f"- SEC: {raw['sec_observations']} sec:* observations; {raw['sec_note']}", "",
        "## known values (PLAN 4.3 / re-derived proofs)", "",
        f"- proofs re-verified: {known['exact']}/{known.get('records', 0)} exact "
        f"({known.get('n_publishers', 0)} publishers)",
        f"- failures: {len(known.get('failures') or [])}", "",
        "## transaction clusters (PLAN 4.4, D9)", "",
        f"- clusters in DB: {txn.get('clusters_total')}, audited: {txn['sample_size']} "
        f"(stratified by kind: {txn.get('allocation')})",
        f"- precision: {txn.get('passed_clusters')}/{txn['sample_size']} = "
        f"{round(txn['precision'], 4)} (required {TXN_PRECISION})",
        f"- printed source rows re-found verbatim: {txn.get('printed_rows_verified')}",
        f"- failing clusters (first 10): "
        f"{[(c['txn_id'], c['fails']) for c in (txn.get('failures') or [])[:10]]}", "",
        "## DB", "",
        "| table | rows |", "| --- | --- |",
    ]
    for k, v in db.items():
        if k.startswith("views"):
            continue
        md.append(f"| {k} | {v} |")
    md += ["", "## views", "", "| view | rows |", "| --- | --- |"]
    for k, v in (db.get("views") or {}).items():
        md.append(f"| {k} | {v} |")
    (REPORTS / "p2.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    print(f"p2_report: result={result}")
    for k in gates:
        print(f"  {k}: {gates[k]} (required pass={checks[k]})")
    print(f"  db: { {k: v for k, v in db.items() if not k.startswith('views')} }")
    if raw["mismatch_issues"]:
        print(f"  raw_cell mismatch issues: {raw['mismatch_issues']}")
    if txn.get("failures"):
        print(f"  txn failures (first 5): {[(c['txn_id'], c['fails']) for c in txn['failures'][:5]]}")
    return 0 if result == "PASSED" else 1


if __name__ == "__main__":
    sys.exit(main())
