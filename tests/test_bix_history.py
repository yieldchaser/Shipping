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
    # The repo archive must be a superset of the seed: every seed key present
    # (it used to be byte-identical when the seed WAS the whole archive; the
    # full-page harvest now extends the repo archive past the 10-day seed).
    seed_keys = {(r['observation_date'], r['index_code'], r['grade']) for r in rows}
    repo_keys = {(r['observation_date'], r['index_code'], r['grade'])
                 for r in _read(HISTORY_CSV)}
    assert seed_keys <= repo_keys


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
    assert payload['rows'] == 3840
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
    assert bh['rows'] >= 2000
    assert set(bh['series'].keys()) == {'BIX_World', 'BIX_World3', 'BIX_APAC', 'BIX_EMEA', 'BIX_Americas'}
    for grades in bh['series'].values():
        for s in grades.values():
            assert s['dates'] == sorted(s['dates'])
            assert len(s['dates']) == len(s['prices']) == len(s['change_usd'])
    world = bh['series']['BIX_World']['VLSFO']
    # The full-page harvest (chart series) is at least as fresh as the flat
    # seed snapshot (benchmarks_bix): archive last date >= flat last date.
    flat_last = max(d['date'] for d in data['benchmarks_bix']
                    if d['index'] == 'BIX_World' and d['grade'] == 'VLSFO')
    assert world['dates'][-1] >= flat_last


def test_bix_history_regression_floor():
    """Distinct obs dates in the archive must never fall back below the seed."""
    rows = _read(HISTORY_CSV)
    dates = {r['observation_date'] for r in rows}
    seed_dates = {r['observation_date'] for r in _read(SEED_CSV)}
    # Floor grows with the archive: max(seed floor, recorded historical floor).
    # After the full-page backfill the archive carries ~256 published days; the
    # default floor of 200 catches any regression below the published series.
    floor = max(10, len(seed_dates), int(os.environ.get('BIX_HISTORY_MIN_DATES', '200')))
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
    assert stats['total_rows'] == 3840
    assert stats['written'] is False
    before = open(HISTORY_CSV, 'rb').read()
    res2 = subprocess.run([sys.executable, SCRIPT], capture_output=True, text=True, cwd=REPO)
    assert res2.returncode == 0, res2.stderr
    assert open(HISTORY_CSV, 'rb').read() == before


# ------------------------------------------------- full-history parser tests

if REPO not in sys.path:
    sys.path.insert(0, REPO)
from bunker_pipeline.extractors import bunkerindex_bix as bixmod  # noqa: E402


def _fixture_html():
    """Synthetic page: one labelled chart array per grade + a trailing table.
    Known ground truth: VLSFO chart 2026-01-02 = 501.25 (chart-only day, no
    change/low/high), 2026-01-05 = 502.50 (table row, change -1.25, low 495.5,
    high 510); IFO380/MGO chart-only days in the same window."""
    series = [('IFO 380', [('2026-01-02', '410.00'), ('2026-01-05', '411.50')]),
              ('VLSFO', [('2026-01-02', '501.25'), ('2026-01-05', '502.50')]),
              ('MGO', [('2026-01-02', '900.10'), ('2026-01-05', '901.00')])]
    parts = ['<html><body>']
    for label, pts in series:
        pairs = ','.join('{"date":"%s","price":"%s"}' % (d, p) for d, p in pts)
        parts.append('<script>let data = [%s];' % pairs)
        parts.append("let productName = '%s';</script>" % label)
    parts.append(
        '<table><tr><th>Date</th><th>Price</th><th>+/-</th><th>+/- %</th>'
        '<th>Low</th><th>High</th></tr>'
        '<tr><td>2026-01-05</td><td>411.50</td><td>+1.50</td><td>+0.37</td>'
        '<td>405.00</td><td>415.00</td></tr></table>'
        '<table><tr><th>Date</th><th>Price</th><th>+/-</th><th>+/- %</th>'
        '<th>Low</th><th>High</th></tr>'
        '<tr><td>2026-01-05</td><td>502.50</td><td>-1.25</td><td>-0.25</td>'
        '<td>495.50</td><td>510.00</td></tr></table>')
    parts.append('</body></html>')
    return ''.join(parts)


def test_parse_history_fixture_known_series():
    """Synthetic page with a known series -> exact parsed rows."""
    rows = bixmod.parse_bix_history(_fixture_html(), 'BIX_World')
    got = {(r['grade'], r['observation_date']): r for r in rows}
    assert ('VLSFO', '2026-01-02') in got
    chart_only = got[('VLSFO', '2026-01-02')]
    assert chart_only['price_usd'] == 501.25
    # chart series carries no change/low/high: fields stay empty, never invented
    assert chart_only['change_usd'] is None and chart_only['low_usd'] is None \
        and chart_only['high_usd'] is None
    table_day = got[('VLSFO', '2026-01-05')]
    assert table_day['price_usd'] == 502.50
    assert table_day['change_usd'] == -1.25
    assert table_day['change_pct'] == -0.25
    assert table_day['low_usd'] == 495.5 and table_day['high_usd'] == 510.0
    assert ('IFO380', '2026-01-02') in got and ('MGO', '2026-01-02') in got
    assert all(r['index_code'] == 'BIX_World' and r['unit'] == 'USD/MT'
               and r['source'] == 'BunkerIndex_BIX' for r in rows)
    assert len(rows) == 6  # 3 grades x 2 days


def test_parse_history_table_wins_over_chart():
    """The trailing-table row (richer, published revision) overwrites the
    chart-only row for the same (grade, date) key."""
    rows = bixmod.parse_bix_history(_fixture_html(), 'BIX_Americas')
    got = {(r['grade'], r['observation_date']): r for r in rows}
    assert got[('IFO380', '2026-01-05')]['change_usd'] == 1.5
    # a chart-only day with no table row keeps empty change fields
    assert got[('IFO380', '2026-01-02')]['change_usd'] is None
    # a chart day that ALSO has a table row inherits the table values
    assert got[('VLSFO', '2026-01-02')]['price_usd'] == 501.25


def test_parse_history_drops_bad_points():
    """Unparseable / out-of-range chart prices are skipped, never emitted."""
    html = (_fixture_html()
            .replace('{"date":"2026-01-02","price":"501.25"}',
                     '{"date":"2026-01-02","price":"n/a"}')
            .replace('{"date":"2026-01-05","price":"901.00"}',
                     '{"date":"2026-01-05","price":"9"}'))
    rows = bixmod.parse_bix_history(html, 'BIX_World')
    got = {(r['grade'], r['observation_date']) for r in rows}
    assert ('VLSFO', '2026-01-02') not in got
    assert ('MGO', '2026-01-05') not in got
    assert ('VLSFO', '2026-01-05') in got  # untouched points survive


def test_parse_history_grade_fallback_on_unlabelled_blocks():
    """Unlabelled chart blocks fall back to publication order IFO->VLSFO->MGO."""
    series = [('2026-01-02', '410.00'), ('2026-01-05', '411.50')], \
             [('2026-01-02', '501.25'), ('2026-01-05', '502.50')], \
             [('2026-01-02', '900.10'), ('2026-01-05', '901.00')]
    parts = ['<html><body>']
    for pts in series:
        pairs = ','.join('{"date":"%s","price":"%s"}' % (d, p) for d, p in pts)
        parts.append('<script>let data = [%s];</script>' % pairs)
    html = ''.join(parts) + '</body></html>'
    rows = bixmod.parse_bix_history(html, 'BIX_APAC')
    got = {(r['grade'], r['observation_date']): r for r in rows}
    assert got[('IFO380', '2026-01-02')]['price_usd'] == 410.0
    assert got[('VLSFO', '2026-01-02')]['price_usd'] == 501.25
    assert got[('MGO', '2026-01-02')]['price_usd'] == 900.1


def test_parse_history_comma_prices_and_multivar_names():
    """Comma-thousands chart prices parse; var/let/const declarations all work."""
    pairs = ','.join('{"date":"%s","price":"%s"}' % (d, p)
                     for d, p in (('2026-01-02', '1,201.5'), ('2026-01-05', '1,202.25')))
    html = '<script>const data = [%s];let productName = \'MGO\';</script>' % pairs
    rows = bixmod.parse_bix_history(html, 'BIX_EMEA')
    assert {(r['grade'], r['price_usd']) for r in rows} == {('MGO', 1201.5), ('MGO', 1202.25)}


