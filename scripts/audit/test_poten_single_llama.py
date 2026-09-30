import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "extract"))

from llama_manager import get_active_parser

pdf_path = ROOT / "corpus" / "04-poten" / "pdfs" / "2011" / "Tanker_Opinion_20110128.pdf"

parser = get_active_parser(tier="cost_effective")
docs = parser.load_data(str(pdf_path))
full_text = "\n\n".join(d.text for d in docs)
print("--- PREVIEW OF LAST 1000 CHARS ---")
print(full_text[-1000:])
print("--- END PREVIEW ---")
