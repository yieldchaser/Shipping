"""
Drewry AIS Analytics End-to-End Extraction Pipeline.

Extracts weekly Drewry AIS Fleet Performance & Congestion Reports across all 10 vessel classes:
  - Crude: Aframax, Suezmax, VLCC
  - Drybulk: Capesize, Panamax, Supramax, Handysize
  - Product: LR1, LR2
  - LPG: FR (Fully Refrigerated)

Zero Data Loss:
  - Parses each PDF using LlamaParse agentic tier with multi-account automatic rotation.
  - Extracts full Markdown, structured tables/KPI sidecars, and master stacked vessel time-series.
  - Generates dedicated vessel-segregated series CSVs in data/extracted/series/.
"""

import os
import sys
import re
import json
import logging
from pathlib import Path
from collections import defaultdict
import pandas as pd

# Add repo root to pythonpath
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.extract.llama_manager import manager, get_active_parser

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("DrewryAIS")

CACHE_DIR = REPO_ROOT / "data" / "extracted" / "llamaparse_drewry_ais"
MD_BASE_DIR = REPO_ROOT / "data" / "extracted" / "md" / "drewry" / "ais"
SERIES_DIR = REPO_ROOT / "data" / "extracted" / "series"
STATE_FILE = CACHE_DIR / "_run_state.json"

VESSEL_CATEGORIES = [
    "Crude_Aframax",
    "Crude_Suezmax",
    "Crude_VLCC",
    "Drybulk_Capesize",
    "Drybulk_Panamax",
    "Drybulk_Supramax",
    "Drybulk_Handysize",
    "Product_LR1",
    "Product_LR2",
    "LPG_FR"
]


def load_run_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"done": {}, "failed": {}}


def save_run_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def classify_vessel(filename: str) -> str:
    name = filename
    if "Capesize" in name:
        return "Drybulk_Capesize"
    elif "Panamax" in name:
        return "Drybulk_Panamax"
    elif "Supramax" in name:
        return "Drybulk_Supramax"
    elif "Handysize" in name:
        return "Drybulk_Handysize"
    elif "VLCC" in name:
        return "Crude_VLCC"
    elif "Suezmax" in name:
        return "Crude_Suezmax"
    elif "Aframax" in name:
        return "Crude_Aframax"
    elif "LR1" in name:
        return "Product_LR1"
    elif "LR2" in name:
        return "Product_LR2"
    elif "LPG" in name or "FR" in name:
        return "LPG_FR"
    return "Unknown"


def parse_date_week_year(filename: str, page1_text: str = "") -> tuple:
    # Match from filename first
    m_wk = re.search(r'Week(\d+)_(\d{4})', filename)
    week = int(m_wk.group(1)) if m_wk else None
    year = int(m_wk.group(2)[:4]) if m_wk else None

    # Match published date from page 1 text
    pub_date = None
    if page1_text:
        m_pub = re.search(r'Published on:\s*([0-9]{1,2}\s+[A-Za-z]+,?\s+[0-9]{4})', page1_text)
        if m_pub:
            try:
                dt = pd.to_datetime(m_pub.group(1))
                pub_date = dt.strftime("%Y-%m-%d")
            except Exception:
                pass
        if not week:
            m_w = re.search(r'Week\s*(\d+)', page1_text)
            if m_w: week = int(m_w.group(1))
        if not year:
            m_y = re.search(r'(202[4-6])', page1_text)
            if m_y: year = int(m_y.group(1))

    # If pub_date is still missing, estimate from year and week
    if not pub_date and year and week:
        # Standard ISO week Monday
        try:
            pub_date = pd.to_datetime(f"{year}-W{week:02d}-1", format="%Y-W%W-%w").strftime("%Y-%m-%d")
        except Exception:
            pub_date = f"{year}-01-01"

    return pub_date, week, year


def parse_drewry_pdf_with_llamaparse(pdf_path: Path) -> list:
    """
    Parses a Drewry AIS PDF using LlamaParse agentic tier with auto-rotation.
    Returns list of page doc objects with text and metadata.
    """
    stem = pdf_path.stem
    cache_json = CACHE_DIR / f"{stem}.json"
    
    if cache_json.exists():
        try:
            data = json.loads(cache_json.read_text(encoding="utf-8"))
            return data.get("pages", [])
        except Exception:
            pass

    max_retries = 3
    for attempt in range(max_retries):
        try:
            parser = get_active_parser(tier="agentic", version="latest")
            docs = parser.load_data(str(pdf_path))
            if not docs or len(docs) == 0:
                raise RuntimeError("Empty docs returned from LlamaParse - quota exceeded or credit limit")
            pages = [{"page": i + 1, "text": d.text} for i, d in enumerate(docs)]
            
            # Save cache
            cache_json.parent.mkdir(parents=True, exist_ok=True)
            cache_json.write_text(json.dumps({"file": pdf_path.name, "pages": pages}, indent=2), encoding="utf-8")
            manager.record_success(num_pages=len(pages))
            return pages
        except Exception as e:
            err_msg = str(e).lower()
            if any(term in err_msg for term in ["429", "quota", "payment required", "credit", "limit exceeded", "exhausted"]):
                logger.warning(f"Quota exceeded on key {manager.get_current_account_info()['name']}: {e}. Swapping key...")
                manager.mark_key_exhausted(reason=str(e))
            else:
                logger.error(f"Error parsing {pdf_path.name}: {e}")
                if attempt == max_retries - 1:
                    raise e


def extract_metrics_from_pages(pages: list, pdf_name: str, vessel_cat: str) -> dict:
    full_text = "\n\n--- PAGE BREAK ---\n\n".join([p.get("text", "") for p in pages])
    p1_text = pages[0].get("text", "") if pages else ""
    pub_date, week, year = parse_date_week_year(pdf_name, p1_text)

    sector = vessel_cat.split("_")[0]
    vessel_class = vessel_cat.split("_")[1]

    record = {
        "published_date": pub_date,
        "report_year": year,
        "report_week": week,
        "sector": sector,
        "vessel_class": vessel_class,
        "vessel_category": vessel_cat,
        "current_utilisation_pct": None,
        "mom_utilisation_change_pp": None,
        "yoy_utilisation_change_pp": None,
        "tonne_miles_index": None,
        "tonne_miles_yoy_pct": None,
        "bunker_price_usd_per_t": None,
        "bunker_price_mom_pct": None,
        "ballast_speed_east_mom_pct": None,
        "ballast_speed_west_mom_pct": None,
        "anchor_4w_ma_change_mdwt": None,
        "laden_anchor_days_4w_change_pct": None,
        "laden_share_east_mom_pp": None,
        "laden_share_west_mom_pp": None,
        "commentary_title": "",
        "commentary_summary": "",
        "source_file": pdf_name
    }

    # Search page 2 / overview for Utilisation
    for p in pages[:3]:
        txt = p.get("text", "")
        # Utilisation
        m_util = re.search(r'\*{0,2}(\d{1,2}\.?\d*)%\*{0,2}\s*[\r\n]+\s*\*{0,2}Current\s+Utilisation\*{0,2}', txt, re.IGNORECASE)
        if not m_util:
            m_util = re.search(r'Current\s+Utilisation[:\s*]+\*{0,2}(\d{1,2}\.?\d*)%', txt, re.IGNORECASE)
        if not m_util:
            m_util = re.search(r'\*{0,2}(\d{1,2}\.?\d*)%\*{0,2}\s*\n\s*Current\s+Utilisation', txt, re.IGNORECASE)
        if m_util and record["current_utilisation_pct"] is None:
            record["current_utilisation_pct"] = float(m_util.group(1))

        # MoM utilisation change
        m_mom = re.search(r'([▲▼\-+]?\s*[\d\.]+)\s*[\r\n]+\s*\*{0,2}MoM percentage point\s+change in utilisation\*{0,2}', txt, re.IGNORECASE)
        if m_mom and record["mom_utilisation_change_pp"] is None:
            val_str = m_mom.group(1).replace(" ", "")
            sign = -1.0 if any(s in val_str for s in ["▼", "-"]) else 1.0
            val_num = re.search(r'[\d\.]+', val_str)
            if val_num: record["mom_utilisation_change_pp"] = sign * float(val_num.group(0))

        # YoY utilisation change
        m_yoy = re.search(r'([▲▼\-+]?\s*[\d\.]+)\s*[\r\n]+\s*\*{0,2}YoY percentage point\s+change in utilisation\*{0,2}', txt, re.IGNORECASE)
        if m_yoy and record["yoy_utilisation_change_pp"] is None:
            val_str = m_yoy.group(1).replace(" ", "")
            sign = -1.0 if any(s in val_str for s in ["▼", "-"]) else 1.0
            val_num = re.search(r'[\d\.]+', val_str)
            if val_num: record["yoy_utilisation_change_pp"] = sign * float(val_num.group(0))

        # Commentary
        skip_headers = ["utilisation", "ais analytics", "fleet performance", "glossary", "speed", "vessel deployment", "vessel availability", "congestion", "table of contents", "overview"]
        for m_comm in re.finditer(r'##\s+([A-Za-z0-9\s,\'’–\-:]+)\n\n([\s\S]+?)(?=\n##|\Z)', txt):
            cand_title = m_comm.group(1).strip()
            if not any(skip in cand_title.lower() for skip in skip_headers) and len(cand_title) > 10 and not record["commentary_title"]:
                record["commentary_title"] = cand_title
                bullets = [b.strip().lstrip("*-•● ") for b in m_comm.group(2).split("\n") if b.strip().startswith(("*", "-", "•", "●"))]
                record["commentary_summary"] = " | ".join(bullets)

    # Search pages for Tonne-Miles Index, Bunkers, Speeds, Congestion
    for p in pages:
        txt = p.get("text", "")
        # Tonne-miles index
        m_tmi = re.search(r'\*{0,2}(\d{2,3}\.?\d*)\*{0,2}\s*[\r\n]+\s*\*{0,2}Current\s+tonne-miles\s+index\*{0,2}', txt, re.IGNORECASE)
        if not m_tmi:
            m_tmi = re.search(r'Current\s+tonne-miles\s+index[:\s*]+\*{0,2}(\d{2,3}\.?\d*)', txt, re.IGNORECASE)
        if m_tmi and record["tonne_miles_index"] is None:
            record["tonne_miles_index"] = float(m_tmi.group(1))

        # YoY Tonne-miles
        m_tmi_yoy = re.search(r'([▲▼\-+]?\s*[\d\.]+)%\s*[\r\n]+\s*\*{0,2}YoY\s+change in tonne-miles index\*{0,2}', txt, re.IGNORECASE)
        if m_tmi_yoy and record["tonne_miles_yoy_pct"] is None:
            val_str = m_tmi_yoy.group(1).replace(" ", "")
            sign = -1.0 if any(s in val_str for s in ["▼", "-"]) else 1.0
            val_num = re.search(r'[\d\.]+', val_str)
            if val_num: record["tonne_miles_yoy_pct"] = sign * float(val_num.group(0))

        # Bunker price
        m_bnk = re.search(r'\*{0,2}\$(\d+)\*{0,2}\s*[\r\n]+\s*per tonne price of bunker', txt, re.IGNORECASE)
        if m_bnk and record["bunker_price_usd_per_t"] is None:
            record["bunker_price_usd_per_t"] = float(m_bnk.group(1))

        m_bnk_mom = re.search(r'([▲▼\-+]?\s*[\d\.]+)%\s*[\r\n]+\s*MoM\s+change in bunker price', txt, re.IGNORECASE)
        if m_bnk_mom and record["bunker_price_mom_pct"] is None:
            val_str = m_bnk_mom.group(1).replace(" ", "")
            sign = -1.0 if any(s in val_str for s in ["▼", "-"]) else 1.0
            val_num = re.search(r'[\d\.]+', val_str)
            if val_num: record["bunker_price_mom_pct"] = sign * float(val_num.group(0))

        # Ballast speed East & West
        m_spe = re.search(r'([▲▼\-+]?\s*[\d\.]+)%\s*[\r\n]+\s*MoM\s+change in ballast speed in East', txt, re.IGNORECASE)
        if m_spe and record["ballast_speed_east_mom_pct"] is None:
            val_str = m_spe.group(1).replace(" ", "")
            sign = -1.0 if any(s in val_str for s in ["▼", "-"]) else 1.0
            val_num = re.search(r'[\d\.]+', val_str)
            if val_num: record["ballast_speed_east_mom_pct"] = sign * float(val_num.group(0))

        m_spw = re.search(r'([▲▼\-+]?\s*[\d\.]+)%\s*[\r\n]+\s*MoM\s+change in ballast speed in West', txt, re.IGNORECASE)
        if m_spw and record["ballast_speed_west_mom_pct"] is None:
            val_str = m_spw.group(1).replace(" ", "")
            sign = -1.0 if any(s in val_str for s in ["▼", "-"]) else 1.0
            val_num = re.search(r'[\d\.]+', val_str)
            if val_num: record["ballast_speed_west_mom_pct"] = sign * float(val_num.group(0))

        # Tonnage at anchor 4W MA
        m_anc = re.search(r'([▲▼\-+]?\s*[\d\.]+)\s*[\r\n]+\s*mdwt change in tonnage at anchor \(4-week moving average\)', txt, re.IGNORECASE)
        if m_anc and record["anchor_4w_ma_change_mdwt"] is None:
            val_str = m_anc.group(1).replace(" ", "")
            sign = -1.0 if any(s in val_str for s in ["▼", "-"]) else 1.0
            val_num = re.search(r'[\d\.]+', val_str)
            if val_num: record["anchor_4w_ma_change_mdwt"] = sign * float(val_num.group(0))

        # Laden anchor days 4W MA change
        m_lad = re.search(r'([▲▼\-+]?\s*[\d\.]+)%\s*[\r\n]+\s*change in laden anchor days \(4-week moving average\)', txt, re.IGNORECASE)
        if m_lad and record["laden_anchor_days_4w_change_pct"] is None:
            val_str = m_lad.group(1).replace(" ", "")
            sign = -1.0 if any(s in val_str for s in ["▼", "-"]) else 1.0
            val_num = re.search(r'[\d\.]+', val_str)
            if val_num: record["laden_anchor_days_4w_change_pct"] = sign * float(val_num.group(0))

        # Laden share East & West
        m_lse = re.search(r'([▲▼\-+]?\s*[\d\.]+)\s*[\r\n]+\s*MoM percentage point change in the share of laden vessels in East', txt, re.IGNORECASE)
        if m_lse and record["laden_share_east_mom_pp"] is None:
            val_str = m_lse.group(1).replace(" ", "")
            sign = -1.0 if any(s in val_str for s in ["▼", "-"]) else 1.0
            val_num = re.search(r'[\d\.]+', val_str)
            if val_num: record["laden_share_east_mom_pp"] = sign * float(val_num.group(0))

        m_lsw = re.search(r'([▲▼\-+]?\s*[\d\.]+)\s*[\r\n]+\s*MoM percentage point change in the share of laden vessels in West', txt, re.IGNORECASE)
        if m_lsw and record["laden_share_west_mom_pp"] is None:
            val_str = m_lsw.group(1).replace(" ", "")
            sign = -1.0 if any(s in val_str for s in ["▼", "-"]) else 1.0
            val_num = re.search(r'[\d\.]+', val_str)
            if val_num: record["laden_share_west_mom_pp"] = sign * float(val_num.group(0))

    return record


from concurrent.futures import ThreadPoolExecutor, as_completed


def process_single_pdf(pdf_path: Path, cat: str) -> dict:
    stem = pdf_path.stem
    try:
        pages = parse_drewry_pdf_with_llamaparse(pdf_path)
        
        # Save structured markdown file
        md_dir = MD_BASE_DIR / cat
        md_dir.mkdir(parents=True, exist_ok=True)
        md_path = md_dir / f"{stem}.md"
        
        full_md = "\n\n--- PAGE BREAK ---\n\n".join([f"<!-- Page {p['page']} -->\n{p['text']}" for p in pages])
        md_path.write_text(full_md, encoding="utf-8")

        # Extract metrics
        record = extract_metrics_from_pages(pages, pdf_path.name, cat)

        # Save table sidecar JSON
        sidecar_path = md_dir / f"{stem}.tables.json"
        sidecar_path.write_text(json.dumps(record, indent=2), encoding="utf-8")

        logger.info(f"[{cat}] DONE: {pdf_path.name} | Util: {record.get('current_utilisation_pct')}%")
        return {"stem": stem, "record": record, "pages": len(pages), "cat": cat}
    except Exception as e:
        logger.error(f"[{cat}] FAILED {pdf_path.name}: {e}")
        return {"stem": stem, "error": str(e), "cat": cat}


def run_pipeline():
    ais_dir = REPO_ROOT / "corpus" / "06-drewry" / "ais"
    pdf_files = sorted(list(ais_dir.glob("*.pdf")))
    logger.info(f"Found {len(pdf_files)} Drewry AIS PDFs to process.")

    state = load_run_state()
    done = state.get("done", {})

    # Segregate by vessel category
    vessel_files = defaultdict(list)
    for f in pdf_files:
        cat = classify_vessel(f.name)
        vessel_files[cat].append(f)

    logger.info("Vessel breakdown:")
    for cat in VESSEL_CATEGORIES:
        logger.info(f"  {cat}: {len(vessel_files[cat])} PDFs")

    # Process each category strictly in isolation
    for cat in VESSEL_CATEGORIES:
        flist = vessel_files[cat]
        logger.info(f"\n=======================================================")
        logger.info(f"STARTING VESSEL CATEGORY: {cat} ({len(flist)} PDFs)")
        logger.info(f"=======================================================")

        category_records = []
        
        # Filter files already done
        remaining = [f for f in flist if f.stem not in done]
        already_done = [f for f in flist if f.stem in done]
        
        # Load and refresh cached records for already done
        for f in already_done:
            cache_json = CACHE_DIR / f"{f.stem}.json"
            if cache_json.exists():
                try:
                    data = json.loads(cache_json.read_text(encoding="utf-8"))
                    pages = data.get("pages", [])
                    if pages:
                        rec = extract_metrics_from_pages(pages, f.name, cat)
                        category_records.append(rec)
                        sidecar = MD_BASE_DIR / cat / f"{f.stem}.tables.json"
                        sidecar.write_text(json.dumps(rec, indent=2), encoding="utf-8")
                        if f.stem in done:
                            done[f.stem]["utilisation"] = rec.get("current_utilisation_pct")
                        continue
                except Exception:
                    pass
            sidecar = MD_BASE_DIR / cat / f"{f.stem}.tables.json"
            if sidecar.exists():
                try:
                    category_records.append(json.loads(sidecar.read_text(encoding="utf-8")))
                except Exception:
                    remaining.append(f)
            else:
                remaining.append(f)

        state["done"] = done
        save_run_state(state)

        logger.info(f"[{cat}] Already cached: {len(category_records)} | To process: {len(remaining)}")

        if remaining:
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = {executor.submit(process_single_pdf, f, cat): f for f in remaining}
                for fut in as_completed(futures):
                    res = fut.result()
                    stem = res.get("stem")
                    if "error" in res:
                        state.setdefault("failed", {})[stem] = res["error"]
                    else:
                        category_records.append(res["record"])
                        done[stem] = {
                            "timestamp": pd.Timestamp.now(tz="UTC").isoformat(),
                            "category": cat,
                            "pages": res["pages"],
                            "utilisation": res["record"].get("current_utilisation_pct")
                        }
                    state["done"] = done
                    save_run_state(state)

        # Build vessel-segregated series CSV immediately after category finishes
        if category_records:
            df = pd.DataFrame(category_records)
            df = df.sort_values(by=["report_year", "report_week", "published_date"]).reset_index(drop=True)
            csv_path = SERIES_DIR / f"drewry_ais_{cat.lower()}_series.csv"
            df.to_csv(csv_path, index=False)
            logger.info(f"Successfully wrote {len(df)} rows to {csv_path.name}!")

    logger.info("Drewry AIS pipeline complete across all 10 vessel classes.")


if __name__ == "__main__":
    run_pipeline()
