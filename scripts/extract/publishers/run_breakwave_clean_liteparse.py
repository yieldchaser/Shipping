"""
Breakwave In-Process Layout / LiteParse Extractor (Clean Edition)
Extracts:
- Title, Subtitle, Date, Sector
- Short-term Indicators (Momentum, Sentiment, Fundamentals, Futures & Spot Indices with 30D, YTD, YoY trends and directional arrows)
- Editorial commentary preserving span-level bold highlights and clean section headings
- Index composition & methodology note
- Structured Fundamentals tables (Demand, Supply, Freight Rates with Category, Metric, YTD Value, YoY Change)
- Footnotes and data sources

Excludes (per user prompt):
- Charts / graphs and axis ticks
- Legal disclaimer boilerplate
- Corporate contact details, emails, addresses, and ticker boxes
"""

import os
import re
import sys
import glob
import csv
import fitz

if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

def parse_breakwave_clean(pdf_path):
    doc = fitz.open(pdf_path)
    stem = os.path.splitext(os.path.basename(pdf_path))[0]
    category = "tankers" if "tanker" in pdf_path.lower() else "drybulk"
    clean_path = pdf_path.replace("\\", "/")
    
    # Page 1 analysis
    p1 = doc[0]
    blocks1 = p1.get_text("blocks")
    d1 = p1.get_text("dict")
    
    # Detect era: Sidebar layout (Era 2, 2025-2026) vs Horizontal Banner layout (Era 1, 2018-early 2025)
    is_sidebar = any(b[0] >= 400 and "Short-term Indicators" in b[4] for b in blocks1)
    
    title = f"Breakwave {category.title()} Shipping Report"
    subtitle = "Bi-Weekly Industry Report"
    report_date = ""
    
    for b in blocks1:
        text = b[4].strip()
        if b[1] < 120:
            for l in text.split("\n"):
                l_str = l.strip()
                if "Shipping" in l_str and len(l_str) < 40:
                    title = l_str
                if "Bi-Weekly" in l_str:
                    subtitle = l_str
                months = [
                    "January", "February", "March", "April", "May", "June",
                    "July", "August", "September", "October", "November", "December"
                ]
                if any(m in l_str for m in months) and re.search(r"\d{4}", l_str):
                    report_date = l_str

    # 1. Indicators Parsing
    indicators = {}
    futures_trends = {}
    spot_trends = {}
    
    if is_sidebar:
        # Era 2 Sidebar: right column (x0 >= 420, y0 < 420)
        right_blocks = [b for b in blocks1 if b[0] >= 420 and b[1] < 420]
        right_blocks.sort(key=lambda b: b[1])
        
        for b in right_blocks:
            y0 = b[1]
            text = b[4].strip()
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            
            for idx, l in enumerate(lines):
                # Stance
                for stance in ["Momentum:", "Sentiment:", "Fundamentals:"]:
                    if stance in l:
                        val = l.replace(stance, "").strip()
                        if not val and idx + 1 < len(lines):
                            val = lines[idx + 1].strip()
                        indicators[stance[:-1]] = val
                
                # Trends
                m_pct = re.findall(r"(30D|YTD|YOY):\s*([+\-]?\d+(?:\.\d+)?%)", l)
                for k, v in m_pct:
                    arrow = ""
                    if idx + 1 < len(lines) and lines[idx + 1] in ["↑", "↓"]:
                        arrow = " " + lines[idx + 1]
                    trend_str = v + arrow
                    if y0 < 300:
                        futures_trends[k] = trend_str
                    else:
                        spot_trends[k] = trend_str
                        
                # Numeric values (1449, 1274, 14.24, $16.30)
                m_num = re.search(r"^\$?(\d{1,5}(?:\.\d{1,2})?)$", l)
                if m_num:
                    num_val = m_num.group(1)
                    if y0 < 300:
                        indicators["Futures Index"] = num_val
                    else:
                        indicators["Spot Index"] = num_val
    else:
        # Era 1 Horizontal banner layout
        col1_spans = []
        col2_spans = []
        col3_spans = []
        
        for b in d1["blocks"]:
            if "lines" not in b:
                continue
            for l in b["lines"]:
                for s in l["spans"]:
                    txt = s["text"].strip()
                    if not txt:
                        continue
                    y = s["bbox"][1]
                    if 90 <= y <= 210:
                        x = s["bbox"][0]
                        if x < 235:
                            col1_spans.append((y, x, txt))
                        elif x < 420:
                            col2_spans.append((y, x, txt))
                        else:
                            col3_spans.append((y, x, txt))
                            
        col1_spans.sort(key=lambda item: (round(item[0], 1), round(item[1], 1)))
        col2_spans.sort(key=lambda item: (round(item[0], 1), round(item[1], 1)))
        col3_spans.sort(key=lambda item: (round(item[0], 1), round(item[1], 1)))
        
        # Col 1: Futures Index & Trends
        c1_tokens = [item[2] for item in col1_spans]
        c1_text = " ".join(c1_tokens)
        m_fut = re.search(r"Futures Index:\s*([\d,]+)", c1_text)
        if m_fut:
            indicators["Futures Index"] = m_fut.group(1).replace(",", "")
        else:
            for tok in c1_tokens:
                if re.match(r"^[\d,]{3,5}$", tok):
                    indicators["Futures Index"] = tok.replace(",", "")
                    break
        for idx, tok in enumerate(c1_tokens):
            m_pct = re.match(r"^(30D|YTD|YOY):\s*([+\-]?\d+(?:\.\d+)?%)$", tok)
            if m_pct:
                k, v = m_pct.group(1), m_pct.group(2)
                arrow = ""
                if idx > 0 and c1_tokens[idx - 1] in ["↑", "↓"]:
                    arrow = " " + c1_tokens[idx - 1]
                elif idx + 1 < len(c1_tokens) and c1_tokens[idx + 1] in ["↑", "↓"]:
                    arrow = " " + c1_tokens[idx + 1]
                futures_trends[k] = v + arrow

        # Col 2: Spot Index & Trends
        c2_tokens = [item[2] for item in col2_spans]
        c2_text = " ".join(c2_tokens)
        m_spot = re.search(r"(?:\(spot\)|Spot Rates|spot):\s*\$?([\d,\.]+)", c2_text)
        if m_spot:
            indicators["Spot Index"] = m_spot.group(1).replace(",", "")
        else:
            for tok in c2_tokens:
                clean_tok = tok.replace("$", "").replace(",", "")
                if re.match(r"^\d{1,5}(?:\.\d{1,2})?$", clean_tok) and not tok.endswith("%"):
                    indicators["Spot Index"] = clean_tok
                    break
        for idx, tok in enumerate(c2_tokens):
            m_pct = re.match(r"^(30D|YTD|YOY):\s*([+\-]?\d+(?:\.\d+)?%)$", tok)
            if m_pct:
                k, v = m_pct.group(1), m_pct.group(2)
                arrow = ""
                if idx > 0 and c2_tokens[idx - 1] in ["↑", "↓"]:
                    arrow = " " + c2_tokens[idx - 1]
                elif idx + 1 < len(c2_tokens) and c2_tokens[idx + 1] in ["↑", "↓"]:
                    arrow = " " + c2_tokens[idx + 1]
                spot_trends[k] = v + arrow

        # Col 3: Stance (Momentum, Sentiment, Fundamentals)
        c3_tokens = [item[2] for item in col3_spans]
        idx = 0
        while idx < len(c3_tokens):
            tok = c3_tokens[idx]
            for st in ["Momentum", "Sentiment", "Fundamentals"]:
                if tok.startswith(f"{st}:"):
                    val = tok.replace(f"{st}:", "").strip()
                    if not val and idx + 1 < len(c3_tokens):
                        val = c3_tokens[idx + 1]
                        idx += 1
                    indicators[st] = val
            idx += 1

    # 2. Editorial Prose Parsing (preserving bold text and section breaks)
    editorials_raw = []
    current_bullet = []
    
    for b in d1["blocks"]:
        if "lines" not in b:
            continue
        x0, y0, x1, y1 = b["bbox"]
        
        # Spatial bounds for editorial prose
        if is_sidebar:
            in_prose = (x0 < 445 and 130 < y0 < 760)
        else:
            in_prose = (y0 >= 210 and y0 < 735)
            
        if in_prose:
            for line in b["lines"]:
                line_text = ""
                for span in line["spans"]:
                    txt = span["text"]
                    font = span["font"]
                    flags = span["flags"]
                    is_bold = bool(flags & 16) or ("Bold" in font) or ("bold" in font)
                    clean_span = txt.strip()
                    if clean_span:
                        if line_text and not line_text.endswith(" "):
                            line_text += " "
                        if is_bold:
                            line_text += f"**{clean_span}**"
                        else:
                            line_text += clean_span
                clean_l = line_text.strip()
                if clean_l.startswith("•") or clean_l.startswith("**•"):
                    if current_bullet:
                        editorials_raw.append(" ".join("".join(current_bullet).split()))
                        current_bullet = []
                    clean_l = re.sub(r"^\**•\**\s*", "", clean_l)
                if clean_l:
                    current_bullet.append(clean_l + " ")
                    
    if current_bullet:
        editorials_raw.append(" ".join("".join(current_bullet).split()))
        
    editorials = []
    for bullet_text in editorials_raw:
        bullet_text = bullet_text.strip()
        if not bullet_text:
            continue
        bullet_text = re.sub(r"\s+([,.:;!?)])", r"\1", bullet_text)
        bullet_text = re.sub(r"([(])\s+", r"\1", bullet_text)
        bullet_text = re.sub(r"\*\*\s+\*\*", " ", bullet_text)
        
        heading = ""
        body = bullet_text
        m_head = re.match(r"^\*?\*?([^*\n]+?)\s*(?:[–—]|\s-\s)\s*\*?\*?\s*(.*)$", bullet_text, re.DOTALL)
        if m_head:
            heading = m_head.group(1).replace("**", "").strip()
            body = m_head.group(2).strip()
        editorials.append({"heading": heading, "body": body})

    # 3. Methodology Note
    methodology_note = ""
    # In Era 1, methodology note is often at the bottom of Page 1
    for b in blocks1:
        text = b[4].strip()
        if b[1] >= 730 and ("Index (BDI)" in text or "Index (BWETFF)" in text or "measures the" in text):
            methodology_note = " ".join(text.split())

    # 4. Page 2: Index Note, Fundamentals Table, Sources (EXCLUDING GRAPH & DISCLAIMER)
    fundamentals = []
    notes_and_sources = []
    
    if len(doc) > 1:
        p2 = doc[1]
        blocks2 = p2.get_text("blocks")
        for b in sorted(blocks2, key=lambda x: (x[1], x[0])):
            x0, y0, x1, y1, text, _, _ = b
            text = text.strip()
            if not text:
                continue
            
            # Notes & Sources (strictly stopping before Disclaimer / Contact boilerplate)
            if "Note:" in text or "Sources:" in text:
                for l in text.split("\n"):
                    l = l.strip()
                    if l.startswith("Disclaimer:") or "Please visit" in l or "Contact:" in l:
                        break
                    if l.startswith("Note:") or l.startswith("Sources:"):
                        notes_and_sources.append(l)

            # Methodology note directly under graph (Era 2)
            elif len(text) > 80 and ("measures the" in text or "weighting of" in text) and not text.startswith("Disclaimer") and "LLC" not in text:
                methodology_note = " ".join(text.split())
                
            # Fundamentals tables (Demand, Supply, Freight Rates)
            elif any(k in text for k in ["Demand", "Supply", "Freight Rates"]):
                lines = [l.strip() for l in text.split("\n") if l.strip()]
                sec_name = ""
                if "Demand" in lines:
                    sec_name = "Demand"
                elif "Supply" in lines:
                    sec_name = "Supply"
                elif "Freight Rates" in lines:
                    sec_name = "Freight Rates"
                
                items = [l for l in lines if l not in ["Demand", "Supply", "Freight Rates", "YTD", "YOY"]]
                idx = 0
                while idx < len(items):
                    name = items[idx]
                    ytd = items[idx + 1] if idx + 1 < len(items) else ""
                    yoy = items[idx + 2] if idx + 2 < len(items) else ""
                    if "%" in yoy or re.match(r"^[+\-]?\d+(?:\.\d+)?%?$", yoy):
                        fundamentals.append({
                            "section": sec_name or "Fundamentals",
                            "metric": name,
                            "ytd": ytd,
                            "yoy": yoy
                        })
                        idx += 3
                    elif "%" in ytd or re.match(r"^[+\-]?\d+(?:\.\d+)?%?$", ytd):
                        fundamentals.append({
                            "section": sec_name or "Fundamentals",
                            "metric": name,
                            "ytd": ytd,
                            "yoy": ""
                        })
                        idx += 2
                    else:
                        idx += 1

    # Format Publication-Grade Markdown
    md = []
    md.append("---")
    md.append(f'title: "{title}"')
    if subtitle:
        md.append(f'subtitle: "{subtitle}"')
    md.append(f'date: "{report_date}"')
    md.append(f'category: "{category}"')
    md.append('source: "Breakwave Advisors"')
    md.append(f'source_file: "{clean_path}"')
    if indicators:
        md.append("indicators:")
        for k, v in indicators.items():
            md.append(f'  {k}: "{v}"')
    md.append("---")
    md.append("")
    md.append(f"# {title}")
    if subtitle:
        md.append(f"*{subtitle}*  ")
    if report_date:
        md.append(f"**Date:** {report_date}  ")
    md.append(f"**Publisher:** Breakwave Advisors | **Sector:** {category.title()}  ")
    md.append("")
    
    # Indicators Tables (Split into Market Stance and Freight & Futures Indices)
    if indicators or futures_trends:
        md.append("## Short-term Indicators")
        md.append("")
        
        # 1. Market Stance Table
        mom = indicators.get("Momentum", "-")
        sent = indicators.get("Sentiment", "-")
        fund = indicators.get("Fundamentals", "-")
        if any(x != "-" for x in [mom, sent, fund]):
            md.append("### Market Stance")
            md.append("")
            md.append("| Indicator | Assessment |")
            md.append("| :--- | :---: |")
            md.append(f"| **Momentum** | {mom} |")
            md.append(f"| **Sentiment** | {sent} |")
            md.append(f"| **Fundamentals** | {fund} |")
            md.append("")
            
        # 2. Freight & Futures Indices Table
        fut = indicators.get("Futures Index", "-")
        spot = indicators.get("Spot Index", "-")
        fut_30d = futures_trends.get("30D", "-")
        fut_ytd = futures_trends.get("YTD", "-")
        fut_yoy = futures_trends.get("YOY", "-")
        spot_30d = spot_trends.get("30D", "-")
        spot_ytd = spot_trends.get("YTD", "-")
        spot_yoy = spot_trends.get("YOY", "-")
        
        fut_str = f"{int(fut):,}" if fut.isdigit() else fut
        spot_str = f"{int(spot):,}" if spot.isdigit() else spot
        
        fut_label = "Breakwave Futures Index" if category == "drybulk" else "Breakwave Tanker Futures Index"
        spot_label = "Baltic Dry Index (spot)" if category == "drybulk" else "Tanker Spot Rates"
        
        md.append("### Freight & Futures Indices")
        md.append("")
        md.append("| Index | Current Value | 30-Day Trend | YTD Change | YoY Change |")
        md.append("| :--- | :---: | :---: | :---: | :---: |")
        md.append(f"| **{fut_label}** | {fut_str} | {fut_30d} | {fut_ytd} | {fut_yoy} |")
        if spot != "-" or spot_trends:
            md.append(f"| **{spot_label}** | {spot_str} | {spot_30d} | {spot_ytd} | {spot_yoy} |")
        md.append("")

    # Editorial Market Overview & Analysis
    md.append("## Market Overview & Analysis")
    md.append("")
    for ed in editorials:
        if ed["heading"]:
            md.append(f"### {ed['heading']}")
            md.append("")
        md.append(ed["body"])
        md.append("")

    # Methodology
    if methodology_note:
        md.append("## Index Composition & Methodology")
        md.append("")
        md.append(f"> {methodology_note}")
        md.append("")

    # Fundamentals Table
    if fundamentals:
        md.append(f"## {category.title()} Fundamentals")
        md.append("")
        md.append("| Category | Metric | YTD Value | YoY Change |")
        md.append("| :--- | :--- | :---: | :---: |")
        for item in fundamentals:
            md.append(f"| {item['section']} | {item['metric']} | {item['ytd']} | {item['yoy']} |")
        md.append("")

    # Notes & Sources
    if notes_and_sources:
        md.append("---")
        md.append("")
        for ns in notes_and_sources:
            md.append(f"*{ns}*  ")
        md.append("")

    return "\n".join(md), fundamentals, indicators, report_date

def run_batch():
    dry_files = sorted(glob.glob("corpus/03-breakwave/drybulk/**/*.pdf", recursive=True))
    tank_files = sorted(glob.glob("corpus/03-breakwave/tankers/**/*.pdf", recursive=True))
    all_files = dry_files + tank_files
    print(f"Total Breakwave reports to process: {len(all_files)} ({len(dry_files)} drybulk, {len(tank_files)} tankers)")
    
    os.makedirs("data/extracted/md/breakwave/drybulk", exist_ok=True)
    os.makedirs("data/extracted/md/breakwave/tankers", exist_ok=True)
    os.makedirs("data/extracted/series", exist_ok=True)
    
    series_rows = []
    
    for idx, f in enumerate(all_files):
        try:
            stem = os.path.splitext(os.path.basename(f))[0]
            category = "tankers" if "tanker" in f.lower() else "drybulk"
            md_content, funds, ind, rep_date = parse_breakwave_clean(f)
            
            # Extract date ISO if possible
            date_match = re.search(r"(\d{4}-\d{2}-\d{2})", stem)
            iso_date = date_match.group(1) if date_match else ""
            
            out_md_path = f"data/extracted/md/breakwave/{category}/{stem}.md"
            with open(out_md_path, "w", encoding="utf-8") as out_f:
                out_f.write(md_content)
                
            for item in funds:
                series_rows.append({
                    "issue_date": iso_date or rep_date,
                    "sector": category,
                    "category": item["section"],
                    "metric": item["metric"],
                    "ytd_value": item["ytd"],
                    "yoy_change": item["yoy"],
                    "source_file": f.replace("\\", "/")
                })
        except Exception as e:
            print(f"Error processing {f}: {e}")
            
        if (idx + 1) % 50 == 0 or (idx + 1) == len(all_files):
            print(f"Processed {idx + 1}/{len(all_files)} reports...")

    # Write series CSV
    series_path = "data/extracted/series/breakwave_fundamentals_series.csv"
    with open(series_path, "w", encoding="utf-8", newline="") as sf:
        fieldnames = ["issue_date", "sector", "category", "metric", "ytd_value", "yoy_change", "source_file"]
        writer = csv.DictWriter(sf, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(series_rows)
        
    print(f"Complete! Extracted {len(all_files)} markdown files and {len(series_rows)} fundamentals series rows to {series_path}")

if __name__ == "__main__":
    if len(sys.argv) == 1 or (len(sys.argv) > 1 and sys.argv[1] == "--batch"):
        run_batch()
    else:
        target = sys.argv[1]
        md, funds, ind, rep_date = parse_breakwave_clean(target)
        print(md)
