"""End-to-end run: HTML issues + matrix images -> staged Markdown, sidecars, series CSVs and a report."""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from scripts.parse_engine_html import PARSER_NAME, PARSER_VERSION
from scripts.parse_engine_html.html_extract import Article, extract_article, parse_title_date
from scripts.parse_engine_html.matrix import MatrixResult, parse_matrix_image
from scripts.parse_engine_html.render import ImageRef, IssueContext, render_markdown, tables_payload
from scripts.parse_engine_html.series import (MATRIX_FIELDS, SALES_FIELDS, append_new_issues, compare,
                                              matrix_series_rows, sales_rows, write_csv)

DEFAULT_SRC = Path("corpus/02-hellenic/vessel_valuations")
DEFAULT_OUT = Path(".reparse_staging/vessel_valuations")
EXISTING_SERIES = Path("data/extracted/series")
LIVE_MD = Path("data/extracted/md/hellenic/vessel_valuations")
IMG_EXTS = (".jpg", ".jpeg", ".png")


def list_sources(src: Path, years: list[int] | None = None) -> list[Path]:
    files = sorted(src.glob("*/*.html"))
    if years:
        files = [f for f in files if int(f.parent.name) in years]
    return files


def slug_date(name: str):
    m = re.search(r"report-([a-z]+-\d{1,2}-\d{4})", name)
    return parse_title_date(m.group(1).replace("-", " ")) if m else None


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def find_images(html: Path, art: Article) -> tuple[Path | None, Path | None, str]:
    """(matrix image, logo image, how the matrix was found). Companion `_img2.*` first, then a local asset
    referenced by the HTML; remote-only references are reported but not fetched."""
    stem = html.with_suffix("")
    matrix = next((p for ext in IMG_EXTS if (p := Path(f"{stem}_img2{ext}")).exists()), None)
    how = "companion_img2" if matrix else ""
    logo = next((p for ext in IMG_EXTS if (p := Path(f"{stem}_img1{ext}")).exists()), None)
    if matrix is None:
        for ref in art.image_refs:
            if ref.startswith(("http://", "https://")):
                continue
            cand = (html.parent / ref).resolve()
            if cand.exists() and cand.suffix.lower() in IMG_EXTS:
                matrix, how = cand, "html_asset"
                break
    if matrix is None and any(r.startswith(("http://", "https://")) for r in art.image_refs):
        how = "remote_only"
    return matrix, logo, how


def choose_canonical(arts: list[tuple[Path, Article]]):
    """One file per issue date. Several archive slugs can hold the same article (the scraper stored the newest
    article under older slugs); keep the file whose slug date equals the title date."""
    by_date: dict = defaultdict(list)
    for p, a in arts:
        by_date[a.issue_date].append((p, a))
    chosen, dupes = [], {}
    for d, group in sorted(by_date.items(), key=lambda kv: str(kv[0])):
        if len(group) == 1:
            chosen.append(group[0])
            continue
        exact = [g for g in group if slug_date(g[0].name) == d] or group
        keep = sorted(exact, key=lambda g: g[0].name)[0]
        chosen.append(keep)
        dupes[keep[0].name] = [g[0].name for g in group if g is not keep]
    return chosen, dupes


def _ocr_one(args):
    path, cache_dir, article_date = args
    return parse_matrix_image(Path(path), Path(cache_dir), article_date).to_json()


def run(src: Path = DEFAULT_SRC, out: Path = DEFAULT_OUT, years: list[int] | None = None, limit: int | None = None,
        workers: int = 1, do_matrix: bool = True, existing_series: Path = EXISTING_SERIES,
        incremental: bool = False, md_root: Path = LIVE_MD) -> dict:
    """Staging run (default): rebuild everything under `out`. Incremental run: only issues that have no
    `vv_<date>.md` under `md_root` yet are parsed; their MD/sidecar are written next to the existing ones and
    their series rows are appended to `existing_series/*.csv` (existing files and rows are never rewritten)."""
    files = list_sources(src, years)
    parsed: list[tuple[Path, Article]] = []
    skipped: list[dict] = []
    for f in files:
        art = extract_article(f)
        if not art.is_vv_report:
            skipped.append({"file": f.name, "title": art.title})
        else:
            parsed.append((f, art))
    chosen, dupes = choose_canonical(parsed)
    duplicate_files = {n for v in dupes.values() for n in v}
    if incremental:
        chosen = [(f, a) for f, a in chosen
                  if not (md_root / str(a.issue_date.year) / f"vv_{a.issue_date.isoformat()}.md").exists()]
    if limit:
        chosen = chosen[:limit]

    ctxs: list[IssueContext] = []
    todo: list[tuple[Path, str]] = []
    for f, art in chosen:
        ctx = IssueContext(article=art, source_rel=f.as_posix(), duplicates=dupes.get(f.name, []))
        mat, logo, how = find_images(f, art)
        if logo:
            ctx.images.append(ImageRef(logo.as_posix(), sha256_file(logo), "logo"))
        if mat:
            ctx.matrix_image = mat.name
            ctx.images.append(ImageRef(mat.as_posix(), sha256_file(mat), "matrix"))
            todo.append((mat, art.issue_date.isoformat()))
        ctx.matrix_how = how
        ctxs.append(ctx)

    cache_dir = out / "_matrix_cache"
    results: dict[str, MatrixResult] = {}
    if do_matrix and todo:
        jobs = [(str(p), str(cache_dir), d) for p, d in todo]
        if workers > 1:
            with ProcessPoolExecutor(max_workers=workers) as ex:
                outs = list(ex.map(_ocr_one, jobs, chunksize=2))
        else:
            outs = [_ocr_one(j) for j in jobs]
        for (p, _d), o in zip(todo, outs):
            results[p.as_posix()] = MatrixResult.from_json(o)
    ok_results = [r for r in results.values() if r.status == "ok"]
    ref_report = {"ok_matrices": len(ok_results),
                  "benchmark_cells_blank": sum(1 for r in ok_results for c in r.cells if not c.ref_text),
                  "benchmark_cells_total": sum(len(r.cells) for r in ok_results)}

    for ctx in ctxs:
        mat_ref = next((i for i in ctx.images if i.role == "matrix"), None)
        if mat_ref and mat_ref.path in results:
            ctx.matrix = results[mat_ref.path]
        elif mat_ref and not do_matrix:
            ctx.matrix = None

    written = []
    for ctx in ctxs:
        a = ctx.article
        year_dir = (md_root if incremental else out) / str(a.issue_date.year)
        year_dir.mkdir(parents=True, exist_ok=True)
        md_path = year_dir / f"vv_{a.issue_date.isoformat()}.md"
        if incremental and md_path.exists():
            continue                      # never rewrite an existing issue
        md_path.write_text(render_markdown(ctx), encoding="utf-8", newline="\n")
        md_path.with_suffix(".tables.json").write_text(
            json.dumps(tables_payload(ctx), ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
        written.append(md_path.as_posix())

    sales = sales_rows(ctxs)
    matrix = matrix_series_rows(ctxs)
    if incremental:
        append_new_issues(existing_series / "hellenic_vv_sales_series.csv", SALES_FIELDS, sales)
        append_new_issues(existing_series / "hellenic_vv_matrix_series.csv", MATRIX_FIELDS, matrix)
    else:
        write_csv(out / "series" / "hellenic_vv_sales_series.csv", SALES_FIELDS, sales)
        write_csv(out / "series" / "hellenic_vv_matrix_series.csv", MATRIX_FIELDS, matrix)
    comparison = compare(sales, matrix, existing_series)

    report = build_report(ctxs, chosen, skipped, dupes, duplicate_files, results, ref_report, comparison, written, do_matrix)
    out.mkdir(parents=True, exist_ok=True)
    (out / "_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return report


def build_report(ctxs, chosen, skipped, dupes, duplicate_files, results, ref_report, comparison, written, do_matrix):
    n_deals = sum(c.article.n_deals for c in ctxs)
    unparsed = [{"issue_date": c.article.issue_date.isoformat(), "source_file": c.article.source_file,
                 "sector": s.name, "line": line, "reason": why}
                for c in ctxs for s in c.article.sectors for line, why in s.unparsed]
    failed = [{"issue_date": c.article.issue_date.isoformat(), "image": c.matrix_image,
               "errors": c.matrix.errors[:8] if c.matrix else []}
              for c in ctxs if c.matrix_image and c.matrix is not None and c.matrix.status != "ok"]
    no_image = [{"issue_date": c.article.issue_date.isoformat(), "how": getattr(c, "matrix_how", "")}
                for c in ctxs if c.matrix_image is None]
    date_mismatch = [{"issue_date": c.article.issue_date.isoformat(), "image_date": c.matrix.image_date}
                     for c in ctxs if c.matrix is not None and any("date label" in e for e in c.matrix.errors)]
    by_year = defaultdict(lambda: Counter())
    for c in ctxs:
        y = c.article.issue_date.year
        by_year[y]["issues"] += 1
        by_year[y]["deals"] += c.article.n_deals
        by_year[y]["unparsed"] += c.article.n_unparsed
        by_year[y]["matrix_" + c.matrix_status] += 1
    return {
        "parser": PARSER_NAME, "parser_version": PARSER_VERSION,
        "issues": len(ctxs), "html_files_scanned_vv": len(chosen) + len(duplicate_files),
        "duplicate_slug_files": {k: v for k, v in dupes.items()},
        "skipped_non_vv_files": skipped,
        "deals_parsed": n_deals, "deals_unparsed": len(unparsed), "unparsed_lines": unparsed,
        "image_only_issues": [c.article.issue_date.isoformat() for c in ctxs if not c.article.sectors],
        "matrix": {
            "ocr_run": do_matrix,
            "ok": sum(1 for c in ctxs if c.matrix_status == "ok"),
            "failed": len(failed), "no_image": len(no_image),
            "failed_detail": failed, "no_image_detail": no_image,
            "image_date_mismatch": date_mismatch,
            "ref_decode": ref_report,
        },
        "by_year": {str(y): dict(v) for y, v in sorted(by_year.items())},
        "series_comparison": comparison,
        "files_written": len(written),
    }
