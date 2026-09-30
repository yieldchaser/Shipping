import sys
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "extract" / "publishers"))
import test_enhanced_poten
import run_poten

pdf_path = ROOT / "corpus" / "04-poten" / "pdfs" / "2011" / "Tanker_Opinion_20110603.pdf"
meta, full_md, tables_data, ch_rows, md_rel, tbl_rel = run_poten.process_pdf(pdf_path, defaultdict(int))

print("=== FULL EXTRACTED MARKDOWN (Tanker_Opinion_20110603.pdf) ===")
print(full_md)
print("=== END MARKDOWN ===")
