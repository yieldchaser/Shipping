"""Xclusiv weekly: freight benchmark averages printed in the freight commentary.

Every value is a number printed in the commentary sentence that names its index, e.g.
  "The Capesize C5TC average improved by USD 0.1k/day closing the week at USD 48,954/ day."
  "VLCC: average T/CE ended the week down by 8.8k/day at USD 714,143/day."
  "1y T/C rate for Ultramax is USD 17,700/day & 1y T/C rate for Supramax is USD 16,250/day"
  "Eco MR2 1y T/C rate is at USD 15,000/day"
An index average takes the LAST 'at USD x/day' of its sentence ('started the week at USD 20,262/day closing
with an increase at USD 21,662/day' -> 21,662). Route rates ('Trip from ... at USD x/day') are not taken.

Replaces the regexes of run_xclusiv_full_cover_to_cover.extract_freight_benchmarks. Those stopped at the first
'.', so they missed every sentence with a decimal change ('8.8k/day'), and they filed the Ultramax S11TC
average as the Supramax 10TC one.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List

COLUMNS = ["issue_date", "report_week", "sector", "vessel_class", "metric", "rate_usd_day", "source_file"]

# index token -> (sector, vessel_class, metric). Metric names keep the series' existing labels.
INDEX = [
    (r"\bC5TC\b", ("Dry Bulk", "Capesize", "C5TC Average")),
    (r"\bP[45]TC\b", ("Dry Bulk", "Panamax", "P5TC Average")),
    (r"\bS11TC\b", ("Dry Bulk", "Ultramax", "S11TC Average")),
    (r"\bS3TC\b", ("Dry Bulk", "Supramax", "S3TC Average")),
    (r"\b(?:S10TC|10\s*T/?C|BSI[- ]?\d*)\b", ("Dry Bulk", "Supramax", "10TC Average")),
    (r"\b(?:HS7TC|7\s*T/?C|BHSI)\b", ("Dry Bulk", "Handysize", "7TC Average")),
]
TANKER = {"vlcc": "VLCC", "suezmax": "Suezmax", "aframax": "Aframax"}
CLASS_WORDS = [("cape", "Capesize"), ("kamsarmax", "Kamsarmax"), ("panamax", "Panamax"), ("ultramax", "Ultramax"),
               ("supramax", "Supramax"), ("handy", "Handysize"), ("lr2", "LR2"), ("lr1", "LR1"), ("mr2", "MR2"),
               ("mr", "MR2")]
USD = r"(?:USD|usd|US\$|\$)\s*(-?\s?[\d,]+(?:\.\d+)?)\s*/\s*day"   # 2022 tanker TCEs print negative
# 'is [softer|down by USD 2k/day] at USD x/day': the bridge is lazy and may not pass another 'USD n,nnn/day', or it
# would run on into the next clause ('for Ultramax is USD 34,500/day, with ... Supramax at USD 31,500/day').
_BRIDGE = r"(?:(?:(?!USD\s*[\d,]{4,}\s*/)[^.&]){0,60}?\bat\s+)??"
TC_FOR = re.compile(r"1\s*y(?:ear)?\s*T/C\s*(?:rate\s+)?for\b((?:(?!\bis\b).){0,60}?)\bis\s+" + _BRIDGE + USD, re.I)
TC_PRE = re.compile(r"([A-Za-z0-9/ .\-]{2,40}?)\s+1\s*y(?:ear)?\s*T/C\s*(?:rate\s+)?is\s+" + _BRIDGE + USD, re.I)
# '1 year T/C for Supramax at USD 31,500/day' (no 'is')
TC_AT = re.compile(r"1\s*y(?:ear)?\s*T/C\s*(?:rate\s+)?for\s+([A-Za-z0-9/ .\-]{2,40}?)\s+at\s+" + USD, re.I)
SENT = re.compile(r"(?<=day)\.\s+|(?<=day)\s*[,;&]?\s*(?:and|while)\s+(?=[A-Z])")


def _num(s: str) -> float:
    return float(s.replace(",", "").replace(" ", ""))


def _class(what: str):
    w = what.lower()
    for k, v in TANKER.items():
        if k in w:
            return "Tanker", v
    for k, v in CLASS_WORDS:
        if re.search(r"\b" + k, w):
            return ("Clean Products" if v in ("LR2", "LR1", "MR2") else "Dry Bulk"), v
    return None, None


def rows(paragraphs: Iterable[str], issue_date: str, report_week, source_file: str) -> List[Dict[str, Any]]:
    """paragraphs: the commentary text blocks of the report, in reading order."""
    out: List[Dict[str, Any]] = []
    seen = set()

    def add(sector, vclass, metric, val):
        k = (sector, vclass, metric)
        if k in seen:          # first mention per index per issue
            return
        seen.add(k)
        out.append(dict(issue_date=issue_date, report_week=report_week, sector=sector, vessel_class=vclass,
                        metric=metric, rate_usd_day=val, source_file=source_file))

    for para in paragraphs:
        para = re.sub(r"\s+", " ", para or "").strip()
        m = re.match(r"([A-Za-z0-9/ \-]{3,40}?):", para)
        label = (m.group(1) if m else "").lower()
        for sent in re.split(r"(?<=day)\.\s+", para):
            for tc in list(TC_FOR.finditer(sent)) + list(TC_AT.finditer(sent)):
                sector, cls = _class(tc.group(1))
                if cls:
                    add(sector, cls, "1y T/C Rate", _num(tc.group(2)))
            for tc in TC_PRE.finditer(sent):
                sector, cls = _class(tc.group(1).split(",")[-1].split(" and ")[-1])
                if cls:
                    add(sector, cls, "1y T/C Rate", _num(tc.group(2)))
            vals = re.findall(r"\bat\s+" + USD, sent)
            if not vals:
                continue
            if re.search(r"average\s+T/?CE|\bavg\.?\s+T/?CE|\bTCE\b", sent, re.I):
                # the class the sentence names; the paragraph label ('VLCC: average T/CE ...') when it names none
                named = [v for k, v in TANKER.items() if re.search(r"\b" + k + r"\b", sent.lower())]
                cls = named[0] if len(named) == 1 else next((v for k, v in TANKER.items() if k in label), None)
                if cls:
                    add("Tanker", cls, "Average T/CE", _num(vals[-1]))
                continue
            if not re.search(r"\bav(?:era)?g", sent, re.I):
                continue
            for pat, (sector, vclass, metric) in INDEX:
                if re.search(pat, sent):
                    add(sector, vclass, metric, _num(vals[-1]))
                    break
    return out


def paragraphs_from_doc(doc, first=1, last=3) -> List[str]:
    """Text blocks of the freight pages (2-4), in reading order. Sentences are matched on their own wording, so
    chart labels and tables in the same pages cannot produce a row."""
    out = []
    for p in list(doc)[first:last + 1]:
        for b in sorted(p.get_text("blocks"), key=lambda b: (round(b[0] / 200), b[1])):
            if b[6] == 0 and len(b[4]) > 30:
                out.append(b[4].replace("�", "'"))
    return out
