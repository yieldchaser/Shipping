"""P3 stage 3 — deterministic pre-tagging of chunks (plan §6.2).

Design note
  * Single pass over `chunk.body`, no LLM (layer A, plan D2). Aho–Corasick matcher
    built from the registry alias table; patterns are the alias strings pushed
    through the same normaliser as the text, so matching is accent/case/punctuation
    insensitive.
  * Word-boundary checked: a hit must be delimited by non-alphanumerics, so
    "SEA" never matches "SEATTLE".
  * Precision-first for identities (plan D8): a vessel name is tagged only when its
    alias maps to one entity, or when the chunk itself carries corroboration (a
    printed IMO, or DWT/built-year matching one candidate). Ambiguous names without
    corroboration are skipped and counted.
  * Non-vessel aliases (company/port/route/commodity/country/index) are tagged only
    when the alias maps to a single entity; ambiguity is skipped.
  * Name plausibility gate (`vessel_name_ok`, `company_pattern_ok`): the registry
    holds rows that are parse debris rather than names ("OF THE", "81 000 dwt",
    "Red Sea", "EACH", "MANAGEMENT SA"). Those are never used as patterns, so chunk
    tags stay precise; skipped counts are reported by reason.
  * Provisional companies already resolved into a SEC entity are tagged as the SEC
    identity (`merged_into`), never as the provisional shell.
  * Printed IMO numbers with a valid check digit tag the keyed vessel directly
    (this is the identity key, plan §6.3).
  * Writes chunk.entity_ids in batches; resumable via kb/state/p3_tag_checkpoint.json.
"""
from __future__ import annotations

import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import duckdb
import pyarrow as pa

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p3_names as N  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "kb/state/kb.duckdb"
STATE = ROOT / "kb/state"
REPORTS = ROOT / "kb/reports"
LOGS = ROOT / "kb/logs"
CKPT = STATE / "p3_tag_checkpoint.json"
BATCH = 20000
ALIAS_MIN_LEN = 3

NUM_RE = re.compile(r"(?<!\d)(\d{4,7})(?!\d)")
YEAR_RE = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")

# --- tagging plausibility filters (precision-first tagging policy, plan §6.2/D8).
# The registry legitimately contains rows that are *not* taggable names: attribution
# fragments ("OF THE", "were reported"), measurement strings ("81 000 dwt"),
# geography/resource phrases that the parse filed under vessel claims ("Red Sea",
# "East Coast"), and generic business words filed as provisional companies
# ("EACH", "MANAGEMENT SA", "New Shipping"). Tagging those across the corpus would
# bury real entities in noise, so a name must look like a name before it is tagged.
STOP_TOKENS = {"of", "the", "a", "an", "and", "or", "for", "were", "was", "is", "are",
               "reported", "according", "may", "this", "that", "these", "with", "from",
               "to", "in", "on", "at", "by", "as", "were", "be", "been", "has", "have"}
GEO_TOKENS = {"east", "west", "north", "south", "coast", "coasts", "sea", "seas", "canal",
              "gulf", "strait", "straits", "middle", "far", "high", "red", "black",
              "arabian", "persian", "atlantic", "pacific", "mediterranean", "region",
              "route", "routes", "area", "areas", "northern", "southern", "eastern",
              "western"}
UNIT_TOKENS = {"dwt", "gt", "nt", "mt", "teu", "kts", "kn", "nm", "bbl", "ft", "kg",
               "ton", "tons", "tonnes", "cbm", "psi"}
COMPANY_GENERIC = {"shipping", "marine", "maritime", "trading", "trade", "services",
                   "service", "management", "investors", "investment", "charterers",
                   "chartering", "safety", "transportation", "transport", "middle", "east",
                   "west", "north", "south", "africa", "asia", "europe", "japan", "korea",
                   "china", "india", "mediterranean", "sea", "ocean", "new", "sa", "co",
                   "ltd", "limited", "group", "holdings", "holding", "international",
                   "corporation", "corp", "inc", "llc", "ships", "shipyard", "yard",
                   "tankers", "tanker", "carriers", "carrier", "navigation", "bulkers",
                   "bulker", "logistics", "energy", "oil", "gas", "petroleum", "ore",
                   "lines", "line", "company", "partners", "resources", "industries",
                   "enterprise", "enterprises", "ventures", "capital", "assets", "fund",
                   "trust", "one", "each", "the", "of", "and", "for", "global",
                   "standard", "pacific", "atlantic", "union", "regional", "focus",
                   "associated", "central", "special", "first", "star", "american",
                   "european", "asian", "african", "chinese", "japanese", "korean",
                   "indian", "turkish", "hellenic", "norwegian", "danish", "german",
                   "greek", "singapore", "dubai", "hong", "kong"}


def _has_digit(tok: str) -> bool:
    return any(ch.isdigit() for ch in tok)


def vessel_name_ok(norm: str) -> bool:
    """True when a vessel alias looks like a ship name rather than parse debris."""
    toks = [t for t in norm.split() if t]
    if not toks:
        return False
    if any(t in UNIT_TOKENS for t in toks):
        return False
    if all(t in STOP_TOKENS or t in GEO_TOKENS for t in toks):
        return False
    if toks[0] in STOP_TOKENS:
        return False
    if len(toks) == 1:
        return len(toks[0]) >= 4 and not _has_digit(toks[0])
    if any(t in GEO_TOKENS for t in toks) and not any(_has_digit(t) for t in toks):
        return False
    if all(_has_digit(t) for t in toks):
        return False
    return True


def company_pattern_ok(norm: str, is_sec: bool) -> bool:
    """SEC entities are trusted; provisional names must look like a company name."""
    if is_sec:
        return True
    toks = [t for t in norm.split() if t]
    if len(toks) < 2:
        return False
    if any(t in UNIT_TOKENS for t in toks):
        return False
    if toks[0] in STOP_TOKENS or toks[-1] in STOP_TOKENS:
        return False
    distinctive = [t for t in toks if len(t) >= 3 and t not in COMPANY_GENERIC
                   and not _has_digit(t)]
    return bool(distinctive)


def norm_text(s: str) -> str:
    """Lowercase ASCII-folded text with punctuation collapsed to single spaces."""
    out = []
    for ch in N.strip_accents(s or "").lower():
        out.append(ch if (ch.isalnum() or ch.isspace()) else " ")
    return " ".join("".join(out).split())


class AhoCorasick:
    """Minimal Aho–Corasick over space-delimited normalised strings."""

    def __init__(self) -> None:
        self.goto: list[dict[str, int]] = [{}]
        self.fail: list[int] = [0]
        self.out: list[list[int]] = [[]]

    def add(self, pattern: str, pid: int) -> None:
        node = 0
        for ch in pattern:
            nxt = self.goto[node].get(ch)
            if nxt is None:
                self.goto.append({})
                self.fail.append(0)
                self.out.append([])
                nxt = len(self.goto) - 1
                self.goto[node][ch] = nxt
            node = nxt
        self.out[node].append(pid)

    def build(self) -> None:
        from collections import deque
        q = deque()
        for ch, nxt in self.goto[0].items():
            q.append(nxt)
            self.fail[nxt] = 0
        while q:
            node = q.popleft()
            for ch, nxt in self.goto[node].items():
                q.append(nxt)
                f = self.fail[node]
                while f and ch not in self.goto[f]:
                    f = self.fail[f]
                self.fail[nxt] = self.goto[f].get(ch, 0)
                if self.fail[nxt] == nxt:
                    self.fail[nxt] = 0
                self.out[nxt] = self.out[nxt] + self.out[self.fail[nxt]]

    def search(self, text: str):
        """Yield (start, end, pid) for every pattern occurrence."""
        node = 0
        for i, ch in enumerate(text):
            while node and ch not in self.goto[node]:
                node = self.fail[node]
            node = self.goto[node].get(ch, 0)
            if self.out[node]:
                for pid in self.out[node]:
                    yield pid, i


def load_patterns(con) -> tuple[list[dict], Counter]:
    """Build taggable patterns from alias table; return (patterns, stats).

    A pattern carries: norm text, entity ids it may tag, and whether in-chunk
    corroboration is required before tagging (single-token vessel names and names
    shared by 2-3 vessels). Plan D8: a bare name never identifies a ship.
    """
    type_of = {r[0]: r[1] for r in
               con.execute("SELECT entity_id, type FROM entity").fetchall()}
    # Provisional companies that P3 resolved into a SEC entity: tag the SEC identity
    # (the resolved key), never the provisional shell.
    company_target: dict[str, str] = {}
    for eid, attrs in con.execute(
            "SELECT entity_id, attrs FROM entity WHERE entity_id LIKE 'company:int:%'").fetchall():
        try:
            target = (json.loads(attrs or "{}") or {}).get("merged_into")
        except ValueError:
            target = None
        if target and target.startswith("company:cik"):
            company_target[eid] = target
    rows = con.execute("SELECT alias, alias_norm, entity_id, source FROM alias").fetchall()
    by_norm: dict[str, dict[str, set]] = defaultdict(lambda: defaultdict(set))
    for alias, alias_norm, eid, src in rows:
        t = type_of.get(eid)
        if not t:
            continue
        norm = norm_text(alias_norm) or norm_text(alias)
        if len(norm) < ALIAS_MIN_LEN or not any(ch.isalnum() for ch in norm):
            continue
        by_norm[norm][t].add(eid)
    patterns: list[dict] = []
    stats: Counter = Counter()
    for norm, by_type in by_norm.items():
        if len(by_type) > 1:  # same string, different entity types: too risky
            stats["skipped_cross_type"] += 1
            continue
        t, eids = next(iter(by_type.items()))
        if t == "vessel":
            if not vessel_name_ok(norm):
                stats["skipped_implausible_vessel"] += 1
                continue
            if len(eids) > 3:
                stats["skipped_many_vessels"] += 1
                continue
            patterns.append({"norm": norm, "type": t, "eids": sorted(eids),
                             "corroborate": len(eids) > 1 or " " not in norm})
            stats["ambiguous_vessel_norms" if len(eids) > 1 else "vessel_norms"] += 1
        elif t == "company":
            mapped = sorted({company_target.get(e, e) for e in eids})
            if len(mapped) != 1:
                stats["skipped_multi_entity"] += 1
                continue
            eid = mapped[0]
            if not company_pattern_ok(norm, eid.startswith("company:cik")):
                stats["skipped_generic_company"] += 1
                continue
            patterns.append({"norm": norm, "type": t, "eids": [eid],
                             "corroborate": False})
        elif len(eids) == 1:
            patterns.append({"norm": norm, "type": t, "eids": sorted(eids),
                             "corroborate": False})
        else:
            stats["skipped_multi_entity"] += 1
    pattern_by_id = {i: p for i, p in enumerate(patterns)}
    stats["patterns"] = len(patterns)
    return pattern_by_id, stats


def corroborated(cands: list[str], attrs_by_eid: dict, imo_to_eid: dict,
                 chunk_imos: list[str], nums: list[int], years: list[int]) -> str | None:
    """Return the single candidate entity the chunk itself corroborates, else None."""
    for imo in chunk_imos:
        eid = imo_to_eid.get(imo)
        if eid and eid in cands:
            return eid
    winners = []
    for c in cands:
        a = attrs_by_eid.get(c) or {}
        d = a.get("dwt")
        b = a.get("built")
        if nums and d and any(N.dwt_close(d, v) for v in nums):
            winners.append(c)
        elif years and b and any(N.year_close(b, y) for y in years):
            winners.append(c)
    return winners[0] if len(winners) == 1 else None


def tag_chunk(body: str, ac: AhoCorasick, pattern_by_id: dict, attrs_by_eid: dict,
              imo_to_eid: dict, stats: Counter) -> list[str]:
    text = norm_text(body)
    if not text:
        return []
    tags: list[str] = []
    seen: set[str] = set()
    cached: dict[str, list] = {}

    def numbers():
        if "nums" not in cached:
            plain = re.sub(r"\d[\d,]*", lambda m: m.group(0).replace(",", ""), body)
            nums = [int(x) for x in NUM_RE.findall(plain)]
            years = [int(y) for y in YEAR_RE.findall(plain)]
            imos = [x for x in NUM_RE.findall(plain) if N.imo_checksum_ok(x)]
            cached["nums"] = (nums, years, imos)
        return cached["nums"]

    def add(eid: str) -> None:
        if eid not in seen:
            seen.add(eid)
            tags.append(eid)

    for pid, end in ac.search(text):
        p = pattern_by_id[pid]
        start = end - len(p["norm"]) + 1
        before = text[start - 1] if start > 0 else " "
        after = text[end + 1] if end + 1 < len(text) else " "
        if before.isalnum() or after.isalnum():
            continue
        if p["corroborate"]:
            stats["hits_needing_corroboration"] += 1
            nums, years, imos = numbers()
            eid = corroborated(p["eids"], attrs_by_eid, imo_to_eid, imos, nums, years)
            if eid:
                add(eid)
                stats["ambiguous_corroborated"] += 1
            else:
                stats["ambiguous_skipped"] += 1
            continue
        for eid in p["eids"]:
            add(eid)
        stats["hits"] += 1
    # printed IMO = identity key (independent of any name match)
    for imo in numbers()[2]:
        eid = imo_to_eid.get(imo)
        if eid and eid not in seen:
            seen.add(eid)
            tags.append(eid)
            stats["imo_tags"] += 1
    return tags


def main() -> int:
    LOGS.mkdir(parents=True, exist_ok=True)
    logf = (LOGS / "p3_tag.log").open("a", encoding="utf-8")

    def log(msg: str) -> None:
        line = f"[{time.strftime('%H:%M:%S')}] {msg}"
        print(line, flush=True)
        logf.write(line + "\n")
        logf.flush()

    con = duckdb.connect(str(DB))
    con.execute("SET memory_limit='700MB'")
    con.execute("SET threads=2")
    t0 = time.time()
    if "--reset" in sys.argv:
        con.execute("UPDATE chunk SET entity_ids = NULL")
        if CKPT.exists():
            CKPT.unlink()
    pattern_by_id, pstats = load_patterns(con)
    log(f"patterns={pstats['patterns']} vessel_norms={pstats.get('vessel_norms', 0)} "
        f"ambiguous_vessel_norms={pstats.get('ambiguous_vessel_norms', 0)}")
    attrs_by_eid = {}
    imo_to_eid = {}
    for eid, attrs in con.execute(
            "SELECT entity_id, attrs FROM entity WHERE entity_id LIKE 'vessel:imo:%'").fetchall():
        a = json.loads(attrs) if attrs else {}
        attrs_by_eid[eid] = a
        imo = str(a.get("imo") or eid.rsplit(":", 1)[-1])
        imo_to_eid[imo] = eid
    ac = AhoCorasick()
    for pid, p in pattern_by_id.items():
        ac.add(p["norm"], pid)
    ac.build()
    log(f"automaton nodes={len(ac.goto)}")

    ck = json.loads(CKPT.read_text()) if CKPT.exists() else {"last": ""}
    max_chunks = None
    for i, a in enumerate(sys.argv):
        if a == "--max-chunks":
            max_chunks = int(sys.argv[i + 1])
    stats: Counter = Counter()
    done = 0
    while True:
        limit = BATCH if not max_chunks else min(BATCH, max_chunks - done)
        if limit <= 0:
            break
        rows = con.execute(
            "SELECT chunk_id, body FROM chunk WHERE chunk_id > ? ORDER BY chunk_id LIMIT ?",
            [ck["last"], limit]).fetchall()
        if not rows:
            break
        out_ids, out_tags = [], []
        for cid, body in rows:
            tags = tag_chunk(body or "", ac, pattern_by_id, attrs_by_eid,
                             imo_to_eid, stats)
            if tags:
                out_ids.append(cid)
                out_tags.append(tags)
        if out_ids:
            t = pa.table({"chunk_id": pa.array(out_ids, pa.string()),
                          "entity_ids": pa.array(out_tags, pa.list_(pa.string()))})
            con.register("_tags_arrow", t)
            con.execute("UPDATE chunk SET entity_ids = t.entity_ids FROM _tags_arrow t "
                        "WHERE chunk.chunk_id = t.chunk_id")
            con.unregister("_tags_arrow")
        ck["last"] = rows[-1][0]
        done += len(rows)
        CKPT.write_text(json.dumps(ck))
        if done % (BATCH * 5) == 0:
            log(f"  chunks={done} tagged={stats['hits']} ambig_skip={stats['ambiguous_skipped']}")
    tagged_rows, multi = con.execute(
        "SELECT count(*), count(*) FILTER (WHERE len(entity_ids) > 1) FROM chunk "
        "WHERE entity_ids IS NOT NULL AND len(entity_ids) > 0").fetchone()
    out = {"phase": "P3", "stage": "tag", "patterns": pstats["patterns"],
           "ambiguity": {k: v for k, v in pstats.items() if k.startswith(("ambiguous", "skipped"))},
           "tag_stats": dict(stats), "chunks_tagged": int(tagged_rows),
           "chunks_multi_tag": int(multi), "chunks_total": int(
               con.execute("SELECT count(*) FROM chunk").fetchone()[0]),
           "money_spent_usd": 0.0, "wall_seconds": round(time.time() - t0, 1)}
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "p3_tag.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    log(f"done chunks_tagged={tagged_rows} multi={multi} stats={dict(stats)}")
    log(f"wall={out['wall_seconds']}s")
    logf.close()
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
