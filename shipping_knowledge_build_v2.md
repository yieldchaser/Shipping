# Shipping Intelligence — Knowledge System Build

## Your Environment
- Repo: `C:\Users\Dell\Github\Shipping`
- Agent: Codex
- Gemini API Key: `AIzaSyCIXEZtsD86VZAy74OKNxgSfd7MDJ3EDL8`
- Python: 3.11 (confirmed in status bar)

## Your Mission
Build a world-class, fully incremental, source-extensible shipping intelligence knowledge base.
Do this completely and autonomously — create every file, install every dependency, run the
processor locally, validate the output, set up GitHub Actions, and commit everything to the repo.

**Do NOT touch:** `index.html`, any existing CSV files, any existing scripts in `scripts/`.
**Do NOT modify:** `reports/` directory contents.

---

## Confirmed Source Layout (already on disk)

```
reports/
  drybulk/
    2018/ … 2026/         ← YYYY-MM-DD_Breakwave_Dry_Bulk.pdf  (~280 KB each)
  tankers/
    2023/ … 2026/         ← YYYY-MM-DD_Breakwave_Tankers.pdf   (~280 KB each)
  baltic/
    dry/{year}/           ← YYYY-MM-DD_WNN_{slug}_dry.html
    tanker/{year}/        ← YYYY-MM-DD_WNN_{slug}_tanker.html
    gas/{year}/           ← YYYY-MM-DD_WNN_{slug}_gas.html
    container/{year}/     ← YYYY-MM-DD_WNN_{slug}_container.html
    ningbo/{year}/        ← YYYY-MM-DD_{slug}_ningbo.html
  *.pdf                   ← 12 shipping reference books (flat in reports/ root)
```

---

## Target Knowledge Layout (create this from scratch)

```
knowledge/
  docs/
    breakwave/drybulk/YYYY/YYYY-MM-DD.md
    breakwave/tankers/YYYY/YYYY-MM-DD.md
    baltic/dry/YYYY/YYYY-MM-DD.md
    baltic/tanker/YYYY/YYYY-MM-DD.md
    baltic/gas/YYYY/YYYY-MM-DD.md
    baltic/container/YYYY/YYYY-MM-DD.md
    baltic/ningbo/YYYY/YYYY-MM-DD.md
    books/{sanitised_title}.md
  chunks/
    breakwave_drybulk.jsonl
    breakwave_tankers.jsonl
    baltic_dry.jsonl
    baltic_tanker.jsonl
    baltic_gas.jsonl
    baltic_container.jsonl
    baltic_ningbo.jsonl
    books.jsonl
  manifests/
    documents.jsonl
    sources.json
    errors.jsonl
  derived/
    signals.jsonl
    themes.jsonl
    timelines.json
  CLAUDE.md
```

---

## Step 1 — Environment Setup

Create `.env` in repo root:
```
GEMINI_API_KEY=AIzaSyCIXEZtsD86VZAy74OKNxgSfd7MDJ3EDL8
```

Ensure `.gitignore` contains `.env` — add it if missing.

Create `requirements_knowledge.txt` in repo root:
```
pdfplumber>=0.10.0
beautifulsoup4>=4.12.0
lxml>=5.0.0
google-generativeai>=0.5.0
tiktoken>=0.6.0
python-frontmatter>=1.1.0
python-dotenv>=1.0.0
```

Run: `pip install -r requirements_knowledge.txt`

---

## Step 2 — Create `knowledge/CLAUDE.md`

This is the shared schema contract. Write it with exactly this content:

```markdown
# Shipping Intelligence Knowledge Base — Schema & Query Contract

## Purpose
Unified corpus of Breakwave Advisors bi-weekly reports (dry bulk + tankers),
Baltic Exchange weekly roundups (dry, tanker, gas, container, ningbo), and
shipping reference books — for market intelligence, historical context, and Q&A.

## Document Schema (frontmatter in every knowledge/docs/**/*.md)
```yaml
---
doc_id: breakwave_drybulk_2024-03-05
source: breakwave          # breakwave | baltic | book
category: drybulk          # drybulk | tankers | dry | tanker | gas | container | ningbo | book
date: 2024-03-05           # ISO date; null for books
title: "Dry Bulk Shipping — March 5, 2024"
source_path: reports/drybulk/2024/2024-03-05_Breakwave_Dry_Bulk.pdf
document_type: biweekly_report   # biweekly_report | weekly_roundup | reference_book
vessel_classes: [capesize, panamax, supramax]
regions: [china, brazil, australia, atlantic, pacific]
commodities: [iron_ore, coal, grain, bauxite]
signals:
  bdryff: 1016
  bdryff_30d_pct: -0.1
  bdryff_ytd_pct: -1.1
  bdryff_yoy_pct: -58.3
  bdi_spot: 602
  bdi_30d_pct: -45.1
  bdi_ytd_pct: -60.3
  bdi_yoy_pct: -69.0
  momentum: neutral
  sentiment: negative
  fundamentals: positive
---
```

## Chunk Schema (one JSON object per line in knowledge/chunks/*.jsonl)
```json
{
  "chunk_id": "breakwave_drybulk_2024-03-05_001",
  "doc_id": "breakwave_drybulk_2024-03-05",
  "source": "breakwave",
  "category": "drybulk",
  "date": "2024-03-05",
  "section": "main",
  "text": "...",
  "token_count": 380,
  "keywords": ["capesize", "iron_ore", "china"]
}
```

## Chunk Size Rules
- Breakwave reports: 400 tokens, 50-token overlap, max 3 chunks per report
- Baltic HTML: one chunk per vessel-class/commodity section; split if section > 600 tokens
- Books: 500 tokens, 100-token overlap, respect heading boundaries

## Query Instructions for AI Agents
1. Always read this file first.
2. Load `knowledge/manifests/documents.jsonl` for document inventory.
3. Keyword search: scan chunk `keywords` arrays first, then full-text.
4. Signal queries: use `knowledge/derived/signals.jsonl`.
5. Timeline queries: use `knowledge/derived/timelines.json`.
6. Cross-source synthesis: retrieve from both breakwave and baltic, date-align by ISO week.
7. Always cite: source, date, doc_id.
8. Market outlook: retrieve 3 most recent Breakwave reports + matching Baltic week, reason from those.

## Source Registry
- breakwave/drybulk: 2018–present, bi-weekly (~26/year)
- breakwave/tankers: 2023–present, bi-weekly (~26/year)
- baltic/dry, tanker, gas, container, ningbo: 2015–present, weekly
- books: 12 reference titles (shipping economics, maritime history, fleet analysis)
```

---

## Step 3 — Create `scripts/process_knowledge.py`

This is the master knowledge compiler. Write it completely.

### CLI Interface
```
python scripts/process_knowledge.py                      # process all unprocessed
python scripts/process_knowledge.py --source breakwave   # breakwave only
python scripts/process_knowledge.py --source baltic      # baltic only
python scripts/process_knowledge.py --source books       # books only
python scripts/process_knowledge.py --rebuild            # wipe knowledge/ and rebuild all
python scripts/process_knowledge.py --no-llm             # skip all Gemini calls
python scripts/process_knowledge.py --derived-only       # only rebuild derived artifacts
```

### Top of file — imports and config
```python
import os, re, json, time, hashlib, argparse, traceback
from pathlib import Path
from datetime import datetime
import pdfplumber
from bs4 import BeautifulSoup
import tiktoken
import frontmatter
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
REPO_ROOT    = Path(__file__).parent.parent
REPORTS_ROOT = REPO_ROOT / "reports"
KNOWLEDGE    = REPO_ROOT / "knowledge"
GEMINI_KEY   = os.environ.get("GEMINI_API_KEY")
TOKENIZER    = tiktoken.get_encoding("cl100k_base")

if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
    GEMINI = genai.GenerativeModel("gemini-2.0-flash")
else:
    GEMINI = None
```

### Processing Flow (for each source file)
```
1. Derive doc_id from source path
2. Load documents.jsonl manifest into a set of processed doc_ids
3. Skip if doc_id already in set (unless --rebuild)
4. Route to correct adapter: breakwave | baltic | book
5. Adapter returns: normalized_text (str), metadata (dict), sections (list of {heading, text})
6. Write knowledge/docs/{source}/{category}/{year}/{date}.md with YAML frontmatter
7. Chunk according to source type rules
8. Unless --no-llm: call Gemini for summary + keywords + theme tags
9. Unless --no-llm and source==breakwave: call Gemini as fallback for signal extraction
10. Append chunks to knowledge/chunks/{source}_{category}.jsonl
11. Append doc entry to knowledge/manifests/documents.jsonl
12. If breakwave: append to knowledge/derived/signals.jsonl
13. Print: [SOURCE] [DATE] ✓  or  [SOURCE] [DATE] ✗ reason
```

### Adapter A — Breakwave PDF

```python
def adapt_breakwave(pdf_path: Path, category: str) -> dict:
    """
    Extract text, signals, and fundamentals table from a Breakwave PDF.
    category: 'drybulk' or 'tankers'
    Returns: {text, metadata, sections}
    """
```

**PDF layout (handle both old and new format):**
- Page 1: 3-column header → BDRYFF value + 30D/YTD/YOY | BDI value + 30D/YTD/YOY | Short-term Indicators
- Old format (pre-2021) uses `www.drybulkETF.com` branding — parsing identical
- Page 1 body: "Bi-Weekly Report" heading + 3–5 bullet points
- Page 2: chart (skip, it's an image) + "Dry Bulk Fundamentals" table

**Signal extraction — regex first, Gemini fallback:**
```python
BDRYFF_RE    = re.compile(r'Breakwave Dry Futures Index[:\s]+([0-9,]+)')
BDI_RE       = re.compile(r'Baltic Dry Index \(spot\)[:\s]+([0-9,]+)')
CHANGE_RE    = re.compile(r'(30D|YTD|YOY)[:\s]+([+-]?\d+\.?\d*)%')
MOMENTUM_RE  = re.compile(r'Momentum[:\s]+(Positive|Negative|Neutral)', re.I)
SENTIMENT_RE = re.compile(r'Sentiment[:\s]+(Positive|Negative|Neutral)', re.I)
FUNDAMENT_RE = re.compile(r'Fundamentals[:\s]+(Positive|Negative|Neutral)', re.I)
```
If any field is None after regex AND Gemini is available, pass first 600 chars of page 1 to:
> "Extract these fields as JSON with no markdown: bdryff_value, bdi_value,
> bdryff_30d_pct, bdryff_ytd_pct, bdryff_yoy_pct, bdi_30d_pct, bdi_ytd_pct,
> bdi_yoy_pct, momentum, sentiment, fundamentals. Use null for missing values."

**Fundamentals table (page 2):**
Use `pdfplumber`'s `.extract_tables()`. Store as structured dict. Fields:
China Steel Production, China Steel Inventories, China Iron Ore Inventories,
China Iron Ore Imports, China Coal Imports, China Soybean Imports,
Brazil Iron Ore Exports, Australia Iron Ore Exports, Dry Bulk Fleet,
Baltic Dry Index Average, Capesize Spot Rates Average, Panamax Spot Rates Average.
Each row: `{"ytd": value, "yoy_pct": value}`. Store null if table not found.

**For tanker reports:** swap BDRYFF→BWETFF, BDI→BDTI/BCTI. Adjust regexes accordingly.

### Adapter B — Baltic Exchange HTML

```python
def adapt_baltic(html_path: Path, category: str) -> dict:
    """
    Extract article text with section awareness from Baltic Exchange HTML files.
    category: 'dry' | 'tanker' | 'gas' | 'container' | 'ningbo'
    Returns: {text, metadata, sections}
    """
```

**HTML structure (confirmed from samples):**
```html
<time datetime="2024-01-05">05 Jan 2024</time>
<h1>Gas report - Week 1</h1>
<div class="article-content">
  <p><b>LNG</b></p><p>...</p>
  <p><b>LPG</b></p><p>...</p>
</div>
```

**Content extraction logic:**
1. Parse with BeautifulSoup lxml
2. Content root: try `div.article-content` first; fallback to div containing `<time>` tag
3. (Some older files have `<h1>This site uses cookies</h1>` wrapper — ignore it, still find the real content)
4. Date: from `<time datetime="...">` attribute, fallback to filename prefix
5. Title: from `<h1>` inside content area
6. Sections: find all `<b>` or `<h4>` tags inside content — each is a section label
7. Section text = all `<p>` text following that label until next label
8. If zero sections detected: one chunk for the full article text

**Expected section names by category:**
- dry: Capesize, Panamax, Supramax, Handysize
- tanker: VLCC, Suezmax, Aframax, Clean Products
- gas: LNG, LPG
- container, ningbo: extract all bold headers as-is

### Adapter C — Shipping Books

```python
def adapt_book(pdf_path: Path) -> dict:
    """
    Page-by-page streaming extraction for large PDFs.
    Never loads entire book into memory at once.
    Returns: {text, metadata, sections}  (sections = chapters)
    """
```

**Critical constraints:**
- Process page by page via `pdfplumber.open()` context manager
- Skip pages where: text < 50 chars, or text is all-caps header, or looks like TOC (many short lines with numbers), or is a disclaimer/copyright page
- Detect chapter headings: a line is a heading if it's alone/near-alone on a page, title-cased or ALL CAPS, and < 15 tokens
- One Gemini call per book total (not per page) — for a short 3-sentence master summary
- chunk at chapter boundaries; fall back to 500-token chunks with 100-token overlap

### Chunking utility
```python
def chunk_text(text: str, max_tokens: int, overlap: int) -> list[str]:
    tokens = TOKENIZER.encode(text)
    chunks = []
    start = 0
    while start < len(tokens):
        end = min(start + max_tokens, len(tokens))
        chunks.append(TOKENIZER.decode(tokens[start:end]))
        start += max_tokens - overlap
    return chunks
```

### Gemini call utility
```python
def call_gemini(prompt: str, retries: int = 3) -> str | None:
    if GEMINI is None:
        return None
    for attempt in range(retries):
        try:
            time.sleep(1.5)
            r = GEMINI.generate_content(prompt)
            return r.text.strip()
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(4 * (attempt + 1))
            else:
                return None
```

### Error handling
- Wrap entire per-file processing in try/except
- On exception: log to `knowledge/manifests/errors.jsonl`:
  `{"file": "...", "error": "...", "ts": "ISO timestamp"}`
- Never crash the whole run on one bad file
- Always exit code 0

### Incremental logic
- On startup: load `documents.jsonl` → set of processed `doc_id`s
- `--rebuild`: delete `knowledge/docs/`, `knowledge/chunks/`, `knowledge/derived/`, all `.jsonl` manifests, then rebuild
- All `.jsonl` files: append-only (never rewrite during incremental run)

---

## Step 4 — Build Derived Artifacts

Add `build_derived()` function (called at end of every run, or via `--derived-only`).

**`knowledge/derived/signals.jsonl`** — one line per Breakwave report:
```json
{
  "date": "2024-03-05",
  "source": "breakwave",
  "category": "drybulk",
  "doc_id": "breakwave_drybulk_2024-03-05",
  "bdryff": 1016,
  "bdi": 602,
  "momentum": "neutral",
  "sentiment": "negative",
  "fundamentals": "positive",
  "bdryff_30d_pct": -0.1,
  "bdi_30d_pct": -45.1,
  "china_iron_ore_imports_yoy": -1.6,
  "dry_bulk_fleet_yoy": 2.4
}
```

**`knowledge/derived/timelines.json`** — keyed by ISO week `YYYY-Www`:
```json
{
  "2024-W10": {
    "breakwave_drybulk": "breakwave_drybulk_2024-03-05",
    "breakwave_tankers": null,
    "baltic_dry": "baltic_dry_2024-03-08",
    "baltic_gas": "baltic_gas_2024-03-08"
  }
}
```

**`knowledge/derived/themes.jsonl`** — one line per document, Gemini-generated:
```json
{
  "doc_id": "breakwave_drybulk_2024-03-05",
  "themes": ["china_demand", "capesize_weakness", "contango", "fleet_supply"],
  "key_entities": ["Vale", "Brazil", "China", "Atlantic basin"],
  "market_tone": "cautiously_bearish"
}
```

---

## Step 5 — Create `scripts/validate_knowledge.py`

Write a standalone validation script that:
1. Counts all source files in `reports/` by category
2. Counts all processed entries in `documents.jsonl` by category
3. Checks all `.md` docs have parseable YAML frontmatter
4. Checks all `.jsonl` chunk files are valid JSON line by line
5. Reports how many Breakwave reports have null signals (regex failed)
6. Prints a clean summary table:

```
Source                  Files   Processed   Missing   Chunks    Signals
breakwave/drybulk         186       186         0       558        186
breakwave/tankers          52        52         0       156         52
baltic/dry                570       570         0      2280          —
baltic/tanker             480       480         0      1920          —
baltic/gas                480       480         0       960          —
baltic/container          480       480         0       960          —
baltic/ningbo             480       480         0       960          —
books                      12        12         0      8400          —
─────────────────────────────────────────────────────────────────────
TOTAL                    2740      2740         0     16194        238
```

---

## Step 6 — GitHub Actions Workflows

### `.github/workflows/process_knowledge.yml`

```yaml
name: Process Knowledge Base

on:
  push:
    paths:
      - 'reports/**'
  workflow_dispatch:
    inputs:
      source:
        description: 'Source: breakwave | baltic | books | all'
        default: 'all'
      rebuild:
        description: 'Full rebuild: true | false'
        default: 'false'

jobs:
  process:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          token: ${{ secrets.GITHUB_TOKEN }}
          fetch-depth: 0

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r requirements_knowledge.txt

      - name: Pull latest
        run: git pull origin main --rebase

      - name: Run processor
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
        run: |
          FLAGS=""
          SRC="${{ github.event.inputs.source || 'all' }}"
          RB="${{ github.event.inputs.rebuild || 'false' }}"
          [ "$SRC" != "all" ] && FLAGS="$FLAGS --source $SRC"
          [ "$RB" == "true" ] && FLAGS="$FLAGS --rebuild"
          python scripts/process_knowledge.py $FLAGS

      - name: Commit knowledge artifacts
        run: |
          git config user.name "knowledge-bot"
          git config user.email "bot@shipping"
          git add knowledge/
          git diff --staged --quiet || git commit -m "knowledge: update $(date -u +%Y-%m-%d)"
          git push
```

### `.github/workflows/daily_knowledge_update.yml`

Runs daily at 15:30 UTC (after the existing scrapers). Checks if any `reports/` file is newer
than the last manifest update. If yes, runs incremental process and commits.

```yaml
name: Daily Knowledge Update

on:
  schedule:
    - cron: '30 15 * * *'
  workflow_dispatch:

jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          token: ${{ secrets.GITHUB_TOKEN }}
          fetch-depth: 0

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r requirements_knowledge.txt

      - name: Pull latest
        run: git pull origin main --rebase

      - name: Check for new reports
        id: check
        run: |
          MANIFEST="knowledge/manifests/documents.jsonl"
          if [ ! -f "$MANIFEST" ]; then
            echo "new=true" >> $GITHUB_OUTPUT
          else
            NEWER=$(find reports/ -newer "$MANIFEST" -name "*.pdf" -o -newer "$MANIFEST" -name "*.html" 2>/dev/null | head -1)
            [ -n "$NEWER" ] && echo "new=true" >> $GITHUB_OUTPUT || echo "new=false" >> $GITHUB_OUTPUT
          fi

      - name: Process new reports
        if: steps.check.outputs.new == 'true'
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
        run: python scripts/process_knowledge.py

      - name: Commit if changes
        if: steps.check.outputs.new == 'true'
        run: |
          git config user.name "knowledge-bot"
          git config user.email "bot@shipping"
          git add knowledge/
          git diff --staged --quiet || git commit -m "knowledge: daily update $(date -u +%Y-%m-%d)"
          git push
```

---

## Step 7 — Add GEMINI_API_KEY to GitHub Secrets

Using the GitHub CLI or direct API call, add the secret to the repo:
```bash
gh secret set GEMINI_API_KEY --body "AIzaSyCIXEZtsD86VZAy74OKNxgSfd7MDJ3EDL8" --repo yieldchaser/Shipping
```
If `gh` CLI is not available, print a reminder to the user to add it manually at:
`github.com/yieldchaser/Shipping → Settings → Secrets → Actions → New repository secret`

---

## Step 8 — Run the Full Local Build

After all files are created, run the build locally in this exact order:

```bash
# 1. Books first — large files, no LLM (avoids memory issues)
python scripts/process_knowledge.py --source books --no-llm

# 2. Breakwave — with full Gemini summaries and signal extraction
python scripts/process_knowledge.py --source breakwave

# 3. Baltic — no LLM (2000+ files, would exhaust free tier)
python scripts/process_knowledge.py --source baltic --no-llm

# 4. Build all derived artifacts
python scripts/process_knowledge.py --derived-only

# 5. Validate everything
python scripts/validate_knowledge.py
```

---

## Step 9 — Commit Everything

```bash
git add knowledge/ scripts/process_knowledge.py scripts/validate_knowledge.py \
        requirements_knowledge.txt .github/workflows/process_knowledge.yml \
        .github/workflows/daily_knowledge_update.yml .gitignore
git commit -m "feat: add shipping intelligence knowledge system"
git push origin main
```

---

## Done Criteria

The build is complete when ALL of the following are true:
- `knowledge/CLAUDE.md` exists with full schema
- `knowledge/manifests/documents.jsonl` has one line per source file in `reports/`
- `knowledge/chunks/*.jsonl` contains chunks for all sources
- `knowledge/derived/signals.jsonl` has structured entries for all Breakwave reports
- `knowledge/derived/timelines.json` maps ISO weeks to document IDs
- `python scripts/validate_knowledge.py` prints **zero missing files**
- Both GitHub Actions workflows are committed and visible in `.github/workflows/`
- `GEMINI_API_KEY` is set in GitHub repo secrets
- No changes to `index.html`, existing CSVs, or existing scripts
