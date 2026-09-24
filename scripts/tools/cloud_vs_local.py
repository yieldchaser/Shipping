"""Does LlamaParse beat the local pipeline on the pages that remain flagged?

The user is right to keep asking why credits sit still. This answers it with a measurement
instead of an argument, on the pages that are ACTUALLY flagged.

Method
------
For each source with a non-zero paid surface, take a small sample of its flagged pages,
run the local text layer and LlamaParse `cost_effective` on the SAME page, and compare
against the page's own rendered ground truth.

The comparison is not "does the cloud return text" - it returns text everywhere. It is
"does it return text a reader would accept where the local layer does not". A page whose
local text is already clean is a page the cloud must beat, not join.

Cost: the sample is deliberately tiny. A 6-page sample at 3 cr is 18 credits, which
answers the question for a fraction of 1% of the remaining balance. Scaling is a separate
decision made only if the sample shows the cloud wins.

Run:  python3 -B scripts/tools/cloud_vs_local.py [--pages N] [--source NAME]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import pymupdf

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "tools"))
import set_llama_key as _keys                           # noqa: E402


def get_api_key():
    """The stored key, read at RUN TIME from the canonical env file.

    The Hermes .env is not exported into terminal subprocesses, so os.environ cannot see
    it. set_llama_key.read_lines() returns (lines, style, raw) - the first element is a
    list of raw 'NAME=value' strings, which is what current_value() expects; passing the
    whole tuple is what raised 'list object has no attribute strip' on the first attempt.
    """
    p = _keys.target_file()
    if not Path(p).exists():
        return None
    lines, _style, _raw = _keys.read_lines(p)
    return _keys.current_value(lines) or None


OUT = REPO / "data" / "derived" / "cloud_vs_local.json"
PNG = REPO / "scratch" / "cloud_vs_local"
PNG.mkdir(parents=True, exist_ok=True)

CIPHER = re.compile(r"[^A-Za-z0-9\s]{3,}")


def local_quality(page):
    """(chars, suspicious_spans) for the local text layer.

    `suspicious_spans` counts lines that are punctuation-dense with no alphabetic
    content - the signature of the banchero glyph cipher, where a table renders real
    values but the text layer emits '!"#$ %FG()" *G()" +GHG+ -GHG-'.
    """
    text = page.get_text()
    sus = 0
    for line in text.splitlines():
        s = line.strip()
        if len(s) < 4:
            continue
        letters = sum(c.isalpha() for c in s)
        if letters == 0 and CIPHER.search(s):
            sus += 1
    return len(text), sus


def cloud_markdown(pdf_path, page_index, api_key, max_pages=1):
    """Parse ONE page through LlamaParse cost_effective and return the markdown."""
    from llama_cloud import LlamaCloud
    client = LlamaCloud(api_key=api_key)
    # page targeting is what makes this affordable: one page, not the document
    target = str(page_index + 1)
    with open(pdf_path, "rb") as fh:
        fobj = client.files.create(file=fh, purpose="parse")
    try:
        res = client.parsing.parse(
            file_id=fobj.id,
            tier="cost_effective",
            version="latest",
            expand=["markdown_full"],
            page_ranges={"target_pages": target},
        )
        return getattr(res, "markdown_full", None) or ""
    finally:
        try:
            client.files.delete(file_id=fobj.id)
        except Exception:                                  # noqa: BLE001
            pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=6)
    ap.add_argument("--source", default=None)
    ap.add_argument("--force", default=None,
                    help="parse this exact 'file.pdf:page' regardless of the detector")
    ap.add_argument("--cache", action="store_true",
                    help="reuse an existing comparison for the same file+page")
    args = ap.parse_args()

    api_key = get_api_key()
    if not api_key:
        print("no LLAMA_CLOUD_API_KEY available", file=sys.stderr)
        return 1

    surface = json.loads(
        (REPO / "data" / "derived" / "paid_surface_by_source.json").read_text("utf-8"))
    flagged = [(k, v.get("flagged_pages", 0)) for k, v in surface.items()
               if isinstance(v, dict) and v.get("flagged_pages", 0)]
    flagged.sort(key=lambda t: -t[1])
    if args.source:
        flagged = [(k, n) for k, n in flagged if k == args.source]
    if not flagged:
        print("no flagged sources - nothing to compare")
        return 0

    budget = args.pages
    results = []
    if OUT.exists():
        try:
            results = json.loads(OUT.read_text(encoding="utf-8"))
        except Exception:                                  # noqa: BLE001
            results = []

    if args.force:
        # parse a named page directly, for a case the detector's signature misses -
        # notably a table drawn as a raster image, where the text layer holds the prose
        # and none of the numbers
        name, _, pg_s = args.force.rpartition(":")
        pdfs = list((REPO / "corpus" / "01-brokers").glob("**/" + name))
        if not pdfs:
            print(f"no PDF matching {name}")
            return 1
        pdf = pdfs[0]
        pi = int(pg_s) - 1
        with pymupdf.open(pdf) as d:
            pg = d[pi]
            chars, sus = local_quality(pg)
            loc_text = pg.get_text()[:20000]
            png = PNG / f"forced_{pdf.stem}_p{pi+1}.png"
            pg.get_pixmap(dpi=150).save(png)
        print(f"forced: {pdf.name} p{pi+1}: local {chars} chars, {sus} cipher lines")
        t0 = time.time()
        md = cloud_markdown(str(pdf), pi, api_key)
        print(f"  cloud {len(md)} chars, {len(re.findall(chr(92)+'d', md))} digits, "
              f"{time.time()-t0:.0f}s, 3 cr")
        results = [r for r in results
                   if not (r.get("file") == pdf.name and r.get("page") == pi + 1)]
        results.append({
            "source": pdf.parent.parent.name, "file": pdf.name, "page": pi + 1,
            "local_chars": chars, "local_suspect_lines": sus,
            "local_text": loc_text,
            "cloud_chars": len(md), "cloud_markdown": md[:20000],
            "cloud_seconds": round(time.time() - t0, 1), "png": str(png),
        })
        OUT.write_text(json.dumps(results, indent=1), encoding="utf-8")
        print(f"wrote {OUT}")
        return 0

    for src, _n in flagged:
        if budget <= 0:
            break
        pdfs = sorted((REPO / "corpus" / "01-brokers" / src).glob("*/*.pdf"))
        # find a page with a suspicious local layer
        for pdf in pdfs:
            if budget <= 0:
                break
            try:
                with pymupdf.open(pdf) as d:
                    for pi, pg in enumerate(d):
                        chars, sus = local_quality(pg)
                        if sus < 2:
                            continue
                        budget -= 1
                        print(f"[{src}] {pdf.name} p{pi+1}: "
                              f"local {chars} chars, {sus} cipher-like lines", flush=True)
                        png = PNG / f"{src}_{pdf.stem}_p{pi+1}.png"
                        pg.get_pixmap(dpi=150).save(png)
                        t0 = time.time()
                        try:
                            md = cloud_markdown(str(pdf), pi, api_key)
                        except Exception as e:              # noqa: BLE001
                            print(f"    cloud FAILED: {str(e)[:160]}", flush=True)
                            results.append({"source": src, "file": pdf.name,
                                            "page": pi + 1, "local_chars": chars,
                                            "local_suspect": sus, "cloud_error":
                                            str(e)[:200]})
                            break
                        # count digits in the cloud output: a ciphered page's values
                        # appear as digits in markdown tables
                        cloud_digits = len(re.findall(r"\d", md))
                        print(f"    cloud {len(md)} chars, {cloud_digits} digit chars, "
                              f"{time.time()-t0:.0f}s, 3 cr", flush=True)
                        results.append({
                            "source": src, "file": pdf.name, "page": pi + 1,
                            "local_chars": chars, "local_suspect_lines": sus,
                            "local_text": pg.get_text()[:20000],
                            "cloud_chars": len(md), "cloud_digit_chars": cloud_digits,
                            "cloud_markdown": md[:20000],
                            "cloud_seconds": round(time.time() - t0, 1),
                            "png": str(png),
                        })
                        (OUT.with_suffix(".partial.json")).write_text(
                            json.dumps(results, indent=1), encoding="utf-8")
                        break
            except Exception as e:                          # noqa: BLE001
                print(f"  {src} {pdf.name}: {str(e)[:100]}", flush=True)
    OUT.write_text(json.dumps(results, indent=1), encoding="utf-8")
    print(f"\nwrote {len(results)} comparisons -> {OUT}")
    if results:
        spent = sum(1 for r in results if "cloud_error" not in r) * 3
        print(f"credits spent: {spent}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
