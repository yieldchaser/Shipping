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

# scripts/tools/score_cloud_vs_local.py -> [0]=tools, [1]=scripts, [2]=repo root.
REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "cvl", REPO / "scripts" / "tools" / "cloud_vs_local.py")
cvl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cvl)

import pymupdf                                     # noqa: E402


def has_number(text, value, variants=None):
    """True if `value` appears as a standalone number in `text`.

    THE PUBLISHER'S OWN THOUSANDS SEPARATOR MATTERS. Measured on fearnleys 2018 W29 p2,
    the cloud returns '15 000' and '44 000' with a THIN SPACE, while the render and the
    surrounding text read '15,800' with a comma. A comma-only pattern scored the cloud at
    1/8 on a page where it actually recovered 8/8 - the same shape of error as reading a
    European '60.000' as 60, only in the other direction: a correct extraction declared
    wrong because the number was formatted differently.

    So every plausible grouping of the same digits is accepted: comma, thin space, plain
    space, and no separator. The digits must still be a standalone token, so '15' does not
    match inside '150'.
    """
    raw = str(value).replace(",", "").replace("\u2009", "").replace("\u00a0", "")
    if not re.fullmatch(r"-?\d+(?:\.\d+)?", raw):
        return False
    seps = ["", ",", r"\s", "\u2009", "\u00a0", "_"]
    intpart = raw.split(".")[0]
    frac = raw.split(".")[1] if "." in raw else None
    # split the integer part into thousands from the RIGHT, so '15800' -> 15|000
    chunks = []
    rest = intpart
    while len(rest) > 3:
        chunks.insert(0, rest[-3:])
        rest = rest[:-3]
    chunks.insert(0, rest)
    for s in seps:
        # r"\s" is a regex CLASS and must be used as-is; re.escape() on it yields the
        # literal '\\s', which is why a plain ASCII space separator never matched even
        # though the cloud's output contains '15 000' with codepoint 0x20.
        body = (s if s == r"\s" else re.escape(s)).join(chunks) if s else intpart
        if frac:
            body += r"\." + frac
        if re.search(rf"(?<![\d.]){body}(?![\d])", text):
            return True
    return False


def main(argv):
    # values arrive comma-separated, so a value may NOT contain a comma - strip the
    # thousands separators first, otherwise '15,800' is split into '15' and '800' and the
    # score counts two bogus values instead of one real one.
    if len(argv) < 3:
        print("usage: score_cloud_vs_local.py <file.pdf> <page#> <v1|v2|v3>")
        return 2
    pdf, page_s, values = argv[0], argv[1], argv[2]
    page_i = int(page_s) - 1
    want = [v.replace(",", "") for v in values.split("|") if v.strip()]

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
