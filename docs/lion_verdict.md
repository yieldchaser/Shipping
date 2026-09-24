# lion (Lion Shipbrokers) - extraction verdict

Source 9 of the broker set, and the last broker source. Pipeline:
`scripts/extract/publishers/run_lion.py` (self-contained: PDF -> text -> parse ->
parquet + summary + per-issue markdown). Survey: `docs/lion_survey.md`.

**Status: COMPLETE and verified.** 43 of 44 issues yield data; the 44th is not a
Lion weekly (see below). Three real defects were found by verification, fixed, and
the fix re-verified by content.

## 1. What the source holds

| fact | measured |
|---|---|
| documents | 44 (`corpus/01-brokers/lion/`) |
| issues parsed | **43**; 1 skipped |
| pages/issue | 2-4 (the skipped 2024 file is 20 pages) |
| skipped | `lion_2024_W31_Market-report-Week-31` - a **star-asia reprint** filed under the Lion dir: page 3 is headed "Shipbroking (www.star-asia.com.sg)" and carries a tabular S&P list. It has no DEMOMETER and no REPRESENTATIVE SALES section. star_asia is already extracted (193/193), so this is a RESTATEMENT and is correctly skipped. |
| numbers | ISO; European comma-decimals appear only in rare tokens ("$ 6,75 mill" = 6.75). Both forms are handled and both are verified below. |

Two deliverables per issue:

1. **LION'S DEMOMETER (USD $/LT)** - a real printed table: 4 countries
   (TURKEY, PAKISTAN, INDIA, BANGLADESH) x 3 vessel types (BULKER, TANKER,
   CONT/TWEEN) + a trend word. 12 cells per issue.
2. **REPRESENTATIVE SALES** - borderless deal narratives, one vessel per record,
   split BULKERS / TANKERS / CONTAINER-MPP-TWEEN / DEMOLITION.

Deliberately NOT extracted: the Baltic index block at the top of page 0
(BDI/BCI/BPI/BSI/BHSI with a daily change). That is a RESTATEMENT of a public
index already held in `data/indices/bdiy_historical.csv` (10,522 rows).

## 2. Deliverables (measured)

| artefact | size |
|---|---|
| `data/extracted/lion_demometer.parquet` | **516 rows** x 11 cols, 43 weeks, 2025-10-03 -> 2026-09-04, 4 countries x 3 vessel types x 43 weeks |
| `data/extracted/lion_deals.parquet` | **1,145 rows** x 38 cols across 43 issues; 1,117 distinct vessels |
| `data/extracted/lion_summary.json` | per-country/type stats + policies + example rows |
| `data/extracted/md/lion/*.md` | **43** per-issue files (demometer table + deal table + narratives) |

Demometer shape: 221 ranges (both bounds kept), 294 singles, 1 dash cell
(`-` in 2025 W41 Pakistan CONT/TWEEN, stored null with `value_kind='dash'`).
Deal shape: 1,042 sold, 93 demolition, 10 price-only; 89.3% carry a price;
44.4% a named buyer.

## 3. Three defects found by verification, then fixed (v3)

The Sep-22 extraction was correct in shape but wrong in **38 of 1,145 rows** on
en-bloc pricing. All three families were found by reading the sentences against
the assigned values, then confirmed on the rendered page. The other 1,107 rows
were untouched by the fix.

**A. The group total was kept as one vessel's own price (31 rows).**
The code's own docstring says a group total leaves the per-vessel price null, but
the loop nulled only the *members*, never the *carrier* row. So the carrier
reported the whole group's money as its own sale price:

| issue | vessel | v2 (wrong) | truth |
|---|---|---|---|
| 2026 W02 | NORDIC LUNA | 50.0 | **25 each** - the publisher's own W07 commentary says "NORDIC LUNA & NORDIC SPRINTER ... for $25 mill each", while the W02 en-bloc line says "$50 mill" for the pair |
| 2026 W03 | FRONT FORTH | 831.5 | a **total for 8 VLCCs** |
| 2026 W03 | AEGEAN | 530.0 | a total for 6 VLCCs |
| 2026 W03 | QIDONG XIANGYU XYQD-028 | 196.6 | a total for 6 newbuildings |
| 2026 W01 | DHT EUROPE | 101.6 | a total for 2 VLCCs |

Discriminator used: a price that appears **after** the "en bloc" phrase in the
row's own text came from the sentence (a group amount); a price that appears
**before** it is the vessel's own spec-line price and is kept. That is what keeps
2026 W22 VS SPIRIT at its correct $14 mill (its line reads "- $ 14 mill. Sold en
bloc for $ 25 mill", where 11 + 14 = 25 - the sentence restates the pair's sum).

**B. The "respectively" form silently lost a price (2 rows).**
2025 W40: "C/V OOCL DURBAN ... - sold en bloc for $75.7 mill & $79.3 mill
respectively to clients of ONE (Ocean Network Express)". The pair is OOCL BRAZIL
(last line of page 0) + OOCL DURBAN (first line of page 1). v2 kept 75.7 on
DURBAN and **dropped 79.3 entirely**. Which amount belongs to which ship is
decided by "respectively" against a listing order that crosses a page break, so
under the standing rule (never assign by position; a wrong value is worse than a
missing one) both per-vessel prices are now null and **both amounts are recorded
in the note** so nothing is lost.

**C. A parenthetical per-vessel price was ignored, copying the TOTAL to every
ship (5 rows).**

| issue | sentence | v2 | truth |
|---|---|---|---|
| 2025 W42 | "en bloc for region $52.5 mill ($17.5 mill each)" | 52.5 to all 3 | **17.5 each**, 52.5 is the trio total (a 3x overstatement) |
| 2025 W42 | "en bloc to U.A.E buyers for region $43 mill ... ($21.5 mill each)" | 43 to both | **21.5 each** (2x) |

After the fix the maximum `price_usd_m` in the corpus falls from 831.5 to 170.0 -
a group total can no longer masquerade as a sale price.

## 4. Verification (all measured, none estimated)

No image/vision tool was available in this session, so per the standing rule the
visual check was replaced by the strongest available substitutes - full
reconciliation plus a pixel-ink test - and that limitation is stated plainly.

| check | result |
|---|---|
| **Recall, demometer** - every number printed in each issue's demometer block must be accounted for | **736 printed numbers, 0 mismatches.** Closure is exact: 221 ranges x 2 + 294 singles + 1 dash = 736. Nothing printed is missed and nothing is invented. |
| **Traceability, demometer** - every stored value found in the PDF's own demometer block (read from the PDF, not the text cache) | 516 rows, **0 untraceable** |
| **Traceability, deals** - every price amount found in its own issue's PDF text | 1,023 values, **0 not found** |
| **Vessel names** | 1,145 rows, **0 missing** from their issue |
| **Render + pixel ink test** (substitute for a look) | W36 page 0 rendered at 115 dpi; page mean brightness 242.7; **17 of 17** numeric tokens in the demometer band sit on ink (mean 176-203) at their printed coordinates |
| **Control** - the .md, the parquet and the render all point at the same document | W36 md shows TURKEY 280/290/300, PAKISTAN 510/520/530-535, INDIA 440-450/460-470/500-510, BANGLADESH 490-500/515-525/540 - identical to the page dump |
| **Reproducibility** - the text cache was regenerated from the PDFs and the parse compared | generator recovered exactly: `get_text(sort=True)` per page, PAGEBREAK-joined, footer lines dropped, per-line whitespace collapsed - matches the original cache on **43/44** docs (the exception is the skipped 2024 digest). Parse from regenerated text: **1,145 deal rows identical**; demometer identical apart from trailing whitespace in the debug-only `trend_raw` field, which is not in the parquet. |
| **European comma-decimals** | 12 price values that my first check called "not in the PDF" were the publisher's comma form ("$ 6,75 mill"). With the comma form included: **0 not found**. The extractor was right; the checker was wrong. |

The one number the v2 verifier still flags (`buyer strings not traceable: 41`) is
a **verifier limitation, not a defect**: those rows are en-bloc groups whose buyer
is printed once in a group line ("Sold en bloc for region $196.6 mill to Chinese
buyers (clients of Seacon Shipping Group)") and propagated to each member. All 41
were re-checked against the full issue text: **41 of 41 are present**.

## 5. Baseline test - is it already ours? (three baselines)

| baseline | finding | verdict |
|---|---|---|
| **1. feeds** | `data/derived/scrappage_prices.csv` holds country demolition rates (dry/tanker/container, India/Bangladesh/Pakistan/Turkey) from **Hellenic GMS reports**, 380 rows 2021-07 -> 2026-09. Nearest-week comparison against Lion's demometer (Bangladesh bulker): 43 pairs, mean diff -8.2, median abs diff 10.0, range -40..+20 (Lion 395-495 vs feed 385-470). | The demometer is a **RESTATEMENT** of the same market from a second house, not new information. Lion adds Turkey tanker + Turkey cont/tween, which the feed lacks. |
| **2. our own extraction** | Lion's deal tape: 1,117 distinct vessels. banchero_costa holds 2,920 deal vessels, overlap **92** (8.2%). fearnleys fixtures overlap **764** by name, but every fearnleys department is a **charter** fixture (BULK / TANKPRO / TANK / LNG / LPG / RoRo) - there is no S&P department, so a shared name is not a shared sale. | **~1,025 of Lion's 1,117 sale vessels are not in any other broker's sale tape.** |
| **3. what the app displays** | `index.html` renders a scrappage chart from `data/derived/scrappage_prices.csv` (country x dry/tanker $/LDT) plus a static "Global Ship Demolition & Scrap Matrix". | Country-level demolition rates are **already displayed** - from the GMS feed. |

**Verdict: the demometer is REVIEW-only; the deal tape is CONSTRUCT-worthy.**
Lion's own recorded S&P transactions are the part no other source holds and they
repeat weekly - the demometer's marginal value is a second opinion on numbers the
app already shows.

## 6. Known limitations (stated, not hidden)

* **The typed deal layer is best-effort; the markdown is the primary deliverable.**
  84.3% of rows carry a `price_usd_m`, 7.9% a `price_per_lt`, 44.4% a named buyer.
  A price that cannot be read is left NULL - never guessed.
* **En-bloc groups with no per-vessel price** now carry the group total in
  `en_bloc_group_price_usd_m` + `en_bloc_group_size` and NULL per-vessel price.
  Downstream code must not read a NULL price as "unsold".
* **The "respectively" pair (OOCL DURBAN/BRAZIL, 2025 W40)** is deliberately left
  with both per-vessel prices NULL; both amounts are in `notes`. Do not
  "recover" them by position.
* **Coverage starts 2025-10-03.** The 2024 issue is a star-asia reprint and the
  earlier 2024 Lion weeklies are not in the corpus, so no 2024 demometer exists.
* **The demometer's `price_point` is the midpoint of a range.** Where Lion prints
  a range (221 of 516 cells) the midpoint is a derived number, not a print.
* `data/extracted/` is gitignored, so the parquet/md are local artefacts: the
  runner regenerates them from the PDFs in one command.
* **No vision tool was available this session.** The rendered PNG
  (`scratch/lion/render_W36_p0.png`) was produced and ink-tested, but not read by
  eye. A human glance at one demometer and one deal page is still worth doing.

## 7. Reproduce

```
export PATH="/c/Users/Dell/AppData/Local/Programs/Python/Python314:$PATH"
python scripts/extract/publishers/run_lion.py            # uses the text cache
python scripts/extract/publishers/run_lion.py --rebuild-txt   # re-renders text from the PDFs
```
