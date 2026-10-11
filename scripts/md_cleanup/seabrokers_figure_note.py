"""Seabrokers figure tables the parser estimated by eye: replaced by a note, or corrected to the printed label.

Seabrokers reprints third-party figures (Norwegian Offshore Directorate, Westwood, IEA, Wood Mackenzie, Rystad,
vendor screenshots). The parser turned several of them into tables of values that the page never prints (e.g. a
component market series of 100, 120, 150... with the other columns an exact half and tenth of it). The scan
(--scan) lists tables whose numbers are missing from the page's text layer and OCR; that is only a lead (labels
inside images can be too small for OCR, and small integers match by chance). Each lead was checked against the page
render, and the verdicts are listed in DECISIONS:

  note  - the figure prints no values (bars/lines/areas only), or prints values the table assigns wrongly:
          the table lines become a note, and the table leaves the .tables.json sidecar
  fix   - the figure prints the values and the table holds one misread: that cell is set to the printed label

Tables whose values the figure prints, and the table matches, are kept (floating wind portfolio 2024-10, Hornbeck/
Helix revenue pies 2026-04, SURF by depth 2024-08, Hormuz infographic 2026-05, Seabay / SeaPortal screenshots).
Only the listed table lines change.

    python scripts/md_cleanup/seabrokers_figure_note.py [--apply] [--scan]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MD_ROOT = ROOT / "data" / "extracted" / "md" / "seabrokers"
MIRROR = ROOT / "corpus" / "05-seabrokers"            # run_seabrokers_llamaparse.py writes each MD to both places
NOTE = ("> **Chart not transcribed.** The figure prints no values{why}; the table the parser estimated from the "
        "image was removed. See the source PDF.")
TABLE = re.compile(r"^\s*\|")

# (issue date, first header cells, first cell of the first body row) -> verdict
DECISIONS = [
    ("2020-02-01", "Category", "**Vessel Availability**", "note", ""),           # SeaPortal mini bar chart
    ("2020-02-01", "Month", "Feb 19", "note", ""),                                # SeaPortal "Average Rates"
    ("2020-02-01", "Date", "26/01", "note", ""),                                  # SeaPortal "Utilisation"
    ("2021-08-01", "Year", "2014", "note", ""),                                   # Wood Mackenzie MCR area chart
    ("2021-11-01", "Category", "Loading History", "note", ""),                    # software advert dashboard
    ("2024-03-01", "Year", "2015", "note", ""),                                   # Wood Mackenzie FID count bars
    ("2024-03-01", "Year", "2015|Project capex", "note", ""),                     # Wood Mackenzie capex bars
    ("2024-06-01", "Year", "2019", "note", ""),                                   # Westwood performance bars/lines
    ("2024-06-01", "Category", "Mid-Large", "note", ""),                          # Westwood bubble chart
    ("2024-08-01", "Year", "2018-20", "note", ""),                                # Rystad subsea expenditure bars
    ("2024-09-01", "Category", "Revenue", "note", ""),                            # Offshore Directorate bars
    ("2024-09-01", "Region", "NCS", "note", ""),                                  # Offshore Directorate bars
    ("2025-09-01", "Year", "2000", "note", ""),                                   # IEA Figure 1 areas/bars
    ("2025-09-01", "Year", "2000-05", "note", ""),                                # IEA Figure 6 areas/bars
    ("2025-10-01", "Region", "China", "note",
     " it can be matched to (the donut prints 49/17/8/6/4/3/3/10% and ~197 GW; the regions are flags only)"),
    ("2025-10-01", "Year", "2015", "note", ""),                                   # Rystad annual additions bars
    ("2026-05-01", "Date", None, "note", ""),                                     # Brent price line chart
    ("2026-06-01", "Year", "2021", "note", ""),                                   # Westwood discovered resource
    ("2026-06-01", "Category", "Onshore", "note", ""),                            # Westwood success by depth
    ("2026-06-01", "Reservoir Age", "Neogene", "note", ""),                       # Westwood discovery size bars
    ("2024-08-01", "Country", "Brazil", "fix", {"US": ("16%", "15%")}),          # pie label prints 15%
    ("2026-08-01", "Vessel", "MV Viking Provider", "fix", {"MV Orion Mariner": ("22.89", "22.86")}),
]


def cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def blocks(lines: list[str]):
    """(start, end, heading) of each markdown table; heading is the nearest non-empty line above."""
    i = 0
    while i < len(lines):
        if TABLE.match(lines[i]):
            j = i
            while j < len(lines) and TABLE.match(lines[j]):
                j += 1
            k = i - 1
            while k >= 0 and not lines[k].strip():
                k -= 1
            yield i, j, (lines[k].strip() if k >= 0 else "")
            i = j
        else:
            i += 1


def matches(lines, a, b, head, first) -> bool:
    if b - a < 3 or cells(lines[a])[0] != head:
        return False
    if first is None:
        return True
    if "|" in first:                                  # "row cell|second header cell" disambiguates same-shape tables
        first, h2 = first.split("|")
        if len(cells(lines[a])) < 2 or cells(lines[a])[1] != h2:
            return False
    return cells(lines[a + 2])[0] == first


def sidecar(md: Path, drop: list[list[str]], fixes: list[tuple[list[str], dict]], apply: bool) -> int:
    side = md.with_suffix(".tables.json")
    if not side.exists():
        return 0
    raw = side.read_bytes().decode("utf-8")
    j = json.loads(raw)
    n = 0
    keep = []
    for t in j.get("tables", []):
        cols = [str(c).strip() for c in t.get("columns", [])]
        if any(cols == [c.replace("\\*", "*") for c in d] or cols == d for d in drop):
            n += 1
            continue
        for hdr, fix in fixes:
            if cols == hdr:
                for r in t.get("rows", []):
                    row_key = str(r.get(hdr[0], "")).strip()
                    for col, val in r.items():
                        for label, (old, new) in fix.items():
                            if row_key == label and str(val).strip() == old:
                                r[col] = new
                                n += 1
        keep.append(t)
    if not n:
        return 0
    j["tables"] = keep
    if "tables_count" in j:
        j["tables_count"] = len(keep)
    out = json.dumps(j, ensure_ascii=True, indent=2)
    if "\r\n" in raw:
        out = out.replace("\n", "\r\n")
    if raw.endswith(("\n", "\r\n")):
        out += "\r\n" if raw.endswith("\r\n") else "\n"
    if apply:
        side.write_bytes(out.encode("utf-8"))
    return n


def fix_md(raw: str, date: str) -> tuple[str, list[str], list[list[str]], list[tuple[list[str], dict]]]:
    lines = raw.splitlines(keepends=True)
    nl = "\r\n" if lines and lines[0].endswith("\r\n") else "\n"
    done, drop, fixes, edits = [], [], [], []
    todo = [d for d in DECISIONS if d[0] == date]
    for a, b, _ in blocks(lines):
        for d in todo:
            _, head, first, verdict, arg = d
            if not matches(lines, a, b, head, first):
                continue
            todo.remove(d)
            hdr = cells(lines[a])
            if verdict == "note":
                drop.append(hdr)
                edits.append((a, b, [NOTE.format(why=arg) + nl]))
            else:
                new = list(lines[a:b])
                for k in range(2, len(new)):
                    parts = new[k].split("|")                 # ["", " label ", " v1 ", ..., "\n"]
                    for label, (old, val) in arg.items():
                        if parts[1].strip() == label:
                            parts = [p.replace(old, val, 1) if p.strip() == old else p for p in parts]
                    new[k] = "|".join(parts)
                fixes.append((hdr, arg))
                edits.append((a, b, new))
            done.append(f"{verdict}: {hdr[:3]} / {first}")
            break
    for a, b, rep in reversed(edits):
        lines[a:b] = rep
    missing = [f"NOT FOUND: {d[1]} / {d[2]}" for d in todo]
    return "".join(lines), done + missing, drop, fixes


def scan() -> None:
    """Leads only: tables whose numbers are missing from the PDF text layer (check each against the page render)."""
    import pymupdf
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import intermodal_table_rebuild as R
    from star_asia_page_rebuild import nums
    for md in sorted(MD_ROOT.rglob("*.md")):
        raw = md.read_bytes().decode("utf-8")
        pdf = R.source_pdf(raw)
        if pdf is None:
            continue
        printed = set().union(*(nums(p.get_text()) for p in pymupdf.open(pdf)))
        lines = raw.splitlines()
        for a, b, h in blocks(lines):
            if h.startswith(">"):
                continue
            n = nums("\n".join(lines[a + 2:b]))
            if len(n) >= 3 and len(n - printed) / len(n) > 0.2:
                print(f"{md.name} L{a + 1} | {h[:60]} | {len(n - printed)}/{len(n)} unprinted")


def main() -> int:
    if "--scan" in sys.argv:
        scan()
        return 0
    apply = "--apply" in sys.argv
    for date in sorted({d[0] for d in DECISIONS}):
        for md in sorted(MD_ROOT.glob(f"{date[:4]}/{date}_*.md")):
            raw = md.read_bytes().decode("utf-8")
            new, log, drop, fixes = fix_md(raw, date)
            side = sidecar(md, drop, fixes, apply)
            mirror = MIRROR / md.parent.name / md.name
            same = mirror.exists() and mirror.read_bytes() == md.read_bytes()
            print(md.relative_to(ROOT).as_posix(), "| sidecar", side, "| mirror", "same" if same else "differs: left")
            for x in log:
                print("   ", x)
            if apply and new != raw:
                md.write_bytes(new.encode("utf-8"))
                if same:                              # keep the corpus copy identical to the extracted MD
                    mirror.write_bytes(new.encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
