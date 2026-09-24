# Flagged-page triage: 65 of 69 are false positives; only fearnleys 2018 is real

Date: 2026-09-24. Method: every flagged page outside banchero was rendered to
`scratch/bench/png/flagged/<source>/` and the spans that tripped the detector printed
(`data/derived/flagged_pages_manifest.json`). Nothing was sent to any API.

## Result

| source | pages | what tripped the detector | verdict |
|---|---|---|---|
| affinity | 7 | `######` | FALSE POSITIVE - Excel "column too narrow" |
| agora | 5 | `#DIV/0!` | FALSE POSITIVE - a spreadsheet error string |
| intermodal | 25 | `"W-EAGLE"`, `"WARRIOR"`, `"DANAI"`, `"KASAGISAN"` | FALSE POSITIVE - vessel names in quotes |
| star_asia | 24 | `**GADDANI,` | FALSE POSITIVE - a yard/place name |
| xclusiv | 4 | `"taper"`, `"improved"`, `$95-$98/mt` | FALSE POSITIVE - quoted prose |
| **fearnleys** | **4** | `!"#\x05$%&'(\x14\x05(%)`, `>6*28!333$` | **REAL GLYPH CIPHER** |

**Cost avoided: 65 pages x 3 cr = 195 credits.**

## The real case, inspected

`fearnleys_2018_W29_fw_week_29_2018b` p2 is a **Fearnleys Weekly Report, 18 July 2018**
with dense Dry Bulk tables (Capesize 180d / Panamax / Supramax), an **LNG spot market**
table, a GAS section and a **1-Year T/C Dry Bulk chart**. Perfectly legible to a human;
only the text layer is ciphered.

Standing decision still applies: **fearnleys is SKIP for data** - the Hasura API already
ingests their output (563,000+ rows) and the user instructed this. These 3 PDFs are from
2018, three years before the live feed. **Recommendation: 12 credits at most, or skip.**

## IMPORTANT: the detector cannot be fixed by a threshold - and here is the proof

I tried to tighten `span_is_ciphered` and measured rather than assumed. Using 2,093
known-cipher banchero spans and 84 known-false-positive spans:

| rule | cipher kept | false positives kept |
|---|---|---|
| strong>=2 len>=6 (current) | 1869/2093 | **84** |
| strong>=3 len>=8 | 9/2093 | 0 |
| strong>=3 len>=10 | 0/2093 | 0 |
| strong>=4 len>=8 | 9/2093 | 0 |
| strong>=4 len>=10 | 0/2093 | 0 |

**No threshold separates them.** Every setting that eliminates the false positives also
destroys the cipher recall. The reason is that the cipher's punctuation is not unusually
dense - it is the same density as a quoted vessel name.

Per-page hit counts, measured with the DEPLOYED detector:

```
banchero    max  3 hits on a page    <- real cipher, few but LONG spans
fearnleys   max 11 hits on a page    <- real cipher
intermodal  max  2                   <- false positives
affinity    max  2                   <- false positives
agora       max  2                   <- false positives
xclusiv     max  1                   <- false positives
star_asia   max  0
```

A `>=4 hits` page threshold separates fearnleys from the false positives but would MISS
banchero (max 3). So it is not safe to deploy as-is either.

**The honest conclusion: span-level punctuation counting cannot reliably distinguish
glyph cipher from ordinary quoted text.** The only reliable discriminator found remains
the expensive one - render and look, which is what produced this document. Practical
policy going forward:

1. **Never auto-pay on a detector hit alone.** Triage by rendering (free) first.
2. **A hit is a prompt to look, not a verdict.** 65 of 69 hits this session were false.
3. **If a page must be auto-classified, require corroboration** - e.g. cipher hits AND
   the page's extractable alphabetic content falling below a threshold (a genuinely
   ciphered page has almost no real words). That is the test to build next, and it needs
   measurement, not a guessed constant.
