"""Guards for the GitHub Pages deploy (.github/workflows/pages.yml).

1. Upload and deploy run in separate jobs. In one job, deploy-pages looked the
   artifact up ~0.3 s after the upload and intermittently found none
   (8 failed deploys, 2026-11-18 .. 11-22).
2. Files the deploy strips out to keep the artifact small must never be
   fetched by the site: if a served page names one, it would 404 in production.
"""
from __future__ import annotations

import fnmatch
import re
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PAGES = ROOT / ".github" / "workflows" / "pages.yml"


def _workflow():
    return yaml.safe_load(PAGES.read_text(encoding="utf-8"))


def test_upload_and_deploy_are_separate_jobs():
    jobs = _workflow()["jobs"]
    build_uses = [s.get("uses", "") for s in jobs["build"]["steps"]]
    deploy_uses = [s.get("uses", "") for s in jobs["deploy"]["steps"]]
    assert any(u.startswith("actions/upload-pages-artifact") for u in build_uses)
    assert any(u.startswith("actions/deploy-pages") for u in deploy_uses)
    assert not any(u.startswith("actions/deploy-pages") for u in build_uses)
    needs = jobs["deploy"].get("needs")
    assert needs == "build" or (isinstance(needs, list) and "build" in needs)


def _slim_patterns():
    steps = _workflow()["jobs"]["build"]["steps"]
    run = next(s["run"] for s in steps if s.get("name", "").startswith("Clean Heavy Folders"))
    tail = run.split("Raw and intermediate files", 1)[1]
    pats = re.findall(r"(?<![\w./-])((?:data/|bunker_master)[\w./*-]+)", tail)
    pats = [p.rstrip("/") for p in pats]
    pats += [p + "/*" for p in list(pats) if "." not in Path(p).name]  # directories
    pats.append("*.parquet")
    return pats


def _stripped_files():
    files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True,
                           check=True).stdout.split()
    pats = _slim_patterns()
    return [f for f in files if any(fnmatch.fnmatch(f, p) for p in pats)]


def test_slimming_rules_match_real_files():
    stripped = _stripped_files()
    assert "bunker_master_historical.csv" in stripped
    assert "data/congestion/port_calls_daily.csv" in stripped
    # The site's own data must survive the slimming.
    for keep in ("index.html", "data/bunkers/bunker_prices_daily.csv",
                 "data/congestion/portwatch_port_congestion.csv",
                 "data/geospatial/portwatch_ports_master.csv"):
        assert keep not in stripped, keep


def test_site_never_fetches_a_stripped_file():
    served = [ROOT / "index.html"] + sorted(ROOT.glob("*.js")) + sorted((ROOT / "js").glob("**/*.js"))
    text = "\n".join(p.read_text(encoding="utf-8", errors="ignore") for p in served if p.exists())
    hits = [f for f in _stripped_files() if Path(f).name in text]
    assert not hits, f"pages.yml strips files the site references: {hits[:10]}"
