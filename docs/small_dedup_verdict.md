# small duplicate-key items - VERDICT (2026-10-03, hourly supervisor run)

Scope: the 8 small census items the 02:34 run left "newly named" (35 rows). Method and
convention follow the campaign: a duplicate is DROPPED only when two different SOURCE FILES
carry the same row (a copy / capture / misfiled pair); an in-document repeat that the
publisher actually prints is LEFT AS-IS and recorded, exactly like the carriers_sales
LAMBADA precedent.

## CLOSED - 2 files, cross-source, lossless (7 rows)

| series | before | after | removed | class |
|---|---|---|---|---|
| star_asia_demolition_series.csv | 3,120 | 3,116 | 4 | misfiled 2023 W41/W42 pair (the valuation_matrix class) |
| hellenic_iron_ore_commentary_series.csv | 1,182 | 1,179 | 3 | multiple Wayback captures of one MMI page (baltic_ncfi class) |

star_asia_demolition: the 4 rows are issue_date 2023-10-14 / week 41, contributed once by
`star_asia_2023_W41_Market-report-Week-41.pdf` and once by the misfiled
`star_asia_2023_W42_Market-report-Week-42.pdf` (both cover "WEEK 41 - October 14, 2023").
hellenic_iron_ore_commentary: 2026-03-19 from the 03-17/03-19 captures, 2026-06-08 from the
06-04/06-05/06-08 captures - same commentary text, same issue.

CONTROL (key = every column except `source_file`): star_asia_demolition removed 4 / added 0 /
keys_pre_only 0 / keys_post_only 0; hellenic_iron_ore_commentary removed 3 / added 0 /
keys_pre_only 0 / keys_post_only 0. Post dup keys = 0 on both.
Guards NOT wired: `run_star_asia_tables.py` (demolition); the MMI-iron-ore writer - a future
re-run would reintroduce them. The delivered CSVs are the artefact of record.
Pre-fix copies: `scratch/small_dedup/PRE_*.csv`; filter `scratch/small_dedup/dedup_small.py`.

## LEFT AS-IS - 6 files, 28 rows, all SAME-SOURCE faithful repeats (do NOT re-flag)

Measured evidence - occurrences of the row's distinguishing text field in the SOURCE PDF
(when occurrences >= row count the publisher prints it repeatedly; a parser double-write
would give 1):

| series | rows | field | text occurrences vs rows |
|---|---|---|---|
| clarksons_desk_talk_series.csv | 17 | commentary_text | running header "Sale & Purchase \| Clarksons Hellas Weekly Bulletin \| ..." appears 2-4x per doc (once per page) |
| xclusiv_sales_series.csv | 5 | NAME | JIANGSU NEWYANGZI 2/2, ZHOUSHAN CHANGHONG 4/2, JINGJIANG NANYANG 4/4 |
| poten_top_charterers_series.csv | 2 | charterer | Mexico 5/2, Dominican Republic 2/2 |
| star_asia_deals_series.csv | 2 | vessel_name | JOINT LUCK 2/2, WHITE PALM 2/2 |
| hellenic_gms_port_positions_series.csv | 1 | vessel_name | P Delta 2/2 |
| star_asia_ferrous_scrap_series.csv | 1 | grade | Shredded 1/2 (single-row ambiguity, left in place - lower risk) |

Note on clarksons: the "commentary" rows are running page headers captured as commentary by
the parser (commentary_text = "24 December 2021", or the bulletin masthead line). That is a
parser-sensitivity observation about a RECORD tier, not a duplication defect; the rows are
faithful to the page. Flagged, not changed.

## Reverted work (recorded so it is not repeated)

A first pass removed all 35 rows by exact full-row key. That is WRONG for the 28 same-source
rows: it deletes a value the publisher prints. Reverted the 6 files from their PRE copies;
kept only the 2 cross-source fixes above. Lesson: an exact-duplicate filter must split
same-source from cross-source BEFORE it writes.

## Post-fix census

Only remaining duplicate rows: hellenic VV 214 cross-source (hellenic_vv_matrix 132,
hellenic_vv_sales 60, hellenic_vv_benchmark_sales 22) - the ONE documented HUMAN DECISION -
plus 1 documented carriers_sales publisher double-print, plus the 15 hellenic_vv_matrix
same-source rows inside that same VV decision. Nothing else.
