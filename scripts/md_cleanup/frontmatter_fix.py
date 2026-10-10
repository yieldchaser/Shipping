"""Frontmatter-only metadata normaliser for extracted markdown (data/extracted/md).

Many extracted MDs are owner hand-perfected. This tool changes NOTHING but the metadata block:

* a file with no YAML frontmatter gets a new `---` block prepended;
* a file whose frontmatter has no `issue_date` gets the missing canonical keys appended inside
  the existing block (existing lines are never edited, reordered or removed).

The BODY (everything after the closing `---` line of the frontmatter, or the whole file when it had
none) must stay byte-identical: the sha256 of the body before and after is compared in code and a
mismatch refuses the file. Line endings (LF / CRLF) are preserved; mixed endings are skipped.

Canonical keys: title, issue_date (YYYY-MM-DD), year, report_week, publisher, source_file.
`issue_date` is never guessed: every date candidate found for a file (labelled body date, the
`Issue: Week N | ... date` line, `Week N - Month D, YYYY`, `Week N/YYYY (D Mon - D Mon)` range, the
file name, the `.tables.json` sidecar, an existing `reference_date`) must agree; no candidate or a
disagreement leaves the file unchanged and reports it.

Source markdown is never modified: results go to .reparse_staging/frontmatter_fix/ (staged .md +
.changelog.json carrying source_sha256 / staged_sha256 / body_sha256).

Usage:
    python -m scripts.md_cleanup.frontmatter_fix [--detect-only] [--limit N] [--sources a,b]
    python -m scripts.md_cleanup.frontmatter_fix --survey            # date-key report for baltic/breakwave/voice
    python -m scripts.md_cleanup.frontmatter_fix --promote            # dry-run list (default)
    python -m scripts.md_cleanup.frontmatter_fix --promote --apply    # copy changed files
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MAIN_CHECKOUT = Path(r"C:\Users\Dell\Github\Shipping")
MD_ROOT_REL = Path("data/extracted/md")
STAGING_REL = Path(".reparse_staging/frontmatter_fix")

CRLF = chr(13) + chr(10)
LF = chr(10)
CANON = ("title", "issue_date", "year", "report_week", "publisher", "source_file")
MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
     "november", "december"], 1)}
MONTHS.update({k[:3]: v for k, v in list(MONTHS.items())})
MON = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*"
HEAD_CHARS = 6000           # body header region searched for dates

# source -> profile. skip_flat: files directly under a year dir matching the glob (owned by another task).
PROFILES: dict[str, dict] = {
    "advanced_shipping": {"publisher": "Advanced Shipping & Trading",
                          "title": "Advanced Shipping & Trading Weekly Market Report - Week {week}, {year}"},
    "agora": {"publisher": "Agora Shipbroking Corporation", "agora_ranges": True,
              "title": "Agora Snapshot of Commercial Indicators - Week {week} / {year}"},
    "intermodal": {"publisher": "Intermodal Shipbrokers",
                   "title": "Intermodal Weekly Market Report - Week {week}, {year}"},
    "hellenic/dry_charter": {"publisher": "Alibra Shipping Limited", "title": "{h1}"},
    "hellenic/tanker_charter": {"publisher": "Alibra Shipping Limited", "title": "{h1}"},
    "hellenic/demolition": {"publisher": None, "title": "{h1}", "skip_flat": "gms_*.md"},
    "banchero_costa": {"publisher": "Banchero Costa", "title": "Banchero Costa Weekly Market Report - Week {week}, {year}",
                       "filename_dmy_is_date": False},
    "carriers": {"publisher": "carriers", "title": "{h1}", "filename_dmy_is_date": True},
    "fearnleys": {"publisher": "Fearnleys", "title": "Fearnleys Weekly Report - Week {week}, {year}",
                  "exclude_dirs": ("voice",)},
    "fearnleys-md": {"publisher": "Fearnleys", "title": "{h1}", "exclude_names": ("INDEX.md",)},
    "seabrokers": {"publisher": "Seabrokers Chartering",
                   "title": "Seabreeze Monthly Offshore Market Report - {month} {year}"},
    "drewry": {"publisher": "Drewry Maritime Research", "title": "{h1}"},
}
# Per-index schemas that key their date as `date:`; reported by --survey, never changed here.
SURVEY_GROUPS = {"baltic": "baltic", "breakwave": "breakwave", "fearnleys/voice": "fearnleys/voice"}


class FixError(Exception):
    pass


# ---------------------------------------------------------------- frontmatter / body split
KEY_LINE = re.compile(r"^[A-Za-z_][\w\-]*:")


def split_frontmatter(text: str) -> tuple[str | None, str]:
    """(frontmatter_block_incl_delimiters_or_None, body). Text uses a single EOL style.
    Raises FixError when the file starts with `---` but that is not a well-formed frontmatter block."""
    if not text.startswith("---"):
        return None, text
    lines = text.split(LF)
    if lines[0].rstrip(chr(13)) != "---":
        return None, text
    pos = len(lines[0]) + 1
    for i in range(1, len(lines)):
        line = lines[i].rstrip(chr(13))
        if line == "---":
            inner = lines[1:i]
            for ln in inner:
                s = ln.strip()
                if s and not (KEY_LINE.match(ln) or ln[:1] in (" ", "\t", "-", "#")):
                    raise FixError("leading '---' block is not YAML frontmatter")
            end = pos + len(lines[i]) + 1
            return text[:end], text[end:]
        pos += len(lines[i]) + 1
    raise FixError("leading '---' without a closing '---' line")


def sha(data: bytes | str) -> str:
    return hashlib.sha256(data.encode("utf-8") if isinstance(data, str) else data).hexdigest()


def fm_keys(block: str) -> dict[str, str]:
    out = {}
    for ln in block.split(LF):
        m = re.match(r"^([A-Za-z_][\w\-]*):\s*(.*?)\s*$", ln.rstrip(chr(13)))
        if m:
            out[m.group(1)] = m.group(2).strip("\"'")
    return out


# ---------------------------------------------------------------- date parsing
def mkdate(y: int, m: int, d: int) -> str | None:
    try:
        return dt.date(y, m, d).isoformat()
    except ValueError:
        return None


def month_no(name: str) -> int | None:
    return MONTHS.get(name.lower()) or MONTHS.get(name.lower()[:3])


def find_dates(text: str) -> list[str]:
    """Every full calendar date written in `text`, as ISO strings, in order of appearance."""
    text = re.sub(r"</?sup>", "", text)
    hits: list[tuple[int, str]] = []
    for m in re.finditer(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)", text):
        d = mkdate(int(m[1]), int(m[2]), int(m[3]))
        if d:
            hits.append((m.start(), d))
    for m in re.finditer(rf"(?<!\d)(\d{{1,2}})(?:st|nd|rd|th)?[ \-]({MON})[ ,\-]+(\d{{4}})(?!\d)", text, re.I):
        mo = month_no(m[2])
        d = mkdate(int(m[3]), mo, int(m[1])) if mo else None
        if d:
            hits.append((m.start(), d))
    for m in re.finditer(rf"\b({MON})\.? (\d{{1,2}})(?:st|nd|rd|th)?,? (\d{{4}})(?!\d)", text, re.I):
        mo = month_no(m[1])
        d = mkdate(int(m[3]), mo, int(m[2])) if mo else None
        if d:
            hits.append((m.start(), d))
    return [d for _, d in sorted(hits)]


LABEL = re.compile(r"^[\s>\-*_]*\**(issue date|publication date|reference date|date)\**\s*:?\s*\**\s*:?\s*(.+)$", re.I)


def body_candidates(head: str) -> tuple[list[dict], list[int]]:
    """Date candidates written in the body header: [{src, iso}], and week numbers found there."""
    cands: list[dict] = []
    weeks: list[int] = []
    seen_label = False
    for raw in head.split(LF)[:80]:
        ln = raw.rstrip(chr(13))
        m = LABEL.match(ln)
        if m and not seen_label:
            ds = find_dates(m[2])
            if ds:
                cands.append({"src": f"body:{m[1].lower()}", "iso": ds[0]})
                seen_label = True
        m = re.match(r"^\s*Issue:\s*Week\s+(\d{1,2})\b(.*)$", ln, re.I)           # intermodal
        if m:
            weeks.append(int(m[1]))
            ds = find_dates(m[2])
            if ds:
                cands.append({"src": "body:issue-line", "iso": ds[0]})
        m = re.match(r"^\s*Week\s+(\d{1,2})\s*[-\u2013]\s*(.+)$", ln, re.I)       # fearnleys weekly
        if m:
            ds = find_dates(m[2])
            if ds:
                weeks.append(int(m[1]))
                cands.append({"src": "body:week-line", "iso": ds[0]})
        m = re.search(rf"Week\s+(\d{{1,2}})\s*/\s*(\d{{4}})\s*\(\s*(\d{{1,2}})\s+({MON})\s*[-\u2013]\s*(\d{{1,2}})\s+({MON})\s*\)", ln, re.I)
        if m:                                                                       # banchero range
            iso = banchero_end(int(m[1]), int(m[2]), int(m[3]), m[4], int(m[5]), m[6])
            weeks.append(int(m[1]))
            if iso:
                cands.append({"src": "body:week-range", "iso": iso})
        m = re.match(r"^\W*(?:Report )?Week\W*:?\W*(?:Week\s+)?(\d{1,2})\b\W*$", ln, re.I)
        if m:
            weeks.append(int(m[1]))
    return cands, weeks


def banchero_end(week: int, year: int, d1: int, m1: str, d2: int, m2: str) -> str | None:
    """End date of a `Week N/YYYY (D Mon - D Mon)` range, only when the start is the Monday of ISO week N
    (in the stated year, or December before week 1/2) and the end is exactly 7 days later."""
    a, b = month_no(m1), month_no(m2)
    if not a or not b:
        return None
    y = year - 1 if (a == 12 and week <= 2) else year      # week 1 may start in December of the previous year
    start = mkdate(y, a, d1)
    if not start:
        return None
    s = dt.date.fromisoformat(start)
    if s.weekday() == 0 and s.isocalendar()[1] == week:
        e = s + dt.timedelta(days=7)
        if (e.day, e.month) == (d2, b):
            return e.isoformat()
    return None


def in_iso_week(iso: str, week: int, year: int) -> bool:
    return dt.date.fromisoformat(iso).isocalendar()[:2] == (year, week)


def agora_range_end(week: int, year: int, d1: int, m1: str | None, d2: int, m2: str) -> str | None:
    """END date of a printed `Week N / YYYY (DD-DD Month)` / `(DD Mon - DD Mon)` range, only when the end
    falls in ISO week N of YYYY and the start is 1-7 days earlier (handles `29 Dec - 02 Jan` rollover)."""
    b = month_no(m2)
    a = month_no(m1) if m1 else b
    if not a or not b:
        return None
    found = set()
    for ey in (year - 1, year, year + 1):
        end = mkdate(ey, b, d2)
        start = mkdate(ey if a <= b else ey - 1, a, d1)
        if not end or not start or not in_iso_week(end, week, year):
            continue
        if 0 < (dt.date.fromisoformat(end) - dt.date.fromisoformat(start)).days <= 7:
            found.add(end)
    return found.pop() if len(found) == 1 else None


def agora_candidates(head: str) -> tuple[list[dict], list[int]]:
    """Agora prints one token per line; collapse whitespace first. Range end date, or the printed
    `(Reference point DD Month YYYY)` date (the accepted agora MDs use it as issue_date)."""
    s = re.sub(r"\s+", " ", head)
    m = re.search(r"Week (\d{1,2}) ?/ ?(\d{4})\b", s)
    if not m:
        return [], []
    week, year = int(m[1]), int(m[2])
    tail = s[m.end():m.end() + 80]
    cands: list[dict] = []
    r = re.match(r" ?\( ?(\d{1,2}) ?([A-Za-z]+)? ?[-–�] ?(\d{1,2}) ?([A-Za-z]+) ?\)", tail)
    if r:
        iso = agora_range_end(week, year, int(r[1]), r[2], int(r[3]), r[4])
        if iso:
            cands.append({"src": "body:agora-range-end", "iso": iso})
    else:
        r = re.match(r" ?\(Reference point (\d{1,2}) ?([A-Za-z]+)[. ]*(\d{2}|\d{4})\)", tail)
        if r and month_no(r[2]):
            y = int(r[3]) + (2000 if len(r[3]) == 2 else 0)
            iso = mkdate(y, month_no(r[2]), int(r[1]))
            if iso and in_iso_week(iso, week, year):
                cands.append({"src": "body:agora-reference-point", "iso": iso})
    return cands, [week]


def name_candidates(stem: str, dmy: bool) -> tuple[list[dict], list[int]]:
    cands: list[dict] = []
    for m in re.finditer(r"(?<!\d)(\d{4})[-_](\d{2})[-_](\d{2})(?!\d)", stem):
        d = mkdate(int(m[1]), int(m[2]), int(m[3]))
        if d:
            cands.append({"src": "filename", "iso": d})
    for m in re.finditer(rf"(?<!\d)(\d{{1,2}})-({MON})-(\d{{4}})(?!\d)", stem, re.I):
        d = mkdate(int(m[3]), month_no(m[2]) or 0, int(m[1])) if month_no(m[2]) else None
        if d:
            cands.append({"src": "filename", "iso": d})
    if dmy:
        m = re.search(r"(?<!\d)(\d{2})_(\d{2})_(\d{4})(?!\d)", stem)
        if m:
            d = mkdate(int(m[3]), int(m[2]), int(m[1]))
            if d:
                cands.append({"src": "filename", "iso": d})
    weeks = [int(m[1]) for m in re.finditer(r"_W(\d{1,2})_", stem)]
    return cands, weeks


def sidecar_candidates(md: Path) -> tuple[list[dict], list[int], str | None]:
    side = md.with_name(md.stem + ".tables.json")
    if not side.exists():
        return [], [], None
    try:
        d = json.loads(side.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return [], [], None
    if not isinstance(d, dict):
        return [], [], None
    meta = d.get("metadata") if isinstance(d.get("metadata"), dict) else d
    cands, weeks = [], []
    iso = meta.get("issue_date")
    if isinstance(iso, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", iso) and mkdate(int(iso[:4]), int(iso[5:7]), int(iso[8:])):
        cands.append({"src": "sidecar", "iso": iso})
    rw = meta.get("report_week")
    if isinstance(rw, (int, str)) and str(rw).isdigit():
        weeks.append(int(rw))
    sf = meta.get("source_file")
    return cands, weeks, sf if isinstance(sf, str) else None


# ---------------------------------------------------------------- per-document derivation
def corpus_exists(rel: str) -> bool:
    return any((root / rel).exists() for root in (REPO_ROOT, MAIN_CHECKOUT))


def body_source_file(head: str) -> str | None:
    for m in re.finditer(r"`(corpus/[^`\n]+)`", head):
        return m[1]
    return None


def md_root_of(md: Path) -> Path:
    for parent in md.parents:
        if parent.name == "md" and parent.parent.name == "extracted":
            return parent
    return md.parent


def yq(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def derive(md: Path, body: str, fm: dict[str, str], prof: dict) -> dict:
    """Canonical values for one file. Raises FixError when issue_date cannot be proven."""
    head = body[:HEAD_CHARS].replace(CRLF, LF)
    cands, weeks = body_candidates(head)
    if prof.get("agora_ranges"):
        ac, aw = agora_candidates(head)
        cands += ac
        weeks += aw
    c2, w2 = name_candidates(md.stem, prof.get("filename_dmy_is_date", False))
    c3, w3, side_src = sidecar_candidates(md)
    cands += c2 + c3
    weeks += w2 + w3
    ref = fm.get("reference_date")
    if ref:
        ds = find_dates(ref)
        if ds:
            cands.append({"src": "fm:reference_date", "iso": ds[0]})
    isos = sorted({c["iso"] for c in cands})
    if not isos:
        raise FixError("no date derivable (no body date, file-name date or sidecar issue_date)")
    if len(isos) > 1:
        raise FixError("date candidates disagree: " + ", ".join(f"{c['src']}={c['iso']}" for c in cands))
    iso = isos[0]
    out: dict = {"issue_date": iso, "year": int(iso[:4]), "evidence": cands, "warnings": []}
    if len(set(weeks)) == 1:
        out["report_week"] = weeks[0]
    elif weeks:
        out["warnings"].append(f"report_week not set: sources disagree {sorted(set(weeks))}")
    h1 = next((ln.rstrip(chr(13))[2:].strip() for ln in body.replace(CRLF, LF).split(LF) if ln.startswith("# ")), "")
    tmpl = prof["title"]
    if "{h1}" in tmpl:
        title = h1 or None
    elif "{month}" in tmpl:
        title = tmpl.format(month=dt.date.fromisoformat(iso).strftime("%B"), year=out["year"])
    elif "report_week" in out:
        ym = re.search(r"_(\d{4})_W\d", md.stem)         # week-of-year label: the report's own year, which
        title = tmpl.format(week=out["report_week"], year=ym[1] if ym else out["year"])   # can differ from the date's
    else:
        title = h1 or None      # a week-templated title needs the week; fall back to the printed H1
    if title and "---" in title:
        title = None            # would break naive frontmatter splitters
    if title:
        out["title"] = title
    pub = prof.get("publisher")
    pm = re.search(r"(?im)^[\s\-*]*\**publisher\**\s*:\s*\**\s*([^|\n*]+?)\s*(?:\||$)", head)
    out["publisher"] = (pm[1].strip() if pm else pub) or None
    sf = body_source_file(head) or side_src
    if sf and not sf.startswith("corpus/") and "/" not in sf:     # a bare sidecar PDF name
        sf = f"corpus/01-brokers/{md.relative_to(md_root_of(md)).parts[0]}/{md.parent.name}/{sf}"
    if sf and not sf.startswith("corpus/"):
        sf = None
    if sf and corpus_exists(sf):
        out["source_file"] = sf
    elif sf:
        out["warnings"].append(f"source_file not set: {sf} not found under corpus/")
    return out


def render_lines(vals: dict, present: set[str]) -> tuple[list[str], list[str]]:
    lines, added = [], []
    for k in CANON:
        if k in present or vals.get(k) in (None, ""):
            continue
        v = vals[k]
        lines.append(f"{k}: {v if isinstance(v, int) else yq(str(v))}")
        added.append(k)
    return lines, added


def fix_text(md: Path, raw: str, prof: dict) -> tuple[str, dict]:
    """(new_text, info). new_text == raw when nothing changes. Raises FixError."""
    eol = CRLF if CRLF in raw else LF
    txt = raw.replace(CRLF, LF)
    if txt.replace(LF, eol) != raw:
        raise FixError("mixed line endings")
    if raw.startswith("\ufeff"):
        raise FixError("byte-order mark before frontmatter")
    block, body = split_frontmatter(txt)
    fm = fm_keys(block) if block else {}
    if "issue_date" in fm:
        return raw, {"status": "unchanged"}
    vals = derive(md, body, fm, prof)
    new_lines, added = render_lines(vals, set(fm))
    if "issue_date" not in added:
        raise FixError("issue_date could not be rendered")
    if block is None:
        new_txt = LF.join(["---", *new_lines, "---", ""]) + body
    else:
        close = block.rindex("---")
        new_txt = block[:close] + LF.join([*new_lines, ""]) + block[close:] + body
    out = new_txt.replace(LF, eol)
    nb = split_frontmatter(out.replace(CRLF, LF))[1]
    if sha(nb.replace(LF, eol)) != sha(body.replace(LF, eol)) or not out.endswith(body.replace(LF, eol)):
        raise FixError("body hash check failed")
    return out, {"status": "changed", "keys_added": added, "evidence": vals["evidence"],
                 "warnings": vals["warnings"], "body_sha256": sha(body.replace(LF, eol)),
                 "frontmatter_existed": block is not None, "values": {k: vals[k] for k in added}}


# ---------------------------------------------------------------- driver
def list_files(md_root: Path, source: str, prof: dict) -> list[Path]:
    base = md_root / source
    files = sorted(p for p in base.rglob("*.md") if p.is_file())
    out = []
    for p in files:
        rel = p.relative_to(base).parts
        if any(d in prof.get("exclude_dirs", ()) for d in rel[:-1]):
            continue
        if p.name in prof.get("exclude_names", ()):
            continue
        if prof.get("skip_flat") and len(rel) == 2 and p.match(prof["skip_flat"]):
            continue
        out.append(p)
    return out


def run(sources: list[str] | None, limit: int | None, detect_only: bool, out_root: Path,
        md_root: Path | None = None, profiles: dict | None = None) -> dict:
    md_root = md_root or (REPO_ROOT / MD_ROOT_REL)
    profiles = profiles or PROFILES
    summary: dict = {"per_source": {}, "unresolved": [], "files_changed": 0, "body_hash_checked": 0}
    for source, prof in profiles.items():
        if sources and source not in sources:
            continue
        if not (md_root / source).exists():
            continue
        st = Counter()
        keys = Counter()
        paths = list_files(md_root, source, prof)
        skipped_flat = 0
        if prof.get("skip_flat"):
            skipped_flat = sum(1 for p in (md_root / source).rglob(prof["skip_flat"])
                               if len(p.relative_to(md_root / source).parts) == 2)
        if limit:
            paths = paths[:limit]
        for p in paths:
            rel = p.relative_to(md_root)
            stale_md = out_root / rel
            if not detect_only:      # never leave a previous run's output for a file that no longer changes
                stale_md.unlink(missing_ok=True)
                stale_md.with_name(p.stem + ".changelog.json").unlink(missing_ok=True)
            st["files"] += 1
            raw_b = p.read_bytes()
            try:
                raw = raw_b.decode("utf-8")
                new, info = fix_text(p, raw, prof)
            except (FixError, UnicodeDecodeError) as exc:
                st["unresolved"] += 1
                summary["unresolved"].append({"source": source, "file": str(rel).replace(chr(92), "/"), "reason": str(exc)})
                continue
            if info["status"] == "unchanged":
                st["already_has_issue_date"] += 1
                continue
            st["changed"] += 1
            st["body_hash_ok"] += 1
            summary["body_hash_checked"] += 1
            summary["files_changed"] += 1
            for k in info["keys_added"]:
                keys[k] += 1
            if info["warnings"]:
                st["with_warnings"] += 1
            if not detect_only:
                d = out_root / rel.parent
                d.mkdir(parents=True, exist_ok=True)
                staged = new.encode("utf-8")
                (d / p.name).write_bytes(staged)
                (d / (p.stem + ".changelog.json")).write_text(json.dumps({
                    "md": str(MD_ROOT_REL / rel).replace(chr(92), "/"), "source": source,
                    "source_sha256": sha(raw_b), "staged_sha256": sha(staged), "body_sha256": info["body_sha256"],
                    "keys_added": info["keys_added"], "values": info["values"], "evidence": info["evidence"],
                    "warnings": info["warnings"], "frontmatter_existed": info["frontmatter_existed"],
                    "changes": [{"class": "frontmatter", "keys_added": info["keys_added"]}]},
                    indent=1, ensure_ascii=False), encoding="utf-8")
        entry = {**dict(st), "keys_added": dict(keys)}
        if skipped_flat:
            entry["skipped_flat_files"] = skipped_flat
        summary["per_source"][source] = entry
    return summary


def body_of(data: bytes) -> str:
    t = data.decode("utf-8")
    eol = CRLF if CRLF in t else LF
    return split_frontmatter(t.replace(CRLF, LF))[1].replace(LF, eol)


def apply_staged(staging: Path, do_apply: bool, repo_root: Path | None = None) -> dict:
    """Copy staged MDs over the real MDs, only for files that have a changelog, whose source is
    byte-identical to what the fixer read and whose body is byte-identical to the staged body."""
    repo_root = repo_root or REPO_ROOT
    res = {"applied": [], "refused": [], "dry_run": not do_apply}
    for log in sorted(staging.rglob("*.changelog.json")):
        meta = json.loads(log.read_text(encoding="utf-8"))
        staged = log.with_name(log.name[: -len(".changelog.json")] + ".md")
        target = repo_root / meta["md"]
        if not meta.get("changes") or not staged.exists() or not target.exists():
            res["refused"].append({"file": log.name, "reason": "no changes / missing staged or target"})
            continue
        if sha(target.read_bytes()) != meta.get("source_sha256"):
            res["refused"].append({"file": log.name, "reason": "target changed since staging"})
            continue
        if sha(staged.read_bytes()) != meta.get("staged_sha256"):
            res["refused"].append({"file": log.name, "reason": "staged file differs from what the fixer wrote"})
            continue
        try:
            same = sha(body_of(staged.read_bytes())) == sha(body_of(target.read_bytes())) == meta.get("body_sha256")
        except (FixError, UnicodeDecodeError):
            same = False
        if not same:
            res["refused"].append({"file": log.name, "reason": "body differs between target and staged"})
            continue
        if do_apply:
            target.write_bytes(staged.read_bytes())
        res["applied"].append(str(target.relative_to(repo_root)))
    return res


def survey(md_root: Path | None = None, groups: dict | None = None) -> dict:
    """Date-key report for the per-index groups that key their date as `date:` (read-only)."""
    md_root = md_root or (REPO_ROOT / MD_ROOT_REL)
    out = {}
    for name, rel in (groups or SURVEY_GROUPS).items():
        base = md_root / rel
        c: Counter = Counter()
        ex: dict = {}
        for p in sorted(base.rglob("*.md")):
            if name == "fearnleys" and "voice" in p.relative_to(base).parts:
                continue
            head = p.read_bytes()[:3000].decode("utf-8", "replace").replace(CRLF, LF)
            c["files"] += 1
            if not head.startswith("---"):
                c["no_frontmatter"] += 1
                continue
            end = head.find(LF + "---", 3)
            keys = fm_keys(head[: end if end > 0 else len(head)])
            if "issue_date" in keys:
                c["has_issue_date"] += 1
                continue
            dk = "date" if "date" in keys else "none"
            val = keys.get("date", "")
            form = "iso" if re.fullmatch(r"\d{4}-\d{2}-\d{2}", val) else ("derivable_text" if find_dates(val) else "unparseable")
            c[f"date_key={dk}/{form}"] += 1
            ex.setdefault(f"date_key={dk}/{form}", f"{p.relative_to(md_root)} -> {val!r}")
        out[name] = {"counts": dict(c), "examples": ex}
    return out


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--detect-only", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--sources")
    ap.add_argument("--survey", action="store_true", help="report date keys of baltic/breakwave/fearnleys voice")
    ap.add_argument("--promote", action="store_true", help="list/apply staged files, do not re-run the fixer")
    ap.add_argument("--apply", action="store_true",
                    help="copy staged files into data/extracted/md (default is a dry-run list)")
    a = ap.parse_args()
    if a.apply and not a.promote:
        ap.error("--apply requires --promote")
    if a.survey:
        print(json.dumps(survey(), indent=1, ensure_ascii=False))
        return
    if a.promote:
        r = apply_staged(REPO_ROOT / STAGING_REL, a.apply)
        print(json.dumps({"dry_run": r["dry_run"], "applied": len(r["applied"]), "refused": r["refused"]}, indent=1))
        return
    out = REPO_ROOT / STAGING_REL
    s = run(a.sources.split(",") if a.sources else None, a.limit, a.detect_only, out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "_summary.json").write_text(json.dumps(s, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in s.items() if k != "unresolved"}, indent=1, ensure_ascii=False))
    print("unresolved:", len(s["unresolved"]))


if __name__ == "__main__":
    main()
