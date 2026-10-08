"""Phase 1: inventory all corpus seabrokers table grids into scratch JSONL."""
import json, os, glob, re

ROOT = r"C:/Users/Dell/Github/Shipping"
CORPus = os.path.join(ROOT, "data/extracted/corpus/seabrokers")
OUT = os.path.join(ROOT, "scratch/seabrokers_ext")
os.makedirs(OUT, exist_ok=True)

rows = []
for d in sorted(os.listdir(CORPus)):
    dp = os.path.join(CORPus, d)
    if not os.path.isdir(dp):
        continue
    tp = os.path.join(dp, "tables.jsonl")
    if not os.path.exists(tp):
        continue
    docdate = d[:10]
    for i, line in enumerate(open(tp, encoding="utf-8")):
        try:
            rec = json.loads(line)
        except Exception:
            continue
        grid = rec.get("rows")
        if not grid:
            continue
        cells = [str(c) for row in grid for c in row if c not in (None, "")]
        blob = " | ".join(cells)
        # numeric density
        num = len(re.findall(r"\d", blob))
        rows.append({
            "doc": d, "date": docdate, "tidx": i, "page": rec.get("page"),
            "engine": rec.get("engine"), "acc": rec.get("acc"),
            "nrows": len(grid), "ncols": max(len(r) for r in grid) if grid else 0,
            "ncells": len(cells), "ndigits": num,
            "blob": blob[:1200],
        })

with open(os.path.join(OUT, "table_inventory.jsonl"), "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

print("docs scanned:", len(set(r["doc"] for r in rows)))
print("total grids:", len(rows))
print("with >=20 digits:", sum(1 for r in rows if r["ndigits"] >= 20))
