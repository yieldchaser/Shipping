#!/usr/bin/env python3
"""
GraphRAG phase P3 — seed registry (plan §6.3, D8).

Builds `entity` + `alias` rows from keyed reference sources only:
  vessels   AIS voyage registries (data/geospatial/signal_vessels_*.json, IMO-keyed)
            + benchmark_core_fleet.json + IMO-keyed vessel rows already produced by P2
  companies SEC EDGAR frontmatter (cik + ticker + company_name) -> company:cik<10d>
            + counterparty names appearing in P2 claims -> company:int:<slug> (provisional)
  ports     PortWatch master with a UN/LOCODE -> port:<LOC5>
  regions   commodity_normalisation.region_mappings basins -> region:<slug>
  routes    Baltic route taxonomy + Fearnleys TSID registry -> route:<CODE>
  indices   Baltic index definitions -> index:<CODE>
  commodities commodity_normalisation.commodity_mappings -> commodity:<slug>
  countries demonym lexicon (p3_names.NATIONALITY) -> country:<ISO2>

No LLM. No name-only vessel identities (plan D8): a vessel entity here always has a
printed/registry IMO. Name-only claim identities stay `vessel:prov:*` (P2) and are only
aliased here so tagging/resolution can find them.

Deterministic + idempotent: rows are rebuilt from source each run; `INSERT OR REPLACE`
semantics via staging tables. Usage: python kb/p3_seed.py [--report]
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

import duckdb
import pyarrow as pa
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p3_names as N  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "kb" / "state" / "kb.duckdb"
REPORTS = ROOT / "kb" / "reports"
GEO = ROOT / "data" / "geospatial"
REF = ROOT / "data" / "reference"

ENTITY_SCHEMA = pa.schema([
    ("entity_id", pa.string()), ("type", pa.string()), ("canonical_name", pa.string()),
    ("attrs", pa.string()), ("status", pa.string()), ("created_by", pa.string()),
])
ALIAS_SCHEMA = pa.schema([
    ("alias", pa.string()), ("alias_norm", pa.string()), ("entity_id", pa.string()),
    ("source", pa.string()), ("confidence", pa.float64()), ("merged_by", pa.string()),
    ("valid_from", pa.date32()), ("valid_to", pa.date32()),
])

ISO2_NAME = {
    "AE": "United Arab Emirates", "AF": "Afghanistan", "AG": "Antigua and Barbuda",
    "AR": "Argentina", "AS": "Asia", "AT": "Austria", "AU": "Australia", "BD": "Bangladesh",
    "BE": "Belgium", "BG": "Bulgaria", "BH": "Bahrain", "BM": "Bermuda", "BR": "Brazil",
    "CA": "Canada", "CH": "Switzerland", "CL": "Chile", "CN": "China", "CY": "Cyprus",
    "DE": "Germany", "DK": "Denmark", "DZ": "Algeria", "EE": "Estonia", "EG": "Egypt",
    "ES": "Spain", "EU": "Europe", "FE": "Far East", "FI": "Finland", "FR": "France",
    "GB": "United Kingdom", "GR": "Greece", "HK": "Hong Kong", "HR": "Croatia",
    "ID": "Indonesia", "IE": "Ireland", "IN": "India", "IQ": "Iraq", "IR": "Iran",
    "IS": "Iceland", "IT": "Italy", "JP": "Japan", "KR": "South Korea", "KW": "Kuwait",
    "LR": "Liberia", "LT": "Lithuania", "LV": "Latvia", "LY": "Libya", "MA": "Morocco",
    "ME": "Middle East", "MH": "Marshall Islands", "MT": "Malta", "MX": "Mexico",
    "MY": "Malaysia", "NG": "Nigeria", "NL": "Netherlands", "NO": "Norway",
    "NZ": "New Zealand", "OM": "Oman", "PA": "Panama", "PH": "Philippines", "PK": "Pakistan",
    "PL": "Poland", "PT": "Portugal", "QA": "Qatar", "RU": "Russia", "SA": "Saudi Arabia",
    "SE": "Sweden", "SG": "Singapore", "TH": "Thailand", "TR": "Turkey", "TW": "Taiwan",
    "UA": "Ukraine", "US": "United States", "VN": "Vietnam", "ZA": "South Africa",
}
# aliases that must never be used as a text tag (too generic / ambiguous)
_TAG_BLOCK = {
    "US", "UK", "EU", "AS", "ME", "FE", "INDIA", "CHINA", "GREECE", "UNKNOWN", "N A",
    "NOT SET", "TBA", "TBN", "VARIOUS", "UNDISCLOSED",
}
PORT_ID_BLOCK = {"NOT SET"}


class Registry:
    def __init__(self) -> None:
        self.entities: dict[str, dict] = {}
        self.aliases: dict[tuple[str, str], dict] = {}
        self.stats: Counter = Counter()

    # ------------------------------------------------------------------ adders
    def entity(self, entity_id: str, etype: str, name: str, attrs: dict | None = None,
               status: str = "confirmed") -> dict:
        cur = self.entities.get(entity_id)
        if cur is None:
            cur = {"entity_id": entity_id, "type": etype, "canonical_name": name,
                   "attrs": dict(attrs or {}), "status": status, "created_by": "p3_seed"}
            self.entities[entity_id] = cur
            self.stats[f"entity_{etype}"] += 1
        else:
            for k, v in (attrs or {}).items():
                if v not in (None, "", [], {}):
                    cur["attrs"].setdefault(k, v)
            if status == "confirmed" and cur["status"] != "confirmed":
                cur["status"] = "confirmed"
        return cur

    def alias(self, alias: str | None, entity_id: str, source: str,
              confidence: float = 0.9, norm: str | None = None) -> bool:
        if not alias:
            return False
        an = norm if norm is not None else N.norm_text(alias)
        if not an or an in _TAG_BLOCK or len(an) < 2 or an.isdigit():
            return False
        key = (an, entity_id)
        if key in self.aliases:
            self.aliases[key]["confidence"] = max(self.aliases[key]["confidence"], confidence)
            return False
        self.aliases[key] = {"alias": alias.strip(), "alias_norm": an, "entity_id": entity_id,
                             "source": source, "confidence": float(confidence),
                             "merged_by": None, "valid_from": date(2026, 1, 1),
                             "valid_to": None}
        return True


def load_ais(reg: Registry, stats: Counter) -> list[dict]:
    recs = []
    frames = []
    for f in sorted(GEO.glob("signal_vessels_*.json")):
        sector = f.stem.replace("signal_vessels_", "")
        data = json.loads(f.read_text(encoding="utf-8"))
        stats[f"ais_{sector}"] = len(data)
        frames.append((sector, data))
    # pass 1 — how many distinct IMOs carry each normalised name (yard / hull placeholders)
    imos_by_name: dict[str, set] = {}
    for _sector, data in frames:
        for r in data:
            nm = N.norm_vessel_name(r.get("vesselName") or "")
            imo = str(r.get("imo") or "")
            if nm and N.imo_checksum_ok(imo):
                imos_by_name.setdefault(nm, set()).add(imo)
    # pass 2 — entities + trustworthy name aliases
    for sector, data in frames:
        for r in data:
            imo = str(r.get("imo") or "")
            if not N.imo_checksum_ok(imo):
                stats["ais_bad_imo"] += 1
                continue
            name = (r.get("vesselName") or "").strip()
            nm = N.norm_vessel_name(name)
            attrs = {"imo": imo, "dwt": r.get("deadweight") or None,
                     "built": r.get("yearBuilt") or None, "class": r.get("vesselClass"),
                     "sector": sector, "operator": r.get("companyName") or None,
                     "vessel_type_id": r.get("vesselTypeId"),
                     "tanker_capacity": r.get("liquidCapacity") or None,
                     "geared": r.get("geared"), "scrubbers": r.get("scrubbers")}
            reg.entity(f"vessel:imo:{imo}", "vessel", name or f"IMO {imo}", attrs, "confirmed")
            if name and N.vessel_alias_ok(nm, len(imos_by_name.get(nm, ()))):
                n_imos = len(imos_by_name[nm])
                reg.alias(name, f"vessel:imo:{imo}", "p3_ais_name",
                          0.95 if n_imos == 1 else 0.7, norm=nm)
            elif name:
                stats["ais_name_alias_skipped"] += 1
            recs.append({"imo": imo, "name": name, "dwt": attrs["dwt"],
                         "built": attrs["built"], "sector": sector,
                         "operator": attrs["operator"]})
    return imos_by_name


def load_benchmark(reg: Registry, stats: Counter, imos_by_name: dict[str, set]) -> None:
    data = json.loads((REF / "benchmark_core_fleet.json").read_text(encoding="utf-8"))
    stats["benchmark_meta"] = data.get("metadata", {}).get("total_hulls")
    rows_all = [(sector, r) for sector, rows in (data.get("sectors") or {}).items() for r in rows]
    # the benchmark file repeats shipyard placeholders as names (e.g. "Hudong Zhonghua")
    for _sector, r in rows_all:
        imo = str(r.get("imo") or "")
        nm = N.norm_vessel_name(r.get("name") or "")
        if nm and N.imo_checksum_ok(imo):
            imos_by_name.setdefault(nm, set()).add(imo)
    for sector, r in rows_all:
        imo = str(r.get("imo") or "")
        if not N.imo_checksum_ok(imo):
            stats["benchmark_bad_imo"] += 1
            continue
        nm = N.norm_vessel_name(r.get("name") or "")
        attrs = {"imo": imo, "dwt": N.parse_dwt(r.get("dwt")),
                 "built": N.parse_year(r.get("built")), "class": r.get("class"),
                 "sector": sector, "operator": r.get("operator"),
                 "benchmark": True}
        reg.entity(f"vessel:imo:{imo}", "vessel", (r.get("name") or "").strip() or f"IMO {imo}",
                   attrs, "confirmed")
        if nm and N.vessel_alias_ok(nm, len(imos_by_name.get(nm, ()))):
            n_imos = len(imos_by_name[nm])
            reg.alias(r["name"], f"vessel:imo:{imo}", "p3_benchmark_name",
                      0.95 if n_imos == 1 else 0.7, norm=nm)
        if r.get("operator") and not N.is_undisclosed(r["operator"]):
            slug = N.company_slug(r["operator"])
            if slug:
                reg.entity(f"company:int:{slug}", "company", r["operator"].strip(),
                           {"source": ["benchmark_fleet"]}, "provisional")
                reg.alias(r["operator"], f"company:int:{slug}", "p3_benchmark_operator",
                          0.7, norm=N.norm_company(r["operator"]))


def load_sec(con, reg: Registry, stats: Counter) -> None:
    rows = con.execute("""
        SELECT json_extract_string(frontmatter,'$.cik') AS cik,
               json_extract_string(frontmatter,'$.ticker') AS ticker,
               json_extract_string(frontmatter,'$.company_name') AS company_name,
               publisher_id, count(*) AS n
        FROM document
        WHERE json_extract_string(frontmatter,'$.cik') IS NOT NULL
        GROUP BY 1,2,3,4 ORDER BY n DESC""").fetchall()
    seen = set()
    for cik, ticker, company_name, publisher, n in rows:
        cik = "".join(ch for ch in (cik or "") if ch.isdigit())
        if len(cik) != 10:
            stats["sec_bad_cik"] += 1
            continue
        eid = f"company:cik{cik}"
        name = (company_name or publisher or ticker or cik).strip()
        reg.entity(eid, "company", name,
                   {"cik": cik, "ticker": ticker, "publisher_id": publisher,
                    "source": ["sec_edgar"], "doc_count": n}, "confirmed")
        reg.alias(name, eid, "p3_sec_company", 0.99, norm=N.norm_company(name))
        reg.alias(publisher, eid, "p3_sec_publisher", 0.9, norm=N.norm_company(publisher))
        reg.alias(ticker, eid, "p3_sec_ticker", 0.95, norm=N.norm_text(ticker))
        seen.add(eid)
    stats["sec_companies"] = len(seen)


def load_ports(reg: Registry, stats: Counter) -> dict[str, str]:
    """PortWatch ports with UN/LOCODE -> port:<LOC5>. Returns norm_name -> entity_id."""
    name_index: dict[str, str] = {}
    with open(GEO / "portwatch_ports_master.csv", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            raw = (row.get("LOCODE") or "").replace(" ", "").replace("-", "")
            if len(raw) != 5 or not raw.isalnum():
                stats["port_no_locode"] += 1
                continue
            eid = f"port:{raw}"
            attrs = {"locode": raw, "port_name": row.get("portname"),
                     "country": row.get("country"), "iso3": row.get("ISO3"),
                     "lat": row.get("lat"), "lon": row.get("lon"),
                     "portid": row.get("portid"),
                     "vessel_count_total": row.get("vessel_count_total")}
            reg.entity(eid, "port", row.get("portname") or raw, attrs, "confirmed")
            for a, conf in ((row.get("portname"), 0.95), (row.get("fullname"), 0.8)):
                if reg.alias(a, eid, "p3_portwatch", conf):
                    name_index.setdefault(N.norm_text(a), eid)
            stats["ports"] += 1
    # extra port names from the commodity gazetteer that are unambiguous port names
    comm = json.loads((REF / "commodity_normalisation.json").read_text(encoding="utf-8"))
    for raw_name, info in (comm.get("region_mappings") or {}).items():
        nm = N.norm_text(raw_name)
        basin = (info or {}).get("basin")
        region_name = (info or {}).get("region_name")
        if basin and region_name and region_name.upper() == nm:
            slug = N.company_slug(region_name)
            if slug:
                reg.entity(f"region:{slug}", "region", region_name,
                           {"basin": basin}, "confirmed")
                reg.alias(raw_name, f"region:{slug}", "p3_gazetteer_region", 0.9)
            continue
        eid = name_index.get(nm)
        if eid:
            reg.alias(raw_name, eid, "p3_gazetteer_port", 0.75)
    return name_index


def load_routes_indices(reg: Registry, stats: Counter) -> None:
    b = json.loads((REF / "baltic_route_taxonomy.json").read_text(encoding="utf-8"))
    for code, r in (b.get("routes") or {}).items():
        eid = f"route:{code}"
        reg.entity(eid, "route", f"{code} {r.get('description') or ''}".strip(),
                   {"code": code, "description": r.get("description"),
                    "vessel_class": r.get("vessel_class"), "category": r.get("category"),
                    "unit": r.get("unit"), "source": ["baltic_taxonomy"]}, "confirmed")
        reg.alias(code, eid, "p3_baltic_route", 0.99)
        stats["routes"] += 1
    f = json.loads((REF / "fearnleys_tsid_registry.json").read_text(encoding="utf-8"))
    for _, r in f.items():
        code = r.get("code")
        if not code:
            continue
        eid = f"route:{code}"
        reg.entity(eid, "route", f"{code} {r.get('taxonomy_description') or ''}".strip(),
                   {"code": code, "historical_code": r.get("historical_code"),
                    "vessel_class": r.get("vessel_class"),
                    "description": r.get("taxonomy_description"),
                    "source": ["fearnleys_tsid"]}, "confirmed")
        reg.alias(code, eid, "p3_fearnleys_route", 0.99)
        if r.get("historical_code"):
            reg.alias(str(r["historical_code"]), eid, "p3_fearnleys_route", 0.8)
        stats["routes_fearnleys"] += 1
    for code, r in (b.get("indices") or {}).items():
        eid = f"index:{code}"
        reg.entity(eid, "index", (r or {}).get("name") or code,
                   {"code": code, "description": (r or {}).get("description"),
                    "source": ["baltic_taxonomy"]}, "confirmed")
        reg.alias(code, eid, "p3_baltic_index", 0.99)
        stats["indices"] += 1


def load_commodities(reg: Registry, stats: Counter) -> None:
    comm = json.loads((REF / "commodity_normalisation.json").read_text(encoding="utf-8"))
    canon: dict[str, dict] = {}
    for key, v in (comm.get("commodity_mappings") or {}).items():
        name = (v or {}).get("canonical") or key
        canon.setdefault(name, v or {})
    for name, v in canon.items():
        slug = N.company_slug(name) or N.company_slug(f"x{abs(hash(name))}")
        eid = f"commodity:{slug}"
        reg.entity(eid, "commodity", name,
                   {"canonical": name, "group": v.get("group"), "subgroup": v.get("subgroup"),
                    "vessel_class": v.get("vessel_class"),
                    "source": ["commodity_normalisation"]}, "confirmed")
        reg.alias(name, eid, "p3_commodity", 0.95)
        stats["commodities"] += 1
    for key, v in (comm.get("commodity_mappings") or {}).items():
        name = (v or {}).get("canonical") or key
        slug = N.company_slug(name)
        if slug:
            reg.alias(key, f"commodity:{slug}", "p3_commodity_synonym", 0.85)


def load_countries(reg: Registry, stats: Counter) -> None:
    for word, iso in N.NATIONALITY.items():
        eid = f"country:{iso}"
        reg.entity(eid, "country", ISO2_NAME.get(iso, iso), {"iso2": iso}, "confirmed")
        reg.alias(word, eid, "p3_nationality_lexicon", 0.9)
        stats["countries"] += 1


def load_p2_vessels(con, reg: Registry, stats: Counter) -> None:
    """Upgrade P2's IMO vessels; register name aliases for P2 provisional vessels."""
    rows = con.execute(
        "SELECT entity_id, canonical_name, status, attrs, created_by FROM entity "
        "WHERE entity_id LIKE 'vessel:imo:%'").fetchall()
    upgraded = 0
    for eid, name, status, attrs, created_by in rows:
        imo = (json.loads(attrs) if attrs else {}).get("vessel_key", "").replace("imo:", "") \
            or eid.rsplit(":", 1)[-1]
        seed_attrs = {"imo": imo}
        if created_by == "p2_transactions":
            seed_attrs["p2_claim"] = True
            upgraded += 1
        reg.entity(eid, "vessel", name, seed_attrs, "confirmed")
        if name:
            reg.alias(name, eid, "p2_claim_name", 0.9, norm=N.norm_vessel_name(name))
    stats["p2_imo_vessels"] = upgraded
    prov = con.execute(
        "SELECT entity_id, canonical_name FROM entity WHERE entity_id LIKE 'vessel:prov:%'").fetchall()
    kept = 0
    for eid, name in prov:
        if reg.alias(name, eid, "p2_claim_name", 0.4, norm=N.norm_vessel_name(name)):
            kept += 1
    stats["p2_prov_entities"] = len(prov)
    stats["p2_prov_aliases"] = kept


def load_counterparties(con, reg: Registry, port_names: dict[str, str], stats: Counter) -> None:
    """Counterparty strings in P2 claims -> country tags and provisional companies."""
    cur = con.execute("SELECT claimed FROM mention")
    name_counts: Counter = Counter()
    countries: Counter = Counter()
    while True:
        batch = cur.fetchmany(5000)
        if not batch:
            break
        for (claimed,) in batch:
            try:
                c = json.loads(claimed)
            except (TypeError, json.JSONDecodeError):
                stats["claim_json_bad"] += 1
                continue
            for raw in (c.get("counterparties") or []):
                if not isinstance(raw, str) or N.is_undisclosed(raw):
                    continue
                iso, rest = N.strip_nationality(raw)
                if iso:
                    countries[iso] += 1
                if rest and not N.is_undisclosed(rest):
                    name_counts[rest] += 1
    for iso, n in countries.items():
        eid = f"country:{iso}"
        if eid not in reg.entities:
            reg.entity(eid, "country", ISO2_NAME.get(iso, iso), {"iso2": iso}, "confirmed")
        stats["country_tags"] += 1
    for name, n in name_counts.items():
        nm = N.norm_company(name)
        if not nm or nm.isdigit() or len(nm) < 2 or nm in _TAG_BLOCK:
            continue
        pid = port_names.get(N.norm_text(name))
        if pid:
            reg.alias(name, pid, "p3_counterparty_port", 0.6)
            stats["counterparty_ports"] += 1
            continue
        slug = N.company_slug(name)
        if not slug:
            continue
        eid = f"company:int:{slug}"
        reg.entity(eid, "company", name.strip(), {"alias_count": 1,
                                                  "source": ["p2_claims"]}, "provisional")
        reg.alias(name, eid, "p3_counterparty", 0.55, norm=nm)
        stats["counterparty_companies"] += 1
    stats["counterparty_distinct"] = len(name_counts)


def write_out(con, reg: Registry, stats: Counter) -> None:
    ents = list(reg.entities.values())
    ali = list(reg.aliases.values())
    # a vessel name carried by many IMOs is a shipyard / hull placeholder, never an identity tag
    db_vessel_ids = {r[0] for r in
                     con.execute("SELECT entity_id FROM entity WHERE type = 'vessel'").fetchall()}
    db_company_ids = {r[0] for r in
                      con.execute("SELECT entity_id FROM entity WHERE type = 'company'").fetchall()}

    def _type(eid: str) -> str:
        e = reg.entities.get(eid)
        if e:
            return e["type"]
        return "vessel" if eid in db_vessel_ids else "company" if eid in db_company_ids else ""

    vcount: Counter = Counter()
    for a in ali:
        if _type(a["entity_id"]) == "vessel":
            vcount[a["alias_norm"]] += 1
    before = len(ali)
    ali = [a for a in ali
           if not (_type(a["entity_id"]) == "vessel"
                   and vcount[a["alias_norm"]] > N.ALIAS_MAX_IMOS)]
    stats["vessel_alias_dropped_ambiguous"] = before - len(ali)
    con.execute("CREATE OR REPLACE TEMP TABLE _seed_entity(entity_id VARCHAR, type VARCHAR, "
                "canonical_name VARCHAR, attrs VARCHAR, status VARCHAR, created_by VARCHAR)")
    con.execute("CREATE OR REPLACE TEMP TABLE _seed_alias(alias VARCHAR, alias_norm VARCHAR, "
                "entity_id VARCHAR, source VARCHAR, confidence DOUBLE, merged_by VARCHAR, "
                "valid_from DATE, valid_to DATE)")
    if ents:
        t = pa.table({
            "entity_id": [e["entity_id"] for e in ents],
            "type": [e["type"] for e in ents],
            "canonical_name": [e["canonical_name"] for e in ents],
            "attrs": [json.dumps(e["attrs"], ensure_ascii=False, default=str) for e in ents],
            "status": [e["status"] for e in ents],
            "created_by": [e["created_by"] for e in ents],
        }, schema=ENTITY_SCHEMA)
        con.register("_seed_entity_arrow", t)
        con.execute("INSERT INTO _seed_entity SELECT * FROM _seed_entity_arrow")
        con.unregister("_seed_entity_arrow")
    if ali:
        t = pa.table({
            "alias": [a["alias"] for a in ali],
            "alias_norm": [a["alias_norm"] for a in ali],
            "entity_id": [a["entity_id"] for a in ali],
            "source": [a["source"] for a in ali],
            "confidence": [a["confidence"] for a in ali],
            "merged_by": [a["merged_by"] for a in ali],
            "valid_from": [a["valid_from"] for a in ali],
            "valid_to": [a["valid_to"] for a in ali],
        }, schema=ALIAS_SCHEMA)
        con.register("_seed_alias_arrow", t)
        con.execute("INSERT INTO _seed_alias SELECT * FROM _seed_alias_arrow")
        con.unregister("_seed_alias_arrow")

    con.execute("BEGIN TRANSACTION")
    con.execute("DELETE FROM entity WHERE entity_id IN (SELECT entity_id FROM _seed_entity)")
    con.execute("INSERT INTO entity SELECT * FROM _seed_entity")
    # aliases owned by the seeding step are rebuilt; merge aliases (p3_merge_*) are preserved
    owned = ("'p2_claim_name'", "'p3_ais_name'", "'p3_benchmark_name'", "'p3_benchmark_operator'",
             "'p3_portwatch'", "'p3_gazetteer_port'", "'p3_gazetteer_region'", "'p3_baltic_route'",
             "'p3_baltic_index'", "'p3_fearnleys_route'", "'p3_commodity'",
             "'p3_commodity_synonym'", "'p3_nationality_lexicon'", "'p3_sec_company'",
             "'p3_sec_publisher'", "'p3_sec_ticker'", "'p3_counterparty'",
             "'p3_counterparty_port'")
    con.execute(f"DELETE FROM alias WHERE source IN ({', '.join(owned)})")
    con.execute("DELETE FROM alias WHERE (alias_norm, entity_id) IN "
                "(SELECT alias_norm, entity_id FROM _seed_alias)")
    con.execute("INSERT INTO alias SELECT * FROM _seed_alias")
    con.execute("COMMIT")

    stats["entities_written"] = len(ents)
    stats["aliases_written"] = len(ali)
    stats["entity_total"] = con.execute("SELECT count(*) FROM entity").fetchone()[0]
    stats["alias_total"] = con.execute("SELECT count(*) FROM alias").fetchone()[0]
    stats["by_type"] = dict(con.execute(
        "SELECT type, count(*) FROM entity GROUP BY 1 ORDER BY 2 DESC").fetchall())
    stats["by_status"] = dict(con.execute(
        "SELECT status, count(*) FROM entity GROUP BY 1").fetchall())
    stats["alias_by_source"] = dict(con.execute(
        "SELECT source, count(*) FROM alias GROUP BY 1 ORDER BY 2 DESC").fetchall())


def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB))
    con.execute("SET memory_limit='700MB'")
    con.execute("SET checkpoint_threshold='256MB'")
    con.execute("SET threads=2")
    reg = Registry()
    stats = reg.stats
    imos_by_name = load_ais(reg, stats)
    load_benchmark(reg, stats, imos_by_name)
    load_p2_vessels(con, reg, stats)
    load_sec(con, reg, stats)
    port_names = load_ports(reg, stats)
    load_routes_indices(reg, stats)
    load_commodities(reg, stats)
    load_countries(reg, stats)
    load_counterparties(con, reg, port_names, stats)
    write_out(con, reg, stats)
    con.close()

    out = {"phase": "P3", "step": "seed", "stats": dict(sorted(stats.items()))}
    (REPORTS / "p3_seed.json").write_text(json.dumps(out, indent=2, default=str) + "\n",
                                          encoding="utf-8")
    for k, v in sorted(stats.items(), key=lambda kv: str(kv[0])):
        print(f"{k}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
