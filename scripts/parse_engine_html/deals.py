"""Deal-line parser for VesselsValue weekly S&P lines.

Typical line:
  Handy BC Lancaster Strait (37,000 DWT, Jan 2013, Hyundai Mipo) sold to unknown German buyers for
  USD 16.20 mil, VV Value USD 16.37 mil - Inc TC.

Anything that does not parse into class + spec + VV value is returned as a failure with a reason; the caller
must list it verbatim (never drop it).
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

# --------------------------------------------------------------------------------------------------
# Vessel-class vocabulary (built from a survey of every VV issue 2021-2026; see `vocab` CLI command).
# class := [count] BASE [plural] [SUFFIX ...] [(qualifier)]
# --------------------------------------------------------------------------------------------------
CLASS_BASES = (
    "Post[ -]?Panamax", "Sub[ -]?Panamax", "New Panamax", "Small Clean", "Small Chemical",
    "Handy/Feedermax", "J19 Stainless Steel", "25K Stainless Steel",
    "Capesize", "Newcastlemax", "Kamsarmax", "Panamax", "Ultramax", "Supramax", "Handymax", "Handysize",
    "Handy", "Feedermax", "Aframax", "Suezmax", "VLCC", "ULCV", "LR1", "LR2", "LR3", "MR1", "MR2", "MR",
)
CLASS_SUFFIXES = ("Chemical", "Clean", "Tankers?", "BCs?", "Bulkers?", "Containers?", "Conts?")
CLASS_QUALIFIERS = r"(?:Chem[^)]*|Open Hatch|Newcastlemax|Clean|Dirty|Chip|Methanol|Bunkering)"

_PLURAL = r"(?:es|s|['’]s)?"
CLASS_RE = re.compile(
    r"^(?:(?P<count>\d+(?:/\d+)?)\s*x?\s+)?(?:(?P<resale>Resale)\s+)?"
    r"(?P<cls>(?:" + "|".join(CLASS_BASES) + r")" + _PLURAL +
    r"(?:\s+(?:" + "|".join(CLASS_SUFFIXES) + r"))*"
    r"(?:\s*\(" + CLASS_QUALIFIERS + r"\))?)"
    r"(?=\s|$|\(|(?-i:[A-Z]))", re.I)

NUM = r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
SPEC_RE = re.compile(
    rf"^(?:c\.\s*)?(?P<size>{NUM}\s?[kK]?(?:\s*(?:/|-|–|&|and|to)\s*{NUM}\s?[kK]?)*)\s*"
    rf"(?P<unit>DWT|TEU|CBM|cbm)?(?P<flag>\s+(?:resale|newbuild)s?)?\s*(?:,\s*(?P<rest>.*))?$", re.I | re.S)
UNIT = r"(?:mill?|mi|bil|bn|m)"
VV_RE = re.compile(
    rf"VV\s+(?P<eb>en[\s-]?bloc\s+)?values?\s*(?:USD\s*)?(?P<v>{NUM})(?:\s*(?:USD\s*)?(?P<u>{UNIT})(?![A-Za-z0-9]|\.\d))?(?![A-Za-z0-9]|\.\d)",
    re.I)
VV_EXTRA_RE = re.compile(rf"^\s*,?\s*(?:and|/|&)\s*(?:USD\s*)?{NUM}", re.I)
# price phrases, most specific first; `tail` is the text up to the next comma
PRICE_RES = (
    re.compile(rf"\b(?:for|worth)\s+(?:a\s+total\s+of\s+)?(?:USD\s*)?(?P<p>{NUM})\s*(?P<u>{UNIT})(?![A-Za-z0-9]|\.\d)(?P<tail>[^,]*)", re.I),
    re.compile(rf"\bfor\s+(?P<p>{NUM})\s*USD\s*(?P<u>{UNIT})(?![A-Za-z0-9]|\.\d)(?P<tail>[^,]*)", re.I),
    re.compile(rf"\b(?:for|worth)\s+(?:a\s+total\s+of\s+)?USD\s*(?P<p>{NUM})(?P<u>)(?![A-Za-z0-9]|\.\d)(?P<tail>[^,]*)", re.I),
    re.compile(rf"\bfor\s+(?P<p>{NUM})(?P<u>)(?![A-Za-z0-9]|\.\d)(?P<tail>[^,]*)", re.I),
    re.compile(rf"\s(?P<p>{NUM})\s*(?P<u>{UNIT})(?![A-Za-z0-9]|\.\d)(?P<tail>[^,]*)", re.I),
)
UNDISC_PRICE_RE = re.compile(
    r"\b(?:for\s+)?(?:an?\s+)?(?:undisclosed|unknown|not disclosed)\s+price\b|[“\"]undisclosed[”\"]|\bundisclosed$",
    re.I)
DASH_CLASS = "–—−�\\-"
TAIL_RE = re.compile(rf"^\s*\.?\s*(?:[{DASH_CLASS}]+\s*(?P<c>.*?))?\s*\.?\s*$", re.S)
EN_BLOC_RE = re.compile(r"\b(?:in\s+an?\s+)?en[\s-]?bloc(?:\s+deal)?\b", re.I)
ACTION_RE = re.compile(r"^(sold|on subs|ordered|acquired|purchased|bought)\b", re.I)
WHO_RE = re.compile(r"(?:^|\s)(to|by)\s+", re.I)
MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
UNIT_MULT = {"mil": 1.0, "mill": 1.0, "mi": 1.0, "m": 1.0, "bil": 1000.0, "bn": 1000.0}


@dataclass
class Deal:
    raw: str
    sector: str = ""
    vessel_class: str = ""
    vessel_name: str = ""
    n_vessels: int | None = None
    size: float | None = None
    size_text: str = ""
    size_unit: str = ""
    built: str | None = None
    built_text: str = ""
    yard: str = ""
    action: str = ""
    buyer: str = ""
    seller: str = ""
    price_raw: str = ""
    price_usd_m: float | None = None
    vv_value_raw: str = ""
    vv_value_usd_m: float | None = None
    premium_pct: float | None = None
    comments: str = ""            # text after the dash, verbatim
    qualifiers: str = ""          # sale terms embedded in the sentence ("DD Due", "inc TC", ...)
    flags: list[str] = field(default_factory=list)

    @property
    def comments_all(self) -> str:
        return "; ".join(x for x in (self.comments, self.qualifiers) if x)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["comments_all"] = self.comments_all
        return d


@dataclass
class ParseResult:
    deal: Deal | None
    reason: str = ""


def norm_line(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("\xa0", " ")).strip()


def is_deal_candidate(text: str) -> bool:
    """A paragraph that carries a VV valuation, or a priced sale with a vessel spec, is a deal line."""
    if VV_RE.search(text):
        return True
    return bool(re.search(r"\bUSD\b", text) and re.search(r"\b\d[\d,]*\s*(?:DWT|TEU|CBM)\b", text))


def _to_float(num: str) -> float:
    return float(num.replace(",", ""))


def _size_value(size_text: str) -> float | None:
    m = re.fullmatch(rf"({NUM})\s?([kK])?", size_text.strip())
    if not m:
        return None
    v = _to_float(m.group(1))
    return v * 1000 if m.group(2) else v


def _built_iso(text: str) -> str | None:
    t = text.strip()
    m = re.fullmatch(r"([A-Za-z]{3,9})\.?\s+(\d{4})", t)
    if m and m.group(1)[:3].lower() in MONTHS:
        return f"{m.group(2)}-{MONTHS[m.group(1)[:3].lower()]:02d}"
    if re.fullmatch(r"\d{4}", t):
        return t
    return None


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip(" ,.;")


def parse_deal_line(text: str, sector: str = "") -> ParseResult:
    t = norm_line(text)
    vv = None
    for vv in VV_RE.finditer(t):
        pass
    if vv is None:
        return ParseResult(None, "no 'VV value' figure")
    head = t[:vv.start()].rstrip(" ,")
    tail = t[vv.end():]

    # 1. spec parenthesis = first parenthesis that starts with a number
    spec_ms = [pm for pm in re.finditer(r"\(([^()]*)\)", head) if re.match(r"\s*(?:c\.\s*)?\d", pm.group(1))]
    if not spec_ms:
        return ParseResult(None, "no vessel spec parenthesis (size, built, yard)")
    spec_m = spec_ms[0]
    lead = norm_line(head[:spec_m.start()])
    after = norm_line(head[spec_ms[-1].end():])
    sms = []
    for x in spec_ms:
        one = SPEC_RE.match(x.group(1).strip())
        if not one:
            return ParseResult(None, f"spec not understood: ({x.group(1)})")
        sms.append(one)
    sm = sms[0]
    # extra vessels of an en bloc deal: "A (spec), B (spec) and C (spec) sold ..."
    extra_names: list[str] = []
    for prev, cur in zip(spec_ms, spec_ms[1:]):
        chunk = norm_line(head[prev.end():cur.start()]).strip(" ,")
        chunk = re.sub(r"^(?:and|&)\s+", "", chunk).strip()
        if not chunk or re.search(r"\b(?:sold|for|USD|VV)\b", chunk, re.I):
            return ParseResult(None, "several vessel specs in one line (sale clause between them)")
        extra_names.append(chunk)

    # 2. class vocabulary: longest match from the start of the lead
    cm = CLASS_RE.match(lead)
    if not cm:
        return ParseResult(None, "vessel class not in vocabulary")
    d = Deal(raw=text)
    d.vessel_class = norm_line(cm.group("cls"))
    d.vessel_name = _clean(lead[cm.end():])
    if cm.group("resale"):
        d.flags.append("resale")
    count = cm.group("count")
    if count:
        d.flags.append("count_prefix")
        d.n_vessels = int(count) if count.isdigit() else None
    last_word = re.sub(r"\s*\(.*\)$", "", d.vessel_class).split()[-1].lower()
    plural_class = last_word.endswith("s")
    multi = bool(re.search(r",|\band\b|&", d.vessel_name)) or plural_class or bool(count)
    if multi:
        d.flags.append("multi_vessel")
        if d.n_vessels is None and d.vessel_name:
            d.n_vessels = len([x for x in re.split(r",\s*(?:and\s+)?|\s+and\s+|\s*&\s*", d.vessel_name) if x.strip()])
    if d.n_vessels is None and not multi:
        d.n_vessels = 1
    if not d.vessel_name:
        d.flags.append("no_vessel_name")

    # 3. spec fields (one spec per vessel; en bloc lines with several specs are joined with " / ")
    sizes, builts, yards, units = [], [], [], set()
    for one in sms:
        sizes.append(norm_line(one.group("size")))
        if one.group("unit"):
            units.add(one.group("unit").upper())
        if one.group("flag"):
            d.flags.append(one.group("flag").strip().lower())
        rest = one.group("rest")
        built = yard = ""
        if rest:
            if "," in rest:
                built, yard = rest.split(",", 1)
            elif re.search(r"\d{4}", rest):
                built, yard = rest, ""
            else:
                built, yard = "", rest
            built, yard = norm_line(built), norm_line(yard)
            if not re.search(r"\d{4}", built) and re.fullmatch(r"\d{4}", yard):
                built, yard = yard, built
                d.flags.append("spec_order_swapped")
        builts.append(built)
        yards.append(yard)
    d.size_text = " / ".join(sizes)
    d.size = _size_value(sizes[0]) if len(sizes) == 1 else None
    if units:
        d.size_unit = "/".join(sorted(units))
    else:
        d.size_unit = "TEU" if sector.lower().startswith("container") else "DWT"
        d.flags.append("unit_inferred")
    d.built_text = " / ".join(builts) if len(builts) > 1 else builts[0]
    d.built = _built_iso(builts[0]) if len(builts) == 1 else None
    d.yard = " / ".join(dict.fromkeys(y for y in yards if y))
    if extra_names:
        d.flags.append("multi_spec")
        d.vessel_name = ", ".join([d.vessel_name] + extra_names)
        d.n_vessels = len(sms)
        d.flags = [f for f in d.flags if f != "no_vessel_name"]

    # 4. VV value (a second figure means per-vessel values: cannot be a single clean row)
    if VV_EXTRA_RE.match(tail):
        return ParseResult(None, "several VV values in one line")
    d.vv_value_raw = vv.group(0)
    d.vv_value_usd_m = _to_float(vv.group("v")) * UNIT_MULT.get((vv.group("u") or "mil").lower(), 1.0)
    if not vv.group("u"):
        d.flags.append("vv_unit_assumed_mil")
    if vv.group("eb"):
        d.flags.append("en_bloc")

    # 5. comments after the dash (verbatim, minus trailing full stop)
    tm = TAIL_RE.match(tail)
    if tm:
        d.comments = (tm.group("c") or "").strip()
    else:
        d.comments = tail.strip(" .")
        d.flags.append("tail_without_dash")
    d.comments = d.comments.rstrip(".").strip()

    # 6. price / buyer / seller / embedded qualifiers
    pm = None
    for rx in PRICE_RES:
        pm = rx.search(after)
        if pm:
            break
    post = ""
    if pm:
        unit = (pm.group("u") or "").lower()
        d.price_raw = pm.group(0).strip()
        d.price_usd_m = _to_float(pm.group("p")) * UNIT_MULT.get(unit, 1.0)
        if not unit:
            d.flags.append("price_unit_assumed_mil")
        pre_text = after[:pm.start()]
        post = pm.group("tail").strip()
        if post.upper() in ("DWT", "TEU"):
            d.flags.append("price_unit_typo")
            post = ""
    else:
        um = UNDISC_PRICE_RE.search(after)
        if um:
            d.price_raw = um.group(0).strip()
            d.flags.append("price_undisclosed")
            pre_text = (after[:um.start()] + " " + after[um.end():])
        else:
            d.flags.append("price_not_stated")
            pre_text = after
    quals: list[str] = []
    for chunk, is_tail in ((pre_text, False), (post, True)):
        sentence = norm_line(chunk)
        if EN_BLOC_RE.search(sentence):
            d.flags.append("en_bloc")
            sentence = norm_line(EN_BLOC_RE.sub(" ", sentence))
        if not is_tail:
            am = ACTION_RE.match(sentence)
            if am:
                d.action = am.group(1).lower()
                sentence = sentence[am.end():].strip()
        pieces = WHO_RE.split(sentence)
        if pieces[0].strip():
            quals.append(_clean(pieces[0]))
        for i in range(1, len(pieces) - 1, 2):
            who = _clean(pieces[i + 1])
            if pieces[i].lower() == "to":
                d.buyer = d.buyer or who
            else:
                d.seller = d.seller or who
    d.qualifiers = "; ".join(q for q in quals if q)
    d.flags = list(dict.fromkeys(d.flags))

    if d.price_usd_m is not None and d.vv_value_usd_m:
        d.premium_pct = round((d.price_usd_m / d.vv_value_usd_m - 1) * 100, 2)
    return ParseResult(d)
