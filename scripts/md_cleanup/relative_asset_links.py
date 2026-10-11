"""Make local asset links in tracked MDs resolve, from any checkout, without publishing a machine path.

1. Absolute local links (file:///C:/Users/<you>/.../Shipping/X, file:////home/runner/.../Shipping/X) become paths
   relative to the MD.
2. Relative links that do not resolve from data/extracted/md (Breakwave and Signal MDs were written with paths
   relative to their corpus copy) are repointed to the asset, found by its unique file name.
3. Asset names that hold a literal "%20" get their "%" encoded, so a browser asks for the real file.

Only link targets change; every other byte of each file is kept. Site-relative links ("/contact") are left alone.

    python scripts/md_cleanup/relative_asset_links.py            # dry run
    python scripts/md_cleanup/relative_asset_links.py --apply [--sources breakwave signal]
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import quote, unquote

ROOT = Path(__file__).resolve().parents[2]
MAIN = ROOT.parents[2] if ROOT.parent.name == "worktrees" else ROOT   # untracked assets (PDFs) live in the main checkout
TARGET = r"((?:[^()\s]|\([^()\s]*\))+)"                                # a link target; file names may hold "(2)"
LOCAL_LINK = re.compile(r"(\]\()" + TARGET + r"(\))")
ABS_PREFIX = re.compile(r"^file:///+(?:[A-Za-z]:/(?:[^/]+/)*?Shipping|home/runner/work/Shipping/Shipping)/")
SAFE = "/._-~(),'"
ABS_SPACED = re.compile(r"(\]\()(file:///(?:[^()\n]|\([^()\n]*\))*? (?:[^()\n]|\([^()\n]*\))*?\.[A-Za-z0-9]{2,5})(\))")   # raw spaces in the file name


def git(*args: str) -> list[str]:
    out = subprocess.run(["git", "-c", "core.quotepath=off", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8").stdout
    return [x for x in out.split("\0") if x]


def exists(p: Path) -> bool:
    if p.exists():
        return True
    try:
        return (MAIN / os.path.normpath(p).replace(os.sep, "/").split(str(ROOT).replace(os.sep, "/") + "/", 1)[1]).exists()
    except IndexError:
        return False


def main() -> int:
    apply = "--apply" in sys.argv
    sources = set(sys.argv[sys.argv.index("--sources") + 1:]) if "--sources" in sys.argv else None
    stat = Counter()
    by_name: dict[str, set[str]] = {}
    for f in git("ls-files", "-z", "corpus", "data/extracted/charts", "data/extracted/md"):
        if not f.endswith((".md", ".json", ".csv")):
            by_name.setdefault(f.rsplit("/", 1)[-1], set()).add(f)
    for sub in ("corpus/03-breakwave", "corpus/07-signal"):
        for dp, _, fs in os.walk(MAIN / sub):
            for f in fs:
                by_name.setdefault(f, set()).add((Path(dp) / f).relative_to(MAIN).as_posix())
    mds = set(git("grep", "-lz", "file:///", "--", "data/extracted/md/*.md"))
    mds |= set(git("grep", "-lzE", r"\]\([^h#/{m)]", "--", "data/extracted/md/*.md"))
    for rel in sorted(mds):
        path = ROOT / rel
        if not path.exists() or (sources and rel.split("/")[3] not in sources):
            continue
        raw = path.read_bytes().decode("utf-8")
        src = rel.split("/")[3]

        def to_rel(repo_path: str) -> str:
            return quote(os.path.relpath(ROOT / repo_path, path.parent).replace(os.sep, "/"), safe=SAFE)

        def fix(m: re.Match) -> str:
            t = m.group(2)
            if t.startswith(("http:", "https:", "#", "mailto:", "data:", "/", "{")):
                return m.group(0)
            if ABS_PREFIX.match(t):
                t = to_rel_abs = ABS_PREFIX.sub("", t)
                stat["absolute links made relative"] += 1
                for cand in (unquote(to_rel_abs), to_rel_abs):
                    if (MAIN / cand).exists() or (ROOT / cand).exists():
                        return m.group(1) + to_rel(cand) + m.group(3)
                t = os.path.relpath(ROOT / unquote(to_rel_abs), path.parent).replace(os.sep, "/")
            if exists(path.parent / unquote(t)):
                return m.group(1) + t + m.group(3)
            if exists(path.parent / t):              # literal "%20" in the file name
                stat["links re-encoded"] += 1
                return m.group(1) + quote(t, safe=SAFE) + m.group(3)
            name = t.rsplit("/", 1)[-1]
            hits = by_name.get(unquote(name)) or by_name.get(name) or set()
            if len(hits) != 1:
                stat[f"links unresolved {src}"] += 1
                if "--list-missing" in sys.argv:
                    print("MISSING", rel, t)
                return m.group(1) + t + m.group(3)
            stat["links repointed"] += 1
            return m.group(1) + to_rel(next(iter(hits))) + m.group(3)

        new = LOCAL_LINK.sub(fix, ABS_SPACED.sub(lambda m: m.group(1) + m.group(2).replace(" ", "%20") + m.group(3), raw))
        if "file:///" in new:
            stat["files with file:/// left"] += 1
            print("LEFT", rel)
        if new != raw:
            stat[f"files changed {src}"] += 1
            if apply:
                path.write_bytes(new.encode("utf-8"))
    for k, v in sorted(stat.items()):
        print(f"{v:7}  {k}")
    print("APPLIED" if apply else "dry run (use --apply)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
