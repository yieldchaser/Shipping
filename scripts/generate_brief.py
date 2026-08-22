"""
Daily shipping market brief generator.

Reads quantitative CSV data + recent Breakwave signals + Baltic roundups + wiki context and writes:
  knowledge/briefs/latest.json
  knowledge/briefs/YYYY-MM-DD.json

LLM provider cascade: Groq -> Gemini -> NVIDIA NIM -> OpenRouter -> Ollama.
If all providers fail, a deterministic mathematical template brief is generated.
"""
from __future__ import annotations

import csv
import json
import math
import os
import random
import re
import sys
import time
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib import error as urllib_error
from urllib import request as urllib_request

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE = ROOT / "knowledge"
DERIVED = KNOWLEDGE / "derived"
WIKI = KNOWLEDGE / "wiki"
BRIEFS = KNOWLEDGE / "briefs"

SIGNALS_FILE = DERIVED / "signals.jsonl"

# CSV files: key -> path  (DD-MM-YYYY, Index, %Change)
ETF_HOLDINGS_FILES = {
    "bdry": ROOT / "data" / "etf" / "bdry_holdings.csv",
    "bwet": ROOT / "data" / "etf" / "bwet_holdings.csv",
}
SGX_CURVE_FILES = {
    "cape": ROOT / "data" / "futures" / "sgx_cape_futures.csv",
    "panamax": ROOT / "data" / "futures" / "sgx_panamax_futures.csv",
    "supramax": ROOT / "data" / "futures" / "sgx_supramax_futures.csv",
    "handysize": ROOT / "data" / "futures" / "sgx_handysize_futures.csv",
}

CSV_FILES = {
    "bdi": ROOT / "data" / "indices" / "bdiy_historical.csv",
    "capesize": ROOT / "data" / "indices" / "cape_historical.csv",
    "panamax": ROOT / "data" / "indices" / "panama_historical.csv",
    "supramax": ROOT / "data" / "indices" / "suprama_historical.csv",
    "handysize": ROOT / "data" / "indices" / "handysize_historical.csv",
    "clean_tanker": ROOT / "data" / "indices" / "cleantanker_historical.csv",
    "dirty_tanker": ROOT / "data" / "indices" / "dirtytanker_historical.csv",
}

WIKI_EXCERPTS = {
    "dry_bulk": WIKI / "dry_bulk_market.md",
    "capesize": WIKI / "capesize.md",
    "tanker": WIKI / "tanker_market.md",
}

CONFLUENCE_TYPES = {"BULL_CONFLUENCE", "BEAR_CONFLUENCE", "DIVERGENCE", "NEUTRAL"}
RECENT_REPORTS = 6  # Breakwave reports per sector (6 ≈ 6-8 weeks of analysis)
BALTIC_REPORTS = 2  # Baltic Exchange weekly reports (2 weeks of vessel-class detail)

# Baltic Exchange weekly HTML report directories
BALTIC_DRY_DIR = ROOT / "reports" / "baltic" / "dry"
BALTIC_TANKER_DIR = ROOT / "reports" / "baltic" / "tanker"


OLLAMA_API_KEY = os.environ.get("OLLAMA_API_KEY", "").strip()
OLLAMA_MODEL = (os.environ.get("OLLAMA_MODEL") or "deepseek-v4-flash:cloud").strip()
OLLAMA_BASE_URL = (os.environ.get("OLLAMA_BASE_URL") or "https://api.ollama.com/v1").strip().rstrip("/")
OLLAMA_MIN_INTERVAL_SEC = float(os.environ.get("OLLAMA_MIN_INTERVAL_SEC", "1.5"))
OLLAMA_MAX_RETRIES = int(os.environ.get("OLLAMA_MAX_RETRIES", "3"))
OLLAMA_BACKOFF_BASE_SEC = float(os.environ.get("OLLAMA_BACKOFF_BASE_SEC", "1.5"))
OLLAMA_MAX_BACKOFF_SEC = float(os.environ.get("OLLAMA_MAX_BACKOFF_SEC", "15.0"))

NIM_API_KEY = (os.environ.get("NIM_API_KEY") or os.environ.get("NVIDIA_API_KEY") or "").strip()
NIM_MODEL = (os.environ.get("NIM_MODEL") or "meta/llama-3.3-70b-instruct").strip()
NIM_BASE_URL = (os.environ.get("NIM_BASE_URL") or "https://integrate.api.nvidia.com/v1").strip().rstrip("/")
NIM_MIN_INTERVAL_SEC = float(os.environ.get("NIM_MIN_INTERVAL_SEC", "1.5"))
NIM_MAX_RETRIES = int(os.environ.get("NIM_MAX_RETRIES", "3"))
NIM_BACKOFF_BASE_SEC = float(os.environ.get("NIM_BACKOFF_BASE_SEC", "1.5"))
NIM_MAX_BACKOFF_SEC = float(os.environ.get("NIM_MAX_BACKOFF_SEC", "15.0"))

GROQ_API_KEY = (os.environ.get("GROQ_API_KEY") or "").strip()
GROQ_MODEL = (os.environ.get("GROQ_MODEL") or "openai/gpt-oss-120b").strip()
GROQ_BASE_URL = (os.environ.get("GROQ_BASE_URL") or "https://api.groq.com/openai/v1").strip().rstrip("/")
GROQ_MIN_INTERVAL_SEC = float(os.environ.get("GROQ_MIN_INTERVAL_SEC", "1.5"))
GROQ_MAX_RETRIES = int(os.environ.get("GROQ_MAX_RETRIES", "3"))
GROQ_BACKOFF_BASE_SEC = float(os.environ.get("GROQ_BACKOFF_BASE_SEC", "1.5"))
GROQ_MAX_BACKOFF_SEC = float(os.environ.get("GROQ_MAX_BACKOFF_SEC", "15.0"))

GEMINI_API_KEY = (os.environ.get("GEMINI_API_KEY") or "").strip()
GEMINI_MODEL = (os.environ.get("GEMINI_MODEL") or "gemini-2.5-flash").strip()
GEMINI_MIN_INTERVAL_SEC = float(os.environ.get("GEMINI_MIN_INTERVAL_SEC", "1.5"))
GEMINI_MAX_RETRIES = int(os.environ.get("GEMINI_MAX_RETRIES", "3"))
GEMINI_BACKOFF_BASE_SEC = float(os.environ.get("GEMINI_BACKOFF_BASE_SEC", "1.5"))
GEMINI_MAX_BACKOFF_SEC = float(os.environ.get("GEMINI_MAX_BACKOFF_SEC", "15.0"))

OPENROUTER_API_KEY = (os.environ.get("OPENROUTER_API_KEY") or "").strip()
OPENROUTER_MODEL = (os.environ.get("OPENROUTER_MODEL") or "meta-llama/llama-3.3-70b-instruct").strip()
OPENROUTER_BASE_URL = (os.environ.get("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1").strip().rstrip("/")
OPENROUTER_MIN_INTERVAL_SEC = float(os.environ.get("OPENROUTER_MIN_INTERVAL_SEC", "1.5"))
OPENROUTER_MAX_RETRIES = int(os.environ.get("OPENROUTER_MAX_RETRIES", "3"))
OPENROUTER_BACKOFF_BASE_SEC = float(os.environ.get("OPENROUTER_BACKOFF_BASE_SEC", "1.5"))
OPENROUTER_MAX_BACKOFF_SEC = float(os.environ.get("OPENROUTER_MAX_BACKOFF_SEC", "15.0"))

ALLOWED_PROVIDERS = {"groq", "nim", "openrouter", "ollama"}
raw_order = (os.environ.get("LLM_PROVIDER_ORDER") or "").strip()
if not raw_order:
    raw_order = "groq,nim,openrouter,ollama"

LLM_PROVIDER_ORDER = [
    part.strip().lower()
    for part in raw_order.split(",")
    if part.strip().lower() in ALLOWED_PROVIDERS
]
if not LLM_PROVIDER_ORDER:
    LLM_PROVIDER_ORDER = ["groq", "nim", "openrouter", "ollama"]

_last_ollama_call_ts = 0.0
_last_nim_call_ts = 0.0
_last_groq_call_ts = 0.0
_last_gemini_call_ts = 0.0
_last_openrouter_call_ts = 0.0

_QUAL_SCORES = {
    "positive": 1.0,
    "constructive": 0.75,
    "cautiously_bullish": 0.5,
    "neutral": 0.0,
    "mixed": 0.0,
    "cautiously_bearish": -0.5,
    "negative": -1.0,
}


for stream_name in ("stdout", "stderr"):
    stream = getattr(sys, stream_name, None)
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")


# ------------------------ Quantitative helpers ------------------------

def parse_csv_series(path: Path) -> list[float | None]:
    """Parse DD-MM-YYYY,Index,Change CSV -> list of values in chronological order."""
    values: list[float | None] = []
    try:
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.reader(f):
                if len(row) < 2:
                    continue
                raw = row[1].strip()
                try:
                    values.append(float(raw) if raw not in ("", "-", "N/A") else None)
                except ValueError:
                    continue
    except FileNotFoundError:
        pass
    return values


def rolling_mean_std(values: list[float | None], window: int) -> tuple[float | None, float | None]:
    """Mean and population std of the last `window` non-null values."""
    window_vals = [v for v in values[-window:] if v is not None]
    if len(window_vals) < 20:
        return None, None
    mean_value = sum(window_vals) / len(window_vals)
    variance = sum((v - mean_value) ** 2 for v in window_vals) / len(window_vals)
    return mean_value, math.sqrt(variance) if variance > 0 else 0.0


def compute_zscore_252d(values: list[float | None]) -> float | None:
    """Rolling 252-day Z-score of the last value."""
    non_null = [v for v in values if v is not None]
    if not non_null:
        return None
    current = non_null[-1]
    mean_value, std_dev = rolling_mean_std(values, 252)
    if mean_value is None or std_dev is None:
        return None
    return round((current - mean_value) / std_dev, 3) if std_dev > 0 else 0.0


def compute_regime(values: list[float | None]) -> tuple[str, str, float | None, float | None]:
    """
    Matches Momentum Regime logic in index.html:
      MA(200) anchor + ROC(60) velocity.
    Returns (regime, regime_emoji, ma200, roc60_pct).
    """
    non_null = [v for v in values if v is not None]
    if len(non_null) < 201:
        return "INSUFFICIENT_DATA", "N/A", None, None

    current = non_null[-1]
    ma200 = sum(non_null[-200:]) / 200

    if len(non_null) >= 62:
        base = non_null[-61]
        roc60 = ((current - base) / base * 100) if base else 0.0
    else:
        roc60 = 0.0

    if current > ma200 and roc60 > 0:
        regime, regime_emoji = "EXPANSION", "UP"
    elif current > ma200:
        regime, regime_emoji = "DISTRIBUTION", "FLAT"
    elif roc60 > 0:
        regime, regime_emoji = "ACCUMULATION", "RECOVERY"
    else:
        regime, regime_emoji = "CONTRACTION", "DOWN"

    return regime, regime_emoji, round(ma200, 1), round(roc60, 2)


def percentile_5y(values: list[float | None]) -> float | None:
    """5-year (252 * 5 trading days) percentile rank of the last value."""
    non_null = [v for v in values if v is not None]
    if not non_null:
        return None
    current = non_null[-1]
    window = non_null[-(252 * 5) :]
    if not window:
        return None
    return round(sum(1 for v in window if v <= current) / len(window), 3)



def load_etf_holdings_data(fund_key: str) -> list[dict]:
    p = ETF_HOLDINGS_FILES.get(fund_key)
    if not p or not p.exists():
        return []
    holdings = []
    try:
        with open(p, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get("Name", "")
                ticker = row.get("Ticker", "")
                if "Cash" in name or "Portfolio" in name or "AGPXX" in ticker:
                    continue
                try:
                    lots = float(row.get("Lots", 0) or 0)
                    price = float(row.get("Price", 0) or 0)
                    mv = float(row.get("Market_Value", 0) or 0)
                    wt_str = row.get("Weightings", "0%").replace("%", "").strip()
                    wt = float(wt_str) if wt_str else 0.0
                    if lots > 0:
                        holdings.append({
                            "name": name,
                            "ticker": ticker,
                            "lots": lots,
                            "price": price,
                            "market_value": mv,
                            "weight": wt
                        })
                except Exception:
                    continue
    except Exception:
        pass
    return holdings


def parse_curve_date(date_str):
    """Parses SGX curve dates (strict DD-MM-YYYY, ISO fallback) to datetime for
    correct chronological comparison; returns None when unparseable."""
    s = str(date_str or "").strip()
    if not s:
        return None
    try:
        return datetime.strptime(s, "%d-%m-%Y")
    except ValueError:
        pass
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        try:
            return datetime.strptime(s, "%Y-%m-%d")
        except ValueError:
            return None
    return None


def load_sgx_curve_data() -> dict[str, list[dict]]:
    curves: dict[str, list[dict]] = {}
    for cls, p in SGX_CURVE_FILES.items():
        if not p.exists():
            continue
        try:
            contract_map: dict[str, dict] = {}
            with open(p, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    c = row.get("contract")
                    if not c:
                        continue
                    try:
                        px = float(row.get("price", 0) or 0)
                        prev = contract_map.get(c)
                        row_dt = parse_curve_date(row.get("date", ""))
                        prev_dt = parse_curve_date(prev.get("date", "")) if prev else None
                        is_newer = prev is None or (
                            row_dt is not None and prev_dt is not None and row_dt >= prev_dt
                        ) or ((row_dt is None or prev_dt is None) and str(row.get("date", "")) >= str(prev.get("date", "")))
                        if is_newer:
                            contract_map[c] = {
                                "contract": c,
                                "expiry_month": row.get("expiry_month"),
                                "expiry_year": row.get("expiry_year"),
                                "price": px,
                                "date": row.get("date", "")
                            }
                    except Exception:
                        continue
            curves[cls] = list(contract_map.values())
        except Exception:
            pass
    return curves


def compute_etf_curve_metrics(fund_key: str, holdings: list[dict], curves: dict) -> dict:
    if not holdings:
        return {}
    
    # Sort holdings by weight descending
    sorted_h = sorted(holdings, key=lambda x: x.get("weight", 0), reverse=True)
    prompt_h = sorted_h[0] if len(sorted_h) > 0 else {}
    next_h = sorted_h[1] if len(sorted_h) > 1 else {}
    
    prompt_px = prompt_h.get("price", 0.0)
    next_px = next_h.get("price", 0.0)
    
    # Implied monthly roll yield
    roll_spread_pct = 0.0
    regime = "NEUTRAL"
    if prompt_px > 0 and next_px > 0:
        roll_spread_pct = round(((prompt_px - next_px) / prompt_px) * 100, 2)
        regime = "BACKWARDATION_CARRY" if roll_spread_pct > 0 else ("CONTANGO_DRAG" if roll_spread_pct < 0 else "FLAT")
        
    is_bdry = (fund_key.lower() == "bdry")
    summary_30d = (
        f"30-Day Hold: Direct bet on {prompt_h.get('name', 'Prompt')} settling above ${prompt_px:,.0f}/day with {abs(roll_spread_pct):.1f}% monthly {regime.replace('_', ' ').lower()}."
        if is_bdry else
        f"30-Day Hold: Direct bet on {prompt_h.get('name', 'Prompt')} settling above WS {prompt_px:.1f} (~${round(prompt_px*1000):,}/d) with {abs(roll_spread_pct):.1f}% monthly {regime.replace('_', ' ').lower()}."
    )
    summary_90d = (
        f"90-Day Hold: Traverses prompt through Q-strip. Requires spot to beat {abs(roll_spread_pct*3):.1f}% cumulative 3-month {regime.replace('_', ' ').lower()}."
    )
    summary_180d = (
        f"180-Day Hold: Seasonal cycle traversal. Requires seasonal demand peak to overcome cumulative roll friction and 1.45% OER."
    )
    
    return {
        "prompt_contract": prompt_h,
        "next_contract": next_h,
        "implied_roll_yield_pct": roll_spread_pct,
        "curve_regime": regime,
        "holding_bet_summary_30d": summary_30d,
        "holding_bet_summary_90d": summary_90d,
        "holding_bet_summary_180d": summary_180d,
        "total_active_contracts": len(holdings)
    }

def build_market_snapshot() -> dict:
    snapshot: dict[str, dict] = {}
    for name, path in CSV_FILES.items():
        values = parse_csv_series(path)
        non_null = [v for v in values if v is not None]
        if not non_null:
            continue
        current = non_null[-1]
        regime, regime_emoji, ma200, roc60 = compute_regime(values)
        z_score = compute_zscore_252d(values)
        pctl = percentile_5y(values)
        snapshot[name] = {
            "value": round(current, 1),
            "z_score_252d": z_score,
            "pctl_5y": pctl,
            "regime": regime,
            "regime_emoji": regime_emoji,
            "ma200": ma200,
            "roc60": roc60,
        }
    return snapshot


def compute_tanker_z(snapshot: dict) -> float | None:
    clean = snapshot.get("clean_tanker", {}).get("z_score_252d")
    dirty = snapshot.get("dirty_tanker", {}).get("z_score_252d")
    if clean is not None and dirty is not None:
        return round((clean + dirty) / 2, 3)
    return clean if clean is not None else dirty


# ------------------------ Qualitative helpers ------------------------

def load_signals() -> list[dict]:
    signals: list[dict] = []
    try:
        with open(SIGNALS_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    signals.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except FileNotFoundError:
        pass
    return signals


def recent_breakwave(signals: list[dict], category: str, n: int = RECENT_REPORTS) -> list[dict]:
    filtered = [
        signal
        for signal in signals
        if signal.get("source") == "breakwave"
        and signal.get("category") == category
        and signal.get("date", "0000") not in ("0000-00-00", "", None)
        and signal.get("sentiment") is not None
    ]
    filtered.sort(key=lambda x: x.get("date", ""), reverse=True)
    return filtered[:n]


def compute_confluence(
    z_score: float | None,
    sentiments: list[str],
    momentums: list[str] | None = None,
    fundamentals: list[str] | None = None,
) -> str:
    """Classify confluence between quantitative Z-score and qualitative signals.

    Weights: fundamentals 50%, sentiment 30%, momentum 20%.
    Uses exponential decay (0.85^i) on each dimension (newest = highest weight).
    Consistent with JS Signal Engine for the sentiment dimension.
    """
    if not sentiments or z_score is None:
        return "NEUTRAL"

    def _weighted_score(values: list[str]) -> float:
        if not values:
            return 0.0
        decay = 0.85
        weights = [decay ** i for i in range(len(values))]
        return sum(w * _QUAL_SCORES.get((str(v or 'neutral')).lower(), 0.0) for w, v in zip(weights, values)) / sum(weights)

    s_score = _weighted_score(sentiments)
    m_score = _weighted_score(momentums) if momentums else 0.0
    f_score = _weighted_score(fundamentals) if fundamentals else 0.0

    # Composite: fundamentals 50%, sentiment 30%, momentum 20%
    if fundamentals:
        qual_score = 0.50 * f_score + 0.30 * s_score + 0.20 * m_score
    else:
        # Fallback: sentiment 60%, momentum 40% (legacy behaviour)
        qual_score = 0.60 * s_score + 0.40 * m_score

    if z_score > 0.5 and qual_score > 0.15:
        return "BULL_CONFLUENCE"
    if z_score < -0.5 and qual_score < -0.15:
        return "BEAR_CONFLUENCE"
    if (z_score > 0.5 and qual_score < -0.15) or (z_score < -0.5 and qual_score > 0.15):
        return "DIVERGENCE"
    return "NEUTRAL"


def wiki_excerpt(path: Path, max_chars: int = 1800) -> str:
    try:
        text = path.read_text(encoding="utf-8")
        if text.startswith("---"):
            end = text.find("---", 3)
            if end > 0:
                text = text[end + 3 :].strip()
        return text[:max_chars]
    except FileNotFoundError:
        return ""


# ------------------------ Prompt + JSON helpers ------------------------

def _fmt_signed(value: float | None, digits: int = 2, suffix: str = "") -> str:
    if value is None:
        return "N/A"
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.{digits}f}{suffix}"


def _fmt_percentile(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value * 100:.1f}%"


def _fmt_snapshot_line(name: str, snap: dict) -> str:
    value = snap.get("value")
    value_txt = "N/A" if value is None else f"{value:.1f}"
    return (
        f"{name.upper():15s} "
        f"value={value_txt} "
        f"z={_fmt_signed(snap.get('z_score_252d'), 2, 'sigma')} "
        f"regime={snap.get('regime', 'N/A')} "
        f"roc60={_fmt_signed(snap.get('roc60'), 1, '%')} "
        f"pctl_5y={_fmt_percentile(snap.get('pctl_5y'))}"
    )


def _fmt_time_ago(date_str: str) -> str:
    try:
        d = datetime.fromisoformat(date_str).date()
        delta = (date.today() - d).days
        if delta == 0: return "today"
        if delta == 1: return "1 day ago"
        if delta < 14: return f"{delta} days ago"
        return f"{delta // 7} week{'s' if delta // 7 > 1 else ''} ago"
    except Exception:
        return date_str


def _fmt_rich_signal(signal: dict, idx: int) -> str:
    sentiment_raw = (signal.get("sentiment") or "neutral").lower()
    sentiment_label = sentiment_raw.upper().replace("_", " ")
    arrow_map = {
        "positive": "▲", "constructive": "▲", "cautiously_bullish": "↗",
        "neutral": "→", "mixed": "→", "cautiously_bearish": "↘", "negative": "▼",
    }
    arrow = arrow_map.get(sentiment_raw, "→")
    momentum = _clean_text(signal.get("momentum") or "N/A")
    fundamentals = _clean_text(signal.get("fundamentals") or "N/A")
    m_lower = momentum.lower()
    if any(w in m_lower for w in ["improv", "strong", "positiv", "rising", "acceler"]):
        m_arrow = " ↑"
    elif any(w in m_lower for w in ["weaken", "declin", "falling", "slow", "deterior"]):
        m_arrow = " ↓"
    else:
        m_arrow = ""
    date_str = signal.get("date", "")
    time_part = f" ({_fmt_time_ago(date_str)})" if date_str else ""
    return (
        f"{date_str} | {arrow} {sentiment_label:<22} | "
        f"momentum: {momentum}{m_arrow} | fundamentals: {fundamentals}{time_part}"
    )


def _signal_tally(signals: list[dict], z_score: float | None, confluence: str) -> str:
    """Build a pre-computed signal tally block to inject into the LLM prompt.

    Explicitly counts pos/neg/neutral for each Breakwave dimension so the LLM
    cannot hallucinate an incorrect confluence label.
    """
    if not signals:
        return "No Breakwave signals available for this sector."

    def _count(field: str) -> tuple[int, int, int]:
        pos = sum(1 for s in signals if str(s.get(field, "")).lower() == "positive")
        neg = sum(1 for s in signals if str(s.get(field, "")).lower() == "negative")
        neu = len(signals) - pos - neg
        return pos, neg, neu

    sp, sn, su = _count("sentiment")
    mp, mn, mu = _count("momentum")
    fp, fn, fu = _count("fundamentals")
    n = len(signals)

    z_str = f"{z_score:+.2f}σ" if z_score is not None else "N/A"

    lines = [
        f"PRE-COMPUTED SIGNAL INTELLIGENCE ({n} reports, newest first):",
        f"  Quantitative Z-score (252d): {z_str}",
        f"  Sentiment    : {sp} positive / {sn} negative / {su} neutral  (of {n})",
        f"  Momentum     : {mp} positive / {mn} negative / {mu} neutral  (of {n})",
        f"  Fundamentals : {fp} positive / {fn} negative / {fu} neutral  (of {n})",
        f"  >>> PYTHON PRE-COMPUTED CONFLUENCE: {confluence} <<<",
        f"  (Weights: fundamentals 50% + sentiment 30% + momentum 20%)",
        f"  You MUST use this confluence label in your JSON output unless Baltic data",
        f"  provides compelling real-time evidence to override it — in which case",
        f"  state the override reason explicitly in confluence_note.",
    ]
    return "\n".join(lines)


def compute_spreads(snapshot: dict) -> dict:
    spreads: dict = {}
    cape = snapshot.get("capesize", {}).get("value")
    pana = snapshot.get("panamax", {}).get("value")
    clean = snapshot.get("clean_tanker", {}).get("value")
    dirty = snapshot.get("dirty_tanker", {}).get("value")
    if cape is not None and pana is not None:
        sp = round(cape - pana, 1)
        spreads["cape_panamax"] = sp
        spreads["cape_panamax_ctx"] = "Capesize leading" if sp > 500 else ("converging" if sp < 100 else "normal range")
    if clean is not None and dirty is not None:
        sp = round(clean - dirty, 1)
        spreads["clean_dirty"] = sp
        spreads["clean_dirty_ctx"] = "clean outperforming" if sp > 0 else "dirty outperforming"
    bdi_pctl = snapshot.get("bdi", {}).get("pctl_5y")
    if bdi_pctl is not None:
        spreads["bdi_hist"] = (
            "top-quartile" if bdi_pctl > 0.75 else
            "above median" if bdi_pctl > 0.5 else
            "below median" if bdi_pctl > 0.25 else "bottom-quartile"
        )
    cz = snapshot.get("clean_tanker", {}).get("z_score_252d")
    dz = snapshot.get("dirty_tanker", {}).get("z_score_252d")
    if cz is not None and dz is not None:
        gap = round(cz - dz, 2)
        spreads["tanker_z_gap"] = gap
        spreads["tanker_z_ctx"] = (
            f"significant split: clean Z={cz:+.2f}\u03c3 vs dirty Z={dz:+.2f}\u03c3"
            if abs(gap) > 0.5 else
            f"aligned: clean Z={cz:+.2f}\u03c3, dirty Z={dz:+.2f}\u03c3"
        )
    return spreads


def _build_analytics_context(snapshot: dict, spreads: dict) -> str:
    hdr = f"{'INDEX':<16} {'LEVEL':>8} {'REGIME':<14} {'Z-SCORE':>10} {'ROC60':>8} {'5Y PCTL':>8} {'vs MA200':>10}"
    sep = "─" * 80
    rows = []
    for name, snap in snapshot.items():
        v = snap.get("value")
        z = snap.get("z_score_252d")
        roc = snap.get("roc60")
        pctl = snap.get("pctl_5y")
        ma200 = snap.get("ma200")
        regime = (snap.get("regime") or "N/A")[:13]
        z_s = f"{z:+.2f}\u03c3" if z is not None else "N/A"
        roc_s = f"{roc:+.1f}%" if roc is not None else "N/A"
        pctl_s = f"{pctl*100:.0f}th" if pctl is not None else "N/A"
        if v is not None and ma200 and ma200 > 0:
            ma_s = f"{(v - ma200) / ma200 * 100:+.1f}%"
        else:
            ma_s = "N/A"
        rows.append(f"{name.upper():<16} {str(v) if v is not None else 'N/A':>8} {regime:<14} {z_s:>10} {roc_s:>8} {pctl_s:>8} {ma_s:>10}")
    lines = ["INDEX ANALYTICS (interpreted):", hdr, sep] + rows + [""]
    lines.append("CROSS-MARKET SPREADS:")
    if "cape_panamax" in spreads:
        lines.append(f"  Capesize–Panamax spread: {spreads['cape_panamax']:+.0f} pts → {spreads['cape_panamax_ctx']}")
    if "clean_dirty" in spreads:
        lines.append(f"  Clean–Dirty tanker spread: {spreads['clean_dirty']:+.0f} pts → {spreads['clean_dirty_ctx']}")
    if "bdi_hist" in spreads:
        lines.append(f"  BDI historical context: {spreads['bdi_hist']} historically")
    if "tanker_z_ctx" in spreads:
        lines.append(f"  Tanker Z-spread: {spreads['tanker_z_ctx']}")
    # Add ETF Constituent Holdings and Forward Curve analytics
    bdry_h = load_etf_holdings_data("bdry")
    bwet_h = load_etf_holdings_data("bwet")
    sgx_c = load_sgx_curve_data()
    bdry_m = compute_etf_curve_metrics("bdry", bdry_h, sgx_c)
    bwet_m = compute_etf_curve_metrics("bwet", bwet_h, sgx_c)
    
    lines.append("\nETF CONSTITUENTS & FORWARD ROLL DYNAMICS:")
    if bdry_m:
        lines.append(f"  BDRY (Dry Bulk): Prompt {bdry_m['prompt_contract'].get('name','')} (${bdry_m['prompt_contract'].get('price',0):,.0f}/d) -> Next {bdry_m['next_contract'].get('name','')} (${bdry_m['next_contract'].get('price',0):,.0f}/d) | Monthly Roll Yield: {bdry_m['implied_roll_yield_pct']:+.2f}% ({bdry_m['curve_regime']})")
        lines.append(f"    * {bdry_m['holding_bet_summary_30d']}")
        lines.append(f"    * {bdry_m['holding_bet_summary_90d']}")
    # Add Physical Freight, Period Time Charter & Capital Cycle Signals
    phys_ctx = load_physical_signals_context()
    if phys_ctx:
        lines.append("\nPHYSICAL FREIGHT, PERIOD TIME CHARTER & CAPITAL CYCLE SIGNALS:")
        lines.append(phys_ctx)
        
    return "\n".join(lines)


def load_physical_signals_context() -> str:
    """Extract maximized multi-period insights across all physical and derivative series (180d spot, SGX curves, 24w Alibra, 22m tanker forward, 2y restocking, 10y S&P, 120d ETF flows)."""
    lines = []
    
    # 1. Macro & Baltic Spot Indices Rolling 180-Day Daily Time Series Table
    indices_files = {
        "BDI": ROOT / "data" / "indices" / "bdiy_historical.csv",
        "Capesize": ROOT / "data" / "indices" / "cape_historical.csv",
        "Panamax": ROOT / "data" / "indices" / "panama_historical.csv",
        "Supramax": ROOT / "data" / "indices" / "suprama_historical.csv",
        "Handysize": ROOT / "data" / "indices" / "handysize_historical.csv",
        "Dirty_Tanker": ROOT / "data" / "indices" / "dirtytanker_historical.csv",
        "Clean_Tanker": ROOT / "data" / "indices" / "cleantanker_historical.csv",
    }
    daily_matrix = {}
    for idx_name, path in indices_files.items():
        if path.exists():
            with open(path, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    d_raw = row.get("Date") or row.get("date")
                    val = row.get("Index") or row.get("value") or row.get("price")
                    if d_raw and val:
                        try:
                            if "-" in d_raw and len(d_raw.split("-")[0]) == 2:
                                dt = datetime.strptime(d_raw, "%d-%m-%Y").strftime("%Y-%m-%d")
                            else:
                                dt = d_raw[:10]
                            if dt not in daily_matrix:
                                daily_matrix[dt] = {}
                            daily_matrix[dt][idx_name] = float(val)
                        except Exception:
                            pass
                            
    sorted_dates = sorted(daily_matrix.keys(), reverse=True)
    recent_14_dates = sorted_dates[:14]
    
    lines.append("=== 1. ROLLING 14-DAY DAILY SPOT FREIGHT BENCHMARK MATRIX ===")
    lines.append(f"  {'DATE':<12} {'BDI':>8} {'CAPESIZE':>10} {'PANAMAX':>10} {'SUPRAMAX':>10} {'HANDY':>8} {'BDTI (DIRTY)':>14} {'BCTI (CLEAN)':>14}")
    lines.append("  " + "─" * 84)
    for dt in recent_14_dates:
        m = daily_matrix[dt]
        bdi = m.get("BDI", 0)
        c = m.get("Capesize", 0)
        p = m.get("Panamax", 0)
        s = m.get("Supramax", 0)
        h = m.get("Handysize", 0)
        d_tank = m.get("Dirty_Tanker", 0)
        c_tank = m.get("Clean_Tanker", 0)
        lines.append(f"  {dt:<12} {bdi:>8.0f} {c:>10.0f} {p:>10.0f} {s:>10.0f} {h:>8.0f} {d_tank:>14.0f} {c_tank:>14.0f}")
        
    # 2. SGX Dry Bulk FFA Forward Curves (Cape, Panamax, Supramax, Handy - All Expiries)
    sgx_files = {
        "Capesize": ROOT / "data" / "futures" / "sgx_cape_futures.csv",
        "Panamax": ROOT / "data" / "futures" / "sgx_panamax_futures.csv",
        "Supramax": ROOT / "data" / "futures" / "sgx_supramax_futures.csv",
        "Handysize": ROOT / "data" / "futures" / "sgx_handysize_futures.csv",
    }
    lines.append("\n=== 2. SGX DRY BULK FFA FORWARD CURVE MATRIX (Prompt through Cal+3) ===")
    for cls_name, p in sgx_files.items():
        if p.exists():
            with open(p, encoding="utf-8") as f:
                c_map = {}
                for row in csv.DictReader(f):
                    c = row.get("contract")
                    px = float(row.get("price") or 0)
                    dt = row.get("date", "")
                    if c and px > 0:
                        if c not in c_map or dt >= c_map[c]["date"]:
                            c_map[c] = {"contract": c, "price": px, "date": dt}
                pts = [f"{c['contract']}: ${c['price']:,.0f}/d" for c in list(c_map.values())[:6]]
                lines.append(f"  [{cls_name.upper()} SGX FFA CURVE]: " + " | ".join(pts))

    # 3. Alibra Period TCE Matrix - 6-Week Historical Time Series
    p_tc = ROOT / "data" / "derived" / "time_charter_rates.csv"
    if p_tc.exists():
        lines.append("\n=== 3. ALIBRA PERIOD TIME CHARTER MATRIX (6-Week Historical Fixtures) ===")
        tc_rows = []
        with open(p_tc, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                tc_rows.append(row)
        tc_by_date = {}
        for r in tc_rows:
            d = r.get("date")
            if d:
                if d not in tc_by_date: tc_by_date[d] = []
                tc_by_date[d].append(r)
        sorted_tc_dates = sorted(tc_by_date.keys(), reverse=True)[:4]
        for d in sorted_tc_dates:
            lines.append(f"\n  --- Alibra Assessment Date: {d} ---")
            for r in tc_by_date[d]:
                sec = str(r.get("sector") or "")
                cls = str(r.get("vessel_class") or "")
                tenor = str(r.get("tenor") or "")
                basin = str(r.get("basin") or "")
                rate = float(r.get("rate_usd_day") or 0)
                chg = float(r.get("wow_change_pct") or 0)
                lines.append(f"    • {sec:<8} | {cls:<22} | Tenor: {tenor:<3} | Basin: {basin:<8} | Rate: ${rate:>7,.0f}/day ({chg:+.1f}%)")

    # 4. Tanker FFA Forward Curves (22 Months + Eco Premiums)
    p_fwd = ROOT / "data" / "derived" / "tanker_forward_curves.csv"
    if p_fwd.exists():
        fwd_rows = []
        with open(p_fwd, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                fwd_rows.append(row)
        lines.append("\n=== 4. TANKER FFA FORWARD CURVE 22-MONTH MATRIX & ECO PREMIUMS ===")
        lines.append(f"  {'MONTH':<12} {'VLCC TD3C':>12} {'VLCC ECO':>12} {'ECO SAVINGS':>14} {'SUEZ TD20':>12} {'AFRA TD25':>12} {'LR1 TC5':>10} {'MR TC2':>10}")
        lines.append("  " + "─" * 90)
        for r in fwd_rows:
            m = r.get("forward_month", "")
            v = float(r.get("vlcc_td3c") or 0)
            v_eco = float(r.get("vlcc_eco_td3c") or 0)
            diff = v - v_eco if v > 0 and v_eco > 0 else 0
            s = float(r.get("suezmax_td20") or 0)
            a = float(r.get("aframax_td25") or 0)
            lr1 = float(r.get("clean_lr1_tc5") or 0)
            mr = float(r.get("clean_mr_tc2") or 0)
            lines.append(f"  {m:<12} ${v:>10,.0f} ${v_eco:>10,.0f} ${diff:>12,.0f} ${s:>10,.0f} ${a:>10,.0f} ${lr1:>8,.0f} ${mr:>8,.0f}")

    # 5. China Raw Material Restocking & Steel Production (16-Week Trajectory)
    p_ore = ROOT / "data" / "derived" / "iron_ore_restocking.csv"
    if p_ore.exists():
        ore_rows = []
        with open(p_ore, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("cfr_62") or row.get("inventories_mt"):
                    ore_rows.append(row)
        lines.append("\n=== 5. CHINA RAW MATERIAL RESTOCKING & STEEL FUNDAMENTALS (16-Week Trajectory) ===")
        lines.append(f"  {'DATE':<12} {'QINGDAO PORT (MT)':>18} {'62% Fe CFR':>12} {'65% CARAJAS':>14} {'SPREAD (65-62)':>16} {'CRUDE STEEL (MT)':>18} {'STEEL INVENT (MT)':>18}")
        lines.append("  " + "─" * 114)
        for r in ore_rows[-12:]:
            d = r.get("date", "")
            inv = r.get("inventories_mt") or "-"
            fe62 = float(r.get("cfr_62") or 0)
            fe65 = float(r.get("cfr_65") or 0)
            sp = f"+${(fe65 - fe62):.1f}/t" if fe62 > 0 and fe65 > 0 else "-"
            st = r.get("steel_production_mt") or "-"
            st_inv = r.get("steel_inventories_mt") or "-"
            fe62_s = f"${fe62:.1f}/t" if fe62 > 0 else "-"
            fe65_s = f"${fe65:.1f}/t" if fe65 > 0 else "-"
            lines.append(f"  {d:<12} {inv:>18} {fe62_s:>12} {fe65_s:>14} {sp:>16} {st:>18} {st_inv:>18}")

    # 6. Vessel Valuations & Scrappage Cycles (24-Month S&P History)
    p_val = ROOT / "data" / "derived" / "vessel_valuations.csv"
    p_scrap = ROOT / "data" / "derived" / "scrappage_prices.csv"
    if p_val.exists() and p_scrap.exists():
        val_rows = []
        with open(p_val, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                val_rows.append(row)
        scrap_rows = []
        with open(p_scrap, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                scrap_rows.append(row)
        lines.append("\n=== 6. VESSEL SECONDHAND ASSET VALUES & DEMOLITION SCRAP BENCHMARKS (24-Month History) ===")
        val_10y = [r for r in val_rows if '10' in r.get('tenor_type', '')][-18:]
        for r in val_10y:
            lines.append(f"    • {r.get('date')} | {r.get('vessel_class'):<24} | Tenor: {r.get('tenor_type'):<6} | Value: ${float(r.get('valuation_usd_m') or 0):>6.1f}M")

    # 7. ETF Daily Holdings & Creation/Redemption Flows (20 Sessions)
    p_bdry_f = ROOT / "data" / "etf" / "BDRY_flows.csv"
    p_bwet_f = ROOT / "data" / "etf" / "BWET_flows.csv"
    lines.append("\n=== 7. ETF CREATION/REDEMPTION FLOWS & LIQUIDITY (Last 20 Sessions) ===")
    if p_bdry_f.exists():
        with open(p_bdry_f, encoding="utf-8") as f:
            bdry_flows = list(csv.DictReader(f))[-14:]
            lines.append("  [BDRY (Dry Bulk ETF) Daily Net Flows - $M]")
            for r in bdry_flows:
                lines.append(f"    • {r.get('date')}: Net Flow = ${float(r.get('flow_usd_m') or r.get('net_flow') or 0):>+6.2f}M | Shares Out = {float(r.get('shares_out') or 0):>10,.0f} | NAV = ${float(r.get('nav') or 0):>5.2f}")
    if p_bwet_f.exists():
        with open(p_bwet_f, encoding="utf-8") as f:
            bwet_flows = list(csv.DictReader(f))[-14:]
            lines.append("  [BWET (Tanker ETF) Daily Net Flows - $M]")
            for r in bwet_flows:
                lines.append(f"    • {r.get('date')}: Net Flow = ${float(r.get('flow_usd_m') or r.get('net_flow') or 0):>+6.2f}M | Shares Out = {float(r.get('shares_out') or 0):>10,.0f} | NAV = ${float(r.get('nav') or 0):>5.2f}")

    # 8. Gas Shipping Benchmarks (LPG & LNG Fleet History)
    p_lpg = ROOT / "data" / "derived" / "lpg_charter_rates.csv"
    p_lng = ROOT / "data" / "derived" / "lng_charter_rates.csv"
    if p_lpg.exists() and p_lng.exists():
        try:
            with open(p_lpg, encoding="utf-8") as f:
                lpg_rows = list(csv.DictReader(f))
            with open(p_lng, encoding="utf-8") as f:
                lng_rows = list(csv.DictReader(f))
            if lpg_rows and lng_rows:
                lines.append(f"\n=== 8. GAS SHIPPING BENCHMARKS (LPG & LNG) ===")
                last_lpg = lpg_rows[-1]
                last_lng = lng_rows[-1]
                vlgc_pcm = float(last_lpg.get("vlgc_84k_tc") or 0)
                lines.append(f"  • LPG Fleet: VLGC 84k 1Y TC ${vlgc_pcm/30.4375:,.0f}/day (${vlgc_pcm:,.0f}/month) | MGC 38k ${float(last_lpg.get('mgc_38k_tc') or 0):,.0f}/month | Handy 22k ${float(last_lpg.get('hdy_22k_tc') or 0):,.0f}/month")
                lines.append(f"  • LNG Fleet: 174k 2-Stroke 7Y TC ${float(last_lng.get('lngc_174k_7y_tc') or 0):,.0f}/day | 10Y TC ${float(last_lng.get('lngc_174k_10y_tc') or 0):,.0f}/day | Newbuilding Order: ${float(last_lng.get('lngc_80k_nb_price') or 262):,.0f}M")
        except Exception:
            pass
            
    return "\n".join(lines)


def load_recent_report_text(category: str, n_reports: int = RECENT_REPORTS) -> str:
    """Load all chunk sections for the most recent N reports."""
    chunk_map = {
        "drybulk": "breakwave_drybulk",
        "tankers": "breakwave_tankers",
    }
    stem = chunk_map.get(category)
    paths: list[Path] = []
    if stem:
        # Discover shards dynamically (dated year-shards newest-first, then
        # the legacy undated full-history file) so briefs keep reading fresh
        # chunks after every January rollover without code changes.
        dated = sorted(
            (KNOWLEDGE / "chunks").glob(f"{stem}_*.jsonl"),
            key=lambda p: p.name,
            reverse=True,
        )
        legacy = KNOWLEDGE / "chunks" / f"{stem}.jsonl"
        paths = dated + ([legacy] if legacy.exists() else [])
    chunks: list[dict] = []
    for path in paths:
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        chunks.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except FileNotFoundError:
            continue
    chunks.sort(key=lambda x: x.get("date", ""), reverse=True)
    seen_dates: list[str] = []
    for chunk in chunks:
        d = chunk.get("date", "")
        if d and d not in seen_dates:
            seen_dates.append(d)
    
    entries = []
    for report_date in seen_dates[:n_reports]:
        date_chunks = [c for c in chunks if c.get("date") == report_date]
        sections = []
        for c in date_chunks:
            section = c.get("section_title", "")
            text = _clean_text(c.get("text"))
            if text:
                sections.append(f"[{section}] {text}" if section else text)
        entries.append(f"{report_date}:\n" + "\n".join(sections))
    return "\n---\n".join(entries) if entries else "No report text available."


def _strip_html(html: str) -> str:
    """Minimal stdlib HTML stripper — removes style/script blocks then all tags."""
    text = re.sub(r"<(style|script)[^>]*>.*?</\1>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


_BALTIC_SKIP_PHRASES = (
    "this site uses cookies",
    "back to all",
    "previous",
    "next",
    "balticexchange.com",
    "http://",
    "https://",
)


def load_baltic_report_text(sector: str, n_reports: int = BALTIC_REPORTS) -> str:
    """Load the N most recent Baltic Exchange weekly HTML reports for a sector."""
    base_dir = BALTIC_DRY_DIR if sector == "dry" else BALTIC_TANKER_DIR
    if not base_dir.exists():
        return "No Baltic Exchange reports available."

    key_to_file: dict = {}
    for html_file in sorted(base_dir.rglob("*.html")):
        name = html_file.name
        m_week = re.search(r"week-(\d+)", name)
        m_year = re.search(r"(\d{4})", name)
        if not m_week or not m_year:
            continue
        week = int(m_week.group(1))
        year = int(m_year.group(1))
        key = (year, week)
        is_dated = bool(re.match(r"\d{4}-\d{2}-\d{2}_", name))
        existing = key_to_file.get(key)
        if existing is None or (is_dated and not existing[0]):
            key_to_file[key] = (is_dated, html_file)

    sorted_files = sorted(key_to_file.items(), key=lambda x: x[0], reverse=True)
    selected = [path for _, (_, path) in sorted_files[:n_reports]]

    entries = []
    for html_path in selected:
        try:
            raw_html = html_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        date_m = re.match(r"(\d{4}-\d{2}-\d{2})_", html_path.name)
        if date_m:
            report_date = date_m.group(1)
        else:
            date_meta = re.search(r"Date:\s*(\d{1,2}\s+\w+\s+\d{4})", raw_html)
            report_date = date_meta.group(1) if date_meta else html_path.stem[:7]

        vessel_cls_list = [
            "Capesize", "Panamax", "Ultramax/Supramax", "Ultramax", "Supramax",
            "Handysize", "VLCC", "Suezmax", "Aframax", "LR2", "LR1", "MR",
            "Clean", "Dirty",
        ]
        css_skip = ("box-sizing", "font-family", "font-size", "border-collapse")
        segments = re.split(r"</p>", raw_html)
        sections: dict[str, str] = {}
        current_class: str | None = None
        for seg in segments:
            plain = re.sub(r"<[^>]+>", " ", seg)
            plain = re.sub(r"&[a-z#\d]+;", " ", plain)
            plain = re.sub(r"\s+", " ", plain).strip()
            if not plain or any(s in plain.lower() for s in css_skip):
                continue
            heading_found: str | None = None
            if len(plain) < 120:
                for vc in vessel_cls_list:
                    if vc in plain:
                        heading_found = vc
                        break
            if heading_found:
                current_class = heading_found
            elif current_class and len(plain) > 80 and current_class not in sections:
                sections[current_class] = plain[:1500]

        if sections:
            entries.append(f"{report_date} (Baltic Weekly):\n"
                           + "\n".join(f"[{vc}] {txt}" for vc, txt in sections.items()))

    return "\n---\n".join(entries) if entries else "No Baltic Exchange reports available."


def build_system_message() -> str:
    return (
        "You are the head freight strategist at a tier-1 commodity trading desk — the most respected and feared analyst on the floor. "
        "Your daily brief is the first thing portfolio managers read every morning before trading FFAs, "
        "freight options, and shipping equities. You have 15 years of experience synthesizing Baltic "
        "Exchange data, Breakwave Advisors research, and global macro flows into actionable intelligence.\n\n"

        "YOUR VOICE: Write like the best sell-side analyst in the world briefing the trading floor — "
        "authoritative, opinionated, and surgically precise. Numbers support the argument; they do not replace it. "
        "Every sentence must carry a distinct analytical insight that could not be gleaned from the raw data table alone.\n\n"

        "TWO-SOURCE INTELLIGENCE: You now have TWO independent report sources: "
        "(1) BREAKWAVE ADVISORS — strategic/fundamental analysis with sentiment signals. "
        "(2) BALTIC EXCHANGE WEEKLY — granular vessel-class narratives (Capesize, Panamax, VLCC, etc.) with specific fixture rates and market colour. "
        "Cross-reference these sources. When both agree, state the confluence explicitly. "
        "When they diverge, name the tension and state which you weight more heavily and why. "
        "The Baltic vessel-class colour (e.g. 'C5 pushed into the mid-$15s', 'Panamax P5TC rose to $20,099') "
        "is primary evidence — use these specific figures in your analysis.\n\n"

        "CONTRARIAN INTELLIGENCE MANDATE: You are REQUIRED to actively look for what the consensus is missing. "
        "If every signal is bullish, ask: what could break this? If momentum is extreme (Z>2.5 or Z<-2.5), "
        "explicitly flag mean-reversion risk. If qualitative and quantitative signals diverge, name the tension "
        "and state which you trust more and why. If a rally appears overextended relative to fundamentals, say so. "
        "Do NOT be a cheerleader for the data. Be the analyst who protects the desk from getting caught offsides. "
        "A brief that only confirms what the data already shows adds zero value. Your edge is in surfacing what "
        "the numbers cannot tell you: the fragility, the second-order effects, the regime risks.\n\n"

        "CRITICAL WRITING RULES:\n"
        "RULE 1 — NO DATA TRANSCRIPTION. Never write a sentence whose sole purpose is to repeat a number "
        "from the data table. Numbers must appear inside a sentence that interprets their significance. "
        "BAD: 'BDI ROC60: +53.3%' or 'Capesize Z-score: +2.59σ'. "
        "GOOD: 'A +53.3% ROC60 on the BDI signals one of the fastest six-month recoveries since 2020, "
        "placing the current cycle firmly in acceleration territory rather than mere mean-reversion.'\n\n"

        "RULE 1A — STRICT UNIT INTEGRITY (INDEX POINTS vs CHARTER RATES): "
        "Baltic freight indices (BDI, BCI, BPI, BSI, BHSI, BDTI, BCTI) are unitless index POINTS (e.g. '3,083 points' or 'breakout above 3,200 points on the BDI'). "
        "NEVER prefix an index with a dollar sign '$' (NEVER write '$3200 on the BDI' or '$3083'). "
        "Dollar signs ($/day) apply strictly to daily time-charter fixture rates (TCE rates like '$25,000/day' or VLCC '$48,000/day').\n\n"

        "RULE 2 — ANALYTICAL LAYERING. Each sentence in 'summary' must add a new analytical layer: "
        "(1) WHERE the market is — level, regime, and historical context in one sentence. "
        "(2) HOW FAST it got there — momentum characterization with Z-score and ROC60 giving the rate-of-change story. "
        "(3) WHAT THE ANALYSTS THINK — synthesize the Breakwave signal consensus into a qualitative verdict, "
        "noting any divergence between their tone and the quant readings. "
        "(4) SO WHAT — the actionable conclusion: what this confluence means for positioning over the next 2-4 weeks.\n\n"

        "RULE 3 — KEY SIGNALS MUST BE INSIGHTS, NOT LABELS. "
        "Each entry in 'key_signals' must be a full analytical sentence explaining WHY the signal matters. "
        "BAD: 'BDI: 3001.0' or 'Capesize Z-score: +2.59σ'. "
        "GOOD: 'Capesize rates at 4,976 sit +2.59σ above their 252-day mean — a level historically "
        "associated with sustained FFA curve steepening as forward holders hedge into strength.' "
        "GOOD: 'The Capesize-Panamax spread of +2,693 points is at its widest since Q4 2023, "
        "indicating that iron ore and coal voyages are crowding out grain-driven demand for smaller vessels.'\n\n"

        "RULE 4 — NATURAL PROSE FLOW. Write sentences that flow into each other, not a list of facts. "
        "Use causal connectives: 'which signals', 'against a backdrop of', 'reinforcing the view that', "
        "'despite', 'in contrast to', 'historically, this level has preceded'.\n\n"

        "RULE 5 — BANNED PHRASES (never use): 'it is worth noting', 'importantly', 'it is crucial', "
        "'it should be noted', 'as mentioned', 'in conclusion', 'overall', 'in summary', "
        "'the data suggests', 'it appears', 'it seems', 'needless to say', 'showcasing', 'reflecting'.\n\n"

        "RULE 6 — TRADE IDEAS ARE OPTIONAL, NOT MANDATORY. Generate a trade_idea ONLY when: "
        "(a) quant and qual signals clearly agree, (b) a specific entry trigger or rate level exists, "
        "AND (c) a concrete exit thesis can be articulated. If NOT all three are met, write: "
        "'No high-conviction setup: [what would need to change]'. Never fabricate a trade to fill the field.\n\n"

        "RULE 7 — RISK NOTES must name the SPECIFIC event or data point that would invalidate the current thesis — "
        "not a generic 'macro uncertainty'. BAD: 'Risk of macro slowdown'. "
        "GOOD: 'A Chinese iron ore import volume print below 95mt in the next customs release would confirm "
        "demand destruction and invalidate the BDI expansion thesis.'\n\n"

        "RULE 8 — CATALYST WATCH must name SPECIFIC forward-looking upcoming events with realistic near-term timing. "
        "Always anchor events to the current calendar date. NEVER reference expired past months (e.g. if today is in August, reference late August / September prints). "
        "GOOD: 'China NBS Manufacturing PMI, upcoming monthly customs commodity trade data, and US weekly EIA petroleum status reports are the three near-term catalysts.'\n\n"

        "RULE 9 — MACRO NOTE must be event-specific, not geopolitical boilerplate. "
        "Never write generic sentences about 'rising interest rates' or 'geopolitical uncertainty'. "
        "Name the specific macro driver currently active, its freight transmission mechanism, and the "
        "named upcoming data release or event that will confirm or refute it.\n\n"

        "RULE 9B — GEOPOLITICAL INTELLIGENCE MANDATE: You are REQUIRED to scan the analyst report narratives "
        "for any mention of active armed conflict, military escalation, sanctions regimes, supply route disruptions, "
        "or port access restrictions. If ANY such event is found, you MUST: "
        "(1) Name it explicitly by country/region in the macro_note — e.g. 'The Iran-Israel conflict', 'Taiwan Strait tensions', 'Russia Black Sea blockade'. "
        "(2) Explain its SPECIFIC freight transmission mechanism — which routes, vessel types, and ton-mile impacts are affected. "
        "(3) State whether it is currently bullish or bearish for the affected sector and why. "
        "(4) Flag it in the relevant sector's risk_note or catalyst_watch with an explicit trigger that would confirm escalation or de-escalation. "
        "If no geopolitical disruption is mentioned in the analyst reports, do not invent one. "
        "But if it IS in the reports and you fail to surface it, you have failed the desk.\n\n"

        "RULE 10 — KEY SIGNALS: Aim for 6-8 signals. Cover: the headline index interpretation, "
        "the momentum character, the cross-segment spread story, at least one contrarian or fragility signal, "
        "and the analyst consensus alignment. Do NOT list fewer than 5 signals.\n\n"

        "RULE 11 — MOMENTUM GRADE derivation: "
        "STRONG_UP (Z>1.5 AND ROC>10%), UP (Z>0.5 OR ROC>5%), FLAT (|Z|<=0.5 AND |ROC|<=5%), "
        "DOWN (Z<-0.5 OR ROC<-5%), STRONG_DOWN (Z<-1.5 AND ROC<-10%).\n\n"

        "RULE 12 — CONFIDENCE SCORE: 1.0 = perfect quant+qual convergence with no fragility flags, "
        "0.7 = strong alignment with minor caveats, 0.5 = mixed signals, "
        "0.3 = significant quant-qual divergence, 0.0 = direct contradiction.\n\n"

        "RULE 13 — TRADE IDEAS ARE OPTIONAL, NOT MANDATORY. Only generate a trade_idea when ALL three "
        "conditions are met: (a) quant and qual signals are clearly aligned, (b) there is an identifiable "
        "entry trigger or rate level, and (c) a concrete exit thesis exists. If these conditions are NOT met "
        "— e.g. signals are mixed, geopolitical uncertainty is high, or the setup is unclear — write exactly: "
        "'No high-conviction setup: [1 sentence explaining what would need to change to generate a trade]'. "
        "Do NOT fabricate a trade to fill the field.\n\n"

        "OUTPUT: Respond ONLY with a single valid JSON object. No preamble, no markdown fences, no explanation outside the JSON."
    )


def build_user_message(
    snapshot: dict,
    dry_signals: list[dict],
    tanker_signals: list[dict],
    wiki_dry: str,
    wiki_tanker: str,
    wiki_cape: str,
    dry_report_text: str = "",
    tanker_report_text: str = "",
    spreads: dict | None = None,
    baltic_dry_text: str = "",
    baltic_tanker_text: str = "",
    pre_dry_conf: str = "NEUTRAL",
    pre_tanker_conf: str = "NEUTRAL",
) -> str:
    today_dt = date.today()
    today = today_dt.isoformat()
    cur_month = today_dt.strftime("%B")
    cur_year = today_dt.strftime("%Y")
    next_month_dt = (today_dt.replace(day=1) + timedelta(days=32)).replace(day=1)
    next_month = next_month_dt.strftime("%B")
    next_year = next_month_dt.strftime("%Y")
    analytics = _build_analytics_context(snapshot, spreads or {})
    dry_block = "\n".join(_fmt_rich_signal(s, i) for i, s in enumerate(dry_signals)) or "No recent reports."
    tanker_block = "\n".join(_fmt_rich_signal(s, i) for i, s in enumerate(tanker_signals)) or "No recent reports."
    dry_z = snapshot.get("bdi", {}).get("z_score_252d")
    tanker_z = compute_tanker_z(snapshot)
    dry_tally = _signal_tally(dry_signals, dry_z, pre_dry_conf)
    tanker_tally = _signal_tally(tanker_signals, tanker_z, pre_tanker_conf)
    n_dry = len([r for r in dry_report_text.split("---") if r.strip()])
    n_tank = len([r for r in tanker_report_text.split("---") if r.strip()])
    return f"""DAILY FREIGHT INTELLIGENCE BRIEF — {today} (CURRENT TIMELINE: {cur_month.upper()} {cur_year} -> {next_month.upper()} {next_year})

{analytics}

RECENT BREAKWAVE DRY BULK ANALYST SIGNALS (newest first — weight: 0.85^i decay):
{dry_tally}
{dry_block}

RECENT BREAKWAVE TANKER ANALYST SIGNALS (newest first — weight: 0.85^i decay):
{tanker_tally}
{tanker_block}

ANALYST REPORT NARRATIVES — DRY BULK (last {n_dry} Breakwave reports, newest first):
{dry_report_text}

ANALYST REPORT NARRATIVES — TANKERS (last {n_tank} Breakwave reports, newest first):
{tanker_report_text}

BALTIC EXCHANGE WEEKLY REPORTS — DRY BULK (last {BALTIC_REPORTS} weeks, vessel-class narrative, newest first):
{baltic_dry_text or 'No Baltic reports available.'}

BALTIC EXCHANGE WEEKLY REPORTS — TANKERS (last {BALTIC_REPORTS} weeks, vessel-class narrative, newest first):
{baltic_tanker_text or 'No Baltic reports available.'}

STRUCTURAL MARKET CONTEXT:
[Dry Bulk Market]
{wiki_dry}

[Capesize Segment]
{wiki_cape}

[Tanker Market]
{wiki_tanker}

TASK: Write today's institutional freight brief for {today} ({cur_month} {cur_year}).
TIMELINE MANDATE: Today is {today}. All upcoming catalysts, trade triggers, and outlooks MUST be forward-looking into {cur_month} / {next_month} {next_year}. NEVER mention expired months.

WRITING QUALITY MANDATE:
- Freight indices (BDI, BCI, BPI, BSI, BHSI, BDTI, BCTI) are index POINTS, NEVER write '$' on indices.
- Every 'key_signals' entry MUST be a full analytical sentence explaining significance, not a raw data label.
- 'summary' MUST read as flowing analysis where each sentence builds on the previous one.
- Numbers must support arguments, not replace them.
- 'trade_idea' must be immediately actionable with a named vehicle and trigger.

Return ONLY valid JSON matching this schema:
{{
  "vessel_classes": {{
    "dry_bulk": {{
      "confluence_type": "<BULL_CONFLUENCE|BEAR_CONFLUENCE|DIVERGENCE|NEUTRAL>",
      "momentum_grade": "<STRONG_UP|UP|FLAT|DOWN|STRONG_DOWN>",
      "confidence_score": <float 0.0-1.0>,
      "confluence_note": "<2 sentences — S1: state the exact Z-score from analytics table and what regime/percentile this implies historically; S2: MANDATORY — copy the EXACT counts from the PRE-COMPUTED SIGNAL INTELLIGENCE block above (do NOT recount from report narrative text). Use this exact format: 'Of the N Breakwave reports: Sentiment X pos/Y neg/Z neu; Momentum A pos/B neg/C neu; Fundamentals D pos/E neg/F neu — [one clause explaining whether this confirms or contradicts the quant reading and the dominant driver of the divergence/alignment]'>",
      "summary": "<4 sentences of flowing analysis: S1=where the market is with historical context; S2=momentum characterization using Z+ROC explaining the rate-of-change story; S3=analyst consensus + vessel-class breakdown (Cape vs Panamax vs Handysize), noting any quant-qual divergence; S4=integrate GEOPOLITICAL factors (supply disruptions, port congestion, route hazards) if active, and actionable conclusion on positioning over the next 2-4 weeks>",
      "key_signals": ["<analytical sentence with embedded number explaining WHY it matters — NOT a raw data label>", "...up to 8 total"],
      "positioning_bias": "<LONG|SHORT|NEUTRAL|LONG_SPREAD_VS_TANKER|SHORT_SPREAD_VS_TANKER>",
      "trade_idea": "<IF signals clearly aligned: '1 sentence with direction + specific vehicle + entry trigger + exit thesis'. IF NOT clearly aligned OR geopolitical uncertainty is elevated: 'No high-conviction setup: [specific condition needed to validate the thesis]'>",
      "outlook": "<1 sentence naming the 2-4 week directional thesis with the key variable that could change it — if geopolitical risk is elevated, name that as either a tail upside or downside risk>",
      "catalyst_watch": "<1 sentence naming 2-3 SPECIFIC forward-looking events or seasonal inflections for late {cur_month} / {next_month} (e.g. upcoming monthly trade data, inventory releases, or seasonal freight inflections) — NEVER reference past months>",
      "risk_note": "<1 sentence naming the single biggest tail risk and the SPECIFIC data point or event that would confirm it — if geopolitical, name the specific disruption threshold that would break the thesis>"
    }},
    "tanker": {{
      "confluence_type": "<BULL_CONFLUENCE|BEAR_CONFLUENCE|DIVERGENCE|NEUTRAL>",
      "momentum_grade": "<STRONG_UP|UP|FLAT|DOWN|STRONG_DOWN>",
      "confidence_score": <float 0.0-1.0>,
      "confluence_note": "<2 sentences — S1: state the exact Z-score from analytics table and what regime/percentile this implies historically; S2: MANDATORY — copy the EXACT counts from the PRE-COMPUTED SIGNAL INTELLIGENCE block above (do NOT recount from report narrative text). Use this exact format: 'Of the N Breakwave reports: Sentiment X pos/Y neg/Z neu; Momentum A pos/B neg/C neu; Fundamentals D pos/E neg/F neu — [one clause explaining whether this confirms or contradicts the quant reading and the dominant driver of the divergence/alignment]'>",
      "summary": "<4 sentences flowing analysis: S1=current tanker market positioning with historical context; S2=Z-score + momentum + clean/dirty split explicitly; S3=analyst consensus assessment vs quant signals, flagging any divergences; S4=integrate GEOPOLITICAL factors (supply disruptions, sanctions, route hazards) if active, and actionable positioning thesis over 2-4 weeks>",
      "key_signals": ["<analytical sentence with embedded number>", "...up to 8 total"],
      "positioning_bias": "<LONG|SHORT|NEUTRAL|LONG_SPREAD_VS_DRY|SHORT_SPREAD_VS_DRY>",
      "trade_idea": "<IF signals clearly aligned: '1 sentence with direction + specific vehicle + entry trigger + exit thesis'. IF NOT clearly aligned OR geopolitical uncertainty is elevated: 'No high-conviction setup: [specific condition needed to validate the thesis]'>",
      "outlook": "<1 sentence: 2-4 week directional thesis with the SPECIFIC swing variable that could change it — if geopolitical risk is elevated, name that as a tail upside driver>",
      "catalyst_watch": "<1 sentence naming 2-3 SPECIFIC upcoming events with approximate forward dates for {cur_month}/{next_month} {next_year} (e.g. upcoming OPEC+ ministerial reviews, weekly EIA crude stock figures, seasonal refinery runs) — NEVER reference past months>",
      "risk_note": "<1 sentence naming a SPECIFIC data print or event that would invalidate the thesis — e.g. 'If geopolitical premiums compress despite ongoing supply threats, it would signal that traders are pricing in a resolution timeline'>",
      "geopolitical_impact": "<IF active supply disruptions, sanctions, or route hazards are mentioned in analyst reports: 1-2 sentences explaining the explicit tonnage impact + which tanker segments (VLCC vs Suez vs Aframax) benefit most from rerouting. ELSE: null or empty string>"
    }}
  }},
  "cross_sector_analysis": {{
    "relative_value": "<1 sentence comparing dry vs tanker with specific Z-differential or spread value — name which sector has better risk-reward and articulate the structural reason>",
    "dominant_driver": "<1 sentence naming the single most consequential macro force for BOTH sectors today — be specific, not generic>",
    "positioning_recommendation": "<1 sentence: specific cross-sector trade with named vehicles, entry rationale, and exit trigger>"
  }},
  "executive_tldr": [
    "<Bullet 1: 1 concise punchy takeaway on macro freight velocity & regime divergence>",
    "<Bullet 2: 1 concise takeaway on top actionable positioning / spread trade setup>",
    "<Bullet 3: 1 concise takeaway on the most critical near-term catalyst & risk invalidation trigger for {cur_month}/{next_month}>"
  ],
  "macro_note": "<2 sentences: S1 — IF analyst reports mention any active armed conflict, sanctions, or supply route disruption, NAME IT EXPLICITLY then explain its freight transmission mechanism; ELSE name the specific macro driver active today and its direct freight impact with supporting data. S2 — name the SPECIFIC upcoming data release or event for {cur_month}/{next_month} {next_year} that will either confirm or invalidate the current freight thesis — NEVER reference past months>"
}}"""


def _repair_json(raw: str) -> str:
    """Best-effort repairs for common LLM JSON mistakes."""
    import re as _re
    # Python literals → JSON
    raw = _re.sub(r"\bNone\b", "null", raw)
    raw = _re.sub(r"\bTrue\b", "true", raw)
    raw = _re.sub(r"\bFalse\b", "false", raw)
    # Trailing commas before } or ]
    raw = _re.sub(r",\s*([}\]])", r"\1", raw)
    # Single-quoted keys and values → double-quoted (without destroying internal apostrophes in double quotes)
    raw = _re.sub(r"(?<=[{,\s])'([^'\r\n]+)'\s*:", r'"\1":', raw)
    raw = _re.sub(r":\s*'([^'\r\n]*)'(?=[,\s}\]])", r': "\1"', raw)
    return raw


def _extract_json_payload(text: str | None) -> dict | None:
    if not text:
        return None
    raw = text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?", "", raw).strip()
        raw = re.sub(r"```$", "", raw).strip()
    match = re.search(r"\{.*\}", raw, re.S)
    if match:
        raw = match.group(0)
    # First attempt: parse as-is
    try:
        payload = json.loads(raw)
        if isinstance(payload, dict):
            return payload
        return None
    except json.JSONDecodeError as exc:
        print(f"[brief] JSONDecodeError: {exc}. Raw text: {raw[:200]}", file=sys.stderr)
    # Second attempt: apply common repairs
    try:
        repaired = _repair_json(raw)
        payload = json.loads(repaired)
        if isinstance(payload, dict):
            print("[brief] JSON repair succeeded.", file=sys.stderr)
            return payload
    except json.JSONDecodeError:
        pass
    return None


def _clean_text(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return text


def _clean_signals(values) -> list[str]:
    if not isinstance(values, list):
        return []
    cleaned = []
    for value in values:
        text = _clean_text(value)
        if text:
            cleaned.append(text)
    return cleaned[:8]


# ------------------------ Provider utilities ------------------------

def _is_rate_limit_error(exc_text: str) -> bool:
    lower = (exc_text or "").lower()
    return "429" in lower or "too many requests" in lower or "quota" in lower or "rate limit" in lower


def _parse_retry_after(exc_text: str) -> float | None:
    match = re.search(r"retry_after\s+([0-9]+(?:\.[0-9]+)?)", exc_text or "", re.I)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _apply_interval(last_ts: float, min_interval: float) -> float:
    now = time.monotonic()
    elapsed = now - last_ts
    wait_for = min_interval - elapsed
    if wait_for > 0:
        time.sleep(wait_for)
    return time.monotonic()


def _backoff_sleep(
    attempt: int,
    exc_text: str,
    base_delay: float,
    max_delay: float,
) -> None:
    retry_after = _parse_retry_after(exc_text)
    if retry_after is not None:
        delay = retry_after
    elif _is_rate_limit_error(exc_text):
        delay = base_delay * (2 ** attempt)
    else:
        delay = base_delay * (attempt + 1)
    delay = min(delay, max_delay)
    delay += random.uniform(0.1, 0.9)
    time.sleep(delay)


# ------------------------ Provider calls ------------------------

def ollama_available() -> bool:
    return bool(OLLAMA_BASE_URL and OLLAMA_MODEL)


def _call_ollama_once(messages: list) -> str | None:
    is_v1 = OLLAMA_BASE_URL.endswith("/v1")

    if is_v1:
        payload = {
            "model": OLLAMA_MODEL,
            "messages": messages,
            "temperature": 0.35,
            "max_tokens": 2048,
            "response_format": {"type": "json_object"},
        }
        endpoint = f"{OLLAMA_BASE_URL}/chat/completions"
    else:
        payload = {
            "model": OLLAMA_MODEL,
            "messages": messages,
            "stream": False,
            "format": "json",
        }
        endpoint = f"{OLLAMA_BASE_URL}/chat"

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if OLLAMA_API_KEY:
        headers["Authorization"] = f"Bearer {OLLAMA_API_KEY}"
    req = urllib_request.Request(
        endpoint,
        data=body,
        headers=headers,
        method="POST",
    )
    try:
        with urllib_request.urlopen(req, timeout=45) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except urllib_error.HTTPError as exc:
        retry_after = exc.headers.get("Retry-After") if exc.headers else None
        err_body = exc.read().decode("utf-8", errors="replace")
        details = err_body or str(exc)
        if retry_after:
            details = f"{details} retry_after {retry_after}"
        raise RuntimeError(f"Ollama HTTP {exc.code}: {details}") from exc
    except urllib_error.URLError as exc:
        raise RuntimeError(f"Ollama connection error: {exc}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Ollama returned non-JSON payload: {raw[:200]}") from exc

    if is_v1:
        choices = data.get("choices") or []
        if not choices:
            return None
        message = choices[0].get("message") or {}
    else:
        message = data.get("message") or {}

    text = _clean_text(message.get("content"))
    return text or None


def call_ollama_text(messages: list, retries: int | None = None) -> str | None:
    if not ollama_available():
        return None
    retries = retries or OLLAMA_MAX_RETRIES
    global _last_ollama_call_ts
    for attempt in range(retries):
        try:
            _last_ollama_call_ts = _apply_interval(_last_ollama_call_ts, OLLAMA_MIN_INTERVAL_SEC)
            return _call_ollama_once(messages)
        except Exception as exc:
            exc_text = str(exc)
            if attempt < retries - 1:
                _backoff_sleep(attempt, exc_text, OLLAMA_BACKOFF_BASE_SEC, OLLAMA_MAX_BACKOFF_SEC)
            else:
                print(f"[brief] Ollama failed: {exc_text}", file=sys.stderr)
                return None
    return None


def nim_available() -> bool:
    has_key = bool(NIM_API_KEY)
    has_model = bool(NIM_MODEL)
    has_url = bool(NIM_BASE_URL)
    key_disp = f"PRESENT (len={len(NIM_API_KEY)})" if has_key else "MISSING/EMPTY (check GitHub Secret NVIDIA_API_KEY or NIM_API_KEY)"
    print(f"[brief] NIM env check: API key={key_disp}, Model={NIM_MODEL}, BaseURL={NIM_BASE_URL}", file=sys.stderr)
    return has_key and has_model and has_url


def _call_nim_once(messages: list) -> str | None:
    payload = {
        "model": NIM_MODEL,
        "messages": messages,
        "temperature": 0.35,
        "max_tokens": 2500,
        "response_format": {"type": "json_object"},
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {NIM_API_KEY}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    }
    req = urllib_request.Request(
        f"{NIM_BASE_URL}/chat/completions",
        data=body,
        headers=headers,
        method="POST",
    )
    try:
        with urllib_request.urlopen(req, timeout=180) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except urllib_error.HTTPError as exc:
        retry_after = exc.headers.get("Retry-After") if exc.headers else None
        err_body = exc.read().decode("utf-8", errors="replace")
        details = err_body or str(exc)
        if retry_after:
            details = f"{details} retry_after {retry_after}"
        raise RuntimeError(f"NIM HTTP {exc.code}: {details}") from exc
    except urllib_error.URLError as exc:
        raise RuntimeError(f"NIM connection error: {exc}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"NIM returned non-JSON payload: {raw[:200]}") from exc
    choices = data.get("choices") or []
    if not choices:
        return None
    message = choices[0].get("message") or {}
    text = _clean_text(message.get("content"))
    return text or None


def call_nim_text(messages: list, retries: int | None = None) -> str | None:
    if not nim_available():
        return None
    retries = retries or NIM_MAX_RETRIES
    global _last_nim_call_ts
    for attempt in range(retries):
        try:
            print(f"[brief] NIM API call attempt {attempt + 1}/{retries} starting...", file=sys.stderr)
            _last_nim_call_ts = _apply_interval(_last_nim_call_ts, NIM_MIN_INTERVAL_SEC)
            res = _call_nim_once(messages)
            if res:
                print(f"[brief] NIM API call attempt {attempt + 1} SUCCESS!", file=sys.stderr)
                return res
            else:
                print(f"[brief] NIM API call attempt {attempt + 1} returned empty content.", file=sys.stderr)
        except Exception as exc:
            exc_text = str(exc)
            print(f"[brief] NIM attempt {attempt + 1}/{retries} failed with error: {exc_text}", file=sys.stderr)
            if any(code in exc_text for code in ("HTTP 400:", "HTTP 401:", "HTTP 403:", "API_KEY_INVALID")):
                print("[brief] NIM auth/client error detected; skipping further retries.", file=sys.stderr)
                return None
            if attempt < retries - 1:
                _backoff_sleep(attempt, exc_text, NIM_BACKOFF_BASE_SEC, NIM_MAX_BACKOFF_SEC)
            else:
                print(f"[brief] NIM failed all {retries} retries.", file=sys.stderr)
                return None
    return None


def groq_available() -> bool:
    has_key = bool(GROQ_API_KEY)
    has_model = bool(GROQ_MODEL)
    has_url = bool(GROQ_BASE_URL)
    key_disp = f"PRESENT (len={len(GROQ_API_KEY)})" if has_key else "MISSING/EMPTY (check GitHub Secret GROQ_API_KEY)"
    print(f"[brief] Groq env check: API key={key_disp}, Model={GROQ_MODEL}, BaseURL={GROQ_BASE_URL}", file=sys.stderr)
    return has_key and has_model and has_url


def _call_groq_once(messages: list) -> str | None:
    payload = {
        "model": GROQ_MODEL,
        "messages": messages,
        "temperature": 0.35,
        "max_tokens": 2500,
        "response_format": {"type": "json_object"},
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    }
    req = urllib_request.Request(
        f"{GROQ_BASE_URL}/chat/completions",
        data=body,
        headers=headers,
        method="POST",
    )
    try:
        with urllib_request.urlopen(req, timeout=60) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except urllib_error.HTTPError as exc:
        retry_after = exc.headers.get("Retry-After") if exc.headers else None
        err_body = exc.read().decode("utf-8", errors="replace")
        details = err_body or str(exc)
        if retry_after:
            details = f"{details} retry_after {retry_after}"
        raise RuntimeError(f"Groq HTTP {exc.code}: {details}") from exc
    except urllib_error.URLError as exc:
        raise RuntimeError(f"Groq connection error: {exc}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Groq returned non-JSON payload: {raw[:200]}") from exc
    choices = data.get("choices") or []
    if not choices:
        return None
    message = choices[0].get("message") or {}
    text = _clean_text(message.get("content"))
    return text or None


def call_groq_text(messages: list, retries: int | None = None) -> str | None:
    if not groq_available():
        return None
    retries = retries or GROQ_MAX_RETRIES
    global _last_groq_call_ts
    for attempt in range(retries):
        try:
            print(f"[brief] Groq API call attempt {attempt + 1}/{retries} starting...", file=sys.stderr)
            _last_groq_call_ts = _apply_interval(_last_groq_call_ts, GROQ_MIN_INTERVAL_SEC)
            res = _call_groq_once(messages)
            if res:
                print(f"[brief] Groq API call attempt {attempt + 1} SUCCESS!", file=sys.stderr)
                return res
            else:
                print(f"[brief] Groq API call attempt {attempt + 1} returned empty content.", file=sys.stderr)
        except Exception as exc:
            exc_text = str(exc)
            print(f"[brief] Groq attempt {attempt + 1}/{retries} failed with error: {exc_text}", file=sys.stderr)
            if any(code in exc_text for code in ("HTTP 400:", "HTTP 401:", "HTTP 403:", "invalid_api_key")):
                print("[brief] Groq auth/client error detected; skipping further retries.", file=sys.stderr)
                return None
            if attempt < retries - 1:
                _backoff_sleep(attempt, exc_text, GROQ_BACKOFF_BASE_SEC, GROQ_MAX_BACKOFF_SEC)
            else:
                print(f"[brief] Groq failed all {retries} retries.", file=sys.stderr)
                return None
    return None


def gemini_available() -> bool:
    has_key = bool(GEMINI_API_KEY)
    has_model = bool(GEMINI_MODEL)
    key_disp = f"PRESENT (len={len(GEMINI_API_KEY)})" if has_key else "MISSING/EMPTY (check GitHub Secret GEMINI_API_KEY)"
    print(f"[brief] Gemini env check: API key={key_disp}, Model={GEMINI_MODEL}", file=sys.stderr)
    return has_key and has_model


def _call_gemini_once(messages: list, model_override: str | None = None) -> str | None:
    system_text = ""
    contents = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if role == "system":
            system_text += content + "\n\n"
        elif role == "assistant":
            contents.append({"role": "model", "parts": [{"text": content}]})
        else:
            contents.append({"role": "user", "parts": [{"text": content}]})

    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": 0.35,
            "response_mime_type": "application/json",
        }
    }
    if system_text.strip():
        payload["system_instruction"] = {
            "parts": [{"text": system_text.strip()}]
        }

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    }
    target_model = (model_override or GEMINI_MODEL).replace("models/", "")
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{target_model}:generateContent?key={GEMINI_API_KEY}"
    req = urllib_request.Request(
        endpoint,
        data=body,
        headers=headers,
        method="POST",
    )
    try:
        with urllib_request.urlopen(req, timeout=60) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except urllib_error.HTTPError as exc:
        retry_after = exc.headers.get("Retry-After") if exc.headers else None
        err_body = exc.read().decode("utf-8", errors="replace")
        details = err_body or str(exc)
        if retry_after:
            details = f"{details} retry_after {retry_after}"
        raise RuntimeError(f"Gemini HTTP {exc.code}: {details}") from exc
    except urllib_error.URLError as exc:
        raise RuntimeError(f"Gemini connection error: {exc}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Gemini returned non-JSON payload: {raw[:200]}") from exc
    candidates = data.get("candidates") or []
    if not candidates:
        return None
    content_obj = candidates[0].get("content") or {}
    parts = content_obj.get("parts") or []
    if not parts:
        return None
    text = _clean_text(parts[0].get("text"))
    return text or None


def call_gemini_text(messages: list, retries: int | None = None) -> str | None:
    if not gemini_available():
        return None
    retries = retries or GEMINI_MAX_RETRIES
    global _last_gemini_call_ts
    gemini_candidates = [GEMINI_MODEL, "gemini-2.5-flash", "gemini-1.5-flash", "gemini-1.5-pro"]
    for candidate in gemini_candidates:
        for attempt in range(retries):
            try:
                print(f"[brief] Gemini API call attempt {attempt + 1}/{retries} using {candidate} starting...", file=sys.stderr)
                _last_gemini_call_ts = _apply_interval(_last_gemini_call_ts, GEMINI_MIN_INTERVAL_SEC)
                res = _call_gemini_once(messages, model_override=candidate)
                if res:
                    print(f"[brief] Gemini API call attempt {attempt + 1} SUCCESS with {candidate}!", file=sys.stderr)
                    return res
                else:
                    print(f"[brief] Gemini API call attempt {attempt + 1} returned empty content.", file=sys.stderr)
            except Exception as exc:
                exc_text = str(exc)
                print(f"[brief] Gemini attempt {attempt + 1}/{retries} ({candidate}) failed: {exc_text}", file=sys.stderr)
                if "HTTP 404:" in exc_text:
                    print(f"[brief] Gemini model {candidate} 404'd; trying next candidate model.", file=sys.stderr)
                    break
                if any(code in exc_text for code in ("HTTP 400:", "HTTP 401:", "HTTP 403:", "API_KEY_INVALID")):
                    print("[brief] Gemini auth/client error detected; skipping further retries.", file=sys.stderr)
                    return None
                if attempt < retries - 1:
                    _backoff_sleep(attempt, exc_text, GEMINI_BACKOFF_BASE_SEC, GEMINI_MAX_BACKOFF_SEC)
    return None


def openrouter_available() -> bool:
    has_key = bool(OPENROUTER_API_KEY)
    has_model = bool(OPENROUTER_MODEL)
    has_url = bool(OPENROUTER_BASE_URL)
    key_disp = f"PRESENT (len={len(OPENROUTER_API_KEY)})" if has_key else "MISSING/EMPTY (check GitHub Secret OPENROUTER_API_KEY)"
    print(f"[brief] OpenRouter env check: API key={key_disp}, Model={OPENROUTER_MODEL}, BaseURL={OPENROUTER_BASE_URL}", file=sys.stderr)
    return has_key and has_model and has_url


def _call_openrouter_once(messages: list, model_override: str | None = None) -> str | None:
    target_model = model_override or OPENROUTER_MODEL
    payload = {
        "model": target_model,
        "messages": messages,
        "temperature": 0.35,
        "max_tokens": 2500,
        "response_format": {"type": "json_object"},
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://yieldchaser.github.io/Shipping/",
        "X-Title": "Shipping Intelligence Terminal",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    }
    req = urllib_request.Request(
        f"{OPENROUTER_BASE_URL}/chat/completions",
        data=body,
        headers=headers,
        method="POST",
    )
    # Free models: 60s timeout (scale-to-zero, respond fast or not at all)
    # Paid models: 180s timeout (guaranteed capacity)
    is_free_model = ":free" in target_model or "free" in target_model.lower()
    read_timeout = 60 if is_free_model else 180
    try:
        with urllib_request.urlopen(req, timeout=read_timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except urllib_error.HTTPError as exc:
        retry_after = exc.headers.get("Retry-After") if exc.headers else None
        err_body = exc.read().decode("utf-8", errors="replace")
        details = err_body or str(exc)
        if retry_after:
            details = f"{details} retry_after {retry_after}"
        raise RuntimeError(f"OpenRouter HTTP {exc.code}: {details}") from exc
    except urllib_error.URLError as exc:
        raise RuntimeError(f"OpenRouter connection error: {exc}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"OpenRouter returned non-JSON payload: {raw[:200]}") from exc
    choices = data.get("choices") or []
    if not choices:
        return None
    message = choices[0].get("message") or {}
    text = _clean_text(message.get("content"))
    return text or None


def call_openrouter_text(messages: list, retries: int | None = None) -> str | None:
    if not openrouter_available():
        return None
    retries = retries or OPENROUTER_MAX_RETRIES
    global _last_openrouter_call_ts
    or_candidates = [
        OPENROUTER_MODEL,    # paid primary (env-configured, e.g. meta-llama/llama-3.3-70b-instruct)
        "openrouter/free",   # meta-router: auto-selects best free model (21 models, filters for
                             # structured output support, load-balances, avoids rate-limited providers)
                             # top routed models: gpt-oss-120b (13.9%), Hy3 (11.7%), nemotron-nano-30b (8.6%)
    ]
    for candidate in or_candidates:
        for attempt in range(retries):
            try:
                print(f"[brief] OpenRouter API call attempt {attempt + 1}/{retries} using {candidate} starting...", file=sys.stderr)
                _last_openrouter_call_ts = _apply_interval(_last_openrouter_call_ts, OPENROUTER_MIN_INTERVAL_SEC)
                res = _call_openrouter_once(messages, model_override=candidate)
                if res:
                    # Validate that the response is actually parseable JSON before declaring success
                    test_parse = _extract_json_payload(res)
                    if test_parse is not None:
                        print(f"[brief] OpenRouter API call attempt {attempt + 1} SUCCESS with {candidate}!", file=sys.stderr)
                        return res
                    else:
                        print(f"[brief] OpenRouter attempt {attempt + 1} ({candidate}) returned non-JSON content; trying next candidate.", file=sys.stderr)
                        break  # skip remaining retries for this candidate
                else:
                    print(f"[brief] OpenRouter API call attempt {attempt + 1} returned empty content.", file=sys.stderr)
            except Exception as exc:
                exc_text = str(exc)
                print(f"[brief] OpenRouter attempt {attempt + 1}/{retries} ({candidate}) failed: {exc_text}", file=sys.stderr)
                if "HTTP 404:" in exc_text or "unavailable for free" in exc_text or "No endpoints found" in exc_text:
                    print(f"[brief] OpenRouter model {candidate} unavailable/404; trying next candidate.", file=sys.stderr)
                    break
                if "HTTP 402:" in exc_text:
                    print(f"[brief] OpenRouter model {candidate} requires credits (402); trying next free candidate.", file=sys.stderr)
                    break
                if "HTTP 429:" in exc_text:
                    print(f"[brief] OpenRouter model {candidate} rate-limited (429); trying next candidate.", file=sys.stderr)
                    break
                if any(code in exc_text for code in ("HTTP 400:", "HTTP 401:", "HTTP 403:", "invalid_api_key")):
                    print("[brief] OpenRouter auth/client error detected; skipping further retries.", file=sys.stderr)
                    return None
                if attempt < retries - 1:
                    _backoff_sleep(attempt, exc_text, OPENROUTER_BACKOFF_BASE_SEC, OPENROUTER_MAX_BACKOFF_SEC)
    return None


def call_llm_payload(messages: list) -> tuple[dict | None, str | None, list[str]]:
    attempted: list[str] = []
    for provider in LLM_PROVIDER_ORDER:
        attempted.append(provider)
        text = None
        if provider == "groq":
            text = call_groq_text(messages)
        elif provider == "nim":
            text = call_nim_text(messages)
        elif provider == "gemini":
            text = call_gemini_text(messages)
        elif provider == "openrouter":
            text = call_openrouter_text(messages)
        elif provider == "ollama":
            text = call_ollama_text(messages)
        else:
            continue
        if not text:
            continue
        payload = _extract_json_payload(text)
        if payload:
            return payload, provider, attempted
        print(f"[brief] {provider} returned non-JSON output; trying next provider.", file=sys.stderr)
    return None, None, attempted


# ------------------------ Deterministic templates ------------------------

def _sentiment_mix(signals: list[dict]) -> tuple[str, float, str]:
    if not signals:
        return "neutral", 0.0, "no recent analyst sentiment records"
    sentiments = [_clean_text(s.get("sentiment")) or "neutral" for s in signals]
    counts = Counter(sentiments)
    dominant = counts.most_common(1)[0][0]
    score = sum(_QUAL_SCORES.get(s, 0.0) for s in sentiments) / len(sentiments)
    parts = [f"{name}:{count}" for name, count in counts.items()]
    return dominant, score, ", ".join(parts)


def _template_confluence_note(
    confluence: str,
    label: str,
    z_score: float | None,
    qual_score: float,
    tally: dict | None = None,
) -> str:
    z_txt = _fmt_signed(z_score, 2, "sigma")
    tally_str = ""
    if tally:
        tally_str = (
            f" Of {tally['n']} Breakwave reports: "
            f"Sentiment {tally['sp']} pos/{tally['sn']} neg/{tally['su']} neu; "
            f"Momentum {tally['mp']} pos/{tally['mn']} neg/{tally['mu']} neu; "
            f"Fundamentals {tally['fp']} pos/{tally['fn']} neg/{tally['fu']} neu."
        )
    if confluence == "BULL_CONFLUENCE":
        return (
            f"Quant momentum and analyst signals align bullishly for {label} "
            f"(Z={z_txt}).{tally_str}"
        )
    if confluence == "BEAR_CONFLUENCE":
        return (
            f"Quant momentum and analyst signals align bearishly for {label} "
            f"(Z={z_txt}).{tally_str}"
        )
    if confluence == "DIVERGENCE":
        return (
            f"Quant and analyst signals disagree for {label} (Z={z_txt}): "
            f"rates are elevated but fundamentals are under pressure.{tally_str}"
        )
    return (
        f"Signal alignment is mixed for {label} (Z={z_txt}); "
        f"conviction remains limited.{tally_str}"
    )


def _template_outlook(confluence: str, label: str) -> str:
    if confluence == "BULL_CONFLUENCE":
        return f"Bias stays constructive for {label} while momentum and sentiment remain aligned."
    if confluence == "BEAR_CONFLUENCE":
        return f"Bias stays defensive for {label} unless sentiment and momentum materially improve."
    if confluence == "DIVERGENCE":
        return f"{label} remains tactical; resolution should come from either analyst upgrades or price mean reversion."
    return f"{label} outlook is range-bound until either quant momentum or analyst tone breaks decisively."


def _template_watch(confluence: str, latest_signal: dict | None) -> str:
    if confluence == "DIVERGENCE":
        return "Watch whether the next analyst print confirms momentum or rejects it."
    if latest_signal and latest_signal.get("fundamentals"):
        return f"Watch fundamentals trend in the next report ({latest_signal.get('fundamentals')})."
    if confluence == "BULL_CONFLUENCE":
        return "Watch for momentum rollover in spot rates or a downshift in report sentiment."
    if confluence == "BEAR_CONFLUENCE":
        return "Watch for sentiment stabilization that could trigger a countertrend rebound."
    return "Watch for a clear break in both momentum and analyst tone."


def _template_macro_note(dry_conf: str, tanker_conf: str) -> str:
    if dry_conf == tanker_conf and dry_conf in {"BULL_CONFLUENCE", "BEAR_CONFLUENCE"}:
        direction = "risk-on" if dry_conf == "BULL_CONFLUENCE" else "risk-off"
        return f"Cross-sector signal alignment is {direction}: dry bulk and tanker narratives point in the same direction."
    if "DIVERGENCE" in {dry_conf, tanker_conf}:
        return "Cross-sector setup is mixed: at least one vessel class is in divergence, so relative-value positioning may outperform outright beta."
    return "Cross-sector signals are mixed with no broad confluence across dry bulk and tanker segments."


def _template_cross_sector(snapshot: dict, dry_conf: str, tanker_conf: str) -> dict:
    bdi = snapshot.get("bdi", {})
    dirty = snapshot.get("dirty_tanker", {})
    dry_z = bdi.get("z_score_252d", 0.0) or 0.0
    tanker_z = dirty.get("z_score_252d", 0.0) or 0.0
    z_diff = dry_z - tanker_z

    if z_diff > 0.5:
        rv = f"Dry Bulk displays stronger statistical momentum than Tankers (Z-differential {_fmt_signed(z_diff, 2)}σ), favoring dry bulk spread positioning."
        pos = "Overweight Dry Bulk (BDI/Capesize) relative to Tanker assets on favorable commodity restocking momentum."
    elif z_diff < -0.5:
        rv = f"Tankers outperform Dry Bulk on quantitative velocity (Z-differential {_fmt_signed(z_diff, 2)}σ), favoring energy freight over industrial dry bulk."
        pos = "Overweight Dirty Tankers (BDTI/VLCC) relative to Dry Bulk on resilient crude flows."
    else:
        rv = f"Dry Bulk and Tanker sectors are closely balanced (Z-differential {_fmt_signed(z_diff, 2)}σ), favoring segment-specific selection over broad sector rotations."
        pos = "Maintain sector-neutral freight weighting; focus on intra-segment Capesize/Panamax or Clean/Dirty spread trades."

    dom = "Global industrial commodity restocking cycles and regional geopolitical rerouting across key maritime choke points."

    return {
        "relative_value": rv,
        "dominant_driver": dom,
        "positioning_recommendation": pos,
    }


def _template_executive_tldr(dry_entry: dict, tanker_entry: dict, cross_sector: dict, macro_note: str) -> list[str]:
    dry_conf = dry_entry.get("confluence_type", "").replace("_", " ").title()
    tanker_conf = tanker_entry.get("confluence_type", "").replace("_", " ").title()
    rv = cross_sector.get("relative_value", "")
    pos = cross_sector.get("positioning_recommendation", "")
    cat = dry_entry.get("catalyst_watch") or tanker_entry.get("catalyst_watch") or "Monitor upcoming weekly freight prints."
    risk = dry_entry.get("risk_note") or tanker_entry.get("risk_note") or "Watch for moving average breakdown."

    return [
        f"Regime Split: Dry Bulk is in {dry_conf} while Tankers exhibit {tanker_conf}. {rv}",
        f"Tactical Desk Strategy: {pos}",
        f"Catalyst & Risk Boundary: {cat} Invalidation Trigger: {risk}"
    ]


def _template_vessel_entry(
    vessel_key: str,
    pre_conf: str,
    qual_signals: list[dict],
    snapshot: dict,
    tanker_z: float | None,
) -> dict:
    is_dry = vessel_key == "dry_bulk"
    label = "dry bulk" if is_dry else "tanker"
    primary_key = "bdi" if is_dry else "clean_tanker"
    secondary_key = "capesize" if is_dry else "dirty_tanker"
    primary = snapshot.get(primary_key, {})
    secondary = snapshot.get(secondary_key, {})
    primary_value = primary.get("value")
    primary_regime = primary.get("regime", "N/A")
    primary_z = primary.get("z_score_252d")
    primary_roc = primary.get("roc60")
    primary_pctl = primary.get("pctl_5y")
    z_for_logic = primary_z if is_dry else tanker_z
    latest_signal = qual_signals[0] if qual_signals else None
    dominant_sentiment, qual_score, sentiment_mix = _sentiment_mix(qual_signals)

    # Build tally dict for the template confluence note
    def _tc(field: str) -> tuple[int, int, int]:
        p = sum(1 for s in qual_signals if str(s.get(field, "")).lower() == "positive")
        n = sum(1 for s in qual_signals if str(s.get(field, "")).lower() == "negative")
        return p, n, len(qual_signals) - p - n
    sp, sn, su = _tc("sentiment")
    mp, mn, mu = _tc("momentum")
    fp, fn, fu = _tc("fundamentals")
    tally = dict(n=len(qual_signals), sp=sp, sn=sn, su=su, mp=mp, mn=mn, mu=mu, fp=fp, fn=fn, fu=fu)

    summary_parts = [
        f"{label.title()} is in {primary_regime.lower()} regime at {primary_value if primary_value is not None else 'N/A'}, "
        f"with z-score {_fmt_signed(z_for_logic, 2, 'sigma')} and ROC60 {_fmt_signed(primary_roc, 1, '%')}.",
        f"Recent analyst sentiment skews {dominant_sentiment} ({sentiment_mix}).",
        _template_confluence_note(pre_conf, label, z_for_logic, qual_score, tally=tally),
    ]
    summary = " ".join(part.strip() for part in summary_parts if part.strip())

    key_signals = [
        f"Quant: {primary_key.upper()} value={primary_value if primary_value is not None else 'N/A'}, "
        f"z={_fmt_signed(z_for_logic, 2, 'sigma')}, 5Y percentile={_fmt_percentile(primary_pctl)}.",
        f"Qual: last {len(qual_signals)} reports sentiment mix -> {sentiment_mix}.",
    ]
    if secondary:
        key_signals.append(
            f"Cross-check: {secondary_key.upper()} value={secondary.get('value', 'N/A')}, "
            f"z={_fmt_signed(secondary.get('z_score_252d'), 2, 'sigma')}."
        )
    if latest_signal:
        key_signals.append(
            f"Latest report {latest_signal.get('date')}: momentum={latest_signal.get('momentum') or 'N/A'}, "
            f"fundamentals={latest_signal.get('fundamentals') or 'N/A'}."
        )

    # Deterministic Momentum Grade
    z_val = z_for_logic if z_for_logic is not None else 0.0
    roc_val = primary_roc if primary_roc is not None else 0.0
    if z_val > 1.5 and roc_val > 10:
        momentum_grade = "STRONG_UP"
    elif z_val > 0.5 or roc_val > 5:
        momentum_grade = "UP"
    elif abs(z_val) <= 0.5 and abs(roc_val) <= 5:
        momentum_grade = "FLAT"
    elif z_val < -1.5 and roc_val < -10:
        momentum_grade = "STRONG_DOWN"
    else:
        momentum_grade = "DOWN"

    # Deterministic Positioning Bias, Confidence, Trade Idea, Catalysts, Risks
    if pre_conf == "BULL_CONFLUENCE":
        positioning_bias = "LONG"
        confidence_score = 0.80
        if is_dry:
            trade_idea = f"Tactical long {primary_key.upper()} exposure on pullbacks toward MA200 ({primary.get('ma200', 'N/A')}), targeting trend extension while momentum grade is {momentum_grade}."
            catalyst_watch = "China steel PMI and iron ore port inventory draws over the next 2-4 weeks are the primary directional catalysts."
            risk_note = f"A reversal below {primary.get('ma200', 'N/A')} or negative shift in Capesize voyage fixtures would invalidate the bullish thesis."
        else:
            trade_idea = f"Long {secondary_key.upper()} vs {primary_key.upper()} spread to capture dirty tanker momentum outperformance."
            catalyst_watch = "Upcoming OPEC+ production quota decisions and Middle East route fixture volume are the near-term catalysts."
            risk_note = "A sudden compression in crude arbitrage margins or rapid fleet repositioning would invalidate the upside thesis."
    elif pre_conf == "BEAR_CONFLUENCE":
        positioning_bias = "SHORT"
        confidence_score = 0.75
        trade_idea = f"Defensive hedge on freight beta; reduce high-beta vessel exposure until momentum stabilizes above Z=-0.50σ."
        catalyst_watch = "Watch for scrap demolition acceleration or fleet layups as early indicators of supply tightening."
        risk_note = "Unexpected stimulus or supply disruption creating a sharp spot squeeze would invalidate the defensive stance."
    elif pre_conf == "DIVERGENCE":
        positioning_bias = "LONG_SPREAD_VS_TANKER" if is_dry else "SHORT_SPREAD_VS_DRY"
        confidence_score = 0.55
        trade_idea = f"No outright high-conviction direction: trade the relative-value spread between {primary_key.upper()} and {secondary_key.upper()} rather than outright directional beta."
        catalyst_watch = "Resolution of the tension between spot rate levels and analyst fundamental grades in the next reporting print."
        risk_note = "A breakdown in rate-of-change momentum below ROC60=0.0% would confirm that fundamentals are dragging spot prices lower."
    else:
        positioning_bias = "NEUTRAL"
        confidence_score = 0.45
        trade_idea = "No high-conviction setup: Maintain neutral book positioning and await decisive alignment between momentum and freight fundamentals."
        catalyst_watch = "Next weekly Baltic Exchange index revisions and Breakwave fundamental assessment."
        risk_note = "A rapid expansion beyond ±1.0σ Z-score would break the current range-bound regime."

    return {
        "confluence_type": pre_conf if pre_conf in CONFLUENCE_TYPES else "NEUTRAL",
        "momentum_grade": momentum_grade,
        "positioning_bias": positioning_bias,
        "confidence_score": confidence_score,
        "confluence_note": _template_confluence_note(pre_conf, label, z_for_logic, qual_score, tally=tally),
        "summary": summary,
        "key_signals": key_signals[:6],
        "trade_idea": trade_idea,
        "outlook": _template_outlook(pre_conf, label),
        "catalyst_watch": catalyst_watch,
        "watch": catalyst_watch,
        "risk_note": risk_note,
        "report_dates": [s.get("date") for s in qual_signals if s.get("date")],
    }


def _overlay_vessel(template_entry: dict, llm_entry: dict | None, pre_conf: str = "NEUTRAL") -> dict:
    result = dict(template_entry)
    if not isinstance(llm_entry, dict):
        return result

    # ── Confluence label is ALWAYS the Python pre-computed value ────────────────
    # The LLM writes narrative text only. It cannot override the label badge
    # because small models (ollama) hallucinate wrong counts and soften/flip
    # factual computations. pre_conf is already set correctly by template_entry.
    llm_conf = _clean_text(llm_entry.get("confluence_type")).upper()
    if llm_conf in CONFLUENCE_TYPES and llm_conf != pre_conf:
        print(
            f"[brief] INFO: LLM confluence '{llm_conf}' differs from "
            f"pre-computed '{pre_conf}' — keeping Python verdict.",
            file=sys.stderr,
        )

    for key in ("summary", "outlook", "watch"):
        text = _clean_text(llm_entry.get(key))
        if text:
            result[key] = text
    # catalyst_watch from LLM overrides the deterministic template watch
    catalyst = _clean_text(llm_entry.get("catalyst_watch"))
    if catalyst:
        result["watch"] = catalyst
    # New world-class fields — pass through if present
    for key in ("momentum_grade", "positioning_bias", "trade_idea", "catalyst_watch", "risk_note"):
        text = _clean_text(llm_entry.get(key))
        if text:
            result[key] = text
    cs = llm_entry.get("confidence_score")
    if cs is not None:
        try:
            result["confidence_score"] = round(float(cs), 3)
        except (TypeError, ValueError):
            pass
    key_signals = _clean_signals(llm_entry.get("key_signals"))
    if key_signals:
        result["key_signals"] = key_signals
    return result


def _ensure_tanker_segment_coverage(entry: dict, snapshot: dict) -> dict:
    """Ensure tanker narrative explicitly references both clean and dirty segments."""
    result = dict(entry)
    clean = snapshot.get("clean_tanker", {})
    dirty = snapshot.get("dirty_tanker", {})
    if not clean and not dirty:
        return result

    clean_value = clean.get("value")
    dirty_value = dirty.get("value")
    clean_roc = clean.get("roc60")
    dirty_roc = dirty.get("roc60")

    summary = _clean_text(result.get("summary"))
    summary_lower = summary.lower()
    if summary and ("clean" in summary_lower) and ("dirty" not in summary_lower):
        clean_seg = (
            f"clean tankers at {clean_value if clean_value is not None else 'N/A'} "
            f"(ROC60 {_fmt_signed(clean_roc, 1, '%')})"
        )
        dirty_seg = (
            f"dirty tankers at {dirty_value if dirty_value is not None else 'N/A'} "
            f"(ROC60 {_fmt_signed(dirty_roc, 1, '%')})"
        )
        result["summary"] = (
            summary.rstrip(".")
            + f". Segment breadth remains important: {clean_seg}, alongside {dirty_seg}."
        )

    key_signals = list(result.get("key_signals") or [])
    key_text = " ".join(str(s).lower() for s in key_signals)
    if "dirty" not in key_text:
        key_signals.append(
            f"Dirty tanker check: level={dirty_value if dirty_value is not None else 'N/A'}, "
            f"ROC60={_fmt_signed(dirty_roc, 1, '%')}."
        )
    if key_signals:
        result["key_signals"] = key_signals[:8]

    return result


def _sanitize_text_units(text: str | None) -> str | None:
    if not text or not isinstance(text, str):
        return text
    # Fix "$3200 on the BDI" -> "3,200 points on the BDI", "$3000 BDI" -> "3,000 points BDI", "$3200 on BDI" -> "3,200 points on BDI"
    text = re.sub(r'\$(\d+(?:,\d+)?(?:\.\d+)?)\s*(?:points\s*)?(?:on\s+(?:the\s+)?)?(BDI|BCI|BPI|BSI|BHSI|BDTI|BCTI|Baltic Dry Index)', r'\1 points on the \2', text, flags=re.IGNORECASE)
    text = re.sub(r'\$(\d+(?:,\d+)?(?:\.\d+)?)\s*(BDI|BCI|BPI|BSI|BHSI|BDTI|BCTI)', r'\1 points \2', text, flags=re.IGNORECASE)
    text = re.sub(r'(BDI|BCI|BPI|BSI|BHSI|BDTI|BCTI)\s*(?:at |of |above |below )?\$(\d+(?:,\d+)?(?:\.\d+)?)', r'\1 at \2 points', text, flags=re.IGNORECASE)
    return text


def _sanitize_brief_data(obj):
    if isinstance(obj, str):
        return _sanitize_text_units(obj)
    elif isinstance(obj, dict):
        return {k: _sanitize_brief_data(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_sanitize_brief_data(v) for v in obj]
    return obj


# ------------------------ Main ------------------------

def main() -> None:
    BRIEFS.mkdir(parents=True, exist_ok=True)

    print("[brief] Building market snapshot from CSVs...")
    snapshot = build_market_snapshot()
    if not snapshot:
        print("[brief] ERROR: no CSV data found; aborting.", file=sys.stderr)
        sys.exit(1)

    print("[brief] Loading qualitative signals...")
    signals = load_signals()
    dry_signals = recent_breakwave(signals, "drybulk")
    tanker_signals = recent_breakwave(signals, "tankers")

    dry_z = snapshot.get("bdi", {}).get("z_score_252d")
    tanker_z = compute_tanker_z(snapshot)
    pre_dry_conf = compute_confluence(
        dry_z,
        sentiments=[s.get("sentiment") or "neutral" for s in dry_signals],
        momentums=[s.get("momentum") or "neutral" for s in dry_signals],
        fundamentals=[s.get("fundamentals") or "neutral" for s in dry_signals],
    )
    pre_tanker_conf = compute_confluence(
        tanker_z,
        sentiments=[s.get("sentiment") or "neutral" for s in tanker_signals],
        momentums=[s.get("momentum") or "neutral" for s in tanker_signals],
        fundamentals=[s.get("fundamentals") or "neutral" for s in tanker_signals],
    )

    print("[brief] Loading wiki excerpts...")
    wiki_dry = wiki_excerpt(WIKI_EXCERPTS["dry_bulk"])
    wiki_tanker = wiki_excerpt(WIKI_EXCERPTS["tanker"])
    wiki_cape = wiki_excerpt(WIKI_EXCERPTS["capesize"])

    print(f"[brief] Provider order: {','.join(LLM_PROVIDER_ORDER)}")
    print("[brief] Loading recent Breakwave report narratives...")
    dry_report_text = load_recent_report_text("drybulk")
    tanker_report_text = load_recent_report_text("tankers")

    print(f"[brief] Loading Baltic Exchange weekly reports (last {BALTIC_REPORTS} weeks)...")
    baltic_dry_text = load_baltic_report_text("dry")
    baltic_tanker_text = load_baltic_report_text("tanker")

    spreads = compute_spreads(snapshot)
    system_msg = build_system_message()
    user_msg = build_user_message(
        snapshot, dry_signals, tanker_signals,
        wiki_dry, wiki_tanker, wiki_cape,
        dry_report_text, tanker_report_text,
        spreads=spreads,
        baltic_dry_text=baltic_dry_text,
        baltic_tanker_text=baltic_tanker_text,
        pre_dry_conf=pre_dry_conf,
        pre_tanker_conf=pre_tanker_conf,
    )
    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user",   "content": user_msg},
    ]
    llm_payload, provider_used, attempted = call_llm_payload(messages)
    if provider_used:
        print(f"[brief] LLM response accepted from: {provider_used}")
    else:
        print("[brief] All providers unavailable or invalid; using deterministic template.")

    template_dry = _template_vessel_entry("dry_bulk", pre_dry_conf, dry_signals, snapshot, tanker_z)
    template_tanker = _template_vessel_entry("tanker", pre_tanker_conf, tanker_signals, snapshot, tanker_z)

    llm_vessel = (llm_payload or {}).get("vessel_classes", {})
    dry_entry = _overlay_vessel(template_dry, llm_vessel.get("dry_bulk"), pre_conf=pre_dry_conf)
    tanker_entry = _overlay_vessel(template_tanker, llm_vessel.get("tanker"), pre_conf=pre_tanker_conf)
    tanker_entry = _ensure_tanker_segment_coverage(tanker_entry, snapshot)

    macro_note = _clean_text((llm_payload or {}).get("macro_note"))
    if not macro_note:
        macro_note = _template_macro_note(dry_entry["confluence_type"], tanker_entry["confluence_type"])

    today = date.today().isoformat()
    generated_at = datetime.now(timezone.utc).isoformat()
    generation_mode = "llm" if provider_used else "template"
    generation_provider = provider_used or "template"

    model_name = ""
    if generation_provider == "ollama":
        model_name = OLLAMA_MODEL
    elif generation_provider == "nim":
        model_name = NIM_MODEL
    elif generation_provider == "groq":
        model_name = GROQ_MODEL
    elif generation_provider == "gemini":
        model_name = GEMINI_MODEL
    elif generation_provider == "openrouter":
        model_name = OPENROUTER_MODEL

    cross_sector = (llm_payload or {}).get("cross_sector_analysis")
    if not isinstance(cross_sector, dict) or not cross_sector.get("relative_value"):
        cross_sector = _template_cross_sector(snapshot, dry_entry["confluence_type"], tanker_entry["confluence_type"])

    tldr_raw = (llm_payload or {}).get("executive_tldr")
    if isinstance(tldr_raw, list) and len(tldr_raw) > 0:
        executive_tldr = [_clean_text(str(b)) for b in tldr_raw if _clean_text(str(b))]
    elif isinstance(tldr_raw, str) and len(tldr_raw) > 10:
        executive_tldr = [_clean_text(b) for b in tldr_raw.split("\n") if _clean_text(b)]
    else:
        executive_tldr = _template_executive_tldr(dry_entry, tanker_entry, cross_sector, macro_note)

    output = {
        "generated_at": generated_at,
        "brief_date": today,
        "constituent_holdings": {
            "bdry": compute_etf_curve_metrics("bdry", load_etf_holdings_data("bdry"), load_sgx_curve_data()),
            "bwet": compute_etf_curve_metrics("bwet", load_etf_holdings_data("bwet"), load_sgx_curve_data())
        },
        "generation": {
            "mode": generation_mode,
            "provider_used": generation_provider,
            "model": model_name,
            "provider_order": LLM_PROVIDER_ORDER,
            "attempted_providers": attempted,
        },
        "executive_tldr": executive_tldr,
        "market_snapshot": snapshot,
        "vessel_classes": {
            "dry_bulk": dry_entry,
            "tanker": tanker_entry,
        },
        "macro_note": macro_note,
        "cross_sector_analysis": cross_sector,
        "sources": [s["doc_id"] for s in dry_signals + tanker_signals if s.get("doc_id")],
    }
    output = _sanitize_brief_data(output)

    latest_path = BRIEFS / "latest.json"
    dated_path = BRIEFS / f"{today}.json"
    for out_path in (latest_path, dated_path):
        out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
        try:
            display_path = out_path.relative_to(ROOT)
        except ValueError:
            display_path = out_path
        print(f"[brief] Wrote {display_path}")

    all_dates = sorted([p.stem for p in BRIEFS.glob("????-??-??.json")], reverse=True)
    manifest_data = {
        "latest_date": all_dates[0] if all_dates else "",
        "total_briefs": len(all_dates),
        "dates": all_dates
    }
    (BRIEFS / "manifest.json").write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")
    print("[brief] Wrote knowledge/briefs/manifest.json")

    print(
        "[brief] Done "
        f"dry={output['vessel_classes']['dry_bulk']['confluence_type']} "
        f"tanker={output['vessel_classes']['tanker']['confluence_type']} "
        f"mode={generation_mode} provider={generation_provider}"
    )


if __name__ == "__main__":
    main()
