"""GMS market commentary series from the issue MDs (one MD per issue, front matter checked against the print).

    python scripts/extract/publishers/gms_commentary_series.py [--apply] [--out CSV]

Rows: the cover editorial ("General / Editorial": headline, the cover highlights, every paragraph) and each country
page (Bangladesh, India, Pakistan, Turkey: headline, margin notes, paragraphs up to the sales block). The text is the
MD's text, so the series carries the lead paragraph and keeps margin notes out of the body. Rebuilt in full from the
MDs on every run (an issue without an MD has no row), written LF.
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MD_ROOT = ROOT / "data" / "extracted" / "md" / "hellenic" / "demolition" / "gms"
OUT = ROOT / "data" / "extracted" / "series" / "gms_market_commentary_series.csv"
COLUMNS = ["issue_date", "report_week", "section", "headline", "highlights", "body_text", "source_file"]
COUNTRIES = ("Bangladesh", "India", "Pakistan", "Turkey")
# a country page's text ends at its sales block; the cover's rankings table (and its "*Small LDT" footnote) sits
# inside the editorial, which goes on after it (announcements), so tables, sub-headings and figure notes are skipped
STOP = re.compile(r"^(#{1,2} |### Market Sales Reported|\*\*NO MARKET SALES REPORTED\*\*)")
SKIP = re.compile(r"^(\||### |> )")


def front_matter(text: str) -> dict[str, str]:
    m = re.match(r"---\r?\n(.*?)\r?\n---\r?\n", text, re.S)
    fm = {}
    for line in (m.group(1).splitlines() if m else []):
        k, _, v = line.partition(":")
        if _ and not line.startswith(" "):
            fm[k.strip()] = v.strip().strip("'\"")
    return fm


def sections(body: str) -> list[tuple[str, list[str]]]:
    """[(H1 title, lines under it)]"""
    out: list[tuple[str, list[str]]] = []
    for line in body.splitlines():
        if line.startswith("# "):
            out.append((line[2:].strip(), []))
        elif out:
            out[-1][1].append(line)
    return out


def block(lines: list[str]) -> tuple[str, str, str]:
    """(headline, margin notes, paragraphs) of one commentary H1 block."""
    headline, notes, paras, after_table = "", "", [], False
    for line in lines:
        s = line.strip()
        if s.startswith("## ") and not headline and not paras:
            headline = s[3:].strip()
            continue
        if s.startswith("*Margin notes:") and not paras:
            notes = s[len("*Margin notes:"):].rstrip("*").strip()
            continue
        if STOP.match(s):
            break
        if SKIP.match(s):
            after_table = s.startswith("|")
            continue
        if not s:
            continue
        if after_table and re.match(r"^\*[^*].{0,40}$", s):   # table footnote ("*Small LDT")
            continue
        after_table = False
        paras.append(s)
    return headline, notes, "\n\n".join(paras)


def issue_rows(md: Path) -> list[dict[str, str]]:
    text = md.read_bytes().decode("utf-8").replace("\r\n", "\n")
    fm = front_matter(text)
    base = {"issue_date": fm.get("issue_date", ""), "report_week": fm.get("report_week", ""),
            "source_file": Path(fm.get("source_file", "")).name}
    secs = dict((t, ls) for t, ls in reversed(sections(text.split("\n---\n", 1)[-1])))   # first occurrence wins
    rows = []
    highlights = " | ".join(l.strip()[2:].strip() for l in secs.get("Highlights", []) if l.strip().startswith("- "))
    if "Market Commentary" in secs:
        h, _n, b = block(secs["Market Commentary"])
        rows.append({**base, "section": "General / Editorial", "headline": h, "highlights": highlights, "body_text": b})
    else:   # web-article issues: "# GMS Week 1 – STASIS!" then "## Market Commentary" up to the rankings
        for title, ls in secs.items():
            i = next((k for k, l in enumerate(ls) if l.strip() == "## Market Commentary"), None)
            if i is None:
                continue
            # the site's breadcrumb and attribution lines are not the editorial
            body = [l for l in ls[i + 1:] if not re.match(r"\s*(in Weekly Demolition Reports \d|Source: GMS)", l)]
            _h, _n, b = block(["## x"] + body)
            h = re.split(r"\s+[–-]\s+", title, maxsplit=1)[-1] if re.match(r"GMS Week \d+\s+[–-]", title) else ""
            rows.append({**base, "section": "General / Editorial", "headline": h, "highlights": highlights, "body_text": b})
            break
    for c in COUNTRIES:
        if c in secs:
            h, n, b = block(secs[c])
            if h or b:
                rows.append({**base, "section": c, "headline": h, "highlights": n, "body_text": b})
    return rows


def build() -> list[dict[str, str]]:
    rows = []
    for md in sorted(MD_ROOT.glob("*/*.md")):
        rows.extend(issue_rows(md))
    rows.sort(key=lambda r: (r["issue_date"], r["section"]))
    return rows


def main_write(dest: Path | None) -> list[dict[str, str]]:
    rows = build()
    issues = {r["issue_date"] for r in rows}
    empty = [r for r in rows if not r["body_text"]]
    print(f"{len(rows)} rows from {len(issues)} issues; {len(empty)} without body")
    for r in empty[:10]:
        print(f"  empty: {r['issue_date']} {r['section']}")
    if dest:
        with open(dest, "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=COLUMNS, lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
        print(f"wrote {dest}")
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--apply", action="store_true", help="write the series CSV")
    ap.add_argument("--out", help="write here instead of the series path")
    a = ap.parse_args()
    main_write(Path(a.out) if a.out else (OUT if a.apply else None))
    return 0


if __name__ == "__main__":
    sys.exit(main())
