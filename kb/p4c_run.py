"""P4c step 3: run the bulk extraction over the whole frozen prose scope (plan §7, §10.3).

Streaming + resumable: packs are read one batch at a time from `packs.jsonl` so 21k packs never sit
in RAM together, and the runner's ledger + stored raws mean a killed run resumes at the batch that
was in flight. Every batch prints real ledger spend so the pipeline budget is visible while running;
the catch-up ladder (same-model single chunk calls, then a stronger escalation model) is a separate
command so a failed transport night never needs the bulk pass to be re-billed.

Model choice is a parameter, not a constant: the bulk/escalation models are decided at checkpoint C1
and recorded in `kb/reports/p4c.json`; the code refuses to run without a transport mode that the
preflight wrote, so a shape that was never tested cannot silently start a 21k-call run.
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

import p4b_run as B  # noqa: E402  (same prompts, job keys and transport policy as the bake-off)
import runner as R  # noqa: E402

OUT = KB.parent / "kb/state/p4c"
PACKS = OUT / "packs.jsonl"
MODE_FILE = OUT / "modes.json"


def state_path(pass_name: str) -> Path:
    """Per-pass run state so the bulk pass and each rung of the ladder keep their own timings."""
    return OUT / f"run_{pass_name}.json"

FULL_SCOPE_CHUNKS = 86607  # plan §7.1 prose-only scope, frozen by scope_P0_5.json
BULK_PASS = "p4c_bulk"
RETRY_PASS = "p4c_bulk_retry"
ESC_PASS = "p4c_esc"
SHARD = 200  # packs per batch: 200 x ~4 chunks ~= 800 chunks, ~5 min at the free-tier rate
UNTIL_DONE_RESERVE = 0.0


def load_modes() -> dict:
    try:
        return json.loads(MODE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_modes(modes: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    MODE_FILE.write_text(json.dumps(modes, indent=2, sort_keys=True), encoding="utf-8")


def load_packs(path: Path | None = None):
    path = path or PACKS
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                yield json.loads(line)


def batches(packs, size: int = SHARD):
    batch = []
    for pack in packs:
        batch.append(pack)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def has_raw(pass_name: str, model: str, mode: str, pack: dict) -> bool:
    return B.load_result(pass_name, B.make_job(pass_name, model, mode, pack)) is not None


def pending(batch: list[dict], pass_name: str, model: str, mode: str) -> list[dict]:
    """Drop packs that already have a stored raw for this pass/model/mode (resume without a re-bill)."""
    return [p for p in batch if not has_raw(pass_name, model, mode, p)]


def pack_shards(packs_path: Path, limit: int = 0, shard: int = SHARD, start: int = 0):
    """Yield (batch, chunks_in_batch, batch_no, pack_offset) lazily so memory stays flat.

    `start` skips whole batches that end at or before that pack offset, so a driver can walk the
    scope in resumable windows without rescanning from pack 1 every round (and without spinning on
    an all-cached window). `pack_offset` is the 0-based pack index where the yielded batch begins.
    """
    n = 0
    taken = 0
    seen = 0
    for batch in batches(load_packs(packs_path), shard):
        n += 1
        base = seen
        seen += len(batch)
        if seen <= start:
            continue
        taken += len(batch)
        yield batch, sum(len(p["chunk_ids"]) for p in batch), n, base
        if limit and taken >= limit:
            break


def run_packs(pass_name: str, model: str, cap: float, packs_path: Path | None = None,
              limit: int = 0, shard: int = SHARD, progress: bool = True,
              job_maker=None, start: int = 0) -> dict:
    """Run the packed bulk calls for one pass/model. Resumable; returns run metadata.

    `start` is the pack offset to resume from (whole batches only); the returned `start_next` is
    the offset just past the last batch this call looked at, so a driver can advance its window
    even when every pack in it was already cached.

    `job_maker(pass_name, model, mode, pack)` lets a derived pass (gleaning) send a different user
    message while keeping the same ledger key: the key is built from pass name + model + transport
    variant + pack key, so raw paths stay derivable by `p4c_gate.raw_for`.
    """
    make = job_maker or B.make_job
    modes = load_modes()
    mode = modes.get(model)
    if not mode:
        raise SystemExit(
            f"no transport mode for {model} in {MODE_FILE}: run the P4c transport preflight first "
            f"(python -m kb.p4c_preflight)")
    runner = B.runner_for(pass_name, model, cap)
    st = {"pass": pass_name, "model": model, "mode": mode, "packs": 0, "packs_skipped": 0,
          "chunks": 0, "chunks_skipped": 0, "wall_s": 0.0, "cost_usd": 0.0,
          "started": dt.datetime.now().isoformat(timespec="seconds"), "finished": None,
          "batches": 0, "start": start, "start_next": start}
    t0 = time.time()
    total_chunks = FULL_SCOPE_CHUNKS if not limit else 0
    for batch, chunks, n, base in pack_shards(packs_path or PACKS, limit=limit, shard=shard,
                                              start=start):
        st["start_next"] = base + len(batch)
        todo = pending(batch, pass_name, model, mode)
        st["packs"] += len(todo)
        st["chunks"] += sum(len(p["chunk_ids"]) for p in todo)
        st["packs_skipped"] += len(batch) - len(todo)
        st["chunks_skipped"] += chunks - sum(len(p["chunk_ids"]) for p in todo)
        st["batches"] += 1
        spent_before = R.spent(passes=[pass_name])
        if todo:
            jobs = [make(pass_name, model, mode, p) for p in todo]
            runner.run(jobs)
        cost = round(R.spent(passes=[pass_name]), 6)
        st["cost_usd"] = cost
        st["wall_s"] = round(time.time() - t0, 1)
        done_chunks = max(1, st["chunks"] + st["chunks_skipped"])
        rate = done_chunks / max(1.0, st["wall_s"])
        eta_h = (total_chunks - done_chunks) / rate / 3600 if total_chunks else None
        if progress:
            print(f"batch {st['batches']} packs {len(todo)}/{len(batch)} "
                  f"chunks_done {done_chunks}/{total_chunks or '?'} "
                  f"spend ${cost:.4f} (+${cost - spent_before:.4f}) wall {st['wall_s']:.0f}s"
                  + (f" eta {eta_h:.1f}h" if eta_h is not None else ""), flush=True)
            state_path(pass_name).write_text(json.dumps({**st, "updated": dt.datetime.now().isoformat(
                timespec="seconds"), "spent_total": st["cost_usd"]}, indent=2), encoding="utf-8")
    st["finished"] = dt.datetime.now().isoformat(timespec="seconds")
    st["wall_s"] = round(time.time() - t0, 1)
    st["cost_usd"] = round(R.spent(passes=[pass_name]), 6)
    st["rate_packs_per_min"] = round(st["packs"] / max(1e-9, st["wall_s"] / 60), 2)
    state_path(pass_name).write_text(json.dumps(st, indent=2), encoding="utf-8")
    return st


# --- escalation ladder ----------------------------------------------------------------------
def single_pack(pack: dict, cid: str, n: int = 0) -> dict:
    """One chunk from a packed call, in the same pack shape so prompts/job keys stay canonical."""
    idx = pack["chunk_ids"].index(cid)
    block = pack["blocks"][idx]
    return {"n": n, "pack_id": f"s{n:06d}", "doc_id": pack["doc_id"],
            "ord_first": pack.get("ord_first", 0), "key": f"{pack['doc_id']}|{cid}",
            "chunk_ids": [cid], "tokens": pack.get("tokens", 0), "doc": pack["doc"],
            "year": pack.get("year"), "section_class": pack.get("section_class"),
            "blocks": [{"cid": block["cid"], "sentences": block["sentences"]}],
            "known": pack.get("known") or [], "known_ids": pack.get("known_ids") or []}


def singles_for(pack: dict, failed: dict[str, list[str]]) -> list[dict]:
    return [single_pack(pack, cid, n) for n, cid in enumerate(pack["chunk_ids"]) if cid in failed]


def load_failures(path: Path) -> dict[str, list[str]]:
    """{doc_id: [failed chunk_id, ...]} from a p4c_gate failures.jsonl."""
    out: dict[str, list[str]] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        raise SystemExit(f"no failure queue at {path}: run the gate first")
    for line in lines:
        if not line.strip():
            continue
        row = json.loads(line)
        out.setdefault(row.get("doc_id") or "", []).append(row["chunk_id"])
    return out


def plan_escalation(packs_path: Path, failures_path: Path, out_path: Path) -> dict:
    """Write one single-chunk pack per failed chunk (same doc/section prompts as the bulk call)."""
    failed = load_failures(failures_path)
    wanted = {cid for cids in failed.values() for cid in cids}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with out_path.open("w", encoding="utf-8") as fh:
        for pack in load_packs(packs_path):
            hit = [cid for cid in pack["chunk_ids"] if cid in wanted]
            if not hit:
                continue
            for sp in singles_for(pack, {cid: [] for cid in hit}):
                sp["n"] = written
                sp["pack_id"] = f"s{written:06d}"
                fh.write(json.dumps(sp, ensure_ascii=False) + "\n")
                written += 1
    missing = len(wanted) - written
    st = {"failed_chunks": len(wanted), "singles": written, "unmatched": missing,
          "out": str(out_path)}
    (out_path.parent / "escalation_plan.json").write_text(json.dumps(st, indent=2), encoding="utf-8")
    return st


def cmd_run(args) -> int:
    packs = Path(args.packs) if args.packs else PACKS
    cap = args.cap if args.cap is not None else max(0.0, B.PIPELINE_CAP - R.spent())
    st = run_packs(args.pass_name, args.model, cap, packs_path=packs, limit=args.limit,
                   shard=args.shard)
    print(json.dumps({k: st[k] for k in ("pass", "model", "mode", "packs", "packs_skipped",
                                        "chunks", "chunks_skipped", "cost_usd", "wall_s")},
                     indent=2))
    return 0


def cmd_escalate(args) -> int:
    out_path = OUT / f"singles_{args.pass_name}.jsonl"
    st = plan_escalation(Path(args.packs) if args.packs else PACKS,
                         Path(args.failures), out_path)
    print(json.dumps(st, indent=2))
    if args.plan_only:
        return 0
    cap = args.cap if args.cap is not None else max(0.0, B.PIPELINE_CAP - R.spent())
    run = run_packs(args.pass_name, args.model, cap, packs_path=out_path, shard=args.shard)
    print(json.dumps({k: run[k] for k in ("packs", "chunks", "cost_usd", "wall_s")}, indent=2))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="P4c: bulk extraction over the frozen prose scope")
    ap.add_argument("--run", action="store_true", help="run the packed bulk pass")
    ap.add_argument("--escalate", action="store_true", help="single-chunk retries for the failure queue")
    ap.add_argument("--pass", dest="pass_name", default=BULK_PASS)
    ap.add_argument("--model", required=True)
    ap.add_argument("--packs", default=None)
    ap.add_argument("--failures", default=str(OUT / "failures.jsonl"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--shard", type=int, default=SHARD)
    ap.add_argument("--cap", type=float, default=None)
    ap.add_argument("--plan-only", action="store_true")
    args = ap.parse_args()
    if args.escalate:
        return cmd_escalate(args)
    return cmd_run(args)


if __name__ == "__main__":
    raise SystemExit(main())

