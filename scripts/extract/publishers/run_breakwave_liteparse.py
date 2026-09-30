"""
Breakwave In-Process Layout / LiteParse Extractor
Extracts 100% of narrative prose, sentiment/momentum indicators, index benchmarks,
and fundamentals tables (Demand, Supply, Freight Rates) from Breakwave PDF reports
without parsing graphs.

Outputs:
- data/extracted/md/breakwave/drybulk/<stem>.md
- data/extracted/md/breakwave/tankers/<stem>.md
- data/extracted/series/breakwave_fundamentals_series.csv
"""

import os
import re
import sys
import glob
import fitz

def parse_breakwave_pdf(pdf_path, category):
    doc = fitz.open(pdf_path)
    stem = os.path.splitext(os.path.basename(pdf_path))[0]
    clean_path = pdf_path.replace("\\", "/")
    
    # Page 1: Text & Layout
    p1 = doc[0]
    blocks1 = p1.get_text("blocks")
    
    title = f"Breakwave {category.title()} Shipping Report"
    report_date = ""
    editorials = []
    indicators = {}
    
    for b in sorted(blocks1, key=lambda x: (x[1], x[0])):
        x0, y0, x1, y1, text, _, _ = b
        text = text.strip()
        if not text:
            continue
        
        # Header area
        if y0 < 120:
            if "Shipping" in text:
                title = text.split("\n")[0].strip()
            months = [
                "January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November", "December"
            ]
            if any(m in text for m in months):
                for l in text.split("\n"):
                    if any(m in l for m in months):
                        report_date = l.strip()
                        
        # Left column: narrative prose (x0 < 445)
        elif x0 < 445 and y0 < 740:
            clean_text = text.replace("•", "").replace("", "").strip()
            clean_text = " ".join(clean_text.split())
            if not clean_text:
                continue
            
            heading = ""
            body = clean_text
            for sep in [" – ", " - ", " — "]:
                if sep in clean_text[:120]:
                    parts = clean_text.split(sep, 1)
                    heading = parts[0].strip()
                    body = parts[1].strip()
                    break
            editorials.append({"heading": heading, "body": body})
            
        # Right column: indicators (x0 >= 445)
        elif x0 >= 445 and y0 < 500:
            lines = [line.strip() for line in text.split("\n") if line.strip()]
            for idx, l in enumerate(lines):
                for ind in ["Momentum:", "Sentiment:", "Fundamentals:"]:
                    if ind in l:
                        val = l.replace(ind, "").strip()
                        if not val and idx + 1 < len(lines):
                            val = lines[idx + 1].strip()
                        indicators[ind[:-1]] = val
                m_pct = re.findall(r"(30D|YTD|YOY):\s*([\d\.\+\-\%]+)", l)
                for k, v in m_pct:
                    indicators[k] = v
                m_val = re.search(r"^\b(\d{3,5}(?:\.\d{1,2})?)\b$", l)
                if m_val:
                    if "index_value" not in indicators:
                        indicators["index_value"] = m_val.group(1)
                    else:
                        indicators["spot_value"] = m_val.group(1)

    # Page 2: Text & Tables (Ignoring graph vectors and axes)
    fundamentals = []
    index_description = ""
    if len(doc) > 1:
        p2 = doc[1]
        blocks2 = p2.get_text("blocks")
        for b in sorted(blocks2, key=lambda x: (x[1], x[0])):
            x0, y0, x1, y1, text, _, _ = b
            text = text.strip()
            if not text:
                continue
            
            # Index / Baltic methodology description
            if 270 <= y0 <= 360 and len(text) > 80:
                index_description = " ".join(text.split())
                
            # Fundamentals tables
            if 360 <= y0 < 650:
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
                    if "%" in yoy or re.match(r"[\+\-\d\.]+", yoy):
                        fundamentals.append({
                            "section": sec_name or "Fundamentals",
                            "metric": name,
                            "ytd": ytd,
                            "yoy": yoy
                        })
                        idx += 3
                    elif "%" in ytd or re.match(r"[\+\-\d\.]+", ytd):
                        fundamentals.append({
                            "section": sec_name or "Fundamentals",
                            "metric": name,
                            "ytd": ytd,
                            "yoy": ""
                        })
                        idx += 2
                    else:
                        idx += 1

    # Render Clean Markdown
    md = []
    md.append("---")
    md.append(f'title: "{title}"')
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
    if report_date:
        md.append(f"**Date:** {report_date}  ")
    md.append(f"**Publisher:** Breakwave Advisors | **Sector:** {category.title()}  ")
    md.append("")
    
    # Indicators callout table
    if indicators:
        md.append("## Market Indicators")
        md.append("")
        md.append("| Indicator | Assessment / Value | Trend (30D) | YTD | YoY |")
        md.append("| :--- | :---: | :---: | :---: | :---: |")
        momentum = indicators.get("Momentum", "N/A")
        sentiment = indicators.get("Sentiment", "N/A")
        fund = indicators.get("Fundamentals", "N/A")
        idx_val = indicators.get("index_value", "N/A")
        spot_val = indicators.get("spot_value", "N/A")
        d30 = indicators.get("30D", "N/A")
        ytd = indicators.get("YTD", "N/A")
        yoy = indicators.get("YOY", "N/A")
        md.append(f"| **Sentiment & Momentum** | Momentum: {momentum} \\| Sentiment: {sentiment} \\| Fundamentals: {fund} | {d30} | {ytd} | {yoy} |")
        if idx_val != "N/A" or spot_val != "N/A":
            md.append(f"| **Futures / Spot Index** | Futures: {idx_val} \\| Spot: {spot_val} | {d30} | {ytd} | {yoy} |")
        md.append("")

    # Editorial Prose
    md.append("## Market Overview & Analysis")
    md.append("")
    for ed in editorials:
        if ed["heading"]:
            md.append(f"### {ed['heading']}")
            md.append("")
        md.append(ed["body"])
        md.append("")

    # Index Methodology
    if index_description:
        md.append("## Index Methodology & Composition")
        md.append("")
        md.append(f"> {index_description}")
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

    return "\n".join(md), fundamentals

def run_all():
    out_base = "data/extracted/md/breakwave"
    dry_out = os.path.join(out_base, "drybulk")
    tank_out = os.path.join(out_base, "tankers")
    os.makedirs(dry_out, exist_ok=True)
    os.makedirs(tank_out, exist_ok=True)
    
    series_dir = "data/extracted/series"
    os.makedirs(series_dir, exist_ok=True)
    csv_path = os.path.join(series_dir, "breakwave_fundamentals_series.csv")

    dry_pdfs = sorted(glob.glob("corpus/03-breakwave/drybulk/**/*.pdf", recursive=True))
    tank_pdfs = sorted(glob.glob("corpus/03-breakwave/tankers/**/*.pdf", recursive=True))
    
    print(f"Starting LiteParse extraction: {len(dry_pdfs)} Dry Bulk PDFs, {len(tank_pdfs)} Tankers PDFs...")
    
    all_funds = []
    
    # Process Dry Bulk
    for idx, p in enumerate(dry_pdfs, 1):
        stem = os.path.splitext(os.path.basename(p))[0]
        md_text, funds = parse_breakwave_pdf(p, "drybulk")
        target_md = os.path.join(dry_out, f"{stem}.md")
        with open(target_md, "w", encoding="utf-8") as f:
            f.write(md_text)
        for fund in funds:
            fund["source_file"] = p.replace("\\", "/")
            fund["report_slug"] = stem
            fund["category"] = "drybulk"
            all_funds.append(fund)
            
    # Process Tankers
    for idx, p in enumerate(tank_pdfs, 1):
        stem = os.path.splitext(os.path.basename(p))[0]
        md_text, funds = parse_breakwave_pdf(p, "tankers")
        target_md = os.path.join(tank_out, f"{stem}.md")
        with open(target_md, "w", encoding="utf-8") as f:
            f.write(md_text)
        for fund in funds:
            fund["source_file"] = p.replace("\\", "/")
            fund["report_slug"] = stem
            fund["category"] = "tankers"
            all_funds.append(fund)

    # Write series CSV
    import csv
    if all_funds:
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["category", "report_slug", "section", "metric", "ytd", "yoy", "source_file"])
            writer.writeheader()
            writer.writerows(all_funds)
            
    print(f"Extraction complete! Saved {len(dry_pdfs)} drybulk .md, {len(tank_pdfs)} tankers .md.")
    print(f"Fundamentals series saved to {csv_path} with {len(all_funds):,} rows.")

if __name__ == "__main__":
    run_all()
