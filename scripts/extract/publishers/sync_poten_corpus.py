import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EXTRACTED_DIR = ROOT / "data" / "extracted" / "md" / "poten"
CORPUS_DIR = ROOT / "corpus" / "04-poten"

def sync_corpus():
    extracted_files = sorted(EXTRACTED_DIR.glob("*/*.md"))
    print(f"Found {len(extracted_files)} files in {EXTRACTED_DIR}")
    
    # Index corpus files by year
    corpus_files = list(CORPUS_DIR.glob("[0-9]*/*.md"))
    print(f"Found {len(corpus_files)} files in {CORPUS_DIR}")
    
    # Map corpus files by pdf_file name
    pdf_to_corpus = {}
    for cf in corpus_files:
        txt = cf.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r'pdf_file:\s*"([^"\r\n]+)"', txt)
        if not m:
            m = re.search(r'pdf_file:\s*([^\r\n]+)', txt)
        if m:
            p_name = Path(m.group(1).strip().strip('"').strip("'")).name
            pdf_to_corpus.setdefault(p_name, []).append(cf)
            
    replaced_stubs = 0
    synced = 0
    
    for ef in extracted_files:
        txt = ef.read_text(encoding="utf-8")
        m_src = re.search(r'source_file:\s*"([^"]+)"', txt)
        if not m_src:
            continue
        pdf_name = Path(m_src.group(1)).name
        year = ef.parent.name
        
        target_corpus_dir = CORPUS_DIR / year
        target_corpus_dir.mkdir(parents=True, exist_ok=True)
        target_corpus_file = target_corpus_dir / ef.name
        
        # Check if there are existing stubs for this PDF
        stubs = pdf_to_corpus.get(pdf_name, [])
        for s in stubs:
            if s != target_corpus_file and s.exists():
                s.unlink()
                replaced_stubs += 1
                
        target_corpus_file.write_text(txt, encoding="utf-8")
        synced += 1
        
    print(f"Successfully synced {synced} files to {CORPUS_DIR}")
    print(f"Removed {replaced_stubs} old stubs")
    
    # Check remaining stubs
    remaining = list(CORPUS_DIR.glob("[0-9]*/*.md"))
    unknown_count = sum(1 for f in remaining if "unknown-01-01" in f.name or "unknown-01-01" in f.read_text(encoding="utf-8", errors="ignore"))
    print(f"Remaining total files in corpus: {len(remaining)}")
    print(f"Remaining files with unknown-01-01: {unknown_count}")

if __name__ == "__main__":
    sync_corpus()
