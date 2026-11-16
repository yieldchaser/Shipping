"""Tests for kb/p4c_report.py - ladder merge, coverage, gate rows and report shape (no model calls)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

KB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KB))

import p4c_report as P  # noqa: E402


def gchunk(cid, ok=True, call_failed=False, facts=1, dropped=0):
    return {"chunk_id": cid, "records_total": facts + dropped, "records_ok": facts,
            "gates_2_4_failed": dropped, "call_failed": call_failed,
            "no_content": facts + dropped == 0, "records": [],
            "kept": {"state_facts": [{"chunk": cid}] * facts, "events": [], "claims": []}}


def gated(cid_doc, chunks, rung_dir):
    path = rung_dir / "gated.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"pack_key": cid_doc + "|", "doc_id": cid_doc,
                                "chunks": chunks, "call": {}}) + "\n", encoding="utf-8")
    return path


def packs_file(tmp_path, docs=("d1", "d2")):
    path = tmp_path / "packs.jsonl"
    rows = []
    for d in docs:
        rows.append({"n": 0, "pack_id": "p000000", "doc_id": d, "key": d + "|a+b",
                     "chunk_ids": ["a", "b"], "doc": {"publisher": "Baltic Exchange",
                                                      "doc_type": "broker_weekly",
                                                      "published_at": "2015-10-02", "heading": "T"}})
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return path


def test_merge_ladder_precedence(tmp_path):
    bulk = gated("d1", {"a": gchunk("a", ok=False, dropped=1), "b": gchunk("b")}, tmp_path / "bulk")
    esc = gated("d1", {"a": gchunk("a")}, tmp_path / "esc1")
    merged = P.merge([bulk, esc])
    assert set(merged["chunks"]) == {"a", "b"}
    assert merged["chunks"]["a"]["clean"] and merged["chunks"]["a"]["was_failed"]
    assert merged["chunks"]["b"]["rung"] == "bulk"
    again = P.merge([bulk, gated("d1", {"a": gchunk("a", ok=False, dropped=1)}, tmp_path / "esc2")])
    assert not again["chunks"]["a"]["clean"]
    assert again["chunks"]["a"]["rung"] == "bulk"


def test_totals_and_failure_rate():
    chunks = {"a": P.chunk_state(gchunk("a", dropped=1)), "b": P.chunk_state(gchunk("b")),
              "c": P.chunk_state(gchunk("c", call_failed=True, facts=0, dropped=0)),
              "d": P.chunk_state(gchunk("d", facts=0))}
    st = P.totals(chunks)
    # frozen gate = D12 repair queue: only `c` broke (call failed). `a` kept a record, so it is
    # quality-dirty but repairable-by-nobody, and rule 6 never queues it.
    assert st["chunks"] == 4 and st["chunks_clean"] == 2 and st["chunks_failed"] == 1
    assert st["chunks_broken"] == 1 and st["failure_queue_rate"] == 0.25
    # the strict per-record reading is reported, distinct, and deliberately not the gated value
    assert st["chunks_strict_failed"] == 2 and st["strict_failure_rate"] == 0.5
    assert st["records_kept"] == 2 and st["records_dropped"] == 1
    assert st["chunks_no_content"] == 2


def test_failure_queue_counts_broken_not_dropped_records():
    """A chunk that kept >=1 record is never in the D12 queue, however many records it dropped."""
    kept_one = P.chunk_state(gchunk("a", facts=1, dropped=9))
    assert not kept_one["clean"] and not kept_one["broken"]
    all_dropped = P.chunk_state(gchunk("b", facts=0, dropped=5))
    assert not all_dropped["clean"] and all_dropped["broken"]
    # never extracted: missing, not broken
    assert not P.chunk_state(gchunk("c", facts=0))["broken"]


def test_coverage_declares_partial(tmp_path):
    meta = {"d1": {"publisher": "P1", "doc_type": "broker_weekly", "published_at": "2015-10-02"},
            "d2": {"publisher": "P2", "doc_type": "sec_10k", "published_at": "2020-01-01"}}
    chunks = {"a": {"doc_id": "d1"}, "b": {"doc_id": "d2"}, "c": {"doc_id": "d1"}}
    cov = P.coverage(chunks, meta)
    assert cov["chunks"] == 3 and cov["docs"] == 2
    assert cov["publisher_count"] == 2 and cov["doc_type_count"] == 2
    assert cov["years"] == ["2015", "2020"]
    assert cov["partial"] and cov["missing_chunks"] == P.SCOPE_CHUNKS - 3


def test_gate_rows_follow_audit_state():
    st = {"failure_queue_rate": 0.01}
    cov = {"chunks": 100}
    absent = P.gate_rows(st, {"present": False}, cov)
    assert not absent["all_pass"]
    assert not absent["rows"]["random_audit_records"]["pass"]
    ok_audit = {"present": True, "sampled": 200, "wrong_rate": 0.01, "judge_family": "glm",
                "extractor_family": "deepseek"}
    good = P.gate_rows(st, ok_audit, cov)
    assert good["all_pass"], good
    bad_audit = dict(ok_audit, wrong_rate=0.05)
    assert not P.gate_rows(st, bad_audit, cov)["all_pass"]
    same_family = dict(ok_audit, judge_family="deepseek")
    assert not P.gate_rows(st, same_family, cov)["all_pass"]
    slow = P.gate_rows({"failure_queue_rate": 0.03}, ok_audit, cov)
    assert not slow["rows"]["failure_queue_max"]["pass"]


def test_gate_rows_reject_unreadable_rates_instead_of_passing_them():
    """Defect 26: `inf <= 0.02` and `-inf <= 0.03` are True, so a non-finite rate PASSED a §12 gate.

    The gates are ratio reads out of on-disk artefacts, so both operands go through
    `money.unit_score` at the verdict: a broken read is unmeasured and the row FAILS.
    """
    cov = {"chunks": 100}
    audit = {"present": True, "sampled": 200, "wrong_rate": 0.01, "judge_family": "glm",
             "extractor_family": "deepseek"}
    # Non-vacuity: the in-range boundary arms still pass, so the fix cannot pass by blanket-failing.
    assert P.gate_rows({"failure_queue_rate": 0.0}, audit, cov)["rows"]["failure_queue_max"]["pass"]
    assert P.gate_rows({"failure_queue_rate": 0.02}, audit, cov)["rows"]["failure_queue_max"]["pass"]
    for broken in (True, float("inf"), float("-inf"), float("nan"), "0.01", [0.01], 1.5, -0.1):
        bad = P.gate_rows({"failure_queue_rate": broken}, audit, cov)["rows"]
        assert bad["failure_queue_max"]["measured"] is None, broken
        assert not bad["failure_queue_max"]["pass"], broken
        assert not P.gate_rows({"failure_queue_rate": broken}, audit, cov)["all_pass"], broken
        a_bad = dict(audit, wrong_rate=broken)
        assert P.gate_rows({"failure_queue_rate": 0.0}, a_bad, cov)["rows"][
            "random_audit_wrong_max"]["measured"] is None, broken
        assert not P.gate_rows({"failure_queue_rate": 0.0}, a_bad, cov)["all_pass"], broken
    # An audit that was never run stays unmeasured, not a fabricated zero rate.
    assert P.gate_rows({"failure_queue_rate": 0.0}, {"present": False}, cov)["rows"][
        "random_audit_wrong_max"]["measured"] is None


def test_artefact_rate_readers_guard_their_value(tmp_path):
    """`audit_gate` and `union_stats` are the two artefact readers; both rates are guarded there.

    The render path then prints `n/a` for an unusable read rather than `True` / `100.00%` / `inf`.
    """
    audit = tmp_path / "audit.json"
    stats = tmp_path / "union_stats.json"

    def read(audit_row, stats_row):
        audit.write_text(json.dumps(audit_row), encoding="utf-8")
        stats.write_text(json.dumps(stats_row), encoding="utf-8")
        return P.audit_gate(audit), P.union_stats(stats)

    for broken in (True, float("inf"), float("-inf"), float("nan"), "0.01", [0.01], 1.5, -0.1):
        g, u = read({"model": "glm-5.3", "wrong_rate": broken},
                    {"duplicates_rate": broken, "failure_queue_rate": broken})
        assert g["wrong_rate"] is None, broken
        assert u["duplicates_rate"] is None and u["failure_queue_rate"] is None, broken
    g, u = read({"model": "glm-5.3", "wrong_rate": 0.0},
                {"duplicates_rate": 0.0, "failure_queue_rate": 0.02})
    assert g["wrong_rate"] == 0.0  # a genuine measured zero stays, not None
    assert u["duplicates_rate"] == 0.0 and u["failure_queue_rate"] == 0.02
    # The renderer: a guarded rate renders as a percentage, an unusable one as `n/a`.
    assert P._pct(0.02) == "2.00%" and P._pct(0.0) == "0.00%"
    assert P._pct(None) == "n/a" and P._pct(True) == "n/a" and P._pct(float("inf")) == "n/a"
    assert P._pct("0.01") == "n/a" and P._pct(1.5) == "n/a"


def test_gate_rows_reject_unreadable_counts_instead_of_passing_them():
    """Defect 32: `inf >= 200` and `inf > 0` are True, so an unreadable *count* PASSED a §12 gate.

    The two count limbs of the gate (`random_audit_records` on `audit.json`'s `sampled`, and
    `coverage_of_frozen_scope_reported` on the coverage dict's `chunks`) were read raw while the
    sibling rates were already guarded. `sampled or 0` additionally invented a measured zero for a
    key the audit never wrote - and `_count(True)`/`_count(1.5)` must be `None`, since no producer
    here (`len(rows)`) can yield a bool or a fraction.
    """
    assert P._count(0) == 0 and P._count(200) == 200 and P._count(200.0) == 200
    for broken in (True, float("inf"), float("-inf"), float("nan"), "200", [200], 200.5, -0.1, None):
        assert P._count(broken) is None, broken

    st = {"failure_queue_rate": 0.0}
    cov = {"chunks": 100}
    base = {"present": True, "sampled": 200, "wrong_rate": 0.01, "judge_family": "glm",
            "extractor_family": "deepseek"}
    # Non-vacuity: the boundary arms still pass, so the fix cannot pass by blanket-failing.
    assert P.gate_rows(st, base, cov)["all_pass"]
    assert P.gate_rows(st, dict(base, sampled=199), cov)["rows"]["random_audit_records"]["pass"] is False
    for broken in (True, float("inf"), float("-inf"), float("nan"), "200", [200], 200.5, -0.1):
        rows = P.gate_rows(st, dict(base, sampled=broken), cov)["rows"]
        assert rows["random_audit_records"]["measured"] is None, broken
        assert not rows["random_audit_records"]["pass"], broken
        assert not P.gate_rows(st, dict(base, sampled=broken), cov)["all_pass"], broken
        crows = P.gate_rows(st, base, {"chunks": broken})["rows"]
        assert crows["coverage_of_frozen_scope_reported"]["measured"] is False, broken
        assert not crows["coverage_of_frozen_scope_reported"]["pass"], broken
        assert not P.gate_rows(st, base, {"chunks": broken})["all_pass"], broken
    # A count the artefact never wrote is UNMEASURED, not a fabricated measured zero.
    absent = dict(base)
    absent.pop("sampled")
    assert P.gate_rows(st, absent, cov)["rows"]["random_audit_records"]["measured"] is None
    assert not P.gate_rows(st, absent, cov)["all_pass"]
    # A missing coverage key must not raise a KeyError either: it fails as unmeasured.
    assert not P.gate_rows(st, base, {})["rows"]["coverage_of_frozen_scope_reported"]["pass"]


def test_audit_gate_guards_its_counts_and_the_render_says_unmeasured(tmp_path):
    """Defect 32: the audit artefact's four counts feed a gate (200) and the rendered packet."""
    audit = tmp_path / "audit.json"
    audit.write_text(json.dumps({"model": "glm-5.3", "judge_family": "glm",
                                 "extractor_family": "deepseek", "sampled": float("inf"),
                                 "judged": True, "drop": "2", "unparseable": 0.5,
                                 "wrong": 2, "wrong_rate": 0.01}), encoding="utf-8")
    a = P.audit_gate(audit)
    assert a["sampled"] is None and a["judged"] is None
    assert a["drop"] is None and a["unparseable"] is None
    assert a["wrong"] == 2  # a readable count survives
    # The renderer must not print a raw unusable read into the owner packet. Build the coverage
    # block and totals through their real producers so the pin exercises the true `_md` shape.
    cs = P.chunk_state({"chunk_id": "a", "call_failed": False, "gates_2_4_failed": 0,
                        "kept": {"state_facts": [{}]}, "records_total": 1, "records_ok": 1,
                        "no_content": False})
    cs["doc_id"], cs["rung"] = "d1", "bulk"
    chunks = {"a": cs}
    meta = {"d1": {"publisher": "P1", "doc_type": "broker_weekly", "published_at": "2015-10-02"}}
    cov, st = P.coverage(chunks, meta), P.totals(chunks)
    assert P._r(None) == "n/a" and P._r(0) == "0" and P._r(200) == "200"
    rep = {"extraction": st, "coverage": cov, "audit": a, "gate_results": P.gate_rows(st, a, cov)["rows"],
           "cost": {"per_pass": {}, "total_usd": None}, "wall": {}, "sample": [],
           "sample_seed": P.seed_for("P4C"), "phase": "P4C", "generated": "now",
           "scope": {}, "ladder": {"final_rung": None}, "rule6": {}, "union": {"present": False},
           "recall": {}, "gated_source": "rungs", "gated_rows": 0, "merged_chunks": 1, "rungs": {},
           "all_pass": False}
    md = P._md(rep)
    assert "n/a sampled" in md and "inf sampled" not in md
    # An unsurveyed count is not silently reported as zero either.
    audit.write_text(json.dumps({"model": "glm-5.3", "wrong_rate": 0.0}), encoding="utf-8")
    assert P.audit_gate(audit)["sampled"] is None


def test_build_and_markdown(tmp_path, monkeypatch):
    bulk = gated("d1", {"a": gchunk("a", ok=False, dropped=1), "b": gchunk("b")}, tmp_path / "bulk")
    esc = gated("d1", {"a": gchunk("a")}, tmp_path / "esc1")
    audit = tmp_path / "audit.json"
    audit.write_text(json.dumps({"model": "glm-5.3", "judge_family": "glm", "extractor_model":
                                 "deepseek-v4.1-flash-1017-ultrafast", "extractor_family": "deepseek",
                                 "sampled": 200, "judged": 200, "drop": 2, "unparseable": 0,
                                 "wrong": 2, "wrong_rate": 0.01}), encoding="utf-8")
    monkeypatch.setattr(P, "OUT", tmp_path)
    monkeypatch.setattr(P, "doc_paths", lambda ids: {d: f"corpus/x/{d}.md" for d in ids})
    # `cost()` now reads `spent_exact` so that "no ledger row" stays distinct from a measured zero;
    # the old `spent` stub is repointed rather than left to silently exercise the live ledger
    # (Defect 19 corollary: splitting a helper means every stub of the old one must move).
    monkeypatch.setattr(P.R, "spent_exact", lambda passes=None: 1.5)
    # `build()`'s `union_path` default is bound at def time to the gitignored live export, so a
    # fixture-only test that omits it silently scored `kb/state/p4c/union/gated_union.jsonl` (280 MB,
    # 86,607 chunks) while asserting `gated_source == "rungs"` and `recovered_by_ladder == 1` - the
    # assertions held only until the live escalation changed that artefact (Defect 37 class: a unit
    # test reading live state is not a unit test). Point it at a missing path explicitly.
    rep = P.build([bulk, esc], packs_file(tmp_path), audit, tmp_path / "no_union.json")
    assert rep["sample_seed"] == P.seed_for("P4C")
    assert rep["all_pass"]
    assert rep["extraction"]["recovered_by_ladder"] == 1
    assert rep["cost"]["total_usd"] == round(1.5 * (len(P.PASSES) + 1), 6)
    assert rep["gated_source"] == "rungs" and not rep["union"]["present"]
    assert len(rep["sample"]) == 2 and rep["sample"][0]["source_path"].startswith("corpus/")
    md = P._md(rep)
    for needle in ("Scope coverage", "failure_queue_max", "random_audit_records", "Ten sampled chunks",
                   "glm-5.3"):
        assert needle in md
    json.dumps(rep, default=str)  # must be serialisable for the gate file


def test_main_writes_reports(tmp_path, monkeypatch):
    bulk = gated("d1", {"b": gchunk("b")}, tmp_path / "bulk")
    packs = packs_file(tmp_path)
    audit = tmp_path / "audit.json"
    audit.write_text(json.dumps({"present": True}), encoding="utf-8")
    monkeypatch.setattr(P, "REPORTS", tmp_path / "reports")
    monkeypatch.setattr(P, "REPORT_JSON", tmp_path / "reports" / "p4c.json")
    monkeypatch.setattr(P, "REPORT_MD", tmp_path / "reports" / "p4c.md")
    monkeypatch.setattr(P, "doc_paths", lambda ids: {})
    monkeypatch.setattr(P.R, "spent_exact", lambda passes=None: 0.0)
    monkeypatch.setattr(sys, "argv", ["p4c_report.py", "--gated", str(bulk), "--packs", str(packs),
                                      "--audit", str(audit), "--union", str(tmp_path / "no_union.json"),
                                      "--write"])
    assert P.main() == 0
    rep = json.loads((tmp_path / "reports" / "p4c.json").read_text(encoding="utf-8"))
    assert rep["phase"] == "P4C" and rep["sample_seed"] == P.seed_for("P4C")
    assert (tmp_path / "reports" / "p4c.md").read_text(encoding="utf-8").startswith("# P4c")


def test_merge_accepts_flat_gate_rows(tmp_path):
    """`p4c_gate.gate_run` writes one flat row per chunk; merge must not need the nested fixture shape."""
    path = tmp_path / "bulk" / "gated.jsonl"
    path.parent.mkdir(parents=True)
    rows = []
    for cid, ok in (("a", False), ("b", True)):
        ch = gchunk(cid, ok=ok, dropped=0 if ok else 1)
        ch["doc_id"] = "d1"
        ch["pack_key"] = "d1|a+b"
        rows.append(ch)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    esc = tmp_path / "esc_retry" / "gated.jsonl"
    esc.parent.mkdir(parents=True)
    flat = gchunk("a")
    flat["doc_id"] = "d1"
    esc.write_text(json.dumps(flat) + "\n", encoding="utf-8")
    merged = P.merge([path, esc])
    assert merged["gated_rows"] == 3 and merged["merged_chunks"] == 3
    assert set(merged["chunks"]) == {"a", "b"}
    assert merged["chunks"]["a"]["clean"] and merged["chunks"]["a"]["was_failed"]
    assert merged["chunks"]["a"]["doc_id"] == "d1"
    assert merged["chunks"]["b"]["rung"] == "bulk"


def test_missing_rows_are_not_coverage_and_not_clean():
    """A never-extracted placeholder row (Defect 10) is neither covered nor clean nor broken."""
    st = P.chunk_state({"chunk_id": "m", "call_missing": True, "call_failed": False,
                        "records_total": 0, "kept": {}})
    assert st["missing"] and not st["clean"] and not st["broken"] and not st["call_failed"]
    t = P.totals({"m": st, "ok": P.chunk_state(gchunk("ok"))})
    assert t["chunks"] == 2 and t["chunks_missing"] == 1 and t["chunks_extracted"] == 1
    assert t["chunks_clean"] == 1 and t["chunks_failed"] == 0
    # missing dilutes neither reading: strict failure counts only extracted chunks
    assert t["failure_queue_rate"] == 0.0 and t["strict_failure_rate"] == 0.0
    cov = P.coverage({"m": dict(st, doc_id="d1"), "ok": dict(P.chunk_state(gchunk("ok")), doc_id="d2")},
                     {"d1": {}, "d2": {}})
    assert cov["chunks"] == 1 and cov["rows"] == 2 and cov["missing_chunks_rows"] == 1


def test_merge_keeps_records_when_a_later_rung_has_no_raw(tmp_path):
    """A clean-but-empty rung row must not overwrite an earlier rung's real records."""
    good = tmp_path / "bulk" / "gated.jsonl"
    good.parent.mkdir(parents=True)
    good.write_text(json.dumps(gchunk("a")) + "\n", encoding="utf-8")
    miss = tmp_path / "retry" / "gated.jsonl"
    miss.parent.mkdir(parents=True)
    miss.write_text(json.dumps({"chunk_id": "a", "call_missing": True, "call_failed": False,
                                "records_total": 0, "gates_2_4_failed": 0, "kept": {}}) + "\n",
                    encoding="utf-8")
    merged = P.merge([good, miss])
    assert merged["chunks"]["a"]["clean"] and merged["chunks"]["a"]["kept"]["state_facts"] == 1
    assert merged["chunks"]["a"]["rung"] == "bulk"


def test_merge_union_missing_row_is_not_clean(tmp_path):
    up = tmp_path / "union" / "gated_union.jsonl"
    up.parent.mkdir(parents=True)
    up.write_text(json.dumps(union_row("a", kept=0, missing=True)) + "\n", encoding="utf-8")
    m = P.merge_union(up)
    assert m["chunks"]["a"]["missing"] and not m["chunks"]["a"]["clean"]
    assert not m["chunks"]["a"]["broken"]


def test_scope_year_count_matches_corpus():
    assert P.SCOPE_YEARS == 24


def union_row(cid, doc="d1", kept=2, broken=False, missing=False):
    return {"chunk_id": cid, "doc_id": doc, "records_total": kept, "records_ok": kept,
            "gates_dropped": 1 if not kept else 0, "call_broken": broken,
            "call_missing": missing, "no_content": kept == 0 and not broken and not missing,
            "kept": {"state_facts": [{}] * kept, "events": [], "claims": []}}


def test_merge_union_is_the_final_record_set(tmp_path, monkeypatch):
    up = tmp_path / "union" / "gated_union.jsonl"
    up.parent.mkdir(parents=True)
    up.write_text("".join(json.dumps(r) + "\n" for r in (
        union_row("a", kept=3), union_row("b", kept=0, broken=True), union_row("c", kept=0))),
        encoding="utf-8")
    merged = P.merge_union(up)
    assert merged["gated_rows"] == 3 and set(merged["chunks"]) == {"a", "b", "c"}
    a, b, c = (merged["chunks"][k] for k in "abc")
    assert a["clean"] and a["rung"] == "union" and sum(a["kept"].values()) == 3
    assert not b["clean"] and b["call_failed"] and b["broken"]
    assert c["clean"] and c["no_content"]


def test_merge_union_streams_rows_instead_of_materialising(tmp_path, monkeypatch):
    """The merge must consume rows lazily: at frozen scope the parsed list alone is ~970 MB."""
    up = tmp_path / "union" / "gated_union.jsonl"
    up.parent.mkdir(parents=True)
    up.write_text("".join(json.dumps(union_row(f"c{i}", kept=2)) + "\n" for i in range(50)),
                  encoding="utf-8")
    seen = []
    real = P.iter_jsonl

    def spy(path):
        for row in real(path):
            seen.append(row)
            yield row

    monkeypatch.setattr(P, "iter_jsonl", spy)
    monkeypatch.setattr(P, "load_jsonl",
                        lambda path: pytest.fail("merge_union must not materialise the file"))
    merged = P.merge_union(up)
    assert len(seen) == 50 and merged["gated_rows"] == 50
    assert len(merged["chunks"]) == 50


def test_merge_streams_and_matches_materialising_result(tmp_path):
    """Streaming and whole-file merges must agree on order and per-chunk status."""
    rows = [union_row("a", kept=3), union_row("b", kept=0, broken=True),
            union_row("c", kept=0), union_row("b", kept=2)]
    p = tmp_path / "union" / "gated_union.jsonl"
    p.parent.mkdir(parents=True)
    p.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    streamed = P.merge_union(p)
    materialised = P.merge_union(p)
    assert streamed["order"] == materialised["order"] == ["a", "b", "c"]
    assert streamed["chunks"] == materialised["chunks"]
    # a later clean row for a repeated chunk id replaces the broken verdict
    assert streamed["chunks"]["b"]["clean"] and not streamed["chunks"]["b"]["broken"]


def test_load_jsonl_still_returns_a_list(tmp_path):
    p = tmp_path / "rows.jsonl"
    p.write_text('{"a": 1}\n\n{"a": 2}\n', encoding="utf-8")
    assert P.load_jsonl(p) == [{"a": 1}, {"a": 2}]


def test_rule6_and_recall_readers(tmp_path):
    plan = tmp_path / "ladder_plan.json"
    plan.write_text(json.dumps({"queue": {"chunks": 100, "queue": 8, "queue_rate": 0.08,
                                         "triggers": {"fail_pct": 6}},
                                "retry": {"selected": 8, "unmatched": 1},
                                "escalation": {"picked": 5, "skipped": 3, "spent": 0.07,
                                               "cap": 17.0, "model": "glm-5.3",
                                               "partial_coverage": True}}), encoding="utf-8")
    r6 = P.rule6(plan)
    assert r6["present"] and r6["queue"] == 8 and r6["escalation_skipped"] == 3
    assert r6["partial_coverage"] is True and r6["escalation_model"] == "glm-5.3"
    # The fixture used to carry `est_usd`/`cap_usd` - the vocabulary this reader *asked* for and that
    # `p4c_ladder` never wrote - so the round-trip looked healthy while §12 rendered `$None of $None
    # cap`. Pin the real ladder keys (`spent`/`cap`) AND that the dead vocabulary is not what is read.
    # `cap: 17.0` is deliberately NOT the config booking (11.0): this fixture pins the reader's key, not
    # the policy number. The booking itself is pinned by test_p4c_ladder.py:256-268, which asserts the
    # live default equals config and that config is no longer 17.
    assert r6["escalation_est_usd"] == 0.07 and r6["escalation_cap_usd"] == 17.0
    plan.write_text(json.dumps({"escalation": {"est_usd": 0.07, "cap_usd": 17.0}}), encoding="utf-8")
    dead = P.rule6(plan)
    assert dead["present"] and dead["escalation_est_usd"] is None
    assert dead["escalation_cap_usd"] is None
    rec = tmp_path / "recall.json"
    rec.write_text(json.dumps({"union": {"recall": 0.61, "candidates": 500, "matched": 200},
                               "baseline_replayed_p4b_cand_recall": 0.4006,
                               "recall_gain_vs_replayed_baseline": 0.2094,
                               "p4b_report_recall": 0.5362}), encoding="utf-8")
    rc = P.recall(rec)
    assert rc["present"] and rc["strict"]["recall"] == 0.61
    assert rc["gain_vs_replayed"] == 0.2094 and rc["baseline_replayed"] == 0.4006
    assert not P.rule6(tmp_path / "nope.json")["present"]
    assert not P.recall(tmp_path / "nope.json")["present"]


def test_build_prefers_union_when_present(tmp_path, monkeypatch):
    bulk = gated("d1", {"a": gchunk("a", ok=False, dropped=1), "b": gchunk("b")}, tmp_path / "bulk")
    audit = tmp_path / "audit.json"
    audit.write_text(json.dumps({"model": "glm-5.3", "judge_family": "glm",
                                 "extractor_model": "deepseek-v4.1-flash-1017-ultrafast",
                                 "extractor_family": "deepseek", "sampled": 200, "judged": 200,
                                 "drop": 0, "unparseable": 0, "wrong": 0, "wrong_rate": 0.0}),
                     encoding="utf-8")
    up = tmp_path / "union" / "gated_union.jsonl"
    up.parent.mkdir(parents=True)
    up.write_text("".join(json.dumps(r) + "\n" for r in (
        union_row("a", kept=4), union_row("b", kept=1))), encoding="utf-8")
    (tmp_path / "union" / "union_stats.json").write_text(json.dumps(
        {"sources": [], "chunks": 2, "records": 5, "by_kind": {"state_facts": 5, "events": 0,
                                                               "claims": 0},
         "records_per_source": {"p4c_bulk": 4, "p4c_glean": 1}, "duplicates": 1,
         "duplicates_rate": 0.1667, "dropped_by_gates": 0, "broken_chunks": 0,
         "failure_queue_rate": 0.0}), encoding="utf-8")
    monkeypatch.setattr(P, "OUT", tmp_path)
    monkeypatch.setattr(P, "doc_paths", lambda ids: {})
    monkeypatch.setattr(P.R, "spent_exact", lambda passes=None: 0.0)
    rep = P.build([bulk], packs_file(tmp_path), audit, up, tmp_path / "nope.json",
                  tmp_path / "nope2.json")
    assert rep["gated_source"] == "union" and rep["union"]["records"] == 5
    assert rep["extraction"]["records_kept"] == 5
    assert rep["extraction"]["failure_queue_rate"] == 0.0
    md = P._md(rep)
    for needle in ("Union of extraction passes (D13)", "records after merge", "D11"):
        assert needle in md, needle


def test_main_refuses_without_gated(tmp_path, monkeypatch):
    monkeypatch.setattr(P, "OUT", tmp_path / "empty")
    (tmp_path / "empty").mkdir()
    monkeypatch.setattr(sys, "argv", ["p4c_report.py", "--packs", str(tmp_path / "p.jsonl")])
    try:
        P.main()
    except SystemExit as exc:
        assert "no gated output" in str(exc)
    else:
        raise AssertionError("expected SystemExit")


def test_unpriced_pass_renders_unmeasured_not_a_measured_zero(tmp_path, monkeypatch):
    """A pass with wall time but no cost row must not be reported as `$0.0000` (Defect 17 class).

    `per_pass.get(p, 0)` invented a measured zero for a pass the ledger never reported, i.e. the
    report claimed "free" for something it had not measured. The money table must say UNMEASURED.
    """
    bulk = gated("d1", {"b": gchunk("b")}, tmp_path / "bulk")
    audit = tmp_path / "audit.json"
    audit.write_text(json.dumps({"present": True}), encoding="utf-8")
    monkeypatch.setattr(P, "OUT", tmp_path)
    monkeypatch.setattr(P, "doc_paths", lambda ids: {d: f"corpus/x/{d}.md" for d in ids})
    # Ledger reports only the first pass; every other pass in the wall table stays unpriced.
    monkeypatch.setattr(P.R, "spent_exact",
                        lambda passes=None: 1.5 if passes == [P.PASSES[0]] else None)
    rep = P.build([bulk], packs_file(tmp_path), audit, tmp_path / "no_union.json")
    rep["wall"]["p4c_absent"] = {"wall_s": 12, "packs": 3}
    rep["cost"]["per_pass"] = {"p4c_absent": None}
    md = P._md(rep)
    row = next(ln for ln in md.splitlines() if "p4c_absent" in ln)
    cells = [c.strip() for c in row.strip("|").split("|")]
    assert cells[1] == "UNMEASURED", row
    assert cells[1] != "$0.0000", row


def test_tiny_pass_cost_is_not_flattened_to_zero_in_the_money_table(tmp_path, monkeypatch):
    """A real sub-cent pass cost must survive the gate report's money table (Lesson 67)."""
    bulk = gated("d1", {"b": gchunk("b")}, tmp_path / "bulk")
    audit = tmp_path / "audit.json"
    audit.write_text(json.dumps({"present": True}), encoding="utf-8")
    monkeypatch.setattr(P, "OUT", tmp_path)
    monkeypatch.setattr(P, "doc_paths", lambda ids: {d: f"corpus/x/{d}.md" for d in ids})
    monkeypatch.setattr(P.R, "spent_exact", lambda passes=None: 0.0)
    rep = P.build([bulk], packs_file(tmp_path), audit, tmp_path / "no_union.json")
    rep["wall"]["p6_judge"] = {"wall_s": 1, "packs": 1}
    rep["cost"]["per_pass"] = {"p6_judge": 1.3e-05}
    rep["cost"]["total_usd"] = 1.3e-05
    md = P._md(rep)
    row = next(ln for ln in md.splitlines() if "p6_judge" in ln)
    cells = [c.strip() for c in row.strip("|").split("|")]
    assert cells[1] == "$0.00001", row          # not the measured-zero string, and not flattened
    assert cells[1] != "$0.0000", row
    assert "**$0.00001**" in md, "total line flattened a real spend to the measured-zero string"


def test_cost_reads_the_ledger_exactly_so_an_unpriced_pass_is_none(tmp_path, monkeypatch):
    """`cost()` must hand the renderer `None` for a pass with no ledger row, not `0.0`.

    `R.spent()` collapses "no measurement" to 0.0 with `SUM` over no rows - the same value a genuine
    zero produces. The mitigation has to live in the reader, so this pins the contract at the reader.
    """
    monkeypatch.setattr(P.R, "spent_exact", lambda passes=None: None)
    rep = P.cost()
    want = set(P.PASSES) | {"p4c_audit"}
    assert set(rep["per_pass"]) == want
    assert all(v is None for v in rep["per_pass"].values())
    assert rep["total_usd"] is None, "an all-unmeasured ledger must not total to a measured $0.0000"
    assert rep["passes_unmeasured"] == sorted(want)


def test_cost_total_sums_only_measured_passes(tmp_path, monkeypatch):
    """One measured pass plus one unpriced pass must not be totalled as a one-pass zero-sum."""
    monkeypatch.setattr(P.R, "spent_exact",
                        lambda passes=None: 0.5 if passes == ["p4c_bulk"] else None)
    rep = P.cost()
    assert rep["per_pass"]["p4c_bulk"] == 0.5
    assert rep["total_usd"] == 0.5
    assert "p4c_esc" in rep["passes_unmeasured"] and "p4c_bulk" not in rep["passes_unmeasured"]


