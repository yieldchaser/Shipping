"""Seabrokers monthly: stack each issue's tables into the seabrokers_* series (append-only).

The series were exported from a parquet built by the camelot pipeline (seabrokers_ext/), which CI does not run,
so issues ingested after 2026-09 reached the MD but never the series. This reads the .tables.json sidecar that
CI writes next to every MD, with the row rules of that pipeline:

  * osv_spot_rates       "NORTH SEA AVERAGE RATES <MONTH>": avg / prev-year / % change / min / max per class
  * osv_utilisation      "NORTH SEA SPOT AVERAGE UTILISATION <MONTH>": the six printed months per class
  * osv_monthly_history  "North Sea Average Spot Rates" month grids: last year and this year to the issue month
  * fleet_moves          "ARRIVALS / DEPARTURES NORTH SEA SPOT"
  * snp_auctions         the Bourbon auction table (VESSEL/S, TYPE, WINNING BID, BUYING ENTITY)
  * rigs_market          "INACTIVE RIGS" table (section rigs_inactive)
  * feature_vessels      the featured-vessel fact box ("Vessel Name:", "Owner:", "Length:" ...)

source_page is the PDF page holding the table title. --check rebuilds every issue already in a series and
compares it row for row (the control); --new-only appends issues not in a series yet.

    python scripts/extract/publishers/seabrokers_series.py --check
    python scripts/extract/publishers/seabrokers_series.py --new-only
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MD = ROOT / "data" / "extracted" / "md" / "seabrokers"
SER = ROOT / "data" / "extracted" / "series"
FAMILIES = ("osv_spot_rates", "osv_utilisation", "osv_monthly_history", "fleet_moves", "snp_auctions",
            "rigs_market", "feature_vessels")
MONTHS = {m: i for i, m in enumerate(("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT",
                                      "NOV", "DEC"), 1)}
CLASSES = ("PSVs < 900m2", "PSVs > 900m2", "AHTS < 22,000 bhp", "AHTS > 22,000 bhp")
# fact-box label -> (metric, unit); numeric units take the number, "text" keeps the printed value
FACTS = {"length": ("length", "m"), "breadth": ("breadth", "m"), "deck area": ("deck_area", "m2"),
         "deadweight": ("deadweight", "tonnes"), "accommodation": ("accommodation", "persons"),
         "main crane": ("main_crane", "tonnes"), "installed power": ("installed_power", "kW"),
         "delivery": ("delivery_year", "year"), "owner": ("owner", "text"), "manager": ("manager", "text"),
         "design": ("design", "text"), "designer": ("designer", "text"),
         "dynamic positioning": ("dynamic_positioning", "text"), "helideck": ("helideck", "text"),
         "moonpool": ("moonpool", "text"), "rovs": ("rovs", "text")}
MOVE_NOTE = "North Sea spot market vessel move (term/layup moves excluded per report footnote)"


def vclass(label: str) -> str | None:
    s = label.upper()
    if "PSV" not in s and "AHTS" not in s:
        return None
    big = ">" in s or "LARGE" in s
    return CLASSES[(2 if "AHTS" in s else 0) + big]


def fnum(tok: str) -> float | None:
    t = re.sub(r"[^\d.\-+]", "", (tok or "").replace(",", ""))
    try:
        return float(t)
    except ValueError:
        return None


def period(tok: str) -> str | None:
    """'AUG 2026' / 'Aug 26' -> '2026-08'."""
    m = re.match(r"([A-Za-z]{3})[a-z]*\.?\s+'?(\d{2,4})$", tok.strip())
    if not m or m.group(1).upper() not in MONTHS:
        return None
    y = int(m.group(2))
    return f"{y + 2000 if y < 100 else y}-{MONTHS[m.group(1).upper()]:02d}"


class Pages:
    """0-based page index, as the series prints it ('5.0'), of the first page carrying a table title and the
    table's first cell (the title alone also hits the contents box on page 1)."""

    def __init__(self, pdf: Path):
        self.pages: list[str] = []
        try:
            import pymupdf
            with pymupdf.open(pdf) as doc:
                self.pages = [re.sub(r"\s+", " ", p.get_text()).upper() for p in doc]
        except Exception:
            pass

    def of(self, title: str, vals: list[list[str]] | None = None) -> str:
        t = re.sub(r"\s+", " ", re.sub(r"[*#]", "", title)).strip().upper()
        cell = next((m.group(0) for v in (vals or []) for c in v if (m := re.search(r"\d[\d,.]*\d", c))), "")
        for i, txt in enumerate(self.pages):
            if t and t in txt and cell in txt:
                return f"{i}.0"
        return ""


def build(side: Path) -> tuple[str, dict[str, list[dict]]] | None:
    d = json.loads(side.read_text(encoding="utf-8"))
    date = d.get("issue_date") or ""
    if not re.fullmatch(r"\d{4}-\d{2}-01", date):
        return None
    year, month = int(date[:4]), int(date[5:7])
    pdf = ROOT / (d.get("source_file") or "")
    pages = Pages(pdf) if pdf.is_file() else Pages(Path(""))
    base = {"report_date": date, "year": str(year), "month": str(month)}
    out: dict[str, list[dict]] = {f: [] for f in FAMILIES}
    grids = []
    for t in d.get("tables", []):
        title, cols, rows = t.get("title", ""), t.get("columns", []), t.get("rows", [])
        T = title.upper()
        vals = [[str((r.get(c) if isinstance(r, dict) else (r[i] if i < len(r) else "")) or "").replace("**", "").strip("* ")
                 for i, c in enumerate(cols)] for r in rows]
        if not out["feature_vessels"]:
            fv = feature_rows(base, cols, vals, "")
            if fv:
                pg = pages.of(fv[0]["vessel_class"], vals)
                out["feature_vessels"] = [{**r, "source_page": pg} for r in fv]
                continue
        if T.startswith("NORTH SEA AVERAGE RATES") and len(cols) >= 6:
            pg = pages.of(title, vals)
            for v in vals:
                vc = vclass(v[0])
                if not vc:
                    continue
                for metric, i, unit in (("avg_dayrate", 1, "GBP/day"), ("prev_year_dayrate", 2, "GBP/day"),
                                        ("yoy_change", 3, "percent"), ("min_dayrate", 4, "GBP/day"),
                                        ("max_dayrate", 5, "GBP/day")):
                    x = fnum(v[i])
                    if x is not None:
                        out["osv_spot_rates"].append({**base, "vessel_class": vc, "metric": metric, "value": str(x),
                                                      "unit": unit, "source": "seabrokers_osv_dayrates.csv (reused)",
                                                      "source_page": ""})
        elif T.startswith("NORTH SEA SPOT AVERAGE UTILISATION"):
            pg = pages.of(title, vals)
            per = [period(c) for c in cols]
            for v in vals:
                vc = vclass(v[0])
                for j in range(1, len(cols)):
                    x = fnum(v[j])
                    if vc and per[j] and x is not None and 0 <= x <= 100:   # (a rates grid can carry this title)
                        out["osv_utilisation"].append({**base, "period": per[j], "vessel_class": vc,
                                                       "metric": "spot_avg_utilisation", "value": str(x),
                                                       "unit": "percent", "source": "seabrokers", "source_page": pg})
        elif T.startswith("NORTH SEA AVERAGE SPOT RATES") and any(c.strip().lower() == "month" for c in cols):
            grids.append((title, cols, vals))
        elif T.startswith(("ARRIVALS NORTH SEA", "DEPARTURES NORTH SEA")) and cols and cols[0].upper() == "VESSEL":
            # (some parses lost the vessel column and kept only the origin: those are not rebuilt)
            pg = pages.of(title.rstrip(" *"), vals)
            metric = "arrival_from" if T.startswith("ARR") else "departure_to"
            for v in vals:
                if v and v[0].strip():
                    out["fleet_moves"].append({**base, "vessel_class": v[0].strip(), "metric": metric,
                                               "value_text": "", "note": MOVE_NOTE, "source": "seabrokers",
                                               "source_page": pg})
        elif [c.upper() for c in cols[1:3]] in (["TYPE", "WINNING BID"], ["TYPE", "STARTING PRICE"]):
            # sold vessels (winning bid, buying entity) and vessels still to be auctioned (starting price, date)
            pg = pages.of(title, vals)
            sold = cols[2].upper() == "WINNING BID"
            for v in vals:
                x = fnum(v[2])
                if x is None:
                    continue
                last = v[3].strip() if len(v) > 3 else ""
                out["snp_auctions"].append({**base, "vessel_class": v[1].strip(),
                                            "metric": "winning_bid" if sold else "starting_price",
                                            "value": str(x), "unit": "USD million",
                                            "note": f"vessel={v[0].strip()}; " + ("buyer=" if sold else "auction_date=") + last,
                                            "source": "seabrokers", "source_page": pg})
        elif "INACTIVE RIGS" in T and [c.upper() for c in cols[:3]] == ["NAME", "TYPE", "STATUS"]:
            pg = pages.of(title, vals)
            region = "Northwest Europe"
            for v in vals:
                if v[0].strip() and "STACK" in v[2].upper():
                    out["rigs_market"].append({**base, "section": "rigs_inactive", "region": region,
                                               "vessel_class": "", "metric": "inactive_rig", "value": "1.0",
                                               "value_text": "", "unit": "count", "period": date[:7],
                                               "note": f"rig={v[0].strip()}; type={v[1].strip()}; status={v[2].strip()}",
                                               "source": "seabrokers", "source_page": pg})
    # month grids: a Category column, or one unlabelled grid per class. An unlabelled grid is the class whose
    # issue-month rates (this year, last year) are the ones the average-rates table prints; else it is skipped
    rate = {}
    for r in out["osv_spot_rates"]:
        rate.setdefault(r["vessel_class"], {})[r["metric"]] = float(r["value"])
    for title, cols, vals in grids:
        lc = [c.strip().lower() for c in cols]
        mi = lc.index("month")
        ci = lc.index("category") if "category" in lc else None
        pg = pages.of(title, vals)
        anchor = None
        if ci is None:
            yc = {int(c): j for j, c in enumerate(cols) if re.fullmatch(r"\d{4}", c.strip())}
            now = next((v for v in vals if MONTHS.get(v[mi].strip()[:3].upper()) == month), None)
            if now and year in yc and year - 1 in yc:
                hit = [vc for vc, m in rate.items() if (m.get("avg_dayrate"), m.get("prev_year_dayrate"))
                       == (fnum(now[yc[year]]), fnum(now[yc[year - 1]]))]
                anchor = hit[0] if len(hit) == 1 else None
        for v in vals:
            vc = vclass(v[ci]) if ci is not None else anchor
            mo = MONTHS.get(v[mi].strip()[:3].upper())
            if not vc or not mo:
                continue
            for j, c in enumerate(cols):
                if re.fullmatch(r"\d{4}", c.strip()):
                    x = fnum(v[j])
                    if x is not None and (int(c), mo) <= (year, month):
                        out["osv_monthly_history"].append({**base, "period": f"{c.strip()}-{mo:02d}",
                                                           "vessel_class": vc, "metric": "monthly_avg_spot_dayrate",
                                                           "value": str(x), "unit": "GBP/day", "source": "seabrokers",
                                                           "source_page": pg})
    return date, out


def facts(cols: list[str], vals: list[list[str]]) -> list[tuple[str, str]]:
    """(label, value) pairs of a fact box: "**Label:** value" cells, or label / value columns."""
    cols = [c.replace("**", "").strip() for c in cols]
    if len(cols) == 2 and cols[0].endswith(":"):
        return [(k.strip().rstrip(":"), v.strip()) for k, v in [cols] + [r[:2] for r in vals if len(r) >= 2]]
    cells = cols + [c for v in vals for c in v]
    return [(m.group(1).strip(), m.group(2).strip()) for c in cells
            if (m := re.match(r"([A-Za-z][A-Za-z /]{1,40}):\s*(.+)", c.strip()))]


def feature_rows(base: dict, cols: list[str], vals: list[list[str]], pg: str) -> list[dict]:
    kv = facts(cols, vals)
    if not kv or kv[0][0].lower() != "vessel name":
        return []
    name, rows = kv[0][1], []
    rows.append({**base, "vessel_class": name, "metric": "featured", "value": "1.0", "value_text": "",
                 "unit": "count", "note": "", "source": "seabrokers", "source_page": pg})
    for k, v in kv[1:]:
        metric, unit = FACTS.get(k.lower(), (None, None))
        if not metric or not v:
            continue
        if unit == "text":
            rows.append({**base, "vessel_class": name, "metric": metric, "value": "", "value_text": v,
                         "unit": "text", "note": "", "source": "seabrokers", "source_page": pg})
            continue
        m = re.search(r"\b(19|20)\d\d\b", v) if unit == "year" else re.match(r"[\d,]+(?:\.\d+)?", v)
        if m:
            rows.append({**base, "vessel_class": name, "metric": metric, "value": str(float(m.group(0).replace(",", ""))),
                         "value_text": "", "unit": unit, "note": "", "source": "seabrokers", "source_page": pg})
    return rows


def repairable(hdr: list[str], got: list[list[str]], old: list[list[str]]) -> bool:
    pi = hdr.index("source_page")
    key = lambda r: tuple(r[:pi])                                   # noqa: E731
    if {key(r) for r in old} < {key(r) for r in got}:
        return True
    if "value_text" in hdr:                         # fact-box texts the old export cut at the line wrap
        ti = hdr.index("value_text")
        full = {tuple(r[:ti]): r[ti] for r in got}
        if all(tuple(r[:ti]) in full and full[tuple(r[:ti])].startswith(r[ti]) and r[ti + 1:pi] == next(
                g[ti + 1:pi] for g in got if tuple(g[:ti]) == tuple(r[:ti])) for r in old) and len(got) >= len(old):
            return True
    if "note" in hdr and "metric" in hdr:                           # auctions: starting prices held as winning bids
        vi, ni = hdr.index("value"), hdr.index("note")
        bare = lambda rs: sorted((r[3], r[vi], r[ni].split(";")[0]) for r in rs)   # noqa: E731
        return bare(got) == bare(old)
    return False


def write(path: Path, hdr: list[str], body: list[list[str]], raw: bytes) -> None:
    nl = "\r\n" if raw.split(b"\n", 1)[0].endswith(b"\r") else "\n"
    buf = io.StringIO()
    csv.writer(buf, lineterminator=nl).writerows([hdr] + body)
    tmp = path.with_suffix(".csv.tmp")
    tmp.write_bytes((b"\xef\xbb\xbf" if raw.startswith(b"\xef\xbb\xbf") else b"") + buf.getvalue().encode("utf-8"))
    os.replace(tmp, path)


def read(path: Path):
    raw = path.read_bytes()
    rd = csv.reader(io.StringIO(raw.decode("utf-8-sig")))
    hdr = next(rd)
    return hdr, [r for r in rd if r], raw


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true", help="rebuild issues already in the series and compare")
    g.add_argument("--new-only", action="store_true", help="append issues not in the series yet")
    g.add_argument("--repair", nargs="+", choices=FAMILIES, metavar="FAMILY",
                   help="replace, in place, the rows of issues whose rebuild holds every series row and more "
                        "(rows the old export dropped), or relabels the same auction rows")
    a = ap.parse_args(argv)
    csv.field_size_limit(10 ** 9)

    series = {f: read(SER / f"seabrokers_{f}_series.csv") for f in FAMILIES}
    have = {f: {} for f in FAMILIES}
    for f, (hdr, body, _) in series.items():
        for r in body:
            if f == "rigs_market" and r[hdr.index("section")] != "rigs_inactive":
                continue
            have[f].setdefault(r[0], []).append(r)
    stats = {f: [0, [], 0] for f in FAMILIES}
    added = {f: [] for f in FAMILIES}
    fixes: dict[str, dict[str, list[list[str]]]] = {f: {} for f in FAMILIES}
    for side in sorted(MD.rglob("*.tables.json")):
        b = build(side)
        if b is None:
            continue
        date, out = b
        for f, rows in out.items():
            hdr = series[f][0]
            got = [[r.get(c, "") for c in hdr] for r in rows]
            if date in have[f]:
                pi = hdr.index("source_page")
                # the PDF is not in every checkout: a row without a page then matches any page
                old = [r[:pi] + ([""] if g and not g[pi] else r[pi:pi + 1]) + r[pi + 1:]
                       for r, g in zip(sorted(have[f][date]), [got[0]] * len(have[f][date]))] if got else []
                if not got:
                    stats[f][2] += 1
                elif sorted(got) == sorted(have[f][date]) or sorted(got) == sorted(old):
                    stats[f][0] += 1
                else:
                    stats[f][1].append((date, len(got), len(have[f][date])))
                    if repairable(hdr, got, have[f][date]):
                        fixes[f][date] = got
            elif got and a.new_only and f == "osv_monthly_history" and len({r[4] for r in got}) < len(CLASSES):
                print(f"  ! {f}: {date} grid parse covers {len({r[4] for r in got})} of 4 classes, not appended")
            elif got and a.new_only:
                added[f].extend(got)
                print(f"  + {f}: {date} {len(got)} rows <- {side.name}")
    if a.repair:
        for f in a.repair:
            hdr, body, raw = series[f]
            out, done = [], set()
            for r in body:
                if r[0] in fixes[f] and (f != "rigs_market" or r[hdr.index("section")] == "rigs_inactive"):
                    if r[0] not in done:
                        out.extend(fixes[f][r[0]])
                        done.add(r[0])
                    continue
                out.append(r)
            write(SER / f"seabrokers_{f}_series.csv", hdr, out, raw)
            print(f"{f}: {len(done)} issues replaced from their sidecar: {sorted(done)}")
        return 0
    if a.check:
        bad = 0
        for f, (ok, diff, none) in stats.items():
            print(f"{f}: {ok} issues identical, {len(diff)} differ, {none} not rebuilt (table not found)")
            for x in diff[:8]:
                print("   differs", x)
            bad += len(diff)
        return 1 if bad else 0
    for f, rows in added.items():
        if not rows:
            continue
        hdr, body, raw = series[f]
        nl = "\r\n" if raw.split(b"\n", 1)[0].endswith(b"\r") else "\n"
        with open(SER / f"seabrokers_{f}_series.csv", "a", encoding="utf-8", newline="") as fh:
            if not raw.endswith(b"\n"):
                fh.write(nl)
            csv.writer(fh, lineterminator=nl).writerows(rows)
    print("seabrokers series: " + ", ".join(f"{f} +{len(r)}" for f, r in added.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
