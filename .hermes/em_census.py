
import re
p = r"C:\Users\Dell\Github\Shipping\index.html"
src = open(p, encoding="utf-8").read()

# find function bounds
i = src.find("getCalculatedTooltip(")
# locate 'function getCalculatedTooltip' or const
mi = re.search(r'function getCalculatedTooltip\s*\(', src)
print("func decl at char", mi.start(), "line", src.count(chr(10), 0, mi.start())+1)
# find matching close: simple brace counting from first {
b = src.find("{", mi.start())
depth = 0
j = b
in_s = None
while j < len(src):
    c = src[j]
    if in_s:
        if c == "\\\\":
            j += 2
            continue
        if c == in_s:
            in_s = None
    elif c in ('"', "'"):
        in_s = c
    elif c == "{":
        depth += 1
    elif c == "}":
        depth -= 1
        if depth == 0:
            break
    j += 1
fn = src[mi.start():j+1]
print("fn len:", len(fn), "ends line:", src.count(chr(10), 0, j)+1)
em = [k for k, ch in enumerate(fn) if ch == "\\u2014"]
print("em dashes in fn:", len(em))
for k in em[:60]:
    ctx = fn[max(0,k-70):k+70].replace("\\n", " | ")
    line_no = fn.count(chr(10), 0, k) + 1
    print(" ~", line_no, ctx)
open(r"C:\Users\Dell\Github\Shipping\.hermes\fn_bounds.txt","w").write(str((mi.start(), j+1)))
