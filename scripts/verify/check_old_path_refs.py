"""
check_old_path_refs.py - fast reference check using git grep.

Any TRACKED file (any type) that still names a moved path in a functional way.
git grep is used because it searches only tracked content and respects
.gitignore, so it is both fast and correct for "does anything still point here".

Usage:
    python scripts/verify/check_old_path_refs.py          # report
    python scripts/verify/check_old_path_refs.py --strict # exit 1 on any hit
"""

from __future__ import annotations

import re
import subprocess
import sys

# old paths that were migrated
OLD = [
    "reports/shipbrokers", "reports/broker_reports", "reports/hellenic",
    "reports/breakwave", "reports/drybulk", "reports/tankers", "reports/poten",
    "reports/seabrokers", "reports/drewry", "reports/signal", "reports/baltic",
    "reports/panama_canal", "reports/fearnleys/", "reports/fearnleys_reports_catalog",
    "reports/seabrokers_catalog", "scripts/drewry_ais_pdfs", "scratch/ppa_pdf",
]

# The 2 catalogs under data/reports/ are the AUTHORITATIVE live copies - not moved.
ALLOW = (
    "data/reports/fearnleys_reports_catalog.json",
    "data/reports/seabrokers_catalog.json",
)


def main() -> int:
    strict = "--strict" in sys.argv
    hits = 0
    functional = 0
    for term in OLD:
        pat = re.escape(term)
        r = subprocess.run(
            ["git", "grep", "-n", "-I", "-E", pat, "--", "."],
            capture_output=True, text=True, errors="ignore",
        )
        lines = [ln for ln in r.stdout.splitlines() if ln.strip()]
        lines = [ln for ln in lines if not any(a in ln for a in ALLOW)]
        if not lines:
            continue
        print(f"\n=== {term} : {len(lines)} hit(s) ===")
        for ln in lines[:12]:
            # classify: comment/docstring vs real code
            body = ln.split(":", 2)[-1].strip()
            is_comment = body.startswith("#") or body.startswith("*") or body.startswith('"""')
            tag = "comment" if is_comment else "CODE?"
            if not is_comment:
                functional += 1
            hits += 1
            print(f"   [{tag:<8}] {ln[:120]}")
        if len(lines) > 12:
            print(f"   ... and {len(lines) - 12} more")

    print(f"\ntotal hits: {hits}   non-comment (needs review): {functional}")
    if strict and functional:
        print("FAIL: functional references to moved paths remain")
        return 1
    print("OK: no functional references to moved paths" if not functional
          else "REVIEW the CODE? lines above")
    return 0


if __name__ == "__main__":
    sys.exit(main())
