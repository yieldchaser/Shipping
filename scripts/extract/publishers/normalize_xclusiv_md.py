"""
Xclusiv Shipbrokers - Markdown Normalizer & Polisher.

Comprehensive, zero-defect normalizer for extracted Xclusiv weekly reports:
1. Strips all accidental strikethroughs (~~) from negative numbers, diffs, and colored text.
2. Converts raw HTML <table> blocks into clean GitHub-Flavored Markdown tables.
3. Unpacks <br/>-packed header tables into full multi-row Markdown tables.
4. Splits merged Baltic Dry & Tanker indices into two distinct tables.
5. Flattens multi-level header rows (e.g. 'Average Prices' spanning '2023 | 2022 | 2021').
6. Promotes standalone table title headers to clean '### Heading' sections.
7. Strips repeated multi-level prefixes (e.g. 'DEMO SALES NAME', 'DEMOLITION PRICES (in USD/ldt) BULKERS').
8. Removes all stray running headers, footers, page numbers, broker URLs, and address blocks.
9. Fixes mislabeled duplicate headings (e.g. 'MR Pacific Basket').
"""

from __future__ import annotations

import glob
import os
import pathlib
import re
from typing import List, Tuple
from bs4 import BeautifulSoup

ROOT = pathlib.Path(__file__).resolve().parents[3]
MD_DIR = ROOT / "data" / "extracted" / "md" / "xclusiv"


def strip_strikethrough(text: str) -> str:
    """Removes all strikethrough (~~) tags across the document."""
    return re.sub(r"~~([^~]+)~~", r"\1", text)


def fix_mislabeled_headings(text: str) -> str:
    """Fixes duplicated headings where second chart is actually Pacific Basket."""
    text = re.sub(
        r"(### MR Atlantic Basket\s*\n\s*\|[^\n]+\|\s*\n\s*\|[-:\|\s]+\|\s*\n(?:\|[^\n]+\|\s*\n)*\s*)### MR Atlantic Basket(\s*\n\s*\|[^\n]*MR Pacific Basket)",
        r"\1### MR Pacific Basket\2",
        text
    )
    return text


def clean_boilerplate_lines(text: str) -> str:
    """Strips running headers, footers, logos, page numbers, URLs, and address blocks."""
    lines = text.splitlines()
    cleaned = []

    addr_patterns = [
        re.compile(r"XCLUSIV SHIPBROKERS INC", re.I),
        re.compile(r"Kifissias\s+\d+", re.I),
        re.compile(r"15451\s+Psych", re.I),
        re.compile(r"Athens,?\s+Hellas", re.I),
        re.compile(r"Tel:\s*\+30", re.I),
        re.compile(r"^\s*#*\s*shipbrokers\s*$", re.I),
        re.compile(r"^\s*#*\s*\[xclusiv\]\s*(?:shipbrokers)?\s*$", re.I),
        re.compile(r"^\s*\[xclusiv\]\s*$", re.I),
        re.compile(r"^\s*\d{1,2}(?:<sup>)?(?:st|nd|rd|th)?(?:</sup>)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\s*$", re.I),
        re.compile(r"^\s*\d{1,2}/\d{1,2}/\d{4}\s*$"),
        re.compile(r"^\s*Page\s+\d+\s*$", re.I),
        re.compile(r"^\s*\d{1,2}\s*$"),  # standalone page numbers
    ]

    for line in lines:
        stripped = line.strip()
        # Any line containing xclusiv.gr is header/footer noise
        if "xclusiv.gr" in stripped.lower():
            continue
        if any(p.search(stripped) for p in addr_patterns):
            continue
        cleaned.append(line)

    text = "\n".join(cleaned)
    text = re.sub(r"\n*--- PAGE BREAK ---\n*", "\n\n---\n\n", text)
    return text


def html_tables_to_gfm(text: str) -> str:
    """Converts raw HTML <table> blocks to clean Markdown pipe tables."""
    def repl(m):
        html = m.group(0)
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table")
        if not table:
            return html

        caption = ""
        first_th = table.find("th")
        if first_th and first_th.get("colspan"):
            caption = first_th.get_text().strip()

        rows = []
        for tr in table.find_all("tr"):
            cells = [re.sub(r"\s+", " ", td.get_text()).strip() for td in tr.find_all(["th", "td"])]
            if any(cells):
                if len(cells) == 1 and cells[0] == caption:
                    continue
                rows.append(cells)

        if not rows:
            return ""

        max_c = max(len(r) for r in rows)
        if max_c == 0:
            return ""

        padded = [r + [""] * (max_c - len(r)) for r in rows]
        headers = padded[0]
        data = padded[1:]

        md_lines = []
        if caption:
            md_lines.append(f"### {caption.title()}\n")

        md_lines.append("| " + " | ".join(headers) + " |")
        md_lines.append("| " + " | ".join(["---"] * max_c) + " |")
        for r in data:
            md_lines.append("| " + " | ".join(r) + " |")

        return "\n\n" + "\n".join(md_lines) + "\n\n"

    return re.sub(r"<table>.*?</table>", repl, text, flags=re.DOTALL | re.IGNORECASE)


def clean_table_block(table_lines: List[str], preceding_heading: str) -> str:
    """Transforms a raw Markdown table block into a clean, normalized table."""
    parsed = []
    for l in table_lines:
        cells = [c.strip() for c in l.strip()[1:-1].split("|")]
        parsed.append(cells)

    if len(parsed) < 2:
        return "\n".join(table_lines)

    r0 = parsed[0]
    r1 = parsed[1]
    data_rows = parsed[2:]
    out_heading = ""

    # 1. Check Case: Table entirely packed into header cells with <br/>
    has_no_data = len(data_rows) == 0 or all(not any(c for c in r) for r in data_rows)
    is_packed = any(c.count("<br/>") >= 2 for c in r0) and has_no_data

    if is_packed:
        first_parts = [p.strip() for p in r0[0].split("<br/>") if p.strip()]
        title = first_parts[0] if first_parts else ""
        col_headers = []
        col_data = []

        for c in r0:
            parts = [p.strip() for p in c.split("<br/>") if p.strip()]
            if not parts:
                continue
            if len(parts) == 1 and parts[0].upper() == title.upper():
                continue
            if parts[0].upper() == title.upper() or title.upper() in parts[0].upper():
                hdr = parts[1] if len(parts) > 1 else "Value"
                items = parts[2:] if len(parts) > 2 else []
            else:
                hdr = parts[0]
                items = parts[1:]
            col_headers.append(hdr)
            col_data.append(items)

        max_rows = max((len(c) for c in col_data), default=0)
        if col_headers and max_rows > 0:
            res = []
            if title and len(title) > 2 and not title.lower().startswith("col"):
                if title.lower() not in preceding_heading.lower():
                    res.append(f"### {title.title()}\n")
            res.append("| " + " | ".join(col_headers) + " |")
            res.append("| " + " | ".join(["---"] * len(col_headers)) + " |")
            for r_idx in range(max_rows):
                r_vals = [(col_data[c_idx][r_idx] if r_idx < len(col_data[c_idx]) else "") for c_idx in range(len(col_headers))]
                res.append("| " + " | ".join(r_vals) + " |")
            return "\n".join(res)

    # 2. Check Case: 3-level Demolition Prices header
    if any("DEMOLITION" in c.upper() for c in r0) and len([c for c in r0 if c]) == 1 and len(data_rows) >= 2:
        r_sub1 = data_rows[0]
        r_sub2 = data_rows[1]
        if any("BULKER" in c.upper() for c in r_sub1) and any("WEEK" in c.upper() or "CHANGE" in c.upper() for c in r_sub2):
            cur_sector = ""
            new_headers = []
            for c1, c2 in zip(r_sub1, r_sub2):
                if "BULKER" in c1.upper():
                    cur_sector = "Bulkers"
                elif "TANKER" in c1.upper():
                    cur_sector = "Tankers"
                if not cur_sector:
                    new_headers.append(c2 if c2 else "Demo Country")
                else:
                    new_headers.append(f"{cur_sector} {c2}".strip())
            out_heading = "### Demolition Prices (in USD/ldt)\n\n"
            r0 = new_headers
            data_rows = data_rows[2:]

    # 3. Check Case: Single Title in first row (e.g. ['TANKER SALES', '', ...])
    non_empty_r0 = [c for c in r0 if c]
    if len(non_empty_r0) == 1 and len(r0) > 2 and len(data_rows) > 0:
        title = non_empty_r0[0]
        real_headers = data_rows[0]
        non_empty_real = [c for c in real_headers if c]
        if len(non_empty_real) >= 3:
            if title.lower() not in preceding_heading.lower():
                out_heading = f"### {title.title()}\n\n"
            r0 = real_headers
            data_rows = data_rows[1:]

    # 4. Check Case: Baltic Dry & Tanker merged inside data rows
    split_idx = -1
    for idx, row in enumerate(data_rows):
        if any("BALTIC TANKER INDICES" in c for c in row):
            split_idx = idx
            break

    if split_idx != -1:
        dry_rows = data_rows[:split_idx]
        clean_r0 = []
        for c in r0:
            c_clean = re.sub(r"BALTIC DRY INDICES\s*", "", c, flags=re.I).strip()
            c_clean = re.sub(r"BALTIC INDICES\s*", "", c_clean, flags=re.I).strip()
            clean_r0.append(c_clean if c_clean else "BALTIC INDICES")

        t1 = "| " + " | ".join(clean_r0) + " |\n| " + " | ".join(["---"] * len(clean_r0)) + " |\n"
        for r in dry_rows:
            if any(r):
                padded = r + [""] * (len(clean_r0) - len(r))
                t1 += "| " + " | ".join(padded[:len(clean_r0)]) + " |\n"

        tanker_sub = data_rows[split_idx + 1:]
        real_tanker_rows = []
        for r in tanker_sub:
            if any(x in r[0] for x in ["BDTI", "BCTI"]) or (len(r) > 1 and any(x in r[0] for x in ["Dirty", "Clean"])):
                padded = r + [""] * (len(clean_r0) - len(r))
                real_tanker_rows.append(padded[:len(clean_r0)])

        t2 = "### Baltic Tanker Indices\n\n"
        t2 += "| " + " | ".join(clean_r0) + " |\n| " + " | ".join(["---"] * len(clean_r0)) + " |\n"
        for r in real_tanker_rows:
            t2 += "| " + " | ".join(r) + " |\n"

        prefix_head = "### Baltic Dry Indices\n\n" if "Baltic" not in preceding_heading else ""
        return (prefix_head + t1.strip() + "\n\n" + t2.strip()).strip()

    # 5. Check Case: Multi-level header row in data_rows[0] (e.g. ['', '', '', '', '2023', '2022', '2021'])
    if len(data_rows) > 0:
        d0 = data_rows[0]
        years = [c for c in d0 if re.match(r"^(?:19|20)\d{2}$", c)]
        if len(years) >= 2 and d0[:len(d0) - len(years)] == [""] * (len(d0) - len(years)):
            new_headers = []
            prefix = ""
            for h, sub in zip(r0, d0):
                if h and not sub:
                    new_headers.append(h)
                    if "Average" in h or "Prices" in h:
                        prefix = h
                elif sub:
                    pfx = prefix if prefix else "Average"
                    pfx_short = "Average" if "Average" in pfx else pfx
                    new_headers.append(f"{pfx_short} {sub}")
                else:
                    new_headers.append(h)
            r0 = new_headers
            data_rows = data_rows[1:]

    # 6. Check Case: Repeated prefixes in column headers
    common_pfx = None
    for pfx in [
        "DEMOLITION PRICES (in USD/ldt)",
        "DEMOLITION PRICES ($/LDT)",
        "BALTIC DRY INDICES",
        "BALTIC TANKER INDICES",
        "DRY SECONDHAND PRICES ($ mills)",
        "TANKER SECONDHAND PRICES ($ mills)",
        "DRY NEWBUILDING PRICES ($ mills)",
        "TANKER NEWBUILDING PRICES ($ mills)",
        "DEMO SALES",
        "BULK CARRIER SALES",
        "TANKER SALES",
        "CONTAINER SALES",
        "GAS SALES",
    ]:
        matching = sum(1 for c in r0 if pfx.lower() in c.lower())
        if matching >= 2:
            common_pfx = pfx
            break

    if common_pfx:
        if not out_heading and common_pfx.lower() not in preceding_heading.lower():
            out_heading = f"### {common_pfx.title()}\n\n"
        r0 = [re.sub(re.escape(common_pfx), "", c, flags=re.I).strip() for c in r0]
        r0 = [c if c else "Country" for c in r0]

    # Clean any internal <br/> inside column headers
    r0 = [re.sub(r"<br/?>", " ", c).strip() for c in r0]

    res = []
    if out_heading:
        res.append(out_heading.strip())
    res.append("| " + " | ".join(r0) + " |")
    res.append("| " + " | ".join(["---"] * len(r0)) + " |")
    for r in data_rows:
        if any(r):
            padded = r + [""] * (len(r0) - len(r))
            res.append("| " + " | ".join(padded[:len(r0)]) + " |")

    return "\n".join(res)


def normalize_markdown(text: str) -> str:
    """Applies the complete sequence of normalization transforms to markdown text."""
    # Step 1: Strip strikethrough tags unconditionally
    t1 = strip_strikethrough(text)

    # Step 2: Fix mislabeled headings
    t2 = fix_mislabeled_headings(t1)

    # Step 3: Strip boilerplate headers, footers, logos, page numbers, addresses
    t3 = clean_boilerplate_lines(t2)

    # Step 4: Convert HTML tables to GFM
    t4 = html_tables_to_gfm(t3)

    # Step 5: Process and clean Markdown table blocks
    lines = t4.splitlines()
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.strip().startswith("|") and i + 1 < len(lines) and any(s in lines[i + 1] for s in ["| ---", "|:---", "|---"]):
            table_lines = [line, lines[i + 1]]
            j = i + 2
            while j < len(lines) and lines[j].strip().startswith("|"):
                table_lines.append(lines[j])
                j += 1

            preceding = ""
            for k in range(len(out) - 1, max(-1, len(out) - 5), -1):
                if out[k].startswith("#"):
                    preceding = out[k]
                    break

            cleaned_table = clean_table_block(table_lines, preceding)
            out.append(cleaned_table)
            out.append("")
            i = j
            continue

        out.append(line)
        i += 1

    res = "\n".join(out)
    res = re.sub(r"\n{3,}", "\n\n", res)
    return res.strip() + "\n"


def normalize_file(file_path: pathlib.Path) -> bool:
    try:
        orig = file_path.read_text(encoding="utf-8", errors="replace")
        cleaned = normalize_markdown(orig)
        if cleaned != orig:
            file_path.write_text(cleaned, encoding="utf-8")
            return True
        return False
    except Exception as e:
        print(f"Error normalizing {file_path.name}: {e}")
        return False


def main():
    # md tier is organised by YEAR subdirectory (2023/, 2024/, ...): a non-recursive
    # glob finds 0 files and the normaliser silently no-ops. Verified 2026-09-30:
    # top-level *.md = 0, recursive = 271.
    md_files = sorted(MD_DIR.rglob("*.md"))
    print(f"Normalizing {len(md_files)} Xclusiv Markdown files...")
    updated_cnt = 0
    for f in md_files:
        if normalize_file(f):
            updated_cnt += 1

    print(f"Normalization complete! Updated {updated_cnt} / {len(md_files)} files.")


if __name__ == "__main__":
    main()
