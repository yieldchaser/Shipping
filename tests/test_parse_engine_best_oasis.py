"""Tests for the Best Oasis weekly ship-recycling parser (profile `best_oasis`, module scripts/parse_engine/best_oasis.py)."""
from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest

from scripts.parse_engine import best_oasis as bo
from scripts.parse_engine import best_oasis_continuity as cont
from scripts.parse_engine import prose
from scripts.parse_engine.config import MAIN_CHECKOUT, REPO_ROOT, load_profile
from scripts.parse_engine.dates import parse_issue_date

PROFILE = load_profile("best_oasis")
PDF_DIR = "corpus/02-hellenic/demolition/pdfs"
TEAL, DARK = (0.07, 0.63, 0.72), (0.02, 0.26, 0.29)


def _text(page: pymupdf.Page, x: float, y: float, text: str, size: float = 9) -> None:
    page.insert_text((x, y), text, fontsize=size)


def _chart_page(legend: tuple[str, str] = ("Previous Week", "This Week"), labels: dict[str, list[str]] | None = None,
                colours: bool = True, bar_fills: tuple = (TEAL, DARK), stacked: bool = False,
                commentary_on_label_row: str | None = None) -> pymupdf.Page:
    """A bar chart drawn like the source slides: title, legend (marker + words), two labelled bars per category,
    category names under the bars."""
    labels = labels or {"Container": ["550", "555"], "Tanker": ["515", "520"], "Bulker": ["495", "505"]}
    doc = pymupdf.open()
    page = doc.new_page(width=900, height=500)
    _text(page, 300, 40, "Price for Recycling Ships in India", 14)
    for k, (name, x) in enumerate(zip(legend, (320, 320) if stacked else (320, 440))):
        y = 63 + (16 * k if stacked else 0)
        if colours:
            page.draw_rect(pymupdf.Rect(x - 14, y - 8, x - 4, y + 2), color=None, fill=(TEAL, DARK)[k])
        _text(page, x, y, name)
    for i, (cat, vals) in enumerate(labels.items()):
        x0 = 220 + i * 160
        for j, v in enumerate(vals):
            bx = x0 + j * 45
            if colours:
                page.draw_rect(pymupdf.Rect(bx, 120 + 5 * j, bx + 40, 300), color=None, fill=bar_fills[j])
            _text(page, bx + 8, 114 + 5 * j, v, 8)
        _text(page, x0 + 20, 320, cat)
    if commentary_on_label_row:
        _text(page, 20, 114, commentary_on_label_row, 8)       # same baseline as the first data labels
    return page


def test_chart_with_two_labels_per_category_becomes_a_table():
    charts = bo.find_charts(_chart_page(), 3)
    assert len(charts) == 1 and charts[0]["note"] is None
    assert charts[0]["columns"] == ["Category", "Previous Week", "This Week"]
    assert charts[0]["rows"] == [["Container", "550", "555"], ["Tanker", "515", "520"], ["Bulker", "495", "505"]]


def test_reversed_legend_swaps_the_series_instead_of_failing():
    page = _chart_page(legend=("This Week", "Previous Week"))
    rows = bo.find_charts(page, 3)[0]["rows"]
    assert rows[0] == ["Container", "555", "550"]          # left bar (first legend entry) is this week


def test_series_follow_the_bar_colour_not_the_position():
    page = _chart_page(legend=("This Week", "Previous Week"), colours=True)
    colours, status = bo._series_colours(page, *_legend(page), [w for w in page.get_text("words") if w[4] in ("550", "555")])
    assert status == "ok" and sorted(colours.values()) == ["previous", "this"]


def _legend(page: pymupdf.Page) -> tuple[list[tuple], list[tuple]]:
    words = page.get_text("words")
    return ([w for w in words if w[4] == "Previous"], [w for w in words if w[4] == "This"])


def test_an_unpaired_label_is_a_figure_note_and_never_a_table():
    page = _chart_page(labels={"Container": ["550", "555"], "Tanker": ["515"], "Bulker": ["495", "505"]})
    c = bo.find_charts(page, 3)[0]
    assert c["note"] and c["rows"] == []
    assert c["note_kind"] == "info" and "cannot be assigned" in c["note"]
    md = bo._chart_md(c, "p3c0")
    assert "> Figure:" in md and "|" not in md                  # a note with the labels as printed, never a table


def test_category_without_labels_stays_empty():
    page = _chart_page(labels={"Container": ["550", "555"], "Tanker": [], "Bulker": ["495", "505"]})
    c = bo.find_charts(page, 3)[0]
    assert c["note"] is None
    assert c["rows"][1] == ["Tanker", "", ""]


def test_chart_without_any_label_is_an_info_note_and_keeps_its_footnote_in_the_text():
    page = _chart_page(labels={"Container": [], "Tanker": [], "Bulker": []})
    _text(page, 300, 200, "*The market remains closed")
    c = bo.find_charts(page, 5)[0]
    assert c["note_kind"] == "info" and c["rows"] == [] and "no data labels" in c["note"]
    footnote = next(w for w in page.get_text("words") if w[4] == "market")
    assert not any(b[0] <= footnote[0] <= b[2] and b[1] <= footnote[1] <= b[3] for b in c["boxes"])


def test_banner_heading_without_categories_is_not_a_chart():
    doc = pymupdf.open()
    page = doc.new_page(width=600, height=400)
    _text(page, 50, 50, "BUNKER PRICES AT PORT", 16)
    assert bo.find_charts(page, 6) == []


def test_axis_ticks_are_never_read_as_data_labels():
    page = _chart_page()
    for k, v in enumerate(["0", "100", "200", "300"]):
        _text(page, 170, 300 - 60 * k, v)                  # right-aligned tick column at the left of the plot
    c = bo.find_charts(page, 3)[0]
    assert c["note"] is None and len(c["rows"]) == 3


def test_label_value_blocks_pair_each_title_with_its_own_column():
    doc = pymupdf.open()
    page = doc.new_page(width=800, height=300)
    for x, title, vals in ((50, "USD / INR", ("95.9", "95.51", "Loss", "0.39")),
                           (250, "USD / BDT", ("122.83", "123.39", "Gain", "0.56"))):
        _text(page, x, 60, title)
        _text(page, x, 90, "This Week : " + vals[0])
        _text(page, x, 105, "Previous Week : " + vals[1])
        _text(page, x, 120, f"{vals[2]} : {vals[3]}")
    (table,) = bo.kv_tables(page, 2)
    assert table["rows"] == [["USD / INR", "95.9", "95.51", "Loss 0.39"], ["USD / BDT", "122.83", "123.39", "Gain 0.56"]]


def test_crude_lines_are_kept_as_printed_without_labelling_the_figures():
    doc = pymupdf.open()
    page = doc.new_page(width=600, height=300)
    _text(page, 40, 60, "BRENT CRUDE: (104.86 103.16) - 1.7")
    _text(page, 40, 90, "WTI CRUDE: (99.78 101.05) +1.27")
    (table,) = bo.crude_table(page, 3)
    assert table["rows"] == [["BRENT CRUDE", "(104.86 103.16)", "- 1.7"], ["WTI CRUDE", "(99.78 101.05)", "+1.27"]]


def test_header_printed_over_merged_cells_moves_onto_its_data_column():
    raw = [["Vessel Name", "Type of Vessel", "", "", "", "Country of Build", "LDT", "Term of Sale"],
           ["", "", "", "Year of", "", "", "", ""], ["", "", "", "Build", "", "", "", ""],
           ["Moon Spring", "Tanker", "1996", "", "", "Singapore", "2,354.40", "Delivered"],
           ["Kutch Bay", "Tanker", "1997", "", "", "Japan", "16,701.00", "As-Is"]]
    cols, rows = bo.normalise_table(raw)
    assert cols == ["Vessel Name", "Type of Vessel", "Year of Build", "Country of Build", "LDT", "Term of Sale"]
    assert rows[0] == ["Moon Spring", "Tanker", "1996", "Singapore", "2,354.40", "Delivered"]


def test_table_without_a_numeric_row_is_not_a_table():
    assert bo.normalise_table([["A", "B"], ["x", "y"]]) is None


def test_turkiye_glyph_and_apostrophes_are_restored():
    assert bo.fix_text("T�rkiye") == "Türkiye"
    assert bo.fix_text("market�s") == "market’s"


def test_beaching_dates_become_a_label_and_bullets():
    class L:
        def __init__(self, t): self.plain = t

    class P:
        lines = [L("Beaching Dates"), L("10 May to 13 May 2024"), L("21 May to 29 May 2024")]
    assert bo._beaching_text(P) == "**Beaching Dates:**\n- 10 May to 13 May 2024\n- 21 May to 29 May 2024"


def test_beaching_label_and_its_date_lines_form_one_block_so_the_label_is_not_cleaned_away():
    doc = pymupdf.open()
    page = doc.new_page(width=600, height=400)
    for y, t in ((100, "Beaching Dates"), (125, "10 May to 13 May 2024"), (145, "Throughout the month")):
        _text(page, 60, y, t, 12)
    body = prose.body_font_size(doc, [1])
    (para,) = bo.group_beaching(prose.page_prose(page, 1, [], set(), body))
    assert para.text == "**Beaching Dates:**\n- 10 May to 13 May 2024\n- Throughout the month"


def test_a_sentence_set_in_large_type_over_several_paragraphs_is_joined():
    doc = pymupdf.open()
    page = doc.new_page(width=800, height=400)
    for y, t in ((100, "The forum brings the whole industry together to discuss and"), (150, "strategize the way forward amidst the complexities and"), (200, "changing landscape of the industry.")):
        _text(page, 60, y, t, 20)
    body = prose.body_font_size(doc, [1])
    paras = bo.merge_split_sentences(prose.page_prose(page, 1, [], set(), body))
    assert len(paras) == 1 and "complexities and changing landscape" in prose._join_lines(paras[0].lines)


def test_issue_date_is_the_filename_date_and_ranges_never_become_dates():
    iso, src, conflict, header = parse_issue_date(PROFILE["date_patterns"], "( 12 SEPTEMBER - 18 SEPTEMBER) 2026",
                                                  "2026-09-19_best-oasis-weekly-recycling-market-report_x.pdf")
    assert (iso, src, conflict, header) == ("2026-09-19", "filename", False, None)


def test_profile_selects_the_best_oasis_prose_engine_and_promotes_into_its_own_folder():
    assert PROFILE["geom"]["prose_engine"] == "best_oasis"
    assert PROFILE["promotion"]["dest"] == PROFILE["promotion"]["legacy_dirs"][0] == "data/extracted/md/hellenic/demolition/best_oasis"
    assert PROFILE["sidecar_vessel_rows"] is False


def _sample(name: str) -> Path | None:
    for base in (MAIN_CHECKOUT, REPO_ROOT):
        p = base / PDF_DIR / name
        if p.exists():
            return p
    return None


@pytest.mark.parametrize("name,min_tables,must_contain", [
    ("2021-07-03_Weekly-Ship-Recycling-Report.pdf", 8, ["| Moon Spring | Tanker | 1996 |", "| Houston | 617 | 624 |"]),
    ("2024-05-10_Weekly-Ship-Recycling-Report-04-May-10-May-2024_compressed.pdf", 10,
     ["| Container | 550 | 555 |", "| Brent Crude | 84.36 | 83.56 | + 0.8 |", "| USD / INR | 83.51 | 83.42 | Lost 0.09 |"]),
    ("2026-09-19_best-oasis-weekly-recycling-market-report-18-september-2026_weekly-ship-recycling-report-12-sept_e014d3c2af15.pdf", 4,
     ["| INDIA | FIRM | 485 | 455 | 440 | (0) |", "| LEO STAR | MOTORTANKER | 1,961 |"]),
])
def test_sample_issues_extract_tables_commentary_and_pass_validation(tmp_path, name, min_tables, must_contain):
    from scripts.parse_engine import engine as eng
    pdf = _sample(name)
    if pdf is None:
        pytest.skip("corpus PDF not available")
    plan = eng.plan_file(pdf, PROFILE)
    row = eng.run_file(plan, PROFILE, "best_oasis", tmp_path, "pymupdf_table", "geom", None, {"spent": 0})
    md = Path(row["output"]).read_text(encoding="utf-8")
    assert row["passed"], row["flags"]
    assert row["tables"] >= min_tables and row["numeric_axis_runs"] == 0 and row["garbage_chars"] == 0
    for needle in must_contain:
        assert needle in md
    assert "Contact" not in md and "Disclaimer" not in md


def test_picture_chart_uses_legend_order_even_when_the_legend_is_reversed():
    page = _chart_page(legend=("This Week", "Previous Week"), colours=False)
    c = bo.find_charts(page, 3)[0]
    assert c["series_basis"] == "legend_order" and c["rows"][0] == ["Container", "555", "550"]


def test_stacked_legend_without_colours_is_a_note_not_a_guess():
    page = _chart_page(colours=False, stacked=True)
    c = bo.find_charts(page, 3)[0]
    assert c["rows"] == [] and c["note_kind"] == "info" and "stacked" in c["note"]


def test_stacked_legend_with_colours_still_resolves_by_colour():
    page = _chart_page(stacked=True)
    c = bo.find_charts(page, 3)[0]
    assert c["series_basis"] == "colour" and c["rows"][0] == ["Container", "550", "555"]


def test_colour_and_legend_order_disagreeing_is_flagged():
    page = _chart_page(bar_fills=(DARK, TEAL))             # bars drawn in the opposite colour order to the legend
    c = bo.find_charts(page, 3)[0]
    assert c["rows"] == [] and c["note_kind"] == "flag" and "disagree" in c["note"]


def test_bars_of_one_colour_are_flagged():
    page = _chart_page(bar_fills=(TEAL, TEAL))
    c = bo.find_charts(page, 3)[0]
    assert c["rows"] == [] and c["note_kind"] == "flag"


def test_two_candidate_marker_fills_make_the_chart_ambiguous():
    page = _chart_page()
    page.draw_rect(pymupdf.Rect(305, 54, 313, 62), color=None, fill=(0.9, 0.1, 0.1))     # second marker under "Previous Week"
    c = bo.find_charts(page, 3)[0]
    assert c["rows"] == [] and c["note_kind"] == "flag" and "ambiguous" in c["note"]


def test_commentary_sharing_a_baseline_with_a_chart_label_keeps_its_words():
    page = _chart_page(commentary_on_label_row="the previous week with little activity.")
    bo._remove_words(page, [r for c in bo.find_charts(page, 3) for r in c["apparatus"]])
    text = page.get_text()
    assert "previous week with little activity." in text and "550" not in text and "Container" not in text


def test_running_text_saying_previous_week_is_not_a_legend():
    page = _chart_page(commentary_on_label_row="is comparable to the previous week with")
    page.insert_text((60, 150), "Previous week saw less", fontsize=9)
    c = bo.find_charts(page, 3)[0]
    assert c["note"] is None and c["rows"][0] == ["Container", "550", "555"]


def _table(title, page, rows, basis="legend_order", country="india", cid="p2c0"):
    return {"title": title, "page": page, "rows": rows, "series_basis": basis, "country": country, "printed": "", "chart_id": cid}


HMS = "Price of HMS 1&2 (80:20) and Shredded"
SHIPS = "Price for Recycling Ships in India"


def test_continuity_keeps_a_chart_with_two_cells_confirmed_in_the_stated_orientation():
    t = _table(SHIPS, 2, [["Container", "530", "540"], ["Tanker", "520", "525"]])
    nxt = _table(SHIPS, 2, [["Container", "540", "560"], ["Tanker", "525", "530"]])
    keep, _, contradiction = cont.verdict(t, None, nxt)
    assert keep and not contradiction


def test_continuity_needs_two_confirming_cells_and_a_majority():
    t = _table(SHIPS, 2, [["Container", "530", "540"], ["Tanker", "520", "525"], ["Bulker", "510", "515"]])
    one = _table(SHIPS, 2, [["Container", "540", "560"], ["Tanker", "999", "530"], ["Bulker", "998", "520"]])
    keep, reason, contradiction = cont.verdict(t, None, one)
    assert not keep and not contradiction and "1 of 3" in reason
    single = _table(SHIPS, 2, [["Container", "530", "540"]])
    assert not cont.verdict(single, None, _table(SHIPS, 2, [["Container", "540", "560"]]))[0]     # one cell is not enough


def test_continuity_contradiction_in_the_swapped_orientation_is_flagged():
    t = _table(SHIPS, 2, [["Container", "530", "540"], ["Tanker", "520", "525"]])
    nxt = _table(SHIPS, 2, [["Container", "560", "530"], ["Tanker", "540", "520"]])           # chains only when swapped
    keep, reason, contradiction = cont.verdict(t, None, nxt)
    assert not keep and contradiction and "contradicts" in reason


def test_continuity_without_a_neighbour_is_a_note():
    t = _table(SHIPS, 2, [["Container", "530", "540"], ["Tanker", "520", "525"]])
    assert cont.verdict(t, None, None)[:2] == (False, "no adjacent issue with this chart to check the week-to-week continuity")


def test_a_stale_chart_repeated_in_two_issues_is_still_judged_by_its_neighbours():
    """Pakistan HMS 2021-07-17 and 2021-07-24 print the same 540 -> 530 chart (the publisher did not update it)."""
    rows = [["HMS 80:20", "540", "530"], ["Shredded", "555", "546"]]
    issue_17, issue_24 = (_table(HMS, 4, rows, country="pakistan") for _ in range(2))
    issue_31 = _table(HMS, 4, [["HMS 80:20", "530", "535"], ["Shredded", "546", "550"]], country="pakistan")
    assert cont.verdict(issue_24, issue_17, issue_31)[0]            # 530 and 546 (this, 07-24) chain to the 07-31 previous week


def _md_with_three_hms_charts() -> str:
    parts = []
    for cid, country, vals in (("p3c1", "India", ("500", "505")), ("p4c1", "Bangladesh", ("535", "540")), ("p5c1", "Pakistan", ("540", "530"))):
        parts.append(f"<!-- bo-chart {cid} -->\n### {HMS}\n\n| Category | Previous Week | This Week |\n|---|---|---|\n"
                     f"| HMS 80:20 | {vals[0]} | {vals[1]} |\n\nCommentary of {country}.")
    return "\n\n".join(parts)


def test_only_the_marked_chart_is_replaced_when_three_headings_are_identical():
    md = _md_with_three_hms_charts()
    out = cont.strip_markers(cont.replace_chart_table(md, "p4c1", "> Figure: demoted"))
    assert out.count("> Figure: demoted") == 1
    assert "| HMS 80:20 | 500 | 505 |" in out and "| HMS 80:20 | 540 | 530 |" in out and "535" not in out
    assert out.index("demoted") > out.index("500") and out.index("demoted") < out.index("540 | 530")     # middle one only
    assert "bo-chart" not in out


def test_replacement_fails_loudly_on_a_missing_or_duplicated_marker():
    md = _md_with_three_hms_charts()
    with pytest.raises(cont.ContinuityError):
        cont.replace_chart_table(md, "p9c9", "> Figure: x")
    with pytest.raises(cont.ContinuityError):
        cont.replace_chart_table(md + "\n\n<!-- bo-chart p4c1 -->\n", "p4c1", "> Figure: x")


def test_promote_refuses_an_issue_without_the_continuity_marker(tmp_path):
    from scripts.parse_engine import promote
    d = tmp_path / "best_oasis" / "2021"
    d.mkdir(parents=True)
    (d / "a.md").write_text("---\nissue_date: '2021-07-03'\nsource_file: x.pdf\n---\nbody\n", encoding="utf-8")
    (d / "a.validation.json").write_text('{"flags": []}', encoding="utf-8")
    assert promote.load_staged(tmp_path, "best_oasis", "continuity_ran")[0].flags == ["missing_continuity_ran"]
    (d / "a.validation.json").write_text('{"flags": [], "continuity_ran": true}', encoding="utf-8")
    assert promote.load_staged(tmp_path, "best_oasis", "continuity_ran")[0].flags == []


def test_equal_labels_need_no_series_assignment_even_when_both_markers_share_a_colour():
    page = _chart_page(labels={"Container": ["470", "470"], "Tanker": ["445", "445"], "Bulker": ["435", "435"]},
                       bar_fills=(TEAL, TEAL))
    page.draw_rect(pymupdf.Rect(426, 54, 436, 64), color=None, fill=TEAL)          # second marker, same colour as the first
    c = bo.find_charts(page, 3)[0]
    assert c["series_basis"] == "series_equal" and c["rows"][0] == ["Container", "470", "470"] and c["note"] is None


def test_chart_title_sharing_a_baseline_with_commentary_is_still_found():
    page = _chart_page()
    _text(page, 20, 40, "same baseline text", 14)
    charts = bo.find_charts(page, 3)
    assert len(charts) == 1 and charts[0]["rows"][0] == ["Container", "550", "555"]


def test_commentary_numbers_that_line_up_are_not_taken_for_axis_ticks_or_removed():
    page = _chart_page()
    for k, v in enumerate(["12", "345", "6789"]):
        _text(page, 60 + (30 if len(v) < 4 else 0) - 10 * (len(v) - 2), 160 + 40 * k, v)       # right-aligned figures at the left margin
    charts = bo.find_charts(page, 3)
    assert len(charts) == 1 and charts[0]["rows"][0] == ["Container", "550", "555"]
    assert min(b[0] for b in charts[0]["boxes"]) > 150            # the chart's own boxes never reach the commentary column


# ------------------------------------------------------------------------------------------ promote invariants
def _git_repo(root: Path) -> None:
    import subprocess
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "base"], cwd=root, check=True)


def _promote_fixture(tmp_path: Path):
    """A hashed legacy MD that already has the new canonical name, and a plain-named duplicate of the same issue."""
    from scripts.parse_engine import promote
    stem = "2021-07-03_best-oasis-weekly-recycling-market-report-02-july-2021_weekly-ship-recycling-report_137b264ac3ac"
    repo = tmp_path / "repo"
    dest = repo / "data" / "best_oasis"
    (dest / "2021").mkdir(parents=True)
    old_fm = "---\nissue_date: '2021-07-03'\nsource_file: corpus/x/2021-07-03_Weekly-Ship-Recycling-Report.pdf\n---\nOLD\n"
    (dest / "2021" / (stem + ".md")).write_text(old_fm, encoding="utf-8")                     # same name as the new target
    (dest / "2021" / "best_oasis_2021-07-03_2021-07-03_weekly-ship-recycling-report.md").write_text(old_fm, encoding="utf-8")
    other = dest / "2021" / "best_oasis_2021-07-17_2021-07-17_weekly-ship-recycling-report-2.md"       # an issue not re-parsed
    other.write_text("---\nissue_date: '2021-07-17'\nsource_file: corpus/x/b.pdf\n---\nKEEP\n", encoding="utf-8")
    _git_repo(repo)
    stg = tmp_path / "staging" / "best_oasis" / "2021"
    stg.mkdir(parents=True)
    (stg / (stem + ".md")).write_text("---\nissue_date: '2021-07-03'\nsource_file: corpus/x/new.pdf\n---\nNEW\n", encoding="utf-8")
    (stg / (stem + ".validation.json")).write_text('{"flags": [], "continuity_ran": true}', encoding="utf-8")
    plan = promote.build_plan("best_oasis", tmp_path / "staging", dest, [dest], set(), repo_root=repo,
                              name_markers=("oasis", "weekly-ship-recycling-report"), require_marker="continuity_ran")
    return promote, plan, dest, stem, other


def test_promote_target_equal_to_an_old_hashed_name_is_overwritten_never_removed(tmp_path):
    promote, plan, dest, stem, other = _promote_fixture(tmp_path)
    target = dest / "2021" / (stem + ".md")
    assert promote._key(target) not in {promote._key(p) for p in plan.remove}
    report = promote.apply_plan(plan, dest, repo_root=dest.parents[1], allowed_dirs=[dest])
    assert target.read_text(encoding="utf-8").endswith("NEW\n")                                 # the new file survived
    assert not (dest / "2021" / "best_oasis_2021-07-03_2021-07-03_weekly-ship-recycling-report.md").exists()   # duplicate gone
    assert other.exists()                                                                       # unrelated issue untouched
    assert report["git_rm"] == 1 and len(list((dest / "2021").glob("*.md"))) == 2


def test_a_removal_that_is_also_a_target_fails_the_plan_loudly(tmp_path):
    promote, plan, dest, stem, _ = _promote_fixture(tmp_path)
    plan.remove.append(dest / "2021" / (stem + ".md"))
    with pytest.raises(promote.PromoteError):
        promote.assert_plan_invariants(plan, dest)
    with pytest.raises(promote.PromoteError):
        promote.apply_plan(plan, dest, repo_root=dest.parents[1], allowed_dirs=[dest])
    assert (dest / "2021" / (stem + ".md")).read_text(encoding="utf-8").endswith("OLD\n")      # nothing was touched


def test_apply_fails_when_a_promoted_target_is_missing_afterwards(tmp_path, monkeypatch):
    promote, plan, dest, stem, _ = _promote_fixture(tmp_path)
    monkeypatch.setattr(promote.shutil, "copyfile", lambda src, dst: Path(dst).write_text("", encoding="utf-8"))   # silent empty write
    with pytest.raises(promote.PromoteError):
        promote.apply_plan(plan, dest, repo_root=dest.parents[1], allowed_dirs=[dest])
