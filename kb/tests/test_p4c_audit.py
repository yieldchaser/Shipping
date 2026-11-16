"""Tests for kb/p4c_audit.py - seeded sampling, verdict parsing, family rule (no model calls)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

KB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KB))

import p4c_audit as A  # noqa: E402


def rec(kind="state_facts", **over):
    base = {"chunk": "c1", "sids": [0], "confidence": 0.9, "quote": ["Rotterdam handled 12 vessels."]}
    base.update(over)
    return base


def gated_row(cid="c1", n_facts=2):
    return {"chunk_id": cid, "doc_id": "d1", "publisher": "Baltic Exchange",
            "doc_type": "broker_weekly", "published_at": "2015-10-02",
            "state_facts": [rec() for _ in range(n_facts)], "events": [],
            "claims": [rec(kind="claims")]}


def real_gate_row(cid="c1", n_facts=2):
    """The shape `p4c_gate.py` actually writes: kinds live *inside* `kept`, never at top level."""
    return {"chunk_id": cid, "doc_id": "d1", "publisher": "Baltic Exchange",
            "doc_type": "broker_weekly", "published_at": "2015-10-02",
            "kept": {"state_facts": [rec() for _ in range(n_facts)], "events": [],
                     "claims": [rec(kind="claims")]}}


def union_row(cid="c1", n_facts=2):
    """The union export writes `kept` *and* spreads the same lists at top level."""
    row = real_gate_row(cid, n_facts)
    row.update(row["kept"])
    return row


def test_model_family_and_rule():
    assert A.model_family("DeepSeek-V4.1-Flash") == "deepseek"
    assert A.model_family("deepseek-v4.1-flash-1017-ultrafast") == "deepseek"
    assert A.model_family("glm-5.3") == "glm"
    assert A.model_family("nvidia/nemotron-3-ultra-550b-a55b") == "nvidia"
    assert A.judge_family_ok("glm-5.3", "DeepSeek-V4.1-Flash")
    assert not A.judge_family_ok("deepseek-v4-flash", "DeepSeek-V4.1-Flash")


def test_selected_extractor_is_the_p4c_bulk_source():
    """The label must follow P4c's own extractor, not whatever P4b happened to select."""
    assert A._selected_extractor() == "DeepSeek-V4.1-Flash"
    assert A.model_family(A._selected_extractor()) == "deepseek"
    assert A.judge_family_ok("glm-5.3", A._selected_extractor())
    assert not A.judge_family_ok("DeepSeek-V4.1-Flash", A._selected_extractor())


def test_flat_records_one_entry_per_record():
    rows = [gated_row(n_facts=2), gated_row(cid="c2", n_facts=0)]
    flat = A.flat_records(rows)
    assert len(flat) == 4
    assert [f["kind"] for f in flat] == ["state_facts", "state_facts", "claims", "claims"]
    assert flat[0]["quote"] == "Rotterdam handled 12 vessels."
    assert flat[0]["doc_id"] == "d1" and flat[0]["index"] == 0


def test_flat_records_reads_the_shape_the_gate_writes():
    """Regression: gate rows keep kinds inside `kept`, so a top-level-only reader yielded 0 records
    and the 200-record audit gate could never be satisfied."""
    flat = A.flat_records([real_gate_row(n_facts=2)])
    assert len(flat) == 3
    assert [f["kind"] for f in flat] == ["state_facts", "state_facts", "claims"]
    assert flat[0]["quote"] == "Rotterdam handled 12 vessels."


def test_flat_records_reads_the_union_shape_without_double_counting():
    """Union rows carry both shapes; the reader must count each record once."""
    flat = A.flat_records([union_row(n_facts=2)])
    assert len(flat) == 3
    assert [f["kind"] for f in flat] == ["state_facts", "state_facts", "claims"]


def test_default_gated_prefers_the_union_export(tmp_path, monkeypatch):
    """The audit must judge the same record set P5 loads, which puts the union export first."""
    monkeypatch.setattr(A, "OUT", tmp_path)
    assert A.default_gated() == tmp_path / "gated.jsonl"  # union missing -> gate rows
    (tmp_path / "union").mkdir()
    (tmp_path / "union/gated_union.jsonl").write_text("", encoding="utf-8")
    assert A.default_gated() == tmp_path / "union/gated_union.jsonl"


def test_sample_records_is_seeded_and_capped():
    flat = A.flat_records([gated_row(n_facts=30)])
    a = A.sample_records(flat, n=5, seed=1234)
    b = A.sample_records(flat, n=5, seed=1234)
    c = A.sample_records(flat, n=5, seed=999)
    assert [x["chunk_id"] for x in a] == [x["chunk_id"] for x in b]
    assert [x["index"] for x in a] == [x["index"] for x in b]
    assert [x["index"] for x in a] != [x["index"] for x in c]
    assert [x["audit_id"] for x in a] == ["a000", "a001", "a002", "a003", "a004"]
    assert len(A.sample_records(flat[:3], n=5, seed=1)) == 3


def test_plan_streams_the_same_sample_it_used_to_load(tmp_path, monkeypatch):
    """`plan()` must pick the records the in-memory selection picked, without loading them all.

    Guards the memory fix: the streaming plan is only acceptable because its output is identical, so
    this pins the two implementations against each other on a file with more rows than the sample.
    """
    import json as _json
    rows = [gated_row(n_facts=3) for _ in range(12)]
    for i, r in enumerate(rows):
        r["chunk_id"] = f"c{i:03d}"
    path = tmp_path / "gated.jsonl"
    path.write_text("\n".join(_json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    monkeypatch.setattr(A, "AUDIT_ITEMS", tmp_path / "audit_items.json")

    total = A.count_records(path)
    assert total == sum(len(A.flat_row_records(r)) for r in rows) == len(A.flat_records(rows))

    st = A.plan(path, n=5)
    got = _json.loads((tmp_path / "audit_items.json").read_text(encoding="utf-8"))
    assert st["records_available"] == total and st["items"] == 5

    # same seeded indices the whole-file version would draw, walked in ascending order
    flat = A.flat_records(rows)
    old = A.sample_records(flat, n=5, seed=A.seed_for())
    assert _json.dumps(got["items"], sort_keys=True) == _json.dumps(old, sort_keys=True)
    assert [x["audit_id"] for x in got["items"]] == ["a000", "a001", "a002", "a003", "a004"]


def test_plan_over_a_small_file_takes_everything(tmp_path, monkeypatch):
    import json as _json
    rows = [gated_row(n_facts=2)]
    path = tmp_path / "gated.jsonl"
    path.write_text(_json.dumps(rows[0]) + "\n", encoding="utf-8")
    monkeypatch.setattr(A, "AUDIT_ITEMS", tmp_path / "audit_items.json")
    st = A.plan(path, n=200)
    got = _json.loads((tmp_path / "audit_items.json").read_text(encoding="utf-8"))
    assert st["records_available"] == 3 and st["items"] == 3  # 2 facts + 1 claim, fewer than the target
    assert [x["audit_id"] for x in got["items"]] == ["a000", "a001", "a002"]


def test_parse_verdict_variants():
    assert A.parse_verdict('{"verdict": "keep", "reason": "ok"}') == ("keep", "ok")
    assert A.parse_verdict('```json\n{"verdict":"drop","reason":"number missing"}\n```')[0] == "drop"
    assert A.parse_verdict('I think {"verdict":"DROP"}') == ("drop", "")
    assert A.parse_verdict("nonsense") == (None, "")
    assert A.parse_verdict('{"verdict":"maybe"}') == (None, "")


def test_summarise_counts_wrong_conservatively(monkeypatch):
    payload = {"items": [{"audit_id": f"a{i:03d}", "chunk_id": f"c{i}", "kind": "state_facts",
                          "record": rec(), "quote": "q", "index": i} for i in range(6)]}
    raws = {0: '{"verdict":"keep"}', 1: '{"verdict":"drop","reason":"x"}',
            2: '{"verdict":"keep"}', 3: "garbage", 4: '{"verdict":"keep"}'}  # item 5 unjudged

    def fake_result(pass_name, job):
        i = payload["items"].index([it for it in payload["items"]
                                    if it["audit_id"] == job["meta"]["audit_id"]][0])
        return {"raw": raws[i]} if i in raws else None

    monkeypatch.setattr(A.B, "load_result", fake_result)
    st = A.summarise(payload, "glm-5.3", "json_schema")
    assert st["sampled"] == 6 and st["judged"] == 5
    assert st["keep"] == 3 and st["drop"] == 1 and st["unparseable"] == 1
    assert st["wrong"] == 2 and st["wrong_rate"] == 0.4


def test_plan_writes_seeded_items(monkeypatch, tmp_path):
    src = tmp_path / "gated.jsonl"
    src.write_text(json.dumps(gated_row(n_facts=4)) + "\n" + json.dumps(gated_row(cid="c2")) + "\n",
                   encoding="utf-8")
    monkeypatch.setattr(A, "OUT", tmp_path)
    monkeypatch.setattr(A, "AUDIT_ITEMS", tmp_path / "audit_items.json")
    st = A.plan(src, n=3)
    payload = json.loads((tmp_path / "audit_items.json").read_text(encoding="utf-8"))
    assert st == {"records_available": 8, "items": 3, "out": str(tmp_path / "audit_items.json")}
    assert payload["seed"] == A.seed_for("P4C") and len(payload["items"]) == 3


def test_judge_job_never_carries_the_extractor_tool(monkeypatch):
    """Defect 37: judge calls inherited the extractor's forced `record_extraction` tool.

    `make_job` built `extra_body` from the extractor transport mode, so with `mode="tools"` every
    judge call was forced to call the extraction function and answered with an extraction body. The
    audit then read 184/200 verdicts as unparseable and reported `wrong_rate 1.0` - a failing gate
    invented by the harness. Pin the judge transport: JSON verdict, no `tools`/`tool_choice`, however
    the extractor negotiated its own mode, and bump the version tag so polluted verdicts cannot be
    served from the raw cache.
    """
    item = {"chunk_id": "c1", "kind": "state_facts", "index": 0, "audit_id": "a000",
            "record": rec(), "quote": ["Rotterdam handled 12 vessels."]}
    for mode in ("tools", "json_schema", "json_object"):
        body = A.make_job(item, "glm-5.3", mode)["extra_body"]
        assert "tools" not in body and "tool_choice" not in body, mode
        assert body["response_format"] == {"type": "json_object"}
    plain = A.make_job(item, "deepseek-v4-flash", "tools")
    assert "tools" not in plain["extra_body"]
    assert plain["job_key"] != A.make_job(item, "glm-5.3", "tools")["job_key"]
    # the version tag moved past the polluted cache, not just the transport mode
    assert A.make_job(item, "glm-5.3", "tools")["job_key"] != A.R.job_key(
        A.PASS, "glm-5.3", "audit-v1", "tools", "c1|state_facts|0")


def test_the_cache_tag_is_derived_from_the_prompt(monkeypatch):
    """Defect 38: a literal version tag replays verdicts from a superseded prompt.

    Rewriting `JUDGE_PROMPT` to score the frozen §7.4 contract changed the instrument. If the cache
    tag stayed a constant, `runner.run` would serve the previous prompt's raw verdicts and the audit
    would report a measurement it never took. The tag must be a function of the prompt text.
    """
    item = {"chunk_id": "c1", "kind": "state_facts", "index": 0, "audit_id": "a000",
            "record": rec(), "quote": ["Rotterdam handled 12 vessels."]}
    before = A.make_job(item, "glm-5.3", "tools")["job_key"]
    assert A.judge_prompt_version().startswith("audit-")
    assert len(A.judge_prompt_version()) == len("audit-") + 12
    monkeypatch.setattr(A, "JUDGE_PROMPT", A.JUDGE_PROMPT + "\nOne more sentence.")
    after = A.make_job(item, "glm-5.3", "tools")["job_key"]
    assert after != before, "editing the judge prompt must invalidate the cached verdicts"


def test_the_judge_prompt_scores_only_the_frozen_contract():
    """The judge must not demand evidence the acceptance contract never asks for.

    Measured: 0/183,486 union records violate §7.4 rules 3-4 (union re-gates every record through
    `extract_gates`), yet the old prompt produced 44/184 drops. Prompting for `direction` and entity
    semantics that the frozen contract resolves code-side is an instrument defect (Defect 37/38
    family), not a record defect.
    """
    p = A.JUDGE_PROMPT
    assert "§7.4" in p
    assert "need NOT appear in the quote" in p  # known ids resolve document-wide (rule 4)
    assert "new_entities_verified" in p  # Defect 39: the catalog the gate verified must be given
    assert "Do not judge tone" in p and "paraphrase" in p
    # the five legal direction values, and nothing beyond them
    assert all(v in p for v in ("`up`", "`down`", "`flat`", "`mixed`", "`na`"))


def test_the_audit_item_carries_the_catalog_rule_4_is_checked_against():
    """Defect 39: rule 4 is checked against a new entity's OWN sentences, so the item must carry them.

    The frozen `extract_gates.gate_chunk` verifies each new entity against `quote_for(ne.sids,
    ne_sents)` and `p4c_union` keeps only the passing ids. An audit item that omitted that catalog
    made the judge re-test rule 4 against the *record's* quote and drop 8 compliant records
    (`kb/state/tmp/audit9_unionmap.out.txt`: every dropped `new:` ref had `unresolved_new=[]`).
    """
    row = {"chunk_id": "c9", "doc_id": "d9", "publisher": "Fearnleys", "doc_type": "broker_weekly",
           "published_at": "2026-01-05",
           "new_entities": {"company:new:nautilus_international": "Nautilus International"},
           "kept": {"claims": [{"subjects": ["company:new:nautilus_international"], "direction": "na",
                                "quote": ["Owners are reorganising."]}]}}
    (item,) = A.flat_row_records(row)
    assert item["new_entities_verified"] == {
        "company:new:nautilus_international": "Nautilus International"}
    body = json.loads(A.item_messages(item)[1]["content"])
    assert body["new_entities_verified"]["company:new:nautilus_international"] == "Nautilus International"
    # a row with no catalog must still produce a usable item, not crash or fabricate one
    (bare,) = A.flat_row_records({"chunk_id": "c1", "kept": {"claims": [{"quote": ["x"]}]}})
    assert bare["new_entities_verified"] == {}
    assert json.loads(A.item_messages(bare)[1]["content"])["new_entities_verified"] == {}


def test_cmd_run_refuses_same_family(monkeypatch):
    monkeypatch.setattr(A, "_selected_extractor", lambda: "deepseek-v4-flash")
    args = type("Args", (), {"model": "deepseek-v4-pro", "extractor": None, "cap": 0.0, "limit": 0})()
    try:
        A.cmd_run(args)
    except SystemExit as exc:
        assert "family" in str(exc)
    else:
        raise AssertionError("expected SystemExit")


# --- cap gate and unmeasured judge spend -------------------------------------------------------
def _audit_args(**kw):
    base = {"model": "glm-5.3", "extractor": "deepseek-v4-flash", "cap": None, "limit": 0}
    base.update(kw)
    return type("Args", (), base)()


def test_cmd_run_refuses_to_book_a_judge_pass_against_an_unreadable_cap(monkeypatch, tmp_path):
    """`max(0.0, None - x)` either raises or lies; the guard must refuse and name `--cap`."""
    monkeypatch.setattr(A, "AUDIT_ITEMS", tmp_path / "audit_items.json")
    (tmp_path / "audit_items.json").write_text(
        json.dumps({"records_available": 0, "items": []}), encoding="utf-8")
    monkeypatch.setattr(A.B, "cap_arg", lambda explicit: None)
    monkeypatch.setattr(A, "run_judge", lambda *a, **k: pytest.fail("must not book a judge pass"))
    monkeypatch.setattr(A, "summarise", lambda *a, **k: pytest.fail("must not write a summary"))
    with pytest.raises(SystemExit) as exc:
        A.cmd_run(_audit_args())
    msg = str(exc.value)
    assert "cannot price this audit run" in msg
    assert "unreadable" in msg and "--cap" in msg


def test_cmd_run_honours_an_explicit_cap_with_an_unreadable_ledger(monkeypatch, tmp_path):
    """An operator `--cap 0.0` is a deliberate choice: the guard must not fire and the cap must arrive."""
    monkeypatch.setattr(A, "AUDIT_ITEMS", tmp_path / "audit_items.json")
    (tmp_path / "audit_items.json").write_text(
        json.dumps({"seed": 1, "records_available": 0, "items": []}), encoding="utf-8")
    monkeypatch.setattr(A, "AUDIT_JSON", tmp_path / "audit.json")
    monkeypatch.setattr(A, "AUDIT_MD", tmp_path / "audit.md")
    monkeypatch.setattr(A.B, "pipeline_cap", lambda: None)
    monkeypatch.setattr(A.R, "spent_exact", lambda *a, **k: None)
    seen = {}

    def fake_run_judge(model, cap, limit=0):
        seen["cap"] = cap
        return {"model": model, "mode": "tools", "jobs": 0, "ok": 0,
                "cost_usd": A.M.round_usd(A.R.spent_exact(passes=[A.PASS])), "wall_s": 0.0}

    monkeypatch.setattr(A, "run_judge", fake_run_judge)
    assert A.cmd_run(_audit_args(cap=0.0)) == 0
    assert seen["cap"] == 0.0
    assert json.loads((tmp_path / "audit.json").read_text(encoding="utf-8"))["run"]["cost_usd"] is None


def test_run_judge_reports_an_unpriced_ledger_as_unmeasured(monkeypatch):
    """`round(R.spent(...), 6)` collapsed "no measurement" to the measured-zero string `0.0`.

    The judge spend sits beside the §11 gate verdict in the owner-facing audit, so an unpriced ledger
    must read UNMEASURED rather than free (Defect 17 class)."""
    monkeypatch.setattr(A.B, "load_modes", lambda: {"glm-5.3": "tools"})
    monkeypatch.setattr(A.B, "runner_for", lambda *a, **k: type("R", (), {
        "run": lambda self, jobs: None, "stats": {"ok": 0}})())
    monkeypatch.setattr(A.R, "spent_exact", lambda passes=None: None)
    got = A.run_judge("glm-5.3", 5.0, limit=0)
    assert got["cost_usd"] is None
    monkeypatch.setattr(A.R, "spent_exact", lambda passes=None: 0.0)
    assert A.run_judge("glm-5.3", 5.0, limit=0)["cost_usd"] == 0.0   # a measured zero survives

