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
BALTIC_REPORTS = 8  # number of weekly Baltic Exchange reports to feed into the brief

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

GEMINI_API_KEY = (os.environ.get("GEMINI_API_KEY") or "").strip()
GEMINI_MODEL = (os.environ.get("GEMINI_MODEL") or "gemini-2.0-flash").strip()
GEMINI_MIN_INTERVAL_SEC = float(os.environ.get("GEMINI_MIN_INTERVAL_SEC", "1.5"))
GEMINI_MAX_RETRIES = int(os.environ.get("GEMINI_MAX_RETRIES", "3"))
GEMINI_BACKOFF_BASE_SEC = float(os.environ.get("GEMINI_BACKOFF_BASE_SEC", "1.5"))
GEMINI_MAX_BACKOFF_SEC = float(os.environ.get("GEMINI_MAX_BACKOFF_SEC", "15.0"))


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

    return {
        "confluence_type": pre_conf if pre_conf in CONFLUENCE_TYPES else "NEUTRAL",
        "confluence_note": _template_confluence_note(pre_conf, label, z_for_logic, qual_score, tally=tally),
        "summary": summary,
        "key_signals": key_signals[:4],
        "outlook": _template_outlook(pre_conf, label),
        "watch": _template_watch(pre_conf, latest_signal),
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
        sentiments=[s.get("sentiment", "neutral") for s in dry_signals],
        momentums=[s.get("momentum", "neutral") for s in dry_signals],
        fundamentals=[s.get("fundamentals", "neutral") for s in dry_signals],
    )
    pre_tanker_conf = compute_confluence(
        tanker_z,
        sentiments=[s.get("sentiment", "neutral") for s in tanker_signals],
        momentums=[s.get("momentum", "neutral") for s in tanker_signals],
        fundamentals=[s.get("fundamentals", "neutral") for s in tanker_signals],
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
