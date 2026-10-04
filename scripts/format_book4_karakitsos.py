#!/usr/bin/env python3
"""
scripts/format_book4_karakitsos.py
Complete, clean formatter for Book 4:
Maritime Economics: A Macroeconomic Approach
by Elias Karakitsos and Lambros Varnavides
"""

import re
import subprocess
from pathlib import Path

def format_book4():
    p = Path("corpus/books/maritime_economics_a_macroeconomic_approach_elias_karakitsos_lambros_varnavides_auth_z_lib_org.md")
    try:
        raw = subprocess.check_output(
            ["git", "show", "HEAD:corpus/books/maritime_economics_a_macroeconomic_approach_elias_karakitsos_lambros_varnavides_auth_z_lib_org.md"],
            text=True,
            encoding="utf-8"
        )
    except Exception:
        raw = p.read_text(encoding="utf-8")

    # 1. Preserve YAML frontmatter
    parts = raw.split("---", 2)
    fm = f"---{parts[1]}---\n"
    body = parts[2].lstrip("\r\n")

    # Summary extraction
    summary_match = re.search(r"## Summary\s*\n(.*?)(?=\n##|\nLIST OF ABBREVIATIONS|\n1 THE BENEFITS|\Z)", body, re.S)
    summary_text = summary_match.group(1).strip() if summary_match else ""

    # Clean body: strip old summary block
    body = re.sub(r"## Summary\s*\n.*?(?=\nLIST OF ABBREVIATIONS|\n1 THE BENEFITS|\Z)", "", body, flags=re.S)

    # 2. Heal Ligature splits
    ligature_fixes = [
        (r"\bfl eet\b", "fleet"),
        (r"\bfl eets\b", "fleets"),
        (r"\bfi xed\b", "fixed"),
        (r"\bfi x\b", "fix"),
        (r"\binfl ation\b", "inflation"),
        (r"\binfl ationary\b", "inflationary"),
        (r"\bdefl ation\b", "deflation"),
        (r"\bfl uctuate\b", "fluctuate"),
        (r"\bfl uctuations\b", "fluctuations"),
        (r"\bfl uctuating\b", "fluctuating"),
        (r"\beffi cient\b", "efficient"),
        (r"\beffi ciency\b", "efficiency"),
        (r"\bineffi cient\b", "inefficient"),
        (r"\bprofi t\b", "profit"),
        (r"\bprofi ts\b", "profits"),
        (r"\bprofi table\b", "profitable"),
        (r"\bprofi tability\b", "profitability"),
        (r"\bdiff erent\b", "different"),
        (r"\bdiff erence\b", "difference"),
        (r"\bdiff erences\b", "differences"),
        (r"\bdefi ne\b", "define"),
        (r"\bdefi ned\b", "defined"),
        (r"\bdefi nition\b", "definition"),
        (r"\bdefi nitions\b", "definitions"),
        (r"\bsignifi cant\b", "significant"),
        (r"\bsignifi cance\b", "significance"),
        (r"\bspecifi c\b", "specific"),
        (r"\bspecifi cally\b", "specifically"),
        (r"\blett er\b", "letter"),
        (r"\blett ers\b", "letters"),
        (r"\bshipp ing\b", "shipping"),
        (r"\bcharter ing\b", "chartering"),
        (r"\boperat ing\b", "operating"),
        (r"\bbuild ing\b", "building"),
        (r"\bfl ow\b", "flow"),
        (r"\bfl ows\b", "flows"),
        (r"\bfi gure\b", "figure"),
        (r"\bfi gures\b", "figures"),
        (r"\bfi rst\b", "first"),
        (r"\bfi nal\b", "final"),
        (r"\bfi nance\b", "finance"),
        (r"\bfi nancial\b", "financial"),
    ]
    for pattern, replacement in ligature_fixes:
        body = re.sub(pattern, replacement, body, flags=re.I)

    # 3. Format List of Abbreviations
    body = re.sub(r"(?:\n|^)LIST OF ABBREVIATIONS\s*\n", "\n\n## List of Abbreviations\n\n", body)

    # 4. Format Chapters and Parts
    # Parts
    body = re.sub(r"(?:\n|^)THE MICROFOUNDATIONS OF\s*\nMARITIME ECONOMICS\s*\n", "\n\n# Part I: The Microfoundations of Maritime Economics\n\n", body)
    body = re.sub(r"(?:\n|^)THE MACROFOUNDATIONS OF\s*\nMARITIME ECONOMICS\s*\n", "\n\n# Part II: The Macrofoundations of Maritime Economics\n\n", body)

    # Chapters
    body = re.sub(
        r"(?:\n|^)1\s+THE BENEFITS OF A MACROECONOMIC APPROACH\s*\n",
        "\n\n## Chapter 1: The Benefits of a Macroeconomic Approach\n\n",
        body
    )
    body = re.sub(
        r"(?:\n|^)2\s+THE THEORETICAL\s*\nFOUNDATIONS OF\s*\nTHE FREIGHT MARKET\s*\n",
        "\n\n## Chapter 2: The Theoretical Foundations of the Freight Market\n\n",
        body
    )
    body = re.sub(
        r"(?:\n|^)THE SHIPYARD, SCRAP AND\s*\nSECONDHAND MARKETS\s*\n",
        "\n\n## Chapter 3: The Shipyard, Scrap and Secondhand Markets\n\n",
        body
    )
    body = re.sub(
        r"(?:\n|^)THE EFFICIENCY OF SHIPPING\s*\nMARKETS\s*\n",
        "\n\n## Chapter 4: The Efficiency of Shipping Markets\n\n",
        body
    )
    body = re.sub(
        r"(?:\n|^)BUSINESS CYCLES\s*\n(?=EXECUTIVE SUMMARY)",
        "\n\n## Chapter 5: Business Cycles\n\n",
        body
    )
    body = re.sub(
        r"(?:\n|^)THE THEORY OF SHIPPING\s*\nCYCLES\s*\n",
        "\n\n## Chapter 6: The Theory of Shipping Cycles\n\n",
        body
    )
    body = re.sub(
        r"(?:\n|^)SHIPPING AND SHIP FINANCE\s*\n",
        "\n\n## Chapter 7: Shipping and Ship Finance\n\n",
        body
    )
    body = re.sub(
        r"(?:\n|^)THE FINANCIALISATION\s*\nOF SHIPPING MARKETS\s*\n",
        "\n\n## Chapter 8: The Financialisation of Shipping Markets\n\n",
        body
    )
    body = re.sub(
        r"(?:\n|^)MACROECONOMICS AND SHIPPING CYCLES IN\s*\nPRACTICE\s*\n",
        "\n\n## Chapter 9: Macroeconomics and Shipping Cycles in Practice\n\n",
        body
    )
    body = re.sub(
        r"(?:\n|^)INVESTMENT STRATEGY\s*\n(?=EXECUTIVE SUMMARY)",
        "\n\n## Chapter 10: Investment Strategy\n\n",
        body
    )

    # 5. Executive Summaries
    body = re.sub(r"(?:\n|^)EXECUTIVE SUMMARY\s*\n", "\n\n### Executive Summary\n\n", body)

    # 6. Format Section Headings (healing fused chapter headings)
    # Convert numbered uppercase headings like "2 THE STRUCTURE OF THE BOOK" to clean markdown headings
    def clean_heading(match):
        num = match.group(1)
        title = match.group(2).strip()
        # Title case the title
        title_words = [w.capitalize() if w.lower() not in ("of", "the", "and", "in", "a", "an", "for", "to", "with", "on") else w.lower() for w in title.split()]
        if title_words:
            title_words[0] = title_words[0].capitalize()
        title_cased = " ".join(title_words)
        return f"\n\n### {num} {title_cased}\n\n"

    section_pat = r"(?:\n|^)([0-9]{1,2})\s+([A-Z\s]{4,45})\n(?=[A-Z0-9\$\(])"
    body = re.sub(section_pat, clean_heading, body)

    # 7. Strip running headers (e.g. repeated uppercase lines or page number headers)
    # "## \d+ ..." if any
    body = re.sub(r"\n\s*##\s+\d+\s+[A-Z\s]{4,40}\s*\n", "\n", body)
    body = re.sub(r"\n\s*##\s+THE FINANCIALISATION OF SHIPPING MARKETS \d+\s*\n", "\n", body)

    # Clean excessive whitespace
    body = re.sub(r"\n{3,}", "\n\n", body).strip()

    # Final document assembly
    doc = (
        fm + "\n"
        "# Maritime Economics: A Macroeconomic Approach\n\n"
        "**Authors**: Elias Karakitsos and Lambros Varnavides  \n"
        "**Publisher**: Palgrave Macmillan (2014)  \n\n"
        "## Summary\n\n"
        f"{summary_text}\n\n"
        "---\n\n"
        f"{body}\n"
    )

    p.write_text(doc, encoding="utf-8")
    dest = Path("knowledge/docs/books/maritime_economics_a_macroeconomic_approach_elias_karakitsos_lambros_varnavides_auth_z_lib_org.md")
    dest.write_text(doc, encoding="utf-8")
    print(f"Book 4 formatted successfully: {len(doc)} chars, {len(doc.splitlines())} lines written to {p} and {dest}")

if __name__ == "__main__":
    format_book4()
