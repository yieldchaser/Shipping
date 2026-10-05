import os
import re
import json
import shutil
from pathlib import Path

MD_ROOT = Path("data/extracted/md")

def extract_year_from_file(p: Path) -> str:
    # 1. From filename
    m = re.search(r'\b(201\d|202\d)\b', p.name)
    if m:
        return m.group(1)
    
    # 2. From date pattern in filename: YYYY-MM-DD or DD_MM_YYYY
    m_iso = re.search(r'\b(20\d{2})[-_]\d{2}[-_]\d{2}\b', p.name)
    if m_iso:
        return m_iso.group(1)
        
    m_dmy = re.search(r'\b\d{2}[-_]\d{2}[-_](20\d{2})\b', p.name)
    if m_dmy:
        return m_dmy.group(1)
        
    # 3. From file content (YAML frontmatter or JSON)
    try:
        content = p.read_text(encoding="utf-8", errors="ignore")[:2000]
        if p.suffix == ".json":
            try:
                data = json.loads(p.read_text(encoding="utf-8", errors="ignore"))
                if "year" in data and str(data["year"]).isdigit():
                    return str(data["year"])
                if "issue_date" in data:
                    return str(data["issue_date"])[:4]
            except Exception:
                pass
        m_yaml = re.search(r'(?:year|date|issue_date):\s*["\']?(20\d{2})', content)
        if m_yaml:
            return m_yaml.group(1)
    except Exception:
        pass
        
    return "2026"

def audit_and_reorganize(dry_run=True):
    actions = {
        "deleted_exact_duplicates": 0,
        "updated_richer_to_subdir": 0,
        "deleted_stale_root_duplicates": 0,
        "moved_to_year_subdir": 0,
        "errors": []
    }

    for bdir in sorted(MD_ROOT.iterdir()):
        if not bdir.is_dir() or bdir.name in ["images", "fearnleys_cleaned"]:
            continue
            
        loose = [f for f in bdir.iterdir() if f.is_file() and not f.name.startswith("_")]
        if not loose:
            continue
            
        # Map existing subdir files
        sub_files = {} # name -> Path
        for item in bdir.iterdir():
            if item.is_dir():
                for sf in item.iterdir():
                    if sf.is_file():
                        sub_files[sf.name] = sf
                        
        print(f"\nProcessing {bdir.name} ({len(loose)} loose files)...")
        
        for lf in loose:
            if lf.name in sub_files:
                sf = sub_files[lf.name]
                lf_sz = lf.stat().st_size
                sf_sz = sf.stat().st_size
                
                if lf_sz == sf_sz:
                    actions["deleted_exact_duplicates"] += 1
                    if not dry_run:
                        lf.unlink()
                elif lf_sz > sf_sz:
                    # Loose file is larger (newer/richer content)
                    actions["updated_richer_to_subdir"] += 1
                    if not dry_run:
                        shutil.copy2(lf, sf)
                        lf.unlink()
                else:
                    # Subdir file is already larger/richer (loose was empty stub)
                    actions["deleted_stale_root_duplicates"] += 1
                    if not dry_run:
                        lf.unlink()
            else:
                # File not in any subdir -> determine year and move
                year = extract_year_from_file(lf)
                target_dir = bdir / year
                target_file = target_dir / lf.name
                actions["moved_to_year_subdir"] += 1
                if not dry_run:
                    target_dir.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(lf), str(target_file))

        # Process fearnleys_cleaned if present
    fc_dir = MD_ROOT / "fearnleys_cleaned"
    if fc_dir.exists() and fc_dir.is_dir():
        print(f"\nReconciling fearnleys_cleaned ({len(list(fc_dir.iterdir()))} items)...")
        f_dir = MD_ROOT / "fearnleys"
        sub_files_f = {}
        for item in f_dir.iterdir():
            if item.is_dir():
                for sf in item.iterdir():
                    if sf.is_file():
                        sub_files_f[sf.name] = sf
                        
        fc_items = list(fc_dir.iterdir())
        for fci in fc_items:
            if fci.name.startswith("_"):
                if not dry_run:
                    fci.unlink()
                continue
            if fci.name in sub_files_f:
                sf = sub_files_f[fci.name]
                if fci.stat().st_size > sf.stat().st_size:
                    if not dry_run:
                        shutil.copy2(fci, sf)
                        fci.unlink()
                else:
                    if not dry_run:
                        fci.unlink()
            else:
                year = extract_year_from_file(fci)
                tgt = f_dir / year / fci.name
                if not dry_run:
                    (f_dir / year).mkdir(parents=True, exist_ok=True)
                    shutil.move(str(fci), str(tgt))
        if not dry_run and not list(fc_dir.iterdir()):
            fc_dir.rmdir()
            print("  Removed redundant fearnleys_cleaned directory.")

    print("\nSummary of Actions (dry_run=" + str(dry_run) + "):")
    for k, v in actions.items():
        print(f"  {k}: {v}")

if __name__ == "__main__":
    import sys
    dry = "--run" not in sys.argv
    audit_and_reorganize(dry_run=dry)
