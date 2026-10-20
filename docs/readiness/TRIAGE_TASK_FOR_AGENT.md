# Readiness gate: flagged-page triage (task for an agent)

Input: `data/derived/readiness/numbers_flagged_pages.csv`, written by `scripts/verify/readiness_numbers.py`.
Each row is one PDF page where numbers printed in the PDF text layer are missing from the page's Markdown
(`data/extracted/md/<md>`; the PDF is the MD's `source_file`). `sample_missing` lists up to 12 of the missing values.

## Rules

- READ ONLY. Do not edit any file under `data/`, `corpus/` or `scripts/`. The only file you write is
  `data/derived/readiness/triage.csv`.
- Every verdict comes from looking at the rendered page, never from the text alone. Render with
  `python -c "import pymupdf; d=pymupdf.open(PDF); d[PAGE-1].get_pixmap(dpi=110).save('p.png')"` and look at it.
- Do not guess. If you cannot tell, the category is `unsure`.

## Work pattern

Group the flagged rows by publisher and page number. Pages that flag in almost every issue (for example
Advanced p8-9, Carriers p3, Intermodal p7) are one layout: check 3 issues spread over the years (oldest, middle,
latest). If all 3 get the same category, apply it to the group and say so in `note`. Pages that flag rarely are
checked one by one.

## triage.csv columns

`publisher, page, md (or "ALL <n> issues"), category, where_the_numbers_are, note`

Categories:

- `excluded_by_design`: a page the MDs deliberately leave out (contacts, Greek equities, FX/stock tickers,
  disclaimers, Fearnleys rate cards). Name the page content.
- `chart_labels`: the numbers are labels printed on a chart (data labels, axis ticks, legends).
- `missing_table`: a table or table rows printed on the page are not in the MD. Give the table title.
- `missing_text`: prose numbers missing (a paragraph dropped or truncated).
- `wrong_values`: the MD has the table but with different numbers. Give one example: printed vs MD.
- `unsure`.

Stop and report the counts per category per publisher when done. Do not fix anything.
