import sys
import os
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Ensure UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

from llama_parse import LlamaParse
from scripts.extract.llama_manager import manager

key = manager.get_current_key()
account = manager.get_current_account_info()
print(f"Using account: {account['name']} (ID: {account['id']})")

pdf_path = Path("corpus/01-brokers/banchero_costa/2026/banchero_costa_2026_W13_Bancosta-Weekly-2026-13.pdf")
# pages 2 through 15 are 1 to 14 in 0-indexed
target_pages = ",".join(str(i) for i in range(1, 15))
print(f"Target pages: {target_pages}")

parser = LlamaParse(
    api_key=key,
    result_type="markdown",
    target_pages=target_pages,
    tier="cost_effective",
    version="latest",
    verbose=True
)

docs = parser.load_data(str(pdf_path))
print(f"Parsed {len(docs)} documents")
if docs:
    full_md = "\n\n".join(d.text for d in docs)
    print(f"Total length of markdown: {len(full_md)} chars")
    out_file = Path("data/extracted/test_w13_llamaparse.md")
    out_file.write_text(full_md, encoding="utf-8")
    print(f"Saved test file to {out_file}")
    manager.record_success(num_pages=14)
