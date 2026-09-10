#!/usr/bin/env python3
"""
Fabrication Detector — Integrity Verification System
===================================================
Scans the repository for forbidden fabrication patterns (F1-F6) and orphan series:
  1. F1: Hardcoded series (dict literals with >= 8 numeric values keyed by year or month)
  2. F2: Silent fallbacks (except blocks returning empty/None with caller 'or <literal>', or ternary 'X if X else <numeric>')
  3. F3: Unverified provenance claims (docstrings with 'authentic', 'verified', 'genuine', '100% real', 'raw published' in files with no network calls)
  4. F5: Hardcoded timestamps ('generated_at', 'as_of', 'last_updated' assigned a date string literal)
  5. Orphan series: Any file under data/ fetched by index.html lacking an entry in data/provenance/manifest.json

Exits non-zero if any violation is detected.
"""

import ast
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
ALLOWLIST_FILE = ROOT / "scripts" / "verify" / "fabrication_allowlist.txt"
PROVENANCE_MANIFEST = ROOT / "data" / "provenance" / "manifest.json"
INDEX_HTML = ROOT / "index.html"

# Keyword regexes
PROVENANCE_WORDS = re.compile(
    r"\b(authentic|verified|genuine|100% real|raw published)\b", re.IGNORECASE
)
NETWORK_LIBS = re.compile(
    r"\b(requests|urllib|aiohttp|httpx|socket|playwright|selenium|http\.client)\b"
)
DATE_LITERAL = re.compile(r"^\d{4}-\d{2}-\d{2}")
TIMESTAMP_KEYS = {"generated_at", "as_of", "last_updated"}


def load_allowlist():
    allowlist = set()
    if ALLOWLIST_FILE.exists():
        with open(ALLOWLIST_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    parts = line.split()
                    if parts:
                        allowlist.add(parts[0])
    return allowlist


def get_numeric_value(node):
    """Extract numeric value from Constant or UnaryOp (for negative numbers)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        if isinstance(node.operand, ast.Constant) and isinstance(node.operand.value, (int, float)):
            return -node.operand.value if isinstance(node.op, ast.USub) else node.operand.value
    return None


def is_year_or_month_key(key_node):
    val = get_numeric_value(key_node)
    if val is not None and isinstance(val, int):
        if (1900 <= val <= 2100) or (1 <= val <= 12):
            return True
    elif isinstance(key_node, ast.Constant) and isinstance(key_node.value, str):
        s = key_node.value.strip()
        if re.match(r"^(19|20)\d{2}([-/](0?[1-9]|1[0-2]))?$", s):
            return True
        if re.match(r"^(0?[1-9]|1[0-2])$", s):
            return True
        if s in {
            "Jan", "Feb", "Mar", "Apr", "May", "Jun",
            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
        }:
            return True
    return False


def check_f1_hardcoded_series(file_path, tree, content_lines, allowlist, violations):
    """Detect dict literals with >= 8 numeric values keyed by year or month."""
    rel_path = str(file_path.relative_to(ROOT)).replace("\\", "/")
    if rel_path in allowlist:
        return

    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            year_month_numeric_count = 0
            has_nested_series = False

            for k, v in zip(node.keys, node.values):
                if k is not None and is_year_or_month_key(k):
                    if get_numeric_value(v) is not None:
                        year_month_numeric_count += 1
                    elif isinstance(v, ast.Dict):
                        inner_numeric = sum(
                            1
                            for ik, iv in zip(v.keys, v.values)
                            if ik is not None
                            and is_year_or_month_key(ik)
                            and get_numeric_value(iv) is not None
                        )
                        if inner_numeric >= 4:
                            has_nested_series = True
                            year_month_numeric_count += inner_numeric

            if year_month_numeric_count >= 8 or (has_nested_series and len(node.keys) >= 2):
                lineno = getattr(node, "lineno", 1)
                snippet = content_lines[lineno - 1].strip() if lineno <= len(content_lines) else ""
                violations.append({
                    "violation": "F1 (Hardcoded Series)",
                    "file": rel_path,
                    "line": lineno,
                    "snippet": snippet[:100],
                })


def check_f2_silent_fallbacks(file_path, tree, content, content_lines, violations):
    """Detect silent fallback patterns."""
    rel_path = str(file_path.relative_to(ROOT)).replace("\\", "/")

    # Pattern A: ast.IfExp where else branch is a non-zero numeric literal or fallback variable
    # e.g. x if x else -73.1, or expr if cond else 75.0
    for node in ast.walk(tree):
        if isinstance(node, ast.IfExp):
            val = get_numeric_value(node.orelse)
            if val is not None:
                lineno = getattr(node, "lineno", 1)
                snippet = content_lines[lineno - 1].strip() if lineno <= len(content_lines) else ""

                is_fallback = False
                if val != 0 and val != 0.0 and val != 1 and val != -1:
                    is_fallback = True
                elif isinstance(node.test, ast.Name) and isinstance(node.body, ast.Name):
                    if node.test.id == node.body.id:
                        is_fallback = True

                if is_fallback:
                    violations.append({
                        "violation": "F2 (Silent Fallback Literal)",
                        "file": rel_path,
                        "line": lineno,
                        "snippet": snippet[:100],
                    })

    # Pattern B: regex for `if <var> <= 0: <var> = <FALLBACK>`
    fallback_assign = re.compile(
        r"if\s+([a-zA-Z0-9_]+)\s*(?:<=|<|==)\s*0:\s*(?:\n\s*)*\1\s*=\s*([A-Z0-9_]*FALLBACK[A-Z0-9_]*|-?[0-9]+(?:\.[0-9]+)?)"
    )
    for m in fallback_assign.finditer(content):
        start_idx = m.start()
        lineno = content[:start_idx].count("\n") + 1
        snippet = content_lines[lineno - 1].strip() if lineno <= len(content_lines) else ""
        violations.append({
            "violation": "F2 (Silent Fallback Assignment)",
            "file": rel_path,
            "line": lineno,
            "snippet": snippet[:100],
        })

    # Pattern C: except block returning empty / None followed by caller 'or <literal>'
    except_fallback = re.compile(
        r"except(?:\s+[\w.]+)?:\s*(?:\n\s*)*(?:return\s*(\{\}|None)|pass)\s*(?:\n\s*)*[^\n]*\bor\s+(-?[0-9]+(?:\.[0-9]+)?|\{\}|\[\]|\w+FALLBACK\w*)"
    )
    for m in except_fallback.finditer(content):
        start_idx = m.start()
        lineno = content[:start_idx].count("\n") + 1
        snippet = content_lines[lineno - 1].strip() if lineno <= len(content_lines) else ""
        violations.append({
            "violation": "F2 (Except Silent Fallback)",
            "file": rel_path,
            "line": lineno,
            "snippet": snippet[:100],
        })


def check_f3_unverified_provenance(file_path, tree, content, content_lines, violations):
    """Detect docstrings claiming authenticity in files with no network calls."""
    rel_path = str(file_path.relative_to(ROOT)).replace("\\", "/")
    has_network = bool(NETWORK_LIBS.search(content))

    if not has_network:
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                doc = ast.get_docstring(node)
                if doc:
                    m = PROVENANCE_WORDS.search(doc)
                    if m:
                        lineno = getattr(node, "lineno", 1)
                        snippet = content_lines[lineno - 1].strip() if lineno <= len(content_lines) else ""
                        violations.append({
                            "violation": f"F3 (Unverified Provenance: '{m.group(0)}')",
                            "file": rel_path,
                            "line": lineno,
                            "snippet": snippet[:100],
                        })


def check_f5_hardcoded_timestamps(file_path, tree, content_lines, violations):
    """Detect 'generated_at', 'as_of', 'last_updated' assigned a literal date string."""
    rel_path = str(file_path.relative_to(ROOT)).replace("\\", "/")

    for node in ast.walk(tree):
        # Dict entry: {'generated_at': '2026-09-07'}
        if isinstance(node, ast.Dict):
            for k, v in zip(node.keys, node.values):
                if isinstance(k, ast.Constant) and k.value in TIMESTAMP_KEYS:
                    if isinstance(v, ast.Constant) and isinstance(v.value, str):
                        if DATE_LITERAL.match(v.value):
                            lineno = getattr(k, "lineno", 1)
                            snippet = content_lines[lineno - 1].strip() if lineno <= len(content_lines) else ""
                            violations.append({
                                "violation": f"F5 (Hardcoded Timestamp: '{k.value}')",
                                "file": rel_path,
                                "line": lineno,
                                "snippet": snippet[:100],
                            })
        # Assignment: generated_at = "2026-09-07"
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in TIMESTAMP_KEYS:
                    if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                        if DATE_LITERAL.match(node.value.value):
                            lineno = getattr(node, "lineno", 1)
                            snippet = content_lines[lineno - 1].strip() if lineno <= len(content_lines) else ""
                            violations.append({
                                "violation": f"F5 (Hardcoded Timestamp: '{target.id}')",
                                "file": rel_path,
                                "line": lineno,
                                "snippet": snippet[:100],
                            })


def check_orphan_series(violations):
    """Detect any file under data/ that index.html fetches but which has no entry in manifest.json."""
    if not INDEX_HTML.exists():
        return

    with open(INDEX_HTML, "r", encoding="utf-8", errors="ignore") as f:
        html_content = f.read()

    # Match all data file references in index.html (csv, json, parquet, js)
    fetched_files = set()
    for m in re.finditer(r'["\'](data/[a-zA-Z0-9_\-./]+\.(csv|json|parquet|js))["\']', html_content):
        fetched_files.add(m.group(1).replace("\\", "/"))

    # Also check dynamic string template interpolations like data/derived/fearnleys_comments_${desk}.json
    for m in re.finditer(r'`(data/[a-zA-Z0-9_\-./$}{]+?\.(csv|json|parquet|js))`', html_content):
        raw_tmpl = m.group(1)
        if "${desk}" in raw_tmpl:
            for desk in ["tanker", "dry", "gas", "snp"]:
                fetched_files.add(raw_tmpl.replace("${desk}", desk))
        elif "${vesselClass}" in raw_tmpl:
            for vc in ["cape", "panamax", "supramax", "handysize"]:
                fetched_files.add(raw_tmpl.replace("${vesselClass}", vc))

    # Read manifest
    manifest_files = set()
    if PROVENANCE_MANIFEST.exists():
        try:
            with open(PROVENANCE_MANIFEST, "r", encoding="utf-8") as f:
                data = json.load(f)
                entries = data.get("series", []) if isinstance(data, dict) else data
                for entry in entries:
                    if isinstance(entry, dict):
                        out_f = entry.get("output_file")
                        if out_f:
                            manifest_files.add(out_f.replace("\\", "/").lstrip("./"))
        except Exception:
            pass

    for fetched in sorted(fetched_files):
        f_norm = fetched.lstrip("./")
        if f_norm not in manifest_files:
            violations.append({
                "violation": "Orphan Series (Unregistered in manifest)",
                "file": f_norm,
                "line": 1,
                "snippet": f"index.html fetches '{f_norm}' with no registered entry in manifest.json",
            })


def main():
    allowlist = load_allowlist()
    violations = []

    # 1. Scan python files in scripts/ and bunker_pipeline/
    target_dirs = [ROOT / "scripts", ROOT / "bunker_pipeline"]
    for tdir in target_dirs:
        if not tdir.exists():
            continue
        for root, _, files in os.walk(tdir):
            for file in files:
                if file.endswith(".py"):
                    fpath = Path(root) / file
                    rel_path = str(fpath.relative_to(ROOT)).replace("\\", "/")
                    if rel_path in allowlist:
                        continue
                    try:
                        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                        tree = ast.parse(content, filename=str(fpath))
                    except Exception:
                        continue

                    content_lines = content.splitlines()

                    check_f1_hardcoded_series(fpath, tree, content_lines, allowlist, violations)
                    check_f2_silent_fallbacks(fpath, tree, content, content_lines, violations)
                    check_f3_unverified_provenance(fpath, tree, content, content_lines, violations)
                    check_f5_hardcoded_timestamps(fpath, tree, content_lines, violations)

    # 2. Scan for orphan series
    check_orphan_series(violations)

    # Print output table
    col_w = [36, 52, 6, 60]
    sep = f"+{'-' * col_w[0]}+{'-' * col_w[1]}+{'-' * col_w[2]}+{'-' * col_w[3]}+"
    header = f"| {'VIOLATION':<{col_w[0]-2}} | {'FILE':<{col_w[1]-2}} | {'LINE':<{col_w[2]-2}} | {'SNIPPET':<{col_w[3]-2}} |"

    print("\n" + sep)
    print(header)
    print(sep)

    for v in violations:
        viol = (v['violation'][:col_w[0]-5] + '...') if len(v['violation']) > col_w[0]-2 else v['violation']
        f_str = (v['file'][:col_w[1]-5] + '...') if len(v['file']) > col_w[1]-2 else v['file']
        line_str = str(v['line'])
        snip = (v['snippet'][:col_w[3]-5] + '...') if len(v['snippet']) > col_w[3]-2 else v['snippet']
        print(f"| {viol:<{col_w[0]-2}} | {f_str:<{col_w[1]-2}} | {line_str:<{col_w[2]-2}} | {snip:<{col_w[3]-2}} |")

    print(sep)
    print(f"\nTotal violations found: {len(violations)}\n")

    if violations:
        sys.exit(1)
    else:
        print("[OK] No fabrication violations detected.")
        sys.exit(0)


if __name__ == "__main__":
    main()
