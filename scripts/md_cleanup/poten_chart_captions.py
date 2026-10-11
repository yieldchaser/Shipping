"""Give every Poten exhibit its real caption: chart title, unit, x-axis span, legend series and data source.

The Poten runner (run_poten.py) captioned every chart with the ARTICLE title and a hardcoded "Source: Poten &
Partners"; the charts are raster images, so their titles, axes, legends and source lines never reached the MD.
Measured 2026-10-11: 1,501 exhibits in 859 MDs. Example - 25 Sep 2026 prints "Global Diesel Exports by Origin
Region" (Kb/d, Source: Vortexa); the MD said "Exhibit 1: Do We Need To Plan For A Diesel Export Ban".

Each PDF page is read once by LlamaParse (agentic tier, cached under .reparse_staging/poten_charts/) with a prompt that
copies, per chart: title, unit, first/last x label, legend names, source. Chart blocks are matched to the MD's
exhibit images in reading order, confirmed by OCR of the cropped image's title where it reads. Only the exhibit
caption lines change; article text is untouched. No chart VALUES are read.

    python scripts/md_cleanup/poten_chart_captions.py --plan          # count pages, no calls
    python scripts/md_cleanup/poten_chart_captions.py --parse -j 6    # fill the cache (LlamaParse credits)
    python scripts/md_cleanup/poten_chart_captions.py                 # dry run from cache
    python scripts/md_cleanup/poten_chart_captions.py --apply
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAIN = ROOT.parents[2] if ROOT.parent.name == "worktrees" else ROOT
sys.path.insert(0, str(ROOT))
CACHE = ROOT / ".reparse_staging" / "poten_charts"
PROMPT = ("For every chart or exhibit on the page output a block exactly like:\n"
          "CHART: <title as printed>\n"
          "UNIT: <y-axis unit as printed; add the right-axis unit after ' | ' if there is one>\n"
          "X: <first x-axis label> .. <last x-axis label>\n"
          "SERIES: <legend names as printed, separated by '; '>\n"
          "SOURCE: <text after 'Source:' printed under the chart>\n"
          "Leave a field empty if it is not printed. Copy text exactly. Do not estimate values.")
EXHIBIT_IMG = re.compile(r"^!\[Exhibit (\d+): [^\n]*?\]\(((?:[^()\s]|\([^()\s]*\))+)\)$", re.M)
FIELDS = ("CHART", "UNIT", "X", "SERIES", "SOURCE")


def git_files() -> list[str]:
    if "--untracked" in sys.argv:   # CI: only the issues this run just extracted
        out = subprocess.run(["git", "-c", "core.quotepath=off", "ls-files", "-z", "--others", "--exclude-standard",
                              "data/extracted/md/poten"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8").stdout
        return sorted(x for x in out.split("\0") if x.endswith(".md"))
    out = subprocess.run(["git", "-c", "core.quotepath=off", "grep", "-lz", "-E", r"^!\[Exhibit", "--", "data/extracted/md/poten/*.md"],
                         cwd=ROOT, capture_output=True, text=True, encoding="utf-8").stdout
    return sorted(x for x in out.split("\0") if x)


def pdf_of(md: str) -> Path | None:
    m = re.search(r'^source_file:\s*"?([^"\n]+\.pdf)', md, re.M)
    return next((b / m.group(1) for b in (ROOT, MAIN) if m and (b / m.group(1)).exists()), None)


def cache_path(pdf: Path, page: int) -> Path:
    return CACHE / f"{hashlib.sha1(pdf.read_bytes()).hexdigest()[:16]}_p{page}.json"


def parse_page(pdf: Path, page: int) -> str:
    cp = cache_path(pdf, page)
    if cp.exists():
        return json.loads(cp.read_text(encoding="utf-8"))["markdown"]
    from scripts.parse_engine.llama import LlamaParseClient
    r = LlamaParseClient().parse(pdf, "agentic", "latest", str(page), PROMPT, False)
    CACHE.mkdir(parents=True, exist_ok=True)
    cp.write_text(json.dumps({"pdf": pdf.name, "page": page, "markdown": r["markdown"], "job_id": r.get("job_id")},
                             ensure_ascii=False), encoding="utf-8")
    return r["markdown"]


def chart_blocks(markdown: str) -> list[dict]:
    out, cur = [], None
    for line in markdown.splitlines():
        m = re.match(r"^\s*\**(CHART|UNIT|X|SERIES|SOURCE)\**\s*:\s*(.*?)\s*$", line)
        if not m:
            continue
        k, v = m.group(1), m.group(2).strip().strip("*").strip()
        if k == "CHART":
            cur = {f: "" for f in FIELDS}
            out.append(cur)
        if cur is not None and not cur[k]:
            cur[k] = "" if v.lower() in ("null", "none", "n/a", "-") else v
    return [c for c in out if c["CHART"] or c["SERIES"]]


# The 2004-2008 cropper saved the Poten & Partners masthead logo as "Exhibit 1" in 245 MDs (three crop variants,
# difference-hash fingerprints below). It is not content: those exhibit entries are dropped (the PNG stays on disk).
LOGO_DHASHES = (0x48334d33c5000000e000c0017c1cc63cc364e934e31cc7017c00c000c00000,
                0x3b4b334d000000e120c1417d1cc634c334eb3cc31cc6407910c100800000,
                0x1785000000e000c000f0055c1cc734c364e934c93cc30c4e00f800c000c00000)


def is_logo(png: Path) -> bool:
    try:
        from PIL import Image
        px = list(Image.open(png).convert("L").resize((17, 16)).get_flattened_data())
    except Exception:
        return False
    h = sum(1 << i for i in range(256) if px[(i // 16) * 17 + i % 16] > px[(i // 16) * 17 + i % 16 + 1])
    return any(bin(h ^ ref).count("1") <= 20 for ref in LOGO_DHASHES)


def ocr_title(png: Path) -> str:
    try:
        import pytesseract
        from PIL import Image
        pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        im = Image.open(png).convert("L")
        top = im.crop((0, 0, im.width, int(im.height * 0.22)))
        return pytesseract.image_to_string(top, config="--psm 6")
    except Exception:
        return ""


def sim(a: str, b: str) -> float:
    a, b = re.sub(r"[^a-z0-9 ]", "", a.lower()), re.sub(r"[^a-z0-9 ]", "", b.lower())
    return SequenceMatcher(None, a, b).ratio() if a and b else 0.0


def caption(n: str, c: dict, img: str) -> list[str]:
    lines = [f"> **Exhibit {n}: {c['CHART'] or 'Untitled chart'}**  "]
    meta = []
    if c["UNIT"]:
        meta.append(f"Unit: {c['UNIT']}")
    if c["X"] and c["X"].strip(". "):
        meta.append(f"X-axis: {c['X'].replace(' .. ', ' to ')}")
    if meta:
        lines.append("> " + " · ".join(meta) + "  ")
    if c["SERIES"]:
        lines.append("> Series: " + ", ".join(s.strip() for s in c["SERIES"].split(";") if s.strip()) + "  ")
    if c["SOURCE"]:
        lines.append(f"> *Source: {c['SOURCE']}*  ")
    lines.append(f"> [Chart image (200 DPI PNG)]({img})")
    return lines


def main() -> int:
    plan, do_parse, apply = "--plan" in sys.argv, "--parse" in sys.argv, "--apply" in sys.argv
    jobs = int(sys.argv[sys.argv.index("-j") + 1]) if "-j" in sys.argv else 4
    import pymupdf
    work, stat = [], Counter()
    for rel in git_files():
        md = (ROOT / rel).read_bytes().decode("utf-8")
        pdf = pdf_of(md)
        if pdf is None:
            stat["no pdf"] += 1
            continue
        work.append((rel, pdf, len(pymupdf.open(pdf))))
    if "--limit" in sys.argv:                       # pilot: an even spread across the years
        k = int(sys.argv[sys.argv.index("--limit") + 1])
        work = work[:: max(1, len(work) // k)][:k]
    if plan or do_parse:
        todo = [(pdf, p) for _, pdf, n in work for p in range(1, n + 1) if not cache_path(pdf, p).exists()]
        print(f"{len(work)} MDs, {sum(n for *_, n in work)} pages, {len(todo)} not cached (~{10 * len(todo)} LlamaParse credits)")
        if do_parse:
            done = 0
            with ThreadPoolExecutor(jobs) as ex:
                futs = {ex.submit(parse_page, pdf, p): (pdf, p) for pdf, p in todo}
                for f in as_completed(futs):
                    done += 1
                    try:
                        f.result()
                    except Exception as e:  # noqa: BLE001
                        print("FAIL", futs[f][0].name, futs[f][1], str(e)[:160], flush=True)
                        if "exhausted" in str(e).lower():
                            ex.shutdown(cancel_futures=True)
                            break
                    if done % 50 == 0:
                        print(done, "/", len(todo), flush=True)
        return 0
    report = []
    for rel, pdf, n in work:
        if not all(cache_path(pdf, p).exists() for p in range(1, n + 1)):
            stat["not parsed yet"] += 1
            continue
        blocks = [dict(c, page=p) for p in range(1, n + 1)
                  for c in chart_blocks(json.loads(cache_path(pdf, p).read_text(encoding="utf-8"))["markdown"])]
        path = ROOT / rel
        raw = path.read_bytes().decode("utf-8")
        crlf = "\r\n" in raw
        md = raw.replace("\r\n", "\n")

        def png_of(target: str) -> Path:
            p = (path.parent / target).resolve()
            if not p.exists() and ROOT.resolve() in p.parents:
                p = MAIN / p.relative_to(ROOT.resolve())
            return p

        cleaned = md
        for m in reversed(list(EXHIBIT_IMG.finditer(md))):
            if not is_logo(png_of(m.group(2))):
                continue
            start, end = m.start(), m.end()
            a = re.match(r"\n\n> \*\*Interactive Asset:\*\*[^\n]*\n", cleaned[end:])
            if a:
                end += a.end() - 1
            b = re.search(r"> \*\*Exhibit \d+: [^\n]*\*\*  \n> \*Source: [^\n]*\*  \n> \*\*Interactive Data & Source:\*\*[^\n]*\n\n\Z", cleaned[:start])
            if b:
                start = b.start()
            cleaned = cleaned[:start] + cleaned[end:].lstrip("\n")
            stat["logo 'exhibits' dropped"] += 1
        md_before_logo, md = md, cleaned
        exhibits = list(EXHIBIT_IMG.finditer(md))
        if not blocks:
            stat["no chart blocks read"] += 1
            report.append((rel, "no chart blocks"))
            if md != md_before_logo and apply:
                path.write_bytes((md.replace("\n", "\r\n") if crlf else md).encode("utf-8"))
            continue
        # match exhibit -> block: OCR title when it reads, else reading order (only when counts agree)
        assign, used = {}, set()
        for i, m in enumerate(exhibits):
            png = (path.parent / m.group(2))
            png = png if png.exists() else MAIN / png.resolve().relative_to(ROOT.resolve()) if ROOT.resolve() in png.resolve().parents else png
            t = ocr_title(png) if png.exists() else ""
            scores = sorted(((sim(t[:200], b["CHART"]), j) for j, b in enumerate(blocks) if j not in used and b["CHART"]), reverse=True)
            if scores and scores[0][0] >= 0.55:
                assign[i] = scores[0][1]
                used.add(scores[0][1])
                stat["matched by OCR title"] += 1
        if len(blocks) == len(exhibits):
            free = [j for j in range(len(blocks)) if j not in used]
            for i in range(len(exhibits)):
                if i not in assign and free:
                    j = i if i not in used and i in free else free[0]
                    assign[i] = j
                    used.add(j)
                    free.remove(j)
                    stat["matched by order"] += 1
        unmatched = len(exhibits) - len(assign)
        if unmatched:
            stat["exhibits left unmatched"] += unmatched
            report.append((rel, f"{len(exhibits)} exhibits vs {len(blocks)} charts read; {unmatched} left as is"))
        new = md
        for i, m in sorted(((i, m) for i, m in enumerate(exhibits) if i in assign), key=lambda t: -t[1].start()):
            c, num, img = blocks[assign[i]], m.group(1), m.group(2)
            title = c["CHART"] or "Untitled chart"
            img_line = f"![Exhibit {num}: {title}]({img})"
            # caption block that follows the image (end-of-doc layout) ...
            after = re.compile(r"\A\n\n> \*\*Interactive Asset:\*\* \[Local Asset \(200 DPI PNG\)\]\(([^)\n]*)\)\n")
            tail = new[m.end():]
            a = after.match(tail)
            # ... or the inline layout's caption block that precedes it
            before = re.compile(r"> \*\*Exhibit \d+: [^\n]*\*\*  \n> \*Source: [^\n]*\*  \n> \*\*Interactive Data & Source:\*\* \[Local Asset \(200 DPI PNG\)\]\(([^)\n]*)\)\n\n\Z")
            head = new[:m.start()]
            b = before.search(head)
            cap = "\n".join(caption(num, c, img))
            ours = r"> \*\*Exhibit \d+: [^\n]*\n(?:> [^\n]*\n)*?> \[Chart image \(200 DPI PNG\)\]\([^)\n]*\)"
            a2, b2 = re.match(r"\A\n\n" + ours + r"\n", tail), re.search(ours + r"\n\n\Z", head)
            if a2:                                   # captioned by an earlier run: refresh in place
                new = head + img_line + "\n\n" + cap + "\n" + tail[a2.end():]
            elif b2:
                new = head[:b2.start()] + cap + "\n\n" + img_line + tail
            elif a:
                new = head + img_line + "\n\n" + cap + "\n" + tail[a.end():]
            elif b:
                new = head[:b.start()] + cap + "\n\n" + img_line + tail
            else:
                new = head + img_line + "\n\n" + cap + tail
            stat["exhibits captioned"] += 1
        # only when every crop is accounted for; otherwise an unmatched crop may be one of these charts
        extra = [b for j, b in enumerate(blocks) if j not in used and (b["CHART"] or b["SERIES"])] if len(blocks) > len(exhibits) and not unmatched else []
        extra = [b for b in extra if f"Chart on PDF page {b['page']}: {b['CHART'] or 'Untitled chart'}**" not in new]
        if extra:   # printed in the PDF but never cropped into an exhibit image: keep what the PDF says about them
            lines = []
            for b in extra:
                cap = caption("", b, "")[:-1]
                cap[0] = f"> **Chart on PDF page {b['page']}: {b['CHART'] or 'Untitled chart'}**  "
                lines.append("\n".join(cap + ["> *No image crop of this chart was saved; caption read from the PDF.*"]))
            sep = "" if "## Market Exhibits & Charts" in new else "## Market Exhibits & Charts\n\n"
            new = new.rstrip("\n") + "\n\n" + sep + "\n\n".join(lines) + "\n"
            stat["uncropped charts added as captions"] += len(extra)
        if new != md_before_logo:
            stat["files changed"] += 1
            if apply:
                path.write_bytes((new.replace("\n", "\r\n") if crlf else new).encode("utf-8"))
    (ROOT / ".reparse_staging" / "poten_chart_captions_report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    for k, v in sorted(stat.items()):
        print(f"{v:6}  {k}")
    print("APPLIED" if apply else "dry run (use --apply)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
