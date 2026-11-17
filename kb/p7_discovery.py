"""P7 discovery pass (AGENT_TASK §55-61) — statistics only, no model calls.

Design note (D18):
- Domains are keyword-mapped from `series.name` (free text dims), the same surface P6
  classifies on. A series belongs to one primary domain.
- Tests: cross-domain lead/lag over -3..+3 months, within-domain co-movement, graph
  bridges (entities spanning >= 2 domains), event studies and cross-domain claims.
  Every test carries n, window, Pearson r, p, BH-FDR q and an out-of-sample split check.
- Survivors are stored in `discovered_link` with `label='computed'` and the evidence ids
  used to compute them. Nothing here is a fact: rows are statistics with provenance.
- Top 30 findings + 20 cross-domain multi-hop questions (>=3 hops) go to the C2 report.
- Event studies and cross-domain claims need the P5 `event`/`claim` tables; when empty the
  module reports zero with a reason instead of inventing links.

Known limitation (measured, reported, NOT papered over — AGENT_TASK §3 rule 9):
- The two producers that must yield `bridge` and `claims` links are dead on the real KB by
  construction. `bridges()` reads `series.entity_ids`, and `p2_series.py` writes that column
  as SQL NULL for all 29,827 rows; `claims_cross_domain()` inherits the same NULL set through
  `attach_entities()`. `chunk.entity_ids` is populated (185,454 rows) but no join to a series
  exists (`series.source_csv -> document.path` is 0 rows, stem joins are 0 rows).
- Nine candidate substitute producers were measured and all were rejected as noise: unbounded
  `chunk`-derived bridges (93% multi-domain), SQL-bounded obs->chunk (4,154 edges, all junk
  hubs spanning 11/11 domains), strict edge-endpoint cross-domain (0), typed-entity min-support
  (every candidate spans 11/11), the row-level `observation -> mention` path (0 join rows),
  `entity.attrs` classification (3,444/100,333 noise), `edge`-derived (175/940 noise),
  and both `series.definition.entity_signature` variants (169 and 28 resolved entities,
  0 multi-domain: the signature's first column is a data-source token such as `value_source`
  or `week_ending`, not an entity).
- Consequence, stated plainly rather than hidden: the survivor pool collapses to the
  `lead_lag`/`comovement`/`event` kinds and every discovery question is a statistics question.
  The `publishers` hop that would otherwise be missing is recovered from a chain the KB does
  populate: `observation.doc_id -> document.publisher_id` (26,945 series).
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

import ask as A  # noqa: E402
import gates as G  # noqa: E402
import money as M  # noqa: E402
import p7_eval as E  # noqa: E402
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
# Hypothesis-tested kinds: the only rows that belong to the Benjamini-Hochberg family (Defect 9).
# `bridge`/`event`/`claims` are descriptive cross-domain rows with no null hypothesis, kept on their
# own evidence and labelled `descriptive_evidence` at the write site.
STAT_KINDS = ("lead_lag", "comovement")
# Gate operands read from the frozen `kb/gates.yaml` P7 block (Defect 40 family). An unreadable
# operand is `None`; `build` then reports it and the row cannot silently satisfy the gate.
FDR_MAX = G.threshold(PHASE, "discovered_links_fdr_max")
OOS_REQUIRED = G.flag_threshold(PHASE, "discovered_links_out_of_sample_checked")
MIN_DISCOVERY_Q = G.count_threshold(PHASE, "discovery_questions_3hop")
# Defect 40 (limb 3): the frozen `discovery_multihop_f1: 0.70` operand had NO producer anywhere in the
# repo -- `p7_report.check_discovery` read `dc["multihop_f1"]` and `p7_discovery.build` never wrote it,
# so the C2 discovery gate was permanently UNMEASURED. The threshold is READ from the frozen file
# (never hardcoded); unreadable => `None` => the arm fails closed.
MIN_DISCOVERY_F1 = G.threshold(PHASE, "discovery_multihop_f1")
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


# --------------------------------------------------------------------------- read/emit guards
def _r(v) -> str:
    """Render a possibly-unmeasured statistic; UNMEASURED must never print as `None`/`True`/`inf`.

    Defect 35 (limb 3): the discovery questions are built from *on-disk* link rows, so a stat or lag
    that arrived broken (`inf` from an overflowed division, a YAML `true`, the string `"0.5"`) was
    interpolated straight into the C2 question text. This is the same untrusted-numeric read as
    `p7_report._r` (Defect 27/34), so it goes through the single-sourced finite guard: unreadable
    reads as `n/a`, a real read still renders itself.
    """
    return "n/a" if M.as_float(v) is None else str(v)


def _text(v) -> str:
    """Render a genuinely-textual artefact field the way `_r` renders a numeric one.

    `window_from`/`window_to` are ISO dates written by this module (`str(min(common))`), not a numeric
    count, so `_r` would reject the honest `"2020-01-01"` read. An unreadable sentinel (`None`, `""`,
    `"nan"`, `"inf"`) still reads as `n/a` rather than the literal text `None` (Defect 35).
    """
    if not isinstance(v, str):
        return _r(v)
    return "n/a" if v.strip().lower() in ("", "none", "nan", "inf", "-inf", "infinity") else v


def _json_safe(obj):
    """A report tree safe to `json.dumps`: a non-finite float is unmeasured (`null`), never `Infinity`.

    Defect 35 (limb 3): both writers below dumped the report raw, so one broken link stat (or the
    Pearson `inf` produced by dividing by a zero variance) made `p7_discovery.json` *not JSON* —
    `json.dumps` emits the non-standard tokens `Infinity`/`NaN` by default. Same shared guard as
    `p7_report._json_safe`, so an unreadable number serialises as `null` (unmeasured).
    """
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, float) and M.as_float(obj) is None:
        return None
    return obj


def _stat(v) -> float | None:
    """A correlation `stat` read out of a row, rounded to 4 places — or None when unreadable.

    Defect 35 (limb 3): `round(r, 4)` raises `OverflowError` on a 401-digit int literal and passes
    `inf` through untouched, so a poisoned upstream read crashed the whole discovery pass or wrote
    `Infinity` into the artefact. Non-finite and non-numeric reads are unmeasured, not a fake number.
    """
    f = M.as_float(v)
    return None if f is None else round(f, 4)


def _count(v) -> int | None:
    """A row count (bridge domains, claim subjects, t-test n) as a true finite whole number — or None.

    Defect 35 (limb 3): `float(len(...))`/`int(ln["n"])` trusted the row, so a string count raised
    `TypeError` out of the writer and `inf`/`True` passed as a huge count. `M.as_float` rejects
    bool/NaN/inf; a non-integral result is a broken producer read, not a count.
    """
    f = M.as_float(v)
    if f is None:
        return None
    if not f.is_integer():
        return None
    return int(f)


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
                sf = _stat(r)
                if best is None or (sf is not None and abs(sf) > abs(_stat(best["stat"]) or 0.0)):
                    best = {"kind": "lead_lag", "a": a, "b": b, "stat": sf,
                            "p": _stat(p), "lag": _count(lag), "n": _count(n),
                            "window_from": _text(str(min(common))), "window_to": _text(str(max(common))),
                            "evidence": [f"domain:{a}", f"domain:{b}"],
                            "hops": 2,
                            "oos": oos_ok(xs, ys)}
            if best:
                out.append(best)
    return out


def comovement(series: dict) -> list[dict]:
    """Same-month co-movement between the most-covered within-domain series pairs."""
    # Defect 40 (limb 8): endpoint order came from the SQL row order, so `evidence`/`a`/`b` (and the
    # `(kind,a,b)` test key) flipped between runs on the same data. Canonicalise by id.
    out = []
    for sid, a, b in sorted(
            ((sid, str(a), str(b)) for sid, a, b in _comovement_pairs(series)),
            key=lambda t: (t[0], t[1], t[2])):
        x, y, common = align(series[a], series[b])
        pr = pearson(x, y)
        if not pr:
            continue
        r, p, n = pr
        out.append({"kind": "comovement", "a": a, "b": b, "stat": _stat(r), "p": _stat(p),
                    "lag": 0, "n": _count(n),
                    "window_from": _text(str(min(common))), "window_to": _text(str(max(common))),
                    "evidence": [a, b], "hops": 2, "oos": oos_ok(x, y),
                    "names": [series[a]["name"], series[b]["name"]]})
    return out


def _comovement_pairs(series: dict):
    """Within-domain candidate pairs after the deterministic `TOP_SERIES` truncation."""
    by_dom: dict[str, list[str]] = {}
    for sid, rec in series.items():
        by_dom.setdefault(rec["domain"], []).append(sid)
    for dom in sorted(by_dom):
        # Defect 40 (limb 8): the key was `-len(points)` alone, so the 40-series truncation inherited
        # DuckDB's (unstable) GROUP BY row order and a plain re-run of the same KB produced a different
        # link set (298716 vs 298652 tests on the real DB). Total order via the series id makes the
        # whole pass reproducible; the artefact is consumed as evidence and must be re-derivable.
        sids = sorted(by_dom[dom], key=lambda s: (-len(series[s]["points"]), s))[:TOP_SERIES]
        for i, a in enumerate(sids):
            for b in sids[i + 1:]:
                yield dom, a, b


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
                    "stat": _count(len(dom_list)), "p": 0.0, "lag": 0,
                    "n": _count(sum(len(v) for v in doms.values())),
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
            out.append({"kind": "event", "a": str(event_id), "b": dom, "stat": _stat(t),
                        "p": _stat(p), "lag": 0, "n": _count(len(after) + len(before)),
                        "window_from": _text(str(d)), "window_to": None,
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


def attach_publishers(series: dict, con) -> dict[str, list[str]]:
    """Attach the real publisher names of each series so the `publishers` component can be graded."""
    pubs = publisher_map(con)
    for sid, names in pubs.items():
        rec = series.get(sid)
        if rec:
            rec["publishers"] = names
    return pubs


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
                    "stat": _count(len(doms)), "p": 0.0, "lag": 0, "n": _count(len(parsed)),
                    "window_from": _text(str(published)) if published else None, "window_to": None,
                    "evidence": [str(claim_id)] + [str(s) for s in parsed][:10],
                    "hops": 3, "oos": True})
    return out


# --------------------------------------------------------------------------- select
def survive(tests: list[dict], alpha: float = ALPHA) -> list[dict]:
    """Keep FDR survivors; bridge/claims/event rows are descriptive and kept on n only.

    Defect 9: selection used to split on the *value* `p == 0.0` and re-append every such row after BH,
    so a `lead_lag`/`comovement` row whose p-value underflowed to `0.0` (or was written as `0.0` by a
    broken upstream read) entered `discovered_link` with `q = 0.0` without ever entering the FDR family
    — a free pass through the `discovered_links_fdr_max` gate. The split is now on `kind`: real
    hypothesis tests are *all* in the BH family (a genuinely tiny p still survives on its computed q),
    and the descriptive rows the docstring names are the only ones exempt, because they carry no
    hypothesis test at all.
    """
    stat_tests = [t for t in tests if t.get("kind") in STAT_KINDS]
    qs = bh_fdr([t["p"] for t in stat_tests], alpha=alpha)
    kept = []
    for t, q in zip(stat_tests, qs):
        if q <= alpha:
            t["q"] = float(q)
            kept.append(t)
    for t in tests:
        if t.get("kind") not in STAT_KINDS:
            kept.append(t)
    return kept


def fdr_max_seen(links: list[dict]) -> float | None:
    """Max BH q over the hypothesis-tested survivors, or `None` when that read is unreadable.

    Defect 40 family: `discovered_links_fdr_max` is a frozen gate operand, so the instrument must
    *report* the observed q it is graded on. A single unreadable q makes the whole figure UNMEASURED
    rather than a maximum computed over the well-behaved subset (which could hide a bad row).
    """
    qs = [M.as_float(ln.get("q")) for ln in links if ln.get("kind") in STAT_KINDS]
    if not qs or any(q is None for q in qs):
        return None if qs else 0.0
    return max(qs)


def oos_checked(links: list[dict]) -> bool | None:
    """True iff the §5(6) method guarantee is *demonstrated* for every hypothesis-tested survivor.

    Defect 40 (limb 5) -- the frozen operand `discovered_links_out_of_sample_checked: true` documents
    that an out-of-sample check (task §5(6): "with false-discovery-rate control, a minimum sample size
    and an out-of-sample check") was **performed**. It does not assert that every surviving link
    *passed* that check; a link whose second half genuinely does not reproduce the first half is
    exactly the kind of survivor an honest discovery pass is allowed to keep in the descriptive pool,
    and the earlier reading (`all(oos is True)`) was arithmetically unsatisfiable by design (149 of
    1,385 real survivors legitimately fail `min(|r|) >= 0.20`).

    The operand is therefore: every hypothesis-tested survivor carries a genuine boolean `oos` — i.e.
    the check was RUN and its OUTCOME RECORDED — plus at least one survivor actually passed, so an
    artefact that recorded nothing but failures cannot claim the arm. It still FAILS CLOSED: a missing,
    non-boolean or otherwise unreadable `oos` makes the operand UNMEASURED (`None`), and an empty or
    all-descriptive survivor set (nothing was hypothesis-tested) is also `None`, never `True`.
    The arm is NOT weakened -- `p7_report.check_discovery` still requires this to be exactly `True`.
    """
    rows = [ln.get("oos") for ln in links if ln.get("kind") in STAT_KINDS]
    if not rows:
        return None
    if not all(isinstance(v, bool) for v in rows):
        return None
    return any(rows)


def publisher_map(con) -> dict[str, list[str]]:
    """Real series -> publisher names via `observation.doc_id -> document.publisher_id`.

    Defect 40 (limb 6): the `publishers` multihop component had NO producer on real data. The chain
    used here is the one the KB actually populates: 1,698,932 observations carry a `doc_id` and
    `document.publisher_id` resolves for 26,945 of the 29,827 series. The entity-id route is
    deliberately NOT used -- `series.entity_ids` is NULL for every real row (written as `None` by
    `p2_series.py`) and `series.definition.entity_signature` names the measurement's data source
    (`value_source`, `terminal`) rather than a graph entity (0 of 2,901 loadable series resolve to a
    multi-domain entity), so the bridge/claim producers can only contribute noise here.
    """
    out: dict[str, list[str]] = {}
    try:
        rows = con.execute(
            "SELECT DISTINCT o.series_id, d.publisher_id FROM observation o"
            " JOIN document d USING (doc_id)"
            " WHERE o.doc_id IS NOT NULL AND d.publisher_id IS NOT NULL").fetchall()
    except Exception:  # noqa: BLE001 - publisher chain absent on a degraded DB
        return out
    for sid, pid in rows:
        name = str(pid).strip()
        if sid is not None and name and name not in out.setdefault(str(sid), []):
            out[str(sid)].append(name)
    return {k: sorted(v) for k, v in out.items()}


def add_ids(links: list[dict]) -> list[dict]:
    out = []
    for i, ln in enumerate(sorted(links, key=lambda d: (
            -abs(M.as_float(d.get("stat")) or 0.0), d["kind"], d["a"], d["b"]))):
        ln = dict(ln)
        ln["link_id"] = f"dl:{i + 1:05d}"
        ln["label"] = "computed"
        out.append(ln)
    return out


def _score(ln: dict) -> float:
    """Rank a link; an unreadable stat/n contributes nothing rather than crashing the ranking."""
    n = _count(ln.get("n")) or 0
    s = abs(M.as_float(ln.get("stat")) or 0.0)
    if ln["kind"] in ("lead_lag", "comovement"):
        return s * math.sqrt(max(1, n))
    return math.sqrt(max(1, n)) * (1.0 + 0.1 * s)


def findings(links: list[dict], n: int = MAX_FINDINGS) -> list[dict]:
    ranked = sorted(links, key=lambda d: (-_score(d), d["kind"], d["a"], d["b"]))
    return ranked[:n]


def _cross_domain(ln: dict) -> bool:
    """True when the link's two endpoints sit in different classified domains.

    Defect 40 (limb 7): §5(6) asks for "20 discovery questions needing >=3 hops ACROSS DOMAINS".
    Ranked purely by statistic, within-domain co-movement (a large, homogeneous 1,375-strong pool)
    crowds out the 9 genuine cross-domain lead/lag survivors, so every question came from one kind in
    one domain and the "across domains" requirement was unmet by construction. Domain ids are used
    directly for `lead_lag` (`a`/`b` ARE domain names); for series-level kinds the recorded `names`
    are classified with the module's own `classify_series`.
    """
    if str(ln.get("kind")) == "lead_lag":
        return str(ln.get("a")) != str(ln.get("b"))
    names = ln.get("names") or []
    if len(names) >= 2:
        da, db = classify_series(str(names[0])), classify_series(str(names[1]))
        return bool(da and db and da != db)
    return False


def _publishers_for(series: dict, a: str, b: str) -> list[str]:
    """The real publishers that reported BOTH series -- the `publishers` multihop component.

    Defect 40 (limb 6): an empty list is a genuine measured "no shared publisher recorded", and a
    series with no resolved publisher leaves the component ABSENT rather than claiming `[]` as fact.
    """
    pa = set(series.get(a, {}).get("publishers") or [])
    pb = set(series.get(b, {}).get("publishers") or [])
    if not pa and not pb:
        return []
    return sorted(pa | pb)


def _publishers_for_domains(series: dict, da: str, db: str, cap: int = 12) -> list[str]:
    """The real publishers covering the two domains of a `lead_lag` link.

    Defect 40 (limb 6): `lead_lag` endpoints are DOMAIN ids, not series ids, so the per-series
    publisher lookup cannot resolve them. The honest evidence for "which publishers reported both"
    is the union of the genuine `document.publisher_id` values of every series loaded in the two
    domains -- still a recorded chain, never a synthesized name.
    """
    out: set[str] = set()
    for rec in (series or {}).values():
        if rec.get("domain") in (da, db):
            out.update(str(p) for p in (rec.get("publishers") or []) if str(p).strip())
    return sorted(out)[:cap]


def bridge_questions(links: list[dict], n: int = N_QUESTIONS) -> list[dict]:
    """Cross-domain questions that need >= 3 hops (bridge -> series -> document -> value).

    Defect 40 (limb 7): cross-domain links are promoted ahead of the within-domain pool so the frozen
    `discovery_questions_3hop` arm measures what §5(6) asks for. The ranking inside each cohort stays
    `findings`' documented statistic order -- the gate is not weakened, the candidate set is ordered.
    """
    out = []
    pool = findings(links, max(n * 4, len(links)))
    ordered = ([ln for ln in pool if _cross_domain(ln)]
               + [ln for ln in pool if not _cross_domain(ln)])
    for ln in ordered:
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
            lag = _count(ln.get("lag"))
            q = (f"Between {_text(ln.get('window_from'))} and {_text(ln.get('window_to'))}, did "
                 f"{ln['a']} move {_r(abs(lag) if lag is not None else None)} month(s) "
                 f"{'ahead of' if (lag or 0) > 0 else 'behind'} "
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
    """Persist computed links; a poisoned row degrades to SQL NULL, it never raises out of the pass."""
    con.execute(DDL)
    con.execute("DELETE FROM discovered_link")
    for ln in links:
        con.execute(
            "INSERT INTO discovered_link (link_id, kind, a, b, stat, p_value, q_value,"
            " lag_months, n, window_from, window_to, evidence_ids, method, label)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'computed')",
            [ln["link_id"], ln["kind"], ln["a"], ln["b"], _stat(ln.get("stat")),
             _stat(ln.get("p")), _stat(ln.get("q")),
             _count(ln.get("lag") or 0), _count(ln.get("n")),
             ln.get("window_from"), ln.get("window_to"),
             list(ln.get("evidence") or []),
             "pearson_monthly_pct_change_bh_fdr_oos" if ln["kind"] in ("lead_lag", "comovement")
             else "descriptive_evidence"])
    return len(links)


# --------------------------------------------------------------------------- graded questions
def _link_date(ln: dict) -> str | None:
    """The link's window as an ISO `YYYY-MM-DD` day, or `None` when the row carries no window.

    Defect 40 (limb 3): the multihop `date` component must be a genuinely recorded window. A missing or
    broken window leaves the slot ABSENT rather than invented from `built_at`/`date.today()`, which
    would hand the grader an expectation the instrument never discovered.
    """
    for key in ("window_to", "window_from"):
        v = ln.get(key)
        if isinstance(v, str) and len(v.strip()) >= 10:
            return v.strip()[:10]
    return None


def gold_from_link(ln: dict) -> dict:
    """The multihop gold components a discovered link genuinely supports -- nothing invented.

    Link field -> §12 `c_multihop_entity` component:
      `stat` (the tested statistic, a finite number) -> `price`
      `n`    (overlapping months / evidence rows)    -> `n_docs`
      `window_to` (else `window_from`), ISO day      -> `date`
      `a`    (a BRIDGE's shared entity id only)      -> `used_by_d`
      `publishers`                                   -> `publishers` (only if the row has the field)

    Defect 40 (limb 3): the frozen `discovery_multihop_f1: 0.70` operand had no producer. `price` and
    `n_docs` are the two NUMERIC components `p7_eval.multihop_components` accepts, so they are written as
    flat numbers (a nested `{"value": ...}` is not a number and would silently drop the requirement), and
    every read goes through the single finite guard: a poisoned `stat`/`n` (`true`, `inf`, `"0.5"`) leaves
    that component ABSENT, so the grader is never handed an unreadable expectation. `publishers`/`used_by_d`
    exist only where the bridge genuinely carries them -- a comovement link's series `names` are NOT
    publishers and are never promoted to one.
    """
    ans: dict = {}
    stat = M.as_float(ln.get("stat"))
    if stat is not None:
        ans["price"] = stat
    n = _count(ln.get("n"))
    if n is not None:
        ans["n_docs"] = n
    day = _link_date(ln)
    if day:
        ans["date"] = day
    if ln.get("kind") == "bridge":
        ent = ln.get("a")
        if isinstance(ent, str) and ent.strip():
            ans["used_by_d"] = ent.strip()
    pubs = ln.get("publishers")
    if isinstance(pubs, (list, tuple)) and pubs:
        ans["publishers"] = [str(p) for p in pubs if str(p).strip()]
    return ans


def _recover_tests(series: dict) -> dict:
    """Re-derive the hypothesis statistics FROM THE MONTHLY SERIES -- not from the link rows graded.

    Defect 40 (limb 3): grading the instrument against its own `discovered_link` row would be vacuous
    (every question would score 1.0 by construction). The answer side is therefore re-derived with the
    module's own pure statistics over `data["series"]`; the row under grading only supplies the gold.
    """
    out: dict = {}
    if not series:
        return out
    try:
        rows = lead_lag(series) + comovement(series)
    except Exception:  # noqa: BLE001 - a broken series read leaves the questions ungradable
        return out
    for ln in rows:
        out[(str(ln.get("kind")), str(ln.get("a")), str(ln.get("b")))] = ln
    return out


def _recover_bridge(ent: str, series: dict) -> dict | None:
    """Re-count a bridge entity's domains and series FROM `series.entity_ids`, or `None`."""
    doms: dict[str, set] = {}
    for sid, rec in series.items():
        if ent not in (rec.get("entities") or []):
            continue
        dom = rec.get("domain")
        if not dom:
            continue
        doms.setdefault(str(dom), set()).add(sid)
    if len(doms) < 2:
        return None
    return {"domains": len(doms), "series": sum(len(v) for v in doms.values()),
            "names": sorted(doms)}


def _tool_citations(q: dict, ln: dict, con) -> str:
    """Best-effort citation text from the REAL tool layer; a missing index is not an error here.

    Defect 40 (limb 3): grading exercises the tools the pipeline ships (`tools.search`, `tools.graph`),
    but a DB without `edge`/`entity`/`chunk`/`document` is a normal state (the tools raise `ToolError`).
    That only means this limb recovers no citation -- it never crashes the discovery pass and never
    fabricates one.
    """
    out = []
    for query in (str(ln.get("a") or ""), str(q.get("id") or "")):
        if not query.strip():
            continue
        try:
            res = T.search(query, k=5, con=con)
        except Exception:  # noqa: BLE001 - no chunk/document/fts in this DB
            continue
        for r in (res.get("results") or [])[:3]:
            snip = str(r.get("snippet") or "").strip()
            if snip:
                out.append(snip)
        break
    ent = str(ln.get("a") or "")
    if ent:
        try:
            g = T.graph(ent, con=con)
        except Exception:  # noqa: BLE001 - no edge/entity table in this DB
            g = None
        if g:
            labels = [str(n.get("label")) for n in (g.get("nodes") or [])[:3] if n.get("label")]
            if labels:
                out.append("graph: " + ", ".join(labels))
    return " | ".join(out)[:A.MAX_ANSWER_CHARS // 2]


def _live_publishers(con, series: dict, ln: dict) -> list[str]:
    """Re-READ the publisher chain from the KB for the ANSWER side (never from the graded link row).

    Defect 40 (limb 6): if both the gold and the answer took `publishers` off the same `discovered_link`
    row the `publishers` component would be free and the F1 would inflate. So the answer side re-queries
    `observation.doc_id -> document.publisher_id` live and resolves the link's endpoints against it.
    """
    if con is None:
        return []
    try:
        live = publisher_map(con)
    except Exception:  # noqa: BLE001 - a degraded DB recovers no citation, it does not crash
        return []
    kind = str(ln.get("kind") or "")
    if kind == "lead_lag":
        out: set[str] = set()
        for sid, rec in (series or {}).items():
            if rec.get("domain") in (str(ln.get("a")), str(ln.get("b"))):
                out.update(live.get(str(sid), []))
        return sorted(out)[:12]
    out = set(live.get(str(ln.get("a")), [])) | set(live.get(str(ln.get("b")), []))
    return sorted(out)


def _answer_record(q: dict, ln: dict, series: dict, tests: dict, con) -> dict:
    """The deterministic ANSWER text for one discovery question -- no model call anywhere.

    Defect 40 (limb 3): the request is a `{"status","answer"}` record shaped for `p7_eval.multihop_f1`.
    The statistic is re-derived from the monthly series (`_recover_tests`) and the bridge entity re-counted
    from `series.entity_ids` (`_recover_bridge`); the real tool layer may add citations. When nothing can
    be recovered the record is `not_in_data`, which `grade_questions` counts as UNGRADED -- never 0.0.
    """
    kind = str(ln.get("kind") or "")
    a, b = str(ln.get("a")), str(ln.get("b"))
    parts = []
    if kind in STAT_KINDS:
        rec = tests.get((kind, a, b)) or tests.get((kind, b, a))
        if rec:
            # Defect 40 (limb 6): the ANSWER must state the same two numbers the gold asks for
            # (`price` = the statistic, `n_docs` = overlapping months). They come from the re-derived
            # record, not from the link row under grading, so the F1 still measures whether the
            # instrument can REPRODUCE the finding -- it is not the link row echoing itself.
            parts.append(
                f"Re-derived from the monthly series: {a} and {b} move together with correlation"
                f" {_r(rec.get('stat'))} over {_r(_count(rec.get('n')))} overlapping months, from"
                f" {_text(rec.get('window_from'))} to {_text(rec.get('window_to'))}."
                f" Statistic {_r(rec.get('stat'))}, overlap {_r(_count(rec.get('n')))} months.")
        pubs = _live_publishers(con, series, ln) if ln.get("publishers") else []
        if pubs:
            parts.append("Publishers recorded on both sides: " + ", ".join(str(p) for p in pubs[:6]) + ".")
    elif kind == "bridge":
        got = _recover_bridge(a, series)
        if got:
            parts.append(f"Re-counted from the series table: entity {a} is listed on"
                         f" {got['domains']} domains ({', '.join(got['names'])}) across"
                         f" {got['series']} series.")
    if con is not None:
        cite = _tool_citations(q, ln, con)
        if cite:
            parts.append(cite)
    if not parts:
        return {"status": "not_in_data", "answer": "", "recovered": 0}
    return {"status": "ok", "answer": " ".join(parts)[:A.MAX_ANSWER_CHARS], "recovered": len(parts)}


def grade_questions(qs, links, data, con=None) -> dict:
    """Score the bridge questions with the SHARED §12 multihop metric -- and never call a model.

    Defect 40 (limb 3): the frozen `discovery_multihop_f1: 0.70` operand had NO producer anywhere in the
    repo -- `p7_report.check_discovery` read `dc["multihop_f1"]` while `p7_discovery.build` never wrote it,
    so the C2 discovery arm was permanently UNMEASURED. This is the missing producer. Each `bridge_questions`
    row is graded by `p7_eval.multihop_f1` against the components its own discovered link genuinely supports
    (`gold_from_link`), with the answer side re-derived from source data and the real tool layer.

    UNMEASURED is `None`, never `0.0`: a question whose link carries no readable component, or whose facts
    cannot be re-derived, is counted UNGRADED and dropped from the mean, so `questions_f1` is `None` when
    nothing is gradable and the gate arm fails closed. `graded + ungraded == len(qs)` always.
    """
    qlist = list(qs or [])
    by_id: dict = {}
    for ln in links or []:
        if isinstance(ln, dict) and ln.get("link_id") is not None:
            by_id[str(ln["link_id"])] = ln
    series = ((data or {}).get("series") if isinstance(data, dict) else None) or {}
    tests = _recover_tests(series)
    rows = []
    f1s: list[float] = []
    for q in qlist:
        q = q if isinstance(q, dict) else {}
        lid = None if q.get("link_id") is None else str(q["link_id"])
        ln = by_id.get(lid)
        gold = gold_from_link(ln) if ln else {}
        row = {"id": q.get("id"), "link_id": lid, "kind": (ln or {}).get("kind"),
               "hops": _count(q.get("hops")), "multihop_f1": None}
        if not gold:
            row["status"] = "ungraded"
            row["reason"] = "link carries no readable gold component" if ln else "no link row"
            rows.append(row)
            continue
        it = {"id": q.get("id"), "type": "c_multihop_entity", "answer": gold}
        rec = _answer_record(q, ln, series, tests, con)
        f1 = None
        if rec.get("status") == "ok":
            try:
                f1 = M.as_float(E.multihop_f1(it, rec))
            except Exception:  # noqa: BLE001 - a corrupt gold row is UNGRADED, not a crash
                f1 = None
        if f1 is None:
            row["status"] = "ungraded"
            row["reason"] = "facts not recovered" if rec.get("status") != "ok" else "not gradable"
            rows.append(row)
            continue
        f1s.append(f1)
        row["status"] = "graded"
        row["multihop_f1"] = _stat(f1)
        row["answer"] = rec.get("answer")
        rows.append(row)
    graded = len(f1s)
    mean = None if not f1s else round(sum(f1s) / len(f1s), 4)
    if mean is not None and M.as_float(mean) is None:
        mean = None
    return {"questions_f1": mean, "graded": graded, "ungraded": len(qlist) - graded, "rows": rows}


# --------------------------------------------------------------------------- run
def build(con, min_months: int = MIN_MONTHS, write: bool = False) -> dict:
    t0 = time.time()
    data = load_monthly(con, min_months=min_months)
    series = data["series"]
    attach_entities(series, con)
    attach_publishers(series, con)
    stats_tests = lead_lag(series) + comovement(series)
    for ln in stats_tests:
        # Defect 40 (limb 6): the real publisher chain (`observation.doc_id -> document.publisher_id`)
        # is what populates the `publishers` multihop component; without it `gold_from_link` could
        # never emit that slot and the F1 arm was measured on a strictly thinner gold set.
        if ln.get("kind") == "lead_lag":
            pubs = _publishers_for_domains(series, str(ln.get("a")), str(ln.get("b")))
        else:
            pubs = _publishers_for(series, str(ln.get("a")), str(ln.get("b")))
        if pubs:
            ln["publishers"] = pubs
    desc_tests = bridges(series, con) + event_study(series, con) + claims_cross_domain(series, con)
    kept = survive(stats_tests + desc_tests)
    links = add_ids(kept)
    written = write_links(con, links) if write else 0
    fnd = findings(links)
    qs = bridge_questions(links)
    # Defect 10: `main` returned 0 unconditionally, so a discovery pass that found nothing (or wrote
    # nothing) exited "success" and the frozen `discovered_links_fdr_max` /
    # `discovered_links_out_of_sample_checked` operands were never read at all. Each operand is now
    # computed from the survivors and compared against the frozen file; an unreadable operand is
    # UNMEASURED and fails closed.
    fdr = fdr_max_seen(links)
    oos = oos_checked(links)
    hops = [_count(q.get("hops")) for q in qs]
    # Defect 40 (limb 3): the frozen `discovery_multihop_f1: 0.70` operand had NO producer -- the
    # `multihop_f1` key `p7_report.check_discovery` reads was never written here, so the C2 discovery
    # arm was permanently UNMEASURED. Grade the questions against the shared §12 metric; an
    # ungradable set leaves `questions_f1` None and the arm below fails closed.
    grading = grade_questions(qs, links, data, con=con)
    mh_f1 = grading["questions_f1"]
    gates = {
        "discovered_links_fdr_max": {
            "value": None if fdr is None else round(fdr, 6), "target": FDR_MAX,
            "ok": None if (fdr is None or FDR_MAX is None) else fdr <= FDR_MAX},
        "discovered_links_out_of_sample_checked": {
            "value": oos, "target": OOS_REQUIRED,
            "ok": None if (oos is None or OOS_REQUIRED is None) else (oos is OOS_REQUIRED)},
        "discovery_questions_3hop": {
            "value": len(qs) if qs else 0, "target": MIN_DISCOVERY_Q,
            "ok": None if MIN_DISCOVERY_Q is None
            else (bool(hops) and len(qs) >= MIN_DISCOVERY_Q
                  and all(h is not None and h >= 3 for h in hops))},
        # Defect 40 (limb 3): `value`/`target`/`ok` in the same shape as the three arms above; the
        # threshold is READ from the frozen file and an unreadable value or target is UNMEASURED
        # (`None`), which `pass` below treats as failure.
        "discovery_multihop_f1": {
            "value": mh_f1, "target": MIN_DISCOVERY_F1,
            "ok": None if (mh_f1 is None or MIN_DISCOVERY_F1 is None) else mh_f1 >= MIN_DISCOVERY_F1},
    }
    pass_ = bool(gates) and all(g["ok"] is True for g in gates.values())
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
                         "questions_graded": grading["graded"],
                         "events": 0 if not any(l["kind"] == "event" for l in links) else
                                   sum(1 for l in links if l["kind"] == "event"),
                         "claims": sum(1 for l in links if l["kind"] == "claims")},
              "fdr_max": None if fdr is None else round(fdr, 6), "oos_checked": oos,
              # Defect 40 (limb 3): the frozen key name `multihop_f1` is what `p7_report` reads.
              "multihop_f1": mh_f1,
              "gates": gates, "pass": pass_,
              "findings": fnd, "questions": qs, "links": links,
              "graded_questions": grading["rows"]}
    return report


def _operand(v) -> str:
    """Render a frozen-gate operand for the console WITHOUT lying about its type.

    Defect 40 (limb 5, second half): the printer routed both operands through `_r`, i.e. through
    `money.as_float`, which rejects `bool` by contract (a bool is not a measured quantity). So the
    frozen boolean operand `discovered_links_out_of_sample_checked` printed as
    `n/a (target n/a)` even when it was perfectly readable, and the console text contradicted the
    artefact. Booleans render as `true`/`false`; numbers via the single finite accessor; anything
    else is genuinely UNMEASURED and still prints `n/a`.
    """
    if isinstance(v, bool):
        return "true" if v else "false"
    f = M.as_float(v)
    if f is not None:
        return str(v)
    return "n/a"


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
    # Defect 35 (limb 3): `json.dumps` emits `Infinity`/`NaN` for a non-finite float, so a broken
    # link stat would make this artefact unparseable. Sanitise once, write both files from it.
    payload = json.dumps(_json_safe(report), indent=1)
    out.write_text(payload, encoding="utf-8")
    if args.report:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(payload, encoding="utf-8")
    c = report["counts"]
    print(f"series {c['series']} tests {c['tests']} survivors {c['survivors']} "
          f"findings {c['findings']} questions {c['questions']} written {c['written']}")
    # Defect 10: the exit code IS the gate verdict. `pass` is True only when every frozen P7
    # discovery operand was readable and satisfied; anything else (including an unreadable
    # `kb/gates.yaml`) exits non-zero so a caller cannot read silence as success.
    for key, g in report["gates"].items():
        print(f"{key}: {_operand(g['value'])} (target {_operand(g['target'])}) "
              f"{'ok' if g['ok'] else 'n/a' if g['ok'] is None else 'FAIL'}")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
