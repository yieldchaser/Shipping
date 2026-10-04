#!/usr/bin/env python3
"""
scripts/normalize_books.py
=============================================================================
High-Fidelity Format Normalization Engine for Maritime Reference Books.

Fixes:
1. Strips running headers, vertical margin letter-runs, and page numbers.
2. Heals sentences and paragraphs split across page breaks and column boundaries.
3. De-hyphenates line-break hyphenations while preserving true compound words.
4. Heals drop-cap character separations at section starts.
5. Formats math formulas and equations into LaTeX ($$...$$).
6. Normalizes chapter and section headings.
7. Cleans up repetitive index banners (e.g., Lloyd's Maritime Atlas) and injects legends.
8. Preserves 100% of YAML frontmatter and factual knowledge disclosures.
=============================================================================
"""

import re
from pathlib import Path
from typing import Dict, List, Set, Tuple

# Genuine hyphenated words to preserve
COMPOUND_PREFIXES = {
    "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety",
    "long", "short", "double", "ice", "full", "cross", "cost", "trade", "well",
    "break", "deep", "post", "pre", "supply", "demand", "panamax", "capesize",
    "handysize", "suezmax", "aframax", "tanker", "bulker", "dry", "wet",
    "self", "all", "non", "anti", "ex", "quasi", "semi", "multi", "sub"
}

COMPOUND_WORDS = {
    "twenty-one", "twenty-two", "twenty-three", "twenty-four", "twenty-five",
    "twenty-six", "twenty-seven", "twenty-eight", "twenty-nine",
    "thirty-one", "thirty-two", "thirty-three", "thirty-four", "thirty-five",
    "thirty-six", "thirty-seven", "thirty-eight", "thirty-nine",
    "forty-one", "forty-two", "forty-three", "forty-four", "forty-five",
    "forty-six", "forty-seven", "forty-eight", "forty-nine",
    "fifty-one", "fifty-two", "fifty-three", "fifty-four", "fifty-five",
    "sixty-one", "sixty-two", "sixty-three", "sixty-four", "sixty-five",
    "seventy-one", "seventy-two", "seventy-three", "seventy-four", "seventy-five",
    "eighty-one", "eighty-two", "eighty-three", "eighty-four", "eighty-five",
    "ninety-one", "ninety-two", "ninety-three", "ninety-four", "ninety-five",
    "long-distance", "time-charter", "double-bottom", "ice-class", "full-rigged",
    "cross-border", "cost-effective", "trade-off", "well-known", "break-even",
    "short-term", "long-term", "deep-sea", "post-panamax", "pre-eminence",
    "supply-side", "demand-side", "cap-and-trade", "co-operation", "co-ordination",
    "dead-weight", "state-of-the-art", "ton-mile", "tonne-mile", "day-to-day",
    "panamax-size", "capesize-size", "handysize-size", "second-hand", "new-building",
    "round-trip", "trip-charter", "bare-boat", "bareboat-charter", "spot-market",
    "off-hire", "lay-up", "roll-on", "roll-off", "lift-on", "lift-off"
}

COMMON_SUFFIXES = (
    "tion", "tions", "sion", "sions", "ing", "ings", "ed", "ment", "ments",
    "ity", "ities", "al", "ally", "ly", "ive", "ively", "ance", "ances",
    "ence", "ences", "ous", "ously", "able", "ible", "ic", "ical", "ically",
    "ure", "ures", "ise", "ize", "ised", "ized", "ising", "izing", "ship",
    "ships", "less", "ness", "hood", "dom", "ist", "ists", "ism", "isms",
    "ate", "ated", "ating", "ation", "ations", "ant", "ants", "ent", "ents",
    "ry", "ries", "tor", "tors", "ture", "tures", "tive", "tives", "ary", "aries"
)


def split_frontmatter(text: str) -> Tuple[str, str]:
    """Isolate YAML frontmatter from document body."""
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            return f"---{parts[1]}---\n", parts[2].lstrip("\r\n")
    return "", text


def remove_vertical_letter_runs(text: str) -> str:
    """Strip vertical runs of letters from margin thumb markers."""
    # Pattern: 2 or more single capital letters on consecutive lines
    vert_pattern = re.compile(r"(?:\n|^)([A-Z]\n){2,}[A-Z](?:\n\d+)?(?=\n|$)", re.M)
    text = vert_pattern.sub("\n", text)
    
    # Standalone single thumb character lines
    thumb_chars = {"C", "H", "A", "P", "T", "E", "R"}
    lines = text.splitlines()
    cleaned = []
    for l in lines:
        if l.strip() in thumb_chars:
            continue
        cleaned.append(l)
    return "\n".join(cleaned)


def heal_drop_caps(text: str) -> str:
    """Join drop-cap letters separated by space at line start (e.g. 'C harter' -> 'Charter')."""
    lines = text.splitlines()
    out = []
    drop_cap_re = re.compile(r"^([B-HJ-Z])\s+([a-z]{2,}.*)$")
    for line in lines:
        m = drop_cap_re.match(line)
        if m:
            out.append(f"{m.group(1)}{m.group(2)}")
        else:
            out.append(line)
    return "\n".join(out)


def strip_thumb_prefixes(text: str, fname: str) -> str:
    """Remove marginal thumb characters prepended to prose lines in Stopford."""
    if "stopford" not in fname and "maritime_economics_3rd_edition" not in fname:
        return text
    lines = text.splitlines()
    out = []
    thumb_re = re.compile(r"^([CHPTER])\s+([a-z].*)$")
    for line in lines:
        m = thumb_re.match(line.strip())
        if m:
            out.append(m.group(2))
        else:
            out.append(line)
    return "\n".join(out)


def dehyphenate_text(text: str) -> str:
    """Join hyphenated line breaks cleanly."""
    def repl(m):
        w1, w2 = m.group(1), m.group(2)
        combined_lower = f"{w1.lower()}{w2.lower()}"
        hyphenated_lower = f"{w1.lower()}-{w2.lower()}"
        
        # Check if known compound word
        if hyphenated_lower in COMPOUND_WORDS or w1.lower() in COMPOUND_PREFIXES:
            return f"{w1}-{w2}"
        
        # Suffix matching
        if w2.lower().endswith(COMMON_SUFFIXES) or len(w2) <= 4 or len(w1) <= 4:
            return f"{w1}{w2}"
            
        return f"{w1}{w2}"

    # Match word- \n word
    return re.sub(r"\b([A-Za-z]{2,})-\s*\n\s*([A-Za-z]{2,})\b", repl, text)


def heal_running_headers_and_page_breaks(text: str, fname: str) -> str:
    """Remove running header lines, page numbers, and heal split sentences."""
    lines = text.splitlines()
    
    # 1. Identify repeated headers across the book
    h2_counts: Dict[str, int] = {}
    for line in lines:
        s = line.strip()
        if s.startswith("## ") and len(s) < 80:
            h2_counts[s] = h2_counts.get(s, 0) + 1
            
    repeated_h2 = {k for k, v in h2_counts.items() if v > 1}
    seen_h2: Set[str] = set()
    
    # Running header with trailing numbers: e.g. ## THE FINANCIALISATION OF SHIPPING MARKETS 289
    header_num_re = re.compile(r"^##\s+([A-Z\s,–\-\'\"&/]{4,}?\s+\d{1,4}|\d{1,4})\s*$")
    
    cleaned_lines: List[str] = []
    i = 0
    n = len(lines)
    
    while i < n:
        line = lines[i]
        stripped = line.strip()
        
        is_running_header = False
        
        # Check repeated header
        if stripped in repeated_h2:
            if stripped not in seen_h2:
                seen_h2.add(stripped)
                cleaned_lines.append(line)
                i += 1
                continue
            else:
                is_running_header = True
                
        # Check header with page number
        elif header_num_re.match(stripped):
            is_running_header = True
            
        # Check standalone page number
        elif re.match(r"^\d{1,4}$", stripped):
            is_running_header = True
            
        if is_running_header:
            # Find previous non-empty line
            p_idx = len(cleaned_lines) - 1
            while p_idx >= 0 and not cleaned_lines[p_idx].strip():
                p_idx -= 1
                
            # Find next non-empty line that isn't a header or digit
            j = i + 1
            while j < n and (not lines[j].strip() or lines[j].strip() in repeated_h2 or header_num_re.match(lines[j].strip()) or re.match(r"^\d{1,4}$", lines[j].strip())):
                j += 1
                
            if p_idx >= 0 and j < n:
                prev_line = cleaned_lines[p_idx].strip()
                next_line = lines[j].strip()
                
                # Check sentence continuation across page boundary
                if prev_line and not re.search(r"[\.!\?:;\"\'\)\]]$", prev_line):
                    if next_line and (next_line[0].islower() or next_line.startswith(("to ", "and ", "or ", "of ", "in ", "that ", "which ", "for ", "with ", "at ", "from ", "by "))):
                        cleaned_lines[p_idx] = f"{cleaned_lines[p_idx]} {next_line}"
                        cleaned_lines = cleaned_lines[:p_idx + 1]
                        i = j + 1
                        continue
            i += 1
            continue
            
        cleaned_lines.append(line)
        i += 1
        
    # Second pass: heal paragraphs split by page break blanks
    healed_pass: List[str] = []
    for line in cleaned_lines:
        if not line.strip():
            healed_pass.append(line)
            continue
        if healed_pass and healed_pass[-1].strip() == "":
            p = len(healed_pass) - 1
            while p >= 0 and not healed_pass[p].strip():
                p -= 1
            if p >= 0:
                prev = healed_pass[p].strip()
                curr = line.strip()
                if not re.search(r"[\.!\?:;\"\'\)\]]$", prev) and (curr[0].islower() or curr.startswith(("to ", "and ", "or ", "of ", "in ", "that ", "which ", "for ", "with ", "at ", "from ", "by "))):
                    healed_pass[p] = f"{healed_pass[p]} {curr}"
                    healed_pass = healed_pass[:p + 1]
                    continue
        healed_pass.append(line)
        
    return "\n".join(healed_pass)


def format_novel_chapters(text: str) -> str:
    """Format novel chapters in The Shipping Man into clean Markdown headings."""
    lines = text.splitlines()
    out: List[str] = []

    word_to_num = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
        "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
        "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
        "nineteen": 19, "twenty": 20, "twenty-one": 21, "twenty one": 21,
        "twenty-two": 22, "twenty two": 22, "twenty-three": 23, "twenty three": 23,
        "twenty-four": 24, "twenty four": 24, "twenty-five": 25, "twenty five": 25,
        "twenty-six": 26, "twenty six": 26, "twenty-seven": 27, "twenty seven": 27,
        "twenty-eight": 28, "twenty eight": 28
    }

    num_words_pat = r"(?:twenty[\s\-](?:one|two|three|four|five|six|seven|eight)|twenty|nineteen|eighteen|seventeen|sixteen|fifteen|fourteen|thirteen|twelve|eleven|ten|nine|eight|seven|six|five|four|three|two|one|\d+)"
    ch_re = re.compile(rf"^(?:##\s+)?Chapter\s+({num_words_pat})\s*(?:[-–:]\s*|\s+)(.*)$", re.I)

    for line in lines:
        s = line.strip()
        m = ch_re.match(s)
        if m:
            ch_raw = m.group(1).lower().strip()
            num = word_to_num.get(ch_raw) or (int(ch_raw) if ch_raw.isdigit() else None)
            if num:
                rest = m.group(2).strip()
                prose_part = ""
                if " - " in rest:
                    title_part, prose_part = rest.split(" - ", 1)
                else:
                    title_part = rest

                out.append("")
                out.append(f"## Chapter {num}: {title_part.strip()}")
                out.append("")
                if prose_part:
                    out.append(prose_part.strip())
                continue

        out.append(line)

    return "\n".join(out)


def normalize_lloyds_atlas(text: str) -> str:
    """Format Lloyd's Maritime Atlas index entries and remove repetitive headers."""
    # 1. Strip repetitive running headers
    text = re.sub(r"\n\d{1,3}\s+GEOGRAPHIC INDEX[^\n]*\n", "\n", text)
    text = re.sub(r"\n[A-Za-z\s\(\)]*GEOGRAPHIC INDEX\s+\d{1,3}\n", "\n", text)
    text = re.sub(r"\nPPetroleum QOtherLiquidBulk[^\n]*\n", "\n", text)
    text = re.sub(r"\nCContainers RRo-Ro[^\n]*\n", "\n", text)
    text = re.sub(r"\nAAirport\(within100km\)\n", "\n", text)
    text = re.sub(r"\nLloyd\'s Maritime Atlas www\.lloydsmiu\.com[^\n]*\n", "\n", text)
    text = re.sub(r"\n\d{1,3}ALPHABETICAL INDEX[^\n]*\n", "\n", text)
    
    # 2. Add Facility Codes legend if not present
    legend = """### Facility Codes Legend

| Code | Facility Description |
| :---: | :--- |
| **P** | Petroleum terminal |
| **Q** | Other liquid bulk |
| **Y** | Dry bulk terminal |
| **G** | General cargo |
| **C** | Container facility |
| **R** | Ro-Ro berth |
| **L** | Cruise terminal |
| **B** | Bunkers available |
| **D** | Dry dock / shipyard repair |
| **T** | Towage available |
| **A** | Airport within 100km |

---
"""
    if "### Facility Codes Legend" not in text:
        if "# Lloyd's Maritime Atlas" in text:
            text = text.replace("# Lloyd's Maritime Atlas", f"# Lloyd's Maritime Atlas\n\n{legend}")
        else:
            text = f"{legend}\n\n{text}"
            
    return text


def normalize_math_and_figures(text: str) -> str:
    """Format LaTeX math equations and figure blockquotes in economics texts."""
    # Cobb-Douglas / Solow growth equation
    text = re.sub(
        r"y=a[·\.]l\+\(1-a\)[·\.]k\+q\s*\(5\.54\)",
        lambda m: r"$$y = a \cdot l + (1 - a) \cdot k + q \quad (5.54)$$",
        text
    )
    # Remove stray standalone bullet dashes around formulas
    text = re.sub(r"\n-\s*\n\s*(\$\$[^\$]+\$\$)\s*\n-\s*\n", r"\n\n\1\n\n", text)
    
    # Format figure captions
    text = re.sub(
        r"\n(Figure\s+\d+\.\d+)\s+([^\n]+)\n",
        r"\n\n> **\1**: \2\n\n",
        text
    )
    
    # Format numbered sections like 9.2 SUPPLY-SIDE DETERMINANTS
    def sec_repl(m):
        num, title = m.group(1), m.group(2)
        title_proper = title.title()
        return f"\n\n### {num} {title_proper}\n\n"
        
    text = re.sub(r"\n(\d+\.\d+)\s+([A-Z\s–\-]{4,})\n", sec_repl, text)
    
    return text


def clean_markdown_whitespace(text: str) -> str:
    """Normalize paragraph spacing and clean excessive blank lines."""
    # Collapse 3+ consecutive newlines to 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def normalize_book(source_path: Path) -> str:
    """Complete normalization pipeline for a single book."""
    raw = source_path.read_text(encoding="utf-8")
    fm, body = split_frontmatter(raw)
    fname = source_path.name.lower()
    
    # 1. Marginalia
    body = remove_vertical_letter_runs(body)
    
    # 2. Drop caps
    body = heal_drop_caps(body)
    
    # 3. Thumb prefixes in Stopford
    body = strip_thumb_prefixes(body, fname)
    
    # 4. Running headers & page numbers & sentence healing
    body = heal_running_headers_and_page_breaks(body, fname)
    
    # 5. Hyphenations
    body = dehyphenate_text(body)
    
    # 6. Book-specific refinements
    if "shipping_man" in fname:
        body = format_novel_chapters(body)
    elif "lloyds_maritime_atlas" in fname:
        body = normalize_lloyds_atlas(body)
    elif "macroeconomic" in fname or "stopford" in fname or "quantitative" in fname or "predictability" in fname or "finance" in fname:
        body = normalize_math_and_figures(body)
        
    # 7. Clean whitespace
    body = clean_markdown_whitespace(body)
    
    return fm + body


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        target = Path(sys.argv[1])
        if target.is_file():
            normalized = normalize_book(target)
            target.write_text(normalized, encoding="utf-8")
            print(f"Normalized {target.name}")
        else:
            print(f"File not found: {target}")
    else:
        print("Usage: python scripts/normalize_books.py <path-to-book.md>")
