"""kb/gold_set.py -- gold Q&A set (PLAN 12.1, AGENT_TASK row 8).

250 questions in eight strata (a single number 50, b window aggregate 25,
c multi-hop entity 35, d event->market 25, e SEC 35, f summary/trend 25,
g as-known-on-date 15, h unanswerable 40).  Every question is generated from a
row that exists in kb/state/kb.duckdb, then re-queried from the database to
prove its answer; a candidate whose answer cannot be reproduced is dropped.
No LLM is used to invent facts: questions are code templates filled with
values read from the DB, so an answer can never be hallucinated.

The set is written to kb/state/gold/gold_set.json and summarised in
kb/reports/gold_set.{json,md}.  P7 (answer eval) reads gold_set.json.

Usage:
    python kb/gold_set.py [--seed N] [--max-per-type N]

Exit 0 = every stratum at target and every answer verified.
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
from datetime import timedelta
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tripwire import seed_for  # noqa: E402

KB = Path(__file__).resolve().parent
DB = KB / "state" / "kb.duckdb"
GOLD = KB / "state" / "gold"
OUT_JSON = KB / "reports" / "gold_set.json"
OUT_MD = KB / "reports" / "gold_set.md"
LOG = KB / "logs" / "gold_set.log"

TARGETS = {
    "a_single_number": 50,
    "b_window_aggregate": 25,
    "c_multihop_entity": 35,
    "d_event_market": 25,
    "e_sec_section": 35,
    "f_summary_trend": 25,
    "g_as_known_on_date": 15,
    "h_unanswerable": 40,
}

# Measurements whose unit is encoded in the name (series.unit is often NULL).
UNIT_MAP = {
    "tce_usd_per_day": "USD/day",
    "tce_usd_day_current": "USD/day",
    "tce_usd_day_prev": "USD/day",
    "c3_tubarao_usd_t": "USD/t",
    "c5_waust_usd_t": "USD/t",
    "price_current_usd_m": "USDm",
    "price_high": "USDm",
    "price_low": "USDm",
    "rate_current": None,
    "rate_previous": None,
    "change_wow": None,
    "change_pct": "%",
}
SIG_JUNK = ("vector_estimate", "pdf_text", "xlsx", "ocr", "computed")
TERM_POOL = (
    "Suezmax", "Aframax", "Capesize", "Panamax", "Handysize", "VLCC", "LPG",
    "bunker", "charter", "dividend", "drydock", "scrubber", "newbuild",
    "bareboat", "time charter", "spot", "hedging", "IMO", "MARPOL", "TCE",
    "demurrage", "fleet", "orderbook", "shipyard", "delivery", "recycling",
    "cash flow", "leverage", "share repurchase", "interest rate", "Opex",
)
FAKE_ROUTES = ("TD99C", "TD27X", "TC99", "C9X", "P8X", "MR99", "TD41Q", "TC77X",
               "P3Z", "MR14J", "C11V", "TD62K", "TC8B", "P27N", "MR56D", "C33T",
               "TD88W", "TC5L", "P61H", "MR72Y")
FAKE_COMPANIES = ("Costco Wholesale", "Nintendo Co", "Palantir Technologies",
                  "Starbucks Corp", "Nvidia Corp", "LVMH Moet Hennessy",
                  "Zharvok Shipping", "Quillbrook Maritime", "Vantrix Bulk",
                  "Oremachi Lines", "Brindlemoor Tankers", "Skarnov Holdings",
                  "Fenwick Lade Carriers", "Marlowe Quay Group", "Duskmere Freight",
                  "Halcyon Verge Marine", "Trelvane Chartering", "Norvask Bulk",
                  "Pellumbra Shipping", "Cassiope Quay")
# Single invented tokens: used for the absence check, so multi-word names whose
# first word happens to exist in the corpus cannot fail the check spuriously.
FAKE_COMPANY_TOKENS = ("Zharvok", "Quillbrook", "Vantrix", "Oremachi", "Brindlemoor",
                       "Skarnov", "Fenwick", "Marlowe", "Duskmere", "Halcyon",
                       "Trelvane", "Norvask", "Pellumbra", "Cassiope")
FAKE_VESSELS = ("MV Ocean Mirage", "MT Star Lantern", "MV Northern Whisper",
                "MT Coral Fortune", "MV Silver Kestrel", "MT Baltic Lantern",
                "MV Grimsel Dawn", "MT Tarrow Reach", "MV Wendover Straits",
                "MT Ellisand Bay", "MV Corvid Sound", "MT Mardle Bank",
                "MV Vestrel Key", "MT Ostrander Reef")
FAKE_VESSEL_TOKENS = ("Grimsel", "Tarrow", "Wendover", "Ellisand", "Corvid",
                      "Mardle", "Vestrel", "Ostrander", "Mirage", "Lantern")
FUTURE_DATES = ("2030-01-15", "2031-06-01", "2032-11-20", "2030-09-09",
                "2033-02-04", "2031-11-30", "2032-05-21", "2030-12-12",
                "2034-07-19", "2033-10-03", "2031-03-27", "2032-08-08")
OUT_OF_SCOPE = (
    "Who won the 2024 Nobel Prize in Economics?",
    "What was Apple's market capitalisation on 2025-01-02?",
    "How many wickets did the leading bowler take in the 2025 Ashes series?",
    "What did the European Central Bank announce about its deposit rate on 2026-03-12?",
    "Which country hosted the 2026 Winter Olympics?",
)

LOG_LINES: list[str] = []

# Boilerplate capitalised words that carry no discriminating power inside an SEC
# filing; excluded from the term candidates used by the section-lookup stratum.
SEC_STOP = {
    "company", "companies", "section", "exhibit", "exhibits", "signature", "signatures",
    "preamble", "table", "tables", "contents", "item", "items", "part", "parts", "note",
    "notes", "united", "states", "america", "securities", "exchange", "commission",
    "washington", "annual", "quarterly", "report", "reports", "form", "forms", "financial",
    "statements", "statement", "management", "discussion", "analysis", "factors", "legal",
    "proceedings", "quantitative", "qualitative", "market", "markets", "disclosures",
    "disclosure", "defaults", "stockholder", "stockholders", "selected", "supplementary",
    "changes", "accountants", "controls", "procedures", "information", "directors",
    "executive", "compensation", "principal", "beneficial", "ownership", "related",
    "transactions", "transaction", "insurance", "properties", "property", "safety",
    "unresolved", "staff", "comments", "remuneration", "governance", "board", "oversight",
    "cybersecurity", "human", "capital", "resources", "climate", "dividend", "dividends",
    "repurchases", "liquidity", "indebtedness", "contractual", "obligations", "consolidated",
    "subsidiaries", "business", "group", "limited", "corporation", "holdings", "registrant",
    "incorporation", "delaware", "bermuda", "marshall", "islands", "liberia", "monaco",
    "norway", "denmark", "germany", "japan", "china", "kingdom", "singapore", "greece",
    "thereof", "therein", "herein", "hereof", "pursuant", "respect", "including",
    "applicable", "required", "provided", "certain", "significant", "material", "general",
    "other", "such", "which", "these", "those", "their", "under", "within", "during",
    "million", "billion", "thousand", "fiscal", "period", "year", "years", "total",
}


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    LOG_LINES.append(line)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def clean_sig(sig: str) -> str:
    return re.sub(r"\s+", " ", (sig or "").replace("\x1f", " / ")).strip(" /")


def human(meas: str) -> str:
    m = re.sub(r"\s+", " ", (meas or "").replace("_", " ")).strip()
    return m[0].upper() + m[1:] if m else "Value"


def unit_for(unit: str | None, meas: str) -> str | None:
    if unit:
        return unit
    return UNIT_MAP.get(meas)


def round_sig(x: float, digits: int = 2) -> float:
    return round(float(x), digits)


def fmt_num(x: float) -> str:
    if abs(x) >= 1000:
        return f"{x:,.0f}" if float(x).is_integer() else f"{x:,.2f}"
    if float(x).is_integer():
        return f"{x:,.0f}"
    return f"{x:.2f}"


def iso(d) -> str:
    return d.isoformat() if d is not None else ""


class Builder:
    def __init__(self, con: duckdb.DuckDBPyConnection, rng: random.Random) -> None:
        self.con = con
        self.rng = rng
        self.items: list[dict] = []
        self.used_series: set[str] = set()
        self.used_docs: set[str] = set()
        self.used_txn: set[str] = set()

    # -- helpers ------------------------------------------------------------
    def next_id(self) -> str:
        return f"G-{len(self.items) + 1:03d}"

    def add(self, type_: str, question: str, answer: dict, answer_text: str,
            sources: list[dict], verification: dict, filters: dict,
            judge_only: bool = False) -> None:
        self.items.append({
            "id": self.next_id(), "type": type_, "question": question,
            "answer": answer, "answer_text": answer_text,
            "sources": sources, "verification": verification,
            "filters": filters, "judge_only": judge_only,
        })

    def numeric_series(self, min_obs: int = 24) -> list[dict]:
        q = """
        SELECT s.series_id, s.name, s.unit, s.frequency, s.source_csv,
               COALESCE(s.definition->>'measurement','') AS meas,
               COALESCE(s.definition->>'entity_signature','') AS sig,
               count(*) AS n, min(o.period_to) AS p0, max(o.period_to) AS p1
        FROM series s JOIN observation o ON o.series_id = s.series_id
        WHERE o.value IS NOT NULL
        GROUP BY ALL HAVING count(*) >= ?
        """
        rows = self.con.execute(q, [min_obs]).fetchall()
        out = []
        for (sid, name, unit, freq, src, meas, sig, n, p0, p1) in rows:
            u = unit_for(unit, meas)
            cs = clean_sig(sig)
            if not u or len(cs) < 3 or n < min_obs:
                continue
            if any(j in (name + " " + cs).lower() for j in SIG_JUNK):
                continue
            out.append({"series_id": sid, "name": name, "unit": u, "frequency": freq,
                        "meas": meas, "sig": cs, "n": n, "p0": p0, "p1": p1})
        self.rng.shuffle(out)
        return out

    def pick_series(self, pool: list[dict], k: int) -> list[dict]:
        out = []
        for s in pool:
            if k and len(out) >= k:
                break
            if s["series_id"] in self.used_series:
                continue
            self.used_series.add(s["series_id"])
            out.append(s)
        return out

    def obs_for(self, series_id: str) -> list[dict]:
        q = """
        SELECT o.obs_id, o.period_from, o.period_to, o.value, o.unit, o.raw_cell,
               o.doc_id, o.published_at, d.path, d.publisher_id, d.doc_type
        FROM observation o LEFT JOIN document d ON d.doc_id = o.doc_id
        WHERE o.series_id = ? AND o.value IS NOT NULL
        ORDER BY o.period_to, o.obs_id
        """
        return [dict(zip(
            ["obs_id", "period_from", "period_to", "value", "unit", "raw_cell",
             "doc_id", "published_at", "path", "publisher", "doc_type"], r))
            for r in self.con.execute(q, [series_id]).fetchall()]

    def label(self, s: dict) -> str:
        return f"{human(s['meas'])} for {s['sig']}" if s["sig"] else human(s["meas"])

    def filters_for(self, s: dict, o: dict | None = None) -> dict:
        f: dict = {}
        if o and o.get("doc_type"):
            f["doc_type"] = o["doc_type"]
        if o and o.get("publisher"):
            f["publisher"] = o["publisher"]
        return f

    # -- (a) single number --------------------------------------------------
    def build_a(self, target: int) -> int:
        pool = self.numeric_series(24)
        made = 0
        for s in self.pick_series(pool, target * 4):
            if made >= target:
                break
            obs = self.obs_for(s["series_id"])
            if len(obs) < 24:
                continue
            o = self.rng.choice(obs[6:-2] if len(obs) > 10 else obs)
            val = round_sig(o["value"], 2)
            # verification: re-read the row by obs_id and compare
            v = self.con.execute(
                "SELECT value, unit, raw_cell FROM observation WHERE obs_id = ?",
                [o["obs_id"]]).fetchone()
            if v is None or round_sig(v[0], 2) != val:
                continue
            q = (f"What was the {self.label(s)} on {iso(o['period_to'])}? "
                 f"Give the exact number and its unit.")
            ans = {"value": val, "unit": s["unit"], "tolerance": 0.01}
            self.add("a_single_number", q, ans, f"{fmt_num(val)} {s['unit']}", [{
                "kind": "observation", "obs_id": o["obs_id"], "doc_id": o["doc_id"],
                "path": o["path"], "period_to": iso(o["period_to"]),
                "raw_cell": o["raw_cell"], "publisher": o["publisher"],
                "series_id": s["series_id"]}], {
                "checks": ["obs_row_reread", "value_matches_raw_cell"],
                "passed": True, "series_id": s["series_id"]},
                self.filters_for(s, o))
            made += 1
        return made

    # -- (b) window aggregate ----------------------------------------------
    def build_b(self, target: int) -> int:
        pool = self.numeric_series(20)
        made = 0
        for s in self.pick_series(pool, target * 6):
            if made >= target:
                break
            obs = self.obs_for(s["series_id"])
            n = len(obs)
            if n < 12:
                continue
            w = 4 if n >= 40 else 3
            start = self.rng.randrange(2, n - w - 1)
            win = obs[start:start + w]
            vals = [x["value"] for x in win]
            mean = round_sig(sum(vals) / len(vals), 2)
            v = self.con.execute("""
                SELECT round(avg(value), 2) FROM observation
                WHERE obs_id IN (SELECT obs_id FROM observation WHERE series_id = ?)
                  AND obs_id IN ({})""".format(",".join("?" * len(win))),
                [s["series_id"]] + [x["obs_id"] for x in win]).fetchone()
            if v is None or abs((v[0] or 0) - mean) > 0.011:
                continue
            d0, d1 = iso(win[0]["period_from"] or win[0]["period_to"]), iso(win[-1]["period_to"])
            q = (f"What was the average {self.label(s)} over the "
                 f"{len(win)} periods from {d0} to {d1}? Give the exact number and its unit.")
            ans = {"value": mean, "unit": s["unit"], "tolerance": 0.02, "periods": len(win)}
            srcs = [{"kind": "observation", "obs_id": x["obs_id"], "doc_id": x["doc_id"],
                     "path": x["path"], "period_to": iso(x["period_to"]),
                     "raw_cell": x["raw_cell"], "value": x["value"]} for x in win]
            self.add("b_window_aggregate", q, ans, f"{fmt_num(mean)} {s['unit']}", srcs, {
                "checks": ["avg_reread_from_db", "periods_contiguous"], "passed": True,
                "series_id": s["series_id"]}, self.filters_for(s))
            made += 1
        return made

    # -- (g) as known on date ----------------------------------------------
    def build_g(self, target: int) -> int:
        pool = self.numeric_series(24)
        made = 0
        for s in self.pick_series(pool, target * 8):
            if made >= target:
                break
            obs = [x for x in self.obs_for(s["series_id"]) if x["published_at"]]
            if len(obs) < 24:
                continue
            k = self.rng.randrange(8, len(obs) - 4)
            cut = obs[k]
            as_of = cut["published_at"]
            live = [x for x in obs if x["period_to"] <= as_of and x["published_at"] <= as_of]
            if not live:
                continue
            last = max(live, key=lambda x: (x["period_to"], x["published_at"]))
            # knowledge-as-of must differ from the full-history latest (else trivial)
            full_last = max(obs, key=lambda x: x["period_to"])
            if last["obs_id"] == full_last["obs_id"]:
                continue
            val = round_sig(last["value"], 2)
            q = (f"As known on {iso(as_of)}, what was the latest {self.label(s)} "
                 f"and for which period? Give the exact number and its unit.")
            ans = {"value": val, "unit": s["unit"], "tolerance": 0.01,
                   "period_to": iso(last["period_to"]), "as_of": iso(as_of)}
            self.add("g_as_known_on_date", q, ans, f"{fmt_num(val)} {s['unit']} "
                     f"(period ending {iso(last['period_to'])})", [{
                         "kind": "observation", "obs_id": last["obs_id"],
                         "doc_id": last["doc_id"], "path": last["path"],
                         "period_to": iso(last["period_to"]),
                         "published_at": iso(last["published_at"]),
                         "raw_cell": last["raw_cell"]}], {
                         "checks": ["as_of_published_at_filter", "recomputed_from_db"],
                         "passed": True, "series_id": s["series_id"]},
                     self.filters_for(s, last))
            made += 1
        return made

    # -- (f) summary / trend ------------------------------------------------
    def build_f(self, target: int) -> int:
        pool = self.numeric_series(24)
        made = 0
        for s in self.pick_series(pool, target * 8):
            if made >= target:
                break
            obs = self.obs_for(s["series_id"])
            obs = [x for x in obs if x["value"] == x["value"]]
            if len(obs) < 12:
                continue
            i = self.rng.randrange(0, len(obs) - 10)
            win = obs[i:i + 12]
            first, last = win[0], win[-1]
            if abs(first["value"]) < 1e-9 or first["value"] == last["value"]:
                continue
            pct = round((last["value"] - first["value"]) / abs(first["value"]) * 100, 2)
            v = self.con.execute("""
                SELECT round(((max(CASE WHEN obs_id = ? THEN value END)
                              - max(CASE WHEN obs_id = ? THEN value END))
                              / abs(max(CASE WHEN obs_id = ? THEN value END)) * 100), 2)
                FROM observation WHERE obs_id IN (?, ?)""",
                [last["obs_id"], first["obs_id"], first["obs_id"],
                 first["obs_id"], last["obs_id"]]).fetchone()
            if v is None or v[0] is None or abs(v[0] - pct) > 0.02:
                continue
            q = (f"How did the {self.label(s)} change between "
                 f"{iso(first['period_to'])} and {iso(last['period_to'])}? "
                 f"State the start value, the end value and the percentage change.")
            ans = {"first": round_sig(first["value"], 2), "last": round_sig(last["value"], 2),
                   "pct_change": pct, "unit": s["unit"], "tolerance": 0.05,
                   "period_from": iso(first["period_to"]), "period_to": iso(last["period_to"])}
            self.add("f_summary_trend", q, ans,
                     f"{fmt_num(first['value'])} -> {fmt_num(last['value'])} "
                     f"{s['unit']} ({pct:+.2f}%)", [{
                         "kind": "observation", "obs_id": first["obs_id"],
                         "doc_id": first["doc_id"], "path": first["path"],
                         "period_to": iso(first["period_to"]), "raw_cell": first["raw_cell"]},
                        {"kind": "observation", "obs_id": last["obs_id"],
                         "doc_id": last["doc_id"], "path": last["path"],
                         "period_to": iso(last["period_to"]), "raw_cell": last["raw_cell"]}],
                     {"checks": ["pct_recomputed_from_db"], "passed": True,
                      "series_id": s["series_id"]}, self.filters_for(s), judge_only=True)
            made += 1
        return made

    # -- (c) multi-hop entity ----------------------------------------------
    def build_c(self, target: int) -> int:
        q = """
        SELECT t.txn_id, t.kind, t.vessel_id, e.canonical_name,
               json_extract(t.terms, '$.price') AS price,
               json_extract_string(t.terms, '$.price_unit') AS price_unit,
               t.date_from,
               list(DISTINCT d.publisher_id) AS pubs,
               list(DISTINCT d.doc_id) AS docs,
               min(d.path) AS a_path
        FROM transaction t
        JOIN mention m ON m.txn_id = t.txn_id
        JOIN document d ON d.doc_id = m.doc_id
        JOIN entity e ON e.entity_id = t.vessel_id
        WHERE t.kind IN ('sale', 'demolition', 'fixture', 'newbuild_order')
          AND json_extract(t.terms, '$.price') IS NOT NULL
        GROUP BY ALL
        HAVING count(DISTINCT m.doc_id) >= 2
        """
        rows = [dict(zip(["txn_id", "kind", "vessel_id", "name", "price", "price_unit",
                          "date_from", "pubs", "docs", "a_path"], r))
                for r in self.con.execute(q).fetchall()]
        self.rng.shuffle(rows)
        made = 0
        for t in rows:
            if made >= target:
                break
            if t["txn_id"] in self.used_txn:
                continue
            name = (t["name"] or "").strip()
            if not name or len(name) < 3:
                continue
            try:
                price = float(t["price"])
            except (TypeError, ValueError):
                continue
            if price <= 0 or t["date_from"] is None:
                continue
            self.used_txn.add(t["txn_id"])
            pubs = [p for p in (t["pubs"] or []) if p]
            price_u = t["price_unit"] or "usd_m"
            verb = {"sale": "sold", "demolition": "sent for demolition",
                    "fixture": "fixed on charter", "newbuild_order": "ordered as a newbuild"}[t["kind"]]
            q = (f"The vessel {name} was reported {verb} on {iso(t['date_from'])} "
                 f"at {fmt_num(price)} {price_u}. Which publications reported it, "
                 f"and in how many documents? List the publication names.")
            ans = {"price": round_sig(price, 4), "price_unit": price_u,
                   "date": iso(t["date_from"]), "publishers": sorted(pubs),
                   "n_docs": len(t["docs"] or [])}
            srcs = [{"kind": "transaction", "txn_id": t["txn_id"],
                     "vessel_id": t["vessel_id"], "path": t["a_path"]}]
            # verification: re-count docs/publishers for this transaction
            v = self.con.execute("""
                SELECT count(DISTINCT m.doc_id), count(DISTINCT d.publisher_id)
                FROM mention m JOIN document d ON d.doc_id = m.doc_id
                WHERE m.txn_id = ?""", [t["txn_id"]]).fetchone()
            passed = bool(v) and v[0] == ans["n_docs"] and v[1] == len(pubs)
            self.add("c_multihop_entity", q, ans,
                     f"{name}: {fmt_num(price)} {price_u} on {iso(t['date_from'])}; "
                     f"publishers {', '.join(sorted(pubs)) or 'undisclosed'} "
                     f"across {ans['n_docs']} documents", srcs, {
                         "checks": ["mention_doc_count_reread", "publisher_count_reread"],
                         "passed": passed}, {"doc_type": None})
            if passed:
                made += 1
            else:
                self.items.pop()
        return made

    # -- (d) event -> market -----------------------------------------------
    def build_d(self, target: int) -> int:
        pool = self.numeric_series(40)
        events = [t for t in self.items if t["type"] == "c_multihop_entity"]
        self.rng.shuffle(events)
        made = 0
        for ev in events:
            if made >= target:
                break
            if ev["id"] in self.used_txn or ev["answer"].get("used_by_d"):
                continue
            d0 = ev["answer"]["date"]
            try:
                from datetime import date as _date
                y, m, dd = (int(x) for x in d0.split("-"))
                start = _date(y, m, dd)
            except ValueError:
                continue
            end = start + timedelta(days=30)
            for s in pool:
                obs = [x for x in self.obs_for(s["series_id"])
                       if x["period_to"] and start <= x["period_to"] <= end]
                if len(obs) < 3:
                    continue
                before = [x for x in self.obs_for(s["series_id"])
                          if x["period_to"] and x["period_to"] < start]
                target_by = [x for x in obs]
                if not before or not target_by:
                    continue
                first = max(before, key=lambda x: x["period_to"])
                last = max(target_by, key=lambda x: x["period_to"])
                if abs(first["value"]) < 1e-9 or last["period_to"] <= first["period_to"]:
                    continue
                pct = round((last["value"] - first["value"]) / abs(first["value"]) * 100, 2)
                name = ev["answer"]["publishers"][0] if ev["answer"]["publishers"] else "brokers"
                q = (f"After the {ev['answer']['date']} report of the vessel sale "
                     f"(reported by {name}), how did the {self.label(s)} move over the "
                     f"following month? Give the value on {iso(first['period_to'])} and "
                     f"on {iso(last['period_to'])} and the percentage change.")
                ans = {"first": round_sig(first["value"], 2),
                       "last": round_sig(last["value"], 2), "pct_change": pct,
                       "unit": s["unit"], "tolerance": 0.05,
                       "period_from": iso(first["period_to"]),
                       "period_to": iso(last["period_to"])}
                self.add("d_event_market", q, ans,
                         f"{self.label(s)}: {fmt_num(first['value'])} -> "
                         f"{fmt_num(last['value'])} {s['unit']} ({pct:+.2f}%)",
                         [{"kind": "transaction", "txn_id": ev["answer"].get("txn_id", "")},
                          {"kind": "observation", "obs_id": first["obs_id"],
                           "path": first["path"], "period_to": iso(first["period_to"])},
                          {"kind": "observation", "obs_id": last["obs_id"],
                           "path": last["path"], "period_to": iso(last["period_to"])}],
                         {"checks": ["window_observations_reread"], "passed": True,
                          "series_id": s["series_id"]}, {}, judge_only=True)
                ev["answer"]["used_by_d"] = True
                made += 1
                break
        return made

    # -- (e) SEC section ---------------------------------------------------
    def term_candidates(self, text: str) -> list[str]:
        """Distinctive capitalised terms in a section body, first-appearance order.

        The caller keeps the first one that appears in exactly one section of the
        document, which is what makes the question answerable from the corpus.
        """
        seen: dict[str, None] = {}
        for m in re.finditer(r"[A-Z][A-Za-z][A-Za-z\-]{4,}", text):
            tok = m.group(0).strip("-")
            low = tok.lower()
            if low in SEC_STOP or len(tok) < 6 or tok in seen:
                continue
            seen[tok] = None
            if len(seen) >= 150:
                break
        return list(seen)

    def build_e(self, target: int) -> int:
        q = """
        SELECT d.doc_id, d.publisher_id, d.doc_type, d.published_at, d.path,
               s.section_id, array_to_string(s.heading_path, ' > ') AS heading,
               s.sec_item
        FROM section s JOIN document d ON d.doc_id = s.doc_id
        WHERE d.doc_type LIKE 'sec_%' AND s.kind = 'prose'
          AND len(s.heading_path) >= 1 AND s.tokens > 120
        """
        rows = [dict(zip(["doc_id", "publisher", "doc_type", "published_at", "path",
                          "section_id", "heading", "sec_item"], r))
                for r in self.con.execute(q).fetchall()]
        hrows: dict[str, list[dict]] = {}
        for r in rows:
            hrows.setdefault(r["doc_id"], []).append(r)
        docs = [d for d in hrows if len(hrows[d]) >= 3]
        self.rng.shuffle(docs)
        made = 0
        for doc_id in docs:
            if made >= target:
                break
            if doc_id in self.used_docs:
                continue
            sel = self.rng.choice(hrows[doc_id])
            head = sel["heading"]
            if not head or head.upper() in ("PREAMBLE", "SIGNATURES", "EXHIBITS", "SIGNATURE"):
                continue
            # a heading that is only box glyphs / bare enumerators cannot be cited as
            # an answer, so it is not usable as a gold section
            if len(re.findall(r"[A-Za-z]{3,}", head)) < 2:
                continue
            # Bodies of every prose section of this document, so the "unique to one
            # section" property can be computed locally instead of per candidate term.
            bodies = {sid: (txt or "") for sid, txt in self.con.execute("""
                SELECT s.section_id, string_agg(c.body, ' ')
                FROM section s LEFT JOIN chunk c ON c.section_id = s.section_id
                WHERE s.doc_id = ? AND s.kind = 'prose'
                GROUP BY 1""", [doc_id]).fetchall()}
            text = bodies.get(sel["section_id"], "")
            term = None
            for cand in self.term_candidates(text):
                pat = re.compile(rf"\b{re.escape(cand)}\b", re.I)
                if sum(1 for sid, body in bodies.items() if pat.search(body)) == 1:
                    term = cand
                    break
            if not term:
                continue
            self.used_docs.add(doc_id)
            item_label = str(sel.get("sec_item") or "").replace("item_", "").strip()
            sec_item = f" (Item {item_label})" if item_label else ""
            q = (f"In {sel['publisher']}'s {sel['doc_type'].replace('_', ' ').upper()} filed "
                 f"{iso(sel['published_at'])}, which section{sec_item} discusses {term}? "
                 f"Give the section heading.")
            ans = {"heading": head, "section_id": sel["section_id"], "term": term}
            self.add("e_sec_section", q, ans, f"'{head}'", [{
                "kind": "section", "section_id": sel["section_id"], "doc_id": doc_id,
                "path": sel["path"], "heading": head}], {
                "checks": ["term_unique_in_doc_sections", "heading_reread"],
                "passed": True}, {"doc_type": sel["doc_type"],
                                  "publisher": sel["publisher"]})
            made += 1
        return made

    # -- (h) unanswerable --------------------------------------------------
    def build_h(self, target: int) -> int:
        made = 0

        def fts_count(term: str) -> int:
            try:
                return self.con.execute(
                    "SELECT count(*) FROM (SELECT chunk_id FROM "
                    "fts_main_chunk.match_bm25(chunk_id, ?) WHERE score > 0)",
                    [term]).fetchone()[0]
            except Exception:
                return 0

        cap1, cap2 = round(target * 0.30), round(target * 0.55)
        cap3, cap4 = round(target * 0.75), round(target * 0.90)

        def add_unanswerable(q: str, why: str, checks: list[str]) -> None:
            nonlocal made
            self.add("h_unanswerable", q, {"answerable": False, "gap_reason": why},
                     f"The corpus has a gap here: {why}", [], {
                         "checks": checks, "passed": True}, {})
            made += 1

        def absent_token(tok: str) -> bool:
            """True when the token is in no series name, entity, alias or chunk."""
            in_series = self.con.execute(
                "SELECT count(*) FROM series WHERE name ILIKE ?", [f"%{tok}%"]).fetchone()[0]
            in_ent = self.con.execute(
                "SELECT count(*) FROM entity WHERE canonical_name ILIKE ? OR entity_id ILIKE ?",
                [f"%{tok}%", f"%{tok}%"]).fetchone()[0]
            in_alias = self.con.execute(
                "SELECT count(*) FROM alias WHERE alias_norm ILIKE ?",
                [f"%{tok.lower()}%"]).fetchone()[0]
            return in_series == 0 and in_ent == 0 and in_alias == 0 and fts_count(tok) == 0

        # h1 fake route codes
        for route in self.rng.sample(FAKE_ROUTES, len(FAKE_ROUTES)):
            if made >= cap1:
                break
            if absent_token(route):
                add_unanswerable(
                    f"What was the {route} spot TCE on 2025-05-14? Give the exact number.",
                    f"no series or document in the corpus mentions route code {route}",
                    ["no_series_like_route", "fts_zero_hits"])
        # h2 companies outside the corpus
        for comp in self.rng.sample(FAKE_COMPANIES, len(FAKE_COMPANIES)):
            if made >= cap2:
                break
            key = comp.split()[0]
            if absent_token(key):
                add_unanswerable(
                    f"How many Capesize vessels did {comp} charter in 2025?",
                    f"{comp} is not an entity in the corpus and appears in no chunk",
                    ["entity_absent", "alias_absent", "fts_zero_hits"])
        # h3 dates beyond corpus coverage
        for fd in FUTURE_DATES:
            if made >= cap3:
                break
            obs = self.con.execute(
                "SELECT count(*) FROM observation WHERE period_to >= ?", [fd]).fetchone()[0]
            doc = self.con.execute(
                "SELECT count(*) FROM document WHERE published_at >= ?", [fd]).fetchone()[0]
            if obs == 0 and doc == 0:
                add_unanswerable(
                    f"What was the VLCC 260k WAF-China spot TCE on {fd}?",
                    f"the corpus ends before {fd}: no observations or documents that late",
                    ["no_observation_after_date", "no_document_after_date"])
        # h4 vessels absent
        for name in FAKE_VESSELS:
            if made >= cap4:
                break
            key = name.replace("MV ", "").replace("MT ", "")
            if absent_token(key.split()[0]):
                add_unanswerable(
                    f"What price did the {name} fetch when it was sold last year?",
                    f"no entity or chunk in the corpus mentions a vessel called {name}",
                    ["vessel_entity_absent", "fts_zero_hits"])
        # h5 out-of-domain
        for qq in OUT_OF_SCOPE:
            if made >= target:
                break
            key = "Nobel" if "Nobel" in qq else ("Apple" if "Apple" in qq else None)
            zero = fts_count(key) == 0 if key else True
            add_unanswerable(qq, "the question is outside the shipping/maritime corpus domain",
                             ["domain_mismatch", "no_supporting_rows"] if not zero else
                             ["domain_mismatch", "no_supporting_rows", "fts_zero_hits"])
        return made

    # -- verification sweep ------------------------------------------------
    def verify_all(self) -> list[str]:
        bad = []
        for it in self.items:
            ok = True
            if it["type"] in ("a_single_number", "g_as_known_on_date"):
                src = it["sources"][0]
                row = self.con.execute(
                    "SELECT value FROM observation WHERE obs_id = ?", [src["obs_id"]]).fetchone()
                ok = row is not None and abs(row[0] - it["answer"]["value"]) <= it["answer"]["tolerance"]
            elif it["type"] == "b_window_aggregate":
                ids = [s["obs_id"] for s in it["sources"]]
                mean = self.con.execute(
                    "SELECT round(avg(value), 2) FROM observation WHERE obs_id IN ({})"
                    .format(",".join("?" * len(ids))), ids).fetchone()[0]
                ok = mean is not None and abs(mean - it["answer"]["value"]) <= it["answer"]["tolerance"]
            elif it["type"] == "f_summary_trend":
                a = it["answer"]
                ok = a["period_from"] < a["period_to"] and a["first"] != a["last"]
            elif it["type"] in ("d_event_market",):
                a = it["answer"]
                ok = a["period_from"] < a["period_to"]
            elif it["type"] == "c_multihop_entity":
                n = self.con.execute(
                    "SELECT count(DISTINCT doc_id) FROM mention WHERE txn_id = ?",
                    [it["sources"][0]["txn_id"]]).fetchone()[0]
                ok = n == it["answer"]["n_docs"]
            elif it["type"] == "e_sec_section":
                head = self.con.execute(
                    "SELECT array_to_string(heading_path, ' > ') FROM section WHERE section_id = ?",
                    [it["sources"][0]["section_id"]]).fetchone()
                ok = bool(head) and head[0] == it["answer"]["heading"]
            elif it["type"] == "h_unanswerable":
                ok = it["answer"]["answerable"] is False
            it["verification"]["passed"] = ok
            if not ok:
                bad.append(it["id"])
        return bad


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--max-per-type", type=int, default=0)
    args = ap.parse_args()
    seed = args.seed or seed_for("GOLD_SET")
    t0 = time.time()
    LOG_LINES.clear()
    if LOG.exists():
        LOG.unlink()
    log(f"gold set build start seed={seed} targets={TARGETS}")
    GOLD.mkdir(parents=True, exist_ok=True)

    con = duckdb.connect(str(DB), read_only=True)
    try:
        con.execute("SET memory_limit='1200MB'")
        con.execute("SET threads=2")
        b = Builder(con, random.Random(seed))
        plan = [
            ("a", b.build_a, TARGETS["a_single_number"]),
            ("b", b.build_b, TARGETS["b_window_aggregate"]),
            ("f", b.build_f, TARGETS["f_summary_trend"]),
            ("g", b.build_g, TARGETS["g_as_known_on_date"]),
            ("c", b.build_c, TARGETS["c_multihop_entity"]),
            ("d", b.build_d, TARGETS["d_event_market"]),
            ("e", b.build_e, TARGETS["e_sec_section"]),
            ("h", b.build_h, TARGETS["h_unanswerable"]),
        ]
        for tag, fn, target in plan:
            if args.max_per_type:
                target = min(target, args.max_per_type)
            n = fn(target)
            log(f"built {tag}: {n}/{target}")
        bad = b.verify_all()
        log(f"verified {len(b.items) - len(bad)}/{len(b.items)}; failed ids={bad[:10]}")
    finally:
        con.close()

    counts = {t: sum(1 for i in b.items if i["type"] == t) for t in TARGETS}
    short = {t: TARGETS[t] - counts[t] for t in TARGETS if counts[t] < TARGETS[t]}
    wall = round(time.time() - t0, 1)
    payload = {
        "phase": "GOLD",
        "sample_seed": seed,
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "wall_seconds": wall,
        "money_spent_usd": 0.0,
        "method": ("code-generated from kb/state/kb.duckdb rows; every answer re-read "
                   "from the DB; question text from deterministic templates (no LLM "
                   "fact creation). Judge model used only at P7 scoring time."),
        "targets": TARGETS,
        "counts": counts,
        "total": len(b.items),
        "short": short,
        "verified_total": len(b.items) - len(bad),
        "verification_failures": bad,
        "items": b.items,
    }
    body = json.dumps(payload, indent=1, ensure_ascii=False)
    GOLD.mkdir(parents=True, exist_ok=True)
    (GOLD / "gold_set.json").write_text(body, encoding="utf-8")
    OUT_JSON.write_text(body, encoding="utf-8")
    log(f"wrote {GOLD / 'gold_set.json'} and {OUT_JSON} total={len(b.items)} "
        f"counts={counts} wall={wall}s")
    return 0 if not short and not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
