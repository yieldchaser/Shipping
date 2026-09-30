import os
import json
import csv
from pathlib import Path

def count_rows(path):
    if not os.path.exists(path): return 0
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        return sum(1 for _ in f) - 1 # excluding header

D = 'data/extracted/series'
if os.path.exists(D):
    for f in os.listdir(D):
        if f.endswith('.csv'):
            print(f"{f}: {count_rows(os.path.join(D, f))} rows")

print("Seabrokers LlamaParse:")
f = 'data/extracted/llamaparse_seabrokers/llamaparse_state.json'
if os.path.exists(f):
    try:
        print(len(json.load(open(f))))
    except Exception as e:
        print(e)
else:
    print("Not found")

print("Poten extracted MD:")
d = 'data/extracted/md/poten'
if os.path.exists(d):
    print(len([f for f in os.listdir(d) if f.endswith('.md')]))

print("Breakwave scraper in scripts/scrapers/")
print(os.path.exists('scripts/scrapers/breakwave_scraper.py'))

print("Signal monitors:")
d = 'corpus/07-signal'
if os.path.exists(d):
    print("HTML:", sum(1 for root, _, files in os.walk(d) for f in files if f.endswith('.html')))
    print("PNG:", sum(1 for root, _, files in os.walk(d) for f in files if f.endswith('.png')))
    # wait, monitors
    print("Monitors:", sum(1 for root, _, files in os.walk(d) for f in files if 'monitor' in f.lower()))

