"""Per-source runner: SEASURE ("S&P Summary Sales", corpus/archive/other, 86 PDFs, 2021-2023).

Deliverable:
  * data/extracted/md/seasure/<year>/<stem>.md            (PRIMARY, full text)
  * data/extracted/md/seasure/<year>/<stem>.tables.json   (parsed deals)
  * data/extracted/series/seasure_sales_series.csv        (deal grid)

MEASURED (docs/seasure_survey.md): numbers ISO ("58,100"=58100; "15.8"=15.8).
Geometry STABLE 2021-2023; anchors re-derived per page from its own header row.
A vessel row is anchored on its DWT numeric.
"""
import csv, json, re, subprocess, sys, time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SRC_DIR = REPO / "corpus" / "archive" / "other"
OUT_MD = REPO / "data" / "extracted" / "md" / "seasure"
OUT_SERIES = REPO / "data" / "extracted" / "series"
STATE = OUT_MD / "_run_state.json"
DEALS_CSV = OUT_SERIES / "seasure_sales_series.csv"

SECTIONS = {"BULKER", "TANKER", "CONTAINER"}
HEADER_LABELS = {"Name", "Type", "DWT", "Yard", "Built", "USD", "mill",
                 "Comments", "VV", "Buyer", "Seller"}
COLS = ["Name", "Type", "DWT", "Yard", "Built", "USD", "Comments", "VV", "Buyer", "Seller"]
MONTHS = {m.lower(): i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"], 1)}


def is_seasure(doc):
    t = " ".join(doc[i].get_text() for i in range(len(doc))).lower()
    return "seasure" in t or "s&p summary sales" in t


def issue_date(stem):
    m = re.search(r"(\d{1,2})[- ]([A-Za-z]+)[- ](\d{4})", stem)
    if m:
        key = m.group(2).lower()
        mon = next((v for k, v in MONTHS.items() if k.startswith(key)), None)
        if mon:
            return f"{int(m.group(3)):04d}-{mon:02d}-{int(m.group(1)):02d}"
    return ""


def _header_anchors(page):
    words = page.get_text("words")
    groups = []
    for w in sorted(words, key=lambda w: w[1]):
        if groups and abs(w[1] - groups[-1][0]) <= 2:
            groups[-1][1].append(w)
        else:
            groups.append([w[1], [w]])
    best = None
    for y, ws in groups:
        d = {}
        for w in ws:
            if w[4] in COLS and w[4] not in d:
                d[w[4]] = w[0]
        if "Name" in d and "DWT" in d and "Buyer" in d and len(d) >= 8:
            if best is None or y < best[0]:
                best = (y, d)
    return best


def _bounds(a):
    order = [c for c in COLS if c in a]
    xs = [a[c] for c in order]
    b = {}
    for i in range(len(order) - 1):
        lo, hi = order[i], order[i + 1]
        if lo == "Yard":
            b[lo] = a["Built"] - 4
        elif lo == "Comments":
            b[lo] = a["VV"] - 10
        else:
            b[lo] = (xs[i] + xs[i + 1]) / 2
    b[order[-1]] = 1e9
    return order, b


def _col_of(x, order, b):
    for c in order:
        if x < b[c]:
            return c
    return order[-1]


def parse_deals(page, page_no):
    ha = _header_anchors(page)
    if not ha:
        return []
    hy, anchors = ha
    order, b = _bounds(anchors)
    dwt_lo, dwt_hi = anchors["DWT"] - 20, anchors["DWT"] + 25
    words = page.get_text("words")
    heads = [(w[1], w[4].upper()) for w in words
             if w[4].upper() in SECTIONS and w[0] < anchors["Type"]]
    ys = sorted(w[1] for w in words
                if dwt_lo <= w[0] <= dwt_hi
                and re.fullmatch(r"\d[\d,]*", w[4]) and w[1] > hy)
    rows_y = []
    for y in ys:
        if not rows_y or y - rows_y[-1] > 3:
            rows_y.append(y)
    deals = []
    for i, ry in enumerate(rows_y):
        lo = ry - 3
        hi = (min(rows_y[i + 1] - 1.5, ry + 7.0)
              if i + 1 < len(rows_y) else ry + 7.0)
        cells = {c: [] for c in order}
        for w in words:
            if not (lo <= w[1] < hi):
                continue
            if (w[4].upper() in SECTIONS or w[4] in HEADER_LABELS
                    or re.fullmatch(r"[-+]?\d+(?:\.\d+)?%", w[4])):
                continue
            cells[_col_of(w[0], order, b)].append((w[0], w[4]))
        dwt = " ".join(t for _, t in sorted(cells.get("DWT", [])))
        if not re.search(r"\d", dwt):
            continue
        sect = ""
        for hy2, s in heads:
            if hy2 <= ry + 3:
                sect = s

        def join(c):
            return " ".join(t for _, t in sorted(cells.get(c, []))).strip()

        def num(c):
            m = re.search(r"-?\d[\d,]*(?:\.\d+)?", join(c))
            return m.group(0) if m else ""

        deals.append({
            "vessel_name": join("Name"), "type": join("Type"),
            "dwt_raw": dwt.strip(), "yard": join("Yard"),
            "built_year": num("Built"), "price_raw": num("USD"),
            "comments": join("Comments"), "vv_raw": num("VV"),
            "buyer": join("Buyer"), "seller": join("Seller"),
            "section": sect, "page": page_no})
    return deals


def parse_doc(pdf_path):
    import pymupdf
    doc = pymupdf.open(pdf_path)
    stem = Path(pdf_path).stem
    if not is_seasure(doc):
        return None
    pages, deals = [], []
    for i in range(len(doc)):
        pages.append(doc[i].get_text())
        deals.extend(parse_deals(doc[i], i + 1))
    return {"stem": stem, "year": stem.split("_")[1] if "_" in stem else "",
            "issue_date": issue_date(stem), "pages": pages, "deals": deals,
            "source_file": pdf_path}


def write_doc(rec):
    ydir = OUT_MD / rec["year"]
    ydir.mkdir(parents=True, exist_ok=True)
    header = f"# Seasure S&P Summary Sales\n\nIssue: {rec['issue_date'] or rec['stem']}\n\n"
    body = "\n\n".join(p.strip() for p in rec["pages"])
    (ydir / f"{rec['stem']}.md").write_text(header + body, encoding="utf-8")
    payload = {"issue_date": rec["issue_date"], "stem": rec["stem"],
               "source_file": str(rec["source_file"]),
               "tables": {"deals": rec["deals"]}}
    (ydir / f"{rec['stem']}.tables.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")


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


def deal_rows(rec):
    out = []
    for d in rec["deals"]:
        def fn(s):
            if not s:
                return None
            try:
                return float(s.replace(",", ""))
            except ValueError:
                return None
        out.append({
            "issue_date": rec["issue_date"], "section": d["section"],
            "vessel_name": d["vessel_name"], "type": d["type"],
            "dwt": fn(d["dwt_raw"]), "yard": d["yard"],
            "built_year": d["built_year"], "price_usd_m": fn(d["price_raw"]),
            "price_raw": d["price_raw"], "comments": d["comments"],
            "vv_raw": d["vv_raw"], "buyer": d["buyer"], "seller": d["seller"],
            "source_file": Path(rec["source_file"]).name, "page": d["page"]})
    return out


def run_one(pdf_path):
    rec = parse_doc(pdf_path)
    if rec is None:
        return None
    write_doc(rec)
    return rec


FIELDS = ["issue_date", "section", "vessel_name", "type", "dwt", "yard",
          "built_year", "price_usd_m", "price_raw", "comments", "vv_raw",
          "buyer", "seller", "source_file", "page"]


def run_all():
    pdfs = sorted(SRC_DIR.rglob("*.pdf"))
    st = _load_state(); done = set(st["done"])
    jsonl = OUT_MD / "_deals.jsonl"
    OUT_MD.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    for i, pdf in enumerate(pdfs, 1):
        if pdf.stem in done:
            continue
        try:
            p = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--doc", str(pdf)],
                               capture_output=True, text=True, timeout=180)
            line = [l for l in p.stdout.strip().splitlines() if l.startswith("{")]
            if p.returncode != 0 or not line:
                st.setdefault("failed", []).append(pdf.stem)
                print(f"[{i}/{len(pdfs)}] FAIL {pdf.stem}: {p.stderr[-200:]}")
            else:
                payload = json.loads(line[-1])
                for row in payload["rows"]:
                    with jsonl.open("a", encoding="utf-8") as fh:
                        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                done.add(pdf.stem)
                print(f"[{i}/{len(pdfs)}] ok {pdf.stem} ({payload['n_deals']} deals)")
        except subprocess.TimeoutExpired:
            st.setdefault("failed", []).append(pdf.stem)
            print(f"[{i}/{len(pdfs)}] TIMEOUT {pdf.stem}")
        st["done"] = sorted(done); _save_state(st)
    rows = []
    if jsonl.exists():
        for ln in jsonl.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(ln))
            except Exception:
                pass
    seen, uniq = set(), []
    for r in rows:
        k = (r["source_file"], r["vessel_name"], r["dwt"], r["price_raw"])
        if k in seen:
            continue
        seen.add(k); uniq.append(r)
    uniq.sort(key=lambda r: (r["issue_date"], r["page"] or 0))
    OUT_SERIES.mkdir(parents=True, exist_ok=True)
    with DEALS_CSV.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS); w.writeheader(); w.writerows(uniq)
    print(f"CSV {DEALS_CSV} rows={len(uniq)} (from {len(rows)} raw)")
    print(f"done={len(done)} failed={len(st.get('failed', []))} in {time.time()-t0:.0f}s")


if __name__ == "__main__":
    if "--doc" in sys.argv:
        rec = run_one(sys.argv[sys.argv.index("--doc") + 1])
        if rec is None:
            print(json.dumps({"stem": None, "n_deals": 0, "rows": []}))
        else:
            print(json.dumps({"stem": rec["stem"], "n_deals": len(rec["deals"]),
                              "rows": deal_rows(rec)}))
    else:
        run_all()
