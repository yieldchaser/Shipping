"""
Xclusiv Shipbrokers - LlamaParse High-Fidelity Extraction Runner.

Extracts narrative desk commentary, reported sales tables, newbuilding orders,
secondhand valuation matrices, and demolition tables using LlamaParse ('cost_effective' tier).

Target Pages:
  - 9-page weekly reports (2024-2026): '0,3,4,5,6' (0-indexed; pages 1, 4, 5, 6, 7)
    * Page 0 (p1): Market Commentary & 'In a Nutshell'
    * Page 3 (p4): Newbuilding Prices & Newbuilding Orders table
    * Page 4 (p5): Dry S&P Activity prose, Dry Secondhand Prices, Bulker Sales table
    * Page 5 (p6): Tanker S&P Activity prose, Tanker Secondhand Prices, Tanker Sales table
    * Page 6 (p7): Indicative Demolition Scrap Prices & Demo Sales table
  - 7-page weekly reports (2022-2023): '0,3,4'
  - 4-page recycling reports: '0,1,2,3'

Outputs:
  - Full markdown: data/extracted/md/xclusiv/<stem>.md
  - Run state: data/extracted/llamaparse_xclusiv/_run_state.json
  - Table sidecars: data/extracted/md/xclusiv/<stem>.tables.json
"""

import argparse
import concurrent.futures
import json
import os
import pathlib
import sys
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

import pymupdf
from llama_parse import LlamaParse

ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.extract.llama_manager import manager

CORPUS_DIR = ROOT / "corpus" / "01-brokers" / "xclusiv"
OUT_MD_DIR = ROOT / "data" / "extracted" / "md" / "xclusiv"
STATE_DIR = ROOT / "data" / "extracted" / "llamaparse_xclusiv"
STATE_FILE = STATE_DIR / "_run_state.json"

TIER_CREDITS_PER_PAGE = {
    "fast": 1,
    "cost_effective": 3,
    "agentic": 18,
    "agentic_plus": 45,
}

INITIAL_ACCOUNT_CREDITS = 10000
state_lock = threading.Lock()
quota_exceeded_event = threading.Event()


def load_state() -> Dict[str, Any]:
    if STATE_FILE.exists():
        try:
            st = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            if "failed" in st and any("exceeded" in str(v).lower() or "plan" in str(v).lower() for v in st["failed"].values()):
                st["failed"] = {}
            return st
        except Exception:
            pass
    return {
        "done": {},
        "failed": {},
        "pages_parsed": 0,
        "credits_estimated": 0,
        "credits_initial": INITIAL_ACCOUNT_CREDITS,
        "credits_remaining_est": INITIAL_ACCOUNT_CREDITS,
        "tier": "cost_effective",
    }


def save_state(state: Dict[str, Any]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def determine_target_pages(pdf_path: pathlib.Path) -> Tuple[str, int]:
    """Dynamically determine target page indices (0-indexed comma-separated string) and count
    per Shipbroking_Source_Parsing_Notes.docx:
      - Later reports (>=9 pages): First 7 pages (0,1,2,3,4,5,6), discarding the last 2 pages.
      - Earlier reports (7-8 pages): First 5 pages (0,1,2,3,4), discarding the last 2 pages.
      - 6-page reports (2021): First 5 pages (0,1,2,3,4), discarding the last page.
      - <=4 pages: all pages.
    """
    try:
        with pymupdf.open(pdf_path) as doc:
            n_pages = len(doc)
            if n_pages >= 9:
                pages = list(range(7))  # 0 to 6
            elif n_pages in (7, 8):
                pages = list(range(5))  # 0 to 4
            elif n_pages == 6:
                pages = list(range(5))  # 0 to 4
            elif n_pages <= 4:
                pages = list(range(n_pages))
            else:
                pages = list(range(max(1, n_pages - 2)))
            return ",".join(str(i) for i in pages), len(pages)
    except Exception:
        return "0,1,2,3,4,5,6", 7


def is_credit_or_quota_error(err_msg: str) -> bool:
    msg = err_msg.lower()
    indicators = [
        "quota",
        "credit",
        "payment required",
        "402",
        "429",
        "rate limit",
        "insufficient",
        "exceeded",
        "out of credit",
        "plan limit",
    ]
    return any(ind in msg for ind in indicators)


def parse_pdf(
    pdf_path: pathlib.Path,
    tier: str = "cost_effective",
    api_key: Optional[str] = None,
    force: bool = False,
    state: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    stem = pdf_path.stem
    target_pages_str, page_count = determine_target_pages(pdf_path)
    out_file = OUT_MD_DIR / f"{stem}.md"

    # Pre-check if already done with the EXACT required target_pages
    if state and not force:
        done_entry = state.get("done", {}).get(stem)
        if (
            done_entry
            and done_entry.get("target_pages") == target_pages_str
            and out_file.exists()
            and out_file.stat().st_size > 5000
        ):
            content = out_file.read_text(encoding="utf-8", errors="replace")
            if "--- PAGE BREAK ---" in content or "--- Page 1 ---" not in content:
                return {
                    "stem": stem,
                    "status": "cached",
                    "bytes": len(content),
                    "pages": page_count,
                    "target_pages": target_pages_str,
                }

    if quota_exceeded_event.is_set():
        return {
            "stem": stem,
            "status": "aborted",
            "error": "Quota or credit limit reached; aborting parse.",
        }

    t0 = time.time()
    max_retries = 3
    for attempt in range(max_retries):
        try:
            curr_key = api_key or manager.get_current_key()
            parser = LlamaParse(
                api_key=curr_key,
                result_type="markdown",
                target_pages=target_pages_str,
                tier=tier,
                version="latest",
                verbose=False,
            )
            docs = parser.load_data(str(pdf_path))
            full_text = "\n\n--- PAGE BREAK ---\n\n".join(d.text for d in docs)
            elapsed = round(time.time() - t0, 2)

            # Write to primary target location
            OUT_MD_DIR.mkdir(parents=True, exist_ok=True)
            out_file.write_text(full_text, encoding="utf-8")

            # Also save to llamaparse_xclusiv dir for provenance
            STATE_DIR.mkdir(parents=True, exist_ok=True)
            backup_file = STATE_DIR / f"{stem}.md"
            backup_file.write_text(full_text, encoding="utf-8")

            # Extract structured table sidecars
            try:
                from scripts.extract.publishers.run_xclusiv_tables import process_pdf
                process_pdf(pdf_path)
            except Exception as pe:
                pass

            manager.record_success(page_count * TIER_CREDITS_PER_PAGE.get(tier, 3))
            return {
                "stem": stem,
                "status": "ok",
                "bytes": len(full_text),
                "pages": page_count,
                "target_pages": target_pages_str,
                "elapsed_s": elapsed,
            }
        except Exception as e:
            err_str = str(e)
            if is_credit_or_quota_error(err_str):
                try:
                    new_key = manager.mark_key_exhausted(reason=err_str)
                    print(f"Key exhausted! Rotated to next key: {new_key[:12]}...")
                    api_key = new_key
                    continue
                except RuntimeError:
                    quota_exceeded_event.set()
                    return {
                        "stem": stem,
                        "status": "aborted",
                        "error": "ALL LlamaParse API keys exhausted!",
                        "pages": page_count,
                        "target_pages": target_pages_str,
                    }
            return {
                "stem": stem,
                "status": "error",
                "error": err_str,
                "pages": page_count,
                "target_pages": target_pages_str,
            }


def verify_sample(stem: str = "xclusiv_2026_xclusiv-2026_02_24") -> Dict[str, Any]:
    md_file = OUT_MD_DIR / f"{stem}.md"
    if not md_file.exists():
        return {"status": "missing", "details": f"{md_file} not found"}

    text = md_file.read_text(encoding="utf-8", errors="replace")
    checks = {
        "LEICESTER": "LEICESTER" in text,
        "SINGAPORE SPIRIT": "SINGAPORE SPIRIT" in text,
        "NAVE BUENA SUERTE": "NAVE BUENA SUERTE" in text,
        "Tanker Secondhand Prices": "tanker secondhand prices" in text.lower(),
        "Tanker S&P Activity text": "tanker s&p activity" in text.lower(),
        "Market Commentary text": "market commentary" in text.lower(),
        "Dry S&P Activity text": "dry s&p activity" in text.lower(),
    }
    all_passed = all(checks.values())
    return {
        "status": "passed" if all_passed else "failed",
        "stem": stem,
        "checks": checks,
        "chars": len(text),
    }


def main():
    parser = argparse.ArgumentParser(description="Xclusiv LlamaParse Extraction Specialist")
    parser.add_argument("--year", default="2026", help="Year to process (2026, 2025, or all)")
    parser.add_argument("--limit", type=int, default=0, help="Max reports to process (0 = all)")
    parser.add_argument("--workers", type=int, default=3, help="Concurrent worker threads (default: 3)")
    parser.add_argument("--tier", default="cost_effective", choices=list(TIER_CREDITS_PER_PAGE.keys()))
    parser.add_argument("--api-key", default=None, help="LlamaParse API Key (defaults to KeyManager pool)")
    parser.add_argument("--force", action="store_true", help="Force re-extraction of cached files")
    parser.add_argument("--status", action="store_true", help="Print extraction status and exit")
    parser.add_argument("--verify", action="store_true", help="Verify sample report and exit")
    parser.add_argument("--single", type=str, default="", help="Process a single PDF filename or stem")
    args = parser.parse_args()

    state = load_state()

    if args.status:
        done_cnt = len(state.get("done", {}))
        fail_cnt = len(state.get("failed", {}))
        pages = state.get("pages_parsed", 0)
        credits_used = state.get("credits_estimated", 0)
        credits_rem = state.get("credits_remaining_est", INITIAL_ACCOUNT_CREDITS - credits_used)
        print("=" * 60)
        print("XCLUSIV LLAMAPARSE EXTRACTION STATUS:")
        print(f"  Reports Done:         {done_cnt}")
        print(f"  Reports Failed:       {fail_cnt}")
        print(f"  Total Pages Parsed:   {pages}")
        print(f"  Est. Credits Used:    {credits_used}")
        print(f"  Est. Credits Left:    {credits_rem} / {INITIAL_ACCOUNT_CREDITS}")
        print("=" * 60)
        return

    if args.verify:
        res = verify_sample()
        print("SAMPLE VERIFICATION RESULT:")
        print(json.dumps(res, indent=2))
        return

    # Select target PDFs
    target_pdfs: List[pathlib.Path] = []
    if args.single:
        for p in CORPUS_DIR.rglob("*.pdf"):
            if args.single in p.stem or args.single == p.name:
                target_pdfs.append(p)
    elif args.year == "2026":
        target_pdfs = sorted((CORPUS_DIR / "2026").glob("*.pdf"))
    elif args.year == "2025":
        target_pdfs = sorted((CORPUS_DIR / "2025").glob("*.pdf"))
    elif args.year == "all":
        # 2026 first, then 2025, then earlier
        y2026 = sorted((CORPUS_DIR / "2026").glob("*.pdf"))
        y2025 = sorted((CORPUS_DIR / "2025").glob("*.pdf"))
        others = sorted([p for p in CORPUS_DIR.rglob("*.pdf") if p not in y2026 and p not in y2025])
        target_pdfs = y2026 + y2025 + others
    else:
        target_pdfs = sorted((CORPUS_DIR / args.year).glob("*.pdf"))

    print(f"Total PDFs found for year='{args.year}': {len(target_pdfs)}")
    
    # Filter pending: requires parse if stem not in done, or if previous target_pages was incomplete
    todo: List[pathlib.Path] = []
    for p in target_pdfs:
        req_pages, _ = determine_target_pages(p)
        done_entry = state["done"].get(p.stem)
        if args.force or not done_entry or done_entry.get("target_pages") != req_pages:
            todo.append(p)

    if args.limit > 0:
        todo = todo[:args.limit]

    print(f"PDFs to process: {len(todo)} (already done with full pages: {len(target_pdfs) - len(todo)})")
    print(f"Tier: {args.tier} ({TIER_CREDITS_PER_PAGE[args.tier]} credits/page) | Workers: {args.workers}")
    print("-" * 60)

    cr_per_page = TIER_CREDITS_PER_PAGE[args.tier]
    success_count = 0
    fail_count = 0
    cached_count = 0

    def worker_job(pdf_p: pathlib.Path) -> Dict[str, Any]:
        return parse_pdf(pdf_p, tier=args.tier, api_key=args.api_key, force=args.force, state=state)

    # Use ThreadPoolExecutor for concurrent requests
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_map = {executor.submit(worker_job, p): p for p in todo}
        for i, future in enumerate(concurrent.futures.as_completed(future_map), 1):
            pdf_p = future_map[future]
            stem = pdf_p.stem
            try:
                res = future.result()
                status = res.get("status")

                with state_lock:
                    if status == "ok":
                        success_count += 1
                        pages = res.get("pages", 5)
                        state["done"][stem] = {
                            "pages": pages,
                            "bytes": res.get("bytes", 0),
                            "target_pages": res.get("target_pages", ""),
                            "elapsed_s": res.get("elapsed_s", 0),
                            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                        }
                        state["pages_parsed"] = state.get("pages_parsed", 0) + pages
                        state["credits_estimated"] = state.get("credits_estimated", 0) + (pages * cr_per_page)
                        state["credits_remaining_est"] = INITIAL_ACCOUNT_CREDITS - state["credits_estimated"]
                        save_state(state)
                        print(
                            f"[{i}/{len(todo)}] OK: {stem[:45]:<45} "
                            f"({res.get('bytes', 0):>5} chars, {res.get('elapsed_s', 0):>4.1f}s) "
                            f"| Est. credits left: {state['credits_remaining_est']}",
                            flush=True,
                        )

                    elif status == "cached":
                        cached_count += 1
                        pages = res.get("pages", 5)
                        if stem not in state["done"]:
                            state["done"][stem] = {
                                "pages": pages,
                                "bytes": res.get("bytes", 0),
                                "target_pages": res.get("target_pages", ""),
                                "cached": True,
                            }
                            save_state(state)
                        print(f"[{i}/{len(todo)}] CACHED: {stem[:45]:<45}", flush=True)

                    elif status == "aborted":
                        print(f"[{i}/{len(todo)}] ABORTED: {stem[:45]:<45} (Credits exhausted)", flush=True)

                    else:
                        fail_count += 1
                        err = res.get("error", "Unknown error")
                        state.setdefault("failed", {})[stem] = err
                        save_state(state)
                        print(f"[{i}/{len(todo)}] FAILED: {stem[:45]:<45} -> {err[:80]}", flush=True)

                if quota_exceeded_event.is_set():
                    print("\n[CRITICAL] Credit limit or API quota error encountered! Stopping pending tasks...")
                    # Cancel remaining futures
                    for f in future_map:
                        f.cancel()
                    break

            except Exception as exc:
                fail_count += 1
                with state_lock:
                    state.setdefault("failed", {})[stem] = str(exc)
                    save_state(state)
                print(f"[{i}/{len(todo)}] EXCEPTION: {stem[:45]:<45} -> {str(exc)[:80]}", flush=True)

    print("\n" + "=" * 60)
    print("RUN COMPLETE SUMMARY:")
    print(f"  Processed this run:   {success_count} newly parsed, {cached_count} cached, {fail_count} failed")
    print(f"  Total done in state:  {len(state['done'])}")
    print(f"  Total pages parsed:   {state['pages_parsed']}")
    print(f"  Est. credits used:    {state['credits_estimated']}")
    print(f"  Est. credits left:    {state['credits_remaining_est']} / {INITIAL_ACCOUNT_CREDITS}")
    if quota_exceeded_event.is_set():
        print("  ALERT: CREDITS RUN OUT OR RATE LIMIT REACHED! API KEY ROTATION REQUIRED.")
    print("=" * 60)

    # Verification gate
    v = verify_sample()
    print("\nGROUND TRUTH / SAMPLE VERIFICATION ON xclusiv_2026_xclusiv-2026_02_24:")
    print(f"  Overall Status: {v.get('status')}")
    for k, passed in v.get("checks", {}).items():
        print(f"    - {k:<28}: {'PASS' if passed else 'FAIL'}")


if __name__ == "__main__":
    main()
