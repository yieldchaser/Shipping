# intermodal macro - kerned-label recall defect FIXED (+15 rows)

*Run: 2026-10-03 (source-by-source, unattended). Writer: scripts/extract/publishers/run_intermodal_finance.py*

## The defect

The macro parser (`parse_finance_page`) matched indicator rows against a hardcoded
20-label allowlist by **exact string equality** (`IND_CAT.get(lab)`). Intermodal's own
text layer kernels one label apart in one era:

```
2023 W21-W36 finance page text-layer lines:
  74: 'Dow J ones '     <-- split by kerning, and with a TRAILING SPACE
  75: '33,093.34' 76: '32,764.65' 77: '32,799.92' 78: '33,055.51' 79: '33,286.58' 80: '-1.0%'
```

`'Dow J ones ' != 'Dow Jones'`, so the row was silently dropped. This is the same
class as the currency-allowlist bug fixed in the 09:xx run: a hardcoded label list
against a publisher whose text layer varies.

Measured: `intermodal_macro_series.csv` held **239** Dow Jones rows against **254**
documents. The **15** missing documents are exactly `intermodal_2023_W21..W36`
(the W32 file is absent from the corpus).

## The fix

Label keys are now **whitespace-insensitive** (`re.sub(r"\s+","",s).lower()`), and the
row is stored under the **canonical** label, not the kerned form:

```python
def _nkey(s): return re.sub(r"\s+","",s).lower()
IND_CAT = {_nkey(k): (k, v) for k, v in INDICATORS}
...
hit = IND_CAT.get(_nkey(lab))
if hit is None: continue
lab, cat = hit   # canonical label
```

## Measured result

Re-ran the writer over 255 canonical reports (2 byte-identical duplicates skipped: the
`_broker_s_insi` W38/W39 second-collection-route copies, whose data is already held via
`intermodal_2026_W38/W39`).

| series | before | after | delta |
|---|---|---|---|
| `intermodal_macro_series.csv` | 4,803 | **4,818** | **+15** |
| `intermodal_maritime_stocks_series.csv` | 3,152 | 3,152 | 0 |
| `intermodal_bunkers_series.csv` | 2,287 | 2,287 | 0 |

Dow Jones rows: **239 -> 254**.

**Control (byte-identical):** maritime_stocks md5 `4bdc56eaf98f988f1d788acc02a86346`,
bunkers md5 `b048156b6008a36229a30e2b5da505a3` - both UNCHANGED pre/post.

**Lossless check:** set-diff on `(source_file, indicator, issue_date, report_week)`:
**added 15, removed 0**, all 15 added are `Dow Jones`; **common-key row diffs = 0**
(no existing value moved).

**Content verification (eye-substitute per skill: no vision tool in this session):**
every one of the 15 added rows re-read against its source PDF page text - the label
line followed by the printed 5-value series and W-O-W `Change %`:
**15/15 = 100% verbatim** on latest_value, prior_value AND wow_change_pct.
Sample `intermodal_2023_W21`: page `Dow J ones / 33,093.34 ... -1.0%` matches the row.

## Disclosed residuals (measured, NOT fixed this run)

- The other intermodal series (currencies, sales, TC rates, newbuilding*, indicative,
  demolition*, tanker_spot) have **not** had this per-page label reconciliation. Only
  macro had a hardcoded allowlist that a text-layer split could defeat; the rest were
  checked for the `Nasdaq` false-positive class and show no analogous gap in the
  finance page, but a full row-count audit per series is still owed.
- `Yuan / $` and `Won / $` show 252 rows vs 254 docs; the 2 gaps are the same
  `_broker_s_insi` duplicate copies (data held), not a parser defect.
