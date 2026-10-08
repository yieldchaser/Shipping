"""Rebuild the Clarksons sales and demolition series from parsed `<stem>.tables.json` files.

Reads staged output (default) or promoted output, writes
  clarksons_sales_series.csv       one row per vessel sold
  clarksons_demolition_series.csv  one row per vessel demolished
plus a comparison against the existing series (by (issue_date, vessel)).
"""
from __future__ import annotations

import csv
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

from scripts.parse_engine.config import REPO_ROOT
from scripts.parse_engine.promote import DEFAULT_NAME_MARKERS, belongs_to_source, read_frontmatter

# Columns of the old series files, kept so existing readers (r["issue"], r["NAME"] ...) keep working.
SALES_ALIASES = ["issue", "page", "NAME", "TYPE", "DWT", "BUILT", "YARD", "PRICE", "BUYERS", "SS_DD", "COMMENTS", "extra_json"]
DEMO_ALIASES = ["issue", "page", "NAME", "TYPE", "DWT", "BUILT", "YARD", "PRICE", "DELIVERY", "COMMENTS", "extra_json"]
SALES_FIELDS = ["issue_date", "report_week", "section", "vessel", "dwt", "built_year", "yard", "details", "ss_dd",
                "price_raw", "price_usd_m", "price_usd_m_per_vessel", "price_qualifier", "price_scope", "buyer", "en_bloc",
                "en_bloc_group",
                "built_raw", "source_file", "source_sha256"] + SALES_ALIASES
DEMO_FIELDS = ["issue_date", "report_week", "section", "vessel", "dwt", "built_year", "built_place", "ldt",
               "price_raw", "price_usd_ldt", "destination", "details", "built_raw", "source_file", "source_sha256"] + DEMO_ALIASES

NO_SALES = "no reported sales"
EN_BLOC_RE = re.compile(r"en\s*-?\s*bloc", re.I)
UNDISCLOSED = {"u/d", "undisclosed", "und", "-", "", "n/a", "tba", "tbc"}
QUAL_WORDS = {"LOW": "LOW", "MID": "MID", "HIGH": "HIGH", "XS": "XS", "RGN": "RGN", "REGION": "RGN"}
# optional "USD"/"$", optional qualifier words, then number + optional unit (M / B)
AMOUNT_RE = re.compile(
    r"(?:USD|US\$|\$)?\s*(?:(?:LOW|MID|HIGH|XS|RGN|REGION|ABT)(?:\s*[/\-–’�]\s*(?:LOW|MID|HIGH|XS|RGN))?\s+)*"
    r"(\d[\d.,]*)\s*(m|mn|mil|mln|million|bn|b|billion)?(?![\w/])", re.I)


# ---------------------------------------------------------------------------------------- parsing
def parse_amount(token: str) -> float | None:
    """'22,7' -> 22.7 (decimal comma), '1,250' -> 1250, '222.5' -> 222.5, '1.250,5' -> 1250.5, '1,250.5' -> 1250.5."""
    t = token.strip().rstrip(".,")
    if "," in t and "." in t:
        # the separator that comes last is the decimal mark
        t = t.replace(".", "").replace(",", ".") if t.rfind(",") > t.rfind(".") else t.replace(",", "")
    elif "," in t:
        head, _, tail = t.rpartition(",")
        t = f"{head.replace(',', '')}.{tail}" if 1 <= len(tail) <= 2 and head else t.replace(",", "")
    try:
        return float(t)
    except ValueError:
        return None


def parse_price(raw: str) -> dict[str, Any]:
    """price_usd_m (USD million), qualifier (LOW/MID/HIGH/XS/RGN, joined with '/'), en_bloc, scope.

    Undisclosed ('U/D', '-', blank) gives a blank price. For an en-bloc deal the price is the group
    price (scope 'group'); '... each' prices are per vessel (scope 'vessel'). A number needs either a
    USD/$ sign or a unit (M/B) to count as a price."""
    text = (raw or "").strip()
    out: dict[str, Any] = {"price_usd_m": "", "price_qualifier": "", "en_bloc": False, "price_scope": ""}
    if text.lower() in UNDISCLOSED:
        return out
    out["en_bloc"] = bool(EN_BLOC_RE.search(text))
    for m in AMOUNT_RE.finditer(text):
        whole = m.group(0)
        if not (re.search(r"USD|US\$|\$", whole, re.I) or m.group(2)):
            continue
        val = parse_amount(m.group(1))
        if val is None:
            continue
        unit = (m.group(2) or "").lower()
        if unit in ("b", "bn", "billion"):
            val *= 1000.0
        elif not unit and val >= 100000:          # plain USD amount
            val /= 1e6
        out["price_usd_m"] = round(val, 3)
        quals = []
        for w in re.findall(r"[A-Za-z]+", text[: m.start(1)].upper()):
            q = QUAL_WORDS.get(w)
            if q and q not in quals:
                quals.append(q)
        out["price_qualifier"] = "/".join(quals)
        out["price_scope"] = "vessel" if re.search(r"\beach\b|per vessel", text, re.I) else ("group" if out["en_bloc"] else "vessel")
        break
    if not out["price_qualifier"]:
        quals = []
        for w in re.findall(r"[A-Za-z]+", text.upper()):
            q = QUAL_WORDS.get(w)
            if q and q not in quals:
                quals.append(q)
        out["price_qualifier"] = "/".join(quals)
    return out


def parse_int(text: str) -> int | str:
    t = re.sub(r"\s", "", text or "")
    if re.fullmatch(r"\d{1,3}([.,]\d{3})+", t):         # 175.085 / 175,085: thousands separators
        t = re.sub(r"[.,]", "", t)
    return int(t) if t.isdigit() else ""


def parse_year(text: str) -> int | str:
    m = re.fullmatch(r"\s*((?:19|20)\d{2})\s*", text or "")
    return int(m.group(1)) if m else ""


def section_of(table_name: str) -> str:
    n = table_name.lower()
    if "tanker" in n:
        return "tanker"
    if "bulk" in n or "bulker" in n:
        return "bulk"
    return "other"


def parse_ldt(details: str, bare_ok: bool = False) -> int | str:
    """LDT from a Details cell ("9,543 LDT"). With `bare_ok` (a demolition table, where the column holds the
    light displacement) a bare number such as "9,200" is read as LDT too."""
    m = re.search(r"([\d.,]+)\s*LDT", details or "", re.I)
    if not m and bare_ok:
        m = re.fullmatch(r"\s*([\d][\d.,]*)\s*", details or "")
    if not m:
        return ""
    tok = m.group(1).strip(".,")
    if re.fullmatch(r"\d{1,3}([.,]\d{3})+", tok):       # 8.895 / 9,543 are thousands separators
        tok = re.sub(r"[.,]", "", tok)
    try:
        return int(float(tok.replace(",", ".")))
    except ValueError:
        return ""


GREEK_TO_LATIN = str.maketrans({"Α": "A", "Β": "B", "Ε": "E", "Ζ": "Z", "Η": "H", "Ι": "I", "Κ": "K", "Μ": "M",
                                "Ν": "N", "Ο": "O", "Ρ": "P", "Τ": "T", "Υ": "Y", "Χ": "X", "ο": "o", "ν": "v"})
PRICE_RANGE_RE = re.compile(r"(\d[\d.,]*)\s*[-–]\s*(\d[\d.,]*)")


def latinize(name: str) -> str:
    """Greek capitals that look like Latin letters ("ΑLPHA") back to Latin, so one vessel keeps one spelling."""
    return (name or "").translate(GREEK_TO_LATIN)


def parse_demo_price(raw: str) -> float | str:
    """USD/LDT of a demolition price; a printed range ("540-550") is kept verbatim as text, never cut to its low end."""
    rng = PRICE_RANGE_RE.search(raw or "")
    if rng:
        return f"{rng.group(1)}-{rng.group(2)}"
    m = re.search(r"([\d][\d.,]*)\s*(?:/\s*(?:LDT|LT|ldt)|USD)?", raw or "")
    if not m or not re.search(r"\d", raw or ""):
        return ""
    val = parse_amount(m.group(1))
    return "" if val is None else val


# ---------------------------------------------------------------------------------------- export
def _iter_issues(root: Path, markers: tuple[str, ...] = DEFAULT_NAME_MARKERS) -> list[tuple[Path, Path]]:
    """(md, tables.json) pairs under `root` that belong to the source: another publisher's report filed under
    the same directory (an SSY report in clarksons/2026) is not an issue of this series."""
    pairs = []
    for tj in sorted(root.glob("*/*.tables.json")):
        md = tj.with_name(tj.name[: -len(".tables.json")] + ".md")
        if md.exists() and belongs_to_source(md, markers):
            pairs.append((md, tj))
    return pairs


def _col(columns: list[str], *names: str) -> int | None:
    low = [c.lower() for c in columns]
    for n in names:
        if n.lower() in low:
            return low.index(n.lower())
    return None


def with_aliases(row: dict[str, Any], demo: bool) -> dict[str, Any]:
    """Add the legacy-named columns (see SALES_ALIASES / DEMO_ALIASES) to a flat series row."""
    import json as _json
    extra = {"stem": Path(str(row.get("source_file", ""))).stem, "source_file": Path(str(row.get("source_file", ""))).name,
             "raw_built": row.get("built_raw", "")}
    out = {**row, "issue": row.get("issue_date"), "NAME": row.get("vessel"), "TYPE": "",
           "DWT": row.get("dwt_raw", row.get("dwt")), "BUILT": row.get("built_raw") if demo else row.get("built_year"),
           "YARD": row.get("built_place") if demo else row.get("yard"), "PRICE": row.get("price_raw"),
           "COMMENTS": row.get("details"), "extra_json": _json.dumps(extra, ensure_ascii=False)}
    if demo:
        out["DELIVERY"] = row.get("destination")
    else:
        out["BUYERS"] = row.get("buyer")
        out["SS_DD"] = row.get("ss_dd")
    return out


def tables_of(data: Any) -> list[dict[str, Any]]:
    """The table list of a tables.json: schema parse_engine/v1 (object with "tables") or a bare list."""
    if isinstance(data, dict):
        return list(data.get("tables") or [])
    return list(data or [])


def issue_rows(tables: list[dict[str, Any]], meta: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Flat vessel rows (sales, demolitions) of one issue. `meta` carries issue_date, report_week,
    source_file and source_sha256.

    en_bloc_group changes when the en-bloc state, the raw price or the buyer changes between consecutive
    rows, so two neighbouring en-bloc deals are two groups. price_usd_m_per_vessel is the group price
    divided by the vessels in the group when price_scope is 'group', otherwise it equals price_usd_m."""
    sales: list[dict[str, Any]] = []
    demo: list[dict[str, Any]] = []
    for t in tables:
        cols, rows = t["columns"], t["rows"]
        if t.get("empty") or (rows and rows[0][0].strip().lower() == NO_SALES):
            continue
        is_demo = t["name"].lower().startswith("demolition")
        ix = {k: _col(cols, *v) for k, v in {
            "vessel": ("Vessel",), "dwt": ("DWT",), "year": ("Year",), "yard": ("Yard",),
            "built": ("Built",), "details": ("Details",), "ssdd": ("SS/DD",), "price": ("Price",),
            "buyer": ("Buyer",), "delivery": ("Delivery",)}.items()}
        get = lambda row, k: row[ix[k]].strip() if ix[k] is not None and ix[k] < len(row) else ""  # noqa: E731
        vessel = lambda row: latinize(get(row, "vessel"))  # noqa: E731
        flagged = set(t.get("en_bloc_rows", []))
        sec = section_of(t["name"])
        group = 0
        prev_key: tuple[str, str] | None = None
        first_sale = len(sales)
        for ri, row in enumerate(rows):
            if re.fullmatch(r"[-\u2013\u2014\s]*", get(row, "vessel")):
                continue                      # a dash placeholder row ("--") is not a vessel
            if is_demo:
                built = get(row, "built") or get(row, "year")
                m = re.match(r"((?:19|20)\d{2})\s*(.*)$", built)
                demo.append({**meta, "section": sec, "vessel": vessel(row), "page": t.get("page"),
                             "dwt_raw": get(row, "dwt"), "dwt": parse_int(get(row, "dwt")), "built_year": int(m.group(1)) if m else "",
                             "built_place": (m.group(2) if m else built).strip(), "ldt": parse_ldt(get(row, "details"), bare_ok=True),
                             "price_raw": get(row, "price"), "price_usd_ldt": parse_demo_price(get(row, "price")),
                             "destination": get(row, "delivery"), "details": get(row, "details"), "built_raw": built})
                continue
            price_raw = get(row, "price")
            buyer = get(row, "buyer")
            pp = parse_price(price_raw)
            en_bloc = bool(pp["en_bloc"] or ri in flagged or EN_BLOC_RE.search(buyer))
            key = (price_raw, buyer)
            if en_bloc and (prev_key is None or key != prev_key):
                group += 1
            prev_key = key if en_bloc else None
            if en_bloc and not pp["price_scope"] and pp["price_usd_m"] != "":
                pp["price_scope"] = "group"
            year_raw = get(row, "year") or get(row, "built")
            sales.append({**meta, "section": sec, "vessel": vessel(row), "page": t.get("page"),
                          "dwt_raw": get(row, "dwt"), "dwt": parse_int(get(row, "dwt")), "built_year": parse_year(year_raw),
                          "yard": get(row, "yard"), "details": get(row, "details"), "ss_dd": get(row, "ssdd"),
                          "price_raw": price_raw, "price_usd_m": pp["price_usd_m"],
                          "price_qualifier": pp["price_qualifier"], "price_scope": pp["price_scope"],
                          "buyer": buyer, "en_bloc": en_bloc,
                          "en_bloc_group": f"{meta['issue_date']}#{sec}{group}" if en_bloc else "",
                          "built_raw": year_raw})
        sizes: dict[str, int] = {}
        for r in sales[first_sale:]:
            if r["en_bloc_group"]:
                sizes[r["en_bloc_group"]] = sizes.get(r["en_bloc_group"], 0) + 1
        for r in sales[first_sale:]:
            price = r["price_usd_m"]
            if price == "":
                r["price_usd_m_per_vessel"] = ""
            elif r["price_scope"] == "group" and r["en_bloc_group"]:
                r["price_usd_m_per_vessel"] = round(price / sizes[r["en_bloc_group"]], 3)
            else:
                r["price_usd_m_per_vessel"] = price
    return sales, demo


def legacy_aliases(row: dict[str, Any]) -> dict[str, Any]:
    """Upper-case keys the legacy Clarksons sidecars used (NAME, DWT, BUILT, YARD, PRICE, BUYERS, SS_DD)."""
    return {**row, "NAME": row.get("vessel"), "DWT": row.get("dwt"), "BUILT": row.get("built_year"),
            "YARD": row.get("yard"), "PRICE": row.get("price_raw"), "BUYERS": row.get("buyer"),
            "SS_DD": row.get("ss_dd")}


def sidecar_payload(tables: list[dict[str, Any]], issue_date: str | None, source_file: str,
                    source_sha256: str, vessel_rows: bool = True) -> dict[str, Any]:
    """tables.json for one issue: object schema parse_engine/v1, readable by the legacy consumers
    (dict root, `sales`, `demolitions`, `sales_count`, `demo_count`) and carrying the geometric tables."""
    week = date.fromisoformat(issue_date).isocalendar()[1] if issue_date else None
    meta = {"issue_date": issue_date, "report_week": week, "source_file": source_file, "source_sha256": source_sha256}
    sales, demo = issue_rows(tables, meta) if vessel_rows else ([], [])
    return {"schema": "parse_engine/v1", "issue_date": issue_date, "report_week": week, "source_file": source_file,
            "source_sha256": source_sha256, "sales_count": len(sales), "demo_count": len(demo),
            "tables": tables, "sales": [legacy_aliases(r) for r in sales], "demolitions": demo}


def export(root: Path, out_dir: Path, only_stems: set[str] | None = None,
           require_engine_schema: bool = False, markers: tuple[str, ...] = DEFAULT_NAME_MARKERS) -> dict[str, Any]:
    if require_engine_schema:
        legacy = [tj for _, tj in _iter_issues(root, markers)
                  if not isinstance(json.loads(tj.read_text(encoding="utf-8")), dict)
                  or json.loads(tj.read_text(encoding="utf-8")).get("schema") != "parse_engine/v1"]
        if legacy:
            raise SystemExit(f"series: {len(legacy)} tables.json under {root} are not schema parse_engine/v1 "
                             f"(first: {legacy[0].name}); promote the parse_engine output first")
    sales: list[dict[str, Any]] = []
    demo: list[dict[str, Any]] = []
    issues = 0
    for md, tj in _iter_issues(root, markers):
        if only_stems is not None and md.stem not in only_stems:
            continue
        fm = read_frontmatter(md)
        issue_date = fm.get("issue_date")
        if not issue_date:
            continue
        issues += 1
        week = date.fromisoformat(str(issue_date)).isocalendar()[1]
        meta = {"issue_date": str(issue_date), "report_week": week, "source_file": fm.get("source_file", ""),
                "source_sha256": fm.get("source_sha256", "")}
        s_rows, d_rows = issue_rows(tables_of(json.loads(tj.read_text(encoding="utf-8"))), meta)
        sales.extend(s_rows)
        demo.extend(d_rows)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, fields, rows, is_demo in (("clarksons_sales_series.csv", SALES_FIELDS, sales, False),
                                        ("clarksons_demolition_series.csv", DEMO_FIELDS, demo, True)):
        with open(out_dir / name, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            w.writerows(with_aliases(r, is_demo) for r in rows)
    return {"issues": issues, "sales_rows": len(sales), "demolition_rows": len(demo), "sales": sales, "demo": demo}


# ---------------------------------------------------------------------------------------- comparison
def _norm_vessel(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").upper()).strip()


def _read_keys(path: Path, date_col: str, vessel_col: str) -> set[tuple[str, str]]:
    keys = set()
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            keys.add((r[date_col], _norm_vessel(r[vessel_col])))
    return keys


def compare(new_rows: list[dict[str, Any]], old_path: Path, date_col: str, vessel_col: str,
            out_csv: Path | None = None) -> dict[str, Any]:
    new_keys = {(r["issue_date"], _norm_vessel(r["vessel"])) for r in new_rows}
    old_keys = _read_keys(old_path, date_col, vessel_col)
    new_dates = {d for d, _ in new_keys}
    old_dates = {d for d, _ in old_keys}
    common = new_dates & old_dates
    only_old = sorted(k for k in old_keys - new_keys)
    only_new = sorted(k for k in new_keys - old_keys)
    only_old_c = [k for k in only_old if k[0] in common]
    only_new_c = [k for k in only_new if k[0] in common]
    if out_csv:
        out_csv.parent.mkdir(parents=True, exist_ok=True)
        with open(out_csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["side", "issue_date", "vessel", "issue_in_both_sets"])
            w.writerows(("old_only", d, v, d in common) for d, v in only_old)
            w.writerows(("new_only", d, v, d in common) for d, v in only_new)
    return {"old_rows_keys": len(old_keys), "new_rows_keys": len(new_keys), "old_issue_dates": len(old_dates),
            "new_issue_dates": len(new_dates), "dates_only_in_old": len(old_dates - new_dates),
            "dates_only_in_new": len(new_dates - old_dates), "old_not_in_new": len(only_old),
            "new_not_in_old": len(only_new), "old_not_in_new_common_dates": len(only_old_c),
            "new_not_in_old_common_dates": len(only_new_c)}


DEFAULT_OLD = {"sales_series": ("clarksons_sales_series.csv", "issue_date", "NAME"),
               "snp_sales_series": ("clarksons_snp_sales_series.csv", "issue_date", "vessel_name")}


def run_export(root: Path, out_dir: Path, series_dir: Path = REPO_ROOT / "data" / "extracted" / "series",
               only_stems: set[str] | None = None, require_engine_schema: bool = False,
               markers: tuple[str, ...] = DEFAULT_NAME_MARKERS) -> dict[str, Any]:
    res = export(root, out_dir, only_stems, require_engine_schema, markers)
    res["comparison"] = {}
    for key, (fname, dcol, vcol) in DEFAULT_OLD.items():
        path = series_dir / fname
        if path.exists():
            res["comparison"][fname] = compare(res["sales"], path, dcol, vcol, out_dir / f"compare_vs_{fname}")
    return res
