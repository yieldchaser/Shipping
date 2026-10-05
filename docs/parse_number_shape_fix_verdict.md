# parse_number x1000 regression - shape-based fix

Generated: 2026-10-05 14:1x (hourly overnight supervisor)

## What was wrong
`scripts/process_knowledge.py::parse_number` applied a global x1000 rescale to
ANY dotted value in [5,100): `if "." in token and 5.0 <= val < 100.0: val *= 1000`.
Intended for OCR dot-instead-of-comma (9.750 -> 9750), but it also fired on
genuine 1-2 decimal prices. On the 2026-10-05 iron-ore md re-ingest this turned
30.43 -> 30430.0 and 13.21 -> 13210.0; the resulting md was reverted.

## Fix
Gate the rescale on SHAPE: only a dot followed by EXACTLY three digits (a
thousands-separator signature) is rescaled.

    if re.fullmatch(r"-?\d+\.\d{3}", token) and 5.0 <= val < 100.0:
        val *= 1000.0

File: scripts/process_knowledge.py (8 insertions, 5 deletions). py_compile OK.

## Measured (18 cases, actual function via AST-extracted source)
| input | output | input | output |
|---|---|---|---|
| 9.750 | 9750.0 | 30.43 | 30.43 |
| 60.000 | 60000.0 | 13.21 | 13.21 |
| 82.900 | 82900.0 | 8.7 | 8.7 |
| 8.700 | 8700.0 | 99.999 | 99999.0 |
| 1,234,567 | 1234567.0 | 4.999 | 4.999 |
| 2,026 | 2026.0 | 1.234 | 1.234 |
| 0,00 | 0.0 | 5.0 | 5.0 |
| 1240 | 1240.0 | 100.0 | 100.0 |
| -17 | -17.0 | 1027 | 1027.0 |

FAILURES 0. The two values the regression corrupted (30.43, 13.21) are now left
untouched; every intended OCR case (3-decimal thousands signature) still scales.

## Scope check
Only scripts/process_knowledge.py::parse_number carried the [5,100) x1000 rule.
The per-source parse_number copies (build_views.py, extract/publishers/
advanced_shipping.py, run_star_asia.py, star_asia.py) do NOT contain it - not
touched, per the ONE-SOURCE-AT-A-TIME doctrine.

## NOT done (deliberate)
No iron-ore md re-ingest. The code fix is inert until regeneration; re-ingesting
was the operation that caused the regression and needs the same validated pass,
so it is left for a controlled run. Changes left UNCOMMITTED (never touch main).
