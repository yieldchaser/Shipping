"""
daily_fearnleys_sync.py
Polite, incremental delta synchronization for Fearnleys Hasura GraphQL backend.
Designed for daily / scheduled automation (runs in <30 seconds without hammer).

Workflow:
  1. Fixtures: Delta pull using cursor id > max_existing_id (only newly added deals).
  2. Rates: Pulls only recent prints (last 30 days) across series and upserts into fearnpulse_rates_full.csv.
  3. S&P Transactions: Pages back until caught up and appends any unseen records.
  4. Broker Comments: Pages back from the newest comment until a whole page is
     already stored, and appends every unseen record.
  5. Custom Reports: Same paging for publications; saves markdown for each new issue
     and writes both catalogue copies (data/reports is the one the site reads).
  6. Rebuilds pre-aggregated cache: scripts/fearnleys/build_fearnleys_cache.py.
"""

import csv
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
import requests

# fetch_fearnleys_reports.py and build_fearnleys_cache.py live in scripts/ and
# scripts/fearnleys/; make both importable however this script is launched.
SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for _p in (SCRIPTS_DIR, os.path.dirname(os.path.abspath(__file__))):
    if _p not in sys.path:
        sys.path.insert(0, _p)

ENDPOINT = "https://pbrokerapp.hasura.app/v1/graphql"
HEADERS = {
    "Content-Type": "application/json",
    "Origin": "https://fearnpulse.com",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) FearnpulseDeltaSync/1.0",
}

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DERIVED_DIR = os.path.join(BASE_DIR, "data", "derived")
REPORTS_DIR = os.path.join(BASE_DIR, "reports", "fearnleys")
DATA_REPORTS_DIR = os.path.join(BASE_DIR, "data", "reports", "fearnleys")

FIXTURES_CSV = os.path.join(DERIVED_DIR, "fearnleys_fixtures_full.csv")
FIXTURES_PARQUET = os.path.join(DERIVED_DIR, "fearnleys_fixtures_full.parquet")
RATES_CSV = os.path.join(DERIVED_DIR, "fearnpulse_rates_full.csv")
SNP_CSV = os.path.join(DERIVED_DIR, "fearnleys_snp_transactions.csv")
COMMENTS_CSV = os.path.join(DERIVED_DIR, "fearnleys_broker_comments.csv")
# The site reads data/reports/; reports/ keeps the knowledge-base copy in step.
REPORTS_CATALOG = os.path.join(BASE_DIR, "data", "reports", "fearnleys_reports_catalog.json")
REPORTS_CATALOG_COPIES = [REPORTS_CATALOG, os.path.join(BASE_DIR, "reports", "fearnleys_reports_catalog.json")]
PAGE_SIZE = 50
MAX_PAGES = 40


def post_graphql_with_retry(payload, max_retries=3, timeout=30):
    for attempt in range(max_retries):
        try:
            resp = requests.post(ENDPOINT, json=payload, headers=HEADERS, timeout=timeout)
            if resp.status_code in (429, 500, 502, 503, 504):
                time.sleep(2.0 * (attempt + 1))
                continue
            resp.raise_for_status()
            data = resp.json()
            if "errors" in data:
                print(f"    [WARN] GraphQL error: {data['errors']}", flush=True)
                return None
            return data.get("data")
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"    [ERROR] Request failed: {e}", flush=True)
                return None
            time.sleep(2.0 * (attempt + 1))
    return None


# -----------------------------------------------------------------------------
# 1. FIXTURES DELTA SYNC
# -----------------------------------------------------------------------------
FIXTURE_QUERY = """
query GetNewFixtures($lastId: bigint!, $batchSize: Int!) {
  fixture(
    limit: $batchSize
    where: {id: {_gt: $lastId}}
    order_by: {id: asc}
  ) {
    id
    date
    charterer
    owner
    vessel
    imo
    rate
    period
    route
    segment
    department
    commodity
    load_port
    discharge_port
    laycan
    comment
  }
}
"""

FIXTURE_FIELDS = [
    "id", "date", "charterer", "owner", "vessel", "imo", "rate", "period",
    "route", "segment", "department", "commodity", "load_port", "discharge_port",
    "laycan", "comment"
]


def sync_fixtures():
    print(">>> [1/5] Synchronizing Commercial Fixtures (Cursor Delta)...", flush=True)
    if not os.path.exists(FIXTURES_CSV):
        print("    [WARN] Base fixtures CSV not found, skipping delta sync.")
        return 0

    max_id = 0
    with open(FIXTURES_CSV, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for r in reader:
            try:
                rid = int(r.get("id", 0))
                if rid > max_id:
                    max_id = rid
            except Exception:
                continue

    print(f"    Current highest fixture ID: {max_id}", flush=True)
    # Cursor pages of 500 until caught up; a single page left any backlog above 500 behind.
    new_fixtures, cursor = [], max_id
    for _ in range(200):
        payload = {
            "operationName": "GetNewFixtures",
            "query": FIXTURE_QUERY,
            "variables": {"lastId": cursor, "batchSize": 500},
        }
        data = post_graphql_with_retry(payload)
        if not data or "fixture" not in data:
            raise RuntimeError("No response from fixtures endpoint.")
        batch = data["fixture"]
        new_fixtures.extend(batch)
        if len(batch) < 500:
            break
        cursor = max(int(r["id"]) for r in batch)
        time.sleep(1.0)

    if not new_fixtures:
        print("    Fixtures database is fully up to date (0 new fixtures).", flush=True)
        return 0

    print(f"    Found {len(new_fixtures)} new fixtures. Appending...", flush=True)
    with open(FIXTURES_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIXTURE_FIELDS, lineterminator="\n")
        for r in new_fixtures:
            clean_row = {}
            for col in FIXTURE_FIELDS:
                val = r.get(col)
                if val is None:
                    clean_row[col] = ""
                elif isinstance(val, str):
                    clean_row[col] = val.replace("\r\n", " ").replace("\n", " ")
                else:
                    clean_row[col] = str(val)
            # Date sanity check: reject any future dates more than 30 days ahead (e.g. 2026-12-18 typo)
            f_date = clean_row.get("date", "")
            max_future = (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%Y-%m-%d")
            if f_date and f_date > max_future:
                print(f"    [WARN] Future fixture date rejected ({f_date} > {max_future}) for id {clean_row.get('id')}", flush=True)
                continue
            writer.writerow(clean_row)

    # Regenerate Parquet if pandas is available
    try:
        import pandas as pd
        df = pd.read_csv(FIXTURES_CSV, low_memory=False)
        df.to_parquet(FIXTURES_PARQUET, index=False, compression="snappy")
        print("    Regenerated fearnleys_fixtures_full.parquet.", flush=True)
    except Exception as e:
        print(f"    (Parquet update skipped: {e})", flush=True)

    return len(new_fixtures)


# -----------------------------------------------------------------------------
# 2. RATES RECENT DELTA SYNC
# -----------------------------------------------------------------------------
RATES_DELTA_QUERY = """
query GetRecentRates($dateFrom: date!) {
  rate_meta {
    info {
      rate_type
      rate_subtype
      route
    }
    rate_unit
    rates(where: {date: {_gte: $dateFrom}}, order_by: {date: desc}) {
      date
      rate
    }
  }
}
"""


def sync_rates():
    print("\n>>> [2/5] Synchronizing Recent Freight & Asset Benchmarks (30-day window)...", flush=True)
    date_from = (datetime.now(timezone.utc) - timedelta(days=35)).strftime("%Y-%m-%d")
    payload = {
        "operationName": "GetRecentRates",
        "query": RATES_DELTA_QUERY,
        "variables": {"dateFrom": date_from},
    }
    data = post_graphql_with_retry(payload, timeout=45)
    if not data or "rate_meta" not in data:
        raise RuntimeError("Failed to fetch recent rates.")

    rate_metas = data["rate_meta"]
    new_rows = []
    for m in rate_metas:
        info = m.get("info") or {}
        rt = info.get("rate_type")
        rst = info.get("rate_subtype")
        route = info.get("route")
        unit = m.get("rate_unit") or "usd"
        if not (rt and rst and route):
            continue

        label = f"{re.sub(r'[^a-zA-Z0-9]+', '_', rt).strip('_').upper()}_{re.sub(r'[^a-zA-Z0-9]+', '_', rst).strip('_').upper()}_{re.sub(r'[^a-zA-Z0-9]+', '_', route).strip('_').upper()}"
        for r in m.get("rates", []):
            new_rows.append({
                "label": label,
                "rate_type": rt,
                "rate_subtype": rst,
                "route": route,
                "unit": unit,
                "date": r["date"],
                "rate": r["rate"],
            })

    print(f"    Received {len(new_rows)} recent rate observations.", flush=True)
    if not new_rows or not os.path.exists(RATES_CSV):
        return 0

    import pandas as pd
    df_existing = pd.read_csv(RATES_CSV, low_memory=False)
    df_new = pd.DataFrame(new_rows)

    # Concat, drop duplicates on [rate_type, rate_subtype, route, unit, date] keeping latest
    combined = pd.concat([df_existing, df_new], ignore_index=True)
    before_len = len(df_existing)
    combined = combined.drop_duplicates(subset=["rate_type", "rate_subtype", "route", "unit", "date"], keep="last")
    combined.sort_values(by=["rate_type", "rate_subtype", "route", "date"], inplace=True)
    after_len = len(combined)

    added = after_len - before_len
    print(f"    Appended {added} new rate observations (total now {after_len}).", flush=True)
    combined.to_csv(RATES_CSV, index=False, lineterminator="\n")
    return added


# -----------------------------------------------------------------------------
# 3. S&P DEALS SYNC
# -----------------------------------------------------------------------------
SNP_QUERY = """
query GetRecentSnp($limit: Int!, $offset: Int!) {
  snp_transaction(limit: $limit, offset: $offset, order_by: [{created_at: desc}, {id: desc}]) {
    id
    created_at
    vessel
    built
    yard
    dwt
    segment
    price
    buyer
    comment
  }
}
"""


def sync_snp():
    print("\n>>> [3/5] Synchronizing S&P Transactions Ledger...", flush=True)
    if not os.path.exists(SNP_CSV):
        raise RuntimeError(f"missing {SNP_CSV}")

    # Collect existing IDs
    existing_ids = set()
    with open(SNP_CSV, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for r in reader:
            existing_ids.add(str(r.get("id")))

    unseen = fetch_unseen("GetRecentSnp", SNP_QUERY, "snp_transaction", existing_ids)
    if not unseen:
        print("    S&P transactions are up to date (0 new deals).", flush=True)
        return 0

    print(f"    Found {len(unseen)} new S&P deals. Appending...", flush=True)
    fields = ["id", "created_at", "vessel", "built", "yard", "dwt", "segment", "price", "buyer", "comment"]
    with open(SNP_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        for d in reversed(unseen):
            clean_d = {k: d.get(k, "") for k in fields}
            writer.writerow(clean_d)
    return len(unseen)


# -----------------------------------------------------------------------------
# 4. BROKER COMMENTS SYNC
# -----------------------------------------------------------------------------
COMMENTS_QUERY = """
query GetRecentComments($limit: Int!, $offset: Int!) {
  comment(limit: $limit, offset: $offset, order_by: [{date: desc}, {id: desc}]) {
    id
    date
    text
    created_at
    comment_meta_id
    metadata {
      comment_type
      comment_subtype
      comment_name
    }
  }
}
"""


def fetch_unseen(operation, query, key, existing_ids):
    """Page newest-first until a full page holds nothing new. Raises if the API fails."""
    unseen, seen_new = [], set()
    for page in range(MAX_PAGES):
        payload = {"operationName": operation, "query": query,
                   "variables": {"limit": PAGE_SIZE, "offset": page * PAGE_SIZE}}
        data = post_graphql_with_retry(payload)
        if not data or key not in data:
            raise RuntimeError(f"{operation}: Hasura returned no '{key}' data (page {page})")
        rows = data[key]
        fresh = [r for r in rows if str(r.get("id")) not in existing_ids and str(r.get("id")) not in seen_new]
        seen_new.update(str(r.get("id")) for r in fresh)
        unseen.extend(fresh)
        if len(rows) < PAGE_SIZE or not fresh:
            break
        time.sleep(1.0)
    return unseen


def sync_comments():
    print("\n>>> [4/5] Synchronizing Broker Commentary Feed...", flush=True)
    if not os.path.exists(COMMENTS_CSV):
        raise RuntimeError(f"missing {COMMENTS_CSV}")

    existing_ids = set()
    with open(COMMENTS_CSV, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for r in reader:
            existing_ids.add(str(r.get("id")))

    # Newest first, as the single 50-row page used to arrive; appended in reverse below.
    unseen = fetch_unseen("GetRecentComments", COMMENTS_QUERY, "comment", existing_ids)
    if not unseen:
        print("    Broker comments are up to date (0 new notes).", flush=True)
        return 0

    print(f"    Found {len(unseen)} new broker comments. Appending...", flush=True)
    fields = ["id", "date", "comment_type", "comment_subtype", "comment_name", "text", "created_at", "comment_meta_id"]
    with open(COMMENTS_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        for c in reversed(unseen):
            meta = c.pop("metadata", None) or {}
            c["comment_type"] = meta.get("comment_type", "")
            c["comment_subtype"] = meta.get("comment_subtype", "")
            c["comment_name"] = meta.get("comment_name", "")
            if isinstance(c.get("text"), str):
                c["text"] = c["text"].replace("\r\n", " ").replace("\n", " ")
            writer.writerow({k: c.get(k, "") for k in fields})
    return len(unseen)


# -----------------------------------------------------------------------------
# 5. RESEARCH REPORTS CHECK
# -----------------------------------------------------------------------------
REPORTS_QUERY = """
query GetRecentReports($limit: Int!, $offset: Int!) {
  custom_report(limit: $limit, offset: $offset, order_by: [{date: desc}, {created_at: desc}]) {
    id
    date
    title
    department
    slug
    status
    pdf_url
    audio_url
    content
    created_at
    updated_at
  }
}
"""


def sync_reports():
    print("\n>>> [5/5] Checking for New Fearnleys Weekly Reports...", flush=True)
    if not os.path.exists(REPORTS_CATALOG):
        raise RuntimeError(f"missing {REPORTS_CATALOG}")

    with open(REPORTS_CATALOG, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    existing_ids = {str(r.get("id")) for r in catalog}
    unseen = fetch_unseen("GetRecentReports", REPORTS_QUERY, "custom_report", existing_ids)

    if not unseen:
        print("    Reports catalog is up to date (0 new publications).", flush=True)
        return 0

    print(f"    Found {len(unseen)} new publications! Updating catalog and generating markdown...", flush=True)
    from fetch_fearnleys_reports import blocks_to_markdown, slugify

    for r in unseen:
        catalog.append(r)
        rep_date = r.get("date") or "undated"
        rep_slug = r.get("slug") or slugify(r.get("title") or r.get("id"))
        filename = f"{rep_date}_{rep_slug}.md"
        md_content = blocks_to_markdown(r)
        year_str = str(rep_date[:4]) if len(rep_date) >= 4 and rep_date[:4].isdigit() else "other"
        year_reports_dir = os.path.join(REPORTS_DIR, year_str)
        os.makedirs(year_reports_dir, exist_ok=True)
        with open(os.path.join(year_reports_dir, filename), "w", encoding="utf-8", newline="\n") as mf:
            mf.write(md_content)
        os.makedirs(DATA_REPORTS_DIR, exist_ok=True)
        with open(os.path.join(DATA_REPORTS_DIR, filename), "w", encoding="utf-8", newline="\n") as mf:
            mf.write(md_content)

    catalog.sort(key=lambda r: (r.get("date") or "", r.get("created_at") or ""), reverse=True)
    for path in REPORTS_CATALOG_COPIES:
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(catalog, f, indent=2, ensure_ascii=False)

    return len(unseen)


def main():
    print("================================================================", flush=True)
    print("  FEARNLEYS HASURA POLITE DAILY INCREMENTAL SYNCHRONIZER        ", flush=True)
    print("================================================================\n", flush=True)

    t0 = time.time()
    failures = []

    def guarded(name, fn):
        # One failing feed must not stop the others, or the cache rebuild, from running.
        # Failures are listed at the end and the script exits non-zero.
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            failures.append(f"{name}: {exc}")
            return 0

    n_fix = guarded("fixtures", sync_fixtures)
    n_rates = guarded("rates", sync_rates)
    n_snp = guarded("snp", sync_snp)
    n_comm = guarded("comments", sync_comments)
    n_rep = guarded("reports", sync_reports)

    # Rebuild all pre-aggregated frontend caches & tapes
    print("\n================================================================", flush=True)
    print("  REBUILDING FEARNLEYS PRE-AGGREGATED FRONTEND CACHES & TAPES   ", flush=True)
    print("================================================================", flush=True)
    def rebuild_cache():
        import build_fearnleys_cache
        build_fearnleys_cache.main()
    guarded("summary cache", rebuild_cache)

    def rebuild_fixtures_tape():
        import build_fixtures_tape
        build_fixtures_tape.main()
    guarded("fixtures tape", rebuild_fixtures_tape)

    def rebuild_desk_caches():
        import build_desk_caches
        build_desk_caches.main()
    guarded("desk caches", rebuild_desk_caches)

    def rebuild_comment_chunks():
        import build_comment_chunks
        build_comment_chunks.main()
    guarded("comment chunks", rebuild_comment_chunks)

    def rebuild_gas_rate_csvs():
        import build_gas_rate_csvs
        build_gas_rate_csvs.main(do_verify=False)
    guarded("gas rate csvs", rebuild_gas_rate_csvs)

    def rebuild_series_cache():
        import build_series_cache
        build_series_cache.main()
    guarded("series monthly cache", rebuild_series_cache)

    elapsed = time.time() - t0
    print(f"Daily Sync Complete in {elapsed:.1f}s.")
    print(f"Deltas -> Fixtures: +{n_fix} | Rates: +{n_rates} | S&P: +{n_snp} | Comments: +{n_comm} | Reports: +{n_rep}")
    print("================================================================\n", flush=True)
    if failures:
        print("FAILED STEPS:\n  " + "\n  ".join(failures), flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
