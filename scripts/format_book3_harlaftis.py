#!/usr/bin/env python3
"""
scripts/format_book3_harlaftis.py
Complete, clean formatter for Book 3:
The World's Key Industry: History and Economics of International Shipping
Edited by Gelina Harlaftis, Stig Tenold, Jesús M. Valdaliso
"""

import re
import subprocess
from pathlib import Path

def format_book3():
    p = Path("corpus/books/the_world_s_key_industry_history_and_economics_of_international_shipping_g_harlaftis_s_tenold_j_valdaliso_z_lib_org.md")
    try:
        raw = subprocess.check_output(
            ["git", "show", "HEAD:corpus/books/the_world_s_key_industry_history_and_economics_of_international_shipping_g_harlaftis_s_tenold_j_valdaliso_z_lib_org.md"],
            text=True,
            encoding="utf-8"
        )
    except Exception:
        raw = p.read_text(encoding="utf-8")

    # 1. Preserve YAML frontmatter
    parts = raw.split("---", 2)
    fm = f"---{parts[1]}---\n"
    body = parts[2].lstrip("\r\n")

    # Summary
    summary_match = re.search(r"## Summary\s*\n(.*?)(?=\n##|\nNotes on|\Z)", body, re.S)
    summary_text = summary_match.group(1).strip() if summary_match else ""

    # Clean body: strip old summary and raw title dump up to Notes on the Contributors
    body = re.sub(r"## Summary\s*\n.*?(?=\nNotes on the Contributors|\Z)", "", body, flags=re.S)

    # 2. Format Frontmatter and Chapter Titles FIRST before stripping running headers
    body = re.sub(r"(?:\n|^)Notes on the Contributors\s*\n", "\n\n## Notes on the Contributors\n\n", body)

    # Chapter 1
    body = re.sub(
        r"(?:\n|^)Introduction\s*\n\s*Gelina Harlaftis, Stig Tenold and Jes[ú\ufffd]s M\. Valdaliso\s*\n",
        "\n\n## Chapter 1: Introduction\n\n**Authors**: Gelina Harlaftis, Stig Tenold, and Jesús M. Valdaliso  \n\n",
        body
    )

    # Chapter 2
    body = re.sub(
        r"(?:\n|^)Lewis R\. Fischer and the Progress\s*\nof Maritime Economic History\s*\n\s*David M\. Williams and Lars U\. Scholl\s*\n",
        "\n\n## Chapter 2: Lewis R. Fischer and the Progress of Maritime Economic History\n\n**Authors**: David M. Williams and Lars U. Scholl  \n\n",
        body
    )

    # Chapter 3
    body = re.sub(
        r"(?:\n|^)Shipping and Staple Economies\s*\nin the Periphery\s*\n\s*C\. Knick Harley\s*\n",
        "\n\n## Chapter 3: Shipping and Staple Economies in the Periphery\n\n**Author**: C. Knick Harley  \n\n",
        body
    )

    # Chapter 4
    body = re.sub(
        r"(?:\n|^)An Appraisal of the Progress\s*\nof the Steamship in the\s*\nNineteenth Century\s*\n\s*David M\. Williams and John Armstrong\s*\n",
        "\n\n## Chapter 4: An Appraisal of the Progress of the Steamship in the Nineteenth Century\n\n**Authors**: David M. Williams and John Armstrong  \n\n",
        body
    )

    # Chapter 5
    body = re.sub(
        r"(?:\n|^)The Advantages of Water\s*\nCarriage: Scale Economies\s*\nand Shipping Technology,\s*\nc\.\s*1870-2000\s*\n\s*Yrj[ö\ufffd] Kaukiainen\s*\n",
        "\n\n## Chapter 5: The Advantages of Water Carriage: Scale Economies and Shipping Technology, c. 1870-2000\n\n**Author**: Yrjö Kaukiainen  \n\n",
        body
    )

    # Chapter 6
    body = re.sub(
        r"(?:\n|^)Building the Networks of Trade:\s*\nPerspectives on Twentieth-Century\s*\nMaritime History\s*\n\s*Espen Ekberg, Even Lange and Eivind Merok\s*\n",
        "\n\n## Chapter 6: Building the Networks of Trade: Perspectives on Twentieth-Century Maritime History\n\n**Authors**: Espen Ekberg, Even Lange, and Eivind Merok  \n\n",
        body
    )

    # Chapter 7
    body = re.sub(
        r"(?:\n|^)The Development of Commercial\s*\nInfrastructure for World Shipping\s*\n\s*Gordon Boyce\s*\n",
        "\n\n## Chapter 7: The Development of Commercial Infrastructure for World Shipping\n\n**Author**: Gordon Boyce  \n\n",
        body
    )

    # Chapter 8
    body = re.sub(
        r"(?:\n|^)Government and the British\s*\nShipping Industry in the Later\s*\nTwentieth Century\s*\n\s*Sarah Palmer\s*\n",
        "\n\n## Chapter 8: Government and the British Shipping Industry in the Later Twentieth Century\n\n**Author**: Sarah Palmer  \n\n",
        body
    )

    # Chapter 9
    body = re.sub(
        r"(?:\n|^)Why They are Tall and We are\s*\nSmall! Competition between\s*\nAntwerp and Rotterdam in the\s*\nTwentieth Century\s*\n\s*Stephan Vanfraechem\s*\n",
        "\n\n## Chapter 9: Why They are Tall and We are Small! Competition between Antwerp and Rotterdam in the Twentieth Century\n\n**Author**: Stephan Vanfraechem  \n\n",
        body
    )

    # Chapter 10
    body = re.sub(
        r"(?:\n|^)Institutional Path Dependence\s*\nin Port Regulation: A Comparison\s*\nof New Zealand and Australia\s*\n\s*James Reveley and Malcolm Tull\s*\n",
        "\n\n## Chapter 10: Institutional Path Dependence in Port Regulation: A Comparison of New Zealand and Australia\n\n**Authors**: James Reveley and Malcolm Tull  \n\n",
        body
    )

    # Chapter 11
    body = re.sub(
        r"(DEC2010_v2\.pdf\.\s*Accessed 14 July 2011\.\s*\n+)(?:Adolf K\. Y\. Ng and Ka-chai Tam 181\s*\n+)?(?=\(referred to as the)",
        r"\1\n\n## Chapter 11: China's Seaport Development (1978-2002)\n\n**Authors**: Adolf K. Y. Ng and Ka-chai Tam  \n\n",
        body
    )

    # Chapter 12
    body = re.sub(
        r"(?:\n|^)Private Companies, Culture and\s*\nPlace in the Development of\s*\nHull's Maritime Business Sector,\s*\nc\.1860-1914\s*\n\s*Michaela G\. Barnard and David J\. Starkey\s*\n",
        "\n\n## Chapter 12: Private Companies, Culture and Place in the Development of Hull's Maritime Business Sector, c. 1860-1914\n\n**Authors**: Michaela G. Barnard and David J. Starkey  \n\n",
        body
    )

    # Chapter 13
    body = re.sub(
        r"(?:\n|^)Risks and Rewards: The Business\s*\nof Norwegian Shipping\s*\n\s*Stig Tenold\s*\n",
        "\n\n## Chapter 13: Risks and Rewards: The Business of Norwegian Shipping\n\n**Author**: Stig Tenold  \n\n",
        body
    )

    # Chapter 14
    body = re.sub(
        r"(?:\n|^)Business Groups and\s*\nEntrepreneurial Families in\s*\nSouthern Europe: Comparing\s*\nGreek and Spanish Shipowners\s*\nin the Nineteenth and\s*\nTwentieth Centuries1?\s*\n\s*Gelina Harlaftis and Jes[ú\ufffd]s M\. Valdaliso\s*\n",
        "\n\n## Chapter 14: Business Groups and Entrepreneurial Families in Southern Europe: Comparing Greek and Spanish Shipowners in the 19th and 20th Centuries\n\n**Authors**: Gelina Harlaftis and Jesús M. Valdaliso  \n\n",
        body
    )

    # 3. Excise Roman numeral running headers in frontmatter
    body = re.sub(r"\n\s*(?:[xvi]+\s+)+Notes on the Contributors\s*\n", "\n", body)
    body = re.sub(r"\n\s*Notes on the Contributors\s+[xvi]+\s*\n", "\n", body)

    # 4. Excise all running headers across chapters
    # Author running headers on odd pages
    authors = [
        r"David M\. Williams and Lars U\. Scholl",
        r"David M\. Williams and John Armstrong",
        r"C\. Knick Harley",
        r"Yrj[ö\ufffd] Kaukiainen",
        r"Espen Ekberg, Even Lange and Eivind Merok",
        r"Gordon Boyce",
        r"Sarah Palmer",
        r"Stephan Vanfraechem",
        r"James Reveley and Malcolm Tull",
        r"Adolf K\. Y\. Ng and Ka-chai Tam",
        r"Adolf K\.Y\. Ng and Ka-chai Tam",
        r"Michaela G\. Barnard and David J\. Starkey",
        r"Stig Tenold",
        r"Gelina Harlaftis and Jes[ú\ufffd]s (?:M\. )?Valdaliso",
        r"Gelina Harlaftis, Stig Tenold and Jes[ú\ufffd]s M\. Valdaliso",
        r"Notes on the Contributors",
    ]
    odd_pattern = r"(?:^|\n)\s*(?:##\s+)?(?:" + "|".join(authors) + r")\s+\d{1,3}\s*(?:\n|$)"
    body = re.sub(odd_pattern, "\n", body)

    # Title running headers on even pages
    titles = [
        r"Introduction",
        r"Lewis R\. Fischer and the Progress of Maritime Economic History",
        r"Shipping and Staple Economies in the Periphery",
        r"The Progress of the Steamship",
        r"The Advantages of Water Carriage",
        r"Building the Networks of Trade",
        r"The Development of Commercial Infrastructure for World Shipping",
        r"Government and British Shipping in the Later Twentieth Century",
        r"The Evolution of Antwerp and Rotterdam",
        r"Institutional Path Dependence in Port Regulation",
        r"China's Seaport Development",
        r"Private Companies, Culture and Place in Hull's Maritime Business Sector",
        r"Risks and Rewards: The Business of Norwegian Shipping",
        r"Business Groups and Entrepreneurial Families in Southern Europe",
    ]
    even_pattern = r"(?:^|\n)\s*(?:##\s+)?\d{1,3}\s+(?:" + "|".join(titles) + r")\s*(?:\n|$)"
    body = re.sub(even_pattern, "\n", body)

    # Clean any remaining "## \d+ Introduction" or "## Author \d+"
    body = re.sub(r"\n\s*##\s+\d+\s+Introduction\s*\n", "\n", body)
    body = re.sub(r"\n\s*##\s+[A-Z][a-zA-Z\s\.,\-–&]+\s+\d+\s*\n", "\n", body)

    # 5. Heal severed sentences across running headers
    # Chapter 14 attribution split by 8 Introduction:
    body = re.sub(
        r"byGelina Harlaftis\s*\n\s*and Jesús Valdaliso",
        "by Gelina Harlaftis and Jesús Valdaliso",
        body
    )
    # David M. Williams and Lars U. Scholl 13 split:
    body = re.sub(
        r"one individual, Professor\s*\n\s*Lewis R\. Fischer",
        "one individual, Professor Lewis R. Fischer",
        body
    )
    # David M. Williams and John Armstrong 57 split:
    body = re.sub(
        r"transition being\s*\n\s*a gradual process",
        "transition being a gradual process",
        body
    )
    # General split healing: word ending with hyphen or space across boundary
    body = re.sub(r"(\b[a-z]+)-\s*\n\s*([a-z]+\b)", r"\1\2", body)

    # 6. Repair accents cleanly
    body = body.replace("Jess", "Jesús").replace("Yrj", "Yrjö")

    # Clean excessive whitespace
    body = re.sub(r"\n{3,}", "\n\n", body).strip()

    # Final document assembly
    doc = (
        fm + "\n"
        "# The World's Key Industry: History and Economics of International Shipping\n\n"
        "**Editors**: Gelina Harlaftis, Stig Tenold, and Jesús M. Valdaliso  \n"
        "**Publisher**: Palgrave Macmillan (Palgrave Studies in Maritime Economics)  \n\n"
        "## Summary\n\n"
        f"{summary_text}\n\n"
        "---\n\n"
        f"{body}\n"
    )

    p.write_text(doc, encoding="utf-8")
    dest = Path("knowledge/docs/books/the_world_s_key_industry_history_and_economics_of_international_shipping_g_harlaftis_s_tenold_j_valdaliso_z_lib_org.md")
    dest.write_text(doc, encoding="utf-8")
    print(f"Book 3 formatted successfully: {len(doc)} chars, {len(doc.splitlines())} lines written to {p} and {dest}")

if __name__ == "__main__":
    format_book3()
