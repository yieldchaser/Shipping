#!/usr/bin/env python3
"""
GraphRAG phase P0: input inventory and readiness checks R3, R4, R7 (docs/GRAPHRAG_BUILD_PLAN.md section 1.3).

Reads the repo only. Walks the GraphRAG inputs, parses each MD's frontmatter and reports:
  R3  every MD names a source_file that exists; where the MD carries source_sha256 it must match the file
      (SEC MDs are themselves the normalised filing: their source_file points at the MD)
  R4  every MD has a parseable publication date (issue_date / filing_date / date / report_date)
  R7  no secret-shaped strings in the MD text (llx-, sk-..., ghp_, AKIA, Bearer <token>, nace_sk_)
plus counts per publisher / form: files, bytes, table-row bytes, prose bytes, date span and a token count.

Token counts use the DeepSeek-V3 tokenizer when `tokenizers` is installed and the tokenizer file can be loaded
(--tokenizer PATH, or downloaded once from the Hugging Face hub into kb/.cache); otherwise they are estimated as
prose chars/4 + table chars/2.5 and the report says so.

Outputs: kb/reports/p0_inventory.json (summary, per-group rows, every failing file) and
         kb/reports/p0_inventory_files.csv (one row per MD).
Exit 0 when R3, R4 and R7 all pass, 1 otherwise.

Usage: python kb/p0_inventory.py [--no-hash] [--no-tokens] [--tokenizer path/to/tokenizer.json]
"""
import argparse
import csv
import hashlib
import json
import re
import sys
from collections import defaultdict
import subprocess
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "kb" / "reports"
INPUTS = [
    ("broker", ROOT / "data" / "extracted" / "md"),          # data/extracted/md/<publisher>/...
    ("sec", ROOT / "corpus" / "10-companies"),               # corpus/10-companies/<TICKER>/<FORM>/...
    ("reference", ROOT / "corpus" / "books"),
]
DATE_KEYS = ("issue_date", "filing_date", "date", "report_date", "publication_date", "published")
SECRET_RE = re.compile(r"llx-[A-Za-z0-9]{8,}|\bsk-[A-Za-z0-9_]{12,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|"
                       r"Bearer\s+[A-Za-z0-9._-]{20,}|nace_sk_[A-Za-z0-9]{8,}")
PRINTED_RANGE = re.compile(r"\(\s*\d{1,2}\s*[-–]\s*(\d{1,2})\s+([A-Z][a-z]+)\s*\)")
TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$", re.M)
TOKENIZER_REPO = "deepseek-ai/DeepSeek-V3"


def frontmatter(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    fm = {}
    for line in text[3:end].splitlines():
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if m:
            fm[m[1]] = m[2].strip().strip("'\"")
    return fm


def parse_date(fm: dict, body: str = "") -> str:
    for k in DATE_KEYS:
        v = fm.get(k, "")
        m = re.match(r"(\d{4})-(\d{2})-(\d{2})", v)
        if m:
            try:
                return date(int(m[1]), int(m[2]), int(m[3])).isoformat()
            except ValueError:
                continue
        try:                                            # Breakwave prints "July 3, 2018"
            return datetime.strptime(v.strip(), "%B %d, %Y").date().isoformat()
        except ValueError:
            pass
    if fm.get("year", "").isdigit() and body:
        # issues that carry only year + broker week (Agora): the last day of the range printed on page 1, e.g.
        # "Week 35 / 2021 (23-27 August)". The broker's week number is not the ISO week, so it is not used.
        m = PRINTED_RANGE.search(body[:4000])
        if m:
            for fmt in ("%d %B %Y", "%d %b %Y"):
                try:
                    return datetime.strptime(f"{m[1]} {m[2]} {fm['year']}", fmt).date().isoformat()
                except ValueError:
                    pass
    return ""


def source_roots() -> list[Path]:
    """The worktree and the main checkout: source PDFs are gitignored and live only in the main checkout."""
    roots = [ROOT]
    try:
        common = subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=ROOT,
                                capture_output=True, text=True, check=True).stdout.strip()
        main = Path(common).parent
        if main.resolve() != ROOT.resolve():
            roots.append(main)
    except (OSError, subprocess.CalledProcessError):
        pass
    return roots


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_lf(path: Path) -> str:
    """sha256 of the file with CRLF read back as LF, i.e. of the blob git stores."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def load_tokenizer(path: str | None):
    try:
        from tokenizers import Tokenizer
    except ImportError:
        return None, "tokenizers not installed"
    try:
        if path:
            return Tokenizer.from_file(path), f"DeepSeek tokenizer from {path}"
        cache = ROOT / "kb" / ".cache"
        cache.mkdir(parents=True, exist_ok=True)
        local = cache / "deepseek_v3_tokenizer.json"
        if not local.exists():
            import urllib.request
            urllib.request.urlretrieve(f"https://huggingface.co/{TOKENIZER_REPO}/resolve/main/tokenizer.json", local)
        return Tokenizer.from_file(str(local)), f"{TOKENIZER_REPO} tokenizer.json"
    except Exception as e:  # noqa: BLE001
        return None, f"tokenizer unavailable ({e})"


def group_of(kind: str, rel: Path) -> str:
    parts = rel.parts
    if kind == "broker":
        return parts[0]
    if kind == "sec":
        return f"SEC {parts[1]}" if len(parts) > 2 else "SEC"
    return kind


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-hash", action="store_true", help="skip source_sha256 verification")
    ap.add_argument("--no-tokens", action="store_true", help="estimate tokens instead of tokenizing")
    ap.add_argument("--tokenizer", help="path to a DeepSeek tokenizer.json")
    a = ap.parse_args()

    tok, tok_note = (None, "estimated (--no-tokens)") if a.no_tokens else load_tokenizer(a.tokenizer)
    if tok is None and not a.no_tokens:
        tok_note = "estimated: " + tok_note
    files, fails = [], defaultdict(list)
    roots = source_roots()
    groups = defaultdict(lambda: {"files": 0, "bytes": 0, "table_bytes": 0, "prose_bytes": 0, "tokens": 0,
                                  "min_date": "", "max_date": ""})
    for kind, base in INPUTS:
        if not base.exists():
            continue
        for p in sorted(base.rglob("*.md")):
            rel = p.relative_to(base)
            if kind == "broker" and rel.parts[0] in ("images",):
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
            fm = frontmatter(text)
            body = text[text.find("\n---", 3) + 4:] if fm else text
            tables = "\n".join(TABLE_ROW.findall(body))
            tb, pb = len(tables.encode()), len(body.encode()) - len(tables.encode())
            d = parse_date(fm, body) if kind != "reference" else "n/a"
            # R3
            src = fm.get("source_file", "")
            if not src and fm.get("local_pdf"):          # Fearnleys bespoke research: PDF path relative to the MD
                src = (p.parent / fm["local_pdf"]).resolve().relative_to(ROOT.resolve()).as_posix()
            r3 = ""
            if kind != "reference":
                found = next((r / src for r in roots if src and (r / src).exists()), None)
                if not src:
                    # API-origin records (Fearnleys voice, Fearnleys app reports without a PDF) have no file: their
                    # provenance is the API record id
                    api = (fm.get("id") and "API" in text[:1500]) or fm.get("report_id")
                    r3 = "" if api else "no source_file"
                elif found is None:
                    r3 = f"source_file missing: {src}"
                elif fm.get("source_sha256") and not a.no_hash and fm["source_sha256"] not in (
                        sha256(found), sha256_lf(found)):   # Windows checkouts turn stored LF into CRLF
                    r3 = "source_sha256 mismatch"
            # R4
            r4 = "" if kind == "reference" or d else "no parseable publication date"
            # R7
            m7 = SECRET_RE.search(text)
            r7 = f"secret-shaped string at char {m7.start()}" if m7 else ""
            if tok is not None:
                # chunked at line breaks: one encode of a multi-MB filing exhausts the tokenizer's memory
                ntok, i = 0, 0
                while i < len(body):
                    j = body.find("\n", i + 50_000)
                    j = len(body) if j < 0 else j + 1
                    ntok += len(tok.encode(body[i:j], add_special_tokens=False).ids)
                    i = j
            else:
                ntok = round(pb / 4 + tb / 2.5)
            relp = p.relative_to(ROOT).as_posix()
            for rule, msg in (("R3", r3), ("R4", r4), ("R7", r7)):
                if msg:
                    fails[rule].append({"file": relp, "problem": msg})
            g = groups[group_of(kind, rel)]
            g["files"] += 1
            g["bytes"] += len(text.encode())
            g["table_bytes"] += tb
            g["prose_bytes"] += pb
            g["tokens"] += ntok
            if d and d != "n/a":
                g["min_date"] = min(g["min_date"] or d, d)
                g["max_date"] = max(g["max_date"], d)
            files.append({"file": relp, "kind": kind, "group": group_of(kind, rel), "date": d,
                          "bytes": len(text.encode()), "table_bytes": tb, "prose_bytes": pb, "tokens": ntok,
                          "has_sha256": bool(fm.get("source_sha256")), "R3": r3, "R4": r4, "R7": r7})

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_DIR / "p0_inventory_files.csv", "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(files[0].keys()), lineterminator="\n")
        w.writeheader()
        w.writerows(files)
    summary = {
        "generated": date.today().isoformat(),
        "token_count_method": tok_note,
        "hash_check": "skipped (--no-hash)" if a.no_hash else "source_sha256 verified where present",
        "totals": {"files": len(files), "bytes": sum(f["bytes"] for f in files),
                   "table_bytes": sum(f["table_bytes"] for f in files),
                   "prose_bytes": sum(f["prose_bytes"] for f in files), "tokens": sum(f["tokens"] for f in files),
                   "with_sha256": sum(f["has_sha256"] for f in files)},
        "checks": {r: {"pass": not fails[r], "failures": len(fails[r])} for r in ("R3", "R4", "R7")},
        "groups": dict(sorted(groups.items())),
        "failures": {r: fails[r] for r in ("R3", "R4", "R7")},
    }
    (OUT_DIR / "p0_inventory.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    t = summary["totals"]
    print(f"P0 inventory: {t['files']:,} MDs, {t['bytes'] / 1e6:,.1f} MB, {t['tokens'] / 1e6:,.1f}M tokens ({tok_note})")
    for r in ("R3", "R4", "R7"):
        c = summary["checks"][r]
        print(f"  {r}: {'PASS' if c['pass'] else 'FAIL'} ({c['failures']} failing files)")
        for f in fails[r][:5]:
            print(f"      {f['file']}: {f['problem']}")
    return 0 if all(summary["checks"][r]["pass"] for r in ("R3", "R4", "R7")) else 1


if __name__ == "__main__":
    sys.exit(main())
