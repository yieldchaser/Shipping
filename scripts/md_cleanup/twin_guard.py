"""CI guard: catch a newly extracted document that is a byte-identical re-drop of an issue we already hold.

The HSN collection route re-posts broker issues under dd_mm_yyyy_ / nan_ / general_broker_ names a day or two
after the broker's own drop. A CI checkout carries only the new PDFs (most broker PDFs are not in git), so the
runners' in-folder byte dedup (scripts/extract/publishers/doc_dedup.py) cannot see the earlier copy.
data/derived/pdf_md5_index.json remembers the md5 of every corpus PDF; a new MD whose PDF hash is already
indexed under another name is registered in data/derived/twin_documents.json and resolved by
scripts/md_cleanup/resolve_twins.py (twin MD archived, its series rows folded into the canonical issue).

    python scripts/md_cleanup/twin_guard.py --build-index     # (re)hash every corpus PDF on this machine
    python scripts/md_cleanup/twin_guard.py [--apply]         # after extraction, before commit
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "md_cleanup"))
from resolve_twins import REGISTRY, resolve  # noqa: E402

INDEX = ROOT / "data" / "derived" / "pdf_md5_index.json"
MD_ROOT = ROOT / "data" / "extracted" / "md"
CORPUS_ROOTS = [ROOT / "corpus"] + ([ROOT.parents[2] / "corpus"] if ROOT.parent.name == "worktrees" else [])
REPOST_NAME = re.compile(r"(?:^|_)\d{2}_\d{2}_\d{4}_|_nan_|general_broker_")


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def load_index() -> dict:
    return json.loads(INDEX.read_text(encoding="utf-8")) if INDEX.exists() else {}


def save_index(idx: dict) -> None:
    INDEX.write_text(json.dumps(dict(sorted(idx.items())), indent=0) + "\n", encoding="utf-8")


def build_index() -> None:
    idx = load_index()
    for base in CORPUS_ROOTS:
        for dp, _, fs in os.walk(base):
            for f in fs:
                if f.lower().endswith(".pdf"):
                    p = Path(dp) / f
                    rel = p.relative_to(base.parent).as_posix()
                    h = md5(p)
                    old = idx.get(h)
                    # one name per hash: prefer the broker's own name over a collection-route repost name
                    if old is None or (REPOST_NAME.search(Path(old).name) and not REPOST_NAME.search(f)):
                        idx[h] = rel
    save_index(idx)
    print(f"indexed {len(idx)} distinct PDFs -> {INDEX.relative_to(ROOT)}")


def new_mds() -> list[Path]:
    out = subprocess.run(["git", "-c", "core.quotepath=off", "status", "--porcelain", "-z", "--untracked-files=all", "--", "data/extracted/md"],
                         cwd=ROOT, capture_output=True, text=True, encoding="utf-8").stdout
    paths = [e[3:] for e in out.split("\0") if e[:2] in ("??", "A ", "AM")]
    return [ROOT / p for p in paths if p.endswith(".md")]


def source_pdf(md: Path) -> Path | None:
    m = re.search(r'^source_file:\s*"?([^"\n]+\.pdf)', md.read_text(encoding="utf-8", errors="replace")[:4000], re.M)
    if not m:
        return None
    for base in [ROOT] + [c.parent for c in CORPUS_ROOTS]:
        if (base / m.group(1)).is_file():
            return base / m.group(1)
    return None


def corpus_rel(pdf: Path) -> str:
    return "corpus/" + pdf.as_posix().split("/corpus/", 1)[-1]


def md_for_pdf(pdf_name: str) -> Path | None:
    stem = Path(pdf_name).stem
    hits = list(MD_ROOT.rglob(f"*{stem}*.md"))
    return min(hits, key=lambda p: len(p.name)) if hits else None


def main() -> int:
    if "--build-index" in sys.argv:
        build_index()
        return 0
    apply = "--apply" in sys.argv
    idx = load_index()
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    known = {t["twin"] for t in reg["twins"]}
    added = 0
    for md in sorted(new_mds(), key=lambda p: bool(REPOST_NAME.search(p.name))):  # broker names first
        pdf = source_pdf(md)
        if pdf is None:
            continue
        h = md5(pdf)
        prior = idx.get(h)
        if prior is None or Path(prior).name == pdf.name:
            idx.setdefault(h, corpus_rel(pdf))
            continue
        canon_md = md_for_pdf(prior)
        if canon_md is None or canon_md == md:
            continue
        # The newcomer is always the twin: accepted MDs are protected in CI (scripts/ci/protect_accepted_md.py),
        # so a tracked MD is never archived here even when the broker's own drop arrives after a repost.
        twin, canon = md, canon_md
        rel_twin, rel_canon = twin.relative_to(ROOT).as_posix(), canon.relative_to(ROOT).as_posix()
        if rel_twin in known:
            continue
        twin_pdf = pdf.name if twin == md else Path(prior).name
        canon_pdf = Path(prior).name if twin == md else pdf.name
        reg["twins"].append({"twin": rel_twin, "canonical": rel_canon, "twin_pdf": twin_pdf, "canonical_pdf": canon_pdf,
                             "reason": "byte-identical re-drop of the same issue (found by twin_guard)",
                             "misfile": False, "action": "archive"})
        known.add(rel_twin)
        added += 1
        print(f"TWIN {rel_twin}  ->  {rel_canon}")
    if apply:
        save_index(idx)
        if added:
            REGISTRY.write_text(json.dumps(reg, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        # also when a runner re-extracted an already-resolved twin (2024-02-13 Breakwave came back on 2026-10-12)
        if added or any((ROOT / t).exists() for t in known):
            for k, v in sorted(resolve(True).items()):
                print(f"{v:6}  {k}")
    print(f"{added} new twin(s){'' if apply else ' (dry run)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
