"""Orchestration: plan a document, run an engine, normalise, stage, validate."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pymupdf

from scripts.parse_engine import geom_table, liteparse, prose
from scripts.parse_engine.cache import cache_get, cache_put
from scripts.parse_engine.config import (CREDITS_PER_PAGE, REPO_ROOT, pages_to_spec, repo_relative,
                                         select_pages, sha256_file)
from scripts.parse_engine.dates import parse_issue_date
from scripts.parse_engine.llama import CreditsExhausted, LlamaParseClient, estimate_credits
from scripts.parse_engine.normalize import build_frontmatter, clean_markdown, html_tables_to_gfm, now_iso
from scripts.parse_engine.validate import validate_output, write_validation

ENGINE_TAG = {"llamaparse": "llama", "pymupdf_table": "geom", "liteparse": "lit", "pymupdf": "pymupdf"}
DEFAULT_STAGING = REPO_ROOT / ".reparse_staging"
# plan notes that are informational and never block promotion
INFO_NOTE_PREFIXES = ("trailing_boilerplate_dropped", "two_page_content_kept", "last_page_not_boilerplate_kept", "pages_override", "issue_date_conflict_filename_chosen",
                      "issue_date_conflict_year_typo_filename_chosen", "issue_date_conflict_header_corroborated")


@dataclass
class FilePlan:
    pdf: Path
    sha256: str
    pages_total: int
    pages: list[int]
    engine: str
    fallback: str | None
    tier: str | None
    version: str | None
    year: int | None
    issue_date: str | None
    date_source: str | None
    date_conflict: bool
    header_date: str | None
    est_credits: int
    notes: list[str] = field(default_factory=list)

    @property
    def pages_spec(self) -> str:
        return pages_to_spec(self.pages)


def _year_from_path(pdf: Path) -> int | None:
    m = re.search(r"[\\/](20\d{2}|19\d{2})[\\/]", str(pdf))
    return int(m.group(1)) if m else None


def _match_plan(entries: list[dict[str, Any]], year: int | None, filename: str) -> dict[str, Any]:
    for e in entries or []:
        cond = e.get("match") or {}
        if "until_year" in cond and (year is None or year > cond["until_year"]):
            continue
        if "from_year" in cond and (year is None or year < cond["from_year"]):
            continue
        if "filename_regex" in cond and not re.search(cond["filename_regex"], filename):
            continue
        return e
    return {"engine": "pymupdf_table"}


def plan_file(pdf: Path, profile: dict[str, Any], engine_override: str | None = None,
              pages_override: list[int] | None = None) -> FilePlan:
    sha = sha256_file(pdf)
    doc = pymupdf.open(pdf)
    total = len(doc)
    header = doc[0].get_text() if total else ""
    iso, src, conflict, header_iso = parse_issue_date(profile.get("date_patterns", {}), header, pdf.name,
                                                      int(profile.get("header_text_chars", 400)),
                                                      folder_year=_year_from_path(pdf))
    year = int(iso[:4]) if iso else _year_from_path(pdf)
    notes: list[str] = []
    if iso is None:
        notes.append("issue_date_null")
    if conflict:
        # accepted when the stale-header rule resolved it; otherwise it needs a human decision
        notes.append({"filename_over_stale_header": "issue_date_conflict_filename_chosen",
                      "filename_over_header_year_typo": "issue_date_conflict_year_typo_filename_chosen",
                      "header_corroborated_by_filename": "issue_date_conflict_header_corroborated",
                      }.get(src, "issue_date_conflict_header_chosen"))

    rule = profile.get("pages")
    pages = select_pages(total, rule, year)
    # a page is only dropped when it carries no commentary/tables once the profile's dropped regions
    # (market-data box, contacts/disclaimer) are removed: blank pages and contacts pages go, a last
    # page that mixes commentary with contacts stays (its contacts block is cut as a region)
    bp = (rule or {}).get("last_page_boilerplate_regex") if isinstance(rule, dict) else None
    if bp:
        drops = profile.get("drop_regions")

        def trailing(p: int) -> bool:
            page = doc[p - 1]
            boxes = prose.drop_region_boxes(page, drops)
            content = sum(1 for w in page.get_text("words")
                          if not any(b[1] <= (w[1] + w[3]) / 2 <= b[3] for b in boxes))
            return content < 25 or (bool(re.search(bp, page.get_text())) and content < 60)

        if len(pages) < total:
            for p in [q for q in range(1, total + 1) if q not in pages]:
                if p == total and not trailing(p):
                    pages.append(p)
                    notes.append(f"two_page_content_kept_p{p}" if total == 2
                                 else f"last_page_not_boilerplate_kept_p{p}")
            pages.sort()
        while len(pages) > 1 and trailing(pages[-1]):
            notes.append(f"trailing_boilerplate_dropped_p{pages[-1]}")
            pages.pop()

    if pages_override:
        pages = [p for p in pages_override if 1 <= p <= total]
        notes.append("pages_override")

    plan = _match_plan(profile.get("engine_plan"), year, pdf.name)
    engine = engine_override or plan.get("engine", "pymupdf_table")
    llama_cfg = profile.get("llamaparse", {})
    tier = llama_cfg.get("tier") if engine == "llamaparse" or plan.get("fallback") == "llamaparse" else None
    version = llama_cfg.get("version") if tier else None
    est = estimate_credits(tier, len(pages)) if engine == "llamaparse" and tier else 0
    return FilePlan(pdf, sha, total, pages, engine, plan.get("fallback"), tier, version, year, iso, src,
                    conflict, header_iso, est, notes)


def dedupe_pdfs(paths: list[Path], prefer_regex: str | None, prefer_name_regex: str | None = None
                ) -> tuple[list[Path], list[tuple[Path, Path]]]:
    """Drop byte-identical duplicates. The kept path is the year-partitioned one; among those the
    canonically named one (`prefer_name_regex`, e.g. hashed bulletin names), then the shortest path."""
    by_sha: dict[str, list[Path]] = {}
    for p in paths:
        by_sha.setdefault(sha256_file(p), []).append(p)
    rx = re.compile(prefer_regex) if prefer_regex else None
    nx = re.compile(prefer_name_regex) if prefer_name_regex else None
    keep: list[Path] = []
    dropped: list[tuple[Path, Path]] = []
    for group in by_sha.values():
        group.sort(key=lambda p: (0 if rx and rx.search(p.as_posix()) else 1,
                                  0 if nx and nx.search(p.name) else 1, len(p.as_posix()), p.as_posix()))
        keep.append(group[0])
        dropped.extend((d, group[0]) for d in group[1:])
    order = {p: i for i, p in enumerate(paths)}
    keep.sort(key=lambda p: order[p])
    return keep, dropped


# ------------------------------------------------------------------------------------------ engines
def _lit_pages(plan: FilePlan) -> dict[int, str]:
    return {p: liteparse.parse_page(plan.pdf, plan.sha256, p, "markdown")["markdown"] for p in plan.pages}


def run_geom(plan: FilePlan, profile: dict[str, Any], prose_engine: str | None = None) -> dict[str, Any]:
    gcfg = profile.get("geom", {})
    prose_engine = prose_engine or gcfg.get("prose_engine", "pymupdf")
    doc = pymupdf.open(plan.pdf)
    level = int(gcfg.get("table_heading_level", 2))
    drops = profile.get("drop_regions")
    all_tables, parts = [], []
    memory: dict[Any, Any] = {}
    if prose_engine == "pymupdf":
        repeated = prose.repeated_band_texts(doc)
        body = prose.body_font_size(doc, plan.pages)
        all_paras: list[Any] = []
        page_items: list[list[tuple[str, Any]]] = []
        for p in plan.pages:
            page = doc[p - 1]
            tables = _page_tables(page, p, gcfg, drops, memory)
            exclude = [t.bbox for t in tables] + prose.drop_region_boxes(page, drops)
            paras = prose.page_prose(page, p, exclude, repeated, body)
            all_paras.extend(paras)
            page_items.append(prose.order_items(paras, tables))
            all_tables.extend(tables)
        prose.assign_heading_levels(all_paras, body)
        parts = [prose.render([it for items in page_items for it in items], level)]
        parser = "pymupdf_table + pymupdf_prose"
    else:
        lit = _lit_pages(plan)
        for p in plan.pages:
            page = doc[p - 1]
            tables = _page_tables(page, p, gcfg, drops, memory)
            parts.append(geom_table.merge_prose_and_tables(lit[p], tables, geom_table.page_words(page), level))
            all_tables.extend(tables)
        parser = f"pymupdf_table + liteparse {liteparse.lit_version()}"
    return {
        "markdown": "\n\n".join(parts),
        "tables": [t.to_json() for t in all_tables],
        "parser": parser,
        "api": "local", "tier": None, "credits_used": 0, "parsed_at": None,
    }


def _page_tables(page: pymupdf.Page, p: int, gcfg: dict[str, Any], drops: list[dict[str, Any]] | None,
                 memory: dict[Any, Any] | None = None):
    tables = geom_table.find_tables(page, p, gcfg.get("tables", []), gcfg.get("stop_anchors"),
                                    float(gcfg.get("footer_margin", 45)), memory)
    boxes = prose.drop_region_boxes(page, drops)
    return [t for t in tables if not any(t.bbox[1] >= b[1] - 1 for b in boxes)]


def dropped_boxes(plan: FilePlan, profile: dict[str, Any]) -> list[dict[str, Any]]:
    doc = pymupdf.open(plan.pdf)
    out = []
    for p in plan.pages:
        for box in prose.drop_region_boxes(doc[p - 1], profile.get("drop_regions")):
            out.append({"page": p, "bbox": box})
    return out


def run_lit(plan: FilePlan, profile: dict[str, Any]) -> dict[str, Any]:
    from scripts.parse_engine.liteparse import lit_version
    lit = _lit_pages(plan)
    return {"markdown": "\n\n".join(lit[p] for p in plan.pages), "tables": [],
            "parser": f"liteparse {lit_version()}", "api": "cli", "tier": None, "credits_used": 0,
            "parsed_at": None}


def run_llama(plan: FilePlan, profile: dict[str, Any], client: LlamaParseClient | None,
              budget: dict[str, Any]) -> dict[str, Any]:
    cfg = profile.get("llamaparse", {})
    tier, version = plan.tier or cfg["tier"], plan.version or cfg["version"]
    spec = plan.pages_spec
    payload = cache_get(plan.sha256, "llamaparse", tier, version, spec)
    hit = payload is not None
    used = 0
    if payload is None:
        est = estimate_credits(tier, len(plan.pages))
        cap = budget.get("max_credits")
        if cap is not None and budget["spent"] + est > cap:
            raise BudgetExceeded(f"{est} credits would exceed --max-credits {cap} (spent {budget['spent']})")
        client = client or LlamaParseClient()
        payload = client.parse(plan.pdf, tier, version, spec, cfg.get("custom_prompt"),
                               bool(cfg.get("merge_continued_tables", True)))
        cache_put(plan.sha256, "llamaparse", tier, version, spec, payload)
        used = est
        budget["spent"] += used
    resolved = payload.get("version_resolved") or version
    return {
        "markdown": html_tables_to_gfm(payload["markdown"]).replace("<br />", " "), "tables": [],
        "parser": f"llamaparse {tier} {resolved} ({payload['api']})",
        "api": payload["api"], "tier": tier, "credits_used": used, "cache_hit": hit,
        "parsed_at": _epoch_iso(payload.get("parsed_at_epoch")), "job_id": payload.get("job_id"),
        "key_prefix": payload.get("key_prefix"),
    }


class BudgetExceeded(RuntimeError):
    pass


def _epoch_iso(epoch: int | None) -> str | None:
    if not epoch:
        return None
    from datetime import datetime, timezone
    return datetime.fromtimestamp(epoch, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ------------------------------------------------------------------------------------------ driver
def stage_paths(staging: Path, source: str, plan: FilePlan, tag: str | None) -> dict[str, Path]:
    year = str(plan.year) if plan.year else "unknown"
    base = staging / source / year
    stem = plan.pdf.stem + (f".{tag}" if tag else "")
    return {"md": base / f"{stem}.md", "validation": base / f"{stem}.validation.json",
            "tables": base / f"{stem}.tables.json"}


def _regions(plan: FilePlan, profile: dict[str, Any]) -> list[dict[str, Any]]:
    """Table regions on the PDF (found geometrically, free) used for numeric recall of any engine."""
    gcfg = profile.get("geom")
    if not gcfg:
        return []
    doc = pymupdf.open(plan.pdf)
    out = []
    memory: dict[Any, Any] = {}
    for p in plan.pages:
        for t in _page_tables(doc[p - 1], p, gcfg, profile.get("drop_regions"), memory):
            out.append({"page": p, "name": t.name, "bbox": t.bbox})
    return out


def run_file(plan: FilePlan, profile: dict[str, Any], source: str, staging: Path, engine: str,
             tag: str | None, client: LlamaParseClient | None, budget: dict[str, Any],
             prose_engine: str | None = None) -> dict[str, Any]:
    if engine == "pymupdf_table":
        res = run_geom(plan, profile, prose_engine)
    elif engine == "llamaparse":
        res = run_llama(plan, profile, client, budget)
    elif engine == "liteparse":
        res = run_lit(plan, profile)
    else:
        raise ValueError(f"unsupported engine '{engine}'")

    body = clean_markdown(res["markdown"], profile)
    title_tpl = profile.get("title_template", "{source} {issue_date}")
    if plan.issue_date:
        title = title_tpl.format(issue_date=plan.issue_date, source=source)
    else:
        title = title_tpl.replace(" {issue_date}", "").format(source=source) + " (undated)"
    meta = {
        "title": title, "publisher": profile.get("publisher"), "source": source,
        "issue_date": plan.issue_date, "document_header_date": plan.header_date,
        "issue_date_conflict": plan.date_conflict, "year": plan.year, "source_file": repo_relative(plan.pdf),
        "source_sha256": plan.sha256, "pages_total": plan.pages_total, "pages_parsed": plan.pages_spec,
        "parser": res["parser"], "parsed_at": res.get("parsed_at") or now_iso(),
    }
    md = build_frontmatter(meta) + body
    paths = stage_paths(staging, source, plan, tag)
    paths["md"].parent.mkdir(parents=True, exist_ok=True)
    paths["md"].write_text(md, encoding="utf-8")
    if res.get("tables"):
        paths["tables"].write_text(json.dumps(res["tables"], indent=2, ensure_ascii=False), encoding="utf-8")

    regions = res["tables"] and [{"page": t["page"], "name": t["name"], "bbox": t["bbox"]} for t in res["tables"]]
    if not regions:
        regions = _regions(plan, profile)
    report = validate_output(md, plan.pdf, plan.pages, profile, plan.year, regions, plan.issue_date,
                             dropped_boxes(plan, profile))
    report.update({"engine": engine, "api": res.get("api"), "tier": res.get("tier"), "parser": res["parser"],
                   "credits_used": res.get("credits_used", 0), "cache_hit": res.get("cache_hit"),
                   "notes": plan.notes, "tables_json_tables": len(res.get("tables") or [])})
    unassigned = sum(t.get("unassigned_words", 0) for t in (res.get("tables") or []))
    flags = list(report["problems"])
    flags += [n for n in plan.notes if not n.startswith(INFO_NOTE_PREFIXES)]
    if report["tables"] < 2 and engine == "pymupdf_table":
        flags.append("few_tables")
    if unassigned:
        flags.append(f"table_unassigned_words={unassigned}")
    report["flags"] = flags
    write_validation(paths["validation"], report)
    return {
        "file": plan.pdf.name, "engine": engine, "tier": res.get("tier"), "api": res.get("api"),
        "year": plan.year, "issue_date": plan.issue_date, "pages_total": plan.pages_total,
        "pages_parsed": plan.pages_spec, "credits_used": res.get("credits_used", 0),
        "tables": report["tables"], "header_only_tables": report["header_only_tables"],
        "ragged_tables": report["ragged_tables"], "numeric_axis_runs": report["numeric_axis_runs"],
        "garbage_chars": report["garbage_chars"], "broken_sentences": report["broken_sentences"],
        "text_recall": report["text_recall"],
        "table_numeric_recall": report["table_numeric_recall"], "sections_missing": report["sections_missing"],
        "problems": report["problems"], "flags": flags, "passed": report["passed"] and not flags,
        "tables_detail": ";".join(f"{t['name']}:{0 if t['empty'] else len(t['rows'])}" for t in (res.get("tables") or [])),
        "issue_date_conflict": plan.date_conflict, "document_header_date": plan.header_date,
        "source_file": repo_relative(plan.pdf), "source_sha256": plan.sha256,
        "output": paths["md"].as_posix(),
    }


__all__ = ["FilePlan", "plan_file", "run_file", "dedupe_pdfs", "BudgetExceeded", "CreditsExhausted",
           "ENGINE_TAG", "DEFAULT_STAGING", "CREDITS_PER_PAGE"]
