"""Verifier: is the extraction actually healthy and progressing?

Designed to be run periodically (cron, or a supervising agent every few hours).
Exits non-zero and prints ACTION lines when something needs attention, and
prints a compact OK snapshot otherwise. Never mutates the corpus.

Checks:
  1. state file freshness  - is a batch alive and advancing?
  2. duplicate rows        - concurrent-batch corruption in the checkpoint
  3. failure rate          - per-status counts vs a threshold
  4. output presence       - do completed docs actually have their artefacts?
  5. golden recall         - the Star Asia fixture cells must still be present
  6. db integrity          - cells/catalogue parquet present and row-count sane
  7. disk headroom         - extraction output must not fill the volume

Usage:
  python scripts/extract/verify_extraction.py [--state ...] [--out ...] [--json]
"""
import argparse
import collections
import glob
import json
import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FAIL_RATE_MAX = 0.10          # >10% non-ok is a smell
STALE_MIN = 30                # state older than this means the batch is not advancing
GOLDEN = ["princess eternity", "182,263", "78.0", "mount dampier", "38.0",
          "sidra", "19.2", "spar scorpio", "11.25", "arklow spirit", "16.6",
          "glory bridge", "7.5", "bdi", "3,186"]


def check_state(state_path, actions, info):
    if not os.path.exists(state_path):
        actions.append(f"no state file at {state_path} - has a batch ever run?")
        return
    st = json.load(open(state_path, encoding="utf-8"))
    age = time.time() - os.path.getmtime(state_path)
    info["state_age_min"] = round(age / 60, 1)
    info.update({k: st.get(k) for k in
                 ("done", "planned", "status_counts", "secs_per_doc", "eta_min")})
    if age > STALE_MIN * 60:
        actions.append(f"state file is {age / 60:.0f} min old "
                       f"(> {STALE_MIN}) - batch may have died; rerun with --resume")
    counts = st.get("status_counts", {}) or {}
    total = sum(counts.values())
    bad = total - counts.get("ok", 0)
    if total and bad / total > FAIL_RATE_MAX:
        actions.append(f"failure rate {bad}/{total} exceeds {FAIL_RATE_MAX:.0%}: {counts}")


def check_duplicates(checkpoint, actions, info):
    if not os.path.exists(checkpoint):
        return
    rows = []
    for line in open(checkpoint, encoding="utf-8"):
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                actions.append("torn line in checkpoint (crash artefact) - "
                               "resume will skip it, but investigate if frequent")
    if not rows:
        return
    paths = collections.Counter(r.get("path") for r in rows)
    dupes = sum(v - 1 for v in paths.values() if v > 1)
    info["checkpoint_rows"] = len(rows)
    info["checkpoint_unique"] = len(paths)
    if dupes:
        actions.append(f"{dupes} duplicate checkpoint rows across "
                       f"{sum(1 for v in paths.values() if v > 1)} docs - "
                       f"two batches probably ran concurrently; check for strays")


def check_outputs(out_root, actions, info):
    """Flag completed docs whose artefacts are missing.

    Excludes docs that are EMPTY BY DESIGN: scanned statements superseded by a
    richer feed (provenance-only) legitimately produce no text/tables. Without
    this the check cries wolf every hour on ~140 CFTC dirs.
    """
    import glob as _glob
    dirs = _glob.glob(os.path.join(out_root, "*", "*"))
    info["doc_dirs"] = len(dirs)
    empty, by_design = 0, 0
    # Fixed 2026-09-21: this used to scan only dirs[:600]. Measured over 1,532
    # doc dirs: the capped scan reported 0 unexpected-empty dirs, the uncapped
    # scan reported 9 - including the 3 documents the per-doc timeout killed,
    # whose dirs hold only charts/ and no text/tables/pages. Capping the audit
    # means it silently under-reports as the corpus grows toward 7,816 docs.
    # The full scan costs ~0.4 s on 1,532 dirs.
    for d in dirs:
        tj = os.path.join(d, "text.jsonl")
        tabj = os.path.join(d, "tables.jsonl")
        pj = os.path.join(d, "pages.jsonl")
        has_text = os.path.exists(tj) and os.path.getsize(tj) > 0
        has_tab = os.path.exists(tabj) and os.path.getsize(tabj) > 0
        if has_text or has_tab:
            continue
        # scanned page with no text layer == nothing to extract, not a defect
        if os.path.exists(pj):
            try:
                pages = [json.loads(l) for l in open(pj, encoding="utf-8") if l.strip()]
                if pages and all(p.get("route") in ("scanned", "empty") for p in pages):
                    by_design += 1
                    continue
            except Exception:
                pass
        empty += 1
    info["empty_by_design"] = by_design
    info["empty_unexpected"] = empty
    if empty:
        actions.append(f"{empty} completed doc dirs have no text.jsonl/meta.json "
                       f"and are NOT scanned-only - inspect")


def check_quality(out_root, actions, info, sample=40):
    """Audit the QUALITY of what has been extracted, not just that it ran.

    Samples the most recently written documents and measures whether the output
    is substantive, whether reconciliation confidence is holding, and whether new
    failure modes are appearing that were not in the known list.
    """
    import glob
    import json as _json
    import statistics
    docs = glob.glob(os.path.join(out_root, "*", "*"))
    if not docs:
        info["quality"] = "no output yet"
        return
    docs.sort(key=lambda d: os.path.getmtime(d), reverse=True)
    recent = docs[:sample]
    blocks, tables, imgs, tv_means, orphans = [], [], [], [], []
    thin = []
    for d in recent:
        tj = os.path.join(d, "text.jsonl")
        tabj = os.path.join(d, "tables.jsonl")
        nb = sum(1 for _ in open(tj, encoding="utf-8")) if os.path.exists(tj) else 0
        ntab = sum(1 for _ in open(tabj, encoding="utf-8")) if os.path.exists(tabj) else 0
        blocks.append(nb)
        tables.append(ntab)
        meta = os.path.join(d, "charts", "meta.jsonl")
        imgs.append(sum(1 for _ in open(meta, encoding="utf-8")) if os.path.exists(meta) else 0)
        v = []
        if os.path.exists(tabj):
            for line in open(tabj, encoding="utf-8"):
                try:
                    t = _json.loads(line)
                except _json.JSONDecodeError:
                    continue
                if t.get("text_verified") is not None:
                    v.append(t["text_verified"])
        if v:
            tv_means.append(sum(v) / len(v))
        if nb == 0 and ntab == 0:
            thin.append(os.path.basename(d))
    info["quality_recent_docs"] = len(recent)
    info["quality_median_blocks"] = int(statistics.median(blocks)) if blocks else 0
    info["quality_median_tables"] = int(statistics.median(tables)) if tables else 0
    info["quality_median_images"] = int(statistics.median(imgs)) if imgs else 0
    info["quality_mean_text_verified"] = (round(statistics.mean(tv_means), 3)
                                          if tv_means else None)
    info["quality_empty_docs_in_sample"] = len(thin)

    # a run that is "succeeding" while producing nothing is the silent failure
    # this whole check exists to catch
    if recent and len(thin) / len(recent) > 0.35:
        actions.append(f"QUALITY: {len(thin)}/{len(recent)} of the most recent docs "
                       f"produced no text and no tables - extraction may have "
                       f"silently degraded. Inspect one: {thin[0]}")
    if tv_means and statistics.mean(tv_means) < 0.5:
        actions.append(f"QUALITY: mean text_verified has fallen to "
                       f"{statistics.mean(tv_means):.2f} in recent docs (grid is "
                       f"dropping more values than the text layer confirms)")


def check_new_failures(checkpoint, actions, info):
    """Flag failure modes not already known/explained."""
    if not os.path.exists(checkpoint):
        return
    import collections as _c
    import json as _json
    kinds = _c.Counter()
    for line in open(checkpoint, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            r = _json.loads(line)
        except _json.JSONDecodeError:
            continue
        if r.get("status") not in ("ok",):
            kinds[f"{r.get('status')}:{str(r.get('error',''))[:40]}"] += 1
    known = ("not-a-pdf", "timeout", "no-extractable-content", "provenance-only")
    unknown = {k: v for k, v in kinds.items()
               if not any(kn in k for kn in known)}
    info["failure_kinds"] = dict(kinds)
    if unknown:
        actions.append(f"NEW failure mode(s) not previously seen: {unknown}")


def check_golden(out_root, actions, info):
    hits = glob.glob(os.path.join(out_root, "*", "star_asia_2026_W35_Market*", "tables.jsonl"))
    if not hits:
        info["golden"] = "not in this output set"
        return
    blob = " ".join(open(hits[0], encoding="utf-8").read().split()).casefold()
    found = sum(1 for k in GOLDEN if k in blob)
    info["golden"] = f"{found}/{len(GOLDEN)}"
    if found < len(GOLDEN):
        actions.append(f"GOLDEN REGRESSION: {found}/{len(GOLDEN)} Star Asia cells present")


def check_db(out_root, actions, info):
    db_dir = os.path.join(out_root, "db")
    cat = os.path.join(db_dir, "catalogue.parquet")
    cells = os.path.join(db_dir, "tables.parquet")
    if not os.path.exists(cat):
        info["db"] = "not built yet"
        return
    try:
        import pandas as pd
        c = pd.read_parquet(cat)
        n = len(pd.read_parquet(cells, columns=["doc"]))
        info["db"] = f"{len(c)} tables, {n} cells"
        if len(c) == 0 or n == 0:
            actions.append("db parquet exists but is empty")
    except Exception as exc:
        actions.append(f"db unreadable: {type(exc).__name__}: {exc}")


def check_disk(out_root, actions, info):
    try:
        import shutil
        total, used, free = shutil.disk_usage(out_root if os.path.exists(out_root) else REPO)
        info["disk_free_gb"] = round(free / 1e9, 1)
        if free / 1e9 < 5:
            actions.append(f"only {free / 1e9:.1f} GB free - extraction will fail soon")
    except Exception:
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(REPO, "data", "extracted"))
    ap.add_argument("--state", default=os.path.join(REPO, "data", "extracted", "batch_state.json"))
    ap.add_argument("--checkpoint", default=os.path.join(REPO, "data", "extracted", "batch_checkpoint.jsonl"))
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    actions, info = [], {}
    check_state(a.state, actions, info)
    check_duplicates(a.checkpoint, actions, info)
    check_outputs(os.path.join(a.out, "corpus"), actions, info)
    check_quality(os.path.join(a.out, "corpus"), actions, info)
    check_new_failures(a.checkpoint, actions, info)
    check_golden(os.path.join(a.out, "corpus"), actions, info)
    check_db(a.out, actions, info)
    check_disk(a.out, actions, info)

    if a.json:
        print(json.dumps({"info": info, "actions": actions}, indent=1))
    else:
        print("=== extraction health:")
        for k, v in info.items():
            print(f"  {k}: {v}")
        if actions:
            print("\n=== ACTION REQUIRED:")
            for act in actions:
                print(f"  ! {act}")
        else:
            print("\nOK - no action required")
    return 1 if actions else 0


if __name__ == "__main__":
    sys.exit(main())
