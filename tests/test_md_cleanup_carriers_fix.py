"""Tests for scripts/md_cleanup/carriers_fix.py (targeted Carriers MD cell fixer)."""
import re
from pathlib import Path

import pytest

from scripts.md_cleanup import carriers_fix as cf

PDF = Path(r"C:\Users\Dell\Github\Shipping\corpus\01-brokers\carriers\2025"
           r"\carriers_2025_W21_WK-21-25-CARRIERS_SP-MARKET-REPORT.pdf")
# pre-fix W21 MD, committed so tests do not depend on the live (already fixed) MD
MD = Path(__file__).parent / "fixtures" / "carriers" / "carriers_2025_W21_prefix.md"
needs_files = pytest.mark.skipif(not PDF.exists(), reason="local-only PDF missing")


def test_split_join_roundtrip():
    line = "| VLCC TCE | 38.806 | -5551.0 | 44.357 |"
    assert cf.join_row(cf.split_row(line)) == line
    blank = "| Containers | Subcontinent | 6000 - 10000 |  |  |"
    assert cf.join_row(cf.split_row(blank)) == blank


def test_parse_md_tables_finds_rows_and_title():
    lines = ["## T", "", "| a | b |", "| --- | --- |", "| 1 | 2 |", "| 3 | 4 |"]
    (tbl,) = cf.parse_md_tables(lines)
    assert tbl["title"] == "T" and tbl["header"] == ["a", "b"]
    assert [r[0] for r in tbl["rows"]] == [4, 5]


def _fixed():
    import pymupdf
    txt = MD.read_bytes().decode("utf-8").replace("\r\n", "\n")
    return txt, cf.fix_document(txt, pymupdf.open(PDF))


@needs_files
def test_w21_known_cells():
    txt, (new, changes, _) = _fixed()
    assert "| VLCC TCE | 38806 | -5551 | 44357 |" in new
    assert "| Baltic Dry Indices | BDI | 1296 | -51 | 1347 |" in new
    assert "| Tankers | Vlcc | 305000 | 108.542 | DOWN |" in new
    assert "| Bulkers | Panamax | 82500 | 31.807 | UP |" in new
    assert "| Sale and Purchase Index | DSPA | 3.590 |" in new
    assert "| Containers | Subcontinent | 6000 - 10000 | N/A |" in new
    assert all(c["pdf_evidence"] for c in changes)


@needs_files
def test_w21_only_changed_cells_differ():
    txt, (new, changes, _) = _fixed()
    a, b = txt.split("\n"), new.split("\n")
    assert len(a) == len(b)
    assert {i + 1 for i, (x, y) in enumerate(zip(a, b)) if x != y} == {c["line"] for c in changes}


@needs_files
def test_w21_idempotent():
    import pymupdf
    _, (new, _, _) = _fixed()
    again, changes, _ = cf.fix_document(new, pymupdf.open(PDF))
    assert changes == [] and again == new


@needs_files
def test_arrow_colours_come_from_pdf():
    import pymupdf
    arrows = cf.page2_arrows(pymupdf.open(PDF)[1])
    got = {(a["section"], a["label"]): a["colour"] for a in arrows}
    assert got[("BSPA", "VLCC")] == "red" and got[("BSPA", "MR PRODUCT")] == "green"
    assert got[("BDA", "TANKERS")] == "red"
    assert re.fullmatch(r"[A-Z]{4}", "DSPA") and got[("INDEX", "DSPA")] == "red"


def _span(x0, x1, y, text, color=0):
    return {"x0": x0, "x1": x1, "yc": y, "text": text, "color": color}


def test_bspa_label_is_nearest_in_y_and_skips_section_labels(monkeypatch):
    spans = [
        _span(10, 40, 100, "BSPA as reported (5 years old Vessels)"),
        _span(10, 40, 138, "Tankers"),          # section label, nearer in y than the real label
        _span(10, 40, 141, "VLCC"),
        _span(10, 40, 150, "AFRAMAX"),
        _span(230, 236, 141, cf.ARROW, 0xFF0000),
        _span(20, 60, 300, "Sale and Purchase Index"),
    ]

    class Rect:
        width = 595.0

    class FakePage:
        rect = Rect()

    monkeypatch.setattr(cf, "page_spans", lambda page: spans)
    (a,) = cf.page2_arrows(FakePage())
    assert a["section"] == "BSPA" and a["label"] == "VLCC" and a["colour"] == "red"


@needs_files
def test_evidence_is_bound_to_the_row():
    import pymupdf
    pw = cf.page_words(pymupdf.open(PDF))
    vlcc = cf.bound_tokens(pw, "BSPA Secondhand Market Assessments (5 Years Old)",
                           ["Tankers", "Vlcc", "305000", "108.542", "UP"])
    assert "108.542" in vlcc and "64.072" not in vlcc
    tradership = cf.bound_tokens(pw, "Second-hand Market Reported Sold", ["TRADERSHIP", "BC"])
    assert tradership["176925"] == "176,925" and "119480" not in tradership   # comma-free key
    bdi = cf.bound_tokens(pw, "Market & Baltic Indices", ["Baltic Dry Indices", "BDI"])
    assert "1296" in bdi and "1809" not in bdi
    assert cf.bound_tokens(pw, "Some Other Table", ["x", "y"]) is None


@needs_files
def test_comma_printed_integer_is_fixed_not_skipped():
    _, (new, changes, _) = _fixed()
    assert "| TRADERSHIP | BC | 176925 |" in new
    assert any(c["old"] == "176925.0" and c["pdf_evidence"] == "PDF printed 176,925" for c in changes)


def test_apply_is_dry_run_by_default_and_only_touches_logged_files(tmp_path, monkeypatch):
    import json
    import hashlib
    monkeypatch.setattr(cf, "REPO_ROOT", tmp_path)
    md = tmp_path / cf.MD_ROOT_REL / "2025"
    st = tmp_path / cf.STAGING_REL / "2025"
    md.mkdir(parents=True)
    st.mkdir(parents=True)
    (md / "a.md").write_bytes(b"old\r\n")
    (md / "b.md").write_bytes(b"untouched\r\n")
    (st / "a.md").write_bytes(b"new\r\n")
    (st / "b.md").write_bytes(b"stray staged file without changelog\r\n")
    (st / "a.changelog.json").write_text(json.dumps({
        "md": str(cf.MD_ROOT_REL / "2025" / "a.md"), "changes": [{"line": 1}],
        "source_sha256": hashlib.sha256(b"old\r\n").hexdigest()}))
    staging = tmp_path / cf.STAGING_REL
    r = cf.apply_staged(staging, tmp_path / cf.MD_ROOT_REL, False)
    assert r["dry_run"] and len(r["applied"]) == 1 and (md / "a.md").read_bytes() == b"old\r\n"
    cf.apply_staged(staging, tmp_path / cf.MD_ROOT_REL, True)
    assert (md / "a.md").read_bytes() == b"new\r\n" and (md / "b.md").read_bytes() == b"untouched\r\n"
    (md / "a.md").write_bytes(b"edited meanwhile\r\n")
    r = cf.apply_staged(staging, tmp_path / cf.MD_ROOT_REL, True)
    assert r["refused"] and (md / "a.md").read_bytes() == b"edited meanwhile\r\n"
