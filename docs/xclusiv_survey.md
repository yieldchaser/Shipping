# Xclusiv survey (source 4) - IN PROGRESS

266 PDFs. Rendered pages from every year and read them.

## Inventory / structure
  2021: 6 pages   2022: 7   2023: 7   2024: 9   2025: 9   2026: 9
Page count GROWS across years, so nothing may be pinned to a page number.

Page 1 : MARKET COMMENTARY (prose) + IN A NUTSHELL (bullets) + a Baltic Indices
         table: Week N / Week N-1 / +/-% plus 3-year AVERAGE columns.
Page 3 : Freight Market - Wet. The values are INSIDE PROSE SENTENCES:
             "VLCC: average T/C ended the week up by 5.1k/day at USD 219,233/day."
             "Suezmax: average T/C closed the week firmer by 10.8k/day at USD 117,640/day."
             "Products: the LR2 route (TC1) Middle East to Japan ... USD 153,488/day."
         plus 5 charts (VLCC/Suezmax/Aframax/MR TCE) drawn with Average/Min/Max
         reference lines.
Charts are VECTOR (pages 2,3,4,7,8 carry vector segments; page 8 also has one
large raster image).

## The value question, asked BEFORE building (the lesson from source 1)
Page 1's Baltic table (BDI/BCI/BPI/BSI/BHSI/BDTI/BCTI) DUPLICATES the series we
already hold in corpus/08-baltic and already display. The 3-year average columns
are derived from that same data. So page 1's table carries little unique value.
The unique payload is the PROSE T/C rates by route and vessel class, which is
what the extractor targets.

## Extraction approach: prose-anchored, not table-anchored
Unlike sources 1-3 there is no grid to assemble. The values are sentence-embedded,
so the pipeline splits text into sentences, takes the LAST "USD <n>/day" in each,
reads the change from "by <n>k/day", and pairs the subject from the text before
the first colon.

## MEASURED (2026-04-27 doc, verified against the rendered page)
  values recovered and matching the page:
     VLCC      219,233  (+5.1k)   OK
     Suezmax   117,640  (+10.8k)  OK
     Aframax   110,265  (+13.9k)  OK
     Products  153,488  (+4.4k)   OK   (LR2 route TC1)
  change values all match the page.

## OPEN PROBLEMS (do not declare this source done until fixed)
  1. Only 7 of 31 value sentences get a clean subject label. The majority come
     out subject=None. Values are right; labels are missing.
  2. A heading, 'IN A NUTSHELL', was accepted as a subject once. Headings and
     section titles must be excluded - this is the wrong-label failure mode, and
     a wrong label is worse than a missing one.
  3. 'MR Atlantic' (76,581) is not recovered; its sentence has a different shape
     and needs its own handling.
  4. A first run appeared to fail (VLCC/Suezmax/Aframax all MISS) purely because
     the script took the newest file while the eye-values came from the April
     document. Always point the control at the SAME document that was rendered.

## Fingerprint across all years (scratch/recon_source.py xclusiv)
  2021: 23 docs   2022: 51   2023: 50   2024: 51   2025: 51   2026: 40   (266)

  yr    pp  vec rast  E-dec E-thou US-thou   font sizes on the sampled doc
  2021   6   6   0      0      8    1114      4.9 5.0 5.3 6.0 6.3 6.4
  2022   7   5   0      1      6    1744      4.8 4.9 6.0 6.7 7.0 7.3
  2023   7   5   0      0     10    1744      4.8 4.9 6.0 6.6 6.7 7.0
  2024   9   4   1      0      4    1906      6.9 8.4 8.6 8.8 8.9 9.0
  2025   9   4   1      0      0    2036      6.8 6.9 8.2 8.4 8.6 8.8
  2026   9   5   1      0      7    2436      6.7 6.8 8.2 8.3 8.8 8.9

  NUMBER CONVENTION: ISO/US. US-thousands tokens run 1100-2400 per document
  while European thousands are 0-10 and European decimals 0-1. So do NOT reuse
  the advanced_shipping European parser.
  CHARTS: VECTOR on 4-6 pages per document (calibratable in principle). A raster
  page appears from 2024 onward as well.
  FONTS: the whole document is small (4.8-9.0pt), so any size-based discriminator
  must be derived from the page rather than hardcoded - the lesson from SSY,
  where a fixed 9.5pt threshold dropped an entire table.
  CAVEAT on the size column: the first entry is a spurious huge value (e.g.
  1114.9, 906.9, 2436.7) - a text artefact of that magnitude, not a real font.
  Treat it as a parsing artefact to investigate, not as a font size.
