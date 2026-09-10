import re, io
p = r"C:\Users\Dell\Github\Shipping\index.html"
src = io.open(p, encoding="utf-8").read()
lines = src.split("\n")

# all occurrences of getCalculatedTooltip
for i, ln in enumerate(lines):
    if "getCalculatedTooltip" in ln:
        print("HIT line", i + 1, ":", ln.strip()[:100])

EMD = chr(0x2014)

# find function header lines (6-indent style may vary) -> find decl with 'function getCalculatedTooltip'
hdr = None
for i, ln in enumerate(lines):
    if re.search(r'\bfunction\s+getCalculatedTooltip\s*\(', ln):
        hdr = i
        break
print("header line:", hdr + 1, repr(lines[hdr][:80]))

# end = first subsequent line that is exactly 6 spaces + '}' (same indent as header)
hindent = len(lines[hdr]) - len(lines[hdr].lstrip(" "))
end = None
for j in range(hdr + 1, len(lines)):
    ln = lines[j]
    if re.match(r'^ {6}\}\s*$', ln):
        end = j
        break
print("end line:", end + 1, repr(lines[end][:40]))
fn = "\n".join(lines[hdr:end + 1])
print("fn lines:", end + 1 - hdr)

cnt = fn.count(EMD)
print("EM DASHES IN FN:", cnt)
for k, ln in enumerate(fn.split("\n")):
    if EMD in ln:
        print("  +%d %s" % (k + hdr + 1, ln.strip()[:160]))

# census in whole file for the 5 jargon phrases + em dash near tooltip strings
for phrase in ["harvest window", "as published on", "Click the tile", "marketapi/TS"]:
    hits = [i + 1 for i, ln in enumerate(lines) if phrase in ln]
    print("PHRASE %r -> lines %s" % (phrase, hits))
allhit = [(i + 1, ln.strip()[:150]) for i, ln in enumerate(lines) if EMD in ln]
print("TOTAL FILE EM DASH LINES:", len(allhit))

# locate 'archived route series not shown'
for i, ln in enumerate(lines):
    if "archived route series not shown" in ln:
        print("S3-FOOTER line", i + 1, ":", ln.strip()[:250])
