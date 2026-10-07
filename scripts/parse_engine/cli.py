"""CLI: python -m scripts.parse_engine run --source clarksons --files <pdf>... | --glob "<pattern>" ..."""
from __future__ import annotations

import argparse
import csv
import glob as globmod
import sys
from datetime import datetime, timezone
from pathlib import Path

from scripts.parse_engine import engine as eng
from scripts.parse_engine import export_series, promote
from scripts.parse_engine.config import (CREDITS_PER_PAGE, corpus_root, load_profile, repo_relative,
                                         resolve_pdf, spec_to_pages)
from scripts.parse_engine.keys import KeyPool
from scripts.parse_engine.llama import CreditsExhausted, LlamaParseClient, LlamaParseError, estimate_credits
from scripts.parse_engine.validate import write_summary_csv

ENGINES = ["plan", "pymupdf_table", "llamaparse", "liteparse"]


def _collect(args, profile) -> list[Path]:
    paths: list[Path] = []
    for f in args.files or []:
        p = resolve_pdf(f)
        if not p.exists():
            print(f"missing: {f}", file=sys.stderr)
            continue
        paths.append(p)
    patterns = list(args.glob or [])
    if not args.files and not patterns:
        patterns = profile.get("globs", [])
    for pat in patterns:
        base = pat if Path(pat).is_absolute() else str(corpus_root() / pat)
        paths.extend(Path(x) for x in sorted(globmod.glob(base, recursive=True)) if x.lower().endswith(".pdf"))
    seen, uniq = set(), []
    for p in paths:
        if p.resolve() not in seen:
            seen.add(p.resolve())
            uniq.append(p)
    return uniq


def cmd_run(args) -> int:
    profile = load_profile(args.source)
    paths = _collect(args, profile)
    paths, dups = eng.dedupe_pdfs(paths, profile.get("prefer_path_regex"), profile.get("prefer_name_regex"))
    if dups:
        print(f"dedupe: {len(dups)} duplicate file(s) dropped (sha256), year-partitioned path kept")
        if not args.dry_run:
            dup_csv = (Path(args.staging_dir) if args.staging_dir else eng.DEFAULT_STAGING) / args.source / "duplicates.csv"
            dup_csv.parent.mkdir(parents=True, exist_ok=True)
            with open(dup_csv, "w", newline="", encoding="utf-8") as fh:
                w = csv.writer(fh)
                w.writerow(["duplicate", "kept"])
                w.writerows((repo_relative(d), repo_relative(k)) for d, k in dups)
    if args.limit:
        paths = paths[: args.limit]
    override = None if args.engine == "plan" else args.engine
    tag = None if args.engine == "plan" else eng.ENGINE_TAG[args.engine]
    pages_override = spec_to_pages(args.pages) if args.pages else None
    plans = [eng.plan_file(p, profile, override, pages_override) for p in paths]
    llama_cfg = profile.get("llamaparse", {})
    if args.new_only:
        from scripts.parse_engine.config import REPO_ROOT
        pcfg = profile.get("promotion") or {}
        index = promote.existing_index([REPO_ROOT / d for d in [pcfg.get("dest"), *pcfg.get("legacy_dirs", [])] if d],
                                       profile.get("date_patterns"),
                                       tuple(pcfg.get("name_markers", promote.DEFAULT_NAME_MARKERS)))
        keep = [pl for pl in plans if not promote.is_existing(pl.pdf.stem, pl.issue_date, index)]
        print(f"new-only: {len(plans) - len(keep)} PDF(s) already have an MD and are skipped, {len(keep)} new")
        plans = keep

    if args.dry_run:
        total = worst = 0
        print(f"{'file':64} {'year':>5} {'pages':>9} {'engine/tier':24} credits")
        for pl in plans:
            tier = llama_cfg.get("tier")
            fb = estimate_credits(tier, len(pl.pages)) if tier and pl.fallback == "llamaparse" else 0
            et = pl.engine + (f"/{pl.tier}" if pl.engine == "llamaparse" else "")
            line = (f"{pl.pdf.name[:64]:64} {pl.year or '-':>5} {pl.pages_spec:>5}/{pl.pages_total:<3} "
                    f"{et:24} {pl.est_credits:>5}")
            if fb and pl.engine != "llamaparse":
                line += f"  (fallback llamaparse/{tier}: {fb})"
            print(line)
            total += pl.est_credits
            worst += pl.est_credits + (fb if pl.engine != "llamaparse" else 0)
        rate = CREDITS_PER_PAGE.get(llama_cfg.get("tier", ""), 0)
        print(f"files={len(plans)} estimated_credits={total} worst_case_with_fallback={worst} "
              f"(tier {llama_cfg.get('tier')} = {rate}/page)")
        return 0

    staging = Path(args.staging_dir) if args.staging_dir else eng.DEFAULT_STAGING
    client = LlamaParseClient(KeyPool())
    budget = {"spent": 0, "max_credits": args.max_credits}
    rows = []
    for pl in plans:
        engine_name = pl.engine
        try:
            row = eng.run_file(pl, profile, args.source, staging, engine_name, tag, client, budget, args.prose)
            if not row["passed"] and args.fallback and engine_name != "llamaparse" and pl.fallback == "llamaparse":
                pl.tier, pl.version = llama_cfg.get("tier"), llama_cfg.get("version")
                row = eng.run_file(pl, profile, args.source, staging, "llamaparse", "llama", client, budget)
        except eng.BudgetExceeded as exc:
            row = {"file": pl.pdf.name, "engine": engine_name, "problems": [f"budget: {exc}"], "passed": False}
        except LlamaParseError as exc:
            row = {"file": pl.pdf.name, "engine": engine_name, "problems": [f"llamaparse_error: {exc}"],
                   "flags": [f"llamaparse_error"], "passed": False}
        except CreditsExhausted as exc:
            row = {"file": pl.pdf.name, "engine": engine_name, "problems": [f"credits_exhausted: {exc}"],
                   "passed": False}
        rows.append(row)
        status = "OK" if row["passed"] else "CHECK " + ",".join(row.get("flags") or row["problems"])
        print(f"{row['file'][:60]:60} {row['engine']:14} credits={row.get('credits_used', 0):>3} "
              f"tables={row.get('tables', '-')} recall={row.get('text_recall')} "
              f"num_recall={row.get('table_numeric_recall')} {status}")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    summary = staging / args.source / f"run_summary_{stamp}.csv"
    write_summary_csv(summary, rows)
    print(f"credits_spent={budget['spent']} summary={summary.as_posix()}")
    return 0


def cmd_promote(args) -> int:
    from scripts.parse_engine.config import REPO_ROOT

    profile = load_profile(args.source)
    cfg = profile.get("promotion") or {}
    staging = Path(args.staging_dir) if args.staging_dir else eng.DEFAULT_STAGING
    dest = REPO_ROOT / cfg["dest"]
    legacy = [REPO_ROOT / d for d in cfg.get("legacy_dirs", [])]
    accept = set(cfg.get("accept_flags", [])) | {f for f in (args.accept_flags or "").split(",") if f}
    plan = promote.build_plan(args.source, staging, dest, legacy, accept, date_patterns=profile.get("date_patterns"),
                              name_markers=tuple(cfg.get("name_markers", promote.DEFAULT_NAME_MARKERS)),
                              new_only=args.new_only)
    csv_path = Path(args.plan_csv) if args.plan_csv else staging / args.source / "promotion_plan.csv"
    promote.write_plan_csv(plan, csv_path)
    counts = promote.summarize(plan)
    print("plan: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())) + f"  csv={csv_path.as_posix()}")
    if not args.apply or args.dry_run:
        print("dry-run: nothing written or removed (pass --apply to promote)")
        return 0
    report = promote.apply_plan(plan, dest, allowed_dirs=legacy)
    print(f"applied: {report['written']} file(s) written, {len(report['removed'])} legacy file(s) removed "
          f"(git rm: {report['git_rm']}, deleted untracked: {report['deleted_untracked']}), not committed")
    for p, why in report["skipped"]:
        print(f"  NOT removed {p}: {why}")
    return 1 if report["skipped"] else 0


def cmd_series(args) -> int:
    staging = Path(args.staging_dir) if args.staging_dir else eng.DEFAULT_STAGING
    root = Path(args.root) if args.root else staging / args.source
    out_dir = Path(args.out_dir) if args.out_dir else staging / args.source / "series"
    only = None
    if args.eligible_only:
        only = {s.stem for s in promote.load_staged(staging, args.source) if not s.flags and s.issue_date}
    res = export_series.run_export(root, out_dir, only_stems=only, require_engine_schema=args.require_engine_schema)
    print(f"issues={res['issues']} sales_rows={res['sales_rows']} demolition_rows={res['demolition_rows']} out={out_dir.as_posix()}")
    for name, c in res["comparison"].items():
        print(name, c)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m scripts.parse_engine")
    sub = ap.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="parse documents into the staging directory")
    run.add_argument("--source", required=True, help="profile id (scripts/parse_engine/profiles/<source>.yaml)")
    run.add_argument("--files", nargs="+", help="PDF paths (absolute, or corpus/... resolved via CORPUS_ROOT)")
    run.add_argument("--glob", nargs="+", help="glob pattern(s) relative to CORPUS_ROOT (or absolute)")
    run.add_argument("--limit", type=int, help="process at most N files")
    run.add_argument("--dry-run", action="store_true", help="show the plan and credit estimate; no parse calls")
    run.add_argument("--max-credits", type=int, help="refuse paid calls that would exceed this total")
    run.add_argument("--engine", choices=ENGINES, default="plan", help="override the profile engine plan")
    run.add_argument("--prose", choices=["pymupdf", "liteparse"], help="prose engine for pymupdf_table (default: profile, else pymupdf)")
    run.add_argument("--pages", help="1-based page spec overriding the profile page rule, e.g. 5-6")
    run.add_argument("--new-only", action="store_true", help="parse only PDFs with no MD yet (never re-parses or overwrites)")
    run.add_argument("--fallback", action="store_true", help="run the paid fallback engine if validation fails")
    run.add_argument("--staging-dir", help="default: <repo>/.reparse_staging")
    run.set_defaults(func=cmd_run)
    pr = sub.add_parser("promote", help="promote validated staged output into data/extracted/md (plan first)")
    pr.add_argument("--source", required=True)
    pr.add_argument("--dry-run", action="store_true", help="write the plan CSV only; change nothing (the default)")
    pr.add_argument("--apply", action="store_true", help="actually write the promoted files and git rm the replaced ones")
    pr.add_argument("--new-only", action="store_true",
                    help="promote only issues with no MD yet; never removes or overwrites (weekly incremental mode)")
    pr.add_argument("--accept-flags", help="comma-separated flags that do not block promotion")
    pr.add_argument("--staging-dir")
    pr.add_argument("--plan-csv", help="default: <staging>/<source>/promotion_plan.csv")
    pr.set_defaults(func=cmd_promote)
    se = sub.add_parser("series", help="rebuild sales/demolition series CSVs from parsed tables.json")
    se.add_argument("--source", default="clarksons")
    se.add_argument("--root", help="directory with <year>/<stem>.md + .tables.json (default: staging)")
    se.add_argument("--out-dir")
    se.add_argument("--staging-dir")
    se.add_argument("--require-engine-schema", action="store_true",
                    help="refuse to export when any tables.json under --root is not schema parse_engine/v1")
    se.add_argument("--eligible-only", action="store_true", help="only issues whose validation has no flags")
    se.set_defaults(func=cmd_series)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
