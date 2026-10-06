#!/usr/bin/env python3
"""
scripts/format_book5_atlas.py
Complete, clean formatter for Book 5:
Lloyd's Maritime Atlas of World Ports and Shipping Places (24th Edition)
"""

import re
import subprocess
from pathlib import Path

def format_book5():
    p = Path("corpus/books/lloyds_maritime_atlas_24e.md")
    try:
        raw = subprocess.check_output(
            ["git", "show", f"HEAD:{p.as_posix()}"],
            text=True,
            encoding="utf-8"
        )
    except Exception:
        raw = p.read_text(encoding="utf-8")

    # 1. Preserve YAML frontmatter
    parts = raw.split("---", 2)
    fm = f"---{parts[1]}---\n"
    body = parts[2].lstrip("\r\n")

    # Clean out duplicate Summary block
    body = re.sub(r"## Summary\s*\n.*?(?=\n## Lloyds|\n### Facility Codes|\n## Geographical|\Z)", "", body, flags=re.S)
    body = re.sub(r"## Lloyds Maritime Atlas 24th Edition\s*\n", "", body)

    # Clean out raw (cid:0) and font artifact dumps
    body = body.replace("(cid:0)", "")

    # Preserve and ensure clean Facility Codes Legend
    legend = (
        "## Facility Codes Legend\n\n"
        "| Code | Facility Description |\n"
        "| :---: | :--- |\n"
        "| **P** | Petroleum terminal |\n"
        "| **Q** | Other liquid bulk |\n"
        "| **Y** | Dry bulk terminal |\n"
        "| **G** | General cargo |\n"
        "| **C** | Container facility |\n"
        "| **R** | Ro-Ro berth |\n"
        "| **L** | Cruise terminal |\n"
        "| **B** | Bunkers available |\n"
        "| **D** | Dry dock / shipyard repair |\n"
        "| **T** | Towage available |\n"
        "| **A** | Airport within 100km |\n\n"
        "---\n\n"
    )
    # Remove existing legend block if present to re-insert cleanly
    body = re.sub(r"###? Facility Codes Legend.*?(?=---\n\n|\n##|\Z)", "", body, flags=re.S)
    body = body.lstrip("-\r\n\t ")

    # 2. Split crammed multi-column port entries onto separate lines
    # Fast non-backtracking pattern: Coordinate sequence followed by start of next entry
    coord_split_pat = r"(\b\d{1,2}\s+\d{1,2}\s+[NS]\s+\d{1,3}\s+\d{1,2}\s+[EW](?:\s+[0-9A-Z]{1,4})?)\s+(?=[A-Z][^\n\r\d]{1,50}\s+\d{1,2}\s+\d{1,2}\s+[NS])"
    body = re.sub(coord_split_pat, r"\1\n", body)

    # Also handle country headers embedded inline before a port name
    # e.g., "FRANCE Menton 43 47 N..." -> "\n\n### FRANCE\n\nMenton 43 47 N..."
    known_countries = [
        "ALBANIA", "ALGERIA", "ANGOLA", "ARGENTINA", "AUSTRALIA", "BAHAMAS", "BAHRAIN",
        "BANGLADESH", "BARBADOS", "BELGIUM", "BELIZE", "BENIN", "BERMUDA", "BRAZIL",
        "BULGARIA", "CAMBODIA", "CAMEROON", "CANADA", "CHILE", "CHINA", "COLOMBIA",
        "CONGO", "COSTA RICA", "CROATIA", "CUBA", "CYPRUS", "DENMARK", "ECUADOR",
        "EGYPT", "ESTONIA", "FINLAND", "FRANCE", "GABON", "GEORGIA", "GERMANY",
        "GHANA", "GIBRALTAR", "GREECE", "GUATEMALA", "GUINEA", "GUYANA", "HAITI",
        "HONDURAS", "ICELAND", "INDIA", "INDONESIA", "IRAN", "IRAQ", "IRELAND",
        "ISRAEL", "ITALY", "JAMAICA", "JAPAN", "JORDAN", "KENYA", "KOREA", "KUWAIT",
        "LATVIA", "LEBANON", "LIBERIA", "LIBYA", "LITHUANIA", "MADAGASCAR", "MALAYSIA",
        "MALTA", "MAURITANIA", "MAURITIUS", "MEXICO", "MONACO", "MONTENEGRO", "MOROCCO",
        "MOZAMBIQUE", "MYANMAR", "NAMIBIA", "NETHERLANDS", "NEW ZEALAND", "NICARAGUA",
        "NIGERIA", "NORWAY", "OMAN", "PAKISTAN", "PANAMA", "PAPUA NEW GUINEA", "PERU",
        "PHILIPPINES", "POLAND", "PORTUGAL", "QATAR", "ROMANIA", "RUSSIA", "SAUDI ARABIA",
        "SENEGAL", "SIERRA LEONE", "SINGAPORE", "SLOVENIA", "SOMALIA", "SOUTH AFRICA",
        "SPAIN", "SRI LANKA", "SUDAN", "SURINAME", "SWEDEN", "SYRIA", "TAIWAN", "TANZANIA",
        "THAILAND", "TOGO", "TRINIDAD AND TOBAGO", "TUNISIA", "TURKEY", "UKRAINE",
        "UNITED ARAB EMIRATES", "UNITED KINGDOM", "UNITED STATES", "URUGUAY", "VENEZUELA",
        "VIETNAM", "YEMEN"
    ]
    for country in known_countries:
        # Separate inline country headers
        body = re.sub(rf"(?<=[a-zA-Z0-9\)])\s+\b{country}\b\s+(?=[A-Z0-9])", f"\n\n### {country}\n\n", body)
        # Standalone country lines or country at start of line
        body = re.sub(rf"(?:\n|^)\b{country}\b(?:\s*\(continued\))?\s*(?=[0-9A-Za-z])", f"\n\n### {country}\n\n", body)

    # 3. Clean excessive whitespace and empty lines
    body = re.sub(r"\n{3,}", "\n\n", body).strip()

    # Final document assembly
    doc = (
        fm + "\n"
        "# Lloyd's Maritime Atlas of World Ports and Shipping Places (24th Edition)\n\n"
        "**Publisher**: Lloyd's Marine Intelligence Unit (Informa UK Ltd.)  \n\n"
        "## Summary\n\n"
        "The premier reference guide to the world's ports and shipping places, providing precise latitude "
        "and longitude coordinates, commercial port facilities (petroleum, dry bulk, container, general cargo, "
        "bunkers, repair dry docks), canals, and regional marine indexation.\n\n"
        "---\n\n"
        f"{legend}"
        f"{body}\n"
    )

    p.write_text(doc, encoding="utf-8")
    dest = Path("knowledge/docs/books/lloyds_maritime_atlas_24e.md")
    dest.write_text(doc, encoding="utf-8")
    print(f"Book 5 formatted successfully: {len(doc)} chars, {len(doc.splitlines())} lines written to {p} and {dest}")

if __name__ == "__main__":
    format_book5()
