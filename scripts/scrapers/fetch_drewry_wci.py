"""
Standalone Drewry World Container Index (WCI) Tracker Scraper.
Extracts the composite index and route-by-route spot assessments from
Drewry's public WCI pages, maintains a clean time-series CSV, and saves
the weekly narrative snapshot as Markdown.

Only uses requests, beautifulsoup4 and pandas (per implementation plan).
"""

import io
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = REPO_ROOT / "data" / "indices"
REPORTS_DIR = REPO_ROOT / "reports" / "drewry"
CHECKPOINT_FILE = REPO_ROOT / "data" / "derived" / "drewry_checkpoint.json"

WCI_PAGE_URLS = [
    "https://www.drewry.co.uk/supply-chain-advisors/supply-chain-expertise/world-container-index-assessed-by-drewry",
    "https://www.drewry.co.uk/trackers-and-indices/latest-trackers-and-indices",
]
RED_SEA_URL = "https://www.drewry.co.uk/red-sea-freight-tracker"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

CSV_COLUMNS = [
    "date",
    "composite_index",
    "shanghai_rotterdam",
    "shanghai_genoa",
    "shanghai_la",
    "shanghai_ny",
    "rotterdam_shanghai",
]

# Route label variants seen across Drewry pages/articles -> CSV column
ROUTE_PATTERNS = [
    (r"shanghai\s*[-\u2013\u2014to]+\s*rotterdam", "shanghai_rotterdam"),
    (r"shanghai\s*[-\u2013\u2014to]+\s*genoa", "shanghai_genoa"),
    (r"shanghai\s*[-\u2013\u2014to]+\s*los\s*angeles", "shanghai_la"),
    (r"shanghai\s*[-\u2013\u2014to]+\s*new\s*york", "shanghai_ny"),
    (r"rotterdam\s*[-\u2013\u2014to]+\s*shanghai", "rotterdam_shanghai"),
]
COMPOSITE_PAT = re.compile(
    r"(?:world\s*container\s*index|wci|composite\s*index)[^.]{0,120}?"
    r"\$\s*([\d,]+(?:\.\d+)?)\s*(?:per|/)?\s*(?:40\s*(?:ft|foot)|40')",
    re.I,
)
ROUTE_VALUE_PAT = re.compile(
    r"([a-z][a-z\s]*?)\s*[-\u2013\u2014to]+\s*([a-z][a-z\s]*?)\D{0,60}?"
    r"\$\s*([\d,]+(?:\.\d+)?)",
    re.I,
)


def load_checkpoint():
    if CHECKPOINT_FILE.exists():
        try:
            return json.loads(CHECKPOINT_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_checkpoint(cp):
    CHECKPOINT_FILE.parent.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_FILE.write_text(json.dumps(cp, indent=2), encoding="utf-8", newline="\n")


def get_with_backoff(url, attempts=3):
    delay = 2.0
    last_exc = None
    for _ in range(attempts):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            if resp.status_code == 200:
                return resp
            if resp.status_code in (429, 503):
                time.sleep(delay)
                delay *= 2
                continue
            print(f"    [!] HTTP {resp.status_code} for {url}")
            return None
        except Exception as exc:
            last_exc = exc
            time.sleep(delay)
            delay *= 2
    if last_exc:
        print(f"    [!] Failed {url}: {last_exc}")
    return None


def clean_number(raw):
    try:
        return float(re.sub(r"[^0-9.]", "", raw))
    except Exception:
        return None


def extract_assessments(html_text):
    """Pull composite + route values from tables and free text."""
    soup = BeautifulSoup(html_text, "html.parser")
    flat_text = soup.get_text(" \n", strip=True)

    values = {}

    m = COMPOSITE_PAT.search(flat_text)
    if m:
        val = clean_number(m.group(1))
        if val:
            values["composite_index"] = val

    value_rx = re.compile(r"\$\s*([\d,]+(?:\.\d+)?)")
    # A LEVEL is introduced by "to" ("...to $4,453"), but this publisher also
    # writes "to reach $11,173" and "held steady at $7,904": the absolute CHANGE
    # ("increased 17% or $1,331 to $9,158") is nearer the label and would be a
    # 10x-class error, so an introduced value outranks a nearer one that is not.
    to_rx = re.compile(r"\b(?:to|at|reach)\s*$", re.I)
    # "increased 17% or $1,331" - the CHANGE, never the level.
    or_rx = re.compile(r"\bor\s*$", re.I)
    sent_rx = re.compile(r"(?<=[.!?])\s+")
    # Clause boundaries. MEASURED on 231 archived pages (scratch/wci/census_shapes.py):
    # 75 multi-lane sentences are one-clause-per-lane ("A dropped 8% or $999 to
    # reach $11,173 and B fell 5% or $739 to $15,110"), where distance alone
    # crosses the boundary.
    split_rx = re.compile(
        r"(?:;\s*|,\s*|\s+)(?:and|but|while|whereas|however|conversely|also|"
        r"similarly|likewise|furthermore|moreover|followed\s+by|"
        r"on\s+the\s+other\s+hand)\b|;\s*|\n", re.I)
    # ANY route named in a sentence, tracked or not: a "respectively" list can
    # name a lane we do not keep, and dropping it shifts every ordinal in it.
    label_rx = re.compile(
        r"\b([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?)\s*(?:to|[\u2013\u2014])\s*"
        r"([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?)")
    # The publisher's own port vocabulary, DERIVED from ROUTE_PATTERNS (never
    # hardcoded). A match whose every word is not a port name is prose
    # ("According to Drewry"), not a lane, and must not consume an ordinal.
    PORT_WORDS = set()
    for _pat, _col in ROUTE_PATTERNS:
        PORT_WORDS.update(re.findall(r"[a-z]{2,}", _pat))
    max_dist = 120

    def is_route_mention(seg):
        words = re.findall(r"[A-Za-z]+", seg)
        return bool(words) and all(w.lower() in PORT_WORDS for w in words)

    def label_col(seg):
        for pat, col in ROUTE_PATTERNS:
            if re.search(pat, seg, re.I):
                return col
        return None

    def sentences(text):
        """[(sentence, offset_into_text)] - the delimiter stays on its left."""
        out, pos = [], 0
        for part in sent_rx.split(text):
            idx = text.find(part, pos)
            if idx < 0:
                idx = pos
            out.append((part, idx))
            pos = idx + len(part)
        return out

    def clauses(sent):
        """[(start, end)] runs of one sentence between clause conjunctions."""
        out, pos = [], 0
        for m in split_rx.finditer(sent):
            out.append((pos, m.start()))
            pos = m.end()
        out.append((pos, len(sent)))
        return out

    def gap(le, ls, c):
        """Chars between a label and a value."""
        if c[0] >= le:
            return c[0] - le
        if c[1] <= ls:
            return ls - c[1]
        return 0

    def assign_route_values(text, pairs):
        """Give each route the value its OWN sentence and clause give it.

        Three measured defects drove this shape; all three were on pages whose
        whole assessment is ONE text line, so none is a line-splitting problem.

        (a) SENTENCE SCOPE. 2024-04-18: "...Shanghai to New York decreased 5%
            or $257 to $4,453 ... Shanghai to Los Angeles dropped 4% or $147 to
            $3,487 ... rates on Shanghai to Rotterdam and Shanghai to Genoa
            declined 2% to $2,989 and $3,577 per feu respectively. Conversely,
            rates from Rotterdam to New York increased by 3% or $67 to $2,291."
            Pairing k-th label with k-th value across the paragraph gave Genoa
            the $2,291 that belongs to Rotterdam-New York.
        (b) ORDINAL OVER UNTRACKED LANES. 2024-04-25: "...from Rotterdam to New
            York and Shanghai to Los Angeles decreased 3% to $2,214 and $3,395
            respectively." Rotterdam-New York is not a column we keep, so
            pairing only TRACKED labels gave Los Angeles the $2,214.
        (c) CLAUSE SCOPE. 2026-07-30: "spot rates declined 6% to $5,630 per 40ft
            container from Shanghai to Genoa and decreased 3% to $4,677 per 40ft
            container on Shanghai to Rotterdam." Genoa's own level is the
            $5,630 of its clause; the $4,677 of the NEXT clause sits closer.
        """
        for sent, off in sentences(text):
            local = []
            for col, ls, le in pairs:
                if ls < off or le > off + len(sent):
                    continue
                local.append((col, ls - off, le - off))
            if not local:
                continue
            cands = [(mo.start(), mo.end(), clean_number(mo.group(1)))
                     for mo in value_rx.finditer(sent)]
            cands = [c for c in cands if c[2] is not None]
            if not cands:
                continue
            low = sent.lower()
            all_labels = [(m.start(), m.end(), label_col(sent[m.start():m.end()]))
                          for m in label_rx.finditer(sent)
                          if is_route_mention(m.group(0))]
            to_vals = [c for c in cands
                       if to_rx.search(sent[max(0, c[0] - 8):c[0]])]
            parallel = (len(all_labels) >= 2
                        and max(l[1] for l in all_labels) <= cands[0][0])
            if len(all_labels) >= 2 and ('respectively' in low or parallel):
                free = [c for c in cands
                        if not or_rx.search(sent[max(0, c[0] - 8):c[0]])]
                vals = (to_vals if len(to_vals) == len(all_labels)
                        else free if len(free) == len(all_labels)
                        else cands if len(cands) == len(all_labels) else None)
                if vals:
                    for (_ls, _le, col), (_vs, _ve, val) in zip(all_labels, vals):
                        if col and col not in values:
                            values[col] = val
                    continue
            cls = clauses(sent)
            for ci, (a, b) in enumerate(cls):
                cl_lab = [(ls, le, col) for col, ls, le in local
                          if ls >= a and le <= b]
                cl_val = [c for c in cands if a <= c[0] < b]
                if not cl_lab or not cl_val:
                    continue
                if len(cl_lab) == 1:
                    ls, le, col = cl_lab[0]
                    lev = [c for c in cl_val
                           if to_rx.search(sent[max(0, c[0] - 8):c[0]])]
                    if not lev and ci + 1 < len(cls):
                        # "...diminished 3% or $16 and stood at $500": the
                        # clause carries only the CHANGE, and the level is the
                        # value of the next lane-less clause.
                        na, nb = cls[ci + 1]
                        if not [1 for _c, l2, l3 in local
                                if l2 >= na and l3 <= nb]:
                            lev = [c for c in cands if na <= c[0] < nb
                                   and to_rx.search(sent[max(0, c[0] - 8):c[0]])]
                    pool = lev or cl_val
                    pick = min(pool, key=lambda c: gap(le, ls, c))
                    if col not in values:
                        values[col] = pick[2]
                elif len(cl_lab) == len(cl_val):
                    for (ls, le, col), (_vs, _ve, val) in zip(
                            sorted(cl_lab, key=lambda t: t[0]),
                            sorted(cl_val, key=lambda c: c[0])):
                        if col not in values:
                            values[col] = val
            scored = []
            for col, ls, le in local:
                if col in values:
                    continue
                for vs, ve, val in cands:
                    dist = gap(le, ls, (vs, ve, val))
                    if dist <= max_dist:
                        pref = 1 if to_rx.search(sent[max(0, vs - 8):vs]) else 0
                        scored.append((-pref, dist, col, vs, val))
            scored.sort(key=lambda t: (t[0], t[1], t[2], t[3]))
            used_cols, used_vals = set(), set()
            for _pref, dist, col, vs, val in scored:
                if col in used_cols or vs in used_vals:
                    continue
                used_cols.add(col)
                used_vals.add(vs)
                if col not in values:
                    values[col] = val
    # Rendered tables first (label cell next to the value cell)
    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])]
            row_text = " | ".join(cells)
            pairs = []
            for pat, col in ROUTE_PATTERNS:
                if col in values:
                    continue
                rm = re.search(pat, row_text, re.I)
                if rm:
                    pairs.append((col, rm.start(), rm.end()))
            if pairs:
                assign_route_values(row_text, pairs)

    # Free-text fallback for routes the tables did not carry. EVERY mention of a
    # route in the page is a candidate, scored inside its own sentence; a mention
    # that carries no number ("...and New York to Rotterdam remained stable")
    # therefore cannot block a later mention that does.
    if len(values) < len(CSV_COLUMNS):
        for sent, _off in sentences(flat_text):
            pairs = []
            for pat, col in ROUTE_PATTERNS:
                if col in values:
                    continue
                rm = re.search(pat, sent, re.I)
                if rm:
                    pairs.append((col, rm.start(), rm.end()))
            if pairs:
                assign_route_values(sent, pairs)

    # As-of date on the page
    page_date = None
    dm = re.search(
        r"assessment\s+for[^0-9]{0,40}?\b(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})\b",
        flat_text,
        re.I,
    ) or re.search(
        r"(?:as\s*of|published|assessment\s*date|dated)[:\s]*([A-Za-z]+ \d{1,2},? \d{4})",
        flat_text,
        re.I,
    ) or re.search(r"\b(\d{1,2}\s+[A-Za-z]+\s+\d{4})\b", flat_text)
    if dm:
        for fmt in ("%B %d, %Y", "%B %d %Y", "%d %B %Y", "%d %b %Y"):
            try:
                page_date = datetime.strptime(dm.group(1).replace(",", ""), fmt.replace(",", "")).strftime("%Y-%m-%d")
                break
            except ValueError:
                continue
    if not page_date:
        page_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    return values, page_date, flat_text


WAYBACK_CDX_URL = "https://web.archive.org/cdx/search/cdx"
# WCI pages to look up in the Wayback CDX index (2011 -> present).
WCI_WAYBACK_URL_PATTERNS = [
    "drewry.co.uk/supply-chain-advisors/supply-chain-expertise/world-container-index-assessed-by-drewry*",
    "drewry.co.uk/*world-container-index*",
    "drewry.co.uk/*container-index*",
]

# Build F: synthetic baseline removed. This stub is kept only for backward
# compatibility with older imports; it NEVER synthesizes values.
def generate_canonical_wci_history():
    print("    [!] generate_canonical_wci_history() is deprecated (Build F): no values synthesized.")
    return pd.DataFrame(columns=CSV_COLUMNS)


def fetch_wayback_cdx(url_pattern, from_year=2011, limit=200):
    """Query the Wayback CDX API for snapshot list. Returns list of dicts.

    Fail-soft: per-request timeout 30s, max 3 attempts with backoff.
    Returns [] on persistent archive.org errors (e.g. GitHub Actions IP
    throttling) so the caller can commit partial results instead of wedging.
    """
    params = {
        "url": url_pattern,
        "from": str(from_year),
        "output": "json",
        "filter": ["statuscode:200", "mimetype:text/html"],
        "fl": "timestamp,original,statuscode,digest",
        "collapse": "digest",
        "limit": str(limit),
    }
    delay = 2.0
    for attempt in range(1, 4):
        try:
            resp = requests.get(WAYBACK_CDX_URL, params=params, headers=HEADERS, timeout=30)
            if resp.status_code == 200:
                try:
                    data = resp.json()
                except Exception as exc:
                    print(f"    [!] CDX JSON decode failed for {url_pattern}: {exc}")
                    return []
                if not data or len(data) < 2:
                    return []
                header, rows = data[0], data[1:]
                return [dict(zip(header, r)) for r in rows]
            if resp.status_code in (429, 503):
                print(f"    [!] CDX HTTP {resp.status_code} for {url_pattern} (attempt {attempt}/3)")
            else:
                print(f"    [!] CDX HTTP {resp.status_code} for {url_pattern}")
                return []
        except Exception as exc:
            print(f"    [!] CDX query failed for {url_pattern} (attempt {attempt}/3): {exc}")
        if attempt < 3:
            time.sleep(delay)
            delay *= 2
    return []


def backfill_drewry_wayback(from_year=2011, limit_per_pattern=200, max_snapshots=50, sleep_s=0.5,
                            deadline_s=540, max_consec_fail=10):
    """Backfill assessed WCI history via the Wayback Machine CDX API.

    - Covers drewry.co.uk WCI pages from from_year -> present.
    - Bounds work: newest max_snapshots only (default 50), per-request
      timeout 30s via get_with_backoff(), max 3 attempts with backoff,
      overall deadline_s budget + consecutive-failure circuit breaker so
      archive.org throttling (ConnectTimeout / Connection refused on
      GitHub Actions IPs) fails soft instead of wedging the job.
    - Parses each snapshot with extract_assessments(); only real assessed
      values are kept. Missing weeks are left absent (frontend renders gaps
      with spanGaps:true); values are NEVER invented.
    - Upserts into data/indices/drewry_wci_historical.csv with dedup + sort,
      preserving the canonical header (date, composite_index, ...).
    - Idempotent: re-running yields the same sorted, deduped CSV.
    - Fail-soft: returns partial (csv_path, n) on timeout/circuit-break;
      never raises on Wayback errors.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = DATA_DIR / "drewry_wci_historical.csv"
    t_start = time.monotonic()

    snapshots = []
    seen_ts = set()
    for pat in WCI_WAYBACK_URL_PATTERNS:
        print(f"[+] CDX query: {pat} (from {from_year}, limit {limit_per_pattern})")
        rows = fetch_wayback_cdx(pat, from_year=from_year, limit=limit_per_pattern)
        print(f"    found {len(rows)} snapshots")
        for r in rows:
            key = (r.get("timestamp"), r.get("digest") or r.get("original"))
            if key in seen_ts:
                continue
            seen_ts.add(key)
            snapshots.append(r)
    snapshots.sort(key=lambda r: r.get("timestamp", ""))
    if len(snapshots) > max_snapshots:
        # Keep newest snapshots: bounds runtime and prefers recent assessed
        # prints over deep-history (e.g. flaky 2022 snapshots).
        snapshots = snapshots[-max_snapshots:]
        print(f"    capped to newest {len(snapshots)} snapshots")

    collected = []
    consec_fail = 0
    for idx, snap in enumerate(snapshots, 1):
        if time.monotonic() - t_start > deadline_s:
            print(f"    [!] Wayback deadline ({deadline_s}s) reached at {idx}/{len(snapshots)}; "
                  f"keeping partial {len(collected)} rows (fail-soft).")
            break
        ts = snap.get("timestamp", "")
        orig = snap.get("original", "")
        wb_url = f"https://web.archive.org/web/{ts}id_/{orig}"
        try:
            resp = get_with_backoff(wb_url, attempts=3)
            if not resp:
                consec_fail += 1
                if consec_fail >= max_consec_fail:
                    print(f"    [!] {consec_fail} consecutive Wayback failures; archive.org likely "
                          f"throttling this IP. Aborting with partial {len(collected)} rows (fail-soft).")
                    break
                continue
            values, page_date, _ = extract_assessments(resp.text)
            if not values.get("composite_index") and len(values) < 2:
                consec_fail += 1
                if consec_fail >= max_consec_fail:
                    print(f"    [!] {consec_fail} consecutive unparseable snapshots; aborting "
                          f"with partial {len(collected)} rows (fail-soft).")
                    break
                continue
            consec_fail = 0
            row = {col: values.get(col) for col in CSV_COLUMNS}
            # Prefer the assessed page date; fall back to snapshot date.
            if page_date:
                row["date"] = page_date
            else:
                try:
                    row["date"] = datetime.strptime(ts[:8], "%Y%m%d").strftime("%Y-%m-%d")
                except Exception:
                    continue
            collected.append(row)
        except Exception as exc:
            print(f"    [!] snapshot parse failed {wb_url}: {exc}")
            consec_fail += 1
            if consec_fail >= max_consec_fail:
                print(f"    [!] circuit-breaker tripped; keeping partial {len(collected)} rows.")
                break
            continue
        finally:
            if sleep_s:
                time.sleep(sleep_s)

    print(f"[+] Wayback: parsed {len(collected)} assessed snapshots")
    if not collected:
        print("[!] No assessed WCI values recovered from Wayback; CSV left unchanged.")
        return csv_path, 0

    new_df = pd.DataFrame(collected)
    csv_path = upsert_wci_rows(new_df)
    return csv_path, len(collected)


def upsert_wci_rows(new_df):
    """Idempotent upsert: merge new rows, dedup by date (last wins), sort, keep header."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = DATA_DIR / "drewry_wci_historical.csv"
    if csv_path.exists():
        try:
            existing = pd.read_csv(csv_path)
        except Exception:
            existing = pd.DataFrame(columns=CSV_COLUMNS)
    else:
        existing = pd.DataFrame(columns=CSV_COLUMNS)
    combined = pd.concat([existing, new_df], ignore_index=True) if len(new_df) else existing
    # Keep only canonical columns (extra keys dropped), preserve header order.
    for col in CSV_COLUMNS:
        if col not in combined.columns:
            combined[col] = None
    combined = combined[CSV_COLUMNS]
    combined["date"] = pd.to_datetime(combined["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    combined = combined.dropna(subset=["date"]).drop_duplicates(subset="date", keep="last").sort_values("date")
    combined.to_csv(csv_path, index=False, lineterminator="\n")
    return csv_path


def update_csv(row=None, extra_df=None):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = DATA_DIR / "drewry_wci_historical.csv"
    if csv_path.exists():
        try:
            df = pd.read_csv(csv_path)
        except Exception:
            df = pd.DataFrame(columns=CSV_COLUMNS)
    else:
        df = pd.DataFrame(columns=CSV_COLUMNS)

    frames = [df]
    if row and row.get("date"):
        frames.append(pd.DataFrame([row]))
    if extra_df is not None and len(extra_df):
        frames.append(extra_df)
    if len(frames) > 1:
        df = pd.concat(frames, ignore_index=True)

    return upsert_wci_rows(df) if len(df) else upsert_wci_rows(pd.DataFrame(columns=CSV_COLUMNS))


def _parse_backfill_args(argv):
    """Parse optional backfill bounds. Defaults keep weekly runs bounded."""
    from_year, limit_per_pattern, max_snapshots = 2011, 200, 50
    for i, a in enumerate(argv):
        try:
            if a == "--from-year" and i + 1 < len(argv):
                from_year = int(argv[i + 1])
            elif a == "--limit-per-pattern" and i + 1 < len(argv):
                limit_per_pattern = max(1, int(argv[i + 1]))
            elif a == "--max-snapshots" and i + 1 < len(argv):
                max_snapshots = max(1, int(argv[i + 1]))
        except ValueError:
            continue
    return from_year, limit_per_pattern, max_snapshots


def main():
    print("=" * 80)
    print("  DREWRY WORLD CONTAINER INDEX INGESTION")
    print("=" * 80)

    if "--backfill" in sys.argv:
        from_year, limit_per_pattern, max_snapshots = _parse_backfill_args(sys.argv)
        print(f"\n[+] Wayback backfill requested (--backfill): {from_year} -> present, "
              f"newest {max_snapshots} (limit {limit_per_pattern}/pattern), no synthesis.")
        try:
            csv_path, n = backfill_drewry_wayback(
                from_year=from_year, limit_per_pattern=limit_per_pattern,
                max_snapshots=max_snapshots)
        except Exception as exc:
            print(f"    [!] Wayback backfill failed (fail-soft): {exc}")
            csv_path = upsert_wci_rows(pd.DataFrame(columns=CSV_COLUMNS))
            n = 0
        print(f"\n[OK] Wayback backfill complete: {n} assessed snapshots -> {csv_path.relative_to(REPO_ROOT)}")
        return 0

    checkpoint = load_checkpoint()
    primary = None
    narrative = ""
    for url in WCI_PAGE_URLS:
        print(f"\n[+] Fetching {url}")
        resp = get_with_backoff(url)
        if not resp:
            continue
        values, page_date, flat_text = extract_assessments(resp.text)
        print(f"    parsed values: {values} (page date: {page_date})")
        if values.get("composite_index") or len(values) >= 2:
            primary = {"url": url, "values": values, "date": page_date}
            narrative = "\n".join(
                line.strip() for line in flat_text.splitlines()
                if re.search(r"wci|container index|\$[\d,]+|red sea", line, re.I) and len(line.strip()) > 25
            )[:6000]
            break

    if not primary:
        print("\n[!] Live WCI page JS-rendered or offline; attempting limited Wayback backfill (no synthesis).")
        print("    Missing weeks are left as gaps (frontend spanGaps:true); no values invented.")
        try:
            # Fail-soft fallback: bounded (newest 50) so a blocked archive.org
            # never wedges the weekly job; partial results are committed.
            csv_path, n = backfill_drewry_wayback(
                limit_per_pattern=200, max_snapshots=50, sleep_s=0.5)
            print(f"\n[OK] Time-series backfilled: {csv_path.relative_to(REPO_ROOT)} ({n} assessed snapshots)")
        except Exception as exc:
            print(f"    [!] Wayback backfill failed: {exc}; ensuring header-only CSV exists.")
            csv_path = upsert_wci_rows(pd.DataFrame(columns=CSV_COLUMNS))
            print(f"\n[OK] Time-series preserved: {csv_path.relative_to(REPO_ROOT)}")
        return 0

    row = {col: primary["values"].get(col) for col in CSV_COLUMNS}
    row["date"] = primary["date"]
    csv_path = update_csv(row)
    print(f"\n[OK] Time-series updated: {csv_path.relative_to(REPO_ROOT)}")

    year_dir = REPORTS_DIR / primary["date"][:4]
    year_dir.mkdir(parents=True, exist_ok=True)
    md_path = year_dir / f"{primary['date']}_drewry_wci.md"
    md_content = f"""---
title: "Drewry World Container Index Snapshot - {primary['date']}"
date: "{primary['date']}"
source: "drewry"
category: "containers"
source_url: "{primary['url']}"
---

# Drewry World Container Index Snapshot - {primary['date']}

## Assessed Values ($/40ft)

| Metric | Value |
| --- | --- |
""" + "\n".join(
        f"| {col} | {primary['values'].get(col, '')} |" for col in CSV_COLUMNS[1:] if col != "date"
    ) + f"""

## Page Commentary

{narrative}
"""
    md_path.write_text(md_content, encoding="utf-8", errors="ignore", newline="\n")
    print(f"[OK] Narrative saved: {md_path.relative_to(REPO_ROOT)}")

    checkpoint["last_success_date"] = primary["date"]
    checkpoint["last_values"] = primary["values"]
    save_checkpoint(checkpoint)

    # Red Sea tracker narrative (best effort, never fatal)
    resp = get_with_backoff(RED_SEA_URL)
    if resp:
        rs_soup = BeautifulSoup(resp.text, "html.parser")
        rs_text = rs_soup.get_text("\n", strip=True)
        rs_lines = [
            line.strip() for line in rs_text.splitlines()
            if re.search(r"suez|transit|cape of good hope|diversion|red sea", line, re.I) and len(line.strip()) > 30
        ][:60]
        if rs_lines:
            rs_path = year_dir / f"{primary['date']}_drewry_red_sea_tracker.md"
            rs_path.write_text(
                f"""---
title: "Drewry Red Sea Freight Tracker Notes - {primary['date']}"
date: "{primary['date']}"
source: "drewry"
category: "containers"
source_url: "{RED_SEA_URL}"
---

# Drewry Red Sea Freight Tracker Notes - {primary['date']}

""" + "\n\n".join(rs_lines),
                encoding="utf-8",
                errors="ignore", newline="\n"
            )
            print(f"[OK] Red Sea notes saved: {rs_path.relative_to(REPO_ROOT)}")

    print("\n[DONE] Drewry ingestion complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
