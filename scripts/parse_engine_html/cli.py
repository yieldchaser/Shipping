"""CLI: python -m scripts.parse_engine_html <vv|survey|vocab|compare> [options]"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from scripts.parse_engine_html.deals import CLASS_RE
from scripts.parse_engine_html.html_extract import extract_article
from scripts.parse_engine_html.pipeline import (DEFAULT_OUT, DEFAULT_SRC, EXISTING_SERIES, find_images, list_sources,
                                                run)


def _years(arg: list[int] | None) -> list[int] | None:
    return arg or None


def cmd_vv(args) -> int:
    report = run(src=Path(args.src), out=Path(args.out), years=_years(args.years), limit=args.limit,
                 workers=args.workers, do_matrix=not args.no_matrix, existing_series=Path(args.existing_series),
                 incremental=args.incremental, md_root=Path(args.md_root))
    print(json.dumps({k: v for k, v in report.items() if k not in ("unparsed_lines",)}, ensure_ascii=False,
                     indent=1)[:12000])
    print(f"\nunparsed deal lines: {report['deals_unparsed']}")
    for u in report["unparsed_lines"]:
        print(f"  [{u['issue_date']}] ({u['sector']}) {u['reason']}: {u['line'][:200]}")
    return 0


def cmd_survey(args) -> int:
    """Formats per year: page container, sector-header style, comment style, matrix image source."""
    per: dict[int, Counter] = defaultdict(Counter)
    for f in list_sources(Path(args.src), _years(args.years)):
        art = extract_article(f)
        if not art.is_vv_report or art.issue_date is None:
            continue
        y = art.issue_date.year
        c = per[y]
        c["issues"] += 1
        c[f"container:{art.container}"] += 1
        for st in sorted(art.header_styles) or ["no_sector_text"]:
            c[f"header:{st}"] += 1
        deals = [d for s in art.sectors for d in s.deals]
        if any(d.comments for d in deals):
            c["dash_comments"] += 1
        if any(d.qualifiers for d in deals):
            c["inline_qualifiers"] += 1
        if any("tail_without_dash" in d.flags for d in deals):
            c["comment_without_dash"] += 1
        mat, _logo, how = find_images(f, art)
        c[f"matrix:{how or 'none'}"] += 1
    for y in sorted(per):
        print(y, dict(sorted(per[y].items())))
    return 0


def cmd_vocab(args) -> int:
    """Which leading class strings the vocabulary does not cover (should be only narrative lines)."""
    miss: Counter = Counter()
    seen: Counter = Counter()
    for f in list_sources(Path(args.src), _years(args.years)):
        art = extract_article(f)
        for s in art.sectors:
            for d in s.deals:
                seen[d.vessel_class] += 1
            for line, why in s.unparsed:
                if "vocabulary" in why:
                    miss[" ".join(line.split()[:3])] += 1
    print("classes matched:")
    for k, v in seen.most_common():
        print(f"  {v:5d}  {k}")
    print("lines with a class outside the vocabulary:", dict(miss))
    _ = CLASS_RE
    return 0


def cmd_compare(args) -> int:
    from scripts.parse_engine_html.series import compare, read_csv
    out = Path(args.out) / "series"
    new_sales = read_csv(out / "hellenic_vv_sales_series.csv")
    new_matrix = read_csv(out / "hellenic_vv_matrix_series.csv")
    print(json.dumps(compare(new_sales, new_matrix, Path(args.existing_series)), indent=1))
    return 0


def cmd_fallback(args) -> int:
    from scripts.parse_engine_html.fallback import main_cli
    rep = main_cli(Path(args.out), Path(args.existing_series), args.threshold)
    print(json.dumps({k: v for k, v in rep.items() if k != "dropped"}, indent=1))
    print(f"dropped: {len(rep['dropped'])} (see _fallback_report.json)")
    return 0


def cmd_promote(args) -> int:
    from scripts.parse_engine_html.promote import main_cli
    rep = main_cli(Path(args.out), Path(args.live), args.apply)
    print(json.dumps(rep, indent=1, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m scripts.parse_engine_html")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, fn, help_ in (("vv", cmd_vv, "parse every Hellenic VV issue into the staging tree"),
                            ("survey", cmd_survey, "list the HTML/image formats found per year"),
                            ("vocab", cmd_vocab, "vessel-class vocabulary coverage"),
                            ("compare", cmd_compare, "staged vs existing series row counts"),
                            ("fallback", cmd_fallback, "keep current matrix rows for failed issues where accurate"),
                            ("promote", cmd_promote, "copy passing staged issues over the live MDs (dry run unless --apply)")):
        sp = sub.add_parser(name, help=help_)
        sp.add_argument("--src", default=str(DEFAULT_SRC))
        sp.add_argument("--out", default=str(DEFAULT_OUT))
        sp.add_argument("--years", type=int, nargs="*")
        sp.add_argument("--existing-series", default=str(EXISTING_SERIES))
        if name == "vv":
            sp.add_argument("--limit", type=int)
            sp.add_argument("--workers", type=int, default=1)
            sp.add_argument("--no-matrix", action="store_true", help="skip OCR (text parsing only)")
            sp.add_argument("--incremental", action="store_true",
                            help="new issues only: write MD/sidecar under --md-root and append their series rows to "
                                 "--existing-series; existing files and rows are never rewritten")
            sp.add_argument("--md-root", default="data/extracted/md/hellenic/vessel_valuations")
        if name == "promote":
            sp.add_argument("--live", default="data/extracted/md/hellenic/vessel_valuations")
            sp.add_argument("--apply", action="store_true", help="write the files (default: dry run)")
        if name == "fallback":
            sp.add_argument("--threshold", type=float, default=0.98)
        sp.set_defaults(fn=fn)
    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
