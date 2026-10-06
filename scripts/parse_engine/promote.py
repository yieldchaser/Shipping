"""Promotion of staged, validated output into data/extracted/md/<source>/<year>/ (plan first, then apply).

An issue is promotable when its validation report has no flags (or only flags passed with
--accept-flags). For each promoted issue the old extracted Markdown of the same issue date in the
configured legacy directories is removed with `git rm`; legacy files with no matching new issue are
kept and listed. Only files inside the legacy directories of the source are ever touched.
"""
from __future__ import annotations

import csv
import json
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from scripts.parse_engine.config import REPO_ROOT

DATE_IN_NAME = re.compile(r"(?<!\d)((?:19|20)\d{2})-(\d{2})-(\d{2})(?!\d)")
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)


@dataclass
class Staged:
    stem: str
    year: str
    issue_date: str | None
    md: Path
    tables: Path | None
    flags: list[str]
    source_file: str | None


@dataclass
class Plan:
    rows: list[dict[str, str]] = field(default_factory=list)
    promote: list[Staged] = field(default_factory=list)
    remove: list[Path] = field(default_factory=list)
    overwrite: list[Path] = field(default_factory=list)


def read_frontmatter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")[:4000]
    m = FRONTMATTER.match(text)
    if not m:
        return {}
    try:
        data = yaml.safe_load(m.group(1))
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


HASH_SUFFIX = re.compile(r"_([0-9a-f]{12})(?:\.[a-z.]+)?$")


def old_issue_dates(path: Path, date_patterns: dict[str, Any] | None = None) -> set[str]:
    """Issue dates an existing MD stands for: frontmatter issue_date, the date prefix of its name and,
    when the profile's filename patterns are given, any date they find in the name
    (e.g. 'Weekly-Sales-04th-Sept-2026')."""
    dates = set()
    if date_patterns:
        from scripts.parse_engine.dates import parse_issue_date
        iso = parse_issue_date({"filename": date_patterns.get("filename", []), "header_text": []}, "", path.name)[0]
        if iso:
            dates.add(iso)
    fm = read_frontmatter(path)
    if fm.get("issue_date"):
        dates.add(str(fm["issue_date"]))
    m = DATE_IN_NAME.search(path.name)
    if m:
        dates.add("-".join(m.groups()))
    return dates


def load_staged(staging: Path, source: str) -> list[Staged]:
    out = []
    for vpath in sorted((staging / source).glob("*/*.validation.json")):
        stem = vpath.name[: -len(".validation.json")]
        md = vpath.with_name(stem + ".md")
        if not md.exists():
            continue
        report = json.loads(vpath.read_text(encoding="utf-8"))
        fm = read_frontmatter(md)
        tables = vpath.with_name(stem + ".tables.json")
        out.append(Staged(stem, vpath.parent.name, fm.get("issue_date"), md, tables if tables.exists() else None,
                          list(report.get("flags", report.get("problems", []))), fm.get("source_file")))
    return out


def build_plan(source: str, staging: Path, dest_root: Path, legacy_dirs: list[Path], accept_flags: set[str],
               repo_root: Path = REPO_ROOT, date_patterns: dict[str, Any] | None = None) -> Plan:
    plan = Plan()
    staged = load_staged(staging, source)
    legacy: list[tuple[Path, set[str]]] = []
    for d in legacy_dirs:
        for md in sorted(d.rglob("*.md")):
            legacy.append((md, old_issue_dates(md, date_patterns)))

    def rel(p: Path) -> str:
        try:
            return p.resolve().relative_to(repo_root.resolve()).as_posix()
        except ValueError:
            return p.as_posix()

    promoted_dates: dict[str, Staged] = {}
    flagged_dates: dict[str, Staged] = {}
    for st in staged:
        blocking = [f for f in st.flags if f not in accept_flags]
        if blocking or not st.issue_date:
            plan.rows.append({"action": "skip_flagged", "old_path": "", "new_path": rel(dest_root / st.year / (st.stem + ".md")),
                              "issue_date": st.issue_date or "", "detail": ";".join(blocking or ["issue_date_null"])})
            if st.issue_date:
                flagged_dates[st.issue_date] = st
            continue
        if st.issue_date in promoted_dates:     # two staged files claiming one issue: do not guess
            plan.rows.append({"action": "skip_flagged", "old_path": "", "new_path": rel(dest_root / st.year / (st.stem + ".md")),
                              "issue_date": st.issue_date, "detail": f"duplicate_issue_date_with_{promoted_dates[st.issue_date].stem}"})
            continue
        promoted_dates[st.issue_date] = st
        plan.promote.append(st)
        new_md = dest_root / st.year / (st.stem + ".md")
        plan.rows.append({"action": "promote", "old_path": "", "new_path": rel(new_md), "issue_date": st.issue_date,
                          "detail": "accepted:" + ";".join(f for f in st.flags if f in accept_flags) if st.flags else ""})

    dest_paths = {}
    for st in plan.promote:
        base = dest_root / st.year / st.stem
        dest_paths[base.with_name(base.name + ".md").resolve()] = st
        dest_paths[base.with_name(base.name + ".tables.json").resolve()] = st

    for md, dates in legacy:
        match = next((promoted_dates[d] for d in sorted(dates) if d in promoted_dates), None)
        companions = [md, md.with_suffix(".tables.json")]
        companions = [c for c in companions if c.exists()]
        if match is None:
            h = HASH_SUFFIX.search(md.name)
            dup_of = next((st for st in plan.promote if h and st.stem.endswith("_" + h.group(1))), None)
            if dup_of is not None:
                # same PDF content as a promoted issue, filed under another date: a duplicate, not an issue
                for c in companions:
                    if c.resolve() in dest_paths:        # same path as a promoted file: it is overwritten, never removed
                        plan.overwrite.append(c)
                        plan.rows.append({"action": "overwrite_in_place", "old_path": rel(c), "new_path": rel(c),
                                          "issue_date": dup_of.issue_date or "", "detail": "same stem as promoted issue"})
                        continue
                    plan.remove.append(c)
                    plan.rows.append({"action": "git_rm_hash_duplicate", "old_path": rel(c),
                                      "new_path": rel(dest_root / dup_of.year / (dup_of.stem + ".md")),
                                      "issue_date": ",".join(sorted(dates)),
                                      "detail": f"same PDF hash as promoted issue {dup_of.issue_date} ({dup_of.stem})"})
                continue
            blocked = next((flagged_dates[d] for d in sorted(dates) if d in flagged_dates), None)
            plan.rows.append({"action": "keep_unmatched" if blocked is None else "keep_issue_flagged",
                              "old_path": rel(md), "new_path": "", "issue_date": ",".join(sorted(dates)),
                              "detail": "" if blocked is None else "new parse flagged: " + ";".join(blocked.flags)})
            continue
        new_md = dest_root / match.year / (match.stem + ".md")
        for c in companions:
            counterpart = new_md if c.suffix == ".md" else new_md.with_suffix(".tables.json")
            target_same = c.resolve() == counterpart.resolve()
            if target_same:
                plan.overwrite.append(c)
                plan.rows.append({"action": "overwrite_in_place", "old_path": rel(c), "new_path": rel(c),
                                  "issue_date": match.issue_date or "", "detail": ""})
            elif c.resolve() in dest_paths:
                plan.overwrite.append(c)
                plan.rows.append({"action": "overwrite_in_place", "old_path": rel(c), "new_path": rel(c),
                                  "issue_date": match.issue_date or "", "detail": "same stem as another promoted issue"})
            else:
                plan.remove.append(c)
                plan.rows.append({"action": "git_rm", "old_path": rel(c), "new_path": rel(new_md),
                                  "issue_date": match.issue_date or "", "detail": ""})
    return plan


def summarize(plan: Plan) -> dict[str, int]:
    counts: dict[str, int] = {}
    for r in plan.rows:
        counts[r["action"]] = counts.get(r["action"], 0) + 1
    return counts


def write_plan_csv(plan: Plan, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["action", "issue_date", "old_path", "new_path", "detail"])
        w.writeheader()
        w.writerows(plan.rows)


def apply_plan(plan: Plan, dest_root: Path, repo_root: Path = REPO_ROOT) -> None:
    """Copy promoted files, then `git rm` the replaced legacy files. Nothing is committed."""
    for st in plan.promote:
        target = dest_root / st.year
        target.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(st.md, target / (st.stem + ".md"))
        if st.tables is not None:
            shutil.copyfile(st.tables, target / (st.stem + ".tables.json"))
    written = {(dest_root / st.year / (st.stem + suffix)).resolve() for st in plan.promote
               for suffix in (".md", ".tables.json")}
    removable = [str(p) for p in plan.remove if p.exists() and p.resolve() not in written]
    for i in range(0, len(removable), 50):
        subprocess.run(["git", "rm", "-q", "-f", "--", *removable[i:i + 50]], cwd=repo_root, check=True)
