"""Rebuild the bodies of the HTML-era Gibson weekly MDs (2023-10 onward) from the archived pages.

The first renderer (scripts/extract/publishers/run_gibson_html.py) kept the prose but:
  - dropped feature sub-headings and the region headings it had no alias for, so paragraphs landed
    under the previous region; special-report sections (S&P, Dry Cargo, Newbuilding ...) were ignored;
  - kept the "Home > title" breadcrumb and the newsletter boilerplate;
  - dropped the rate-table footnote (it records the TCE basis switch to "eco" on 2024-04-26) and
    re-shaped the tables without their column dates / FFA period, printing 0 changes as "-";
  - left the exact chart data (Chart.js wpDataCharts payloads) in gitignored sidecars.

This walks the article DOM in order. Feature charts are one-offs and are written into the MD as exact
data tables (values exactly as the page embeds them). The three recurring spot-rate charts carry
Gibson's daily WS assessments; they go to data/extracted/series/gibson_spot_chart_daily.csv
(one row per date and route, latest edition wins) and the MD keeps a pointer.

Frontmatter and the title/week lines are kept byte-identical.

    python scripts/md_cleanup/gibson_html_rebuild.py [--apply] [files...]
"""
from __future__ import annotations

import csv
import glob
import json
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, Tag

ROOT = Path(__file__).resolve().parents[2]
MAIN = Path("C:/Users/Dell/Github/Shipping")  # corpus HTML lives in the main checkout
SERIES = ROOT / "data" / "extracted" / "series" / "gibson_spot_chart_daily.csv"
RECURRING = ("Crude Tanker Spot Rates (WS)", "Clean Tanker Spot Rates (WS)", "Dirty Product Tanker Spot Rates (WS)")
CHART_RE = re.compile(r"wpDataCharts\[(\d+)\]\s*=\s*\{\s*render_data:\s*(\{.+?\})\s*,\s*(?:engine|container|chart_id)", re.S)
STOP = ("print the report", "get your weekly update", "contact details")


def text(el):
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)).replace(" ,", ",").replace(" .", ".").strip()


def inline(el):
    """Paragraph text keeping the source's own spacing (get_text(' ') would split '<b>US</b>’s')."""
    return re.sub(r"\s+", " ", el.get_text()).strip()


def num(v):
    return v if isinstance(v, (int, float)) else v


def chart_payload(el):
    for sc in el.find_all("script"):
        m = CHART_RE.search(sc.string or sc.get_text() or "")
        if m:
            return json.loads(m.group(2))
    return None


def chart_table(data):
    o = data["options"]["data"]
    labels, sets = o.get("labels", []), o.get("datasets", [])
    md = ["| " + " | ".join([""] + [str(s.get("label", "")).replace("|", "/") for s in sets]) + " |",
          "|" + "---|" * (len(sets) + 1)]
    for i, lab in enumerate(labels):
        row = [str(lab)] + ["" if i >= len(s.get("data", [])) or s["data"][i] is None else str(s["data"][i]) for s in sets]
        md.append("| " + " | ".join(row) + " |")
    return md


def table_md(t):
    rows = [[text(c).replace("|", "/") for c in tr.find_all(["td", "th"])] for tr in t.find_all("tr")]
    rows = [r for r in rows if any(r)]
    if not rows:
        return []
    w = max(len(r) for r in rows)
    rows = [r + [""] * (w - len(r)) for r in rows]
    if any(re.fullmatch(r"[+\-]?[\d,.]+%?", c) for c in rows[0][1:]):
        rows.insert(0, [""] * w)        # the page printed no header row (no column dates): keep it blank
    return ["| " + " | ".join(rows[0]) + " |", "|" + "---|" * w] + ["| " + " | ".join(r) + " |" for r in rows[1:]]


def walk(main):
    """Yield content elements in document order, not descending into the ones we render whole."""
    for el in main.descendants:
        if not isinstance(el, Tag):
            continue
        if el.find_parent(["table", "ul", "ol"]) is not None:
            continue
        if el.name in ("h1", "h2", "h3", "h4", "h5", "h6", "p", "ul", "ol", "table"):
            yield el
        elif el.name == "div" and "wpdatacharts" in " ".join(el.get("class", [])).lower():
            yield el


def rebuild(html, title, daily, report_date):
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("main") or soup
    out, pending_chart_title, in_feature, skip_toc, in_market = [], None, True, False, False
    norm_title = re.sub(r"\W", "", title.lower())
    els = list(walk(main))
    payload = {i: chart_payload(el) for i, el in enumerate(els) if el.name == "div"}

    def chart_next(i):
        for j in range(i + 1, len(els)):
            if els[j].name == "p" and not inline(els[j]):
                continue                          # empty spacer paragraph
            return payload.get(j) is not None
        return False

    def all_bold(p):
        b = "".join(x.get_text() for x in p.find_all(["strong", "b"]) if not x.find_parent(["strong", "b"]))
        return bool(b.strip()) and re.sub(r"\s", "", b) == re.sub(r"\s", "", p.get_text())

    for i, el in enumerate(els):
        cls = " ".join(el.get("class", []))
        t = text(el) if el.name != "p" else inline(el)
        if el.name in ("h2", "h3") and t.lower() in STOP:
            break
        # the chart title is styled several ways over the years: p.is-style-h6, an h2 (styled or plain)
        # or an all-bold paragraph; whatever the markup, a short line directly above a chart titles it
        if t and chart_next(i) and (el.name in ("h2", "h3", "h4", "h5", "h6") or "is-style-h6" in cls
                                    or (el.name == "p" and (all_bold(el) or (len(t.split()) <= 15
                                                                            and not re.search(r"[.!?:;]$", t))))):
            if pending_chart_title is not None:
                out += [("### " if in_feature else "#### ") + pending_chart_title, ""]
            pending_chart_title = t
            continue
        if el.name == "div":
            data = payload.get(i)
            if data is None:
                continue
            name = pending_chart_title or ""
            pending_chart_title = None
            if name in RECURRING:
                o = data["options"]["data"]
                for s in o.get("datasets", []):
                    for lab, v in zip(o.get("labels", []), s.get("data", [])):
                        if v is not None:
                            daily[(name, s.get("label", ""), lab)] = (v, report_date)
                out += [f"*Chart: {name} - Gibson daily assessments, kept in "
                        f"data/extracted/series/gibson_spot_chart_daily.csv*", ""]
            else:
                out += [f"*Chart: {name}*" if name else "*Chart*",
                        "", "Chart data as embedded in the report:", ""] + chart_table(data) + [""]
            continue
        if pending_chart_title is not None:      # a styled line not followed by a chart is a sub-heading
            out += [("### " if in_feature else "#### ") + pending_chart_title, ""]
            pending_chart_title = None
        if el.name == "h2":
            if t.lower() == "table of contents":
                skip_toc = True
                continue
            if re.sub(r"\W", "", t.lower()) == norm_title:
                continue                          # article title, already the MD heading
            in_feature = False
            if "is-style-h2" in cls:
                in_market = t in ("Crude Oil", "Clean Products", "Dirty Products")
            elif in_market:                       # 2026 pages tag the "Med" region as a bare h2
                out += [f"### {t}", ""]
                continue
            out += [f"## {t}", ""]
        elif el.name in ("h3", "h4", "h5", "h6"):
            if t:
                out += [("### " if el.name == "h3" else "#### ") + t, ""]
        elif el.name in ("ul", "ol"):
            if skip_toc:
                skip_toc = False
                continue
            items = [inline(li) for li in el.find_all("li", recursive=False)]
            out += [f"- {i}" for i in items if i] + [""]
        elif el.name == "table":
            out += table_md(el) + [""]
        elif el.name == "p":
            if not t or t.startswith("Home >") or "content-title" in cls:
                continue
            if "is-style-h6" in cls:
                pending_chart_title = t
                continue
            out += [t, ""]
    if pending_chart_title:
        out += [("### " if in_feature else "#### ") + pending_chart_title, ""]
    body = "\n".join(out)
    return re.sub(r"\n{3,}", "\n\n", body).strip() + "\n"


def split_md(raw):
    i = raw.index("## Feature Story")
    j = raw.index("\n", i) + 1
    return raw[:j], raw[j:]


def iso(d):
    return f"{d[6:10]}-{d[3:5]}-{d[0:2]}" if re.match(r"\d\d/\d\d/\d{4}$", d) else d


def write_series(daily):
    """Merge into the CSV keyed on (chart, route, ISO date); for a date in several editions the latest wins."""
    rows = {}
    if SERIES.exists():
        with open(SERIES, encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                k = (r["chart"], r["route"], iso(r["date"]))
                if k not in rows or rows[k][1] <= r["report_date"]:
                    rows[k] = (r["ws"], r["report_date"])
    for (chart, route, d), (v, rd) in daily.items():
        k = (chart, route, iso(d))
        if k not in rows or rows[k][1] <= rd:
            rows[k] = (str(v), rd)
    with open(SERIES, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["date", "chart", "route", "ws", "report_date"])
        for k in sorted(rows, key=lambda k: (k[2], k[0], k[1])):
            w.writerow([k[2], k[0], k[1], rows[k][0], rows[k][1]])


def main():
    apply = "--apply" in sys.argv
    files = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not files:
        files = [f for f in sorted(glob.glob(str(ROOT / "data/extracted/md/gibson/*/*.md")))
                 if 'format: "html"' in open(f, encoding="utf-8").read()[:800]]
    daily = {}
    for f in files:
        raw = open(f, encoding="utf-8").read()
        rel = re.search(r'^source_file: "(.*)"', raw, re.M).group(1)
        src = ROOT / rel if (ROOT / rel).exists() else MAIN / rel
        if not src.exists():
            print(f"skip (no archived html): {Path(f).name}")
            continue
        title = re.search(r'^title: "(.*)"', raw, re.M).group(1)
        rdate = re.search(r'^issue_date: "(.*)"', raw, re.M).group(1)
        keep, _ = split_md(raw)
        new = rebuild(src.read_text(encoding="utf-8"), title, daily, rdate)
        if apply:
            with open(f, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(keep + "\n" + new)
        else:
            print(f"===== {Path(f).name}")
            print(new)
    if apply:
        write_series(daily)
        print(f"{len(daily)} daily chart points")


if __name__ == "__main__":
    main()
