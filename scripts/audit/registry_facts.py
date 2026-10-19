"""Facts for the corpus registry, counted from disk on every run (never carried over from a hardcoded value).

Per registry entry:
  raw counts (pdf/html/img/md in the corpus folder, plus PDFs that are only listed in the untracked inventory,
  since corpus PDFs are gitignored and CI checkouts do not have them), latest raw issue, latest parsed MD issue,
  parse backlog (recent raw issues no MD points at), parse quality (tables sidecars, tiny MDs, universal-fallback
  MDs), and a status from the source's cadence: CURRENT / DUE / STALE / PARSE BEHIND / REFERENCE.

Nested folders that belong to another entry (fearnleys/voice inside fearnleys) are excluded, and an MD folder
shared by two entries (Clarksons via 01-brokers and via 02-hellenic/shipbuilding) is split by each MD's
frontmatter source_file.
"""
from __future__ import annotations

import bisect
import os
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

RAW_EXT = (".pdf", ".html", ".htm")
IMG_EXT = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")

# days a source may go without a new issue before it is DUE; STALE beyond twice that
ALLOWED_GAP = {
    "Daily": 4, "Daily / Bi-weekly": 7, "Weekly": 10, "Bi-weekly": 21, "Monthly": 45,
    "Continuous / Periodic": 120,
}
BACKLOG_WINDOW_DAYS = 120          # raw issues newer than this must have an MD
TINY_MD_BYTES = 800
FALLBACK_MARK = re.compile(r"^detected_charts: \d+\s*$", re.M)   # frontmatter key only the orchestrator universal-pipeline MD writes
FM_DATE = re.compile(r"^(?:issue_date|date|filing_date|report_date|published)\s*:\s*[\"']?(\d{4}-\d{2}-\d{2})", re.M)
FM_SRC = re.compile(r"^(?:source_file|source_pdf|source_path)\s*:\s*[\"']?([^\"'\n]+)", re.M)


def _rel(root: Path, p: Path) -> str:
    return p.resolve().relative_to(root.resolve()).as_posix()


def _walk(base: Path, exclude: List[Path]):
    ex = [e.resolve() for e in exclude]
    for r, dirs, files in os.walk(base):
        rp = Path(r).resolve()
        dirs[:] = [d for d in dirs if (rp / d) not in ex and not d.startswith((".", "_staging"))]
        for f in files:
            if not f.startswith("."):
                yield Path(r) / f


def _head(p: Path, n: int = 1500) -> str:
    try:
        with open(p, "r", encoding="utf-8", errors="ignore") as fh:
            return fh.read(n)
    except OSError:
        return ""


def collect(root: Path, registry: List[dict], untracked: List[str], parse_date, today: date,
            only: Optional[str] = None) -> Dict[str, dict]:
    folders = {e["category_id"]: (root / e["folder"]) for e in registry}
    mddirs = {e["category_id"]: (root / e["md_dir"]) for e in registry}
    shared = {}
    for cid, d in mddirs.items():
        shared.setdefault(d.resolve(), []).append(cid)
    out: Dict[str, dict] = {}
    for e in registry:
        if only and e["category_id"] != only:
            continue
        cid, folder, mdd = e["category_id"], folders[e["category_id"]], mddirs[e["category_id"]]
        others_f = [f for c, f in folders.items() if c != cid and f.resolve() != folder.resolve()
                    and folder.resolve() in f.resolve().parents]
        others_m = [d for c, d in mddirs.items() if c != cid and d.resolve() != mdd.resolve()
                    and mdd.resolve() in d.resolve().parents]
        prefix = e["folder"].rstrip("/") + "/"

        # ---- raw corpus
        raw: Dict[str, Optional[date]] = {}
        counts = {"pdf": 0, "html": 0, "img": 0, "md": 0, "total": 0}
        files = set()
        if folder.exists():
            files |= {_rel(root, p) for p in _walk(folder, others_f)}
        ex_pref = [_rel(root, f) + "/" for f in others_f if f.exists()] + \
                  [str(f.relative_to(root)).replace("\\", "/") + "/" for f in others_f]
        files |= {u for u in untracked if u.startswith(prefix) and not any(u.startswith(x) for x in ex_pref)}
        for rp in files:
            name = rp.rsplit("/", 1)[-1].lower()
            counts["total"] += 1
            if name.endswith(".pdf"):
                counts["pdf"] += 1
            elif name.endswith((".html", ".htm")):
                counts["html"] += 1
            elif name.endswith(IMG_EXT):
                counts["img"] += 1
            elif name.endswith(".md"):
                counts["md"] += 1
            if name.endswith(RAW_EXT) and (not e.get("raw_match") or re.search(e["raw_match"], name, re.I)):
                raw[rp] = parse_date(rp.rsplit("/", 1)[-1])   # raw_match: the issues this entry parses to MD

        # ---- parsed MDs
        same_tree = mdd.resolve() == folder.resolve()
        split_by_source = len(shared.get(mdd.resolve(), [])) > 1
        mds: List[tuple] = []
        if mdd.exists():
            for p in _walk(mdd, others_m):
                if not p.name.lower().endswith(".md") or p.name.startswith("_") or p.name.upper().startswith("README"):
                    continue
                h = _head(p, 4000)
                m = FM_SRC.search(h[:1500])
                src = m.group(1).strip() if m else ""
                if split_by_source and not src.replace("\\", "/").startswith(prefix):
                    continue
                m = FM_DATE.search(h[:1500])
                d = parse_date(m.group(1)) if m else None
                d = d or parse_date(p.name)
                mds.append((p, d, src, bool(FALLBACK_MARK.search(h)), len(h) < TINY_MD_BYTES and p.stat().st_size < TINY_MD_BYTES))
        if same_tree:                       # native-MD sources (SEC filings, books): the MDs are the corpus
            raw = {_rel(root, m[0]): m[1] for m in mds}

        n_md = len(mds)
        sidecars = sum(1 for m in mds if m[0].with_name(m[0].name[:-3] + ".tables.json").exists())
        tiny = [m[0] for m in mds if m[4]]
        fallback = [m[0] for m in mds if m[3]]

        # ---- backlog: recent raw issues with no MD dated near them. Matched on the issue date, not the file
        # name: two downloaders name the same issue differently (xclusiv_06_10_2026_... vs xclusiv-2026_10_05).
        md_dates = sorted({m[1] for m in mds if m[1]})
        cutoff = today - timedelta(days=BACKLOG_WINDOW_DAYS)

        # downloaders name files by fetch date (ism_14_09_2026 = the Week 37 issue dated 09-07): a weekly issue
        # can sit up to a week after its MD's issue_date
        tol = timedelta(days=3 if e.get("frequency", "").startswith("Daily") else 8)

        def _has_md(d: date) -> bool:
            i = bisect.bisect_left(md_dates, d - tol)
            return i < len(md_dates) and md_dates[i] <= d + tol

        # only raw types MDs are actually made from (Hellenic shipbuilding: Clarksons PDFs -> MD, its HTML news
        # pages feed the knowledge layer only); a source with no MDs at all is series-only (PPA)
        src_ext = {Path(m[2]).suffix.lower() for m in mds if m[2]}
        backlog = sorted(rp for rp, d in raw.items() if d and cutoff <= d <= today and not same_tree and mds
                         and (not src_ext or Path(rp).suffix.lower() in src_ext) and not _has_md(d))

        def _latest(pairs):
            best = None
            for k, d in pairs:
                if d and d <= today + timedelta(days=7) and (best is None or d > best[1]):
                    best = (k, d)
            return best

        lr = _latest(raw.items())
        lm = _latest(((m[0].name, m[1]) for m in mds))
        out[cid] = {
            "pdf_count": counts["pdf"], "html_count": counts["html"], "image_count": counts["img"],
            "corpus_md_count": counts["md"], "total_files": counts["total"], "md_count": n_md,
            "latest_raw_date": lr[1].isoformat() if lr else "", "latest_raw_file": Path(lr[0]).name if lr else "",
            "latest_md_date": lm[1].isoformat() if lm else "", "latest_md_file": lm[0] if lm else "",
            "earliest_md_date": md_dates[0].isoformat() if md_dates else "",
            "sidecar_pct": round(100.0 * sidecars / n_md, 1) if n_md else 0.0,
            "tiny_md": len(tiny), "fallback_md": len(fallback),
            "fallback_examples": [p.name for p in fallback[:3]],
            "backlog": len(backlog), "backlog_examples": [Path(b).name for b in backlog[:3]],
        }
        out[cid]["status"], out[cid]["days_ago"] = status_for(e, out[cid], today)
    return out


def status_for(entry: dict, f: dict, today: date) -> Tuple[str, int]:
    freq = entry.get("frequency", "")
    latest = max(f["latest_raw_date"], f["latest_md_date"])   # ISO strings; some raw names carry no date
    if freq.startswith("Static"):
        return "REFERENCE", 0
    if entry.get("superseded_by"):
        return f"SUPERSEDED (new issues arrive via {entry['superseded_by']})", 0
    if not latest:
        return "NO DATED ISSUES", -1
    days = max(0, (today - date.fromisoformat(latest)).days)
    gap = ALLOWED_GAP.get(freq, 10)
    if f["backlog"]:
        return f"PARSE BEHIND ({f['backlog']} recent issue(s) without MD)", days
    if f["latest_raw_date"] and f["latest_md_date"] and f["latest_md_date"] < f["latest_raw_date"]:
        lag = (date.fromisoformat(f["latest_raw_date"]) - date.fromisoformat(f["latest_md_date"])).days
        if lag > 3:
            return f"PARSE BEHIND (latest MD {lag}d older than latest issue)", days
    if days <= gap:
        return f"CURRENT ({days}d)", days
    if days <= 2 * gap:
        return f"DUE ({days}d, cadence {freq.lower()})", days
    return f"STALE ({days}d, cadence {freq.lower()})", days
