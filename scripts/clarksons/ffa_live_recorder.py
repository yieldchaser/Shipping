#!/usr/bin/env python3
"""
ffa_live_recorder.py
====================
Records the live dry-bulk FFA market through the London session so an intraday
move away from the previous SGX settlement is visible before the next settlement.

Every --interval seconds it reads the live screen (fetch_ffa_live_snapshot.fetch)
and, for each of the 20 tenors (Cape/Panamax/Supramax/Handysize x Sep, Oct, Q, Q, Cal):

  data/ffa_live/ticks/YYYY-MM.csv   one row whenever the live price or the SGX
                                    settlement changed (plus the first read of
                                    each UTC day); columns ts_utc,segment,tenor,price,settle
  data/ffa_live/daily.csv           one row per UTC day and tenor: settlement in
                                    force, open/high/low/last live price, times, reads
  data/ffa_live/latest.json         current prices, today's session stats and
                                    today's price path, read by the Broker Desk page

With --push it commits those files straight on top of the current origin/main
every --push-every seconds (only when something changed). The files are written
by this script alone, so the commit never conflicts with other jobs.

Runs until --until (HH:MM UTC) or once with --once.
"""

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_ffa_live_snapshot import build, fetch  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_DIR = REPO_ROOT / "data" / "ffa_live"
TICK_FIELDS = ["ts_utc", "segment", "tenor", "price", "settle"]
DAILY_FIELDS = ["date", "segment", "tenor", "settle", "open", "high", "low", "last",
                "first_ts", "last_ts", "reads", "settle_changes"]


def now_utc():
    return datetime.now(timezone.utc)


def read_csv(path):
    if not path.exists():
        return []
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, path)


class Recorder:
    def __init__(self, out_dir=OUT_DIR):
        self.out = Path(out_dir)
        self.daily_path = self.out / "daily.csv"
        self.latest_path = self.out / "latest.json"
        self.daily = {(r["date"], r["segment"], r["tenor"]): r for r in read_csv(self.daily_path)}
        self.last_tick = {}   # (segment, tenor) -> (date, price, settle) of the last stored tick
        self.session = {}     # (segment, tenor) -> [[ts, price, settle], ...] for today
        self._load_today_ticks()

    def _ticks_path(self, ts):
        return self.out / "ticks" / f"{ts[:7]}.csv"

    def _load_today_ticks(self):
        today = now_utc().strftime("%Y-%m-%d")
        for r in read_csv(self._ticks_path(today)):
            key = (r["segment"], r["tenor"])
            self.last_tick[key] = (r["ts_utc"][:10], float(r["price"]), float(r["settle"]))
            if r["ts_utc"].startswith(today):
                self.session.setdefault(key, []).append([r["ts_utc"], float(r["price"]), float(r["settle"])])

    def record(self, snapshot):
        """Apply one snapshot (fetch_ffa_live_snapshot.build output). Returns True if anything changed."""
        ts = snapshot["fetched_at_utc"]
        day = ts[:10]
        new_ticks = []
        for seg in snapshot["segments"]:
            for t in seg["tenors"]:
                key = (seg["key"], t["name"])
                price, settle = float(t["price"]), float(t["settle"])
                prev = self.last_tick.get(key)
                if prev is None or prev[0] != day or prev[1] != price or prev[2] != settle:
                    new_ticks.append({"ts_utc": ts, "segment": key[0], "tenor": key[1],
                                      "price": f"{price:g}", "settle": f"{settle:g}"})
                    self.last_tick[key] = (day, price, settle)
                    if prev is None or prev[0] != day:
                        self.session[key] = []
                    self.session.setdefault(key, []).append([ts, price, settle])

                d = self.daily.get((day, key[0], key[1]))
                if d is None:
                    d = {"date": day, "segment": key[0], "tenor": key[1], "settle": f"{settle:g}",
                         "open": f"{price:g}", "high": f"{price:g}", "low": f"{price:g}", "last": f"{price:g}",
                         "first_ts": ts, "last_ts": ts, "reads": "0", "settle_changes": "0"}
                    self.daily[(day, key[0], key[1])] = d
                if float(d["settle"]) != settle:
                    d["settle"] = f"{settle:g}"
                    d["settle_changes"] = str(int(d["settle_changes"]) + 1)
                d["high"] = f"{max(float(d['high']), price):g}"
                d["low"] = f"{min(float(d['low']), price):g}"
                d["last"] = f"{price:g}"
                d["last_ts"] = ts
                d["reads"] = str(int(d["reads"]) + 1)

        if new_ticks:
            path = self._ticks_path(ts)
            write_csv(path, TICK_FIELDS, read_csv(path) + new_ticks)
        rows = sorted(self.daily.values(), key=lambda r: (r["date"], r["segment"], r["tenor"]))
        write_csv(self.daily_path, DAILY_FIELDS, rows)
        self._write_latest(snapshot)
        return bool(new_ticks)

    def _write_latest(self, snapshot):
        ts = snapshot["fetched_at_utc"]
        day = ts[:10]
        segments = []
        for seg in snapshot["segments"]:
            tenors = []
            for t in seg["tenors"]:
                key = (seg["key"], t["name"])
                d = self.daily[(day, key[0], key[1])]
                tenors.append({
                    "name": t["name"], "price": t["price"], "settle": t["settle"],
                    "open": float(d["open"]), "high": float(d["high"]), "low": float(d["low"]),
                    "first_ts": d["first_ts"],
                    "path": [[p[0][11:16], p[1]] for p in self.session.get(key, [])],
                })
            segments.append({"key": seg["key"], "label": seg["label"], "tenors": tenors})
        payload = {
            "fetched_at_utc": ts,
            "unit": snapshot["unit"],
            "price_basis": snapshot["price_basis"],
            "settle_basis": snapshot["settle_basis"],
            "session_date": day,
            "segments": segments,
        }
        self.out.mkdir(parents=True, exist_ok=True)
        tmp = self.latest_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, separators=(",", ":")) + "\n", encoding="utf-8")
        os.replace(tmp, self.latest_path)


def git(*args, check=True):
    return subprocess.run(["git", *args], cwd=REPO_ROOT, check=check, capture_output=True, text=True)


def push(message):
    """Commit data/ffa_live on top of the newest origin/main and push; retry on races."""
    for attempt in range(5):
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copytree(OUT_DIR, Path(tmp) / "ffa_live")
            git("fetch", "--depth=1", "origin", "main")
            git("reset", "--hard", "FETCH_HEAD")
            shutil.rmtree(OUT_DIR, ignore_errors=True)
            shutil.copytree(Path(tmp) / "ffa_live", OUT_DIR)
        git("add", "data/ffa_live")
        if git("diff", "--cached", "--quiet", check=False).returncode == 0:
            return True
        git("commit", "-m", message)
        if git("push", "origin", "HEAD:main", check=False).returncode == 0:
            print(f"  pushed ({message})", flush=True)
            return True
        print(f"  push race, retry {attempt + 1}", flush=True)
        time.sleep(5 + 5 * attempt)
    print("  [WARN] push failed after retries; data kept for the next push", flush=True)
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=int, default=120)
    ap.add_argument("--push-every", type=int, default=600)
    ap.add_argument("--until", default=None, help="stop at HH:MM UTC")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--push", action="store_true")
    args = ap.parse_args()
    if args.push and os.environ.get("GITHUB_ACTIONS") != "true":
        # push() hard-resets the checkout onto origin/main; never do that to a working copy.
        ap.error("--push only runs inside GitHub Actions")

    deadline = None
    if args.until:
        hh, mm = map(int, args.until.split(":"))
        deadline = now_utc().replace(hour=hh, minute=mm, second=0, microsecond=0)

    rec = Recorder()
    dirty, last_push, failures, reads = False, time.monotonic(), 0, 0
    while True:
        try:
            snap = build(fetch(), now_utc().strftime("%Y-%m-%dT%H:%M:%SZ"))
            changed = rec.record(snap)
            dirty = dirty or changed
            reads += 1
            failures = 0
            cape = snap["segments"][0]["tenors"][0]
            print(f"{snap['fetched_at_utc']} {'changed' if changed else 'same   '} Cape {cape['name']} {cape['price']:,.0f} vs settle {cape['settle']:,.0f}", flush=True)
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"{now_utc():%H:%M:%S} read failed ({failures}): {exc}", flush=True)

        finished = args.once or (deadline is not None and now_utc() >= deadline)
        if args.push and dirty and (finished or time.monotonic() - last_push >= args.push_every):
            if push(f"data(ffa-live): intraday FFA ticks {now_utc():%Y-%m-%d %H:%M} UTC [skip ci]"):
                dirty = False
                rec = Recorder()  # the reset re-read the files; reload state from them
            last_push = time.monotonic()
        if finished:
            break
        time.sleep(args.interval)

    if reads == 0:
        print("No successful reads this run.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
