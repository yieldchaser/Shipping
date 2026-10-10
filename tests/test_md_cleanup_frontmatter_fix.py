"""Tests for scripts/md_cleanup/frontmatter_fix.py (frontmatter-only metadata normaliser).

Synthetic MDs are written under tmp_path; no live data/extracted/md file is read or written.
"""
import json
from pathlib import Path

import pytest

from scripts.md_cleanup import frontmatter_fix as fx

LF = chr(10)
CRLF = chr(13) + chr(10)

PROF = {
    "title": "Test Weekly Report - Week {week}, {year}",
    "publisher": "Test Broker",
}
H1_PROF = {"title": "{h1}", "publisher": "Alibra Shipping Limited"}

BODY = (
    "# Weekly Market Report\n\n"
    "- **Issue Date**: 2023-10-10\n"
    "- **Publisher**: Some Publisher Ltd\n\n"
    "---\n\n## Section\n\n| a | b |\n| --- | --- |\n| 1 | 2 |\n\ntrailing  \n"
)


def write(path: Path, text: str, eol: str = LF) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.replace(LF, eol).encode("utf-8"))
    return path


def split(text: str):
    return fx.split_frontmatter(text)


# ---------------------------------------------------------------- body split
def test_split_no_frontmatter_returns_whole_text_as_body():
    block, body = split("# T\n\ntext\n")
    assert block is None and body == "# T\n\ntext\n"


def test_split_frontmatter_body_starts_after_closing_line():
    block, body = split("---\ntitle: x\n---\n# T\n---\nrule\n")
    assert block == "---\ntitle: x\n---\n"
    assert body == "# T\n---\nrule\n"


def test_split_leading_horizontal_rule_is_not_frontmatter():
    with pytest.raises(fx.FixError):
        split("---\n\nProse here is not yaml\n---\nbody\n")


def test_split_unclosed_block_refused():
    with pytest.raises(fx.FixError):
        split("---\ntitle: x\nbody without close\n")


# ---------------------------------------------------------------- date parsing
@pytest.mark.parametrize("text,iso", [
    ("2023-10-10", "2023-10-10"),
    ("Tuesday 20<sup>th</sup> July 2021", "2021-07-20"),
    ("February 02, 2022", "2022-02-02"),
    ("21st September 2026", "2026-09-21"),
    ("19-Nov-2021", "2021-11-19"),
])
def test_find_dates(text, iso):
    assert fx.find_dates(text) == [iso]


def test_find_dates_rejects_impossible_dates():
    assert fx.find_dates("2023-02-31 and 31 February 2021") == []


def test_banchero_end_requires_monday_of_the_iso_week():
    assert fx.banchero_end(36, 2026, 31, "Aug", 7, "Sep") == "2026-09-07"
    assert fx.banchero_end(36, 2026, 1, "Sep", 8, "Sep") is None        # start is not the ISO-week Monday
    assert fx.banchero_end(37, 2026, 31, "Aug", 7, "Sep") is None       # wrong week number


# ---------------------------------------------------------------- fix_text
def test_adds_block_to_file_without_frontmatter_and_keeps_body_identical(tmp_path):
    md = write(tmp_path / "test_2023_W41_report.md", BODY)
    raw = md.read_bytes().decode("utf-8")
    new, info = fx.fix_text(md, raw, PROF)
    assert info["status"] == "changed"
    block, body = split(new)
    assert body == BODY                       # byte-identical body
    assert new == block + BODY
    assert fx.fm_keys(block)["issue_date"] == "2023-10-10"
    assert fx.fm_keys(block)["year"] == "2023"
    assert fx.fm_keys(block)["report_week"] == "41"
    assert fx.fm_keys(block)["publisher"] == "Some Publisher Ltd"
    assert info["keys_added"][:2] == ["title", "issue_date"]


def test_body_publisher_line_wins_over_profile_constant(tmp_path):
    md = write(tmp_path / "test_2023_W41_report.md", BODY)
    new, _ = fx.fix_text(md, md.read_bytes().decode("utf-8"), PROF)
    assert fx.fm_keys(split(new)[0])["publisher"] == "Some Publisher Ltd"


def test_crlf_preserved_everywhere(tmp_path):
    md = write(tmp_path / "test_2023_W41_report.md", BODY, CRLF)
    raw = md.read_bytes().decode("utf-8")
    new, info = fx.fix_text(md, raw, PROF)
    assert LF not in new.replace(CRLF, "")           # no bare LF introduced
    assert new.endswith(raw)                          # body (== whole original) untouched
    assert new.startswith("---" + CRLF)


def test_mixed_line_endings_refused(tmp_path):
    md = write(tmp_path / "test_2023_W41_report.md", "# T\r\n- **Issue Date**: 2023-10-10\nmore\n")
    with pytest.raises(fx.FixError, match="mixed"):
        fx.fix_text(md, md.read_bytes().decode("utf-8"), PROF)


def test_existing_frontmatter_gets_keys_appended_inside_block_and_old_lines_untouched(tmp_path):
    text = '---\ntitle: "Kept"\nreference_date: "27 August 2026"\nyear: 2026\n---\n' + "# H\n\nbody\n"
    md = write(tmp_path / "test_2026_W35_report.md", text)
    new, info = fx.fix_text(md, text, PROF)
    block, body = split(new)
    assert body == "# H\n\nbody\n"
    old_lines = text.split(LF)[1:4]
    assert block.split(LF)[1:4] == old_lines                          # untouched, same order
    keys = fx.fm_keys(block)
    assert keys["issue_date"] == "2026-08-27"
    assert keys["title"] == "Kept" and keys["year"] == "2026"       # existing values never overwritten
    assert info["keys_added"] == ["issue_date", "report_week", "publisher"]


def test_file_with_issue_date_is_left_alone(tmp_path):
    text = '---\ntitle: x\nissue_date: "2023-01-01"\n---\nbody\n'
    md = write(tmp_path / "a_2023_W01_x.md", text)
    new, info = fx.fix_text(md, text, PROF)
    assert new == text and info["status"] == "unchanged"


def test_no_derivable_date_is_refused_not_guessed(tmp_path):
    md = write(tmp_path / "agora_2021_W27_report.md", "# T\n\nWeek 27 / 2021 (05-09 July)\n")
    with pytest.raises(fx.FixError, match="no date derivable"):
        fx.fix_text(md, md.read_bytes().decode("utf-8"), PROF)


def test_body_and_filename_date_disagreement_is_refused(tmp_path):
    md = write(tmp_path / "x_2023-10-11.md", BODY)
    with pytest.raises(fx.FixError, match="disagree"):
        fx.fix_text(md, md.read_bytes().decode("utf-8"), PROF)


def test_sidecar_date_disagreement_is_refused_and_agreement_accepted(tmp_path):
    md = write(tmp_path / "x_2023_W41_r.md", BODY)
    side = md.with_name(md.stem + ".tables.json")
    side.write_text(json.dumps({"issue_date": "2023-10-09", "report_week": 41}), encoding="utf-8")
    with pytest.raises(fx.FixError, match="disagree"):
        fx.fix_text(md, BODY, PROF)
    side.write_text(json.dumps({"issue_date": "2023-10-10", "report_week": 41}), encoding="utf-8")
    new, info = fx.fix_text(md, BODY, PROF)
    assert fx.fm_keys(split(new)[0])["issue_date"] == "2023-10-10"
    assert {c["src"] for c in info["evidence"]} == {"body:issue date", "sidecar"}


def test_conflicting_weeks_drop_report_week_with_warning(tmp_path):
    md = write(tmp_path / "x_2023_W40_r.md", BODY)
    side = md.with_name(md.stem + ".tables.json")
    side.write_text(json.dumps({"issue_date": "2023-10-10", "report_week": 41}), encoding="utf-8")
    new, info = fx.fix_text(md, BODY, PROF)
    assert "report_week" not in fx.fm_keys(split(new)[0])
    assert any("report_week" in w for w in info["warnings"])


def test_intermodal_issue_line_gives_date_and_week(tmp_path):
    text = "# Weekly Market Report\n\nIssue: Week 28 | Tuesday 20<sup>th</sup> July 2021\n\n## Market insight\n"
    md = write(tmp_path / "intermodal_2021_W28_Intermodal-Report-Week-28-2021.md", text)
    new, _ = fx.fix_text(md, text, {"title": "Intermodal Weekly Market Report - Week {week}, {year}", "publisher": "P"})
    keys = fx.fm_keys(split(new)[0])
    assert keys["issue_date"] == "2021-07-20" and keys["report_week"] == "28"
    assert keys["title"] == "Intermodal Weekly Market Report - Week 28, 2021"
    assert split(new)[1] == text


def test_title_from_h1_when_profile_asks(tmp_path):
    text = "# Weekly Dry Time Charter Estimates, June 14 2023\n\n- **Issue Date**: 2023-06-14\n"
    md = write(tmp_path / "alibra_dry_2023-06-14.md", text)
    new, _ = fx.fix_text(md, text, H1_PROF)
    assert fx.fm_keys(split(new)[0])["title"] == "Weekly Dry Time Charter Estimates, June 14 2023"


def test_title_with_triple_dash_is_dropped(tmp_path):
    text = "# A --- B\n\n- **Issue Date**: 2023-06-14\n"
    md = write(tmp_path / "alibra_dry_2023-06-14.md", text)
    new, info = fx.fix_text(md, text, H1_PROF)
    assert "title" not in info["keys_added"]


def test_source_file_only_written_when_it_exists_in_corpus(tmp_path, monkeypatch):
    monkeypatch.setattr(fx, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(fx, "MAIN_CHECKOUT", tmp_path / "nowhere")
    text = BODY + "\nsource: `corpus/01-brokers/x/a.pdf`\n"
    md = write(tmp_path / "t_2023_W41_a.md", text)
    new, info = fx.fix_text(md, text, PROF)
    assert "source_file" not in fx.fm_keys(split(new)[0])
    assert any("not found under corpus" in w for w in info["warnings"])
    (tmp_path / "corpus/01-brokers/x").mkdir(parents=True)
    (tmp_path / "corpus/01-brokers/x/a.pdf").write_bytes(b"%PDF")
    new, _ = fx.fix_text(md, text, PROF)
    assert fx.fm_keys(split(new)[0])["source_file"] == "corpus/01-brokers/x/a.pdf"


# ---------------------------------------------------------------- driver
def make_tree(tmp_path):
    md_root = tmp_path / "md"
    write(md_root / "src" / "2023" / "t_2023_W41_a.md", BODY)                          # fixable
    write(md_root / "src" / "2023" / "t_2023_W42_b.md", "# T\n\nno date at all\n", CRLF)  # unresolved
    write(md_root / "src" / "2023" / "t_2023_W43_c.md", '---\nissue_date: "2023-10-25"\n---\nx\n')  # has date
    write(md_root / "src" / "2023" / "gms_2023-01-02.md", BODY)                        # skipped flat
    profs = {"src": {**PROF, "skip_flat": "gms_*.md"}}
    return md_root, profs


def test_run_stages_changed_files_and_reports_unresolved(tmp_path):
    md_root, profs = make_tree(tmp_path)
    out = tmp_path / "stage"
    before = {p: p.read_bytes() for p in md_root.rglob("*.md")}
    s = fx.run(None, None, False, out, md_root=md_root, profiles=profs)
    assert {p: p.read_bytes() for p in md_root.rglob("*.md")} == before      # sources untouched
    st = s["per_source"]["src"]
    assert st["changed"] == 1 and st["body_hash_ok"] == 1 and st["unresolved"] == 1
    assert st["already_has_issue_date"] == 1 and st["skipped_flat_files"] == 1
    assert [u["file"] for u in s["unresolved"]] == ["src/2023/t_2023_W42_b.md"]
    staged = out / "src" / "2023" / "t_2023_W41_a.md"
    meta = json.loads((out / "src" / "2023" / "t_2023_W41_a.changelog.json").read_text(encoding="utf-8"))
    assert meta["source_sha256"] == fx.sha((md_root / "src/2023/t_2023_W41_a.md").read_bytes())
    assert meta["staged_sha256"] == fx.sha(staged.read_bytes())
    assert not (out / "src" / "2023" / "gms_2023-01-02.md").exists()


def test_stale_staged_output_is_removed_when_file_no_longer_changes(tmp_path):
    md_root, profs = make_tree(tmp_path)
    out = tmp_path / "stage"
    fx.run(None, None, False, out, md_root=md_root, profiles=profs)
    staged = out / "src" / "2023" / "t_2023_W41_a.md"
    assert staged.exists()
    write(md_root / "src" / "2023" / "t_2023_W41_a.md", '---\nissue_date: "2023-10-10"\n---\n' + BODY)
    fx.run(None, None, False, out, md_root=md_root, profiles=profs)
    assert not staged.exists()
    assert not staged.with_name("t_2023_W41_a.changelog.json").exists()


def test_detect_only_writes_no_staged_files(tmp_path):
    md_root, profs = make_tree(tmp_path)
    out = tmp_path / "stage"
    s = fx.run(None, None, True, out, md_root=md_root, profiles=profs)
    assert s["files_changed"] == 1 and not list(out.rglob("*.md"))


# ---------------------------------------------------------------- promote
def stage_for_promote(tmp_path):
    md_root, profs = make_tree(tmp_path)
    repo = tmp_path / "repo"
    target_dir = repo / "data/extracted/md/src/2023"
    for p in md_root.rglob("*.md"):
        write(target_dir / p.name, p.read_bytes().decode("utf-8").replace(CRLF, LF),
              CRLF if CRLF in p.read_bytes().decode("utf-8") else LF)
    out = tmp_path / "stage"
    fx.run(None, None, False, out, md_root=repo / "data/extracted/md", profiles=profs)
    return repo, out


def test_promote_dry_run_changes_nothing_and_apply_copies(tmp_path):
    repo, out = stage_for_promote(tmp_path)
    target = repo / "data/extracted/md/src/2023/t_2023_W41_a.md"
    before = target.read_bytes()
    r = fx.apply_staged(out, False, repo)
    assert r["dry_run"] and len(r["applied"]) == 1 and target.read_bytes() == before
    r = fx.apply_staged(out, True, repo)
    assert len(r["applied"]) == 1 and target.read_bytes().startswith(b"---")
    assert fx.body_of(target.read_bytes()) == BODY


def test_promote_refuses_changed_target(tmp_path):
    repo, out = stage_for_promote(tmp_path)
    target = repo / "data/extracted/md/src/2023/t_2023_W41_a.md"
    target.write_bytes(target.read_bytes() + b"edited by owner\n")
    r = fx.apply_staged(out, True, repo)
    assert r["applied"] == [] and "changed since staging" in r["refused"][0]["reason"]
    assert target.read_bytes().endswith(b"edited by owner\n")


def test_promote_refuses_tampered_staged_file(tmp_path):
    repo, out = stage_for_promote(tmp_path)
    staged = out / "src/2023/t_2023_W41_a.md"
    staged.write_bytes(staged.read_bytes().replace(b"trailing", b"TRAILING"))
    r = fx.apply_staged(out, True, repo)
    assert r["applied"] == [] and "staged file differs" in r["refused"][0]["reason"]


def test_apply_requires_promote(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["frontmatter_fix", "--apply"])
    with pytest.raises(SystemExit):
        fx.main()


# ---------------------------------------------------------------- survey
def test_survey_reports_date_key_forms(tmp_path):
    md_root = tmp_path / "md"
    write(md_root / "baltic/dry/2015/a.md", '---\ntitle: x\ndate: "2015-09-25"\n---\nb\n')
    write(md_root / "baltic/dry/2015/b.md", '---\ntitle: x\ndate: "August 28, 2018"\n---\nb\n')
    write(md_root / "baltic/dry/2015/c.md", '---\ntitle: x\nissue_date: "2015-09-25"\n---\nb\n')
    r = fx.survey(md_root, {"baltic": "baltic"})["baltic"]["counts"]
    assert r == {"files": 3, "date_key=date/iso": 1, "date_key=date/derivable_text": 1, "has_issue_date": 1}


# ---------------------------------------------------------------- agora ranges
@pytest.mark.parametrize("week,year,args,iso", [
    (27, 2021, (5, None, 9, "July"), "2021-07-09"),
    (39, 2021, (27, "September", 1, "October"), "2021-10-01"),
    (1, 2021, (28, "December", 1, "January"), None),        # end 1 Jan 2021 is ISO week 53 of 2020
    (53, 2020, (28, "December", 1, "January"), "2021-01-01"),
    (1, 2025, (30, "December", 3, "January"), "2025-01-03"),   # rollover into the new ISO year
    (28, 2021, (5, None, 9, "July"), None),                  # not in ISO week 28
])
def test_agora_range_end(week, year, args, iso):
    assert fx.agora_range_end(week, year, *args) == iso


def test_agora_one_token_per_line_range_and_conflict(tmp_path):
    prof = {**PROF, "agora_ranges": True}
    text = "# stem\n\nSNAPSHOT\nWeek\n27\n/\n2021\n(05-09\nJuly)\ntext\n"
    md = write(tmp_path / "agora_2021_W27_x.md", text)
    new, info = fx.fix_text(md, text, prof)
    keys = fx.fm_keys(split(new)[0])
    assert keys["issue_date"] == "2021-07-09" and keys["report_week"] == "27"
    assert split(new)[1] == text
    md.with_name(md.stem + ".tables.json").write_text(json.dumps({"issue_date": "2021-01-01"}), encoding="utf-8")
    with pytest.raises(fx.FixError, match="disagree"):
        fx.fix_text(md, text, prof)


def test_agora_garbled_reference_point_is_not_a_date(tmp_path):
    prof = {**PROF, "agora_ranges": True}
    text = "# stem\n\nWeek 48 / 2022 1st (Reference point Dec.2022)\n"
    md = write(tmp_path / "agora_2022_W48_x.md", text)
    with pytest.raises(fx.FixError, match="no date derivable"):
        fx.fix_text(md, text, prof)
