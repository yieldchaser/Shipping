# Clarksons — machine pass verdict (Claude, 2026-10-13)

- MDs: 181. Machine pass (`page_view.py`-style text-layer check, numbers >=3 digits): 179 clean,
  1 absent, 1 missing PDF. Table: `clarksons_machine.csv`.
- ABSENT: `clarksons/2026/2026-05-18_ssy-pacific-capesize-index-...090a95d37484.md` was an **SSY Pacific
  Capesize Index** PDF (filed under corpus/02-hellenic/shipbuilding) dressed as a Clarksons S&P weekly:
  invented "No bulker/tanker sales reported" and a Clarksons contact block that is not on the page; the
  real route table was missing. Deleted. Replaced by `ssy/2026/ssy_2026_20260515-Pacific-Capesize-Report.md`
  built from the page text layer in the SSY template; its 2026-05-08 column equals the current column of
  the committed 20260508 MD (independent cross-check). Change columns are computed (curr - prev).
  The 0515 PDF exists only under hellenic/shipbuilding; no .tables.json sidecar written.
- MISSING PDF: `clarksons_2026_Weekly-Sales-9th-October-2026.md` — source PDF not in the corpus checkout;
  not checked.
- NOT YET DONE: eye pass (manual 4a) on 2 issues per year with `page_view.py side`. Spot check done:
  2021-07-02 p1 side-by-side — 9 rows, all cells match the page.
