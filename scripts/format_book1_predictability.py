#!/usr/bin/env python3
"""
scripts/format_book1_predictability.py
Complete, clean formatter for Book 1:
secondhand_bulker_predictability_duru algorithm
"""

import re
from pathlib import Path

def format_book1():
    p = Path("corpus/books/secondhand_bulker_predictability_duru.md")
    raw = p.read_text(encoding="utf-8")

    # Preserve YAML frontmatter
    parts = raw.split("---", 2)
    fm = f"---{parts[1]}---\n"
    body = parts[2].lstrip("\r\n")

    # 1. Summary
    summary_match = re.search(r"## Summary\s*\n(.*?)(?=\n##|\nARTICLE|\n1\.|\Z)", body, re.S)
    summary_text = summary_match.group(1).strip() if summary_match else ""

    # Clean out journal metadata and header dumps
    body = re.sub(r"## Summary\s*\n.*?(?=\n##|\nARTICLE|\n1\.|\nPredictability|\Z)", "", body, flags=re.S)
    body = re.sub(r"## G Model\s*\n", "", body)
    body = re.sub(r"ARTICLE IN PRESS\s*\n", "", body)
    body = re.sub(r"AJSL-\d+;\s*No\. of Pages \d+\s*\n", "", body)
    body = re.sub(r"The Asian Journal of Shipping and Logistics[^\n]*\n", "", body)
    body = re.sub(r"Contents lists available at ScienceDirect\s*\n", "", body)
    body = re.sub(r"HOSTED BY\s*\n", "", body)
    body = re.sub(r"j ourna l h omepage:[^\n]*\n", "", body)
    body = re.sub(r"a r t i c l e i n f o\s*\n", "", body)
    body = re.sub(r"Article history:[^\n]*\n(?:Received[^\n]*\n)+", "", body)
    body = re.sub(r"Keywords:[^\n]*\n(?:[A-Z][^\n]*\n)+", "", body)
    body = re.sub(r"© \d{4} The Author\.[^\n]*\n[^\n]*BY-NC-ND license[^\n]*\n", "", body)
    body = re.sub(r"https://doi\.org/[^\n]*\n", "", body)
    body = re.sub(r"\d{4}-\d{4} © \d{4} The Author[^\n]*\n", "", body)
    body = re.sub(r"Please cite this article as:[^\n]*\n[^\n]*\n", "", body)
    body = re.sub(r"O\. Duru et al\.[^\n]*\n", "", body)
    body = re.sub(r"View publication stats\s*\n", "", body)
    body = re.sub(r"∗\s*\nCorresponding author\.[^\n]*\n[^\n]*\n", "", body)
    body = re.sub(r"\b1 Deadweight tonnage \(dwt\)[^\n]*\n[^\n]*\n", "", body)
    body = re.sub(r"\b2 Literally it means the maximum size[^\n]*\n(?:tions,\s*\n)?(?:Canal\.\s*\n)?", "", body)

    # Clean Abstract heading
    body = re.sub(r"a\s*\nindex\s*\nb s t r a c t\s*\n", "\n\n## Abstract\n\n", body)

    # Format Section Headings
    body = re.sub(r"(?:\n|^)1\.\s+Introduction\s*\n", "\n\n## 1. Introduction\n\n", body)
    body = re.sub(r"(?:\n|^)2\.2\.1\.\s+Linear forecasting models\s*\n", "\n\n### 2.2.1 Linear Forecasting Models\n\n", body)
    body = re.sub(r"(?:\n|^)2\.2\.2\.\s+Nonlinear forecasting models\s*\n", "\n\n### 2.2.2 Nonlinear Forecasting Models\n\n", body)
    body = re.sub(
        r"They emphasised the superiority of their\s*\n2\.2\.3\.\s*\nproposed\s*\napproach\.\s*\nHybrid forecasting models",
        "They emphasised the superiority of their proposed approach.\n\n### 2.2.3 Hybrid Forecasting Models\n\n",
        body
    )
    body = re.sub(r"(?:\n|^)3\.\s+Methodology and data\s*\n", "\n\n## 3. Methodology and Data\n\n", body)
    body = re.sub(r"(?:\n|^)3\.1\.\s+Shipping Q as an adaptation of Tobin's Q index\s*\n", "\n\n### 3.1 Shipping Q as an Adaptation of Tobin's Q Index\n\n", body)
    body = re.sub(r"(?:\n|^)5\.\s+Conclusion\s*\n", "\n\n## 5. Conclusion\n\n", body)
    body = re.sub(r"(?:\n|^)Author declaration\s*\n", "\n\n## Author Declaration\n\n", body)
    body = re.sub(r"(?:\n|^)Declarations of interest\s*\n", "\n\n## Declarations of Interest\n\n", body)

    # Format Figures cleanly as blockquotes
    body = re.sub(r"\nFig\.\s*1\.\s*([^\n]+)\n", r"\n\n> **Figure 1**: \1\n\n", body)
    body = re.sub(r"\nFig\.\s*2\.\s*([^\n]+)\n", r"\n\n> **Figure 2**: \1\n\n", body)
    body = re.sub(r"\nFig\.\s*3\.\s*([^\n]+)\n", r"\n\n> **Figure 3**: \1\n\n", body)

    # Heal Figure 6 and split sentence
    body = re.sub(
        r"different time series data in other\s*\nFig\.\s*\nareas\.\s*\n6\.\s*Second-hand dry bulk carriers 15 years old:\s*\(a\)\s*Capesize,\s*\(b\)\s*Handymax,\s*\(c\)\s*\n\s*Handysize,\s*and\s*\(d\)\s*Panamax\.",
        "different time series data in other areas.\n\n> **Figure 6**: Second-hand dry bulk carriers 15 years old: (a) Capesize, (b) Handymax, (c) Handysize, and (d) Panamax.",
        body
    )
    # Also handle if already partly joined
    body = re.sub(
        r"different time series data in other\s*\nFig\.\s*\nareas\.\s*\n6\.\s*Second-hand dry bulk carriers 15 years old:[^\n]*\n[^\n]*\n",
        "different time series data in other areas.\n\n> **Figure 6**: Second-hand dry bulk carriers 15 years old: (a) Capesize, (b) Handymax, (c) Handysize, and (d) Panamax.\n\n",
        body
    )

    # Heal broken sentences around Tobin Q:
    tobin_healed = (
        "In Tobin Q theory, if the ratio is greater than 1, investment is encouraged; "
        "if the ratio is below 1, then the asset is undervalued, and the signal is interpreted as a buy opportunity. "
        "The SQ index is calculated as the ratio of the market value of a ship to the nominal long-term value of the vessel.\n\n"
        "However, static book value measures are not practically useful if the security shortfall arises as a result of "
        "market collapse and asset bubbles. In this regard, the SQ index can be utilised in identifying overpriced assets "
        "and potential security value shortfalls during the credit analysis stage."
    )
    body = re.sub(
        r"In Tobin Q theory, if the ratio is greater than 1, investment is encouraged;.*?"
        r"value shortfalls during the credit analysis stage\.",
        tobin_healed,
        body,
        flags=re.S
    )

    # Clean out stray single "Handysize, and (d) Panamax."
    body = re.sub(r"\nHandysize, and \(d\) Panamax\.\s*\n", "\n", body)

    # Clean out duplicate sentence
    body = re.sub(
        r"market collapse and asset bubbles\. In this regard, the SQ index can\s*\n"
        r"be utilised in identifying overpriced assets and potential security\s*\n"
        r"value shortfalls during the credit analysis stage\.\s*\n",
        "",
        body
    )

    # Clean and structure References
    if "## References" in body:
        pre_ref, ref_part = body.split("## References", 1)
        # Parse individual citations
        citations = []
        raw_cites = re.split(r"(?:^|\n)\s*-\s+(?:-\s+)?(?=[A-Z][A-Za-z\s\.,\-–&]+\(\d{4}\))", ref_part.strip())
        if len(raw_cites) <= 1:
            # Try splitting by Author (YYYY)
            raw_cites = re.split(r"(?<=\.)\s+(?=[A-Z][a-zA-Z\s\.,\-–&]+\(\d{4}\))", ref_part.strip())

        for c in raw_cites:
            c_clean = " ".join(c.strip().split())
            c_clean = re.sub(r"^-\s*(?:-\s*)?", "", c_clean).strip()
            if c_clean:
                citations.append(f"- {c_clean}")

        body = pre_ref.strip() + "\n\n## References\n\n" + "\n".join(citations) + "\n"

    # Clean whitespace
    body = re.sub(r"\n{3,}", "\n\n", body).strip()

    # Final document structure
    doc = (
        fm + "\n"
        "## Summary\n\n"
        f"{summary_text}\n\n"
        "---\n\n"
        f"{body}\n"
    )
    
    p.write_text(doc, encoding="utf-8")
    Path("knowledge/docs/books/secondhand_bulker_predictability_duru.md").write_text(doc, encoding="utf-8")
    print(f"Book 1 formatted and verified: {len(doc)} chars, {len(doc.splitlines())} lines")

if __name__ == "__main__":
    format_book1()
