"""Replace the eyeballed MMi iron ore chart tables with values computed from the PDFs' vector charts.

Touches only three sections of data/extracted/md/hellenic/iron_ore_pdf/**.md and the matching keys of
their .tables.json sidecars:

  ## Historical Iron Ore Index Comparisons (USD/DMT)
  ## Dry Bulk Freight Rates Historical Line Data (USD/MT)
  ## Total China Iron Ore Import Volumes (Million Tonnes)

A section whose chart reads cleanly (scripts/extract/publishers/mmi_vector_charts.py self-checks) gets the
vector table and the "Estimate" note. A section whose chart does not read cleanly loses the parser's
table, which was read by eye from the image, and gets a "Chart not transcribed" note instead (2026-10-12;
before that it kept the table under an "Approximate" note). Every other byte of each file is kept.

    python scripts/md_cleanup/iron_ore_vector_charts_patch.py            # dry run: report only
    python scripts/md_cleanup/iron_ore_vector_charts_patch.py --apply
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.extract.publishers.mmi_vector_charts import ESTIMATE_NOTES, apply_vector_charts  # noqa: E402

# A worktree holds only some PDFs; fall back to the main checkout that owns this worktree.
CORPUS_ROOTS = [ROOT] + ([ROOT.parents[2]] if ROOT.parent.name == "worktrees" else [])
SECTIONS = {
    "comparisons": ("## Historical Iron Ore Index Comparisons (USD/DMT)",
                    "| Date | IOSI62 (USD/DMT) | IOPi62 CFR Eq (USD/DMT) | IOSI65 (USD/DMT) | IOPi65 CFR Eq (USD/DMT) |\n| :--- | :--- | :--- | :--- | :--- |\n",
                    lambda r: f"| {r['chart_date']} | {n2(r['iosi62_usd_dmt'])} | {n2(r['iopi62_eq_usd_dmt'])} | {n2(r['iosi65_usd_dmt'])} | {n2(r['iopi65_eq_usd_dmt'])} |"),
    "freight": ("## Dry Bulk Freight Rates Historical Line Data (USD/MT)",
                "| Date | C5 W. Australia - Qingdao (USD/MT) | C3 Tubarao - Qingdao (USD/MT) |\n| :--- | :--- | :--- |\n",
                lambda r: f"| {r['chart_date']} | {n2(r['c5_waust_usd_t'])} | {n2(r['c3_tubarao_usd_t'])} |"),
    "imports": ("## Total China Iron Ore Import Volumes (Million Tonnes)",
                "| Month / Period | Import Volume (Million Tonnes) |\n| :--- | :--- |\n",
                lambda r: f"| {r['period']} | {n2(r['volume_mt'])} |"),
}
NOT_TRANSCRIBED = ("> **Chart not transcribed.** The report prints no numbers for this chart and its vector "
                   "geometry does not read cleanly; the table the parser estimated from the image was removed. "
                   "See the source PDF.")
SIDECAR_KEY = {"comparisons": "historical_index_comparisons", "freight": "historical_freight_rates",
               "imports": "historical_import_volumes"}


def n2(v):
    return "-" if v is None else f"{v:,.2f}"


def section_re(heading):
    return re.compile("(" + re.escape(heading) + r"[^\n]*\n)(> \*\*(?:Estimate|Approximate)\.\*\*[^\n]*\n\n)?((?:\|[^\n]*\n)+)")


def main():
    apply = "--apply" in sys.argv
    out = subprocess.run(["git", "-c", "core.quotepath=off", "ls-files", "-z", "data/extracted/md/hellenic/iron_ore_pdf"],
                         cwd=ROOT, capture_output=True, text=True, encoding="utf-8").stdout
    mds = sorted(f for f in out.split("\0") if f.endswith(".md") and (ROOT / f).exists())
    stat = Counter()
    for n, rel in enumerate(mds, 1):
        path = ROOT / rel
        raw = path.read_bytes().decode("utf-8")
        crlf = "\r\n" in raw
        md = raw.replace("\r\n", "\n")
        present = [k for k, (h, _, _) in SECTIONS.items() if h in md]
        if not present:
            stat["no chart sections"] += 1
            continue
        m = re.search(r'^source_file:\s*"?([^"\n]+\.pdf)', md, re.M)
        pdf = None
        for base in CORPUS_ROOTS if m else []:
            cands = [base / m.group(1)] + list((base / "corpus/02-hellenic/iron_ore/pdfs").glob(f"*/{Path(m.group(1)).name}"))
            pdf = next((c for c in cands if c.exists()), None)
            if pdf:
                break
        issue = re.search(r'^issue_date:\s*"?([\d-]+)', md, re.M)
        issue = issue.group(1) if issue else rel.split("/")[-1][:10]
        rows = {"comparisons": [], "freight": [], "imports": []}
        src = apply_vector_charts(pdf, issue, issue[:4], rows["comparisons"], rows["freight"], rows["imports"]) if pdf else {}
        new = md
        for key in present:
            heading, head, line = SECTIONS[key]
            rx = section_re(heading)
            hit = rx.search(new)
            if not hit:
                stat[f"{key}: unmatched layout"] += 1
                continue
            if src.get(key) == "vector":
                body = head + "\n".join(line(r)
                                        for r in rows[key]) + "\n"
                stat[f"{key}: vector"] += 1
            else:
                body = ""
                stat[f"{key}: eyeballed table -> not-transcribed note"] += 1
            note = ESTIMATE_NOTES["vector"] if src.get(key) == "vector" else NOT_TRANSCRIBED
            new = new[:hit.start()] + hit.group(1) + note + ("\n\n" + body if body else "\n") + new[hit.end():]
        if apply and new != md:
            path.write_bytes((new.replace("\n", "\r\n") if crlf else new).encode("utf-8"))
            side = path.with_name(path.name[:-3] + ".tables.json")
            if side.exists():
                sc = json.loads(side.read_text(encoding="utf-8"))
                for key in present:
                    if src.get(key) == "vector":
                        sc[SIDECAR_KEY[key]] = rows[key]
                sc["chart_value_source"] = {k: ("vector" if src.get(k) == "vector" else "visual") for k in present}
                side.write_text(json.dumps(sc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        if n % 50 == 0:
            print(n, dict(stat), flush=True)
    print("done", len(mds), dict(stat))


if __name__ == "__main__":
    main()
