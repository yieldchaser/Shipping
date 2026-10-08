import os, re, csv, glob, json
from collections import defaultdict

SER = 'data/extracted/series'
MD  = 'data/extracted/md'
OUT = {}
DATE_COLS = ('issue_date','date','report_date','reference_date','as_of','snapshot_date')

def max_date_in_csv(path):
    best=None; col=None; n=0
    try:
        with open(path, newline='', encoding='utf-8', errors='replace') as f:
            r=csv.DictReader(f)
            if not r.fieldnames: return None,None,0
            dcols=[c for c in r.fieldnames if c and c.lower() in DATE_COLS]
            if not dcols: return None,None,0
            for row in r:
                n+=1
                for c in dcols:
                    v=(row.get(c) or '').strip()
                    m=re.match(r'(\d{4})-(\d{2})-(\d{2})$', v)
                    if m and '0000' not in v:
                        if best is None or v>best: best=v; col=c
    except Exception as e:
        return None,f'ERR:{e}',0
    return best,col,n

def newest_md_date(mdsrc):
    # derive newest content date from md filenames across all subdirs
    best=None; bestf=None
    for p in glob.glob(os.path.join(MD,mdsrc,'**','*.md'), recursive=True):
        b=os.path.basename(p)
        # try YYYY_MM_DD or DD_MM_YYYY or DD_MM_YYYY patterns
        dates=[]
        for m in re.finditer(r'(20\d{2})[_-](\d{2})[_-](\d{2})', b):
            dates.append(f"{m.group(1)}-{m.group(2)}-{m.group(3)}")
        for m in re.finditer(r'(?<![\d-])(\d{2})[_-](\d{2})[_-](20\d{2})', b):
            d=f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
            if m.group(2) in ('10','11','12') or int(m.group(2))<=12:
                dates.append(d)
        for d in dates:
            if (best is None or d>best): best=d; bestf=b
    return best,bestf

# map series csv -> source by prefix
series_by_src=defaultdict(list)
for p in sorted(glob.glob(os.path.join(SER,'*_series.csv'))):
    b=os.path.basename(p)
    src=b.split('_')[0] if not b.startswith('intermodal_') else 'intermodal'
    series_by_src[src].append(p)

md_dirs=[d for d in os.listdir(MD) if os.path.isdir(os.path.join(MD,d))]

report=[]
for src in sorted(md_dirs):
    mdd, mdf = newest_md_date(src)
    csvs = series_by_src.get(src, [])
    smax=None; scol=None; smaxfile=None; rows=0
    for p in csvs:
        d,c,n = max_date_in_csv(p)
        rows+=n
        if d and (smax is None or d>smax):
            smax=d; scol=c; smaxfile=os.path.basename(p)
    report.append((src, mdd, mdf, smax, scol, smaxfile, len(csvs), rows))

print(f"{'source':22} {'newest_md':11} {'series_max':11} {'#csv':>4} {'rows':>7}  gap?  seriesfile")
for src,mdd,mdf,smax,scol,smaxfile,ncsv,rows in report:
    gap=''
    if mdd and smax and mdd>smax:
        gap='<<< MD NEWER'
    elif mdd and not smax:
        gap='(no date col)'
    print(f"{src:22} {str(mdd):11} {str(smax):11} {ncsv:>4} {rows:>7}  {gap:14} {smaxfile or ''}")
