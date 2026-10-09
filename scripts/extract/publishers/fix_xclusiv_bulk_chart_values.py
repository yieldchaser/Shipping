#!/usr/bin/env python3
"""Per-source fix: xclusiv bulk-carrier chart series values.

ROOT CAUSE (measured 2026-10-09): run_xclusiv_vector_charts.py selected the
* navy horizontal "Average" reference line * instead of the light-blue DATA
curve. Selection test `c[0]<0.35 and c[1]<0.6 and c[2]>0.4` accepts the navy
reference (0.106,0.255,0.443) and REJECTS the data curve (0.612,0.729,0.835),
so the emitted value was the reference line's y -> a constant per layout,
200-300% off the same document's own stated weekly rate.

FIX: pick the light-blue curve (0.612,0.729,0.835) with the most line items,
fit value=a*y+b from that chart's own printed y-axis tick labels, map the
curve's latest point. CONTROL: the corrected value must agree (<=30%) with the
SAME document's page-1 prose weekly rate (C5TC/P5TC/S11TC/HS7TC); rows that
fail are BLANKED (a wrong value is worse than a missing one) and listed.

Idempotent: a second run writes nothing. Values only; row identity untouched.
"""
import csv, os, re, glob, sys
import pymupdf
from collections import defaultdict

ROOT = "corpus/01-brokers/xclusiv"
CSV_PATH = "data/extracted/series/xclusiv_bulk_carrier_charts_series.csv"
LC = (0.612, 0.729, 0.835)
CLASSES = ["Capesize 5TC", "Kamsarmax 5TC", "Ultramax 11TC", "Handysize 7TC"]
KW = {"Capesize 5TC": "C5TC", "Kamsarmax 5TC": "P5TC",
      "Ultramax 11TC": "S11TC", "Handysize 7TC": "HS7TC"}


def _close(c, t, tol=0.035):
    return bool(c) and all(abs(a - b) < tol for a, b in zip(c, t))


def _charts(pg):
    ts = []
    for w in pg.get_text("words"):
        x0, y0, txt = w[0], w[1], w[4]
        if x0 >= 305:
            continue
        t = txt.replace(",", "")
        if re.fullmatch(r"\d{3,6}", t):
            ts.append((y0, int(t)))
    ts = sorted(set(ts))
    if len(ts) < 4:
        return []
    out, cur = [], [ts[0]]
    for p in ts[1:]:
        if p[0] - cur[-1][0] > 40:
            out.append(cur); cur = [p]
        else:
            cur.append(p)
    out.append(cur)
    return out


def _fit(ch):
    ys = [p[0] for p in ch]; vs = [p[1] for p in ch]; n = len(ch)
    sy = sum(ys); sv = sum(vs)
    syy = sum(y * y for y in ys); syv = sum(y * v for y, v in ch)
    a = (n * syv - sy * sv) / (n * syy - sy * sy)
    return a, (sv - a * sy) / n


def _curve(pg, ch):
    ytop = min(p[0] for p in ch); ybot = max(p[0] for p in ch)
    best = None
    for d in pg.get_drawings():
        r = d.get("rect")
        if not r or r.y1 - r.y0 < 20:
            continue
        if not _close(d.get("color"), LC):
            continue
        if not (r.y0 >= ytop - 15 and r.y1 <= ybot + 35):
            continue
        nl = sum(1 for it in d["items"] if it[0] == "l")
        if nl < 50:
            continue
        pts = [it[1] for it in d["items"] if it[0] == "l"]
        if best is None or nl > best[0]:
            best = (nl, pts)
    return best


def chart_values(pg):
    chs = _charts(pg)
    if len(chs) != 4:
        return None
    out = {}
    for cls, ch in zip(CLASSES, chs):
        a, b = _fit(ch); c = _curve(pg, ch)
        if not c:
            out[cls] = None; continue
        _, pts = c
        mx = max(p.x for p in pts)
        latest = [p for p in pts if p.x >= mx - 1.5]
        y = sum(p.y for p in latest) / len(latest)
        out[cls] = round(a * y + b, 1)
    return out


def prose_rates(pg):
    t = re.sub(r"\s+", " ", pg.get_text())
    out = {}
    for cls, kw in KW.items():
        i = t.find(kw)
        if i < 0:
            out[cls] = None; continue
        m = re.search(r"at USD\s*([\d][\d,]*(?:\.\d+)?)\s*/\s*day", t[i:i + 200])
        out[cls] = float(m.group(1).replace(",", "")) if m else None
    return out


def main():
    dry = "--apply" not in sys.argv
    paths = {os.path.basename(p): p for p in glob.glob(ROOT + "/*/*.pdf")}
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    fields = list(rows[0].keys())
    byfile = defaultdict(list)
    for r in rows:
        byfile[r["source_file"]].append(r)

    changed = 0; blanked = 0; keep = 0; no_doc = 0
    fail_list = []
    for sf, rs in byfile.items():
        p = paths.get(sf)
        if not p:
            no_doc += len(rs); continue
        d = pymupdf.open(p)
        if len(d) < 2:
            no_doc += len(rs); continue
        cv = chart_values(d[1]); pv = prose_rates(d[1])
        for r in rs:
            if cv is None or cv.get(r["vessel_class"]) is None:
                new = ""; blanked += 1
            else:
                val = cv[r["vessel_class"]]; pr = pv.get(r["vessel_class"])
                if pr and abs(val - pr) / pr <= 0.30:
                    new = f"{val}"; keep += 1
                else:
                    new = ""; blanked += 1
                    fail_list.append((sf, r["vessel_class"], r["rate_usd_per_day"], val, pr))
            old = r["rate_usd_per_day"]
            if old != new:
                changed += 1
            r["rate_usd_per_day"] = new

    print(f"rows={len(rows)} changed={changed} kept(control-pass)={keep} "
          f"blanked={blanked} no_doc={no_doc}")
    for e in fail_list[:25]:
        print("  CONTROL-FAIL", e)
    if dry:
        print("DRY RUN - no write. Pass --apply to write.")
        return
    if changed == 0:
        print("idempotent: nothing stale, no write")
        return
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader(); w.writerows(rows)
    print(f"wrote {CSV_PATH}")


if __name__ == "__main__":
    main()
