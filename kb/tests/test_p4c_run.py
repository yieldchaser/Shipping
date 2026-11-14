"""Tests for kb/p4c_run.py - batch streaming, resume, and the escalation ladder (no model calls)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

KB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KB))

import p4c_run as C  # noqa: E402


def pack(doc="d1", cids=("a", "b"), key=None):
    blocks = [{"cid": f"c{i + 1}", "sentences": [[0, f"text {cid}"]]} for i, cid in enumerate(cids)]
    return {"n": 0, "pack_id": "p000000", "doc_id": doc, "ord_first": 0,
            "key": key or f"{doc}|{'+'.join(cids)}", "chunk_ids": list(cids), "tokens": 10,
            "doc": {"publisher": "P", "doc_type": "broker_weekly", "published_at": "2015-10-02",
                    "heading": "T"},
            "year": 2015, "section_class": "prose", "blocks": blocks,
            "known": [{"id": "port:NLRTM", "type": "port", "name": "Rotterdam", "key": ""}],
            "known_ids": ["port:NLRTM"]}


def write_jsonl(path: Path, rows) -> None:
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def test_batches_sizes():
    got = [len(b) for b in C.batches(list(range(7)), 3)]
    assert got == [3, 3, 1]


def test_pending_skips_packs_with_a_raw(monkeypatch):
    packs = [pack(cids=("a",)), pack(cids=("b",)), pack(cids=("c",))]
    done = {packs[1]["key"]}

    def fake_has_raw(pass_name, model, mode, p):
        return p["key"] in done

    monkeypatch.setattr(C, "has_raw", fake_has_raw)
    left = C.pending(packs, "p4c_bulk", "m", "tools")
    assert [p["key"] for p in left] == [packs[0]["key"], packs[2]["key"]]


def test_single_pack_keeps_envelope_and_one_block():
    sp = C.single_pack(pack(cids=("a", "b")), "b", n=3)
    assert sp["chunk_ids"] == ["b"] and sp["key"] == "d1|b"
    assert sp["pack_id"] == "s000003" and sp["n"] == 3
    assert len(sp["blocks"]) == 1 and sp["blocks"][0]["cid"] == "c2"
    assert sp["doc"] == pack()["doc"] and sp["known"][0]["id"] == "port:NLRTM"


def test_singles_for_only_failed_chunks():
    p = pack(cids=("a", "b", "c"))
    out = C.singles_for(p, {"b": ["sid_missing"]})
    assert [s["chunk_ids"][0] for s in out] == ["b"]


def test_pending_retries_a_truncated_raw(monkeypatch):
    """Regression: a raw stored with finish_reason=length at the max_tokens cap is unusable, so the
    pack must stay pending and be re-requested (plan §7.4 gate 1) rather than counted as done."""
    import p4b_run as B

    packs = [pack(cids=("a",)), pack(cids=("b",))]
    raws = {packs[0]["key"]: {"raw": '{"records":[]}', "finish_reason": "length"},
            packs[1]["key"]: {"raw": '{"records":[]}', "finish_reason": "tool_calls"}}
    monkeypatch.setattr(B, "load_result", lambda pass_name, job: raws.get(job["request_hash"]))

    def fake_make_job(pass_name, model, mode, p):
        return {"request_hash": p["key"]}

    monkeypatch.setattr(B, "make_job", fake_make_job)
    assert C.has_raw("p4c_bulk", "m", "tools", packs[0]) is False   # truncated -> retry
    assert C.has_raw("p4c_bulk", "m", "tools", packs[1]) is True    # complete -> cached
    assert [p["key"] for p in C.pending(packs, "p4c_bulk", "m", "tools")] == [packs[0]["key"]]


def test_plan_escalation_writes_singles(tmp_path):
    packs = tmp_path / "packs.jsonl"
    write_jsonl(packs, [pack(cids=("a", "b")), pack(doc="d2", cids=("c",), key="d2|c")])
    fails = tmp_path / "failures.jsonl"
    write_jsonl(fails, [{"doc_id": "d1", "chunk_id": "b", "reasons": ["sid_missing"]},
                        {"doc_id": "d2", "chunk_id": "c", "reasons": ["schema_fail"]}])
    st = C.plan_escalation(packs, fails, tmp_path / "singles.jsonl")
    assert st == {"failed_chunks": 2, "singles": 2, "unmatched": 0,
                  "out": str(tmp_path / "singles.jsonl")}
    rows = [json.loads(x) for x in (tmp_path / "singles.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [r["chunk_ids"] for r in rows] == [["b"], ["c"]]
    assert [r["pack_id"] for r in rows] == ["s000000", "s000001"]


def test_plan_escalation_reports_unmatched(tmp_path):
    packs = tmp_path / "packs.jsonl"
    write_jsonl(packs, [pack()])
    fails = tmp_path / "failures.jsonl"
    write_jsonl(fails, [{"doc_id": "dX", "chunk_id": "nope"}])
    st = C.plan_escalation(packs, fails, tmp_path / "singles.jsonl")
    assert st["failed_chunks"] == 1 and st["singles"] == 0 and st["unmatched"] == 1


def test_run_packs_resumes_and_counts(monkeypatch, tmp_path):
    packs = tmp_path / "packs.jsonl"
    write_jsonl(packs, [pack(doc=f"d{i}", cids=("a", "b"), key=f"d{i}|a+b") for i in range(3)])
    monkeypatch.setattr(C, "load_modes", lambda: {"m": "tools"})
    monkeypatch.setattr(C, "state_path", lambda pass_name: tmp_path / f"run_{pass_name}.json")
    seen = []

    class FakeRunner:
        def __init__(self, *a, **k):
            self.stats = {"ok": 0}

        def run(self, jobs):
            seen.extend(j["meta"]["pack_key"] for j in jobs)

    monkeypatch.setattr(C.B, "runner_for", lambda *a, **k: FakeRunner())
    spent = {"v": 0.0}

    def fake_spent(passes=None):
        spent["v"] += 0.01 * len(seen)
        return spent["v"]

    monkeypatch.setattr(C.R, "spent", fake_spent)
    monkeypatch.setattr(C, "has_raw", lambda *a, **k: False)
    st = C.run_packs("p4c_bulk", "m", 10.0, packs_path=packs, shard=2, progress=False)
    assert len(seen) == 3 and st["packs"] == 3 and st["chunks"] == 6
    assert st["batches"] == 2 and st["packs_skipped"] == 0
    assert (tmp_path / "run_p4c_bulk.json").exists()


def test_run_packs_requires_a_recorded_mode(monkeypatch, tmp_path):
    monkeypatch.setattr(C, "load_modes", lambda: {})
    try:
        C.run_packs("p4c_bulk", "m", 1.0, packs_path=tmp_path / "p.jsonl", progress=False)
    except SystemExit as exc:
        assert "preflight" in str(exc)
    else:
        raise AssertionError("expected SystemExit")


def test_run_packs_windows_start_and_advance(monkeypatch, tmp_path):
    """`start` skips whole cached batches and `start_next` lands past the last batch looked at."""
    packs = tmp_path / "packs.jsonl"
    write_jsonl(packs, [pack(doc=f"d{i}", cids=("a",), key=f"d{i}|a") for i in range(5)])
    monkeypatch.setattr(C, "load_modes", lambda: {"m": "tools"})
    monkeypatch.setattr(C, "state_path", lambda pass_name: tmp_path / f"run_{pass_name}.json")
    monkeypatch.setattr(C.B, "runner_for", lambda *a, **k: type("R", (), {
        "run": lambda self, jobs: None, "stats": {"ok": 0}})())
    monkeypatch.setattr(C.R, "spent", lambda passes=None: 0.0)
    monkeypatch.setattr(C, "has_raw", lambda *a, **k: True)
    st = C.run_packs("p4c_bulk", "m", 10.0, packs_path=packs, shard=2, limit=2, progress=False,
                     start=2)
    assert st["packs"] == 0 and st["start"] == 2
    assert st["start_next"] == 4          # two batches of 2 starting at pack 2
    st2 = C.run_packs("p4c_bulk", "m", 10.0, packs_path=packs, shard=2, limit=2, progress=False,
                      start=4)
    assert st2["start_next"] == 5         # tail batch of 1
    st3 = C.run_packs("p4c_bulk", "m", 10.0, packs_path=packs, shard=2, limit=2, progress=False,
                      start=5)
    assert st3["packs"] == 0 and st3["start_next"] == 5   # past the end: no window yielded


def test_pending_shards_packs_only_missing_packs_densely(tmp_path, monkeypatch):
    """Regression for the 2026-11-14 head-sweep stall: with packs 0-1399 done, the windowed walk
    handed the runner 1-2 packs per batch (~0.5 ok/min from a pool accepting 120/min) and a
    monotonic cursor could step over a sparse tail it never revisited. Dense mode must hand over
    exactly the pending packs, in full-width batches, and must not skip a pending pack."""
    packs = tmp_path / "packs.jsonl"
    write_jsonl(packs, [pack(doc=f"d{i}", cids=("a",), key=f"d{i}|a") for i in range(7)])
    done = {f"d{i}|a" for i in range(5)}          # head finished, pending = d5, d6
    monkeypatch.setattr(C, "has_raw", lambda pass_name, model, mode, p: p["key"] in done)

    def has_raw(pass_name, model, mode, p):
        return p["key"] in done

    batches = list(C.pending_shards(packs, "p4c_bulk", "m", "tools", limit=0, shard=2))
    assert [[p["key"] for p in b] for b, _c, _n, _o in batches] == [["d5|a", "d6|a"]]
    assert [c for _b, c, _n, _o in batches] == [2]

    # a limit caps the number of pending packs taken, not the number of windows walked
    capped = list(C.pending_shards(packs, "p4c_bulk", "m", "tools", limit=1, shard=1))
    assert [[p["key"] for p in b] for b, _c, _n, _o in capped] == [["d5|a"]]


def test_run_packs_dense_delivers_full_batches_behind_a_finished_head(monkeypatch, tmp_path):
    """Same regression through `run_packs(dense=True)`: the six finished head packs must not starve
    the batch, and every pending pack must still be sent exactly once."""
    packs = tmp_path / "packs.jsonl"
    write_jsonl(packs, [pack(doc=f"d{i}", cids=("a",), key=f"d{i}|a") for i in range(8)])
    done = {f"d{i}|a" for i in range(6)}
    monkeypatch.setattr(C, "load_modes", lambda: {"m": "tools"})
    monkeypatch.setattr(C, "state_path", lambda pass_name: tmp_path / f"run_{pass_name}.json")
    sent = []

    class FakeRunner:
        def __init__(self, *a, **k):
            self.stats = {"ok": 0}

        def run(self, jobs):
            sent.extend(j["meta"]["pack_key"] for j in jobs)

    monkeypatch.setattr(C.B, "runner_for", lambda *a, **k: FakeRunner())
    monkeypatch.setattr(C.R, "spent", lambda passes=None: 0.0)
    monkeypatch.setattr(C, "has_raw",
                        lambda pass_name, model, mode, p: p["key"] in done)
    st = C.run_packs("p4c_bulk", "m", 10.0, packs_path=packs, shard=2, dense=True,
                     progress=False)
    assert sent == ["d6|a", "d7|a"]
    assert st["packs"] == 2 and st["chunks"] == 2 and st["batches"] == 1


def test_run_packs_dense_flag_reaches_pending_shards(monkeypatch, tmp_path):
    """The daemon's round call must actually switch the scheduler, not silently keep windowing."""
    seen = {}

    def fake_pending(packs_path, pass_name, model, mode, limit=0, shard=200):
        seen["pending"] = (pass_name, model, mode, limit, shard)
        return iter(())

    monkeypatch.setattr(C, "load_modes", lambda: {"m": "tools"})
    monkeypatch.setattr(C, "state_path", lambda pass_name: tmp_path / f"run_{pass_name}.json")
    monkeypatch.setattr(C.B, "runner_for", lambda *a, **k: type("R", (), {
        "run": lambda self, jobs: None, "stats": {"ok": 0}})())
    monkeypatch.setattr(C.R, "spent", lambda passes=None: 0.0)
    monkeypatch.setattr(C, "pending_shards", fake_pending)
    monkeypatch.setattr(C, "pack_shards", lambda *a, **k: pytest.fail(
        "dense run must not use the windowed scheduler"))
    st = C.run_packs("p4c_bulk", "m", 10.0, packs_path=tmp_path / "p.jsonl", shard=3, limit=9,
                     dense=True, progress=False)
    assert seen["pending"] == ("p4c_bulk", "m", "tools", 9, 3)
    assert st["packs"] == 0
