# Source parity audit - the user's question, answered by measurement

## The question
Was source 1's level of treatment applied to every other source, or were things
missed?

## The answer: NO. Chart-value extraction was done for ONE of six sources.

Measured by inspecting what each source actually shipped (not recalled):

    source                  md  tables  charts   charts.json CONTENT
    advanced_shipping      249     249     249   VALUES  keys=['1','2','6','8']
    star_asia              193     193     193   page-records only
    ssy                    519     519       2   page-records only
    xclusiv                266     266     266   page-records only
    fearnleys              257     257     257   page-records only  keys=[]
    banchero_costa         243     243       0   none

    files containing chart-value content:
      advanced_shipping : 40
      every other source: 0

## What source 1 delivered that the others did not
    .charts.json carrying axis-CALIBRATED values, e.g. a fitted line
    value = -3.3148*y + 1224.08 with max_err 0.039, plus per-chart scale
    clustering so stacked charts were not forced onto one scale (that error had
    produced max_err 124.5), and per-chart tick grouping at the real 18pt pitch
    (a 6pt threshold had split every tick and found 0 charts on a page with 4).
    Individual chart values were then verified by eye against the rendered axis
    (a grey gridline read 630.8 against an axis label of 630).

No other source received any of that.

## Two findings worse than 'missing'
1. fearnleys has 257 charts.json files that are EMPTY (keys=[]). Files that exist
   and contain nothing look like chart handling was done. Missing would have been
   more honest.
2. banchero_costa has NO charts.json at all.

## The process failure this exposes, in plain terms
Source 1 was my own output. I had the bar available the entire time and did not
use it as the standard for subsequent sources. Instead the success criterion
drifted to "N/N documents, 0 failures" - a metric that is satisfied by converting
text only. The same substitution produced the banchero table miss, the intermodal
backtest (252/252 while 16.5% wrong) and xclusiv's labels (85% while wrong).

A justification was also applied beyond the case that earned it: star_asia's
charts legitimately restate its tables (verified by reading a page), and that
finding was then used to skip charts everywhere - including xclusiv, whose charts
plot TCE SERIES OVER TIME that may exist nowhere else in the document. The
conclusion was generalised without being re-verified.

## What is owed, by source, in priority order
1. xclusiv - 266 docs, VECTOR charts on pages 2,3,4,7,8. Its charts carry TCE
   time series; source 1's calibration method applies directly since the charts
   are vector. Most likely to hold unique series.
2. banchero_costa - tables are glyph-ciphered (~30% of docs) and charts are not
   extracted at all. Two separate debts in one source.
3. fearnleys - replace the 257 empty charts.json files with real content or remove
   them, so absence is visible rather than disguised.
4. ssy - charts (it has 2 charts.json files, both page-records only).
5. star_asia - re-verify the "charts restate the tables" claim on more than the
   one page that earned it, rather than inheriting it.
6. advanced_shipping - the only source at standard. Re-verify it still holds after
   the Baltic/T-C/BDTI label fixes rather than assuming.

## Also still open
- banchero tables: cipher decoded partially, OCR proven to read values, decoding
  not yet applied.
- intermodal has a value CSV but NO .md at all.
- The 22 scripts referencing the deleted reports/ directory.
- The Fearnleys S&P sync that has not updated for days.
