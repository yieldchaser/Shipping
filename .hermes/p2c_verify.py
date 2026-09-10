import io, json, re

P = r"C:\Users\Dell\Github\Shipping\index.html"
src = io.open(P, encoding="utf-8").read()

# 1. census
for phrase in ["harvest window", "as published on", "Click the tile", "marketapi/TS", "fearnpulse market-api", "cache"]:
    print(f"{phrase!r}: {src.count(phrase)}")

# 2. em dash in fn
lines = src.split("\n")
hdr = next(i for i, l in enumerate(lines) if "function getCalculatedTooltip(" in l)
end = next(j for j in range(hdr + 1, len(lines)) if lines[j].rstrip() == "      }")
fn = "\n".join(lines[hdr:end + 1])
print("fn lines:", end + 1 - hdr, "| em dashes in fn:", fn.count(chr(0x2014)))

# 3. KB coverage
kb = re.search(r"var FDESK_ROUTE_KB = \{(.*?)\n\};", src, re.S).group(1)
kb_keys = set(re.findall(r"'([^']+)':\s*\{\s*what:", kb))
print("KB keys:", len(kb_keys))

def cachepairs(path):
    d = json.load(open(path, encoding="utf-8"))
    return {(s.get("klass", ""), s.get("route", "")) for s in d["series"].values()}, d

tp, _ = cachepairs(r"C:\Users\Dell\Github\Shipping\data\derived\fearnleys_tanker_routes_daily.json")
dp, _ = cachepairs(r"C:\Users\Dell\Github\Shipping\data\derived\fearnleys_dry_routes_daily.json")
need = tp | dp
missing = need - kb_keys
extra = kb_keys - need
print("cache pairs:", len(need), "| missing from KB:", sorted(missing), "| extra:", sorted(extra))

# 4. klass notes coverage
kn = re.search(r"var FDESK_KLASS_NOTES = \{(.*?)\n\};", src, re.S).group(1)
kn_keys = set(re.findall(r"'([^']+)':", kn))
klasses = {k for k, _ in need}
print("klass notes keys:", len(kn_keys), "| missing:", sorted(klasses - kn_keys))

# 5. tooltip branch sanity: count markers
for m in ["fearn-route-state", "fearn-tank-tile", "fearn-tank-klass-tab", "fearn-tank-chart-select"]:
    print(m, "occurrences:", src.count(m))
print("What it is rows:", src.count(">What it is<"))
print("What moves it rows:", src.count(">What moves it<"))
print("What it feeds rows:", src.count(">What it feeds<"))
