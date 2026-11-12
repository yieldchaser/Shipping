"""Pick the P4c glm-5.3 second-extractor packs (C1 owner decision 4).

DESIGN NOTE
Owner reply 4: after all phase caps are booked, the spare of the $82 goes to glm-5.3 as a *second
extractor* on the highest-value chunks, unioned with the Ultrafast output and re-gated. Value order
is fixed by that instruction: (0) the 120 frozen gold chunks first so the recall gain is measurable
at all, (1) SEC 10-K/20-F/6-K MD&A plus fleet sections, (2) broker forecasts/outlook, (3) fixtures
and time-charter assessments, (4) S&P/index commentary. Within a tier, packs are ranked by weighted
keyword hits with a light recency bonus, so a tier that cannot be covered fully is filled with the
densest evidence first. Selection is budget-first, not tier-complete: `est_cost` prices a pack with
the glm-5.3 tariff fitted from the ledger (`fresh in $2.205/M, cached in $0.2205/M, out $6.93/M`,
exact fit on 244 ok jobs) using a conservative no-cache assumption plus prompt-overhead and output
means, and the picker stops when the reserved budget is spent. The unselected remainder is reported
as declared partial coverage (deviation D12), so the P4c report never claims full coverage of the
value tiers. Output is a normal `packs.jsonl`-shaped file so `p4c_run.run_packs` can consume it.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

KB = Path(__file__).resolve().parent
sys.path.insert(0, str(KB))

STATE = KB / "state"
OUT = STATE / "p4c"
PACKS = OUT / "packs.jsonl"
GOLD_ITEMS = STATE / "gold" / "p4b_items.json"
SELECTED = OUT / "packs_glm2.jsonl"
STATS = OUT / "highvalue_stats.json"

MODEL = "glm-5.3"
BUDGET_USD = 25.25
SAFETY = 0.90  # keep 10% of the cap unbooked so ledger-priced overruns cannot breach it
PRICE_IN = 2.205 / 1_000_000
PRICE_OUT = 6.93 / 1_000_000
IN_OVERHEAD = 3_700  # static prompt + tool schema + known_entities block, measured off p4c_dry
OUT_TOKENS = 1_490  # glm-5.3 mean output tokens per pack (p4b ledger)
CACHED_SHARE = 0.0  # no cache credit: conservative

TIERS = {
    "gold": 0,
    "sec_mda_fleet": 1,
    "broker_forecast": 2,
    "fixtures_tc": 3,
    "sp_index": 4,
    "other": 5,
}

# Budget split over the value tiers the owner listed (gold is taken first, at actual cost). The SEC
# share is the largest because that instruction names SEC MD&A/fleet before the broker material, but
# the split keeps every named category covered instead of letting one tier eat the whole cap.
QUOTA = {"sec_mda_fleet": 0.55, "broker_forecast": 0.20, "fixtures_tc": 0.15, "sp_index": 0.10}

SEC_TYPES = {"sec_10k", "sec_20f", "sec_6k", "sec_10q"}
MD_A_SECTIONS = {"md_a", "business", "subsequent"}
KW = {
    "mda": re.compile(r"\b(item\s*7|md&a|management'?s discussion|results of operations)\b"),
    "fleet": re.compile(r"\b(vessel|vessels|fleet|newbuilding|newbuildings|orderbook)\b"),
    "forecast": re.compile(r"\b(outlook|forecast|forecasts|expect|expected|projection|guidance)\b"),
    "fixture": re.compile(r"\b(fixture|fixtures|fixtured|time.?charter|timecharter|tctrip|tc rate)\b"),
    "sp": re.compile(r"\b(s&p|platts|index|baltic)\b"),
}
WEIGHTS = {"mda": 3, "fleet": 2, "forecast": 3, "fixture": 2, "sp": 1}


def load_gold_chunk_ids(path: Path | None = None) -> set[str]:
    path = path or GOLD_ITEMS
    if not path.exists():
        return set()
    return {it["chunk_id"] for it in json.loads(path.read_text(encoding="utf-8"))}


def text_of(pack: dict) -> str:
    parts = []
    for block in pack.get("blocks") or []:
        parts.extend(str(t) for _sid, t in block.get("sentences") or [])
    return " ".join(parts).lower()


def tier_of(pack: dict, gold_chunk_ids: set[str]) -> str:
    if gold_chunk_ids and any(cid in gold_chunk_ids for cid in pack.get("chunk_ids") or []):
        return "gold"
    doc = pack.get("doc") or {}
    dtype = (doc.get("doc_type") or "").lower()
    section = (pack.get("section_class") or "").lower()
    if dtype in SEC_TYPES and (section in MD_A_SECTIONS or KW["fleet"].search(text_of(pack))):
        return "sec_mda_fleet"
    if dtype.startswith("broker"):
        text = text_of(pack)
        if KW["forecast"].search(text):
            return "broker_forecast"
        if KW["fixture"].search(text):
            return "fixtures_tc"
    blob = " ".join([(doc.get("publisher") or ""), (doc.get("heading") or ""), dtype,
                     (doc.get("heading") or "")]).lower() + " " + text_of(pack)[:4000]
    if KW["sp"].search(blob):
        return "sp_index"
    return "other"


def score_of(pack: dict) -> float:
    text = text_of(pack)
    hits = sum(WEIGHTS[k] * min(len(pat.findall(text)), 8) for k, pat in KW.items())
    year = int(pack.get("year") or 0)
    return hits + (year - 2000) / 50.0  # recency tiebreak, never outranks a keyword hit


def est_cost(pack: dict) -> float:
    fresh_in = int(pack.get("tokens") or 0) + IN_OVERHEAD
    return fresh_in * PRICE_IN * (1.0 - CACHED_SHARE) + OUT_TOKENS * PRICE_OUT


def plan(path: Path = PACKS, budget: float = BUDGET_USD, safety: float = SAFETY) -> dict:
    """Metadata-only pass: tier+score every pack, then budget-greedy pick without holding rows."""
    gold = load_gold_chunk_ids()
    meta = []
    with path.open("r", encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            if not line.strip():
                continue
            pack = json.loads(line)
            meta.append({"i": i, "pack_id": pack["pack_id"],
                         "tier": TIERS[tier_of(pack, gold)],
                         "score": round(score_of(pack), 4),
                         "chunks": len(pack.get("chunk_ids") or []),
                         "tokens": int(pack.get("tokens") or 0),
                         "cost": round(est_cost(pack), 6)})
    eff = budget * safety
    meta.sort(key=lambda m: (m["tier"], -m["score"], m["i"]))
    picked, spent = [], 0.0
    gold_row = TIERS["gold"]
    for m in meta:
        if m["tier"] != gold_row:
            continue
        if spent + m["cost"] > eff:
            break
        picked.append(m)
        spent += m["cost"]
    pool = eff - spent
    carry = 0.0
    used = {}
    for name in sorted(QUOTA, key=lambda k: TIERS[k]):
        tier = TIERS[name]
        remaining = eff - spent
        tier_budget = min(remaining, QUOTA[name] * pool + carry)
        got = 0
        for m in meta:
            if m["tier"] != tier or m in picked:
                continue
            if got + m["cost"] > tier_budget:
                continue
            picked.append(m)
            got += m["cost"]
            spent += m["cost"]
        used[name] = round(got, 4)
        carry = round(carry + QUOTA[name] * pool - got, 6)
    tiers = {}
    for m in picked:
        name = next(k for k, v in TIERS.items() if v == m["tier"])
        t = tiers.setdefault(name, {"packs": 0, "chunks": 0, "est_cost": 0.0})
        t["packs"] += 1
        t["chunks"] += m["chunks"]
        t["est_cost"] = round(t["est_cost"] + m["cost"], 4)
    return {"picked": picked, "spent": round(spent, 4), "effective_budget": round(eff, 4),
            "budget": budget, "tiers": tiers, "quota": QUOTA, "tier_spend": used,
            "carry": round(carry, 4),
            "candidates": len(meta),
            "tier_candidates": {k: sum(1 for m in meta if m["tier"] == v)
                                for k, v in TIERS.items()}}


def write(plan_result: dict, path: Path = PACKS, out: Path = SELECTED) -> dict:
    want = {m["pack_id"]: m for m in plan_result["picked"]}
    out.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("r", encoding="utf-8") as fh, out.open("w", encoding="utf-8") as w:
        for line in fh:
            if not line.strip():
                continue
            pack = json.loads(line)
            if pack["pack_id"] in want:
                w.write(json.dumps(pack, ensure_ascii=False) + "\n")
                n += 1
    stats = {k: v for k, v in plan_result.items() if k != "picked"}
    stats.update({"packs_written": n, "model": MODEL,
                  "selected_path": str(out),
                  "est_cost_per_chunk": round(
                      plan_result["spent"] / max(1, sum(m["chunks"] for m in plan_result["picked"])), 6),
                  "gold_chunks": len(load_gold_chunk_ids()),
                  "partial_coverage": True,
                  "note": "declared partial coverage (D12): remaining value tiers not extracted by glm-5.3"})
    stats["tier_names"] = TIERS
    return stats


def summarise(stats: dict, dry: bool = False) -> str:
    lines = [f"glm2 packs {stats['packs_written']} chunks "
             f"{sum(t['chunks'] for t in stats['tiers'].values())} "
             f"est cost ${stats['spent']:.2f} / ${stats['budget']:.2f} "
             f"(effective ${stats['effective_budget']:.2f})"]
    for name in sorted(stats["tiers"], key=lambda k: TIERS[k]):
        t = stats["tiers"][name]
        lines.append(f"  {name:<16} packs {t['packs']:>5} chunks {t['chunks']:>6} "
                     f"est ${t['est_cost']:.2f}")
    if dry:
        lines.insert(0, "DRY: selection only, no extraction")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="P4c: select glm-5.3 second-extractor packs")
    ap.add_argument("--packs", default=str(PACKS))
    ap.add_argument("--out", default=str(SELECTED))
    ap.add_argument("--stats", default=str(STATS))
    ap.add_argument("--budget", type=float, default=BUDGET_USD)
    ap.add_argument("--safety", type=float, default=SAFETY)
    ap.add_argument("--dry", action="store_true", help="report the selection, write nothing")
    ap.add_argument("--limit", type=int, default=0, help="cap the number of selected packs (debug)")
    args = ap.parse_args()
    res = plan(Path(args.packs), args.budget, args.safety)
    if args.limit:
        res["picked"] = res["picked"][:args.limit]
        res["spent"] = round(sum(m["cost"] for m in res["picked"]), 4)
        tiers = {}
        for m in res["picked"]:
            name = next(k for k, v in TIERS.items() if v == m["tier"])
            t = tiers.setdefault(name, {"packs": 0, "chunks": 0, "est_cost": 0.0})
            t["packs"] += 1
            t["chunks"] += m["chunks"]
            t["est_cost"] = round(t["est_cost"] + m["cost"], 4)
        res["tiers"] = tiers
    stats = write(res, Path(args.packs), Path(args.out)) if not args.dry else {
        k: v for k, v in res.items() if k != "picked"}
    stats.setdefault("packs_written", len(res["picked"]))
    if "est_cost_per_chunk" not in stats:
        stats["est_cost_per_chunk"] = round(
            res["spent"] / max(1, sum(m["chunks"] for m in res["picked"])), 6)
        stats["model"] = MODEL
        stats["partial_coverage"] = True
        stats["gold_chunks"] = len(load_gold_chunk_ids())
    Path(args.stats).write_text(json.dumps(stats, indent=2, default=str), encoding="utf-8")
    print(summarise(stats, dry=args.dry))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
