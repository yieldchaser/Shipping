"""Rebuild the bodies of the PDF-era Gibson weekly MDs (2021-2023) from the PDF text layer.

The first extraction glued chart axis/legend text into the prose, cut sentences that wrap around a
chart (the rest of the sentence and following paragraphs were lost), dropped numbers from some
fixture quotes ("30 x ws for X-Med"), duplicated some paragraphs, and rendered the rate tables
without their column dates, FFA period or footnote and with "+0" changes shown as "-".

All issues share one template (verified over the 109 PDFs):
  - page header/footer bands (y < 95, y > 785) are boilerplate;
  - body text is near-black 9.5-12.5pt; chart ticks, legends and notes are <= 9.4pt and dropped;
  - 24pt headings are the sections (Crude Oil, Clean Products, Dirty Products), 14pt navy the
    regions; 14pt black bold on market pages are the recurring spot-rate chart titles (Baltic data,
    public: dropped); on the feature page bold one-line blocks are chart titles (kept as captions,
    no values);
  - the PDFs are written in reading order and MuPDF keeps wrapped text, inset tables and chart labels
    in separate blocks, so blocks are walked in native order;
  - inset data tables on the feature page are rebuilt as Markdown tables;
  - the rates page has positional tables with two-line headers.

Frontmatter and the title/week lines are kept byte-identical; only the body below them is rebuilt.

    python scripts/md_cleanup/gibson_pdf_rebuild.py [--apply] [files...]
"""
from __future__ import annotations

import glob
import re
import sys
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[2]
MAIN = Path("C:/Users/Dell/Github/Shipping")  # corpus PDFs live in the main checkout
LIGATURES = str.maketrans({"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl",
                           "\u2060": None, "\u200b": None, "\u200c": None, "\u200d": None, "\ufeff": None,
                           "\u00a0": " "})
SECTIONS = ("Crude Oil", "Clean Products", "Dirty Products")
TOP, BOTTOM = 95, 785
NUMERIC = re.compile(r"^[\s\-+–$€£%.,/()0-9]*$")


def dark(s):
    c = s["color"]
    return max((c >> 16) & 255, (c >> 8) & 255, c & 255) <= 0x40


def prose_ok(s):
    """Body text: near-black, 9.45-12.6pt (any weight). Chart ticks/legends/notes are <= 9.4pt."""
    return dark(s) and 9.45 <= s["size"] <= 12.6


def span_dict(s):
    x0, y0, x1, y1 = s["bbox"]
    return dict(t=s["text"].translate(LIGATURES), x0=x0, y0=y0, x1=x1, y1=y1, size=round(s["size"], 1),
                bold="Bold" in s["font"] or bool(s["flags"] & 16), color=s["color"])


def spans_of(page):
    out = []
    for b in page.get_text("dict")["blocks"]:
        for ln in b.get("lines", []):
            for s in ln["spans"]:
                d = span_dict(s)
                if d["t"].strip() and not (d["y1"] < TOP or d["y0"] > BOTTOM):
                    out.append(d)
    return out


def glue_scripts(spans):
    """Attach superscripts/subscripts (1st, CO2) to the prose span they touch."""
    body = [s for s in spans if prose_ok(s)]
    keep = []
    for s in sorted(spans, key=lambda s: s["x0"]):
        if prose_ok(s) or s["size"] >= 9.45 or not dark(s):
            keep.append(s)
            continue
        host = next((b for b in body if b["y0"] - 2 <= (s["y0"] + s["y1"]) / 2 <= b["y1"] + 2
                     and -1.0 <= s["x0"] - b["x1"] <= 1.5), None)
        if host is None:
            keep.append(s)
            continue
        host["t"] = host["t"].rstrip() + s["t"].strip() + (" " if s["t"].endswith(" ") else "")
        host["x1"] = s["x1"]
    return keep


def line_of(sp):
    sp = sorted(sp, key=lambda x: x["x0"])
    txt = ""
    for x in sp:
        if txt and not txt.endswith(" ") and not x["t"].startswith(" "):
            txt += " "
        txt += x["t"]
    return dict(sp=sp, t=re.sub(r"\s+", " ", txt).strip(), x0=sp[0]["x0"], x1=max(x["x1"] for x in sp),
                y0=min(x["y0"] for x in sp), y1=max(x["y1"] for x in sp), size=max(x["size"] for x in sp))


def group_lines(spans, tol=2.5):
    """Group spans into visual rows (same baseline band), sorted by x. Used for positional tables."""
    rows = []
    for s in sorted(spans, key=lambda s: (round(s["y1"]), s["x0"])):
        for r in rows:
            if abs(r[0]["y1"] - s["y1"]) <= tol:
                r.append(s)
                break
        else:
            rows.append([s])
    return [line_of(r) for r in rows]


def native_blocks(page):
    """MuPDF blocks in content-stream order, each with its lines (spans glued for super/subscripts)."""
    out = []
    for b in page.get_text("dict")["blocks"]:
        lines = []
        for ln in b.get("lines", []):
            if abs(ln["dir"][1]) > 0.01:
                continue                 # rotated text: chart axis labels
            sp = [d for d in (span_dict(s) for s in ln["spans"])
                  if d["t"].strip() and not (d["y1"] < TOP or d["y0"] > BOTTOM)]
            if sp:
                lines.append(line_of(glue_scripts(sp)))
        if lines:
            out.append(dict(lines=lines, x0=min(l["x0"] for l in lines), y0=min(l["y0"] for l in lines),
                            x1=max(l["x1"] for l in lines), y1=max(l["y1"] for l in lines)))
    return out


def join_line(text, line):
    if not text:
        return line
    if text.endswith("-") and not text.endswith(" -"):
        return text + line
    return text + " " + line


def ends_sentence(t):
    return bool(re.search(r"[.!?:;\"”’)…]\s*$", t))


class Doc:
    def __init__(self):
        self.blocks = []  # [kind, text]  kind: h2, h3, p
        self.para = None
        self.last = None  # last prose line, for gap detection

    def flush(self):
        if self.para:
            self.blocks.append(["p", self.para])
        self.para = None
        self.last = None

    def heading(self, kind, t):
        self.flush()
        self.blocks.append([kind, t])

    def prose(self, l):
        if self.para is not None and self.last is not None and abs(l["y1"] - self.last["y1"]) > 2.5:
            gap = l["y0"] - self.last["y1"]
            if gap > 0.35 * l["size"]:
                self.flush()                     # paragraph spacing
            elif l["y0"] < self.last["y0"] - 1 and ends_sentence(self.para):
                self.flush()                     # jumped up (new column/page) after a full stop
        self.para = join_line(self.para or "", l["t"])
        self.last = l


def is_table_block(b):
    """Inset data table: >= 6 body-size cells, mostly numbers, no running text."""
    L = [l for l in b["lines"] if all(prose_ok(s) for s in l["sp"])]
    if len(L) < 6 or len(L) < 0.8 * len(b["lines"]):
        return False
    if any(len(l["t"].split()) >= 5 for l in L):
        return False
    if sum(1 for l in L if NUMERIC.match(l["t"])) < 0.35 * len(L):
        return False
    grid = group_lines([s for l in L for s in l["sp"]], tol=2.0)
    return sum(1 for r in grid if len(r["sp"]) >= 3) >= 3     # a 2-D grid, not a tick column


def render_table(b, title, notes):
    rows = sorted(group_lines([s for l in b["lines"] for s in l["sp"]], tol=2.0), key=lambda r: r["y1"])
    head = rows[0]["sp"]
    has_label = any(r["sp"][0]["x1"] < head[0]["x0"] - 5 for r in rows[1:])
    cols = [((h["x0"] + h["x1"]) / 2, h["x1"]) for h in head]
    md = [f"*Table: {title}*" if title else "*Table*", "",
          "| " + (" | " if has_label else "") + " | ".join(h["t"].strip() for h in head) + " |",
          "|" + "---|" * (len(head) + has_label)]
    for r in rows[1:]:
        label, cells = "", [""] * len(head)
        for c in r["sp"]:
            if has_label and c["x1"] < head[0]["x0"] - 5:
                label = (label + " " + c["t"].strip()).strip()
                continue
            cx = (c["x0"] + c["x1"]) / 2
            j = min(range(len(cols)), key=lambda k: min(abs(cols[k][0] - cx), abs(cols[k][1] - c["x1"])))
            cells[j] = (cells[j] + " " + c["t"].strip()).strip()
        md.append("| " + (label + " | " if has_label else "") + " | ".join(cells) + " |")
    return md + ([""] + [f"*{n}*" for n in notes] if notes else []) + [""]


def rate_tables(spans):
    """Rebuild the positional rate tables of the rates page."""
    md, notes = [], []
    lines = sorted(group_lines([s for s in spans if s["size"] >= 7], tol=2.0), key=lambda l: l["y0"])
    cols, open_table = None, None   # open_table: "spot" | "bunker" | None
    i = 0
    while i < len(lines):
        l, t = lines[i], lines[i]["t"]
        if "Spot Market Developments" in t and not t[:2] in ("TD", "TC"):
            md += ["", f"### {t}", ""]
            open_table = None
        elif t.startswith("wk on wk") and i + 1 < len(lines):
            bot = lines[i + 1]["sp"]
            cols = []
            for s in l["sp"]:
                cx = (s["x0"] + s["x1"]) / 2
                under = [b for b in bot if abs((b["x0"] + b["x1"]) / 2 - cx) < 25]
                cols.append((cx, " ".join([s["t"].strip()] + [b["t"].strip() for b in under])))
            i += 2
            continue
        elif cols and l["sp"][0]["x0"] < 100 and re.match(r"^(TD|TC|ClearView|Bunker)", t):
            label = [s for s in l["sp"] if s["x1"] < cols[0][0] - 25]
            cells = [""] * len(cols)
            for s in l["sp"]:
                if s in label:
                    continue
                cx = (s["x0"] + s["x1"]) / 2
                cells[min(range(len(cols)), key=lambda k: abs(cols[k][0] - cx))] = s["t"].strip()
            if t.startswith(("ClearView", "Bunker")):
                heads = [h for _, h in cols if not h.startswith("FFA")]
                if open_table != "bunker":
                    md += ["", "### Bunker Prices ($/tonne)", "",
                           "| Bunker price | " + " | ".join(heads) + " |", "|---|" + "---|" * len(heads)]
                    open_table = "bunker"
                vals = [c for (_, h), c in zip(cols, cells) if not h.startswith("FFA")]
                md.append("| " + " ".join(s["t"].strip() for s in label) + " | " + " | ".join(vals) + " |")
            else:
                code = " ".join(s["t"].strip() for s in label if s["x0"] < 85)
                vessel = " ".join(s["t"].strip() for s in label if 85 <= s["x0"] < 145)
                desc = " ".join(s["t"].strip() for s in label if s["x0"] >= 145)
                if open_table != "spot":
                    md += ["| Route | Vessel | Description | " + " | ".join(h for _, h in cols) + " |",
                           "|---|---|---|" + "---|" * len(cols)]
                    open_table = "spot"
                md.append(f"| {code} | {vessel} | {desc} | " + " | ".join(cells) + " |")
        elif t.startswith(("(a)", "*")):
            notes.append(t)
        i += 1
    if notes:
        md += [""] + [f"*{n}*" for n in notes]
    return md


def table_insets(blocks):
    """Feature-page inset tables with their bold title (just above) and source/notes (just below)."""
    found, claimed = [], set()
    for tb in (b for b in blocks if is_table_block(b)):
        title, notes = None, []
        for b in blocks:
            if b is tb or len(b["lines"]) != 1 or b["x0"] < tb["x0"] - 15 or b["x1"] > tb["x1"] + 40:
                continue
            t = b["lines"][0]["t"]
            if 0 <= tb["y0"] - b["y1"] <= 40 and all(s["bold"] for s in b["lines"][0]["sp"]) and title is None:
                title = t
                claimed.add(id(b))
            elif 0 <= b["y0"] - tb["y1"] <= 25 and t.startswith(("Source", "*")):
                notes.append(t)
                claimed.add(id(b))
        claimed.add(id(tb))
        found.append(render_table(tb, title, notes))
    return found, claimed


def summary_table(spans):
    """Half-year/annual 'Summary Table - Market & Fleet Data' page: rows vary in layout, so each
    visual row is kept as one pipe-separated line ('$' joined to its amount)."""
    rows = sorted(group_lines([s for s in spans if s["size"] >= 7], tol=2.0), key=lambda r: r["y1"])
    md = []
    for r in rows:
        cells = []
        for c in r["sp"]:
            t = re.sub(r"\$\s+", "$", re.sub(r"\s{2,}", "  ", c["t"].strip()))
            t = re.sub(r"\s{2,}", " | " if re.search(r"\d\s{2,}\$", t) else " ", t)
            if cells and cells[-1] in ("$", "-$"):
                cells[-1] += t
            else:
                cells.append(t)
        if r["size"] >= 13 and "Summary Table" in r["t"]:
            md += [f"### {r['t']}", ""]
        else:
            md.append("- " + " | ".join(cells))
    return md + [""]


def rebuild(pdf_path):
    d = pymupdf.open(pdf_path)
    doc = Doc()
    captions = []            # md line lists, emitted after the feature text
    section = None
    tables_md = []
    for page in d:
        spans = spans_of(page)
        alltext = " ".join(s["t"] for s in spans)
        if "OFFERING THE WORLD" in alltext.upper() or "www.gibsons.co.uk" in alltext:
            continue
        if "Spot Market Developments" in alltext and "wk on wk" in alltext:
            doc.flush()
            tables_md += rate_tables(spans)
            continue
        if any(s["size"] >= 13 and "Summary Table" in s["t"] for s in spans):
            captions.append(summary_table(spans))
            continue
        blocks = native_blocks(page)
        claimed = set()
        if section is None:
            insets, claimed = table_insets(blocks)
            captions += insets
        for b in blocks:
            if id(b) in claimed:
                continue
            running = any(len(x["t"].split()) >= 4 for x in b["lines"])
            body_lines = [x for x in b["lines"] if all(prose_ok(sp) for sp in x["sp"])]
            if body_lines and len(body_lines) == len(b["lines"]) and all(all(sp["bold"] for sp in x["sp"]) for x in body_lines)                     and not any(re.search(r"[.!?]\s*$", x["t"]) for x in body_lines):
                if section is None and re.search(r"[a-z]{3}", body_lines[0]["t"]) and len(body_lines[0]["t"].split()) >= 2:
                    captions.append([f"*Chart: {body_lines[0]['t']}*", ""])   # chart title / legend block
                continue
            for l in b["lines"]:
                t, big = l["t"], l["size"]
                bold = all(s["bold"] for s in l["sp"])
                black = all(dark(s) for s in l["sp"])
                if big >= 22 and t in SECTIONS:
                    section = t
                    doc.heading("h2", t)
                elif big >= 17:          # feature title (already in the MD header)
                    continue
                elif 13 <= big < 17:
                    if t.startswith("Weekly Tanker Market Report"):
                        continue
                    if section and bold and not black:
                        doc.heading("h3", t)                     # navy region sub-heads
                    elif section is None and bold and re.search(r"[a-z]{3}", t):
                        captions.append([f"*Chart: {t}*", ""])   # feature chart title
                    # else: recurring spot-rate chart titles on market pages (Baltic data, public)
                elif all(prose_ok(s) for s in l["sp"]):
                    if bold and len(b["lines"]) == 1 and len(t) < 90 and not re.search(r"[.!?:;]\s*$", t):
                        if section is None and re.search(r"[a-z]{3}", t):
                            captions.append([f"*Chart: {t}*", ""])   # bold one-line block: chart title
                        continue
                    if not running and NUMERIC.match(t):
                        continue                                  # chart/table cells at body size
                    doc.prose(l)
                elif section is None and bold and 9.45 <= big < 13 and all(s["color"] == 0xFFFFFF for s in l["sp"])                         and re.search(r"[a-z]{3}", t):
                    captions.append([f"*Chart: {t}*", ""])       # white-on-bar chart title
                # else: chart ticks / legends / notes
        if section is None and doc.para and ends_sentence(doc.para):
            doc.flush()
    doc.flush()
    out, feature_done = ["## Market Editorial", ""], False
    for kind, t in doc.blocks:
        if kind == "h2" and not feature_done:
            for c in captions:
                out += c
            feature_done = True
        if kind == "h2":
            out += [f"## {t}", ""]
        elif kind == "h3":
            out += [f"### {t}", ""]
        else:
            out += [t, ""]
    if tables_md:
        out += ["## Tanker Market Assessment Tables"] + tables_md + [""]
    body = "\n".join(out)
    return re.sub(r"\n{3,}", "\n\n", body).strip() + "\n"


def split_md(raw):
    """frontmatter + title/week header kept verbatim; returns (keep, old_body)."""
    i = raw.index("## Market Editorial")
    return raw[:i], raw[i:]


def main():
    apply = "--apply" in sys.argv
    files = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not files:
        files = [f for f in sorted(glob.glob(str(ROOT / "data/extracted/md/gibson/*/*.md")))
                 if 'format: "html"' not in open(f, encoding="utf-8").read()[:800]]
    for f in files:
        raw = open(f, encoding="utf-8").read()
        src = re.search(r'^source_file: "(.*)"', raw, re.M).group(1)
        keep, _ = split_md(raw)
        new = rebuild(MAIN / src)
        if apply:
            with open(f, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(keep + new)
        else:
            print(f"===== {Path(f).name}")
            print(new)


if __name__ == "__main__":
    main()
