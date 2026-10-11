"""Rebuild the Seabrokers "DAILY NORTH SEA OSV AVAILABILITY" tables from the chart's vector geometry.

The chart prints no numbers: its four lines (PSV / AHTS, this year and last year) are vector paths with one node per
day, and the y-axis labels are in the PDF text layer. The original parse read the lines by eye (half-step guesses
such as 23.5 / 27.5, and a run of arrays for 2023-09). Each node is mapped to a value with a linear fit of the axis
labels and to a day with the x-axis labels; the series name comes from the legend marker of the same colour.
The table is replaced only when all four series read cleanly (one node per day label, axis fit exact to 0.05),
and it is labelled as read from the chart. Only that section's table/array lines change.

    python scripts/md_cleanup/seabrokers_availability_vector.py [--apply] [--untracked]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import intermodal_table_rebuild as R  # noqa: E402  (source_pdf lookup)

MD_ROOT = ROOT / "data" / "extracted" / "md" / "seabrokers"
HEAD = re.compile(r"^#{1,4} .*DAILY NORTH SEA OSV AVAILABILITY", re.I)
NOTE = ("> **Read from the chart.** The report prints no numbers for this chart; each value is the chart line's node "
        "for that day, converted with the printed axis labels (vector geometry, not an eyeball estimate).")


def fit(pairs):
    n = len(pairs)
    mx = sum(p[0] for p in pairs) / n
    my = sum(p[1] for p in pairs) / n
    sxx = sum((p[0] - mx) ** 2 for p in pairs)
    a = sum((p[0] - mx) * (p[1] - my) for p in pairs) / sxx
    b = my - a * mx
    err = max(abs(a * p[0] + b - p[1]) for p in pairs)
    return a, b, err


def end_point(item):
    return item[-1] if item[0] == "c" else item[2] if item[0] == "l" else None


def read_chart(page) -> tuple[list[str], list[list[str]]] | str:
    """The first title on the page with a chart under it (a contents list repeats the title)."""
    why = "chart title not on page"
    for title in page.search_for("DAILY NORTH SEA OSV AVAILABILITY"):
        got = read_chart_at(page, title)
        if not isinstance(got, str):
            return got
        why = got
    return why


def read_chart_at(page, title) -> tuple[list[str], list[list[str]]] | str:
    words = page.get_text("words")
    series = [d for d in page.get_drawings() if d.get("color") and len(d["items"]) >= 20 and (d.get("width") or 0) >= 1
              and d["rect"].y0 > title.y1 - 2 and d["rect"].y1 < title.y1 + 320 and max(d["color"]) - min(d["color"]) > 0.3]
    if len(series) != 4:
        return f"{len(series)} chart lines, expected 4"
    plot = series[0]["rect"]
    for s in series[1:]:
        plot |= s["rect"]
    # y axis: numbers left of the plot inside its vertical band; x axis: numbers just below it
    ylab = [(float(w[4]), (w[1] + w[3]) / 2) for w in words
            if re.fullmatch(r"\d+(\.\d+)?", w[4]) and w[2] < plot.x0 - 1 and plot.x0 - 40 < w[0]
            and title.y1 < (w[1] + w[3]) / 2 < title.y1 + 320]
    bottom = max((y for _, y in ylab), default=plot.y1)          # the axis, not the lowest data point
    xlab = [(int(w[4]), (w[0] + w[2]) / 2) for w in words
            if re.fullmatch(r"\d{1,2}", w[4]) and bottom - 2 < w[1] < bottom + 25 and w[0] > plot.x0 - 15]
    if len(ylab) < 3 or len(xlab) < 20:
        return "axis labels not found"
    # a label's text centre sits a little off its gridline: use the gridline it labels
    grid = []
    for d in page.get_drawings():
        for it in d["items"]:
            if it[0] == "l" and abs(it[1].y - it[2].y) < 0.3 and abs(it[2].x - it[1].x) > 0.5 * plot.width:
                grid.append(it[1].y)
    if len(grid) >= 3:
        snapped = []
        for v, y in ylab:
            g = min(grid, key=lambda gy: abs(gy - y))
            snapped.append((v, g if abs(g - y) < 4 else y))
        ylab = snapped
    ay, by, err = fit([(y, v) for v, y in ylab])
    if err > 0.05:
        return f"y axis labels not linear (err {err:.2f})"
    days = sorted(xlab)
    # legend: a short line of the series colour, label = the words right of it on the same line
    legend = {}
    for d in page.get_drawings():
        c = d.get("color")
        if not c or len(d["items"]) > 2 or d["rect"].width < 5 or d["rect"].height > 2 or not (title.y0 - 30 < d["rect"].y0 < plot.y0 + 5):
            continue
        r = d["rect"]
        lab = sorted((w for w in words if abs((w[1] + w[3]) / 2 - r.y0) < 5 and r.x1 - 1 < w[0] < r.x1 + 60), key=lambda w: w[0])
        text = " ".join(w[4] for w in lab[:2])
        if text:
            legend[tuple(round(x, 2) for x in c)] = text
    header, cols = ["Date"], []
    for s in series:
        key = tuple(round(x, 2) for x in s["color"])
        if key not in legend:
            return f"no legend for colour {key}"
        pts = [s["items"][0][1]] + [end_point(it) for it in s["items"]]
        vals = {}
        for p in pts:
            day, x = min(days, key=lambda dx: abs(dx[1] - p.x))
            if abs(x - p.x) > 3 or day in vals:
                return f"{legend[key]}: node off the day grid at x={p.x:.1f}"
            vals[day] = ay * p.y + by
        header.append(legend[key])
        cols.append(vals)
    order = sorted(range(4), key=lambda i: (not header[i + 1].startswith("PSV"), -int(re.sub(r"\D", "", header[i + 1]) or 0)))
    header = ["Date"] + [header[i + 1] for i in order]
    cols = [cols[i] for i in order]
    rows = []
    for day, _ in days:
        cells = [str(day)]
        for c in cols:
            v = c.get(day)
            cells.append("" if v is None else (f"{round(v) + 0:.0f}" if abs(v - round(v)) < 0.05 else f"{v + 0:.1f}"))   # + 0: no "-0"
        rows.append(cells)
    return header, rows


def update_sidecar(md: Path, header: list[str], rows: list[list[str]]) -> None:
    """The issue's .tables.json carries the same table: give it the chart values (other tables untouched)."""
    import json
    side = md.with_suffix(".tables.json")
    if not side.exists():
        return
    raw = side.read_bytes().decode("utf-8")
    j = json.loads(raw)
    hit = False
    for t in j.get("tables", []):
        if "DAILY NORTH SEA OSV AVAILABILITY" in str(t.get("title", "")).upper():
            t["columns"] = header
            t["rows"] = [dict(zip(header, r)) for r in rows]
            t["row_count"] = len(rows)
            t["value_source"] = "vector_chart_read"
            hit = True
    if not hit:
        return
    out = json.dumps(j, ensure_ascii=True, indent=2)
    if "\r\n" in raw:
        out = out.replace("\n", "\r\n")
    if raw.endswith(("\n", "\r\n")):
        out += "\r\n" if raw.endswith("\r\n") else "\n"
    side.write_bytes(out.encode("utf-8"))


def main() -> int:
    apply = "--apply" in sys.argv
    mds = sorted(MD_ROOT.rglob("*.md"))
    if "--untracked" in sys.argv:
        import subprocess
        out = subprocess.run(["git", "-c", "core.quotepath=off", "ls-files", "--others", "--exclude-standard", "-z", "--",
                              MD_ROOT.relative_to(ROOT).as_posix()], cwd=ROOT, capture_output=True, text=True,
                             encoding="utf-8").stdout
        mds = sorted(ROOT / p for p in out.split("\0") if p.endswith(".md"))
    done = left = 0
    for md in mds:
        raw = md.read_bytes().decode("utf-8")
        lines = raw.splitlines(keepends=True)
        def holds_data(i):
            nxt = next((l for l in lines[i + 1:] if l.strip() and not re.match(r"^(Legend:|- (PSV|AHTS) \d{4}\s*$)", l)), "")
            return nxt.startswith("|") or nxt.startswith("> **Read from") or bool(re.match(r"^(PSV|AHTS)[^:]{0,12}:", nxt))
        idx = next((i for i, l in enumerate(lines) if HEAD.match(l) and holds_data(i)), None)
        if idx is None:
            continue
        pdf = R.source_pdf(raw)
        if pdf is None:                     # no source_file: the one PDF of that issue date, if there is exactly one
            date = re.search(r'^issue_date:\s*"?(\d{4}-\d{2}-\d{2})', raw, re.M)
            hits = [b / "corpus" / "05-seabrokers" / "pdfs" for b in R.CORPUS_BASES]
            hits = sorted({p.name: p for d in hits if d.is_dir() for p in d.glob(f"{date.group(1)}*.pdf")}.values()) if date else []
            pdf = hits[0] if len(hits) == 1 else None
        page = None
        if pdf:
            for p in pymupdf.open(pdf):
                if "DAILY NORTH SEA OSV AVAILABILITY" in p.get_text().upper():
                    page = p
                    break
        got = read_chart(page) if page is not None else "chart page not found"
        if isinstance(got, str):
            left += 1
            print(f"left  {md.name}: {got}")
            continue
        header, rows = got
        # the old body: blank lines, table lines, "PSV 2023: ..." arrays and an earlier note, up to the next heading/prose
        j = idx + 1
        while j < len(lines) and (not lines[j].strip() or lines[j].startswith("|") or lines[j].startswith("> **Read from")
                                  or re.match(r"^(Legend:|- (PSV|AHTS) \d{4}\s*$)", lines[j])
                                  or re.match(r"^(PSV|AHTS)[^:]{0,12}:\s*[\d.]", lines[j])):
            j += 1
        nl = "\r\n" if lines[idx].endswith("\r\n") else "\n"
        new = [nl, NOTE + nl, nl, "| " + " | ".join(header) + " |" + nl,
               "| " + " | ".join("---" for _ in header) + " |" + nl]
        new += ["| " + " | ".join(r) + " |" + nl for r in rows] + [nl]
        lines[idx + 1:j] = new
        done += 1
        print(f"ok    {md.relative_to(ROOT).as_posix()}  {header[1:]}")
        if apply:
            # run_seabrokers_llamaparse.py writes the same MD to corpus/05-seabrokers: keep that copy identical
            mirror = ROOT / "corpus" / "05-seabrokers" / md.parent.name / md.name
            same = mirror.exists() and mirror.read_bytes() == md.read_bytes()
            md.write_bytes("".join(lines).encode("utf-8"))
            if same:
                mirror.write_bytes(md.read_bytes())
            update_sidecar(md, header, rows)
    print(f"{done} charts read, {left} left as is {'(applied)' if apply else '(dry run)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
