"""Banchero 'by Destination/Source/Origin' label tables vs the PDF TEXT LAYER (the bar labels are real text).

For each MD table: locate the chart title on the page, take the words of that chart's half-page column below it,
find each category label (the MD's first column) under the plot, assign every numeric label above them to the
nearest category by x, order within a category by x = series in legend order. Compare to the MD cell by cell.
Image-only charts (no text layer) come out UNRESOLVED; they were render-checked by hand on 2026-11-08 and carry a note.
Writes data/audit/banchero_label_tables.json; exit code 1 when any table is a MISMATCH.

    python scripts/verify/banchero_label_tables.py
"""
import json, os, re, sys
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# PDFs are gitignored: in a worktree they are found in the main checkout (git common dir parent)
MAIN = Path(os.environ.get("SHIPPING_MAIN_CHECKOUT", ROOT))
HERE = ROOT / "data" / "audit"
HEAD = re.compile(r"by Destination|by Source|by Origin", re.I)
NUM = re.compile(r"^-?\d[\d,]*\.?\d*%?$")


def norm(t):
    t = t.replace(",", "").rstrip("%")
    try:
        return round(float(t), 3)
    except ValueError:
        return None


def tables(md):
    text = md.read_text(encoding="utf-8", errors="replace")
    L = text.split("\n")
    out, i = [], 0
    while i < len(L):
        if L[i].startswith("|"):
            j = i
            while j < len(L) and L[j].startswith("|"):
                j += 1
            head = next((L[k] for k in range(i - 1, max(i - 4, -1), -1) if L[k].strip()), "")
            if head.startswith("#") and HEAD.search(head):
                rows = [[c.strip() for c in r.strip().strip("|").split("|")] for r in L[i:j]]
                out.append((i, j, head, rows))
            i = j
        else:
            i += 1
    m = re.search(r'^source_file:\s*"?([^"\n]+)', text, re.M)
    src = next((b / m[1].strip() for b in (ROOT, MAIN) if m and (b / m[1].strip()).exists()), None)
    return out, src


def rebuild(doc, head, rows):
    title = re.sub(r"^#+\s*", "", head)
    title = title.split(" (")[0].strip()
    cats = [r[0] for r in rows[2:]]
    series = rows[0][1:]
    for pg in doc:
        hits = pg.search_for(title) or pg.search_for(title.split(" - ", 1)[-1])
        if not hits:
            continue
        t = hits[0]
        mid = pg.rect.width / 2
        left = (t.x0 + t.x1) / 2 < mid
        x0, x1 = (0, mid) if left else (mid, pg.rect.width)
        # next title below in the same column bounds the chart
        ws = pg.get_text("words")
        below = [w for w in ws if x0 <= (w[0] + w[2]) / 2 < x1 and w[1] > t.y1]
        y_end = pg.rect.height
        for w in below:
            if w[1] > t.y1 + 60 and w[4] in ("-",) and False:
                pass
        # stop at the next chart title: a line containing ' - ' title pattern words like 'by' after the first chart
        lines = {}
        for w in below:
            lines.setdefault(round(w[1]), []).append(w)
        for y in sorted(lines):
            txt = " ".join(w[4] for w in sorted(lines[y], key=lambda w: w[0]))
            if y > t.y1 + 40 and re.search(r"\b(by|Monthly|Seasonality|Exports|Imports|Loadings|Discharges)\b", txt) and " - " in txt:
                y_end = y
                break
        W = [w for w in below if w[1] < y_end]
        # category anchors: first word of each category label
        anchors = []
        byline = {}
        for w in W:
            byline.setdefault(round(w[1]), []).append(w)
        used = set()
        for c in cats:
            toks = [t for t in re.split(r"[\s/]+", c.strip()) if t]
            found = None
            for y in sorted(byline):
                ln = sorted(byline[y], key=lambda w: w[0])
                lt = [re.split(r"/", w[4])[0] for w in ln]
                n = len(toks)
                # whole name on one line, else its first line ('Others/' over 'Unknown')
                for k in range(len(ln)):
                    for m in (n, 1):
                        if lt[k:k + m] == toks[:m] and (y, k) not in used and (m == n or k + 1 == len(ln) or lt[k + 1:k + 2] != toks[1:2] or True):
                            if m == 1 and n > 1 and lt[k + 1:k + n] == toks[1:]:
                                continue
                            found = (y, k, m, ln)
                            break
                    if found:
                        break
                if found:
                    break
            if not found:
                return None, f"category '{c}' not on page"
            y, k, m, ln = found
            used.add((y, k))
            span = ln[k:k + m]
            anchors.append((min(w[0] for w in span), min(w[1] for w in span), max(w[2] for w in span), max(w[3] for w in span)))
        cat_y = min(a[1] for a in anchors)
        xs = [(a[0] + a[2]) / 2 for a in anchors]
        if xs != sorted(xs):
            return None, "categories not left-to-right"
        sp = min((b - a) for a, b in zip(xs, xs[1:])) if len(xs) > 1 else 60
        lo_x, hi_x = xs[0] - sp * 0.6, xs[-1] + sp * 0.6
        wordy = {round(w[1]) for w in W if re.search(r"[A-Za-z]", w[4]) and lo_x < (w[0] + w[2]) / 2 < hi_x}
        labels = [w for w in W if round(w[1]) not in wordy and w[3] <= cat_y + 1 and NUM.match(w[4]) and xs[0] - sp * 0.6 < (w[0] + w[2]) / 2 < xs[-1] + sp * 0.6]
        groups = [[] for _ in cats]
        for w in labels:
            cx = (w[0] + w[2]) / 2
            k = min(range(len(xs)), key=lambda k: abs(xs[k] - cx))
            groups[k].append(w)
        out = []
        for c, g in zip(cats, groups):
            g.sort(key=lambda w: w[0])
            if len(g) != len(series):
                return None, f"category '{c}': {len(g)} labels for {len(series)} series ({[w[4] for w in g]})"
            out.append([c] + [w[4] for w in g])
        return out, pg.number
    return None, "title not found"


def work(mdp):
    import pymupdf
    md = Path(mdp)
    tabs, src = tables(md)
    if not tabs:
        return []
    rel = md.relative_to(ROOT).as_posix()
    if not src:
        return [{"md": rel, "status": "UNRESOLVED", "why": "no source"}]
    doc = pymupdf.open(src)
    res = []
    for s, e, head, rows in tabs:
        reb, info = rebuild(doc, head, rows)
        if reb is None:
            res.append({"md": rel, "line": s + 1, "head": head, "status": "UNRESOLVED", "why": info})
            continue
        diffs = []
        for r_md, r_pdf in zip(rows[2:], reb):
            for c_md, c_pdf in zip(r_md[1:], r_pdf[1:]):
                if norm(c_md) != norm(c_pdf):
                    diffs.append((r_md[0], c_md, c_pdf))
        res.append({"md": rel, "line": s + 1, "head": head, "page": info,
                    "status": "OK" if not diffs else "MISMATCH", "diffs": diffs,
                    "header": rows[0], "rebuilt": reb, "md_rows": rows[2:]})
    return res


if __name__ == "__main__":
    mds = [str(p) for p in sorted((ROOT / "data/extracted/md/banchero_costa").rglob("*.md")) if tables(p)[0]]
    print("MDs:", len(mds), flush=True)
    res = []
    with Pool(4) as pool:
        for r in pool.imap_unordered(work, mds):
            res.extend(r)
    res.sort(key=lambda r: (r["md"], r.get("line", 0)))
    with open(HERE / "banchero_label_tables.json", "w", encoding="utf-8", newline="\n") as fh:
        json.dump(res, fh, indent=1)
    from collections import Counter
    c = Counter(r["status"] for r in res)
    print(dict(c))
    sys.exit(1 if c.get("MISMATCH") else 0)
