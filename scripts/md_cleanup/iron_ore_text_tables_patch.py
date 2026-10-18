"""Rewrite the printed-table sections of the MMi iron ore MDs from the PDF text layer.

The MD template (run_hellenic_iron_ore_pdf.py) filled these sections from a parser's markdown and
lost or misplaced printed cells. Checked against the PDFs:

  dashboard  freight change / change % and steel-inventory change % always "-"; every row dated
             the issue date (lump, steel and inventories are "Week Ending ..." prints, freight is
             the previous day); 2026 issues print IOPI61 / IOSI61 but the rows say IOPI62 / IOSI62
  ports      Tianjin and Rizhao dropped in ~410 MDs
  futures    the "Change" cells hold the open-positions change; volume, open-positions, day low and
             day high changes are not carried at all

Each section is rebuilt from scripts/extract/publishers/mmi_text_tables.py (copied text, nothing
estimated), in the template's number style. An MD is patched only when every value it already
holds that the rebuild also holds is equal (indices, freight, steel, inventories, futures closing
prices and port inventories), so a misread can never replace a right value. Only the five tables
change; every other byte is kept.

    python scripts/md_cleanup/iron_ore_text_tables_patch.py [--apply] [--limit N] [paths...]
"""
from __future__ import annotations

import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.extract.publishers.mmi_text_tables import (  # noqa: E402
    read_benchmarks, read_dashboard, read_futures, read_port_inventories, signed)

CORPUS_ROOTS = [ROOT] + ([ROOT.parents[2]] if ROOT.parent.name == "worktrees" else [])


def num(s):
    return float(str(s).replace(",", "").replace("%", "").replace("+", "").strip())


def _dp(s):
    """Printed decimals when the print carries 3 (118.715); 2 otherwise (the template style)."""
    frac = str(s).replace("%", "").strip().partition(".")[2]
    return 3 if len(frac) == 3 and frac.isdigit() else 2


def f_num(s):
    return f"{num(s):,.{_dp(s)}f}"


def f_chg(chg, pct):
    """Template style (+1.00) when the print gives a direction; printed text when it does not."""
    if chg is None:                 # blank in the print
        return "not printed"
    s = signed(chg, pct)
    v = f"{abs(num(chg)):,.{_dp(chg)}f}"
    if num(chg) == 0:
        return v
    return ("-" if s.startswith("-") else "+" if s.startswith("+") else "") + v


def f_pct(pct):
    if pct is None:                 # printed as "######", or blank
        return "not printed"
    v = num(pct)
    return f"{v:+.{_dp(pct)}f}%" if v else "0.00%"


def pdf_for(md):
    m = re.search(r'^source_file:\s*"?([^"\n]+\.pdf)', md, re.M)
    if not m:
        return None
    for base in CORPUS_ROOTS:
        cands = [base / m.group(1)] + list((base / "corpus/02-hellenic/iron_ore/pdfs").glob(f"*/{Path(m.group(1)).name}"))
        hit = next((c for c in cands if c.exists()), None)
        if hit:
            return hit
    return None


def table_span(md, heading):
    """(start, end) of the table lines under an exact heading line, or of the template's
    "_No ... reported for this session._" placeholder there; None if neither."""
    m = re.search("^" + re.escape(heading) + r"[^\n]*\n((?:\|[^\n]*\n)+|_No [^\n]* reported for this session\._\n)",
                  md, re.M)
    return (m.start(1), m.end(1)) if m else None


def cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def plain(s):
    return s.replace("**", "").strip()


# ------------------------------------------------------------------------------------------- builders

def card_parts(card):
    """'IOPI62 62% Fe Fines RMB/t' -> ('IOPI62', '62% Fe Fines', 'RMB/t')."""
    line = card["lines"][-1]
    m = re.match(r"^(\S+)\s+(.*?)\s+(\S+/\S+)$", line)
    return (m.group(1), m.group(2), m.group(3)) if m else (line, "", "")


def when(card):
    return card["date"] + (" (holiday)" if card.get("holiday") else "")


def build_dashboard(cards):
    by = lambda pred: next((c for c in cards if pred(" ".join(c["lines"]))), None)  # noqa: E731
    idx_keys = [r"\bIOPI6[12]\b", r"\bIOPI65\b", r"\bIOPI58\b", r"\bIOSI6[12]\b", r"\bIOSI65\b", r"\bIOPLI\b"]
    idx = [by(lambda t, k=k: re.search(k, t)) for k in idx_keys]
    dce = by(lambda t: t.startswith("DCE Iron Ore"))
    sgx = by(lambda t: t.startswith("SGX Iron Ore"))
    shfe = by(lambda t: t.startswith("SHFE Rebar"))
    c3 = by(lambda t: t.startswith("C3,"))
    c5 = by(lambda t: t.startswith("C5,"))
    rebar = by(lambda t: t.startswith("Steel Rebar"))
    hrc = by(lambda t: t.startswith("Steel HRC"))
    port = by(lambda t: t.startswith("Iron Ore Inventory at Chinese Ports"))
    steel_inv = by(lambda t: t.startswith("Steel Inventory in China"))
    need = idx + [dce, sgx, shfe, c3, c5, rebar, hrc, port, steel_inv]
    if any(c is None for c in need):
        return None
    out = {}
    rows = []
    for c in idx:
        name, grade, unit = card_parts(c)
        market = re.sub(r"^Iron (Ore )?", "", c["lines"][0])
        rows.append(f"| **{name}** | {grade} | {market} | {unit} | {f_num(c['value'])} | "
                    f"{f_chg(c['change'], c['change_pct'])} | {f_pct(c['change_pct'])} | {when(c)} |")
    out["### Iron Ore Benchmark Price Indices"] = (
        "| Benchmark Index | Fe Grade | Market / Delivery Point | Unit | Price | Change | Change % | Date |\n"
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n" + "\n".join(rows) + "\n")
    rows = []
    for c, ex in ((dce, "DCE"), (sgx, "SGX"), (shfe, "SHFE")):
        sub = re.sub(r"\s*\([^)]*close\)\s*$", "", c["lines"][-1])          # "I2401 (Jan) RMB/t (3pm close)"
        m = re.match(r"^(.*?)\s+(\S+/\S+)$", sub)
        contract, unit = (m.group(1), m.group(2)) if m else (sub, "")
        product = c["lines"][-2] if len(c["lines"]) >= 2 else ex
        sess = ", ".join(x for x in (c["session"], when(c)) if x)
        rows.append(f"| **{product}, {contract}** | {ex} | {unit} | {f_num(c['value'])} | "
                    f"{f_chg(c['change'], c['change_pct'])} | {f_pct(c['change_pct'])} | {sess} |")
    out["### Exchange Traded Futures & Derivatives"] = (
        "| Contract | Exchange | Unit | Settlement / Close | Change | Change % | Session |\n"
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n" + "\n".join(rows) + "\n")
    spec = [(c3, "C3 Freight", "Tubarao - Qingdao", " USD/t"), (c5, "C5 Freight", "W. Australia - Qingdao", " USD/t"),
            (rebar, "Steel Rebar", "China Domestic", " RMB/t"), (hrc, "Steel HRC", "China Domestic", " RMB/t"),
            (port, "Port Iron Ore Inventory", "35 Chinese Ports", " Mt"), (steel_inv, "Steel Inventory", "China", " Mt")]
    rows = [f"| **{name}** | {cat} | {f_num(c['value'])}{u} | {f_chg(c['change'], c['change_pct'])} | "
            f"{f_pct(c['change_pct'])} | {when(c)} |" for c, name, cat, u in spec]
    out["### Dry Bulk Freight Rates, Spot Steel & Inventories"] = (
        "| Indicator | Category / Route | Value | Change | Change % | Date |\n"
        "| :--- | :--- | :--- | :--- | :--- | :--- |\n" + "\n".join(rows) + "\n")
    return out


def build_ports(inv):
    rows = []
    for r in inv["rows"]:
        b = "**" if r["terminal"].startswith("Total") else ""
        rows.append(f"| {b}{r['terminal']}{b} | {b}{f_num(r['inventory_mt'])}{b} | {b}{f_pct(r['change_pct'])}{b} | "
                    f"{f_num(r['low_12m'])} | {f_num(r['high_12m'])} |")
    wk = f" ({inv['week_ending']})" if inv.get("week_ending") else ""
    return ("| Port Terminal / Survey Area | Inventory (Mt)" + wk + " | Weekly Change % | 12-Month Low | 12-Month High |\n"
            "| :--- | :--- | :--- | :--- | :--- |\n" + "\n".join(rows) + "\n")


def build_futures(fut):
    a, b = fut["columns"]
    head = (f"| Metric | {a['exchange']} {a['contract']} ({a['unit']}) | Change | Change % | "
            f"{b['exchange']} {b['contract']} ({b['unit']}) | Change | Change % |\n"
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |\n"
            f"| Closing Date | {a['closing_date']}{' (holiday)' if a.get('holiday') else ''} | | | "
            f"{b['closing_date']}{' (holiday)' if b.get('holiday') else ''} | | |\n")
    rows = []
    for r in fut["rows"]:
        v = r["cells"]
        rows.append(f"| {r['metric']} | {f_num(v[0])} | {f_chg(v[1], v[2])} | {f_pct(v[2])} | "
                    f"{f_num(v[3])} | {f_chg(v[4], v[5])} | {f_pct(v[5])} |")
    return head + "\n".join(rows) + "\n"


BENCH_HEADING = "## MMi Detailed Iron Ore Benchmark Assessments"
# MD row name -> (printed labels, offset of its 7 cells in the printed row: 0 FOT/seaborne, 7 CFR equivalent)
BENCH_ROWS = {
    "IOPI62_61": (("IOPI62", "IOPI61"), 0), "IOPI62_61_CFR_EQ": (("IOPI62", "IOPI61"), 7),
    "IOPI58": (("IOPI58",), 0), "IOPI58_CFR_EQ": (("IOPI58",), 7),
    "IOPI65": (("IOPI65",), 0), "IOPI65_CFR_EQ": (("IOPI65",), 7),
    "IOPLI62": (("IOPLI62",), 0), "IOPLI62_CFR_EQ": (("IOPLI62",), 7),
    "IOSI62_61": (("IOSI62", "IOSI61"), 0), "IOSI65": (("IOSI65",), 0),
}


def build_benchmarks(table, bench):
    """The benchmark table with every row's 7 numbers replaced by the printed ones (template style:
    price/averages '1,558.00', change '+1.00' (no thousands separator), change % '+0.10%'); name, market,
    grade and unit cells are kept. None when a row cannot be matched to a printed row."""
    lines = table.rstrip("\n").split("\n")
    out = lines[:2]
    for line in lines[2:]:
        c = cells(line)
        name = plain(c[0])
        spec = BENCH_ROWS.get(name)
        lab = next((x for x in (spec[0] if spec else ()) if x in bench), None)
        if lab is None or len(c) != 11:
            return None
        v = bench[lab][spec[1]:spec[1] + 7]
        if all(x is None for x in v):        # the whole side is under the print's HOLIDAY box
            out.append("| " + " | ".join(c[:4] + ["HOLIDAY"] + ["-"] * 6) + " |")
            continue
        fmt = (f_num, lambda x: f"{num(x):+.{_dp(x)}f}", lambda x: f"{num(x):+.{_dp(x)}f}%") + (f_num,) * 4
        new = c[:4] + ["-" if x is None else f(x) for f, x in zip(fmt, v)]   # '-': cell under the box
        if v[0] is None:
            new[4] = "HOLIDAY"
        out.append("| " + " | ".join(new) + " |")
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------------------------- checks

def old_values(table):
    """[(row label, [numbers])] of a table, in order (numbers only; '-' cells skipped)."""
    out = []
    for line in table.splitlines()[2:]:
        c = cells(line)
        vals = []
        for x in c[1:]:
            x = plain(x).replace(" USD/t", "").replace(" RMB/t", "").replace(" Mt", "")
            try:
                vals.append(num(x))
            except ValueError:
                pass
        out.append((plain(c[0]), vals))
    return out


# Near misses checked by eye on the page render, where the printed value is right and the old parse was
# shifted by a row: {issue date: what the render shows}.
RENDER_CHECKED = {
    "2026-06-26": "IOPI61 card prints 710 / 4 / 0.63%; the old MD's 870 / -28 is the IOPLI lump card",
}


def disagreements(pairs):
    """pairs: [((old label, old numbers), (new label, new numbers))]; the first numbers must be equal.
    -> (close, scrambled): a near miss (within 30%) blocks the MD; an old value off by more than that
    is a shifted or concatenated column of the old parse (a change or volume where the price belongs,
    '5670140' for 5670), and the printed value replaces it."""
    close, scrambled = [], []
    for o, n in pairs:
        if o[1] and n[1] and abs(o[1][0] - n[1][0]) > 0.005:
            ratio = o[1][0] / n[1][0] if n[1][0] else 0
            (close if 0.7 <= ratio <= 1.3 else scrambled).append(f"{o[0]}: {o[1][0]} vs {n[1][0]}")
    return close, scrambled


def patch(md, doc, checked=False):
    """-> (new md, problems list, changed section names). checked: the issue is in RENDER_CHECKED."""
    probs, done = [], []
    cards = read_dashboard(doc)
    built = {}
    if cards:
        dash = build_dashboard(cards)
        if dash:
            built.update(dash)
        else:
            probs.append("dashboard cards incomplete")
    else:
        probs.append("dashboard not read")
    inv = read_port_inventories(doc)
    if inv:
        built["## Iron Ore Port Inventories (Million Tonnes)"] = build_ports(inv)
    else:
        probs.append("port inventories not read")
    fut = read_futures(doc)
    if fut:
        built["## Iron Ore Futures Contracts (DCE & SGX)"] = build_futures(fut)
    else:
        probs.append("futures not read")
    bench = read_benchmarks(doc)
    span = table_span(md, BENCH_HEADING)
    if bench and span:
        table = build_benchmarks(md[span[0]:span[1]], bench)
        if table is None:
            probs.append("benchmark rows not matched")
        elif table != md[span[0]:span[1]]:
            # the printed table is authoritative here: the old parse often took the monthly-averages
            # row (March, April, ...) for the daily one, so a disagreement is the old MD's error
            olds = old_values(md[span[0]:span[1]])
            news = dict(old_values(table))
            diff = [f"{o[0]}: {o[1][:1]} -> {news.get(o[0], [None])[:1]}" for o in olds if o[1] != news.get(o[0])]
            probs.append("BENCHMARK REBUILT: " + "; ".join(diff[:3]) + (" ..." if len(diff) > 3 else ""))
            md = md[:span[0]] + table + md[span[1]:]
            done.append(BENCH_HEADING)
    elif span:
        probs.append("benchmarks not read")
    edits = []
    for heading, table in built.items():
        span = table_span(md, heading)
        if not span:
            probs.append(f"no table under {heading}")
            continue
        old = old_values(md[span[0]:span[1]])
        new = old_values(table)
        if heading.startswith("## Iron Ore Port"):
            nd = dict(new)
            pairs = [(o, (o[0], nd[o[0]])) for o in old if o[0] in nd]
        elif heading.startswith("## Iron Ore Futures"):
            # old rows are per exchange (Closing Price is the 4th cell), new rows per metric
            cp = dict(new).get("Closing Price", [])
            ref = {"DCE": cp[:1], "SGX": cp[3:4]}
            pairs = []
            for line in md[span[0]:span[1]].splitlines()[2:]:
                c = [plain(x) for x in cells(line)]
                try:
                    pairs.append(((c[0], [num(c[3])]), (c[0], ref.get(c[0], []))))
                except (ValueError, IndexError):
                    pass
        else:                                # dashboard tables: same rows in the same order
            pairs = list(zip(old, new))
        bad, scrambled = disagreements(pairs)
        if bad and checked:
            probs.append(f"RENDER CHECKED {heading}: " + "; ".join(bad))
        elif bad:
            probs.append(f"DISAGREE {heading}: " + "; ".join(bad))
            continue
        if scrambled:
            probs.append(f"OLD SCRAMBLED {heading}: " + "; ".join(scrambled))
        if md[span[0]:span[1]] != table:
            edits.append((span, table, heading))
    if any(p.startswith("DISAGREE") for p in probs):
        return md, probs, []                # a value disagreement: leave the whole MD for review
    for (a, b), table, heading in sorted(edits, key=lambda e: -e[0][0]):
        md = md[:a] + table + md[b:]
        done.append(heading)
    return md, probs, done


def main():
    apply = "--apply" in sys.argv
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
    paths = [a for a in sys.argv[1:] if a.endswith(".md")]
    if not paths:
        out = subprocess.run(["git", "-c", "core.quotepath=off", "ls-files", "-z", "data/extracted/md/hellenic/iron_ore_pdf"],
                             cwd=ROOT, capture_output=True, text=True, encoding="utf-8").stdout
        paths = sorted(f for f in out.split("\0") if f.endswith(".md"))
    stat = Counter()
    for n, rel in enumerate(paths[:limit], 1):
        path = ROOT / rel
        if not path.exists():               # tracked but removed in the working tree (an archived twin)
            continue
        raw = path.read_bytes().decode("utf-8")
        crlf = "\r\n" in raw
        md = raw.replace("\r\n", "\n")
        if "### Iron Ore Benchmark Price Indices" not in md:
            stat["not the MMi template"] += 1
            continue
        pdf = pdf_for(md)
        if pdf is None:
            stat["no pdf"] += 1
            print(f"NOPDF {rel}")
            continue
        issue = re.search(r'^issue_date:\s*"?([\d-]+)', md, re.M)
        new, probs, done = patch(md, pymupdf.open(pdf), checked=bool(issue) and issue.group(1) in RENDER_CHECKED)
        for p in probs:
            stat["problem: " + p.split(":")[0]] += 1
            print(f"PROB  {Path(rel).name[:70]} | {p}")
        for d in done:
            stat["rewrote " + d] += 1
        if new != md:
            stat["mds changed"] += 1
            if apply:
                path.write_bytes((new.replace("\n", "\r\n") if crlf else new).encode("utf-8"))
        if n % 100 == 0:
            print(n, flush=True)
    for k, v in sorted(stat.items()):
        print(f"{v:6d}  {k}")
    print("(applied)" if apply else "(dry run)")


if __name__ == "__main__":
    main()
