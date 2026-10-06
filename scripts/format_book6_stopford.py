#!/usr/bin/env python3
"""
scripts/format_book6_stopford.py
Complete, clean formatter for Book 6:
Maritime Economics (3rd Edition) by Martin Stopford
"""

import re
import sys
import subprocess
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

def title_case(s):
    words = s.split()
    lower_words = {"and", "or", "the", "a", "an", "of", "in", "to", "for", "on", "with", "at", "by", "from"}
    out = []
    for i, w in enumerate(words):
        wl = w.lower()
        if i == 0 or wl not in lower_words:
            out.append(w.capitalize() if w.isupper() else w)
        else:
            out.append(wl)
    return " ".join(out)

def format_book6():
    p = Path("corpus/books/maritime_economics_stopford_3e.md")
    try:
        raw = subprocess.check_output(
            ["git", "show", f"HEAD:{p.as_posix()}"],
            text=True,
            encoding="utf-8"
        )
    except Exception:
        raw = p.read_text(encoding="utf-8")

    # 1. Separate YAML frontmatter
    parts = raw.split("---", 2)
    fm = f"---{parts[1]}---\n"
    body = parts[2].lstrip("\r\n")

    # 2. Heal hyphenated words split by margin markers at line end
    # e.g., "commodi- P\nties" -> "commodities"
    body = re.sub(r"([a-z]+)-\s+[PTAR12]\s*\r?\n\s*([a-z]+)", r"\1\2", body)

    # 3. Heal trailing margin markers
    # e.g., "word, P\n" -> "word,\n"
    body = re.sub(r"([a-z0-9,\.;\)])\s+[PTAR12]\s*(?=\r?\n)", r"\1", body)

    # 4. Heal fused margin characters in specific words
    fused_words = [
        (r"\bPmade\b", "made"),
        (r"\bTtrade\b", "trade"),
        (r"\bTimportant\b", "important"),
        (r"\bPthe\b", "the"),
        (r"\bTranges\b", "ranges"),
        (r"\bPrevolutionary\b", "revolutionary"),
        (r"\bTarea\b", "area"),
        (r"\bfreTquency\b", "frequency"),
        (r"\bRimportant\b", "important"),
        (r"\bPby\b", "by"),
        (r"\bTby\b", "by"),
        (r"\bPto\b", "to"),
        (r"\bTto\b", "to"),
        (r"\bPand\b", "and"),
        (r"\bTand\b", "and"),
        (r"\bPof\b", "of"),
        (r"\bTof\b", "of"),
        (r"\bPfor\b", "for"),
        (r"\bTis\b", "is"),
        (r"\bPis\b", "is"),
        (r"\bTin\b", "in"),
        (r"\bPin\b", "in"),
        (r"\bPon\b", "on"),
        (r"\bTwas\b", "was"),
        (r"\bTthat\b", "that"),
        (r"\bTthis\b", "this"),
        (r"\bTan\b", "an"),
        (r"\bPhave\b", "have"),
        (r"\bTbe\b", "be"),
        (r"\bPbe\b", "be"),
        (r"\bTas\b", "as"),
        (r"\bTmade\b", "made"),
        (r"\bPwas\b", "was"),
        (r"\bPat\b", "at"),
        (r"\bTat\b", "at"),
        (r"\bThave\b", "have"),
        (r"\bTwere\b", "were"),
        (r"\bTon\b", "on"),
        (r"\bTare\b", "are"),
        (r"\bTregional\b", "regional"),
    ]
    for pat, repl in fused_words:
        body = re.sub(pat, repl, body)

    # 5. Excise running headers that broke mid-sentence (SAME LINE ONLY)
    def clean_mid_sentence_header(match):
        rem = match.group(1).strip()
        rem = re.sub(r"\s+[PTAR12]$", "", rem)
        return "\n" + rem + " "

    body = re.sub(
        r"\n##[ \t]+[A-Z0-9,\'\-]+(?:[ \t]+[A-Z0-9,\'\-]+)*(?:[ \t]+\d+\.\d+)?[ \t]+([a-z].*?)(?=\r?\n)",
        clean_mid_sentence_header,
        body
    )

    # 6. Clean running headers that appeared as standalone ## <TITLE> inside chapter body
    running_headers_to_remove = [
        r"\n##\s+THE ORGANIZATION OF THE SHIPPING MARKET\s*\n",
        r"\n##\s+THE FOUR SHIPPING MARKETS\s*\n(?=.*?\b5\.\d+\b)",
        r"\n##\s+FINANCING SHIPS AND SHIPPING COMPANIES\s*\n(?=.*?\b7\.\d+\b)",
        r"\n##\s+THE TRANSPORT OF SPECIALIZED CARGOES\s*\n(?=.*?\b12\.\d+\b)",
        r"\n##\s+INTRODUCTION TO SHIPPING MARKET MODELLING\s*\n",
        r"\n##\s+TONNAGE MEASUREMENT AND CONVERSION FACTORS\s*\n",
    ]
    for rh in running_headers_to_remove:
        body = re.sub(rh, "\n\n", body)

    # 7. Promote Parts and Chapters at their exact opening epigraph locations
    # Chapter 1
    body = re.sub(
        r"(?:##\s*SEA TRANSPORT AND THE GLOBAL ECONOMY\s*\n+|and the Global\s*\n+Economy\s*\n+)(?=Wonders are many on earth)",
        "\n\n---\n\n# Part 1: Introduction to Shipping\n\n---\n\n## Chapter 1: Sea Transport and the Global Economy\n\n",
        body
    )

    # Chapter 2
    body = re.sub(
        r"The Organization\s*\n+of the Shipping\s*\n+Market\s*\n+(?=Shipping is an exciting business)",
        "\n\n---\n\n## Chapter 2: The Economic Organization of the Shipping Market\n\n",
        body
    )

    # Chapter 3
    body = re.sub(
        r"(?:##\s*SHIPPING MARKET CYCLES\s*\n+|Shipping Market\s*\n+Cycles\s*\n+)(?=The four most expensive words)",
        "\n\n---\n\n# Part 2: Shipping Market Economics\n\n---\n\n## Chapter 3: Shipping Market Cycles\n\n",
        body
    )

    # Chapter 4
    body = re.sub(
        r"(?:##\s*SUPPLY,\s*DEMAND AND FREIGHT RATES\s*\n+)?(?=The price of freight\s*\n+Today is great)",
        "\n\n---\n\n## Chapter 4: Supply, Demand and Freight Rates\n\n",
        body,
        count=1
    )

    # Chapter 5
    body = re.sub(
        r"(?:The Four Shipping\s*\n+)?Markets\s*\n+(?=Economists understand by the term Market)",
        "\n\n---\n\n## Chapter 5: The Four Shipping Markets\n\n",
        body
    )

    # Chapter 6
    body = re.sub(
        r"(?:##\s*COSTS,\s*REVENUE AND CASHFLOW\s*\n+|Costs, Revenue\s*\n+and Cashflow\s*\n+)(?=Annual income twenty pounds)",
        "\n\n---\n\n# Part 3: Shipping Company Economics\n\n---\n\n## Chapter 6: Costs, Revenue and Cashflow\n\n",
        body
    )

    # Chapter 7
    body = re.sub(
        r"Financing Ships\s*\n+and Shipping\s*\n+Companies\s*\n+(?=For the ordinary investor)",
        "\n\n---\n\n## Chapter 7: Financing Ships and Shipping Companies\n\n",
        body
    )

    # Chapter 8
    body = re.sub(
        r"(?:Risk, Return and\s*\n+)?Shipping Company\s*\n+Economics\s*\n+(?=A wise man will make more opportunities)",
        "\n\n---\n\n## Chapter 8: Risk, Return and Shipping Company Economics\n\n",
        body
    )

    # Chapter 9
    body = re.sub(
        r"The Geography of\s*\n+Maritime Trade\s*\n+(?=Such therefore are the advantages of water carriage)",
        "\n\n---\n\n# Part 4: Seaborne Trade and Transport Systems\n\n---\n\n## Chapter 9: The Geography of Maritime Trade\n\n",
        body
    )

    # Chapter 10
    body = re.sub(
        r"The Principles of\s*\n+Maritime Trade\s*\n+(?=A kingdom, that has a large import)",
        "\n\n---\n\n## Chapter 10: The Theory of Maritime Trade\n\n",
        body
    )

    # Chapter 11
    body = re.sub(
        r"The Transport of\s*\n+Bulk Cargoes\s*\n+(?=God must have been a shipowner)",
        "\n\n---\n\n## Chapter 11: Bulk Cargo and the Economics of Bulk Shipping\n\n",
        body
    )

    # Chapter 12
    body = re.sub(
        r"(?:The Transport of\s*\n+)?Specialized\s*\n+Cargoes\s*\n+(?=It is difficult though not impossible)",
        "\n\n---\n\n## Chapter 12: The Transport of Specialized Cargoes\n\n",
        body
    )

    # Chapter 13
    body = re.sub(
        r"The Transport of\s*\n+General Cargo\s*\n+(?=The growing intricacy and variety)",
        "\n\n---\n\n## Chapter 13: The Economics of Liner Shipping\n\n",
        body
    )

    # Chapter 14
    body = re.sub(
        r"The Ships that\s*\n+Provide the\s*\n+Transport\s*\n+(?=Managers may believe that industry)",
        "\n\n---\n\n## Chapter 14: The Ships that Supply the Transport\n\n",
        body
    )

    # Chapter 15
    body = re.sub(
        r"(?=Till after many a week, at length,\s*\n+Wonderful for form and strength)",
        "\n\n---\n\n## Chapter 15: The Economics of Merchant Shipbuilding and Scrapping\n\n",
        body,
        count=1
    )

    # Chapter 16
    body = re.sub(
        r"The Regulation of\s*\n+the Maritime\s*\n+Industry\s*\n+(?=Whosoever commands the sea)",
        "\n\n---\n\n## Chapter 16: The Regulation of the Maritime Industry\n\n",
        body
    )

    # Chapter 17
    body = re.sub(
        r"(?:Maritime\s*\n+)?Forecasting and\s*\n+Market Research\s*\n+(?=The wretched boatmen do not know)",
        "\n\n---\n\n## Chapter 17: Maritime Forecasting and Market Research\n\n",
        body
    )

    # 8. Promote Sections to clean ### X.Y <Title>
    def format_section(match):
        title = match.group(1).strip()
        num = match.group(2).strip()
        title = re.sub(r",\s*", ", ", title)
        title = title_case(title)
        return f"\n\n### {num} {title}\n\n"

    # Pattern A: ## <TITLE> <NUM>
    body = re.sub(
        r"(?:\n|^)##\s+([A-Z0-9\s,\'\-]+?)\s+(\d+\.\d+)\s*(?=\r?\n)",
        format_section,
        body
    )

    # Pattern B: ## <NUM> <TITLE>
    body = re.sub(
        r"(?:\n|^)##\s+(\d+\.\d+)\s+([A-Z0-9\s,\'\-]+?)\s*(?=\r?\n)",
        lambda m: f"\n\n### {m.group(1)} {title_case(m.group(2).strip())}\n\n",
        body
    )

    # Pattern C: Standalone numbered section line: "^[PTEAR12]?\s*(\d+\.\d+)\s+([A-Z\s,\'\-]+?)$"
    body = re.sub(
        r"(?:\n|^)[PTEAR12]?\s*(\d+\.\d+)\s+([A-Z0-9\s,\'\-]{3,60})\s*(?=\r?\n)",
        lambda m: f"\n\n### {m.group(1)} {title_case(m.group(2).strip())}\n\n",
        body
    )

    # 9. Clean End Matter Headings & Margin letters
    body = re.sub(
        r"(?:\n|^)##\s*A\s*\n+An Introduction\s*\n+to Shipping Market\s*\n+Modelling",
        "\n\n---\n\n## Appendix A: An Introduction to Shipping Market Modelling\n\n",
        body
    )
    body = re.sub(
        r"(?:\n|^)##\s*B\s*\n+Tonnage\s*\n+Measurement and\s*\n+Conversion Factors",
        "\n\n---\n\n## Appendix B: Tonnage Measurement and Conversion Factors\n\n",
        body
    )
    body = re.sub(r"(?:\n|^)##\s*INDEX\s*\n", "\n\n---\n\n## Index\n\n", body)
    body = re.sub(r"(?:\n|^)##\s*NOTES\s*\n", "\n\n---\n\n## Notes\n\n", body)
    body = re.sub(r"(?:\n|^)##\s*REFERENCES AND SUGGESTED READING\s*\n", "\n\n---\n\n## References and Suggested Reading\n\n", body)

    # Clean margin text in Appendix A & B:
    body = re.sub(r"\nE\s+Building", "\nBuilding", body)
    body = re.sub(r"\nNcan specify", "\ncan specify", body)
    body = re.sub(r"\nD\s*\n(?=equations)", "", body)
    body = re.sub(r"\nI\s*\nX\s*\n", "\n", body)
    body = re.sub(r"\nEopen space", "\nopen space", body)
    body = re.sub(r"\nNenclosed spaces", "\nenclosed spaces", body)
    body = re.sub(r"\nD\s*\n(?=types)", "", body)
    body = re.sub(r"\nI\s*\nXdifferent", "\ndifferent", body)

    # 10. Clean excessive newlines
    body = re.sub(r"\n{3,}", "\n\n", body).strip()

    # Final document assembly
    doc = (
        fm + "\n"
        "# Maritime Economics (3rd Edition)\n\n"
        "**Author**: Martin Stopford  \n"
        "**Publisher**: Routledge (Taylor & Francis Group)  \n\n"
        f"{body}\n"
    )

    p.write_text(doc, encoding="utf-8")
    dest = Path("knowledge/docs/books/maritime_economics_stopford_3e.md")
    dest.write_text(doc, encoding="utf-8")
    print(f"Book 6 formatted successfully: {len(doc)} chars, {len(doc.splitlines())} lines written to {p} and {dest}")

if __name__ == "__main__":
    format_book6()
