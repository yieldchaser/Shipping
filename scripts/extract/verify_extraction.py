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
  8. inventory drift       - has the corpus on disk outgrown the frozen queue?

Usage:
  python scripts/extract/verify_extraction.py [--state ...] [--out ...] [--json]
"""
import argparse
import collections
import glob
import hashlib
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


def remaining_work(checkpoint):
    """How many documents in run_batch's own selection are still un-extracted?

    Recomputes run_batch's queue (inventory minus content-duplicates, minus
    PROVENANCE_ONLY) and subtracts the paths already in the checkpoint. A
    finished run stops advancing its state file, so staleness alone cannot tell
    COMPLETE from DEAD - only real remaining work is an ACTION.

    Returns (count, note); (None, note) when the queue cannot be recomputed, so
    the caller falls back to the plain staleness warning instead of claiming a
    completed corpus.
    """
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        if here not in sys.path:
            sys.path.insert(0, here)
        import run_batch as RB
        rows = RB.load_inventory()
        try:
            from source_configs import PROVENANCE_ONLY
        except ImportError:
            PROVENANCE_ONLY = {}
        if PROVENANCE_ONLY:
            import fnmatch

            def _prov_only(path):
                p = path.replace(chr(92), "/")
                for pat in PROVENANCE_ONLY:
                    if (fnmatch.fnmatch(p, pat)
                            or fnmatch.fnmatch(p, pat + "/*")
                            or pat.rstrip("*").rstrip("/") in p):
                        return True
                return False

            rows = [r for r in rows if not _prov_only(r["path"])]
        done = RB.load_done(checkpoint) if (checkpoint and os.path.exists(checkpoint)) else {}
        todo = [r for r in rows if r["path"] not in done]
        return len(todo), "%d planned, %d recorded" % (len(rows), len(done))
    except Exception as exc:
        return None, "could not recompute remaining work (%s: %s)" % (type(exc).__name__, exc)


_DRIFT_MEMO = []


def inventory_drift(limit=20):
    """How far has the corpus on disk outgrown inventory.jsonl?

    run_batch's queue - and therefore `remaining_work()` above - is computed
    from `data/extracted/inventory.jsonl`, a FROZEN file. `build_inventory.py`
    is reorg-aware, but nothing re-runs it, so every issue that lands in
    `corpus/` after it was written is invisible to the queue, and this check
    then reports "0 documents remain ... run COMPLETE" for a corpus that has
    since moved on.

    Measured 2026-10-01: the inventory was built 2026-09-21 and held 9,912 rows
    (7,816 after content-duplicates) while 12,912 PDFs sat under the same roots
    - 338 of them absent by filename, and 274 of those carrying content (md5)
    the inventory has never seen: the 2026 W36..W39 broker weeklies, the MMI
    iron-ore dailies, the GMS / Best Oasis demolition weeks 38-39, the
    fearnleys-md backfill tree (176) and 12 Drewry AIS weeklies. Those are
    covered by their publishers' bespoke runners (`scripts/extract/publishers/`),
    which open the source PDFs directly, so no live series was gapped - but the
    COMPLETE claim was only ever a statement about the 2026-09-21 list.

    Cheap by construction: filename comparison first, md5 only for the
    residue. Measured cost on this corpus: 10.4 s (338 md5s); the hourly check
    it runs inside costs 25 s in total. Informational only - a corpus
    outgrowing a frozen queue is expected, not an ACTION.
    """
    if _DRIFT_MEMO:
        return _DRIFT_MEMO[0]
    res = None
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        if here not in sys.path:
            sys.path.insert(0, here)
        import build_inventory as BI
        inv_path = os.path.join(REPO, "data", "extracted", "inventory.jsonl")
        rows = [json.loads(l) for l in open(inv_path, encoding="utf-8") if l.strip()]
        have, md5s = set(), set()
        for r in rows:
            have.add(os.path.basename(str(r.get("path", "")).replace(os.sep, "/")).lower())
            if r.get("md5"):
                md5s.add(r["md5"])
        seen, candidates, on_disk = set(), [], 0
        for root in BI.ROOTS:
            full = os.path.join(REPO, root)
            if not os.path.isdir(full):
                continue
            for fp in glob.glob(os.path.join(full, "**", "*.pdf"), recursive=True):
                # ROOTS overlap (corpus/01-brokers and corpus/01-brokers/fearnleys-md)
                # and spell them with different separators, so the raw path string
                # is NOT a stable identity: de-duplicate on the normcased one.
                # Measured 2026-10-01: without this the 176 fearnleys-md files were
                # counted twice and content_new read 450 instead of 274.
                key = os.path.normcase(os.path.normpath(fp))
                if key in seen:
                    continue
                seen.add(key)
                on_disk += 1
                if os.path.basename(fp).lower() not in have:
                    candidates.append(fp)
        new = []
        for fp in candidates:
            try:
                h = hashlib.md5()
                with open(fp, "rb") as fh:
                    for chunk in iter(lambda: fh.read(1 << 20), b""):
                        h.update(chunk)
            except OSError:
                continue
            if h.hexdigest() not in md5s:
                new.append(os.path.relpath(fp, REPO).replace(os.sep, "/"))
        res = {"inventory_built": time.strftime(
                   "%Y-%m-%d", time.localtime(os.path.getmtime(inv_path))),
               "inventory_rows": len(rows),
               "pdfs_on_disk": on_disk,
               "absent_by_name": len(candidates),
               "content_new": len(new),
               "examples": sorted(new)[:limit]}
    except Exception as exc:
        res = {"error": "%s: %s" % (type(exc).__name__, exc)}
    _DRIFT_MEMO.append(res)
    return res


def check_inventory_drift(actions, info):
    """Surface - never escalate - how far the on-disk corpus outgrew the queue."""
    d = inventory_drift()
    if d and d.get("content_new", 0) > 0:
        info["inventory_drift"] = d


def check_state(state_path, actions, info, checkpoint=None):
    if not os.path.exists(state_path):
        actions.append(f"no state file at {state_path} - has a batch ever run?")
        return
    st = json.load(open(state_path, encoding="utf-8"))
    age = time.time() - os.path.getmtime(state_path)
    info["state_age_min"] = round(age / 60, 1)
    info.update({k: st.get(k) for k in
                 ("done", "planned", "status_counts", "secs_per_doc", "eta_min")})
    if age > STALE_MIN * 60:
        # Fixed 2026-09-23 with a remaining_work() helper; found MISSING again
        # on 2026-10-01, so the hourly job was reporting a dead batch every hour
        # for a corpus that finished on 2026-09-22 (7,816/7,816 documents, 0
        # remaining). Only real remaining work is an ACTION.
        remaining, note = remaining_work(checkpoint)
        if remaining == 0:
            info["state_note"] = (
                f"state file is {age / 60:.0f} min old but 0 documents remain "
                f"({note}) - run COMPLETE, not a dead batch")
            d = inventory_drift()
            if d and d.get("content_new", 0) > 0:
                info["inventory_drift"] = d
                info["state_note"] += (
                    f"; NOTE: the queue comes from inventory.jsonl built "
                    f"{d['inventory_built']}, and {d['content_new']} PDFs now in "
                    f"the corpus have content it has never seen, so COMPLETE "
                    f"describes that list, not the corpus")
        elif remaining is None:
            info["state_note"] = note
            actions.append(f"state file is {age / 60:.0f} min old "
                           f"(> {STALE_MIN}) - batch may have died; rerun with --resume")
        else:
            actions.append(f"state file is {age / 60:.0f} min old "
                           f"(> {STALE_MIN}) and {remaining} documents are still "
                           f"un-extracted ({note}) - rerun with --resume")
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


def check_outputs(out_root, actions, info, checkpoint=None):
    """Flag completed docs whose artefacts are missing.

    Excludes docs that are EMPTY BY DESIGN: scanned statements superseded by a
    richer feed (provenance-only) legitimately produce no text/tables. Without
        this the check cries wolf every hour on ~140 CFTC dirs.

    An empty dir means three different things, so it is now classified against
    the checkpoint (added 2026-09-21):
      * recorded ok but holding no artefacts - a silent failure. Measured on
        the live corpus: 11 Hellenic MMi dailies had status ok with blocks=706
        and no text.jsonl / tables.jsonl / pages.jsonl / charts/meta.jsonl at
        all, while the per-page chart images written earlier in the same run
        were still on disk. Cause not established. This is the actionable class.
      * recorded as a failure (timeout/crash) - known, reported separately.
      * absent from the checkpoint - still being extracted right now.
    Without that classification the check also fires on documents in flight,
    which is why the old cap hidden the defect instead of surfacing it.
    """
    import glob as _glob
    dirs = _glob.glob(os.path.join(out_root, "*", "*"))
    info["doc_dirs"] = len(dirs)
    recorded_ok, failed_stems = set(), set()
    if checkpoint and os.path.exists(checkpoint):
        for line in open(checkpoint, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("status") == "ok" and rec.get("doc"):
                recorded_ok.add(rec["doc"])
            elif rec.get("status") and rec.get("path"):
                failed_stems.add(os.path.splitext(os.path.basename(rec["path"]))[0])
    empty_ok, empty_failure, in_flight, by_design = 0, 0, 0, 0
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
        rel_doc = os.path.relpath(d, out_root).replace(os.sep, "/")
        if rel_doc in recorded_ok:
            empty_ok += 1
            if empty_ok <= 5:
                actions.append(f"SILENT EMPTY OUTPUT: {rel_doc} is recorded ok in "
                               f"the checkpoint but holds no text/tables/pages")
        elif os.path.basename(d) in failed_stems:
            empty_failure += 1
        else:
            in_flight += 1
    info["empty_by_design"] = by_design
    info["empty_after_ok_status"] = empty_ok
    info["empty_after_failure"] = empty_failure
    info["empty_not_in_checkpoint"] = in_flight
    info["empty_unexpected"] = empty_ok
    if empty_ok:
        actions.append(f"{empty_ok} dirs recorded ok in the checkpoint hold no "
                       f"text/tables/pages - silent failure; re-extract them")


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


def check_new_failures(checkpoint, actions, info, out_root=None):
    """Flag failure modes not already known/explained."""
    if not os.path.exists(checkpoint):
        return
    import collections as _c
    import json as _json

    # The crash-recovery pass re-extracted documents that died when
    # extract_all.py was transiently partially-written (workers imported a file
    # that still had null bytes). Their checkpoint row still reads CRASH because
    # the live batch holds that file open for append and rewriting it would drop
    # completed rows, so the recovery log is the source of truth for what has
    # since been fixed. Without this the 204 recovered rows would be reported as
    # a NEW failure mode on every single run.
    recovered = set()
    rec_log = os.path.join(os.path.dirname(checkpoint), "crash_recovery.jsonl")
    if os.path.exists(rec_log):
        for line in open(rec_log, encoding="utf-8", errors="replace"):
            line = line.strip()
            if not line:
                continue
            try:
                rr = _json.loads(line)
            except _json.JSONDecodeError:
                continue
            if rr.get("status") in ("ok", "provenance-only", "no-extractable-content"):
                recovered.add(rr.get("path"))
    info["crash_recovered_docs"] = len(recovered)

    kinds = _c.Counter()
    recovered_seen = 0
    for line in open(checkpoint, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            r = _json.loads(line)
        except _json.JSONDecodeError:
            continue
        status = r.get("status")
        if status == "CRASH" and r.get("path") in recovered:
            recovered_seen += 1
            continue
        if status not in ("ok",):
            # A failure row whose artefacts now exist has been re-extracted by a
            # recovery pass (crash batch, trailing-dot stems, silent-empty). The
            # checkpoint cannot be rewritten while the live batch holds it open,
            # so the artefacts on disk are the honest signal that it is resolved.
            # Without this every recovered document alarms as a NEW failure mode
            # on every run - the alarm becomes noise and stops meaning anything.
            if _has_artefacts(out_root, r.get("path")):
                recovered_seen += 1
                continue
            kinds[f"{status}:{str(r.get('error',''))[:40]}"] += 1
    if recovered_seen:
        info["crash_rows_resolved"] = recovered_seen
    known = ("not-a-pdf", "timeout", "no-extractable-content", "provenance-only")
    unknown = {k: v for k, v in kinds.items()
               if not any(kn in k for kn in known)}
    info["failure_kinds"] = dict(kinds)
    if unknown:
        actions.append(f"NEW failure mode(s) not previously seen: {unknown}")


def _has_artefacts(out_root, rel_path):
    """True when a document's output directory exists with real text in it.

    Mirrors the extractor's own naming (source subdir + Windows-safe stem) so a
    failure row can be recognised as already recovered. Kept as a local probe
    rather than importing extract_all, which pulls in the PDF stack and would
    make this diagnostic script depend on it.
    """
    import re as _re

    if not rel_path:
        return False
    p = str(rel_path).replace("\\", "/")
    stem = os.path.splitext(os.path.basename(p))[0]
    stem = _re.sub(r"[ .]+$", "", stem)          # extract_all.safe_stem
    if not stem:
        return False
    parts = p.split("/")
    # source is the first path segment, except under reports/ where it is the
    # second (reports/<lineage>/...), matching extract_all.derive_source.
    candidates = []
    if len(parts) > 1 and parts[0] == "reports":
        candidates.append(parts[1])
    if len(parts) > 1:
        candidates.append(parts[0])
    for src in candidates:
        tj = os.path.join(out_root, src, stem, "text.jsonl")
        try:
            if os.path.getsize(tj) > 0:
                return True
        except OSError:
            continue
    return False


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
    check_state(a.state, actions, info, a.checkpoint)
    check_inventory_drift(actions, info)
    check_duplicates(a.checkpoint, actions, info)
    check_outputs(os.path.join(a.out, "corpus"), actions, info,
                  checkpoint=a.checkpoint)
    check_quality(os.path.join(a.out, "corpus"), actions, info)
    check_new_failures(a.checkpoint, actions, info, os.path.join(a.out, "corpus"))
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
