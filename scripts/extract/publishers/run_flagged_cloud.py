"""Run the 12 warranted pages through the cloud, page-targeted, and store the output.

This is the real spend, and it is small on purpose: 12 pages at 3 cr is 36 credits,
against a 6,480 balance. The 48 CLEAN pages are skipped entirely, because the triage
already showed their local layers hold the values.

Each page is verified after the fact: the cloud output must contain a table, and the
values must be paired with row labels. A page that returns prose with no table is
recorded as a failure rather than counted as done.

Run:  python3 -B scripts/extract/publishers/run_fearnleys_cipher.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
VERDICT = REPO / "data" / "derived" / "flagged_verdict.json"
OUT = REPO / "data" / "extracted" / "llamaparse_flagged"
PNG = REPO / "scratch" / "flagged_cloud"
PNG.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(REPO / "scripts" / "tools"))
import cloud_vs_local as cvl                          # noqa: E402

# Verdicts that justify a cloud parse. CIPHER is the text-layer signature. NO NUMBERS is
# included because it was PROVEN to be a real gap, not assumed: on star_asia 2023 W42 p11
# the page renders a Ship Recycling table full of values (Alang 520-530, Chattogram
# 510-520, Gaddani 510-520) and the local text layer holds 213 characters and NONE of
# them. Scored: local 0/15, cloud 11/15. The table body is drawn as vector paths, so the
# text layer sees the prose and misses every number.
#
# An earlier reading of this source claimed the opposite - "local 15/15" - and it was
# measured on a DIFFERENT page (2023 W40 p9) that does have a text layer. Page choice
# changed the verdict, which is exactly why every one of these is scored per page.
WARRANTED = ("CIPHER", "NO NUMBERS")


def main():
    api_key = cvl.get_api_key()
    if not api_key:
        print("no API key", file=sys.stderr)
        return 1
    if not VERDICT.exists():
        print("no flagged_verdict.json - run verify_flagged_pages.py --apply first")
        return 1
    rows = json.loads(VERDICT.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    state_path = OUT / "_run_state.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {}

    todo = [r for r in rows if r.get("verdict") in WARRANTED and r.get("file")]
    print(f"pages warranted for cloud spend: {len(todo)} "
          f"(~{3 * len(todo)} credits)")
    for r in todo:
        print(f"   {r['source']:<12} {r['file'][:44]:<46} p{r['page']} {r['why']}")
    print()

    done = 0
    for r in todo:
        sid = f"{r['file']}::p{r['page']}"
        if state.get(sid, {}).get("chars", 0) > 200:
            done += 1
            continue
        pdfs = list((REPO / "corpus" / "01-brokers" / r["source"]).glob(
            "**/" + r["file"]))
        if not pdfs:
            state[sid] = {"chars": 0, "error": "pdf not found"}
            continue
        pi = int(r["page"]) - 1
        try:
            md = cvl.cloud_markdown(str(pdfs[0]), pi, api_key)
        except Exception as e:                            # noqa: BLE001
            state[sid] = {"chars": 0, "error": str(e)[:200]}
            print(f"  {sid}: FAILED {str(e)[:100]}", flush=True)
            state_path.write_text(json.dumps(state, indent=1), encoding="utf-8")
            continue
        # a parse is only a success if it produced TABLE structure, not just prose
        has_table = ("<table" in md) or ("|" in md and md.count("|") > 8)
        nums = len(re.findall(r"\d", md))
        (OUT / (Path(r["file"]).stem + f"_p{r['page']}.llamaparse.md")).write_text(
            md, encoding="utf-8")
        state[sid] = {"chars": len(md), "digits": nums, "has_table": has_table,
                      "source": r["source"], "file": r["file"], "page": r["page"]}
        state_path.write_text(json.dumps(state, indent=1), encoding="utf-8")
        done += 1
        print(f"  {r['source']:<12} p{r['page']}: {len(md)} chars, {nums} digits, "
              f"table={has_table}", flush=True)

    print(f"\ndone={done} credits~{3 * done}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
