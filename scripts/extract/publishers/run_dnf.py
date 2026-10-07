"""Per-source runner: DNF ANALYSIS "Dry Bulk Weekly Brief"
(corpus/archive/other, 38 PDFs, 2021-2022).

Deliverables
  * data/extracted/md/dnf/<year>/<stem>.md           (PRIMARY, full page text)
  * data/extracted/md/dnf/<year>/<stem>.tables.json  (parsed tables)
  * data/extracted/series/dnf_secondhand_transactions_series.csv
  * data/extracted/series/dnf_bunker_prices_series.csv

MEASURED facts (docs/dnf_survey.md):
  TWO LAYOUT ERAS - do NOT hardcode geometry.
    ERA A  2021 W26-W32 (6 docs, 7 pages) "DRY BULK WEEKLY"
      Latest Transactions header order: Week | Ships Sold | Built | DWT |
      Reported Price (US$) | Country/Region of Buyer | Owner | Notes
      (data row: name x~77, built x~201, dwt x~235, price x~280, buyer x~362,
       owner x~421)
    ERA B  2021 W33 -> 2022 W18 (32 docs, 4 pages) "DRY BULK WEEKLY BRIEF"
      header order: WEEK | Vessel Name | DWT | Built | Reported Price
      (data row: name x~339-370, dwt x~459, built x~508, price x~561)
  ==> the DWT and Built columns SWAP ORDER between the eras (European-style
      convention flip). Column order is therefore derived from the page's own
      header row, never assumed.
  Numbers are ISO ("206,331" = 206331; "26.5" = 26.5).
  The currency token is whatever the PAGE prints ($ or the publisher's own
  stray GBP glyph) - read it, do not assume.
  Rows are anchored on the DWT-column numeric; tokens are assigned to the
  column whose header anchor is nearest, with the header's own x boundaries.
"""
import csv, json, re, subprocess, sys, time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SRC_DIR = REPO / "corpus" / "archive" / "other"
OUT_MD = REPO / "data" / "extracted" / "md" / "dnf"
OUT_SERIES = REPO / "data" / "extracted" / "series"
STATE = OUT_MD / "_run_state.json"
TXN_CSV = OUT_SERIES / "dnf_secondhand_transactions_series.csv"
BUN_CSV = OUT_SERIES / "dnf_bunker_prices_series.csv"

_MON = ["January", "February", "March", "April", "May", "June", "July",
        "August", "September", "October", "November", "December"]
MONTHS = {m.lower(): i for i, m in enumerate(_MON, 1)}
MONTHS.update({m.lower()[:3]: i for i, m in enumerate(_MON, 1)})

# header vocabulary per logical column (first token of the printed header)
TXN_VOCAB = {
    "week":  ("week", "wk"),
    "name":  ("vessel", "ships", "name"),
    "built": ("built", "yob"),
    "dwt":   ("dwt",),
    "price": ("reported", "average", "price"),
    "buyer": ("country",),
    "owner": ("owner",),
    "notes": ("notes",),
}
MONEY = re.compile(r"([$\u00a3])\s*([\d,]+(?:\.\d+)?)\s*([MmKk]?)")
YEAR_RE = re.compile(r"^(19|20)\d{2}$")
INT_RE = re.compile(r"^\d{1,4}$")


def is_dnf(doc):
    t = " ".join(doc[i].get_text() for i in range(len(doc))).lower()
    return "dnfanalysis" in t


def issue_date(doc):
    """Date from the publisher's OWN cover line (page 0), then filename."""
    t = doc[0].get_text()
    m = re.search(r"Monday,\s*(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", t)
    if not m:
        m = re.search(r"(\d{1,2})\s+(January|February|March|April|May|June|July|"
                      r"August|September|October|November|December)\s+(\d{4})", t)
    if m:
        mon = MONTHS[m.group(2).lower()[:3]]
        return f"{int(m.group(3)):04d}-{mon:02d}-{int(m.group(1)):02d}"
    return ""


def _yclusters(words, tol=3.0):
    groups = []
    for w in sorted(words, key=lambda w: (w[1], w[0])):
        if groups and abs(w[1] - groups[-1][0]) <= tol:
            groups[-1][1].append(w)
        else:
            groups.append([w[1], [w]])
    return groups


def _col_anchors(ws, vocab):
    out = {}
    for col, toks in vocab.items():
        cands = [w for w in ws
                 if any(w[4].lower().startswith(t) for t in toks)]
        if cands:
            out[col] = min(w[0] for w in cands)
    return out


def _bounds(anchors):
    order = sorted(anchors, key=lambda c: anchors[c])
    b = []
    for i, c in enumerate(order):
        b.append(1e9 if i == len(order) - 1
                 else (anchors[order[i]] + anchors[order[i + 1]]) / 2.0)
    def colof(x):
        for i, c in enumerate(order):
            if x < b[i]:
                return c
        return order[-1]
    return colof


def _strip_pua(t):
    return "".join(ch for ch in t if not ("" <= ch <= ""))


HEADER_TOKENS = {"Week", "Ships", "Sold", "Built", "DWT", "Reported", "Price",
                 "(US$)", "Country/", "Region", "of", "Buyer", "Owner", "Notes",
                 "Vessel", "Name", "Last", "Min", "YoB", "Average", "WEEK",
                 "NAME", "Count", "UNITS"}


def _assign(band, anchors, gap=6.0):
    """Split a row band into cells by x-gaps, then label each cell by the
    header anchor nearest its centre. Robust to centred headers and to
    multi-word cells that a fixed x-cut would shred."""
    clusters = []
    for w in band:
        if _strip_pua(w[4]).strip() in HEADER_TOKENS:
            continue
        if clusters and w[0] - clusters[-1][-1][2] <= gap:
            clusters[-1].append(w)
        else:
            clusters.append([w])
    cells = {}
    for cl in clusters:
        cx = (cl[0][0] + cl[-1][2]) / 2.0
        col = min(anchors, key=lambda c: abs(anchors[c] - cx))
        cells.setdefault(col, []).extend(cl)
    return cells


def txn_header(page):
    """Find the transactions header row: the y-cluster that literally prints DWT."""
    for y, ws in _yclusters(page.get_text("words")):
        if any(w[4] == "DWT" for w in ws):
            a = _col_anchors(ws, TXN_VOCAB)
            if {"dwt", "built", "price", "week"} <= set(a):
                return y, a
    return None


def parse_money1(tok):
    m = MONEY.search(tok)
    if not m:
        return None, ""
    v = float(m.group(2).replace(",", ""))
    suf = m.group(3).upper()
    if suf == "M":
        pass
    elif suf == "K":
        v /= 1000.0
    else:
        v /= 1e6
    return round(v, 4), m.group(1)


def parse_txn(page, page_no):
    h = txn_header(page)
    if not h:
        return []
    hy, anchors = h
    left = anchors["week"] + 8.0
    colof = _bounds(anchors)
    words = [w for w in page.get_text("words")
             if w[1] > hy + 3.0 and w[0] >= left
             and re.search(r"[0-9A-Za-z]", _strip_pua(w[4]))]
    # DWT-column numerics = row anchors
    dwt_words = sorted((w for w in words
                        if colof(w[0]) == "dwt"
                        and re.fullmatch(r"\d[\d,]*(?:\.\d+)?", w[4])),
                       key=lambda w: w[1])
    anchors_y = []
    for w in dwt_words:
        if not anchors_y or w[1] - anchors_y[-1] > 45.0:
            if anchors_y:
                break            # contiguous table block only
        anchors_y.append(w[1])
    if len(anchors_y) < 2:
        return []
    gaps = sorted(anchors_y[j + 1] - anchors_y[j]
                  for j in range(len(anchors_y) - 1))
    pitch = gaps[len(gaps) // 2] if gaps else 20.0
    rows = []
    for i, ry in enumerate(anchors_y):
        top = hy + 15.0 if i == 0 else (anchors_y[i - 1] + ry) / 2.0
        bot = (ry + max(5.0, pitch * 0.5) if i == len(anchors_y) - 1
               else (ry + anchors_y[i + 1]) / 2.0)
        band = sorted((w for w in words if top <= w[1] < bot),
                      key=lambda w: (w[0], w[1]))
        cells = _assign(band, anchors)
        cells = {c: [(w[1], w[0], w[4]) for w in ws]
                 for c, ws in cells.items()}

        def j(c):
            return " ".join(t for _, _, t in sorted(cells.get(c, []))).strip()
        price_raw = j("price")
        pm, cur = parse_money1(price_raw)
        name = j("name")
        if not name and pm is None:
            continue
        rows.append({
            "vessel_name": name,
            "dwt_raw": j("dwt"), "built_raw": j("built"),
            "price_raw": price_raw, "price_currency": cur, "price_m": pm,
            "buyer": j("buyer"), "owner": j("owner"), "notes": j("notes"),
            "page": page_no})
    return rows


def parse_bunker(page, page_no):
    """ERA B dashboard: header WEEK | VLSFO | MGO | IFO380 (3 weekly rows)."""
    hdr = None
    for y, ws in _yclusters(page.get_text("words")):
        toks = {w[4].upper() for w in ws}
        if {"VLSFO", "MGO", "IFO380"} <= toks:
            hdr = (y, ws)
            break
    if not hdr:
        return []
    hy, ws = hdr
    a = _col_anchors(ws, {"week": ("week", "wk"), "vlsfo": ("vlsfo",),
                          "mgo": ("mgo",), "ifo380": ("ifo380",)})
    if len(a) < 4:
        return []
    left = a["week"] - 5.0
    colof = _bounds(a)
    words = [w for w in page.get_text("words")
             if w[1] > hy + 3.0 and w[0] >= left
             and re.search(r"[0-9A-Za-z]", _strip_pua(w[4]))]
    # row anchors = the WEEK column's own integers (content-anchored, so every
    # row is guaranteed to carry its week label; chart values never land here)
    ys = sorted({round(w[1], 1) for w in words
                 if colof(w[0]) == "week" and INT_RE.fullmatch(w[4])})
    runs = []
    for y in ys:
        if not runs or y - runs[-1] > 45.0:
            if runs:
                break
        runs.append(y)
    out = []
    gaps = sorted(runs[j + 1] - runs[j] for j in range(len(runs) - 1))
    pitch = gaps[len(gaps) // 2] if gaps else 28.0
    for i, ry in enumerate(runs):
        top = hy + 3.0 if i == 0 else (runs[i - 1] + ry) / 2.0
        bot = (ry + max(5.0, pitch * 0.5) if i == len(runs) - 1
               else (ry + runs[i + 1]) / 2.0)
        band = {colof(w[0]): w[4] for w in words if top <= w[1] < bot}
        vals = {}
        for c in ("vlsfo", "mgo", "ifo380"):
            t = band.get(c, "")
            m = re.search(r"\d[\d,]*", t)
            vals[c] = float(m.group(0).replace(",", "")) if m else None
        wk = band.get("week", "").strip()
        if not re.fullmatch(r"\d{1,3}", wk):
            continue
        if any(v is not None for v in vals.values()):
            out.append({**vals, "week_label": wk.strip(), "page": page_no})
    return out


def parse_doc(pdf_path):
    import pymupdf
    doc = pymupdf.open(pdf_path)
    if not is_dnf(doc):
        return None
    stem = Path(pdf_path).stem
    date = issue_date(doc)
    year = stem.split("_")[1] if stem.count("_") >= 2 else ""
    pages, txn, bun = [], [], []
    for i in range(len(doc)):
        pages.append(doc[i].get_text())
        txn.extend(parse_txn(doc[i], i + 1))
        bun.extend(parse_bunker(doc[i], i + 1))
    return {"stem": stem, "year": year, "issue_date": date, "pages": pages,
            "txn": txn, "bunker": bun, "source_file": str(pdf_path)}


def write_doc(rec):
    ydir = OUT_MD / rec["year"]
    ydir.mkdir(parents=True, exist_ok=True)
    header = (f"# DNF Analysis | Dry Bulk Weekly Brief\n\n"
              f"Issue: {rec['issue_date'] or rec['stem']}\n"
              f"Source: {Path(rec['source_file']).name}\n\n")
    (ydir / f"{rec['stem']}.md").write_text(
        header + "\n\n".join(p.strip() for p in rec["pages"]), encoding="utf-8")
    payload = {"issue_date": rec["issue_date"], "stem": rec["stem"],
               "source_file": str(rec["source_file"]),
               "tables": {"secondhand_transactions": rec["txn"],
                          "bunker_prices": rec["bunker"]}}
    (ydir / f"{rec['stem']}.tables.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")


def _num(s):
    if not s:
        return None
    m = re.search(r"[\d,]+(?:\.\d+)?", s)
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


def txn_rows(rec):
    out = []
    for d in rec["txn"]:
        out.append({
            "issue_date": rec["issue_date"],
            "vessel_name": d["vessel_name"],
            "dwt": _num(d["dwt_raw"]),
            "built_year": (_num(d["built_raw"]) if YEAR_RE.fullmatch(
                (d["built_raw"] or "").strip()) else d["built_raw"]),
            "price_raw": d["price_raw"],
            "price_currency": d["price_currency"],
            "price_m": d["price_m"],
            "buyer": d["buyer"], "owner": d["owner"], "notes": d["notes"],
            "source_file": Path(rec["source_file"]).name, "page": d["page"]})
    return out


def bunker_rows(rec):
    out = []
    for d in rec["bunker"]:
        for grade, key in (("VLSFO", "vlsfo"), ("MGO", "mgo"),
                           ("IFO380", "ifo380")):
            out.append({"issue_date": rec["issue_date"],
                        "week_label": d.get("week_label", ""), "grade": grade,
                        "price_usd_t": d.get(key),
                        "source_file": Path(rec["source_file"]).name,
                        "page": d["page"]})
    return out


TXN_FIELDS = ["issue_date", "vessel_name", "dwt", "built_year", "price_raw",
              "price_currency", "price_m", "buyer", "owner", "notes",
              "source_file", "page"]
BUN_FIELDS = ["issue_date", "week_label", "grade", "price_usd_t", "source_file", "page"]


def _load_state():
    if STATE.exists():
        try:
            return json.loads(STATE.read_text())
        except Exception:
            pass
    return {"done": [], "failed": []}


def _save_state(st):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, indent=1))


def _dedup(rows, keys):
    seen, out = set(), []
    for r in rows:
        k = tuple(r.get(x) for x in keys)
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out


def run_all():
    pdfs = []
    for p in sorted(SRC_DIR.rglob("*.pdf")):
        pdfs.append(p)
    st = _load_state()
    done = set(st["done"])
    OUT_MD.mkdir(parents=True, exist_ok=True)
    txn_jsonl = OUT_MD / "_txn.jsonl"
    bun_jsonl = OUT_MD / "_bunker.jsonl"
    t0 = time.time()
    for i, pdf in enumerate(pdfs, 1):
        if pdf.stem in done:
            continue
        try:
            pr = subprocess.run([sys.executable, str(Path(__file__).resolve()),
                                 "--doc", str(pdf)],
                                capture_output=True, text=True, timeout=180)
            lines = [l for l in pr.stdout.strip().splitlines()
                     if l.startswith("{")]
            if pr.returncode != 0 or not lines:
                st.setdefault("failed", []).append(pdf.stem)
                print(f"[{i}/{len(pdfs)}] FAIL {pdf.stem}: {pr.stderr[-200:]}")
            else:
                pl = json.loads(lines[-1])
                if pl["stem"] is None:
                    print(f"[{i}/{len(pdfs)}] skip {pdf.stem}")
                else:
                    for r in pl["txn"]:
                        with txn_jsonl.open("a", encoding="utf-8") as fh:
                            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
                    for r in pl["bunker"]:
                        with bun_jsonl.open("a", encoding="utf-8") as fh:
                            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
                    done.add(pdf.stem)
                    print(f"[{i}/{len(pdfs)}] ok {pdf.stem} "
                          f"(txn={len(pl['txn'])} bun={len(pl['bunker'])})")
        except subprocess.TimeoutExpired:
            st.setdefault("failed", []).append(pdf.stem)
            print(f"[{i}/{len(pdfs)}] TIMEOUT {pdf.stem}")
        st["done"] = sorted(done)
        _save_state(st)

    def load(path):
        rows = []
        if path.exists():
            for ln in path.read_text(encoding="utf-8").splitlines():
                try:
                    rows.append(json.loads(ln))
                except Exception:
                    pass
        return rows
    trows = _dedup(load(txn_jsonl),
                   ("issue_date", "vessel_name", "dwt", "price_raw"))
    trows.sort(key=lambda r: (r["issue_date"], r["page"], r["vessel_name"]))
    brows = _dedup(load(bun_jsonl), ("issue_date", "week_label", "grade"))
    brows.sort(key=lambda r: (r["issue_date"], r["week_label"], r["grade"]))
    OUT_SERIES.mkdir(parents=True, exist_ok=True)
    for path, fields, rows in ((TXN_CSV, TXN_FIELDS, trows),
                               (BUN_CSV, BUN_FIELDS, brows)):
        with path.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
        print(f"CSV {path.name} rows={len(rows)}")
    print(f"done={len(done)} failed={len(st.get('failed', []))} "
          f"in {time.time() - t0:.0f}s")


def run_one(pdf_path):
    rec = parse_doc(pdf_path)
    if rec is None:
        return None
    write_doc(rec)
    return rec


if __name__ == "__main__":
    if "--doc" in sys.argv:
        rec = run_one(sys.argv[sys.argv.index("--doc") + 1])
        if rec is None:
            print(json.dumps({"stem": None}))
        else:
            print(json.dumps({"stem": rec["stem"],
                              "issue_date": rec["issue_date"],
                              "txn": txn_rows(rec),
                              "bunker": bunker_rows(rec)}))
    else:
        run_all()
