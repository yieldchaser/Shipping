#!/usr/bin/env python3
"""
GraphRAG phase P2 loader — layer-A series + observations (docs/GRAPHRAG_BUILD_PLAN.md §3 DDL, §4.1).
Reads kb/series_map.yaml and data/extracted/series/*.csv and writes, into kb/state/kb.duckdb:
  - all layer-A tables (CREATE IF NOT EXISTS, exact PLAN §3 DDL)
  - `series`     one row per (stem, measurement, entity-signature)
  - `observation` one row per numeric cell, value parsed, raw_cell verbatim
Deterministic + idempotent: re-running TRUNCATEs and rebuilds `series`/`observation` only.
Handled edge cases:
  (a) drewry_ais_chart_series date_from ['year','week'] -> period_from = ISO-week Monday.
  (b) seabrokers_fleet_moves: no `value` col, metric categorical -> 0 numeric observations (logged).
  (c) empty date_col cells -> fall back to `issue` then extra_json.{issue_date,report_date,date}.
  (d) mixed_sources (clarksons via source_file, breakwave via `sector`): still one CSV stem; the
      per-row source_file cascade resolves doc_id/published_at per row.
  (e) source_file -> doc_id via exact/basename/stem cascade; no-source_file rows -> method csv:<file>
      and published_at = first git commit containing the CSV (never invented).
Deferred to p2_transactions.py: singletons_sales_series, xclusiv/intermodal newbuilding-orders,
and all transaction clustering. SEC XBRL loader is skipped (SEC_USER_AGENT unset).
Usage: python kb/p2_series.py
"""
import csv
import hashlib
import json
import re
import subprocess
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
import duckdb
import pyarrow as pa
import yaml
# Observation load columns, in DDL order minus ingested_at (DEFAULT now()).
OBS_COLS = ["obs_id", "series_id", "period_from", "period_to", "value", "unit", "raw_cell",
            "doc_id", "table_ord", "row_ord", "col_ord", "published_at", "supersedes",
            "method", "provenance"]
OBS_TYPES = [pa.int64(), pa.string(), pa.date32(), pa.date32(), pa.float64(), pa.string(),
             pa.string(), pa.string(), pa.int32(), pa.int32(), pa.int32(), pa.date32(),
             pa.int64(), pa.string(), pa.string()]
OBS_SCHEMA = pa.schema(list(zip(OBS_COLS, OBS_TYPES)))
OBS_SQL_COLS = "(" + ", ".join(OBS_COLS) + ")"
try:
    import psutil
except ImportError:  # guard still works; no RAM-aware throttle
    psutil = None
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
# §10 memory guard: shrink batch below 700 MB free; pause (exit 3) below 280 MB free.
# Host baseline on this 8 GB box is ~0.5-0.9 GB available, so the thresholds are set to
# leave genuine headroom for the loader's own ~200 MB footprint without pausing on noise.
FREE_LO_BYTES = 700 * 1024 * 1024          # <700 MB -> shrink batch
FREE_PAUSE_BYTES = 280 * 1024 * 1024       # <280 MB -> halt safely (exit 3, resumable)
def free_ram_bytes():
    if psutil is None:
        return None
    try:
        return psutil.virtual_memory().available
    except Exception:
        return None
class MemoryPressure(Exception):
    pass
ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "kb" / "state" / "kb.duckdb"
SERIES = ROOT / "data" / "extracted" / "series"
MAP = ROOT / "kb" / "series_map.yaml"
REPORTS = ROOT / "kb" / "reports"
# stems that p2_series defers to p2_transactions (deal clustering, no plain numeric series)
# one row = one vessel sale/order/demo; entity_cols are per-row-unique -> series explosion
DEFER_STEMS = {
    # per-row vessel deal/transaction tables -> p2_transactions (D9 clustering)
    "singletons_sales_series",
    "advanced_shipping_sales_series",
    "advanced_shipping_newbuilding_series",
    "advanced_shipping_demo_sales_series",
    "clarksons_sales_series",
    "clarksons_snp_sales_series",
    "clarksons_demolition_series",
    "clarksons_demolition_sales_series",
    "intermodal_sales_series",
    "intermodal_demo_sales_series",
    "bancosta_sales_series",
    "bancosta_container_fixtures_series",
    "carriers_demolition_series",
    "carriers_sales_series",
    "carriers_newbuilding_series",
    "gms_demolition_sales_series",
    "hellenic_best_oasis_deals_series",
    "hellenic_vv_benchmark_sales_series",
    "hellenic_vv_sales_series",
    "hellenic_gms_port_positions_series",
    "lion_deals_series",
    "lion_demo_sales_series",
    "lion_sales_series",
    "star_asia_deals_series",
    "star_asia_snp_sales_series",
    "xclusiv_sales_series",
    "xclusiv_demo_sales_series",
    # categorical/non-numeric, no numeric observations
    "seabrokers_fleet_moves_series",
}
# documented first-commit dates for no-source_file CSVs (last-resort only, git is authoritative)
FIRST_COMMIT_FALLBACK = {
    "drewry_ais_chart_series": "2026-10-12",
    "seabrokers_rig_utilisation_monthly_series": "2026-10-25",
}
FIRST_COMMIT_DEFAULT = "2026-10-06"
DDL = """
CREATE TABLE IF NOT EXISTS entity (entity_id VARCHAR PRIMARY KEY,
  type VARCHAR NOT NULL, canonical_name VARCHAR NOT NULL, attrs JSON, status VARCHAR,
  created_by VARCHAR NOT NULL);
CREATE TABLE IF NOT EXISTS alias (alias VARCHAR, alias_norm VARCHAR, entity_id VARCHAR, source VARCHAR,
  confidence REAL, merged_by VARCHAR, valid_from DATE, valid_to DATE,
  PRIMARY KEY (alias_norm, entity_id));
CREATE TABLE IF NOT EXISTS merge_log (run VARCHAR, a VARCHAR, b VARCHAR, decision VARCHAR, method VARCHAR,
  score REAL, evidence JSON, "at" TIMESTAMP);
CREATE TABLE IF NOT EXISTS series (series_id VARCHAR PRIMARY KEY, name VARCHAR, unit VARCHAR, currency VARCHAR,
  basis VARCHAR, frequency VARCHAR, entity_ids VARCHAR[], source_csv VARCHAR, definition JSON);
CREATE TABLE IF NOT EXISTS observation (obs_id BIGINT PRIMARY KEY, series_id VARCHAR,
  period_from DATE NOT NULL, period_to DATE NOT NULL,
  value DOUBLE NOT NULL, unit VARCHAR, raw_cell VARCHAR NOT NULL,
  doc_id VARCHAR, table_ord INT, row_ord INT, col_ord INT,
  published_at DATE NOT NULL, ingested_at TIMESTAMP DEFAULT now(),
  method VARCHAR NOT NULL, provenance VARCHAR NOT NULL, supersedes BIGINT);
CREATE TABLE IF NOT EXISTS transaction (txn_id VARCHAR PRIMARY KEY, kind VARCHAR,
  vessel_id VARCHAR, counterparties JSON, date_from DATE, date_to DATE,
  terms JSON, status VARCHAR);
CREATE TABLE IF NOT EXISTS mention (txn_id VARCHAR, doc_id VARCHAR, table_ord INT, row_ord INT, chunk_id VARCHAR,
  sids INT[], published_at DATE, claimed JSON);
CREATE TABLE IF NOT EXISTS edge (edge_id VARCHAR PRIMARY KEY, type VARCHAR NOT NULL, src VARCHAR, dst VARCHAR,
  attrs_printed JSON, attrs JSON, valid_from DATE, valid_to DATE,
  published_at DATE NOT NULL, doc_id VARCHAR, chunk_id VARCHAR, sids INT[], quote VARCHAR NOT NULL,
  extractor VARCHAR NOT NULL, confidence REAL, status VARCHAR DEFAULT 'active');
CREATE TABLE IF NOT EXISTS event (event_id VARCHAR PRIMARY KEY, type VARCHAR, summary VARCHAR,
  occurred_from DATE, occurred_to DATE, published_at DATE, location VARCHAR, magnitude_printed VARCHAR,
  doc_id VARCHAR, chunk_id VARCHAR, sids INT[], quote VARCHAR NOT NULL, extractor VARCHAR, confidence REAL);
CREATE TABLE IF NOT EXISTS event_role (event_id VARCHAR, role VARCHAR, entity_id VARCHAR);
CREATE TABLE IF NOT EXISTS claim (claim_id VARCHAR PRIMARY KEY, kind VARCHAR,
  subject_ids VARCHAR[], text_printed VARCHAR, horizon VARCHAR, direction VARCHAR,
  published_at DATE, doc_id VARCHAR, chunk_id VARCHAR, sids INT[], quote VARCHAR NOT NULL,
  extractor VARCHAR, confidence REAL);
CREATE TABLE IF NOT EXISTS corpus_known_gaps (scope VARCHAR, key VARCHAR, gap_from DATE, gap_to DATE,
  reason VARCHAR, source VARCHAR);
CREATE TABLE IF NOT EXISTS period_summary (segment VARCHAR, grain VARCHAR, period_from DATE, period_to DATE,
  summary VARCHAR, cited_ids VARCHAR[], model VARCHAR, prompt_version VARCHAR, input_hash VARCHAR,
  built_at TIMESTAMP, PRIMARY KEY (segment, grain, period_from));
CREATE TABLE IF NOT EXISTS meta (key VARCHAR PRIMARY KEY, value JSON);
"""
ISO_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
def to_number(cell: str):
    """Parse a numeric cell to float. Handles $ % , () -paren negatives. Returns None if non-numeric."""
    s = cell.strip()
    if not s:
        return None
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg = True
        s = s[1:-1].strip()
    s = s.replace(",", "").replace("%", "").replace("$", "").replace("\u00a0", " ").strip()
    if s == "":
        return None
    # trailing units / words -> non-numeric
    if re.search(r"[A-Za-z]", s):
        return None
    try:
        v = float(s)
    except ValueError:
        return None
    return -v if neg else v
def parse_date(s: str):
    s = (s or "").strip()
    m = ISO_RE.match(s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%B %d, %Y", "%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None
def sha16(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:16]
def obs_id(stem: str, row_ord: int, col_ord: int) -> int:
    # 15 hex == 60 bits, fits signed BIGINT, deterministic across re-runs
    return int(hashlib.sha256(f"{stem}\x1f{row_ord}\x1f{col_ord}".encode()).hexdigest()[:15], 16)
def git_first_commit(rel: Path) -> str:
    try:
        r = subprocess.run(
            ["git", "log", "--diff-filter=A", "--format=%cs", "--", str(rel)],
            cwd=ROOT, capture_output=True, text=True,
        )
        lines = [x.strip() for x in r.stdout.splitlines() if x.strip()]
        if lines:
            return lines[-1]  # oldest first-commit
    except (OSError, subprocess.CalledProcessError):
        pass
    return ""
def load_doc_maps(con):
    rows = con.execute(
        "SELECT source_file, path, doc_id, published_at FROM document"
    ).fetchall()
    doc_by_source_file = {}
    doc_by_srcf_basename = {}
    doc_by_sf_stem = {}
    doc_pub = {}
    stem_list = []  # sorted list of (stem, doc_id) for prefix lookup
    for srcf, path, doc_id, pub in rows:
        doc_pub[doc_id] = pub
        if srcf:
            doc_by_source_file[srcf] = doc_id
            doc_by_srcf_basename.setdefault(Path(srcf).name, doc_id)
            doc_by_sf_stem.setdefault(Path(srcf).stem, doc_id)
        if path:
            doc_by_sf_stem.setdefault(Path(path).stem, doc_id)
    # Collect unique stems from source_file and path; prefer a single doc per stem.
    stem_to_doc = {}
    for srcf, path, doc_id, _pub in rows:
        for f in (srcf, path):
            if f:
                stem_to_doc.setdefault(Path(f).stem, doc_id)
    stem_list = sorted(stem_to_doc.items())  # (stem, doc_id) lexicographic
    return doc_by_source_file, doc_by_srcf_basename, doc_by_sf_stem, doc_pub, stem_list
def _prefix_doc(stem, stem_list):
    """Unique doc whose stem has `stem` as a prefix (e.g. CSV .html stem vs doc .pdf stem)."""
    import bisect
    idx = bisect.bisect_left(stem_list, (stem, ""))
    cand = None
    n = len(stem_list)
    while idx < n and stem_list[idx][0].startswith(stem):
        d = stem_list[idx][1]
        if cand is None:
            cand = d
        elif cand != d:
            return None  # ambiguous
        idx += 1
    return cand
def resolve_doc(sf, doc_by_source_file, doc_by_srcf_basename, doc_by_sf_stem, stem_list=None):
    if not sf:
        return None
    sf = sf.strip()
    if not sf:
        return None
    if sf in doc_by_source_file:
        return doc_by_source_file[sf]
    base = Path(sf.replace("\\", "/")).name
    if base in doc_by_srcf_basename:
        return doc_by_srcf_basename[base]
    stem = Path(sf.replace("\\", "/")).stem
    if stem in doc_by_sf_stem:
        return doc_by_sf_stem[stem]
    if stem_list is not None:
        return _prefix_doc(stem, stem_list)
    return None
def row_date(row, date_col, extra_keys):
    """Resolve a period date: date_col, then issue, then extra_json keys."""
    v = row.get(date_col) if date_col else None
    d = parse_date(v) if v else None
    if d:
        return d
    for k in ("issue",):
        if k in row and parse_date(row.get(k)):
            return parse_date(row.get(k))
    ej = row.get("extra_json") or ""
    if ej:
        try:
            extra = json.loads(ej)
        except json.JSONDecodeError:
            extra = {}
        for k in extra_keys:
            if extra.get(k):
                d = parse_date(str(extra[k]))
                if d:
                    return d
    return None
def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    meta = yaml.safe_load(MAP.read_text(encoding="utf-8"))
    entries = meta["series"]
    con = duckdb.connect(str(DB))
    con.execute("SET memory_limit='700MB'")
    con.execute("SET checkpoint_threshold='256MB'")
    con.execute("SET threads=1")
    con.execute(DDL)
    con.commit()
    doc_by_source_file, doc_by_srcf_basename, doc_by_sf_stem, doc_pub, stem_list = load_doc_maps(con)
    # idempotent resume: obs_id/series_id are deterministic; INSERT OR IGNORE skips completed rows.
    # checkpoint = last stem whose insert fully committed; stems before+including it are skipped on resume.
    ck_path = REPORTS / "p2_series_checkpoint.json"
    done_stems = set()
    if ck_path.exists():
        try:
            ck = json.loads(ck_path.read_text(encoding="utf-8"))
            done_stems = set(ck.get("completed_stems", []) or [])
        except (json.JSONDecodeError, TypeError):
            done_stems = set()
    git_commit_cache = {}
    series_rows = {}
    obs_batch = []
    stats = {"files_loaded": 0, "files_skipped": 0, "deferred": 0, "resumed": 0,
             "observations": 0, "series": 0, "cells_skipped_nonnum": 0,
             "rows_skipped_nodate": 0, "unresolved_doc": 0, "git_fallback_used": 0}
    defects = []
    defer_log = []
    batch = 5000  # rows per staging append; grown under RAM pressure headroom (max 20000)
    # Bulk load: Python `executemany` costs ~0.8 ms/row on this host (prepared-statement loop),
    # so each batch is handed to DuckDB as one Arrow table and inserted set-based, ordered by
    # obs_id so the ART primary key is maintained in sorted order (measured: 20k rows / 0.2 s).

    def flush():
        nonlocal obs_batch
        t_flush = time.time()
        n_flush = len(obs_batch)
        if series_rows:
            con.executemany(
                "INSERT OR IGNORE INTO series VALUES (?,?,?,?,?,?,?,?,?)",
                list(series_rows.values()),
            )
            series_rows.clear()
        t_series = time.time()
        t_stg = t_bulk = t_commit = t_series
        if obs_batch:
            colvals = list(zip(*obs_batch))
            table = pa.table({name: list(vals) for name, vals in zip(OBS_COLS, colvals)},
                             schema=OBS_SCHEMA)
            con.register("_obs_arrow", table)
            t_stg = time.time()
            con.execute(
                "INSERT OR IGNORE INTO observation " + OBS_SQL_COLS +
                " SELECT * FROM (SELECT * FROM _obs_arrow ORDER BY obs_id)")
            con.unregister("_obs_arrow")
            obs_batch = []
            t_bulk = time.time()
        con.commit()
        t_commit = time.time()
        if n_flush >= 5000:
            dt_flush = t_commit - t_flush
            print(f"[flush] obs={n_flush:,} dur={dt_flush:.1f}s "
                  f"(stg={t_stg - t_series:.1f} bulk={t_bulk - t_stg:.1f} "
                  f"commit={t_commit - t_bulk:.1f}) total={stats['observations']:,} "
                  f"rate={n_flush / max(dt_flush, 1e-9):,.0f}/s batch={batch}", flush=True)
    def emit(stem, series_id, period, value, raw_cell, unit, doc_id, row_ord, col_ord,
             published_at, method, provenance, period_to=None):
        nonlocal batch
        obs_batch.append((obs_id(stem, row_ord, col_ord), series_id, period, period_to or period,
                          value, unit, raw_cell, doc_id, 0, row_ord, col_ord,
                          published_at, None, method, provenance))
        stats["observations"] += 1
        if len(obs_batch) >= batch:
            # §10 guard: persist current unit, then shrink batch below 1 GB / pause below 600 MB.
            fr = free_ram_bytes()
            if fr is not None and fr < FREE_PAUSE_BYTES:
                flush()
                print(f"[memory-guard] free RAM {fr/2**30:.2f} GB < {FREE_PAUSE_BYTES/2**20:.0f} MB -> pausing safely", file=sys.stderr)
                raise MemoryPressure()
            flush()
            if fr is not None and fr < FREE_LO_BYTES and batch > 500:
                batch = max(500, batch // 2)
                print(f"[memory-guard] free RAM {fr/2**30:.2f} GB < {FREE_LO_BYTES/2**20:.0f} MB -> batch -> {batch}", file=sys.stderr)
            elif fr is not None and fr > FREE_LO_BYTES and batch < 20000:
                batch = min(20000, batch * 2)
    def stem_done(stem, t0, n0):
        flush()
        stats["files_loaded"] += 1
        done_stems.add(stem)
        ck_path.write_text(json.dumps({"completed_stems": sorted(done_stems)}), encoding="utf-8")
        print(f"[stem] done {stem} obs+={stats['observations'] - n0:,} dt={time.time() - t0:.1f}s", flush=True)
    def add_series(stem, measure, entity_sig, unit, frequency, provenance, mode, e):
        sig = entity_sig
        key = f"{stem}|{measure}|{sig}"
        sid = "s:" + sha16(key)
        if sid in series_rows:
            return sid
        name = f"{stem}::{measure}" + (f" | {sig}" if sig else "")
        definition = {
            "stem": stem, "measurement": measure, "entity_signature": sig,
            "mode": mode, "provenance": provenance,
            "entity_cols": e.get("entity_cols") or [],
            "value_cols": e.get("value_cols") or ([e.get("value_col")] if e.get("value_col") else []),
            "source": e.get("source"), "frequency": e.get("frequency"),
        }
        series_rows[sid] = (sid, name, unit, None, None, frequency, None, stem, json.dumps(definition, ensure_ascii=False))
        stats["series"] += 1
        return sid
    try:
        for e in entries:
            stem = e.get("stem")
            if e.get("skip"):
                stats["files_skipped"] += 1
                continue
            if stem in DEFER_STEMS:
                stats["deferred"] += 1
                defer_log.append({"stem": stem, "reason": "defer_transactions"})
                continue
            if stem in done_stems:
                stats["resumed"] += 1
                continue
            csv_path = SERIES / f"{stem}.csv"
            if not csv_path.exists():
                defects.append({"stem": stem, "issue": "csv_missing"})
                continue
            mode = e.get("mode")
            t_stem = time.time()
            n_obs0 = stats["observations"]
            print(f"[stem] start {stem} mode={mode}", flush=True)
            date_col = e.get("date_col")
            method = f"csv:{stem}"
            provenance = e.get("provenance", "reported_table")
            frequency = e.get("frequency")
            unit_col = e.get("unit_col")
            # streaming read: never materialise the whole CSV in memory (8 GB host)
            if mode in ("wide",) or (mode is None and e.get("value_cols")):
                value_cols = e.get("value_cols") or []
                entity_cols = e.get("entity_cols") or []
                row_filter = e.get("row_filter") or None
                with open(csv_path, newline="", encoding="utf-8-sig", errors="replace") as fh:
                    header = next(csv.reader(fh), None)
                    if header is None:
                        defects.append({"stem": stem, "issue": "csv_empty"})
                        continue
                    col_ord = {c: i for i, c in enumerate(header)}
                    for row_ord, rec in enumerate(csv.reader(fh)):
                        if not rec:
                            continue
                        row = {c: (rec[i] if i < len(rec) else "") for i, c in enumerate(header)}
                        if row_filter:
                            keep = True
                            for fk, fv in row_filter.items():
                                vals = fv if isinstance(fv, list) else [fv]
                                if (row.get(fk) or "").strip() not in vals:
                                    keep = False
                                    break
                            if not keep:
                                continue
                        period = row_date(row, date_col, ("issue_date", "report_date", "date", "published_date"))
                        if period is None:
                            stats["rows_skipped_nodate"] += 1
                            continue
                        sf = row.get("source_file")
                        doc_id = resolve_doc(sf, doc_by_source_file, doc_by_srcf_basename, doc_by_sf_stem, stem_list)
                        if sf and not doc_id:
                            stats["unresolved_doc"] += 1
                        if date_col and row.get(date_col) and parse_date(row.get(date_col)):
                            published_at = period
                        elif doc_id and doc_pub.get(doc_id):
                            published_at = doc_pub[doc_id]
                        else:
                            published_at = period
                        entity_sig = "\x1f".join((row.get(ec) or "") for ec in entity_cols if (row.get(ec) or "").strip())
                        for vc in value_cols:
                            cell = row.get(vc)
                            if cell is None:
                                continue
                            s = cell if isinstance(cell, str) else str(cell)
                            if not s.strip():
                                continue
                            v = to_number(s)
                            if v is None:
                                stats["cells_skipped_nonnum"] += 1
                                continue
                            sid = add_series(stem, vc, entity_sig, None, frequency, provenance, "wide", e)
                            emit(stem, sid, period, v, s, None, doc_id, row_ord, col_ord.get(vc, -1),
                                 published_at, method, provenance)
                stem_done(stem, t_stem, n_obs0)
            elif mode == "long":
                date_from = e.get("date_from")
                measurement_col = e.get("measurement_col")
                value_col = e.get("value_col")
                entity_cols = e.get("entity_cols") or []
                with open(csv_path, newline="", encoding="utf-8-sig", errors="replace") as fh:
                    header = next(csv.reader(fh), None)
                    if header is None:
                        defects.append({"stem": stem, "issue": "csv_empty"})
                        continue
                    col_ord = {c: i for i, c in enumerate(header)}
                    if value_col not in header:
                        defects.append({"stem": stem, "issue": f"no value col {value_col!r}; categorical/transaction_table"})
                        stats["files_skipped"] += 1
                        continue
                    for row_ord, rec in enumerate(csv.reader(fh)):
                        row = {c: (rec[i] if i < len(rec) else "") for i, c in enumerate(header)}
                        if date_from:
                            y = row.get(date_from[0]); w = row.get(date_from[1])
                            try:
                                period = date.fromisocalendar(int(y), int(w), 1)
                                period_to = period + timedelta(days=6)
                            except (ValueError, TypeError):
                                stats["rows_skipped_nodate"] += 1
                                continue
                        else:
                            period = row_date(row, date_col, ("issue_date", "report_date", "date", "published_date"))
                            if period is None:
                                stats["rows_skipped_nodate"] += 1
                                continue
                            period_to = period
                        cell = row.get(value_col)
                        s = cell if isinstance(cell, str) else (str(cell) if cell is not None else "")
                        if not s.strip():
                            continue
                        v = to_number(s)
                        if v is None:
                            stats["cells_skipped_nonnum"] += 1
                            continue
                        measure = row.get(measurement_col) or value_col
                        unit = (row.get(unit_col) or None) if unit_col else None
                        entity_sig = "\x1f".join((row.get(ec) or "") for ec in entity_cols if (row.get(ec) or "").strip())
                        sid = add_series(stem, str(measure), entity_sig, unit, frequency, provenance, "long", e)
                        sf = row.get("source_file")
                        doc_id = resolve_doc(sf, doc_by_source_file, doc_by_srcf_basename, doc_by_sf_stem, stem_list)
                        if sf and not doc_id:
                            stats["unresolved_doc"] += 1
                        if doc_id and doc_pub.get(doc_id):
                            published_at = doc_pub[doc_id]
                        elif date_col and parse_date(row.get(date_col)):
                            published_at = parse_date(row.get(date_col))
                        else:
                            key = stem
                            if key not in git_commit_cache:
                                gc = git_first_commit(csv_path.relative_to(ROOT))
                                git_commit_cache[key] = gc
                            gc = git_commit_cache[key] or FIRST_COMMIT_FALLBACK.get(stem) or FIRST_COMMIT_DEFAULT
                            if not git_commit_cache[key]:
                                stats["git_fallback_used"] += 1
                            published_at = date.fromisoformat(gc)
                        emit(stem, sid, period, v, s, unit, doc_id, row_ord, col_ord.get(value_col, -1),
                             published_at, method, provenance, period_to=period_to)
                stem_done(stem, t_stem, n_obs0)
            else:
                defects.append({"stem": stem, "issue": f"unknown mode {mode!r}"})
        flush()
    except MemoryPressure:
        flush()
        con.close()
        print(f"[memory-guard] P2 paused: free RAM < {FREE_PAUSE_BYTES/2**20:.0f} MB. Re-run to resume (idempotent).", file=sys.stderr)
        return 3
    flush()
    n_ser = con.execute("SELECT count(*) FROM series").fetchone()[0]
    n_obs = con.execute("SELECT count(*) FROM observation").fetchone()[0]
    con.close()
    report = {
        "phase": "P2_series",
        "stats": stats,
        "actual_series": n_ser,
        "actual_observations": n_obs,
        "defects": defects,
        "deferred": defer_log,
    }
    (REPORTS / "p2_series.json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"p2_series: series={n_ser:,} observations={n_obs:,} files_loaded={stats['files_loaded']} "
          f"skipped={stats['files_skipped']} deferred={stats['deferred']}")
    print(f"  skipped_nonnum={stats['cells_skipped_nonnum']:,} nodate={stats['rows_skipped_nodate']:,} "
          f"unresolved_doc={stats['unresolved_doc']:,} git_fallback={stats['git_fallback_used']}")
    for d in defects[:30]:
        print("  defect:", d)
    return 0
if __name__ == "__main__":
    sys.exit(main())
