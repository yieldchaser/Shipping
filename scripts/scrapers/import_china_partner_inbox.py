#!/usr/bin/env python3
"""
Import China customs imports-by-partner files dropped in data/commodities/inbox/ (see docs/CHINA_PARTNER_DATA_GAP.md).

stats.customs.gov.cn (the official GACC query platform) is the only free source of China's imports by HS code and
partner country, and it answers scripts with a JavaScript challenge. A CSV exported from it (or any equivalent
file) dropped as data/commodities/inbox/china_partner_imports_<YYYY-MM>.csv is joined to the stored series here:

  china_customs_monthly_imports.csv    one row per (month, HS): total USD, partner count, top-3 partners and shares
  china_customs_partners_summary.json  latest_month / latest_partners / all-time partner totals per HS
  guinea_bauxite_exports.csv           HS 26060000 from Guinea: tonnes and CIF USD/t (outranks the SMM print)
  minor_bulks_monthly.csv              HS 28182000 China total alumina imports: tonnes and USD

Accepted columns (English, or the GACC export's Chinese headers):
  month | 数据年月          YYYY-MM or YYYYMM
  hs_code | 商品编码       the stored series keys are 2601 2701 2709 2711 1201 3102 3105 72 26060000 28182000; longer
                           codes are summed into the key they start with
  partner | 贸易伙伴名称
  quantity | 第一数量       with quantity_unit | 第一计量单位 (千克/kg or 吨/t)
  value_usd | 美元
Processed files move to data/commodities/inbox/processed/. Nothing is estimated: a month is written only from a file.
"""
import csv
import json
import logging
import re
import shutil
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
ROOT = Path(__file__).resolve().parent.parent.parent
CDIR = ROOT / "data" / "commodities"
INBOX = CDIR / "inbox"
HS_CSV = CDIR / "china_customs_monthly_imports.csv"
SUMMARY = CDIR / "china_customs_partners_summary.json"
GUINEA_CSV = CDIR / "guinea_bauxite_exports.csv"
MINOR_CSV = CDIR / "minor_bulks_monthly.csv"
KEYS = ["26060000", "28182000", "2601", "2701", "2709", "2711", "1201", "3102", "3105", "72"]   # longest first
COLS = {
    "month": ("month", "数据年月", "date", "period"),
    "hs_code": ("hs_code", "商品编码", "hs", "commodity_code"),
    "partner": ("partner", "贸易伙伴名称", "country", "partner_name"),
    "quantity": ("quantity", "第一数量", "qty"),
    "quantity_unit": ("quantity_unit", "第一计量单位", "unit"),
    "value_usd": ("value_usd", "美元", "usd", "value"),
}
PARTNER_EN = {
    "几内亚": "Guinea", "澳大利亚": "Australia", "巴西": "Brazil", "印度尼西亚": "Indonesia", "俄罗斯联邦": "Russia",
    "蒙古": "Mongolia", "沙特阿拉伯": "Saudi Arabia", "伊拉克": "Iraq", "马来西亚": "Malaysia", "美国": "United States",
    "南非": "South Africa", "印度": "India", "秘鲁": "Peru", "加拿大": "Canada", "卡塔尔": "Qatar", "阿曼": "Oman",
    "阿拉伯联合酋长国": "United Arab Emirates", "安哥拉": "Angola", "科威特": "Kuwait", "巴布亚新几内亚": "Papua New Guinea",
    "土库曼斯坦": "Turkmenistan", "哈萨克斯坦": "Kazakhstan", "阿根廷": "Argentina", "乌克兰": "Ukraine", "智利": "Chile",
    "毛里塔尼亚": "Mauritania", "塞拉利昂": "Sierra Leone", "圭亚那": "Guyana", "土耳其": "Turkey", "加纳": "Ghana",
    "牙买加": "Jamaica", "越南": "Vietnam", "日本": "Japan", "韩国": "South Korea", "挪威": "Norway", "白俄罗斯": "Belarus",
    "以色列": "Israel", "约旦": "Jordan", "老挝": "Laos", "菲律宾": "Philippines", "新西兰": "New Zealand", "伊朗": "Iran",
}


def _col(header: list[str], key: str) -> str:
    for name in COLS[key]:
        for h in header:
            if h.strip().lower() == name.lower():
                return h
    raise ValueError(f"column for {key!r} not found (accepted: {', '.join(COLS[key])})")


def read_inbox(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as fh:
        rd = csv.DictReader(fh)
        h = rd.fieldnames or []
        c = {k: _col(h, k) for k in ("month", "hs_code", "partner", "value_usd")}
        cq = {k: next((x for x in h for n in COLS[k] if x.strip().lower() == n.lower()), None)
              for k in ("quantity", "quantity_unit")}
        out = []
        for r in rd:
            m = re.sub(r"\D", "", r[c["month"]])
            hs = re.sub(r"\D", "", r[c["hs_code"]])
            key = next((k for k in KEYS if hs.startswith(k)), None)
            if len(m) < 6 or not key:
                continue
            usd = float(str(r[c["value_usd"]]).replace(",", "") or 0)
            qty = None
            if cq["quantity"] and r.get(cq["quantity"], "").strip():
                q = float(str(r[cq["quantity"]]).replace(",", ""))
                unit = (r.get(cq["quantity_unit"]) or "").strip().lower() if cq["quantity_unit"] else ""
                qty = q / 1000.0 if unit in ("千克", "kg", "kilogram", "kilograms") else q if unit in ("吨", "t", "ton", "tons", "tonnes") else None
            partner = r[c["partner"]].strip()
            out.append({"month": f"{m[:4]}-{m[4:6]}", "key": key, "partner": PARTNER_EN.get(partner, partner),
                        "usd": usd, "tonnes": qty})
    return out


def main() -> int:
    files = sorted(INBOX.glob("*.csv")) if INBOX.exists() else []
    if not files:
        logging.info("inbox empty: nothing to import")
        return 0
    agg = defaultdict(lambda: defaultdict(lambda: {"usd": 0.0, "tonnes": 0.0, "has_t": True}))
    for f in files:
        rows = read_inbox(f)
        logging.info("%s: %d usable rows", f.name, len(rows))
        for r in rows:
            a = agg[(r["month"], r["key"])][r["partner"]]
            a["usd"] += r["usd"]
            if r["tonnes"] is None:
                a["has_t"] = False
            else:
                a["tonnes"] += r["tonnes"]

    with open(HS_CSV, encoding="utf-8", newline="") as fh:
        rd = csv.DictReader(fh)
        hs_fields, hs_rows = list(rd.fieldnames), list(rd)
    template = {r["hs_code"]: r for r in hs_rows}
    stored = {(r["date"][:7], r["hs_code"]) for r in hs_rows}
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    src = "GACC query export (stats.customs.gov.cn) via data/commodities/inbox"
    added = 0
    for (month, key), partners in sorted(agg.items()):
        total = sum(p["usd"] for p in partners.values())
        if total <= 0 or key not in template:
            continue
        ranked = sorted(partners.items(), key=lambda kv: -kv[1]["usd"])
        top = [f"{n} ({100 * p['usd'] / total:.1f}%)" for n, p in ranked[:3]] + ["", "", ""]
        row = dict(template[key])
        row.update({"date": f"{month}-01", "value_usd": f"{total:.1f}", "partner_count": str(len(partners)),
                    "top_partner_1": top[0], "top_partner_2": top[1], "top_partner_3": top[2],
                    "source_url": "http://stats.customs.gov.cn/", "publisher": "General Administration of Customs (GACC)",
                    "method": src})
        hs_rows = [r for r in hs_rows if not (r["date"][:7] == month and r["hs_code"] == key)]
        hs_rows.append(row)
        added += (month, key) not in stored
        s = summary["commodities"].get(key)
        if s and month >= (s.get("latest_month") or ""):
            s["latest_month"] = month
            s.setdefault("coverage", {})["latest_month"] = month
            s["latest_partners"] = [{"partner": n, "share_pct": round(100 * p["usd"] / total, 2),
                                     "value_usd": round(p["usd"]), "rank": i + 1} for i, (n, p) in enumerate(ranked[:10])]
            s["source_url"] = "http://stats.customs.gov.cn/"
        # Guinea bauxite mirror and alumina tonnes
        if key == "26060000" and "Guinea" in partners and partners["Guinea"]["has_t"]:
            upsert_guinea(month, partners["Guinea"])
        if key == "28182000" and all(p["has_t"] for p in partners.values()):
            upsert_alumina(month, sum(p["tonnes"] for p in partners.values()), total)
    hs_rows.sort(key=lambda r: (r["commodity"], r["date"]))
    with open(HS_CSV, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=hs_fields, lineterminator="\n")
        w.writeheader()
        w.writerows(hs_rows)
    summary["generated_at"] = datetime.now(timezone.utc).isoformat()
    summary["api_provider"] = "chinadata.live / api/v2 to 2026-08; GACC query exports via inbox after"
    SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    done = INBOX / "processed"
    done.mkdir(exist_ok=True)
    for f in files:
        shutil.move(str(f), done / f.name)
    logging.info("imported %d (month, HS) totals (%d new); files moved to %s", len(agg), added, done)
    return 0


def upsert_guinea(month: str, g: dict) -> None:
    with open(GUINEA_CSV, encoding="utf-8", newline="") as fh:
        rd = csv.DictReader(fh)
        fields, rows = list(rd.fieldnames), list(rd)
    cif = g["usd"] / g["tonnes"] if g["tonnes"] else None
    new = {k: "" for k in fields}
    new.update({"date": f"{month}-01", "tonnes": f"{g['tonnes']:.1f}", "import_volume_t": f"{g['tonnes']:.1f}",
                "company": "Bilateral Mirror (China Imports from Guinea)",
                "source_url": "http://stats.customs.gov.cn/queryData/queryDataNew",
                "publisher": "General Administration of Customs of China (GACC)",
                "source_quote": f"GACC HS 26060000 Guinea: {g['tonnes']:,.1f} t, US${g['usd']:,.0f}" + (f" (CIF ${cif:.2f}/t)" if cif else ""),
                "method": "GACC query export (inbox) - HS 26060000", "avg_cif_usd_t": f"{cif:.2f}" if cif else "",
                "granularity": "monthly_bilateral_mirror"})
    rows = [r for r in rows if not (r.get("granularity") == "monthly_bilateral_mirror" and r["date"] == new["date"])]
    rows.append(new)
    rows.sort(key=lambda r: r.get("date", ""))
    with open(GUINEA_CSV, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def upsert_alumina(month: str, tonnes: float, usd: float) -> None:
    with open(MINOR_CSV, encoding="utf-8", newline="") as fh:
        rd = csv.DictReader(fh)
        fields, rows = list(rd.fieldnames), list(rd)
    rows = [r for r in rows if not (r.get("commodity") == "Alumina" and r.get("reporter_country") == "China"
                                    and r["date"] == f"{month}-01")]
    new = {k: "" for k in fields}
    new.update({"date": f"{month}-01", "period": month.replace("-", ""), "commodity": "Alumina", "trade_flow": "Imports",
                "reporter_country": "China", "partner_country": "World", "hs_code": "2818",
                "metric_tonnes": f"{tonnes:.2f}", "value_usd": f"{usd:.1f}", "vessel_demand_impact": "Handymax / Supramax",
                "source": "China GACC (HS 28182000, query export via inbox)", "source_url": "http://stats.customs.gov.cn"})
    rows.append(new)
    rows.sort(key=lambda x: (x.get("commodity", ""), x.get("date", "")))
    with open(MINOR_CSV, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    sys.exit(main())
