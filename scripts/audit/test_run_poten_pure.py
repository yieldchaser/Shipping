import sys
sys.stdout.reconfigure(encoding='utf-8')
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "extract" / "publishers"))

import run_poten

pdf_path = ROOT / "corpus" / "04-poten" / "pdfs" / "2004" / "Tanker_Opinion_20040305.pdf"

meta, full_md_content, tables_data, all_charterer_rows, md_rel_path, tables_rel_path = run_poten.process_pdf(pdf_path, defaultdict(int))

print("--- MD CONTENT PREVIEW (FIRST 1500 CHARS) ---")
print(full_md_content[:1500])
print("\n--- MD CONTENT PREVIEW (MIDDLE 1500 CHARS) ---")
print(full_md_content[1500:3000])
print("\n--- MD CONTENT PREVIEW (LAST 1000 CHARS) ---")
print(full_md_content[-1000:])
print(f"\nTables count: {tables_data['tables_count']}")
print(f"Charterers rows: {len(all_charterer_rows)}")
