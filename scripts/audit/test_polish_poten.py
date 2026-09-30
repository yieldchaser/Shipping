import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
import re
from pathlib import Path

DATE_HEADER_PAT = re.compile(
    r"^(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}$",
    re.I
)

def polish_poten_markdown(raw_md: str, title: str, issue_date_str: str) -> str:
    text = raw_md.replace("\r\n", "\n").replace("\r", "\n")

    # 1. Strip repeating headers, running headers, and running footers line-by-line
    line_patterns = [
        r"(?im)^#+\s*Weekly\s+Tanker\s+Opinion\s*$",
        r"(?im)^POTEN\s*&\s*PARTNERS\s*$",
        r"(?im)^#+\s*POTEN\s*&\s*PARTNERS\s*$",
        r"(?im)^<?Poten\s*&\s*Partners\s*\|.*$",
        r"(?im)^www\.poten\.com(?:\s+[A-Za-z]+\s+\d{1,2},?\s+\d{4})?\s*$",
        r"(?im)^Poten\s+Tanker\s+Opinion\s*$",
        r"(?im)^WEEKLY\s+TANKER\s+OPINION\s*$",
        r"(?im)^Email:\s*tankerresearch@poten\.com.*$",
        r"(?im)^NEW YORK\s+LONDON\s+PERTH\s+ATHENS\s+HOUSTON\s+SINGAPORE.*$",
        r"(?im)^----+[ \t]*$",
        r"(?im)^\d+\s*$",
    ]
    for pat in line_patterns:
        text = re.sub(pat, "", text)

    # 2. Strip closing disclaimer block at the very end of the file
    text = re.sub(r"(?is)\*?Poten Tanker Market Opinions are published by the Marine Projects & Consulting department.*$", "", text)
    text = re.sub(r"(?is)Disclaimer:\s*Poten & Partners, Inc\. makes no representation or warranty.*$", "", text)

    # 3. Clean leading duplicate title/date lines (STRICT length check: only short headers)
    text = text.strip()
    title_clean = re.sub(r"[^\w\s]", "", title).strip().lower()

    while text:
        first_line = text.split("\n", 1)[0].strip("#* \t")
        if not first_line:
            text = text.split("\n", 1)[1].strip() if "\n" in text else ""
            continue
        first_clean = re.sub(r"[^\w\s]", "", first_line).strip().lower()
        is_exact_title = (first_clean == title_clean or first_clean == f"weekly tanker opinion {title_clean}" or first_clean == "weekly tanker opinion")
        is_date_header = (len(first_line) < 40 and bool(DATE_HEADER_PAT.match(first_line)))

        if is_exact_title or is_date_header:
            text = text.split("\n", 1)[1].strip() if "\n" in text else ""
        else:
            break

    # 4. Normalize paragraph newlines
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    # 5. Compose formatted body with header
    header = f"# Weekly Tanker Opinion: {title}\n**{issue_date_str}**\n\n"
    return header + text + "\n"

raw_2004 = Path("data/extracted/llamaparse_poten/2004/Tanker_Opinion_20040723.raw.md").read_text(encoding="utf-8")
polished = polish_poten_markdown(raw_2004, "A Midsummer Night's Dream!", "July 23, 2004")
print("--- PREVIEW FIRST 1000 CHARS ---")
print(polished[:1000])
print("\n--- PREVIEW LAST 500 CHARS ---")
print(polished[-500:])
