"""
Daily shipping market brief generator.

Reads quantitative CSV data + recent Breakwave signals + wiki context and writes:
  knowledge/briefs/latest.json
  knowledge/briefs/YYYY-MM-DD.json

LLM provider order: ollama -> nim (Gemini removed — paid inference).
If all providers fail, a deterministic template brief is generated.
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
from datetime import date, datetime, timezone
from pathlib import Path
from urllib import error as urllib_error
from urllib import request as urllib_request

ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE = ROOT / "knowledge"
DERIVED = KNOWLEDGE / "derived"
WIKI = KNOWLEDGE / "wiki"
BRIEFS = KNOWLEDGE / "briefs"

SIGNALS_FILE = DERIVED / "signals.jsonl"

# CSV files: key -> path  (DD-MM-YYYY, Index, %Change)
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
RECENT_REPORTS = 12

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip()
GEMINI_MIN_INTERVAL_SEC = float(os.environ.get("GEMINI_MIN_INTERVAL_SEC", "1.5"))
GEMINI_MAX_RETRIES = int(os.environ.get("GEMINI_MAX_RETRIES", "3"))
GEMINI_BACKOFF_BASE_SEC = float(os.environ.get("GEMINI_BACKOFF_BASE_SEC", "2.0"))
GEMINI_MAX_BACKOFF_SEC = float(os.environ.get("GEMINI_MAX_BACKOFF_SEC", "20.0"))

OLLAMA_API_KEY = os.environ.get("OLLAMA_API_KEY", "").strip()
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "").strip()
OLLAMA_BASE_URL = (os.environ.get("OLLAMA_BASE_URL") or "").strip().rstrip("/")
OLLAMA_MIN_INTERVAL_SEC = float(os.environ.get("OLLAMA_MIN_INTERVAL_SEC", "1.5"))
OLLAMA_MAX_RETRIES = int(os.environ.get("OLLAMA_MAX_RETRIES", "3"))
OLLAMA_BACKOFF_BASE_SEC = float(os.environ.get("OLLAMA_BACKOFF_BASE_SEC", "1.5"))
OLLAMA_MAX_BACKOFF_SEC = float(os.environ.get("OLLAMA_MAX_BACKOFF_SEC", "15.0"))

NIM_API_KEY = os.environ.get("NIM_API_KEY", "").strip()
NIM_MODEL = os.environ.get("NIM_MODEL", "").strip()
NIM_BASE_URL = (os.environ.get("NIM_BASE_URL") or "https://integrate.api.nvidia.com/v1").strip().rstrip("/")
NIM_MIN_INTERVAL_SEC = float(os.environ.get("NIM_MIN_INTERVAL_SEC", "1.5"))
NIM_MAX_RETRIES = int(os.environ.get("NIM_MAX_RETRIES", "3"))
NIM_BACKOFF_BASE_SEC = float(os.environ.get("NIM_BACKOFF_BASE_SEC", "1.5"))
NIM_MAX_BACKOFF_SEC = float(os.environ.get("NIM_MAX_BACKOFF_SEC", "15.0"))

ALLOWED_PROVIDERS = {"ollama", "nim"}
LLM_PROVIDER_ORDER = [
    part.strip().lower()
    for part in os.environ.get("LLM_PROVIDER_ORDER", "ollama,nim").split(",")
    if part.strip().lower() in ALLOWED_PROVIDERS
]
if not LLM_PROVIDER_ORDER:
    LLM_PROVIDER_ORDER = ["ollama", "nim"]

_last_gemini_call_ts = 0.0
_last_ollama_call_ts = 0.0
_last_nim_call_ts = 0.0

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


def compute_confluence(z_score: float | None, sentiments: list[str]) -> str:
    """Classify confluence between quantitative Z-score and qualitative sentiments.

    Uses exponential decay weighting (0.85^i) consistent with the JS
    Signal Engine so that both systems produce the same confluence verdict.
    """
    if not sentiments or z_score is None:
        return "NEUTRAL"
    decay = 0.85
    weights = [decay ** i for i in range(len(sentiments))]
    qual_score = sum(w * _QUAL_SCORES.get(s, 0.0) for w, s in zip(weights, sentiments)) / sum(weights)
    if z_score > 0.5 and qual_score > 0.25:
        return "BULL_CONFLUENCE"
    if z_score < -0.5 and qual_score < -0.25:
        return "BEAR_CONFLUENCE"
    if (z_score > 0.5 and qual_score < -0.25) or (z_score < -0.5 and qual_score > 0.25):
        return "DIVERGENCE"
    return "NEUTRAL"


def wiki_excerpt(path: Path, max_chars: int = 2000) -> str:
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
    return "\n".join(lines)


def build_system_message() -> str:
    return (
        "You are a quantitative freight strategist at a tier-1 commodity trading desk. "
        "Your daily brief is read by portfolio managers who trade freight derivatives (FFAs, options) "
        "and shipping equities. You have 15 years of experience interpreting Baltic Exchange indices, "
        "Breakwave Advisors reports, and cross-sector freight positioning.\n\n"
        "MANDATORY WRITING RULES:\n"
        "1. Every claim must cite at least one specific number (Z-score, ROC60, index level, percentile, or spread).\n"
        "2. Institutional language only: direct and precise. No hedging filler.\n"
        "3. BANNED PHRASES (never use): 'it is worth noting', 'importantly', 'it is crucial', "
        "'it should be noted', 'as mentioned', 'in conclusion', 'overall', 'in summary', "
        "'the data suggests', 'it appears', 'it seems', 'needless to say'.\n"
        "4. 'summary' MUST be EXACTLY 4 sentences: (1) current level + regime with exact value, "
        "(2) momentum direction with exact Z-score and ROC60, "
        "(3) analyst consensus citing the most recent Breakwave reports, "
        "(4) the confluence or divergence verdict with specific drivers.\n"
        "5. Each 'key_signals' entry must contain at least one specific number.\n"
        "6. 'confluence_note' must name the exact Z-score and exact sentiment distribution counts.\n"
        "7. 'trade_idea' must name a direction, vehicle (spot, FFA, specific route), and a rate target or trigger.\n"
        "8. 'catalyst_watch' must name 2-3 specific upcoming events or seasonal patterns with approximate timing.\n"
        "9. 'confidence_score': float 0.0-1.0 where 1.0 = perfect quant+qual convergence, 0.0 = complete contradiction.\n"
        "10. 'momentum_grade': derive from ROC60 and Z-score: STRONG_UP (Z>1.5 and ROC>10%), "
        "UP (Z>0.5 or ROC>5%), FLAT (|Z|<=0.5 and |ROC|<=5%), DOWN (Z<-0.5 or ROC<-5%), "
        "STRONG_DOWN (Z<-1.5 and ROC<-10%).\n\n"
        "OUTPUT: Respond ONLY with a single valid JSON object. No preamble, no markdown, no explanation."
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
) -> str:
    today = date.today().isoformat()
    analytics = _build_analytics_context(snapshot, spreads or {})
    dry_block = "\n".join(_fmt_rich_signal(s, i) for i, s in enumerate(dry_signals)) or "No recent reports."
    tanker_block = "\n".join(_fmt_rich_signal(s, i) for i, s in enumerate(tanker_signals)) or "No recent reports."
    n_dry = len([r for r in dry_report_text.split("---") if r.strip()])
    n_tank = len([r for r in tanker_report_text.split("---") if r.strip()])
    return f"""DAILY FREIGHT INTELLIGENCE BRIEF — {today}

{analytics}

RECENT BREAKWAVE DRY BULK ANALYST SIGNALS (newest first, exponential decay weighting applies):
{dry_block}

RECENT BREAKWAVE TANKER ANALYST SIGNALS (newest first, exponential decay weighting applies):
{tanker_block}

ANALYST REPORT NARRATIVES — DRY BULK (last {n_dry} reports, newest first):
{dry_report_text}

ANALYST REPORT NARRATIVES — TANKERS (last {n_tank} reports, newest first):
{tanker_report_text}

STRUCTURAL MARKET CONTEXT:
[Dry Bulk Market]
{wiki_dry}

[Capesize Segment]
{wiki_cape}

[Tanker Market]
{wiki_tanker}

TASK: Generate today's institutional freight brief. Apply exponential decay (0.85^i) to historical signals.
Return ONLY valid JSON matching this exact schema:
{{
  "vessel_classes": {{
    "dry_bulk": {{
      "confluence_type": "<BULL_CONFLUENCE|BEAR_CONFLUENCE|DIVERGENCE|NEUTRAL>",
      "momentum_grade": "<STRONG_UP|UP|FLAT|DOWN|STRONG_DOWN>",
      "confidence_score": <float 0.0-1.0>,
      "confluence_note": "<2 sentences naming exact Z-score and sentiment distribution>",
      "summary": "<EXACTLY 4 sentences: level+regime | momentum+Z+ROC | analyst consensus | verdict>",
      "key_signals": ["<up to 8 signals, each with a specific number>"],
      "positioning_bias": "<LONG|SHORT|NEUTRAL|LONG_SPREAD_VS_TANKER|SHORT_SPREAD_VS_TANKER>",
      "trade_idea": "<1 actionable sentence: direction, vehicle, rate target or trigger>",
      "outlook": "<1 sentence with explicit 2-4 week time horizon>",
      "catalyst_watch": "<1 sentence naming 2-3 specific upcoming events or seasonal patterns>",
      "risk_note": "<1 sentence of primary tail risk with specific trigger>"
    }},
    "tanker": {{
      "confluence_type": "<BULL_CONFLUENCE|BEAR_CONFLUENCE|DIVERGENCE|NEUTRAL>",
      "momentum_grade": "<STRONG_UP|UP|FLAT|DOWN|STRONG_DOWN>",
      "confidence_score": <float 0.0-1.0>,
      "confluence_note": "<2 sentences naming exact Z-score and sentiment distribution>",
      "summary": "<EXACTLY 4 sentences: level+regime (clean and dirty) | momentum | analyst consensus | verdict>",
      "key_signals": ["<up to 8 signals, each with a specific number>"],
      "positioning_bias": "<LONG|SHORT|NEUTRAL|LONG_SPREAD_VS_DRY|SHORT_SPREAD_VS_DRY>",
      "trade_idea": "<1 actionable sentence: direction, vehicle, rate target or trigger>",
      "outlook": "<1 sentence with explicit 2-4 week time horizon>",
      "catalyst_watch": "<1 sentence naming 2-3 specific upcoming events or seasonal patterns>",
      "risk_note": "<1 sentence of primary tail risk with specific trigger>"
    }}
  }},
  "cross_sector_analysis": {{
    "relative_value": "<1 sentence on dry vs tanker relative momentum with specific spread or Z differential>",
    "dominant_driver": "<1 sentence naming the single biggest macro force across both sectors>",
    "positioning_recommendation": "<1 specific cross-sector trade recommendation>"
  }},
  "macro_note": "<2 sentences: dominant macro driver + its directional impact, then key risk to monitor>"
}}"""


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
    try:
        payload = json.loads(raw)
        if isinstance(payload, dict):
            return payload
        return None
    except json.JSONDecodeError as exc:
        print(f"[brief] JSONDecodeError: {exc}. Raw text: {raw[:1000]}", file=sys.stderr)
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

def gemini_available() -> bool:
    return bool(GEMINI_API_KEY)


def _call_gemini_once(prompt: str) -> str | None:
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.25, 
            "maxOutputTokens": 1200,
            "response_mime_type": "application/json"
        }
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    req = urllib_request.Request(
        url,
        data=body,
        headers=headers,
        method="POST",
    )
    try:
        with urllib_request.urlopen(req, timeout=150) as response:
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
    content = candidates[0].get("content") or {}
    parts = content.get("parts") or []
    if not parts:
        return None
    text = _clean_text(parts[0].get("text"))
    return text or None


def call_gemini_text(prompt: str, retries: int | None = None) -> str | None:
    if not gemini_available():
        return None
    retries = retries or GEMINI_MAX_RETRIES
    global _last_gemini_call_ts
    for attempt in range(retries):
        try:
            _last_gemini_call_ts = _apply_interval(_last_gemini_call_ts, GEMINI_MIN_INTERVAL_SEC)
            return _call_gemini_once(prompt)
        except Exception as exc:
            exc_text = str(exc)
            if attempt < retries - 1:
                _backoff_sleep(attempt, exc_text, GEMINI_BACKOFF_BASE_SEC, GEMINI_MAX_BACKOFF_SEC)
            else:
                print(f"[brief] Gemini failed: {exc_text}", file=sys.stderr)
                return None
    return None


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
        with urllib_request.urlopen(req, timeout=150) as response:
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
    return bool(NIM_API_KEY and NIM_MODEL and NIM_BASE_URL)


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
    }
    req = urllib_request.Request(
        f"{NIM_BASE_URL}/chat/completions",
        data=body,
        headers=headers,
        method="POST",
    )
    try:
        with urllib_request.urlopen(req, timeout=150) as response:
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
            _last_nim_call_ts = _apply_interval(_last_nim_call_ts, NIM_MIN_INTERVAL_SEC)
            return _call_nim_once(messages)
        except Exception as exc:
            exc_text = str(exc)
            if attempt < retries - 1:
                _backoff_sleep(attempt, exc_text, NIM_BACKOFF_BASE_SEC, NIM_MAX_BACKOFF_SEC)
            else:
                print(f"[brief] NIM failed: {exc_text}", file=sys.stderr)
                return None
    return None


def call_llm_payload(messages: list) -> tuple[dict | None, str | None, list[str]]:
    attempted: list[str] = []
    for provider in LLM_PROVIDER_ORDER:
        attempted.append(provider)
        if provider == "ollama":
            text = call_ollama_text(messages)
        elif provider == "nim":
            text = call_nim_text(messages)
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


def _template_confluence_note(confluence: str, label: str, z_score: float | None, qual_score: float) -> str:
    z_txt = _fmt_signed(z_score, 2, "sigma")
    q_txt = _fmt_signed(qual_score, 2)
    if confluence == "BULL_CONFLUENCE":
        return f"Quant momentum and analyst tone align bullishly for {label} (quant {z_txt}, qual {q_txt})."
    if confluence == "BEAR_CONFLUENCE":
        return f"Quant momentum and analyst tone align bearishly for {label} (quant {z_txt}, qual {q_txt})."
    if confluence == "DIVERGENCE":
        return f"Quant and analyst signals disagree for {label} (quant {z_txt}, qual {q_txt}), creating a two-way setup."
    return f"Signal alignment is mixed for {label} (quant {z_txt}, qual {q_txt}); conviction remains limited."


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

    summary_parts = [
        f"{label.title()} is in {primary_regime.lower()} regime at {primary_value if primary_value is not None else 'N/A'}, "
        f"with z-score {_fmt_signed(z_for_logic, 2, 'sigma')} and ROC60 {_fmt_signed(primary_roc, 1, '%')}.",
        f"Recent analyst sentiment skews {dominant_sentiment} ({sentiment_mix}).",
        _template_confluence_note(pre_conf, label, z_for_logic, qual_score),
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

    return {
        "confluence_type": pre_conf if pre_conf in CONFLUENCE_TYPES else "NEUTRAL",
        "confluence_note": _template_confluence_note(pre_conf, label, z_for_logic, qual_score),
        "summary": summary,
        "key_signals": key_signals[:4],
        "outlook": _template_outlook(pre_conf, label),
        "watch": _template_watch(pre_conf, latest_signal),
        "report_dates": [s.get("date") for s in qual_signals if s.get("date")],
    }


def _overlay_vessel(template_entry: dict, llm_entry: dict | None) -> dict:
    result = dict(template_entry)
    if not isinstance(llm_entry, dict):
        return result
    confluence = _clean_text(llm_entry.get("confluence_type")).upper()
    if confluence in CONFLUENCE_TYPES:
        result["confluence_type"] = confluence
    for key in ("confluence_note", "summary", "outlook", "watch"):
        text = _clean_text(llm_entry.get(key))
        if text:
            result[key] = text
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
        result["key_signals"] = key_signals[:4]

    return result


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
    pre_dry_conf = compute_confluence(dry_z, [s.get("sentiment", "neutral") for s in dry_signals])
    pre_tanker_conf = compute_confluence(tanker_z, [s.get("sentiment", "neutral") for s in tanker_signals])

    print("[brief] Loading wiki excerpts...")
    wiki_dry = wiki_excerpt(WIKI_EXCERPTS["dry_bulk"])
    wiki_tanker = wiki_excerpt(WIKI_EXCERPTS["tanker"])
    wiki_cape = wiki_excerpt(WIKI_EXCERPTS["capesize"])

    print(f"[brief] Provider order: {','.join(LLM_PROVIDER_ORDER)}")
    print("[brief] Loading recent report narratives...")
    dry_report_text = load_recent_report_text("drybulk")
    tanker_report_text = load_recent_report_text("tankers")
    spreads = compute_spreads(snapshot)
    system_msg = build_system_message()
    user_msg = build_user_message(
        snapshot, dry_signals, tanker_signals,
        wiki_dry, wiki_tanker, wiki_cape,
        dry_report_text, tanker_report_text,
        spreads=spreads,
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
    dry_entry = _overlay_vessel(template_dry, llm_vessel.get("dry_bulk"))
    tanker_entry = _overlay_vessel(template_tanker, llm_vessel.get("tanker"))
    tanker_entry = _ensure_tanker_segment_coverage(tanker_entry, snapshot)

    macro_note = _clean_text((llm_payload or {}).get("macro_note"))
    if not macro_note:
        macro_note = _template_macro_note(dry_entry["confluence_type"], tanker_entry["confluence_type"])

    today = date.today().isoformat()
    generated_at = datetime.now(timezone.utc).isoformat()
    generation_mode = "llm" if provider_used else "template"
    generation_provider = provider_used or "template"

    output = {
        "generated_at": generated_at,
        "brief_date": today,
        "generation": {
            "mode": generation_mode,
            "provider_used": generation_provider,
            "model": OLLAMA_MODEL if generation_provider == "ollama" else (NIM_MODEL if generation_provider == "nim" else ""),
            "provider_order": LLM_PROVIDER_ORDER,
            "attempted_providers": attempted,
        },
        "market_snapshot": snapshot,
        "vessel_classes": {
            "dry_bulk": dry_entry,
            "tanker": tanker_entry,
        },
        "macro_note": macro_note,
        "cross_sector_analysis": (llm_payload or {}).get("cross_sector_analysis") or {},
        "sources": [s["doc_id"] for s in dry_signals + tanker_signals if s.get("doc_id")],
    }

    latest_path = BRIEFS / "latest.json"
    dated_path = BRIEFS / f"{today}.json"
    for out_path in (latest_path, dated_path):
        out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
        try:
            display_path = out_path.relative_to(ROOT)
        except ValueError:
            display_path = out_path
        print(f"[brief] Wrote {display_path}")

    print(
        "[brief] Done "
        f"dry={output['vessel_classes']['dry_bulk']['confluence_type']} "
        f"tanker={output['vessel_classes']['tanker']['confluence_type']} "
        f"mode={generation_mode} provider={generation_provider}"
    )


if __name__ == "__main__":
    main()
