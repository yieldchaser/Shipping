import os, glob
from collections import Counter

def main():
    base = 'corpus/02-hellenic'
    streams = os.listdir(base)
    print(f"Streams in {base}: {streams}")

    for s in sorted(streams):
        s_path = os.path.join(base, s)
        if not os.path.isdir(s_path):
            continue
        exts = Counter()
        files = []
        for root, dirs, fnames in os.walk(s_path):
            for fn in fnames:
                ext = os.path.splitext(fn)[1].lower()
                exts[ext] += 1
                files.append(os.path.join(root, fn))
        print(f"\n--- Stream: {s} ({len(files)} total files) ---")
        print(f"Extensions: {dict(exts)}")
        sample_files = [f for f in files if os.path.splitext(f)[1].lower() in ['.pdf', '.html', '.md']][:3]
        for sf in sample_files:
            rel = os.path.relpath(sf, base)
            print(f"  Sample: {rel}")

if __name__ == '__main__':
    main()
