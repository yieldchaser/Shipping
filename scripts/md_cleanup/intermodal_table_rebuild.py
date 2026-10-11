"""Rebuild Intermodal tables that the original parse left as a header row only.

Two defect shapes, both a markdown table with a header + separator and NO body rows:
  * crammed - every printed value was packed into the header cells ("Units 2+2 2 4 2 ..."), so the data is there
              but unreadable as a table;
  * empty   - the header was written and the rows were lost (e.g. 2026 "Spot Rates").

For each one the PDF page is found from the numbers of the neighbouring tables (and the crammed values), the page
is read with LlamaParse agentic (cache .reparse_staging/intermodal_tables/), and the matching table replaces the
broken one ONLY when
  * every number of the new table is printed on that PDF page (text layer), and
  * for a crammed table, every number of the old header is in the new table.
Otherwise the table is left as it is and reported. Nothing else in the file changes (line endings kept).
Tables on pages the parsing notes exclude (contacts "Location | Address | Tel | Fax") are skipped.

    python scripts/md_cleanup/intermodal_table_rebuild.py                # plan (no API calls)
    python scripts/md_cleanup/intermodal_table_rebuild.py --parse -j 4   # read the pages (10 credits/page)
    python scripts/md_cleanup/intermodal_table_rebuild.py --apply        # rebuild from the cache
    python scripts/md_cleanup/intermodal_table_rebuild.py --untracked --parse --apply   # CI: new issues only

A merged first-column band label (Spot/TC "VLCC", "Clean", ...) is taken from the band the intact tables give that
row most often and must reproduce the labels on the page; any other merged cell must sit over its rows on the PDF
page (a merged $ price is written "<price> (en bloc)").
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
MD_ROOT = ROOT / "data" / "extracted" / "md" / "intermodal"
CACHE = ROOT / ".reparse_staging" / "intermodal_tables"
REPORT = ROOT / ".reparse_staging" / "intermodal_table_rebuild_report.json"
CORPUS_BASES = [ROOT, ROOT.parents[2]] if ROOT.parent.name == "worktrees" else [ROOT]
PROMPT = ("This is a shipbroker weekly market report page. Reproduce every table exactly as a table with one cell per "
          "column, keeping every header level, and repeat a merged row label (sector) on every row it spans. Copy "
          "numbers exactly as printed. Keep commentary verbatim. Do not describe charts or estimate values.")
SEP = re.compile(r"^\|\s*:?-{3}")
SKIP_HEADER = re.compile(r"(?i)\|\s*(location|address)\s*\|")
NUM = re.compile(r"[-+]?\$?\d[\d,]*(?:\.\d+)?%?")


def norm_num(tok: str) -> str:
    t = tok.replace(",", "").replace("$", "").replace("+", "").rstrip("%")
    try:
        return repr(float(t))
    except ValueError:
        return t


def nums(text: str) -> Counter:
    return Counter(norm_num(t) for t in NUM.findall(text))


def split_row(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def tables(lines: list[str]) -> list[tuple[int, int]]:
    """(start, end) line ranges of every markdown table."""
    out, i = [], 0
    while i < len(lines):
        if lines[i].startswith("|") and i + 1 < len(lines) and SEP.match(lines[i + 1]):
            j = i + 2
            while j < len(lines) and lines[j].startswith("|"):
                j += 1
            out.append((i, j))
            i = j
        else:
            i += 1
    return out


def defects(lines: list[str]) -> list[dict]:
    tabs = tables(lines)
    out = []
    for k, (a, b) in enumerate(tabs):
        if b != a + 2 or SKIP_HEADER.search(lines[a]):
            continue
        hdr = lines[a]
        old = nums(hdr)
        near = Counter()
        for kk in (k - 1, k + 1):
            if 0 <= kk < len(tabs):
                near += nums("\n".join(lines[tabs[kk][0]:tabs[kk][1]]))
        heading = next((lines[j] for j in range(a - 1, max(a - 8, -1), -1) if lines[j].startswith("#")), "")
        out.append({"line": a, "header": hdr, "old": old, "near": near, "heading": heading,
                    "kind": "crammed" if sum(old.values()) >= 4 else "empty"})
    return out


def source_pdf(md_text: str) -> Path | None:
    m = re.search(r'^source_file:\s*"?([^"\n]+\.pdf)', md_text, re.M)
    if not m:
        return None
    for base in CORPUS_BASES:
        if (base / m.group(1)).is_file():
            return base / m.group(1)
    return None


def page_texts(pdf: Path) -> list[str]:
    return [p.get_text() for p in pymupdf.open(pdf)]


def find_page(texts: list[str], d: dict) -> int | None:
    want = d["old"] + d["near"]
    if not want:
        return None
    scores = [sum((nums(t) & want).values()) for t in texts]
    best = max(range(len(texts)), key=lambda i: scores[i])
    return best + 1 if scores[best] >= 5 else None


def cache_path(pdf: Path, page: int) -> Path:
    return CACHE / f"{hashlib.sha1(pdf.read_bytes()).hexdigest()[:16]}_p{page}.json"


def parse_page(pdf: Path, page: int) -> str:
    cp = cache_path(pdf, page)
    if cp.exists():
        return json.loads(cp.read_text(encoding="utf-8"))["markdown"]
    from scripts.parse_engine.llama import LlamaParseClient
    r = LlamaParseClient().parse(pdf, "agentic", "latest", str(page), PROMPT, False)
    CACHE.mkdir(parents=True, exist_ok=True)
    cp.write_text(json.dumps({"pdf": pdf.name, "page": page, "markdown": r["markdown"], "job_id": r.get("job_id")},
                             ensure_ascii=False), encoding="utf-8")
    return r["markdown"]


def cell(v) -> str:
    s = "" if v is None else str(v)
    return "" if s == "nan" else re.sub(r"\s+", " ", s).replace("|", "/").strip()


def html_tables(markdown: str) -> list[tuple[list[list[str]], list[tuple[int, int, int]]]]:
    """Every <table> of the LlamaParse page: (rows, merged). rows[0] is the header (header levels joined per column),
    rowspan/colspan expanded. merged lists body cells LlamaParse wrote as one cell over several rows:
    (col, first_row, last_row) with row indexes into rows."""
    from bs4 import BeautifulSoup
    out = []
    for m in re.finditer(r"<table>.*?</table>", markdown, re.S):
        trs = BeautifulSoup(m.group(0), "html.parser").find_all("tr")
        grid: dict[tuple[int, int], tuple[str, int]] = {}      # (row, col) -> (text, origin id)
        is_head, origin = [], 0
        for r, tr in enumerate(trs):
            cells = tr.find_all(["td", "th"])
            is_head.append(bool(cells) and all(c.name == "th" for c in cells))
            c = 0
            for td in cells:
                while (r, c) in grid:
                    c += 1
                rs, cs = int(td.get("rowspan", 1) or 1), int(td.get("colspan", 1) or 1)
                origin += 1
                for dr in range(rs):
                    for dc in range(cs):
                        grid[(r + dr, c + dc)] = (cell(td.get_text(" ")), origin)
                c += cs
        if not grid:
            continue
        n_rows = max(r for r, _ in grid) + 1
        n_cols = max(c for _, c in grid) + 1
        n_head = 0
        while n_head < n_rows and n_head < len(is_head) and is_head[n_head]:
            n_head += 1
        n_head = max(n_head, 1)
        # LlamaParse sometimes puts the colspan of the leading label cell ("$/day" over sector + route) on the last
        # header cell instead ("2020" spanning two value columns). Year/date headers never span two columns in these
        # reports, so when the body's first two columns are labels, move the extra span back to the front.
        body_lab = [r for r in range(n_head, n_rows) if grid.get((r, 1)) and not NUM.fullmatch(grid[(r, 1)][0] or "x")]
        for r in range(n_head):
            row = [grid.get((r, c), ("", 0)) for c in range(n_cols)]
            L = 1
            while L < n_cols and row[-1 - L][1] == row[-1][1]:
                L += 1
            if (L > 1 and NUM.search(row[-1][0]) and row[0][0] and not NUM.search(row[0][0])
                    and row[1][1] != row[0][1] and len(body_lab) >= (n_rows - n_head) * 0.8):
                new = [row[0]] * L + row[1:n_cols - L + 1]
                for c in range(n_cols):
                    grid[(r, c)] = new[c]
        hdr = []
        for c in range(n_cols):
            parts = []
            for r in range(n_head):
                t = grid.get((r, c), ("", 0))[0]
                if t and t not in parts:
                    parts.append(t)
            hdr.append(" ".join(parts))
        # a table title repeated in every header cell ("Bulk Carriers Size", "Bulk Carriers Name", ...) is dropped
        words = [h.split() for h in hdr if h]
        k = 0
        while words and all(len(w) > k + 1 and w[k] == words[0][k] for w in words):
            k += 1
        if k and len(words) > 1:
            hdr = [" ".join(h.split()[k:]) if h else h for h in hdr]
        rows = [hdr] + [[grid.get((r, c), ("", 0))[0] for c in range(n_cols)] for r in range(n_head, n_rows)]
        # trailing columns with no value in any body row carry only spilled header text ("2020 | 2020 | Index")
        while n_cols > 1 and len(rows) > 1 and not any(r[n_cols - 1] for r in rows[1:]):
            n_cols -= 1
            rows = [r[:n_cols] for r in rows]
        merged = []
        for c in range(n_cols):
            r = n_head
            while r < n_rows:
                o = grid.get((r, c), ("", -1))[1]
                e = r
                while e + 1 < n_rows and grid.get((e + 1, c), ("", -2))[1] == o:
                    e += 1
                if e > r and grid[(r, c)][0]:
                    merged.append((c, r - n_head + 1, e - n_head + 1))
                r = e + 1
        out.append((rows, merged))
    return out


def row_key(cells: list[str]) -> str:
    """Identity of a row inside its band: the next non-empty cells after the band label ("265k MEG-SPORE",
    "300k 1yr TC"), case/space-insensitive."""
    rest = [c for c in cells[1:3] if c and not NUM.fullmatch(c.replace(" ", "")) or re.match(r"^\d+[kK]\b", c)]
    return re.sub(r"\s+", " ", " ".join(rest[:2])).strip().lower()


_BANDS: dict[str, Counter] | None = None


def band_lookup() -> dict[str, Counter]:
    """row_key -> Counter(band label) over every intact Intermodal table whose first column is a band label."""
    global _BANDS
    if _BANDS is None:
        _BANDS = {}
        for md in MD_ROOT.rglob("*.md"):
            lines = md.read_text(encoding="utf-8").splitlines()
            for a, b in tables(lines):
                if b - a < 4:
                    continue
                band = ""
                for line in lines[a + 2:b]:
                    cells = split_row(line)
                    if len(cells) < 3:
                        continue
                    lab = re.sub(r"[*_]", "", cells[0]).strip()
                    if lab and not NUM.search(lab):
                        band = lab
                    if band:
                        _BANDS.setdefault(row_key(cells), Counter())[band] += 1
    return _BANDS


def page_lines(page) -> list[tuple[float, list[tuple]]]:
    lines: list[tuple[float, list[tuple]]] = []
    for w in sorted(page.get_text("words"), key=lambda w: (w[1] + w[3]) / 2):
        yc = (w[1] + w[3]) / 2
        if lines and abs(lines[-1][0] - yc) <= 2.5:
            lines[-1][1].append(w)
        else:
            lines.append((yc, [w]))
    return lines


def row_ys(rows: list[list[str]], merged, lines) -> list[float | None]:
    """y of each body row on the PDF page: the text line holding most of the row's own (not merged) cell words."""
    mcells = {(r, c) for c, a, b in merged for r in range(a, b + 1)}
    ys: list[float | None] = [None]
    for r in range(1, len(rows)):
        toks = [t for c, v in enumerate(rows[r]) if (r, c) not in mcells for t in v.split()]
        best, score = None, 0
        for yc, ws in lines:
            have = Counter(w[4] for w in ws)
            s = sum((Counter(toks) & have).values())
            if s > score:
                best, score = yc, s
        ys.append(best if score >= max(2, len(toks) // 2) else None)
    return ys


def check_merged(rows, merged, page) -> tuple[list[list[str]] | None, str]:
    """Merged cells must sit over the rows they span. A merged first-column label (sector) is re-assigned to the
    rows its printed label is centred on; any other merged cell that does not fit rejects the table."""
    if not merged:
        return rows, "ok"
    lines = page_lines(page)
    ys = row_ys(rows, merged, lines)
    if any(y is None for y in ys[1:]):
        return None, "rows not located on the PDF page"
    words = page.get_text("words")
    rows = [list(r) for r in rows]

    def label_y(text, lo, hi):
        first = text.split()[0]
        cands = [(w[1] + w[3]) / 2 for w in words if w[4] == first and lo - 15 <= (w[1] + w[3]) / 2 <= hi + 15]
        return cands

    col0 = [g for g in merged if g[0] == 0]
    if col0:
        # labels of column 0 in order, each one printed once at the centre of its band
        groups, r = [], 1
        while r < len(rows):
            g = next((g for g in col0 if g[1] == r), None)
            e = g[2] if g else r
            groups.append(rows[r][0])
            r = e + 1
        # The bands have no rule lines and the rotated labels sit off-centre, so neither LlamaParse's spans nor the
        # page geometry say reliably where a band ends (checked by eye on 2025/2026 pages: "75k MEG-JAPAN" is printed
        # in the Aframax band, "140k BSEA-MED" in the Suezmax band). The template is fixed: take each row's band
        # from the intact Intermodal tables (majority over every week printing that row) and accept it only when
        # it reproduces the band labels printed on this page, in order.
        lk = band_lookup()
        new = []
        for r in range(1, len(rows)):
            hits = lk.get(row_key(rows[r]))
            if not hits:
                return None, f"no intact table gives the band of row '{' '.join(rows[r][1:3])}'"
            lab, n = hits.most_common(1)[0]
            if n < 0.6 * sum(hits.values()):
                return None, f"band of row '{' '.join(rows[r][1:3])}' is ambiguous: {dict(hits)}"
            new.append(lab)
        seq = [lab for i, lab in enumerate(new) if i == 0 or new[i - 1] != lab]
        if [g.lower() for g in seq] != [g.lower() for g in groups]:
            return None, f"band sequence {seq} differs from the page labels {groups}"
        for r, lab in enumerate(new, 1):
            rows[r][0] = lab
    for c, a, b in merged:
        if c == 0:
            continue
        text = rows[a][c]
        mean = sum(ys[a:b + 1]) / (b - a + 1)
        pitch = (ys[b] - ys[a]) / max(b - a, 1)
        cs = label_y(text, ys[a], ys[b]) if text else []
        if not any(ys[a] - 3 <= y <= ys[b] + 3 and abs(y - mean) <= max(4.0, pitch / 2) for y in cs):
            return None, f"merged cell '{text[:20]}' (col {c}) does not span rows {a}-{b} on the page"
        if "$" in text and "en bloc" not in text.lower():
            for r in range(a, b + 1):           # one price for several ships (owner convention, see intermodal_fix)
                rows[r][c] = f"{text} (en bloc)"
    return rows, "ok"


def to_md(t: list[list[str]], nl: str) -> list[str]:
    hdr, rows = t[0], t[1:]
    lines = ["| " + " | ".join(hdr) + " |", "| " + " | ".join("---" for _ in hdr) + " |"]
    lines += ["| " + " | ".join(r) + " |" for r in rows]
    return [x + nl for x in lines]


def header_sim(a: list[str], b: list[str]) -> float:
    wa = set(re.findall(r"[a-z0-9/]+", " ".join(a).lower()))
    wb = set(re.findall(r"[a-z0-9/]+", " ".join(b).lower()))
    return len(wa & wb) / max(len(wa), 1)


def pick(cands, d: dict, page) -> tuple[list[list[str]] | None, str]:
    best, why = None, "no table on the page"
    scored = []
    printed = set(nums(page.get_text()))
    for t, merged in cands:
        tn = set(nums("\n".join(" ".join(r) for r in t)))
        body = set(nums("\n".join(" ".join(r) for r in t[1:])))
        if len(t) < 2 or not body:
            continue
        # sets, not counts: a merged (rowspan) cell is repeated on every row it spans
        unprinted = body - printed
        if unprinted:
            why = f"numbers not on the PDF page: {sorted(unprinted)[:5]}"
            continue
        if d["kind"] == "crammed":
            # the crammed header glued neighbouring cells ("6-Oct-23205k"); only values printed on the page must survive
            lost = (set(d["old"]) & printed) - tn
            if lost:
                why = f"old values missing from candidate: {sorted(lost)[:5]}"
                continue
            score = len(set(d["old"]) & printed)
            if score < 4:
                why = "too few printed values in the old table to identify it"
                continue
        else:
            score = header_sim(split_row(d["header"]), t[0])
            if score < 0.6:
                why = f"header similarity {score:.2f}"
                continue
        scored.append((score, t, merged))
    for score, t, merged in sorted(scored, key=lambda x: -x[0])[:1]:
        best, why = check_merged(t, merged, page)
    return best, why


def main() -> int:
    parse, apply = "--parse" in sys.argv, "--apply" in sys.argv
    jobs = int(sys.argv[sys.argv.index("-j") + 1]) if "-j" in sys.argv else 4
    plan, report, stat = [], [], Counter()
    mds = sorted(MD_ROOT.rglob("*.md"))
    if "--untracked" in sys.argv:                      # CI: only the issues extracted in this run
        import subprocess
        out = subprocess.run(["git", "-c", "core.quotepath=off", "ls-files", "--others", "--exclude-standard", "-z",
                              "--", MD_ROOT.relative_to(ROOT).as_posix()],
                             cwd=ROOT, capture_output=True, text=True, encoding="utf-8").stdout
        mds = sorted(ROOT / p for p in out.split("\0") if p.endswith(".md"))
    for md in mds:
        raw = md.read_bytes().decode("utf-8")
        lines = raw.splitlines(keepends=True)
        ds = defects([l.rstrip("\r\n") for l in lines])
        if not ds:
            continue
        pdf = source_pdf(raw)
        if pdf is None:
            stat["no source pdf"] += len(ds)
            continue
        texts = page_texts(pdf)
        for d in ds:
            d["page"] = find_page(texts, d)
            stat[f"{d['kind']} table"] += 1
            if d["page"] is None:
                stat["page not found"] += 1
                report.append({"md": md.relative_to(ROOT).as_posix(), "line": d["line"] + 1, "result": "page not found"})
        plan.append((md, pdf, texts, lines, ds))
    pages = sorted({(pdf, d["page"]) for _, pdf, _, _, ds in plan for d in ds if d["page"]}, key=str)
    todo = [p for p in pages if not cache_path(*p).exists()]
    print(f"{sum(len(x[4]) for x in plan)} broken tables in {len(plan)} MDs; {len(pages)} pages, {len(todo)} not cached "
          f"(~{10 * len(todo)} LlamaParse credits)")
    if parse and todo:
        def one(p):
            try:
                parse_page(*p)
                return None
            except Exception as e:  # keep going; report at the end
                return f"{p[0].name} p{p[1]}: {e}"
        with ThreadPoolExecutor(jobs) as ex:
            for i, err in enumerate(ex.map(one, todo), 1):
                if err:
                    print("FAIL", err)
                if i % 10 == 0:
                    print(f"{i} / {len(todo)}", flush=True)
    for md, pdf, texts, lines, ds in plan:
        nl = "\r\n" if lines and lines[0].endswith("\r\n") else "\n"
        doc = pymupdf.open(pdf)
        new_lines, changed = list(lines), False
        for d in sorted(ds, key=lambda x: -x["line"]):          # bottom-up keeps line numbers valid
            if d["page"] is None or not cache_path(pdf, d["page"]).exists():
                continue
            t, why = pick(html_tables(parse_page(pdf, d["page"])), d, doc[d["page"] - 1])
            report.append({"md": md.relative_to(ROOT).as_posix(), "line": d["line"] + 1, "kind": d["kind"],
                           "page": d["page"], "heading": d["heading"], "result": why})
            stat[f"{d['kind']}: {'rebuilt' if t else 'left as is'}"] += 1
            if t:
                new_lines[d["line"]:d["line"] + 2] = to_md(t, nl)
                changed = True
        if changed:
            stat["files changed"] += 1
            if apply:
                md.write_bytes("".join(new_lines).encode("utf-8"))
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    for k, v in sorted(stat.items()):
        print(f"{v:6}  {k}")
    print("APPLIED" if apply else "dry run (use --apply)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
