"""
China bauxite (HS 26060000) and alumina (HS 28182000) imports - GACC figures as published by SMM
=================================================================================================
GACC releases the detailed (8-digit, by-country) customs data around the 20th of the following month. The
only places it is printed are stats.customs.gov.cn (a JavaScript challenge answers every scripted client) and
chinadata.live (its trade API was retired in 2026-10 and its product pages now sit behind a challenge too).

Shanghai Metals Market (news.metal.com) publishes the GACC figures the same day, as text:
  "According to General Administration of Customs data, domestic bauxite imports totalled 19.04 million
   tonnes in July 2026 ... Domestic imports of Guinean bauxite stood at 14.88 million tonnes in July 2026"
  "... alumina imports stood at 367,000 tonnes"
Checked against the GACC query export for 2026-07 (Guinea 14,879,453.5 t; alumina 366,577.68 t): equal at the
precision SMM prints (2026-04 Guinea: SMM 16.423 Mt, the later export 16,370,579 t - an early print). Articles are found through SMM's own monthly sitemaps (robots.txt allows them), so no
search engine sits in between.

Outputs:
  data/commodities/guinea_bauxite_exports.csv   monthly_bilateral_mirror row: China imports from Guinea (t);
                                                the source quote also carries the China total and Australia
  data/commodities/minor_bulks_monthly.csv      Alumina / China imports: metric_tonnes

Rules:
  - single-month figures only: sentences about cumulative, year-to-date or year-earlier figures are skipped, and
    the patterns read gross imports only ("alumina imports stood at", "imported N t of alumina"), never net ones
  - the article must be published after the month it reports and name that month
  - a figure is written as printed (SMM rounds some months to 10 kt); rows from a GACC query export are never
    overwritten, an SMM row is replaced only by a more precise SMM figure for the same month
  - nothing is derived: no value-share or USD-based tonnes

Usage: fetch_gacc_bauxite_alumina.py [--months N]   (default: the last 4 complete months)
"""

import csv
import html
import logging
import re
import sys
import time
from datetime import date
from pathlib import Path

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("gacc_bauxite_alumina")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
COMMODITIES_DIR = BASE_DIR / "data" / "commodities"
GUINEA_CSV = COMMODITIES_DIR / "guinea_bauxite_exports.csv"
MINOR_BULKS_CSV = COMMODITIES_DIR / "minor_bulks_monthly.csv"

SITEMAP_URL = "https://news.metal.com/sitemap/sitemap-newscontent-{ym}.xml"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
PUBLISHER = "Shanghai Metals Market (SMM), quoting GACC customs data"

MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
          "november", "december"]
# sentences that do not carry a single-month import figure
SKIP_SENTENCE = re.compile(r"cumulative|year[- ]to[- ]date|\bytd\b|first \w+ months|january\s*(?:[-–‑]|to\b)|jan\s*[-–‑]|"
                           r"\bh1\b|\bh2\b|quarter|same period|year earlier|last year|forecast|expected|"
                           r"estimate", re.I)
# capitalised month names only, and "May" only with a year or after "in" (the modal verb is not a month)
MONTH_RE = re.compile(r"\b(January|February|March|April|June|July|August|September|October|November|December|"
                      r"(?<=in )May\b|May(?= \d{4}))(?:\s+(\d{4}))?")
VERB = r"(?:totall?ed|stood at|reached|were|was|hit|amounted to|came in at|of)"
QTY = r"([\d,]+(?:\.\d+)?)\s*(million\s+)?(?:metric\s+)?(?:tonnes|tons|mt)\b"


def _get(url: str) -> str:
    for attempt in range(3):
        try:
            r = requests.get(url, headers=HEADERS, timeout=40)
            r.raise_for_status()
            return r.content.decode("utf-8", errors="ignore")
        except Exception as exc:  # noqa: BLE001
            logger.warning("GET %s failed (%s), attempt %d", url, exc, attempt + 1)
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"unavailable: {url}")


def _shift(ym: tuple[int, int], k: int) -> tuple[int, int]:
    n = ym[0] * 12 + ym[1] - 1 + k
    return n // 12, n % 12 + 1


def article_urls(publish_months: list[tuple[int, int]]) -> list[str]:
    """English bauxite / alumina trade articles listed in SMM's monthly sitemaps."""
    urls = []
    for y, m in publish_months:
        try:
            xml = _get(SITEMAP_URL.format(ym=f"{y}{m:02d}"))
        except RuntimeError as exc:
            logger.warning("%s", exc)
            continue
        for u in re.findall(r"<loc>([^<]+)</loc>", xml):
            slug = u.rsplit("/", 1)[-1].lower()
            if re.search(r"news\.metal\.com/[a-z]{2}/newscontent", u):
                continue     # translated copies
            if "traded" in slug or re.search(r"(?:^|-)ports?(?:-|$)", slug):
                continue     # spot deal notes, port inventories
            if ("bauxite" in slug and "import" in slug) or ("alumina" in slug and re.search(r"import|export|trade", slug)):
                urls.append(u)
    return urls


def article_text(url: str) -> tuple[date | None, str]:
    """(publish date, body text) of an SMM news page."""
    s = _get(url)
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", s, flags=re.S)
    t = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t)))
    m = re.search(r"Published\s*:\s*([A-Z][a-z]{2}) (\d{1,2}), (\d{4})", t)
    if not m:
        return None, ""
    pub = date(int(m[3]), [x[:3] for x in MONTHS].index(m[1].lower()) + 1, int(m[2]))
    body = re.sub(r"^\s*\d{1,2}:\d{2} \(GMT[^)]*\)\s*(?:Source\s*:\s*\S+\s*)?(?:Share\s*)*(?:Save\s*)?", "",
                  t[m.end():])
    end = min([i for i in (body.find("Data Source Statement"), body.find("Related News")) if i > 0] or [len(body)])
    return pub, body[:end]


def _sentences(body: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<!\d)\.(?!\d)|\.(?=\s)", body) if s.strip()]


def _tonnes(num: str, million: str | None) -> float:
    v = float(num.replace(",", ""))
    return v * 1e6 if million else v


def _decimals(num: str) -> int:
    return len(num.split(".")[1]) if "." in num else 0


def report_month(pub: date, body: str) -> tuple[int, int] | None:
    """The month an article reports: the month named in it that is before the publish month (latest such)."""
    named = set()
    for mon, yr in MONTH_RE.findall(body):
        idx = MONTHS.index(mon.lower()) + 1
        y = int(yr) if yr else (pub.year if idx < pub.month else pub.year - 1)
        named.add((y, idx))
    before = [ym for ym in named if ym < (pub.year, pub.month) and ym >= _shift((pub.year, pub.month), -3)]
    return max(before) if before else None


def _month_ok(sentence: str, ym: tuple[int, int]) -> bool:
    """A figure counts when its sentence names the reported month, or names no month at all ("that month")."""
    names = [n for n, _ in MONTH_RE.findall(sentence)]
    return not names or any(n.lower() == MONTHS[ym[1] - 1] for n in names)


def _customs(body: str) -> bool:
    """Only articles that quote the customs release (weekly reviews quote shipments and port arrivals)."""
    return bool(re.search(r"General Administration of Customs|customs data", body, re.I))


def parse_bauxite(body: str, ym: tuple[int, int]) -> dict:
    """{total, guinea[, australia]} or {}: the Guinea figure is kept only next to the China total of the same
    article, and both must be import sentences."""
    if not _customs(body):
        return {}
    out = {}
    pats = {
        "total": r"bauxite imports(?: \w+){0,3}? " + VERB + r"\s+" + QTY,
        "guinea": r"Guinea(?:n bauxite)?\b[^.;%]{0,60}?(?:with|" + VERB[3:-1] + r")\s+" + QTY,
        "australia": r"Australia(?:n bauxite)?\b[^.;%]{0,60}?(?:with|" + VERB[3:-1] + r")\s+" + QTY,
    }
    for s in _sentences(body):
        if SKIP_SENTENCE.search(s) or not _month_ok(s, ym) or "import" not in s.lower():
            continue
        for key, pat in pats.items():
            m = re.search(pat, s, re.I)
            if m and key not in out:
                out[key] = {"tonnes": _tonnes(m[1], m[2]), "decimals": _decimals(m[1]), "quote": s}
    g, tot = out.get("guinea"), out.get("total")
    if not (g and tot):
        return {}
    if not (3e6 <= g["tonnes"] <= 40e6 and 5e6 <= tot["tonnes"] <= 50e6) or g["tonnes"] > tot["tonnes"]:
        logger.warning("bauxite figures out of range or Guinea above the total, article dropped: %s | %s",
                       g["quote"], tot["quote"])
        return {}
    return out


def parse_alumina(body: str, ym: tuple[int, int]) -> dict | None:
    if not _customs(body):
        return None
    pats = [r"alumina imports(?: \w+){0,2}? " + VERB + r"\s+" + QTY,
            r"imported\s+" + QTY + r" of alumina"]
    for s in _sentences(body):
        if SKIP_SENTENCE.search(s) or not _month_ok(s, ym):
            continue
        for pat in pats:
            m = re.search(pat, s, re.I)
            if m:
                t = _tonnes(m[1], m[2])
                if 10_000 <= t <= 3_000_000:
                    return {"tonnes": t, "decimals": _decimals(m[1]) - (6 if m[2] else 0), "quote": s}
                logger.warning("alumina figure outside 10 kt-3 Mt, dropped: %s", s)
    return None


def _read(path: Path) -> tuple[list[str], list[dict]]:
    with open(path, encoding="utf-8", newline="") as fh:
        rd = csv.DictReader(fh)
        return list(rd.fieldnames or []), list(rd)


def _write(path: Path, fields: list[str], rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def write_guinea(period: str, rec: dict, url: str) -> bool:
    fields, rows = _read(GUINEA_CSV)
    g = rec["guinea"]
    quote = g["quote"]
    for k in ("total", "australia"):
        if k in rec and rec[k]["quote"] != quote:
            quote += " | " + rec[k]["quote"]
    new = {k: "" for k in fields}
    new.update({"date": f"{period}-01", "tonnes": f"{g['tonnes']:.1f}", "import_volume_t": f"{g['tonnes']:.1f}",
                "company": "Bilateral Mirror (China Imports from Guinea)", "source_url": url, "publisher": PUBLISHER,
                "source_quote": f"SMM: {quote}", "method": f"SMM report of GACC customs data (HS 26060000), "
                f"printed to {g['decimals']} decimals", "granularity": "monthly_bilateral_mirror"})
    for i, r in enumerate(rows):
        if r.get("granularity") == "monthly_bilateral_mirror" and r.get("date") == new["date"]:
            if not r.get("method", "").startswith("SMM"):
                return False                      # GACC query export / older official row: keep
            old_dec = int(re.search(r"(\d+) decimals", r["method"])[1]) if "decimals" in r["method"] else 0
            if g["decimals"] <= old_dec:
                return False
            rows[i] = new
            break
    else:
        rows.append(new)
    rows.sort(key=lambda r: r.get("date", ""))
    _write(GUINEA_CSV, fields, rows)
    logger.info("Guinea bauxite %s: %s t (%s)", period, new["tonnes"], url)
    return True


def write_alumina(period: str, rec: dict, url: str) -> bool:
    fields, rows = _read(MINOR_BULKS_CSV)
    src = f"China GACC (HS 28182000) as published by SMM: {rec['quote']}"
    for r in rows:
        if r.get("commodity") == "Alumina" and r.get("reporter_country") == "China" and r["date"] == f"{period}-01":
            if r.get("metric_tonnes"):
                return False                      # tonnes already stored (GACC export or earlier SMM read)
            r["metric_tonnes"] = f"{rec['tonnes']:.2f}"
            r["source"] = (r["source"] + "; tonnes: " if r.get("source") else "") + src
            r["source_url"] = url
            break
    else:
        new = {k: "" for k in fields}
        new.update({"date": f"{period}-01", "period": period.replace("-", ""), "commodity": "Alumina",
                    "trade_flow": "Imports", "reporter_country": "China", "partner_country": "World",
                    "hs_code": "2818", "metric_tonnes": f"{rec['tonnes']:.2f}",
                    "vessel_demand_impact": "Handymax / Supramax", "source": src, "source_url": url})
        rows.append(new)
    rows.sort(key=lambda x: (x.get("commodity", ""), x.get("date", "")))
    _write(MINOR_BULKS_CSV, fields, rows)
    logger.info("Alumina %s: %.0f t (%s)", period, rec["tonnes"], url)
    return True


def run(n_months: int = 4) -> int:
    today = date.today()
    targets = [_shift((today.year, today.month), -k) for k in range(n_months, 0, -1)]
    publish = sorted({_shift(t, k) for t in targets for k in (1, 2) if _shift(t, k) <= (today.year, today.month)})
    urls = article_urls(publish)
    logger.info("SMM candidate articles: %d (sitemaps %s)", len(urls), [f"{y}-{m:02d}" for y, m in publish])

    baux: dict[tuple[int, int], tuple[dict, str]] = {}
    alum: dict[tuple[int, int], tuple[dict, str]] = {}
    for u in urls:
        try:
            pub, body = article_text(u)
        except RuntimeError as exc:
            logger.warning("%s", exc)
            continue
        ym = report_month(pub, body) if pub else None
        if ym not in targets:
            continue
        slug = u.rsplit("/", 1)[-1].lower()
        if "bauxite" in slug:
            rec = parse_bauxite(body, ym)
            if "guinea" in rec and ("guinea" not in baux.get(ym, ({}, ""))[0]
                                    or rec["guinea"]["decimals"] > baux[ym][0]["guinea"]["decimals"]):
                baux[ym] = (rec, u)
        else:
            rec = parse_alumina(body, ym)
            if rec and (ym not in alum or rec["decimals"] > alum[ym][0]["decimals"]):
                alum[ym] = (rec, u)
        time.sleep(1)

    changed = 0
    for ym in targets:
        period = f"{ym[0]}-{ym[1]:02d}"
        if ym in baux:
            changed += write_guinea(period, *baux[ym])
        else:
            logger.info("Guinea bauxite %s: no SMM article with a single-month figure yet", period)
        if ym in alum:
            changed += write_alumina(period, *alum[ym])
        else:
            logger.info("Alumina %s: no SMM article with a single-month import figure yet", period)
    logger.info("Done: %d row(s) written", changed)
    # GACC publishes month M around the 20th of M+1; fail only when month M-2 is still missing after that
    due = _shift((today.year, today.month), -2 if today.day < 25 else -1)
    if due in targets and (due not in baux or due not in alum):
        _, grows = _read(GUINEA_CSV)
        have = any(r.get("granularity") == "monthly_bilateral_mirror" and r["date"][:7] == f"{due[0]}-{due[1]:02d}"
                   for r in grows)
        if not have:
            logger.error("Guinea bauxite %d-%02d is due and was not found", *due)
            return 1
    return 0


if __name__ == "__main__":
    n = int(sys.argv[sys.argv.index("--months") + 1]) if "--months" in sys.argv else 4
    sys.exit(run(n))
