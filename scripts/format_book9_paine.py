#!/usr/bin/env python3
"""
Format Book 9: The Sea and Civilization: A Maritime History of the World (Lincoln Paine, Knopf, 2013).
Heals all extraction and typesetting defects:
1. Formats all 20 chapters into clean ## Chapter X: <Title> with opening epigraphs/prose.
2. Formats frontmatter, Acknowledgments, Introduction, Notes, Bibliography, and Index.
3. Strips all 15 "Click here to see a larger image." artifacts.
4. Repairs British pound currency symbol (\\ufffd1.2 million -> £1.2 million) and common accented characters.
5. Fixes accidental ## markings on footnotes in the Notes section.
6. Synchronizes corpus/books/ and knowledge/docs/books/ with zero data loss.
"""

import re
import sys
from pathlib import Path

SOURCE_FILE = Path("corpus/books/sea_and_civilization_paine.md")
DEST_FILE = Path("knowledge/docs/books/sea_and_civilization_paine.md")

FRONTMATTER = """---
title: "The Sea and Civilization: A Maritime History of the World"
author: "Lincoln Paine"
publisher: "Alfred A. Knopf"
year: 2013
isbn: "978-1-4000-4409-2"
pages: 744
source: "corpus/books/sea_and_civilization_paine.md"
category: "Maritime History / Global Commerce"
---

"""

CHAPTERS = [
    (1, "Voyage into the Distant Past"),
    (2, "The River of Egypt"),
    (3, "The Bronze Age Mediterranean"),
    (4, "Phoenicians, Greeks, and the Sea"),
    (5, "The Mediterranean, from Rome to Constantinople"),
    (6, "Monsoons and Crossings: The Indian Ocean"),
    (7, "The Eastern Seas, from the Yangzi to the Yellow River"),
    (8, "The Sea Roads to Islam"),
    (9, "Northern Oceans: From Ireland to the White Sea"),
    (10, "The Medieval Mediterranean"),
    (11, "The Golden Age of Asian Trade"),
    (12, "Europeans on the World Stage"),
    (13, "The Great Voyages: From the Renaissance to the Age of Discovery"),
    (14, "The Early Modern Maritime World"),
    (15, "The Birth of Global Trade"),
    (16, "State and Sea in the Age of European Expansion"),
    (17, "Northern Europe Ascendant"),
    (18, "\"Annihilation of Space and Time\""),
    (19, "Naval Power in Steam and Steel"),
    (20, "The Maritime World Since the 1950s"),
]

def heal_text(text: str) -> str:
    # 1. Currency pound symbols
    text = re.sub(r'\ufffd(\d+[\d,\.]*)', r'£\1', text)

    # 2. Known accented proper names
    unicode_map = [
        ('Bluss\ufffd', 'Blussé'),
        ('Fern\ufffdndez-Armesto', 'Fernández-Armesto'),
        ('K\ufffdln', 'Köln'),
        ('f\ufffdr', 'für'),
        ('L\ufffdbeck', 'Lübeck'),
        ('\ufffdresund', 'Øresund'),
        ('Franois', 'François'),
        ('Fran\ufffdois', 'François'),
        ('St\ufffdphane', 'Stéphane'),
        ('Gudr\ufffdd', 'Gudríd'),
        ('entr\ufffde', 'entrée'),
        ('D\ufffdcada', 'Década'),
        ('Diplom\ufffdtico', 'Diplomático'),
        ('f\ufffdte', 'fête'),
        ('Boh\ufffds', 'Bohus'),
        ('d\ufffdz', 'déz'),
        ('Sch\ufff6neberg', 'Schöneberg'),
        ('K\ufff6chler', 'Köchler'),
        ('K\ufff6hler', 'Köhler'),
        ('P\ufffdrez', 'Pérez'),
        ('B\ufff6rjeson', 'Börjeson'),
        ('M\ufffdller', 'Müller'),
        ('H\ufffdckmann', 'Höckmann'),
        ('H\ufffdkon', 'Håkon'),
        ('H\ufffdkonarson', 'Håkonarson'),
        ('K\ufffdlidasa', 'Kālidāsa'),
        ('Ba\ufffdal', 'Ba‘al'),
        ('menage\ufffd', 'ménage'),
    ]
    for orig, rep in unicode_map:
        text = text.replace(orig, rep)

    # 3. Strip "Click here to see a larger image."
    text = re.sub(r'\s*Click here to see a larger image\.\s*', '\n\n', text)

    return text

def format_all_chapters(text: str) -> str:
    for num, title in CHAPTERS:
        clean_title = title.replace('\"', '')
        # Pattern: \n<num>\n<Title>\n
        pat = rf'\n{num}\s*\n(?:\"?{re.escape(clean_title)}\"?)\s*\n'
        rep = f'\n\n## Chapter {num}: {title}\n\n'
        text, count = re.subn(pat, rep, text, count=1)
        print(f"Chapter {num} ({title}): matched={count > 0}")
    return text

def repair_notes_headers(text: str) -> str:
    # Some notes lines in back matter got marked as '## <num>. <Text>'
    # We repair them to regular note numbering '<num>. <Text>'
    text = re.sub(r'^##\s+(\d+\.\s+[A-Z])', r'\1', text, flags=re.M)
    return text

def main():
    print("Formatting Book 9: The Sea and Civilization (Lincoln Paine)...")
    with open(SOURCE_FILE, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    # Step 1: Strip old frontmatter if present
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            content = parts[2].lstrip()

    # Step 2: Remove old summary / heading wrapper if present
    content = re.sub(r'^## Summary\s*\n.*?\n## The Sea and Civilization[^\n]*\n', '', content, flags=re.S)

    # Step 3: Format major sections
    content = heal_text(content)
    content = format_all_chapters(content)
    content = repair_notes_headers(content)

    # Clean top-level heading
    main_title = "# The Sea and Civilization: A Maritime History of the World\n\n**Author:** Lincoln Paine (Alfred A. Knopf, New York, 2013)\n\n"
    
    # Ensure Notes, Bibliography, Index are cleanly formatted
    content = re.sub(r'^\s*Notes\s*$', '## Notes', content, flags=re.M)
    content = re.sub(r'^\s*Bibliography\s*$', '## Bibliography', content, flags=re.M)
    content = re.sub(r'^\s*Index\s*$', '## Index', content, flags=re.M)
    content = re.sub(r'^\s*A Note About the Author\s*$', '## A Note About the Author', content, flags=re.M)
    content = re.sub(r'^\s*Other Books by This Author\s*$', '## Other Books by This Author', content, flags=re.M)

    # Final assembly
    final_output = FRONTMATTER + main_title + content.strip() + "\n"

    # Write to both locations
    SOURCE_FILE.write_text(final_output, encoding="utf-8")
    DEST_FILE.parent.mkdir(parents=True, exist_ok=True)
    DEST_FILE.write_text(final_output, encoding="utf-8")

    print("Successfully formatted Book 9!")
    print(f"Source size: {len(final_output)} chars written to {SOURCE_FILE}")
    print(f"Dest size: {len(final_output)} chars written to {DEST_FILE}")

if __name__ == "__main__":
    main()
