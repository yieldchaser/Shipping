"""Per-source runner: ALLIED (corpus/archive/allied, 203 PDFs, 2021-2024).

Source-by-source pipeline (user rule). Two document classes:
  * ALLIED-SnP-Statistics-Week-NN   (9 pp, dense S&P statistics tables)
  * ALLIED-Weekly-Market-Report / Allied-Weekly-Market-Review (12-14 pp)

DELIVERABLE:
  * data/extracted/md/allied/<year>/<stem>.md          (primary, full text)
  * data/extracted/md/allied/<year>/<stem>.tables.json (parsed tables)
  * data/extracted/series/allied_sales_series.csv      (Reported Transactions deals)

MEASURED FACTS (docs/allied_survey.md):
  * Numbers are pure ISO everywhere (period-thousands, comma-decimals absent).
  * The Reported-Transactions deal table's COLUMNS CHANGE BY YEAR: 2021 has an
    M/E column, 2024 dropped it and added Coating.  => columns are derived from
    the PAGE's own header row, never hardcoded (skill: layout is not stable).
  * Cell values sit in multi-line wrapped bands; rows are recovered by nearest
    row-start assignment, not by fixed y geometry.
"""
import csv, json, os, re, subprocess, sys, time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SRC_DIR = REPO / "corpus" / "archive" / "allied"
OUT_MD = REPO / "data" / "extracted" / "md" / "allied"
OUT_SERIES = REPO / "data" / "extracted" / "series"
STATE = OUT_MD / "_run_state.json"
DEALS_CSV = OUT_SERIES / "allied_sales_series.csv"

# Header labels we recognise, in left-to-right table order. 'M/E' only 2021-22,
# 'Coating' appears 2023+. Both may be present on a page.
COLS = ["Size", "Name", "Dwt", "Built", "Shipbuilder", "M/E", "Coating",
        "Price", "Buyers", "Comments"]
HEADER_ANCHORS = {"Size", "Price", "Buyers"}


def _clean(s):
    return re.sub(r"\s+", " ", s).strip()


def find_issue_date(stem, doc):
    """Publisher cover/date, then filename DD_MM_YYYY, then ISO in text."""
    m = re.search(r"[_\-](\d{2})[_\-](\d{2})[_\-](\d{4})", stem)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    m = re.search(r"(20\d{2})[_\-](\d{2})[_\-](\d{2})", stem)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    for pg in doc[:2]:
        m = re.search(r"(\d{1,2})\s*(?:st|nd|rd|th)?\s+"
                      r"(January|February|March|April|May|June|July|August|"
                      r"September|October|November|December),?\s+(\d{4})",
                      pg.get_text(), re.I)
        if m:
            mo = ["january","february","march","april","may","june","july",
                  "august","september","october","november","december"].index(
                      m.group(2).lower()) + 1
            return f"{m.group(3)}-{mo:02d}-{int(m.group(1)):02d}"
    return ""


def report_week(stem, doc):
    m = re.search(r"[Ww](?:eek[-_ ]*)?(\d{1,2})", stem)
    if m:
        return int(m.group(1))
    for pg in doc[:2]:
        m = re.search(r"Week\s*(\d{1,2})", pg.get_text())
        if m:
            return int(m.group(1))
    return 0


def _header_rows(words):
    """All deal-table header rows on a page -> list of (header_y, anchors, cols)."""
    rows = {}
    for w in words:
        y = round((w[1] + w[3]) / 2.0)
        rows.setdefault(y, []).append(w)
    heads = []
    for y in sorted(rows):
        labels = [w for w in rows[y] if w[4] in COLS]
        found = set(w[4] for w in labels).intersection(HEADER_ANCHORS)
        if len(found) >= 3:
            labels.sort(key=lambda w: w[0])
            heads.append((y, [w[0] for w in labels], [w[4] for w in labels]))
    return heads


def _col_of(x, anchors):
    """Column = the header anchor nearest this word's x-start."""
    return min(range(len(anchors)), key=lambda i: abs(anchors[i] - x))


_SIZE_OK = re.compile(r"^[A-Za-z][A-Za-z0-9 ./]{0,8}$")


def _parse_band(body, anchors, cols, page_no):
    """Parse one table band (one header to the next) into deal rows."""
    row_ys = sorted(set((w[1] + w[3]) / 2.0 for w in body
                        if _col_of(w[0], anchors) == 0))
    merged = []
    for y in row_ys:
        if not merged or y - merged[-1] > 3.0:
            merged.append(y)
    if not merged:
        return []
    buckets = {}
    for w in body:
        yc = (w[1] + w[3]) / 2.0
        near = min(merged, key=lambda r: abs(r - yc))
        buckets.setdefault(near, []).append(w)
    out = []
    for ry in sorted(buckets):
        cells = {c: [] for c in cols}
        for w in sorted(buckets[ry], key=lambda w: (w[1], w[0])):
            ci = _col_of(w[0], anchors)
            if 0 <= ci < len(cols):
                cells[cols[ci]].append(w[4])
        row = {c: _clean(" ".join(cells.get(c, []))) for c in cols}
        row["_page"] = page_no
        if not row.get("Dwt"):
            row["Dwt"] = row.get("TEU", "") or row.get("CBM", "")
        size = row.get("Size", "")
        name = row.get("Name", "")
        has_num = bool(re.search(r"\d{3,}", row.get("Dwt", "")))
        if not size or size.startswith("\u00a9") or not _SIZE_OK.match(size[:9]):
            continue
        if name and (has_num or re.search(r"\d", row.get("Price", ""))):
            out.append(row)
    return out


def parse_deals_page(page):
    """Parse every sales sub-table on one page -> list of deal dicts."""
    words = [w for w in page.get_text("words") if w[4].strip()]
    heads = _header_rows(words)
    if not heads:
        return []
    out = []
    for idx, (hy, anchors, cols) in enumerate(heads):
        lo = hy + 4
        hi = heads[idx + 1][0] - 4 if idx + 1 < len(heads) else 1e9
        body = [w for w in words if lo < (w[1] + w[3]) / 2.0 < hi]
        out.extend(_parse_band(body, anchors, cols, page.number))
    return out


def parse_doc(pdf_path):
    import pymupdf
    doc = pymupdf.open(pdf_path)
    stem = pdf_path.stem
    year = pdf_path.parent.name
    issue = find_issue_date(stem, doc)
    week = report_week(stem, doc)
    pages_txt = [p.get_text() for p in doc]
    deals = []
    for p in doc:
        deals.extend(parse_deals_page(p))
    n_pages = doc.page_count
    doc.close()
    return dict(stem=stem, year=year, issue_date=issue, report_week=week,
                n_pages=n_pages, pages=pages_txt, deals=deals)


DEAL_FIELDS = ["issue_date", "report_week", "size", "name", "dwt", "built",
               "shipbuilder", "coating", "price_raw", "price_usd_m",
               "group_total_mil", "buyers",
               "comments", "source_file", "page"]


def _norm_price(s):
    m = re.search(r"([\d.,]+)\s*m", s.replace("$", ""))
    if m:
        try:
            return float(m.group(1).replace(",", ".") ) if "," in m.group(1) and "." not in m.group(1) else float(m.group(1).replace(",", ""))
        except ValueError:
            return None
    return None


def write_doc(rec):
    ydir = OUT_MD / rec["year"]
    ydir.mkdir(parents=True, exist_ok=True)
    header = (f"# Allied Weekly Market Report\n\n"
              f"Issue: Week {rec['report_week']:02d} | {rec['issue_date']}\n\n")
    body = "\n\n".join(p.strip() for p in rec["pages"])
    (ydir / f"{rec['stem']}.md").write_text(header + body, encoding="utf-8")
    tables = {"deals": []}
    for d in rec["deals"]:
        row = {"size": d.get("Size", ""), "name": d.get("Name", ""),
               "dwt": d.get("Dwt", ""), "built": d.get("Built", ""),
               "shipbuilder": d.get("Shipbuilder", ""),
               "coating": _clean((d.get("M/E", "") + " " + d.get("Coating", ""))),
               "price_raw": d.get("Price", ""), "buyers": d.get("Buyers", ""),
               "comments": d.get("Comments", ""), "page": d.get("_page")}
        tables["deals"].append(row)
    payload = {"issue_date": rec["issue_date"], "report_week": rec["report_week"],
               "source_file": str(rec["source_file"]), "stem": rec["stem"],
               "tables": tables}
    (ydir / f"{rec['stem']}.tables.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return tables["deals"]


_MONEY_RX = re.compile(r"\$?[ ]*([0-9][0-9.,]*)[ ]*m")


_ENBLOC_RX = re.compile(r"en\s*bloc", re.I)


def _lot_binding(deals):
    """Identify en-bloc LOT totals and which row carries each one.

    A lot is a run of CONSECUTIVE rows on a page that (a) share the SAME size
    class and the SAME fleet name-prefix and (b) contain the words 'en bloc'
    somewhere in that run's price cells. The lot's transaction value is then the
    ONE money amount printed among those rows. The row that carries that amount
    is NOT one vessel's price - blank it and record it as group_total_mil.

    Two guards, both forced by measurement (docs/allied_enbloc_verdict.md):
      * a CERTAIN own-cell ('$ 245.0m en bloc' in one cell) always binds;
      * a run holding MORE THAN ONE amount is ambiguous -> leave every row
        unlabelled (a wrong value is worse than a missing one). Without this
        guard the rule blanked legit per-vessel prices (ERAWAN 10 $12.0m,
        DOLPHIN 03 $18.0m - two separate sales on a page that also holds a lot).
    """
    out = {}
    by_page = {}
    for i, d in enumerate(deals):
        by_page.setdefault(d.get("_page"), []).append(i)

    def _amt(cell):
        m = _MONEY_RX.search(cell or "")
        if not m:
            return None
        n = m.group(1)
        try:
            return float(n.replace(",", ".")) if ("," in n and "." not in n) else float(n.replace(",", ""))
        except ValueError:
            return None

    for pg, idxs in by_page.items():
        runs, run = [], [idxs[0]]
        for a, b in zip(idxs, idxs[1:]):
            na = (deals[a].get("Name", "") or "").split()[:1]
            nb = (deals[b].get("Name", "") or "").split()[:1]
            if b == a + 1 and deals[b].get("Size") == deals[a].get("Size") and na == nb:
                run.append(b)
            else:
                runs.append(run); run = [b]
        runs.append(run)
        for run in runs:
            cells = [deals[i].get("Price", "") or "" for i in run]
            markers = [i for i in run if _ENBLOC_RX.search(deals[i].get("Price", "") or "")]
            if not markers:
                continue
            amts = [(i, _amt(c)) for i, c in zip(run, cells) if _amt(c) is not None]
            # own-cell markers bind their own amount unambiguously
            for i in markers:
                v = _amt(deals[i].get("Price", "") or "")
                if v is not None:
                    out[id(deals[i])] = v
            if len(amts) == 1:
                out[id(deals[amts[0][0]])] = amts[0][1]
    return out


def _split_row(d):
    """Separate the money token from gear/coating text that bled into Price."""
    gear = _clean(" ".join([d.get("M/E", ""), d.get("Coating", ""), d.get("Gear", "")]))
    price_field = _clean(d.get("Price", ""))
    m = _MONEY_RX.search(price_field)
    if m:
        num = m.group(1)
        usd = float(num.replace(",", ".")) if ("," in num and "." not in num) else float(num.replace(",", ""))
        leftover = _clean(price_field.replace(m.group(0), " "))
        if leftover:
            gear = _clean(gear + " " + leftover)
        return gear, m.group(0).replace("$", "").strip(), usd
    return gear, price_field, None


def deal_rows(rec):
    rows = []
    lots = _lot_binding(rec["deals"])
    for d in rec["deals"]:
        gear, price_raw, usd = _split_row(d)
        gt = lots.get(id(d))
        if gt is not None:
            usd = None          # a lot total is not a per-vessel price
        rows.append({
            "issue_date": rec["issue_date"], "report_week": rec["report_week"],
            "size": d.get("Size", ""), "name": d.get("Name", ""),
            "dwt": re.sub(r"[^\d]", "", d.get("Dwt", "")),
            "built": re.sub(r"[^\d]", "", d.get("Built", "")),
            "shipbuilder": d.get("Shipbuilder", ""),
            "coating": gear,
            "price_raw": price_raw, "price_usd_m": usd,
            "group_total_mil": gt,
            "buyers": d.get("Buyers", ""), "comments": d.get("Comments", ""),
            "source_file": rec["source_file"].name, "page": d.get("_page")})
    return rows


def _load_state():
    if STATE.exists():
        try:
            return json.loads(STATE.read_text())
        except Exception:
            return {"done": [], "failed": []}
    return {"done": [], "failed": []}


def _save_state(st):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, indent=1))


def run_one(pdf_path):
    rec = parse_doc(Path(pdf_path))
    rec["source_file"] = Path(pdf_path)
    write_doc(rec)
    return rec


def run_all():
    pdfs = sorted(SRC_DIR.rglob("*.pdf"))
    st = _load_state()
    done = set(st["done"])
    jsonl = OUT_MD / "_deals.jsonl"
    OUT_MD.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    for i, pdf in enumerate(pdfs, 1):
        if pdf.stem in done:
            continue
        try:
            r = subprocess.run([sys.executable, str(Path(__file__).resolve()),
                                "--doc", str(pdf)], capture_output=True, text=True,
                               timeout=180)
            line = [l for l in r.stdout.strip().splitlines() if l.startswith("{")]
            if r.returncode != 0 or not line:
                st["failed"].append(pdf.stem)
                print(f"[{i}/{len(pdfs)}] FAIL {pdf.stem}: {r.stderr[-200:]}")
            else:
                rows = json.loads(line[-1])["rows"]
                with jsonl.open("a", encoding="utf-8") as fh:
                    for row in rows:
                        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                done.add(pdf.stem)
                print(f"[{i}/{len(pdfs)}] ok {pdf.stem} ({len(rows)} deals)")
        except subprocess.TimeoutExpired:
            st["failed"].append(pdf.stem)
            print(f"[{i}/{len(pdfs)}] TIMEOUT {pdf.stem}")
        st["done"] = sorted(done)
        _save_state(st)
    # stack JSONL -> CSV
    if jsonl.exists():
        rows = []
        for ln in jsonl.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(ln))
            except Exception:
                pass
        seen = set()
        uniq = []
        for r in rows:
            k = (r["source_file"], r["name"], r["dwt"], r["price_raw"])
            if k in seen:
                continue
            seen.add(k)
            uniq.append(r)
        uniq.sort(key=lambda r: (r["issue_date"], r["page"] or 0))
        OUT_SERIES.mkdir(parents=True, exist_ok=True)
        with DEALS_CSV.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=DEAL_FIELDS)
            w.writeheader()
            w.writerows(uniq)
        print(f"CSV {DEALS_CSV} rows={len(uniq)} (from {len(rows)} raw)")
    print(f"done={len(done)} failed={len(st['failed'])} in {time.time()-t0:.0f}s")


if __name__ == "__main__":
    if "--doc" in sys.argv:
        rec = run_one(sys.argv[sys.argv.index("--doc") + 1])
        print(json.dumps({"stem": rec["stem"], "n_deals": len(rec["deals"]),
                          "rows": deal_rows(rec)}))
    else:
        run_all()
