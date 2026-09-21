"""Regression ratchet for the pytest suite.

Why this exists
---------------
No workflow ran pytest. The suite had never executed in CI, so 25 pre-existing
failures sat invisible while the only tests CI did run - three in
etf_holdings_update.yml - had been broken by a file move and were dying with
ModuleNotFoundError, which nobody saw either because that job was already red.

Turning the whole suite red is not useful: the 25 are a real backlog, authored
as documentation of known-bad state (their docstrings literally cite baselines
like "baseline: 13 accents / 63 glows / 16 blurs / 11 emoji"). What matters is
that the number never gets WORSE.

So this records the current failure count as a baseline and fails only on
regression. It ratchets: when the count improves the baseline moves down and
never back up. Existing debt is documented; new debt is caught immediately.

Usage:
    python scripts/verify/test_health.py            # compare, ratchet
    python scripts/verify/test_health.py --update   # force the baseline down
    python scripts/verify/test_health.py --test-path tests/test_ui_tabs.py
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BASELINE = os.path.join(ROOT, "knowledge", "manifests", "test_health_baseline.json")

SUMMARY = re.compile(
    r"(?:(?P<failed>\d+) failed)?"
    r"(?:, )?(?:(?P<passed>\d+) passed)?"
    r"(?:, )?(?:(?P<error>\d+) error)?"
)


def parse_counts(output: str) -> dict[str, int] | None:
    """Pull the tallies out of pytest's final summary line.

    Returns None when no summary line exists at all. That distinction matters:
    a missing pytest, a collection error or a crashed run produces no summary,
    and treating that as "0 failures" once recorded a baseline of 0 from a run
    where pytest never started - which would make every later run look like a
    regression. A failed measurement must never become a baseline.
    """
    counts = {"passed": 0, "failed": 0, "error": 0}
    for line in reversed(output.strip().splitlines()):
        line = line.strip().strip("=").strip()
        if not re.search(r"\d+ (passed|failed|error)", line):
            continue
        for key in counts:
            m = re.search(rf"(\d+) {key}", line)
            if m:
                counts[key] = int(m.group(1))
        return counts
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--update", action="store_true", help="accept the current count as the baseline")
    ap.add_argument("--test-path", default="tests/")
    a = ap.parse_args()

    cmd = [sys.executable, "-m", "pytest", a.test_path, "-q", "--no-header", "-p", "no:cacheprovider"]
    print(f"$ {' '.join(cmd)}", flush=True)
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    output = (proc.stdout or "") + (proc.stderr or "")
    tail = "\n".join(output.strip().splitlines()[-3:])
    print(tail, flush=True)

    counts = parse_counts(output)
    if counts is None:
        print("::error::Could not measure the suite: pytest produced no summary line.", flush=True)
        print(tail, flush=True)
        print("Refusing to touch the baseline. Fix the run first.", flush=True)
        return 2
    if counts["passed"] + counts["failed"] + counts["error"] == 0:
        print("::error::pytest collected no tests. Refusing to touch the baseline.", flush=True)
        print(tail, flush=True)
        return 2
    failing = counts["failed"] + counts["error"]
    print(f"\nmeasured: {counts['passed']} passed, {failing} failing "
          f"({counts['failed']} failed + {counts['error']} error)", flush=True)

    baseline = None
    if os.path.exists(BASELINE):
        try:
            baseline = json.loads(open(BASELINE, encoding="utf-8").read())
        except (OSError, json.JSONDecodeError):
            baseline = None

    def write_baseline(n: int) -> None:
        os.makedirs(os.path.dirname(BASELINE), exist_ok=True)
        payload = {"known_failing": n, "test_path": a.test_path, "measured_passed": counts["passed"]}
        with open(BASELINE, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(payload, indent=1) + "\n")

    if baseline is None:
        write_baseline(failing)
        print(f"no baseline existed; recorded {failing} as the baseline.", flush=True)
        return 0

    known = int(baseline.get("known_failing", 0))
    print(f"baseline: {known} failing", flush=True)

    if a.update or failing < known:
        if failing < known:
            print(f"IMPROVED: {known} -> {failing}. Ratcheting the baseline down.", flush=True)
        write_baseline(failing)
        return 0

    if failing > known:
        print(f"::error::REGRESSION: {failing} failing vs {known} known. "
              f"{failing - known} new failure(s).", flush=True)
        for line in output.splitlines():
            if line.startswith("FAILED") or line.startswith("ERROR"):
                print("  " + line, flush=True)
        return 1

    print(f"no regression ({failing} failing, unchanged).", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
