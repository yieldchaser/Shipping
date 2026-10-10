"""VV legacy-runner guards, series vocabulary, matrix headings / unreadable notes and the promote step."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

from scripts.parse_engine_html import PARSER_NAME
from scripts.parse_engine_html.html_extract import Article, Sector
from scripts.parse_engine_html.matrix import AGES, COLUMNS, Cell, MatrixResult
from scripts.parse_engine_html.pipeline import sha256_file
from scripts.parse_engine_html.promote import main_cli, plan
from scripts.parse_engine_html.render import IssueContext, render_markdown, tables_payload
from scripts.parse_engine_html.series import SALES_FIELDS, canonical_class

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "report_ingest.yml"


def test_legacy_vv_runners_refuse_without_override():
    env = {k: v for k, v in os.environ.items() if k != "ALLOW_LEGACY_VV_EXTRACT"}
    for script in ("run_hellenic_vessel_valuations.py", "run_hellenic_vv_matrix.py"):
        res = subprocess.run([sys.executable, str(ROOT / "scripts/extract/publishers" / script)],
                             capture_output=True, text=True, env=env, timeout=120)
        assert res.returncode != 0 and "scripts.parse_engine_html" in (res.stderr + res.stdout)


def test_workflow_and_orchestrator_use_the_new_vv_parser_only():
    wf = WORKFLOW.read_text(encoding="utf-8")
    assert "python -m scripts.parse_engine_html vv --incremental" in wf
    orch = (ROOT / "scripts" / "orchestrate_pipeline.py").read_text(encoding="utf-8")
    for text in (wf, orch):
        live = [ln for ln in text.splitlines()
                if ("run_hellenic_vessel_valuations" in ln or "run_hellenic_vv_matrix" in ln)
                and not ln.strip().startswith("#")]
        assert not live


def test_sales_class_maps_to_existing_vocabulary_and_keeps_unknown_verbatim():
    assert canonical_class("Bulkers", "Panamax BC") == "Panamax"
    assert canonical_class("Bulkers", "Handy BC (Open Hatch)") == "Handysize"
    assert canonical_class("Bulkers", "Capesizes") == "Capesize"
    assert canonical_class("Tankers", "VLCCs") == "VLCC"
    assert canonical_class("Tankers", "MR2 (Chem/Product)") == "MR2"
    assert canonical_class("Tankers", "Handy Tanker") == "Handy Tanker"
    assert canonical_class("Tankers", "J19 Stainless Steel") == "J19 Stainless Steel"
    assert canonical_class("Containers", "Handy Container") == "Handysize"
    assert SALES_FIELDS[:13] == ("issue_date", "sector", "vessel_name", "vessel_class", "dwt_spec", "built_date",
                                 "yard", "buyer", "price_usd_m", "vv_value_usd_m", "premium_pct", "comments",
                                 "source_file")
    assert "vessel_class_raw" in SALES_FIELDS[13:]


def _matrix(status: str, image_date: str | None) -> MatrixResult:
    cells = [Cell(a, g, c, "+0.5%", 0.5, "N/A", None) for a in AGES for g, c in COLUMNS]
    return MatrixResult(status, "m.jpg", "sha", image_date, 6, 13, cells if status == "ok" else [],
                        [] if status == "ok" else ["age 0 Tankers/VLCC: value not read"])


def _ctx(tmp_path: Path, iso: str, matrix: MatrixResult | None, px=None, unparsed=()) -> IssueContext:
    src = tmp_path / "corpus" / f"{iso}.html"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text("<html>vv</html>", encoding="utf-8")
    y, m, d = map(int, iso.split("-"))
    sector = Sector(name="Bulkers", header="Bulkers", header_style="h")
    sector.unparsed = [(line, "why") for line in unparsed]
    art = Article(source_file=src.name, sha256=sha256_file(src), title="Weekly Vessel Valuations Report",
                  issue_date=date(y, m, d), archive_date=None, filename_date=date(y, m, d), container="div",
                  sectors=[sector])
    return IssueContext(article=art, source_rel=src.relative_to(tmp_path).as_posix(), matrix=matrix,
                        matrix_image="m.jpg", matrix_px=px)


def test_ok_matrix_heading_carries_the_issue_date():
    ctx = IssueContext(article=Article("f.html", "x", "T", date(2024, 1, 9), None, None, "div"),
                       source_rel="f.html", matrix=_matrix("ok", "2024-01-09"), matrix_image="m.jpg")
    assert "## VV Mini Matrix \u2013 Weekly Change (%) \u2013 2024-01-09\n" in render_markdown(ctx)


def test_unreadable_matrix_gets_a_note_and_no_numbers_and_low_res_is_stated():
    ctx = IssueContext(article=Article("f.html", "x", "T", date(2026, 9, 22), None, None, "div"),
                       source_rel="f.html", matrix=_matrix("failed", None), matrix_image="m.jpg",
                       matrix_px=(600, 270))
    md = render_markdown(ctx)
    tail = md.split("## VV Mini Matrix", 1)[1]
    assert "Matrix image not machine-readable" in tail and "600x270 px" in tail
    assert "| Age |" not in tail and "%" not in tail.split("\n", 2)[2].replace("(%)", "")


def _stage(tmp_path: Path, iso: str, **kw) -> Path:
    ctx = _ctx(tmp_path, iso, **kw)
    out = tmp_path / "staging" / iso[:4]
    out.mkdir(parents=True, exist_ok=True)
    md = out / f"vv_{iso}.md"
    md.write_text(render_markdown(ctx), encoding="utf-8")
    md.with_suffix(".tables.json").write_text(json.dumps(tables_payload(ctx)), encoding="utf-8")
    return md


def test_promote_is_dry_run_by_default_and_only_passing_issues_are_written(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _stage(tmp_path, "2024-01-09", matrix=_matrix("ok", "2024-01-09"))
    _stage(tmp_path, "2024-01-16", matrix=_matrix("failed", None))
    _stage(tmp_path, "2024-01-23", matrix=_matrix("ok", "2024-01-23"), unparsed=("Cape X sold",))
    blocked_md = _stage(tmp_path, "2024-01-30", matrix=_matrix("ok", "2024-01-30"))
    blocked_md.write_text(blocked_md.read_text(encoding="utf-8").replace(f"parser: {PARSER_NAME}", "parser: other"),
                          encoding="utf-8")
    live = tmp_path / "live"
    (live / "2024").mkdir(parents=True)
    keep = live / "2024" / "vv_2024-01-23.md"
    keep.write_text("OLD", encoding="utf-8")
    staging = tmp_path / "staging"

    p = plan(staging, live, tmp_path)
    assert [i["issue_date"] for i in p["promote"]] == ["2024-01-09", "2024-01-16", "2024-01-23"]
    assert list(p["blocked"]) == ["2024-01-30"]

    dry = main_cli(staging, live, False, tmp_path)
    assert dry["mode"] == "dry-run" and dry["written"] == 0 and not (live / "2024" / "vv_2024-01-09.md").exists()

    done = main_cli(staging, live, True, tmp_path)
    assert done["written"] == 3 and done["blocked"] == 1
    assert (live / "2024" / "vv_2024-01-09.md").exists() and (live / "2024" / "vv_2024-01-09.tables.json").exists()
    assert (live / "2024" / "vv_2024-01-16.md").exists()
    assert "Cape X sold" in keep.read_text(encoding="utf-8")   # unparsed lines do not block; listed verbatim
    assert not (live / "2024" / "vv_2024-01-30.md").exists()   # a blocked issue is never written


def test_unparsed_lines_are_listed_verbatim_after_the_sector_table_and_not_tabulated(tmp_path):
    line = "Aframax Anavatos 2 (115,00 DWT, Jan 2009, Hanjin HI) sold for USD 41.50 mil, VV Value USD 42.78 mil"
    ctx = _ctx(tmp_path, "2024-03-05", _matrix("ok", "2024-03-05"), unparsed=(line, "VLCC 24x sold en bloc"))
    md = render_markdown(ctx)
    sector = md.split("## Bulkers", 1)[1].split("## Unparsed deal lines", 1)[0]
    assert (f"**Other reported deals (as printed, not tabulated):**\n\n- {line}\n- VLCC 24x sold en bloc\n"
            in sector)
    assert "| Vessel |" not in md
    payload = tables_payload(ctx)
    assert [u["line"] for u in payload["sectors"][0]["unparsed"]] == [line, "VLCC 24x sold en bloc"]
    assert "Other reported deals" not in render_markdown(_ctx(tmp_path, "2024-03-12", _matrix("ok", "2024-03-12")))


def test_promote_blocks_unparsed_line_missing_from_md(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    md = _stage(tmp_path, "2024-03-19", matrix=_matrix("ok", "2024-03-19"), unparsed=("Cape X sold",))
    md.write_text(md.read_text(encoding="utf-8").replace("- Cape X sold\n", ""), encoding="utf-8")
    assert "Other reported deals" in " ".join(plan(tmp_path / "staging", tmp_path / "live", tmp_path)["blocked"]["2024-03-19"])


def test_promote_blocks_changed_source_wrong_matrix_date_and_foreign_parser(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    a = _stage(tmp_path, "2024-02-06", matrix=_matrix("ok", "2024-02-06"))
    (tmp_path / "corpus" / "2024-02-06.html").write_text("<html>edited</html>", encoding="utf-8")
    b = _stage(tmp_path, "2024-02-13", matrix=_matrix("ok", "2024-02-06"))
    d = _stage(tmp_path, "2024-02-27", matrix=_matrix("ok", "2024-02-27"))
    d.write_text(d.read_text(encoding="utf-8").replace("source_file: \"corpus", "source_file: \"C:/x/corpus"),
                 encoding="utf-8")
    c = _stage(tmp_path, "2024-02-20", matrix=_matrix("ok", "2024-02-20"))
    c.write_text(c.read_text(encoding="utf-8").replace(f"parser: {PARSER_NAME}", "parser: other"), encoding="utf-8")
    blocked = plan(tmp_path / "staging", tmp_path / "live", tmp_path)["blocked"]
    assert any("source HTML changed" in x for x in blocked["2024-02-06"])
    assert "2024-02-13" not in blocked          # label differs from the issue date: kept, headed by the image's date
    heading = b.read_text(encoding="utf-8").split("## VV Mini Matrix", 1)[1].split(chr(10), 1)[0]
    assert "– 2024-02-06" in heading
    assert any("absolute" in x for x in blocked["2024-02-27"])
    assert any("parser" in x for x in blocked["2024-02-20"])
    assert a.exists() and b.exists()


def test_rejected_ocr_reads_stay_out_of_the_md_and_go_to_the_sidecar():
    from scripts.parse_engine_html.matrix import BandRead, cells_from_bands
    bands = [BandRead(0, "Tankers", "VLCC", "val", "+", False, [["raw", 5, "+7.1%"], ["raw", 4, "+2.9%"]]),
             BandRead(0, "Tankers", "VLCC", "ref", "", False, [["raw", 5, "710k"], ["raw", 4, "310k"]])]
    cell = cells_from_bands(bands)[0]
    assert cell.raw_val == ["+7.1%", "+2.9%"] and cell.raw_ref == ["710k", "310k"]
    assert all(not any(ch.isdigit() for ch in t.replace("age 0", "")) for t in cell.problems + cell.notes)
    m = _matrix("failed", None)
    m.errors = [t for t in cell.problems]
    ctx = IssueContext(article=Article("f.html", "x", "T", date(2025, 5, 13), None, None, "div"),
                       source_rel="f.html", matrix=m, matrix_image="m.jpg")
    assert "raw=" not in render_markdown(ctx) and "7.1" not in render_markdown(ctx)


def test_engine_failure_is_not_cached_not_unreadable_and_not_final(tmp_path, monkeypatch):
    from scripts.parse_engine_html import matrix as mx
    from scripts.parse_engine_html import pipeline
    from PIL import Image
    img = tmp_path / "m.png"
    Image.new("RGB", (50, 50), "white").save(img)
    monkeypatch.setattr(mx, "detect_boxes", lambda rgb: (_ for _ in ()).throw(ImportError("rapidocr missing")))
    res = mx.parse_matrix_image(img, tmp_path / "cache", "2025-01-07")
    assert res.status == "error" and not list((tmp_path / "cache").glob("*.json"))
    ctx = IssueContext(article=Article("f.html", "x", "T", date(2025, 1, 7), None, None, "div"),
                       source_rel="f.html", matrix=None, matrix_image="m.png", matrix_error="engine")
    md = render_markdown(ctx)
    assert "not run" in md and "not machine-readable" not in md
    assert ctx.matrix_status == "not_run"
    assert hasattr(pipeline, "repo_rel")


def test_genuine_layout_failure_is_cached_and_unreadable(tmp_path, monkeypatch):
    from scripts.parse_engine_html import matrix as mx
    from PIL import Image
    img = tmp_path / "m.png"
    Image.new("RGB", (50, 50), "white").save(img)
    monkeypatch.setattr(mx, "detect_boxes", lambda rgb: [])        # no OCR engine needed for a layout verdict
    res = mx.parse_matrix_image(img, tmp_path / "cache", "2025-01-07")
    assert res.status == "failed", res.errors
    assert res.errors[0].startswith("grid:") and len(list((tmp_path / "cache").glob("*.json"))) == 1


def test_paths_in_staged_files_are_repo_relative(tmp_path, monkeypatch):
    from scripts.parse_engine_html.pipeline import repo_rel
    monkeypatch.chdir(tmp_path)
    assert repo_rel(tmp_path / "corpus" / "a" / ".." / "b.jpg").as_posix() == "corpus/b.jpg"
    assert not repo_rel(Path("corpus/x/../y.jpg")).is_absolute()


def test_promote_never_replaces_live_matrix_numbers_with_a_failed_matrix(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _stage(tmp_path, "2024-03-05", matrix=_matrix("failed", None))
    live = tmp_path / "live" / "2024"
    live.mkdir(parents=True)
    (live / "vv_2024-03-05.md").write_text("## VV Mini Matrix\n\n| Age | x |\n", encoding="utf-8")
    p = plan(tmp_path / "staging", tmp_path / "live", tmp_path)
    assert not p["promote"] and "matrix numbers" in p["blocked"]["2024-03-05"][0]


def test_series_class_mr1_is_not_mapped_to_mr_and_count_prefix_is_visible():
    from scripts.parse_engine_html.deals import parse_deal_line
    from scripts.parse_engine_html.render import deal_row
    assert canonical_class("Tankers", "MR1") == "MR1" and canonical_class("Tankers", "MR2s") == "MR2"
    d = parse_deal_line("5 x Handy BC (Cape A, B) (36,000 DWT, 2012, Mitsui) sold to Z for USD 5 mil, "
                        "VV value USD 5 mil", "Bulkers").deal
    if d is None:
        d = parse_deal_line("5 Handy BC (36,000 DWT, 2012, Mitsui) sold to Z for USD 5 mil, VV value USD 5 mil",
                            "Bulkers").deal
    assert d is not None and deal_row(d)[1].startswith("5x ")


def _bench_ctx(tmp_path, iso, ref):
    m = _matrix("ok", iso)
    for c in m.cells:
        c.ref_text, c.ref_size = ("38k", 38000) if (c.group, c.column) == ("Bulkers", "Handy") else ("N/A", None)
    if ref:
        for c in m.cells:
            if (c.group, c.column, c.age) == ("Bulkers", "Handy", 0):
                c.ref_text, c.ref_size = ref, int(ref[:-1]) * 1000
    return _ctx(tmp_path, iso, matrix=m)


def _handy0(ctx):
    return next(c for c in ctx.matrix.cells if (c.group, c.column, c.age) == ("Bulkers", "Handy", 0))


def test_benchmark_size_equal_in_every_render_is_blanked_unless_consensus_or_adjacent(tmp_path):
    from scripts.parse_engine_html.pipeline import reconcile_benchmarks
    dates = ["2025-06-03", "2025-06-10", "2025-06-17", "2025-06-24", "2025-07-01"]
    ctxs = [_bench_ctx(tmp_path, d, "39k" if d == "2025-06-17" else None) for d in dates]
    rep = reconcile_benchmarks(ctxs)
    assert _handy0(ctxs[2]).ref_text == "" and "left blank" in _handy0(ctxs[2]).notes[0]
    assert [b["issue_date"] for b in rep["blanked"]] == ["2025-06-17"] and not rep["surviving_deviations"]
    assert _handy0(ctxs[1]).ref_text == "38k"
    # a step change survives only in a run of >= 4 consecutive weekly issues
    from datetime import timedelta
    wk = [(date(2025, 6, 3) + timedelta(days=7 * n)).isoformat() for n in range(11)]
    ctxs = [_bench_ctx(tmp_path, d, "39k" if d in wk[7:] else None) for d in wk]       # 9 vs 8: confusable
    assert len(reconcile_benchmarks(ctxs)["blanked"]) == 4
    ctxs = [_bench_ctx(tmp_path, d, "37k" if d in wk[7:] else None) for d in wk]       # 7 vs 8: not confusable
    rep = reconcile_benchmarks(ctxs)
    assert all(_handy0(c).ref_text == "37k" for c in ctxs[7:]) and not rep["blanked"]
    assert len(rep["surviving_deviations"]) == 4 and rep["surviving_deviations"][0]["run"] == 4
    ctxs = [_bench_ctx(tmp_path, d, "37k" if d in wk[8:] else None) for d in wk]       # run of 3: blanked
    rep = reconcile_benchmarks(ctxs)
    assert len(rep["blanked"]) == 3 and not rep["surviving_deviations"]


def test_benchmark_adjacency_means_consecutive_weeks_not_next_ok_issue(tmp_path):
    from scripts.parse_engine_html.pipeline import reconcile_benchmarks
    dates = ["2025-06-03", "2025-06-10", "2025-06-17", "2025-06-24", "2025-08-12", "2025-08-26", "2025-09-02",
             "2025-09-09"]
    ctxs = [_bench_ctx(tmp_path, d, "39k" if d in dates[2:6] else None) for d in dates]
    rep = reconcile_benchmarks(ctxs)
    assert [b["issue_date"] for b in rep["blanked"]] == ["2025-06-17", "2025-06-24", "2025-08-12", "2025-08-26"]   # gaps break the run


def test_confusable_digit_slips_and_long_runs(tmp_path):
    from scripts.parse_engine_html.pipeline import confusable
    assert confusable("90k", "80k") and confusable("39k", "38k") and confusable("30k", "38k")
    assert confusable("71k", "11k") and confusable("72k", "22k") and confusable("5500", "6500")
    assert not confusable("37k", "38k") and not confusable("310k", "320k") and not confusable("62k", "60k")
    assert not confusable("110k", "11k") and not confusable("90k", "80") and not confusable("90k", "85k")
    from datetime import timedelta
    from scripts.parse_engine_html.pipeline import reconcile_benchmarks
    wk = [(date(2025, 1, 7) + timedelta(days=7 * n)).isoformat() for n in range(20)]
    ctxs = [_bench_ctx(tmp_path, d, "39k" if d in wk[10:] else None) for d in wk]
    assert not reconcile_benchmarks(ctxs)["blanked"]            # a run of 10 survives even if confusable


def test_zero_keeps_its_printed_minus_and_deal_tables_still_reject_negative_zero():
    from scripts.parse_engine_html.matrix import BandRead, decide_band, normalise_pct
    assert normalise_pct("-0.0%", "")[0] == "-0.0%" and normalise_pct("0.0%", "")[0] == "0.0%"
    mk = lambda *t: BandRead(0, "Tankers", "VLCC", "val", "", False, [["raw", 5, x] for x in t])
    assert decide_band(mk("-0.0%", "-0.0%", "0.0%"))[0] == "-0.0%"
    assert decide_band(mk("0.0%", "0.0%", "-0.0%"))[0] == "0.0%"
    assert decide_band(mk("0.0%", "0.0%"))[0] == "0.0%"


def test_unreliable_label_never_prints_a_heading_date():
    from scripts.parse_engine_html.matrix import finalize
    from tests.test_parse_engine_html_matrix import _result
    res = finalize(_result(["07 May 2025", "07 May 2025"]), "2025-05-27")
    assert res.status == "failed"
    ctx = IssueContext(article=Article("f.html", "x", "T", date(2025, 5, 27), None, None, "div"),
                       source_rel="f.html", matrix=res, matrix_image="m.jpg")
    md = render_markdown(ctx)
    assert "2025-05-07" not in md and "Matrix image not machine-readable" in md and "| Age |" not in md


def test_reconcile_blanking_keeps_the_raw_reads_in_the_sidecar(tmp_path):
    from scripts.parse_engine_html.matrix import BandRead
    from scripts.parse_engine_html.pipeline import reconcile_benchmarks
    from datetime import timedelta
    wk = [(date(2025, 6, 3) + timedelta(days=7 * n)).isoformat() for n in range(6)]
    ctxs = [_bench_ctx(tmp_path, d, "39k" if d == wk[2] else None) for d in wk]
    ctxs[2].matrix.bands = [BandRead(0, "Bulkers", "Handy", "ref", "", False, [["raw", 5, "39k"], ["raw", 4, "39k"]])]
    reconcile_benchmarks(ctxs)
    cell = _handy0(ctxs[2])
    assert cell.ref_text == "" and cell.raw_ref == ["39k", "39k"]


def test_promote_skips_issues_already_live_with_identical_content(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    md = _stage(tmp_path, "2024-04-02", matrix=_matrix("ok", "2024-04-02"))
    live = tmp_path / "live"
    (live / "2024").mkdir(parents=True)
    side = md.with_suffix(".tables.json")
    (live / "2024" / md.name).write_text(md.read_text(encoding="utf-8").replace("parsed_at: ", "parsed_at: 1999 "),
                                         encoding="utf-8")
    d = json.loads(side.read_text(encoding="utf-8"))
    d["parsed_at"] = "1999"
    (live / "2024" / side.name).write_text(json.dumps(d), encoding="utf-8")
    p = plan(tmp_path / "staging", live, tmp_path)
    assert p["promote"] == [] and p["unchanged"] == ["2024-04-02"]
    (live / "2024" / md.name).write_text("OLD", encoding="utf-8")
    assert [i["issue_date"] for i in plan(tmp_path / "staging", live, tmp_path)["promote"]] == ["2024-04-02"]
