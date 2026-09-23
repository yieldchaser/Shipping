# Star Asia (source 2) - COMPLETE and VERIFIED

193/193 documents, 0 failures. Output: data/extracted/md/star_asia/
  .md 193 / .tables.json 193 / .charts.json 193

## Verified numbers
  tables               : 3,640
  docs with >=1 table  : 191/193
  markdown total       : 5.7 MB, smallest 5,132 bytes, 0 files under 1.5 KB
  prose cells remaining: 31        (advanced_shipping: 119 TABLES carried prose)
  Baltic-labelled rows : 1,105
  spot-check on 2026 W19: JENNY LUCKY, GAS CRUSADER, DELIVERED GADANI, 7,176
                          all present, matching the rendered page read by eye

## What worked
Built fresh from measured facts (docs/star_asia_survey.md) rather than cloned,
because the two publishers have opposite conventions - ISO numbers (29,580 =
29580) vs European (60.000 = 60000), and raster vs vector charts. Reusing
either specialisation would have produced wrong values.

drop_prose_rows() removed narrative rows before they reached the typed layer.
That is why only 31 prose cells remain here versus a corpus-wide problem on
source 1: Star Asia's prose sits in its own rows rather than fused into the
numeric grid.

## CORRECTION about the overnight cron job
I reported earlier that the overnight cron job "runs but does not work" because
its delivery was the prompt echoed back with API calls: 0. That was WRONG. The
job DID do the work - it processed all 193 documents between 01:24 and 01:58,
and its output directory contains a .pages.json artifact this pipeline does not
produce, so it built its own runner. Judging a job by its delivery message
alone was the same mistake as judging a fix by one document: a single signal
treated as proof.

## Status
Source 1 (advanced_shipping): complete. Source 2 (star_asia): complete.
Next: pick source 3 and repeat the method.
