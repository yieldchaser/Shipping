"""Per-source runner: GOLDEN_DESTINY (corpus/archive/golden_destiny, 252 PDFs, 2021-2024).

Source-by-source pipeline (user rule). Two document classes:
  * Weekly-SP-Market-Report        (multi-page 4-9): prose-anchored S&P deals.
  * Special-Edition-Weekly-SP-Market-Trends (1 page): aggregate stat cards.

DELIVERABLE:
  * data/extracted/md/golden_destiny/<year>/<stem>.md          (PRIMARY, full text)
  * data/extracted/md/golden_destiny/<year>/<stem>.tables.json (parsed tables)
  * data/extracted/series/golden_destiny_sales_series.csv      (prose deals)

MEASURED FACTS (docs/golden_destiny_survey.md):
  * Deals are PROSE, not a grid: NAME / "<dwt> DWT BLT <yy> ..." / "SOLD FOR
    ABT US $<x> MIL TO <buyer>" / a per-unit value (US$/Dwt|Cbm|Teu) or N/A.
  * Numbers are MIXED in the SAME doc: comma-decimal (15,8=15.8) AND
    period-thousands (252.000=252000) AND period-decimal prices (26.5).
    Parse BY SHAPE; never one global switch.
  * EN-BLOC: one SOLD line covers several preceding vessels. "EACH" = per
    vessel; a group total must NOT sit in a per-vessel price column (lion lesson).
"""
import csv, json, re, subprocess, sys, time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SRC_DIR = REPO / "corpus" / "archive" / "golden_destiny"
OUT_MD = REPO / "data" / "extracted" / "md" / "golden_destiny"
OUT_SERIES = REPO / "data" / "extracted" / "series"
STATE = OUT_MD / "_run_state.json"
DEALS_CSV = OUT_SERIES / "golden_destiny_sales_series.csv"


def _clean(s):
    return re.sub(r"\s+", " ", s).strip()


def num_by_shape(s):
    """Parse a numeric token by its SHAPE (mixed convention)."""
    if s is None:
        return None
    s = s.strip().replace("$", "").replace(" ", "")
    if not s or not re.search(r"\d", s):
        return None
    neg = s.startswith("-")
    s = s.lstrip("+-")
    try:
        if "," in s and "." in s:
            if s.rfind(",") > s.rfind("."):        # 1.234,5 -> 1234.5
                v = float(s.replace(".", "").replace(",", "."))
            else:                                   # 1,234.5 -> 1234.5
                v = float(s.replace(",", ""))
        elif "," in s:
            parts = s.split(",")
            if len(parts) == 2 and len(parts[1]) == 3 and len(parts[0]) >= 1:
                # "166,000" thousands   vs   "15,8" decimal (2 != 3 digits)
                v = float(s.replace(",", ""))
            elif len(parts) == 2:
                v = float(parts[0] + "." + parts[1])   # 15,8 -> 15.8
            else:
                v = float(s.replace(",", ""))
        elif "." in s:
            parts = s.split(".")
            if len(parts) == 2 and len(parts[1]) == 3:
                v = float(s.replace(".", ""))          # 252.000 -> 252000
            else:
                v = float(s)                           # 26.5 -> 26.5
        else:
            v = float(s)
        return -v if neg else v
    except ValueError:
        return None


def find_issue_date(stem, doc):
    """Publisher cover line first, then filename, then ISO in text."""
    for pg in doc[:2]:
        m = re.search(r"(January|February|March|April|May|June|July|August|"
                      r"September|October|November|December)\s+(\d{1,2})"
                      r"(?:st|nd|rd|th)?\s*[, ]?\s*(\d{4})\b", pg.get_text(), re.I)
        if m:
            mo = ["january","february","march","april","may","june","july",
                  "august","september","october","november","december"].index(
                      m.group(1).lower()) + 1
            return f"{m.group(3)}-{mo:02d}-{int(m.group(2)):02d}"
    m = re.search(r"(20\d{2})[_\-](\d{2})[_\-](\d{2})", stem)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
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


SECTIONS = {"BULK CARRIERS", "TANKERS", "GAS TANKERS", "CONTAINERS",
            "GENERAL CARGO", "REEFERS", "SPECIAL PROJECTS", "RO - RO", "RO-RO",
            "CAR CARRIER", "COMBINED", "PASSENGER / CRUISE", "BULK CARRIERS"}
SPEC_RX = re.compile(r"([\d][\d,\.]*)\s*DWT\s+BLT\s+(\d{2})\b")
# NOTE: the page prints the label as "US$/Cbm" - anchored .match() never
# matched it, so every row defaulted to US$/Dwt (measured 2026-10-07).
UNIT_RX = re.compile("/(Dwt|Cbm|Teu)(?![A-Za-z])", re.I)
SOLD_RX = re.compile(r"\bSOLD\b")
NAME_OK = re.compile(r"^[A-Z][A-Z0-9 .&'/_()-]{1,44}$")


def _is_name(s):
    if not s or not NAME_OK.match(s):
        return False
    up = s.strip()
    if up in SECTIONS:
        return False
    if re.search(r"DWT|BLT|SOLD|US\$|RESEARCH|VALUATION|EMAIL|WEBSITE|TEL|REPORT",
                 up, re.I):
        return False
    if up.endswith(":"):
        return False
    if not re.search(r"[A-Z]{2,}", up):
        return False
    return True


def _page_layout(page):
    """Section headings and unit labels WITH their y coordinate.

    Golden Destiny prints the section title in a right-hand cell on the SAME
    line as the block's first vessel, so the linear text order puts the heading
    AFTER its own vessels (and a page can carry 4+ sections). Labelling a row by
    "whatever heading came last on the page" therefore mislabels every row on a
    multi-section page. Only the y coordinate says which block a row is in.
    """
    heads, units, ymap = [], [], {}
    for b in page.get_text("blocks"):
        y0 = b[1]
        for line in b[4].splitlines():
            s = line.strip()
            if not s:
                continue
            ymap.setdefault(s, y0)
            if s.upper() in SECTIONS:
                heads.append((y0, s.upper()))
            if len(s) <= 12:
                m = UNIT_RX.search(s)
                if m:
                    units.append((y0, "US$/" + m.group(1).capitalize()))
    return heads, units, ymap


def _best(y, pairs, dflt):
    """Value of the pair whose y is the greatest <= y (+0.6pt); else dflt."""
    best_y, best_v = None, dflt
    for py, pv in pairs:
        if py <= y + 0.6 and (best_y is None or py > best_y):
            best_y, best_v = py, pv
    return best_v


def parse_deals_page(page, page_no, carry):
    lines = [l.strip() for l in page.get_text().splitlines()]
    heads, units, ymap = _page_layout(page)
    out = []
    buffer, last_sold_idx = [], -1
    last_y = carry.get("last_y", 0.0)
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        m = SPEC_RX.search(line)
        if m:
            y = ymap.get(line, last_y)
            last_y = max(last_y, y)
            # name = nearest preceding name-like line
            name = _clean(line[:m.start()])
            if not _is_name(name):
                name = ""
                k = i - 1
                while k >= 0:
                    if lines[k] == "":
                        k -= 1
                        continue
                    if _is_name(lines[k]):
                        name = _clean(lines[k])
                        break
                    k -= 1
            buffer.append({"name": name, "dwt": num_by_shape(m.group(1)),
                           "built": m.group(2),
                           "section": _best(y, heads, carry.get("sect", "")),
                           "unit": _best(y, units, carry.get("unit", "US$/Dwt")),
                           "page": page_no})
        elif SOLD_RX.search(line) and buffer:
            if "MIL" not in line.upper() and "UNDISCLOSED" not in line.upper():
                buffer = []          # a section header ("TONNAGE SOLD FOR DEMOLITION")
                i += 1
                continue
            price_mil = None
            pm = re.search(r"\$?\s*([\d][\d.,]*)\s*MIL", line, re.I)
            if pm:
                price_mil = num_by_shape(pm.group(1))
            undisclosed = "UNDISCLOSED" in line.upper() and price_mil is None
            each = "EACH" in line.upper()
            bm = re.search("(?<![A-Za-z])TO[ ]*(.+?)(?:[ ]*[-.][ ]*|[ ]*$)", line, re.I)
            buyer = _clean(bm.group(1)) if bm else ""
            buyer = re.sub("(?<![A-Za-z])BYRS?[.]?$", "", buyer).strip(" .-")
            # per-unit value: first following line that is a pure number or N/A
            pv = None
            j = i + 1
            while j < n:
                t = lines[j].strip()
                if t == "" or re.match(r"^\(.*\)$", t):
                    j += 1
                    continue
                if t.upper() == "N/A":
                    break
                if re.match(r"^-?[\d][\d.,]*$", t):
                    pv = num_by_shape(t)
                break
            group_total = (len(buffer) > 1 and not each)
            for b in buffer:
                row = dict(b)
                row.update({
                    "price_mil": None if group_total else price_mil,
                    "price_raw": (f"{price_mil} MIL" if price_mil is not None
                                  else ("UNDISCLOSED" if undisclosed else "")),
                    "per_vessel": ("" if group_total else ("each" if each else "")),
                    "group_total_mil": price_mil if group_total else None,
                    "buyer": buyer,
                    "per_unit": pv,
                    "comment": line.strip(),
                    "sold_text": line.strip(),
                })
                out.append(row)
            buffer = []
        i += 1
    return out, last_y


DEAL_FIELDS = ["issue_date", "report_week", "section", "vessel_name", "dwt",
               "built_year", "price_usd_m", "price_raw", "per_vessel",
               "group_total_mil", "buyer", "per_unit", "per_unit_label",
               "doc_class", "source_file", "page"]


def doc_class(stem):
    return ("special_edition" if "Special-Edition" in stem
            else "weekly_report")


def parse_doc(pdf_path):
    import pymupdf
    doc = pymupdf.open(pdf_path)
    stem = pdf_path.stem
    issue = find_issue_date(stem, doc)
    week = report_week(stem, doc)
    pages_txt = [p.get_text() for p in doc]
    deals = []
    carry = {"sect": "", "unit": "US$/Dwt", "last_y": 0.0}
    for idx, pg in enumerate(doc):
        rows, last_y = parse_deals_page(pg, idx, carry)
        deals.extend(rows)
        carry["sect"] = _best(last_y, _page_layout(pg)[0], carry["sect"])
        carry["unit"] = _best(last_y, _page_layout(pg)[1], carry["unit"])
        carry["last_y"] = last_y
    n_pages = doc.page_count
    doc.close()
    return dict(stem=stem, year=pdf_path.parent.name, issue_date=issue,
                report_week=week, n_pages=n_pages, pages=pages_txt,
                deals=deals, cls=doc_class(stem))


def deal_rows(rec):
    rows = []
    for d in rec["deals"]:
        rows.append({
            "issue_date": rec["issue_date"], "report_week": rec["report_week"],
            "section": d.get("section", ""), "vessel_name": d.get("name", ""),
            "dwt": d.get("dwt"), "built_year": d.get("built", ""),
            "price_usd_m": d.get("price_mil"), "price_raw": d.get("price_raw", ""),
            "per_vessel": d.get("per_vessel", ""),
            "group_total_mil": d.get("group_total_mil"),
            "buyer": d.get("buyer", ""), "per_unit": d.get("per_unit"),
            "per_unit_label": d.get("unit", ""), "doc_class": rec["cls"],
            "source_file": rec["source_file"].name, "page": d.get("page")})
    return rows


def write_doc(rec):
    ydir = OUT_MD / rec["year"]
    ydir.mkdir(parents=True, exist_ok=True)
    header = (f"# Golden Destiny {rec['cls'].replace('_',' ').title()}\n\n"
              f"Issue: Week {rec['report_week']:02d} | {rec['issue_date']}\n\n")
    body = "\n\n".join(p.strip() for p in rec["pages"])
    (ydir / f"{rec['stem']}.md").write_text(header + body, encoding="utf-8")
    payload = {"issue_date": rec["issue_date"], "report_week": rec["report_week"],
               "source_file": str(rec["source_file"]), "stem": rec["stem"],
               "doc_class": rec["cls"],
               "tables": {"deals": [{
                   "vessel_name": d.get("name", ""), "dwt": d.get("dwt"),
                   "built_year": d.get("built", ""), "section": d.get("section", ""),
                   "price_usd_m": d.get("price_mil"), "price_raw": d.get("price_raw", ""),
                   "per_vessel": d.get("per_vessel", ""), "buyer": d.get("buyer", ""),
                   "per_unit": d.get("per_unit"), "page": d.get("page")}
                   for d in rec["deals"]]}}
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
                                "--doc", str(pdf)], capture_output=True,
                               text=True, timeout=180)
            line = [l for l in r.stdout.strip().splitlines() if l.startswith("{")]
            if r.returncode != 0 or not line:
                st.setdefault("failed", []).append(pdf.stem)
                print(f"[{i}/{len(pdfs)}] FAIL {pdf.stem}: {r.stderr[-200:]}")
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
        st["done"] = sorted(done)
        _save_state(st)
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
        seen.add(k)
        uniq.append(r)
    uniq.sort(key=lambda r: (r["issue_date"], r["page"] or 0))
    OUT_SERIES.mkdir(parents=True, exist_ok=True)
    with DEALS_CSV.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=DEAL_FIELDS)
        w.writeheader()
        w.writerows(uniq)
    print(f"CSV {DEALS_CSV} rows={len(uniq)} (from {len(rows)} raw)")
    print(f"done={len(done)} failed={len(st.get('failed', []))} in {time.time()-t0:.0f}s")


if __name__ == "__main__":
    if "--doc" in sys.argv:
        rec = run_one(sys.argv[sys.argv.index("--doc") + 1])
        print(json.dumps({"stem": rec["stem"], "n_deals": len(rec["deals"]),
                          "rows": deal_rows(rec)}))
    else:
        run_all()
