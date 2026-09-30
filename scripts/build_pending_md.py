import sys
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from scripts.extract.publishers.run_banchero_world_class_llama import build_final_md_and_tables
from scripts.extract.publishers.stack_banchero_series import stack_all

raw_dir = ROOT / "data" / "extracted" / "llamaparse_banchero_v2"
corpus_dir = ROOT / "corpus" / "01-brokers" / "banchero_costa"
pdf_map = {p.stem: p for p in corpus_dir.glob("**/*.pdf")}

raw_files = sorted(raw_dir.glob("*.md"))
print(f"Compiling {len(raw_files)} files across all years...")

total_sales = 0
total_rates = 0

for idx, f in enumerate(raw_files, 1):
    stem = f.stem
    pdf_path = pdf_map.get(stem)
    if not pdf_path:
        # Fallback to search by prefix
        candidates = list(corpus_dir.glob(f"**/{stem}.pdf"))
        if candidates:
            pdf_path = candidates[0]
            
    if pdf_path and pdf_path.exists():
        build_final_md_and_tables(stem, pdf_path)
        json_path = ROOT / "data" / "extracted" / "md" / "banchero_costa" / f"{stem}.tables.json"
        if json_path.exists():
            data = json.loads(json_path.read_text(encoding="utf-8"))
            sales = len(data.get("reported_sales", []))
            rates = len(data.get("freight_benchmarks", []))
            total_sales += sales
            total_rates += rates
            if idx % 25 == 0 or idx == len(raw_files):
                print(f"[{idx}/{len(raw_files)}] {stem}: sales={sales}, rates={rates} (Cumulative sales: {total_sales})")

print(f"\nCompleted compilation! Total sales across all reports: {total_sales}, Total rates: {total_rates}")
print("Now running stack_all()...")
stack_all()
print("All series stacked successfully!")
