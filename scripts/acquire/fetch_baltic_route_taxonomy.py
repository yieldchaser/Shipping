#!/usr/bin/env python3
"""
scripts/acquire/fetch_baltic_route_taxonomy.py

Authoritative Baltic Exchange Route Taxonomy Harvester.
Scrapes https://www.balticexchange.com/en/data-services/market-information0/indices.html
Follows Guardrails §0.66 escalation ladder (live -> headers -> archive fallback).
Outputs structured canonical map to data/reference/baltic_route_taxonomy.json.
"""

import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_FILE = ROOT / "data" / "reference" / "baltic_route_taxonomy.json"

LIVE_URL = "https://www.balticexchange.com/en/data-services/market-information0/indices.html"
ARCHIVE_URL = "https://web.archive.org/web/20260420064708id_/https://www.balticexchange.com/en/data-services/market-information0/indices.html"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.balticexchange.com/",
}

def fetch_html():
    # Rung 1: Try live URL with browser headers
    print(f"[1/8] Probing live Baltic URL: {LIVE_URL}")
    req = urllib.request.Request(LIVE_URL, headers=HEADERS)
    used_url = LIVE_URL
    status_code = None
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            status_code = resp.status
            content = resp.read().decode("utf-8", errors="replace")
            if "<title>Challenge Validation</title>" in content or len(content) < 5000:
                print(f"[!] Live URL returned Challenge Validation (Imperva WAF). Escalating per §0.66...")
                content = None
            else:
                print(f"[+] Live URL succeeded! Status {status_code}, length {len(content)}")
                return content, LIVE_URL, status_code
    except Exception as e:
        print(f"[!] Live fetch failed: {e}")

    # Rung 7: Fallback to confirmed snapshot from Wayback Machine
    print(f"[7/8] Escalating to Wayback Machine archive: {ARCHIVE_URL}")
    archive_req = urllib.request.Request(ARCHIVE_URL, headers=HEADERS)
    try:
        with urllib.request.urlopen(archive_req, timeout=20) as resp:
            status_code = resp.status
            content = resp.read().decode("utf-8", errors="replace")
            print(f"[+] Wayback snapshot retrieved! Status {status_code}, length {len(content)}")
            return content, ARCHIVE_URL, status_code
    except Exception as e:
        print(f"[x] Fatal: Failed to fetch from both live and archive: {e}")
        sys.exit(1)

def parse_taxonomy(html, source_url):
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")
    print(f"Parsing {len(tables)} HTML tables from document...")

    sections = {}
    routes_lookup = {}
    index_formulas = {}
    vessel_specs = {}
    baskets = {}

    table_class_map = {
        0: ("Capesize", "Dry Bulk", "usd/day"),
        1: ("Panamax", "Dry Bulk", "usd/day"),
        2: ("Supramax", "Dry Bulk", "usd/day"),
        3: ("Handysize", "Dry Bulk", "usd/day"),
        4: ("Clean Tankers", "Tanker Clean", "worldscale"),
        5: ("Dirty Tankers", "Tanker Dirty", "worldscale"),
        6: ("BLNG", "Gas", "usd/day"),
        7: ("BLPG", "Gas", "usd/day"),
        8: ("Container", "Container", "usd/feu"),
        9: ("Air Freight", "Air", "usd/kg")
    }

    # Voyage freight routes quoted in $/tonne
    TONNE_ROUTES = {"C2", "C3", "C5", "C7", "C17"}

    for idx, table in enumerate(tables):
        vessel_class, category, default_unit = table_class_map.get(idx, ("Unknown", "Unknown", "unknown"))
        rows = table.find_all("tr")
        if not rows:
            continue

        header_cols = [th.get_text(strip=True) for th in rows[0].find_all(["td", "th"])]
        section_name = header_cols[0] if header_cols else f"Section_{idx}"
        section_routes = []

        for row in rows[1:]:
            cells = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
            if not cells or not any(cells):
                continue

            full_text = " ".join(cells)

            # Check for formulas
            if "Weighted Timecharter Average" in full_text or "Weighted Time Charter Average" in full_text:
                baskets[f"{vessel_class}_TCE_Basket"] = full_text
                continue
            if any(idx_kw in full_text for idx_kw in ["Baltic Capesize Index (BCI)", "Baltic Panamax Index (BPI)", "Baltic Supramax Index (BSI)", "Baltic Handysize Index (BHSI)", "Baltic Clean Tanker Index (BCTI)", "Baltic Dirty Tanker Index (BDTI)", "Baltic LPG Index (BLPG)"]):
                m = re.match(r"(Baltic [^:]+[:=])\s*(.*)", full_text)
                if m:
                    idx_name = m.group(1).replace("=", "").replace(":", "").strip()
                    index_formulas[idx_name] = m.group(2).strip()
                else:
                    index_formulas[f"{vessel_class}_Index"] = full_text
                continue

            # Check for vessel specs
            if "vessel for Timecharter routes" in full_text:
                vessel_specs[vessel_class] = full_text
                continue

            # Check for tanker baskets
            if any(b_kw in full_text for b_kw in ["VLCC TCE", "Suezmax TCE", "Aframax TCE", "MR Atlantic Basket", "MR Pacific Basket"]):
                baskets[full_text.split("(")[0].strip()] = full_text
                continue

            # Check if this is a route row
            if len(cells) >= 2:
                raw_code = cells[0]
                raw_desc = cells[1]

                # Clean up code and description if duplicated
                if " - " in raw_code and not raw_desc:
                    parts = raw_code.split(" - ", 1)
                    code = parts[0].strip()
                    desc = parts[1].strip()
                else:
                    code = raw_code.split(" - ")[0].strip()
                    desc = raw_desc.replace(f"{code} - ", "").replace(f"{code}\xa0-\xa0", "").strip()

                if not code or len(code) > 15:
                    continue

                # Determine route unit
                route_unit = "usd/tonne" if code in TONNE_ROUTES else default_unit

                route_entry = {
                    "code": code,
                    "description": desc,
                    "vessel_class": vessel_class,
                    "category": category,
                    "unit": route_unit
                }
                section_routes.append(route_entry)
                routes_lookup[code] = route_entry

        sections[vessel_class] = section_routes

    # Compile authoritative taxonomy document
    taxonomy = {
        "metadata": {
            "source_authority": "Baltic Exchange Official Route Taxonomy",
            "source_url": source_url,
            "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
            "total_routes": len(routes_lookup),
            "sections_count": len(sections),
            "description": "Canonical code -> description -> class -> unit map, index formulas, and vessel specs."
        },
        "routes": routes_lookup,
        "sections": sections,
        "index_formulas": index_formulas,
        "vessel_specifications": vessel_specs,
        "baskets": baskets
    }
    return taxonomy

def main():
    html, url, status = fetch_html()
    taxonomy = parse_taxonomy(html, url)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(taxonomy, f, indent=2)

    print(f"\n[+] Successfully generated {OUTPUT_FILE}")
    print(f"    Total routes parsed: {taxonomy['metadata']['total_routes']}")
    print(f"    Index formulas parsed: {len(taxonomy['index_formulas'])}")
    print(f"    Vessel specs parsed: {len(taxonomy['vessel_specifications'])}")
    print(f"    Baskets parsed: {len(taxonomy['baskets'])}")

if __name__ == "__main__":
    main()
