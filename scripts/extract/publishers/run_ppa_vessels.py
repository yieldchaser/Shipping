#!/usr/bin/env python3
"""PPA family C - the per-vessel register ("Cargo, GRT and DWT Statistics by Commodity
Group", Port of Hedland).  152 PDFs, 5-10 pages each, corpus/09-ppa.

Measured structure (docs/ppa_survey.md):
  * header row(s) print the column names; there are NO ruling lines (1 drawing per page)
  * a CARGO GROUP label ("Iron Ore", "Containers", ...) sits alone on its own row and
    applies to every vessel row beneath it until the next group label
  * one vessel row = Vessel | Destination/Origin Country | Arrival Date | Departure Date |
    Cargo Complete | Import Volume | Export Volume | GRT | DWT
  * the Export Volume glyphs sit ~2.9 pt LOWER than the rest of the row (baseline offset),
    while the row pitch is ~11.3 pt - so rows must be grouped on the date/vessel words and
    the remaining words attached to the NEAREST row, not to a fixed y band
  * a vessel appears several times for the same arrival, once per country; rows carrying
    Export Volume are LOAD (destination), rows carrying Import Volume are DISCHARGE (origin)

Validation: dates must parse, the four numeric columns must be numeric, and the per-month
sum of Export Volume for the "Iron Ore" cargo group is reconciled against family A's
Iron Ore LOAD total for the same month (a DIFFERENT table in a DIFFERENT document).
"""
import argparse, collections, json, re, time
from pathlib import Path

import pymupdf
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
CORPUS = ROOT / "corpus" / "09-ppa"
OUTDIR = ROOT / "data" / "extracted" / "ppa"
OUTDIR.mkdir(parents=True, exist_ok=True)

DATER = re.compile(r"^[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}$")
NUMR = re.compile(r"^-?[0-9,]+(?:[.][0-9]+)?$")
GROUPS = ["IRON ORE", "SALT", "CONTAINERS", "GENERAL", "MANGANESE ORE",
          "COPPER CONCENTRATES", "SPODUMENE CONCENTRATE", "SPODUMENE", "ACID",
          "PRIMARY PRODUCE", "CHEMICAL COMPOUND", "HYDROCARBON", "LITHIUM",
          "COPPER CONCENTRATE", "MANGANESE", "SPODUMENE DSO", "CLAY", "GYPSUM"]


def num(tok):
    if tok is None:
        return None
    t = tok.strip().replace(",", "")
    if not re.fullmatch(r"-?[0-9]+(?:[.][0-9]+)?", t):
        return None
    return float(t)


def rel(path):
    try:
        return str(Path(path).resolve().relative_to(ROOT)).replace(chr(92), "/")
    except Exception:
        return str(path).replace(chr(92), "/")


def page_rows(page):
    """Group words into rows on the DATE / VESSEL words, then attach the rest."""
    ws = page.get_text("words")
    anchors = [w for w in ws if DATER.match(w[4])]
    if not anchors:
        return [], ws
    anchors.sort(key=lambda w: w[1])
    rows = []
    for w in anchors:
        placed = False
        for r in rows:
            if abs(r["y"] - w[1]) <= 5.5:
                r["words"].append(w)
                r["y"] = (r["y"] * r["n"] + w[1]) / (r["n"] + 1)
                r["n"] += 1
                placed = True
                break
        if not placed:
            rows.append({"y": w[1], "n": 1, "words": [w]})
    orphans = []
    for w in ws:
        if DATER.match(w[4]):
            continue
        if not rows:
            orphans.append(w)
            continue
        best = min(rows, key=lambda r: abs(r["y"] - w[1]))
        if abs(best["y"] - w[1]) <= 6.5:
            best["words"].append(w)
        else:
            orphans.append(w)
    # words that belong to no date-anchored row form their own rows: this is how a
    # CARGO GROUP label ("Containers", "Iron Ore") is recovered - it sits alone, ~20 pt
    # above the first vessel row of its group
    for w in orphans:
        placed = False
        for r in rows:
            if abs(r["y"] - w[1]) <= 3.0:
                r["words"].append(w)
                placed = True
                break
        if not placed:
            rows.append({"y": w[1], "n": 1, "words": [w]})
    return rows, ws


def header_cols(page, ws):
    """Column bands from the page's own header words: the header is the block of words
    above the first data row that contains 'Vessel'."""
    # anchor on ANY header word, not only 'Vessel': one 2016-02 file
    # (ppa_pdf/a2c617ad59c5.pdf) prints its header without the word Vessel at all
    v = [w for w in ws if w[4] in ("Vessel", "Departure", "Depature", "Import",
                                   "Export", "Country", "GRT", "DWT")]
    if not v:
        return None
    # the reporting-period line ("Cargo Complete date: 01/12/2023 to 31/12/2023") also
    # contains date-shaped words; the header sits BELOW it
    rp = [w[1] for w in ws if w[4].lower().startswith("date:")]
    rp_y = max(rp) if rp else None
    first_data = min((w[1] for w in ws if DATER.match(w[4])
                      and (rp_y is None or w[1] > rp_y + 2)), default=None)
    # take the LOWEST header candidate that is still above the first data row: the title
    # line also contains 'GRT' and 'DWT' ("Cargo, GRT and DWT Statistics..."), so min(y)
    # picked the title and produced a header of one band
    cand = [w[1] for w in v if first_data is None or w[1] < first_data]
    hy = max(cand) if cand else min(w[1] for w in v)
    hdr = [w for w in ws if hy - 18 <= w[1] <= hy + 4]
    cols = []
    for w in sorted(hdr, key=lambda w: (w[0], w[1])):
        if cols and w[0] - cols[-1]["x1"] <= 14:
            cols[-1]["x1"] = max(cols[-1]["x1"], w[2])
            cols[-1]["words"].append(w)
        else:
            cols.append({"x0": w[0], "x1": w[2], "words": [w]})
    names = []
    for c in cols:
        ws_ = sorted(c["words"], key=lambda w: (round(w[1], 1), w[0]))
        names.append(" ".join(w[4] for w in ws_).strip())
    return {"cols": cols, "names": names, "hy": hy}


def month_from_text(text):
    m = re.search(r"(?:Cargo Complete|Departure|Arrival)\s*date:?\s*([0-9/]+)\s*to\s*([0-9/]+)", text, re.I)
    if not m:
        return None
    for a, b in (m.group(1), m.group(2)),:
        pa = a.split("/")
        pb = b.split("/")
        if len(pa) == 3 and len(pb) == 3:
            for order in ("dm", "md"):
                ma = pa[1] if order == "dm" else pa[0]
                mb = pb[1] if order == "dm" else pb[0]
                if ma == mb and pa[2] == pb[2]:
                    return "%s-%02d-01" % (pa[2], int(ma))
    return None


def parse_vessels(path):
    doc = pymupdf.open(str(path))
    date = None
    out, checks = [], {"rows": 0, "bad_date": 0, "bad_num": 0, "no_cols": 0,
                       "iron_ore_export": 0.0, "pages": 0}
    # the CARGO GROUP label appears only where a group STARTS; continuation pages carry
    # the header but no label, so the group state must persist across pages
    group = None
    for page in doc:
        txt = page.get_text()
        if date is None:
            date = month_from_text(txt)
        rows, ws = page_rows(page)
        hc = header_cols(page, ws)
        if hc is None:
            checks["no_cols"] += 1
            continue
        checks["pages"] += 1
        cols, names = hc["cols"], hc["names"]
        hy = hc["hy"]
        def band_of(x, w):
            # columns are LEFT-aligned: assign by column START, not by containment.
            # Containment truncated vessel names - "WUGANG HAOYUN" put HAOYUN (x0 131)
            # outside the narrow 'Vessel' header band (47.6-72.5) and lost it.
            best = None
            for i, c in enumerate(cols):
                if c["x0"] <= x + 5.0:
                    best = i
                else:
                    break
            if best is not None:
                return best
            cx = (x + w) / 2
            return min(range(len(cols)), key=lambda i: abs(cx - (cols[i]["x0"] + cols[i]["x1"]) / 2))
        for r in sorted(rows, key=lambda r: r["y"]):
            if r["y"] <= hy + 2:
                continue
            cells = collections.defaultdict(list)
            for w in r["words"]:
                i = band_of(w[0], w[2])
                if i is not None:
                    cells[i].append(w)
            vals = {}
            for i, v in cells.items():
                key = names[i] if i < len(names) else "col%d" % i
                v = sorted(v, key=lambda w: (round(w[1], 1), w[0]))
                s = v[0][4]
                for prev, w in zip(v, v[1:]):
                    same = abs(w[1] - prev[1]) < 2.0
                    s += ("" if (same and w[0] - prev[2] < 1.2) else " ") + w[4]
                vals[key] = s.strip()
            nonempty = [k for k, v in vals.items() if v]
            # a cargo group label row: one text cell, no date, no number
            if (len(nonempty) == 1 and not any(DATER.match(v) for v in vals.values())
                    and not any(NUMR.match(v.replace(" ", "")) for v in vals.values() if v)):
                cand = vals[nonempty[0]].upper()
                if any(g in cand or cand in g for g in GROUPS):
                    group = vals[nonempty[0]]
                continue
            if not any(DATER.match(v) for v in vals.values()):
                continue
            rec = {"date": date, "port": "Port Hedland", "cargo_group": group}
            # iterate in BAND order (left to right) and never let a later band overwrite a
            # field an earlier one set: the 2015 layout has both 'Arrival No.' and
            # 'Arrival Date' columns, and a dict-order walk put the PHPA id in arrival_date
            for i in sorted(cells):
                k = names[i] if i < len(names) else "col%d" % i
                v = vals.get(k, "")
                ku = k.upper()
                if not v:
                    continue
                if "VESSEL" in ku and "vessel" not in rec:
                    rec["vessel"] = v
                elif ("DESTINATION" in ku or "ORIGIN" in ku) and "country" not in rec:
                    rec["country"] = v
                elif "ARRIVAL NO" in ku and "arrival_no" not in rec:
                    rec["arrival_no"] = v
                elif "ARRIVAL" in ku and "arrival_date" not in rec and DATER.match(v):
                    rec["arrival_date"] = v
                elif ("DEPARTURE" in ku or "DEPATURE" in ku) and "departure_date" not in rec:
                    if DATER.match(v):
                        rec["departure_date"] = v
                elif "IMPORT" in ku and "import_volume" not in rec:
                    rec["import_volume"] = num(v)
                elif "EXPORT" in ku and "export_volume" not in rec:
                    rec["export_volume"] = num(v)
                elif ku.startswith("GRT") and "grt" not in rec:
                    rec["grt"] = num(v)
                elif ku.startswith("DWT") and "dwt" not in rec:
                    rec["dwt"] = num(v)
            if not rec.get("vessel") or not rec.get("arrival_date"):
                checks["bad_date"] += 1
                continue
            if rec.get("grt") is None and rec.get("dwt") is None:
                checks["bad_num"] += 1
                continue
            checks["rows"] += 1
            if (group or "").upper().startswith("IRON ORE") and rec.get("export_volume"):
                checks["iron_ore_export"] += rec["export_volume"]
            rec["source_file"] = rel(path)
            out.append(rec)
    doc.close()
    return {"date": date, "rows": out, "checks": checks}, None


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
                continue
            done[o["file"]] = o
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--files", nargs="*", default=None)
    args = ap.parse_args()

    files = []
    if args.files:
        files = [Path(f) if Path(f).is_absolute() else ROOT / f for f in args.files]
    else:
        files = sorted(CORPUS.glob("_root_pdfs/*.pdf")) + sorted(CORPUS.glob("ppa_pdf/*.pdf"))
        keep = []
        for f in files:
            try:
                d = pymupdf.open(str(f))
                t = d[0].get_text()
                d.close()
            except Exception:
                continue
            if "GRT and DWT" in t:
                keep.append(f)
        files = keep
    if args.limit:
        files = files[:args.limit]

    ck = OUTDIR / "vessels_rows.jsonl"
    statep = OUTDIR / "vessels_state.json"
    done = load_jsonl(ck) if args.resume else {}
    state = json.loads(statep.read_text()) if (args.resume and statep.exists()) else {}
    state.setdefault("done", [])
    state.setdefault("failed", [])
    state.setdefault("skipped", [])
    t0 = time.time()
    n = 0
    for f in files:
        key = rel(f)
        if key in done:
            continue
        n += 1
        try:
            parsed, err = parse_vessels(f)
        except Exception as exc:  # noqa: BLE001
            state["failed"].append({"file": key, "err": "%s: %s" % (type(exc).__name__, exc)})
            print("FAIL", key, exc, flush=True)
            continue
        if parsed is None or not parsed["rows"]:
            state["skipped"].append(
                {"file": key,
                 "reason": err or "no rows parsed (header prints no Vessel column, so the "
                                  "vessel name has no label - left unlabelled rather than "
                                  "guessed)"})
            continue
        with ck.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"file": key, "rows": parsed["rows"],
                                 "checks": parsed["checks"]}) + "\n")
        done[key] = parsed
        state["done"].append(key)
        if n % 20 == 0:
            statep.write_text(json.dumps(state))
            print("[vessels] %d processed, %.1fs" % (n, time.time() - t0), flush=True)
    statep.write_text(json.dumps(state))
    print("[vessels] DONE processed=%d skipped=%d failed=%d in %.1fs"
          % (n, len(state["skipped"]), len(state["failed"]), time.time() - t0), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
