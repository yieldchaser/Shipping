"""
Compiler for Broker Reports Knowledge Chunks.
Processes markdown files in reports/broker_reports/ and generates
tokenized JSONL shards in knowledge/chunks/broker_reports_2026.jsonl
with chunk_id, source, text, keywords, and metadata for live BM25 retrieval.
"""

import os
import re
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = REPO_ROOT / "reports" / "broker_reports"
CHUNKS_DIR = REPO_ROOT / "knowledge" / "chunks"

def extract_keywords(text):
    words = re.findall(r'\b[a-zA-Z0-9_\-\$]{3,}\b', text.lower())
    # Frequency filter
    counts = {}
    for w in words:
        if w not in {'the', 'and', 'for', 'with', 'from', 'this', 'that', 'were', 'been', 'have', 'which'}:
            counts[w] = counts.get(w, 0) + 1
    sorted_words = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    return [w[0] for w in sorted_words[:25]]

def main():
    CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
    out_file = CHUNKS_DIR / "broker_reports_2026.jsonl"
    
    md_files = list(REPORTS_DIR.rglob("*.md"))
    print(f"Found {len(md_files)} broker report markdown files.")
    
    total_chunks = 0
    with open(out_file, "w", encoding="utf-8") as out_f:
        for md_path in md_files:
            try:
                content = md_path.read_text(encoding="utf-8", errors="ignore")
                
                # Parse frontmatter
                title_match = re.search(r'title:\s*"([^"]+)"', content)
                date_match = re.search(r'date:\s*"([^"]+)"', content)
                source_match = re.search(r'source:\s*"([^"]+)"', content)
                
                title = title_match.group(1) if title_match else md_path.stem
                date_str = date_match.group(1) if date_match else "2026-08-24"
                source = source_match.group(1) if source_match else "broker_report"
                
                # Strip frontmatter
                body = re.sub(r'^---.*?---\s*', '', content, flags=re.DOTALL).strip()
                
                # Split body into logical sections/paragraphs of ~800-1200 chars
                paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
                
                current_chunk = []
                current_len = 0
                chunk_idx = 1
                
                for p in paragraphs:
                    current_chunk.append(p)
                    current_len += len(p)
                    if current_len >= 900:
                        chunk_text = f"Title: {title}\nDate: {date_str}\nBroker: {source}\n\n" + "\n\n".join(current_chunk)
                        chunk_obj = {
                            "chunk_id": f"broker_{source}_{md_path.stem}_{chunk_idx}",
                            "doc_id": md_path.stem,
                            "source": source,
                            "date": date_str,
                            "title": title,
                            "text": chunk_text,
                            "keywords": extract_keywords(chunk_text),
                        }
                        out_f.write(json.dumps(chunk_obj, ensure_ascii=False) + "\n")
                        total_chunks += 1
                        chunk_idx += 1
                        current_chunk = []
                        current_len = 0
                        
                if current_chunk:
                    chunk_text = f"Title: {title}\nDate: {date_str}\nBroker: {source}\n\n" + "\n\n".join(current_chunk)
                    chunk_obj = {
                        "chunk_id": f"broker_{source}_{md_path.stem}_{chunk_idx}",
                        "doc_id": md_path.stem,
                        "source": source,
                        "date": date_str,
                        "title": title,
                        "text": chunk_text,
                        "keywords": extract_keywords(chunk_text),
                    }
                    out_f.write(json.dumps(chunk_obj, ensure_ascii=False) + "\n")
                    total_chunks += 1
                    
            except Exception as e:
                print(f"Error compiling {md_path.name}: {e}")
                
    print(f"[OK] Compiled {total_chunks} grounded knowledge chunks into {out_file.name}")

if __name__ == "__main__":
    main()
