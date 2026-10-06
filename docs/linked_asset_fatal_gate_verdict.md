# Restoring the linked-asset fatal gate (mapping-aware) - 2026-10-06

**Headline:** the CI `Validate knowledge artifacts` gate that counts UNRESOLVED
REQUIRED LOCAL linked assets had been **dead** since `8de08da48` (the variable was
initialised, returned, and summed into the exit code but never populated - line 1114
printed 0 unconditionally). This run **restores it mapping-aware and verifies it on the
committed manifest**, so a genuine future mirroring gap fails CI again while the 59
permanently-unfetchable breakwave assets do not.

## The mechanism (proven from git)

`8de08da48` replaced, inside `validate_linked_asset_coverage()`:

```python
if not local_target.exists() or not local_target.is_file():
    if enforce_required_local_links:
        unresolved_required_local.add(f"{source_path} -> {Path(clean_ref).as_posix()}")
    else:
        external_non_mirrored.add(f"{source_path} -> {normalized_ref}")
```

with a single `external_non_mirrored.add(...)`. `enforce_required_local_links = mirrored > 0`.
`unresolved_required_local` is still summed into `failures` (line ~1173), so restoring the
`.add()` alone reactivates the gate.

## Measured population (committed manifest, `knowledge/manifests/documents.jsonl`, 11,329 rows)

Replaying the removed branch (`scratch/linked_gate_probe2.py`, read-only):

| measure | value |
|---|---|
| rows checked (linked-asset sources, `.html`, exists) | 8,671 |
| **would-be-fatal** | **59** |
| by source | `breakwave_insights` **59 / 59** |
| distinct ref dir | `../pdfs` (59) |
| source dirs | `reports/breakwave/{2022:2, 2023:17, 2024:32, 2025:8}` |

Every one resolves to `reports/breakwave/pdfs/<name>.pdf`, i.e. a publisher-hosted
commodity-call PDF that was never mirrored: the fetch hit an ANZ Portal login wall and
saved a **5,174-byte `Login Page` HTML under a `.pdf` name**
(`docs/breakwave_pdf_mirror_verdict.md`). They are **EXTERNAL_UNAVAILABLE**, not a path
bug; the correct treatment is the non-fatal `external_non_mirrored` class.

## The fix

`EXTERNAL_UNAVAILABLE_LINKED_PREFIXES = ("reports/breakwave/pdfs/",)` plus the restored
branch, which now adds to `unresolved_required_local` iff the resolved target's repo-relative
path does **not** start with an exempt prefix. `external_non_mirrored` still records every
unresolved ref (unchanged warning list).

## Verification (before/after, with controls)

`scratch/verify_linked_gate.py` invokes the validator's OWN function:

| case | unresolved_required_local | external_non_mirrored |
|---|---|---|
| REAL committed manifest | **0** | 11,527 |
| CONTROL: synthetic hellenic ref `-> ../assets/<missing>.png` | **1** (caught) | 1 |
| CONTROL: synthetic breakwave ref `-> ../pdfs/wall.pdf` under `reports/breakwave/` | **0** (exempt) | 1 |

Before the patch the same real manifest also gave 0 (the gate was dead); after the patch it
still gives **0, so CI cannot regress today**, and the control proves a genuine missing
required asset is once again fatal. `py_compile` OK.

## Honest limits

* The exemption is a measured allowlist by path prefix, not a structural detector - the
  auth-wall is not observable at validate time. A *future* breakwave insight whose PDF is
  also auth-walled will land in the exempt class automatically (correct); a future breakwave
  PDF that genuinely should have mirrored but did not will also be exempt (a known,
  accepted blind spot for this one publisher).
* The local end-to-end validator (31 min, prints a different metric set) was NOT run; the
  targeted function-level check with two controls is the test used here.
* Change is committed on the current feature branch, not `main`.
