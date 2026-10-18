"""Banchero Costa charts: replace "tables" read off a chart by eye; rebuild bar charts from printed labels.

Every Banchero chart is a vector drawing with a bold title above it (e.g. "TD3C VLCC MEG-FAR EAST (USD/DAY)").
The LlamaParse pass turned the charts into tables of round numbers ("Jul-20 | 20000", a seasonality table
that runs to December when the chart stops in April, bar labels with the decimals dropped). Line charts
print no values, so those tables are guesses; most are public index data kept elsewhere in this repo, and
the owner rule is not to estimate charts.

A table is a chart reading when the heading above it is the title of a chart in the PDF: a bold 6.5-10 pt
title line (a wrapped second line joined) with a vector plot right under it.
  - Bar charts whose every bar carries a printed value label are rebuilt exactly from the geometry:
    label above its bar, bar fill matched to the legend swatch (column), bar position matched to the
    category label under the plot (row). The values are the printed labels, verbatim.
  - Every other chart table is replaced, heading included, by
        > **Chart (not transcribed):** <title>. The report prints no values for it.

The PDF text of 2024-2026 issues is read through pdf_glyph_decode (their subset fonts carry a bogus
ToUnicode map). Everything outside the replaced blocks stays byte-identical.

    python scripts/md_cleanup/banchero_chart_note.py [--apply] [--untracked] [files...]
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
import pdf_glyph_decode as G  # noqa: E402

MD_ROOT = ROOT / "data" / "extracted" / "md" / "banchero_costa"
PDF_ROOTS = [ROOT, ROOT.parents[2]] if ROOT.parent.name == "worktrees" else [ROOT]
NUM = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?")
BLOCK = re.compile(r"^(#{2,4}) ([^\r\n]+)\r?\n\r?\n((?:\|[^\n]*\n)+)", re.M)
TABLE_HEAD = re.compile(r"^(Unit|\d{1,2}-[A-Z][a-z]{2}|W-o-W|Y-o-Y)\b")
NOTE = "> **Chart (not transcribed):** {title}. The report prints no values for it."
NOTE_UNTITLED = "> **Chart (not transcribed).** The report prints no values for it."
MON = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*"
AXIS = re.compile(rf"^(?:{MON}[-' ]?\d{{2,4}}|{MON}|(?:19|20)\d\d|Q[1-4][-' ]?\d{{2,4}}|\d{{1,2}}-{MON}(?:-\d{{2,4}})?"
                  rf"|W\d{{1,2}}|Week ?\d+)$", re.I)
TABLE = re.compile(r"(?:^\|[^\n]*\n)+", re.M)
# header words of the tables Banchero prints (rates, S&P / demolition lists): never chart readings
PRINTED_TABLE = re.compile(r"W-o-W|Y-o-Y|M-o-M|Premium|\bUnit\b|VESSEL|IMO|\bDWT\b|BUYER", re.I)


def key(s):
    return re.sub(r"[^A-Z0-9]+", "", s.upper().replace("&AMP;", "&"))


def find_pdf(md_text, stem=None):
    m = re.search(r'^source_file:\s*"?([^"\n]+)', md_text, re.M)
    if m:
        rels = [m.group(1).strip()]
    else:   # some MDs lack source_file: the PDF carries the MD's own name
        y = re.search(r'^year:\s*"?(\d{4})', md_text, re.M)
        if not (y and stem):
            return None
        rels = [f"corpus/01-brokers/banchero_costa/{y.group(1)}/{stem}.pdf"]
    for base in PDF_ROOTS:
        for rel in rels:
            p = base / rel
            if p.exists():
                return p
    return None


def lines_of(spans):
    """Join decoded spans that share a baseline into text lines."""
    rows = []
    for bbox, s, bf, size in sorted(spans, key=lambda x: (round(x[0][3]), x[0][0])):
        bold = "Bold" in (bf or "")
        for r in rows:
            if abs(r["y1"] - bbox[3]) < 2 and -1 < bbox[0] - r["x1"] < 6 and r["bold"] == bold:
                r["t"] += s
                r["x1"] = bbox[2]
                break
        else:
            rows.append({"x0": bbox[0], "y0": bbox[1], "x1": bbox[2], "y1": bbox[3], "t": s, "bold": bold,
                         "size": size})
    for r in rows:
        r["rect"] = pymupdf.Rect(r["x0"], r["y0"], r["x1"], r["y1"])
        r["t"] = r["t"].strip()
    return rows


def _fill(g):
    f = g.get("fill")
    return tuple(round(v, 3) for v in f) if f else None


def _white(f):
    return f is None or all(v > 0.97 for v in f)


def _bars(paths, plot):
    """Filled bar rectangles inside the plot: [(rect, fill)] from 're' items of non-white fills."""
    out = []
    for g in paths:
        f = _fill(g)
        if g["type"] not in ("f", "fs") or _white(f) or not plot.intersects(g["rect"]):
            continue
        for it in g["items"]:
            if it[0] == "re" and 1 < it[1].width < plot.width / 3 and it[1].height > 0.3 \
                    and pymupdf.Rect(it[1]) in plot + (-1, -1, 1, 1):
                out.append((pymupdf.Rect(it[1]), f))
    return out


def _bar_table(rows, nums, paths, plot, region):
    """Rows = category labels under the bars, columns = legend entries matched by fill colour, cells =
    the value label printed on each bar. None unless every bar has exactly placed label and legend."""
    bars = _bars(paths, plot)
    if len(bars) < 2:
        return None
    fills = {f for _, f in bars}
    legend = {}
    for g in paths:
        r, f = g["rect"], _fill(g)
        if f in fills and r.width < 10 and r.height < 10 and region.contains(r) and not (r in plot):
            txt = sorted((t for t in rows if abs((t["y0"] + t["y1"]) / 2 - (r.y0 + r.y1) / 2) < 4
                          and 0 <= t["x0"] - r.x1 < 10), key=lambda t: t["x0"])
            if txt:
                legend[f] = (r.x0, txt[0]["t"])
    if len(fills) == 1 and not legend:
        legend[next(iter(fills))] = (0, "Value")         # single series, no legend
    if set(legend) != fills:
        return None
    series = sorted(legend, key=lambda f: legend[f][0])
    names = {v[1] for v in legend.values()}
    cats = []
    for t in sorted((t for t in rows if plot.y1 - 3 <= t["y0"] <= plot.y1 + 28 and region.contains(t["rect"])
                     and t["t"] not in names and not NUM.fullmatch(t["t"])), key=lambda t: t["y0"]):
        up = next((c for c in cats if 0 <= t["y0"] - c["y1"] < 3
                   and abs((t["x0"] + t["x1"]) / 2 - (c["x0"] + c["x1"]) / 2) < 8), None)
        if up:   # a category label wrapped onto a second line ("Others/" + "Unknown")
            up["t"] += ("" if up["t"].endswith(("/", "-")) else " ") + t["t"]
            up["y1"] = t["y1"]
        else:
            cats.append(dict(t))
    if not cats:
        return None
    table, used = {}, set()
    for rect, f in sorted(bars, key=lambda b: b[0].x0):
        cx = (rect.x0 + rect.x1) / 2
        lab = [(abs((r.x0 + r.x1) / 2 - cx), i) for i, (r, s) in enumerate(nums)
               if abs((r.x0 + r.x1) / 2 - cx) < max(4.0, rect.width * 0.75) and rect.y0 - 13 <= r.y1 <= rect.y0 + 4]
        if not lab:
            return None
        i = min(lab)[1]
        if i in used:
            return None
        used.add(i)
        cat = min(cats, key=lambda t: abs((t["x0"] + t["x1"]) / 2 - cx))
        if abs((cat["x0"] + cat["x1"]) / 2 - cx) > 40 or f in table.get(cat["t"], {}):
            return None
        table.setdefault(cat["t"], {})[f] = nums[i][1]
    order = sorted(table, key=lambda c: next(t["x0"] for t in cats if t["t"] == c))
    body = [[c] + [table[c].get(f, "") for f in series] for c in order]
    if any("" in r for r in body):
        return None
    return [["Category"] + [legend[f][1] for f in series]] + body


def analyse(doc):
    """{title key: [chart]}, chart = {title, page, table or None}, for every titled vector chart."""
    out = {}
    for pno in range(len(doc)):
        page = doc[pno]
        spans = G.decode_page(doc, pno)
        rows = lines_of(spans)
        paths = page.get_drawings()
        nums = [(pymupdf.Rect(b), m.group(0)) for b, s, _, _ in spans for m in NUM.finditer(s)
                if s.strip() == m.group(0)]                     # a span that is exactly one number
        heads = sorted([r for r in rows if r["bold"] and 6.5 <= r["size"] <= 10 and len(key(r["t"])) >= 5],
                       key=lambda r: (r["y0"], r["x0"]))
        used = set()
        for i, t in enumerate(heads):
            if i in used:
                continue
            title, rect = t["t"], pymupdf.Rect(t["rect"])
            for j in range(i + 1, len(heads)):   # wrapped title: next bold line right below, centred alike
                u = heads[j]
                if 0 <= u["y0"] - rect.y1 < 4 and abs((u["x0"] + u["x1"]) / 2 - (rect.x0 + rect.x1) / 2) < 40:
                    title += " " + u["t"]
                    rect |= u["rect"]
                    used.add(j)
            if any(abs(r["y1"] - t["y1"]) < 2 and 0 < r["x0"] - rect.x1 < 250 and TABLE_HEAD.match(r["t"])
                   for r in rows if r is not t):
                continue                              # a printed table's title row ("CAPESIZE  Unit  30-May ...")
            cx = (rect.x0 + rect.x1) / 2
            frames = [g["rect"] for g in paths if g["type"] in ("s", "fs") and g["rect"].width > 40
                      and g["rect"].height > 15 and 0 <= g["rect"].y0 - rect.y1 <= 45
                      and g["rect"].x0 - 20 <= cx <= g["rect"].x1 + 20]
            if not frames:
                continue
            plot = max(frames, key=lambda r: r.width * r.height)
            region = pymupdf.Rect(min(plot.x0, rect.x0) - 50, rect.y0, max(plot.x1, rect.x1) + 50, plot.y1 + 45)
            out.setdefault(key(title), []).append({"title": re.sub(r"\s+", " ", title).strip(), "page": pno + 1,
                                                   "table": _bar_table(rows, nums, paths, plot, region)})
    return out


def _norm(n):
    n = n.replace(",", "").lstrip("+-")
    if "." in n:
        n = n.rstrip("0").rstrip(".")
    return n


def _split_runs(chars, size):
    """PDF text runs adjacent cells together ("115.8113.7"); split a run at character gaps > 0.25 * size."""
    pieces, cur, prev = [], "", None
    for ch, x0, x1 in chars:
        if prev is not None and x0 - prev > 0.25 * size:
            pieces.append(cur)
            cur = ""
        cur += ch
        prev = x1
    pieces.append(cur)
    return pieces


def printed_numbers(doc):
    """Every number printed in the PDF text: decoded glyph text and plain rawdict text (the glyph decoder
    misses some runs that the plain text layer has), both split at cell gaps."""
    out = set()
    for i in range(len(doc)):
        page = doc[i]
        for (_, s, _, size), sp in zip(G.decode_page(doc, i), page.get_texttrace()):
            for piece in _split_runs([(ch, c[3][0], c[3][2]) for ch, c in zip(s, sp["chars"])], size):
                out.update(_norm(n) for n in NUM.findall(piece))
        for b in page.get_text("rawdict")["blocks"]:
            for line in b.get("lines", []):
                for sp in line["spans"]:
                    for piece in _split_runs([(c["c"], c["bbox"][0], c["bbox"][2]) for c in sp["chars"]], sp["size"]):
                        out.update(_norm(n) for n in NUM.findall(piece))
    return out


def _is_axis(cells):
    cells = [c.replace("*", "").strip() for c in cells if c.strip()]
    return len(cells) >= 2 and sum(bool(AXIS.match(c)) for c in cells) >= max(2, 0.6 * len(cells))


def axis_chart_tables(text, printed):
    """Headingless chart readings: tables laid out on a time axis (header row or first column of months /
    years, or a long "Date" column) holding numbers the PDF does not print. [(start, end, title or None)]."""
    out = []
    for m in TABLE.finditer(text):
        lines = m.group(0).strip("\r\n").splitlines()
        if len(lines) < 3:
            continue
        cells = [[c.strip() for c in l.strip().strip("|").split("|")] for l in lines]
        hdr, body = cells[0], cells[2:]
        long_axis = len(hdr) > 1 and hdr[1].strip("* ").lower() in ("date", "period", "time")
        if not (_is_axis(hdr[1:]) or _is_axis([r[0] for r in body if r])
                or (long_axis and _is_axis([r[1] for r in body if len(r) > 1]))):
            continue
        nums = [_norm(n) for r in body for c in r[1:] for n in NUM.findall(c.replace("**", ""))]
        nums = [n for n in nums if n not in ("", "0")]
        if not nums or PRINTED_TABLE.search(lines[0]):
            continue
        # Line-chart readings land on the axis tick labels (Brent 40 / 55 / 70), which ARE printed, so
        # "every number printed" only clears a table that is not a time series down its rows.
        rows_axis = _is_axis([r[0] for r in body if r]) or (long_axis and _is_axis([r[1] for r in body if len(r) > 1]))
        if all(n in printed for n in nums) and not (rows_axis and len(body) >= 3):
            continue
        # the parse often put the chart title into the header cells ("TITLE<br/>Date | TITLE<br/>Value")
        heads = [re.split(r"<br\s*/?>", c)[0].strip("* ") for c in hdr]
        title = heads[0] if heads[0] and (heads.count(heads[0]) >= 2 or "<br" in hdr[0]) else None
        out.append((m.start(), m.end(), title if title and not AXIS.match(title) else None))
    return out


def md_table(rows, nl):
    w = len(rows[0])
    return ("| " + " | ".join(rows[0]) + " |" + nl + "|" + " --- |" * w + nl
            + "".join("| " + " | ".join(r) + " |" + nl for r in rows[1:]))


def match(charts, head):
    cands = charts.get(key(head))
    if not cands:   # the MD heading may carry the chart's subtitle in brackets
        base = key(re.sub(r"\s*\([^)]*\)\s*$", "", head))
        cands = charts.get(base) if len(base) >= 15 else None
    return cands


def process(md, apply, verbose=False, pdf=None):
    raw = md.read_bytes().decode("utf-8")
    pdf = pdf or find_pdf(raw, md.stem)
    if not pdf:
        return None
    charts = analyse(pymupdf.open(pdf))
    out, last, noted, rebuilt = [], 0, 0, 0
    for m in BLOCK.finditer(raw):
        head = m.group(2)
        cands = match(charts, head)
        if not cands:
            continue
        chart = cands.pop(0) if len(cands) > 1 else cands[0]
        nl = "\r\n" if "\r\n" in m.group(0) else "\n"
        out.append(raw[last:m.start()])
        if chart["table"]:
            rows = [r[:] for r in chart["table"]]
            first = m.group(3).split("|")[1].strip()       # keep the MD's own label for the category column
            if first and not NUM.fullmatch(first):
                rows[0][0] = first
            tbl = md_table(rows, nl)
            out.append(f"{m.group(1)} {head}{nl}{nl}{tbl}")
            rebuilt += tbl != m.group(3)
            if verbose:
                print("  REBUILT", head[:70], "|" if tbl == m.group(3) else "| changed")
        else:
            out.append(NOTE.format(title=re.sub(r"\s+", " ", head).strip().strip("*").strip()) + nl)
            noted += 1
            if verbose:
                print("  NOTE   ", head[:70])
        last = m.end()
    new = "".join(out) + raw[last:]
    # tables with no chart heading of their own (e.g. right under a printed table)
    pieces, last = [], 0
    for start, end, title in axis_chart_tables(new, printed_numbers(pymupdf.open(pdf))):
        nl = "\r\n" if "\r\n" in new[start:end] else "\n"
        pieces.append(new[last:start])
        pieces.append((NOTE.format(title=title) if title else NOTE_UNTITLED) + nl)
        noted += 1
        if verbose:
            print("  NOTE (axis table)", title or new[start:end].split("\n")[0][:70])
        last = end
    new = "".join(pieces) + new[last:]
    if apply and new != raw:
        md.write_bytes(new.encode("utf-8"))
    return (noted, rebuilt)


def untracked():
    res = subprocess.run(["git", "ls-files", "--others", "--exclude-standard", str(MD_ROOT)],
                         cwd=ROOT, capture_output=True, text=True)
    return [ROOT / l for l in res.stdout.splitlines() if l.endswith(".md")]


def rel(p):
    try:
        return p.relative_to(ROOT).as_posix()
    except ValueError:
        return str(p)


def main():
    apply = "--apply" in sys.argv
    verbose = "-v" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    files = [Path(a).resolve() for a in args] if args else (untracked() if "--untracked" in sys.argv
                                                             else sorted(MD_ROOT.rglob("*.md")))
    n_note = n_rebuilt = n_files = missing = 0
    for md in files:
        if verbose:
            print(md.name)
        r = process(md, apply, verbose)
        if r is None:
            missing += 1
            print(f"no PDF: {rel(md)}")
            continue
        if r[0] or r[1]:
            n_files += 1
            print(f"{r[0]:3d} noted {r[1]:2d} rebuilt  {rel(md)}")
        n_note += r[0]
        n_rebuilt += r[1]
    print(f"{n_note} chart tables noted, {n_rebuilt} bar tables rebuilt from printed labels, in {n_files} files "
          f"{'(applied)' if apply else '(dry run)'}; {missing} without PDF")


if __name__ == "__main__":
    main()
