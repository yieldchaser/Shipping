"""Promotion of staged, validated output into data/extracted/md/<source>/<year>/ (plan first, then apply).

An issue is promotable when its validation report has no flags (or only flags passed with
--accept-flags). For each promoted issue the old extracted Markdown of the same issue date in the
configured legacy directories is removed with `git rm`; legacy files with no matching new issue are
kept and listed. Only files inside the legacy directories of the source are ever touched.
"""
from __future__ import annotations

import csv
import json
import os
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


class PromoteError(RuntimeError):
    """A promotion invariant failed (a target would be removed, or a target is missing after apply)."""


def _key(p: Path) -> str:
    """Case- and separator-insensitive identity of a path (the working tree may be a case-insensitive filesystem)."""
    return os.path.normcase(str(Path(p).resolve()))


def target_keys(plan: "Plan", dest_root: Path) -> set[str]:
    """Every file the plan will write (promoted MD and its sidecar)."""
    keys = set()
    for st in plan.promote:
        keys.add(_key(dest_root / st.year / (st.stem + ".md")))
        if st.tables is not None:
            keys.add(_key(dest_root / st.year / (st.stem + ".tables.json")))
    return keys


def assert_plan_invariants(plan: "Plan", dest_root: Path) -> None:
    """A path the plan writes or overwrites must never be in the removal set; each promoted target is written once."""
    targets = target_keys(plan, dest_root)
    clash = sorted(str(p) for p in plan.remove if _key(p) in targets)
    if clash:
        raise PromoteError(f"{len(clash)} removal(s) are also promotion targets, e.g. {clash[0]}")
    names = [(st.year, st.stem) for st in plan.promote]
    if len(set(names)) != len(names):
        raise PromoteError("two promoted issues share one target name")


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


def load_staged(staging: Path, source: str, require_marker: str | None = None) -> list[Staged]:
    out = []
    for vpath in sorted((staging / source).glob("*/*.validation.json")):
        stem = vpath.name[: -len(".validation.json")]
        md = vpath.with_name(stem + ".md")
        if not md.exists():
            continue
        report = json.loads(vpath.read_text(encoding="utf-8"))
        fm = read_frontmatter(md)
        tables = vpath.with_name(stem + ".tables.json")
        flags = list(report.get("flags", report.get("problems", [])))
        if require_marker and report.get(require_marker) is not True:
            flags.append(f"missing_{require_marker}")        # a post-parse step the profile requires has not run
        out.append(Staged(stem, vpath.parent.name, fm.get("issue_date"), md, tables if tables.exists() else None,
                          flags, fm.get("source_file")))
    return out


DEFAULT_NAME_MARKERS = ("clarkson", "weekly-sales")


def belongs_to_source(md: Path, markers: tuple[str, ...]) -> bool:
    """True when the legacy MD is a file of this source: its own name, or the PDF it was extracted from
    (frontmatter source_file), carries a marker. A frontmatter broker label alone is not enough: the legacy
    extraction mislabelled an SSY report as Clarksons, and nothing but this source's files may be replaced."""
    names = [md.name.lower()]
    sf = read_frontmatter(md).get("source_file")
    if sf:
        names.append(Path(str(sf)).name.lower())
    return any(m in n for n in names for m in markers)


def existing_index(dirs: list[Path], date_patterns: dict[str, Any] | None,
                   markers: tuple[str, ...]) -> tuple[set[str], set[str], set[str]]:
    """(stems, issue dates, 12-hex PDF hashes) of the source's MD files already present in `dirs`."""
    stems: set[str] = set()
    dates: set[str] = set()
    hashes: set[str] = set()
    for d in dirs:
        for md in d.rglob("*.md"):
            if not belongs_to_source(md, markers):
                continue
            stems.add(md.stem)
            dates |= old_issue_dates(md, date_patterns)
            h = HASH_SUFFIX.search(md.name)
            if h:
                hashes.add(h.group(1))
    return stems, dates, hashes


def is_existing(stem: str, issue_date: str | None, index: tuple[set[str], set[str], set[str]]) -> bool:
    stems, dates, hashes = index
    h = HASH_SUFFIX.search(stem + ".md")
    return stem in stems or bool(issue_date and issue_date in dates) or bool(h and h.group(1) in hashes)


def build_plan(source: str, staging: Path, dest_root: Path, legacy_dirs: list[Path], accept_flags: set[str],
               repo_root: Path = REPO_ROOT, date_patterns: dict[str, Any] | None = None,
               name_markers: tuple[str, ...] = DEFAULT_NAME_MARKERS, new_only: bool = False,
               require_marker: str | None = None) -> Plan:
    """new_only: promote only issues that have no MD yet (by stem, issue date or PDF hash) and never remove or
    overwrite anything: the incremental weekly mode."""
    plan = Plan()
    staged = load_staged(staging, source, require_marker)
    if new_only:
        index = existing_index([dest_root, *legacy_dirs], date_patterns, name_markers)
        for st in staged:
            blocking = [f for f in st.flags if f not in accept_flags]
            target = dest_root / st.year / (st.stem + ".md")
            if is_existing(st.stem, st.issue_date, index):
                plan.rows.append({"action": "skip_existing", "old_path": "", "new_path": str(target),
                                  "issue_date": st.issue_date or "", "detail": "an MD for this issue exists"})
            elif blocking or not st.issue_date:
                plan.rows.append({"action": "skip_flagged", "old_path": "", "new_path": str(target),
                                  "issue_date": st.issue_date or "", "detail": ";".join(blocking or ["issue_date_null"])})
            else:
                plan.promote.append(st)
                plan.rows.append({"action": "promote", "old_path": "", "new_path": str(target),
                                  "issue_date": st.issue_date, "detail": "new issue"})
        return plan
    legacy: list[tuple[Path, set[str]]] = []
    foreign: list[Path] = []
    for d in legacy_dirs:
        for md in sorted(d.rglob("*.md")):
            if belongs_to_source(md, name_markers):
                legacy.append((md, old_issue_dates(md, date_patterns)))
            else:
                foreign.append(md)

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

    for st in plan.promote:       # a promoted issue without tables must not keep an old sidecar next to it
        side = dest_root / st.year / (st.stem + ".tables.json")
        if st.tables is None and side.exists():
            plan.remove.append(side)
            plan.rows.append({"action": "git_rm_stale_sidecar", "old_path": rel(side), "new_path": "",
                              "issue_date": st.issue_date or "", "detail": "new parse has no tables"})
    for md in foreign:        # other publishers' files that live in the legacy folders: never touched
        plan.rows.append({"action": "ignore_other_publisher", "old_path": rel(md), "new_path": "",
                          "issue_date": "", "detail": "name/source_file carry no " + "/".join(name_markers)})

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
    assert_plan_invariants(plan, dest_root)
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


def _git(args: list[str], repo_root: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=repo_root, capture_output=True, text=True)


def apply_plan(plan: Plan, dest_root: Path, repo_root: Path = REPO_ROOT,
               allowed_dirs: list[Path] | None = None) -> dict[str, Any]:
    """Copy promoted files, then remove the replaced legacy files one by one. Nothing is committed.

    A tracked file is removed with `git rm` (never -f): if git refuses (local modifications) the file is
    reported in `skipped`, not forced. An untracked file is deleted only when it lies inside one of
    `allowed_dirs` (the source's own legacy folders). Files that were just written are never removed."""
    assert_plan_invariants(plan, dest_root)          # fail before touching anything
    written_n = 0
    for st in plan.promote:
        target = dest_root / st.year
        target.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(st.md, target / (st.stem + ".md"))
        written_n += 1
        if st.tables is not None:
            shutil.copyfile(st.tables, target / (st.stem + ".tables.json"))
            written_n += 1
    written = target_keys(plan, dest_root)
    allowed = [d.resolve() for d in (allowed_dirs or [])]
    report: dict[str, Any] = {"written": written_n, "removed": [], "skipped": [], "git_rm": 0, "deleted_untracked": 0}
    for p in plan.remove:
        if not p.exists() or _key(p) in written:        # a file that was just written is never removed
            continue
        if allowed and not any(a in p.resolve().parents for a in allowed):
            report["skipped"].append((str(p), "outside the source's legacy folders"))
            continue
        tracked = _git(["ls-files", "--error-unmatch", "--", str(p)], repo_root).returncode == 0
        if tracked:
            res = _git(["rm", "-q", "--", str(p)], repo_root)
            if res.returncode != 0:
                report["skipped"].append((str(p), "git rm refused: " + res.stderr.strip().splitlines()[-1][:120]))
                continue
            report["git_rm"] += 1
        else:
            p.unlink()
            report["deleted_untracked"] += 1
        report["removed"].append(str(p))
    missing = [str(Path(k)) for k in sorted(written) if not Path(k).is_file() or Path(k).stat().st_size == 0]
    if missing:
        raise PromoteError(f"{len(missing)} promoted file(s) missing or empty after apply, e.g. {missing[0]}")
    return report
