"""Cross-issue check of the Best Oasis charts whose series were assigned by legend order only.

Picture charts (2021 template) have no bar colours, so "previous / this week" rests on the order of the legend. The
check uses the weekly chain: this week of issue N is the previous week of issue N+1. A legend-order table is kept only
when, against the adjacent issues, at least two cells are confirmed in the stated orientation (and more than half of
the comparable cells when more than two are comparable) and no cell is confirmed only in the swapped orientation.
Anything else (no adjacent issue, too little confirmed, or a contradiction) becomes a `> Figure:` note with the labels
as printed; a contradiction is also a validation flag.

Strict equality of every cell is deliberately not required: on the colour-resolved charts (ground truth) only about 58%
of cells chain exactly, because the publisher revises or re-uses charts (see the stale Pakistan HMS chart of
2021-07-17 / 2021-07-24).

Each chart block in the staged MD starts with a marker line `<!-- bo-chart p<page>c<index> -->` that the parser writes.
Decisions are applied by that unique id, never by heading text (HMS headings repeat once per country); exactly one
replacement per demoted table is required, otherwise the run fails. All markers are removed at the end and every
issue's validation.json gets `continuity_ran: true`; `promote` refuses best_oasis issues without it.

Run after `python -m scripts.parse_engine run --source best_oasis` and before `promote`:

    python -m scripts.parse_engine.best_oasis_continuity [staging_dir]
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

from scripts.parse_engine.config import REPO_ROOT

SOURCE = "best_oasis"
MARKER_RE = re.compile(r"^<!-- bo-chart (p\d+c\d+) -->\n?", re.M)


class ContinuityError(RuntimeError):
    pass


def chart_key(table: dict[str, Any]) -> tuple[str, str]:
    title = re.sub(r"[^a-z0-9]+", " ", table["title"].lower()).strip()
    country = re.sub(r"t.rkiye|turkiye", "turkey", table.get("country") or "")
    if "hms" in title:
        return "hms", country or f"p{table['page']}"
    if "bunker" in title:
        return "bunker", ""
    return "ships", country or title


def _cells(t: dict[str, Any], o: dict[str, Any], t_is_earlier: bool) -> tuple[int, int, int]:
    """(cells confirmed in the stated orientation only, cells confirmed in the swapped orientation only, comparable cells)."""
    fw = sw = n = 0
    other = {r[0]: r for r in o["rows"]}
    for r in t["rows"]:
        q = other.get(r[0])
        if not q or not (r[1] and r[2] and q[1] and q[2]):
            continue
        if r[1:3] == q[1:3]:
            continue                                        # the same chart printed twice (stale): says nothing either way
        a, b = (r, q) if t_is_earlier else (q, r)          # a = earlier issue, b = later issue
        chained, swapped = a[2] == b[1], a[1] == b[2]
        n += 1
        fw += chained and not swapped
        sw += swapped and not chained
    return fw, sw, n


def verdict(table: dict[str, Any], earlier: dict[str, Any] | None, later: dict[str, Any] | None) -> tuple[bool, str, bool]:
    """(keep, reason, contradiction)."""
    fw = sw = n = 0
    for other, t_is_earlier in ((later, True), (earlier, False)):
        if other is not None:
            f, s, c = _cells(table, other, t_is_earlier)
            fw, sw, n = fw + f, sw + s, n + c
    if earlier is None and later is None:
        return False, "no adjacent issue with this chart to check the week-to-week continuity", False
    if sw:
        return False, "the week-to-week continuity contradicts the legend-order assignment", True
    if fw < 2 or (n > 2 and fw * 2 <= n):
        return False, f"only {fw} of {n} comparable cells are confirmed by the adjacent issues", False
    return True, "", False


def _figure_note(table: dict[str, Any], reason: str) -> str:
    printed = f" Labels as printed, left to right: {table['printed']}." if table.get("printed") else ""
    return (f"> Figure: {table['title']} - the series cannot be assigned to previous and this week ({reason}); "
            f"no table written.{printed}")


def replace_chart_table(md: str, chart_id: str, note: str) -> str:
    """Replace the pipe table of the chart block marked `chart_id` by `note`. The marker must occur exactly once and the
    block must hold exactly one table, otherwise ContinuityError."""
    marker = f"<!-- bo-chart {chart_id} -->"
    if md.count(marker) != 1:
        raise ContinuityError(f"{chart_id}: marker found {md.count(marker)} times, expected exactly once")
    lines = md.split("\n")
    i = lines.index(marker)
    j = i + 1
    while j < len(lines) and j <= i + 6 and not lines[j].lstrip().startswith("|"):
        if lines[j].startswith("<!-- bo-chart"):
            raise ContinuityError(f"{chart_id}: no table in the chart block")
        j += 1
    if j >= len(lines) or not lines[j].lstrip().startswith("|"):
        raise ContinuityError(f"{chart_id}: no table in the chart block")
    k = j
    while k < len(lines) and lines[k].lstrip().startswith("|"):
        k += 1
    return "\n".join(lines[:j] + [note] + lines[k:])


def strip_markers(md: str) -> str:
    return MARKER_RE.sub("", md)


def run(staging: Path) -> dict[str, int]:
    issues: dict[str, dict[str, Any]] = {}
    for tj in sorted((staging / SOURCE).glob("*/*.tables.json")):
        data = json.loads(tj.read_text(encoding="utf-8"))
        if not data.get("issue_date"):
            continue
        charts = {chart_key(t): t for t in data["tables"] if t.get("row_source") == "best_oasis_chart"}
        issues[data["issue_date"]] = {"path": tj, "data": data, "charts": charts}
    dates = sorted(issues)
    counts = {"legend_order_tables": 0, "kept": 0, "figure_note": 0, "flagged": 0, "issues": 0}
    for idx, d in enumerate(dates):
        earlier = next((issues[p] for p in reversed(dates[:idx]) if 4 <= (date.fromisoformat(d) - date.fromisoformat(p)).days <= 10), None)
        later = next((issues[n] for n in dates[idx + 1:] if 4 <= (date.fromisoformat(n) - date.fromisoformat(d)).days <= 10), None)
        cur = issues[d]
        md_path = cur["path"].with_name(cur["path"].name[: -len(".tables.json")] + ".md")
        val_path = md_path.with_suffix(".validation.json")
        md = md_path.read_text(encoding="utf-8")
        val = json.loads(val_path.read_text(encoding="utf-8"))
        demoted = []
        for key, t in list(cur["charts"].items()):
            if t.get("series_basis") != "legend_order":
                continue
            counts["legend_order_tables"] += 1
            keep, reason, contradiction = verdict(t, earlier["charts"].get(key) if earlier else None,
                                                  later["charts"].get(key) if later else None)
            if keep:
                counts["kept"] += 1
                continue
            before = md
            md = replace_chart_table(md, t["chart_id"], _figure_note(t, reason))
            if md == before:
                raise ContinuityError(f"{d} {t['chart_id']}: replacement changed nothing")
            demoted.append(t)
            tag = f"{t['chart_id']}:{t['title'][:40]}:{reason[:70]}"
            if contradiction:
                counts["flagged"] += 1
                val.setdefault("flags", []).append(f"best_oasis:chart_not_extracted_continuity_{tag}")
                val["passed"] = False
            else:
                counts["figure_note"] += 1
            val.setdefault("notes", []).append(f"best_oasis:figure_note_continuity_{tag}")
        md = strip_markers(md)
        if "bo-chart" in md:
            raise ContinuityError(f"{d}: chart markers left in the MD")
        if demoted:
            cur["data"]["tables"] = [x for x in cur["data"]["tables"] if not any(x is t for t in demoted)]
            cur["path"].write_text(json.dumps(cur["data"], indent=2, ensure_ascii=False), encoding="utf-8")
        md_path.write_text(md, encoding="utf-8")
        val["continuity_ran"] = True
        val_path.write_text(json.dumps(val, indent=2, ensure_ascii=False), encoding="utf-8")
        counts["issues"] += 1
    # an issue without a tables.json (no tables at all) still needs its marker cleanup and the continuity flag
    for vp in sorted((staging / SOURCE).glob("*/*.validation.json")):
        val = json.loads(vp.read_text(encoding="utf-8"))
        if val.get("continuity_ran"):
            continue
        mdp = vp.with_name(vp.name[: -len(".validation.json")] + ".md")
        if mdp.exists():
            mdp.write_text(strip_markers(mdp.read_text(encoding="utf-8")), encoding="utf-8")
        val["continuity_ran"] = True
        vp.write_text(json.dumps(val, indent=2, ensure_ascii=False), encoding="utf-8")
        counts["issues"] += 1
    return counts


if __name__ == "__main__":
    staging = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO_ROOT / ".reparse_staging"
    print(run(staging))
