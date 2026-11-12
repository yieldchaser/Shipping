"""Tests for kb/p4c_pack.py - deterministic packer for the P4c full-scope extraction."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import duckdb
import pytest

KB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KB))

import p4c_pack as P  # noqa: E402


def rows(spec):
    """spec = [(doc_id, ord, tokens)] -> scope-shaped rows."""
    return [{"chunk_id": f"{d}-{o}", "doc_id": d, "ord": o, "tokens": t, "doc_type": "broker_weekly",
             "publisher": "Baltic Exchange", "published_at": "2015-10-02", "title": "t",
             "year": 2015, "section_class": "prose"} for d, o, t in spec]


# --- pack_rows -----------------------------------------------------------------------------
def test_pack_respects_chunk_cap():
    packs = P.pack_rows(rows([("a", i, 1) for i in range(10)]))
    assert [len(p) for p in packs] == [6, 4]
    assert [r["chunk_id"] for p in packs for r in p] == [f"a-{i}" for i in range(10)]


def test_pack_respects_token_cap():
    packs = P.pack_rows(rows([("a", 0, 2000), ("a", 1, 2000), ("a", 2, 1000), ("a", 3, 1000)]))
    # greedy: 2000 | 2000+1000 | 1000 - the 3rd chunk fits the open pack, the 4th does not
    assert [len(p) for p in packs] == [1, 2, 1]
    assert all(sum(r["tokens"] for r in p) <= 3500 or len(p) == 1 for p in packs)


def test_pack_never_crosses_document():
    packs = P.pack_rows(rows([("a", 0, 10), ("a", 1, 10), ("b", 0, 10)]))
    assert [[r["chunk_id"] for r in p] for p in packs] == [["a-0", "a-1"], ["b-0"]]


def test_oversized_chunk_gets_its_own_pack():
    packs = P.pack_rows(rows([("a", 0, 5000), ("a", 1, 10)]))
    assert [len(p) for p in packs] == [1, 1]
    assert packs[0][0]["chunk_id"] == "a-0"  # kept, never dropped: scope must not shrink


def test_pack_is_deterministic():
    spec = rows([("a", i, 300) for i in range(14)] + [("b", i, 300) for i in range(3)])
    assert P.pack_rows(spec) == P.pack_rows(list(spec))


def test_pack_record_envelope():
    chunk_rows = rows([("a", 0, 10), ("a", 1, 10)])
    rec = P.pack_record(7, chunk_rows)
    assert rec["n"] == 7 and rec["pack_id"] == "p000007"
    assert rec["doc_id"] == "a" and rec["ord_first"] == 0
    assert rec["chunk_ids"] == ["a-0", "a-1"] and rec["tokens"] == 20
    assert rec["doc"]["publisher"] == "Baltic Exchange" and rec["year"] == 2015
    assert rec["key"] == "a|a-0+a-1"


# --- enrich / scope streaming --------------------------------------------------------------
def fixture_db(path: Path) -> Path:
    con = duckdb.connect(str(path))
    con.execute("create table document(doc_id varchar, publisher_id varchar, doc_type varchar, "
                "title varchar, published_at date)")
    con.execute("create table section(section_id varchar, doc_id varchar, kind varchar, "
                "sec_item varchar)")
    con.execute("create table chunk(chunk_id varchar, doc_id varchar, section_id varchar, "
                "ord integer, kind varchar, extract boolean, body varchar, tokens integer, "
                "entity_ids varchar[])")
    con.execute("create table sentence(chunk_id varchar, sid integer, start_char integer, "
                "end_char integer)")
    con.execute("create table entity(entity_id varchar, type varchar, canonical_name varchar, "
                "attrs varchar)")
    con.execute("insert into document values('d1','Baltic Exchange','broker_weekly','T', DATE '2015-10-02')")
    con.execute("insert into section values('s1','d1','prose','')")
    con.execute("insert into entity values('vessel:1','vessel','Alpha','{\"imo\":\"123\"}'),"
                "('port:NLRTM','port','Rotterdam','{}')")
    for i, (body, tok) in enumerate([("One vessel fixture.", 100), ("Two more tonnage.", 5000)]):
        cid = f"d1-{i}"
        con.execute("insert into chunk values(?,?,?,?,?,?,?,?,?)",
                    [cid, "d1", "s1", i, "prose", True, body, tok, ["port:NLRTM", "vessel:1"]])
        con.execute("insert into sentence values(?,?,?,?)", [cid, 0, 0, len(body)])
    con.close()
    return path


def test_enrich_adds_sentences_and_known(tmp_path):
    db = fixture_db(tmp_path / "kb.duckdb")
    con = duckdb.connect(str(db), read_only=True)
    packs = P.enrich(con, [P.pack_record(0, [{"chunk_id": "d1-0", "doc_id": "d1", "ord": 0,
                                             "tokens": 100, "doc_type": "broker_weekly",
                                             "publisher": "Baltic Exchange",
                                             "published_at": "2015-10-02", "title": "T",
                                             "year": 2015, "section_class": "prose"}])])
    con.close()
    p = packs[0]
    assert p["blocks"][0]["cid"] == "c1"
    assert p["blocks"][0]["sentences"] == [[0, "One vessel fixture."]]
    assert [k["id"] for k in p["known"]] == ["port:NLRTM", "vessel:1"]  # sorted by id
    assert p["known"][1]["key"] == "123"  # imo surfaces as the entity key


def test_enrich_caps_known_entities(tmp_path):
    db = fixture_db(tmp_path / "kb.duckdb")
    con = duckdb.connect(str(db), read_only=True)
    rec = P.pack_record(0, [{"chunk_id": "d1-0", "doc_id": "d1", "ord": 0, "tokens": 100,
                             "doc_type": "broker_weekly", "publisher": "Baltic Exchange",
                             "published_at": "2015-10-02", "title": "T", "year": 2015,
                             "section_class": "prose"}])
    old = P.KNOWN_MAX
    P.KNOWN_MAX = 1
    try:
        P.enrich(con, [rec])
    finally:
        P.KNOWN_MAX = old
        con.close()
    assert len(rec["known"]) == 1 and len(rec["known_ids"]) == 2


def test_iter_packs_streams_full_scope(tmp_path):
    db = fixture_db(tmp_path / "kb.duckdb")
    con = duckdb.connect(str(db), read_only=True)
    enrich_con = duckdb.connect(str(db), read_only=True)
    packs = list(P.iter_packs(con, enrich_con))
    con.close()
    enrich_con.close()
    assert len(packs) == 2  # 5,000-token chunk is its own pack
    assert [p["n"] for p in packs] == [0, 1]
    assert packs[0]["chunk_ids"] == ["d1-0"] and packs[1]["chunk_ids"] == ["d1-1"]
    st = P.initial_stats()
    for p in packs:
        P.add_pack(st, p)
    s = P.summarise(st)
    assert s["packs"] == 2 and s["chunks"] == 2 and s["docs"] == 1
    assert s["max_pack_tokens"] == 5000 and s["max_pack_chunks"] == 1
    assert s["frozen_scope"] == {"chunks": P.SCOPE_CHUNKS, "docs": P.SCOPE_DOCS}
    assert s["coverage_complete"] is False  # fixture is a slice, not the frozen scope


def test_iter_packs_reads_past_the_first_stream_batch(tmp_path):
    """Regression: the scope cursor died after batch 1 when enrich reused the same connection,
    which silently truncated the full-scope build to 4,000 of 86,607 chunks."""
    db = fixture_db(tmp_path / "kb.duckdb")
    con = duckdb.connect(str(db), read_only=True)
    enrich_con = duckdb.connect(str(db), read_only=True)
    packs = list(P.iter_packs(con, enrich_con, batch_rows=1))  # 2 rows -> 2 stream batches
    con.close()
    enrich_con.close()
    assert [p["chunk_ids"] for p in packs] == [["d1-0"], ["d1-1"]]
    assert all(p["blocks"][0]["sentences"] for p in packs)



def test_build_writes_jsonl_and_refuses_second_append(tmp_path):
    db = fixture_db(tmp_path / "kb.duckdb")
    out = tmp_path / "packs.jsonl"
    st = P.build(out_path=out, db=db)
    lines = out.read_text(encoding="utf-8").splitlines()
    assert len(lines) == st["packs"] == 2
    rec = json.loads(lines[1])
    assert rec["chunk_ids"] == ["d1-1"] and rec["blocks"][0]["sentences"]
    with pytest.raises(SystemExit):
        P.build(out_path=out, db=db)
