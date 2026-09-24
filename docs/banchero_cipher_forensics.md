# banchero_costa: glyph-cipher forensics and the LlamaParse routing map

Date: 2026-09-24. Status: MEASURED, decision pending an API key.

## What is actually wrong (this corrects two earlier wrong conclusions)

Earlier tonight this source was described as "prose extracted, tables ignored", and
then as "92.5% of table rows readable". Both were wrong, and the second was wrong
because of a bug in my own metric (I counted `"` as a cipher character, which in a
JSON dump appears around every string and pushed every row over the threshold).

The truth, measured:

* **243 / 243 docs carry ciphered content.** There are no clean docs.
* `text.jsonl` does **not** contain `TD3C`, `TD15`, `TD6`, `TD7`, `TD19`, `16-Jan`,
  `116,448` or `105,321`. Those values are **not** in the text layer in any form.
* The **glyph outlines render correctly** - the page shows a perfect table. Only the
  text layer is wrong. This is the classic broken-subset-font case.

## Root cause, established by probing the embedded fonts

Per page there are ~10 subset fonts (`Calibri`, `Calibri-Bold`, `ArialMT`), each used
by a different class of content:

| font | size | content | text layer |
|---|---|---|---|
| Calibri | 11.0 | prose | **correct** English |
| Calibri | 8.4 | rate tables | cipher |
| Calibri-Bold | 8.4 | table headers | cipher |
| ArialMT | 6.8 | table data | cipher |

* Every subset **has** a `/ToUnicode` CMap - and applying them does not fix the text
  (e.g. `BIKXFS+Calibri` decodes 12 characters of `"In 2025, global seaborne crude"`
  correctly and then derails to `"In 205,globaser cu"`).
* Every embedded subset has been **stripped**: no `post` table, glyph names are all
  `glyph00001…glyph000NN`.
* Therefore glyph→character is **not recoverable from font metadata**. The outlines
  are the only carrier of the truth, and reading outlines means reading pixels.

Two attempts to crib-drag a global substitution are committed here as negative results
(`scratch/cipher_crib.py`, `scratch/cipher_crib2.py`) - the mapping is per font subset
and not globally consistent, so a single decode table does not exist.

**Conclusion: this source genuinely cannot be recovered locally.** LlamaParse's
13/13 recall on the same page is not a convenience, it is the only working method.

## The routing map (what we actually need to pay for)

`scratch/banchero_route_map.py` walks every page of every doc and flags pages carrying
ciphered spans. Result, written to `scratch/banchero_cipher_pages.json`:

```
pages scanned            : 3753
pages with cipher spans  : 1074   (28.6%)
clean pages              : 2679   (71.4%)   <- local extraction, free
docs                     : 243
docs needing NO cloud    : 1
```

So the paid surface is **1,074 pages**, not 243 documents (3,753 pages). Pages are
typically the rate/fixture tables - e.g. 2021 docs need pages 7, 12, 13.

## Cost options for the 1,074 pages

| tier | cr/page | total | fits in 10,000? |
|---|---|---|---|
| Fast | 1 | ~1,074 | yes - but no markdown, no items tree |
| Cost Effective | 3 | ~3,222 | yes |
| Agentic | 18 | ~19,300 | **no** |
| Agentic Plus | 45 | ~48,300 | **no** |

The earlier test used plain `agentic` with the cost optimizer **off** and no page
targeting - the most expensive configuration possible - which is why one 16-page doc
cost ~160 credits.

`page_ranges.target_pages` + `cost_optimizer` are the two levers. Caching makes any
re-run of an identical request free for 48h, so verification re-runs cost nothing.

## Decision

Escalate **only** these pages, and verify the tier before scaling. Do not run
`agentic` across the corpus; it does not fit the budget and has not been shown to be
necessary for pages this uniform.
