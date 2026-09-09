#!/usr/bin/env python3
"""
IMF PortWatch Expanded Universe Collector (REAL DATA ONLY)
==========================================================
Expands the 43-port PortWatch slice to the FULL 2065-port universe served by the
public IMF PortWatch ArcGIS FeatureServices (no auth):

  root: https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services
  - PortWatch_ports_database/FeatureServer/0      (2065 ports, infrastructure facts)
  - PortWatch_chokepoints_database/FeatureServer/0 (28 chokepoints, same schema)
  - portwatch_disruptions_database/FeatureServer/0 (132+ disruption events)
  - Daily_Ports_Data/FeatureServer/0              (per-port daily rows, 2019-01-01 -> live)

Verified layer behavior (probes 2026-09-09, and earlier audited work):
- f=json / f=pjson, no auth; maxRecordCount = 1000 (page cap, regardless of
  requested resultRecordCount).
- ObjectId order is NOT date order: pagination may only key off
  exceededTransferLimit / empty batches (never off date monotonicity).
- 'date' on Daily_Ports_Data is a plain ISO string ('YYYY-MM-DD'); DATE
  'YYYY-MM-DD' is the required literal form in where clauses (plain quoted
  string compares silently return 0 rows on some layers).
- A whole-layer date window spans 1000+ ports/day and cannot be paged in one
  query (the 2020-10-30 stall documented in scripts/expansion_portwatch.py);
  queries are bounded per port-chunk and per calendar-year window instead.
- Per-port-chunk pages cost ~2s; a full-universe backfill is ~5.8M rows.

Payload-size decision (measured, not guessed):
- The full 2019->live daily universe is ~5.78M rows: ~726 MB raw CSV (125.5
  B/row measured on port_calls_daily.csv v1), far beyond GitHub's 100 MB/file
  hard limit, so NO single whole-history CSV is written or attempted.
- Measured compression on the same schema: snappy parquet 43.3 B/row, zstd
  30.1 B/row, gzip CSV 25.7 B/row.
- Therefore the daily-expanded output ships as:
    * data/congestion/port_calls_daily_expanded.csv  - HOT file: current year
      (Jan 1 -> live) for ALL ports in the six-class source schema
      (~1.25M rows/yr, ~155 MB raw -> ~24 MB gz committed; zstd parquet
      ~38 MB kept beside it), and
    * data/congestion/port_calls_daily_expanded_<YYYY>.csv.gz - one gzip CSV
      per PRIOR calendar year (2019-2025), 25-95 MB gz each, all committed.
  Nothing is pruned from the data layer: the full history remains in-repo,
  just sharded per year to stay under the 100 MB hard limit. Downstream
  reads concat the year shards + the hot file.
- --refresh only fetches dates AFTER the max date already stored in the hot
  file (incremental, DATE literal idiom from expansion_portwatch.py) and
  refreshes the master/universe/disruption pulls; CI-safe (~1-2 min).

NO synthetic columns, NO fabricated values anywhere: every output column is
verbatim source (dates converted epoch-ms -> ISO where the source uses epoch;
todate-null events get an explicit `ongoing` flag; affectedports kept raw).

Usage:
  python scripts/scrapers/fetch_portwatch_ports_expanded.py --backfill
  python scripts/scrapers/fetch_portwatch_ports_expanded.py --refresh
"""
from __future__ import annotations

import argparse
import gzip
import json
import logging
import random
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

ROOT = Path(__file__).resolve().parent.parent.parent
CONGESTION_DIR = ROOT / "data" / "congestion"
GEOSPATIAL_DIR = ROOT / "data" / "geospatial"

SERVICE_BASE = "https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services"
PORTS_DB_URL = f"{SERVICE_BASE}/PortWatch_ports_database/FeatureServer/0/query"
CHOKEPOINTS_DB_URL = f"{SERVICE_BASE}/PortWatch_chokepoints_database/FeatureServer/0/query"
DISRUPTIONS_URL = f"{SERVICE_BASE}/portwatch_disruptions_database/FeatureServer/0/query"
DAILY_URL = f"{SERVICE_BASE}/Daily_Ports_Data/FeatureServer/0/query"

PORTS_MASTER_OUT = GEOSPATIAL_DIR / "portwatch_ports_master.csv"
CHOKEPOINTS_OUT = CONGESTION_DIR / "chokepoints_master.csv"
DISRUPTIONS_OUT = CONGESTION_DIR / "portwatch_disruptions.csv"
DAILY_HOT_OUT = CONGESTION_DIR / "port_calls_daily_expanded.csv"
DAILY_HOT_PARQUET_OUT = CONGESTION_DIR / "port_calls_daily_expanded.parquet"
MANIFEST_OUT = CONGESTION_DIR / "portwatch_expanded_manifest.json"

PAGE_SIZE = int(__import__("os").environ.get("PW_PAGE_SIZE", "1000"))
PORT_CHUNK = 100          # portids per daily query (bounded page counts)
FETCH_WORKERS = int(__import__("os").environ.get("PW_WORKERS", "1"))
RETRIES = 5               # 400s / IncompleteRead cuts clear on later attempts
RETRY_BASE_SLEEP = 30     # throttle windows need long backoff: 30/60/120/240s
PAGE_SLEEP = float(__import__("os").environ.get("PW_PAGE_SLEEP", "4.0"))
CHUNK_COOLDOWN_S = 90.0   # cool down after a failed chunk before the next
SWEEP_PASSES = 2          # final retry sweeps for failed chunks, per year
TIMEOUT = 180
FIRST_DAY = "2019-01-01"  # full-history floor of Daily_Ports_Data
STABLE_ORDER = "date, ObjectId"

# Optional year filter for resumable backfill runs (argparse sets these).
BACKFILL_YEARS: list[str] = []
OVERWRITE = False

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
}

# Six-class source schema of Daily_Ports_Data (field order on the layer).
DAILY_SCHEMA = [
    "date", "year", "month", "day", "portid", "portname", "country", "ISO3",
    "portcalls_container", "portcalls_dry_bulk", "portcalls_general_cargo",
    "portcalls_roro", "portcalls_tanker", "portcalls_cargo", "portcalls",
    "import_container", "import_dry_bulk", "import_general_cargo",
    "import_roro", "import_tanker", "import_cargo", "import",
    "export_container", "export_dry_bulk", "export_general_cargo",
    "export_roro", "export_tanker", "export_cargo", "export", "ObjectId",
]


# --------------------------------------------------------------------------- #
# HTTP / pagination (idiom proven in scripts/expansion_portwatch.py)
# --------------------------------------------------------------------------- #
def _get_json(url: str, params: dict, retries: int = RETRIES) -> dict:
    last = None
    for attempt in range(1, retries + 1):
        try:
            # Connection: close on EVERY request - the layer's edge rejects
            # requests that ride keep-alive sockets opened earlier in the same
            # process (400 bursts survive all backoffs while the identical
            # query passes on a fresh socket; observed 2026-09-09 when the
            # session pool was poisoned after hours of 429s). Fresh-connection
            # per request costs a re-handshake per page - acceptable here.
            r = requests.get(url, params=dict(params, f="json"),
                             headers=dict(BROWSER_HEADERS, Connection="close"),
                             timeout=TIMEOUT)
            if r.status_code == 200:
                data = r.json()
                # ArcGIS error payloads (e.g. transient 400 "Unable to perform
                # query" under load) are retried like HTTP failures - params
                # here are always constructed by this module, and the same
                # page typically succeeds on a later attempt when the service
                # is degraded.
                if isinstance(data, dict) and "error" in data:
                    raise TransientQueryError(json.dumps(data["error"])[:300])
                return data
            last = RuntimeError(f"HTTP {r.status_code}")
            logging.warning("HTTP %s (attempt %d/%d)", r.status_code, attempt, retries)
        except (requests.RequestException, TransientQueryError) as e:  # noqa: BLE001
            last = e
            logging.warning("%s (attempt %d/%d)", str(e)[:160], attempt, retries)
        time.sleep(min(RETRY_BASE_SLEEP * 2 ** attempt, 240))  # 30/60/120/240s ladder
    raise QueryError(f"ArcGIS query failed after {retries} attempts: {last}")


class TransientQueryError(RuntimeError):
    """ArcGIS error payload that may clear on retry (service under load)."""


class QueryError(RuntimeError):
    """ArcGIS query failed for good after all retries."""


def query_layer(url: str, params: dict, page_size: int = PAGE_SIZE) -> list[dict]:
    """ObjectId-KEYSET paged ArcGIS query returning attribute dicts.

    The FeatureServer rejects deep resultOffset values on where-filtered
    queries (HTTP 400 "Unable to perform query" at offset ~23000), so any
    offset-walking pagination dies on large tables. Keyset pagination instead:
      where = <filter> AND ObjectId > :last_max, orderByFields=ObjectId ASC
    each page advances :last_max to the max(ObjectId) just returned - the
    server never sees a large offset, so it converges on tables of any size.
    ObjectId order != date order (documented), which is irrelevant here: keyset
    only needs monotonic ObjectIds; callers sort by date on write.

    Pagination ends on a page with < page_size features and honors
    exceededTransferLimit. Error payloads surface loudly; error 400s and
    IncompleteRead cuts are retried (service under load), with a jittered
    pause between pages.
    """
    params = dict(params)
    if params.get("orderByFields") == "date":
        params["orderByFields"] = "ObjectId"
    out: list[dict] = []
    last_max = 0
    while True:
        where = params.get("where") or "1=1"
        p = dict(params,
                 where=f"({where}) AND ObjectId > {int(last_max)}",
                 orderByFields="ObjectId",
                 resultRecordCount=page_size,
                 returnGeometry="false")
        # no resultOffset: keyset pages always start at ObjectId > last_max
        p.pop("resultOffset", None)
        data = _get_json(url, p)
        if "error" in (data or {}):
            raise QueryError(
                f"ArcGIS error payload: {json.dumps(data['error'])[:300]} "
                f"(where={p.get('where')!r})")
        feats = data.get("features") or []
        if not feats:
            break
        out.extend(f["attributes"] for f in feats if isinstance(f, dict) and "attributes" in f)
        page_max = max(int(f["attributes"]["ObjectId"]) for f in feats
                       if isinstance(f, dict) and f.get("attributes")
                       and f["attributes"].get("ObjectId") is not None)
        done = (len(feats) < page_size) or not data.get("exceededTransferLimit")
        last_max = page_max
        if done:
            break
        time.sleep(PAGE_SLEEP + random.uniform(0.0, 1.0))  # rate limit: server throttles bursts
    return out


# --------------------------------------------------------------------------- #
# Pure conversion helpers (unit-tested with real captured JSON)
# --------------------------------------------------------------------------- #
def epoch_ms_to_iso(v) -> str:
    """Epoch milliseconds -> 'YYYY-MM-DD' (source fromdate/todate fields)."""
    if v is None or v == "" or (isinstance(v, float) and pd.isna(v)):
        return ""
    if isinstance(v, str):
        return v[:10] if v else ""
    return datetime.fromtimestamp(int(v) / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d")


def normalize_daily_row(attrs: dict) -> dict:
    """One Daily_Ports_Data attribute dict -> flat row, date normalized.

    ISO strings are trimmed to their date part; epoch-ms ints are converted
    defensively (the field is documented ISO but old dumps carried epochs).
    """
    row = {k: attrs.get(k) for k in DAILY_SCHEMA if k in attrs}
    # preserve any extra source fields verbatim (append at end)
    for k, v in attrs.items():
        if k not in row and k != "Shape__Area" and k != "Shape__Length":
            row[k] = v
    d = row.get("date")
    if isinstance(d, (int, float)) and not isinstance(d, bool):
        row["date"] = datetime.utcfromtimestamp(d / 1000.0).strftime("%Y-%m-%d")
    elif isinstance(d, str):
        row["date"] = d[:10]
    return row


def disruptions_to_rows(attrs_list: list[dict]) -> list[dict]:
    """Disruption attribute dicts -> rows with epoch-ms -> ISO dates.

    todate null/empty (event still active) -> empty todate + ongoing=1.
    affectedports is kept RAW (semicolon-separated source string).
    """
    rows = []
    for a in attrs_list:
        r = dict(a)
        r["fromdate"] = epoch_ms_to_iso(r.get("fromdate"))
        todate_iso = epoch_ms_to_iso(r.get("todate"))
        r["todate"] = todate_iso
        r["ongoing"] = 1 if not todate_iso else 0
        rows.append(r)
    return rows


def chunked(seq: list, size: int) -> list[list]:
    return [seq[i:i + size] for i in range(0, len(seq), size)]


def date_where(portids: list[str], start: str, end: str) -> str:
    """Bounded where clause: portid IN (...) AND DATE-literal window."""
    ids = ",".join(f"'{p}'" for p in portids)
    return (f"portid IN ({ids}) AND date >= DATE '{start}' AND date <= DATE '{end}'")


def source_row_count(portids: list[str] | None, start: str, end: str) -> int:
    """Server-side count of source rows for a window (reconciliation only)."""
    if portids is None:
        where = f"date >= DATE '{start}' AND date <= DATE '{end}'"
    else:
        where = date_where(portids, start, end)
    data = _get_json(DAILY_URL, {"where": where, "returnCountOnly": "true"})
    n = data.get("count")
    return int(n) if n is not None else 0


def year_windows(start: str, end: str) -> list[tuple[str, str]]:
    """Split [start, end] into per-calendar-year windows (bounded queries)."""
    y0 = date.fromisoformat(start).year
    y1 = date.fromisoformat(end).year
    windows = []
    for y in range(y0, y1 + 1):
        w_start = max(start, f"{y}-01-01")
        w_end = min(end, f"{y}-12-31")
        if w_start <= w_end:
            windows.append((w_start, w_end))
    return windows


# --------------------------------------------------------------------------- #
# Master database pulls (full, verbatim)
# --------------------------------------------------------------------------- #
def fetch_ports_database() -> pd.DataFrame:
    logging.info("Fetching PortWatch_ports_database (full universe)...")
    attrs = query_layer(PORTS_DB_URL, {"where": "1=1", "outFields": "*",
                                       "orderByFields": "ObjectId"})
    df = pd.DataFrame(attrs)
    logging.info("  %d port rows", len(df))
    return df


def fetch_chokepoints_database() -> pd.DataFrame:
    logging.info("Fetching PortWatch_chokepoints_database...")
    attrs = query_layer(CHOKEPOINTS_DB_URL, {"where": "1=1", "outFields": "*",
                                             "orderByFields": "ObjectId"})
    df = pd.DataFrame(attrs)
    logging.info("  %d chokepoint rows", len(df))
    return df


def fetch_disruptions() -> pd.DataFrame:
    logging.info("Fetching portwatch_disruptions_database...")
    attrs = query_layer(DISRUPTIONS_URL, {"where": "1=1", "outFields": "*",
                                          "orderByFields": "ObjectId"})
    rows = disruptions_to_rows(attrs)
    df = pd.DataFrame(rows)
    logging.info("  %d disruption events (%d ongoing)",
                 len(df), int(pd.to_numeric(df.get("ongoing"), errors="coerce").fillna(0).sum()))
    return df


# --------------------------------------------------------------------------- #
# Daily expanded pulls (per-port-chunk x per-year-window)
# --------------------------------------------------------------------------- #
def fetch_daily_window(portids: list[str], start: str, end: str) -> list[dict]:
    """All Daily_Ports_Data rows for the given portids within [start, end].

    Port chunks are queried with a small bounded worker pool (4) - measured
    ~1.5s per 1000-row page, ~5.8k pages for the full universe backfill, so a
    serial pull would take ~3.5h; 4 workers keep it near ~36 min while staying
    polite to the public service. Results are re-merged in chunk order.
    """
    chunks = chunked(portids, PORT_CHUNK)
    n_chunks = len(chunks)
    attrs_by_idx: list[list[dict]] = [[] for _ in chunks]

    def _one(i: int) -> None:
        where = date_where(chunks[i], start, end)
        attrs_by_idx[i] = query_layer(DAILY_URL, {"where": where, "outFields": "*",
                                                  "orderByFields": "date"})
        logging.info("  chunk %d/%d %s..%s: %d rows", i + 1, n_chunks, start, end,
                     len(attrs_by_idx[i]))

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(_one, range(n_chunks)))
    return [a for chunk_attrs in attrs_by_idx for a in chunk_attrs]


def existing_daily_state() -> tuple[pd.DataFrame | None, str | None]:
    """Load the hot expanded file; return (df, max_date)."""
    if not DAILY_HOT_OUT.exists():
        return None, None
    df = pd.read_csv(DAILY_HOT_OUT, dtype={"portid": str, "ISO3": str, "date": str},
                     low_memory=False)
    if df.empty:
        return df, None
    return df, str(df["date"].max())


# --------------------------------------------------------------------------- #
# Writers
# --------------------------------------------------------------------------- #
def _write_csv_gz(df: pd.DataFrame, path: Path) -> int:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8", newline="", compresslevel=6) as fh:
        df.to_csv(fh, index=False)
    shutil.move(tmp, path)
    return path.stat().st_size


def write_daily_outputs(year_frames: dict[int, pd.DataFrame]) -> dict:
    """Write the hot CSV (+parquet) and per-prior-year gz shards.

    year_frames: {year: df} covering every fetched year; the current calendar
    year becomes the HOT file, prior years become <YYYY>.csv.gz shards.
    Returns sizes/rows for the manifest.
    """
    CONGESTION_DIR.mkdir(parents=True, exist_ok=True)
    this_year = date.today().year
    sizes: dict[str, dict] = {}
    cols = [c for c in DAILY_SCHEMA if c in
            (set().union(*[set(f.columns) for f in year_frames.values()]) if year_frames else set())]

    for year, df in sorted(year_frames.items()):
        df = df.reindex(columns=cols)
        df = df.sort_values(["date", "portid"], kind="stable").reset_index(drop=True)
        if year == this_year:
            df.to_csv(DAILY_HOT_OUT, index=False)
            sizes["port_calls_daily_expanded.csv"] = {
                "rows": int(len(df)), "bytes": DAILY_HOT_OUT.stat().st_size}
            df.to_parquet(DAILY_HOT_PARQUET_OUT, compression="zstd", index=False)
            sizes["port_calls_daily_expanded.parquet"] = {
                "rows": int(len(df)), "bytes": DAILY_HOT_PARQUET_OUT.stat().st_size}
        else:
            shard = CONGESTION_DIR / f"port_calls_daily_expanded_{year}.csv.gz"
            b = _write_csv_gz(df, shard)
            sizes[shard.name] = {"rows": int(len(df)), "bytes": b,
                                 "bytes_gz": b, "format": "csv.gz"}
    return sizes


def _append_rows_to_temp(rows: list[dict], temp_path: Path) -> int:
    """Append normalized daily rows to a per-year temp CSV (streaming backfill).

    Peak memory stays at one 100-port chunk (~12k rows) instead of holding the
    full year's attribute list in RAM. Temp files live in the gitignored tmp/.
    """
    import csv as _csv
    temp_path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not temp_path.exists()
    with open(temp_path, "a", encoding="utf-8", newline="") as fh:
        w = _csv.DictWriter(fh, fieldnames=DAILY_SCHEMA, extrasaction="ignore")
        if new_file:
            w.writeheader()
        w.writerows(rows)
    return len(rows)


def _finalize_year_from_temp(year: int, temp_path: Path) -> dict:
    """Sort + write one year from its temp CSV; remove the temp.

    The current calendar year becomes the hot file (CSV + zstd parquet);
    prior years become <YYYY>.csv.gz shards. Parquet is built in row chunks
    from the final CSV so peak memory stays far below the 2M-row year size.
    """
    import gc

    import pyarrow as pa
    import pyarrow.parquet as pq

    CONGESTION_DIR.mkdir(parents=True, exist_ok=True)
    dtype = {"portid": str, "ISO3": str, "date": str}
    df = pd.read_csv(temp_path, dtype=dtype, low_memory=False)
    df = df.reindex(columns=DAILY_SCHEMA)
    df = df.sort_values(["date", "portid"], kind="stable").reset_index(drop=True)
    rows = int(len(df))
    this_year = date.today().year
    out: dict = {}
    if year == this_year:
        df.to_csv(DAILY_HOT_OUT, index=False)
        del df
        gc.collect()
        writer = None
        for chunk in pd.read_csv(DAILY_HOT_OUT, dtype=dtype, chunksize=400_000,
                                 low_memory=False):
            chunk = chunk.reindex(columns=DAILY_SCHEMA)
            table = pa.Table.from_pandas(chunk, preserve_index=False)
            if writer is None:
                writer = pq.ParquetWriter(DAILY_HOT_PARQUET_OUT, table.schema,
                                          compression="zstd")
            writer.write_table(table)
            del chunk, table
        if writer is not None:
            writer.close()
        out["port_calls_daily_expanded.csv"] = {
            "rows": rows, "bytes": DAILY_HOT_OUT.stat().st_size}
        out["port_calls_daily_expanded.parquet"] = {
            "rows": rows, "bytes": DAILY_HOT_PARQUET_OUT.stat().st_size}
    else:
        shard = CONGESTION_DIR / f"port_calls_daily_expanded_{year}.csv.gz"
        b = _write_csv_gz(df, shard)
        out[shard.name] = {"rows": rows, "bytes": b, "bytes_gz": b, "format": "csv.gz"}
        del df
    temp_path.unlink(missing_ok=True)
    return out


# --------------------------------------------------------------------------- #
# Modes
# --------------------------------------------------------------------------- #
def _refresh_master_tables() -> dict:
    sizes = {}
    ports = fetch_ports_database()
    ports.to_csv(PORTS_MASTER_OUT, index=False)
    sizes["portwatch_ports_master.csv"] = {"rows": int(len(ports)),
                                           "bytes": PORTS_MASTER_OUT.stat().st_size}
    chokes = fetch_chokepoints_database()
    chokes.to_csv(CHOKEPOINTS_OUT, index=False)
    sizes["chokepoints_master.csv"] = {"rows": int(len(chokes)),
                                       "bytes": CHOKEPOINTS_OUT.stat().st_size}
    dis = fetch_disruptions()
    dis.to_csv(DISRUPTIONS_OUT, index=False)
    sizes["portwatch_disruptions.csv"] = {"rows": int(len(dis)),
                                          "bytes": DISRUPTIONS_OUT.stat().st_size}
    return sizes, ports


def _fetch_daily_rows(portids: list[str], windows: list[tuple[str, str]]) -> list[dict]:
    attrs: list[dict] = []
    for (start, end) in windows:
        logging.info("Daily window %s .. %s (%d ports)", start, end, len(portids))
        attrs.extend(fetch_daily_window(portids, start, end))
    return attrs


def backfill() -> dict:
    """Full pull: masters + disruptions + full daily history 2019-01-01 -> live.

    Streams one calendar year at a time; within a year, each completed port
    chunk is normalized and appended to a per-year temp CSV immediately, so
    peak memory stays at one chunk (~12k rows) rather than the full year
    (~2.1M rows x ~30 attrs). Each year is then finalized from its temp.

    Years are processed in REVERSE order (current year first): the hot file
    and recent history land before the deep archive, so an interrupted run
    still leaves the most valuable years committed. A year whose output file
    already exists is skipped unless --overwrite (resumable backfill).
    """
    sizes, ports = _refresh_master_tables()
    portids = [str(p) for p in ports["portid"].dropna().tolist()] or []
    if not portids:
        raise SystemExit("Universe pull returned no portids - aborting rather than writing synthetic data.")
    today = date.today().isoformat()
    windows = year_windows(FIRST_DAY, today)
    if BACKFILL_YEARS:
        want = {int(y) for y in BACKFILL_YEARS}
        windows = [w for w in windows if int(w[0][:4]) in want]
    total = 0
    min_date = None
    max_date = None
    port_set: set[str] = set()
    chunks = chunked(portids, PORT_CHUNK)
    # class-level failure records: per-chunk failures are recorded and the
    # backfill continues; a final sweep pass retries them before outputs are
    # written; anything still failing is recorded in the manifest (never
    # silently dropped).
    skipped: dict[str, str] = {}
    year_counts: dict[str, dict] = {}

    def _fetch_one_chunk(i: int, start: str, end: str, year: int) -> list[dict]:
        where = date_where(chunks[i], start, end)
        got = query_layer(DAILY_URL, {"where": where, "outFields": "*",
                                      "orderByFields": "date"})
        logging.info("  %d chunk %d: %d rows", year, i, len(got))
        return got

    def _year_loop(year: int, start: str, end: str, temp_path: Path) -> tuple[int, list[int]]:
        """Fetch all chunks (+ sweep passes) for one year; return (rows, failed)."""
        year_rows = 0
        done_chunks: set[int] = set()
        failed: set[int] = set()

        def attempt(i: int) -> None:
            nonlocal year_rows
            try:
                got = _fetch_one_chunk(i, start, end, year)
            except QueryError as e:
                failed.add(i)
                skipped[f"{year}:chunk{i}"] = str(e)[:200]
                logging.error("  %d chunk %d FAILED: %s", year, i, str(e)[:140])
                time.sleep(CHUNK_COOLDOWN_S)
                return
            failed.discard(i)
            done_chunks.add(i)
            rows = [normalize_daily_row(a) for a in got]
            year_rows += _append_rows_to_temp(rows, temp_path)
            del rows

        pending = list(range(len(chunks)))
        for pass_no in range(1 + SWEEP_PASSES):
            if not pending:
                break
            todo = pending if pass_no == 0 else sorted(failed)
            failed = set()
            for i in todo:
                attempt(i)
                time.sleep(0.5)
        return year_rows, sorted(failed)

    for (start, end) in sorted(windows, reverse=True):
        year = int(start[:4])
        this_year = date.today().year
        if year == this_year and DAILY_HOT_OUT.exists() and not OVERWRITE:
            logging.info("year %d: output exists, skipping (use --overwrite-years to redo)", year)
            continue
        shard = CONGESTION_DIR / f"port_calls_daily_expanded_{year}.csv.gz"
        if year != this_year and shard.exists() and not OVERWRITE:
            logging.info("year %d: shard exists, skipping (use --overwrite-years to redo)", year)
            continue
        temp_path = Path(ROOT) / "tmp" / f"_td_daily_{year}.csv"
        temp_path.unlink(missing_ok=True)  # fresh temp per (re)run
        year_rows, failed_chunks = _year_loop(year, start, end, temp_path)
        # reconcile against the source: every chunk's rows are accounted for
        src = source_row_count(portids=[p for c in failed_chunks
                                        for p in chunks[c]] if failed_chunks else None,
                               start=start, end=end)
        if failed_chunks:
            logging.warning("  %s: %d/%d chunks still FAILED after sweeps (recorded); "
                            "src-rows-in-failed-chunks=%d, fetched=%d",
                            f"{start}..{end}", len(failed_chunks), len(chunks),
                            src, year_rows)
        if year_rows == 0 and src == 0:
            logging.warning("  window %s..%s returned 0 rows", start, end)
            temp_path.unlink(missing_ok=True)
            continue
        if year_rows == 0 and not failed_chunks:
            logging.warning("  window %s..%s: 0 fetched but source says %d rows", start, end, src)
        sizes.update(_finalize_year_from_temp(year, temp_path))
        total += year_rows
        year_counts[str(year)] = {"fetched": year_rows, "source": None}
        min_date = min_date or start
        max_date = end if end < today else today
        time.sleep(2.0)
    # reconcile per-year source counts (bounded count queries) - best-effort:
    # a count failing after full backoff must not abort the run; the fetched
    # rows are already finalized per year, so the manifest records a null
    # source count instead of losing the whole year's work to a SystemExit.
    for (start, end) in windows:
        y = str(start[:4])
        if y in year_counts:
            try:
                year_counts[y]["source"] = source_row_count(portids=None, start=start, end=end)
            except Exception as e:  # noqa: BLE001
                logging.warning("  %s: source reconciliation count unavailable (%s)", y, str(e)[:140])
                year_counts[y]["source"] = None
    if total == 0:
        raise SystemExit("Daily pull returned 0 rows - aborting rather than writing synthetic data.")
    # distinct ports actually ingested, measured from the final hot file
    hot = pd.read_csv(DAILY_HOT_OUT, usecols=["portid", "date"], dtype=str)
    port_set.update(hot["portid"].astype(str).unique().tolist())
    max_date = str(hot["date"].max())
    result = {"sizes": sizes, "rows": total, "ports_ingested": len(port_set),
              "max_date": max_date, "min_date": min_date}
    if skipped or year_counts:
        result["skipped_chunks"] = skipped
        result["year_reconciliation"] = year_counts
    return result


def refresh() -> dict:
    """Incremental: refresh masters + disruptions; daily only where date > max stored.

    Falls back to backfill() when no hot file exists yet.
    """
    prev, max_date = existing_daily_state()
    if prev is None or max_date is None:
        logging.info("No existing hot file - running full backfill instead.")
        return backfill()

    sizes, ports = _refresh_master_tables()
    portids = [str(p) for p in ports["portid"].dropna().tolist()] or []
    if not portids:
        raise SystemExit("Universe pull returned no portids - aborting rather than writing synthetic data.")

    start = (date.fromisoformat(max_date) + timedelta(days=1)).isoformat()
    today = date.today().isoformat()
    if start > today:
        logging.info("Daily up-to-date (max stored %s); masters refreshed only.", max_date)
        return {"sizes": sizes, "rows": 0, "ports_ingested": int(prev["portid"].nunique()),
                "max_date": max_date, "mode": "refresh-noop"}

    attrs = _fetch_daily_rows(portids, year_windows(start, today))
    rows = [normalize_daily_row(a) for a in attrs]
    fresh = pd.DataFrame(rows)
    if not fresh.empty:
        fresh["date"] = fresh["date"].astype(str)
    added = 0 if fresh.empty else len(fresh)

    combined = pd.concat([prev, fresh], ignore_index=True) if not fresh.empty else prev
    combined = combined.drop_duplicates(subset=["date", "portid"], keep="last")
    this_year = date.today().year
    # Re-shard every year the refresh touched; on a calendar-year roll the
    # previous hot year's rows (already in `combined`) re-shard as their
    # prior-year csv.gz instead of being silently dropped from the outputs.
    touched = sorted({int(y) for y in combined["date"].str[:4]
                      if int(y) >= this_year or int(y) >= int(start[:4])})
    year_frames = {int(y): g for y, g in combined.groupby(combined["date"].str[:4])
                   if int(y) in touched}
    sizes.update(write_daily_outputs(year_frames))
    return {"sizes": sizes, "rows": int(added), "ports_ingested": int(combined["portid"].nunique()),
            "max_date": str(combined["date"].max()),
            "min_date": str(combined["date"].min()), "mode": "refresh"}


def main() -> int:
    ap = argparse.ArgumentParser(description="IMF PortWatch expanded universe collector.")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--backfill", action="store_true", help="full 2019->live pull (all 2065 ports)")
    mode.add_argument("--refresh", action="store_true", help="incremental: dates after max stored")
    ap.add_argument("--years", default="", help="comma-separated year filter for --backfill (resumable)")
    ap.add_argument("--overwrite-years", action="store_true",
                    help="refetch years whose output files already exist")
    args = ap.parse_args()

    if args.years:
        BACKFILL_YEARS[:] = [y.strip() for y in args.years.split(",") if y.strip()]
    if args.overwrite_years:
        global OVERWRITE
        OVERWRITE = True

    started = time.time()
    try:
        result = backfill() if args.backfill else refresh()
    except Exception as e:  # noqa: BLE001
        logging.error("[FAIL] %s", e)
        return 1

    result["mode"] = "backfill" if args.backfill else result.get("mode", "refresh")
    result["elapsed_s"] = round(time.time() - started, 1)
    result["generated_utc"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    manifest = {
        "source": "IMF PortWatch ArcGIS FeatureServices (public, no auth)",
        "root": SERVICE_BASE,
        "payload_decision": (
            "Full 2019->live daily universe ~5.8M rows ~726MB raw CSV exceeds GitHub "
            "100MB/file hard limit; ships as current-year hot CSV (+zstd parquet) plus "
            "per-prior-year csv.gz shards (measured 25.7 B/row gz). No data pruned."),
        **result,
    }
    MANIFEST_OUT.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    logging.info("[ok] manifest -> %s", MANIFEST_OUT)
    for name, s in sorted(result["sizes"].items()):
        logging.info("  %-42s %9d rows  %10.1f KB", name, s["rows"], s["bytes"] / 1024)
    logging.info("[ok] ports ingested: %d | daily rows this run: %d | max date: %s",
                 result["ports_ingested"], result["rows"], result["max_date"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
