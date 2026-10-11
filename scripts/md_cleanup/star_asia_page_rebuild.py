"""Rebuild Star Asia MD pages the original parse left empty, garbled or without their tables.

Star Asia prints most tables as images (S&P reports, Baltic indices, T/C averages, values), and the original pass
dropped them, crammed them into a line of text, or lost whole pages. The parsing notes say Star Asia is useful end to
end, so every page counts. A page is a candidate when, in its "## Page N" section,
  * printed   - numbers of the PDF text layer appear nowhere in the MD (page header/contact numbers excluded),
  * empty     - the page section is near-empty while the PDF page has text,
  * no_table  - a table heading ("Tankers S&P Report", "... Indices", "... Values") has nothing under it,
  * garbled   - a non-table line carries a run of numbers with little prose (a table flattened into text).

Each candidate page is read with LlamaParse agentic (cache .reparse_staging/star_asia_pages/). The new page replaces
the old page section ONLY when
  * every number of the new page is printed on the PDF page: text layer, or an OCR read of the rendered page
    (RapidOCR) for the image tables; a table with any other number (a chart read as a table) is dropped first;
  * every number of the old section that is printed on the page is still there;
  * at least 98% of the old section's words are still there (prose is not lost);
  * the new page holds more printed numbers or more words than the old one.
Otherwise the page is left as it is and reported. Only page sections change (line endings kept).

    python scripts/md_cleanup/star_asia_page_rebuild.py                # plan (no API calls)
    python scripts/md_cleanup/star_asia_page_rebuild.py --parse -j 3   # read the pages (10 credits/page)
    python scripts/md_cleanup/star_asia_page_rebuild.py --apply        # rebuild from the cache
    python scripts/md_cleanup/star_asia_page_rebuild.py --untracked --parse --apply   # CI: new issues only
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import intermodal_table_rebuild as R  # noqa: E402  (shared: html_tables, number normalisation, pdf lookup)

MD_ROOT = ROOT / "data" / "extracted" / "md" / "star_asia"
CACHE = ROOT / ".reparse_staging" / "star_asia_pages"
OCR_CACHE = ROOT / ".reparse_staging" / "star_asia_ocr"
REPORT = ROOT / ".reparse_staging" / "star_asia_page_rebuild_report.json"
PROMPT = ("This is a shipbroker weekly market report page. Reproduce every table exactly as a table with one cell per "
          "column, keeping every header level and the table title. Copy numbers and names exactly as printed. Keep "
          "commentary verbatim. Do not describe charts, do not turn charts into tables, do not estimate values.")
PAGE = re.compile(r"^## Page (\d+)\s*$")
NOISE = {"65", "6227", "7264", "62277264", "62277258", "7258"}           # Singapore office phone numbers
FOOTER = re.compile(r"(?i)star-asia\.com\.sg|starasiasg\.com|member of bimco|^star asia \| weekly market report|"
                    r"^page \d+$|^star asia shipbroking pte ltd|^star asia$|"
                    r"^week \d+ \| [a-z]+ \d+(?:st|nd|rd|th)?,? \d{4}$")   # running page header
TABLE_HEAD = re.compile(r"(?i)S&P|indices|values|prices|t/c rates")


def nums(text: str) -> set[str]:
    text = re.sub(r"(?<=[\d%])(?:[-–—]|\s*[–—~]\s*)(?=[$\d])", " ", text)      # "$420-430", "Apr-17": ranges, not minus
    text = re.sub(r"(?<=[A-Za-z])-(?=\d)", " ", text)
    return {n for n in (R.norm_num(t) for t in R.NUM.findall(text)) if n.replace(".0", "") not in NOISE
            and len(re.sub(r"\D", "", n.replace(".0", ""))) >= 2}


def squash(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def words(text: str) -> Counter:
    return Counter(w.lower() for w in re.findall(r"[A-Za-z][A-Za-z'&.-]*[A-Za-z]|[A-Za-z]", text))


def split_pages(lines: list[str]) -> dict[int, tuple[int, int]]:
    """page number -> (first body line, end line) of its "## Page N" section."""
    marks = [(i, int(m.group(1))) for i, l in enumerate(lines) if (m := PAGE.match(l.rstrip("\r\n")))]
    out = {}
    for k, (i, p) in enumerate(marks):
        end = marks[k + 1][0] if k + 1 < len(marks) else len(lines)
        out.setdefault(p, (i + 1, end))
    return out


def is_table(l: str) -> bool:
    return l.lstrip().startswith("|")


def candidate(sec: str, page_text: str, md_nums: set[str]) -> list[str]:
    why = []
    printed = nums(page_text)
    if len(printed - md_nums) >= 3:
        why.append("printed")
    body = "\n".join(l for l in sec.splitlines() if l.strip())
    pt = "\n".join(l for l in page_text.splitlines() if l.strip() and not FOOTER.search(l.strip()))
    if len(pt) > 300 and len(body) < 0.3 * len(pt):
        why.append("empty")
    ls = [l.strip() for l in sec.splitlines() if l.strip()]
    for i, l in enumerate(ls):
        if l.startswith("#") and TABLE_HEAD.search(l) and (i + 1 == len(ls) or
                                                           (ls[i + 1].startswith("#") and not ls[i + 1].startswith("####"))):
            why.append("no_table")
            break
    for l in ls:
        if not is_table(l) and not l.startswith("#") and len(R.NUM.findall(l)) >= 4 and \
                len(re.findall(r"\b[a-z]{3,}\b", l)) < 6:
            why.append("garbled")
            break
    return why


def cache_path(pdf: Path, page: int) -> Path:
    return CACHE / f"{hashlib.sha1(pdf.read_bytes()).hexdigest()[:16]}_p{page}.json"


NACE_CACHE = ROOT / ".reparse_staging" / "star_asia_pages_nace"


def nace_cache_path(pdf: Path, page: int) -> Path:
    return NACE_CACHE / f"{hashlib.sha1(pdf.read_bytes()).hexdigest()[:16]}_p{page}.json"


def nace_parse_page(pdf: Path, page: int) -> str:
    """Nace NDI Parse (mode high: page verification) of one page; keys from ~/.nace/keys.env, rotated on 402."""
    cp = nace_cache_path(pdf, page)
    if cp.exists():
        return json.loads(cp.read_text(encoding="utf-8"))["markdown"]
    import time
    from nace_sdk import NaceClient
    sys.path.insert(0, str(ROOT / "scripts" / "qa"))
    from nace_crosscheck import keys as nace_keys
    ks, tries = nace_keys(), 0
    for k in ks:
        while True:
            try:
                with NaceClient(api_key=k) as c:
                    up = c.documents.upload(str(pdf), path="star_asia/" + pdf.name, on_conflict="new_version")
                    src = {"type": "workspace_file", "workspace_id": up.workspace_id, "file_id": up.file_id}
                    job = c.documents.parse(src, page_ranges=[{"start": page, "end": page}], parse_mode="high",
                                            output={"formats": ["markdown"], "table_format": "html",
                                                    "include_page_markers": False},
                                            figures={"mode": "omit"}, wait_seconds=60)
                    if job.status not in ("succeeded", "failed", "cancelled"):
                        job = c.jobs.wait(job.job_id)
                    if job.status != "succeeded":
                        raise RuntimeError(f"nace job {job.job_id} {job.status}: {getattr(job, 'error', None)}")
                    md = job.result["document"]["markdown"]
                    NACE_CACHE.mkdir(parents=True, exist_ok=True)
                    cp.write_text(json.dumps({"pdf": pdf.name, "page": page, "markdown": md, "job_id": job.job_id},
                                             ensure_ascii=False), encoding="utf-8")
                    return md
            except Exception as e:  # noqa: BLE001 - next key on no credit, retry transient, re-raise the rest
                s = str(e)
                if "402" in s or "insufficient_credit" in s.lower():
                    break
                if any(t in s for t in (" 503", " 502", " 504", " 429", "timed out", "not confirmed")) and tries < 4:
                    tries += 1
                    time.sleep(15 * tries)
                    continue
                raise
    raise RuntimeError("all Nace keys are out of credit")


def page_markdown(pdf: Path, page: int) -> str | None:
    """The cached page read: LlamaParse first, else Nace."""
    if cache_path(pdf, page).exists():
        return parse_page(pdf, page)
    if nace_cache_path(pdf, page).exists():
        return nace_parse_page(pdf, page)
    return None


def parse_page(pdf: Path, page: int) -> str:
    cp = cache_path(pdf, page)
    if cp.exists():
        return json.loads(cp.read_text(encoding="utf-8"))["markdown"]
    if "--nace" in sys.argv:
        return nace_parse_page(pdf, page)
    from scripts.parse_engine.llama import LlamaParseClient
    r = LlamaParseClient().parse(pdf, "agentic", "latest", str(page), PROMPT, False)
    CACHE.mkdir(parents=True, exist_ok=True)
    cp.write_text(json.dumps({"pdf": pdf.name, "page": page, "markdown": r["markdown"], "job_id": r.get("job_id")},
                             ensure_ascii=False), encoding="utf-8")
    return r["markdown"]


_OCR = None


def ocr_read(pdf: Path, page_no: int, page, full: bool = False) -> tuple[set[str], str]:
    """Numbers and text an OCR read of the rendered page finds: the independent check for tables printed as images."""
    global _OCR
    cp = OCR_CACHE / f"{hashlib.sha1(pdf.read_bytes()).hexdigest()[:16]}_p{page_no}{'_full' if full else ''}.json"
    try:
        j = json.loads(cp.read_text(encoding="utf-8"))
        return set(j["nums"]), j["text"]
    except (OSError, ValueError, KeyError):     # missing, or truncated (e.g. written on a full disk): OCR again
        pass
    import numpy as np
    if _OCR is None:
        from rapidocr_onnxruntime import RapidOCR
        _OCR = RapidOCR()
    # only the embedded images: what the text layer already holds needs no OCR
    area = page.rect.width * page.rect.height
    boxes = []
    for info in page.get_image_info():
        r = pymupdf.Rect(info["bbox"]) & page.rect
        if r.width * r.height < 0.015 * area:
            continue
        for k, o in enumerate(boxes):
            if o.intersects(r):
                boxes[k] = o | r
                break
        else:
            boxes.append(r)
    if full or sum(b.width * b.height for b in boxes) > 0.6 * area:     # full: text drawn as vector outlines
        boxes = [page.rect]
    parts = []
    for clip in boxes:
        dpi = min(200, int(4000 * 72 / max(clip.width, clip.height)))   # big clips at 200 dpi exhaust ONNX memory
        for attempt in (dpi, dpi // 2):
            pix = page.get_pixmap(dpi=attempt, clip=clip)
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)[:, :, :3]
            try:
                res, _ = _OCR(img)
                break
            except Exception:  # noqa: BLE001 - "bad allocation": retry once at half size
                if attempt != dpi:
                    raise
        parts.append(" ".join(r[1] for r in (res or [])))
    text = " ".join(parts)
    out = nums(text) | nums(text.replace(" ", ""))
    OCR_CACHE.mkdir(parents=True, exist_ok=True)
    cp.write_text(json.dumps({"pdf": pdf.name, "page": page_no, "text": text, "nums": sorted(out)}), encoding="utf-8")
    return out, text


def span(cell) -> int:
    """colspan, tolerating the escaped quotes Nace sometimes emits (colspan=\\"4\\")."""
    m = re.search(r"\d+", str(cell.get("colspan", "1") or "1"))
    return int(m.group()) if m else 1


def table_md(html: str) -> tuple[list[str], str]:
    """One LlamaParse <table> as markdown lines; a title row spanning the whole table becomes a #### heading."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    title = ""
    trs = soup.find_all("tr")
    if len(trs) > 2:
        cells = trs[0].find_all(["td", "th"])
        width = max(sum(span(c) for c in tr.find_all(["td", "th"])) for tr in trs)
        if len(cells) == 1 and (span(cells[0]) >= width or width > 1):
            title = R.cell(cells[0].get_text(" "))
            trs[0].decompose()
    got = R.html_tables(str(soup))
    if not got:
        return [], title
    rows, merged = got[0]
    for c, a, b in merged:                       # one price over several ships is an en-bloc price, not repeated
        v = rows[a][c]
        if c > 0 and R.NUM.search(v) and "bloc" not in v.lower():
            for r in range(a, b + 1):
                rows[r][c] = f"{v} (en bloc)"
    rows = [[clean_text(c) for c in r] for r in rows]
    out = [f"#### {title}", ""] if title else []
    return out + [l.rstrip("\n") for l in R.to_md(rows, "\n")], title


def clean_text(line: str) -> str:
    s = re.sub(r"^(>\s*)+", "", line.strip())                      # blockquoted boxes are plain text in the corpus
    s = re.sub(r"</?(u|sup|sub)>", "", s).replace("~~", "")
    s = re.sub(r"<br\s*/?>", " ", s)
    s = re.sub(r"\s*\[icon:[^\]]*\]", "", s)                      # LlamaParse's description of a status icon
    s = re.sub(r"\s*[▲▼▴▾]\s*", " ", s)             # owner: no arrows
    return s.replace(r"\*", "*").strip()


def new_section(markdown: str, old_sec: str, printed: set[str], pdf, page_no, page) -> tuple[list[str], list[str]]:
    """LlamaParse page -> section lines in the corpus style. Tables with unprinted numbers are dropped (reported)."""
    old_heads = {re.sub(r"[#*\s:]+", " ", l).strip().lower(): l.strip() for l in old_sec.splitlines()
                 if l.strip().startswith("#")}
    old_text = old_sec.lower()
    out, dropped, ocr = [], [], None
    for part in re.split(r"(<table>.*?</table>)", markdown, flags=re.S):
        if part.startswith("<table>"):
            lines, title = table_md(part)
            tn = nums("\n".join(lines[2:] if title else lines[1:]))
            missing = tn - printed
            if missing:
                if ocr is None:
                    ocr = ocr_read(pdf, page_no, page)[0]
                missing -= ocr
            if missing:
                dropped.append(f"{title or (lines[0][:60] if lines else '?')}: {sorted(missing)[:6]}")
                continue
            out += [""] + lines + [""]
            continue
        for l in part.splitlines():
            s = clean_text(l)
            if not s:
                out.append("")
                continue
            if s.startswith("![") or re.match(r"(?i)(chart|logo|icon|image|figure)\s*:", s) or (FOOTER.search(s.strip("#* ")) and s.strip("#* ").lower() not in old_text):
                continue
            m = re.fullmatch(r"(#+)\s*(.+)", s)
            b = re.fullmatch(r"\*\*(.+?)\*\*", s)
            if m or b:
                text = (m.group(2) if m else b.group(1)).strip("* ").strip()
                key = re.sub(r"[#*\s:]+", " ", text).strip().lower()
                if not re.search(r"[A-Za-z]", text):            # a figure in a stat box is not a heading
                    out.append(text)
                elif key in old_heads:
                    out.append(old_heads[key])
                elif m:
                    out.append(("# " if len(m.group(1)) <= 2 else "### ") + text)
                else:
                    out.append("#### " + text)
                continue
            plain_key = re.sub(r"[#*\s:]+", " ", s).strip().lower()
            if len(s) < 80 and plain_key in old_heads:              # Nace writes section titles as plain lines
                out.append(old_heads[plain_key])
                continue
            out.append(re.sub(r"\*\*(.+?)\*\*", r"\1", s))
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip("\n")
    return text.split("\n"), dropped


def judge(old_sec: str, new_lines: list[str], page_text: str, printed: set[str], ocr) -> str:
    """ocr() returns (numbers, text) of the OCR read; it is only run when the text layer alone cannot decide."""
    new = "\n".join(new_lines)
    if not new.strip():
        return "new page empty"
    seen, seen_text = set(printed), squash(page_text)

    level = [0]

    def with_ocr():
        """first the embedded images, then (still unresolved) the whole rendered page"""
        nonlocal seen, seen_text
        if level[0] >= 2:
            return
        level[0] += 1
        o_nums, o_text = ocr(level[0] == 2)
        seen |= o_nums
        seen_text += squash(o_text)
        ocr_text[0] += " " + o_text

    ocr_text = [""]
    if nums(new) - seen or nums(old_sec) - seen:
        with_ocr()
    if nums(new) - seen:
        with_ocr()
    unprinted = nums(new) - seen
    if unprinted:
        return f"numbers not on the PDF page: {sorted(unprinted)[:6]}"
    lost = (nums(old_sec) & seen) - nums(new)
    if lost:
        return f"old printed numbers lost: {sorted(lost)[:6]}"
    # prose must be the page's own words: a paragraph whose words are not printed is a paraphrase
    for para in re.split(r"\n\s*\n", new):
        if is_table(para.strip()) or para.strip().startswith("#"):
            continue
        ws = [w for w in words(para).elements() if len(w) > 2]
        if len(ws) >= 8:
            miss = [w for w in ws if squash(w) not in seen_text]
            while len(miss) > 0.1 * len(ws) and level[0] < 2:
                with_ocr()
                miss = [w for w in ws if squash(w) not in seen_text]
            if len(miss) > 0.1 * len(ws):
                return f"paragraph not printed on the page: {para[:80]!r} {miss[:6]}"
    # old words that are printed on the page must survive, each at most as often as the page prints it;
    # header-only table skeletons hold no data (the old parse invented some)
    old_lines = old_sec.splitlines()
    skel = set()
    for i, l in enumerate(old_lines):
        if is_table(l) and i + 1 < len(old_lines) and R.SEP.match(old_lines[i + 1].strip()) and \
                (i + 2 >= len(old_lines) or not is_table(old_lines[i + 2])) and (i == 0 or not is_table(old_lines[i - 1])):
            skel |= {i, i + 1}
    old_body = "\n".join(l for i, l in enumerate(old_lines) if i not in skel)
    wn = words(new)

    def lost_words():
        page_w = words(page_text) | words(ocr_text[0])
        wo = Counter()
        for w, k in words(old_body).items():
            on_page = page_w[w] or (len(w) >= 5 and squash(w) in seen_text)
            wo[w] = min(k, max(page_w[w], 1 if on_page else 0))
        return wo, wo - wn

    wo, lost_w = lost_words()
    while sum(lost_w.values()) > max(1, 0.02 * sum(wo.values())) and level[0] < 2:
        with_ocr()
        wo, lost_w = lost_words()
    if sum(lost_w.values()) > max(1, 0.02 * sum(wo.values())):
        return f"old words kept {1 - sum(lost_w.values()) / sum(wo.values()):.3f}: {sorted(lost_w.elements())[:8]}"
    if len(nums(new) & seen) <= len(nums(old_sec) & seen) and sum(wn.values()) <= 1.05 * sum(words(old_sec).values()):
        return "no gain"
    return "ok"


def main() -> int:
    parse, apply = "--parse" in sys.argv, "--apply" in sys.argv
    jobs = int(sys.argv[sys.argv.index("-j") + 1]) if "-j" in sys.argv else 3
    mds = sorted(MD_ROOT.rglob("*.md"))
    if "--untracked" in sys.argv:                      # CI: only the issues extracted in this run
        import subprocess
        out = subprocess.run(["git", "-c", "core.quotepath=off", "ls-files", "--others", "--exclude-standard", "-z",
                              "--", MD_ROOT.relative_to(ROOT).as_posix()],
                             cwd=ROOT, capture_output=True, text=True, encoding="utf-8").stdout
        mds = sorted(ROOT / p for p in out.split("\0") if p.endswith(".md"))
    if "--only" in sys.argv:                           # pilot: MDs whose name contains any of the comma-separated keys
        keys = sys.argv[sys.argv.index("--only") + 1].split(",")
        mds = [m for m in mds if any(k in m.name for k in keys)]
    plan, report, stat = [], [], Counter()
    for md in mds:
        raw = md.read_bytes().decode("utf-8")
        pdf = R.source_pdf(raw)
        if pdf is None:
            stat["no source pdf"] += 1
            continue
        lines = raw.splitlines(keepends=True)
        secs = split_pages(lines)
        doc = pymupdf.open(pdf)
        md_nums = nums(raw)
        for p in range(1, len(doc) + 1):
            if p not in secs:
                stat["page marker missing"] += 1
                report.append({"md": md.relative_to(ROOT).as_posix(), "page": p, "result": "page marker missing"})
                continue
            a, b = secs[p]
            why = candidate("".join(lines[a:b]), doc[p - 1].get_text(), md_nums)
            if why:
                for w in why:
                    stat[f"candidate: {w}"] += 1
                plan.append((md, pdf, p, why))
    pages = sorted({(pdf, p) for _, pdf, p, _ in plan}, key=str)
    todo = [x for x in pages if not cache_path(*x).exists() and not nace_cache_path(*x).exists()]
    if "--nace" in sys.argv:
        todo = todo[:int(sys.argv[sys.argv.index("--max") + 1])] if "--max" in sys.argv else todo
    print(f"{len(plan)} candidate pages in {len({x[0] for x in plan})} MDs; {len(todo)} not cached "
          f"(~{10 * len(todo)} LlamaParse credits)")
    if parse and todo:
        def one(x):
            try:
                parse_page(*x)
                return None
            except Exception as e:  # keep going; report at the end
                return f"{x[0].name} p{x[1]}: {e}"
        with ThreadPoolExecutor(jobs) as ex:
            for i, err in enumerate(ex.map(one, todo), 1):
                if err:
                    print("FAIL", err)
                if i % 10 == 0:
                    print(f"{i} / {len(todo)}", flush=True)
    by_md: dict[Path, list] = {}
    for md, pdf, p, why in plan:
        by_md.setdefault(md, []).append((pdf, p, why))
    for md, items in by_md.items():
        raw = md.read_bytes().decode("utf-8")
        lines = raw.splitlines(keepends=True)
        nl = "\r\n" if lines and lines[0].endswith("\r\n") else "\n"
        secs = split_pages(lines)
        doc = pymupdf.open(items[0][0])
        changed = False
        for pdf, p, why in sorted(items, key=lambda x: -x[1]):      # bottom-up keeps line numbers valid
            md_page = page_markdown(pdf, p)
            if md_page is None:
                continue
            a, b = secs[p]
            old_sec = "".join(lines[a:b])
            page = doc[p - 1]
            printed = nums(page.get_text())
            try:
                new, dropped = new_section(md_page, old_sec, printed, pdf, p, page)
                verdict = judge(old_sec, new, page.get_text(), printed, lambda full: ocr_read(pdf, p, page, full))
            except Exception as e:  # noqa: BLE001 - an unreadable page is left as is and reported, not fatal
                new, dropped, verdict = [], [], f"error: {type(e).__name__}: {e}"[:200]
            report.append({"md": md.relative_to(ROOT).as_posix(), "page": p, "why": why, "result": verdict,
                           "dropped_tables": dropped})
            stat[f"page {'rebuilt' if verdict == 'ok' else 'left as is'}"] += 1
            if dropped:
                stat["tables dropped (unprinted numbers)"] += len(dropped)
            if verdict == "ok":
                lines[a:b] = [nl] + [l + nl for l in new] + [nl]
                changed = True
        if changed:
            stat["files changed"] += 1
            if apply:
                md.write_bytes("".join(lines).encode("utf-8"))
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    for k, v in sorted(stat.items()):
        print(f"{v:6}  {k}")
    print("APPLIED" if apply else "dry run (use --apply)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
