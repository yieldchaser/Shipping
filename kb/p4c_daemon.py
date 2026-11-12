"""P4c bulk daemon: keep the free Ultrafast run moving across the gateway's daily output quota.

DESIGN NOTE (plan §7.5 "partial coverage beats lower quality", §10.3, C1 owner reply 1)
The free route publishes an output-token ceiling per UTC day, so the bulk pass cannot finish in one
sitting: it runs until the quota is spent, then the gateway starts refusing or truncating calls.
This driver runs the resumable bulk pass in fixed shards, measures output tokens added and errors
recorded from the ledger after every shard, and when a shard is mostly errors it sleeps until the
next UTC midnight (quota reset) before resuming. Nothing is re-billed: `p4c_run.pending` skips every
pack that already has a stored raw, so the driver is safe to kill and restart at any moment. It is
deliberately dumb - one pass name, one model, one retry cadence - so the run state stays legible in
`kb/state/p4c/run_<pass>.json` and in the ledger.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path

KB = Path(__file__).resolve().parent
sys.path.insert(0, str(KB))

import p4b_run as B  # noqa: E402
import p4c_run as PR  # noqa: E402
import runner as R  # noqa: E402

OUT = PR.OUT
QUOTA_OUT_TOKENS = 4_700_000   # stay under the 4.8M/day gateway ceiling
CHUNK_PACKS = 400              # packs per invocation: ~33 min at 12 calls/min
STALL_ERROR_RATE = 0.50        # a shard this broken means the daily quota is gone
STALL_SLEEP_S = 20 * 60        # back-off before re-testing a possibly non-quota outage
RESET_MARGIN_S = 5 * 60


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def next_utc_midnight() -> dt.datetime:
    now = utc_now()
    return (now + dt.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)


def done_n(pass_name: str) -> int:
    d = R.RAW / pass_name
    return sum(1 for _ in d.glob("*.json")) if d.exists() else 0


def total_packs(packs_path: Path) -> int:
    n = 0
    with packs_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                n += 1
    return n


def _ledger_day_utc() -> str:
    return utc_now().strftime("%Y-%m-%d")


def day_out_tokens(model: str) -> int:
    con = R.connect()
    try:
        row = con.execute("SELECT COALESCE(SUM(out_tok),0) FROM jobs WHERE model=? AND substr("
                          "created_at,1,10)=?", [model, _ledger_day_utc()]).fetchone()
    finally:
        con.close()
    return int(row[0] or 0)


def ledger_errors(pass_name: str, since_iso: str) -> int:
    con = R.connect()
    try:
        row = con.execute("SELECT COUNT(*) FROM jobs WHERE pass=? AND created_at>=? AND status!='ok'",
                          [pass_name, since_iso]).fetchone()
    finally:
        con.close()
    return int(row[0] or 0)


def sleep_until(ts: dt.datetime) -> None:
    while True:
        left = (ts - utc_now()).total_seconds()
        if left <= 0:
            return
        print(f"sleeping {left / 60:.0f} min until {ts.strftime('%Y-%m-%dT%H:%MZ')}", flush=True)
        time.sleep(min(left, 1800))


def run(pass_name: str, model: str, packs_path: Path, quota: int, chunk: int,
        shard: int, cap: float, job_maker=None) -> int:
    if not B.load_modes().get(model):
        raise SystemExit(f"no transport mode for {model}: run the p4c transport preflight first")
    total = total_packs(packs_path)
    print(f"[start] pass {pass_name} model {model} packs {total} done {done_n(pass_name)} "
          f"quota {quota}/day", flush=True)
    round_no = 0
    while True:
        have = done_n(pass_name)
        if have >= total:
            print(f"[done] {have}/{total} packs have a stored raw", flush=True)
            return 0
        round_no += 1
        t0 = utc_now()
        before_out = day_out_tokens(model)
        st = PR.run_packs(pass_name, model, cap, packs_path=packs_path, limit=chunk, shard=shard,
                          job_maker=job_maker)
        added_out = day_out_tokens(model) - before_out
        errs = ledger_errors(pass_name, t0.isoformat(timespec="seconds"))
        attempted = max(1, st["packs"])
        print(f"[round {round_no}] attempted {st['packs']} packs, out_tok +{added_out}, "
              f"errors {errs}, day_out {day_out_tokens(model)}, done {done_n(pass_name)}/{total}",
              flush=True)
        if st["packs"] == 0:
            # nothing pending in the window but the pass is not finished: shard window was all cached
            print("[warn] window had no pending packs; continuing from the next window", flush=True)
            continue
        broke = errs / attempted > STALL_ERROR_RATE
        quota_gone = day_out_tokens(model) >= quota
        if broke or quota_gone:
            nm = next_utc_midnight()
            if (nm - utc_now()).total_seconds() > STALL_SLEEP_S * 3:
                # early in the UTC day and already broken: retry after a short back-off first
                print(f"[stall] errors {errs}/{attempted}, day_out {day_out_tokens(model)}; "
                      f"backing off {STALL_SLEEP_S // 60} min", flush=True)
                time.sleep(STALL_SLEEP_S)
            else:
                sleep_until(nm + dt.timedelta(seconds=RESET_MARGIN_S))
        _ = cap


def main() -> int:
    ap = argparse.ArgumentParser(description="P4c: daily-quota-aware bulk driver")
    ap.add_argument("--pass", dest="pass_name", default=PR.BULK_PASS)
    ap.add_argument("--model", default="deepseek-v4.1-flash-1017-ultrafast")
    ap.add_argument("--packs", default=str(PR.PACKS))
    ap.add_argument("--quota", type=int, default=QUOTA_OUT_TOKENS)
    ap.add_argument("--chunk", type=int, default=CHUNK_PACKS)
    ap.add_argument("--shard", type=int, default=PR.SHARD)
    ap.add_argument("--cap", type=float, default=None)
    ap.add_argument("--glean", action="store_true",
                    help="D11 gleaning pass over the packs that already have bulk raws")
    ap.add_argument("--bulk-model", default=None,
                    help="bulk model whose raws seed <first_pass_records> (with --glean)")
    args = ap.parse_args()
    cap = args.cap if args.cap is not None else max(0.0, B.PIPELINE_CAP - R.spent())
    if args.glean:
        import p4c_glean as GL
        bulk_model = args.bulk_model or args.model
        bulk_mode = B.load_modes().get(bulk_model)
        if not bulk_mode:
            raise SystemExit(f"no transport mode for the bulk model {bulk_model}")
        job_maker = GL.job_maker(bulk_model, bulk_mode)
        packs = Path(args.packs)
        if packs == PR.PACKS or not packs.exists():
            packs = GL.GLEAN_PACKS
        if not packs.exists():
            raise SystemExit(f"no glean pack list {packs}: run "
                             f"`python kb/p4c_glean.py --prepare` after the bulk pass")
        return run(GL.GLEAN_PASS, args.model, packs, args.quota, args.chunk, args.shard, cap,
                   job_maker=job_maker)
    return run(args.pass_name, args.model, Path(args.packs), args.quota, args.chunk,
               args.shard, cap)


if __name__ == "__main__":
    raise SystemExit(main())
