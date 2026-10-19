"""Resolve same-issue duplicate documents ("twins") listed in data/derived/twin_documents.json.

A twin is a second copy of one report issue: mostly the HSN collection route re-dropping an issue under a
dd_mm_yyyy_ / nan_ / general_broker_ name (the date is the repost date), plus a few second downloads and misfiles.
Both copies get parsed, so every such issue double-counts in the MDs and the series.

Nothing is deleted:
  archive   the twin MD and its sidecar move to data/archive/twins/<same path>.
  promote   the twin's extraction read more of the PDF than the canonical one, so the canonical MD/sidecar move to
            data/archive/twins/superseded/<same path> and the twin's content takes the canonical path (its file
            names rewritten to the canonical ones); then the twin is archived as above.
Series rows: a row naming the twin is renamed to the canonical document (repost date -> canonical issue date) and
dropped only when the canonical already has that exact row. A misfile twin's rows describe another issue under the
wrong date, so they are dropped (the real issue's own rows stay).

    python scripts/md_cleanup/resolve_twins.py            # dry run: report only
    python scripts/md_cleanup/resolve_twins.py --apply
"""
from __future__ import annotations

import csv
import io
import json
import re
import shutil
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "data" / "derived" / "twin_documents.json"
ARCHIVE = ROOT / "data" / "archive" / "twins"
SERIES = ROOT / "data" / "extracted" / "series"


def issue_date(md: Path) -> str | None:
    m = re.search(r'^issue_date:\s*"?(\d{4}-\d{2}-\d{2})', md.read_text(encoding="utf-8")[:3000], re.M)
    return m.group(1) if m else None


def companions(md: Path) -> list[Path]:
    return [p for p in (md, md.with_name(md.name[:-3] + ".tables.json")) if p.exists()]


def move(src: Path, dest_root: Path, apply: bool) -> None:
    dest = dest_root / src.relative_to(ROOT / "data" / "extracted" / "md")
    if apply:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dest))


def rename_text(text: str, t: dict) -> str:
    """Point a promoted twin's text at the canonical document."""
    tw, ca = Path(t["twin"]), Path(t["canonical"])
    for a, b in ((t["twin_pdf"], t["canonical_pdf"]), (tw.stem, ca.stem), (Path(t["twin_pdf"]).stem, Path(t["canonical_pdf"]).stem)):
        text = text.replace(a, b)
    return text


DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def records(raw: str, nl: str) -> list[str]:
    """Split CSV text into raw records (a quoted cell may hold newlines; quotes pair up within a record)."""
    out, cur = [], None
    for line in raw.split(nl):
        cur = line if cur is None else cur + nl + line
        if cur.count('"') % 2 == 0:
            out.append(cur)
            cur = None
    if cur is not None:
        out.append(cur)
    return out


def base(cell: str) -> str:
    """A cell that holds a document path counts by its file name (series cite corpus/.../<name>.pdf)."""
    return cell.rsplit("/", 1)[-1]


def masked(cells: list[str], src_names: set) -> tuple:
    """Row identity without the document name and dates (a repost carries its repost date)."""
    return tuple("" if base(c) in src_names or DATE_RE.match(c) else c for c in cells)


def fix_series(twins: list[dict], apply: bool, stat: Counter) -> None:
    by_name, canon_names = {}, {}
    for t in twins:
        for n in {t["twin_pdf"], Path(t["twin_pdf"]).stem, Path(t["twin"]).name, Path(t["twin"]).stem}:
            by_name[n] = t
        for n in {t["canonical_pdf"], Path(t["canonical_pdf"]).stem, Path(t["canonical"]).name, Path(t["canonical"]).stem}:
            canon_names[n] = t
    for csv_path in sorted(SERIES.glob("*.csv")):
        raw = csv_path.read_bytes().decode("utf-8")
        if not any(n in raw for n in by_name):
            continue
        nl = "\r\n" if "\r\n" in raw else "\n"
        recs = records(raw, nl)
        parsed = [next(csv.reader(io.StringIO(r)), []) if r else [] for r in recs]
        # canonical rows per twin entry: masked identity + the date they carry
        canon_keys, canon_date = {}, {}
        for cells in parsed[1:]:
            t = next((canon_names[base(c)] for c in cells if base(c) in canon_names), None)
            if t is not None:
                names = {n for n, x in canon_names.items() if x is t}
                canon_keys.setdefault(id(t), set()).add(masked(cells, names))
                d = next((c for c in cells if DATE_RE.match(c)), None)
                if d:
                    canon_date.setdefault(id(t), Counter())[d] += 1
        out, changed = [recs[0]], False
        for rec, cells in zip(recs[1:], parsed[1:]):
            t = next((by_name[base(c)] for c in cells if base(c) in by_name), None)
            if t is None:
                out.append(rec)
                continue
            changed = True
            if t.get("misfile"):
                stat[f"series rows dropped (misfile twin) {csv_path.name}"] += 1
                continue
            twin_names = {n for n, x in by_name.items() if x is t}
            key = masked(cells, twin_names)
            if key in canon_keys.get(id(t), set()):
                stat["series rows dropped (canonical has the same row)"] += 1
                continue
            cdate = canon_date[id(t)].most_common(1)[0][0] if id(t) in canon_date else t.get("canonical_issue_date")
            tdate = next((c for c in cells if DATE_RE.match(c)), None)
            new = []
            for c in cells:
                if c in by_name:
                    c = {t["twin_pdf"]: t["canonical_pdf"], Path(t["twin_pdf"]).stem: Path(t["canonical_pdf"]).stem,
                         Path(t["twin"]).name: Path(t["canonical"]).name, Path(t["twin"]).stem: Path(t["canonical"]).stem}[c]
                elif cdate and c == tdate:
                    c = cdate
                else:
                    c = c.replace(t["twin_pdf"], t["canonical_pdf"])
                new.append(c)
            canon_keys.setdefault(id(t), set()).add(key)
            buf = io.StringIO()
            csv.writer(buf, lineterminator=nl).writerow(new)
            out.append(buf.getvalue()[: -len(nl)])
            stat["series rows renamed to canonical (kept: canonical lacks them)"] += 1
        if changed and apply:
            csv_path.write_bytes(nl.join(out).encode("utf-8"))


def resolve(apply: bool) -> Counter:
    twins = json.loads(REGISTRY.read_text(encoding="utf-8"))["twins"]
    stat = Counter()
    todo = [t for t in twins if (ROOT / t["twin"]).exists()]
    stat["already resolved"] = len(twins) - len(todo)
    for t in [t for t in todo if not (ROOT / t["canonical"]).exists()]:
        print("SKIP: canonical missing", t["canonical"])
        stat["skipped: canonical missing"] += 1
        todo.remove(t)
    for t in todo:
        t["canonical_issue_date"] = issue_date(ROOT / t["canonical"]) if (ROOT / t["canonical"]).exists() else None
    fix_series(todo, apply, stat)
    for t in todo:
        tw, ca = ROOT / t["twin"], ROOT / t["canonical"]
        if t["action"] == "promote":
            new_files = {p: rename_text(p.read_bytes().decode("utf-8"), t) for p in companions(tw)}
            tw_date = issue_date(tw)
            if tw_date and t["canonical_issue_date"] and tw_date != t["canonical_issue_date"]:  # repost date -> issue date
                new_files = {p: x.replace(tw_date, t["canonical_issue_date"]) for p, x in new_files.items()}
            for p in companions(ca):
                move(p, ARCHIVE / "superseded", apply)
            if apply:
                for p, text in new_files.items():
                    (ca.parent / rename_text(p.name, t)).write_bytes(text.encode("utf-8"))
            stat["promoted"] += 1
        for p in companions(tw):
            move(p, ARCHIVE, apply)
        stat["twins archived"] += 1
    return stat


def main() -> int:
    apply = "--apply" in sys.argv
    stat = resolve(apply)
    for k, v in sorted(stat.items()):
        print(f"{v:6}  {k}")
    print("APPLIED" if apply else "dry run (use --apply)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
