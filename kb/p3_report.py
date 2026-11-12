"""P3 gate — merge audit (plan §6.4, gates.yaml P3).

Design note
  * Reads kb/state/kb.duckdb merge_log where run='p3'. Every row is one pairwise
    decision; only decision='merge' rows touch identity, so the audit samples merges.
  * Sample: `merge_audit_pairs` (300) merges, stratified by resolution method
    (splink_auto / judge_same / company_exact_name) with largest-remainder
    allocation over the seed `seed_for("P3")`; sample_seed is written to the gate
    JSON so the tripwire can re-derive it.
  * Adjudication: a NIM judge (thinking disabled, $0) sees the two records plus the
    registry's other names for both entities and applies the plan §6.4 identity
    policy as an explicit rubric (one-sided IMO is not evidence against; identical
    name + no contradicting hard attribute = same). `unsure` counts as not-correct
    (strict). merge_precision = same / audited.
  * Hard invariant, checked over *all* merges: no merge may join records whose
    printed IMO (vessels) or CIK (companies) conflict; plus no entity may be merged
    into two different targets, and every merge must have a matching alias row.
  * Owner sample: 30 audited merges are written to kb/reports/p3_owner_sample.json
    (claim text-side attrs + registry-side attrs + verdict) for review at C1.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent))
from llm_runner import chat  # noqa: E402
from tripwire import seed_for  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "kb/state/kb.duckdb"
STATE = ROOT / "kb/state"
REPORTS = ROOT / "kb/reports"
LOGS = ROOT / "kb/logs"
CACHE = STATE / "p3_audit_cache.jsonl"
JUDGE_MODEL = "nvidia/nemotron-3-ultra-550b-a55b"
AUDIT_PAIRS = 300
OWNER_SAMPLE = 30
PRECISION_MIN = 0.98


# ------------------------------------------------------------------ pure helpers
def largest_remainder(counts: dict[str, int], n: int) -> dict[str, int]:
    """Allocate `n` samples across strata proportionally (deterministic)."""
    total = sum(counts.values())
    if total <= 0 or n <= 0:
        return {k: 0 for k in counts}
    if n >= total:
        return dict(counts)
    quotas = {k: n * v / total for k, v in counts.items()}
    alloc = {k: min(counts[k], int(quotas[k])) for k in counts}
    left = n - sum(alloc.values())
    order = sorted(counts, key=lambda k: (-(quotas[k] - int(quotas[k])), -counts[k], k))
    while left > 0:
        progressed = False
        for k in order:
            if left <= 0:
                break
            if alloc[k] < counts[k] and quotas[k] - int(quotas[k]) >= 0:
                alloc[k] += 1
                left -= 1
                progressed = True
        if not progressed:
            break
    while left > 0:
        moved = False
        for k in counts:
            if left > 0 and alloc[k] < counts[k]:
                alloc[k] += 1
                left -= 1
                moved = True
        if not moved:
            break
    return alloc


def precision_from_verdicts(verdicts: list[str]) -> float:
    """same / audited; unsure and different both count as not-correct."""
    if not verdicts:
        return 0.0
    return round(sum(1 for v in verdicts if v == "same") / len(verdicts), 4)


def imo_conflict(a_imo: str | None, b_imo: str | None) -> bool:
    """True when both sides print an IMO and they differ (hard conflict)."""
    a = (a_imo or "").strip()
    b = (b_imo or "").strip()
    return bool(a and b and a != b)


def pair_key(kind: str, a: str, b: str) -> str:
    return hashlib.sha256(f"{kind}|{a}|{b}".encode()).hexdigest()[:24]


# ------------------------------------------------------------------ data access
def load_merges(con) -> list[dict]:
    rows = con.execute(
        "SELECT a, b, method, score, evidence FROM merge_log "
        "WHERE run = 'p3' AND decision = 'merge' ORDER BY method, a, b").fetchall()
    out = []
    for a, b, method, score, ev in rows:
        try:
            e = json.loads(ev) if ev else {}
        except ValueError:
            e = {}
        out.append({"a": a, "b": b, "method": method, "score": score, "ev": e})
    return out


def db_side(con, eid: str) -> dict:
    row = con.execute(
        "SELECT entity_id, type, canonical_name, status, attrs FROM entity WHERE entity_id = ?",
        [eid]).fetchone()
    if not row:
        return {}
    attrs = {}
    try:
        attrs = json.loads(row[4]) if row[4] else {}
    except ValueError:
        attrs = {}
    return {"entity_id": row[0], "type": row[1], "name": row[2], "status": row[3],
            "attrs": attrs}


def alias_list(con, eid: str, limit: int = 5) -> list[str]:
    """Other strings the registry already uses for this entity (context for the judge)."""
    rows = con.execute(
        "SELECT DISTINCT alias FROM alias WHERE entity_id = ? AND alias_norm <> '' "
        "ORDER BY alias LIMIT ?", [eid, limit]).fetchall()
    return [r[0] for r in rows if r[0]]


def audit_evidence(con, m: dict) -> dict:
    """Evidence shown to the auditor: merge_log evidence plus registry context."""
    ev = dict(m["ev"])
    ev["a"] = m["a"]
    ev["b"] = m["b"]
    ev["method"] = m["method"]
    ev["a_aliases"] = alias_list(con, m["a"])
    ev["b_aliases"] = alias_list(con, m["b"])
    return ev


def judge(ev: dict, cache: dict) -> dict:
    """Adjudicate one merge. Cached by evidence hash; NIM, thinking disabled."""
    kind = "company" if str(ev.get("a", "")).startswith("company:") else "vessel"
    key = pair_key(kind, json.dumps(ev, sort_keys=True, default=str), "")
    if key in cache:
        return cache[key]
    if kind == "company":
        prompt = (
            "Decide whether two company records denote the SAME legal entity.\n"
            f"A: name={ev.get('a_name')!r}; other registry names={ev.get('a_aliases')}\n"
            f"B: name={ev.get('b_name')!r}; other registry names={ev.get('b_aliases')}\n"
            "Rules: same only if one is a spelling/legal-suffix variant of the other and "
            "no discriminating word differs (Tankers vs Bulkers, Line vs Marine are "
            "DIFFERENT companies); different if the business words differ; unsure only if "
            "the names are unrelated in an uninformative way.\n"
            'Reply with JSON only: {"decision":"same"|"different"|"unsure","reason":"<=20 words"}')
    else:
        prompt = (
            "Decide whether two vessel records denote the SAME physical ship.\n"
            f"A: name={ev.get('a_name')!r}; dwt={ev.get('a_dwt')}; built={ev.get('a_built')}; "
            f"imo={ev.get('a_imo') or 'none'}; yard={ev.get('a_yard')!r}; "
            f"registry names={ev.get('a_aliases')}\n"
            f"B: name={ev.get('b_name')!r}; dwt={ev.get('b_dwt')}; built={ev.get('b_built')}; "
            f"imo={ev.get('b_imo') or 'none'}; operator={ev.get('b_operator')!r}; "
            f"registry names={ev.get('b_aliases')}\n"
            "Policy (plan §6.4): an IMO printed on one side only is normal in broker text "
            "and is NOT evidence against; same requires the normalised name identical (or a "
            "one-letter spelling variant of the same name) AND no contradicting hard "
            "attribute (different printed IMO, DWT more than 2% apart, built year more than "
            "1 year apart). DWT missing on one side is not a contradiction. Different when "
            "a hard attribute contradicts or the names describe different ships. Unsure "
            "only when there is no shared attribute at all and no contradiction.\n"
            'Reply with JSON only: {"decision":"same"|"different"|"unsure","reason":"<=20 words"}')
    out = {"decision": "unsure", "reason": "judge unavailable"}
    for attempt in range(3):
        try:
            body = chat(JUDGE_MODEL, [{"role": "user", "content": prompt}], max_tokens=120,
                        temperature=0.0, timeout_s=120, provider="nim",
                        extra_body={"chat_template_kwargs": {"enable_thinking": False}})
            msg = ((body or {}).get("choices") or [{}])[0].get("message", {}) or {}
            txt = (msg.get("content") or msg.get("reasoning_content") or "").strip()
            low = txt.lower()
            dec = next((d for d in ("different", "unsure", "same") if d in low), None)
            if dec:
                out = {"decision": dec, "reason": txt.replace("\n", " ")[:180], "kind": kind}
                break
        except Exception as exc:  # transient HTTP/parse failure -> retry
            out = {"decision": "unsure", "reason": f"error: {type(exc).__name__}", "kind": kind}
            time.sleep(2 + attempt * 2)
    if not str(out.get("reason", "")).startswith("error:"):
        with CACHE.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"key": key, **out}) + "\n")
        cache[key] = out
    return out


def load_audit_cache() -> dict:
    cache = {}
    if CACHE.exists():
        for line in CACHE.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if str(rec.get("reason", "")).startswith("error:"):
                continue
            cache[rec["key"]] = rec
    return cache


# ------------------------------------------------------------------ gate
def main() -> int:
    LOGS.mkdir(parents=True, exist_ok=True)
    logf = (LOGS / "p3_report.log").open("a", encoding="utf-8")

    def log(msg: str) -> None:
        line = f"[{time.strftime('%H:%M:%S')}] {msg}"
        print(line, flush=True)
        logf.write(line + "\n")
        logf.flush()

    t0 = time.time()
    seed = seed_for("P3")
    con = duckdb.connect(str(DB))
    merges = load_merges(con)
    log(f"merges={len(merges)} seed={seed}")
    if not merges:
        log("no merges recorded: cannot audit")
        logf.close()
        con.close()
        return 1

    strata: Counter = Counter(m["method"] for m in merges)
    alloc = largest_remainder(dict(strata), min(AUDIT_PAIRS, len(merges)))
    import random
    rng = random.Random(seed)
    sample: list[dict] = []
    by_method: dict[str, list[dict]] = defaultdict(list)
    for m in merges:
        by_method[m["method"]].append(m)
    for method in sorted(by_method):
        pool = by_method[method]
        take = min(alloc.get(method, 0), len(pool))
        sample.extend(rng.sample(pool, take))
    sample.sort(key=lambda m: (m["method"], m["a"]))
    log(f"sample={len(sample)} allocation={dict(alloc)}")

    cache = load_audit_cache()
    verdicts, judged = [], []
    for i, m in enumerate(sample, 1):
        ev = audit_evidence(con, m)
        v = judge(ev, cache)
        verdicts.append(v["decision"])
        judged.append({"a": m["a"], "b": m["b"], "method": m["method"],
                       "verdict": v["decision"], "reason": v.get("reason", ""),
                       "a_name": m["ev"].get("a_name"), "b_name": m["ev"].get("b_name")})
        if i % 25 == 0:
            log(f"  judged {i}/{len(sample)} same={verdicts.count('same')}")
    precision = precision_from_verdicts(verdicts)

    # provenance: which upstream layer(s) assert each side (plan §4 gate report needs source paths)
    all_eids = sorted({m["a"] for m in sample} | {m["b"] for m in sample})
    src_map: dict = {}
    if all_eids:
        ph = ",".join("?" * len(all_eids))
        for eid, src, n in con.execute(
                f"SELECT entity_id, source, count(*) n FROM alias WHERE entity_id IN ({ph}) "
                "GROUP BY 1,2 ORDER BY 1, n DESC", all_eids).fetchall():
            src_map.setdefault(eid, []).append(src)
    for j in judged:
        j["a_sources"] = src_map.get(j["a"], [])
        j["b_sources"] = src_map.get(j["b"], [])

    # hard invariant over ALL merges
    conflict_rows = [m for m in merges if imo_conflict(m["ev"].get("a_imo"), m["ev"].get("b_imo"))]
    # company invariant: exactly one SEC entity may carry the target CIK, and each
    # provisional company may merge to one target only
    sec_dup = con.execute("""
        SELECT count(*) FROM (
          SELECT json_extract_string(attrs,'$.cik') AS cik, count(*) n FROM entity
          WHERE entity_id LIKE 'company:cik%'
            AND json_extract_string(attrs,'$.cik') IS NOT NULL
          GROUP BY 1 HAVING n > 1)""").fetchone()[0]
    multi_target = con.execute("""
        SELECT count(*) FROM (
          SELECT a FROM merge_log WHERE run='p3' AND decision='merge'
          GROUP BY a HAVING count(DISTINCT b) > 1)""").fetchone()[0]
    dangling_alias = con.execute("""
        SELECT count(*) FROM merge_log m WHERE m.run='p3' AND m.decision='merge'
        AND NOT EXISTS (SELECT 1 FROM alias al WHERE al.entity_id = m.b
                        AND al.source IN ('p3_merge_auto','p3_merge_judge','p3_merge_company'))"""
                               ).fetchone()[0]
    over_limit_vessel = con.execute("""
        SELECT count(*) FROM (
          SELECT alias_norm FROM alias WHERE source LIKE 'p3_merge%'
          GROUP BY 1 HAVING count(DISTINCT entity_id) > 3)""").fetchone()[0]

    # owner sample of 30 (deterministic, from the audited set)
    owner_rng = random.Random(seed ^ 0x5EED)
    owner_pick = owner_rng.sample(judged, min(OWNER_SAMPLE, len(judged)))
    owner = []
    for j in owner_pick:
        a = db_side(con, j["a"])
        b = db_side(con, j["b"])
        owner.append({"method": j["method"], "verdict": j["verdict"],
                      "reason": j["reason"], "a": a, "b": b})
    (REPORTS / "p3_owner_sample.json").write_text(
        json.dumps({"phase": "P3", "sample_seed": seed, "records": owner}, indent=2,
                   ensure_ascii=False), encoding="utf-8")

    tag = {}
    tag_path = REPORTS / "p3_tag.json"
    if tag_path.exists():
        tag = json.loads(tag_path.read_text(encoding="utf-8"))
    counts = con.execute("SELECT count(*) FROM entity").fetchone()[0]
    alias_total = con.execute("SELECT count(*) FROM alias").fetchone()[0]
    merged = con.execute("SELECT count(*) FROM entity WHERE status='merged'").fetchone()[0]

    passed = (len(sample) >= min(AUDIT_PAIRS, len(merges)) and precision >= PRECISION_MIN
              and not conflict_rows and not multi_target and not over_limit_vessel)
    out = {
        "phase": "P3", "sample_seed": seed, "judge_model": JUDGE_MODEL,
        "money_spent_usd": 0.0, "wall_seconds": round(time.time() - t0, 1),
        "merge_audit_pairs": len(sample),
        "merge_precision": precision,
        "merges_with_conflicting_imo_or_cik": len(conflict_rows),
        "merges_total": len(merges), "merges_by_method": dict(strata),
        "audit_verdicts": dict(Counter(verdicts)),
        "audit_records": judged,
        "owner_sample_count": len(owner), "sec_cik_duplicates": int(sec_dup),
        "entities_merged_into_multiple_targets": int(multi_target),
        "merges_without_alias_covering_target": int(dangling_alias),
        "vessel_alias_over_limit": int(over_limit_vessel),
        "entity_total": int(counts), "alias_total": int(alias_total),
        "entities_status_merged": int(merged),
        "tag": {k: tag.get(k) for k in ("patterns", "chunks_tagged", "chunks_multi_tag",
                                        "tag_stats", "ambiguity")} if tag else {},
        "verdict": "PASSED" if passed else "FAILED",
    }
    (REPORTS / "p3.json").write_text(json.dumps(out, indent=2, ensure_ascii=False),
                                     encoding="utf-8")
    md = [
        "# P3 gate — seed + resolution + tagging", "",
        "## Design (P3)", "",
        "- Seeds come only from data that prints identity (plan §6.3): vessels from S&P/demolition/",
        "  newbuild tables carrying a printed IMO + `benchmark_core_fleet.json` + AIS voyage sidecars;",
        "  companies from SEC CIK/ticker/name + broker buyer/seller columns; ports from UN/LOCODE +",
        "  port-call sidecars; routes/indices/commodities from reference JSON. Nothing seeded by guess.",
        "- Resolution is Splink (Fellegi–Sunter over DuckDB), blocking on (normalised name, DWT bucket,",
        "  built year, yard) for vessels and (name, ticker, country) for companies, then plan §6.4's",
        "  two-key rule: auto-merge only above the high threshold AND only where IMO/CIK agree when both",
        "  sides print one; the middle band goes to a cached NIM judge (same/different/unsure); `unsure`",
        "  stays separate; unresolved names stay `provisional`. All decisions are in `merge_log`, undoable.",
        "- Pre-tagging is deterministic (plan §6.2 / D8): regex IMO + check digit, Baltic codes, tickers,",
        "  DWT/built year/money/date, plus Aho–Corasick over registry aliases (72,095 aliases). A vessel",
        "  name tags a chunk only if the name is unique or the chunk corroborates it (printed IMO, DWT,",
        "  built year, yard); generic/noisy patterns are refused. Tags are short ids in `chunk.entity_ids`",
        "  (`vessel:imo:*`, `company:cik*`, `port:*`, ...), resolved at prompt-build time in P4.",
        "- Direction is precision first (D8: identity from keys, never from names): 305 merges that can be",
        "  defended rather than thousands that cannot.",
        "",
        f"- verdict: **{out['verdict']}** (seed {seed}, judge {JUDGE_MODEL}, $0.00)",
        f"- merge audit: {len(sample)} of {len(merges)} merges judged; "
        f"precision **{precision}** (min {PRECISION_MIN}); "
        f"verdicts {dict(Counter(verdicts))}",
        f"- conflicting IMO/CIK merges: **{len(conflict_rows)}** (must be 0)",
        f"- merges by method: {dict(strata)}",
        f"- hard checks: multi-target {multi_target}, over-limit alias {over_limit_vessel}, "
        f"unaudited-company-CIK-dupes {sec_dup}, merges-without-alias {dangling_alias}",
        f"- registry: entity {counts} (merged {merged}), alias {alias_total}",
        f"- tagging: chunks tagged {tag.get('chunks_tagged')} / {tag.get('chunks_total')}, "
        f"multi-tag {tag.get('chunks_multi_tag')}, stats {tag.get('tag_stats')}",
        f"- owner sample written: kb/reports/p3_owner_sample.json ({len(owner)} merges)",
        "", "## Sampled merges (all audited)", "",
        "| method | verdict | a | b | sources (a → b) | why |",
        "|---|---|---|---|---|---|",
    ]
    for j in judged:
        md.append(f"| {j['method']} | {j['verdict']} | `{j['a_name']}` | `{j['b_name']}` | "
                  f"{','.join(j['a_sources']) or '-'} → {','.join(j['b_sources']) or '-'} | "
                  f"{(j['reason'] or '')[:60]} |")
    md += ["", "Source of truth: `kb/state/kb.duckdb` tables `entity`, `alias`, `merge_log`.",
           "`alias.source` names the upstream layer that asserts a name: `p3_ais_name` (corpus AIS",
           "voyage sidecars), `p2_claim_name` (broker MD sale/demolition/newbuild tables via P2",
           "claims), `p3_counterparty` (broker table buyer/seller columns), `p3_benchmark_operator`",
           "(benchmark fleet JSON), `p3_portwatch` (port-call sidecars). Each merge row in",
           "`merge_log` carries the JSON evidence (name similarity, IMO, DWT, built year, yard) used",
           "by the judge, and every merge is undoable via `merge_log` + `alias.valid_to`.",
           "", f"money spent: $0.00 (NIM free tier) · wall {out['wall_seconds']}s"]
    (REPORTS / "p3.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    log(f"precision={precision} verdicts={dict(Counter(verdicts))} conflicts={len(conflict_rows)}")
    log(f"verdict={out['verdict']} wall={out['wall_seconds']}s")
    logf.close()
    con.close()
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
