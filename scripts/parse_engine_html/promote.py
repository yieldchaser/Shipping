"""Promote staged VV Markdown over the live tree - only issues that pass the checks, never any other.

Dry run by default; `--apply` writes `vv_<date>.md` and `vv_<date>.tables.json` into the live year folders. A live
file is overwritten only for a passing issue; live files of failing issues and issues without a staged copy are not
touched. Series CSVs are not written here (see `compare` / `fallback`).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from scripts.parse_engine_html import PARSER_NAME
from scripts.parse_engine_html.pipeline import DEFAULT_OUT, LIVE_MD, sha256_file
from scripts.parse_engine_html.render import MATRIX_UNREADABLE

_ABS_PATH_RE = re.compile(r"^(?:[A-Za-z]:[\\/]|[\\/])")


def _is_absolute(path: str) -> bool:
    return bool(_ABS_PATH_RE.match(path.strip()))


_FM_RE = re.compile(r"\A---\n(.*?)\n---\n", re.S)


def _front(md_text: str) -> dict[str, str]:
    m = _FM_RE.match(md_text)
    out: dict[str, str] = {}
    for line in (m.group(1).splitlines() if m else []):
        if re.match(r"[a-z_]+:", line):
            k, _, v = line.partition(":")
            out[k] = v.strip().strip('"')
    return out


def check_issue(md: Path, repo_root: Path = Path(".")) -> list[str]:
    """Reasons the staged issue must NOT be promoted (empty list = passes)."""
    problems: list[str] = []
    side = md.with_suffix(".tables.json")
    if not side.exists():
        return ["sidecar .tables.json missing"]
    text = md.read_text(encoding="utf-8")
    fm = _front(text)
    payload = json.loads(side.read_text(encoding="utf-8"))
    iso = md.stem.removeprefix("vv_")
    if fm.get("parser") != PARSER_NAME:
        problems.append(f"parser is {fm.get('parser')!r}, not {PARSER_NAME}")
    if fm.get("issue_date") != iso or payload.get("issue_date") != iso or fm.get("year") != iso[:4]:
        problems.append("issue date in front matter / sidecar does not match the file name")
    paths = [payload.get("source_file", "")]
    for ln in (_FM_RE.match(text).group(1).splitlines() if _FM_RE.match(text) else []):
        if re.match(r"\s*(?:-\s*)?(?:path|source_file):", ln):
            paths.append(ln.split(":", 1)[1].strip().strip('"'))
    if any(_is_absolute(x) for x in paths):
        problems.append("absolute or drive-letter path in front matter / sidecar (must be repo-relative)")
    n_unparsed = sum(len(s["unparsed"]) for s in payload["sectors"])
    if n_unparsed:
        problems.append(f"{n_unparsed} unparsed deal line(s)")
    if fm.get("deals_unparsed") not in (None, "", str(n_unparsed)):
        problems.append("front matter deals_unparsed disagrees with the sidecar")
    src = repo_root / payload.get("source_file", "")
    if not src.exists():
        problems.append(f"source HTML {payload.get('source_file')} not found")
    elif sha256_file(src) != payload.get("source_sha256"):
        problems.append("source HTML changed since the staged parse")
    status = (payload.get("matrix") or {}).get("status")
    if payload["matrix_status"] == "ok":
        m = payload["matrix"]
        if status != "ok" or not m.get("image_date"):
            problems.append("matrix marked ok but its image date label was not read")
        elif f"– {m['image_date']}" not in text.split("## VV Mini Matrix", 1)[-1].split("\n", 1)[0]:
            problems.append("ok matrix table has no date label in its heading")
    elif payload["matrix_status"] == "failed" and MATRIX_UNREADABLE not in text:
        problems.append("failed matrix without the 'not machine-readable' note")
    elif payload["matrix_status"] == "not_run":
        problems.append("matrix OCR was not run for this staged build")
    if re.search(r"\|\s*-0(?:\.0+)?%?\s*[|(]", text.split("## VV Mini Matrix", 1)[0]):
        problems.append("negative zero in a deal table")      # matrix cells print '-0.0%' verbatim from the image
    return problems


def plan(staging: Path = DEFAULT_OUT, live: Path = LIVE_MD, repo_root: Path = Path(".")) -> dict:
    promote, blocked = [], {}
    for md in sorted(staging.glob("*/vv_*.md")):
        problems = check_issue(md, repo_root)
        dest = live / md.parent.name / md.name
        if (not problems and dest.exists() and "| Age |" in dest.read_text(encoding="utf-8")
                and "| Age |" not in md.read_text(encoding="utf-8")):
            problems.append("live MD has matrix numbers but the staged matrix failed: not replaced")
        if problems:
            blocked[md.stem.removeprefix("vv_")] = problems
        else:
            dest = live / md.parent.name / md.name
            promote.append({"issue_date": md.stem.removeprefix("vv_"), "staged": md.as_posix(),
                            "live": dest.as_posix(), "replaces_existing": dest.exists()})
    return {"promote": promote, "blocked": blocked}


def apply(p: dict) -> int:
    n = 0
    for item in p["promote"]:
        src, dest = Path(item["staged"]), Path(item["live"])
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(src.read_bytes())
        dest.with_suffix(".tables.json").write_bytes(src.with_suffix(".tables.json").read_bytes())
        n += 1
    return n


def main_cli(staging: Path, live: Path, do_apply: bool, repo_root: Path = Path(".")) -> dict:
    p = plan(staging, live, repo_root)
    written = apply(p) if do_apply else 0
    return {"mode": "apply" if do_apply else "dry-run", "would_promote": len(p["promote"]),
            "replacing_existing": sum(1 for i in p["promote"] if i["replaces_existing"]),
            "blocked": len(p["blocked"]), "written": written, "blocked_detail": p["blocked"]}
