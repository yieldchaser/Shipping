#!/usr/bin/env python3
"""Pilbara Ports Authority (PPA) per-source extractor. Source: corpus/09-ppa (493 PDFs).

FAMILIES (measured, docs/ppa_survey.md):
 A "Cargo Stats by Origin/Destination" (Port Hedland) 255 docs, 2 pages, RULED GRID.
   page0 = DISCHARGE, page1 = LOAD. Table = countries x commodities + Total row/col.
 B "PORT OF DAMPIER <FY> FINANCIAL YEAR CARGO STATISTICS" 83 docs, 1 page, BORDERLESS.
   19 are rotation=90 (sideways text) - handled via page.rotation_matrix.
 C "Cargo, GRT and DWT Statistics by Commodity Group" 152 docs, 6-9 pages, PER-VESSEL.
   Surveyed only (not parsed here).

THREE-BASELINE TEST: data/commodities/australia_ppa_iron_ore.csv already holds IRON ORE
+ TOTAL per month for both ports (423 rows, from these same PDFs) and index.html already
displays it. So the IRON ORE slice is ALREADY OURS. Genuinely missing = the full
COMMODITY x COUNTRY matrix for LOAD and DISCHARGE. That is what this runner produces.

VALIDATION IS ARITHMETIC: every family-A table prints a Total row AND Total column, every
family-B table prints a TOTALS: row. Each parsed table is checked against its own printed
totals; pass/fail counts are recorded per table.
"""
import argparse, collections, json, re, time
from pathlib import Path

import pymupdf
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
CORPUS = ROOT / "corpus" / "09-ppa"
OUTDIR = ROOT / "data" / "extracted" / "ppa"
OUTDIR.mkdir(parents=True, exist_ok=True)


NUMRE = re.compile("^-?[0-9,]+(?:[.][0-9]+)?$")
VESSELCOL = re.compile("VESSEL|ARRIVAL|TRADE|VALIDATION|VARIANCE", re.I)


def rel(path):
    try:
        return str(Path(path).resolve().relative_to(ROOT)).replace(chr(92), "/")
    except Exception:
        return str(path).replace(chr(92), "/")


def num(tok):
    """PPA numbers are ISO: comma = thousands, period = decimal."""
    if tok is None:
        return None
    t = tok.strip().replace("\u2212", "-")
    if t in ("", "-", "\u2013", "\u2014"):
        return None
    t = t.replace(",", "")
    if not re.fullmatch(r"-?\d+(?:\.\d+)?", t):
        return None
    return float(t)


def join_cell(words):
    """Concatenate a cell's word fragments in x order.

    PPA splits numbers across two text spans with a real gap ('1' + '520,746' = 1520746,
    '1,' + '44,068' = 144068). Concatenating with no separator is what reproduces the
    printed value; the arithmetic check is what proves it.
    """
    ws = sorted(words, key=lambda w: (round(w[1], 1), w[0]))
    if not ws:
        return ""
    out = ws[0][4]
    for prev, w in zip(ws, ws[1:]):
        same_line = abs(w[1] - prev[1]) < 2.0
        out += ("" if (same_line and w[0] - prev[2] < 1.2) else " ") + w[4]
    return out


def grid_lines(page):
    xs, ys = collections.Counter(), collections.Counter()
    for d in page.get_drawings():
        for it in d["items"]:
            if it[0] == "l":
                (x0, y0), (x1, y1) = it[1], it[2]
                if abs(x0 - x1) < 0.5:
                    xs[round(x0, 1)] += 1
                elif abs(y0 - y1) < 0.5:
                    ys[round(y0, 1)] += 1
            elif it[0] == "re":
                r = it[1]
                for x in (r.x0, r.x1):
                    xs[round(x, 1)] += 1
                for y in (r.y0, r.y1):
                    ys[round(y, 1)] += 1
    return (sorted(x for x, c in xs.items() if c >= 2),
            sorted(y for y, c in ys.items() if c >= 2))


def table_from_grid(page, xv, yv):
    cells = collections.defaultdict(list)
    for w in page.get_text("words"):
        cx, cy = (w[0] + w[2]) / 2, (w[1] + w[3]) / 2
        ci = ri = None
        for i in range(len(xv) - 1):
            if xv[i] <= cx < xv[i + 1]:
                ci = i
                break
        for j in range(len(yv) - 1):
            if yv[j] <= cy < yv[j + 1]:
                ri = j
                break
        if ci is not None and ri is not None:
            cells[(ri, ci)].append(w)
    return [[join_cell(cells.get((r, c), [])) for c in range(len(xv) - 1)]
            for r in range(len(yv) - 1)]


def month_from_range(text):
    """PPA mixes conventions in one document: 'Cargo Complete Date: 01/07/2026 to
    31/07/2026' is D/M/Y while 'Departure Date: 07/01/2026 to 07/31/2026' is M/D/Y.
    Take the interpretation under which both endpoints share one month.
    Anchor on the reporting-period LINE: the page also prints 'Printed: ... 8/10/2026'
    (the print timestamp, a third date), which must not enter the vote."""
    scope = text
    for ln in text.splitlines():
        low = ln.lower()
        if ("complete date" in low or "departure date" in low
                or "arrival date" in low):
            scope = ln
            break
    pairs = re.findall(r"(\d{1,2})/(\d{1,2})/(\d{4})", scope)[:2]
    if not pairs:
        return None
    for order in ("dm", "md"):
        months = {int(a if order == "dm" else b) for a, b, _ in pairs}
        years = {int(c) for _, _, c in pairs}
        if len(months) == 1 and len(years) == 1:
            m, y = months.pop(), years.pop()
            if 1 <= m <= 12:
                return "%04d-%02d-01" % (y, m)
    return None


# ------------------------------------------------------------------ family A
def parse_hedland(path):
    doc = pymupdf.open(str(path))
    flat = doc[0].get_text()
    if "Cargo Stats by Origin" in flat:
        kind = "origin"
    elif "Cargo Stats by Destination" in flat:
        kind = "destination"
    else:
        doc.close()
        return None, "not-a-cargo-stats-doc"
    date, tables, checks = None, [], []
    for page in doc:
        txt = page.get_text()
        d = month_from_range(txt)
        if d and date is None:
            date = d
        # the direction word is printed on the page ("DISCHARGE"/"Discharge", "LOAD"/"Load");
        # the 2015-era summary files title both pages "by Destination" while one is a
        # Discharge table, so the printed word wins over the title
        if re.search("DISCHARGE", txt, re.I):
            direction = "DISCHARGE"
        elif re.search("LOAD", txt, re.I):
            direction = "LOAD"
        else:
            direction = "DISCHARGE" if "by Origin" in txt else "LOAD"
        xv, yv = grid_lines(page)
        if len(xv) < 4 or len(yv) < 4:
            continue
        words = page.get_text("words")
        # The 2015-era "summary" files draw rules around the DATA cells only: the country
        # label column and the header row sit outside the drawn grid, so the first parsed
        # row is all numbers.  Recover both from the words themselves (measured on
        # ppa_cargo_stats_by_destination_summary_january_2015_pdf.pdf).
        left = min((w[0] for w in words
                    if yv[0] <= (w[1] + w[3]) / 2 <= yv[-1]), default=None)
        if left is not None and left < xv[0] - 1:
            xv = [left - 1] + xv
        grid = table_from_grid(page, xv, yv)
        if len(grid) < 3:
            continue
        if all((not c.strip()) or NUMRE.match(c.strip()) for c in grid[0][1:]):
            pitch = (yv[-1] - yv[0]) / max(1, len(yv) - 1)
            cand = [w for w in words if yv[0] - 1.6 * pitch <= (w[1] + w[3]) / 2 < yv[0]
                    and xv[0] <= (w[0] + w[2]) / 2 <= xv[-1]]
            if cand:
                yv = [min(w[1] for w in cand) - 1] + yv
                grid = table_from_grid(page, xv, yv)
        header = [h.strip() for h in grid[0]]
        body = grid[1:]
        total_row = body[-1] if body and body[-1][0].strip().lower().startswith("total") else None
        country_rows = body[:-1] if total_row else body
        ok = bad = 0
        detail = []
        # column check: sum of country cells == the printed Total-row cell
        if total_row:
            for c in range(1, min(len(header), len(total_row))):
                vals = [num(r[c]) for r in country_rows if c < len(r)]
                vals = [v for v in vals if v is not None]
                tv = num(total_row[c])
                if tv is None or not vals:
                    continue
                if abs(sum(vals) - tv) < 0.51:
                    ok += 1
                else:
                    bad += 1
                    detail.append({"col": header[c], "sum": round(sum(vals), 2), "printed": tv})
        # row check: sum of commodity cells == that row's Total cell (last column).
        # Only valid when the last column actually IS the Total column.
        has_total_col = bool(header) and header[-1].strip().lower().startswith("total")
        for r in (country_rows if has_total_col else []):
            vals = [num(v) for v in r[1:-1]]
            vals = [v for v in vals if v is not None]
            tv = num(r[-1])
            if tv is None or not vals:
                continue
            if abs(sum(vals) - tv) < 0.51:
                ok += 1
            else:
                bad += 1
                detail.append({"row": r[0], "sum": round(sum(vals), 2), "printed": tv})
        checks.append({"page": page.number, "direction": direction, "ok": ok, "bad": bad,
                       "header": header, "mismatches": detail[:5]})
        tables.append({"direction": direction, "header": header,
                       "rows": [r for r in country_rows if r[0].strip()], "total": total_row})
    doc.close()
    if not tables:
        # e.g. the "Cargo Stats by Destination - Detailed" per-vessel listings:
        # the title matches family A but there is no country x commodity grid.
        return None, "no-cargo-grid"
    return {"date": date, "kind": kind, "tables": tables, "checks": checks}, None


def hedland_rows(path, parsed):
    """Long format: one row per (date, direction, commodity, country)."""
    path = Path(path)
    out = []
    for t in parsed["tables"]:
        for r in t["rows"]:
            country = r[0].strip()
            for c in range(1, min(len(t["header"]), len(r))):
                commodity = t["header"][c].strip()
                v = num(r[c])
                if v is None or not commodity or commodity.lower() == "total":
                    continue
                out.append({"date": parsed["date"], "port": "Port Hedland",
                            "direction": t["direction"], "commodity": commodity,
                            "country": country, "tonnes": v,
                            "source_file": rel(path)})
        if t["total"]:
            tr = t["total"]
            for c in range(1, min(len(t["header"]), len(tr))):
                v = num(tr[c])
                commodity = t["header"][c].strip()
                if v is None or not commodity or commodity.lower() == "total":
                    continue
                out.append({"date": parsed["date"], "port": "Port Hedland",
                            "direction": t["direction"], "commodity": commodity,
                            "country": "TOTAL", "tonnes": v,
                            "source_file": rel(path)})
    return out


# ------------------------------------------------------------------ family B
MONTHS = ["JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER",
          "JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE"]


def _dampier_words(page):
    M = page.rotation_matrix
    out = []
    for w in page.get_text("words"):
        r = pymupdf.Rect(w[:4]) * M
        out.append((r.x0, r.y0, r.x1, r.y1, w[4]))
    return out


def _dampier_cols(words):
    """Derive column bands from the page's OWN data rows, then name them from the page's
    OWN header words.  Nothing is a hardcoded x: the 2006-07 file is the same table at a
    smaller scale (IRON spans x 85.9-129.2 where 2025-26 spans 103.4-137.6), so a fixed
    coordinate would silently drop or merge a column.

    Values are RIGHT-aligned to a fixed right edge, and the TOTALS row holds wider numbers
    than the month rows ('154,222,703' starts at 83.2 where '8,922,182' starts at 93.8 but
    both end at 132.8).  Clustering on the LEFT edge therefore bridges two columns; cluster
    on the RIGHT edge.
    """
    month_ys = sorted({round(w[1], 1) for w in words if w[4] in MONTHS})
    if not month_ys:
        return None, None
    first_y = month_ys[0]
    pitch = (month_ys[-1] - first_y) / max(1, len(month_ys) - 1)
    tot_y = [w[1] for w in words if w[4].upper().startswith("TOTALS")]
    tot_y = min(tot_y) if tot_y else None
    # cluster on MONTH rows only: the TOTALS row prints wider numbers ('154,222,703' vs
    # '12,227,510') whose right edge lands outside the month band and would split a column
    data = [w for w in words if w[1] >= first_y - 1
            and (NUMRE.match(w[4].strip()) or w[4].strip() in ("-", "--"))
            and (tot_y is None or w[1] < tot_y - 2)]
    if not data:
        return None, None
    bands = []
    for w in sorted(data, key=lambda w: w[2]):
        if bands and w[2] - bands[-1]["x1"] <= 20:
            bands[-1]["x1"] = max(bands[-1]["x1"], w[2])
            bands[-1]["x0"] = min(bands[-1]["x0"], w[0])
        else:
            bands.append({"x0": w[0], "x1": w[2], "words": []})
    if len(bands) < 4:
        return None, None
    mon = [w[1] for w in words if w[4] == "MONTH"]
    if not mon:
        return None, None          # not a Dampier FY table (no MONTH header row)
    mon_y = min(mon)
    header = [w for w in words
              if mon_y - 0.6 * pitch <= w[1] <= mon_y + 1.3 * pitch]
    centres = sorted((b["x0"] + b["x1"]) / 2 for b in bands)
    bpitch = sorted(b - a for a, b in zip(centres, centres[1:]))
    bpitch = bpitch[len(bpitch) // 2] if bpitch else 50.0
    tol = max(20.0, bpitch * 0.6)
    for w in header:
        cx = (w[0] + w[2]) / 2
        dists = [abs(cx - (b["x0"] + b["x1"]) / 2) for b in bands]
        i = dists.index(min(dists))
        if dists[i] <= tol:
            bands[i]["words"].append(w)
    names = []
    for b in bands:
        ws = sorted(b["words"], key=lambda w: (round(w[1], 1), w[0]))
        toks = [w[4] for w in ws]
        if len(toks) >= 3 and toks[0].upper() == "TOTAL":
            toks = toks[1:]
        names.append(" ".join(toks).strip())
    return bands, names


def parse_dampier(path):
    doc = pymupdf.open(str(path))
    page = doc[0]
    txt = page.get_text()
    m = re.search(r"(20\d\d)\s*-\s*(20\d\d)\s+FINANCIAL YEAR", txt)
    fy = "%s-%s" % (m.group(1), m.group(2)) if m else None
    words = _dampier_words(page)
    cols, names = _dampier_cols(words)
    if cols is None:
        doc.close()
        return None, "no-month-rows"
    first_y = min(w[1] for w in words if w[4] in MONTHS)
    buckets = collections.defaultdict(list)
    for w in words:
        if w[1] >= first_y - 1:
            buckets[round(w[1] / 3.0)].append(w)
    merged = []
    for k in sorted(buckets):
        cy = sum(w[1] for w in buckets[k]) / len(buckets[k])
        if merged and abs(cy - merged[-1]["y"]) < 3.0:
            merged[-1]["words"].extend(buckets[k])
            merged[-1]["y"] = (merged[-1]["y"] + cy) / 2
        else:
            merged.append({"y": cy, "words": list(buckets[k])})
    out_rows, ok, bad, detail = [], 0, 0, []
    for mr in merged:
        ws = mr["words"]
        lab = [w for w in sorted(ws, key=lambda w: w[0]) if w[4] in MONTHS]
        if lab:
            label = lab[0][4]
        elif any(w[4].upper().startswith("TOTALS") for w in ws):
            label = "TOTALS:"
        else:
            continue
        cells = collections.defaultdict(list)
        for w in ws:
            if w[4] in MONTHS or w[4].upper().startswith("TOTALS"):
                continue
            cx = (w[0] + w[2]) / 2
            idx = None
            for i, c in enumerate(cols):
                if c["x0"] - 4 <= cx <= c["x1"] + 4:
                    idx = i
                    break
            if idx is None:
                cs = [abs(cx - (c["x0"] + c["x1"]) / 2) for c in cols]
                idx = cs.index(min(cs))
            cells[idx].append(w)
        vals = {}
        for i, v in cells.items():
            key = names[i] if i < len(names) else "col%d" % i
            if key in vals:
                key = key + "_2"
            vals[key] = join_cell(v)
        out_rows.append({"month_label": label, "values": vals})
    for r in out_rows:
        v = r["values"]
        tot_key = next((k for k in v if "TOTAL" in k.upper() and "CARGO" in k.upper()), None)
        if tot_key is None:
            tot_key = next((k for k in v if k.strip().upper().startswith("TOTAL")), None)
        if tot_key is None:
            continue
        parts = [num(val) for k, val in v.items()
                 if k != tot_key and not VESSELCOL.search(k)]
        parts = [p for p in parts if p is not None]
        tv = num(v[tot_key])
        if tv is None or not parts:
            continue
        if abs(sum(parts) - tv) <= max(1.5, 1e-6 * abs(tv)):
            ok += 1
        else:
            bad += 1
            detail.append({"month": r["month_label"], "sum": round(sum(parts), 2), "printed": tv})
    doc.close()
    return {"fy": fy, "cols": names, "rows": out_rows,
            "check": {"ok": ok, "bad": bad, "mismatches": detail[:5]}}, None


def dampier_rows(path, parsed):
    fy = parsed["fy"]
    start = int(fy.split("-")[0]) if fy else None
    out = []
    src = rel(path)
    for r in parsed["rows"]:
        lab = r["month_label"]
        date = None
        if lab != "TOTALS:" and start:
            i = MONTHS.index(lab)
            y = start if i <= 5 else start + 1
            date = "%04d-%02d-01" % (y, i + 7 if i <= 5 else i - 5)
        for k, v in r["values"].items():
            val = num(v)
            if val is None:
                continue
            out.append({"date": date, "fy": fy, "month_label": lab, "port": "Port of Dampier",
                        "metric": k, "value": val, "source_file": src})
    return out


def load_jsonl(p):
    done = {}
    if p.exists():
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                o = json.loads(line)
            except Exception:
                continue           # torn last line from a crash is normal
            done[o["file"]] = o
    return done


def append_jsonl(p, obj):
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(obj) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--family", choices=["hedland", "dampier", "all"], default="all")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--files", nargs="*", default=None, help="explicit files (trial mode)")
    args = ap.parse_args()

    files = []
    if args.files:
        files = [Path(f) if Path(f).is_absolute() else ROOT / f for f in args.files]
    else:
        # Corpus reorg (2026-10) moved 110 PPA PDFs from the two subdirs to the
        # corpus root; without the third glob those files are invisible to the
        # extractor.  Top-level last so the existing jsonl/CSV row order is kept.
        files = (sorted(CORPUS.glob("_root_pdfs/*.pdf"))
                 + sorted(CORPUS.glob("ppa_pdf/*.pdf"))
                 + sorted(CORPUS.glob("*.pdf")))
    if args.limit:
        files = files[:args.limit]

    for fam in (["hedland", "dampier"] if args.family == "all" else [args.family]):
        ck = OUTDIR / ("%s_rows.jsonl" % fam)
        statep = OUTDIR / ("%s_state.json" % fam)
        done = load_jsonl(ck) if args.resume else {}
        state = json.loads(statep.read_text()) if (args.resume and statep.exists()) else {}
        state.setdefault("done", [])
        state.setdefault("failed", [])
        state.setdefault("skipped", [])
        state.setdefault("checks", [])
        t0 = time.time()
        n = 0
        for f in files:
            key = rel(f)
            if key in done:
                continue
            n += 1
            try:
                if fam == "hedland":
                    parsed, err = parse_hedland(f)
                else:
                    parsed, err = parse_dampier(f)
            except Exception as exc:  # noqa: BLE001
                state["failed"].append({"file": key, "err": "%s: %s" % (type(exc).__name__, exc)})
                print("FAIL", key, exc, flush=True)
                continue
            if parsed is None:
                state["skipped"].append({"file": key, "reason": err})
                continue
            rows = hedland_rows(f, parsed) if fam == "hedland" else dampier_rows(f, parsed)
            rec = {"file": key, "rows": rows,
                   "check": parsed.get("checks") if fam == "hedland" else parsed.get("check")}
            append_jsonl(ck, rec)
            done[key] = rec
            state["done"].append(key)
            if fam == "hedland":
                for c in parsed["checks"]:
                    state["checks"].append({"file": key, "page": c["page"],
                                            "direction": c["direction"], "ok": c["ok"],
                                            "bad": c["bad"]})
            else:
                state["checks"].append({"file": key, "fy": parsed["fy"],
                                        "ok": parsed["check"]["ok"], "bad": parsed["check"]["bad"]})
            if n % 25 == 0:
                statep.write_text(json.dumps(state))
                print("[%s] %d processed, %.1fs" % (fam, n, time.time() - t0), flush=True)
        statep.write_text(json.dumps(state))
        print("[%s] DONE processed=%d skipped=%d failed=%d in %.1fs"
              % (fam, n, len(state["skipped"]), len(state["failed"]), time.time() - t0), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
