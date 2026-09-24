"""Cloud vs local, judged against values READ OFF THE RENDERED PAGE.

The comparison that matters is not "how many characters did each return" - both return
text. It is: do the numbers a human can read on the page appear in each output?

This module takes a page, a small set of values transcribed from its render, and reports
which pipeline recovered them. That is the same discipline the whole programme uses:
render, read, compare, and never trust a count.

The values are supplied by the caller (from a render), never guessed here.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "cvl", REPO / "scripts" / "tools" / "cloud_vs_local.py")
cvl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cvl)

import pymupdf                                     # noqa: E402


def has_number(text, value, variants=None):
    """True if `value` appears as a standalone number in `text`."""
    vs = variants or [value]
    for v in vs:
        pats = set()
        raw = str(v)
        if re.fullmatch(r"-?\d+", raw):
            pats.add(rf"(?<![\d.]){re.escape(raw)}(?![\d])")
            pats.add(rf"(?<![\d.]){raw.replace(str(int(raw)), f'{int(raw):,}')}(?![\d])")
        else:
            pats.add(rf"(?<![\d.]){re.escape(raw)}(?![\d])")
        if any(re.search(p, text) for p in pats):
            return True
    return False


def main(argv):
    if len(argv) < 4:
        print("usage: score_cloud_vs_local.py <page.png-note> <file.pdf> <page#> "
              "<v1,v2,v3>")
        return 2
    _note, pdf, page_s, values = argv[:4]
    page_i = int(page_s) - 1
    want = [v for v in values.split(",") if v]

    # local
    with pymupdf.open(pdf) as d:
        local = d[page_i].get_text()
    # cloud: reuse the stored comparison when it covers this page, else call
    res = []
    stored = REPO / "data" / "derived" / "cloud_vs_local.json"
    cloud_md = None
    if stored.exists():
        data = json.loads(stored.read_text(encoding="utf-8"))
        for r in data:
            if r.get("file") == Path(pdf).name and r.get("page") == page_i + 1:
                cloud_md = r.get("cloud_markdown")
    if cloud_md is None:
        print("no stored cloud markdown for this page - rerun cloud_vs_local.py first")
        return 1

    print(f"file        : {Path(pdf).name}  page {page_i + 1}")
    print(f"ground truth: {want}")
    print()
    for label, text in (("local", local), ("cloud", cloud_md)):
        hits = [v for v in want if has_number(text, v)]
        miss = [v for v in want if v not in hits]
        print(f"  {label:<6} {len(hits)}/{len(want)} recovered"
              f"   missing: {miss if miss else 'none'}")
        for v in hits:
            # show the line it was found on, for a human check
            for ln in text.splitlines():
                if re.search(rf"(?<![\d.]){re.escape(v)}(?![\d])", ln):
                    print(f"         {v}: {ln.strip()[:110]}")
                    break
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
