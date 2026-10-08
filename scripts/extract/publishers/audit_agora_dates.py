import csv, os, sys, datetime as dt, re
from pathlib import Path
import pymupdf
ROOT = Path('.')
CSV = ROOT/"data"/"extracted"/"series"/"agora_indicators_series.csv"
MONTHS = {m:i for i,m in enumerate(["January","February","March","April","May","June","July","August","September","October","November","December"],1)}
WEEK_RE = re.compile(r"Week\s+(\d{1,2})\s*/\s*((?:19|20)\d\d)")
REF_RE  = re.compile(r"Reference\s+point\s+(\d{1,2})\s+([A-Za-z]+)\s+((?:19|20)\d\d)")

def cover_meta(pdf):
    try:
        doc = pymupdf.open(pdf); txt = re.sub(r"\s+"," ",doc[0].get_text()); doc.close()
    except Exception as e:
        return None,None,f"unreadable:{e}"
    w = WEEK_RE.search(txt); r = REF_RE.search(txt)
    if not w: return None,None,"no Week N / YYYY on cover"
    wk,yr = int(w.group(1)), int(w.group(2))
    try: fri = dt.date.fromisocalendar(yr,wk,5)
    except ValueError: return None,None,f"bad ISO week {yr}-W{wk}"
    if r:
        try: ref = dt.date(int(r.group(3)),MONTHS[r.group(2).capitalize()],int(r.group(1)))
        except (KeyError,ValueError): return None,None,"unparseable ref"
        if ref.isocalendar()[:2]!=(yr,wk):
            return None,None,f"cover inconsistent: ref {ref} is ISO wk{ref.isocalendar()[1]}, cover says W{wk}"
    return fri.isoformat(), wk, "ok"

rows=list(csv.DictReader(open(CSV,newline='',encoding='utf-8-sig',errors='ignore')))
byfile={}
for r in rows: byfile.setdefault(r['source_file'],[]).append(r)
print(f"series rows {len(rows)}; distinct source_file {len(byfile)}")
mismatch=[]; nocover=[]; consistent=0
for sf,rs in sorted(byfile.items()):
    pdf = ROOT/sf
    d,wk,note = cover_meta(pdf) if pdf.exists() else (None,None,"pdf missing")
    cur = sorted({x['issue_date'] for x in rs})
    curwk = sorted({x['report_week'] for x in rs})
    if d is None:
        nocover.append((sf,len(rs),cur,note)); continue
    if cur!=[d] or curwk!=[str(wk)]:
        mismatch.append((sf,len(rs),cur,d,curwk,wk))
    else:
        consistent+=1
print(f"\nCONSISTENT (series date == cover Friday): {consistent}")
print(f"\nMISMATCHES: {len(mismatch)}")
for sf,n,cur,d,cw,wk in mismatch:
    print(f"  [{n} rows] series={cur} wk={cw}  -> cover={d} wk={wk}\n      {sf}")
print(f"\nNO COVER DATE: {len(nocover)}")
for sf,n,cur,note in nocover:
    print(f"  [{n}] {cur} {note}\n      {sf}")
