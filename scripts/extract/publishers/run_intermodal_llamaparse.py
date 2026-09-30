"""
Intermodal Weekly - LlamaParse High-Fidelity Extraction Runner
Parses pages 4, 5, 6 (0-indexed target_pages='3,4,5') across 252 Intermodal reports
using LlamaParse 'cost_effective' tier to extract Secondhand Sales, Newbuilding,
and Demolition tables.
"""

import argparse
import concurrent.futures
import json
import os
import pathlib
import time
from typing import Dict, Any, List

from llama_parse import LlamaParse

API_KEY = os.environ.get("LLAMA_CLOUD_API_KEY", "llx-AVMBvb0UULqQGzWhFFJScQpwhrTM8hSVMZvjz4PEGQ9utg1P")
ROOT = pathlib.Path(__file__).resolve().parents[3]
CORPUS_DIR = ROOT / "corpus" / "01-brokers" / "intermodal"
OUT_DIR = ROOT / "data" / "extracted" / "llamaparse_intermodal"
STATE_FILE = OUT_DIR / "_run_state.json"


def load_state() -> Dict[str, Any]:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"done": {}, "failed": {}, "pages_parsed": 0, "credits_estimated": 0}


def save_state(state: Dict[str, Any]):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def parse_single_pdf(pdf_path: pathlib.Path, tier: str = "cost_effective") -> Dict[str, Any]:
    stem = pdf_path.stem
    out_md = OUT_DIR / f"{stem}.md"
    if out_md.exists() and out_md.stat().st_size > 100:
        return {"stem": stem, "status": "cached", "bytes": out_md.stat().st_size, "pages": 3}

    parser = LlamaParse(
        api_key=API_KEY,
        result_type="markdown",
        target_pages="3,4,5",  # 0-indexed: pages 4, 5, 6
        tier=tier,
        version="latest",
        verbose=False,
    )

    docs = parser.load_data(str(pdf_path))
    full_text = "\n\n--- PAGE BREAK ---\n\n".join(d.text for d in docs)
    out_md.write_text(full_text, encoding="utf-8")

    return {"stem": stem, "status": "ok", "bytes": len(full_text), "pages": len(docs)}


def main():
    parser = argparse.ArgumentParser(description="Intermodal LlamaParse Runner")
    parser.add_argument("--limit", type=int, default=0, help="Max reports to parse (0 for all)")
    parser.add_argument("--workers", type=int, default=4, help="Parallel worker threads")
    parser.add_argument("--tier", type=str, default="cost_effective", choices=["fast", "cost_effective", "agentic"])
    parser.add_argument("--status", action="store_true", help="Print parsing status")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    state = load_state()

    if args.status:
        done_count = len(state.get("done", {}))
        fail_count = len(state.get("failed", {}))
        pages = state.get("pages_parsed", 0)
        credits_est = state.get("credits_estimated", 0)
        print(f"Intermodal LlamaParse Status:")
        print(f"  Docs done: {done_count}")
        print(f"  Docs failed: {fail_count}")
        print(f"  Pages parsed: {pages}")
        print(f"  Estimated credits used: {credits_est}")
        return

    all_pdfs = sorted(CORPUS_DIR.rglob("*.pdf"))
    todo_pdfs = [p for p in all_pdfs if p.stem not in state.get("done", {})]

    if args.limit > 0:
        todo_pdfs = todo_pdfs[:args.limit]

    print(f"[intermodal_llamaparse] Found {len(all_pdfs)} total PDFs. Remaining: {len(todo_pdfs)}. Using {args.workers} workers, tier={args.tier}...")

    cost_per_page = 3 if args.tier == "cost_effective" else (18 if args.tier == "agentic" else 1)
    t0 = time.time()
    ok_count = 0
    fail_count = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_to_pdf = {executor.submit(parse_single_pdf, p, args.tier): p for p in todo_pdfs}
        for idx, future in enumerate(concurrent.futures.as_completed(future_to_pdf), 1):
            p = future_to_pdf[future]
            stem = p.stem
            try:
                res = future.result()
                pages_cnt = res.get("pages", 3)
                state["done"][stem] = {
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "pages": pages_cnt,
                    "bytes": res.get("bytes", 0),
                    "tier": args.tier
                }
                state["pages_parsed"] = state.get("pages_parsed", 0) + pages_cnt
                state["credits_estimated"] = state.get("credits_estimated", 0) + (pages_cnt * cost_per_page)
                ok_count += 1
                print(f"  [{idx}/{len(todo_pdfs)}] {stem[:45]:<45} OK (pages={pages_cnt}, {res.get('bytes', 0):,} bytes, elapsed: {time.time()-t0:.1f}s)", flush=True)
            except Exception as e:
                fail_count += 1
                state["failed"][stem] = str(e)
                print(f"  [{idx}/{len(todo_pdfs)}] {stem[:45]:<45} FAILED: {type(e).__name__}: {e}", flush=True)

            if idx % 5 == 0 or idx == len(todo_pdfs):
                save_state(state)

    save_state(state)
    print(f"\n[intermodal_llamaparse] Completed run: {ok_count} OK, {fail_count} failed in {time.time()-t0:.1f}s. Total done so far: {len(state['done'])}/{len(all_pdfs)}.")


if __name__ == "__main__":
    main()
