#!/usr/bin/env python3
"""
tests/test_protect_accepted_md.py
=================================
Verifies scripts/ci/protect_accepted_md.py restores modified accepted Markdown,
removes case-variant duplicates, and honours ALLOW_MD_REWRITE=1 / --dry-run.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "ci" / "protect_accepted_md.py"
ORIGINAL = "# accepted\n\n| Rate | Charterer |\n| 10 | ACME |\n"


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _run(cwd, *args, **env_extra):
    env = {k: v for k, v in os.environ.items() if k != "ALLOW_MD_REWRITE"}
    env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=cwd, env=env, capture_output=True, text=True,
    )


def _case_insensitive_fs(tmp_path):
    d = tmp_path / "_casecheck"
    d.mkdir()
    (d / "a.md").write_text("1", encoding="utf-8")
    (d / "A.md").write_text("2", encoding="utf-8")
    return len(list(d.iterdir())) == 1


@pytest.fixture
def repo(tmp_path_factory):
    repo = tmp_path_factory.mktemp("repo")
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "t")
    _git(repo, "config", "commit.gpgsign", "false")
    md_dir = repo / "data" / "extracted" / "md" / "x"
    md_dir.mkdir(parents=True)
    (md_dir / "a.md").write_text(ORIGINAL, encoding="utf-8")
    (md_dir / "gone.md").write_text("keep me\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")
    return repo


def test_restores_modified_and_deleted_and_removes_case_variant(repo, tmp_path):
    md_dir = repo / "data" / "extracted" / "md" / "x"
    (md_dir / "a.md").write_text("# damaged\n", encoding="utf-8")
    (md_dir / "gone.md").unlink()
    (md_dir / "new.md").write_text("genuinely new\n", encoding="utf-8")
    variant = md_dir / "A.md"
    check_variant = not _case_insensitive_fs(tmp_path)
    if check_variant:
        variant.write_text("dup\n", encoding="utf-8")

    res = _run(repo)

    assert res.returncode == 0, res.stderr
    assert (md_dir / "a.md").read_text(encoding="utf-8") == ORIGINAL
    assert (md_dir / "gone.md").read_text(encoding="utf-8") == "keep me\n"
    assert (md_dir / "new.md").exists()
    assert "::warning::" in res.stdout
    if check_variant:
        assert "A.md" not in os.listdir(md_dir)


def test_allow_md_rewrite_leaves_changes(repo, tmp_path):
    md_dir = repo / "data" / "extracted" / "md" / "x"
    (md_dir / "a.md").write_text("# damaged\n", encoding="utf-8")
    check_variant = not _case_insensitive_fs(tmp_path)
    if check_variant:
        (md_dir / "A.md").write_text("dup\n", encoding="utf-8")

    res = _run(repo, ALLOW_MD_REWRITE="1")

    assert res.returncode == 0, res.stderr
    assert (md_dir / "a.md").read_text(encoding="utf-8") == "# damaged\n"
    if check_variant:
        assert "A.md" in os.listdir(md_dir)


def test_dry_run_leaves_changes(repo):
    md_dir = repo / "data" / "extracted" / "md" / "x"
    (md_dir / "a.md").write_text("# damaged\n", encoding="utf-8")

    res = _run(repo, "--dry-run")

    assert res.returncode == 0, res.stderr
    assert (md_dir / "a.md").read_text(encoding="utf-8") == "# damaged\n"
    assert "would revert" in res.stdout


def test_restores_name_with_spaces_and_curly_apostrophe(repo):
    md_dir = repo / "data" / "extracted" / "md" / "x"
    name = "Owner’s report week 12.md"
    (md_dir / name).write_text(ORIGINAL, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "add odd name")
    (md_dir / name).write_text("# damaged\n", encoding="utf-8")

    res = _run(repo)

    assert res.returncode == 0, res.stderr
    assert (md_dir / name).read_text(encoding="utf-8") == ORIGINAL


def test_state_files_and_corpus_root_files_left_alone(repo):
    state = repo / "corpus" / "01-brokers" / "_run_state.json"
    root_file = repo / "corpus" / "CORPUS_REGISTRY.md"
    state.parent.mkdir(parents=True)
    state.write_text("{}\n", encoding="utf-8")
    root_file.write_text("v1\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "state")
    state.write_text('{"run": 2}\n', encoding="utf-8")
    root_file.write_text("v2\n", encoding="utf-8")

    res = _run(repo)

    assert res.returncode == 0, res.stderr
    assert state.read_text(encoding="utf-8") == '{"run": 2}\n'
    assert root_file.read_text(encoding="utf-8") == "v2\n"


def test_staged_modification_restored(repo):
    md_dir = repo / "data" / "extracted" / "md" / "x"
    (md_dir / "a.md").write_text("# damaged\n", encoding="utf-8")
    _git(repo, "add", "data")

    res = _run(repo)

    assert res.returncode == 0, res.stderr
    assert (md_dir / "a.md").read_text(encoding="utf-8") == ORIGINAL
    status = subprocess.run(["git", "status", "--porcelain"], cwd=repo,
                            capture_output=True, text=True, check=True).stdout
    assert status.strip() == ""


def _load_demolition(monkeypatch, md_base):
    pytest.importorskip("bs4")
    pytest.importorskip("pandas")
    pytest.importorskip("pymupdf")
    import importlib

    mod = importlib.import_module("extract.publishers.run_hellenic_demolition")
    monkeypatch.setattr(mod, "MD_BASE_DIR", md_base)
    return mod


def test_existing_issue_md_matching(monkeypatch, tmp_path):
    mod = _load_demolition(monkeypatch, tmp_path)
    gms = tmp_path / "gms" / "2024"
    gms.mkdir(parents=True)
    flat = tmp_path / "2024"
    flat.mkdir()
    (gms / "gms_2024-01-05_2024-01-08_gms-week-01.md").write_text("x", encoding="utf-8")
    (flat / "Best_Oasis_2024-02-02_Foo.MD").write_text("x", encoding="utf-8")

    # second date token in a canonical name must not block that date
    assert mod.existing_issue_md("gms", "2024", "2024-01-08") is False
    assert mod.existing_issue_md("gms", "2024", "2024-01-05") is True
    # unknown / empty never block
    assert mod.existing_issue_md("gms", "2024", "unknown") is False
    assert mod.existing_issue_md("gms", "2024", "") is False
    # case-insensitive, flat dir searched
    assert mod.existing_issue_md("best_oasis", "2024", "2024-02-02") is True
