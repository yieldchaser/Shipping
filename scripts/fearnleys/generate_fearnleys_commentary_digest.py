#!/usr/bin/env python3
"""
generate_fearnleys_commentary_digest.py
Digests broker commentary records from Fearnleys Hasura API (data/derived/fearnleys_broker_comments.csv)
into cleanly structured, sector-segregated weekly Markdown reports.

Sectors:
1. Dry Bulk (Capesize, Panamax, Supramax)
2. Tankers (VLCC, Suezmax, Aframax, Spot routes)
3. Gas & LNG (LNG Market Report, LPG, Eastern/Western markets)
4. Sale and Purchase (S&P Weekly Comment, Chartering)

Outputs:
- reports/fearnleys/commentary/<year>/fearnleys_weekly_commentary_week_<week>_<year>.md
- data/reports/fearnleys/commentary/<year>/fearnleys_weekly_commentary_week_<week>_<year>.md
- reports/fearnleys/fearnleys_latest_weekly_commentary.md (symlink/copy of newest week)
- data/reports/fearnleys/fearnleys_latest_weekly_commentary.md
"""

import os
import re
from pathlib import Path
from datetime import datetime
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
COMMENTS_CSV = REPO_ROOT / "data" / "derived" / "fearnleys_broker_comments.csv"
REPORTS_DIR = REPO_ROOT / "reports" / "fearnleys" / "commentary"
DATA_REPORTS_DIR = REPO_ROOT / "data" / "reports" / "fearnleys" / "commentary"

# Ordering of commentary types within sectors
DRY_TYPES = [
    "Capesize Weekly Comment",
    "Panamax Weekly Comment",
    "Supramax Weekly Comment",
]

TANKER_TYPES = [
    "VLCC Weekly Comment",
    "Suezmax Weekly Comment",
    "Aframax Weekly Comment",
    "Tank Weekly Comment",
]

GAS_TYPES = [
    "LNG Market Report",
    "Gas Market Weekly Comment - Eastern Market",
    "Gas Market Weekly Comment - Western Market",
    "Gas Market Report",
    "Daily BLPG Report",
]

SNP_TYPES = [
    "SnP Weekly Comment",
    "Chartering Weekly Comment",
]

def clean_comment_text(text: str) -> str:
    if not isinstance(text, str):
        return ""
    t = text.replace("\r\n", "\n").replace("\r", "\n")
    # Normalize double blank lines
    t = re.sub(r'\n{3,}', '\n\n', t).strip()
    return t

def format_comment_card(row: pd.Series) -> str:
    c_type = row.get("comment_type", "")
    subtype = row.get("comment_subtype", "")
    date_str = row.get("date", "")
    text = clean_comment_text(row.get("text", ""))
    
    lines = [
        f"### {c_type}",
        f"**Date:** {date_str} | **Subtype:** {subtype} | **Desk:** Fearnleys Research",
        "",
        text,
        "",
        "---",
        ""
    ]
    return "\n".join(lines)

def build_weekly_markdown(year: int, week: int, week_df: pd.DataFrame) -> str:
    min_date = week_df["date"].min()
    max_date = week_df["date"].max()
    count = len(week_df)
    
    frontmatter = f"""---
title: "Fearnleys Weekly Broker Commentary - Week {week:02d}, {year}"
source: "Fearnleys Hasura GraphQL API (fearnpulse.com)"
year: {year}
week: {week}
date_range: "{min_date} to {max_date}"
comments_count: {count}
sectors: ["Dry Bulk", "Tankers", "Gas & LNG", "Sale and Purchase (S&P)"]
generated_at: "{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
---
"""
    
    doc = [
        frontmatter,
        f"# Fearnleys Weekly Broker Commentary - Week {week:02d}, {year}",
        f"*Coverage Period: {min_date} to {max_date} | Total Notes: {count}*",
        "",
        "## Executive Summary",
        f"Institutional desk intelligence harvested directly from the Fearnleys Hasura GraphQL backend, covering global Dry Bulk, Crude & Product Tankers, Gas/LNG markets, and Secondhand S&P deals for Week {week:02d} ({year}).",
        "",
    ]
    
    # 1. Dry Bulk
    dry_rows = week_df[week_df["comment_type"].isin(DRY_TYPES)]
    doc.append("## 1. Dry Bulk Sector")
    if dry_rows.empty:
        doc.append("*No dedicated dry bulk commentary published this week.*\n")
    else:
        for ct in DRY_TYPES:
            matching = dry_rows[dry_rows["comment_type"] == ct]
            for _, r in matching.iterrows():
                doc.append(format_comment_card(r))
                
    # 2. Tankers
    tanker_rows = week_df[week_df["comment_type"].isin(TANKER_TYPES)]
    doc.append("## 2. Tanker Sector (Crude & Products)")
    if tanker_rows.empty:
        doc.append("*No dedicated tanker commentary published this week.*\n")
    else:
        for ct in TANKER_TYPES:
            matching = tanker_rows[tanker_rows["comment_type"] == ct]
            for _, r in matching.iterrows():
                doc.append(format_comment_card(r))
                
    # 3. Gas & LNG
    gas_rows = week_df[week_df["comment_type"].isin(GAS_TYPES)]
    doc.append("## 3. Gas & LNG Markets")
    if gas_rows.empty:
        doc.append("*No dedicated gas/LNG commentary published this week.*\n")
    else:
        for ct in GAS_TYPES:
            matching = gas_rows[gas_rows["comment_type"] == ct]
            for _, r in matching.iterrows():
                doc.append(format_comment_card(r))
                
    # 4. S&P & Other
    snp_rows = week_df[week_df["comment_type"].isin(SNP_TYPES)]
    other_rows = week_df[~week_df["comment_type"].isin(DRY_TYPES + TANKER_TYPES + GAS_TYPES + SNP_TYPES)]
    doc.append("## 4. Sale and Purchase (S&P) & Corporate Activity")
    if snp_rows.empty and other_rows.empty:
        doc.append("*No dedicated S&P commentary published this week.*\n")
    else:
        for ct in SNP_TYPES:
            matching = snp_rows[snp_rows["comment_type"] == ct]
            for _, r in matching.iterrows():
                doc.append(format_comment_card(r))
        for _, r in other_rows.iterrows():
            doc.append(format_comment_card(r))
            
    return "\n".join(doc)

def main():
    if not COMMENTS_CSV.exists():
        print(f"Error: {COMMENTS_CSV} does not exist.")
        return
        
    print(f"Reading {COMMENTS_CSV}...")
    df = pd.read_csv(COMMENTS_CSV)
    df["date_dt"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date_dt"]).sort_values("date")
    
    df["year"] = df["date_dt"].dt.isocalendar().year
    df["week"] = df["date_dt"].dt.isocalendar().week
    
    weeks_2026 = df[df["year"] == 2026].groupby(["year", "week"])
    
    total_generated = 0
    latest_md_content = None
    latest_week_info = None
    
    for (yr, wk), group in weeks_2026:
        group_clean = group[group["text"].str.len() > 10].copy()
        if group_clean.empty:
            continue
            
        md_text = build_weekly_markdown(yr, wk, group_clean)
        
        out_fname = f"fearnleys_weekly_commentary_week_{wk:02d}_{yr}.md"
        
        target_dir1 = REPORTS_DIR / str(yr)
        target_dir2 = DATA_REPORTS_DIR / str(yr)
        target_dir1.mkdir(parents=True, exist_ok=True)
        target_dir2.mkdir(parents=True, exist_ok=True)
        
        p1 = target_dir1 / out_fname
        p2 = target_dir2 / out_fname
        
        p1.write_text(md_text, encoding="utf-8")
        p2.write_text(md_text, encoding="utf-8")
        
        total_generated += 1
        latest_md_content = md_text
        latest_week_info = (yr, wk)
        
    print(f"Successfully generated {total_generated} weekly commentary Markdown reports for 2026.")
    
    if latest_md_content and latest_week_info:
        yr, wk = latest_week_info
        latest_path1 = REPO_ROOT / "reports" / "fearnleys" / "fearnleys_latest_weekly_commentary.md"
        latest_path2 = REPO_ROOT / "data" / "reports" / "fearnleys" / "fearnleys_latest_weekly_commentary.md"
        latest_path1.parent.mkdir(parents=True, exist_ok=True)
        latest_path2.parent.mkdir(parents=True, exist_ok=True)
        
        latest_path1.write_text(latest_md_content, encoding="utf-8")
        latest_path2.write_text(latest_md_content, encoding="utf-8")
        print(f"Updated latest weekly commentary pointer: Week {wk:02d}, {yr} -> {latest_path1}")

if __name__ == "__main__":
    main()
