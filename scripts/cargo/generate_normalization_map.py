#!/usr/bin/env python3
"""
Generate Canonical Commodity and Region Normalization Reference Map
Maps broker fixture shorthand strings and dirty values into Signal Ocean canonical taxonomy.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
OUTPUT_FILE = ROOT / "data" / "reference" / "commodity_normalisation.json"

NORMALIZATION_MAP = {
    "version": "1.0.0",
    "description": "Canonical reference mapping for broker fixtures and regional shorthand to Signal Ocean cargo taxonomy",
    "commodity_mappings": {
        # Grains
        "grain": {"canonical": "Grain (Clean/General)", "group": "Agricultural Products", "subgroup": "Grains", "vessel_class": "Panamax"},
        "grains": {"canonical": "Grain (Clean/General)", "group": "Agricultural Products", "subgroup": "Grains", "vessel_class": "Panamax"},
        "grain clean": {"canonical": "Grain (Clean/General)", "group": "Agricultural Products", "subgroup": "Grains", "vessel_class": "Panamax"},
        "grain/bale": {"canonical": "Grain (Clean/General)", "group": "Agricultural Products", "subgroup": "Grains", "vessel_class": "Panamax"},
        "wheat": {"canonical": "Wheat", "group": "Agricultural Products", "subgroup": "Grains", "vessel_class": "Panamax"},
        "corn": {"canonical": "Corn", "group": "Agricultural Products", "subgroup": "Grains", "vessel_class": "Panamax"},
        "soybeans": {"canonical": "Soybeans", "group": "Agricultural Products", "subgroup": "Grains", "vessel_class": "Panamax"},
        "soybean": {"canonical": "Soybeans", "group": "Agricultural Products", "subgroup": "Grains", "vessel_class": "Panamax"},
        "barley": {"canonical": "Barley", "group": "Agricultural Products", "subgroup": "Grains", "vessel_class": "Panamax"},
        "sorghum": {"canonical": "Sorghum", "group": "Agricultural Products", "subgroup": "Grains", "vessel_class": "Panamax"},
        "rice": {"canonical": "Rice", "group": "Agricultural Products", "subgroup": "Grains", "vessel_class": "Handysize"},
        "oats": {"canonical": "Oats", "group": "Agricultural Products", "subgroup": "Grains", "vessel_class": "Handysize"},
        "sugar": {"canonical": "Sugar", "group": "Agricultural Products", "subgroup": "Other Agricultural", "vessel_class": "Supramax"},
        "raw sugar": {"canonical": "Sugar", "group": "Agricultural Products", "subgroup": "Other Agricultural", "vessel_class": "Supramax"},
        "canola": {"canonical": "Canola", "group": "Agricultural Products", "subgroup": "Seeds, Beans and Nuts", "vessel_class": "Panamax"},

        # Ores & Rocks
        "iron ore": {"canonical": "Iron Ore", "group": "Ores and Rocks", "subgroup": "Iron Ore", "vessel_class": "Capesize"},
        "ironore": {"canonical": "Iron Ore", "group": "Ores and Rocks", "subgroup": "Iron Ore", "vessel_class": "Capesize"},
        "iron ore fines": {"canonical": "Iron Ore Fines", "group": "Ores and Rocks", "subgroup": "Iron Ore", "vessel_class": "Capesize"},
        "iron ore pellets": {"canonical": "Iron Ore Pellets", "group": "Ores and Rocks", "subgroup": "Iron Ore", "vessel_class": "Capesize"},
        "iron ore lumps": {"canonical": "Iron Ore Lumps", "group": "Ores and Rocks", "subgroup": "Iron Ore", "vessel_class": "Capesize"},
        "pellets": {"canonical": "Iron Ore Pellets", "group": "Ores and Rocks", "subgroup": "Iron Ore", "vessel_class": "Capesize"},
        "fines": {"canonical": "Iron Ore Fines", "group": "Ores and Rocks", "subgroup": "Iron Ore", "vessel_class": "Capesize"},
        "bauxite": {"canonical": "Bauxite", "group": "Ores and Rocks", "subgroup": "Other Ores and Rocks", "vessel_class": "Capesize"},
        "alumina": {"canonical": "Alumina", "group": "Ores and Rocks", "subgroup": "Other Ores and Rocks", "vessel_class": "Supramax"},
        "nickel ore": {"canonical": "Nickel Ore", "group": "Ores and Rocks", "subgroup": "Other Ores and Rocks", "vessel_class": "Supramax"},
        "manganese ore": {"canonical": "Manganese Ore", "group": "Ores and Rocks", "subgroup": "Other Ores and Rocks", "vessel_class": "Supramax"},
        "chrome ore": {"canonical": "Chrome Ore", "group": "Ores and Rocks", "subgroup": "Other Ores and Rocks", "vessel_class": "Supramax"},
        "spodumene": {"canonical": "Spodumene", "group": "Ores and Rocks", "subgroup": "Other Ores and Rocks", "vessel_class": "Supramax"},
        "limestone": {"canonical": "Limestone", "group": "Ores and Rocks", "subgroup": "Other Ores and Rocks", "vessel_class": "Supramax"},

        # Energy / Coal
        "coal": {"canonical": "Coal", "group": "Energy", "subgroup": "Coal", "vessel_class": "Capesize"},
        "thermal coal": {"canonical": "Thermal Coal", "group": "Energy", "subgroup": "Coal", "vessel_class": "Panamax"},
        "metallurgical coal": {"canonical": "Metallurgical Coal", "group": "Energy", "subgroup": "Coal", "vessel_class": "Capesize"},
        "coking coal": {"canonical": "Metallurgical Coal", "group": "Energy", "subgroup": "Coal", "vessel_class": "Capesize"},
        "anthracite": {"canonical": "Anthracite", "group": "Energy", "subgroup": "Coal", "vessel_class": "Panamax"},
        "petcoke": {"canonical": "Petcoke", "group": "Energy", "subgroup": "Other Energy", "vessel_class": "Supramax"},
        "coke": {"canonical": "Coke", "group": "Energy", "subgroup": "Other Energy", "vessel_class": "Supramax"},

        # Wet & Gas
        "crude oil": {"canonical": "Crude Oil", "group": "Tankers & Gas", "subgroup": "Crude Oil", "vessel_class": "VLCC"},
        "crude": {"canonical": "Crude Oil", "group": "Tankers & Gas", "subgroup": "Crude Oil", "vessel_class": "VLCC"},
        "dirty": {"canonical": "Dirty Petroleum Products (DPP)", "group": "Tankers & Gas", "subgroup": "DPP", "vessel_class": "Suezmax"},
        "dpp": {"canonical": "Dirty Petroleum Products (DPP)", "group": "Tankers & Gas", "subgroup": "DPP", "vessel_class": "Suezmax"},
        "cpp": {"canonical": "Clean Petroleum Products (CPP)", "group": "Tankers & Gas", "subgroup": "CPP", "vessel_class": "LR2 / MR"},
        "clean": {"canonical": "Clean Petroleum Products (CPP)", "group": "Tankers & Gas", "subgroup": "CPP", "vessel_class": "LR2 / MR"},
        "ulsd": {"canonical": "Ultra-Low Sulfur Diesel (ULSD)", "group": "Tankers & Gas", "subgroup": "CPP", "vessel_class": "MR"},
        "diesel": {"canonical": "Diesel", "group": "Tankers & Gas", "subgroup": "CPP", "vessel_class": "MR"},
        "gasoline": {"canonical": "Gasoline", "group": "Tankers & Gas", "subgroup": "CPP", "vessel_class": "MR"},
        "jet": {"canonical": "Jet Fuel", "group": "Tankers & Gas", "subgroup": "CPP", "vessel_class": "MR"},
        "naphtha": {"canonical": "Naphtha", "group": "Tankers & Gas", "subgroup": "CPP", "vessel_class": "LR1"},
        "fuel oil": {"canonical": "Fuel Oil", "group": "Tankers & Gas", "subgroup": "DPP", "vessel_class": "Aframax"},
        "lpg": {"canonical": "LPG", "group": "Tankers & Gas", "subgroup": "LPG", "vessel_class": "VLGC"},
        "butane": {"canonical": "Butane", "group": "Tankers & Gas", "subgroup": "LPG", "vessel_class": "VLGC"},
        "propane": {"canonical": "Propane", "group": "Tankers & Gas", "subgroup": "LPG", "vessel_class": "VLGC"},
        "ethylene": {"canonical": "Ethylene", "group": "Tankers & Gas", "subgroup": "Chemical Gases", "vessel_class": "Gas Carrier"},
        "lng": {"canonical": "LNG", "group": "Tankers & Gas", "subgroup": "LNG", "vessel_class": "LNG Carrier (174k)"},

        # Minerals & Metals
        "steel": {"canonical": "Steel Products", "group": "Minerals and Metals", "subgroup": "Steel", "vessel_class": "Supramax"},
        "steels": {"canonical": "Steel Products", "group": "Minerals and Metals", "subgroup": "Steel", "vessel_class": "Supramax"},
        "steel coils": {"canonical": "Steel Coils", "group": "Minerals and Metals", "subgroup": "Steel", "vessel_class": "Handysize"},
        "steel slabs": {"canonical": "Steel Slabs", "group": "Minerals and Metals", "subgroup": "Steel", "vessel_class": "Handysize"},
        "scrap": {"canonical": "Scrap Metal", "group": "Minerals and Metals", "subgroup": "Metals", "vessel_class": "Supramax"},
        "scrap metals": {"canonical": "Scrap Metal", "group": "Minerals and Metals", "subgroup": "Metals", "vessel_class": "Supramax"},
        "salt": {"canonical": "Salt", "group": "Minerals and Metals", "subgroup": "Minerals", "vessel_class": "Supramax"},
        "gypsum": {"canonical": "Gypsum", "group": "Minerals and Metals", "subgroup": "Minerals", "vessel_class": "Supramax"},
        "minerals": {"canonical": "General Minerals", "group": "Minerals and Metals", "subgroup": "Minerals", "vessel_class": "Supramax"},

        # Bulk Chemicals & Fertilizers
        "urea": {"canonical": "Urea", "group": "Bulk Chemicals", "subgroup": "Fertilizers", "vessel_class": "Supramax"},
        "fertilizer": {"canonical": "Fertilizers (Combined)", "group": "Bulk Chemicals", "subgroup": "Fertilizers", "vessel_class": "Supramax"},
        "fertilizers": {"canonical": "Fertilizers (Combined)", "group": "Bulk Chemicals", "subgroup": "Fertilizers", "vessel_class": "Supramax"},
        "potash": {"canonical": "Potash", "group": "Bulk Chemicals", "subgroup": "Fertilizers", "vessel_class": "Supramax"},
        "phosphate": {"canonical": "Phosphate", "group": "Bulk Chemicals", "subgroup": "Fertilizers", "vessel_class": "Supramax"},
        "sulphur": {"canonical": "Sulphur", "group": "Bulk Chemicals", "subgroup": "Fertilizers", "vessel_class": "Supramax"},
        "sulfur": {"canonical": "Sulphur", "group": "Bulk Chemicals", "subgroup": "Fertilizers", "vessel_class": "Supramax"},

        # Cement & Solids
        "cement": {"canonical": "Cement", "group": "Cement and Other Solids", "subgroup": "Cement and Aggregates", "vessel_class": "Handysize"},
        "clinker": {"canonical": "Clinker", "group": "Cement and Other Solids", "subgroup": "Cement and Aggregates", "vessel_class": "Supramax"},
        "slag": {"canonical": "Slag", "group": "Cement and Other Solids", "subgroup": "Cement and Aggregates", "vessel_class": "Supramax"},

        # General & Unclassified
        "general cargo": {"canonical": "General Cargo / Breakbulk", "group": "General & Breakbulk", "subgroup": "General Cargo", "vessel_class": "Handysize"},
        "bulk": {"canonical": "Bulk Unspecified", "group": "General & Breakbulk", "subgroup": "Dry Bulk", "vessel_class": "Supramax"}
    },
    "region_mappings": {
        "MEG": {"region_name": "Middle East Gulf", "basin": "Middle East"},
        "AG": {"region_name": "Middle East Gulf", "basin": "Middle East"},
        "RAS TANURA": {"region_name": "Middle East Gulf", "basin": "Middle East"},
        "FUJAIRAH": {"region_name": "Middle East Gulf", "basin": "Middle East"},
        "MINA AL AHMADI": {"region_name": "Middle East Gulf", "basin": "Middle East"},
        "Ras Laffan": {"region_name": "Middle East Gulf", "basin": "Middle East"},
        "Ruwais": {"region_name": "Middle East Gulf", "basin": "Middle East"},

        "USG": {"region_name": "US Gulf Coast", "basin": "Atlantic"},
        "Houston": {"region_name": "US Gulf Coast", "basin": "Atlantic"},
        "New Orleans": {"region_name": "US Gulf Coast", "basin": "Atlantic"},
        "Corpus Christi": {"region_name": "US Gulf Coast", "basin": "Atlantic"},
        "MISSISSIPPI": {"region_name": "US Gulf Coast", "basin": "Atlantic"},

        "WAFR": {"region_name": "West Africa", "basin": "Atlantic"},
        "NIGERIA": {"region_name": "West Africa", "basin": "Atlantic"},
        "ANGOLA": {"region_name": "West Africa", "basin": "Atlantic"},
        "GUINEA": {"region_name": "West Africa", "basin": "Atlantic"},
        "KAMSAR": {"region_name": "West Africa", "basin": "Atlantic"},

        "BRAZIL": {"region_name": "Brazil / ECSA", "basin": "Atlantic"},
        "TUBARAO": {"region_name": "Brazil / ECSA", "basin": "Atlantic"},
        "PONTA DA MADEIRA": {"region_name": "Brazil / ECSA", "basin": "Atlantic"},
        "SANTOS": {"region_name": "Brazil / ECSA", "basin": "Atlantic"},
        "ITAGUAI": {"region_name": "Brazil / ECSA", "basin": "Atlantic"},
        "GUYANA": {"region_name": "Brazil / ECSA", "basin": "Atlantic"},
        "ECM": {"region_name": "East Coast Mexico / Caribbean", "basin": "Atlantic"},

        "BOT": {"region_name": "Black Sea & Mediterranean", "basin": "Mediterranean"},
        "CPC": {"region_name": "Black Sea & Mediterranean", "basin": "Mediterranean"},
        "NOVO": {"region_name": "Black Sea & Mediterranean", "basin": "Mediterranean"},
        "CEYHAN": {"region_name": "Black Sea & Mediterranean", "basin": "Mediterranean"},
        "SIDI KERIR": {"region_name": "Black Sea & Mediterranean", "basin": "Mediterranean"},
        "ARZEW": {"region_name": "Black Sea & Mediterranean", "basin": "Mediterranean"},
        "MARSA EL HARIGA": {"region_name": "Black Sea & Mediterranean", "basin": "Mediterranean"},

        "AUSTRALIA": {"region_name": "Australia / Indo-Pacific", "basin": "Pacific"},
        "PORT HEDLAND": {"region_name": "Australia / Indo-Pacific", "basin": "Pacific"},
        "DAMPIER": {"region_name": "Australia / Indo-Pacific", "basin": "Pacific"},
        "NEWCASTLE": {"region_name": "Australia / Indo-Pacific", "basin": "Pacific"},
        "HAY POINT": {"region_name": "Australia / Indo-Pacific", "basin": "Pacific"},
        "GLADSTONE": {"region_name": "Australia / Indo-Pacific", "basin": "Pacific"},
        "Kalimantan Island": {"region_name": "Australia / Indo-Pacific", "basin": "Pacific"},
        "INDONESIA": {"region_name": "Australia / Indo-Pacific", "basin": "Pacific"},

        "CHINA": {"region_name": "China / Far East", "basin": "Pacific"},
        "EAST": {"region_name": "China / Far East", "basin": "Pacific"},
        "East": {"region_name": "China / Far East", "basin": "Pacific"},
        "OPTS China": {"region_name": "China / Far East", "basin": "Pacific"},
        "NINGBO": {"region_name": "China / Far East", "basin": "Pacific"},
        "QINGDAO": {"region_name": "China / Far East", "basin": "Pacific"},
        "ROK": {"region_name": "China / Far East", "basin": "Pacific"},
        "JAPAN": {"region_name": "China / Far East", "basin": "Pacific"},
        "SINGAPORE": {"region_name": "Southeast Asia", "basin": "Pacific"},

        "INDIA": {"region_name": "India / South Asia", "basin": "Indian Ocean"},
        "WCI": {"region_name": "India / South Asia", "basin": "Indian Ocean"},
        "SIKKA": {"region_name": "India / South Asia", "basin": "Indian Ocean"},
        "VADINAR": {"region_name": "India / South Asia", "basin": "Indian Ocean"},
        "MUMBAI": {"region_name": "India / South Asia", "basin": "Indian Ocean"},
        "PARADIP": {"region_name": "India / South Asia", "basin": "Indian Ocean"},
        "CHENNAI": {"region_name": "India / South Asia", "basin": "Indian Ocean"},

        "UKC": {"region_name": "Europe / UK Continent", "basin": "Atlantic"},
        "UKCM": {"region_name": "Europe / UK Continent", "basin": "Atlantic"},
        "ROTTERDAM": {"region_name": "Europe / UK Continent", "basin": "Atlantic"},
        "SPAIN": {"region_name": "Europe / UK Continent", "basin": "Mediterranean"},
        "MED": {"region_name": "Europe / UK Continent", "basin": "Mediterranean"}
    }
}

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(NORMALIZATION_MAP, f, indent=2)

print(f"Generated {OUTPUT_FILE} with {len(NORMALIZATION_MAP['commodity_mappings'])} commodities and {len(NORMALIZATION_MAP['region_mappings'])} regions.")
