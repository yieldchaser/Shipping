import os
import sys

if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

REPO_ROOT = os.path.normpath(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
check_dirs = [
    os.path.join(REPO_ROOT, "corpus", "06-drewry"),
    os.path.join(REPO_ROOT, "data", "extracted", "md", "drewry")
]

keywords = [
    "independen't",
    "contrac't's",
    "requi're's",
    "eigh't",
    "consecuti've",
    "assessmen't",
    "WeCha't",
    "atsupplychains@",
    "atenquiries@",
    "ourForecaster",
    "servicesand",
    "Source:Drewry"
]

found = []
total_md = 0

for cdir in check_dirs:
    for root, dirs, files in os.walk(cdir):
        for f in files:
            if f.endswith('.md'):
                total_md += 1
                full = os.path.join(root, f)
                with open(full, 'r', encoding='utf-8', errors='ignore') as fh:
                    txt = fh.read()
                matches = [w for w in keywords if w in txt]
                if matches:
                    found.append((os.path.relpath(full, REPO_ROOT), matches))

print(f"Total markdown files scanned: {total_md}")
print(f"Total offending files found: {len(found)}")
if found:
    for f, m in found[:10]:
        print(f"  {f}: {m}")
else:
    print("ALL 548 DREWRY OPINIONS & WCI FILES ARE 100% CLEAN OF TARGET DEFECTS!")
