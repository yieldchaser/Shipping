# Fearnleys (source 5) - SKIPPED, the PDFs are redundant

**Decision: do NOT extract the fearnleys PDFs.** The user flagged this and the
repository confirms it: we already ingest this publisher structurally, better
than the PDFs represent it.

## What we already hold (verified in the repo, not assumed)
```
scripts/fearnleys/daily_fearnleys_sync.py     - daily sync
scripts/fetch_fearnleys_comments.py           - ALL 11,713+ broker commentary notes
scripts/fetch_fearnleys_fixtures.py           - fixtures (549,479 rows)
scripts/fetch_fearnleys_tc.py                 - T/C rates
scripts/fetch_fearnleys_snp.py                - Sale & Purchase deal data
scripts/fetch_fearnpulse.py / fetch_fearnpulse_full.py
scripts/harvest_all_fearnleys.py
scripts/acquire/backfill_fearnleys_depth.py
scripts/acquire/audit_and_fix_fearnleys_labels.py
```

The commentary fetcher hits the publisher's own backend directly:
```
ENDPOINT = https://pbrokerapp.hasura.app/v1/graphql
query { comment { id date text created_at
                  metadata { comment_type comment_subtype comment_name } } }
-> data/derived/fearnleys_broker_comments.csv
```
with type/subtype/name metadata per note - fields a PDF cannot carry.

## Why the PDFs add nothing
The 2023-2026 PDFs are an HTML page PRINTED from the same Fearnpulse web app
(the footer literally carries the fearnpulse.com report URL with a date
parameter). So the PDF carries a strictly worse copy of what the Hasura harvest
already pulls in structured form: same source, same content, but as cards
instead of rows, with no metadata and no queryability. Extracting them would
duplicate existing data at higher cost.

The survey work was NOT wasted: it established that the two document eras are
(2021-22) 1-page prose posters and (2023-26) 19-page HTML prints, which is what
made the redundancy identifiable rather than merely suspected.

## Scope note
One known gap the user mentioned: S&P deal data has not updated for a couple of
days. That is a SYNC FAILURE in the fetch_fearnleys_snp.py pipeline, NOT
something the PDFs solve - fix the sync, do not re-extract the PDFs. If that gap
persists, investigate the SNP fetcher separately.

## Rule this establishes
Before building any publisher pipeline, check whether the data is ALREADY
INGESTED from that publisher. This source joins advanced_shipping's abandoned
prose table as the second case where checking first was worth more than
extracting. Look for a `fetch_*`/`daily_*` script for the publisher before
writing an extractor.
