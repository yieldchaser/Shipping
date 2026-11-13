"""P4c bulk daemon: keep the free bulk run moving across provider throttling and daily quotas.

DESIGN NOTE (plan §7.5 "partial coverage beats lower quality", §10.3, C1 owner reply 1)
The bulk pass is free but throttled, so it cannot finish in one sitting. Two regimes:
  * Ultrafast publishes an output-token ceiling per UTC day (4.7M): it runs until the quota is spent,
    then the gateway refuses/truncates calls. This driver runs the resumable bulk pass in fixed
    shards, measures output tokens added and errors recorded from the ledger after every shard, and
    when a shard is mostly errors it sleeps until the next UTC midnight (quota reset) before resuming.
  * AMD Token Lab (owner amendment to D10, 2026-11-13) has no output-token ceiling but a hard
    per-key request quota: a 3x16-call ladder at 7.5/12/20 rpm succeeded 9/16, 8/16, 7/16 times, so
    roughly every other call needs the runner's retry ladder. There is nothing to wait for at
    midnight, so `--quota 0` disables the daily-quota branch and a much higher stall threshold is
    used: sustained failure there means the pool itself is down, not a spent quota.
Nothing is re-billed: `p4c_run.pending` skips every pack that already has a stored raw, so the driver
is safe to kill and restart at any moment. It is deliberately dumb - one pass name, one model, one
retry cadence - so the run state stays legible in `kb/state/p4c/run_<pass>.json` and in the ledger.
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


def ledger_now() -> dt.datetime:
    """Naive local clock, matching how `kb/runner.py` stamps `jobs.created_at`.

    The ledger column is written with `time.strftime("%Y-%m-%dT%H:%M:%S")` — naive local time, no
    offset. Comparing it against a UTC ISO string is not merely off by the zone offset: the two
    strings disagree on the date, so `created_at >= t0` matched *all* of the day's rows, including
    the previous run's, and `substr(created_at,1,10)` never equalled the UTC date. That made the
    stall detector fire spuriously (`errors 223/400` when only 67 rows were `error`) and reported
    `day_out_tokens` as 0 forever. Every ledger-derived measurement uses this clock.
    """
    return dt.datetime.now()


def now() -> dt.datetime:
    return ledger_now()


def next_midnight() -> dt.datetime:
    """Next local midnight — the boundary of the day bucket the ledger actually stores."""
    return (ledger_now() + dt.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)


def done_n(pass_name: str, model: str = "") -> int:
    """Packs with a successful stored raw for this pass *and* model.

    Counted from the ledger, not from the raw directory: `kb/state/raw/p4c_bulk` also holds the
    earlier free-Ultrafast raws of the same pass, and a directory count would report the AMD run as
    nearly finished before it had sent a single call.

    Truncated answers are excluded: the runner records `status='ok'` with `finish_reason='length'`
    for a response the provider cut off at `max_tokens`, which is unusable and must be re-requested
    (plan §7.4 gate 1). Counting them as done would also mask the re-key that a raised cap causes
    (`p4b_run.key_variant` embeds `mt{max_tokens}`, so a cap change orphans every stored raw).
    """
    con = R.connect()
    try:
        sql = ("SELECT COUNT(DISTINCT job_key) FROM jobs WHERE pass=? AND status='ok' "
               "AND COALESCE(finish_reason,'')!='length'")
        params: list = [pass_name]
        if model:
            sql += " AND model=?"
            params.append(model)
        return int(con.execute(sql, params).fetchone()[0] or 0)
    finally:
        con.close()


def scope_done(pass_name: str, model: str, packs_path: Path) -> int:
    """Key-exact count of packs in the scope with a usable raw for this pass/model.

    `done_n` counts ledger rows by pass+model, which survives a job-key change and would therefore
    over-report a pass whose cap was raised (see `p4c_run.done_packs`). This is the completion test
    the loop actually uses.
    """
    mode = PR.load_modes().get(model)
    if not mode:
        return done_n(pass_name, model)
    return PR.done_packs(pass_name, model, mode, packs_path=packs_path)


def total_packs(packs_path: Path) -> int:
    n = 0
    with packs_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                n += 1
    return n


def _ledger_day() -> str:
    return ledger_now().strftime("%Y-%m-%d")


def day_out_tokens(model: str) -> int:
    con = R.connect()
    try:
        row = con.execute("SELECT COALESCE(SUM(out_tok),0) FROM jobs WHERE model=? AND substr("
                          "created_at,1,10)=?", [model, _ledger_day()]).fetchone()
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
        left = (ts - ledger_now()).total_seconds()
        if left <= 0:
            return
        print(f"sleeping {left / 60:.0f} min until {ts.strftime('%Y-%m-%dT%H:%MZ')}", flush=True)
        time.sleep(min(left, 1800))


def run(pass_name: str, model: str, packs_path: Path, quota: int, chunk: int,
        shard: int, cap: float, job_maker=None) -> int:
    if not PR.load_modes().get(model):
        raise SystemExit(
            f"no transport mode for {model} in {PR.MODE_FILE}: run the P4c transport preflight first "
            f"(python -m kb.p4c_preflight)")
    total = total_packs(packs_path)
    print(f"[start] pass {pass_name} model {model} packs {total} done {scope_done(pass_name, model, packs_path)} "
          f"quota {quota}/day", flush=True)
    round_no = 0
    cursor = 0
    while True:
        have = scope_done(pass_name, model, packs_path)
        if have >= total:
            print(f"[done] {have}/{total} packs have a stored raw", flush=True)
            return 0
        round_no += 1
        t0 = ledger_now()
        before_out = day_out_tokens(model)
        st = PR.run_packs(pass_name, model, cap, packs_path=packs_path, limit=chunk, shard=shard,
                          job_maker=job_maker, start=cursor)
        cursor = st.get("start_next", cursor)
        added_out = day_out_tokens(model) - before_out
        errs = ledger_errors(pass_name, t0.isoformat(timespec="seconds"))
        attempted = max(1, st["packs"])
        print(f"[round {round_no}] attempted {st['packs']} packs, out_tok +{added_out}, "
              f"errors {errs}, day_out {day_out_tokens(model)}, "
              f"done {scope_done(pass_name, model, packs_path)}/{total}, "
              f"cursor {cursor}", flush=True)
        if st["packs"] == 0:
            # whole window was already cached: advance instead of spinning on the same packs
            if cursor >= total:
                print("[warn] swept every pack window but the pass is not finished (packs without "
                      "a stored raw); backing off before another sweep", flush=True)
                time.sleep(STALL_SLEEP_S)
                cursor = 0
            else:
                print(f"[info] window fully cached; continuing from pack {cursor}", flush=True)
            continue
        broke = errs / attempted > STALL_ERROR_RATE
        quota_gone = quota > 0 and day_out_tokens(model) >= quota
        if broke or quota_gone:
            if quota <= 0:
                # no daily ceiling (AMD): the pool is just unhealthy, re-test after a back-off
                print(f"[stall] errors {errs}/{attempted}, no quota regime; backing off "
                      f"{STALL_SLEEP_S // 60} min", flush=True)
                time.sleep(STALL_SLEEP_S)
                continue
            nm = next_midnight()
            if (nm - ledger_now()).total_seconds() > STALL_SLEEP_S * 3:
                # early in the ledger day and already broken: retry after a short back-off first
                print(f"[stall] errors {errs}/{attempted}, day_out {day_out_tokens(model)}; "
                      f"backing off {STALL_SLEEP_S // 60} min", flush=True)
                time.sleep(STALL_SLEEP_S)
            else:
                sleep_until(nm + dt.timedelta(seconds=RESET_MARGIN_S))
        _ = cap


def main() -> int:
    ap = argparse.ArgumentParser(description="P4c: daily-quota-aware bulk driver")
    ap.add_argument("--pass", dest="pass_name", default=PR.BULK_PASS)
    ap.add_argument("--model", default="DeepSeek-V4.1-Flash")
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
        bulk_mode = PR.load_modes().get(bulk_model)
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
