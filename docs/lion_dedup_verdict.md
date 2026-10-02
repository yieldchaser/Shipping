# lion - duplicate-key regeneration VERDICT (2026-10-03)

**Status: EXECUTED and PROVEN, LOSSLESS.** This closes the earlier run's "human decision #2" (the
stale lion demometer). The delivered lion series were rebuilt by re-running the source's own runner
with the CURRENT code, which no longer loads the W37/W38 digests that caused a double-parse.

## Command

    export PATH="/c/Users/Dell/AppData/Local/Programs/Python/Python314:$PATH"
    python3 scripts/extract/publishers/run_lion_tables.py

46 PDFs -> 46 reports processed. The runner writes `lion_demometer_series.csv`,
`lion_sales_series.csv`, `lion_demo_sales_series.csv`, `lion_deals_series.csv` with `to_csv(index=False)`
(a rebuild, not a merge). `lion_demolition_series.csv` (516 rows) is a DIFFERENT writer and was NOT
touched - it was already 0 duplicate keys.

## Measured before -> after (delivered `data/extracted/series/lion_*`)

| series | before | after | removed | dup keys after |
|---|---|---|---|---|
| lion_deals_series | 1,314 | 1,241 | 73 | 0 |
| lion_sales_series | 1,200 | 1,136 | 64 | 0 |
| lion_demometer_series | 576 | 552 | 24 | 0 |
| lion_demo_sales_series | 114 | 105 | 9 | 0 |
| lion_demolition_series | 516 | 516 | 0 (untouched) | 0 |

170 rows removed in total.

## The cause, and why the digest rows are safe to drop

Every duplicate traces to the W37 (2026-09-11) and W38 (2026-09-18) issues being parsed TWICE - once
from the PDF and once from the `corpus/01-brokers/_digests/lion/2026/` markdown. Source-file census of
the duplicate rows:

    lion_deals: 31 PDF + 31 digest (W37) and 33 PDF + 33 digest (W38)
    lion_sales: 26 PDF + 26 digest (W37) and 29 PDF + 29 digest (W38)
    lion_demo_sales: 5+5 (W37), 4+4 (W38)

The current code looks for digests named `lion_12_09_2026_lion_weekly_market_report_week_37_2026.md`,
which do NOT exist on disk (the files are `lion_shipbrokers_12_09_2026_...`), so the digest jobs are
not added - and the W37/W38 PDFs (which arrived later and now exist) carry the same data. No week is
lost: the delivered series holds the same 46 issue dates before and after.

## Control - provably lossless

Key = every column except `source_file`. `PRE minus POST` = removed (73 / 64 / 24 / 9, one per series),
`POST minus PRE` = **0 added on all four**. Stronger entity check (issue_date + vessel, or
issue_date + country + vessel_type + price_point for the demometer):

    series            PRE entities   POST entities   PRE-only   POST-only
    lion_sales              1136            1136          0           0
    lion_deals              1241            1241          0           0
    lion_demo_sales          105             105          0           0
    lion_demometer           552             552          0           0

So every entity survives and nothing new is invented. Of the removed rows 12 (sales 9 + deals 9 =
18 keys across two series) were not byte-identical duplicates but **whitespace variants** of a kept
row - e.g. W37 M/V AE JUPITER kept with comment "offers invited 27th August" (PDF) and dropped as
"offers invited 27 th August" (digest); POST retains AE JUPITER exactly once, price $11.5m. The
entity check proves no vessel disappeared.

## Notes

* `data/extracted/**` is gitignored - the regenerated CSVs are working-tree artefacts, NOT committed.
* md tier: 46 `.md` + 46 `.tables.json`.
* No value changed on any kept row (`POST minus PRE == 0` on the full-column key rules that out).

## WARNING - re-running this runner writes INTO THE CORPUS

`run_lion_tables.py` does NOT only write the delivered series: for each PDF it also re-renders the
matching digest markdown and OVERWRITES `corpus/01-brokers/_digests/lion/2026/*week_NN_*.md`
(lines 769-776). This re-run modified **8 corpus digest files** (1,327 insertions / 1,360 deletions).
They were restored with `git checkout -- corpus/01-brokers/_digests/lion/2026/`. The series CSVs do
NOT depend on the digests, so the dedup stands. **Lesson: before re-running any publisher's runner,
check whether its write path includes CORPUS, not just data/extracted/.**
