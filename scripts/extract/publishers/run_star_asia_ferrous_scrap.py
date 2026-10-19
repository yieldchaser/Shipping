"""
Star Asia ferrous scrap prices from the "Sub-Continent and Turkey ferrous scrap markets insight" prose.

The section is prose, so a regex cannot tell which grade/origin a price belongs to (the old regex extractor labelled
European HMS as shredded, African HMS as US shredded, PNS as HMS 90:10 ... on about half its rows). Each issue's
section is sent to Nace Extract (one item per printed price, grade/origin as worded), and every item is gated on the
source before it becomes a row:
  - the price is printed verbatim in the section, and its numbers are the row's numbers;
  - the grade and origin words occur in the sentence that carries the price.
Items failing the gate are dropped (and listed by --report); nothing is estimated or computed from FX.

Used by orchestrate_incremental_ingest.extract_star_asia for each new issue (rows_for_md), and as a backfill over all
Star Asia MDs:
    python scripts/extract/publishers/run_star_asia_ferrous_scrap.py [--cache DIR] [--write] [--report]

Output: data/extracted/series/star_asia_ferrous_scrap_series.csv
"""
from __future__ import annotations

import argparse
import csv
import glob
import io
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[3]
MD_DIR = ROOT / "data" / "extracted" / "md" / "star_asia"
SERIES_CSV = ROOT / "data" / "extracted" / "series" / "star_asia_ferrous_scrap_series.csv"

COLS = ["issue_date", "report_week", "country", "origin", "grade", "price_text", "currency", "price_low", "price_high",
        "usd_low", "usd_high", "price_type", "terms", "destination_port", "source_file"]
KEY = ["issue_date", "country", "origin", "grade", "price_text"]

START = re.compile(r"(sub-?cont?i?nent.*scrap|ferrous scrap markets? insight|global ferrous scrap insight)", re.I)
STOP = re.compile(r"^(HMS 1/2|COMMODITIES|BUNKER|EXCHANGE RATES|TIDE|Commodities|Bunker|Exchange Rates|Tide Dates|Iron Ore|"
                  r"Industrial Metal|Crude Oil|Disclaimer|DISCLAIMER|Ship Recycling|SHIP RECYCLING|Demolition|DEMOLITION)\b")

SCHEMA = {"type": "object", "properties": {"quotes": {"type": "array", "items": {"type": "object", "properties": {
    "country": {"type": "string", "description": "Market the paragraph is about: India, Pakistan, Bangladesh, Turkiye (Turkey), or other as printed"},
    "origin": {"type": "string", "description": "Origin of the scrap exactly as worded (e.g. UK, European, Australian, US West Coast, Brazilian). Empty if not stated."},
    "grade": {"type": "string", "description": "Scrap grade exactly as worded for THIS price (e.g. shredded, HMS 80:20, HMS 1&2, PNS, turnings, H2, bonus, domestic scrap). Empty if not stated."},
    "price_text": {"type": "string", "description": "The price exactly as printed, e.g. US$405-410/t, USD416/ton, PKR 132,000-134,000/t"},
    "price_kind": {"type": "string", "description": "offer, bid, deal, indication, workable or domestic"},
    "terms_port": {"type": "string", "description": "Terms and port as printed, e.g. CFR Mundra. Empty if none."},
    "sentence": {"type": "string", "description": "The full sentence containing the price, verbatim"}}}}}}
INSTR = ("One item per printed scrap price (ferrous scrap only; skip rebar, billet, freight, iron ore, coal and other "
         "non-scrap prices, and skip price changes such as 'up US$5/t'). Attribute grade and origin only from the words that "
         "grammatically belong to that price; never carry a grade or origin from a neighbouring price. Copy text verbatim.")

COUNTRY = {"india": "India", "pakistan": "Pakistan", "bangladesh": "Bangladesh", "turkiye": "Turkey", "turkey": "Turkey",
           "turkish": "Turkey", "türkiye": "Turkey", "turkiye (turkey)": "Turkey", "turkey (turkiye)": "Turkey"}
COUNTRY_ADJ = {"indian": "India", "pakistani": "Pakistan", "bangladeshi": "Bangladesh", "turkish": "Turkey"}
NOT_SCRAP = re.compile(r"\b(rebar|billet|freight|iron ore|coal|coke|steel price|bar)s?\b", re.I)
WORD = re.compile(r"[a-z0-9]+")


def _norm(line: str) -> str:
    return line.strip().strip("|").strip().lstrip("#").strip().strip("*").strip()


def section(md_text: str) -> Optional[str]:
    """The ferrous-scrap prose of one issue (page markers, table rules and images dropped; table cells kept as text)."""
    ls = md_text.replace("\r\n", "\n").split("\n")
    s = next((i for i, l in enumerate(ls) if START.search(_norm(l)) and len(_norm(l)) < 140
              and (l.startswith("#") or l.startswith("|") or len(_norm(l)) < 80)), None)
    if s is None:
        return None
    body = []
    for l in ls[s + 1:]:
        n = _norm(l)
        if STOP.match(n) or (l.startswith("# ") and not re.search(r"scrap|india|pakistan|bangladesh|turk", l, re.I)):
            break
        if re.fullmatch(r"\|[\s:|-]*\|?", l.strip()) or re.match(r"^## Page \d+", l) or l.startswith("!["):
            continue
        body.append(" ".join(c.strip() for c in l.strip().strip("|").split("|")) if l.startswith("|") else l)
    text = "\n".join(body).strip()
    return text or None


def nace_quotes(text: str, name: str) -> List[Dict[str, Any]]:
    """Nace Extract over the section text; keys rotate on exhausted credit, transient errors retry."""
    import tempfile
    from nace_sdk import NaceClient
    sys.path.insert(0, str(ROOT / "scripts" / "extract"))
    from nace_backend import nace_keys
    keys = nace_keys()
    if not keys:
        raise RuntimeError("ferrous scrap: no NACE_API_KEY configured")
    tmp = Path(tempfile.mkdtemp(prefix="fe_")) / (name[:80] + ".txt")
    tmp.write_text(text + "\n", encoding="utf-8")
    last: Optional[Exception] = None
    for key in keys:
        for attempt in range(4):
            try:
                with NaceClient(api_key=key) as c:
                    up = c.documents.upload(str(tmp), path="ferrous/" + tmp.name, on_conflict="new_version")
                    src = {"type": "workspace_file", "workspace_id": up.workspace_id, "file_id": up.file_id}
                    job = c.documents.extract(src, schema=SCHEMA, instructions=INSTR, citations={"enabled": False},
                                              wait_seconds=60)
                    t0 = time.time()
                    while job.status not in ("succeeded", "failed", "cancelled") and time.time() - t0 < 600:
                        job = c.jobs.wait(job.job_id)
                    if job.status != "succeeded":
                        raise RuntimeError(f"nace job {job.job_id} {job.status}")
                    return ((job.result or {}).get("data") or {}).get("quotes") or []
            except Exception as e:  # noqa: BLE001 - next key on no credit, retry transient
                last = e
                if "402" in str(e) or "insufficient_credit" in str(e).lower():
                    break
                time.sleep(10 * (attempt + 1))
    raise RuntimeError(f"ferrous scrap: Nace extract failed for {name}: {last}")


CUR_RE = r"(?:US\$|USD|\$|PKR|BDT|INR|Rs\.?|TRY|Euro|EUR)"
NUM = r"(\d[\d,]*(?:\.\d+)?)"
UNIT = r"(?:\s*/\s*(?:t|ton|tonne|mt)\b|\s*per\s+(?:metric\s+)?ton(?:ne)?\b)?"
# a printed price: one value or a range, with an optional bracketed USD equivalent ("PKR 132,000-134,000/t (US$477-484/t)")
MENTION = re.compile(rf"({CUR_RE})\s*{NUM}{UNIT}(?:\s*(?:-|to|and)\s*{CUR_RE}?\s*{NUM}{UNIT})?"
                     rf"(?:\s*\(\s*(?:US\$|USD|\$)\s*{NUM}{UNIT}(?:\s*-\s*(?:US\$|USD|\$)?\s*{NUM}{UNIT})?\s*\))?", re.I)
SINGLE = re.compile(rf"({CUR_RE})\s*{NUM}{UNIT}", re.I)
GENERIC = {"scrap", "scraps", "imported", "import", "material", "materials", "cargo", "cargoes", "deep", "sea", "origin",
           "the", "of", "and", "mix", "grade", "grades", "domestic", "local", "offers", "bulk", "containerised",
           "containerized", "quality", "high", "s", "type"}


def _clean(s: str) -> str:
    """Markdown escapes off, dashes plain, whitespace single."""
    s = re.sub(r"\\([$*_\[\]()#.\-])", r"\1", s or "")
    s = re.sub(r"[ \t\r\f\v]+", " ", s.replace("\u2013", "-").replace("\u2014", "-"))
    return re.sub(r" ?\n[\s]*", "\n", s).strip()   # paragraph breaks kept: they end a sentence


def _num(s: Optional[str]) -> Any:
    return float(s.replace(",", "")) if s else ""


def _cur(s: str) -> str:
    s = s.upper().rstrip(".")
    return {"US$": "USD", "$": "USD", "RS": "INR", "EURO": "EUR"}.get(s, s)


def _key(m: re.Match) -> Tuple:
    g = m.groups()
    return (_cur(g[0]), _num(g[1]), _num(g[2]) if len(g) > 2 and g[2] else _num(g[1]))


def _mentions(text: str) -> List[Tuple[Tuple, int, int]]:
    """Every printed price (ranges and each single value) as (key, start, end) in the cleaned text."""
    out = [(_key(m), m.start(), m.end()) for m in MENTION.finditer(text)]
    out += [(_key(m), m.start(), m.end()) for m in SINGLE.finditer(text)]
    return out


def _sentence(text: str, i: int) -> str:
    """The sentence holding position i (a period ends a sentence only after two letters, digits or a bracket,
    so U.S. / H.M.S. abbreviations do not split)."""
    starts = [0] + [m.end() for m in re.finditer(r"(?<=[A-Za-z0-9)%*/\"]{2}[.!?])\s+|\n", text)]
    s = max(x for x in starts if x <= i)
    e = min([x for x in starts if x > i] + [len(text)])
    return text[s:e]


def gate(q: Dict[str, Any], text: str) -> Tuple[Optional[Dict[str, Any]], str]:
    """(row fields, '') when the item is supported by the printed text, else (None, reason).
    The price must be a printed price (same currency and numbers); the row keeps the PRINTED wording of it. A label
    (grade, origin, terms, port) is kept only when its words (generic words aside) occur in the printed sentence that
    carries the price; otherwise it is left blank, so the price survives without a guessed label."""
    text = _clean(text)
    pt = _clean(q.get("price_text") or "")
    grade, origin = _clean(q.get("grade") or ""), _clean(q.get("origin") or "")
    if origin.lower() in ("null", "none", "n/a"):
        origin = ""
    if not pt:
        return None, "no price"
    if NOT_SCRAP.search(grade):
        return None, "not scrap"
    m = MENTION.search(pt)
    if not m:
        return None, "price unparsed"
    k = _key(m)
    cands = [(s, e) for kk, s, e in _mentions(text) if kk == k]
    if not cands:
        return None, "price not printed"
    sent_hint = _clean(q.get("sentence") or "").lower().replace("*", "")[:50]
    q_country = COUNTRY.get((q.get("country") or "").strip().lower(), "")
    country_words = {"India": ("india",), "Pakistan": ("pakistan",), "Bangladesh": ("bangladesh",),
                     "Turkey": ("turk",)}.get(q_country, ())

    def proven(v: str, sent: str) -> bool:
        return all(w in sent for w in WORD.findall(v.lower()) if w not in GENERIC)

    def score(se: Tuple[int, int]) -> Tuple[int, bool, bool]:
        sent = _sentence(text, se[0]).lower()
        return (proven(grade, sent) + proven(origin, sent), bool(sent_hint) and sent_hint in sent.replace("*", ""),
                any(w in sent for w in country_words))

    # the printed occurrence whose sentence proves the most labels (ties: the sentence Nace quoted)
    s, e = max(cands, key=score)
    sent = _sentence(text, s).lower()
    blanked = [lab for lab, v in (("grade", grade), ("origin", origin)) if v and not proven(v, sent)]
    grade = grade if proven(grade, sent) else ""
    origin = origin if proven(origin, sent) else ""
    printed = text[s:e]
    g = MENTION.match(printed).groups()
    cur, low = _cur(g[0]), _num(g[1])
    high = _num(g[2]) if g[2] else low
    usd_low = usd_high = ""
    if cur == "USD":
        usd_low, usd_high = low, high
    elif g[3]:
        usd_low = _num(g[3])
        usd_high = _num(g[4]) if g[4] else usd_low
    tp = _clean(q.get("terms_port") or "")
    mt = re.match(r"^(CFR|CIF|FOB|ex-?works|delivered)\b\s*(.*)$", tp, re.I)
    terms, port = (mt.group(1), mt.group(2)) if mt else ("", tp)
    port = re.sub(r"^(into|at|to)\s+", "", port).strip().rstrip(".,")
    if terms and not proven(terms, sent):
        terms = ""
    if port and not proven(port, sent):
        blanked.append("port")
        port = ""
    terms = terms.upper() if terms.lower() in ("cfr", "cif", "fob") else terms.capitalize()
    country = (q.get("country") or "").strip()
    country = COUNTRY.get(country.lower(), country)
    # a cross-market aside inside another country's paragraph: "...showing Bangladeshi bids for US HMS near US$370/t"
    other = {COUNTRY_ADJ[a.lower()] for a in re.findall(r"\b(Bangladeshi|Pakistani|Indian|Turkish)\s+(?:bids|buyers|mills|importers|market)\b", sent, re.I)}
    if len(other) == 1 and country not in other:
        country = other.pop()
    return {"country": country, "origin": origin, "grade": grade,
            "price_text": printed, "currency": cur, "price_low": low, "price_high": high, "usd_low": usd_low,
            "usd_high": usd_high, "price_type": (q.get("price_kind") or "").strip().capitalize(), "terms": terms,
            "destination_port": port, "_sentence": _sentence(text, s)}, ("blanked " + "/".join(blanked)) if blanked else ""


def _meta(md_text: str, k: str) -> str:
    m = re.search(rf'^{k}:\s*"?([^"\n]+)', md_text, re.M)
    return m.group(1).strip() if m else ""


def rows_from_quotes(md_text: str, quotes: List[Dict[str, Any]], text: str) -> Tuple[List[Dict[str, Any]], List[Tuple]]:
    base = {"issue_date": _meta(md_text, "issue_date"), "report_week": int(_meta(md_text, "report_week") or 0),
            "source_file": Path(_meta(md_text, "source_file")).name}
    rows, dropped, seen = [], [], set()
    for q in quotes:
        r, why = gate(q, text)
        if r is None or why:
            dropped.append((why, q.get("price_text"), q.get("grade"), q.get("origin")))
        if r is None:
            continue
        k = tuple(str(r[c]).lower() for c in KEY[1:])
        if k in seen:
            continue
        seen.add(k)
        rows.append(dict(base, **r))
    return rows, dropped


def rows_for_md(md_text: str, name: str) -> List[Dict[str, Any]]:
    """CI entry: one new issue's gated rows ([] when the issue has no ferrous section)."""
    text = section(md_text)
    if not text:
        return []
    rows = rows_from_quotes(md_text, nace_quotes(text, name), text)[0]
    return [{c: r[c] for c in COLS} for r in rows]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--cache", help="dir of <md stem>.json Nace results ({'data': {'quotes': [...]}}); missing ones are fetched")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--report", action="store_true", help="list every dropped item")
    a = ap.parse_args()
    cache = Path(a.cache) if a.cache else None
    out, n_drop = [], 0
    for md in sorted(glob.glob(str(MD_DIR / "*" / "*.md"))):
        t = open(md, encoding="utf-8").read()
        text = section(t)
        if not text:
            continue
        stem = Path(md).stem
        cf = cache / f"{stem}.json" if cache else None
        if cf and cf.exists():
            quotes = (json.loads(cf.read_text(encoding="utf-8")).get("data") or {}).get("quotes") or []
        else:
            quotes = nace_quotes(text, stem)
            if cf:
                cf.write_text(json.dumps({"data": {"quotes": quotes}}, indent=1), encoding="utf-8")
        rows, dropped = rows_from_quotes(t, quotes, text)
        out += rows
        n_drop += len(dropped)
        print(f"{_meta(t, 'issue_date')} {stem[:60]:60} quotes {len(quotes):3} rows {len(rows):3} dropped {len(dropped)}")
        if a.report:
            for d in dropped:
                print("     -", *d, sep=" | ")
    out.sort(key=lambda r: r["issue_date"])
    print(f"{len(out)} rows, {n_drop} items dropped by the gate")
    if a.write:
        s = io.StringIO()
        w = csv.DictWriter(s, fieldnames=COLS, lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(out)
        SERIES_CSV.write_bytes(s.getvalue().encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
