"""VLM table audit via local Ollama (qwen2.5vl:3b).

Renders a page region to PNG, asks the local vision model to transcribe the
table, and compares its output against the classical extractor's cells.
Agreement = high confidence; disagreement = review queue.

Runs against the Ollama server on 127.0.0.1:11434 (desktop app or `ollama serve`).

Usage:
  python scripts/analysis/vlm_audit.py <pdf> <page1based> [--out json]
  python scripts/analysis/vlm_audit.py --golden   # Star Asia W35 p3 self-test
"""
import argparse
import base64
import json
import os
import re
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROMPT = ("Extract the table on this page. Output one line per row as "
          "VESSEL | TYPE | DWT | YEAR | PRICE | BUYER. No commentary.")


def render(pdf, page1, dpi=110, clip_frac=(0.42, 1.0)):
    import pymupdf
    doc = pymupdf.open(pdf)
    pg = doc[page1 - 1]
    r = pg.rect
    clip = pymupdf.Rect(30, r.height * clip_frac[0], r.width - 25, r.height * clip_frac[1])
    pix = pg.get_pixmap(dpi=dpi, clip=clip)
    out = os.path.join(REPO, "scratch", "probe", "vlm_page.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    pix.save(out)
    return out


def ask_vlm(img, model="qwen2.5vl:3b", timeout=900):
    t0 = time.time()
    try:
        p = subprocess.run(["ollama", "run", model, PROMPT, img],
                           capture_output=True, text=True, timeout=timeout)
        return {"text": p.stdout.strip(), "secs": round(time.time() - t0, 1),
                "err": p.stderr.strip()[:200] if p.returncode else None}
    except subprocess.TimeoutExpired:
        return {"text": "", "secs": timeout, "err": "timeout"}


def classical(pdf, page1):
    import camelot, warnings
    cells = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        tabs = camelot.read_pdf(pdf, pages=str(page1), flavor="stream")
        for i in range(tabs.n):
            for row in tabs[i].df.values.tolist():
                cells.append(" | ".join(row))
    return "\n".join(cells)


def score(vlm_text, klass_text):
    """Row-level agreement: fraction of VLM vessel-name tokens found classically."""
    names = [l.split("|")[0].strip().upper() for l in vlm_text.splitlines() if "|" in l]
    names = [n for n in names if len(n) > 3 and not n.startswith("VESSEL")]
    if not names:
        return {"rows": 0, "matched": 0, "agreement": None, "names": []}
    kt = klass_text.upper()
    matched = [n for n in names if n in kt]
    return {"rows": len(names), "matched": len(matched),
            "agreement": round(len(matched) / len(names), 3), "names": names}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf", nargs="?")
    ap.add_argument("page", nargs="?", type=int, default=3)
    ap.add_argument("--model", default="qwen2.5vl:3b")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    if a.pdf is None:
        a.pdf = os.path.join(REPO, "reports/shipbrokers/star_asia/2026",
                             "star_asia_2026_W35_Market-Report-Week-35.pdf")
    img = render(a.pdf, a.page)
    klass = classical(a.pdf, a.page)
    vlm = ask_vlm(img, a.model)
    result = {"pdf": a.pdf, "page": a.page, "model": a.model, "image": img,
              "vlm_secs": vlm["secs"], "vlm_err": vlm["err"],
              "vlm_text": vlm["text"][:4000],
              "agreement": score(vlm["text"], klass)}
    print(json.dumps(result, indent=1)[:4000])
    if a.out:
        open(a.out, "w", encoding="utf-8", newline="\n").write(json.dumps(result, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
