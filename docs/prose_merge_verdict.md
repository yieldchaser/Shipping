# Verdict: the prose-merged table defect is NOT worth fixing

Measured 2026-09-24 after a 4.2-hour re-run (249/249 docs, 0 failures).

## The defect
In 2023-2026 Advanced Shipping files, narrative text fuses with the Baltic index
panel into one grid. 119 tables / 103 docs (41%) carry prose cells.

## Why it is not worth fixing
The only content in the fused region is:
  * Baltic indices  BDI/BCI/BPI/BSI/BHSI/BDTI/BCTI
  * chart axis tick runs

Both are ALREADY HELD AND ALREADY DISPLAYED:
  * index.html mentions BDI 111, BCI 25, BPI 14, BSI 11, BHSI 6, BDTI 29, BCTI 20
    and makes 6 baltic feed fetches
  * corpus/08-baltic holds 3,038 files covering 2015-2026
So extracting them again yields nothing new.

The DEAL data in the same documents (vessel, dwt, year, price, buyer) extracts
CLEANLY - ['Capesize','HL Passion','179.656','2015'] - so no unique data is lost
to the fusion. The defect is cosmetic.

## The attempted fix, and why it failed
fix_prose_tables() replaced a polluted table only when a liteparse block shared
>=2 of its values. That guard never fired for these tables because liteparse
fuses the prose too, or does not see them as tables at all. Corpus-level prose
count was IDENTICAL before and after (119 tables / 103 docs), and the one
document I "verified" it on had been cleaned by the earlier LABEL fix, not by
this change. That was a false attribution - testing one document without a
control, then launching a 4.2-hour run on the result.

## What DID work and is verified
  * Daily T/C labels   : 249/249 (100%)
  * BDTI / BCTI labels : 90% / 86%  (were ~0%)
  * full BDI..BHSI     : 226/249 (91%)
  * values, charts, European number handling: verified against rendered pages

## Decision
Source 1 (advanced_shipping) is functionally complete. Move to source 2.
Do not spend further time on prose fusion.
