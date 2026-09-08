#!/usr/bin/env python3
"""
Tests for the BIX benchmark history accumulator
(scripts/bunkers/build_bix_history.py, data/bunkers/bix_history.csv, and the
bix_history embed in data/bunkers/bunker_frontend_summary.json).

Phase AD: the flat bunker_bix_macro_benchmarks.csv is overwritten by the
harvester every run and the source pages only expose ~10 trailing obs days;
the archive must seed, merge, dedupe (latest wins), stay idempotent, and grow.
"""

import csv
import json
import os
import subprocess
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(REPO, 'scripts', 'bunkers', 'build_bix_history.py')
HISTORY_CSV = os.path.join(REPO, 'data', 'bunkers', 'bix_history.csv')
SEED_CSV = os.path.join(REPO, 'data', 'bunkers', 'bunker_bix_macro_benchmarks.csv')
SUMMARY_JSON = os.path.join(REPO, 'data', 'bunkers', 'bunker_frontend_summary.json')

FIELDS = ['observation_date', 'index_code', 'grade', 'price_usd', 'change_usd',
          'change_pct', 'low_usd', 'high_usd', 'unit', 'source']

sys.path.insert(0, os.path.dirname(SCRIPT))
import build_bix_history as bbh  # noqa: E402


def _read(path):
    with open(path, 'r', newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------- helpers

def _row(d='2026-09-10', idx='BIX_World', grade='VLSFO', price='700.0',
         chg='1.5', src='BunkerIndex_BIX'):
    return {'observation_date': d, 'index_code': idx, 'grade': grade,
            'price_usd': price, 'change_usd': chg, 'change_pct': '0.21',
            'low_usd': '640', 'high_usd': '760', 'unit': 'USD/MT', 'source': src}


def _tmp_csv(tmp_path, rows, name='input.csv'):
    p = tmp_path / name
    with open(p, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator='\n')
        w.writeheader()
        w.writerows(rows)
    return str(p)


# ---------------------------------------------------------------- tests

def test_seed_from_source_150_rows(tmp_path):
    """First run with no prior archive: all 150 seed rows land in the archive."""
    hist = tmp_path / 'bix_history.csv'
    archive, stats = bbh.merge_history(history_path=str(hist), seed_path=SEED_CSV)
    assert stats['prior_history_rows'] == 0
    assert stats['total_rows'] == 150
    assert stats['distinct_obs_dates'] == 10
    bbh.write_history(archive, str(hist))
    rows = _read(str(hist))
    assert len(rows) == 150
    # byte-identical to the repo archive built from the same seed
    assert open(str(hist), 'rb').read() == open(HISTORY_CSV, 'rb').read()


def test_idempotent_rerun_byte_identical():
    """Running the script twice leaves the repo archive byte-identical."""
    before = open(HISTORY_CSV, 'rb').read()
    res = subprocess.run([sys.executable, SCRIPT], capture_output=True, text=True, cwd=REPO)
    assert res.returncode == 0, res.stderr
    after = open(HISTORY_CSV, 'rb').read()
    assert before == after


def test_dedupe_latest_wins(tmp_path):
    """Same (date, index, grade) from an extra input: the newer revision wins."""
    hist = tmp_path / 'bix_history.csv'
    archive, _ = bbh.merge_history(history_path=str(hist), seed_path=SEED_CSV)
    bbh.write_history(archive, str(hist))  # persist so the next merge sees a live archive
    rev = _row(price='777.0', src='Backfill_X')
    inp = _tmp_csv(tmp_path, [_row(price='999.0', src='Old_Rev'), rev], name='rev.csv')
    archive, stats = bbh.merge_history(history_path=str(hist), seed_path=SEED_CSV,
                                       inputs=[inp])
    key = ('2026-09-10', 'BIX_World', 'VLSFO')
    assert float(archive[key]['price_usd']) == 777.0  # latest rev, canonical float form
    assert archive[key]['source'] == 'Backfill_X'
    assert stats['new_keys_added'] == 1
    bbh.write_history(archive, str(hist))
    rows = _read(str(hist))
    assert len(rows) == 151  # 150 seed + 1 genuinely new obs
    assert any(r['source'] == 'Backfill_X' for r in rows)


def test_idempotent_after_merge(tmp_path):
    """Re-running with the same extra input never duplicates or reverts."""
    hist = tmp_path / 'bix_history.csv'
    archive, _ = bbh.merge_history(history_path=str(hist), seed_path=SEED_CSV)
    bbh.write_history(archive, str(hist))
    inp = _tmp_csv(tmp_path, [_row(price='777.0', src='Backfill_X')], name='r.csv')
    a1, s1 = bbh.merge_history(history_path=str(hist), seed_path=SEED_CSV, inputs=[inp])
    assert s1['total_rows'] == 151
    b1 = {k: dict(v) for k, v in a1.items()}
    bbh.write_history(a1, str(hist))
    a2, s2 = bbh.merge_history(history_path=str(hist), seed_path=SEED_CSV, inputs=[inp])
    assert s2['total_rows'] == 151
    assert a2 == b1


def test_crlf_safe_roundtrip(tmp_path):
    """A CRLF source merges cleanly and output stays LF/deterministic."""
    hist = tmp_path / 'bix_history.csv'
    archive, _ = bbh.merge_history(history_path=str(hist), seed_path=SEED_CSV)
    bbh.write_history(archive, str(hist))
    crlf = tmp_path / 'crlf.csv'
    with open(crlf, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator='\r\n')
        w.writeheader()
        w.writerows([_row(d='2026-09-11', price='701.0')])
    archive2, stats = bbh.merge_history(history_path=str(hist), seed_path=SEED_CSV,
                                        inputs=[str(crlf)])
    bbh.write_history(archive2, str(hist))
    raw = open(str(hist), 'rb').read()
    assert b'\r\n' not in raw
    assert stats['total_rows'] == 151  # 150 seed + 1 new obs from the CRLF source
    assert not any(r['observation_date'] == '2026-09-11' and '\r' in ''.join(r.values())
                   for r in _read(str(hist)))


def test_ignores_malformed_rows(tmp_path):
    """Rows missing key fields or price never enter the archive (no fabrication)."""
    hist = tmp_path / 'bix_history.csv'
    base, _ = bbh.merge_history(history_path=str(hist), seed_path=SEED_CSV)
    bbh.write_history(base, str(hist))
    junk = _tmp_csv(tmp_path, [
        {'observation_date': '', 'index_code': 'BIX_World', 'grade': 'VLSFO', 'price_usd': '700'},
        {'observation_date': '2026-09-12', 'index_code': 'BIX_World', 'grade': '', 'price_usd': '700'},
        {'observation_date': '2026-09-12', 'index_code': 'BIX_World', 'grade': 'VLSFO', 'price_usd': ''},
    ], name='junk.csv')
    archive, stats = bbh.merge_history(history_path=str(hist), seed_path=SEED_CSV,
                                       inputs=[junk])
    assert stats['total_rows'] == 150


def test_build_payload_shape_and_monotonic_dates():
    """Payload: per index x grade, dates ascending, prices aligned; full archive."""
    payload = bbh.build_bix_history_payload(HISTORY_CSV)
    assert payload['source'] == 'BunkerIndex_BIX'
    assert payload['unit'] == 'USD/MT'
    assert payload['rows'] == 150
    n_series = 0
    for idx, grades in payload['series'].items():
        for grade, s in grades.items():
            assert s['dates'] == sorted(s['dates']), f'{idx}/{grade} dates not monotonic'
            assert len(s['dates']) == len(s['prices']) == len(s['change_usd'])
            # cross-check against the CSV itself (no drift between embed and archive)
            hist_rows = {(r['observation_date']): r for r in _read(HISTORY_CSV)
                         if r['index_code'] == idx and r['grade'] == grade}
            assert set(s['dates']) == set(hist_rows.keys())
            assert s['prices'][-1] == round(float(hist_rows[s['dates'][-1]]['price_usd']), 2)
            n_series += 1
    assert n_series == 15  # 5 indices x 3 grades


def test_summary_embeds_bix_history():
    """The rebuilt summary carries the full-history embed (not just last 10)."""
    with open(SUMMARY_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)
    bh = data.get('bix_history')
    assert bh is not None, 'bix_history embed missing from bunker_frontend_summary.json'
    assert bh['rows'] >= 150
    assert set(bh['series'].keys()) == {'BIX_World', 'BIX_World3', 'BIX_APAC', 'BIX_EMEA', 'BIX_Americas'}
    for grades in bh['series'].values():
        for s in grades.values():
            assert s['dates'] == sorted(s['dates'])
            assert len(s['dates']) == len(s['prices']) == len(s['change_usd'])
    world = bh['series']['BIX_World']['VLSFO']
    assert world['dates'][-1] == max(d['date'] for d in data['benchmarks_bix'] if d['index'] == 'BIX_World' and d['grade'] == 'VLSFO')


def test_bix_history_regression_floor():
    """Distinct obs dates in the archive must never fall back below the seed."""
    rows = _read(HISTORY_CSV)
    dates = {r['observation_date'] for r in rows}
    seed_dates = {r['observation_date'] for r in _read(SEED_CSV)}
    # Floor grows with the archive: max(seed floor, recorded historical floor).
    floor = max(10, len(seed_dates), int(os.environ.get('BIX_HISTORY_MIN_DATES', '10')))
    assert len(dates) >= floor, (
        f'BIX history regressed: {len(dates)} distinct obs dates < floor {floor}')


def test_floor_grows_with_archive(tmp_path, monkeypatch):
    """The floor is designed to grow: an archive with more dates passes higher floors."""
    hist = tmp_path / 'bix_history.csv'
    archive, _ = bbh.merge_history(history_path=str(hist), seed_path=SEED_CSV)
    for i in range(15):  # push to 25 distinct dates
        for idx in ('BIX_World', 'BIX_APAC'):
            archive[(f'2026-10-{i+1:02d}', idx, 'VLSFO')] = _row(d=f'2026-10-{i+1:02d}', idx=idx)
    bbh.write_history(archive, str(hist))
    dates = {r['observation_date'] for r in _read(str(hist))}
    assert len(dates) == 25
    monkeypatch.setenv('BIX_HISTORY_MIN_DATES', '20')
    floor = max(10, len({r['observation_date'] for r in _read(SEED_CSV)}),
                int(os.environ['BIX_HISTORY_MIN_DATES']))
    assert len(dates) >= floor


def test_main_smoke_json_report():
    """CLI smoke: --dry-run prints a parseable stats JSON without writing."""
    res = subprocess.run([sys.executable, SCRIPT, '--dry-run'], capture_output=True, text=True, cwd=REPO)
    assert res.returncode == 0, res.stderr
    stats = json.loads(res.stdout.strip().splitlines()[-1])
    assert stats['total_rows'] == 150
    assert stats['written'] is False
    before = open(HISTORY_CSV, 'rb').read()
    res2 = subprocess.run([sys.executable, SCRIPT], capture_output=True, text=True, cwd=REPO)
    assert res2.returncode == 0, res2.stderr
    assert open(HISTORY_CSV, 'rb').read() == before
