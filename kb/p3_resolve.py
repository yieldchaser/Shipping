"""P3 stage 2 — vessel identity resolution (plan §6.4).

Design note
  * Sources: provisional vessels from P2 claims (name only, no printed IMO) linked
    against confirmed keyed vessels (AIS registry + benchmark core fleet, IMO verified).
  * Blocking (Splink, link_only): exact name_norm, (name_head4, built), (name_head4, dwt_bucket).
  * Fellegi–Sunter weights are evidence only; the *decision* is a deterministic tier
    (p3_names.decide_tier) so an untrained/loose model can never force a merge.
  * Auto-merge needs: EXACT normalised name, >= 2 corroborating attributes, exactly
    one candidate, and no conflicting printed IMO. Near-miss spellings ("Grace Leo"
    vs "Grace Leon") are two letters away from a different ship, so they are always
    adjudicated. Middle band goes to a cached judge model (same|different|unsure).
  * Evidence sufficiency veto (plan §6.4): even a judge "same" is refused when the
    pair shares no hard attribute on both sides (name alone cannot identify a ship —
    plan D8) or when DWT/built-year contradict. Every decision lands in merge_log;
    merges are written as alias rows so they stay undoable.
  * Companies: only exact normalised company-name matches into a single SEC CIK
    entity; vessel-class words (Tankers/Bulkers/Lines) are discriminating, not legal
    suffixes, so they are never stripped.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import duckdb
import pandas as pd
from rapidfuzz import fuzz

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p3_names as N  # noqa: E402
from llm_runner import chat  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "kb/state/kb.duckdb"
STATE = ROOT / "kb/state"
REPORTS = ROOT / "kb/reports"
LOGS = ROOT / "kb/logs"
PAIRS = STATE / "p3_pairs.parquet"
CLAIMS = STATE / "p3_claims.parquet"
KNOWN = STATE / "p3_known.parquet"
JUDGE_CACHE = STATE / "p3_judge_cache.jsonl"
RUN = "p3"
JUDGE_MODEL = "nvidia/nemotron-3-ultra-550b-a55b"

MONEY = 0.0  # NIM free tier; recorded so the gate can report spend honestly


# --------------------------------------------------------------------------- frames
def build_claims(con) -> pd.DataFrame:
    """One row per provisional vessel: best printed attributes seen in P2 claims."""
    prov = {}
    for eid, name, attrs in con.execute(
            "SELECT entity_id, canonical_name, attrs FROM entity "
            "WHERE entity_id LIKE 'vessel:prov:%'").fetchall():
        a = json.loads(attrs) if attrs else {}
        key = str(a.get("vessel_key") or "")
        if key:
            prov[key] = (eid, name)
    best: dict[str, dict] = {}
    imos: dict[str, set] = defaultdict(set)
    for (claimed,) in con.execute("SELECT claimed FROM mention WHERE claimed LIKE '%vessel_key%'").fetchall():
        try:
            c = json.loads(claimed)
        except Exception:
            continue
        key = str(c.get("vessel_key") or "")
        if not key.startswith("prov:") or key not in prov:
            continue
        eid, cname = prov[key]
        printed = c.get("printed") or {}
        name = (printed.get("vessel_name") or c.get("name") or cname or "").strip()
        nm = N.norm_vessel_name(name)
        if not nm:
            continue
        rec = best.setdefault(eid, {"entity_id": eid, "name": name, "name_norm": nm,
                                    "dwt": None, "built": None, "yard": None,
                                    "n_claims": 0, "printed_imo": ""})
        rec["n_claims"] += 1
        dwt = N.parse_dwt(printed.get("dwt"))
        built = N.parse_year(printed.get("built"))
        yard = (printed.get("yard") or "").strip() or None
        if dwt and not rec["dwt"]:
            rec["dwt"] = dwt
        if built and not rec["built"]:
            rec["built"] = built
        if yard and not rec["yard"]:
            rec["yard"] = yard
        imo = N.find_imo(printed.get("imo") or "")
        if imo:
            imos[eid].add(imo)
    for eid, rec in best.items():
        rec["printed_imo"] = ",".join(sorted(imos[eid]))
        rec["n_printed_imos"] = len(imos[eid])
    df = pd.DataFrame(list(best.values()))
    if df.empty:
        raise SystemExit("no provisional claims found")
    df["row_id"] = df["entity_id"]
    df["name_head4"] = df["name_norm"].str[:4]
    df["dwt_bucket"] = df["dwt"].fillna(0).astype(int) // 1000
    df["built_s"] = df["built"].fillna(0).astype(int).astype(str)
    df["side"] = "claim"
    return df


def build_known(con) -> pd.DataFrame:
    rows = con.execute("""
        SELECT entity_id, canonical_name, attrs FROM entity
        WHERE entity_id LIKE 'vessel:imo:%'""").fetchall()
    recs = []
    for eid, name, attrs in rows:
        a = json.loads(attrs) if attrs else {}
        nm = N.norm_vessel_name(name)
        if not nm:
            continue
        recs.append({"entity_id": eid, "name": name, "name_norm": nm,
                     "dwt": N.parse_dwt(a.get("dwt")), "built": N.parse_year(a.get("built")),
                     "yard": a.get("yard") or None, "operator": a.get("operator") or None,
                     "imo": str(a.get("imo") or eid.rsplit(":", 1)[-1]),
                     "class": a.get("class"), "sector": a.get("sector")})
    df = pd.DataFrame(recs)
    if df.empty:
        raise SystemExit("no keyed vessels found")
    df["row_id"] = df["entity_id"]
    df["name_head4"] = df["name_norm"].str[:4]
    df["dwt_bucket"] = df["dwt"].fillna(0).astype(int) // 1000
    df["built_s"] = df["built"].fillna(0).astype(int).astype(str)
    df["side"] = "known"
    return df


SPLINK_COLS = ["unique_id", "name", "name_norm", "dwt", "built", "yard", "imo", "operator",
               "row_id", "name_head4", "dwt_bucket", "built_s", "side"]


def align(claims: pd.DataFrame, known: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Splink 5 needs identical column sets on both sides of a link_only job."""
    left = claims.copy()
    right = known.copy()
    left["unique_id"] = left["entity_id"]
    right["unique_id"] = right["entity_id"]
    for col in ("imo", "operator"):
        if col not in left.columns:
            left[col] = ""
        if col not in right.columns:
            right[col] = ""
    left["dwt_bucket"] = left["dwt_bucket"].astype(int)
    right["dwt_bucket"] = right["dwt_bucket"].astype(int)
    return left[SPLINK_COLS], right[SPLINK_COLS]


# --------------------------------------------------------------------------- splink
def splink_pairs(claims: pd.DataFrame, known: pd.DataFrame, log=print) -> pd.DataFrame:
    import splink.comparison_library as cl
    from splink import DuckDBAPI, Linker, SettingsCreator, block_on

    left, right = align(claims, known)
    dbapi = DuckDBAPI()
    l = dbapi.register(left)
    r = dbapi.register(right)
    settings = SettingsCreator(
        link_type="link_only",
        comparisons=[
            cl.DamerauLevenshteinAtThresholds("name_norm", [1, 2]),
            cl.ExactMatch("built_s"),
            cl.ExactMatch("dwt_bucket"),
        ],
        blocking_rules_to_generate_predictions=[
            block_on("name_norm"),
            block_on("name_head4", "built_s"),
            block_on("name_head4", "dwt_bucket"),
        ],
        probability_two_random_records_match=0.0001,
        retain_matching_columns=True,
        additional_columns_to_retain=["name", "dwt", "built", "yard", "imo", "operator", "dwt_bucket"],
    )
    linker = Linker([l, r], settings)
    t0 = time.time()
    linker.training.estimate_u_using_random_sampling(max_pairs=2_000_000, seed=17)
    try:
        linker.training.estimate_parameters_using_expectation_maximisation(
            block_on("name_head4", "built_s"), estimate_without_term_frequencies=True)
    except Exception as exc:  # EM is optional support for the weights, never the decision
        log(f"  EM skipped: {exc}")
    log(f"  trained in {time.time() - t0:.0f}s")
    df = linker.inference.predict().as_pandas_dataframe()
    log(f"  raw pairs: {len(df)}")
    return df


# --------------------------------------------------------------------------- judge
def _num(v):
    """None/nan-safe rendering for judge prompts."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return "unknown"
    return "unknown" if f != f else int(f)


def load_cache() -> dict:
    cache = {}
    if JUDGE_CACHE.exists():
        for line in JUDGE_CACHE.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if rec.get("reason") in ("judge unavailable",) or str(
                    rec.get("reason", "")).startswith("error:"):
                continue  # transient/parse failures are retried
            cache[rec["key"]] = rec
    return cache


def judge_same(ev: dict, cache: dict) -> dict:
    key = hashlib.sha256(json.dumps(ev, sort_keys=True, ensure_ascii=False)
                         .encode()).hexdigest()[:24]
    if key in cache:
        return cache[key]
    prompt = (
        "You compare two vessel records and decide whether they describe the SAME "
        "physical ship. Records:\n"
        f"A: name={ev.get('a_name')!r}; dwt={_num(ev.get('a_dwt'))}; built={_num(ev.get('a_built'))}; "
        f"imo={ev.get('a_imo') or 'none'}; yard={ev.get('a_yard')!r}\n"
        f"B: name={ev.get('b_name')!r}; dwt={_num(ev.get('b_dwt'))}; built={_num(ev.get('b_built'))}; "
        f"imo={ev.get('b_imo') or 'none'}; operator={ev.get('b_operator')!r}\n"
        'Reply with JSON only: {"decision":"same"|"different"|"unsure","reason":"<=20 words"}'
    )
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
                out = {"decision": dec, "reason": txt.replace("\n", " ")[:180]}
                break
        except Exception as exc:
            out = {"decision": "unsure", "reason": f"error: {type(exc).__name__}"}
            time.sleep(2 + attempt * 2)
    rec = {"key": key, **ev, **out}
    with JUDGE_CACHE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    cache[key] = rec
    return rec


# --------------------------------------------------------------------------- decide
def decide(claims: pd.DataFrame, known: pd.DataFrame, pairs: pd.DataFrame,
           cache: dict, log=print) -> tuple[list[dict], Counter]:
    cmeta = claims.set_index("entity_id")
    kmeta = known.set_index("entity_id")
    stats: Counter = Counter()
    by_claim: dict[str, list[dict]] = defaultdict(list)
    for row in pairs.itertuples(index=False):
        cl_eid = getattr(row, "unique_id_l")
        kn_eid = getattr(row, "unique_id_r")
        if cl_eid not in cmeta.index or kn_eid not in kmeta.index:
            continue
        c = cmeta.loc[cl_eid]
        k = kmeta.loc[kn_eid]
        score = float(getattr(row, "match_weight", 0.0))
        name_sim = fuzz.ratio(c["name_norm"], k["name_norm"]) / 100.0
        name_exact = c["name_norm"] == k["name_norm"]
        n_corr, detail = N.corroboration(
            c["dwt"], k["dwt"], c["built"], k["built"], c["yard"], None, name_sim, name_exact)
        conflict_imo = bool(c["printed_imo"]) and k["imo"] not in str(c["printed_imo"]).split(",")
        by_claim[cl_eid].append({"claim": c, "known": k, "a_eid": cl_eid, "b_eid": kn_eid,
                                 "name_sim": name_sim,
                                 "name_exact": name_exact, "corr": n_corr, "detail": detail,
                                 "weight": score, "conflict_imo": conflict_imo})
    records: list[dict] = []
    for cl_eid, cands in by_claim.items():
        cands.sort(key=lambda d: (-d["corr"], -d["name_sim"]))
        # a printed IMO that disagrees with a candidate forbids that candidate outright
        live = [d for d in cands if not d["conflict_imo"]]
        stats["claims_with_candidates"] += 1
        stats["candidate_pairs"] += len(cands)
        if not live:
            for d in cands:
                records.append(_rec(d, "separate", "imo_conflict", 0.0, "printed IMO disagrees"))
                stats["conflict_imo_separate"] += 1
            continue
        ambiguous = len(live) > 1
        tier = N.decide_tier(live[0]["corr"], live[0]["name_sim"], live[0]["name_exact"],
                             1 if not ambiguous else len(live), live[0]["weight"])
        if ambiguous:
            exact = [d for d in live if d["name_exact"]]
            if len(exact) == 1 and exact[0]["corr"] >= N.AUTO_MIN_CORROBORATION:
                tier = "auto"
                live = exact + [d for d in live if d is not exact[0]]
            else:
                tier = "llm"
        if tier == "auto":
            d = live[0]
            ok, why = _sufficient(d)
            if ok:
                records.append(_rec(d, "merge", "splink_auto", 0.99, _why(d)))
                stats["auto_merges"] += 1
            else:
                records.append(_rec(d, "separate", "auto_insufficient", 0.0, why))
                stats["auto_insufficient"] += 1
        elif tier == "llm":
            d = live[0]
            ev = {"a_name": d["claim"]["name"], "a_dwt": d["claim"]["dwt"],
                  "a_built": d["claim"]["built"], "a_imo": d["claim"]["printed_imo"],
                  "a_yard": d["claim"]["yard"], "b_name": d["known"]["name"],
                  "b_dwt": d["known"]["dwt"], "b_built": d["known"]["built"],
                  "b_imo": d["known"]["imo"], "b_operator": d["known"]["operator"]}
            verdict = judge_same(ev, cache)
            dec = verdict["decision"]
            decision = "merge" if dec == "same" else "separate"
            method = "judge_same" if dec == "same" else f"judge_{dec}"
            conf = 0.9 if dec == "same" else 0.0
            reason = verdict.get("reason", "")[:180]
            if dec == "same":
                ok, why = _sufficient(d)
                if not ok:  # judge said same but the evidence cannot tell the ships apart
                    decision, method, conf = "separate", "judge_insufficient", 0.0
                    reason = f"{reason} [insufficient: {why}]"
                    stats["judge_insufficient"] += 1
            records.append(_rec(d, decision, method, conf, reason))
            stats[f"judge_{dec}"] += 1
            if ambiguous:
                for other in live[1:]:
                    records.append(_rec(other, "separate", "not_best_candidate", 0.0,
                                        "weaker candidate"))
        else:
            d = live[0]
            records.append(_rec(d, "separate", "below_threshold", 0.0,
                                f"corr={d['corr']} name_sim={d['name_sim']:.2f}"))
            stats["separate_threshold"] += 1
            for other in live[1:]:
                records.append(_rec(other, "separate", "not_best_candidate", 0.0, ""))
    return records, stats


def _why(d: dict) -> str:
    bits = [k for k, v in (d["detail"] or {}).items() if v is True]
    return "name+ " + ",".join(bits)


def _sufficient(d: dict) -> tuple[bool, str]:
    """Evidence sufficiency for a merge (plan §6.4); returns (ok, why-not)."""
    if not N.merge_sufficient(d["name_sim"], d["name_exact"], d["corr"], d["detail"]):
        detail = d["detail"] or {}
        if detail.get("dwt_conflict"):
            return False, "dwt disagrees beyond tolerance"
        if detail.get("year_conflict"):
            return False, "built year disagrees"
        if not (d["name_exact"] or d["name_sim"] >= N.MERGE_MIN_NAME_SIM):
            return False, f"name similarity {d['name_sim']:.2f} too low"
        return False, "no corroborating attribute on both sides"
    return True, ""


def _rec(d: dict, decision: str, method: str, conf: float, reason: str) -> dict:
    return {"a": d["a_eid"], "b": d["b_eid"], "decision": decision,
            "method": method, "score": float(d["name_sim"]), "confidence": conf,
            "reason": reason, "weight": float(d["weight"]), "corr": int(d["corr"]),
            "a_name": d["claim"]["name"], "b_name": d["known"]["name"],
            "a_dwt": d["claim"]["dwt"], "b_dwt": d["known"]["dwt"],
            "a_built": d["claim"]["built"], "b_built": d["known"]["built"],
            "b_imo": d["known"]["imo"]}


def resolve_companies(con) -> tuple[list[dict], Counter]:
    """Provisional company names -> the single SEC CIK entity with the same normalised name."""
    stats: Counter = Counter()
    sec = con.execute("""
        SELECT entity_id, canonical_name, attrs FROM entity
        WHERE entity_id LIKE 'company:cik%'""").fetchall()
    by_norm: dict[str, list[str]] = defaultdict(list)
    for eid, name, _attrs in sec:
        by_norm[N.norm_company(name)].append(eid)
    prov = con.execute("""
        SELECT entity_id, canonical_name FROM entity
        WHERE entity_id LIKE 'company:int:%'""").fetchall()
    records = []
    for eid, name in prov:
        norm = N.norm_company(name)
        cands = by_norm.get(norm) or []
        if len(cands) == 1:
            records.append({"a": eid, "b": cands[0], "decision": "merge",
                            "method": "company_exact_name", "score": 1.0, "confidence": 0.95,
                            "reason": "exact normalised company name equals one SEC CIK entity",
                            "weight": 0.0, "corr": 1, "a_name": name,
                            "b_name": con.execute("SELECT canonical_name FROM entity "
                                                  "WHERE entity_id = ?", [cands[0]]).fetchone()[0],
                            "a_dwt": None, "b_dwt": None, "a_built": None, "b_built": None,
                            "b_imo": None})
            stats["company_merges"] += 1
        else:
            stats["company_unresolved"] += 1
    return records, stats


# --------------------------------------------------------------------------- write
def write_out(con, records: list[dict], log=print) -> Counter:
    stats: Counter = Counter()
    con.execute("BEGIN TRANSACTION")
    con.execute("DELETE FROM merge_log WHERE run = ?", [RUN])
    con.execute("DELETE FROM alias WHERE source IN ('p3_merge_auto','p3_merge_judge',"
                "'p3_merge_company')")
    con.execute("UPDATE entity SET status = 'provisional', "
                "attrs = json_merge_patch(CAST(attrs AS JSON), '{\"merged_into\":null}') "
                "WHERE entity_id LIKE 'vessel:prov:%' OR entity_id LIKE 'company:int:%'")
    now = con.execute("SELECT now()").fetchone()[0]
    rows = []
    for r in records:
        rows.append({"run": RUN, "a": r["a"], "b": r["b"], "decision": r["decision"],
                     "method": r["method"], "score": float(r["score"]),
                     "evidence": json.dumps({k: r[k] for k in
                                             ("reason", "weight", "corr", "a_name", "b_name",
                                              "a_dwt", "b_dwt", "a_built", "b_built", "b_imo",
                                              "confidence")}, ensure_ascii=False),
                     "at": now})
    if rows:
        con.executemany(
            "INSERT INTO merge_log (run, a, b, decision, method, score, evidence, \"at\") "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [(r["run"], r["a"], r["b"], r["decision"], r["method"], r["score"],
              r["evidence"], r["at"]) for r in rows])
    alias_rows = []
    for r in records:
        if r["decision"] != "merge":
            continue
        src = ("p3_merge_company" if r["method"].startswith("company")
               else "p3_merge_auto" if r["method"] == "splink_auto" else "p3_merge_judge")
        alias_rows.append((r["a_name"], N.norm_vessel_name(r["a_name"]) if src != "p3_merge_company"
                           else N.norm_company(r["a_name"]), r["b"], src,
                           float(r["confidence"]), RUN, now.date(), None))
        con.execute("UPDATE entity SET status = 'merged', "
                    "attrs = json_merge_patch(CAST(attrs AS JSON), CAST(? AS JSON)) "
                    "WHERE entity_id = ?",
                    [json.dumps({"merged_into": r["b"]}), r["a"]])
    if alias_rows:
        # alias PK (alias_norm, entity_id): drop rows we are about to recreate
        for alias_norm, entity_id, *_ in [(a[1], a[2]) for a in alias_rows]:
            con.execute("DELETE FROM alias WHERE alias_norm = ? AND entity_id = ?",
                        [alias_norm, entity_id])
        con.executemany(
            "INSERT INTO alias (alias, alias_norm, entity_id, source, confidence, merged_by, "
            "valid_from, valid_to) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", alias_rows)
    con.execute("COMMIT")
    stats["merge_log_rows"] = len(rows)
    stats["alias_rows"] = len(alias_rows)
    stats["merges"] = sum(1 for r in records if r["decision"] == "merge")
    stats["vessel_merges"] = sum(1 for r in records
                                 if r["decision"] == "merge" and not r["method"].startswith("company"))
    log(f"  wrote merge_log={len(rows)} alias={len(alias_rows)} merges={stats['merges']}")
    return stats


def main() -> int:
    LOGS.mkdir(parents=True, exist_ok=True)
    STATE.mkdir(parents=True, exist_ok=True)
    logf = (LOGS / "p3_resolve.log").open("a", encoding="utf-8")

    def log(msg: str) -> None:
        line = f"[{time.strftime('%H:%M:%S')}] {msg}"
        print(line, flush=True)
        logf.write(line + "\n")
        logf.flush()

    con = duckdb.connect(str(DB))
    con.execute("SET memory_limit='900MB'")
    con.execute("SET threads=2")
    t0 = time.time()
    refresh = "--refresh" in sys.argv
    if refresh or not CLAIMS.exists() or not KNOWN.exists():
        log("building claim/known frames")
        claims = build_claims(con)
        known = build_known(con)
        claims.to_parquet(CLAIMS, index=False)
        known.to_parquet(KNOWN, index=False)
    else:
        log("reusing cached frames")
        claims = pd.read_parquet(CLAIMS)
        known = pd.read_parquet(KNOWN)
    log(f"claims={len(claims)} known={len(known)}")
    max_claims = None
    for i, a in enumerate(sys.argv):
        if a == "--max-claims":
            max_claims = int(sys.argv[i + 1])
    if max_claims:
        claims = claims.head(max_claims).copy()
        log(f"dry-run slice claims={len(claims)}")
    if refresh or not PAIRS.exists():
        log("running splink blocking/predict")
        pairs = splink_pairs(claims, known, log=log)
        pairs.to_parquet(PAIRS, index=False)
    else:
        log("reusing cached pairs")
        pairs = pd.read_parquet(PAIRS)
    log(f"pairs={len(pairs)}")
    cache = load_cache()
    log(f"judge cache entries={len(cache)}")
    records, stats = decide(claims, known, pairs, cache, log=log)
    crec, cstats = resolve_companies(con)
    records.extend(crec)
    stats.update(cstats)
    stats.update(write_out(con, records, log=log))
    out = {"phase": "P3", "stage": "resolve", "run": RUN,
           "claims": int(len(claims)), "known": int(len(known)), "pairs": int(len(pairs)),
           "stats": dict(stats), "judge_calls": len(cache),
           "judge_model": JUDGE_MODEL, "money_spent_usd": MONEY,
           "wall_seconds": round(time.time() - t0, 1)}
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "p3_resolve.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    log(f"done {out['stats']}")
    log(f"wall={out['wall_seconds']}s")
    logf.close()
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
