"""Tests for scripts/md_cleanup/star_asia_fix.py (targeted Star Asia MD fixer)."""
import hashlib
import json
from pathlib import Path

import pytest

from scripts.md_cleanup import star_asia_fix as sf

PDF = Path(r"C:\Users\Dell\Github\Shipping\corpus\01-brokers\star_asia\2023"
           r"\star_asia_2023_W01_Market-report-Week-1.pdf")
# pre-fix excerpt (pages 8-9) of the W01 2023 MD, committed so tests do not depend on live MDs
MD = Path(__file__).parent / "fixtures" / "star_asia" / "star_asia_2023_W01_prefix.md"
needs_files = pytest.mark.skipif(not PDF.exists(), reason="local-only PDF missing")

FOOTER = "#### Star Asia Shipbroking Pte Ltd ( www.star-asia.com.sg )"


def _span(x0, x1, y, text, size=10.0):
    return {"x0": x0, "x1": x1, "yc": y, "text": text, "size": size}


def _snapshot_spans():
    """Synthetic page laid out like the 2023 template (columns 168/234/300/377/447)."""
    sp = [_span(181, 435, 82, "Ship Recycling Market Snapshot ", 16),
          _span(67, 139, 105.6, "DESTINATION "), _span(168, 217, 105.6, "TANKERS "),
          _span(234, 284, 105.6, "BULKERS  "), _span(310, 339, 105.6, "MPP/ "),
          _span(300, 349, 119.6, "GENERAL "), _span(305, 344, 133.5, "CARGO "),
          _span(367, 438, 105.6, "CONTAINERS  "), _span(469, 542, 105.6, "SENTIMENTS / "),
          _span(463, 548, 119.6, "WEEKLY FUTURE "), _span(487, 526, 133.5, "TREND  ")]
    rows = [(160.8, ["ALANG (WC INDIA)"], ["550 ~ 560", "530 ~ 540", "550 ~ 560", "580 ~ 590"], "IMPROVING /"),
            (208.9, ["CHATTOGRAM,", "BANGLADESH"], ["*520 ~ 530", "*510 ~ 520", "*500 ~ 510", "*550 ~ 560"], "STABLE /"),
            (253.0, ["GADDANI, PAKISTAN"], ["*550 ~ 560", "*540 ~ 550", "*520 ~ 530", "*580 ~ 590"], "STABLE /"),
            (298.3, ["TURKEY"], ["270 ~ 280", "260 ~ 270", "250 ~ 260", "300 ~ 310"], "STABLE /")]
    for y, label, prices, sent in rows:
        ly = y - 12 if label == ["TURKEY"] else y         # the Turkey label sits above its price row
        for k, part in enumerate(label):
            sp.append(_span(55, 150, ly + (k - (len(label) - 1) / 2) * 14, part + " "))
        for x, p in zip((168, 233, 300, 377), prices):
            sp.append(_span(x, x + 50, y, p + " "))
        sp.append(_span(447, 500, y, sent + "  "))
    sp.append(_span(53, 57, 300.0, "*"))                       # Turkey footnote, in the label cell
    sp.append(_span(57, 152, 300.7, "For Non-EU ships. For EU ", 8))
    sp.append(_span(63, 140, 321.9, "Ship, the prices are about less", 8))
    sp += [_span(90, 93, 359.6, "-", 9), _span(108, 352, 360.0, "All prices are USD per light displacement tonnage.  ", 8),
           _span(90, 93, 371.0, "-", 9), _span(108, 346, 371.4, "The prices reported are net.  ", 8),
           _span(108, 509, 393.2, "continued on a second printed line.  ", 8),
           _span(134, 500, 441.8, "5-Year Ship Recycling Average Historical Prices ", 16)]
    # 5-year table below: plain numbers in the same columns must not be taken as snapshot rows
    sp += [_span(233, 251, 519.6, "440"), _span(306, 323, 519.6, "430"),
           _span(233, 251, 532.2, "430"), _span(306, 323, 532.2, "430")]
    return sp


def test_split_join_roundtrip():
    line = "| ALANG (WC INDIA) | 550 ~ 560 | 530 ~ 540 | 550 ~ 560 | 580 ~ 590 | IMPROVING / |"
    assert sf.join_row(sf.split_row(line)) == line
    assert sf.is_sep("|---|---|") and sf.is_sep("| :--- | :---: |") and not sf.is_sep("| a | b |")


def test_join_spans_only_spaces_where_pdf_has_a_gap():
    sp = [_span(53, 57, 300, "*"), _span(57, 100, 300, "For Non-EU "), _span(120, 150, 300, "ships")]
    assert sf.join_spans(sp) == "*For Non-EU ships"


def test_wrapped_capital_tail_is_glued_to_word_above():
    sp = [_span(385, 442, 122, "CONTAINER"), _span(411, 422, 139, "S  ")]
    assert sf.lines_text(sp) == "CONTAINERS"
    assert sf.lines_text([_span(300, 349, 119, "GENERAL "), _span(305, 344, 133, "CARGO ")]) == "GENERAL CARGO"


def test_extract_snapshot_binds_cells_by_row_and_column():
    snap = sf.extract_snapshot(_snapshot_spans())
    assert snap["header"] == ["DESTINATION", "TANKERS", "BULKERS", "MPP/ GENERAL CARGO", "CONTAINERS",
                              "SENTIMENTS / WEEKLY FUTURE TREND"]
    assert snap["rows"][0] == ["ALANG (WC INDIA)", "550 ~ 560", "530 ~ 540", "550 ~ 560", "580 ~ 590", "IMPROVING /"]
    assert snap["rows"][1][0] == "CHATTOGRAM, BANGLADESH"
    assert snap["rows"][1][1] == sf.ESC_STAR + "520 ~ 530"
    assert snap["rows"][3][0] == "TURKEY " + sf.ESC_STAR + "For Non-EU ships. For EU Ship, the prices are about less"
    assert len(snap["rows"]) == 4                      # the 5-year table is not part of the snapshot
    assert snap["notes"] == ["All prices are USD per light displacement tonnage.",
                             "The prices reported are net. continued on a second printed line."]
    assert all(c["x0"] is not None for c in snap["cells"])


def test_missing_price_cell_is_unresolved_not_guessed():
    spans = [s for s in _snapshot_spans() if s["text"].strip() != "*520 ~ 530"]
    with pytest.raises(sf.SnapshotError):
        sf.extract_snapshot(spans)


def test_stray_dot_under_label_is_dropped_and_recorded():
    spans = _snapshot_spans() + [_span(99, 100, 175.0, ".", 8)]
    snap = sf.extract_snapshot(spans)
    assert snap["rows"][0][0] == "ALANG (WC INDIA)" and "." in snap["ignored"]


def test_furniture_match_is_whole_line_and_markup_tolerant():
    fur = {("star asia shipbroking pte ltd ( www.star-asia.com.sg )", 129):
           {"text": "Star Asia Shipbroking Pte Ltd ( www.star-asia.com.sg )", "yc": 779.8, "pages": 15},
           ("page #", 124): {"text": "Page 10", "yc": 750.0, "pages": 10}}
    assert sf.furniture_match(FOOTER, fur)
    assert sf.furniture_match("[Star Asia Shipbroking Pte Ltd ( www.star-asia.com.sg )](http://www.star-asia.com.sg/)", fur)
    assert sf.furniture_match("Page 3", fur)
    assert sf.furniture_match("## Page 3", fur) is None         # extractor page marker, not PDF furniture
    assert sf.furniture_match("The Star Asia Shipbroking Pte Ltd ( www.star-asia.com.sg ) said", fur) is None
    assert sf.furniture_match("| Star Asia Shipbroking Pte Ltd ( www.star-asia.com.sg ) |", fur) is None


def test_find_region_shapes():
    broken = ["## Ship Recycling Market Snapshot", "", "| a | b |", "|---|---|", "", "stray text", "",
              "- All prices are USD per light displacement tonnage in the long ton.", "- The prices reported",
              "", "## 5-Year Ship Recycling Average Historical Prices"]
    assert sf.find_region(broken) == (1, 7, False, False)
    swallowed = broken[:7] + ["- All prices are USD per light displacement tonnage in the long ton. - The prices reported are net"] \
        + ["", "## 5-Year Ship Recycling Average Historical Prices"]
    assert sf.find_region(swallowed) == (1, 9, True, False)
    assert sf.find_region(["# nothing here"]) is None
    headless = ["## Page 9", "", "| Ship DESTINATION | Ship Recycling TANKERS | Market Snapshot CONTAINERS |", "|---|---|---|",
                "", "- All prices are USD per light displacement tonnage in the long ton.", ""]
    assert sf.find_region(headless) == (2, 5, False, True)


class FakeDoc(list):
    pass


def _patch_pdf(monkeypatch, fur):
    monkeypatch.setattr(sf, "snapshot_page", lambda doc: "page")
    monkeypatch.setattr(sf, "page_spans", lambda page: _snapshot_spans())
    monkeypatch.setattr(sf, "pdf_furniture", lambda doc: fur)


FUR = {("star asia shipbroking pte ltd ( www.star-asia.com.sg )", 129):
       {"text": "Star Asia Shipbroking Pte Ltd ( www.star-asia.com.sg )", "yc": 779.8, "pages": 15}}


def test_fix_document_replaces_region_removes_footer_and_nothing_else(monkeypatch):
    _patch_pdf(monkeypatch, FUR)
    text = "\n".join([
        "intro", "", "## Ship Recycling Market Snapshot", "",
        "| DESTINATION | TANKERS |", "|---|---|", "", "ALANG 550 ~ 560", "",
        "- All prices are USD per light displacement tonnage in the long ton.", "",
        FOOTER, "", "## Page 10", "", "tail text", ""])
    new, changes, unresolved = sf.fix_document(text, FakeDoc(range(15)))
    assert unresolved == []
    assert {c["class"] for c in changes} == {"snapshot", "footer"}
    lines = new.split("\n")
    assert lines[:3] == ["intro", "", "## Ship Recycling Market Snapshot"]
    assert lines[6].startswith("| ALANG (WC INDIA) |") and lines[9].startswith("| TURKEY ")
    assert "- All prices are USD per light displacement tonnage in the long ton." in lines
    assert FOOTER not in new and "## Page 10" in lines and lines[-2:] == ["tail text", ""]
    assert "\n\n\n" not in new                      # no double blank left behind by the footer
    foot = [c for c in changes if c["class"] == "footer"][0]
    assert foot["line"] == 12 and "779.8" in foot["pdf_evidence"]


def test_good_table_is_left_alone_and_fix_is_idempotent(monkeypatch):
    _patch_pdf(monkeypatch, FUR)
    text = "\n".join(["## Ship Recycling Market Snapshot", "", "| x |", "|---|", "", "- All prices are USD per light "
                      "displacement tonnage in the long ton.", ""])
    new, _, _ = sf.fix_document(text, FakeDoc(range(15)))
    again, changes, _ = sf.fix_document(new, FakeDoc(range(15)))
    assert changes == [] and again == new


def test_unreadable_table_is_reported_and_left_untouched(monkeypatch):
    _patch_pdf(monkeypatch, {})
    monkeypatch.setattr(sf, "page_spans", lambda page: [_span(181, 435, 82, "Ship Recycling Market Snapshot ", 16)])
    text = "## Ship Recycling Market Snapshot\n\nbroken text\n\n- All prices are USD per light displacement tonnage in the long ton.\n"
    new, changes, unresolved = sf.fix_document(text, FakeDoc(range(15)))
    assert new == text and changes == [] and unresolved[0]["class"] == "snapshot"


def test_unmatched_url_line_is_reported_not_removed(monkeypatch):
    _patch_pdf(monkeypatch, {})
    text = "intro\n\nSee www.star-asia.com.sg for more\n"
    new, _, unresolved = sf.fix_document(text, FakeDoc(range(15)))
    assert "See www.star-asia.com.sg for more" in new
    assert any(u["class"] == "footer" for u in unresolved)


def _fixed():
    import pymupdf
    txt = MD.read_bytes().decode("utf-8").replace("\r\n", "\n")
    return txt, sf.fix_document(txt, pymupdf.open(PDF))


@needs_files
def test_w01_2023_snapshot_rebuilt_from_pdf():
    txt, (new, changes, unresolved) = _fixed()
    assert unresolved == []
    assert "| DESTINATION | TANKERS | BULKERS | MPP/ GENERAL CARGO | CONTAINERS | SENTIMENTS / WEEKLY FUTURE TREND |" in new
    assert "| ALANG (WC INDIA) | 550 ~ 560 | 530 ~ 540 | 550 ~ 560 | 580 ~ 590 | IMPROVING / |" in new
    assert "| CHATTOGRAM, BANGLADESH | \\*520 ~ 530 | \\*510 ~ 520 | \\*500 ~ 510 | \\*550 ~ 560 | STABLE / |" in new
    assert "| GADDANI, PAKISTAN | \\*550 ~ 560 | \\*540 ~ 550 | \\*520 ~ 530 | \\*580 ~ 590 | STABLE / |" in new
    assert "| 270 ~ 280 | 260 ~ 270 | 250 ~ 260 | 300 ~ 310 | STABLE / |" in new
    assert "- Prices quoted are basis simple Japanese / Korean-built tonnages trading units. Premiums are paid on top of the " \
           "above-quoted prices based on quality & quality of Spares, Non-Fe., bunkers, cargo history, and maintenance." in new
    snap = [c for c in changes if c["class"] == "snapshot"]
    assert len(snap) == 1 and snap[0]["pdf_evidence"]["cells"]


@needs_files
def test_w01_2023_only_region_and_footers_differ():
    txt, (new, changes, _) = _fixed()
    snap = [c for c in changes if c["class"] == "snapshot"][0]
    foot = [c for c in changes if c["class"] == "footer"]
    assert len(foot) == 2 and all(c["old"] == FOOTER for c in foot) and FOOTER not in new
    old_region, new_region = set(snap["old"]), set(snap["new"])
    kept_old = [ln for ln in txt.splitlines() if ln.strip() and ln != FOOTER and ln not in old_region]
    kept_new = [ln for ln in new.splitlines() if ln.strip() and ln not in new_region]
    assert kept_old == kept_new                        # everything outside the region and footers is identical
    assert "## Page 9" in new and "## Page 8" in new   # page markers are never touched


@needs_files
def test_w01_2023_idempotent():
    import pymupdf
    _, (new, _, _) = _fixed()
    again, changes, _ = sf.fix_document(new, pymupdf.open(PDF))
    assert changes == [] and again == new


@needs_files
def test_run_preserves_crlf_and_writes_changelog(tmp_path, monkeypatch):
    md_dir = tmp_path / sf.MD_ROOT_REL / "2023"
    md_dir.mkdir(parents=True)
    raw = MD.read_bytes().decode("utf-8").replace("\r\n", "\n").replace("\n", "\r\n")
    (md_dir / "star_asia_2023_W01_Market-report-Week-1.md").write_bytes(raw.encode("utf-8"))
    monkeypatch.setattr(sf, "REPO_ROOT", tmp_path)
    out = tmp_path / sf.STAGING_REL
    summary = sf.run(["2023"], None, False, out)
    staged = (out / "2023" / "star_asia_2023_W01_Market-report-Week-1.md").read_bytes()
    assert summary["files_changed"] == 1 and b"\r\n" in staged and b"\n" not in staged.replace(b"\r\n", b"")
    meta = json.loads((out / "2023" / "star_asia_2023_W01_Market-report-Week-1.changelog.json").read_text(encoding="utf-8"))
    assert meta["source_sha256"] == hashlib.sha256(raw.encode("utf-8")).hexdigest()
    assert {c["class"] for c in meta["changes"]} == {"snapshot", "footer"}
    assert summary["page_marker_lines"]["2023"] == 2


def test_apply_is_dry_run_by_default_and_only_touches_logged_files(tmp_path, monkeypatch):
    monkeypatch.setattr(sf, "REPO_ROOT", tmp_path)
    md = tmp_path / sf.MD_ROOT_REL / "2025"
    st = tmp_path / sf.STAGING_REL / "2025"
    md.mkdir(parents=True)
    st.mkdir(parents=True)
    (md / "a.md").write_bytes(b"old\r\n")
    (md / "b.md").write_bytes(b"untouched\r\n")
    (st / "a.md").write_bytes(b"new\r\n")
    (st / "b.md").write_bytes(b"stray staged file without changelog\r\n")
    (st / "a.changelog.json").write_text(json.dumps({
        "md": str(sf.MD_ROOT_REL / "2025" / "a.md"), "changes": [{"line": 1}],
        "source_sha256": hashlib.sha256(b"old\r\n").hexdigest()}))
    staging = tmp_path / sf.STAGING_REL
    r = sf.apply_staged(staging, tmp_path / sf.MD_ROOT_REL, False)
    assert r["dry_run"] and len(r["applied"]) == 1 and (md / "a.md").read_bytes() == b"old\r\n"
    sf.apply_staged(staging, tmp_path / sf.MD_ROOT_REL, True)
    assert (md / "a.md").read_bytes() == b"new\r\n" and (md / "b.md").read_bytes() == b"untouched\r\n"
    (md / "a.md").write_bytes(b"edited meanwhile\r\n")
    r = sf.apply_staged(staging, tmp_path / sf.MD_ROOT_REL, True)
    assert r["refused"] and (md / "a.md").read_bytes() == b"edited meanwhile\r\n"


def test_notes_escape_printed_asterisk():
    spans = _snapshot_spans() + [_span(90, 93, 404.4, "-", 9),
                                 _span(108, 327, 404.7, "* Prices are based on the subject LC.  ", 8)]
    notes = sf.extract_snapshot(spans)["notes"]
    assert notes[-1] == sf.ESC_STAR + " Prices are based on the subject LC."


def test_orphan_fragments_above_heading_are_removed_but_prose_is_kept(monkeypatch):
    _patch_pdf(monkeypatch, {})
    text = "\n".join(["## Page 10", "", "Some real commentary about markets.", "", "DESTINATION", "",
                      "ALANG (WC INDIA)", "", sf.ESC_STAR + "CHATTOGRAM, BANGLADESH GADDANI, PAKISTAN TURKEY", "",
                      "# Ship Recycling Market Snapshot", "", "| x |", "|---|", "",
                      "- All prices are USD per light displacement tonnage in the long ton.", ""])
    new, changes, _ = sf.fix_document(text, FakeDoc(range(15)))
    lines = new.split("\n")
    assert lines[:5] == ["## Page 10", "", "Some real commentary about markets.", "", "# Ship Recycling Market Snapshot"]
    orphan = [c for c in changes if c["class"] == "snapshot_orphan"][0]
    assert orphan["line"] == 5 and "DESTINATION" in orphan["old"]


def test_intact_header_and_rows_are_kept_and_dash_convention_followed(monkeypatch):
    _patch_pdf(monkeypatch, {})
    spans = [dict(s, text=s["text"].replace(" ~ ", "–")) for s in _snapshot_spans()]
    monkeypatch.setattr(sf, "page_spans", lambda page: spans)
    head = "| DESTINATION | TANKERS | BULKERS | GENERAL CARGO | CONTAINERS | OUTLOOK |"
    alang = "| ALANG, INDIA | 550-560 | 530-540 | 550-560 | 580-590 | IMPROVING / |"
    text = "\n".join(["## Ship Recycling Market Snapshot", "", head, "| :--- | :---: | :---: | :---: | :---: | :---: |",
                      alang, "", "stray", "", "- All prices are USD per light displacement tonnage in the long ton.", ""])
    new, changes, _ = sf.fix_document(text, FakeDoc(range(15)))
    lines = new.split("\n")
    assert lines[2] == head and lines[3].startswith("| :---") and lines[4] == alang
    star = sf.ESC_STAR
    assert f"| GADDANI, PAKISTAN | {star}550-560 | {star}540-550 | {star}520-530 | {star}580-590 | STABLE / |" in lines
    assert "–" not in new
    ev = changes[0]["pdf_evidence"]
    assert ev["kept_header"] and ev["kept_rows"] == 1 and ev["ascii_dash"]


def test_apply_without_promote_is_rejected(monkeypatch):
    monkeypatch.setattr("sys.argv", ["star_asia_fix", "--apply"])
    with pytest.raises(SystemExit):
        sf.main()


def test_orphan_rule_keeps_commentary_that_shares_words_with_cells(monkeypatch):
    _patch_pdf(monkeypatch, {})
    text = "\n".join(["## Page 10", "", "Alang", "", "Prices are about the ships", "",
                      "# Ship Recycling Market Snapshot", "", "| x |", "|---|", "",
                      "- All prices are USD per light displacement tonnage in the long ton.", ""])
    new, changes, _ = sf.fix_document(text, FakeDoc(range(15)))
    assert "Alang" in new.split("\n") and "Prices are about the ships" in new.split("\n")
    assert not [c for c in changes if c["class"] == "snapshot_orphan"]
