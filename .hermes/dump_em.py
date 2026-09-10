
import io
src = io.open(r"C:\Users\Dell\Github\Shipping\index.html", encoding="utf-8").read()
lines = src.split("\n")
EMD = chr(0x2014)
out = []
for i, ln in enumerate(lines):
    if EMD in ln:
        out.append("%d\t%s" % (i+1, ln))
io.open(r"C:\Users\Dell\Github\Shipping\.hermes\emdash_lines.txt", "w", encoding="utf-8").write("\n".join(out))
print("written", len(out), "lines")
