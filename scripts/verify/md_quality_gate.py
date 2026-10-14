#!/usr/bin/env python3
"""
scripts/verify/md_quality_gate.py

Quality gate script enforcing rules R1-R5 on markdown files:
  R1 bare price cell: a table cell that is exactly "$", "Region $", "High $", "Low $".
  R2 fake zero change: a row with two different prices and a change cell "0.0%"/"0.00%".
  R3 personal phone: +<country code> followed by 8+ digits (allow-listing publisher switchboards).
  R4 chart readings: a table whose first column is >=80% month dates in intermodal/banchero_costa.
  R5 frontmatter source_file missing or not existing under corpus/ (main checkout path).

Output format: one line per finding:
  path:line: rule: detail
Exits 1 if findings are present, 0 if clean.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

ROOT = Path(__file__).resolve().parents[2]
MAIN_CORPUS_FALLBACK = Path("C:/Users/Dell/Github/Shipping/corpus")

# Rule R1 constants
R1_BARE_PRICE_CELLS = {"$", "Region $", "High $", "Low $"}

# Rule R2 constants
ZERO_CHANGE_PAT = re.compile(r"^[+\-~*]*0(?:\.0+)?%[~*]*$")
PRICE_NUM_PAT = re.compile(r"^\$?\s*([0-9]{1,3}(?:,[0-9]{3})+(?:\.[0-9]+)?|[0-9]+(?:\.[0-9]+)?)\s*(?:usd/day|usd|ws|points|k|m)?$", re.I)

# Rule R3 constants: Allowed publisher switchboards (normalized digits with leading +)
ALLOWED_SWITCHBOARDS: Set[str] = {
    # Fearnleys Oslo
    "+4722936000",
    # Intermodal Athens
    "+302106293300",
    "+302106293333",
    # Banchero Costa global offices
    "+3901056311",
    "+37797707497",
    "+41227372626",
    "+41912251067",
    "+442073981870",
    "+31612346176",
    "+97143605598",
    "+6563276862",
    "+861057306255",
    "+862151179589",
    "+82269592637",
    "+81362688958",
    # MMI / Hellenic
    "+6568507629",
    "+6568507630",
    "+8602151550306",
    "+862151550306",
    # Seabrokers main/office/chartering switchboards
    "+4751800000",
    "+4751815400",
    "+475181540024",
    "+4755136500",
    "+4745514551",
    "+4746518000",
    "+441224747744",
    "+4401224747744",
    "+44122474774424",
    "+552135054200",
    "+55213505420024",
}

PHONE_PAT = re.compile(r"(?<![/\w])\+(\d{1,4})[\s\-\.\(\)/]*(\d[\s\-\.\(\)/]*){7,}\d\b")

# Rule R4 constants
MONTH_DATE_PAT = re.compile(
    r"^\s*(?:\d{1,2}[/-])?(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[/-]\d{2,4}\b"
    r"|^\s*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b"
    r"|^\s*(?:19|20)\d{2}[-/]\d{1,2}[-/]\d{1,2}\b",
    re.I,
)


@dataclass
class Finding:
    path: str
    line: int
    rule: str
    detail: str

    def format(self) -> str:
        norm_path = self.path.replace("\\", "/")
        return f"{norm_path}:{self.line}: {self.rule}: {self.detail}"


def split_table_row(line: str) -> List[str]:
    """Split markdown table line into cells, trimming whitespace and boundary pipes."""
    s = line.strip()
    if not s or "|" not in s:
        return []
    cells = [c.strip() for c in s.split("|")]
    if len(cells) >= 2 and cells[0] == "":
        cells = cells[1:]
    if len(cells) >= 1 and cells[-1] == "":
        cells = cells[:-1]
    return cells


def is_divider_row(cells: List[str]) -> bool:
    """Check if table row is markdown separator like |---|---:|."""
    if not cells:
        return False
    return all(re.match(r"^:?-+:?$", c) for c in cells)


def check_r1(line: str) -> List[str]:
    """R1: table cell that is exactly '$', 'Region $', 'High $', 'Low $'."""
    cells = split_table_row(line)
    if is_divider_row(cells):
        return []
    findings = []
    for c in cells:
        if c in R1_BARE_PRICE_CELLS:
            findings.append(c)
    return findings


def check_r2(line: str) -> List[Tuple[float, float, str]]:
    """
    R2: row with two different prices and a change cell '0.0%'/'0.00%'.
    Returns list of (price1, price2, zero_change_cell_text).
    """
    cells = split_table_row(line)
    if is_divider_row(cells):
        return []

    zero_cells = []
    for c in cells:
        clean = c.replace("*", "").replace("~", "").strip()
        if ZERO_CHANGE_PAT.match(clean):
            zero_cells.append(c)

    if not zero_cells:
        return []

    # Extract price candidates from other cells
    prices: List[float] = []
    for c in cells:
        clean = c.replace("*", "").replace("~", "").strip()
        if clean in zero_cells or "%" in clean:
            continue
        m = PRICE_NUM_PAT.match(clean)
        if m:
            val_str = m.group(1).replace(",", "")
            try:
                val = float(val_str)
                # Ignore isolated years 1990-2030 unless clearly a price
                if not ("$" in clean or "usd" in clean.lower() or "," in m.group(1)):
                    if 1990 <= val <= 2030 and val.is_integer():
                        continue
                prices.append(val)
            except ValueError:
                pass

    if len(prices) >= 2:
        distinct = sorted(set(prices))
        if len(distinct) >= 2:
            p1, p2 = distinct[0], distinct[1]
            return [(p1, p2, zero_cells[0])]

    return []


def check_r3(line: str, allowed: Set[str] = ALLOWED_SWITCHBOARDS) -> List[str]:
    """
    R3: personal phone: +<country code> followed by 8+ digits.
    Ignores markdown image URLs and allowed publisher switchboard numbers.
    """
    # Strip markdown image syntax ![...](...) to avoid encoded space false-positives
    sanitized = re.sub(r"!\[.*?\]\([^\)]*\)", "", line)
    # Strip markdown link destinations [...](url)
    sanitized = re.sub(r"\[.*?\]\([^\)]*\)", "", sanitized)

    findings = []
    for m in PHONE_PAT.finditer(sanitized):
        raw = m.group(0)
        norm = "+" + re.sub(r"\D", "", raw)
        if len(norm) < 9:  # + plus at least 8 digits
            continue
        if norm in allowed:
            continue
        findings.append(raw)
    return findings


def check_r4_table(rows: List[List[str]]) -> Optional[float]:
    """
    R4: a table whose first column is >=80% month dates.
    Returns the month ratio if >= 0.80, else None.
    """
    if len(rows) < 3:
        return None
    # Skip header
    data_rows = rows[1:]
    if not data_rows:
        return None
    month_count = 0
    total = len(data_rows)
    for r in data_rows:
        if not r:
            continue
        first_cell = r[0]
        if MONTH_DATE_PAT.search(first_cell):
            month_count += 1
    ratio = month_count / total
    return ratio if ratio >= 0.80 else None


def parse_frontmatter(text: str) -> Dict[str, Any]:
    """Parse YAML frontmatter from start of file."""
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    fm_text = parts[1]
    res: Dict[str, Any] = {}
    for line in fm_text.splitlines():
        if ":" in line and not line.strip().startswith("#"):
            k, v = line.split(":", 1)
            res[k.strip()] = v.strip().strip("\"'")
    return res


def check_r5(frontmatter: Dict[str, Any], corpus_roots: List[Path]) -> Optional[str]:
    """
    R5: frontmatter source_file missing or not existing under corpus/ (main checkout path).
    Returns error detail string if invalid, None if OK.
    """
    src = frontmatter.get("source_file")
    if not src:
        return "frontmatter missing or empty 'source_file'"

    for root in corpus_roots:
        cand = root / src if not src.startswith("corpus/") else root / src[len("corpus/"):]
        if cand.exists():
            return None
        direct = root.parent / src
        if direct.exists():
            return None
        if (Path(src)).exists():
            return None

    return f"source_file '{src}' does not exist under corpus/"


def scan_file(file_path: Path, corpus_roots: Optional[List[Path]] = None) -> List[Finding]:
    """Scan a single markdown file against rules R1-R5."""
    findings: List[Finding] = []
    path_str = str(file_path)
    posix_path = file_path.as_posix()

    if corpus_roots is None:
        corpus_roots = [ROOT / "corpus", MAIN_CORPUS_FALLBACK]

    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return [Finding(path_str, 1, "R0", f"could not read file: {e}")]

    lines = content.splitlines()

    # Rule R5: frontmatter check for extracted markdown files
    if "data/extracted/md/" in posix_path:
        fm = parse_frontmatter(content)
        r5_err = check_r5(fm, corpus_roots)
        if r5_err:
            findings.append(Finding(path_str, 1, "R5", r5_err))

    # Check line-by-line rules R1, R2, R3, and collect tables for R4
    is_r4_scope = ("data/extracted/md/intermodal" in posix_path or
                   "data/extracted/md/banchero_costa" in posix_path or
                   "data/extracted/md/banchero-costa" in posix_path)

    current_table: List[List[str]] = []
    table_start_line = 0

    for idx, line in enumerate(lines, 1):
        # R1
        for bare in check_r1(line):
            findings.append(Finding(path_str, idx, "R1", f"bare price cell '{bare}'"))

        # R2
        for p1, p2, z_cell in check_r2(line):
            findings.append(
                Finding(
                    path_str,
                    idx,
                    "R2",
                    f"fake zero change '{z_cell}' with differing prices ({p1} != {p2})",
                )
            )

        # R3
        for phone in check_r3(line):
            findings.append(Finding(path_str, idx, "R3", f"personal phone '{phone}'"))

        # R4 table collection
        if is_r4_scope:
            if "|" in line:
                cells = split_table_row(line)
                if cells and not is_divider_row(cells):
                    if not current_table:
                        table_start_line = idx
                    current_table.append(cells)
            else:
                if current_table:
                    ratio = check_r4_table(current_table)
                    if ratio is not None:
                        findings.append(
                            Finding(
                                path_str,
                                table_start_line,
                                "R4",
                                f"table first column is {ratio:.0%} month dates (chart reading instead of chart notes)",
                            )
                        )
                    current_table = []

    # Final table at end of file if any
    if is_r4_scope and current_table:
        ratio = check_r4_table(current_table)
        if ratio is not None:
            findings.append(
                Finding(
                    path_str,
                    table_start_line,
                    "R4",
                    f"table first column is {ratio:.0%} month dates (chart reading instead of chart notes)",
                )
            )

    return findings


def get_changed_md_files(base: str = "origin/main") -> List[Path]:
    """Get list of changed markdown files vs base."""
    files: Set[str] = set()
    try:
        out = subprocess.check_output(
            ["git", "diff", "--name-only", f"{base}...HEAD"],
            cwd=ROOT,
            text=True,
            encoding="utf-8",
        )
        files.update(out.splitlines())
    except Exception:
        pass

    try:
        out_unstaged = subprocess.check_output(
            ["git", "diff", "--name-only"],
            cwd=ROOT,
            text=True,
            encoding="utf-8",
        )
        files.update(out_unstaged.splitlines())
    except Exception:
        pass

    md_files = [ROOT / f for f in files if f.endswith(".md") and (ROOT / f).exists()]
    return md_files


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Markdown Quality Gate (R1-R5)")
    ap.add_argument("files", nargs="*", help="Files or directories to check")
    ap.add_argument("--all", action="store_true", help="Scan all MD files in repo")
    ap.add_argument("--base", default="origin/main", help="Git base for diff (default: origin/main)")
    ap.add_argument("--corpus-root", default=None, help="Corpus root directory")
    args = ap.parse_args(argv)

    corpus_roots = [Path(args.corpus_root)] if args.corpus_root else [ROOT / "corpus", MAIN_CORPUS_FALLBACK]

    if args.all:
        paths = list(ROOT.rglob("*.md"))
    elif args.files:
        paths = []
        for f in args.files:
            p = Path(f)
            if not p.is_absolute():
                p = ROOT / p
            if p.is_dir():
                paths.extend(p.rglob("*.md"))
            elif p.is_file():
                paths.append(p)
    else:
        paths = get_changed_md_files(args.base)

    findings: List[Finding] = []
    for p in sorted(paths):
        findings.extend(scan_file(p, corpus_roots=corpus_roots))

    for f in findings:
        print(f.format())

    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
