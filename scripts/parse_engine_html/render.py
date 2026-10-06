"""Markdown + .tables.json rendering of one parsed VV issue."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from scripts.parse_engine_html import PARSER_NAME, PARSER_VERSION
from scripts.parse_engine_html.html_extract import Article
from scripts.parse_engine_html.matrix import AGES, COLUMNS, MATRIX_VERSION, MatrixResult

PUBLISHER = "VesselsValue (via Hellenic Shipping News)"
SOURCE = "hellenic_vessel_valuations"
MATRIX_HEADING = "VV Mini Matrix \u2013 Weekly Change (%)"
DEAL_HEADERS = ("Vessel", "Class", "Size", "Built", "Yard", "Buyer", "Price ($M)", "VV Value ($M)",
                "Premium (%)", "Comments")

NO_MATRIX_IMAGE = "No matrix image"
MATRIX_UNREADABLE = "Matrix image present but not machine-readable"


@dataclass
class ImageRef:
    path: str            # repo-relative posix path
    sha256: str
    role: str            # matrix | logo


@dataclass
class IssueContext:
    article: Article
    source_rel: str
    images: list[ImageRef] = field(default_factory=list)
    matrix: MatrixResult | None = None
    matrix_image: str | None = None
    matrix_how: str = ""
    unverified_refs: set[tuple[int, str, str]] = field(default_factory=set)   # (age, group, column)
    duplicates: list[str] = field(default_factory=list)
    parsed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))

    @property
    def matrix_status(self) -> str:
        if self.matrix_image is None:
            return "no_image"
        if self.matrix is None:
            return "not_run"
        return "ok" if self.matrix.status == "ok" else "failed"


def _esc(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ").strip()


def _yaml_str(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _num(x: float | None) -> str:
    return "" if x is None else f"{x:.4f}".rstrip("0").rstrip(".")


def deal_row(d) -> list[str]:
    size = f"{d.size_text} {d.size_unit}".strip() if d.size_text else ""
    buyer = d.buyer
    if d.seller:
        buyer = f"{buyer} (seller: {d.seller})" if buyer else f"(seller: {d.seller})"
    if d.price_usd_m is not None:
        price = _num(d.price_usd_m)
    else:
        price = d.price_raw or "n/a"
    prem = "" if d.premium_pct is None else f"{d.premium_pct:+.2f}"
    return [d.vessel_name, d.vessel_class, size, d.built_text, d.yard, buyer, price,
            _num(d.vv_value_usd_m), prem, d.comments_all]


def matrix_rows(ctx: IssueContext) -> tuple[list[str], list[list[str]]]:
    m = ctx.matrix
    header = ["Age"] + [f"{g} / {c}" for g, c in COLUMNS]
    rows: list[list[str]] = []
    by = {(c.age, c.group, c.column): c for c in m.cells}
    for age in AGES:
        row = [str(age)]
        for g, c in COLUMNS:
            cell = by[(age, g, c)]
            ref = cell.ref_text
            if ref and (age, g, c) in ctx.unverified_refs:
                ref = f"{ref}?"
            row.append(f"{cell.pct_text} ({ref})" if ref else cell.pct_text)
        rows.append(row)
    return header, rows


def md_table(header: list[str], rows: list[list[str]]) -> list[str]:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(_esc(x) for x in r) + " |" for r in rows]
    return out


def render_markdown(ctx: IssueContext) -> str:
    a = ctx.article
    iso = a.issue_date.isoformat() if a.issue_date else ""
    fm = [
        "---",
        f"title: {_yaml_str(a.title or '')}",
        f"publisher: {_yaml_str(PUBLISHER)}",
        f"source: {SOURCE}",
        f"issue_date: {iso}",
        f"filename_date: {a.filename_date.isoformat() if a.filename_date else ''}",
        f"archive_date: {_yaml_str(a.archive_date or '')}",
        f"year: {a.issue_date.year if a.issue_date else ''}",
        f"source_file: {_yaml_str(ctx.source_rel)}",
        f"source_sha256: {a.sha256}",
        "images:",
    ]
    if ctx.images:
        for im in ctx.images:
            fm += [f"  - path: {_yaml_str(im.path)}", f"    sha256: {im.sha256}", f"    role: {im.role}"]
    else:
        fm[-1] = "images: []"
    fm += [
        f"parser: {PARSER_NAME}",
        f"parser_version: {PARSER_VERSION}",
        f"matrix_ocr: {_yaml_str('rapidocr_onnxruntime (PP-OCR, local) matrix reader ' + MATRIX_VERSION)}",
        f"matrix_status: {ctx.matrix_status}",
        f"matrix_image_date: {ctx.matrix.image_date if ctx.matrix and ctx.matrix.image_date else ''}",
        f"deals_parsed: {a.n_deals}",
        f"deals_unparsed: {a.n_unparsed}",
        f"parsed_at: {ctx.parsed_at}",
        "---",
        "",
        f"# {a.title}",
        "",
    ]
    out = fm
    if ctx.duplicates:
        out += [f"> Duplicate archive copies of this issue (same article, other URL slugs): "
                f"{', '.join(ctx.duplicates)}", ""]
    for line in a.preamble:
        out += [line, ""]
    if not a.sectors:
        out += ["*No article text in the archived page (image-only post).*", ""]
    for s in a.sectors:
        out += [f"## {s.name}", ""]
        for c in s.commentary:
            out += [c, ""]
        if not s.commentary:
            out += ["*No sector commentary in the source.*", ""]
        if s.deals:
            out += md_table(list(DEAL_HEADERS), [deal_row(d) for d in s.deals]) + [""]
        for n in s.notes:
            out += [f"*{n}*", ""]
        if not s.deals and not s.notes and not s.unparsed:
            out += ["*No deals listed.*", ""]
    unparsed = [(s.name, line, why) for s in a.sectors for line, why in s.unparsed]
    out += ["## Unparsed deal lines", ""]
    if unparsed:
        out += [f"{len(unparsed)} deal line(s) could not be parsed cleanly; verbatim:", ""]
        for sec, line, why in unparsed:
            out += [f"- ({sec}) {line}", f"  - reason: {why}"]
        out += [""]
    else:
        out += ["None (0).", ""]
    out += [f"## {MATRIX_HEADING}", ""]
    if ctx.matrix_image is None:
        out += [f"*{NO_MATRIX_IMAGE}.*", ""]
    elif ctx.matrix is None:
        out += [f"*Matrix OCR was not run for this build* ({ctx.matrix_image}).", ""]
    elif ctx.matrix.status != "ok":
        out += [f"*{MATRIX_UNREADABLE}* ({ctx.matrix_image}).", ""]
        if ctx.matrix is not None:
            for e in ctx.matrix.errors[:6]:
                out += [f"- {e}"]
            out += [""]
    else:
        m = ctx.matrix
        out += [f"Source image: `{ctx.matrix_image}`"
                + (f" (image date label {m.image_date})" if m.image_date else "") + ".",
                "Each cell: weekly % change (reference benchmark size). `?` = benchmark size not "
                "corroborated by other issues.", ""]
        header, rows = matrix_rows(ctx)
        out += md_table(header, rows) + [""]
    for w in (ctx.matrix.warnings if ctx.matrix else []) + a.warnings:
        out += [f"> Note: {w}"]
    return "\n".join(out).rstrip() + "\n"


def tables_payload(ctx: IssueContext) -> dict:
    a = ctx.article
    matrix = None
    if ctx.matrix is not None:
        matrix = {
            "status": ctx.matrix.status, "image": ctx.matrix_image, "image_sha256": ctx.matrix.image_sha256,
            "image_date": ctx.matrix.image_date, "n_rows": ctx.matrix.n_rows, "n_cols": ctx.matrix.n_cols,
            "errors": ctx.matrix.errors, "warnings": ctx.matrix.warnings,
            "cells": [{**c.__dict__, "ref_unverified": (c.age, c.group, c.column) in ctx.unverified_refs}
                      for c in ctx.matrix.cells],
        }
    return {
        "issue_date": a.issue_date.isoformat() if a.issue_date else None,
        "title": a.title, "source_file": ctx.source_rel, "source_sha256": a.sha256,
        "parser": PARSER_NAME, "parser_version": PARSER_VERSION, "parsed_at": ctx.parsed_at,
        "matrix_status": ctx.matrix_status,
        "sectors": [{
            "name": s.name, "header": s.header, "header_style": s.header_style,
            "commentary": s.commentary, "notes": s.notes,
            "deals": [d.to_dict() for d in s.deals],
            "unparsed": [{"line": line, "reason": why} for line, why in s.unparsed],
        } for s in a.sectors],
        "preamble": a.preamble,
        "matrix": matrix,
    }
