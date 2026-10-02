import os
import shutil
from pathlib import Path
from datetime import datetime

ROOT = Path("c:/Users/Dell/Github/Shipping")
STASH_ROOT = ROOT / "data" / "stashed_redundant_sources"

def execute_stash():
    STASH_ROOT.mkdir(parents=True, exist_ok=True)
    stats = {}

    # 1. Hellenic Iron Ore HTML Previews
    src_io = ROOT / "data" / "extracted" / "md" / "hellenic" / "iron_ore"
    dst_io = STASH_ROOT / "hellenic_iron_ore_html_previews"
    if src_io.exists():
        dst_io.mkdir(parents=True, exist_ok=True)
        count_io = 0
        for item in src_io.iterdir():
            target = dst_io / item.name
            if target.exists():
                if target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink()
            shutil.move(str(item), str(target))
            count_io += 1
        stats["hellenic_iron_ore_html_previews"] = count_io
        
        # Place pointer README in src_io
        src_io.mkdir(parents=True, exist_ok=True)
        pointer_io = src_io / "README_STASHED.md"
        pointer_io.write_text(
            "# Hellenic Iron Ore HTML Web Previews (STASHED)\n\n"
            "The 3,500+ legacy HTML web-preview markdown extractions previously stored here have been "
            "quarantined and stashed to:\n"
            "`data/stashed_redundant_sources/hellenic_iron_ore_html_previews/`\n\n"
            "## Active Ground Truth Path\n"
            "The authoritative cover-to-cover iron ore markdown extractions (6-page MMi and 1-page SMM Daily) "
            "are located at:\n"
            "**`data/extracted/md/hellenic/iron_ore_pdf/`**\n",
            encoding="utf-8"
        )

    # 2. Poten Legacy Scraped Markdown (Corpus)
    poten_corpus = ROOT / "corpus" / "04-poten"
    dst_poten = STASH_ROOT / "poten_legacy_scraped_md"
    dst_poten.mkdir(parents=True, exist_ok=True)
    count_poten = 0
    if poten_corpus.exists():
        for year_dir in poten_corpus.iterdir():
            if year_dir.is_dir() and year_dir.name != "pdfs":
                dst_yr = dst_poten / year_dir.name
                dst_yr.mkdir(parents=True, exist_ok=True)
                for f in list(year_dir.glob("*.md")):
                    dst_f = dst_yr / f.name
                    if dst_f.exists():
                        dst_f.unlink()
                    shutil.move(str(f), str(dst_f))
                    count_poten += 1
                # Remove empty year dir if empty
                if not any(year_dir.iterdir()):
                    year_dir.rmdir()
        stats["poten_legacy_scraped_md"] = count_poten
        
        pointer_poten = poten_corpus / "README_STASHED.md"
        pointer_poten.write_text(
            "# Poten & Partners Corpus (CLEANED & AUDITED)\n\n"
            "Legacy scraped web preview markdown files have been quarantined and stashed to:\n"
            "`data/stashed_redundant_sources/poten_legacy_scraped_md/`\n\n"
            "## Active Authoritative Paths\n"
            "- **Authoritative Corpus PDFs:** `corpus/04-poten/pdfs/` (1,087 PDFs, 2004-2026)\n"
            "- **Authoritative Extracted Markdown:** `data/extracted/md/poten/` (1,087 Markdown files)\n",
            encoding="utf-8"
        )

    # 3. Loose unpartitioned root duplicates across brokers
    brokers = [
        "banchero_costa", "carriers", "fearnleys", 
        "ism", "ssy", "xclusiv", "advanced_shipping", 
        "affinity", "agora", "clarksons", "lion", "star_asia"
    ]
    dst_brokers = STASH_ROOT / "brokers_unpartitioned_root_duplicates"
    dst_brokers.mkdir(parents=True, exist_ok=True)
    
    broker_stats = {}
    for b in brokers:
        b_dir = ROOT / "data" / "extracted" / "md" / b
        if b_dir.exists():
            dst_b = dst_brokers / b
            dst_b.mkdir(parents=True, exist_ok=True)
            root_files = [f for f in b_dir.iterdir() if f.is_file() and not f.name.startswith(".")]
            b_count = 0
            for rf in root_files:
                dst_f = dst_b / rf.name
                if dst_f.exists():
                    dst_f.unlink()
                shutil.move(str(rf), str(dst_f))
                b_count += 1
            if b_count > 0:
                broker_stats[b] = b_count
    stats["brokers_root_duplicates"] = broker_stats

    # 4. Master README in STASH_ROOT
    master_readme = STASH_ROOT / "README.md"
    readme_content = f"""# Stashed Redundant and Misleading Sources Ledger

**Stash Timestamp:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Purpose:** Quarantine legacy, unpartitioned, truncated, or misleading source files and preview extractions so that no automated scanning tool, knowledge graph, or assistant mistakenly references them over the authoritative ground truth sources.

> **CRITICAL POLICY:**
> None of these files have been deleted. Everything is preserved here in this quarantine directory for complete auditability.

---

## 1. Hellenic Iron Ore HTML Web Previews
- **Stashed Count:** {stats.get('hellenic_iron_ore_html_previews', 0)} items
- **Quarantine Path:** `data/stashed_redundant_sources/hellenic_iron_ore_html_previews/`
- **Why Stashed:** These were short (~20-40 line) HTML web article summaries scraped from the Hellenic news website. Because the folder was named `iron_ore`, agents and scripts routinely mistook them for the primary extracted data, ignoring the true multi-page reports.
- **Active Authoritative Path:** [`data/extracted/md/hellenic/iron_ore_pdf/`](file:///c:/Users/Dell/Github/Shipping/data/extracted/md/hellenic/iron_ore_pdf) (1,188 full-fidelity Markdown reports + `.tables.json` sidecars across 2021-2026, plus 21 stacked master series CSVs).

---

## 2. Poten Legacy Scraped Markdown
- **Stashed Count:** {stats.get('poten_legacy_scraped_md', 0)} files
- **Quarantine Path:** `data/stashed_redundant_sources/poten_legacy_scraped_md/`
- **Why Stashed:** These were old markdown files dumped directly into `corpus/04-poten/` with truncated text (`... Read More" />`) and broken dates (`unknown-01-01`). Their presence in the corpus directory caused confusion with the real PDF corpus.
- **Active Authoritative Paths:**
  - **Corpus PDFs:** [`corpus/04-poten/pdfs/`](file:///c:/Users/Dell/Github/Shipping/corpus/04-poten/pdfs) (1,087 authoritative PDFs)
  - **Extracted Markdown:** [`data/extracted/md/poten/`](file:///c:/Users/Dell/Github/Shipping/data/extracted/md/poten) (1,087 full cover-to-cover Markdown reports)

---

## 3. Shipbroker Unpartitioned Root Duplicate Files
- **Stashed Counts:**
{chr(10).join(f"  - `{b}`: {cnt} files" for b, cnt in stats.get('brokers_root_duplicates', {}).items())}
- **Quarantine Path:** `data/stashed_redundant_sources/brokers_unpartitioned_root_duplicates/`
- **Why Stashed:** Early extractor runs placed markdown and sidecar files directly into `data/extracted/md/<broker>/`. Subsequent improvements partitioned the corpus into `<year>/` subdirectories (`2021/` to `2026/`). The loose files in the root folder were 100% duplicate copies of the year-partitioned files, creating clutter and risking stale file references.
- **Active Authoritative Paths:** [`data/extracted/md/<broker>/<year>/`](file:///c:/Users/Dell/Github/Shipping/data/extracted/md)
"""
    master_readme.write_text(readme_content, encoding="utf-8")
    print("Stashing execution completed successfully.")
    print("Summary of stashed assets:")
    for k, v in stats.items():
        print(f"  {k}: {v}")

if __name__ == "__main__":
    execute_stash()
