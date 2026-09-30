import pymupdf
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
pdf_path = ROOT / "corpus/01-brokers/agora/2026/agora_2026_W34_AGORA.-Week-35-2026.-Snapshot-of-Commercial-Indicators.pdf"
doc = pymupdf.open(pdf_path)


def format_prose_page(page, pno):
    blocks = page.get_text("blocks")
    # Clean blocks
    text_blocks = []
    for b in blocks:
        t = b[4].strip()
        if not t:
            continue
        # Filter footer disclaimers & address
        if "AGORA SHIPBROKING CORPORATION" in t or "www.agoraships.com" in t or "Disclaimer:" in t:
            continue
        text_blocks.append((b[1], b[0], t))

    # Sort vertically
    text_blocks.sort(key=lambda x: (round(x[0], 1), x[1]))

    lines = []
    if pno == 0:  # Cover page
        quote_parts = []
        author_parts = []
        intro_parts = []
        is_intro = False
        week_str = ""

        for y, x, t in text_blocks:
            if "SNAPSHOT" in t.upper() or "COMMERCIAL INDICATORS" in t.upper():
                continue
            if re.search(r"Week\s+\d+", t, re.I):
                week_str = t.replace("\n", " ").strip()
                continue
            if "Introductory Note:" in t:
                is_intro = True
                continue
            if is_intro:
                intro_parts.append(t.replace("\n", " ").strip())
            elif any(c in t for c in ("“", "”", '"', "judge by")):
                quote_parts.append(t.replace("\n", " ").strip())
            elif any(k in t for k in ("Longfellow", "poet", "1807", "1882")):
                author_parts.append(t.replace("\n", " ").strip())

        if quote_parts:
            q_txt = " ".join(quote_parts).replace("“", "").replace("”", "").strip()
            a_txt = " ".join(author_parts).strip()
            lines.append(f"> *\"{q_txt}\"*  ")
            if a_txt:
                lines.append(f"> — {a_txt}\n")
        if intro_parts:
            lines.append("### Introductory Note\n")
            lines.append(" ".join(intro_parts).strip() + "\n")

    elif pno == 3:  # Notes page
        lines.append("### Contract Specifications & Commodity Notes\n")
        raw_text = "\n".join(t for y, x, t in text_blocks)
        # Match numbered items: e.g. 1. Crude Oil - ...
        items = re.findall(r"(\d+\.\s*[^0-9]+(?:\([^)]*\)[^0-9]*)*)", raw_text)
        if not items:
            # Fallback line by line
            for ln in raw_text.splitlines():
                ln = ln.strip()
                if ln and ln != "Notes :":
                    lines.append(f"- {ln}")
        else:
            for it in items:
                it_clean = re.sub(r"\s+", " ", it).strip()
                if it_clean:
                    # Bold the commodity name
                    m = re.match(r"^(\d+\.\s*)([^-–:]+)([-–:].*)$", it_clean)
                    if m:
                        lines.append(f"{m.group(1)}**{m.group(2).strip()}**{m.group(3)}")
                    else:
                        lines.append(f"- {it_clean}")
            lines.append("")

    elif pno == 4:  # Contacts page
        lines.append("### Directory & Contact Details\n")
        lines.append("#### Desks & Specialized Divisions\n")
        lines.append("| Desk / Division | Contact / Emails |")
        lines.append("|---|---|")
        lines.append("| **Bulk Desk** | `bulk@agoraships.com`, `panamax@agoraships.com`, `cape@agoraships.com` |")
        lines.append("| **Mini-Bulk (1-5k DWT)** | `minibulk@agoraships.com` |")
        lines.append("| **Period T/C Requirements** | `period@agoraships.com` |")
        lines.append("| **Sale & Purchase (S&P)** | `snp@agoraships.com` (exclusive clients) |")
        lines.append("| **Tanker Desk** | `tanker@agoraships.com`, `bitumen@agoraships.com` |")
        lines.append("| **Project / MPP / RoRo** | `project@agoraships.com`, `roro@agoraships.com` |")
        lines.append("")
        lines.append("#### Key Personnel\n")
        lines.append("- **Mr. Alexandros Psarianos, BSc, MSc, FICS** – Managing Director (mob: `+30 6985.11.11.02`)")
        lines.append("- **Mr. Dimitris Vasiliou, BSc** – Chartering Broker (mob: `+30 698.938.17.45`)")
        lines.append("- **Mr. Nicolas Trantas, BSc, LLM, MICS** – Chartering Broker (mob: `+30 693.6505.888`)")
        lines.append("- **Mr. Nikos Aronis, BSc** – Chartering Broker (mob: `+30 6970.30.78.08`)")
        lines.append("- **Mr. Dimitrios Katsos, Diploma** – Customs Brokerage & Warehousing (mob: `+30 694.456.4171`)")
        lines.append("- **Mr. Akis Vasilliadis, Diploma** – Accounting (mob: `+30 697.263.4347`)")
        lines.append("")

    return "\n".join(lines)


print(format_prose_page(doc[0], 0))
print("---")
print(format_prose_page(doc[3], 3))
print("---")
print(format_prose_page(doc[4], 4))
