#!/usr/bin/env python3
"""
Poten Tanker Opinion fallback: page images posted on X by @ed_fin, OCR'd, used only while the official PDF is missing.

Poten emails the Friday opinion to subscribers and puts it on poten.com days or weeks later (the 2026-10-23 and 10-30
issues were still not online on 11-02). @ed_fin posts the full page 1 image the next day, and the owner's archive repo
(yieldchaser/Twitter-Image-Download-, public) files those images under the series `poten-tanker-opinion`.

For every such image whose issue has no official MD (data/extracted/md/poten/<year>/, written by run_poten.py from the
PDF), this writes poten_<date>_<slug>_x-ocr.md in the same place, marked `extraction: "ocr_x_image"` (own name, so the
official MD is a new file and never an edit of a tracked one, which protect_accepted_md.py would undo):
  - the issue date and title come from the page header the image shows (never from the post date)
  - prose only: OCR paragraphs that read as text; chart axes, labels and data tables are dropped, because numbers read
    off chart pictures never ship (the page image itself is kept and linked so every word can be checked)
  - once run_poten.py has written the official MD for that date, the fallback MD is deleted (--retire-only, which CI
    runs after protect_accepted_md.py so the deletion is kept)
Opinions are one page, so page 1 is the whole issue.

Usage: fetch_poten_x_fallback.py            write / retire fallback MDs
       fetch_poten_x_fallback.py --retire-only  only delete fallback MDs whose official MD now exists
       fetch_poten_x_fallback.py --check    OCR images whose official MD exists and report word agreement (no writes)
"""
import argparse
import csv
import difflib
import io
import logging
import re
import shutil
import sys
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

from PIL import Image
import pytesseract

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
ROOT = Path(__file__).resolve().parent.parent.parent
MD_DIR = ROOT / "data" / "extracted" / "md" / "poten"
IMG_DIR = ROOT / "corpus" / "04-poten" / "x_images"
REPO_RAW = "https://raw.githubusercontent.com/yieldchaser/Twitter-Image-Download-/main/"
SERIES = "poten-tanker-opinion"
ACCOUNT = "ed_fin"
MARK = 'extraction: "ocr_x_image"'
MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
WIN_TESSERACT = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
if WIN_TESSERACT.exists():
    pytesseract.pytesseract.tesseract_cmd = str(WIN_TESSERACT)
sys.path.insert(0, str(ROOT / "scripts" / "extract" / "publishers"))
from run_poten import slugify  # noqa: E402  same slug rule as the official MDs


def http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def image_bytes(row: dict) -> bytes:
    """The archive files images into library/ (catalog `target`); `file` is the original download path."""
    for path in (row.get("target"), row.get("file")):
        if path:
            try:
                return http_get(REPO_RAW + path)
            except OSError:
                continue
    raise FileNotFoundError(row.get("file"))


def catalog_rows() -> list[dict]:
    text = http_get(REPO_RAW + "library/catalog.csv").decode("utf-8")
    return [r for r in csv.DictReader(io.StringIO(text))
            if r["account"] == ACCOUNT and SERIES in (r.get("final_series"), r.get("series"))]


def official_md(issue: str) -> Path | None:
    for p in (MD_DIR / issue[:4]).glob(f"poten_{issue}_*.md"):
        if p.name.endswith(".md") and MARK not in p.read_text(encoding="utf-8", errors="ignore")[:1500]:
            return p
    return None


def official_dates() -> set[str]:
    out = set()
    for p in MD_DIR.rglob("poten_*.md"):
        m = re.match(r"poten_(\d{4}-\d{2}-\d{2})_", p.name)
        if m and MARK not in p.read_text(encoding="utf-8", errors="ignore")[:1500]:
            out.add(m[1])
    return out


def ocr(img: Image.Image) -> dict:
    """Header date + title, and prose paragraphs in reading order (tesseract page segmentation)."""
    d = pytesseract.image_to_data(img.convert("L"), config="--psm 3", output_type=pytesseract.Output.DICT)
    h = img.height
    pars: dict[tuple, list] = {}
    for i, w in enumerate(d["text"]):
        if not w.strip():
            continue
        key = (d["block_num"][i], d["par_num"][i])
        pars.setdefault(key, []).append((d["line_num"][i], w, float(d["conf"][i]), d["top"][i], d["height"][i]))
    paras = []
    for key, words in pars.items():
        lines: dict[int, list] = {}
        for ln, w, c, top, ht in words:
            lines.setdefault(ln, []).append(w)
        text = ""
        for ln in sorted(lines):
            line = " ".join(lines[ln])
            text = text[:-1] + line if text.endswith("-") and text[-2:-1].isalpha() else (text + " " + line).strip()
        paras.append({"text": text, "top": min(t for *_, t, _ in words), "nlines": len(lines),
                      "height": sorted(ht for *_, ht in words)[len(words) // 2],
                      "conf": sum(c for _, _, c, _, _ in words) / len(words)})
    header = " ".join(p["text"] for p in paras if p["top"] < 0.12 * h)
    m = re.search(rf"({MONTHS})\s+(\d{{1,2}})\D{{0,20}}?(20\d\d)", header)
    issue = datetime.strptime(f"{m[1]} {m[2]} {m[3]}", "%B %d %Y").date().isoformat() if m else ""
    body = [p for p in paras if p["top"] >= 0.12 * h and "TANKER OPINION" not in p["text"].upper()]
    return {"issue": issue, "is_poten": "TANKER OPINION" in " ".join(p["text"].upper() for p in paras), "paras": body}


def is_prose(p: dict) -> bool:
    words = p["text"].split()
    alpha = sum(1 for w in words if re.search(r"[A-Za-z]{2}", w))
    # map and axis labels pass an alphabetic test ("ISRAEL IRAQ Suez IRAN"); sentences are mostly lowercase words
    lower = sum(1 for w in words if re.fullmatch(r"[a-z][a-z'’-]*[.,;:]?", w))
    return (len(words) >= 12 and alpha / len(words) >= 0.7 and lower / len(words) >= 0.45
            and re.search(r"[.,;]", p["text"]) is not None and p["conf"] >= 60)


def build(img: Image.Image) -> dict | None:
    o = ocr(img)
    if not (o["is_poten"] and o["issue"]):
        return None
    paras = o["paras"]
    # title: the largest-type short paragraph near the top of the body; the bold standfirst follows it
    tops = [p for p in paras if p["nlines"] == 1 and len(p["text"].split()) <= 14 and p["top"] < 0.22 * img.height]
    title = max(tops, key=lambda p: p["height"])["text"] if tops else ""
    after = [p for p in paras if p["top"] > (max(tops, key=lambda p: p["height"])["top"] if tops else 0)]
    sub = next((p["text"] for p in after if p["nlines"] == 1 and len(p["text"].split()) <= 16 and p["text"] != title), "")
    prose = [p["text"] for p in paras if is_prose(p) and p["text"] not in (title, sub)]
    return {"issue": o["issue"], "title": title.strip(), "subtitle": sub.strip(), "prose": prose}


def write_md(r: dict, row: dict, img_rel: str) -> Path:
    issue, title = r["issue"], r["title"]
    md = MD_DIR / issue[:4] / f"poten_{issue}_{slugify(title)}_x-ocr.md"
    tweet = f"https://x.com/{ACCOUNT}/status/{row['tweet_id']}"
    q = lambda s: s.replace('"', "'")  # noqa: E731
    lines = ["---", f'title: "{q(title.rstrip("?"))}"', f'subtitle: "{q(r["subtitle"])}"', f'issue_date: "{issue}"',
             f"year: {issue[:4]}", 'author: "Poten & Partners"', 'source: "poten"', 'category: "tankers"', "pages: 1",
             f'source_file: "{img_rel}"', f'source_url: "{tweet}"', MARK,
             'extraction_note: "OCR of the page image posted on X; prose only (chart and table numbers are not read'
             ' from images). Replaced by the PDF-based MD once Poten publishes the PDF."', "tables_count: 0",
             "charts_count: 0", "---", "", f"# {title}", ""]
    if r["subtitle"]:
        lines += [f"### {r['subtitle']}", ""]
    for p in r["prose"]:
        lines += [p, ""]
    lines += ["## Page image", "", f"![Poten Tanker Opinion {issue}](../../../../../{img_rel})", ""]
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return md


def retire() -> int:
    n = 0
    for p in MD_DIR.rglob("poten_*.md"):
        if MARK in p.read_text(encoding="utf-8", errors="ignore")[:1500]:
            issue = re.match(r"poten_(\d{4}-\d{2}-\d{2})_", p.name)[1]
            if official_md(issue):
                logging.info("official MD now exists for %s: fallback %s removed", issue, p.name)
                p.unlink()
                n += 1
    return n


def check(rows: list[dict], n: int) -> int:
    done = 0
    for row in sorted(rows, key=lambda r: r["date"], reverse=True):
        img = Image.open(io.BytesIO(image_bytes(row)))
        r = build(img)
        off = official_md(r["issue"]) if r else None
        if not off:
            continue
        body = off.read_text(encoding="utf-8").split("\n---", 1)[1]
        body = body.split("## Market Exhibits", 1)[0]
        a, b = " ".join(r["prose"]).split(), re.sub(r"[#*>]", " ", body).split()
        sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
        covered = sum(x.size for x in sm.get_matching_blocks()) / max(1, len(b))
        precision = sum(x.size for x in sm.get_matching_blocks()) / max(1, len(a))
        logging.info("%s %-45s title_ok=%s words: %d ocr / %d official, recall %.3f precision %.3f", r["issue"],
                     r["title"][:45], slugify(r["title"]) in off.name, len(a), len(b), covered, precision)
        done += 1
        if done >= n:
            break
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", type=int, nargs="?", const=6, help="score OCR vs N official MDs; no writes")
    ap.add_argument("--days", type=int, default=60, help="look at images posted in the last N days")
    ap.add_argument("--retire-only", action="store_true", help="only delete superseded fallback MDs")
    a = ap.parse_args()
    if a.retire_only:
        logging.info("fallback MDs retired %d", retire())
        return 0
    rows = catalog_rows()
    logging.info("%d @%s images filed as %s", len(rows), ACCOUNT, SERIES)
    if a.check:
        return check(rows, a.check)
    retired = retire()
    have = official_dates()
    since = (date.today() - timedelta(days=a.days)).isoformat()
    written = 0
    for row in sorted(rows, key=lambda r: r["date"]):
        if row["date"] < since:
            continue
        # issues are dated the Friday before the post; skip the OCR when an official MD covers that week
        post = date.fromisoformat(row["date"])
        if any((post - timedelta(days=k)).isoformat() in have for k in range(0, 9)):
            continue
        raw = image_bytes(row)
        r = build(Image.open(io.BytesIO(raw)))
        if not r or not r["title"] or len(r["prose"]) < 3:
            logging.warning("%s: not a readable Poten page (skipped)", row["file"])
            continue
        if official_md(r["issue"]):
            continue
        rel = Path("corpus/04-poten/x_images") / r["issue"][:4] / Path(row["file"]).name
        (ROOT / rel).parent.mkdir(parents=True, exist_ok=True)
        (ROOT / rel).write_bytes(raw)
        md = write_md(r, row, rel.as_posix())
        logging.info("fallback written: %s (%d paragraphs)", md.relative_to(ROOT), len(r["prose"]))
        written += 1
    logging.info("fallback MDs written %d, retired %d", written, retired)
    return 0


if __name__ == "__main__":
    sys.exit(main())
