"""Poten: give the in-text chart placeholders the chart's printed title.

The Poten converter marks each chart where it sits in the article with a bare "*Chart*" line (sometimes followed by
"*Source: ...*"). poten_chart_captions.py later read every chart's printed title, unit, legend and source off the PDF
pages (LlamaParse, cached under .reparse_staging/poten_charts/) and captioned the exhibit images at the end of the
MD, but the in-text placeholders stayed bare: "*Chart*" / "*Chart*" / "*Source: Lloyd's List Intelligence; Poten*".

This pass writes "*Chart: <title as printed>*" into those placeholders. Charts are matched in reading order, and
only when the article's placeholders and the charts read from the PDF agree in number; where a placeholder carries a
source line, it must agree with the chart's printed source, otherwise the file is left as is. Placeholders that
already carry a title are never changed. Nothing is fetched: only the existing cache is read.

    python scripts/md_cleanup/poten_inline_chart_titles.py            # dry run, counts + skipped reasons
    python scripts/md_cleanup/poten_inline_chart_titles.py --apply
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.md_cleanup.poten_chart_captions import ROOT, cache_path, chart_blocks, pdf_of, sim  # noqa: E402

PLACEHOLDER = re.compile(r"^\*Chart(?:: ([^*\n]+))?\*[ \t]*$")
SOURCE = re.compile(r"^\*Source:\s*([^*\n]*)\*[ \t]*$")


def inline_charts(lines: list[str], stop: int) -> list[tuple[int, str | None, str | None]]:
    """(line index, existing title, source line text) for each in-text chart placeholder before `stop`."""
    out = []
    for i in range(stop):
        m = PLACEHOLDER.match(lines[i].strip())
        if not m:
            continue
        src = None
        for k in range(i + 1, min(i + 5, stop)):
            s = lines[k].strip()
            if PLACEHOLDER.match(s):
                break
            sm = SOURCE.match(s)
            if sm:
                src = sm.group(1).strip()
                break
        out.append((i, m.group(1), src))
    return out


def chart_slots(lines: list[str], inl) -> list[tuple[int, str | None, str | None, int | None]]:
    """One slot per chart. A placeholder followed by k consecutive "*Source:*" lines stands for k charts printed
    one under the other (the converter wrote one "*Chart*" for the column, then each chart's source line):
    (placeholder line, existing title, source text, line of that source or None)."""
    out = []
    for i, t, _ in inl:
        srcs, k = [], i + 1
        while k < len(lines) and k < i + 12:
            s = lines[k].strip()
            if not s:
                k += 1
                continue
            m = SOURCE.match(s)
            if not m:
                break
            srcs.append((k, m.group(1).strip()))
            k += 1
        if not srcs:
            out.append((i, t, None, None))
        for j, (k, s) in enumerate(srcs):
            out.append((i, t if j == 0 else None, s, k))
    return out


def main(argv: list[str]) -> int:
    apply = "--apply" in argv
    st: Counter = Counter()
    for path in sorted((ROOT / "data/extracted/md/poten").rglob("*.md")):
        raw = path.read_bytes().decode("utf-8")
        crlf = "\r\n" in raw
        md = raw.replace("\r\n", "\n")
        lines = md.split("\n")
        stop = next((i for i, l in enumerate(lines) if l.startswith("## Market Exhibits & Charts")), len(lines))
        inl = inline_charts(lines, stop)
        if not any(t is None for _, t, _ in inl):
            continue
        st["files with bare placeholders"] += 1
        pdf = pdf_of(md)
        if pdf is None:
            st["skip: no PDF"] += 1
            continue
        n = len(pymupdf.open(pdf))
        if not all(cache_path(pdf, p).exists() for p in range(1, n + 1)):
            st["skip: PDF pages not read"] += 1
            continue
        blocks = [dict(c, page=p) for p in range(1, n + 1)
                  for c in chart_blocks(json.loads(cache_path(pdf, p).read_text(encoding="utf-8"))["markdown"])]
        slots = chart_slots(lines, inl)
        groups = [[b] for b in blocks]
        if len(groups) != len(slots):
            # charts printed as one panel over a single shared source line: on the same page, every chart but the
            # last has no source of its own; the converter wrote one "*Chart*" + that source for the panel
            panels: list[list[dict]] = []
            for b in blocks:
                prev = panels[-1][-1] if panels else None
                if prev and prev["page"] == b["page"] and (not prev["SOURCE"] or sim(prev["SOURCE"], b["SOURCE"]) >= 0.9):
                    panels[-1].append(b)
                else:
                    panels.append([b])
            if len(panels) == len(slots):
                groups = panels
                st["files matched as shared-source panels"] += 1
        if len(groups) != len(slots):
            st[f"skip: {len(slots)} chart slots vs {len(blocks)} charts read"] += 1
            continue
        blocks = [dict(g[-1], panel=[x["CHART"].replace("*", "") for x in g if x["CHART"]]) for g in groups]
        if any(src and b["SOURCE"] and sim(src, b["SOURCE"]) < 0.6 for (_, _, src, _), b in zip(slots, blocks)):
            st["skip: a source line disagrees"] += 1
            continue
        if any(t and b["CHART"] and sim(t, b["CHART"]) < 0.5 and sim(t.split(":")[-1], b["CHART"]) < 0.5
               for (_, t, _, _), b in zip(slots, blocks)):
            st["skip: a printed title disagrees"] += 1
            continue
        changed, inserts, seen = 0, [], set()
        for (i, t, _, k), b in zip(slots, blocks):
            title = b["CHART"].replace("*", "") if b["CHART"] else ""
            if i not in seen:                      # the placeholder line: first chart of its column
                seen.add(i)
                if t is None and len(b["panel"]) > 1:   # a panel: every chart's title, then the shared source
                    lines[i] = "\n\n".join(f"*Chart: {x}*" for x in b["panel"])
                    changed += len(b["panel"])
                    st["panel charts titled"] += len(b["panel"])
                elif t is None and title:
                    lines[i] = f"*Chart: {title}*"
                    changed += 1
                elif t is None:
                    st["placeholders left bare (no printed title)"] += 1
            elif title:                            # a further chart of the column: its title above its source
                inserts.append((k, f"*Chart: {title}*"))
                changed += 1
                st["stacked charts titled"] += 1
        for k, line in sorted(inserts, reverse=True):
            lines[k:k] = [line, ""]
        if changed:
            st["files filled"] += 1
            st["placeholders filled"] += changed
            if apply:
                new = "\n".join(lines)
                path.write_bytes((new.replace("\n", "\r\n") if crlf else new).encode("utf-8"))
    for k, v in sorted(st.items(), key=lambda kv: -kv[1]):
        print(f"{v:6}  {k}")
    print("applied" if apply else "dry run")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
