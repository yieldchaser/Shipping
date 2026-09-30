"""Fail loudly when a MEASURED number-format rule is missing from the parser.

Why this exists
---------------
The extraction fixes from 2026-09-21..2026-09-30 were each committed to a
``auto/extract-fixes-<date>`` branch.  Committing to a branch does not change
the working tree, so each fix applied only while that branch stayed checked
out.  When the tree was later switched to another branch the fixes silently
disappeared from disk - no error, no failing gate, nothing in the logs - and
two separate deep-review runs had to re-discover that by hand
(``git merge-base --is-ancestor``, 2026-09-24 and 2026-09-30).

Every one of those rules is silently reversible: reading ``209.523`` as 209.523
instead of 209,523 dwt is a well-formed float of a plausible magnitude, so no
schema check, no recall metric and no plausibility bound can see it.  This
script is the marker test.  It asserts the *measurable* cases the pages were
read for, and names the exact rule that is absent when one fails.

Run:
    python scripts/extract/check_measured_rules.py        # exit 0 = all rules present

Ground truth for each case is recorded next to it (document + page), so a
future reader can re-derive it from the PDF rather than trusting this file.
"""
from __future__ import annotations

import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def load_to_number(path):
    spec = importlib.util.spec_from_file_location("btdb_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.to_number


# (raw cell, kwargs, expected, rule, ground-truth citation)
CASES = [
    ("209.523", {"publisher": "advanced_shipping"}, 209523.0,
     "period-thousands for the 3 measured publishers",
     "advanced_shipping_2026_W22 p2 text: dwt 53.712 / 181.221 / 180.000, newbuild $ 252m"),
    ("3.226", {"publisher": "agora"}, 3226.0,
     "period-thousands for the 3 measured publishers",
     "agora_2026_W22 p2 text: BDI 3.226, BCI 5.517, BCI T/C $46.538, alongside comma decimals 88,90 / 8,84%"),
    ("63.027", {"publisher": "star_asia"}, 63027.0,
     "period-thousands for the 3 measured publishers",
     "star_asia_2026_W21 p2 text: 'the Beltiger 63/2017' dwt, BDI printed 2,991 (comma-thousands)"),
    ("81.682", {"unit_thousands": True}, 81682.0,
     "period as thousands under a dwt/ldt header (publisher-independent)",
     "golden_destiny_2022_W31 p4 text: 'Dwt 171.199 | LDT 21.018 | Price 11.118.522 | 529 $/ldt'"),
    ("11.118.522", {}, 11118522.0,
     "two-or-more period groups are thousands whatever the publisher",
     "golden_destiny_2022_W31 p4 text: Price 11.118.522 = 21.018 x 529 $/ldt"),
    ("$ 15,648", {}, 15648.0,
     "currency marker with a space before the value",
     "allied_2022_W12 p1 text: 'closing on Friday at US$  15,648/day'"),
    ("-$ 1,498", {}, -1498.0,
     "sign before the currency marker",
     "a weekly-change column; same shape as the $/day TCE columns"),
    ("34,5", {}, 34.5,
     "comma is a decimal separator when it is not a 3-digit group",
     "advanced_shipping_2026_W22 p0: 'USD 57,5 mill'"),
    ("1.234,5", {}, 1234.5,
     "European full form: period thousands + comma decimals",
     "measured on the shipbroker weeklies, 2026-09-22"),
    ("-3,91%", {}, -3.91,
     "signed percentage with a comma decimal",
     "advanced_shipping_2026_W38 p1 text: 'BDI 3.370 3.507 -3,91%'"),
    ("2.567", {}, 2.567,
     "DEFAULT UNCHANGED: a bare d.ddd with no publisher/header evidence stays a decimal",
     "the 11,689 shipbroker cells outside the whitelist and outside dwt/ldt columns"),
]


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "build_table_db.py")
    to_number = load_to_number(path)
    print(f"parser under test: {path}")
    bad = 0
    for raw, kwargs, want, rule, cite in CASES:
        try:
            got = to_number(raw, **kwargs)
        except TypeError as exc:
            print(f"FAIL  {raw!r:14s} {kwargs}  -> signature error: {exc}")
            print(f"      rule missing: {rule}")
            print(f"      ground truth: {cite}")
            bad += 1
            continue
        ok = got == want
        print(f"{'ok  ' if ok else 'FAIL'}  {raw!r:14s} {str(kwargs):42s} -> {got!r} (want {want!r})")
        if not ok:
            print(f"      rule missing/broken: {rule}")
            print(f"      ground truth: {cite}")
            bad += 1
    print()
    if bad:
        print(f"{bad}/{len(CASES)} measured rules are MISSING from this parser.")
        print("A number rule that is absent reads as a plausible float: re-derive the case from "
              "the cited page before changing this file, then restore the rule from the "
              "auto/extract-fixes-* branch that holds it.")
        return 1
    print(f"all {len(CASES)} measured rules present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
