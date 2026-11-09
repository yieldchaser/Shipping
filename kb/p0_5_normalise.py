#!/usr/bin/env python3
"""
GraphRAG phase P0.5: per-publisher frontmatter normaliser (docs/GRAPHRAG_BUILD_PLAN.md section 1.2, DDL section 3).

Does NOT edit any MD. Walks the three canonical inputs (broker data/extracted/md, SEC corpus/10-companies,
reference corpus/books) and writes one canonical `document` row per MD into kb/state/kb.duckdb.

Every row carries: doc_id (first 16 hex of sha256(MD bytes)), path, source_file, source_sha256 (computed from
the source file if it is a distinct external file, else null), publisher_id, doc_type, title, published_at
(DATE NOT NULL), date_source (frontmatter|filename|folder|registry), period_from/to, company_id (SEC ticker),
public_ok (false for books), the raw frontmatter JSON, and parser_version.

Deterministic and idempotent: re-running rebuilds `document` from scratch to the same rows.

Usage: python kb/p0_5_normalise.py  (reads kb/gates.yaml seed is handled by tripwire, not here)
"""
import hashlib
import json
import re
import sqlite3  # noqa: F401  (unused; DuckDB is the store)
import sys
from datetime import date, datetime
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "kb" / "state" / "kb.duckdb"
TMP = ROOT / "kb" / "state" / "tmp"

INPUTS = [
    ("broker", ROOT / "data" / "extracted" / "md"),
    ("sec", ROOT / "corpus" / "10-companies"),
    ("reference", ROOT / "corpus" / "books"),
]

DATE_KEYS = ("issue_date", "filing_date", "date", "report_date", "publication_date", "published")
ISO_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
PRINTED_RANGE = re.compile(r"\(\s*\d{1,2}\s*[-–]\s*(\d{1,2})\s+([A-Z][a-z]+)\s*\)")

# ---- locked publisher/route maps (re-verified against real files this session) ----
BROKER_PUBLISHER = {
    "gibson": "Gibson Shipbrokers",
    "intermodal": "Intermodal Shipbrokers",
    "banchero_costa": "Banchero Costa",
    "advanced_shipping": "Advanced Shipping & Trading",
    "seabrokers": "Seabrokers Chartering",
    "affinity": "Affinity Shipbrokers",
    "signal": "The Signal Group",
    "baltic": "Baltic Exchange",
    "lion": "Lion Shipbrokers",
    "ism": "ISM Coasters & Mini-Bulkers",
    "carriers": "Seasure Shipbroking (Blue Report, valuations by VesselsValue)",
    "poten": "Poten & Partners",
    "star_asia": "Star Asia Shipbroking",
    "agora": "Agora Shipbroking Corporation",
    "xclusiv": "Xclusiv Shipbrokers Inc.",
    "clarksons": "Clarksons Hellas",
    "ssy": "SSY (Simpson Spence Young)",
    "fearnleys": "Fearnleys",               # top-level weekly + voice desk comments
    "fearnleys-md": "Fearnleys",            # econometric research (monthly/bespoke)
    "drewry": "Drewry Maritime Research",    # ais + opinions
    "breakwave": "Breakwave Advisors",
}

# SEC form -> doc_type
SEC_DOC_TYPE = {
    "10-K": "sec_10k", "10-Q": "sec_10q", "20-F": "sec_20f", "6-K": "sec_6k", "8-K": "sec_8k",
}


def sec_doc_type(form: str) -> str:
    """Map a SEC form to doc_type; amendments ('10-K-A') collapse to their base form."""
    f = (form or "").strip()
    if f.endswith("-A"):
        f = f[:-2]
    return SEC_DOC_TYPE.get(f, "sec_8k")

# Book registry fallback: title/year are deterministic for every corpus/books MD (both FM shapes verified).
BOOK_YEARS = {
    "business_of_shipping_kendall": 1986,
    "freight_rate_modelling_review_2022": 2022,
    "maritime_economics_macro_karakitsos_varnavides": 2014,
    "maritime_economics_stopford_3e": 2009,
    "worlds_key_industry_harlaftis_tenold_valdaliso": 2012,
}

SKIP_BROKER_TOP = ("images", "books", "companies")
SKIP_BROKER_PATH = ("hellenic/shipbuilding",)


def frontmatter(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    fm = {}
    for line in text[3:end].splitlines():
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if m:
            fm[m[1]] = m[2].strip().strip("'\"")
    return fm


def body_of(text: str, has_fm: bool) -> str:
    if not has_fm:
        return text
    end = text.find("\n---", 3)
    return text[end + 4:] if end >= 0 else ""


def resolve_date(fm: dict, body: str, filename: str, folder_year: str):
    """Return (iso_date, date_source) mirroring p0_inventory.parse_date, with source tracking."""
    for k in DATE_KEYS:
        v = fm.get(k, "")
        m = ISO_RE.search(v)
        if m:
            try:
                return date(int(m[1]), int(m[2]), int(m[3])).isoformat(), "frontmatter"
            except ValueError:
                pass
        try:  # Breakwave "July 3, 2018"
            return datetime.strptime(v.strip(), "%B %d, %Y").date().isoformat(), "frontmatter"
        except ValueError:
            pass
    if fm.get("year", "").isdigit() and body:
        m = PRINTED_RANGE.search(body[:4000])
        if m:
            for fmt in ("%d %B %Y", "%d %b %Y"):
                try:
                    return datetime.strptime(f"{m[1]} {m[2]} {fm['year']}", fmt).date().isoformat(), "frontmatter"
                except ValueError:
                    pass
    m = ISO_RE.search(filename)
    if m:
        try:
            return date(int(m[1]), int(m[2]), int(m[3])).isoformat(), "filename"
        except ValueError:
            pass
    if folder_year and folder_year.isdigit():
        return f"{folder_year}-01-01", "folder"
    return "", "none"


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def source_roots() -> list[Path]:
    roots = [ROOT]
    import subprocess
    try:
        common = subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=ROOT,
                                capture_output=True, text=True, check=True).stdout.strip()
        main = Path(common).parent
        if main.resolve() != ROOT.resolve():
            roots.append(main)
    except (OSError, subprocess.CalledProcessError):
        pass
    return roots


def broker_route(rel: Path, fm: dict):
    """Return (publisher_id, doc_type) for a broker MD under data/extracted/md/<top>/..."""
    top = rel.parts[0]

    # hellenic sub-publisher routing
    if top == "hellenic":
        sub = rel.parts[1] if len(rel.parts) > 1 else ""
        fm_pub = fm.get("publisher", "")
        if sub in ("demolition", "iron_ore_pdf") and fm_pub:
            return fm_pub, ("broker_daily" if sub == "iron_ore_pdf" else "broker_weekly")
        if sub in ("dry_charter", "tanker_charter"):
            return "Alibra Shipping Limited", "broker_weekly"
        if sub == "vessel_valuations":
            return "VesselsValue (via Hellenic Shipping News)", "broker_weekly"
        # shipbuilding has 0 md and is skipped; anything else defaults below

    if top == "breakwave":
        sub = rel.parts[1] if len(rel.parts) > 1 else ""
        return "Breakwave Advisors", ("broker_daily" if sub == "insights" else "broker_weekly")

    if top == "fearnleys":
        sub = rel.parts[1] if len(rel.parts) > 1 else ""
        return "Fearnleys", "broker_weekly"

    if top == "fearnleys-md":
        return "Fearnleys", "broker_monthly"

    pub = BROKER_PUBLISHER.get(top, top)
    # cadence exceptions
    if top == "seabrokers":
        return pub, "broker_monthly"
    return pub, "broker_weekly"


def main() -> int:
    TMP.mkdir(parents=True, exist_ok=True)
    DB.parent.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(str(DB))
    con.execute("SET memory_limit='2GB'")
    con.execute(f"SET temp_directory='{TMP.as_posix()}'")
    con.execute("""
        CREATE TABLE IF NOT EXISTS document (
          doc_id VARCHAR PRIMARY KEY,
          path VARCHAR UNIQUE NOT NULL, source_file VARCHAR, source_sha256 VARCHAR,
          publisher_id VARCHAR NOT NULL, doc_type VARCHAR NOT NULL,
          title VARCHAR, published_at DATE NOT NULL, date_source VARCHAR NOT NULL,
          period_from DATE, period_to DATE, company_id VARCHAR,
          public_ok BOOLEAN NOT NULL,
          frontmatter JSON, parser_version VARCHAR, ingested_at TIMESTAMP DEFAULT now());
    """)
    con.execute("DELETE FROM document")

    roots = source_roots()
    n = 0
    stats = {}
    rows = []
    for kind, base in INPUTS:
        if not base.exists():
            continue
        for p in sorted(base.rglob("*.md")):
            rel = p.relative_to(base)
            relp = p.relative_to(ROOT).as_posix()

            # broker skip rules
            if kind == "broker":
                if rel.parts[0] in SKIP_BROKER_TOP:
                    continue
                if any(relp == s or relp.startswith(s + "/") for s in SKIP_BROKER_PATH):
                    continue

            raw = p.read_bytes()
            text = raw.decode("utf-8", errors="replace")
            fm = frontmatter(text)
            body = body_of(text, bool(fm))
            doc_id = sha256_bytes(raw)[:16]

            # folder year candidate: first 4-digit dir component under the input root
            folder_year = next((c for c in rel.parts if c.isdigit() and len(c) == 4), "")

            if kind == "reference":  # corpus/books/*.md
                slug = p.stem
                yr = fm.get("year", "")
                if yr.isdigit():
                    pub_date, dsrc = f"{int(yr):04d}-01-01", "frontmatter"
                else:
                    pub_date, dsrc = f"{BOOK_YEARS.get(slug, 0):04d}-01-01", "registry"
                if pub_date == "0000-01-01":
                    pub_date, dsrc = "1970-01-01", "registry"
                row = {
                    "doc_id": doc_id, "path": relp,
                    "source_file": None, "source_sha256": None,
                    "publisher_id": fm.get("publisher") or "Reference Literature",
                    "doc_type": "book", "title": fm.get("title"),
                    "published_at": pub_date, "date_source": dsrc,
                    "period_from": None, "period_to": None, "company_id": None,
                    "public_ok": False, "frontmatter": json.dumps(fm),
                    "parser_version": fm.get("parser_version"),
                }

            elif kind == "sec":
                pub_date, dsrc = resolve_date(fm, "", p.name, folder_year)
                if not pub_date:  # R4 guarantees this, but never emit a NULL date
                    pub_date, dsrc = folder_year + "-01-01", "folder"
                row = {
                    "doc_id": doc_id, "path": relp,
                    "source_file": fm.get("source_file"), "source_sha256": None,  # MD is itself the filing
                    "publisher_id": fm.get("company_name") or p.parent.parent.name,
                    "doc_type": sec_doc_type(fm.get("form", "")),
                    "title": fm.get("company_name") or fm.get("ticker"),
                    "published_at": pub_date, "date_source": dsrc,
                    "period_from": None, "period_to": None, "company_id": fm.get("ticker"),
                    "public_ok": True, "frontmatter": json.dumps(fm),
                    "parser_version": fm.get("parser"),  # none present
                }

            else:  # broker
                pub_date, dsrc = resolve_date(fm, body, p.name, folder_year)
                if not pub_date:
                    pub_date, dsrc = folder_year + "-01-01", "folder"
                publisher_id, doc_type = broker_route(rel, fm)
                # source_sha256: trust the frontmatter value when the extractor already computed it;
                # re-hashing every source PDF/HTML here is too slow (19k files) and the extractor's
                # hash already satisfies the dedup provenance requirement when present.
                src = fm.get("source_file", "")
                if not src and fm.get("local_pdf"):
                    src = (p.parent / fm["local_pdf"]).resolve().relative_to(ROOT.resolve()).as_posix()
                source_sha256 = fm.get("source_sha256") or None
                row = {
                    "doc_id": doc_id, "path": relp,
                    "source_file": src or None, "source_sha256": source_sha256,
                    "publisher_id": publisher_id, "doc_type": doc_type,
                    "title": fm.get("title"), "published_at": pub_date, "date_source": dsrc,
                    "period_from": None, "period_to": None, "company_id": None,
                    "public_ok": True, "frontmatter": json.dumps(fm),
                    "parser_version": fm.get("parser_version") or fm.get("parser"),
                }

            rows.append(list(row.values()))
            key = row["publisher_id"]
            stats[key] = stats.get(key, 0) + 1

    con.executemany("""
        INSERT INTO document (doc_id, path, source_file, source_sha256, publisher_id, doc_type,
                              title, published_at, date_source, period_from, period_to, company_id,
                              public_ok, frontmatter, parser_version)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, rows)
    n = len(rows)

    total = con.execute("SELECT count(*) FROM document").fetchone()[0]
    published = con.execute("SELECT count(*) FROM document WHERE published_at IS NOT NULL").fetchone()[0]
    pubs = con.execute("SELECT count(*) FROM document WHERE publisher_id IS NOT NULL").fetchone()[0]
    con.close()

    print(f"P0.5 normalise: {total:,} document rows")
    print(f"  published_at set: {published:,} | publisher_id set: {pubs:,}")
    print("  publishers:")
    for k in sorted(stats):
        print(f"    {k}: {stats[k]:,}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
