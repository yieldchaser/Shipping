"""Independent spot check of extracted Markdown against its source document, read a second time by Nace Extract.

For a random sample of MDs per source and year, Nace transcribes every table cell (table, row label, column, value)
from the source pages. Each printed numeric cell is then looked up in our MD:

  ok         the number is in an MD table cell whose row and column labels match (transposed tables count)
  misplaced  the number is in an MD table, but under other labels (the Athenian legacy scramble looked like this)
  in_prose   the number is only in the MD's running text
  missing    the number is nowhere in the MD (dropped table, chart values, or a Nace misread: triage by rendering)

Nace results are cached under .reparse_staging/qa_nace/cache (keyed by file sha + pages), so a rerun costs nothing.
Keys come from ~/.nace/keys.env (NACE_API_KEY, NACE_API_KEY_2, ...); on 402 (no credit) the next key is used.

    python scripts/qa/nace_crosscheck.py --per-source 6 --pages-per-doc 2 [--sources ssy xclusiv] [--dry-run]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAIN_ROOT = ROOT.parents[2] if ROOT.parent.name == "worktrees" else ROOT   # full corpus lives in the main checkout
MD_ROOT = ROOT / "data" / "extracted" / "md"
OUT = ROOT / ".reparse_staging" / "qa_nace"
CACHE = OUT / "cache"

SCHEMA = {"type": "object", "properties": {"cells": {"type": "array", "items": {"type": "object", "properties": {
    "table_title": {"type": "string"}, "row_label": {"type": "string"},
    "column": {"type": "string"}, "value": {"type": "string"}}}}}}
INSTR = ("Transcribe every data table and every price grid on these pages exactly as printed. For each cell give the "
         "table title, its row label (first-column text) and its column header, and the value text exactly as printed "
         "(keep $, %, commas, parentheses, minus signs). Include infographic grids where values sit in shapes under "
         "row/column headings. Skip charts that print no numbers. Do not compute, infer or round values.")

GROUP_DEPTH2 = {"hellenic", "carriers", "drewry", "brokers"}


# ----------------------------------------------------------------------------------------------- sampling
def group_of(rel: str) -> str:
    parts = rel.split("/")
    return "/".join(parts[:2]) if parts[0] in GROUP_DEPTH2 and len(parts) > 2 else parts[0]


def year_of(rel: str) -> str:
    m = re.search(r"(?:^|/)(20\d\d)(?:/|_|-)", rel) or re.search(r"(20\d\d)", rel)
    return m.group(1) if m else "?"


def tracked_mds() -> list[str]:
    out = subprocess.run(["git", "ls-files", "data/extracted/md"], cwd=ROOT, capture_output=True, text=True).stdout
    return [l[len("data/extracted/md/"):] for l in out.splitlines() if l.endswith(".md")]


def sample(per_source: int, sources: list[str] | None, seed: int) -> dict[str, list[str]]:
    by = defaultdict(lambda: defaultdict(list))
    for rel in tracked_mds():
        by[group_of(rel)][year_of(rel)].append(rel)
    rnd = random.Random(seed)
    picked = {}
    for g, years in sorted(by.items()):
        if sources and g not in sources:
            continue
        ys = sorted(years)
        rnd.shuffle(ys)
        chosen = []
        while len(chosen) < per_source and any(years[y] for y in ys):
            for y in ys:          # round-robin over years so every year is hit before any repeats
                if years[y] and len(chosen) < per_source:
                    chosen.append(years[y].pop(rnd.randrange(len(years[y]))))
        picked[g] = chosen
    return picked


# ----------------------------------------------------------------------------------------------- source lookup
_index: dict[str, Path] | None = None


def corpus_index() -> dict[str, Path]:
    global _index
    if _index is None:
        _index = {}
        for base in (ROOT / "corpus", MAIN_ROOT / "corpus", ROOT / "reports", MAIN_ROOT / "reports"):
            if base.exists():
                for dp, _, fs in os.walk(base):
                    for f in fs:
                        if f.lower().endswith((".pdf", ".html", ".htm")):
                            _index.setdefault(f, Path(dp) / f)
    return _index


def source_of(md_text: str) -> Path | None:
    cands = re.findall(r"(?:source_file|source_pdf|source_path|pdf|source)\s*:\s*[\"'`]?([^\"'`\n]+?\.(?:pdf|html?))", md_text[:4000], re.I)
    cands += re.findall(r"`([^`]+?\.(?:pdf|html?))`", md_text[:4000], re.I)
    for c in cands:
        c = c.strip()
        for base in (ROOT, MAIN_ROOT):
            p = base / c
            if p.is_file():
                return p
        hit = corpus_index().get(Path(c).name)
        if hit:
            return hit
    return None


# ----------------------------------------------------------------------------------------------- numbers / tables
NUM_RE = re.compile(r"\(?-?\$?\d[\d,]*\.?\d*%?\)?")


def num_key(s: str) -> str | None:
    s = str(s).strip()
    if re.fullmatch(r"[^\d]*\d+,\d{1,2}%?\)?", s):     # European decimal comma ("113,5", "-0,68%"): not a thousands separator
        s = s.replace(",", ".")
    t = re.sub(r"[\s$€£%,()+]", "", s).replace("−", "-").lstrip("-")
    if not re.fullmatch(r"\d+(\.\d+)?", t):
        return None
    if "." in t:
        t = t.rstrip("0").rstrip(".")
    t = t.lstrip("0") or "0"
    return t if len(t.replace(".", "")) >= 2 else None    # single digits collide everywhere: not evidence


def toks(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", str(s).lower().replace("**", "")) if len(w) >= 2 or w.isdigit()}


def sim(a: str, b: str) -> bool:
    ta, tb = toks(a), toks(b)
    if not ta or not tb:
        return False
    return bool(ta & tb)


def md_cells(md: str) -> tuple[list[tuple[str, str, str]], set[str]]:
    """(row_label, column_header, num_key) for every numeric table cell, plus the number keys found in prose."""
    cells, prose = [], set()
    header: list[str] | None = None
    for line in md.splitlines():
        s = line.strip()
        if s.startswith("|"):
            parts = [c.strip() for c in s.strip("|").split("|")]
            if all(re.fullmatch(r":?-{2,}:?", c) for c in parts if c):
                continue
            if header is None:
                header = parts
                continue
            # row label = every non-numeric cell (category / type / size / age columns), not just the first
            label = " ".join(c for c in parts if c and not num_key(c)) or (parts[0] if parts else "")
            for j, c in enumerate(parts):
                for m in NUM_RE.findall(c):
                    k = num_key(m)
                    if k:
                        col = header[j] if header and j < len(header) else ""
                        cells.append((label, col, k))
                        if j == 0:    # a number in the label column (years, ranks) also counts against the header
                            cells.append((c, header[0] if header else "", k))
        else:
            header = None
            for m in NUM_RE.findall(s):
                k = num_key(m)
                if k:
                    prose.add(k)
    return cells, prose


def printed_numbers(src: Path, page: int | None) -> set[str] | None:
    """Number keys in the page's text layer, or None when there is no text layer (image page, HTML)."""
    if page is None or src.suffix.lower() != ".pdf":
        return None
    import pymupdf
    text = pymupdf.open(src)[page - 1].get_text()
    keys = {k for k in (num_key(m) for m in NUM_RE.findall(text)) if k}
    return keys if len(keys) >= 5 else None


def classify(nace_cells: list[dict], md: str, printed: set[str] | None = None) -> list[dict]:
    """`printed`: the page's text-layer numbers. A Nace value not printed there was read off a chart, not transcribed:
    it is reported as `unprinted` and never counted against the MD."""
    cells, prose = md_cells(md)
    by_num = defaultdict(list)
    for r, c, k in cells:
        by_num[k].append((r, c))
    out = []
    for nc in nace_cells:
        k = num_key(nc.get("value", ""))
        if not k:
            continue
        row, col, title = nc.get("row_label", ""), nc.get("column", ""), nc.get("table_title", "")
        if printed is not None and k not in printed:
            out.append({**nc, "num": k, "status": "unprinted"})
            continue
        hits = by_num.get(k, [])
        if any((sim(row, r) or sim(title, r)) and sim(col, c) or sim(row, c) and sim(col, r) for r, c in hits):
            st = "ok"
        elif any(sim(row, r) or sim(col, c) or sim(row, c) or sim(col, r) for r, c in hits):
            st = "ok_partial"     # one label agrees (merged headers, units columns): not counted as a defect
        elif hits:
            st = "misplaced"
        elif k in prose:
            st = "in_prose"
        else:
            st = "missing"
        out.append({**nc, "num": k, "status": st})
    return out


# ----------------------------------------------------------------------------------------------- pages
def pick_pages(pdf: Path, n: int) -> list[int]:
    import pymupdf
    doc = pymupdf.open(pdf)
    scores = []
    for i, page in enumerate(doc):
        nums = len([m for m in NUM_RE.findall(page.get_text()) if num_key(m)])
        scores.append((nums, -i, i + 1))
    if not any(s[0] for s in scores):          # image-only: no text layer to rank by
        return list(range(1, min(n, len(doc)) + 1))
    return sorted(p for _, _, p in sorted(scores, reverse=True)[:n])


# ----------------------------------------------------------------------------------------------- nace
def keys() -> list[str]:
    env = Path(os.path.expanduser("~/.nace/keys.env"))
    found = []
    if env.exists():
        for line in env.read_text().splitlines():
            if re.match(r"\s*NACE_API_KEY\w*\s*=", line):
                found.append(line.split("=", 1)[1].strip().strip('"'))
    if os.environ.get("NACE_API_KEY"):
        found.insert(0, os.environ["NACE_API_KEY"])
    return list(dict.fromkeys(k for k in found if k))


class Nace:
    def __init__(self):
        self.keys, self.i, self.credits, self.retries = keys(), 0, 0, 0
        if not self.keys:
            raise SystemExit("no Nace key in ~/.nace/keys.env")

    def extract(self, path: Path, page: int | None) -> list[dict]:
        from nace_sdk import NaceClient
        while self.i < len(self.keys):
            try:
                with NaceClient(api_key=self.keys[self.i]) as c:
                    up = c.documents.upload(str(path), path="qa/" + hashlib.sha1(str(path).encode()).hexdigest()[:10] + "_" + path.name,
                                            on_conflict="new_version")
                    src = {"type": "workspace_file", "workspace_id": up.workspace_id, "file_id": up.file_id}
                    kw = {"page_ranges": [{"start": page, "end": page}]} if page else {}
                    job = c.documents.extract(src, schema=SCHEMA, instructions=INSTR, citations={"enabled": False},
                                              wait_seconds=60, **kw)
                    if job.status not in ("succeeded", "failed", "cancelled"):
                        job = c.jobs.wait(job.job_id)
                    if job.status != "succeeded":
                        raise RuntimeError(f"nace job {job.job_id} {job.status}: {getattr(job, 'error', None)}")
                    self.credits += int(getattr(job, "credits", 0) or 0)
                    self.retries = 0
                    return (job.result or {}).get("data", {}).get("cells") or []
            except Exception as e:   # noqa: BLE001 - rotate on exhausted credit, retry transient, re-raise the rest
                if any(t in str(e) for t in (": 503 ", ": 502 ", ": 504 ", ": 429 ", "timed out")) and self.retries < 4:
                    self.retries += 1
                    import time
                    time.sleep(15 * self.retries)
                    continue
                if "402" in str(e) or "insufficient_credit" in str(e).lower():
                    print(f"  key #{self.i + 1} out of credit -> rotating", flush=True)
                    self.i += 1
                    continue
                raise
        raise SystemExit("ALL Nace keys are out of credit: add more NACE_API_KEY_n lines to ~/.nace/keys.env")


# ----------------------------------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-source", type=int, default=6)
    ap.add_argument("--pages-per-doc", type=int, default=2)
    ap.add_argument("--sources", nargs="+")
    ap.add_argument("--seed", type=int, default=20261011)
    ap.add_argument("--dry-run", action="store_true", help="show the sample and pages; no Nace calls")
    a = ap.parse_args()

    CACHE.mkdir(parents=True, exist_ok=True)
    picked = sample(a.per_source, a.sources, a.seed)
    nace = None if a.dry_run else Nace()
    rows, details = [], []
    for g, mds in picked.items():
        for rel in mds:
            md = (MD_ROOT / rel).read_text(encoding="utf-8", errors="replace")
            src = source_of(md)
            if not src:
                rows.append({"source": g, "md": rel, "src": "", "pages": "", "note": "no source document found"})
                continue
            pages = pick_pages(src, a.pages_per_doc) if src.suffix.lower() == ".pdf" else [None]
            if a.dry_run:
                print(f"{g:28} {rel[-70:]:70} {src.suffix} pages={pages}")
                continue
            sha = hashlib.sha256(src.read_bytes()).hexdigest()[:16]
            got = []
            for p in pages:
                cf = CACHE / f"{sha}_p{p or 'all'}.json"
                if cf.exists():
                    cells = json.loads(cf.read_text(encoding="utf-8"))
                else:
                    try:
                        cells = nace.extract(src, p)
                    except SystemExit:
                        raise
                    except Exception as e:   # noqa: BLE001
                        print(f"  ERROR {rel}: {e}", flush=True)
                        cells = None
                    if cells is not None:
                        cf.write_text(json.dumps(cells, ensure_ascii=False), encoding="utf-8")
                for c in classify(cells or [], md, printed_numbers(src, p)):
                    got.append({**c, "page": p})
            n = len(got)
            cnt = defaultdict(int)
            for c in got:
                cnt[c["status"]] += 1
            n -= cnt["unprinted"]
            ok = cnt["ok"] + cnt["ok_partial"]
            rows.append({"source": g, "md": rel, "src": str(src), "pages": " ".join(map(str, pages)), "cells": n,
                         "ok": cnt["ok"], "ok_partial": cnt["ok_partial"], "misplaced": cnt["misplaced"],
                         "in_prose": cnt["in_prose"], "missing": cnt["missing"], "unprinted": cnt["unprinted"],
                         "ok_rate": round(ok / n, 3) if n else "", "note": ""})
            details += [{"md": rel, **c} for c in got if c["status"] in ("misplaced", "missing")]
            print(f"{g:28} {Path(rel).name[:55]:55} cells={n:4} ok={ok:4} misplaced={cnt['misplaced']:3} "
                  f"missing={cnt['missing']:3} prose={cnt['in_prose']:3}", flush=True)
    if a.dry_run:
        return 0
    fields = ["source", "md", "src", "pages", "cells", "ok", "ok_partial", "misplaced", "in_prose", "missing", "unprinted",
              "ok_rate", "note"]
    with open(OUT / "crosscheck_summary.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    with open(OUT / "crosscheck_defects.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["md", "page", "status", "table_title", "row_label", "column", "value", "num"],
                           extrasaction="ignore")
        w.writeheader()
        w.writerows(details)
    print(f"credits used this run: {nace.credits if nace else 0} -> {OUT / 'crosscheck_summary.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
