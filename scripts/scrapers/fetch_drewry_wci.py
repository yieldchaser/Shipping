"""
Standalone Drewry World Container Index (WCI) Tracker Scraper.
Extracts the composite index and route-by-route spot assessments from
Drewry's public WCI pages, maintains a clean time-series CSV, and saves
the weekly narrative snapshot as Markdown.

Only uses requests, beautifulsoup4 and pandas (per implementation plan).
"""

import io
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = REPO_ROOT / "data" / "indices"
REPORTS_DIR = REPO_ROOT / "reports" / "drewry"
CHECKPOINT_FILE = REPO_ROOT / "data" / "derived" / "drewry_checkpoint.json"

WCI_PAGE_URLS = [
    "https://www.drewry.co.uk/supply-chain-advisors/supply-chain-expertise/world-container-index-assessed-by-drewry",
    "https://www.drewry.co.uk/trackers-and-indices/latest-trackers-and-indices",
]
RED_SEA_URL = "https://www.drewry.co.uk/red-sea-freight-tracker"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

CSV_COLUMNS = [
    "date",
    "composite_index",
    "shanghai_rotterdam",
    "shanghai_genoa",
    "shanghai_la",
    "shanghai_ny",
    "rotterdam_shanghai",
]

# Route label variants seen across Drewry pages/articles -> CSV column
ROUTE_PATTERNS = [
    (r"shanghai\s*[-\u2013\u2014to]+\s*rotterdam", "shanghai_rotterdam"),
    (r"shanghai\s*[-\u2013\u2014to]+\s*genoa", "shanghai_genoa"),
    (r"shanghai\s*[-\u2013\u2014to]+\s*los\s*angeles", "shanghai_la"),
    (r"shanghai\s*[-\u2013\u2014to]+\s*new\s*york", "shanghai_ny"),
    (r"rotterdam\s*[-\u2013\u2014to]+\s*shanghai", "rotterdam_shanghai"),
]
# The composite's unit is printed right after the level, so requiring the unit
# is what separates a LEVEL from the change ("increased 4.7% or $255 to
# $5,726.99 per 40ft container"). MEASURED on 228 archived pages: the previous
# pattern forbade a PERIOD anywhere in its gap, so every page whose headline
# change carries a decimal failed the headline and fell through to the
# publisher's own YEAR-TO-DATE AVERAGE sentence ("The average composite index
# of the WCI ... year-to-date, is $5,143 per 40ft container") - the wrong level
# on 49 pages, 6 of them present in the displayed CSV (up to +21.0% out).
# Averages are now excluded by word, not by the absence of a period.
COMPOSITE_PAT = re.compile(
    r"(?:world\s*container\s*index|wci|composite\s*index)[\s\S]{0,220}?"
    r"\$\s*([\d,]+(?:\.\d+)?)\s*(?:per|/)?\s*(?:40\s*(?:ft|foot)|40')",
    re.I,
)
# "average" / "year-to-date" / "YTD" mark the publisher's own average statement,
# never the week's level.
COMPOSITE_AVG_RX = re.compile(r"average|year[\s-]?to[\s-]?date|\bytd\b", re.I)
ROUTE_VALUE_PAT = re.compile(
    r"([a-z][a-z\s]*?)\s*[-\u2013\u2014to]+\s*([a-z][a-z\s]*?)\D{0,60}?"
    r"\$\s*([\d,]+(?:\.\d+)?)",
    re.I,
)


def load_checkpoint():
    if CHECKPOINT_FILE.exists():
        try:
            return json.loads(CHECKPOINT_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_checkpoint(cp):
    CHECKPOINT_FILE.parent.mkdir(parents=True, exist_ok=True)
    CHECKPOINT_FILE.write_text(json.dumps(cp, indent=2), encoding="utf-8", newline="\n")


def get_with_backoff(url, attempts=3):
    delay = 2.0
    last_exc = None
    for _ in range(attempts):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            if resp.status_code == 200:
                return resp
            if resp.status_code in (429, 503):
                time.sleep(delay)
                delay *= 2
                continue
            print(f"    [!] HTTP {resp.status_code} for {url}")
            return None
        except Exception as exc:
            last_exc = exc
            time.sleep(delay)
            delay *= 2
    if last_exc:
        print(f"    [!] Failed {url}: {last_exc}")
    return None


def clean_number(raw):
    try:
        return float(re.sub(r"[^0-9.]", "", raw))
    except Exception:
        return None


def extract_assessments(html_text):
    """Pull composite + route values from tables and free text."""
    soup = BeautifulSoup(html_text, "html.parser")
    flat_text = soup.get_text(" \n", strip=True)

    values = {}

    for m in COMPOSITE_PAT.finditer(flat_text):
        val = clean_number(m.group(1))
        if not val:
            continue
        if COMPOSITE_AVG_RX.search(flat_text[max(0, m.start() - 90):m.start()]):
            continue            # the publisher's own average, not the week's level
        values["composite_index"] = val
        break

    value_rx = re.compile(r"\$\s*([\d,]+(?:\.\d+)?)")
    # A LEVEL is introduced by "to" ("...to $4,453"), but this publisher also
    # writes "to reach $11,173", "and REACHED $1,052 which is lowest since Jun
    # 2016" and "held steady at $7,904" - MEASURED: the past tense was missing
    # from the alternation, so ""nosedived 10% or $120 ... and reached $1,052""
    # returned the $120 CHANGE on 2023-09-28 and $220 on 2021-07-22. The absolute CHANGE
    # ("increased 17% or $1,331 to $9,158") is nearer the label and would be a
    # 10x-class error, so an introduced value outranks a nearer one that is not.
    # A LEVEL is not always introduced by the bare to|at|reach: 2021-05-20
    # prints "soared 10% or $889 and reached a new high of $9,865" and
    # "surged 7% - an increase of $350 to touch $5,605". Neither "new high of"
    # nor "to touch" was in the alternation, so BOTH lanes returned the CHANGE
    # ($889 / $350) - a change-vs-level error in the plausible direction, which
    # no recall check can see (both numbers ARE on the page). The introducer is
    # matched at the END of a look-back window, so the window width only decides
    # how much PHRASE may precede the $; a "to" earlier in the sentence cannot
    # leak in, because of the trailing anchor.
    to_rx = re.compile(
        r"\b(?:to\s+touch(?:es|ed)?|to|at|reach(?:es|ed)?|touch(?:es|ed)?|"
        r"(?:a\s+)?new\s+(?:high|low)\s+of)\s*$",
        re.I,
    )
    # Width of the introducer look-back. 8 chars held a bare "to $X" but not
    # "a new high of $X" (13). MEASURED over every cached page: see
    # scratch/wci/diff_vs_pv.py.
    INTRO_WIN = 32
    # (pv16) a bare (un-$'d) level number: thousands-comma form or >=4 digits.
    # NOTE: write the boundaries as \b INSIDE an r-string - a plain string turns
    # \b into a literal 0x08 BACKSPACE (the trap COMPOSITE_AVG_RX already hit).
    BARE_RX = re.compile(r"(?<!\$)(?<![\d.,])(\d{1,3}(?:,\d{3})+|\d{4,})(?![\d.,])")
    BARE_UNIT_RX = re.compile(r"\s*(?:per\b|feu\b|/|40\s*ft|container|box|for\b)", re.I)
    # "increased 17% or $1,331" - the CHANGE, never the level.
    or_rx = re.compile(r"\bor\s*$", re.I)
    sent_rx = re.compile(r"(?<=[.!?])\s+")
    # Clause boundaries. MEASURED on 231 archived pages (scratch/wci/census_shapes.py):
    # 75 multi-lane sentences are one-clause-per-lane ("A dropped 8% or $999 to
    # reach $11,173 and B fell 5% or $739 to $15,110"), where distance alone
    # crosses the boundary.
    split_rx = re.compile(
        r"(?:;\s*|,\s*|\s+)(?:and|but|while|whereas|however|conversely|also|"
        r"similarly|likewise|furthermore|moreover|followed\s+by|"
        r"on\s+the\s+other\s+hand)\b|;\s*|\n", re.I)
    # ANY route named in a sentence, tracked or not: a "respectively" list can
    # name a lane we do not keep, and dropping it shifts every ordinal in it.
    # SEPARATOR CLASS INCLUDES THE PLAIN HYPHEN (2026-09-30): the 2021-era pages
    # write "rates on Shanghai-New York and Shanghai-Los Angeles soared 39% and
    # 34% to $11,180 and $8,548 per feu, respectively". With the hyphen absent
    # NO label matched, so the ordinal rule never fired and proximity handed Los
    # Angeles the level of New York. MEASURED: 30 hyphenated lane tokens on the
    # 2021 pages; the non-lane forms (East-West, Intra-Asia, Ro-Ro, Y-o-Y) are
    # rejected by is_route_mention (port vocabulary), not by the separator.
    label_rx = re.compile(
        r"\b([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?)\s*(?:to|[\u2013\u2014-])\s*"
        r"([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?)")
    # Continuation of a lane list after a conjunction: ", and|or|& [from|to] Port".
    cont_rx = re.compile(
        r"\s*(?:\band\b|\bor\b|,|&)\s*(?:(?:from|to)\s+)?"
        r"([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?)")
    # A separator followed by a port is a NEW PAIR, not a continuation: it marks
    # the captured words as an ORIGIN ("...and Shanghai to Rotterdam").
    pair_sep_rx = re.compile(r"\s*(?:to|[\u2013\u2014-])\s*[A-Z][A-Za-z]+")
    # The ORIGIN CAN BE ELIDED on a re-statement of the same lane family:
    # "...rates from Shanghai to New York falling 6% to $2,735 per 40ft container
    # and rates to Los Angeles reducing 4% to $2,089" (2025-11-27). Used ONLY as
    # a monotone fallback that fills a lane still EMPTY after the sentence's own
    # logic - it can never move or overwrite a value another rule found.
    elided_rx = re.compile(
        r'\b(?:rates|those)\s+(?:to|on|from|for)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?)')
    # The publisher's own port vocabulary, DERIVED from ROUTE_PATTERNS (never
    # hardcoded). A match whose every word is not a port name is prose
    # ("According to Drewry"), not a lane, and must not consume an ordinal.
    PORT_WORDS = set()
    for _pat, _col in ROUTE_PATTERNS:
        PORT_WORDS.update(re.findall(r"[a-z]{2,}", _pat))
    max_dist = 120

    def is_route_mention(seg):
        words = re.findall(r"[A-Za-z]+", seg)
        return bool(words) and all(w.lower() in PORT_WORDS for w in words)

    def label_col(seg):
        for pat, col in ROUTE_PATTERNS:
            if re.search(pat, seg, re.I):
                return col
        return None

    def lane_col(origin, dest):
        """The column "<origin> to <dest>" names, or None. DERIVED from
        ROUTE_PATTERNS (the publisher's own lane vocabulary), never hardcoded."""
        probe = "%s to %s" % (origin, dest)
        for pat, col in ROUTE_PATTERNS:
            if re.fullmatch(pat, probe, re.I):
                return col
        return None

    def sentences(text):
        """[(sentence, offset_into_text)] - the delimiter stays on its left."""
        out, pos = [], 0
        for part in sent_rx.split(text):
            idx = text.find(part, pos)
            if idx < 0:
                idx = pos
            out.append((part, idx))
            pos = idx + len(part)
        return out

    def clauses(sent):
        """[(start, end)] runs of one sentence between clause conjunctions."""
        out, pos = [], 0
        for m in split_rx.finditer(sent):
            out.append((pos, m.start()))
            pos = m.end()
        out.append((pos, len(sent)))
        return out

    def gap(le, ls, c):
        """Chars between a label and a value."""
        if c[0] >= le:
            return c[0] - le
        if c[1] <= ls:
            return ls - c[1]
        return 0

    def assign_route_values(text, pairs):
        """Give each route the value its OWN sentence and clause give it.

        Three measured defects drove this shape; all three were on pages whose
        whole assessment is ONE text line, so none is a line-splitting problem.

        (a) SENTENCE SCOPE. 2024-04-18: "...Shanghai to New York decreased 5%
            or $257 to $4,453 ... Shanghai to Los Angeles dropped 4% or $147 to
            $3,487 ... rates on Shanghai to Rotterdam and Shanghai to Genoa
            declined 2% to $2,989 and $3,577 per feu respectively. Conversely,
            rates from Rotterdam to New York increased by 3% or $67 to $2,291."
            Pairing k-th label with k-th value across the paragraph gave Genoa
            the $2,291 that belongs to Rotterdam-New York.
        (b) ORDINAL OVER UNTRACKED LANES. 2024-04-25: "...from Rotterdam to New
            York and Shanghai to Los Angeles decreased 3% to $2,214 and $3,395
            respectively." Rotterdam-New York is not a column we keep, so
            pairing only TRACKED labels gave Los Angeles the $2,214.
        (c) CLAUSE SCOPE. 2026-07-30: "spot rates declined 6% to $5,630 per 40ft
            container from Shanghai to Genoa and decreased 3% to $4,677 per 40ft
            container on Shanghai to Rotterdam." Genoa's own level is the
            $5,630 of its clause; the $4,677 of the NEXT clause sits closer.
        """
        for sent, off in sentences(text):
            local = []
            for col, ls, le in pairs:
                if ls < off or le > off + len(sent):
                    continue
                local.append((col, ls - off, le - off))
            if not local:
                continue
            cands = [(mo.start(), mo.end(), clean_number(mo.group(1)))
                     for mo in value_rx.finditer(sent)]
            cands = [c for c in cands if c[2] is not None]
            # (pv16) BARE LEVEL: the publisher sometimes prints a LEVEL with NO
            # dollar sign - "...rates from Shanghai to Los Angeles fell 3% or
            # $224 to 7,288 per 40ft box." (2024-07-18). value_rx requires a $,
            # so 7,288 was invisible and the lane took the CHANGE ($224), which
            # the numeric spread gate then rejected (max/min = 6074/224 > 5).
            # A bare number is admitted ONLY when (a) the level introducer
            # (to|at|reach|touch|new high of) ends immediately before it, (b) it
            # is followed by a price unit, and (c) it has a thousands comma or
            # >=4 digits - so a week number, a percentage or a year cannot
            # qualify. MEASURED over all 230 cached captures: exactly 1 page
            # moves, 1 value, 224 -> 7288, and that is the level the page prints.
            for mo in BARE_RX.finditer(sent):
                if not to_rx.search(sent[max(0, mo.start() - INTRO_WIN):mo.start()]):
                    continue
                if not BARE_UNIT_RX.match(sent[mo.end():]):
                    continue
                _bv = clean_number(mo.group(1))
                if _bv is None:
                    continue
                cands.append((mo.start(), mo.end(), _bv))
            cands.sort(key=lambda c: c[0])
            if not cands:
                continue
            low = sent.lower()
            # A LEADING PROSE WORD IS NOT PART OF THE LANE. "On Shanghai - New
            # York and Shanghai - Rotterdam, rates fell by 4% to ..." (2023-02-23)
            # matched group1 as "On Shanghai" and was then thrown away by the
            # port-vocabulary guard, so the sentence counted ONE lane instead of
            # two and the respectively rule could not fire. Trim leading non-port
            # words off the match and keep the rest.
            # A SECOND DESTINATION THAT SHARES THE ORIGIN is written as a BARE
            # PORT after a conjunction - "rates from Shanghai to New York and
            # Los Angeles increasing 9% to $9,507 and $6,802 per 40ft container,
            # respectively" (2026-08-20). label_rx needs a separator before the
            # port, so the second lane was INVISIBLE: the sentence counted ONE
            # lane and its value was dropped. MEASURED: 8 of the 26 cached 2026
            # capture pages leave at least one lane unparsed this way. A
            # continuation is taken ONLY when it starts IMMEDIATELY after the
            # label and is not itself the origin of a new pair ("...and Shanghai
            # to Rotterdam" keeps its own label), and its column is DERIVED from
            # ROUTE_PATTERNS by reconstructing "<origin> to <dest>".
            all_labels = []
            label_origins = {}
            for m in label_rx.finditer(sent):
                seg = m.group(0)
                while seg and not is_route_mention(seg):
                    parts = seg.split(None, 1)
                    if len(parts) < 2:
                        seg = ''
                        break
                    seg = parts[1]
                if not (seg and is_route_mention(seg)):
                    continue
                all_labels.append((m.end() - len(seg), m.end(), label_col(seg)))
                _parts = re.split(r"\s*(?:to|[\u2013\u2014-])\s*", seg)
                _origin, _dest = _parts[0], _parts[-1]
                label_origins[(m.end() - len(seg), m.end())] = (_origin, _dest)
                rest = sent[m.end():]
                while True:
                    cm = cont_rx.match(rest)
                    if not cm:
                        break
                    dseg = cm.group(1)
                    after = rest[cm.end():]
                    if (not is_route_mention(dseg)
                            or dseg.strip().lower() == _dest.strip().lower()
                            or pair_sep_rx.match(after)):
                        break
                    all_labels.append((m.end() + cm.start(1), m.end() + cm.end(1),
                                       lane_col(_origin, dseg)))
                    rest = after
            to_vals = [c for c in cands
                       if to_rx.search(sent[max(0, c[0] - INTRO_WIN):c[0]])]
            parallel = (len(all_labels) >= 2
                        and max(l[1] for l in all_labels) <= cands[0][0])
            if len(all_labels) >= 2 and ('respectively' in low or parallel):
                free = [c for c in cands
                        if not or_rx.search(sent[max(0, c[0] - 8):c[0]])]
                # (d) TO-ANCHORED SUFFIX. Both the CHANGE and the LEVEL can be
                # printed as dollars - "grew $617 and $539 to $9,165 and $11,719"
                # (2021-07-01), "dropped 10% or $167 and $127 to $1,531 and
                # $1,172" (2023-09-21) - so none of the three pools above holds
                # exactly k members and the row used to fall through to proximity,
                # which handed the second lane the first lane's level. The LEVELS
                # are the consecutive run that STARTS at the value the publisher
                # introduced with to|at|reach.
                tail = [c for c in cands if to_vals and c[0] >= to_vals[0][0]]
                vals = (to_vals if len(to_vals) == len(all_labels)
                        else free if len(free) == len(all_labels)
                        else cands if len(cands) == len(all_labels)
                        else tail if len(tail) == len(all_labels) else None)
                if vals:
                    for (_ls, _le, col), (_vs, _ve, val) in zip(all_labels, vals):
                        if col and col not in values:
                            values[col] = val
                    continue
                if vals is None and low.count("respectively") >= 2:
                    # (pv17) TWO PARALLEL `respectively` LISTS in one sentence.
                    # 2024-12-19: "rates from Shanghai to Genoa and Rotterdam to Shanghai
                    # decreased 2% to $5,424 per feu and $508 per feu, respectively, and those
                    # from New York to Rotterdam and Shanghai to Rotterdam shrank 1% to $824
                    # per feu and $4,819 per feu, respectively, whereas those from Los Angeles
                    # to Shanghai remained stable." MEASURED: five labels against four values -
                    # one label is the untracked New York-Rotterdam, one is the value-less tail
                    # lane - so NO pool above matches the label count and the clause fallback
                    # handed each lane its own list's FIRST value (rotterdam_shanghai 5424,
                    # should be 508; shanghai_rotterdam 824, should be 4,819).
                    # Each `respectively` CLOSES a list, so the ordinal mapping is scoped to the
                    # part BEFORE that marker, never to the whole sentence. Fires ONLY when the
                    # pools above failed (vals is None), fills EMPTY columns only, and bails
                    # unless every list part has as many labels (tracked or not) as values.
                    _marks = [m.end() for m in re.finditer(r"respectively", low)]
                    _bnds = [0] + _marks + [len(sent)]
                    _plan, _ok = [], True
                    for _i in range(len(_marks)):
                        _a, _b = _bnds[_i], _bnds[_i + 1]
                        _pl = [(ls, le, col) for (_ls, _le, col) in all_labels
                               if _a <= _ls and _le <= _b]
                        _pv = [c for c in free if _a <= c[0] < _b]
                        if not _pl or len(_pl) != len(_pv):
                            _ok = False
                            break
                        _plan.extend(zip(_pl, _pv))
                    if _ok and any(_p[0][2] for _p in _plan):
                        for (_ls, _le, col), (_vs, _ve, val) in _plan:
                            if col and col not in values:
                                values[col] = val
            cls = clauses(sent)
            for ci, (a, b) in enumerate(cls):
                cl_lab = [(ls, le, col) for col, ls, le in local
                          if ls >= a and le <= b]
                cl_val = [c for c in cands if a <= c[0] < b]
                if not cl_lab or not cl_val:
                    continue
                if len(cl_lab) == 1:
                    ls, le, col = cl_lab[0]
                    lev = [c for c in cl_val
                           if to_rx.search(sent[max(0, c[0] - INTRO_WIN):c[0]])]
                    if not lev and ci + 1 < len(cls):
                        # "...diminished 3% or $16 and stood at $500": the
                        # clause carries only the CHANGE, and the level is the
                        # value of the next lane-less clause.
                        na, nb = cls[ci + 1]
                        if not [1 for _c, l2, l3 in local
                                if l2 >= na and l3 <= nb]:
                            lev = [c for c in cands if na <= c[0] < nb
                                   and to_rx.search(sent[max(0, c[0] - INTRO_WIN):c[0]])]
                    pool = lev or cl_val
                    pick = min(pool, key=lambda c: gap(le, ls, c))
                    if col not in values:
                        values[col] = pick[2]
                elif len(cl_lab) == len(cl_val):
                    for (ls, le, col), (_vs, _ve, val) in zip(
                            sorted(cl_lab, key=lambda t: t[0]),
                            sorted(cl_val, key=lambda c: c[0])):
                        if col not in values:
                            values[col] = val
            scored = []
            for col, ls, le in local:
                if col in values:
                    continue
                for vs, ve, val in cands:
                    dist = gap(le, ls, (vs, ve, val))
                    if dist <= max_dist:
                        pref = 1 if to_rx.search(sent[max(0, vs - INTRO_WIN):vs]) else 0
                        scored.append((-pref, dist, col, vs, val))
            scored.sort(key=lambda t: (t[0], t[1], t[2], t[3]))
            used_cols, used_vals = set(), set()
            for _pref, dist, col, vs, val in scored:
                if col in used_cols or vs in used_vals:
                    continue
                used_cols.add(col)
                used_vals.add(vs)
                if col not in values:
                    values[col] = val
            # ELIDED ORIGIN, monotone: only a lane still EMPTY after the whole
            # sentence's logic can be filled here, so no existing assignment can
            # move or be overwritten. The value is the level of the elided
            # mention's OWN clause, taken nearest to it.
            for cm in elided_rx.finditer(sent):
                dseg = cm.group(1)
                if not is_route_mention(dseg) or pair_sep_rx.match(sent[cm.end():]):
                    continue
                for ls, le, col in all_labels:
                    if col is None or col not in values:
                        continue
                    origin, ldest = label_origins.get((ls, le), (None, None))
                    if not origin or dseg.strip().lower() == (ldest or '').strip().lower():
                        continue
                    ncol = lane_col(origin, dseg)
                    if ncol is None or ncol in values:
                        continue
                    cl = None
                    for ca, cb in clauses(sent):
                        if ca <= cm.start(1) and cm.end(1) <= cb:
                            cl = (ca, cb)
                            break
                    pool = [c for c in cands
                            if (cl is None or cl[0] <= c[0] < cl[1])
                            and to_rx.search(sent[max(0, c[0] - INTRO_WIN):c[0]])]
                    if pool:
                        values[ncol] = min(pool, key=lambda c: gap(cm.end(1), cm.start(1), c))[2]
    # Rendered tables first (label cell next to the value cell)
    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])]
            row_text = " | ".join(cells)
            pairs = []
            for pat, col in ROUTE_PATTERNS:
                if col in values:
                    continue
                rm = re.search(pat, row_text, re.I)
                if rm:
                    pairs.append((col, rm.start(), rm.end()))
            if pairs:
                assign_route_values(row_text, pairs)

    # Free-text fallback for routes the tables did not carry. EVERY mention of a
    # route in the page is a candidate, scored inside its own sentence; a mention
    # that carries no number ("...and New York to Rotterdam remained stable")
    # therefore cannot block a later mention that does.
    if len(values) < len(CSV_COLUMNS):
        for sent, _off in sentences(flat_text):
            pairs = []
            for pat, col in ROUTE_PATTERNS:
                if col in values:
                    continue
                rm = re.search(pat, sent, re.I)
                if rm:
                    pairs.append((col, rm.start(), rm.end()))
            if pairs:
                assign_route_values(sent, pairs)

    # ==============================================================
    # pv15 CANDIDATE - additive and monotone: fills EMPTY columns only.
    # A sentence may name the origin in its OPENING lane and then re-state
    # the lanes with the origin ELIDED, as a "respectively" list:
    #   2026-02-12 "Spot rates from Shanghai to major US destinations
    #   declined slightly due to low cargo volume, with spot rates to Los
    #   Angeles and New York falling 1% to $2,214 and $2,800 per 40ft
    #   container, respectively."
    # MEASURED on that page: ROUTE_PATTERNS matches NOTHING in the sentence
    # and label_rx matches NOTHING either (its "destination" is the
    # lowercase GROUP phrase "major US destinations", not a capitalised
    # port pair), so the sentence never entered the lane logic at all and
    # both printed levels were dropped. The origin is printed too - the
    # module's own elided_rx already captures "Shanghai" from "rates from
    # Shanghai"; it was simply never used AS an origin.
    # ==============================================================
    if len(values) < len(CSV_COLUMNS):
        for sent, _off in sentences(flat_text):
            if "respectively" not in sent.lower():
                continue
            if any(re.search(p, sent, re.I) for p, _c in ROUTE_PATTERNS):
                continue                  # the normal path owns this sentence
            origin, dest_start, dests = None, None, []
            for em in elided_rx.finditer(sent):
                if not is_route_mention(em.group(1)):
                    continue
                toks = em.group(0).split()
                conn = toks[1].lower() if len(toks) > 1 else ""
                if conn in ("from", "on"):
                    if origin is None:
                        origin = em.group(1)
                    continue
                if conn in ("to", "for") and not dests:
                    dests.append(em.group(1))
                    dest_start = em.start(1)
                    rest = sent[em.end():]
                    while True:
                        cm = cont_rx.match(rest)
                        if not cm or not is_route_mention(cm.group(1)):
                            break
                        dests.append(cm.group(1))
                        rest = rest[cm.end():]
            if not origin or not dests:
                continue
            cols = [lane_col(origin, d) for d in dests]
            if any(c is None for c in cols) or any(c in values for c in cols):
                continue
            vals = []
            for mo in value_rx.finditer(sent):
                if mo.start() < (dest_start or 0):
                    continue
                if or_rx.search(sent[max(0, mo.start() - INTRO_WIN):mo.start()]):
                    continue              # a CHANGE, not a level
                n = clean_number(mo.group(1))
                if n is not None:
                    vals.append(n)
            if len(vals) != len(cols):
                continue
            for c, val in zip(cols, vals):
                if c not in values:
                    values[c] = val

    # ==============================================================
    # pv18 STABILITY GUARD. A tracked lane the publisher prints as "remained
    # stable" (no level, no "$") must not be handed ANOTHER lane's level by the
    # respectively/ordinal logic.
    # MEASURED 2024-12-05: "...rates from Rotterdam to Shanghai and Rotterdam to
    # New York reduced 1% to $514 and $2,649 per feu, respectively whereas those
    # from Los Angeles to Shanghai and Shanghai to New York remained stable."
    # shanghai_ny was assigned 2,649 - a level the page prints ONCE and gives to
    # Rotterdam-New York. The page prints NO level for Shanghai-New York.
    # It fires only when EVERY mention of that lane on the page is a stability
    # mention with no "$" in its own clause, so "remained stable at $6,818"
    # (a real print) is untouched.
    # ==============================================================
    STABLE_RX = re.compile(
        r"remain(?:s|ed)?\s+(?:stable|steady|unchanged|flat)"
        r"|hover(?:s|ed)?\s+around"
        r"|held\s+steady"
        r"|were\s+unchanged"
        r"|no\s+change"
        r"|at\s+the\s+previous\s+week'?s?\s+level",
        re.I,
    )
    stability_cleared = []
    for _pat, _col in ROUTE_PATTERNS:
        if _col not in values or values[_col] is None:
            continue
        _mentions = list(re.finditer(_pat, flat_text, re.I))
        if not _mentions:
            continue
        _quiet = True
        for _m in _mentions:
            _win = flat_text[_m.end():_m.end() + 160]
            _cut = _win.find('.')
            _win = _win if _cut < 0 else _win[:_cut]
            if ('$' in _win) or not STABLE_RX.search(_win):
                _quiet = False
                break
        if _quiet:
            stability_cleared.append((_col, values[_col]))
            values[_col] = None

    # As-of date on the page
    page_date = None
    dm = re.search(
        r"assessment\s+for[^0-9]{0,40}?\b(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})\b",
        flat_text,
        re.I,
    ) or re.search(
        r"(?:as\s*of|published|assessment\s*date|dated)[:\s]*([A-Za-z]+ \d{1,2},? \d{4})",
        flat_text,
        re.I,
    ) or re.search(r"\b(\d{1,2}\s+[A-Za-z]+\s+\d{4})\b", flat_text)
    if dm:
        for fmt in ("%B %d, %Y", "%B %d %Y", "%d %B %Y", "%d %b %Y"):
            try:
                page_date = datetime.strptime(dm.group(1).replace(",", ""), fmt.replace(",", "")).strftime("%Y-%m-%d")
                break
            except ValueError:
                continue
    if not page_date:
        page_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    return values, page_date, flat_text


WAYBACK_CDX_URL = "https://web.archive.org/cdx/search/cdx"
# WCI pages to look up in the Wayback CDX index (2011 -> present).
WCI_WAYBACK_URL_PATTERNS = [
    "drewry.co.uk/supply-chain-advisors/supply-chain-expertise/world-container-index-assessed-by-drewry*",
    "drewry.co.uk/*world-container-index*",
    "drewry.co.uk/*container-index*",
]

# Build F: synthetic baseline removed. This stub is kept only for backward
# compatibility with older imports; it NEVER synthesizes values.
def generate_canonical_wci_history():
    print("    [!] generate_canonical_wci_history() is deprecated (Build F): no values synthesized.")
    return pd.DataFrame(columns=CSV_COLUMNS)


def fetch_wayback_cdx(url_pattern, from_year=2011, limit=200):
    """Query the Wayback CDX API for snapshot list. Returns list of dicts.

    Fail-soft: per-request timeout 30s, max 3 attempts with backoff.
    Returns [] on persistent archive.org errors (e.g. GitHub Actions IP
    throttling) so the caller can commit partial results instead of wedging.
    """
    params = {
        "url": url_pattern,
        "from": str(from_year),
        "output": "json",
        "filter": ["statuscode:200", "mimetype:text/html"],
        "fl": "timestamp,original,statuscode,digest",
        "collapse": "digest",
        "limit": str(limit),
    }
    delay = 2.0
    for attempt in range(1, 4):
        try:
            resp = requests.get(WAYBACK_CDX_URL, params=params, headers=HEADERS, timeout=30)
            if resp.status_code == 200:
                try:
                    data = resp.json()
                except Exception as exc:
                    print(f"    [!] CDX JSON decode failed for {url_pattern}: {exc}")
                    return []
                if not data or len(data) < 2:
                    return []
                header, rows = data[0], data[1:]
                return [dict(zip(header, r)) for r in rows]
            if resp.status_code in (429, 503):
                print(f"    [!] CDX HTTP {resp.status_code} for {url_pattern} (attempt {attempt}/3)")
            else:
                print(f"    [!] CDX HTTP {resp.status_code} for {url_pattern}")
                return []
        except Exception as exc:
            print(f"    [!] CDX query failed for {url_pattern} (attempt {attempt}/3): {exc}")
        if attempt < 3:
            time.sleep(delay)
            delay *= 2
    return []


def backfill_drewry_wayback(from_year=2011, limit_per_pattern=200, max_snapshots=50, sleep_s=0.5,
                            deadline_s=540, max_consec_fail=10):
    """Backfill assessed WCI history via the Wayback Machine CDX API.

    - Covers drewry.co.uk WCI pages from from_year -> present.
    - Bounds work: newest max_snapshots only (default 50), per-request
      timeout 30s via get_with_backoff(), max 3 attempts with backoff,
      overall deadline_s budget + consecutive-failure circuit breaker so
      archive.org throttling (ConnectTimeout / Connection refused on
      GitHub Actions IPs) fails soft instead of wedging the job.
    - Parses each snapshot with extract_assessments(); only real assessed
      values are kept. Missing weeks are left absent (frontend renders gaps
      with spanGaps:true); values are NEVER invented.
    - Upserts into data/indices/drewry_wci_historical.csv with dedup + sort,
      preserving the canonical header (date, composite_index, ...).
    - Idempotent: re-running yields the same sorted, deduped CSV.
    - Fail-soft: returns partial (csv_path, n) on timeout/circuit-break;
      never raises on Wayback errors.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = DATA_DIR / "drewry_wci_historical.csv"
    t_start = time.monotonic()

    snapshots = []
    seen_ts = set()
    for pat in WCI_WAYBACK_URL_PATTERNS:
        print(f"[+] CDX query: {pat} (from {from_year}, limit {limit_per_pattern})")
        rows = fetch_wayback_cdx(pat, from_year=from_year, limit=limit_per_pattern)
        print(f"    found {len(rows)} snapshots")
        for r in rows:
            key = (r.get("timestamp"), r.get("digest") or r.get("original"))
            if key in seen_ts:
                continue
            seen_ts.add(key)
            snapshots.append(r)
    snapshots.sort(key=lambda r: r.get("timestamp", ""))
    if len(snapshots) > max_snapshots:
        # Keep newest snapshots: bounds runtime and prefers recent assessed
        # prints over deep-history (e.g. flaky 2022 snapshots).
        snapshots = snapshots[-max_snapshots:]
        print(f"    capped to newest {len(snapshots)} snapshots")

    collected = []
    consec_fail = 0
    for idx, snap in enumerate(snapshots, 1):
        if time.monotonic() - t_start > deadline_s:
            print(f"    [!] Wayback deadline ({deadline_s}s) reached at {idx}/{len(snapshots)}; "
                  f"keeping partial {len(collected)} rows (fail-soft).")
            break
        ts = snap.get("timestamp", "")
        orig = snap.get("original", "")
        wb_url = f"https://web.archive.org/web/{ts}id_/{orig}"
        try:
            resp = get_with_backoff(wb_url, attempts=3)
            if not resp:
                consec_fail += 1
                if consec_fail >= max_consec_fail:
                    print(f"    [!] {consec_fail} consecutive Wayback failures; archive.org likely "
                          f"throttling this IP. Aborting with partial {len(collected)} rows (fail-soft).")
                    break
                continue
            values, page_date, _ = extract_assessments(resp.text)
            if not values.get("composite_index") and len(values) < 2:
                consec_fail += 1
                if consec_fail >= max_consec_fail:
                    print(f"    [!] {consec_fail} consecutive unparseable snapshots; aborting "
                          f"with partial {len(collected)} rows (fail-soft).")
                    break
                continue
            consec_fail = 0
            row = {col: values.get(col) for col in CSV_COLUMNS}
            # Prefer the assessed page date; fall back to snapshot date.
            if page_date:
                row["date"] = page_date
            else:
                try:
                    row["date"] = datetime.strptime(ts[:8], "%Y%m%d").strftime("%Y-%m-%d")
                except Exception:
                    continue
            collected.append(row)
        except Exception as exc:
            print(f"    [!] snapshot parse failed {wb_url}: {exc}")
            consec_fail += 1
            if consec_fail >= max_consec_fail:
                print(f"    [!] circuit-breaker tripped; keeping partial {len(collected)} rows.")
                break
            continue
        finally:
            if sleep_s:
                time.sleep(sleep_s)

    print(f"[+] Wayback: parsed {len(collected)} assessed snapshots")
    if not collected:
        print("[!] No assessed WCI values recovered from Wayback; CSV left unchanged.")
        return csv_path, 0

    new_df = pd.DataFrame(collected)
    csv_path = upsert_wci_rows(new_df)
    return csv_path, len(collected)


def _wci_cell(x):
    """Normalise a CSV cell for comparison: NaN/None -> ''."""
    if x is None:
        return ""
    s = str(x).strip()
    return "" if s in ("nan", "None", "NaT") else s


# Diagnostics of the most recent upsert. Populated, never hand-edited; the
# weekly job prints it so a merge can never discard or replace a row silently.
UPSERT_REPORT = {}


def upsert_wci_rows(new_df):
    """Idempotent upsert: merge new rows, dedup by date (last wins), sort, keep header.

    The WCI is assessed on a THURSDAY, so a date that is not a Thursday is a
    parse artefact - and dedup-by-date alone would let such a row overwrite a
    real print silently. This upsert therefore REPORTS what it did (printed as
    ``[wci-upsert]`` lines and kept in ``UPSERT_REPORT``): how many rows the
    date dedupe discarded, which dates had a STORED value replaced, and any
    date that is not a Thursday. Measured 2026-10-01 on the shipped file:
    121 rows, all Thursdays, dates unique and strictly increasing.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = DATA_DIR / "drewry_wci_historical.csv"
    if csv_path.exists():
        try:
            existing = pd.read_csv(csv_path)
        except Exception:
            existing = pd.DataFrame(columns=CSV_COLUMNS)
    else:
        existing = pd.DataFrame(columns=CSV_COLUMNS)
    combined = pd.concat([existing, new_df], ignore_index=True) if len(new_df) else existing
    # Keep only canonical columns (extra keys dropped), preserve header order.
    for col in CSV_COLUMNS:
        if col not in combined.columns:
            combined[col] = None
    combined = combined[CSV_COLUMNS]
    combined["date"] = pd.to_datetime(combined["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    combined = combined.dropna(subset=["date"]).sort_values("date", kind="stable")

    # Date dedupe, last row wins (the new row, since it is concatenated last).
    # Track collisions so a replaced print is named rather than swallowed.
    keep = []
    at = {}
    shadowed = []
    for _idx, r in combined.iterrows():
        d = r["date"]
        if d in at:
            prev = keep[at[d]]
            diffs = {c: (_wci_cell(prev.get(c)), _wci_cell(r.get(c)))
                     for c in CSV_COLUMNS if _wci_cell(prev.get(c)) != _wci_cell(r.get(c))}
            if diffs:
                shadowed.append((d, diffs))
            keep[at[d]] = r
        else:
            at[d] = len(keep)
            keep.append(r)
    out = pd.DataFrame(keep, columns=CSV_COLUMNS) if keep else pd.DataFrame(columns=CSV_COLUMNS)

    non_thursday = []
    for d in out["date"].tolist():
        try:
            if datetime.fromisoformat(str(d)).weekday() != 3:
                non_thursday.append(str(d))
        except Exception:
            non_thursday.append(str(d))

    UPSERT_REPORT.clear()
    UPSERT_REPORT.update({
        "rows_in": int(len(combined)),
        "rows_out": int(len(out)),
        "rows_discarded_by_date_dedupe": int(len(combined) - len(out)),
        "shadowed_dates": shadowed,
        "non_thursday_dates": non_thursday,
    })
    print(f"[wci-upsert] {len(combined)} row(s) in -> {len(out)} out "
          f"({len(combined) - len(out)} discarded by the date dedupe)")
    if shadowed:
        print(f"[wci-upsert] [!] {len(shadowed)} date(s) had a STORED value REPLACED by this merge:")
        for d, diffs in shadowed[:5]:
            print(f"[wci-upsert] [!]   {d}: " + "; ".join(f"{c} {a!r} -> {b!r}" for c, (a, b) in diffs.items()))
    if non_thursday:
        # The publisher assesses on Thursdays; a non-Thursday date is a parse
        # artefact, never a real print.
        print(f"[wci-upsert] [!] {len(non_thursday)} row(s) are NOT a Thursday: {non_thursday[:8]}")

    out.to_csv(csv_path, index=False, lineterminator="\n")
    return csv_path


def update_csv(row=None, extra_df=None):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = DATA_DIR / "drewry_wci_historical.csv"
    if csv_path.exists():
        try:
            df = pd.read_csv(csv_path)
        except Exception:
            df = pd.DataFrame(columns=CSV_COLUMNS)
    else:
        df = pd.DataFrame(columns=CSV_COLUMNS)

    frames = [df]
    if row and row.get("date"):
        frames.append(pd.DataFrame([row]))
    if extra_df is not None and len(extra_df):
        frames.append(extra_df)
    if len(frames) > 1:
        df = pd.concat(frames, ignore_index=True)

    return upsert_wci_rows(df) if len(df) else upsert_wci_rows(pd.DataFrame(columns=CSV_COLUMNS))


def _parse_backfill_args(argv):
    """Parse optional backfill bounds. Defaults keep weekly runs bounded."""
    from_year, limit_per_pattern, max_snapshots = 2011, 200, 50
    for i, a in enumerate(argv):
        try:
            if a == "--from-year" and i + 1 < len(argv):
                from_year = int(argv[i + 1])
            elif a == "--limit-per-pattern" and i + 1 < len(argv):
                limit_per_pattern = max(1, int(argv[i + 1]))
            elif a == "--max-snapshots" and i + 1 < len(argv):
                max_snapshots = max(1, int(argv[i + 1]))
        except ValueError:
            continue
    return from_year, limit_per_pattern, max_snapshots


def main():
    print("=" * 80)
    print("  DREWRY WORLD CONTAINER INDEX INGESTION")
    print("=" * 80)

    if "--backfill" in sys.argv:
        from_year, limit_per_pattern, max_snapshots = _parse_backfill_args(sys.argv)
        print(f"\n[+] Wayback backfill requested (--backfill): {from_year} -> present, "
              f"newest {max_snapshots} (limit {limit_per_pattern}/pattern), no synthesis.")
        try:
            csv_path, n = backfill_drewry_wayback(
                from_year=from_year, limit_per_pattern=limit_per_pattern,
                max_snapshots=max_snapshots)
        except Exception as exc:
            print(f"    [!] Wayback backfill failed (fail-soft): {exc}")
            csv_path = upsert_wci_rows(pd.DataFrame(columns=CSV_COLUMNS))
            n = 0
        print(f"\n[OK] Wayback backfill complete: {n} assessed snapshots -> {csv_path.relative_to(REPO_ROOT)}")
        return 0

    checkpoint = load_checkpoint()
    primary = None
    narrative = ""
    for url in WCI_PAGE_URLS:
        print(f"\n[+] Fetching {url}")
        resp = get_with_backoff(url)
        if not resp:
            continue
        values, page_date, flat_text = extract_assessments(resp.text)
        print(f"    parsed values: {values} (page date: {page_date})")
        if values.get("composite_index") or len(values) >= 2:
            primary = {"url": url, "values": values, "date": page_date}
            narrative = "\n".join(
                line.strip() for line in flat_text.splitlines()
                if re.search(r"wci|container index|\$[\d,]+|red sea", line, re.I) and len(line.strip()) > 25
            )[:6000]
            break

    if not primary:
        print("\n[!] Live WCI page JS-rendered or offline; attempting limited Wayback backfill (no synthesis).")
        print("    Missing weeks are left as gaps (frontend spanGaps:true); no values invented.")
        try:
            # Fail-soft fallback: bounded (newest 50) so a blocked archive.org
            # never wedges the weekly job; partial results are committed.
            csv_path, n = backfill_drewry_wayback(
                limit_per_pattern=200, max_snapshots=50, sleep_s=0.5)
            print(f"\n[OK] Time-series backfilled: {csv_path.relative_to(REPO_ROOT)} ({n} assessed snapshots)")
        except Exception as exc:
            print(f"    [!] Wayback backfill failed: {exc}; ensuring header-only CSV exists.")
            csv_path = upsert_wci_rows(pd.DataFrame(columns=CSV_COLUMNS))
            print(f"\n[OK] Time-series preserved: {csv_path.relative_to(REPO_ROOT)}")
        return 0

    row = {col: primary["values"].get(col) for col in CSV_COLUMNS}
    row["date"] = primary["date"]
    csv_path = update_csv(row)
    print(f"\n[OK] Time-series updated: {csv_path.relative_to(REPO_ROOT)}")

    year_dir = REPORTS_DIR / primary["date"][:4]
    year_dir.mkdir(parents=True, exist_ok=True)
    md_path = year_dir / f"{primary['date']}_drewry_wci.md"
    md_content = f"""---
title: "Drewry World Container Index Snapshot - {primary['date']}"
date: "{primary['date']}"
source: "drewry"
category: "containers"
source_url: "{primary['url']}"
---

# Drewry World Container Index Snapshot - {primary['date']}

## Assessed Values ($/40ft)

| Metric | Value |
| --- | --- |
""" + "\n".join(
        f"| {col} | {primary['values'].get(col, '')} |" for col in CSV_COLUMNS[1:] if col != "date"
    ) + f"""

## Page Commentary

{narrative}
"""
    md_path.write_text(md_content, encoding="utf-8", errors="ignore", newline="\n")
    print(f"[OK] Narrative saved: {md_path.relative_to(REPO_ROOT)}")

    checkpoint["last_success_date"] = primary["date"]
    checkpoint["last_values"] = primary["values"]
    save_checkpoint(checkpoint)

    # Red Sea tracker narrative (best effort, never fatal)
    resp = get_with_backoff(RED_SEA_URL)
    if resp:
        rs_soup = BeautifulSoup(resp.text, "html.parser")
        rs_text = rs_soup.get_text("\n", strip=True)
        rs_lines = [
            line.strip() for line in rs_text.splitlines()
            if re.search(r"suez|transit|cape of good hope|diversion|red sea", line, re.I) and len(line.strip()) > 30
        ][:60]
        if rs_lines:
            rs_path = year_dir / f"{primary['date']}_drewry_red_sea_tracker.md"
            rs_path.write_text(
                f"""---
title: "Drewry Red Sea Freight Tracker Notes - {primary['date']}"
date: "{primary['date']}"
source: "drewry"
category: "containers"
source_url: "{RED_SEA_URL}"
---

# Drewry Red Sea Freight Tracker Notes - {primary['date']}

""" + "\n\n".join(rs_lines),
                encoding="utf-8",
                errors="ignore", newline="\n"
            )
            print(f"[OK] Red Sea notes saved: {rs_path.relative_to(REPO_ROOT)}")

    print("\n[DONE] Drewry ingestion complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
