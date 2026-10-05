"""Scale runner for Banchero Costa S&P, Newbuilding, and Demolition target pages.
Uses LlamaParse tier="cost_effective" with 8 concurrent workers.
"""
import glob, json, os, time, sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import pymupdf
from llama_parse import LlamaParse

API_KEY = os.environ.get("LLAMA_CLOUD_API_KEY", "")
if not API_KEY:
    raise SystemExit("LLAMA_CLOUD_API_KEY is not set in the environment. This runner must "
                     "never carry the key in source - the sibling run_banchero_llamaparse.py "
                     "reads it from the env and never persists it.")
ROOT = Path(__file__).resolve().parents[3]
LP_DIR = ROOT / "data" / "extracted" / "llamaparse_banchero"
MD_DIR = ROOT / "data" / "extracted" / "md" / "banchero_costa"
STATE_FILE = LP_DIR / "_scale_state.json"

LP_DIR.mkdir(parents=True, exist_ok=True)
MD_DIR.mkdir(parents=True, exist_ok=True)

def find_target_pnos(pdf_path):
    doc = pymupdf.open(pdf_path)
    target_pnos = set()
    for pno, page in enumerate(doc):
        t = page.get_text().upper()
        if any(k in t for k in ['NEWBUILDING', 'DEMOLITION', 'SHIP RECYCLING', 'SECONDHAND', 'REPORTED SALES', 'SALE & PURCHASE']):
            if pno > 1: # skip cover and TOC
                target_pnos.add(pno)
    doc.close()
    if not target_pnos:
        target_pnos = {8, 9, 10}
    return sorted(list(target_pnos))

def parse_single_doc(stem, pdf_path, pnos):
    pages_str = ",".join(str(p) for p in pnos)
    t0 = time.time()
    try:
        parser = LlamaParse(
            api_key=API_KEY,
            result_type="markdown",
            tier="cost_effective",
            version="latest",
            target_pages=pages_str,
            output_tables_as_HTML=True,
            verbose=False
        )
        docs = parser.load_data(str(pdf_path))
        md_text = "\n\n".join(d.text for d in docs)
        
        # Save to LP_DIR and year-partitioned MD_DIR
        (LP_DIR / f"{stem}.md").write_text(md_text, encoding="utf-8")
        yr_dir = MD_DIR / pdf_path.parent.name
        yr_dir.mkdir(parents=True, exist_ok=True)
        (yr_dir / f"{stem}.md").write_text(md_text, encoding="utf-8")
        secs = round(time.time() - t0, 1)
        return stem, True, len(md_text), secs, None
    except Exception as e:
        secs = round(time.time() - t0, 1)
        return stem, False, 0, secs, str(e)

def main():
    pdfs = sorted(glob.glob(str(ROOT / "corpus/01-brokers/banchero_costa/*/*.pdf")))
    print(f"Total PDFs found: {len(pdfs)}")
    
    state = {}
    if STATE_FILE.exists():
        try:
            state = json.loads(STATE_FILE.read_text())
        except Exception:
            state = {}
            
    # Check which docs need parsing
    todo = []
    for p in pdfs:
        stem = Path(p).stem
        # Check if already successfully parsed in state
        if stem in state.get("done", {}):
            continue
            
        # Check if already complete in LP_DIR from previous jobs
        lp_md = LP_DIR / f"{stem}.md"
        is_complete = False
        if lp_md.exists():
            txt = lp_md.read_text(encoding="utf-8").upper()
            has_nb = ("CAPESIZE" in txt and "USD MLN" in txt) or "INDICATIVE NEWBUILDING" in txt
            has_demo = ("BANGLADESH" in txt or "PAKISTAN" in txt) and ("USD/LDT" in txt or "USD LDT" in txt)
            if has_nb and has_demo:
                is_complete = True
                
        if is_complete:
            state.setdefault("done", {})[stem] = {"chars": len(txt), "skipped": "already_complete"}
        else:
            pnos = find_target_pnos(p)
            todo.append((stem, p, pnos))
            
    STATE_FILE.write_text(json.dumps(state, indent=2))
    print(f"Already complete: {len(state.get('done', {}))}")
    print(f"To parse now: {len(todo)}")
    
    if not todo:
        print("All documents are complete!")
        return
        
    num_workers = 8
    print(f"Starting execution with {num_workers} parallel workers...")
    
    done_count = len(state.get("done", {}))
    total_docs = len(pdfs)
    
    with ThreadPoolExecutor(max_workers=num_workers) as pool:
        future_to_doc = {
            pool.submit(parse_single_doc, stem, p, pnos): (stem, pnos)
            for stem, p, pnos in todo
        }
        
        for future in as_completed(future_to_doc):
            stem, pnos = future_to_doc[future]
            doc_stem, success, chars, secs, err = future.result()
            if success:
                done_count += 1
                state.setdefault("done", {})[doc_stem] = {
                    "pages": pnos,
                    "chars": chars,
                    "secs": secs
                }
                print(f"[{done_count}/{total_docs}] OK: {doc_stem} ({len(pnos)} pages) -> {chars} chars in {secs}s")
            else:
                state.setdefault("failed", {})[doc_stem] = {
                    "pages": pnos,
                    "error": err
                }
                print(f"[{done_count}/{total_docs}] FAIL: {doc_stem} -> {err}")
                
            # Checkpoint every 5 docs
            if done_count % 5 == 0:
                STATE_FILE.write_text(json.dumps(state, indent=2))
                
    STATE_FILE.write_text(json.dumps(state, indent=2))
    print(f"Finished! Total done: {len(state.get('done', {}))}, Failed: {len(state.get('failed', {}))}")

if __name__ == "__main__":
    main()
