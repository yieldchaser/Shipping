"""Upsert the GMS and Best Oasis demolition series CSVs from the engine's `<stem>.tables.json` sidecars.

    python -m scripts.parse_engine series --source gms --root data/extracted/md/hellenic/demolition/gms \
        --out-dir data/extracted/series [--dry-run]

Semantics are an UPSERT that never drops history: for every issue that has an engine sidecar under `--root` the
rows of that issue (key: issue_date) are replaced in each CSV; the rows of issues without a sidecar are kept
untouched. Rows are stable-sorted by issue_date. Values come only from printed cells; a cell that is not printed
stays empty, and a chart the engine left as a `> Figure:` note produces no rows. When an engine issue differs from the
current CSV only in the `source_file` column the old rows are kept (no churn). A comparison against the current CSVs
is printed and written before anything is written; `--dry-run` stops there.
"""
from __future__ import annotations

import csv
import io
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from scripts.parse_engine.config import corpus_root
from scripts.parse_engine.promote import read_frontmatter

SCHEMA = "parse_engine/v1"
SOURCES = ("gms", "best_oasis")
DEFAULT_ROOT = "data/extracted/md/hellenic/demolition/{source}"
DEFAULT_OUT_DIR = "data/extracted/series"
SAMPLE_CELLS = 8
SAMPLE_ROWS = 3


@dataclass(frozen=True)
class SeriesFile:
    key: str
    name: str
    twin: str | None
    header: tuple[str, ...]
    keep_when_empty: bool = True      # an issue whose sidecar yields no rows for this file keeps its old rows


GMS_FILES = (
    SeriesFile("rankings", "gms_demolition_rankings_series.csv", "hellenic_gms_demolition_series.csv",
               ("issue_date", "report_week", "volume", "issue", "rank", "location", "sentiment",
                "dry_bulk_usd_ldt", "tankers_usd_ldt", "containers_usd_ldt", "source_file")),
    SeriesFile("sales", "gms_demolition_sales_series.csv", None,
               ("issue_date", "report_week", "location", "vessel_name", "vessel_type", "ldt", "price_reported",
                "terms_comments", "source_file"), keep_when_empty=False),
    SeriesFile("ports", "gms_port_positions_series.csv", "hellenic_gms_port_positions_series.csv",
               ("issue_date", "report_week", "as_of_date", "port", "item_no", "vessel_name", "ldt", "vessel_type",
                "status", "source_file")),
)
BO_FILES = (
    SeriesFile("demolition", "best_oasis_demolition_series.csv", "hellenic_best_oasis_demolition_series.csv",
               ("issue_date", "location", "market_status", "container_usd_ldt", "tanker_usd_ldt", "bulker_usd_ldt",
                "hms_80_20_usd_mt", "shredded_usd_mt", "source_file")),
    SeriesFile("deals", "best_oasis_deals_series.csv", "hellenic_best_oasis_deals_series.csv",
               ("issue_date", "vessel_name", "vessel_type", "imo", "year_built", "country_built", "ldt", "sale_terms",
                "delivery_location", "price_usd_ldt", "price_status", "comments", "source_file")),
    SeriesFile("exchange", "best_oasis_exchange_rates_series.csv", None,
               ("issue_date", "usd_inr", "usd_bdt", "usd_pkr", "usd_try", "brent_crude_usd", "wti_crude_usd",
                "source_file")),
)
FILES = {"gms": GMS_FILES, "best_oasis": BO_FILES}

Rows = dict[str, list[dict[str, str]]]     # SeriesFile.key -> rows of one issue


# ---------------------------------------------------------------------------------------------- helpers
def _clean(cell: Any) -> str:
    return str(cell if cell is not None else "").strip()


def _num(text: str) -> float | None:
    """A cell that is exactly one number ("2,354.40", "568") -> float; anything else -> None."""
    t = _clean(text).replace(",", "")
    return float(t) if re.fullmatch(r"\d+(?:\.\d+)?", t) else None


def _fmt(value: float | None) -> str:
    """Existing CSV convention: Python float text (530.0, 2354.4)."""
    return "" if value is None else repr(float(value))


def _signed(text: str) -> float | None:
    t = re.sub(r"[()%\s,]", "", _clean(text)).replace("−", "-").replace("–", "-")
    return float(t) if re.fullmatch(r"[+-]?\d+(?:\.\d+)?", t) else None


def _location(label: str) -> str:
    """Title-cased location as the existing CSVs have it. The chart titles print "T<u-umlaut>rkiye" (the umlaut
    arrives mangled); the series has always called those rows "Turkey", while a plain-ASCII "TURKIYE" label stays
    "Turkiye" exactly as printed."""
    text = _clean(label)
    if re.fullmatch(r"t.{1,2}rkiye", text, re.I) and not text.isascii():
        return "Turkey"
    return text.title()


def _clean_source_path(raw: str) -> str:
    """Repo-relative corpus path of the PDF (drops a worktree prefix the sidecar may carry)."""
    text = (raw or "").replace("\\", "/")
    i = text.find("corpus/")
    return text[i:] if i >= 0 else text


def _source_file(source: str, raw: str) -> str:
    path = _clean_source_path(raw)
    if source == "gms":
        return path.rsplit("/", 1)[-1]
    name = path.rsplit("/", 1)[-1]
    sub = f"corpus/02-hellenic/demolition/pdfs/{source}/{name}"
    flat = f"corpus/02-hellenic/demolition/pdfs/{name}"
    for cand in (sub, flat):
        if (corpus_root() / cand).exists():
            return cand
    return sub


def _cells_by_header(table: dict[str, Any]) -> tuple[list[str], list[list[str]]]:
    return [_clean(c) for c in table.get("columns", [])], [[_clean(c) for c in r] for r in table.get("rows", [])]


def _col(headers: list[str], *prefixes: str) -> int | None:
    for p in prefixes:
        for i, h in enumerate(headers):
            if h.upper().startswith(p.upper()):
                return i
    return None


def _get(row: list[str], idx: int | None) -> str:
    return row[idx] if idx is not None and idx < len(row) else ""


# ---------------------------------------------------------------------------------------------- GMS
def _price_cell(cell: str, headers: list[str], i: int) -> str:
    """A GMS ranking price as printed ("560 / LDT", "310-315 / LDT", "-"); a trailing footnote asterisk is dropped.
    Text that is not a price stays empty, except where the PDF line-wrapped "570 / (small) LDT" and the table reader
    left "570 / (small)" in the column header and "LDT" in the cell: the two printed pieces are joined back."""
    cell = cell.rstrip("*").rstrip()
    if re.match(r"^\d", cell) or cell in ("-", "–"):
        return cell
    tail = re.search(r"USD\s*/\s*LDT\s+(\d.*)$", headers[i]) if i < len(headers) else None
    return f"{tail.group(1).strip()} {cell}" if tail and cell.upper() == "LDT" else ""


def _sales_locations(md_path: Path, n_tables: int) -> list[str]:
    """Country heading above each 'Market Sales Reported' table, read from the promoted MD; empty when the MD and
    the sidecar disagree on how many such tables there are."""
    if not md_path.exists():
        return [""] * n_tables
    found: list[str] = []
    h1 = ""
    for line in md_path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("# "):
            h1 = line[2:].strip()
        elif re.match(r"^#{2,4}\s+Market Sales Reported\s*$", line):
            found.append(h1)
    return found if len(found) == n_tables else [""] * n_tables


def extract_gms(data: dict[str, Any], md_path: Path, source_file: str) -> Rows:
    meta = read_frontmatter(md_path) if md_path.exists() else {}
    # the MD front matter (visually verified against the PDF) wins over the sidecar's report_week
    week = meta.get("report_week", data.get("report_week", ""))
    base = {"issue_date": data["issue_date"], "report_week": _clean(week), "source_file": source_file}
    out: Rows = {"rankings": [], "sales": [], "ports": []}
    tables = data.get("tables", [])
    sales_tables = [t for t in tables if t.get("name") == "market_sales_reported"]
    locations = _sales_locations(md_path, len(sales_tables))
    sales_i = 0
    for t in tables:
        name = t.get("name", "")
        headers, rows = _cells_by_header(t)
        if name == "gms_rankings":
            for r in rows:
                out["rankings"].append({
                    **{k: base[k] for k in ("issue_date", "report_week")},
                    "volume": _clean(meta.get("volume", "")), "issue": _clean(meta.get("issue", "")),
                    "rank": _get(r, 0), "location": _get(r, 1).rstrip("*").rstrip(), "sentiment": _get(r, 2),
                    "dry_bulk_usd_ldt": _price_cell(_get(r, 3), headers, 3),
                    "tankers_usd_ldt": _price_cell(_get(r, 4), headers, 4),
                    "containers_usd_ldt": _price_cell(_get(r, 5), headers, 5), "source_file": base["source_file"]})
        elif name == "market_sales_reported":
            loc = locations[sales_i]
            sales_i += 1
            i_name, i_type, i_ldt, i_price = (_col(headers, "Vessel Name"), _col(headers, "Type"),
                                              _col(headers, "LDT"), _col(headers, "Reported Price"))
            known = {i for i in (i_name, i_type, i_ldt, i_price) if i is not None}
            for r in rows:
                extra = " | ".join(c for i, c in enumerate(r) if i not in known and c)
                out["sales"].append({**base, "location": loc, "vessel_name": _get(r, i_name),
                                     "vessel_type": _get(r, i_type), "ldt": _get(r, i_ldt),
                                     "price_reported": _get(r, i_price), "terms_comments": extra})
        elif name.startswith("port_"):
            m = re.match(r"^(.*?)\s+-\s+Port Position as of\s+(.+)$", _clean(t.get("title", "")))
            if not m:
                continue
            i_no, i_name, i_ldt, i_type, i_status = (_col(headers, "No"), _col(headers, "Vessel Name"),
                                                     _col(headers, "LDT"), _col(headers, "Type"),
                                                     _col(headers, "Status"))
            for r in rows:
                out["ports"].append({**base, "as_of_date": m.group(2).strip(), "port": m.group(1).strip(),
                                     "item_no": _get(r, i_no), "vessel_name": _get(r, i_name), "ldt": _get(r, i_ldt),
                                     "vessel_type": _get(r, i_type), "status": _get(r, i_status)})
    return out


# ---------------------------------------------------------------------------------------------- Best Oasis
DEAL_LABELS = ("VESSEL NAME", "TYPE OF VESSEL", "IMO NO.", "YEAR OF BUILD", "COUNTRY OF BUILD", "LDT",
               "TERM OF SALE", "LOCATION OF DELIVERY", "SALE PRICE")


def _split_polluted_header(headers: list[str], rows: list[list[str]]) -> tuple[list[str], list[list[str]]]:
    """A header cell that carries its first data value ("VESSEL NAME SEAPEAK ASIA") is split into the label and the
    value, which becomes the first data row. The text is exactly what is printed."""
    new_headers, first = [], []
    changed = False
    for h in headers:
        label = next((l for l in DEAL_LABELS if h.upper().startswith(l)), None)
        if label and len(h) > len(label) and h[len(label)] in " /":
            if label == "SALE PRICE":
                m = re.match(r"^SALE PRICE\s*/\s*L\w*\s*\(USD\)\s*(.*)$", h, re.I)
                new_headers.append(h[:m.start(1)].strip() if m else h)
                first.append(m.group(1).strip() if m else "")
            else:
                new_headers.append(h[:len(label)])
                first.append(h[len(label):].strip())
            changed = True
        else:
            new_headers.append(h)
            first.append("")
    return (new_headers, [first] + rows) if changed else (headers, rows)


def parse_price_cell(cell: str) -> tuple[str, str, str]:
    """(price_usd_ldt, price_status, comments) for a printed 'Sale Price/LDT' cell.

    A cell that starts with a number is a reported price. price_usd_ldt is set only when that number stands alone
    (optionally followed by a note such as "(BUNKERS ROB)"); a range ("540-550", "580/640") or a lump sum ("1.6 MM")
    leaves it empty and the printed cell goes to comments. Text that does not start with a number ("UNDISCLOSED (...)")
    is "Undisclosed" with the printed text as comments; a blank or "-" cell has no status."""
    text = _clean(cell)
    if text in ("", "-"):
        return "", "", ""
    m = re.match(r"^(\d[\d,]*(?:\.\d+)?)(.*)$", text)
    if not m:
        return "", "Undisclosed", ("" if text.lower() == "undisclosed" else text)
    rest = m.group(2).strip()
    if re.match(r"(?i)^([-–/]\s*\d|mm\b|m\b|mn\b|million)", rest):
        return "", "Reported", text
    return _fmt(_num(m.group(1))), "Reported", ("" if not rest else text)


def deal_rows(headers: list[str], rows: list[list[str]], base: dict[str, str]) -> list[dict[str, str]]:
    headers, rows = _split_polluted_header(headers, rows)
    idx = {k: _col(headers, p) for k, p in (("name", "VESSEL NAME"), ("type", "TYPE OF VESSEL"), ("imo", "IMO"),
                                            ("year", "YEAR OF BUILD"), ("country", "COUNTRY OF BUILD"),
                                            ("ldt", "LDT"), ("terms", "TERM OF SALE"),
                                            ("loc", "LOCATION OF DELIVERY"), ("price", "SALE PRICE"))}
    out = []
    for r in rows:
        name = _get(r, idx["name"])
        if not name:
            continue
        ldt_text = _get(r, idx["ldt"])
        lm = re.match(r"^(\d[\d,]*(?:\.\d+)?)\s*(.*)$", ldt_text)
        ldt = _fmt(_num(lm.group(1))) if lm else ""
        ldt_note = f"LDT {ldt_text}" if lm and lm.group(2) else ""
        price, status, comments = parse_price_cell(_get(r, idx["price"]))
        imo = _get(r, idx["imo"])
        year = _get(r, idx["year"])
        out.append({**base, "vessel_name": name, "vessel_type": _get(r, idx["type"]),
                    "imo": imo if re.fullmatch(r"\d{7}", imo) else "",
                    "year_built": year if re.fullmatch(r"\d{4}", year) else "",
                    "country_built": _get(r, idx["country"]), "ldt": ldt, "sale_terms": _get(r, idx["terms"]),
                    "delivery_location": _get(r, idx["loc"]), "price_usd_ldt": price, "price_status": status,
                    "comments": "; ".join(c for c in (comments, ldt_note) if c)})
    return out


def _this_week(t: dict[str, Any]) -> dict[str, str]:
    """{row label: This Week value} of a Category / Previous Week / This Week chart table."""
    headers, rows = _cells_by_header(t)
    i = _col(headers, "This Week")
    return {r[0]: _get(r, i) for r in rows if r} if i is not None else {}


def _float_cell(text: str) -> str:
    return _fmt(_num(text))


def _fx_this_week(rows: list[list[str]], headers: list[str]) -> dict[str, str]:
    """{label: This Week value}. A row whose label glues two currencies ("USD / BDT USD / PKR") belongs to the first
    one that has no row of its own."""
    i_this = _col(headers, "This Week")
    if i_this is None:
        return {}
    own = {r[0].upper() for r in rows if r}
    out: dict[str, str] = {}
    for r in rows:
        if not r:
            continue
        label = r[0].upper()
        pair = re.findall(r"USD\s*/\s*[A-Z]{2,3}", label)
        if len(pair) > 1:
            label = next((c for c in pair if c not in own), label)
        out[label] = _get(r, i_this)
    return out


def _crude_this_week(value_text: str, change_text: str) -> str:
    """'(99.73 102.72)' with change '+2.99': the figures carry no previous / this labels (the arrow between them is a
    picture), so the second figure is taken as this week only when second - first equals the signed change as printed.
    Equal figures need no orientation; anything else (sign reversed, change not matching) stays empty."""
    nums = re.findall(r"\d+(?:\.\d+)?", value_text)
    if len(nums) != 2:
        return ""
    a, b = float(nums[0]), float(nums[1])
    if a == b:
        return _fmt(b)
    chg = _signed(change_text)
    return _fmt(b) if chg is not None and abs((b - a) - chg) < 0.011 else ""


def _find_pdf(source: str, raw: str) -> Path | None:
    path = _clean_source_path(raw)
    name = path.rsplit("/", 1)[-1]
    for cand in (path, f"corpus/02-hellenic/demolition/pdfs/{source}/{name}", f"corpus/02-hellenic/demolition/pdfs/{name}"):
        if (corpus_root() / cand).is_file():
            return corpus_root() / cand
    return None


def _crude_from_pdf(pdf: Path | None) -> dict[str, str]:
    """Brent / WTI 'This Week' from the older reports' text boxes, which the engine keeps only as prose whose label
    order is not reliable. Each 'This Week : <value>' box is assigned to the Brent / WTI label nearest to it
    horizontally (the labels sit directly above their box). Needs the PDF; without it the cells stay empty."""
    if pdf is None:
        return {}
    import pymupdf
    out: dict[str, str] = {}
    try:
        doc = pymupdf.open(pdf)
    except Exception:
        return {}
    with doc:
        for page in doc:
            words = page.get_text("words")
            labels = {w[4].upper(): w for w in words if w[4].lower() in ("brent", "wti")}
            if len(labels) != 2:
                continue
            boxes = []
            for i, w in enumerate(words[:-2]):
                nxt = words[i + 1]
                if w[4] == "This" and nxt[4] == "Week" and abs(nxt[1] - w[1]) < 4:
                    vals = [v for v in words if abs(v[1] - w[1]) < 5 and v[0] > nxt[2]
                            and re.fullmatch(r"\d+(?:\.\d+)?", v[4])]
                    if vals:
                        boxes.append((w[0], min(vals, key=lambda v: v[0] - nxt[2])[4]))
            if len(boxes) != 2:
                continue
            for x0, val in boxes:
                name = min(labels, key=lambda k: abs(labels[k][0] - x0))
                out[name + " CRUDE"] = _fmt(float(val))
            if len(out) == 2:
                return out
            out = {}
    return {}


def extract_best_oasis(data: dict[str, Any], md_path: Path, source_file: str) -> Rows:
    base = {"issue_date": data["issue_date"], "source_file": source_file}
    out: Rows = {"demolition": [], "deals": [], "exchange": []}
    price: dict[str, dict[str, str]] = {}      # location -> demolition columns
    order: list[str] = []

    def row_for(label: str) -> dict[str, str]:
        loc = _location(label)
        if loc not in price:
            price[loc] = {}
            order.append(loc)
        return price[loc]

    fx: dict[str, str] = {}
    saw_status_table = saw_hms_table = False
    crude: dict[str, str] = {}
    for t in data.get("tables", []):
        headers, rows = _cells_by_header(t)
        if not headers:
            continue
        title = _clean(t.get("title") or "")
        if headers[0].upper() == "CATEGORY" and t.get("row_source") == "best_oasis_chart":
            vals = _this_week(t)
            country = t.get("country") or ""
            if title.startswith("Price for Recycling Ships in") and country:
                cur = row_for(country)
                for label, col in (("Container", "container_usd_ldt"), ("Tanker", "tanker_usd_ldt"),
                                   ("Bulker", "bulker_usd_ldt")):
                    if label in vals:
                        cur[col] = _float_cell(vals[label])
            elif title.startswith("Price of HMS") and country:
                cur = row_for(country)
                for label, v in vals.items():
                    if label.upper().startswith("HMS"):
                        cur["hms_80_20_usd_mt"] = _float_cell(v)
                    elif label.upper().startswith("SHREDDED"):
                        cur["shredded_usd_mt"] = _float_cell(v)
        elif headers[0].upper() == "LOCATION" and _col(headers, "MARKET STATUS") is not None:
            saw_status_table = True
            i_status, i_c, i_t, i_b = (_col(headers, "MARKET STATUS"), _col(headers, "CONTAINER"),
                                       _col(headers, "TANKER"), _col(headers, "BULKER"))
            for r in rows:
                cur = row_for(r[0])
                cur["market_status"] = _get(r, i_status).title()
                cur["container_usd_ldt"] = _float_cell(_get(r, i_c))
                cur["tanker_usd_ldt"] = _float_cell(_get(r, i_t))
                cur["bulker_usd_ldt"] = _float_cell(_get(r, i_b))
        elif headers[0].upper() == "LOCATION" and _col(headers, "HMS") is not None:
            saw_hms_table = True
            i_h, i_s = _col(headers, "HMS"), _col(headers, "SHREDDED")
            for r in rows:
                cur = row_for(r[0])
                cur["hms_80_20_usd_mt"] = _float_cell(_get(r, i_h))
                cur["shredded_usd_mt"] = _float_cell(_get(r, i_s))
        elif headers[0].upper().startswith("VESSEL NAME"):
            out["deals"].extend(deal_rows(headers, rows, base))
        elif headers[0].upper() == "ITEM" and _col(headers, "This Week") is not None:
            vals = _fx_this_week(rows, headers)
            fx.update(vals)
        elif headers[0].upper() == "ITEM" and _col(headers, "Values as printed") is not None:
            i_v, i_c = _col(headers, "Values as printed"), _col(headers, "Change")
            for r in rows:
                crude[r[0].upper()] = _crude_this_week(_get(r, i_v), _get(r, i_c))
    if saw_hms_table and not saw_status_table:
        # the engine parsed the HMS / Shredded table but not the container / tanker / bulker table of the same
        # template (a page it did not parse): half a week is not an issue's rows, so the old rows stay
        order.clear()
    for loc in order:
        cur = price[loc]
        out["demolition"].append({**base, "location": loc, "market_status": cur.get("market_status", ""),
                                  **{k: cur.get(k, "") for k in ("container_usd_ldt", "tanker_usd_ldt",
                                                                 "bulker_usd_ldt", "hms_80_20_usd_mt",
                                                                 "shredded_usd_mt")}})
    prose = {} if (fx.get("BRENT CRUDE") or crude.get("BRENT CRUDE")) else _crude_from_pdf(_find_pdf("best_oasis", data.get("source_file", "")))
    brent = fx.get("BRENT CRUDE", "") or prose.get("BRENT CRUDE", "")
    wti = fx.get("WTI CRUDE", "") or prose.get("WTI CRUDE", "")
    rates = {
        "usd_inr": _float_cell(fx.get("USD / INR", "")), "usd_bdt": _float_cell(fx.get("USD / BDT", "")),
        "usd_pkr": _float_cell(fx.get("USD / PKR", "")),
        "usd_try": _float_cell(fx.get("USD / TRY", "") or fx.get("USD / TL", "")),
        "brent_crude_usd": _float_cell(brent) or crude.get("BRENT CRUDE", ""),
        "wti_crude_usd": _float_cell(wti) or crude.get("WTI CRUDE", ""),
    }
    if any(rates.values()):
        out["exchange"].append({**base, **rates})
    return out


EXTRACTORS: dict[str, Callable[[dict[str, Any], Path, str], Rows]] = {"gms": extract_gms,
                                                                       "best_oasis": extract_best_oasis}


# ---------------------------------------------------------------------------------------------- IO / merge
def load_issues(source: str, root: Path) -> list[tuple[str, Path, Rows]]:
    """[(issue_date, sidecar path, rows per file key)] for every engine sidecar under root, by issue_date."""
    issues = []
    for p in sorted(root.rglob("*.tables.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        if data.get("schema") != SCHEMA or not data.get("issue_date"):
            continue
        md = p.with_name(p.name[: -len(".tables.json")] + ".md")
        issues.append((data["issue_date"], p, EXTRACTORS[source](data, md, _source_file(source, data.get("source_file", "")))))
    issues.sort(key=lambda x: (x[0], x[1].name))
    return issues


def read_csv(path: Path, header: tuple[str, ...]) -> list[dict[str, str]]:
    if not path.exists():
        return []
    reader = csv.DictReader(io.StringIO(path.read_text(encoding="utf-8"), newline=""))
    if tuple(reader.fieldnames or ()) != header:
        raise ValueError(f"{path}: header {reader.fieldnames} does not match the expected {list(header)}")
    return list(reader)


def render_csv(header: tuple[str, ...], rows: list[dict[str, str]]) -> str:
    buf = io.StringIO(newline="")
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header)
    for r in rows:
        w.writerow([r.get(c, "") for c in header])
    return buf.getvalue()


def _data_key(row: dict[str, str]) -> tuple:
    return tuple(sorted((k, v) for k, v in row.items() if k != "source_file"))


@dataclass
class FileResult:
    spec: SeriesFile
    merged: list[dict[str, str]]
    old_rows: int
    added_issues: list[str]
    changed_issues: list[str]
    unchanged_issues: list[str]
    path_only_issues: list[str]
    kept_empty_issues: list[str]
    rows_added: int
    rows_removed: int
    samples: list[str]
    twin_differs: bool


def _pair_diff(old: list[dict[str, str]], new: list[dict[str, str]], date: str, header: tuple[str, ...],
               samples: list[str]) -> None:
    only_old = [r for r in old if _data_key(r) not in {_data_key(n) for n in new}]
    only_new = [r for r in new if _data_key(r) not in {_data_key(o) for o in old}]
    cols = [c for c in header if c != "source_file"]
    for o in only_old:
        best = max(only_new, key=lambda n: sum(o.get(c) == n.get(c) for c in cols), default=None)
        if best is not None and sum(o.get(c) == best.get(c) for c in cols) >= len(cols) // 2:
            only_new.remove(best)
            diffs = ", ".join(f"{c}: {o.get(c, '')!r} -> {best.get(c, '')!r}" for c in cols if o.get(c) != best.get(c))
            samples.append(f"  {date} changed row: {diffs}")
        else:
            samples.append(f"  {date} removed row: " + " | ".join(o.get(c, "") for c in cols))
    for n in only_new:
        samples.append(f"  {date} added row: " + " | ".join(n.get(c, "") for c in cols))


def merge_file(spec: SeriesFile, old: list[dict[str, str]], issues: list[tuple[str, Path, Rows]],
               twin_old: list[dict[str, str]] | None) -> FileResult:
    old_by_date: dict[str, list[dict[str, str]]] = {}
    for r in old:
        old_by_date.setdefault(r["issue_date"], []).append(r)
    replace: dict[str, list[dict[str, str]]] = {}
    added, changed, unchanged, path_only, kept_empty, samples = [], [], [], [], [], []
    rows_added = rows_removed = 0
    for date, _p, rows in issues:
        new = rows.get(spec.key, [])
        prior = old_by_date.get(date, [])
        if not new and prior and spec.keep_when_empty:
            kept_empty.append(date)
            continue
        if not prior and not new:
            continue
        if not prior:
            added.append(date)
            replace[date] = new
            rows_added += len(new)
            continue
        if Counter(map(_data_key, prior)) == Counter(map(_data_key, new)) and len(prior) == len(new):
            if [r.get("source_file") for r in prior] != [r.get("source_file") for r in new]:
                path_only.append(date)
            else:
                unchanged.append(date)
            continue                                    # identical data: keep the old rows verbatim
        changed.append(date)
        replace[date] = new
        prior_keys, new_keys = Counter(map(_data_key, prior)), Counter(map(_data_key, new))
        rows_added += sum((new_keys - prior_keys).values())
        rows_removed += sum((prior_keys - new_keys).values())
        _pair_diff(prior, new, date, spec.header, samples)
    kept = [r for r in old if r["issue_date"] not in replace]
    merged = sorted(kept + [r for d in sorted(replace) for r in replace[d]], key=lambda r: r["issue_date"])
    twin_differs = twin_old is not None and twin_old != old
    return FileResult(spec, merged, len(old), added, changed, unchanged, path_only, kept_empty, rows_added,
                      rows_removed, samples, twin_differs)


def format_report(source: str, root: Path, out_dir: Path, results: list[FileResult], n_issues: int, dry_run: bool) -> str:
    lines = [f"series comparison: source={source} root={root.as_posix()} out_dir={out_dir.as_posix()} "
             f"sidecar issues={n_issues} mode={'dry-run' if dry_run else 'write'}", ""]
    for r in results:
        s = r.spec
        lines.append(f"== {s.name}" + (f" (+ twin {s.twin})" if s.twin else ""))
        lines.append(f"  rows: current {r.old_rows} -> new {len(r.merged)}; rows added {r.rows_added}, rows removed {r.rows_removed}")
        lines.append(f"  issues: added {len(r.added_issues)}, changed {len(r.changed_issues)}, "
                     f"unchanged {len(r.unchanged_issues)}, unchanged but source_file differs (old rows kept) {len(r.path_only_issues)}, "
                     f"engine gave no usable rows (old rows kept) {len(r.kept_empty_issues)}")
        if r.twin_differs:
            lines.append("  WARNING: the current twin file differs from the primary; both will be written identically")
        for label, dates in (("added", r.added_issues), ("changed", r.changed_issues),
                             ("engine gave no usable rows", r.kept_empty_issues)):
            if dates:
                lines.append(f"  {label}: " + ", ".join(dates[:40]) + (f" ... (+{len(dates) - 40})" if len(dates) > 40 else ""))
        if r.samples:
            lines.append(f"  differing cells / rows (first {SAMPLE_CELLS * 6} of {len(r.samples)}):")
            lines.extend(r.samples[: SAMPLE_CELLS * 6])
        lines.append("")
    return "\n".join(lines)


def run_demolition_series(source: str, root: Path, out_dir: Path, report_path: Path, dry_run: bool = False) -> dict[str, Any]:
    issues = load_issues(source, root)
    results = []
    for spec in FILES[source]:
        old = read_csv(out_dir / spec.name, spec.header)
        twin_old = read_csv(out_dir / spec.twin, spec.header) if spec.twin and (out_dir / spec.twin).exists() else None
        if not old and twin_old:
            old = twin_old
        results.append(merge_file(spec, old, issues, twin_old))
    report = format_report(source, root, out_dir, results, len(issues), dry_run)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report + "\n", encoding="utf-8")
    written = []
    if not dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)
        for r in results:
            text = render_csv(r.spec.header, r.merged)
            for name in (r.spec.name, r.spec.twin):
                if name:
                    (out_dir / name).write_text(text, encoding="utf-8", newline="")
                    written.append(name)
    return {"issues": len(issues), "report": report, "report_path": report_path, "written": written,
            "results": {r.spec.name: r for r in results}}
