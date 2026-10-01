# The hellenic iron-ore publisher runner was a SyntaxError in HEAD

## How it was found

A **repo-wide Python 3.11 compile sweep** over every tracked `scripts/**/*.py`
(the interpreter the GitHub Actions runner uses; a PEP-701 f-string backslash had
already killed one publisher for three weeks, see
`docs/poten_collection_outage_verdict.md`). The sweep is the cheap detector: it
reports 0 failures now and reported this one immediately.

    scripts/extract/publishers/run_hellenic_iron_ore_pdf.py
    IndentationError: expected an indented block after 'if' statement on line 2232

Not version-specific - it fails on **3.11 and 3.14 alike**, so the module could
not be imported or run at all.

## The defect

Commit `6c01a5ce7` (*feat(smm-iron-ore): implement end-to-end 1-page SMM Iron Ore
Daily extraction pipeline*) inserted the new single-page SMM early-branch into
`process_single_mmi_sync()` **at the wrong indentation and on top of the
`if`-body**, deleting both the body and the `try/except` that closed it:

```diff
                 and len(sidecar.get("multi_period_averages", [])) >= 2
             ):
-                return {"status": "skipped", "name": pdf_path.name, "issue_date": issue_date}
-        except Exception:
-            pass
+    # Check if single-page SMM format
+    try:
+        doc = pymupdf.open(str(pdf_path))
```

The `if (...):` was left with no statement, which is the IndentationError.

## The fix (4 lines restored, the new feature kept)

The SMM branch stays where the commit wanted it - an early branch at function
level - and the clobbered `return`/`except`/`pass` are restored inside the
`if not force ...` try block, i.e. HEAD~ behaviour exactly:

```diff
             ):
+                return {"status": "skipped", "name": pdf_path.name, "issue_date": issue_date}
+        except Exception:
+            pass
+
     # Check if single-page SMM format
     try:
         doc = pymupdf.open(str(pdf_path))
```

`git diff` = 4 added lines, 0 removed. Nothing else in the function changed.

## Controls

| control | measured |
|---|---|
| `py_compile` under the runner's interpreter | **3.11 OK** (was `IndentationError`) |
| `py_compile` under 3.14 | OK |
| repo-wide 3.11 sweep over tracked `scripts/**/*.py` | **359 compiled / 0 failed** (was 358 / 1) |
| repo-wide 3.14 sweep | **359 / 0 failed** |
| blast radius | the only importers are `scratch/test_extract_samples.py` and `scratch/test_parse_samples.py` (both gitignored); no workflow or tracked module imports it, so this broke the runner, not a scheduled job |
| diff shape | exactly the 4 lines the SMM commit removed, re-inserted; the SMM early-branch is untouched |
