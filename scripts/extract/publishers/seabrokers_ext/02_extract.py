"""
Phase 2: extract seabrokers report sections that are NOT in the existing
data/derived/seabrokers_osv_dayrates.csv ledger.

Sources (read-only):
  data/extracted/corpus/seabrokers/<doc>/text.jsonl   (bbox + full text items)
  data/extracted/corpus/seabrokers/<doc>/tables.jsonl (camelot grids, fallback)
  data/derived/seabrokers_osv_dayrates.csv            (existing ledger, reused)

Output: scratch/seabrokers_ext/rows.jsonl  (long format, one row per datum)
"""
import json, os, re, csv, sys
from collections import defaultdict

ROOT = r"C:/Users/Dell/Github/Shipping"
BASE = os.path.join(ROOT, "data/extracted/corpus/seabrokers")
OUT = os.path.join(ROOT, "scratch/seabrokers_ext")
LEDGER = os.path.join(ROOT, "data/derived/seabrokers_osv_dayrates.csv")
os.makedirs(OUT, exist_ok=True)

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MONNUM = {m: i + 1 for i, m in enumerate(MONTHS)}

rows = []
stats = defaultdict(lambda: defaultdict(set))   # section -> metric -> set(doc)


def emit(report_date, section, vessel_class, region, metric, value, unit,
         period=None, source="seabrokers", page=None, note=None):
    rows.append({
        "report_date": report_date,
        "section": section,
        "vessel_class": vessel_class,
        "region": region,
        "metric": metric,
        "value": value,
        "unit": unit,
        "period": period,
        "source": source,
        "source_page": page,
        "note": note,
    })
    stats[section][metric].add(report_date)


def num(s):
    if s is None:
        return None
    s = str(s).replace(",", "").replace("£", "").replace("$", "").replace("%", "").strip()
    s = s.replace("\u00a0", "")
    if s in ("-", "", "–", "—", "n/a", "N/A"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def norm_cat(s):
    """Normalise an OSV category label to a canonical key."""
    t = (s or "").replace("\u00b2", "2").replace("M2", "m2").replace("M²", "m2").upper()
    t = re.sub(r"\s+", " ", t).strip()
    if "MED PSV" in t or ("PSV" in t and "<" in t):
        return "PSVs < 900m2"
    if "LARGE PSV" in t or ("PSV" in t and ">" in t):
        return "PSVs > 900m2"
    if "MED AHTS" in t or ("AHTS" in t and "<" in t):
        return "AHTS < 22,000 bhp"
    if "LARGE AHTS" in t or ("AHTS" in t and ">" in t):
        return "AHTS > 22,000 bhp"
    return t


def norm_rig_class(s):
    t = re.sub(r"\s+", " ", str(s)).strip().upper()
    t = t.replace("SEMI-SUB", "SEMISUB").replace("JACK-UP", "JACKUP")
    t = t.replace("HIGH-SPEC", "HIGH SPEC")
    return t


CAT_RE = re.compile(
    r"^(MED PSV|LARGE PSV|MED AHTS|LARGE AHTS|PSVS?\s*[<>]|AHTS\s*[<>])", re.I)
REGION_ROWS = re.compile(
    r"^(NORTHWEST EUROPE|NORTH WEST EUROPE|NORTH SEA|NORTH-EAST EUROPE|SOUTH AMERICA|"
    r"US GULF|WEST AFRICA|MIDDLE EAST|ASIA[\w \-/]*|BRAZIL|MEXICO)\s*$", re.I)
REGIONLIKE = re.compile(r"^(?:EX )?[A-Z][A-Z0-9 /&+\.\-']{2,60}$")


# ---------------------------------------------------------------- ledger reuse
def load_ledger():
    led = {}
    with open(LEDGER, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            led[(r["date"], norm_cat(r["category"]))] = r
    return led


LED = load_ledger()


def extract_ledger():
    """Section A: reuse the existing OSV dayrate ledger (GBP/day)."""
    with open(LEDGER, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            d = r["date"]
            cat = norm_cat(r["category"])
            for col, metric, unit in (
                ("avg_dayrate_gbp", "avg_dayrate", "GBP/day"),
                ("prev_year_dayrate_gbp", "prev_year_dayrate", "GBP/day"),
                ("min_dayrate_gbp", "min_dayrate", "GBP/day"),
                ("max_dayrate_gbp", "max_dayrate", "GBP/day"),
            ):
                v = num(r[col])
                if v is not None:
                    emit(d, "osv_spot_rates", cat, "North Sea", metric, v, unit,
                         period=d[:7], source="seabrokers_osv_dayrates.csv (reused)",
                         note=r.get("report_month"))
            yoy = num(r["yoy_change_pct"])
            if yoy is not None:
                emit(d, "osv_spot_rates", cat, "North Sea", "yoy_change", yoy, "percent",
                     period=d[:7], source="seabrokers_osv_dayrates.csv (reused)")


# ------------------------------------------------------- B: OSV utilisation
def extract_osv_utilisation(doc, date, items):
    """Back-month utilisation grid: TYPE x up to 6 months."""
    if "NORTH SEA SPOT AVERAGE UTILISATION" not in \
            "\n".join(i["text"] for i in items):
        return
    pages = {i["page"] for i in items
             if "NORTH SEA SPOT AVERAGE UTILISATION" in i["text"]}
    for pg in pages:
        pit = sorted([i for i in items if i["page"] == pg], key=lambda x: x["bbox"][1])
        header = None
        for it in pit:
            toks = [t.strip() for t in it["text"].split("\n")]
            if toks and toks[0].upper() == "TYPE":
                per = [t for t in toks[1:] if re.match(r"^[A-Za-z]{3,9}\s+\d{4}$", t)]
                if per:
                    header = (it, per)
                    break
        if not header:
            continue
        hit, periods = header
        # if the header text itself carries the month (e.g. 'NORTH SEA SPOT
        # AVERAGE UTILISATION AUG 2026') periods may be empty -> fall back
        for it in pit:
            toks = [t.strip() for t in it["text"].split("\n")]
            if not toks or not CAT_RE.match(toks[0]):
                continue
            cat = norm_cat(toks[0])
            vals = [num(t) for t in toks[1:]]
            vals = [v for v in vals if v is not None]
            vals = vals[:len(periods)]
            for per, v in zip(periods, vals):
                mm = re.match(r"^([A-Za-z]+)\s+(\d{4})$", per)
                if not mm:
                    continue
                mnum = MONNUM.get(mm.group(1)[:3].title())
                if not mnum:
                    continue
                period = f"{mm.group(2)}-{mnum:02d}"
                emit(date, "osv_utilisation", cat, "North Sea",
                     "spot_avg_utilisation", v, "percent", period=period,
                     page=pg, note=f"back-month column from {date[:7]} report")


# ------------------------------------- C: monthly spot-rate history (page 7)
LABELS = re.compile(
    r"^(PSVS?\s*[<>]\s*900\s*M?2|AHTS\s*[<>]\s*22,?000\s*BHP|"
    r"AHTS\s*<\s*22,?000\s*bhp|AHTS\s*>\s*22,?000\s*bhp|"
    r"RIG MOVES|ALL CARGO RUNS)$", re.I)


def _series_from_tokens(toks):
    """Parse one text item into [(year, [12 values])].

    Two shapes occur in the corpus:
      a) Jan..Dec + <year> + 12 values [+ <year2> + 12 values]
      b) <year> + 12 values            (the year row split into its own item)
    """
    toks = [t.strip() for t in toks if t.strip() != ""]
    out = []
    if len(toks) >= 25 and toks[:12] == MONTHS and \
            re.match(r"^(19|20)\d\d$", toks[12]):
        out.append((int(toks[12]), [num(t) for t in toks[13:25]]))
        if len(toks) >= 38 and re.match(r"^(19|20)\d\d$", toks[25]):
            out.append((int(toks[25]), [num(t) for t in toks[26:38]]))
    elif len(toks) == 13 and re.match(r"^(19|20)\d\d$", toks[0]):
        out.append((int(toks[0]), [num(t) for t in toks[1:13]]))
    return out


def extract_spot_rate_history(doc, date, items):
    ryear = int(date[:4])
    for pg in sorted({i["page"] for i in items}):
        pit = sorted([i for i in items if i["page"] == pg], key=lambda x: x["bbox"][1])
        if not any(_series_from_tokens(i["text"].split("\n")) for i in pit):
            continue
        labs = [i for i in pit if LABELS.match(i["text"].strip())]
        # group items into charts: a "full" item (months+year) anchors the
        # chart, and any bare year-row item close to it belongs to it too.
        for it in pit:
            s0 = _series_from_tokens(it["text"].split("\n"))
            if not s0:
                continue
            if [t.strip() for t in it["text"].split("\n")][:1] != ["Jan"]:
                continue          # only anchor on the months+year item
            x0, y0 = it["bbox"][0], it["bbox"][1]
            series = list(s0)
            have_years = {y for y, _ in series}
            for j in pit:
                if j is it:
                    continue
                xj, yj = j["bbox"][0], j["bbox"][1]
                if abs(xj - x0) > 70 or not (-40 <= yj - y0 <= 300):
                    continue
                for y, v in _series_from_tokens(j["text"].split("\n")):
                    if y not in have_years:
                        series.append((y, v))
                        have_years.add(y)

            # name the chart: match its values against the ledger (the ledger
            # is the already-published OSV dayrate series, so a chart's
            # prior-year monthly values are the ledger's own monthly averages)
            best, bmatch = None, 0
            for cat_key in ("PSVs < 900m2", "PSVs > 900m2",
                            "AHTS < 22,000 bhp", "AHTS > 22,000 bhp"):
                m = 0
                for y, vals in series:
                    for mi, v in enumerate(vals, start=1):
                        if v is None:
                            continue
                        lr = LED.get((f"{y}-{mi:02d}-01", cat_key))
                        if lr and abs(num(lr["avg_dayrate_gbp"]) - v) < 0.5:
                            m += 1
                if m > bmatch:
                    best, bmatch = cat_key, m
            lab_cat, bd = None, 1e9
            for l in labs:
                if abs(l["bbox"][0] - x0) > 70:
                    continue
                dy = y0 - l["bbox"][3]
                if -5 <= dy < 260 and dy < bd:
                    lab_cat, bd = norm_cat(l["text"]), dy
            if bmatch:
                cat = best
                note = "ledger_validated_%d" % bmatch
            else:
                cat = lab_cat
                note = "label_only"
            if cat is None:
                continue
            for y, vals in series:
                for mi, v in enumerate(vals, start=1):
                    if v is None:
                        continue
                    emit(date, "osv_spot_rate_history_monthly", cat, "North Sea",
                         "monthly_avg_spot_dayrate", v, "GBP/day",
                         period=f"{y}-{mi:02d}", page=pg, note=note)


# ---------------------------------------------------- D: YTD average dayrates
YTD_TITLE = re.compile(r"Average (?:Spot )?Day Rates To Month\s*\(([A-Za-z]+) (\d{4})\)")


def extract_ytd(doc, date, items):
    ryear, rmonth = int(date[:4]), int(date[5:7])
    titles = []
    for it in items:
        m = YTD_TITLE.search(it["text"])
        if not m:
            continue
        month_name, year = m.group(1), int(m.group(2))
        mnum = MONNUM.get(month_name[:3].title())
        if not mnum or year != ryear or abs(mnum - rmonth) > 1:
            continue          # stale advert / wrong-era graphic
        titles.append((it, mnum, year))
    for tit, mnum, year in titles:
        pg, ty0 = tit["page"], tit["bbox"][1]
        txs = tit["bbox"][0] < 600
        for blk in items:
            if blk["page"] != pg:
                continue
            bx0, by0 = blk["bbox"][0], blk["bbox"][1]
            if (bx0 < 600) != txs or not (-30 <= by0 - ty0 <= 170):
                continue
            toks = [t.strip() for t in blk["text"].split("\n") if t.strip()]
            if not toks or not CAT_RE.match(toks[0]):
                continue
            if not any(re.match(r"^(19|20)\d\d$", t) for t in toks):
                continue
            labs, rest = [], []
            for t in toks:
                if re.match(r"^(19|20)\d\d$", t):
                    rest.append(t)
                elif not rest:
                    labs.append(t)
                else:
                    rest.append(t)
            if len(labs) != 4 or len(rest) < 5:
                continue
            labels = [norm_cat(l) for l in labs]
            if len({l for l in labels}) != 4:
                continue
            ycur = int(rest[0])
            vcur = [num(t) for t in rest[1:5]]
            for lab, v in zip(labels, vcur):
                if v is None:
                    continue
                emit(date, "osv_spot_rate_ytd", lab, "North Sea",
                     "ytd_avg_spot_dayrate", v, "GBP/day",
                     period=f"{ycur}-01..{ycur}-{mnum:02d}", page=pg,
                     note=f"YTD average to {MONTHS[mnum - 1]} {year}")
            if len(rest) >= 10:
                yprev = int(rest[5])
                vprev = [num(t) for t in rest[6:10]]
                for lab, v in zip(labels, vprev):
                    if v is None:
                        continue
                    emit(date, "osv_spot_rate_ytd", lab, "North Sea",
                         "ytd_avg_spot_dayrate", v, "GBP/day",
                         period=f"{yprev}-01..{yprev}-{mnum:02d}", page=pg,
                         note=f"prior-year YTD to {MONTHS[mnum - 1]} {year}")


# ------------------------------------------- E: arrivals / departures lists
def extract_moves(doc, date, items):
    pages = sorted({i["page"] for i in items})
    for pg in pages:
        pit = sorted([i for i in items if i["page"] == pg],
                     key=lambda x: (round(x["bbox"][1], 1), x["bbox"][0]))
        direction = None
        for it in pit:
            t = it["text"].strip()
            if "ARRIVALS NORTH SEA SPOT" in t:
                direction = "arrival"
                continue
            if "DEPARTURES NORTH SEA SPOT" in t:
                direction = "departure"
                continue
            if not direction:
                continue
            toks = [x.strip() for x in t.split("\n") if x.strip()]
            if len(toks) != 2:
                continue
            vessel, prev = toks
            if vessel.upper().startswith("*") or len(vessel) < 3:
                continue
            if not re.match(r"^[A-Z0-9][A-Z0-9 /\-\.'\(\)&+]{2,}$", vessel.upper()):
                continue
            if vessel.upper() in ("SEABREEZE", "SEABROKERS", "MARKET REPORT"):
                continue
            if re.search(r"\b(19|20)\d\d\b", prev):
                continue          # page furniture, not a region
            if not REGIONLIKE.match(prev.upper()):
                continue
            emit(date, "osv_fleet_moves", vessel, prev,
                 "arrival_from" if direction == "arrival" else "departure_to",
                 1, "count", period=date[:7], page=pg,
                 note="North Sea spot market vessel move "
                      "(term/layup moves excluded per report footnote)")


# --------------------------------------------- F: rig day-rate benchmarks
CLASS_RE = re.compile(r"(JACKUP|JACK-UP|SEMISUB|SEMI-SUB|DRILLSHIP)", re.I)


def extract_rig_rates(doc, date, items):
    for n, it in enumerate(items):
        if "RECENT DAY RATE BENCHMARKS" in it["text"]:
            src = "Seabrokers/IHS-Petrodata (RECENT DAY RATE BENCHMARKS)"
        elif "CURRENT ESTIMATED FIXTURE RATES" in it["text"]:
            src = "Seabrokers/Bassoe Offshore (CURRENT ESTIMATED FIXTURE RATES)"
        else:
            continue
        pg = it["page"]
        y0 = it["bbox"][1]
        for j in items:
            if j["page"] != pg or j is it:
                continue
            if not (y0 - 2 <= j["bbox"][1] <= y0 + 260):
                continue
            toks = [t.strip() for t in j["text"].split("\n") if t.strip()]
            if len(toks) < 2 or not CLASS_RE.search(toks[0]):
                continue
            if toks[0].upper().startswith("RECENT") or \
               toks[0].upper().startswith("CURRENT"):
                continue
            vals = [num(t) for t in toks[1:]]
            vals = [v for v in vals if v is not None]
            if not vals:
                continue
            cls = norm_rig_class(toks[0])
            if len(vals) >= 2:
                emit(date, "rig_day_rates", cls, "Global", "dayrate_low", vals[0],
                     "USD/day", period=date[:7], page=pg, note=src)
                emit(date, "rig_day_rates", cls, "Global", "dayrate_high", vals[-1],
                     "USD/day", period=date[:7], page=pg, note=src)
            else:
                emit(date, "rig_day_rates", cls, "Global", "dayrate", vals[0],
                     "USD/day", period=date[:7], page=pg, note=src)


# -------------------------------------- G: rig utilisation by region x years
def extract_rig_utilisation(doc, date, items):
    pages = sorted({i["page"] for i in items})
    for pg in pages:
        pit = sorted([i for i in items if i["page"] == pg], key=lambda x: x["bbox"][1])
        for k, it in enumerate(pit):
            toks = [t.strip() for t in it["text"].split("\n") if t.strip()]
            if not toks or toks[0].upper() != "UTILISATION":
                continue
            # tokens alternate: MON YYYY MON YYYY ...
            pairs = re.findall(r"([A-Za-z]{3,9})\s+((?:19|20)\d\d)", it["text"])
            pairs = [(a[:3].title(), int(b)) for a, b in pairs
                     if MONNUM.get(a[:3].title())]
            if not pairs:
                continue
            y0 = it["bbox"][3]
            got = 0
            for j in pit[k + 1:]:
                if j["bbox"][1] - y0 > 150:
                    break
                jt = [t.strip() for t in j["text"].split("\n") if t.strip()]
                if len(jt) < 2:
                    continue
                reg = jt[0]
                if not REGION_ROWS.match(reg):
                    continue
                vals = [num(t) for t in jt[1:]]
                vals = [v for v in vals if v is not None]
                vals = [v for v in vals if 0 <= v <= 100]
                for (mn, yr), v in zip(pairs, vals):
                    emit(date, "rig_utilisation", None, reg.title(),
                         "rig_utilisation", v, "percent",
                         period=f"{yr}-{MONNUM[mn]:02d}", page=pg,
                         note="consecutive-year same-month comparison grid")
                    got += 1
            if got:
                break


# --------------------------------- H: offshore S&P / auction result tables
def extract_auction(doc, date, items):
    for n, it in enumerate(items):
        if "WINNING BID" not in it["text"]:
            continue
        pg = it["page"]
        y0 = it["bbox"][3]
        for j in items:
            if j["page"] != pg or j["bbox"][1] < y0 - 3:
                continue
            if j["bbox"][1] - y0 > 520:
                break
            toks = [t.strip() for t in j["text"].split("\n") if t.strip()]
            if len(toks) < 4:
                continue
            if not re.match(r"^(USD|EUR|GBP|\$|€|£)", toks[-2]) and \
               not re.match(r"^(USD|EUR|GBP|\$|€|£)", toks[2]):
                continue
            mbid = re.search(r"(USD|EUR|GBP|\$|€|£)\s*([\d\.,]+)\s*(million|m|bn)?",
                             toks[2], re.I)
            if not mbid:
                continue
            cur = {"USD": "USD", "EUR": "EUR", "GBP": "GBP", "$": "USD",
                   "€": "EUR", "£": "GBP"}[mbid.group(1)]
            mult = 1.0
            if mbid.group(3) and mbid.group(3).lower() in ("million", "m"):
                mult = 1.0
            elif mbid.group(3) and mbid.group(3).lower() == "bn":
                mult = 1000.0
            val = num(mbid.group(2))
            emit(date, "offshore_snp_auction", toks[1], None, "winning_bid",
                 val, f"{cur} million", period=date[:7], page=pg,
                 note=f"vessel={toks[0]}; buyer={toks[3]}")


# ------------------------------- I: renewables lease/auction settlement table
def extract_renewables(doc, date, grid_items=None, tables=None):
    for t in tables or []:
        flat = [str(c) for r in t["rows"] for c in r]
        if not any("Developer" in c for c in flat):
            continue
        hdr = None
        for r in t["rows"]:
            if any("Developer" in str(c) for c in r):
                hdr = r
                break
        if not hdr:
            continue
        idx_dev = next(i for i, c in enumerate(hdr) if "Developer" in str(c))
        idx_val = next((i for i, c in enumerate(hdr) if "Value" in str(c)), None)
        idx_cap = next((i for i, c in enumerate(hdr) if "Capacity" in str(c)), None)
        for r in t["rows"]:
            if r is hdr:
                continue
            if idx_val is None or idx_val >= len(r):
                continue
            dev = str(r[idx_dev]).strip()
            if not dev or dev.lower().startswith("developer"):
                continue
            v = num(r[idx_val])
            if v is not None:
                emit(date, "offshore_renewables_auction", None, "USA",
                     "lease_settlement_value", v, "USD million",
                     period=date[:7], page=t.get("page"),
                     note=f"developer={dev}; development={r[idx_cap] if idx_cap is not None and idx_cap < len(r) else ''}")
            if idx_cap is not None and idx_cap < len(r):
                cap = str(r[idx_cap])
                mc = re.search(r"([\d\.]+)\s*(?:to\s*([\d\.]+))?\s*GW", cap, re.I)
                if mc:
                    emit(date, "offshore_renewables_auction", None, "USA",
                         "lease_capacity_gw",
                         num(mc.group(1)), "GW", period=date[:7], page=t.get("page"),
                         note=f"developer={dev}; raw={cap}")


# --------------------------------------------------- J: feature vessel spec
SPEC_UNITS = [
    (re.compile(r"^Length[:]?\s*([\d\.]+)\s*m", re.I), "length", "m"),
    (re.compile(r"^Breadth[:]?\s*([\d\.]+)\s*m", re.I), "breadth", "m"),
    (re.compile(r"^Deadweight[:]?\s*([\d\.,]+)\s*t", re.I), "deadweight", "tonnes"),
    (re.compile(r"^Accommodation[:]?\s*([\d,]+)\s*persons", re.I), "accommodation", "persons"),
    (re.compile(r"^Main Crane[:]?\s*([\d\.,]+)\s*t", re.I), "main_crane", "tonnes"),
    (re.compile(r"^Deck Area[:]?\s*([\d,]+)\s*m", re.I), "deck_area", "m2"),
    (re.compile(r"^Installed Power[:]?\s*([\d,]+)\s*kW", re.I), "installed_power", "kW"),
    (re.compile(r"^Delivery[:]?\s*((?:19|20)\d\d)", re.I), "delivery_year", "year"),
]


def extract_feature_vessel(doc, date, items):
    for it in items:
        if "Vessel Name:" not in it["text"]:
            continue
        pg = it["page"]
        blob = it["text"]
        y0, y1 = it["bbox"][1], it["bbox"][3]
        # gather companion items in the same spec box
        for j in items:
            if j["page"] != pg or j is it:
                continue
            if y0 - 40 <= j["bbox"][1] <= y1 + 120 and \
               ((":" in j["text"]) and "Vessel Name" not in j["text"]):
                if len(j["text"]) < 600 and re.search(
                        r"(Length|Breadth|Deadweight|Accommodation|Crane|Deck|Power|"
                        r"Owner|Manager|Design|Delivery|ROV|Moonpool|Helideck|DP)",
                        j["text"], re.I):
                    blob += "\n" + j["text"]
        lines = [l.strip() for l in blob.split("\n") if l.strip()]
        name = None
        for l in lines:
            m = re.match(r"^Vessel Name[:]?\s*(.+)$", l, re.I)
            if m:
                name = m.group(1).strip()
                break
        if not name:
            continue
        emit(date, "feature_vessel", name, None, "featured", 1, "count",
             period=date[:7], page=pg)
        for l in lines:
            for rx, metric, unit in SPEC_UNITS:
                m = rx.match(l)
                if m:
                    emit(date, "feature_vessel", name, None, metric,
                         num(m.group(1)), unit, period=date[:7], page=pg)

    # Owner / Manager / Design / DP are text-valued -> record raw
    for it in items:
        if "Vessel Name:" not in it["text"]:
            continue
        pg = it["page"]
        y0, y1 = it["bbox"][1], it["bbox"][3]
        blob = it["text"]
        for j in items:
            if j["page"] != pg or j is it:
                continue
            if y0 - 40 <= j["bbox"][1] <= y1 + 120 and len(j["text"]) < 600:
                blob += "\n" + j["text"]
        sub = re.search(r"Vessel Name[:]?\s*(.+?)(?:\n|$)", blob, re.I)
        name = sub.group(1).strip() if sub else None
        if not name:
            continue
        for metric in ("Owner", "Manager", "Design", "Designer", "Dynamic Positioning",
                       "Helideck", "Moonpool", "ROVs"):
            m = re.search(rf"{metric}[:\s]+([^\n]+)", blob, re.I)
            if m:
                emit(date, "feature_vessel", name, None, metric.lower().replace(" ", "_"),
                     m.group(1).strip()[:120], "text", period=date[:7], page=pg)


# ------------------------------------------------------ K: inactive rig list
RIG_TYPES = {"SS", "JU", "DS"}
_NL = chr(10)
RIG_STATUS_RX = re.compile(r"^(WARM|COLD|HOT)[ ]+STACK$", re.I)
RIG_NAME_RX = re.compile(r"^[A-Z0-9][A-Z0-9 .,'-/&()+]*$")


def _cell_lines(c):
    """A cell can merge several values with newlines (engine-dependent)."""
    return [x.strip() for x in str(c).split(_NL) if x.strip()]


def _is_type(l):
    return l.strip().upper() in RIG_TYPES


def _is_status(l):
    return bool(RIG_STATUS_RX.match(l.strip()))


def _rig_pairs(lines):
    """Split a flat line list into (type, status) pairs if it is all pairs."""
    if len(lines) < 2 or len(lines) % 2:
        return None
    pairs = [(lines[k], lines[k + 1]) for k in range(0, len(lines), 2)]
    if all(_is_type(t) and _is_status(s) for t, s in pairs):
        return pairs
    return None


def _rig_triplets(lines):
    """Split a flat line list into (name, type, status) triplets if it is all
    triplets (one cell holding whole rig rows)."""
    if len(lines) < 3 or len(lines) % 3:
        return None
    trip = [(lines[k], lines[k + 1], lines[k + 2]) for k in range(0, len(lines), 3)]
    if all(_is_type(t) and _is_status(s) and RIG_NAME_RX.match(n) for n, t, s in trip):
        return trip
    return None


def _rig_rows_from_cells(cells):
    """Recover (name, type, status) triples from one grid row.

    Three grid shapes occur in this corpus for the same table:
      A) [name][type][status]        - pdfplumber / some camelot months
      B) [name][type + status]       - camelot when the last two columns
                                       collapse into one cell
      C) [name + type + status]      - everything merged in one cell
    plus every one of them can arrive with the rig columns shifted right by
    several empty cells and with page prose in the leading cells.
    """
    out = []
    n = len(cells)
    for i in range(n):
        lines = _cell_lines(cells[i])
        if not lines:
            continue
        trip = _rig_triplets(lines)
        if trip:
            out.extend(trip)
            continue
        pairs = _rig_pairs(lines)
        if pairs:
            names = _cell_lines(cells[i - 1]) if i >= 1 else []
            if len(names) == len(pairs):
                out.extend((nm, t, s) for nm, (t, s) in zip(names, pairs))
            elif names:
                out.append((names[-1], pairs[0][0], pairs[0][1]))
            continue
        if all(_is_type(l) for l in lines) and i + 1 < n:
            nxt = _cell_lines(cells[i + 1])
            if len(nxt) == len(lines) and all(_is_status(s) for s in nxt):
                names = _cell_lines(cells[i - 1]) if i >= 1 else []
                if len(names) == len(lines):
                    out.extend(zip(names, lines, nxt))
                elif names:
                    out.append((names[-1], lines[0], nxt[0]))
    return out


def extract_inactive(tables, date):
    """Northwest Europe inactive-rig list: NAME | TYPE | STATUS.

    Anchor on CONTENT, never on a column index: the rig table sits inside a
    camelot grid that also carries chart axis labels and page prose, the same
    grid is emitted 2-3 times per page with the columns at different x, and
    the last columns collapse into one cell in some months. Only rows whose
    cells actually read (rig TYPE, *STACK status) are accepted; rows are
    de-duplicated by rig name. Measured against the rendered pages across all
    97 reports (see docs/EXTRACTION_OVERNIGHT_LOG.md 2026-10-08).
    """
    seen = set()
    rows_ = []
    for t in tables:
        flat = [str(c) for r in t["rows"] for c in r]
        if "INACTIVE RIGS" not in " ".join(flat).upper():
            continue
        start = False
        for r in t["rows"]:
            cells = [str(c).strip() for c in r]
            if any("INACTIVE RIGS" in c.upper() for c in cells):
                start = True
                continue
            if not start:
                continue
            if [c.upper() for c in cells[:3]] == ["NAME", "TYPE", "STATUS"]:
                continue
            for nm, tp, st in _rig_rows_from_cells(cells):
                if len(nm) < 3 or not RIG_NAME_RX.match(nm):
                    continue
                if nm.upper() in seen:
                    continue
                seen.add(nm.upper())
                rows_.append((nm, tp, st, t.get("page")))
    for nm, tp, st, pg in rows_:
        emit(date, "rigs_inactive", None, "Northwest Europe", "inactive_rig",
             1, "count", period=date[:7], page=pg,
             note=f"rig={nm}; type={tp}; status={st}")


# ----------------------------------------------------- L: EU/UK ETS prices
ETS_RX = re.compile(r"([\u00a3])\s*(\d{2,4})\s*[\-\u2013\u2014]\s*\u00a3?\s*(\d{2,4})")
ETS_CTX = re.compile(r"(ETS|emissions trading|allowance|per tonne)", re.I)


def extract_ets(doc, date, items):
    for it in items:
        t = re.sub(r"\s+", " ", it["text"])
        if not ETS_CTX.search(t):
            continue
        for m in ETS_RX.finditer(t):
            lo, hi = num(m.group(2)), num(m.group(3))
            ctx = t[max(0, m.start() - 120):m.end() + 120]
            off = m.start() - max(0, m.start() - 120)
            # the scheme label can sit before OR after the figure
            # ("... £190-£220 under the UK's"), so pick the nearest mention by
            # the gap between the token and the figure
            best = None
            for rx, name in ((r"\bEU\b|European", "EU"),
                             (r"\bUK\b|United Kingdom", "UK")):
                for mm2 in re.finditer(rx, t):
                    s, e = mm2.start(), mm2.end()
                    if s >= m.end():
                        gap = s - m.end()
                    elif e <= m.start():
                        gap = m.start() - e
                    else:
                        gap = 0
                    if best is None or gap < best[0]:
                        best = (gap, name)
            region = best[1] if best else "unspecified"
            if re.search(r"\bboth\b", t[m.end():m.end() + 25], re.I):
                region = "EU+UK"
            # the year that governs the figure is the most recent one BEFORE it
            # ("In 2027, allowances are projected at ... and £190-£220 ... rising
            # to £300-£410 ... by 2030"); fall back to the next year after it.
            before = [(m.start() - y.end(), y.group(1))
                      for y in re.finditer(r"\b(20\d\d)\b", t[:m.start()])]
            year = None
            if before:
                d, yv = min(before)
                if d <= 100:
                    year = yv
            if year is None:
                after = [(y.start() - m.end(), y.group(1))
                         for y in re.finditer(r"\b(20\d\d)\b", t[m.end():])]
                year = min(after)[1] if after else None
            emit(date, "carbon_ets", None, region, "ets_allowance_price_low",
                 lo, "GBP/tonne CO2e (MGO combustion)", period=year, page=it["page"],
                 note=t[:250])
            emit(date, "carbon_ets", None, region, "ets_allowance_price_high",
                 hi, "GBP/tonne CO2e (MGO combustion)", period=year, page=it["page"])


# -------------------------------------------------------------------- driver
def load_jsonl(p):
    if not os.path.exists(p):
        return []
    return [json.loads(l) for l in open(p, encoding="utf-8")]


def main():
    docs = sorted(d for d in os.listdir(BASE) if os.path.isdir(os.path.join(BASE, d)))
    extract_ledger()
    for doc in docs:
        date = doc[:10]
        dp = os.path.join(BASE, doc)
        items = load_jsonl(os.path.join(dp, "text.jsonl"))
        tables = load_jsonl(os.path.join(dp, "tables.jsonl"))
        try:
            extract_osv_utilisation(doc, date, items)
            extract_spot_rate_history(doc, date, items)
            extract_ytd(doc, date, items)
            extract_moves(doc, date, items)
            extract_rig_rates(doc, date, items)
            extract_rig_utilisation(doc, date, items)
            extract_auction(doc, date, items)
            extract_renewables(doc, date, tables=tables)
            extract_feature_vessel(doc, date, items)
            extract_inactive(tables, date)
            extract_ets(doc, date, items)
        except Exception as e:
            print("ERROR", doc, type(e).__name__, e, file=sys.stderr)

    # dedupe exact duplicates (report PDFs contain duplicated text layers on
    # the double-page spreads, so the same datum is often parsed twice)
    seen = set()
    deduped = []
    for r in rows:
        k = (r["report_date"], r["section"], r["vessel_class"], r["region"],
             r["metric"], r["period"], r["value"], r["note"])
        if k in seen:
            continue
        seen.add(k)
        deduped.append(r)
    print(f"rows before dedupe: {len(rows)}  after: {len(deduped)}")

    with open(os.path.join(OUT, "rows.jsonl"), "w", encoding="utf-8") as f:
        for r in deduped:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"total rows: {len(deduped)}")
    print(f"{'section':32s} {'metric':28s} {'rows':>7s} {'docs':>5s}")
    for sec in sorted(stats):
        all_rows = [r for r in deduped if r["section"] == sec]
        for met in sorted({r["metric"] for r in all_rows}):
            n = sum(1 for r in all_rows if r["metric"] == met)
            nd = len({r["report_date"] for r in all_rows if r["metric"] == met})
            print(f"{sec:32s} {met:28s} {n:7d} {nd:5d}")


if __name__ == "__main__":
    main()
