# The poten knowledge tier has NO source root: the 2026-09-23 corpus migration left `process_knowledge.py` pointing at a deleted directory

**Date:** 2026-10-01 (cron, unattended) · Read-only diagnosis, no data changed.
**Found by auditing knowledge-tier rebuildability, not by being handed the item.**

## 1. The measured defect (proved by running the builder's own function)

`scripts/process_knowledge.py` reads its poten source from `REPORTS_ROOT / "poten"`
(`REPORTS_ROOT = REPO_ROOT / "reports"`; the path is used in three places: `build_sources_registry`
line ~1312, the `paths` payload line ~1344, and `iter_source_files` line ~1377).
**`reports/poten` no longer exists** - commit `b20829464` (2026-09-23, *refactor(corpus): migrate
Poten, Signal and Baltic archives*) renamed every file to `corpus/04-poten`; `git ls-files
reports/poten` = **0**.

Measured by importing the module and calling the builder's own iterator (control included):

```
REPORTS_ROOT exists: True
poten dir exists : False
baltic dir exists: True
iter_source_files('poten')  -> 0     <-- no poten doc can ever be (re)built
iter_source_files('baltic') -> 187   <-- control: the function works
GROUP_ROOTS['poten']        -> C:\Users\Dell\Github\Shipping\corpus\04-poten   (already canonical)
```

So the poten RAG tier **cannot be refreshed**: a new poten issue can be collected, extracted and
placed in the corpus and it will still never enter `knowledge/`. This is why the poten
`SyntaxError` repair (commit `48b45e9f6`, on main) is necessary but **not sufficient** - the runner
can now import and fetch, but the knowledge step still has no source to read.

## 2. What the frozen tier actually contains

`knowledge/manifests/documents.jsonl` (10,202 rows) holds **1,096 poten rows**, and **all 1,096
`source_path`s point under `reports/poten/`** - i.e. at files that no longer exist. Their shape:
**937 are the thin metadata md** (`date: "unknown-01-01"` / `YYYY-01-01`) and 159 are dated;
**545 rows carry `date: null`**. The tier's `/poten` `sources.json` entry still claims
`counts.poten.tankers = 1096` with `paths.poten.tankers = "reports/poten"` although the current
`build_sources_registry()` would count 0 there.

The user-visible symptom already on record is the phantom document
`knowledge/chunks/poten_tankers_2030.jsonl` (2 chunks, `Published Date: 2030-01-01`), served to
the app's RAG off a mis-dated stub.

## 3. Not a defect: the corpus holds two md generations by design (checked, do not "fix")

A first reading made `corpus/04-poten` look like a duplicated corpus. It is not - it reconciles
exactly, and the mirror is deliberate. Measured census
(`data/extracted/audit/poten_corpus_md_census.json`, `scratch/poten_kb_census.py`):

| measure | value |
|---|---|
| corpus/04-poten md (excl. `pdfs/`) | **2,183** |
| of which metadata md (frontmatter has `pdf_file:`) | **1,096** |
| ... of those, stub-shaped (`date: unknown-01-01` / `YYYY-01-01`) | 937 |
| ... of those, dated | 159 |
| non-metadata md, **byte-identical** to a file in `data/extracted/md/poten/` | **1,087** |
| non-metadata md unexplained | **0** |
| extraction tier `data/extracted/md/poten` | 1,087 |
| 2,183 - 1,087 = the migration's own md count for `reports/poten` | **1,096** ✓ |

The 1,087 byte-identical copies are written on purpose: `run_poten_clean.py` syncs every extracted
opinion to BOTH `data/extracted/md/poten/<year>/` and `corpus/04-poten/<year>/`
(docstring step 5, code at its "2. Sync to corpus/04-poten/<year>/" branch). **No file is
redundant and nothing should be deleted.** (A 937-file "duplicate stub" hypothesis was falsified
here before any deletion was attempted.)

## 4. The pruning question - measured, NOT reproducible, do not act

Simulating `prune_missing_sources()` over the current manifest removes **8,999 of 10,202 rows**,
including all 1,096 poten rows, because their `source_path` does not exist on disk. **Yet eight
days of nightly `knowledge: update` commits since the migration removed none of them** (the
2026-09-29 knowledge commit touched documents.jsonl by **+4 rows, -0**), and `HEAD`'s copy equals
the working tree's. So the code path that *should* have pruned them did not fire, and the reason
is **not established** here. Reported as *not reproducible*, not as a live hazard.

## 5. The fix - APPLIED ON THE BRANCH, with a content-preserving control

`GROUP_ROOTS["poten"]` already resolves to `corpus/04-poten` (`scripts/source_archive_utils_v2.py`),
so the canonical location is defined in exactly one place - `iter_source_files` and
`build_sources_registry` simply never adopted it for poten (they do for `broker_reports`, which
reads `GROUP_ROOTS["brokers"]`).

Applying it is a **two-part** change, which is why it is not done blind in an unattended run:
1. repoint the three poten reads from `REPORTS_ROOT / "poten"` to `GROUP_ROOTS["poten"]`;
2. because `corpus/04-poten` now holds BOTH the 1,096 metadata md and the 1,087 mirrored
   extractions, the read must select ONE generation (the `pdf_file:` metadata set, matching what
   the current tier holds, or the full-text extraction set) - reading the whole directory would
   inject 1,087 duplicate documents into the RAG.

Same class, adjacent: `iter_source_files('baltic')` yields only **187** files while the tier holds
2,036 baltic rows, so the tier and the current source roots have drifted apart generally, not only
for poten. Out of scope here.


**APPLIED (branch `auto/extract-fixes-2026-10-01-poten-kb-source`, `main` untouched):**
`is_poten_metadata_md()` added; the three poten reads (`build_sources_registry` count, the
`paths` payload, `iter_source_files`) now use `GROUP_ROOTS["poten"]`. `scripts/process_knowledge.py`
= 28 insertions / 4 deletions.

**CONTROLS (measured, function-level, pre-patch copy kept at `scratch/process_knowledge.py.prepatch`):**

| source | `iter_source_files` before | after |
|---|---|---|
| poten | **0** | **1,096** |
| baltic | 187 | 187 |
| breakwave_insights | 505 | 505 |
| hellenic | 514 | 514 |
| broker_reports | 180 | 180 |
| breakwave / books | 0 | 0 |

* `py_compile` passes on **3.11** (the Actions runner) and **3.14** (this box).
* **The source set is byte-for-byte the tier's own**: the 1,096 basenames yielded are an EXACT
  match for the 1,096 poten `source_path` basenames already in `documents.jsonl` - 0 in the tier
  are missing from the new yield and 0 new files are added; **0** of the 1,087 mirrored extraction
  md are yielded. So the poten tier becomes rebuildable from the migrated corpus and rebuilds to
  the SAME documents it has always served.
* The tier was NOT rebuilt here - no data was changed. The next `process_knowledge.py` run (or
  `--source poten`) may refresh it. Whether the RAG should keep the thin metadata md or move to the
  full-text extractions in `data/extracted/md/poten/` is a content decision for the user, not a
  migration detail.

## 6. Reproduce

```bash
python3 scratch/poten_kb_census.py       # the corpus md census (section 3)
python3 scratch/poten_cross_tier.py      # corpus vs extraction-tier byte comparison
python3 scratch/poten_dup_pair.py        # the falsified duplicate-stub hypothesis
python3 -c "import sys; sys.path.insert(0,'scripts'); import process_knowledge as pk; \
print(len(list(pk.iter_source_files('poten'))), len(list(pk.iter_source_files('baltic'))))"
```
