"""P7 discovery pass (AGENT_TASK §55-61) — statistics only, no model calls.

Design note (D18):
- Domains are keyword-mapped from `series.name` (free text dims), the same surface P6
  classifies on. A series belongs to one primary domain; entities inherit domains from
  the series that list them in `series.entity_ids`.
- Tests: cross-domain lead/lag over -3..+3 months, within-domain co-movement, graph
  bridges (entities spanning >= 2 domains), event studies and cross-domain claims.
  Every test carries n, window, Pearson r, p, BH-FDR q and an out-of-sample split check.
- Survivors are stored in `discovered_link` with `label='computed'` and the evidence ids
  used to compute them. Nothing here is a fact: rows are statistics with provenance.
- Top 30 findings + 20 cross-domain multi-hop questions (>=3 hops) go to the C2 report.
- Event studies and cross-domain claims need the P5 `event`/`claim` tables; when empty the
  module reports zero with a reason instead of inventing links.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from datetime import date, datetime
from pathlib import Path

import numpy as np
from scipy import stats as sstats

KB_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(KB_DIR))

import tools as T  # noqa: E402

ROOT = KB_DIR.parent
PHASE = "P7"
OUT = ROOT / "kb" / "state" / "p7"
REPORT = ROOT / "kb" / "reports" / "p7_discovery.json"
MIN_MONTHS = 24
MIN_OVERLAP = 24
LAGS = (-3, -2, -1, 0, 1, 2, 3)
TOP_SERIES = 40
ALPHA = 0.05
OOS_SPLIT = 0.5
OOS_MIN_R = 0.20
MAX_FINDINGS = 30
N_QUESTIONS = 20
LINK_KINDS = ("lead_lag", "comovement", "bridge", "event", "claims")
DDL = """CREATE TABLE IF NOT EXISTS discovered_link (
    link_id VARCHAR PRIMARY KEY,
    kind VARCHAR NOT NULL,
    a VARCHAR,
    b VARCHAR,
    stat DOUBLE,
    p_value DOUBLE,
    q_value DOUBLE,
    lag_months INTEGER,
    n INTEGER,
    window_from DATE,
    window_to DATE,
    evidence_ids VARCHAR[],
    method VARCHAR,
    label VARCHAR DEFAULT 'computed',
    created_at TIMESTAMP DEFAULT current_timestamp)"""

DOMAINS = {
    "freight_dry": ["capesize", "panamax", "supramax", "handysize", "bdi", "bci", "bpi", "bsi",
                    "dry bulk", "dry", "ffa", "tc average", "tce", "route"],
    "freight_wet": ["vlcc", "suezmax", "aframax", "mr ", "lr1", "lr2", "tanker", "clean",
                    "dirty", "td3", "td2", "td"],
    "gas": ["lng", "lpg", "propane", "butane", "fob"],
    "container": ["container", "teu", "box"],
    "commodity_iron_ore": ["iron ore", "iron_ore", " ore"],
    "commodity_coal": ["coal"],
    "commodity_grains": ["grain", "wheat", "corn", "soybean", "soyabean", "barley"],
    "asset_newbuild": ["newbuild", "new build", "orderbook", "order book", "resale"],
    "asset_secondhand": ["secondhand", "second hand", "sale and purchase", "s&p", "snp",
                         "demolition", "scrap", "breaking", "vessel value"],
    "bunkers": ["bunker", "ifo", "vlsfo", "mgo", "mdo"],
    "equity_fin": ["eps", "revenue", "ebitda", "net income", "dividend", "share", "market cap"],
}
DOMAIN_ORDER = list(DOMAINS)


def seed_for(phase: str) -> int:
    from hashlib import sha256
    return int(sha256(f"{phase}|kb-gates-v1".encode("utf-8")).hexdigest()[:8], 16)


def connect(db: str | None = None, write: bool = False):
    return T.connect(db or T.KB_DB, read_only=not write)


# --------------------------------------------------------------------------- data
def classify_series(name: str) -> str | None:
    low = (name or "").lower()
    best, best_pos = None, 10 ** 9
    for dom in DOMAIN_ORDER:
        for kw in DOMAINS[dom]:
            pos = low.find(kw)
            if pos >= 0 and pos < best_pos:
                best, best_pos = dom, pos
    return best


def series_domains(names: dict[str, str]) -> dict[str, str]:
    out = {}
    for sid, name in names.items():
        dom = classify_series(name)
        if dom:
            out[sid] = dom
    return out


def load_monthly(con, min_months: int = MIN_MONTHS) -> dict:
    """Monthly mean per series, restricted to mapped domains with enough history."""
    rows = con.execute(
        "SELECT s.series_id, s.name, date_trunc('month', o.period_from) AS m,"
        "       avg(o.value) AS v, count(*) AS n,"
        "       min(o.doc_id) AS doc_id"
        "  FROM series s JOIN observation o USING (series_id)"
        " WHERE o.value IS NOT NULL AND o.period_from IS NOT NULL"
        " GROUP BY 1, 2, 3").fetchall()
    names = {}
    by_series: dict[str, dict] = {}
    for sid, name, m, v, _n, doc_id in rows:
        dom = classify_series(name)
        if not dom:
            continue
        names[sid] = name
        d = m if isinstance(m, date) else datetime.fromisoformat(str(m)).date()
        by_series.setdefault(sid, {"domain": dom, "name": name, "points": {}})["points"][d] = (
            float(v), doc_id)
    kept = {sid: rec for sid, rec in by_series.items() if len(rec["points"]) >= min_months}
    return {"series": kept, "names": names}


def monthly_changes(rec: dict) -> tuple[list[date], np.ndarray]:
    pts = sorted(rec["points"].items())
    months = [p[0] for p in pts]
    vals = np.array([p[1][0] for p in pts], dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        ch = np.where(vals[:-1] != 0, (vals[1:] - vals[:-1]) / np.abs(vals[:-1]), np.nan)
    ch = np.clip(ch, -1.0, 1.0)
    return months[1:], ch


def align(a: dict, b: dict) -> tuple[np.ndarray, np.ndarray, list[date]]:
    ma, ca = monthly_changes(a)
    mb, cb = monthly_changes(b)
    idx_a = {m: v for m, v in zip(ma, ca) if not math.isnan(v)}
    idx_b = {m: v for m, v in zip(mb, cb) if not math.isnan(v)}
    common = sorted(set(idx_a) & set(idx_b))
    return (np.array([idx_a[m] for m in common]), np.array([idx_b[m] for m in common]), common)


def pearson(x: np.ndarray, y: np.ndarray) -> tuple[float, float, int] | None:
    n = len(x)
    if n < MIN_OVERLAP or np.std(x) == 0 or np.std(y) == 0:
        return None
    r, p = sstats.pearsonr(x, y)
    if not np.isfinite(r) or not np.isfinite(p):
        return None
    return float(r), float(p), n


def oos_ok(x: np.ndarray, y: np.ndarray) -> bool:
    cut = int(len(x) * OOS_SPLIT)
    if cut < 12 or len(x) - cut < 12:
        return False

    def r_of(a: np.ndarray, b: np.ndarray) -> float | None:
        if len(a) < 12 or np.std(a) == 0 or np.std(b) == 0:
            return None
        r, _ = sstats.pearsonr(a, b)
        return float(r) if np.isfinite(r) else None

    r1 = r_of(x[:cut], y[:cut])
    r2 = r_of(x[cut:], y[cut:])
    if r1 is None or r2 is None:
        return False
    return r1 * r2 > 0 and min(abs(r1), abs(r2)) >= OOS_MIN_R


def bh_fdr(pvals: list[float], alpha: float = ALPHA) -> list[float]:
    if not pvals:
        return []
    return [float(q) for q in sstats.false_discovery_control(np.array(pvals), method="bh")]


def window_of(months: list[date]) -> tuple[str | None, str | None]:
    if not months:
        return None, None
    return str(min(months)), str(max(months))


# --------------------------------------------------------------------------- tests
def lead_lag(series: dict) -> list[dict]:
    """Co-movement and lead/lag across domains (composite monthly change per domain)."""
    comp: dict[str, dict[date, list[float]]] = {}
    for sid, rec in series.items():
        months, ch = monthly_changes(rec)
        dom = rec["domain"]
        for m, v in zip(months, ch):
            if not math.isnan(v):
                comp.setdefault(dom, {}).setdefault(m, []).append(float(v))
    comp = {d: {m: float(np.mean(vs)) for m, vs in pts.items()} for d, pts in comp.items()}
    out = []
    doms = sorted(comp)
    for i, a in enumerate(doms):
        for b in doms[i + 1:]:
            common = sorted(set(comp[a]) & set(comp[b]))
            if len(common) < MIN_OVERLAP:
                continue
            xa = np.array([comp[a][m] for m in common])
            xb = np.array([comp[b][m] for m in common])
            best = None
            for lag in LAGS:
                if lag > 0:
                    xs, ys = xa[:-lag], xb[lag:]
                elif lag < 0:
                    xs, ys = xa[-lag:], xb[:lag]
                else:
                    xs, ys = xa, xb
                if len(xs) < MIN_OVERLAP:
                    continue
                pr = pearson(xs, ys)
                if not pr:
                    continue
                r, p, n = pr
                if best is None or abs(r) > abs(best["stat"]):
                    best = {"kind": "lead_lag", "a": a, "b": b, "stat": round(r, 4),
                            "p": p, "lag": lag, "n": n,
                            "window_from": str(min(common)), "window_to": str(max(common)),
                            "evidence": [f"domain:{a}", f"domain:{b}"],
                            "hops": 2,
                            "oos": oos_ok(xs, ys)}
            if best:
                out.append(best)
    return out


def comovement(series: dict) -> list[dict]:
    """Same-month co-movement between the most-covered within-domain series pairs."""
    by_dom: dict[str, list[str]] = {}
    for sid, rec in series.items():
        by_dom.setdefault(rec["domain"], []).append(sid)
    out = []
    for dom, sids in by_dom.items():
        sids = sorted(sids, key=lambda s: -len(series[s]["points"]))[:TOP_SERIES]
        for i, a in enumerate(sids):
            for b in sids[i + 1:]:
                x, y, common = align(series[a], series[b])
                pr = pearson(x, y)
                if not pr:
                    continue
                r, p, n = pr
                out.append({"kind": "comovement", "a": a, "b": b, "stat": round(r, 4), "p": p,
                            "lag": 0, "n": n,
                            "window_from": str(min(common)), "window_to": str(max(common)),
                            "evidence": [a, b], "hops": 2, "oos": oos_ok(x, y),
                            "names": [series[a]["name"], series[b]["name"]]})
    return out


def bridges(series: dict, con) -> list[dict]:
    """Entities listed on series from >= 2 domains (documented cross-domain bridges)."""
    ent_dom: dict[str, dict] = {}
    ent_ev: dict[str, list[str]] = {}
    try:
        rows = con.execute(
            "SELECT series_id, name, entity_ids FROM series WHERE entity_ids IS NOT NULL").fetchall()
    except Exception:  # noqa: BLE001 - older DB without entity_ids
        return []
    for sid, name, ids in rows:
        dom = classify_series(name)
        if not dom or not ids:
            continue
        try:
            parsed = json.loads(ids) if isinstance(ids, str) else ids
        except (ValueError, TypeError):
            continue
        for ent in parsed or []:
            ent_dom.setdefault(str(ent), {}).setdefault(dom, set()).add(sid)
            ent_ev.setdefault(str(ent), []).append(sid)
    out = []
    for ent, doms in ent_dom.items():
        if len(doms) < 2:
            continue
        dom_list = sorted(doms)
        out.append({"kind": "bridge", "a": ent, "b": "+".join(dom_list),
                    "stat": float(len(dom_list)), "p": 0.0, "lag": 0,
                    "n": sum(len(v) for v in doms.values()),
                    "window_from": None, "window_to": None,
                    "evidence": sorted({s for v in doms.values() for s in v})[:20],
                    "hops": 3, "oos": True,
                    "domains": {d: sorted(v)[:5] for d, v in doms.items()}})
    return out


def event_study(series: dict, con) -> list[dict]:
    """Mean 3-month change of a domain composite after documented events."""
    try:
        rows = con.execute(
            "SELECT event_id, type, occurred_from FROM event"
            " WHERE occurred_from IS NOT NULL").fetchall()
    except Exception:  # noqa: BLE001 - table absent until P5
        return []
    if not rows:
        return []
    comp: dict[str, dict[date, list[float]]] = {}
    for rec in series.values():
        months, ch = monthly_changes(rec)
        for m, v in zip(months, ch):
            if not math.isnan(v):
                comp.setdefault(rec["domain"], {}).setdefault(m, []).append(float(v))
    out = []
    for event_id, etype, when in rows:
        d = when if isinstance(when, date) else datetime.fromisoformat(str(when)).date()
        for dom, pts in comp.items():
            after = [np.mean(pts[m]) for m in sorted(pts) if 0 < (m.year - d.year) * 12 + m.month - d.month <= 3]
            before = [np.mean(pts[m]) for m in sorted(pts) if -3 <= (m.year - d.year) * 12 + m.month - d.month <= 0]
            if len(after) < 2 or len(before) < 2:
                continue
            try:
                t, p = sstats.ttest_ind(after, before, equal_var=False)
            except Exception:  # noqa: BLE001
                continue
            if not np.isfinite(p):
                continue
            out.append({"kind": "event", "a": str(event_id), "b": dom, "stat": round(float(t), 4),
                        "p": float(p), "lag": 0, "n": len(after) + len(before),
                        "window_from": str(d), "window_to": None,
                        "evidence": [str(event_id)], "hops": 2, "oos": True})
    return out


def attach_entities(series: dict, con) -> None:
    """Copy `series.entity_ids` onto the loaded series so claims/bridges can use them."""
    try:
        rows = con.execute(
            "SELECT series_id, entity_ids FROM series WHERE entity_ids IS NOT NULL").fetchall()
    except Exception:  # noqa: BLE001 - older DB without entity_ids
        return
    for sid, ids in rows:
        rec = series.get(sid)
        if not rec:
            continue
        try:
            parsed = json.loads(ids) if isinstance(ids, str) else ids
        except (ValueError, TypeError):
            parsed = None
        rec["entities"] = [str(x) for x in (parsed or [])]


def claims_cross_domain(series: dict, con) -> list[dict]:
    """Claims whose subjects belong to >= 2 different domains."""
    try:
        rows = con.execute(
            "SELECT claim_id, subject_ids, published_at FROM claim").fetchall()
    except Exception:  # noqa: BLE001 - table absent until P5
        return []
    if not rows:
        return []
    ent_dom: dict[str, set[str]] = {}
    for sid, rec in series.items():
        dom = rec["domain"]
        for ent in rec.get("entities") or []:
            ent_dom.setdefault(str(ent), set()).add(dom)
    out = []
    for claim_id, subjects, published in rows:
        try:
            parsed = json.loads(subjects) if isinstance(subjects, str) else (subjects or [])
        except (ValueError, TypeError):
            continue
        doms = {d for s in parsed for d in ent_dom.get(str(s), set())}
        if len(doms) < 2:
            continue
        out.append({"kind": "claims", "a": str(claim_id), "b": "+".join(sorted(doms)),
                    "stat": float(len(doms)), "p": 0.0, "lag": 0, "n": len(parsed),
                    "window_from": str(published) if published else None, "window_to": None,
                    "evidence": [str(claim_id)] + [str(s) for s in parsed][:10],
                    "hops": 3, "oos": True})
    return out


# --------------------------------------------------------------------------- select
def survive(tests: list[dict], alpha: float = ALPHA) -> list[dict]:
    """Keep FDR survivors; bridge/claims/event rows are descriptive and kept on n only."""
    stat_tests = [t for t in tests if t["p"] > 0]
    qs = bh_fdr([t["p"] for t in stat_tests], alpha=alpha)
    kept = []
    for t, q in zip(stat_tests, qs):
        if q <= alpha:
            t["q"] = float(q)
            kept.append(t)
    for t in tests:
        if t["p"] == 0.0:
            t.setdefault("q", 0.0)
            kept.append(t)
    return kept


def add_ids(links: list[dict]) -> list[dict]:
    out = []
    for i, ln in enumerate(sorted(links, key=lambda d: (-abs(d["stat"]), d["kind"], d["a"], d["b"]))):
        ln = dict(ln)
        ln["link_id"] = f"dl:{i + 1:05d}"
        ln["label"] = "computed"
        out.append(ln)
    return out


def _score(ln: dict) -> float:
    if ln["kind"] in ("lead_lag", "comovement"):
        return abs(ln["stat"]) * math.sqrt(max(1, ln["n"]))
    return math.sqrt(max(1, ln["n"])) * (1.0 + 0.1 * abs(ln["stat"]))


def findings(links: list[dict], n: int = MAX_FINDINGS) -> list[dict]:
    ranked = sorted(links, key=lambda d: (-_score(d), d["kind"], d["a"], d["b"]))
    return ranked[:n]


def bridge_questions(links: list[dict], n: int = N_QUESTIONS) -> list[dict]:
    """Cross-domain questions that need >= 3 hops (bridge -> series -> document -> value)."""
    out = []
    for ln in findings(links, n * 4):
        if len(out) >= n:
            break
        if ln["kind"] == "bridge":
            doms = ln.get("domains") or {}
            names = list(doms)
            if len(names) < 2:
                continue
            q = (f"Trace {ln['a']} across {names[0]} and {names[1]}: which documents link it, "
                 f"what did each domain's market do around the link, and what changed first? "
                 f"Cite every hop.")
            hops = 3
        elif ln["kind"] == "lead_lag":
            q = (f"Between {ln['window_from']} and {ln['window_to']}, did {ln['a']} move "
                 f"{abs(ln['lag'])} month(s) {'ahead of' if ln['lag'] > 0 else 'behind'} "
                 f"{ln['b']}? Quantify it, then find the documents that connect the two domains.")
            hops = 4
        elif ln["kind"] == "comovement":
            q = (f"How tightly did {ln['a']} and {ln['b']} co-move, and which publishers reported "
                 f"both? Take the value from the data, then explain the mechanism with citations.")
            hops = 3
        else:
            continue
        out.append({"id": f"D-{len(out) + 1:03d}", "question": q, "kind": ln["kind"],
                    "link_id": ln["link_id"], "hops": hops,
                    "evidence": ln.get("evidence") or []})
    return out


# --------------------------------------------------------------------------- write
def write_links(con, links: list[dict]) -> int:
    con.execute(DDL)
    con.execute("DELETE FROM discovered_link")
    for ln in links:
        con.execute(
            "INSERT INTO discovered_link (link_id, kind, a, b, stat, p_value, q_value,"
            " lag_months, n, window_from, window_to, evidence_ids, method, label)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'computed')",
            [ln["link_id"], ln["kind"], ln["a"], ln["b"], float(ln["stat"]),
             float(ln["p"]), float(ln.get("q") or 0.0), int(ln.get("lag") or 0),
             int(ln["n"]), ln.get("window_from"), ln.get("window_to"),
             list(ln.get("evidence") or []),
             "pearson_monthly_pct_change_bh_fdr_oos" if ln["kind"] in ("lead_lag", "comovement")
             else "descriptive_evidence"])
    return len(links)


# --------------------------------------------------------------------------- run
def build(con, min_months: int = MIN_MONTHS, write: bool = False) -> dict:
    t0 = time.time()
    data = load_monthly(con, min_months=min_months)
    series = data["series"]
    attach_entities(series, con)
    stats_tests = lead_lag(series) + comovement(series)
    desc_tests = bridges(series, con) + event_study(series, con) + claims_cross_domain(series, con)
    kept = survive(stats_tests + desc_tests)
    links = add_ids(kept)
    written = write_links(con, links) if write else 0
    fnd = findings(links)
    qs = bridge_questions(links)
    report = {"phase": PHASE, "sample_seed": seed_for(PHASE),
              "built_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
              "wall_seconds": round(time.time() - t0, 1),
              "method": {"alpha": ALPHA, "min_months": min_months, "min_overlap": MIN_OVERLAP,
                         "lags": list(LAGS), "fdr": "benjamini-hochberg",
                         "oos": f"two halves, same sign, |r|>={OOS_MIN_R}",
                         "metric": "monthly pct change, clipped to [-1,1]"},
              "counts": {"series": len(series), "domains": len({r["domain"] for r in series.values()}),
                         "tests": len(stats_tests) + len(desc_tests),
                         "stat_tests": len(stats_tests), "survivors": len(links),
                         "by_kind": {k: sum(1 for l in links if l["kind"] == k) for k in LINK_KINDS},
                         "written": written, "findings": len(fnd), "questions": len(qs),
                         "events": 0 if not any(l["kind"] == "event" for l in links) else
                                   sum(1 for l in links if l["kind"] == "event"),
                         "claims": sum(1 for l in links if l["kind"] == "claims")},
              "findings": fnd, "questions": qs, "links": links}
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="P7 discovery pass: cross-domain statistics")
    ap.add_argument("--db", default=None)
    ap.add_argument("--min-months", type=int, default=MIN_MONTHS)
    ap.add_argument("--write", action="store_true", help="write discovered_link rows into the KB")
    ap.add_argument("--report", action="store_true", help="also write kb/reports/p7_discovery.json")
    ap.add_argument("--out", default=str(OUT / "discovery.json"))
    args = ap.parse_args(argv)
    con = connect(args.db, write=args.write)
    try:
        report = build(con, min_months=args.min_months, write=args.write)
    finally:
        con.close()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1), encoding="utf-8")
    if args.report:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(report, indent=1), encoding="utf-8")
    c = report["counts"]
    print(f"series {c['series']} tests {c['tests']} survivors {c['survivors']} "
          f"findings {c['findings']} questions {c['questions']} written {c['written']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
