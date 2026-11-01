"""upsert_rows_to_csv must not re-append a row whose key field is None (written as an empty cell)."""
from scripts.extract.orchestrate_incremental_ingest import upsert_rows_to_csv


def test_none_key_matches_empty_cell_on_rerun(tmp_path):
    p = tmp_path / "s.csv"
    rows = [{"issue": "2026-10-24", "vessel": "A", "dwt": None}]
    assert upsert_rows_to_csv(p, rows, ["issue", "vessel", "dwt"], ["issue", "vessel", "dwt"]) == 1
    assert upsert_rows_to_csv(p, rows, ["issue", "vessel", "dwt"], ["issue", "vessel", "dwt"]) == 0
    assert len(p.read_text(encoding="utf-8").splitlines()) == 2
