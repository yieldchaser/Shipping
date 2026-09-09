#!/usr/bin/env python3
"""
Fixture-Grounded Voyage History (NO FABRICATION)
================================================
Rebuilds the voyage-history layer from reported Fearnleys fixture legs ONLY:

  input : data/derived/fearnleys_fixtures_full.csv
          (date, vessel, imo, segment, department, commodity, load_port, discharge_port)
          + data/geospatial/portwatch_ports_master.csv (2065-port universe:
            portname / fullname / lat / lon / LOCODE, produced by
            scripts/scrapers/fetch_portwatch_ports_expanded.py)
  output: data/geospatial/voyage_history_fixturegrounded.csv (+ .parquet)

One row per reported fixture leg. Kept (real, as reported):
  - vessel name, imo AS REPORTED (blank stays blank - NO generated IMOs),
  - vessel_class from the segment/department mapping (map_segment_to_asset),
  - commodity, load_port, discharge_port, leg_date, leg_sequence (per vessel).

Port resolution (two passes, no new dependencies - stdlib + pandas only):
  1. legacy alias map: fixture-speak ("MEG", "usgc", "hedland") -> hub LOCODE
     (PORT_NAME_ALIASES / PORT_COORDINATES from build_geospatial_tracker.py).
  2. ports-universe pass against portwatch_ports_master.csv: normalize the
     fixture string (lowercase, punctuation -> space, drop generic tokens like
     port/terminal/anch), then
       a. direct LOCODE mention in the raw string (e.g. "... (JP TRG)"),
       b. exact match on normalized portname or fullname,
       c. prefix match (either direction, conservative),
       d. difflib close match (cutoff 0.87, conservative).
     Ambiguities (several ports sharing a name) resolve to the port with the
     largest vessel_count_total - deterministic, no editorializing.

Distance: great-circle nm ONLY when BOTH ends resolve, from either the hub
coordinate table (alias pass) or the ports-universe lat/lon (measured, source
served). Otherwise distance_nm is null. NO port lat/lon polylines, NO
status/days_waiting columns, NO DWT constants, NO synthetic IMOs, NO
+3-day departures. Every row is a REPORTED fixture leg ("reported fixture
voyages - not AIS positions" downstream). Nothing is synthesized.
"""
from __future__ import annotations

import difflib
import logging
import math
import re
import sys
from functools import lru_cache
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "geospatial"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

from build_geospatial_tracker import (  # noqa: E402  (path set above)
    PORT_COORDINATES,
    map_segment_to_asset,
    resolve_port_locode,
)

FIXTURES_PATH = ROOT / "data" / "derived" / "fearnleys_fixtures_full.csv"
PORTS_MASTER_PATH = ROOT / "data" / "geospatial" / "portwatch_ports_master.csv"
OUT_CSV = ROOT / "data" / "geospatial" / "voyage_history_fixturegrounded.csv"
OUT_PARQUET = ROOT / "data" / "geospatial" / "voyage_history_fixturegrounded.parquet"

COLUMNS = [
    "leg_sequence", "vessel", "imo", "vessel_class", "commodity",
    "load_port", "load_locode", "load_portid", "load_match",
    "discharge_port", "discharge_locode", "discharge_portid", "discharge_match",
    "leg_date", "distance_nm",
]

FORBIDDEN_COLUMNS = {
    "status", "days_waiting", "waiting_days", "imo_generated", "generated_imo",
    "dwt", "dwt_tons", "trajectory_sequence_json", "lat", "lon", "latlon",
    "departure_date", "estimated_departure", "arrival_status", "current_status",
}

# Generic tokens dropped during ports-universe normalization (parent-steered
# examples: 'port' / 'terminal' / 'anch').
_GENERIC_TOKENS = {"port", "terminal", "anch", "anchorage", "berth", "the", "of"}

_LOCODE_RE = re.compile(r"\b([A-Z]{2})[\s:]([A-Z]{3})\b")  # e.g. "JP TRG" / "NL:RTM"

# Conservative fuzzy threshold: a fixture string must be nearly the port name.
_FUZZY_CUTOFF = 0.87
_MIN_FUZZY_LEN = 5
_MIN_PREFIX_LEN = 5


def _norm(s: str) -> str:
    """Lowercase, punctuation -> space, collapse whitespace, drop generics."""
    s = re.sub(r"[^a-z0-9\s]", " ", str(s).lower())
    toks = [t for t in s.split() if t and t not in _GENERIC_TOKENS]
    return " ".join(toks)


class PortResolver:
    """Two-pass fixture-port resolver backed by the 2065-port universe."""

    def __init__(self, ports_master: pd.DataFrame):
        # universe candidate names -> port record (largest vessel_count wins ties)
        best: dict[str, pd.Series] = {}
        for _, p in ports_master.iterrows():
            names = []
            for cand in (p.get("portname"), p.get("fullname")):
                n = _norm(cand) if isinstance(cand, str) else ""
                if n and len(n) >= _MIN_PREFIX_LEN:
                    names.append(n)
            for n in names:
                prev = best.get(n)
                if prev is None or (p.get("vessel_count_total") or 0) > (prev.get("vessel_count_total") or 0):
                    best[n] = p
        self._exact_names = best
        self._names_sorted = sorted(best.keys())
        # LOCODE -> (portid, lat, lon) for ports that expose one
        self._locode_index: dict[str, tuple] = {}
        for _, p in ports_master.iterrows():
            loc = p.get("LOCODE")
            if isinstance(loc, str):
                loc = loc.strip().upper().replace(":", " ")
                m = re.match(r"^([A-Z]{2})\s*([A-Z]{3})$", loc)
                if m:
                    self._locode_index[f"{m.group(1)} {m.group(2)}"] = (
                        p.get("portid"), p.get("lat"), p.get("lon"))
        # alias-map LOCODEs also resolve through the hub coordinate table
        self._hub_locodes = set(PORT_COORDINATES.keys())

    # -- pass 1: alias map -------------------------------------------------- #
    def via_alias(self, raw: str):
        code = resolve_port_locode(raw)
        if code and code in self._hub_locodes:
            hub = PORT_COORDINATES[code]
            return {"locode": code, "portid": "", "lat": hub["lat"], "lon": hub["lon"]}
        if code:  # alias outside the hub table (rare): record code, no coords
            return {"locode": code, "portid": "", "lat": None, "lon": None}
        return None

    # -- pass 2: ports-universe resolution ---------------------------------- #
    def via_universe(self, raw: str):
        if not raw or not isinstance(raw, str) or not raw.strip():
            return None
        # (a) direct LOCODE mention, e.g. "Sines (PT SIE)" / "NLRTM"
        for m in _LOCODE_RE.finditer(raw.upper()):
            key = f"{m.group(1)} {m.group(2)}"
            if key in self._locode_index:
                pid, lat, lon = self._locode_index[key]
                return {"locode": key.replace(" ", ""), "portid": pid, "lat": lat, "lon": lon}
        n = _norm(raw)
        if not n:
            return None
        # (b) exact
        rec = self._exact_names.get(n)
        if rec is not None:
            return self._rec(rec, "exact")
        # (c) prefix (either direction; fixture may carry qualifiers/anchors)
        for cand in self._names_sorted:
            if len(cand) >= _MIN_PREFIX_LEN and (n.startswith(cand) or cand.startswith(n)):
                return self._rec(self._exact_names[cand], "prefix")
        # (d) fuzzy close match (conservative cutoff)
        if len(n) >= _MIN_FUZZY_LEN:
            close = difflib.get_close_matches(n, self._names_sorted, n=1, cutoff=_FUZZY_CUTOFF)
            if close:
                return self._rec(self._exact_names[close[0]], "fuzzy")
        return None

    @staticmethod
    def _rec(p: pd.Series, quality: str):
        loc = p.get("LOCODE")
        loc = re.sub(r"[\s:]+", "", str(loc).upper()) if isinstance(loc, str) else ""
        return {"locode": loc, "portid": str(p.get("portid") or ""),
                "lat": p.get("lat"), "lon": p.get("lon"), "quality": quality}

    # -- combined, memoized per unique fixture string ------------------------ #
    def resolve(self, raw: str):
        if not raw or not isinstance(raw, str) or not raw.strip():
            return None
        hit = self.via_alias(raw)
        if hit:
            hit.setdefault("quality", "alias")
            return hit
        hit = self.via_universe(raw)
        if hit:
            hit.setdefault("quality", "locode" if hit.get("locode") and not hit.get("portid") else hit.get("quality", ""))
        return hit


def haversine_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in nautical miles (same constant as the tracker)."""
    r_nm = 3440.065
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2.0) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2)
    return round(2.0 * r_nm * math.atan2(math.sqrt(a), math.sqrt(1.0 - a)), 1)


def build() -> pd.DataFrame:
    if not FIXTURES_PATH.exists():
        raise FileNotFoundError(f"Missing fixtures dataset: {FIXTURES_PATH}")
    if not PORTS_MASTER_PATH.exists():
        raise FileNotFoundError(
            f"Missing ports universe {PORTS_MASTER_PATH} - run "
            "scripts/scrapers/fetch_portwatch_ports_expanded.py first.")

    df = pd.read_csv(
        FIXTURES_PATH,
        usecols=["date", "vessel", "imo", "segment", "department", "commodity",
                 "load_port", "discharge_port"],
        dtype=str,
        keep_default_na=False,
        encoding="utf-8",
        encoding_errors="replace",
        low_memory=False,
    )
    logging.info("Fixture legs read: %d", len(df))

    ports_master = pd.read_csv(PORTS_MASTER_PATH, low_memory=False)
    resolver = PortResolver(ports_master)
    logging.info("Resolver index: %d normalized names, %d locodes",
                 len(resolver._names_sorted), len(resolver._locode_index))

    # One row per reported leg; a leg requires a date and a vessel to belong to.
    df = df[(df["date"].str.strip() != "") & (df["vessel"].str.strip() != "")].copy()
    df["leg_date"] = df["date"].str.strip()
    df["vessel"] = df["vessel"].str.strip()
    # IMO AS REPORTED: blank stays blank. No crc32 generation, ever.
    df["imo"] = df["imo"].str.strip()

    df["vessel_class"] = df.apply(
        lambda r: map_segment_to_asset(r.get("segment"), r.get("department")), axis=1)
    df["commodity"] = df["commodity"].str.strip()
    df["load_port"] = df["load_port"].str.strip()
    df["discharge_port"] = df["discharge_port"].str.strip()

    # resolve unique port strings once (memoized), then map
    @lru_cache(maxsize=200_000)
    def _res(raw: str):
        return resolver.resolve(raw)

    load_hits = df["load_port"].map(_res)
    disc_hits = df["discharge_port"].map(_res)

    for side, hits in (("load", load_hits), ("discharge", disc_hits)):
        df[f"{side}_locode"] = hits.map(lambda h: (h or {}).get("locode", "") or "")
        df[f"{side}_portid"] = hits.map(lambda h: (h or {}).get("portid", "") or "")
        df[f"{side}_match"] = hits.map(lambda h: (h or {}).get("quality", "") or "")

    def _distance(i):
        a, b = load_hits[i], disc_hits[i]
        if not a or not b:
            return None
        la, loa = a.get("lat"), a.get("lon")
        lb, lob = b.get("lat"), b.get("lon")
        try:
            if la is None or loa is None or lb is None or lob is None:
                return None
            return haversine_nm(float(la), float(loa), float(lb), float(lob))
        except (TypeError, ValueError):
            return None

    df["distance_nm"] = [_distance(i) for i in df.index]

    df["leg_sequence"] = (
        df.sort_values(["vessel", "leg_date"], kind="stable")
          .groupby("vessel")
          .cumcount() + 1
    )

    out = df[COLUMNS].sort_values(["vessel", "leg_date", "leg_sequence"],
                                  kind="stable").reset_index(drop=True)
    out.to_csv(OUT_CSV, index=False)
    out.to_parquet(OUT_PARQUET, compression="zstd", index=False)
    resolved_load = int((out["load_match"] != "").sum())
    resolved_disc = int((out["discharge_match"] != "").sum())
    both = int(((out["load_match"] != "") & (out["discharge_match"] != "")).sum())
    dist = int(out["distance_nm"].notna().sum())
    logging.info("[ok] %s: %d legs (%d vessels)", OUT_CSV.name, len(out), out["vessel"].nunique())
    logging.info("  resolution: load %d (%.1f%%) | discharge %d (%.1f%%) | both %d (%.1f%%) | distance %d",
                 resolved_load, 100.0 * resolved_load / len(out),
                 resolved_disc, 100.0 * resolved_disc / len(out),
                 both, 100.0 * both / len(out), dist)
    for q in ("alias", "exact", "prefix", "fuzzy"):
        n = int((out["load_match"] == q).sum() + (out["discharge_match"] == q).sum())
        logging.info("  match quality %-6s (both sides): %d", q, n)
    return out


if __name__ == "__main__":
    build()
