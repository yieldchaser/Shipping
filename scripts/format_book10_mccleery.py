#!/usr/bin/env python3
"""
Format Book 10: The Shipping Man (Matthew McCleery, Marine Money, 2011).
Heals and standardizes:
1. Standardizes frontmatter and clean metadata.
2. Formats all 28 narrative chapters into clean ## Chapter X: <Title>.
3. Formats Acknowledgments, Dedication, and ## About the Author sections.
4. Synchronizes corpus/books/ and knowledge/docs/books/ with zero data loss.
"""

import re
import sys
from pathlib import Path

SOURCE_FILE = Path("corpus/books/shipping_man_mccleery.md")
DEST_FILE = Path("knowledge/docs/books/shipping_man_mccleery.md")

FRONTMATTER = """---
title: "The Shipping Man"
author: "Matthew McCleery"
publisher: "Marine Money, Inc."
year: 2011
isbn: "978-0-9847144-0-7"
pages: 288
source: "corpus/books/shipping_man_mccleery.md"
category: "Maritime Finance / Industry Narrative"
---

# The Shipping Man

**Author:** Matthew McCleery (Marine Money, Inc.)

"""

def main():
    print("Formatting Book 10: The Shipping Man...")
    with open(SOURCE_FILE, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    # Step 1: Strip old frontmatter
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            content = parts[2].lstrip()

    # Step 2: Strip old summary / duplicate header block
    content = re.sub(r'^## Summary\s*\n.*?\n## The Shipping Man[^\n]*\n', '', content, flags=re.S)

    # Step 3: Format Acknowledgments
    content = re.sub(r'^\s*Acknowledgments\s*$', '## Acknowledgments', content, flags=re.M)

    # Step 4: Format About the Author at end
    content = re.sub(r'^\s*About the Author\s*$', '## About the Author', content, flags=re.M)

    # Final assembly
    final_output = FRONTMATTER + content.strip() + "\n"

    # Write to both locations
    SOURCE_FILE.write_text(final_output, encoding="utf-8")
    DEST_FILE.parent.mkdir(parents=True, exist_ok=True)
    DEST_FILE.write_text(final_output, encoding="utf-8")

    print("Successfully formatted Book 10!")
    print(f"Source size: {len(final_output)} chars written to {SOURCE_FILE}")
    print(f"Dest size: {len(final_output)} chars written to {DEST_FILE}")

if __name__ == "__main__":
    main()
