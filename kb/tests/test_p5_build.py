"""Unit tests for kb/p5_build.py: gating, id resolution, txn attach, PPR export, code-sliced quotes."""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import duckdb
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kb"))

import p5_build as P  # noqa: E402

DDL = [
    "CREATE TABLE document (doc_id VARCHAR PRIMARY KEY, path VARCHAR, published_at DATE NOT NULL)",
    "CREATE TABLE chunk (chunk_id VARCHAR PRIMARY KEY, doc_id VARCHAR, body VARCHAR)",
    "CREATE TABLE sentence (chunk_id VARCHAR, sid INTEGER, start_char INTEGER, end_char INTEGER)",
    "CREATE TABLE entity (entity_id VARCHAR, type VARCHAR, canonical_name VARCHAR, attrs JSON, "
    "status VARCHAR, created_by VARCHAR)",
    "CREATE TABLE alias (alias VARCHAR, alias_norm VARCHAR, entity_id VARCHAR, source VARCHAR, "
    "confidence FLOAT, merged_by VARCHAR, valid_from DATE, valid_to DATE)",
    "CREATE TABLE transaction (txn_id VARCHAR PRIMARY KEY, kind VARCHAR, vessel_id VARCHAR, "
    "counterparties JSON, date_from DATE, date_to DATE, terms JSON, status VARCHAR)",
]

BODY_SENTS = ["Sold for USD 26 M in January 2026.", "The vessel is a capesize.", "Delivery in Feb 2026."]


def make_db(path: Path) -> Path:
    con = duckdb.connect(str(path))
    for stmt in DDL:
        con.execute(stmt)
    con.execute("INSERT INTO document VALUES ('d1','data/md/d1.md', DATE '2026-03-01')")
    con.execute("INSERT INTO document VALUES ('d2','data/md/d2.md', DATE '2026-03-15')")
    for eid, typ, nm, status, attrs in [
        ("vessel:imo:1", "vessel", "MV Argo", "confirmed", "{}"),
        ("vessel:imo:2", "vessel", "MV Bela", "confirmed", "{}"),
        ("vessel:old:9", "vessel", "MV Argo (dup)", "merged", '{"merged_into": "vessel:imo:1"}'),
        ("company:imo:7", "company", "Acme Shipping", "confirmed", "{}"),
    ]:
        con.execute("INSERT INTO entity VALUES (?,?,?,?,?,?)", [eid, typ, nm, attrs, status, "test"])
    con.execute(
        "INSERT INTO transaction VALUES ('t:1','sale','vessel:imo:1','[]', DATE '2026-03-05', "
        "DATE '2026-03-05', '{\"price\": 26.0}', 'reported')")
    con.execute(
        "INSERT INTO transaction VALUES ('t:2','sale','vessel:imo:1','[]', DATE '2026-09-01', "
        "DATE '2026-09-01', '{}', 'reported')")
    for i, cid in enumerate(("c1", "c2")):
        add_chunk(con, cid, f"d{i + 1}", BODY_SENTS)
    con.close()
    return path


def add_chunk(con, cid: str, doc: str, sentences: list[str]) -> None:
    body, rows, pos = " ".join(sentences), [], 0
    for sid, text in enumerate(sentences, start=1):
        start = body.index(text, pos)
        end = start + len(text)
        rows.append((cid, sid, start, end))
        pos = end
    con.execute("INSERT INTO chunk VALUES (?,?,?)", [cid, doc, body])
    con.executemany("INSERT INTO sentence VALUES (?,?,?,?)", rows)


def state_fact(cid="c1", src="vessel:imo:1", dst="company:imo:7", price="USD 26 M",
               sids=(1,), vf="January 2026", vt="January 2026", confidence=0.9):
    return {"type": "OWNS", "src": src, "dst": dst,
            "attrs_printed": [{"key": "price", "value_as_printed": price}],
            "valid_from_printed": vf, "valid_to_printed": vt,
            "chunk": cid, "sids": list(sids), "confidence": confidence}


def event(cid="c1", ent="vessel:imo:1", sids=(1,)):
    return {"type": "SALE", "summary": "Sale of MV Argo", "roles": [{"role": "asset", "entity": ent}],
            "when_printed": "January 2026", "magnitude_printed": "USD 26 M",
            "chunk": cid, "sids": list(sids), "confidence": 0.8}


def claim(cid="c1", ent="vessel:imo:1", sids=(1,)):
    return {"kind": "forecast", "subjects": [ent], "direction": "up", "horizon_printed": "2026",
            "chunk": cid, "sids": list(sids), "confidence": 0.7}


def gated_row(cid="c1", doc="d1", published="2026-03-01", kept=None, new_ok=None, new_names=None):
    return {"chunk_id": cid, "doc_id": doc, "published_at": published,
            "kept": kept if kept is not None else {"state_facts": [], "events": [], "claims": []},
            "new_entities_ok": new_ok or {}, "new_names": new_names or {}}


def write_gated(path: Path, rows: list[dict]) -> Path:
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return path


@pytest.fixture()
def db(tmp_path):
    return make_db(tmp_path / "kb.duckdb")


def run(db, tmp_path, rows, name="gated.jsonl", **kw):
    gated = write_gated(tmp_path / name, rows)
    out = tmp_path / "p5"
    report = P.build([gated], db=db, out=out, progress=False, **kw)
    return report, out, gated


# ------------------------------------------------------------------ pure helpers
def test_slice_quote_caps_three_sentences_and_drops_unknown_sids():
    sents = [(1, "a"), (2, "b"), (3, "c"), (4, "d")]
    quote, keep = P.slice_quote(sents, [4, 2, 99, 1])
    assert quote == "a b d" and keep == [1, 2, 4]
    assert P.slice_quote(sents, []) [0] == ""
    assert P.slice_quote([], [1]) [0] == ""


def test_parse_attrs_unambiguous_only():
    attrs = P.parse_attrs([{"key": "price", "value_as_printed": "USD 26 M"},
                           {"key": "share", "value_as_printed": "12.5%"},
                           {"key": "fuzzy", "value_as_printed": "26 M to 30 M"}])
    assert attrs["price"]["value"] == 26e6 and attrs["price"]["printed"] == "USD 26 M"
    assert attrs["share"]["value"] == 0.125
    assert "value" not in attrs["fuzzy"]


def test_resolve_refs_follows_merged_chain(db):
    con = P.connect(db)
    try:
        resolved = P.resolve_refs(con, {"vessel:old:9", "vessel:imo:2", "vessel:new:ghost"})
    finally:
        con.close()
    assert resolved["vessel:old:9"] == "vessel:imo:1"
    assert resolved["vessel:imo:2"] == "vessel:imo:2"
    assert resolved["vessel:new:ghost"] == "vessel:new:ghost"


def test_case_new_only_for_known_types():
    assert P.case_new("vessel:new:mv-argo") == {"type": "vessel", "slug": "mv-argo"}
    assert P.case_new("vessel:imo:9744415") is None
    assert P.case_new("widget:new:thing") is None


def test_record_id_is_content_addressed():
    payload = {"type": "OWNS", "src": "a", "chunk": "c1"}
    assert P.record_id("state_facts", payload) == P.record_id("state_facts", dict(payload))
    assert P.record_id("state_facts", payload).startswith("e:")
    assert P.record_id("state_facts", payload) != P.record_id("state_facts", {"src": "a", "chunk": "c1"})


# ------------------------------------------------------------------ full build
def test_build_inserts_records_and_clears_both_gates(db, tmp_path):
    kept = {"state_facts": [state_fact()], "events": [event()], "claims": [claim()]}
    report, out, _ = run(db, tmp_path, [gated_row(kept=kept)])
    assert report["inserted"] == {"edge": 1, "event": 1, "claim": 1, "event_role": 1, "record_txn": 3}
    assert report["table_counts"] == {"edge": 1, "event": 1, "event_role": 1, "claim": 1, "record_txn": 3}
    assert report["records_without_code_sliced_quote"] == 0
    assert report["dangling_entity_ids"] == 0
    assert report["quote_audit"]["checked"] == 3
    assert report["spend_usd"] == 0.0
    assert (out / "ppr_nodes.parquet").exists() and (out / "ppr_edges.parquet").exists()
    assert report["ppr"]["nodes"] > 0 and report["ppr"]["edges"] > 0
    assert (out / "build_report.json").exists()

    con = P.connect(db, read_only=True)
    try:
        row = con.execute("select type, src, dst, valid_from, valid_to, published_at, quote, "
                          "extractor, status, attrs from edge").fetchone()
        assert row[0] == "OWNS" and row[1] == "vessel:imo:1" and row[2] == "company:imo:7"
        assert row[3] == dt.date(2026, 1, 1) and row[4] == dt.date(2026, 1, 31)
        assert row[5] == dt.date(2026, 3, 1)
        assert row[6] == "Sold for USD 26 M in January 2026."
        assert row[7] == "gated"
        assert row[8] == "active"
        assert json.loads(row[9])["price"]["value"] == 26e6
        ev = con.execute("select type, occurred_from, magnitude_printed, quote from event").fetchone()
        assert ev[0] == "SALE" and ev[1] == dt.date(2026, 1, 1) and ev[2] == "USD 26 M"
        cl = con.execute("select kind, subject_ids, direction, horizon, quote from claim").fetchone()
        assert cl[0] == "forecast" and cl[1] == ["vessel:imo:1"]
    finally:
        con.close()


def test_build_is_idempotent(db, tmp_path):
    kept = {"state_facts": [state_fact()], "events": [], "claims": []}
    first, out, gated = run(db, tmp_path, [gated_row(kept=kept)])
    second = P.build([gated], db=db, out=out, progress=False)
    assert first["table_counts"]["edge"] == second["table_counts"]["edge"] == 1
    assert second["inserted"]["edge"] == 1


def test_ladder_precedence_first_gated_file_wins(db, tmp_path):
    first = write_gated(tmp_path / "a.jsonl", [gated_row(kept={"state_facts": [state_fact(price="USD 26 M")],
                                                             "events": [], "claims": []})])
    second = write_gated(tmp_path / "b.jsonl", [gated_row(kept={"state_facts": [state_fact(price="USD 30 M")],
                                                              "events": [], "claims": []})])
    out = tmp_path / "p5"
    report = P.build([first, second, tmp_path / "missing.jsonl"], db=db, out=out, progress=False)
    assert report["chunks_in"] == 1 and report["inserted"]["edge"] == 1
    con = P.connect(db, read_only=True)
    try:
        assert con.execute("select extractor, attrs from edge").fetchone()[0] == "a"
    finally:
        con.close()


def test_missing_sid_drops_record(db, tmp_path):
    report, _out, _g = run(db, tmp_path, [gated_row(
        kept={"state_facts": [state_fact(sids=(99,))], "events": [], "claims": []})])
    assert report["inserted"]["edge"] == 0
    assert report["drops"]["quote_empty"] == 1
    assert report["records_without_code_sliced_quote"] == 0


def test_number_not_in_quote_drops_record(db, tmp_path):
    report, _out, _g = run(db, tmp_path, [gated_row(
        kept={"state_facts": [state_fact(price="USD 99 M")], "events": [], "claims": []})])
    assert report["inserted"]["edge"] == 0
    assert report["drops"]["number_not_in_quote"] == 1


def test_chunk_mismatch_drops_record(db, tmp_path):
    report, _out, _g = run(db, tmp_path, [gated_row(
        kept={"state_facts": [state_fact(cid="c2")], "events": [], "claims": []})])
    assert report["inserted"]["edge"] == 0
    assert report["drops"]["chunk_mismatch"] == 1


def test_dangling_ref_drops_record_without_dangling_gate(db, tmp_path):
    report, _out, _g = run(db, tmp_path, [gated_row(
        kept={"state_facts": [state_fact(src="vessel:new:ghost")], "events": [], "claims": []})])
    assert report["inserted"]["edge"] == 0
    assert report["dangling_entity_ids"] == 0
    assert any(k.startswith("dangling_entity:vessel:new:ghost") for k in report["drops"])


def test_declared_new_entity_is_provisioned_and_resolves(db, tmp_path):
    nid = "vessel:new:mv-argo"
    row = gated_row(kept={"state_facts": [state_fact(src=nid)], "events": [], "claims": []},
                    new_ok={nid: True}, new_names={nid: "MV Argo"})
    report, _out, _g = run(db, tmp_path, [row])
    assert report["inserted"]["edge"] == 1 and report["dangling_entity_ids"] == 0
    con = P.connect(db, read_only=True)
    try:
        ent = con.execute("select type, canonical_name, status, created_by from entity "
                          "where entity_id = ?", [nid]).fetchone()
        assert ent == ("vessel", "MV Argo", "provisional", "p5_records")
        alias = con.execute("select alias, alias_norm, source from alias where entity_id = ?", [nid]).fetchone()
        assert alias == ("MV Argo", "MV ARGO", "p5_records")
        assert con.execute("select src from edge").fetchone()[0] == nid
    finally:
        con.close()


def test_row_new_entities_accepts_union_and_gate_shapes():
    """Union rows (which win precedence) carry `new_entities`; rung rows carry `new_entities_ok`."""
    assert P.row_new_entities({"new_entities": {"index:new:i2701": "I2701"}}) == {"index:new:i2701": "I2701"}
    assert P.row_new_entities({"new_entities_ok": {"vessel:new:a": True, "vessel:new:b": False},
                               "new_names": {"vessel:new:a": "A", "vessel:new:b": "B"}}) == {"vessel:new:a": "A"}
    assert P.row_new_entities({}) == {}
    assert P.row_new_entities({"new_entities": {}}) == {}


def test_union_shaped_new_entity_is_provisioned_and_resolves(db, tmp_path):
    """The union export is the precedence winner, so its `new_entities` must provision too."""
    nid = "vessel:new:mv-argo"
    row = {"chunk_id": "c1", "doc_id": "d1", "published_at": "2026-03-01",
           "kept": {"state_facts": [state_fact(src=nid)], "events": [], "claims": []},
           "new_entities": {nid: "MV Argo"}}
    report, _out, _g = run(db, tmp_path, [row])
    assert report["inserted"]["edge"] == 1 and report["dangling_entity_ids"] == 0
    con = P.connect(db, read_only=True)
    try:
        assert con.execute("select canonical_name, status from entity where entity_id = ?",
                           [nid]).fetchone() == ("MV Argo", "provisional")
    finally:
        con.close()


def test_merged_entity_ref_is_replaced_by_survivor(db, tmp_path):
    report, _out, gated = run(tmp_path and db, tmp_path, [gated_row(
        kept={"state_facts": [state_fact(src="vessel:old:9")], "events": [], "claims": []})])
    assert report["inserted"]["edge"] == 1
    con = P.connect(db, read_only=True)
    try:
        assert con.execute("select src from edge").fetchone()[0] == "vessel:imo:1"
    finally:
        con.close()


def test_transactions_attached_only_inside_window(db, tmp_path):
    report, _out, _g = run(db, tmp_path, [gated_row(
        kept={"state_facts": [state_fact()], "events": [], "claims": []})])
    assert report["inserted"]["record_txn"] == 1
    con = P.connect(db, read_only=True)
    try:
        link = con.execute("select record_kind, txn_id, via, days_apart from record_txn").fetchone()
        assert link[0] == "state_facts" and link[1] == "t:1"
        assert link[2] == "vessel:imo:1" and link[3] == 4
    finally:
        con.close()


def test_dry_run_limit_slices_chunks(db, tmp_path):
    rows = [gated_row(cid="c1", kept={"state_facts": [state_fact()], "events": [], "claims": []}),
            gated_row(cid="c2", doc="d2", published="2026-03-15",
                      kept={"state_facts": [state_fact(cid="c2")], "events": [], "claims": []})]
    gated = write_gated(tmp_path / "g.jsonl", rows)
    report = P.build([gated], db=db, out=tmp_path / "p5", limit=1, progress=False)
    assert report["chunks_in"] == 1 and report["chunks_processed"] == 1


def test_gate_detects_injected_bad_rows(db, tmp_path):
    run(db, tmp_path, [gated_row(kept={"state_facts": [state_fact()], "events": [], "claims": []})])
    con = P.connect(db)
    try:
        con.execute("INSERT INTO edge (edge_id, type, src, dst, published_at, chunk_id, quote, extractor) "
                    "VALUES ('e:bad','OWNS','vessel:ghost',NULL, DATE '2026-03-01','c1','', 'test')")
        dangling = P.dangling_count(con)
    finally:
        con.close()
    audit = P.audit_quotes(db)
    assert dangling["total"] == 1 and dangling["edge"] == 1
    assert audit["bad"] == 1 and audit["checked"] == 2


def test_sample_records_carry_source_paths(db, tmp_path):
    run(db, tmp_path, [gated_row(kept={"state_facts": [state_fact()], "events": [event()],
                                       "claims": [claim()]})])
    sample = P.sample_records(db, seed=P.seed_for("P5"))
    assert 1 <= len(sample) <= 10
    assert all(r["source_path"].startswith("data/md/") for r in sample)
    assert {r["table"] for r in sample} <= {"edge", "event", "claim"}


def test_report_files_and_seed(db, tmp_path):
    report, _out, _g = run(db, tmp_path, [gated_row(kept={"state_facts": [state_fact()],
                                                          "events": [], "claims": []})])
    paths = P.write_report(report, tmp_path / "P5.json", tmp_path / "P5.md")
    assert Path(paths["json"]).exists() and Path(paths["md"]).exists()
    written = json.loads(Path(paths["json"]).read_text(encoding="utf-8"))
    assert written["sample_seed"] == P.seed_for("P5") == 751592233 or written["sample_seed"] == P.seed_for("P5")
    md = Path(paths["md"]).read_text(encoding="utf-8")
    assert "Gate `records_without_code_sliced_quote` = 0" in md
    assert "Gate `dangling_entity_ids` = 0" in md
    assert "data/md/" in md


def test_cli_returns_nonzero_when_gate_fails(db, tmp_path, monkeypatch):
    gated = write_gated(tmp_path / "g.jsonl", [gated_row(
        kept={"state_facts": [state_fact()], "events": [], "claims": []})])
    monkeypatch.setattr(P, "audit_quotes", lambda *a, **k: {"checked": 1, "bad": 1, "samples": []})
    code = P.main(["--gated", str(gated), "--db", str(db), "--out", str(tmp_path / "p5"), "--no-ppr"])
    assert code == 1
