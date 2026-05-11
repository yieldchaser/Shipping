"""
Daily shipping market brief generator.

Reads quantitative CSV data + recent Breakwave signals + wiki context and writes:
  knowledge/briefs/latest.json
  knowledge/briefs/YYYY-MM-DD.json

LLM provider order: ollama -> nim.
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


def load_recent_report_text(category: str, n_reports: int = RECENT_REPORTS) -> str:
    """Load all chunk sections for the most recent N reports.

    Feeds the LLM the complete analyst narrative — Overview + Fundamentals —
    so it can reference geopolitical events, supply/demand data, etc.
    Each full report is ~200-230 tokens, so 12 reports x 2 categories = ~5400 tokens total.
    """
    chunk_map = {
        "drybulk": [KNOWLEDGE / "chunks" / "breakwave_drybulk_2026.jsonl",
                    KNOWLEDGE / "chunks" / "breakwave_drybulk.jsonl"],
        "tankers": [KNOWLEDGE / "chunks" / "breakwave_tankers.jsonl"],
    }
    paths = chunk_map.get(category, [])
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
    # Group by date, sort dates descending, take top N report dates
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


def build_system_message() -> str:
    return (
        "You are the head freight strategist at a tier-1 commodity trading desk — the most respected and feared analyst on the floor. "
        "Your daily brief is the first thing portfolio managers read every morning before trading FFAs, "
        "freight options, and shipping equities. You have 15 years of experience synthesizing Baltic "
        "Exchange data, Breakwave Advisors research, and global macro flows into actionable intelligence.\n\n"

        "YOUR VOICE: Write like the best sell-side analyst in the world briefing the trading floor — "
        "authoritative, opinionated, and surgically precise. Numbers support the argument; they do not replace it. "
        "Every sentence must carry a distinct analytical insight that could not be gleaned from the raw data table alone.\n\n"

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

        "RULE 8 — CATALYST WATCH must name SPECIFIC upcoming events with approximate timing. "
        "BAD: 'Watch for demand developments'. "
        "GOOD: 'China May steel PMI (due ~June 1), OPEC+ June 1 meeting, and US port labor contract renewal "
        "in late May are the three near-term catalysts.'\n\n"

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
) -> str:
    today = date.today().isoformat()
    analytics = _build_analytics_context(snapshot, spreads or {})
    dry_block = "\n".join(_fmt_rich_signal(s, i) for i, s in enumerate(dry_signals)) or "No recent reports."
    tanker_block = "\n".join(_fmt_rich_signal(s, i) for i, s in enumerate(tanker_signals)) or "No recent reports."
    n_dry = len([r for r in dry_report_text.split("---") if r.strip()])
    n_tank = len([r for r in tanker_report_text.split("---") if r.strip()])
    return f"""DAILY FREIGHT INTELLIGENCE BRIEF — {today}

{analytics}

RECENT BREAKWAVE DRY BULK ANALYST SIGNALS (newest first — weight: 0.85^i decay):
{dry_block}

RECENT BREAKWAVE TANKER ANALYST SIGNALS (newest first — weight: 0.85^i decay):
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

TASK: Write today's institutional freight brief applying 0.85^i exponential decay to historical signals.

WRITING QUALITY MANDATE:
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
      "confluence_note": "<2 sentences: first states the Z-score and what regime it implies historically; second states how many analyst reports are bullish/bearish/neutral and whether they confirm or contradict the quant reading>",
      "summary": "<4 sentences of flowing analysis: S1=where the market is with historical context; S2=momentum characterization using Z+ROC to explain the rate-of-change story; S3=analyst consensus synthesis noting any quant-qual divergence; S4=actionable conclusion on positioning over the next 2-4 weeks>",
      "key_signals": ["<analytical sentence with embedded number explaining WHY it matters — NOT a raw data label>", "...up to 8 total"],
      "positioning_bias": "<LONG|SHORT|NEUTRAL|LONG_SPREAD_VS_TANKER|SHORT_SPREAD_VS_TANKER>",
      "trade_idea": "<IF signals clearly aligned: '1 sentence with direction + specific vehicle + entry trigger + exit thesis'. IF NOT clearly aligned or geopolitical uncertainty is elevated: 'No high-conviction setup: [what would need to change]'>",
      "outlook": "<1 sentence naming the 2-4 week directional thesis with the key variable that could change it>",
      "catalyst_watch": "<1 sentence naming 2-3 specific dated events or seasonal inflections that could shift the picture>",
      "risk_note": "<1 sentence naming the single biggest tail risk and the specific data point or event that would confirm it>"
    }},
    "tanker": {{
      "confluence_type": "<BULL_CONFLUENCE|BEAR_CONFLUENCE|DIVERGENCE|NEUTRAL>",
      "momentum_grade": "<STRONG_UP|UP|FLAT|DOWN|STRONG_DOWN>",
      "confidence_score": <float 0.0-1.0>,
      "confluence_note": "<same structure as dry_bulk: Z-score regime reading + analyst consensus count and alignment>",
      "summary": "<4 sentences flowing analysis — must address clean/dirty split explicitly if Z-spreads diverge>",
      "key_signals": ["<analytical sentence with embedded number>", "...up to 8 total"],
      "positioning_bias": "<LONG|SHORT|NEUTRAL|LONG_SPREAD_VS_DRY|SHORT_SPREAD_VS_DRY>",
      "trade_idea": "<IF signals clearly aligned: '1 sentence with direction + specific vehicle + entry trigger + exit thesis'. IF NOT: 'No high-conviction setup: [what would need to change]'>",
      "outlook": "<1 sentence: 2-4 week directional thesis with the SPECIFIC swing variable that could change it>",
      "catalyst_watch": "<1 sentence naming 2-3 SPECIFIC upcoming events with approximate dates — e.g. 'China May customs data (~June 8), OPEC+ meeting (June 1), and Atlantic hurricane season onset (June 1) are the three near-term catalysts'>",
      "risk_note": "<1 sentence naming a SPECIFIC data print or event that would invalidate the thesis — e.g. 'A Chinese iron ore import print below 95mt would signal demand destruction and break the BDI expansion case'>"
    }}
  }},
  "cross_sector_analysis": {{
    "relative_value": "<1 sentence comparing dry vs tanker with specific Z-differential or spread value — name which sector has better risk-reward and articulate the structural reason>",
    "dominant_driver": "<1 sentence naming the single most consequential macro force for BOTH sectors today — be specific, not generic>",
    "positioning_recommendation": "<1 sentence: specific cross-sector trade with named vehicles, entry rationale, and exit trigger>"
  }},
  "macro_note": "<2 sentences: S1 — IF analyst reports mention any active armed conflict, sanctions, or supply route disruption, NAME IT EXPLICITLY (e.g. 'The Iran-Israel escalation is rerouting VLCC traffic away from the Strait of Hormuz') then explain its freight transmission mechanism; ELSE name the specific macro driver active today and its direct freight impact with supporting data. S2 — name the SPECIFIC upcoming data release or event (with approximate date) that will either confirm or invalidate the current freight thesis — no generic boilerplate>"
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
