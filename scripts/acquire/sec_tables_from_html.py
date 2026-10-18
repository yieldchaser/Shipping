"""Rebuild the tables of the SEC filing Markdowns (corpus/10-companies) from the filing's own HTML.

sec2md drops EDGAR header rows (the standardizer then invents "Col 2 / Col 3" headers) and leaves the
")" of a negative number, the "%" and the "$" in cells of their own, so "(90,612" sits next to a lone ")".
This converter reads every <table> of every HTML document in the filing (primary + exhibits):

  * colspans expanded onto a grid; a header cell keeps its identity across the columns it spans
  * "$" / "(" cells joined to the number on their right, ")" / "%" / ")%" cells to the number on their left
  * columns empty in every body row dropped (EDGAR spacer columns); their header text stays with the
    kept column under the same header cell
  * header rows = the leading rows with no number and more than the first cell filled; multi-row headers
    joined per column; category rows (only the first cell filled) bold

Each Markdown table block is matched to the HTML table with the same body cells (Jaccard of cell tokens
>= 0.85, numbers must all agree) and only that block is replaced: prose stays byte-identical.

    python scripts/acquire/sec_tables_from_html.py --md corpus/10-companies/DHT/20-F/X.md [--check]
    python scripts/acquire/sec_tables_from_html.py --all [--ticker DHT] [--check] [-j 4]
"""
from __future__ import annotations

import argparse
import collections
import html as htmllib
import json
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "corpus" / "10-companies"
CACHE = ROOT / ".reparse_staging" / "sec_html"
IDENTITY = "Antigravity Research research@shippinganalytics.com"
NUMRE = re.compile(r"^[\$€£]?\s*\(?-?[\d,]*\.?\d+\)?\s*%?$")
UNIT = re.compile(r"thousands|millions|billions|in (US)?\$|^\(?(US)?\$|^\(?(USD|EUR|NOK)|^\(?amounts? in", re.I)
NUMTOK = re.compile(r"\d[\d,]*\.?\d*")


def _txt(td) -> str:
    t = td.get_text(" ", strip=True)
    t = htmllib.unescape(t).replace("\xa0", " ")
    t = re.sub(r"\s+", " ", t).strip()
    return re.sub(r"\s+\)", ")", re.sub(r"\(\s+", "(", t))


def is_num(c: str) -> bool:
    c = c.replace(" ", "")
    return bool(c) and bool(NUMRE.match(c)) and any(ch.isdigit() for ch in c)


def grid(table) -> list[list[tuple[int, str]]]:
    """Rows of (cell id, text) per grid column; rowspans ignored (EDGAR rarely uses them)."""
    rows, cid = [], 0
    for tr in table.find_all("tr"):
        r = []
        for td in tr.find_all(["td", "th"]):
            try:
                span = max(1, min(int(td.get("colspan") or 1), 50))
            except ValueError:
                span = 1
            t = _txt(td)
            for _ in range(span):
                r.append((cid, t))
            cid += 1
        if r:
            rows.append(r)
    w = max((len(r) for r in rows), default=0)
    return [r + [(-1, "")] * (w - len(r)) for r in rows]


def _next_dash(r, i) -> bool:
    for j in range(i + 1, len(r)):
        if r[j][1]:
            return r[j][1] in ("-", "—", "–")
    return False


def _join_fragments(r: list[list]) -> None:
    """In place: '$' '(' onto the next filled cell, ')' '%' ')%' onto the previous filled cell."""
    n = len(r)
    for i in range(n):
        t = r[i][1]
        if t in ("$", "(", "$(", "($", "€", "£"):
            for j in range(i + 1, n):
                if r[j][1]:
                    if r[j][1] != t and r[j][0] != r[i][0]:
                        r[j][1] = t + (" " if r[j][1] in ("-", "—", "–") else "") + r[j][1]
                        r[i][1] = ""
                    break
        elif t in (")", "%", ")%", "%)", ") %", "pts", "x"):
            for j in range(i - 1, -1, -1):
                if r[j][1]:
                    if r[j][0] != r[i][0]:
                        r[j][1] = r[j][1] + t.replace(" ", "")
                        r[i][1] = ""
                    break


def convert(table) -> list[list[str]] | None:
    g = grid(table)
    if not g:
        return None
    rows = [[[cid, t] for cid, t in r] for r in g]
    for r in rows:
        _join_fragments(r)
    nonempty = [i for i, r in enumerate(rows) if any(c[1] for c in r)]
    if not nonempty:
        return None
    rows = [rows[i] for i in nonempty]
    # header rows
    h, units = 0, 0
    for k, r in enumerate(rows):
        filled = [c for c in r if c[1]]
        if any(is_num(c[1]) and not re.fullmatch(r"(19|20)\d\d", c[1]) for c in r[1:]):
            break
        if r[0][1] and all(not c[1] for c in r[1:] if c[0] != r[0][0]):
            if k == units and UNIT.search(r[0][1]):
                units += 1  # "(Dollars in thousands)" above the real header: part of the header
                h += 1
                continue
            break  # category row
        spanning = not r[0][1] and len({c[0] for c in filled}) == 1  # 'Three months ended March 31,'
        if (len({c[0] for c in filled}) < 2 and not spanning) or any(len(c[1]) > 80 for c in filled):
            break
        if k > units and r[0][1] and rows[units][0][1] and not any(
                re.fullmatch(r"(19|20)\d\d", c[1]) for c in r[1:]):
            break  # a later header row: under an empty-corner header, or the years row
        h += 1
        if h >= 5:
            break
    if h == units:
        h = 0  # a unit line alone is not a header
    head, body = rows[:h], rows[h:]
    if not body:
        head, body = [], rows
    w = len(rows[0])
    # a column is kept if any body row has text in it and that text is not a repeat of the left column's cell
    keep = []
    for c in range(w):
        has = False
        for r in body:
            if r[c][1] and not (c > 0 and r[c][0] == r[c - 1][0]):
                has = True
                break
        if has:
            keep.append(c)
    if not keep:
        return None
    # header text per kept column: header cells overlapping it (by identity)
    out_head = []
    if head:
        for c in keep:
            parts = []
            for r in head:
                cid, t = r[c]
                if t and t not in parts:
                    parts.append(t)
            out_head.append(" ".join(parts))
        # a header cell that spanned only dropped columns: attach to the nearest kept column on its right
        for r in head:
            for c in range(w):
                cid, t = r[c]
                if not t or any(r[k][0] == cid for k in keep):
                    continue
                for ki, k in enumerate(keep):
                    if k > c:
                        if t not in out_head[ki]:
                            out_head[ki] = (out_head[ki] + " " + t).strip()
                        break
    out_body = []
    for r in body:
        cells, prev = [], None
        for c in keep:
            cells.append("" if r[c][0] == prev and prev != -1 else r[c][1])
            prev = r[c][0]
        if cells[0] and all(not x for x in cells[1:]):
            cells[0] = f"**{cells[0].strip('*')}**"
        out_body.append(cells)
    if len(keep) < 2:
        return None
    return [out_head] + out_body if head else [[]] + out_body


def to_md(t: list[list[str]]) -> str:
    head, body = t[0], t[1:]
    n = len(body[0]) if body else len(head)
    esc = lambda s: re.sub(r"(?<!\\)\$", r"\\$", s.replace("|", "\\|"))  # corpus convention: \$
    if not head or not any(head):
        head = [""] * n
    al = []
    for c in range(n):
        al.append("---:" if any(is_num(r[c]) for r in body if r[c]) and c > 0 else ":---")
    lines = ["| " + " | ".join(esc(x) for x in head) + " |", "| " + " | ".join(al) + " |"]
    lines += ["| " + " | ".join(esc(x) for x in r) + " |" for r in body]
    return "\n".join(lines)


# ---------------------------------------------------------------- matching

def toks(cells) -> list[str]:
    out = []
    for c in cells:
        c = c.replace("**", "").replace("\\|", "|")
        out += [n.replace(",", "") for n in NUMTOK.findall(c)]
        out += [w.lower() for w in re.findall(r"[A-Za-z]{3,}", c)]
    return out


def md_tables(text: str):
    """(start line, end line exclusive, body cells) of every Markdown table block."""
    L = text.split("\n")
    i, out = 0, []
    while i < len(L):
        if L[i].startswith("|") and i + 1 < len(L) and re.match(r"^\|\s*:?-{3}", L[i + 1]):
            j = i + 2
            while j < len(L) and L[j].startswith("|"):
                j += 1
            cells = [c for l in L[i:j] for c in re.split(r"(?<!\\)\|", l.strip().strip("|"))]
            out.append((i, j, [c.strip() for c in cells]))
            i = j
        else:
            i += 1
    return L, out


def num_bag(ts):
    return sorted(t for t in ts if t[0].isdigit())


def match(md_cells, cands, used):
    mt = toks(md_cells)
    ms, mn = set(mt), num_bag(mt)
    best, bi = 0.0, None
    for k, (ht, hs, hn) in enumerate(cands):
        if k in used or not hs:
            continue
        j = len(ms & hs) / max(1, len(ms | hs))
        if j > best:
            best, bi = j, k
    if bi is None or best < 0.85:
        return None, best
    ht, hs, hn = cands[bi]
    if mn and set(mn) - set(hn):
        return None, best  # a number in the MD the HTML table does not have
    return bi, best


# ---------------------------------------------------------------- source html

def filing_htmls(accession: str) -> list[str]:
    from edgar import find, set_identity
    set_identity(IDENTITY)
    f = find(accession)
    docs = []
    try:
        docs.append(f.html() or "")
    except Exception:  # noqa: BLE001
        pass
    for a in getattr(f, "attachments", []) or []:
        name = str(getattr(a, "document", "") or getattr(a, "name", ""))
        if not re.search(r"\.html?$", name, re.I) or re.match(r"R\d+\.html?$", name, re.I):
            continue
        try:
            c = a.download()
            if isinstance(c, bytes):
                c = c.decode("utf-8", "replace")
            if c and c not in docs:
                docs.append(c)
        except Exception:  # noqa: BLE001
            continue
    return docs


def tables_for(accession: str):
    """Converted tables of the filing, cached per accession (raw HTML is not kept: it runs to GBs)."""
    CACHE.mkdir(parents=True, exist_ok=True)
    cp = CACHE / f"{accession}.tables.json"
    if cp.exists():
        ts = json.loads(cp.read_text(encoding="utf-8"))
    else:
        ts = [t for t, _s, _n in html_tables(filing_htmls(accession))]
        cp.write_text(json.dumps(ts, ensure_ascii=False), encoding="utf-8")
    return [(t, None, None) for t in ts]


def html_tables(docs: list[str]):
    out = []
    for h in docs:
        soup = BeautifulSoup(re.sub(r"<!--.*?-->", "", h, flags=re.S), "lxml")
        for tb in soup.find_all("table"):
            if tb.find("table"):
                continue
            t = convert(tb)
            if t and len(t) > 1:
                cells = [c for r in t for c in r]
                ts = toks(cells)
                out.append((t, set(ts), num_bag(ts)))
    return out


PLACEHOLDER = re.compile(r"^(Col \d+|Line Item)$")
OPEN = re.compile(r"^(\\\$\s*)?\(\s*([\d,]*\.?\d+)\s*(%?)$")


def split_row(line: str) -> list[str]:
    return [c.strip() for c in re.split(r"(?<!\\)\|", line.strip()[1:-1] if line.strip().endswith("|") else line.strip()[1:])]


def repair(rows: list[list[str]]) -> list[list[str]]:
    """Step A on the Markdown itself: '( 90,612' + ')' -> '(90,612)'; columns left holding only ')' dropped."""
    out = []
    for r in rows:
        r = list(r)
        for i, c in enumerate(r):
            m = OPEN.match(c)
            if not m:
                continue
            nxt = r[i + 1] if i + 1 < len(r) else None
            if nxt in (")", ")%", "%)"):
                r[i + 1] = ""
                tail = ")%" if "%" in nxt else ")"
            else:
                tail = ")" + m.group(3) if not m.group(3) else "%)"
            r[i] = ("\\$" if m.group(1) else "") + "(" + m.group(2) + tail
        for i, c in enumerate(r[:-1]):
            if c in ("\\$", "$") and r[i + 1] and (r[i + 1][0].isdigit() or r[i + 1][0] in "(-"):
                r[i + 1], r[i] = "\\$" + r[i + 1], ""  # the '$' spacer cell joins its number
        out.append(r)
    return out


def drop_empty_cols(head, body):
    """Drop columns empty in every body row. A real header over a dropped column moves to the column on its
    right when that one only has a placeholder ('2024' over the '$' spacer, 'Col 5' over the 2024 values)."""
    head = list(head)
    w = len(head)
    empty = [c > 0 and not any(r[c] for r in body if c < len(r)) for c in range(w)]
    for c in range(w - 1):
        if empty[c] and head[c] and not PLACEHOLDER.match(head[c]) and not empty[c + 1]                 and (not head[c + 1] or PLACEHOLDER.match(head[c + 1])):
            head[c + 1], head[c] = head[c], ""
    keep = [c for c in range(w) if not empty[c] or (head[c] and not PLACEHOLDER.match(head[c]))]
    return [head[c] for c in keep], [[r[c] if c < len(r) else "" for c in keep] for r in body]


def numbag(cells) -> collections.Counter:
    return collections.Counter(re.sub(r"[^\d.]", "", n).strip(".") for c in cells
                               for n in re.findall(r"\d[\d,]*\.?\d*", c.replace("**", "")))


def wordset(cells) -> set[str]:
    return {w.lower() for c in cells for w in re.findall(r"[A-Za-z]{3,}", c)}


def norm_cell(c: str) -> str:
    return re.sub(r"\s+", "", c.replace("**", "").replace("\\$", "$").replace("\\|", "|"))


def rebuild(md: Path, check: bool) -> dict:
    raw = md.read_bytes().decode("utf-8")
    crlf = "\r\n" in raw
    text = raw.replace("\r\n", "\n")
    acc = re.search(r"^accession_number:\s*'?\"?([\d-]+)", text, re.M)
    if not acc:
        return {"md": md.name, "error": "no accession"}
    L, blocks = md_tables(text)
    st = {"md": md.name, "tables": len(blocks), "repaired": 0, "placeholder": 0, "header_fixed": 0}
    cands = None
    repl = {}
    for (s, e, _cells) in blocks:
        head = split_row(L[s])
        delim = split_row(L[s + 1])
        body = [split_row(l) for l in L[s + 2:e]]
        if any(len(r) != len(head) for r in body):
            continue  # ragged table: leave for a look
        nb = repair(body)
        h2, b2 = drop_empty_cols(head, nb)
        html_head = False
        merged = bool(body) and sum(" — " in c for c in body[0]) >= 2  # header folded into row 1
        if any(PLACEHOLDER.match(h) for h in head) or not any(head) or merged:
            st["placeholder"] += 1
            if cands is None:
                cands = tables_for(acc.group(1))
            want = [[norm_cell(c) for c in r] for r in b2]
            for t, _ts, _tn in cands:
                th, tb = t[0], t[1:]
                if len(th) == len(h2) and any(th) and [[norm_cell(c) for c in r] for r in tb] == want:
                    h2, html_head = th, True
                    st["header_fixed"] += 1
                    break
            if not html_head:
                # the old converter also folded header text into row 1 ('2026 — $65,167'): take the whole
                # source table when it holds exactly the same numbers and nearly the same words
                mine = numbag([c for c in head if not PLACEHOLDER.match(c)] + [c for r in body for c in r])
                mw = wordset(head + [c for r in body for c in r])
                def same_numbers(t):
                    # equal, or the only numbers the Markdown lacks sit in the source header row
                    # (a year header the old converter dropped); never a body number
                    tb = numbag([c for r in t for c in r])
                    return tb == mine or (not (mine - tb) and not ((tb - mine) - numbag(t[0])))
                hits = [t for t, _ts, _tn in cands if same_numbers(t)
                        and len(mw & wordset([c for r in t for c in r])) >= 0.8 * max(1, len(mw))]
                if hits and mine:
                    best = max(hits, key=lambda t: len(mw & wordset([c for r in t for c in r]))
                               / max(1, len(mw | wordset([c for r in t for c in r]))))
                    repl[s] = (e, to_md(best).split(chr(10)))
                    st["replaced_full"] = st.get("replaced_full", 0) + 1
                    continue
                h2 = ["" if PLACEHOLDER.match(c) else c for c in h2]  # invented by the old standardizer
                st["header_blanked"] = st.get("header_blanked", 0) + 1
        digits = lambda rows: sorted(re.sub(r"\D", "", c) for r in rows for c in r if re.search(r"\d", c))
        if digits(body) != digits(b2) or len(b2) != len(body):
            st["skipped"] = st.get("skipped", 0) + 1  # never lose or change a number
            continue
        if len(h2) != len(delim):
            delim = [":---"] + ["---:" if any(is_num(r[c].replace("\\$", "$")) for r in b2 if r[c]) else ":---"
                                for c in range(1, len(h2))]
        esc = lambda x: re.sub(r"(?<!\\)\$", r"\\$", x)
        lines = ["| " + " | ".join(esc(x) if html_head else x for x in h2) + " |",
                 "| " + " | ".join(delim) + " |"] + ["| " + " | ".join(r) + " |" for r in b2]
        if lines != L[s:e]:
            repl[s] = (e, lines)
            st["repaired"] += 1
    if repl and not check:
        out, i = [], 0
        while i < len(L):
            if i in repl:
                e, new = repl[i]
                out += new
                i = e
            else:
                out.append(L[i])
                i += 1
        t = "\n".join(out)
        md.write_bytes((t.replace("\n", "\r\n") if crlf else t).encode("utf-8"))
    return st


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--md", nargs="*")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--ticker")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    mds = [Path(m) for m in a.md or []]
    if a.all:
        mds = sorted((CORPUS / a.ticker if a.ticker else CORPUS).rglob("*.md"))
    for m in mds:
        try:
            print(json.dumps(rebuild(m if m.is_absolute() else ROOT / m, a.check)), flush=True)
        except Exception as e:  # noqa: BLE001
            print(json.dumps({"md": m.name, "error": repr(e)[:200]}), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
