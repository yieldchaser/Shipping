from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

import frontmatter

from build_wiki import load_document_metadata, load_jsonl, load_topics


EXPECTED_CADENCE_DAYS = {
    ("breakwave", "drybulk"): 14,
    ("breakwave", "tankers"): 14,
    ("baltic", "dry"): 7,
    ("baltic", "tanker"): 7,
    ("baltic", "gas"): 7,
    ("baltic", "container"): 7,
    ("baltic", "ningbo"): 7,
    ("breakwave_insights", "insights"): 14,
    ("hellenic", "dry_charter"): 14,
    ("hellenic", "tanker_charter"): 14,
    ("hellenic", "iron_ore"): 14,
    ("hellenic", "vessel_valuations"): 14,
    ("hellenic", "demolition"): 21,
    ("hellenic", "shipbuilding"): 21,
}

ROW_ORDER = [
    ("breakwave", "drybulk", "breakwave/drybulk"),
    ("breakwave", "tankers", "breakwave/tankers"),
    ("baltic", "dry", "baltic/dry"),
    ("baltic", "tanker", "baltic/tanker"),
    ("baltic", "gas", "baltic/gas"),
    ("baltic", "container", "baltic/container"),
    ("baltic", "ningbo", "baltic/ningbo"),
    ("breakwave_insights", "insights", "breakwave_insights/insights"),
    ("hellenic", "dry_charter", "hellenic/dry_charter"),
    ("hellenic", "tanker_charter", "hellenic/tanker_charter"),
    ("hellenic", "iron_ore", "hellenic/iron_ore"),
    ("hellenic", "vessel_valuations", "hellenic/vessel_valuations"),
    ("hellenic", "demolition", "hellenic/demolition"),
    ("hellenic", "shipbuilding", "hellenic/shipbuilding"),
    ("book", "book", "books"),
]

RECENT_WINDOW_DAYS = 120
TONE_SCORES = {
    "positive": 1.0,
    "constructive": 0.75,
    "cautiously_bullish": 0.5,
    "neutral": 0.0,
    "mixed": 0.0,
    "cautiously_bearish": -0.5,
    "negative": -1.0,
}
SEVERITY_ORDER = {"high": 0, "stale": 1, "watch": 2, "info": 3}


def parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def utc_today() -> date:
    return datetime.now(timezone.utc).date()


def format_date(value: date | None) -> str | None:
    return value.isoformat() if value else None


def status_from_age(age_days: int | None, cadence_days: int | None) -> str:
    if cadence_days is None:
        return "reference"
    if age_days is None:
        return "unknown"
    if age_days > cadence_days * 3:
        return "stale"
    if age_days > int(cadence_days * 1.5):
        return "watch"
    return "healthy"


def tone_score(value: str | None) -> float | None:
    if not value:
        return None
    return TONE_SCORES.get(value)


def tone_label(score: float) -> str:
    if score >= 0.65:
        return "constructive"
    if score >= 0.25:
        return "cautiously_bullish"
    if score <= -0.65:
        return "negative"
    if score <= -0.25:
        return "cautiously_bearish"
    return "neutral"


def latest_gap_days(dates: list[date]) -> int | None:
    if len(dates) < 2:
        return None
    return (dates[-1] - dates[-2]).days


def max_recent_gap_days(dates: list[date], sample_size: int = 12) -> int | None:
    if len(dates) < 2:
        return None
    recent_dates = dates[-sample_size:]
    gaps = [(recent_dates[idx] - recent_dates[idx - 1]).days for idx in range(1, len(recent_dates))]
    return max(gaps) if gaps else None


def relevant_cadence_days(topic: dict) -> int | None:
    values = []
    for source in topic.get("sources", []):
        for category in topic.get("categories", []):
            cadence = EXPECTED_CADENCE_DAYS.get((source, category))
            if cadence is not None:
                values.append(cadence)
    return min(values) if values else None


def build_source_health(documents: list[dict], docs_by_id: dict[str, dict], current_date: date):
    docs_by_key: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in documents:
        doc_id = row.get("doc_id")
        source = row.get("source")
        category = row.get("category")
        if not doc_id or not source or not category:
            continue
        metadata = docs_by_id.get(doc_id, {})
        docs_by_key[(source, category)].append({
            "doc_id": doc_id,
            "date": parse_iso_date(metadata.get("date") or row.get("date")),
        })

    rows = []
    warnings = []
    for source, category, label in ROW_ORDER:
        docs = docs_by_key.get((source, category), [])
        dated = sorted(doc["date"] for doc in docs if doc.get("date"))
        undated_count = sum(1 for doc in docs if doc.get("date") is None)
        latest = dated[-1] if dated else None
        age_days = (current_date - latest).days if latest else None
        cadence_days = EXPECTED_CADENCE_DAYS.get((source, category))
        status = status_from_age(age_days, cadence_days)
        latest_gap = latest_gap_days(dated)
        max_gap = max_recent_gap_days(dated)

        row = {
            "label": label,
            "source": source,
            "category": category,
            "status": status,
            "cadence_days": cadence_days,
            "latest_date": format_date(latest),
            "age_days": age_days,
            "latest_gap_days": latest_gap,
            "max_recent_gap_days": max_gap,
            "dated_doc_count": len(dated),
            "undated_doc_count": undated_count,
        }
        rows.append(row)

        if status in {"watch", "stale"}:
            warnings.append({
                "severity": status,
                "kind": "source_freshness",
                "key": label,
                "message": f"{label} is {status} at {age_days} days since the latest dated document.",
                "details": row,
            })
        if cadence_days and latest_gap and latest_gap > cadence_days * 2:
            warnings.append({
                "severity": "watch",
                "kind": "source_gap",
                "key": label,
                "message": f"{label} shows a recent publishing gap of {latest_gap} days versus an expected cadence of {cadence_days}.",
                "details": row,
            })

    return rows, warnings


def build_topic_health(topics: list[dict], topic_rows: list[dict], docs_by_id: dict[str, dict], current_date: date):
    rows_by_topic: dict[str, list[dict]] = defaultdict(list)
    for row in topic_rows:
        rows_by_topic[row.get("topic_id")].append(row)

    topic_health = []
    warnings = []
    divergences = []

    docs_by_source_category: dict[tuple[str, str], list[date]] = defaultdict(list)
    for doc_meta in docs_by_id.values():
        source = doc_meta.get("source")
        category = doc_meta.get("category")
        parsed = parse_iso_date(doc_meta.get("date"))
        if source and category and parsed:
            docs_by_source_category[(source, category)].append(parsed)

    for topic in topics:
        topic_id = topic["topic_id"]
        rows = sorted(rows_by_topic.get(topic_id, []), key=lambda row: (row.get("date") or "", row.get("doc_id") or ""))
        unique_doc_ids = []
        seen_doc_ids = set()
        for row in sorted(rows, key=lambda item: (item.get("date") or "", item.get("doc_id") or ""), reverse=True):
            doc_id = row.get("doc_id")
            if not doc_id or doc_id in seen_doc_ids:
                continue
            seen_doc_ids.add(doc_id)
            unique_doc_ids.append(doc_id)

        latest_evidence_date = max((parse_iso_date(row.get("date")) for row in rows), default=None)
        latest_evidence_age = (current_date - latest_evidence_date).days if latest_evidence_date else None
        cadence_days = relevant_cadence_days(topic)
        status = status_from_age(latest_evidence_age, cadence_days)

        relevant_dates = []
        for source in topic.get("sources", []):
            for category in topic.get("categories", []):
                relevant_dates.extend(docs_by_source_category.get((source, category), []))
        relevant_latest = max(relevant_dates) if relevant_dates else None
        lag_days = (relevant_latest - latest_evidence_date).days if relevant_latest and latest_evidence_date else None

        recent_cutoff = current_date.toordinal() - RECENT_WINDOW_DAYS
        recent_doc_ids_by_source: dict[str, list[str]] = defaultdict(list)
        recent_sources_present = set()
        tone_distribution = Counter()
        for doc_id in unique_doc_ids:
            doc_meta = docs_by_id.get(doc_id, {})
            parsed = parse_iso_date(doc_meta.get("date"))
            if not parsed or parsed.toordinal() < recent_cutoff:
                continue
            source = doc_meta.get("source")
            if source:
                recent_sources_present.add(source)
                recent_doc_ids_by_source[source].append(doc_id)
            tone = doc_meta.get("market_tone")
            if tone:
                tone_distribution[tone] += 1

        periodic_sources = sorted(source for source in topic.get("sources", []) if source != "book")
        missing_recent_sources = sorted(source for source in periodic_sources if source not in recent_sources_present)
        if missing_recent_sources and recent_sources_present:
            warnings.append({
                "severity": "watch",
                "kind": "topic_source_gap",
                "key": topic_id,
                "message": f"{topic_id} is missing recent evidence from expected sources: {', '.join(missing_recent_sources)}.",
                "details": {
                    "topic_id": topic_id,
                    "missing_recent_sources": missing_recent_sources,
                    "recent_sources_present": sorted(recent_sources_present),
                },
            })

        if lag_days and cadence_days and lag_days > cadence_days * 2:
            warnings.append({
                "severity": "watch",
                "kind": "topic_freshness",
                "key": topic_id,
                "message": f"{topic_id} trails the latest relevant corpus evidence by {lag_days} days.",
                "details": {
                    "topic_id": topic_id,
                    "lag_days": lag_days,
                    "latest_evidence_date": format_date(latest_evidence_date),
                    "relevant_corpus_latest_date": format_date(relevant_latest),
                },
            })

        if status in {"watch", "stale"}:
            warnings.append({
                "severity": status,
                "kind": "topic_age",
                "key": topic_id,
                "message": f"{topic_id} is {status} at {latest_evidence_age} days since the latest evidence row.",
                "details": {
                    "topic_id": topic_id,
                    "latest_evidence_date": format_date(latest_evidence_date),
                    "latest_evidence_age_days": latest_evidence_age,
                },
            })

        divergence_sources = []
        for source, doc_ids in recent_doc_ids_by_source.items():
            scores = []
            tone_counts = Counter()
            latest_date = None
            for doc_id in doc_ids[:6]:
                doc_meta = docs_by_id.get(doc_id, {})
                latest_date = max(latest_date or date.min, parse_iso_date(doc_meta.get("date")) or date.min)
                tone = doc_meta.get("market_tone")
                score = tone_score(tone)
                if score is not None:
                    scores.append(score)
                    tone_counts[tone] += 1
            if len(scores) >= 2:
                average = round(sum(scores) / len(scores), 2)
                divergence_sources.append({
                    "source": source,
                    "avg_tone_score": average,
                    "dominant_tone": tone_counts.most_common(1)[0][0] if tone_counts else "unknown",
                    "doc_count": len(doc_ids[:6]),
                    "latest_date": format_date(latest_date if latest_date != date.min else None),
                })

        divergence_sources = sorted(divergence_sources, key=lambda item: item["avg_tone_score"])
        if len(divergence_sources) >= 2:
            lowest = divergence_sources[0]
            highest = divergence_sources[-1]
            diff = round(highest["avg_tone_score"] - lowest["avg_tone_score"], 2)
            severity = None
            if highest["avg_tone_score"] >= 0.5 and lowest["avg_tone_score"] <= -0.5:
                severity = "high"
            elif diff >= 0.75:
                severity = "watch"
            if severity:
                divergence = {
                    "topic_id": topic_id,
                    "title": topic["title"],
                    "severity": severity,
                    "score_diff": diff,
                    "source_scores": divergence_sources,
                    "message": (
                        f"{topic['title']} shows recent tone divergence: "
                        f"{highest['source']} reads {tone_label(highest['avg_tone_score'])} "
                        f"while {lowest['source']} reads {tone_label(lowest['avg_tone_score'])}."
                    ),
                }
                divergences.append(divergence)
                warnings.append({
                    "severity": severity,
                    "kind": "topic_divergence",
                    "key": topic_id,
                    "message": divergence["message"],
                    "details": divergence,
                })

        topic_health.append({
            "topic_id": topic_id,
            "title": topic["title"],
            "status": status,
            "cadence_days": cadence_days,
            "latest_evidence_date": format_date(latest_evidence_date),
            "latest_evidence_age_days": latest_evidence_age,
            "relevant_corpus_latest_date": format_date(relevant_latest),
            "lag_days": lag_days,
            "evidence_count": len(rows),
            "document_count": len(unique_doc_ids),
            "source_counts": dict(sorted(Counter(row.get("source") for row in rows if row.get("source")).items())),
            "category_counts": dict(sorted(Counter(row.get("category") for row in rows if row.get("category")).items())),
            "recent_sources_present": sorted(recent_sources_present),
            "missing_recent_sources": missing_recent_sources,
            "tone_distribution": dict(sorted(tone_distribution.items())),
        })

    return topic_health, warnings, divergences


def build_lint_report(source_rows: list[dict], topic_rows: list[dict], warnings: list[dict], divergences: list[dict], generated_at: str, current_date: date):
    source_status_counts = Counter(row.get("status") for row in source_rows if row.get("status"))
    topic_status_counts = Counter(row.get("status") for row in topic_rows if row.get("status"))
    divergence_counts = Counter(row.get("severity") for row in divergences if row.get("severity"))
    ordered_warnings = sorted(
        warnings,
        key=lambda row: (
            SEVERITY_ORDER.get(row.get("severity"), 99),
            row.get("kind") or "",
            row.get("key") or "",
        ),
    )
    return {
        "generated_at": generated_at,
        "current_date": current_date.isoformat(),
        "warning_count": len(ordered_warnings),
        "high_severity_count": sum(1 for row in ordered_warnings if row.get("severity") in {"high", "stale"}),
        "status_counts": {
            "sources": dict(sorted(source_status_counts.items())),
            "topics": dict(sorted(topic_status_counts.items())),
            "divergences": dict(sorted(divergence_counts.items())),
        },
        "warnings": ordered_warnings,
    }


def build_coverage_report(documents: list[dict], section_rows: list[dict], topic_rows: list[dict], topic_health: list[dict], source_health: list[dict], divergences: list[dict], wiki_page_count: int, generated_at: str, current_date: date):
    chunk_count = sum(row.get("chunk_count", 0) for row in documents if isinstance(row.get("chunk_count"), int))
    return {
        "generated_at": generated_at,
        "current_date": current_date.isoformat(),
        "corpus": {
            "document_count": len(documents),
            "chunk_count": chunk_count,
            "section_count": len(section_rows),
            "topic_count": len(topic_health),
            "topic_evidence_count": len(topic_rows),
            "wiki_page_count": wiki_page_count,
        },
        "sources": source_health,
        "topics": topic_health,
        "divergences": divergences,
    }


def render_health_summary(coverage_report: dict, lint_report: dict, summary_path: Path):
    corpus = coverage_report["corpus"]
    source_rows = coverage_report["sources"]
    topic_rows = coverage_report["topics"]
    divergences = coverage_report["divergences"]
    warnings = lint_report["warnings"]

    lines = [
        "# Knowledge Health Summary",
        "",
        "## Corpus Snapshot",
        f"- Documents: {corpus['document_count']}",
        f"- Chunks: {corpus['chunk_count']}",
        f"- Sections: {corpus['section_count']}",
        f"- Topic evidence rows: {corpus['topic_evidence_count']}",
        f"- Wiki pages: {corpus['wiki_page_count']}",
        "",
        "## Source Freshness",
        "",
        "| Source | Latest | Age (days) | Cadence | Status | Latest Gap | Undated |",
        "|---|---|---:|---:|---|---:|---:|",
    ]
    for row in source_rows:
        cadence = row["cadence_days"] if row["cadence_days"] is not None else "-"
        age = row["age_days"] if row["age_days"] is not None else "-"
        gap = row["latest_gap_days"] if row["latest_gap_days"] is not None else "-"
        latest = row["latest_date"] or "undated"
        lines.append(
            f"| {row['label']} | {latest} | {age} | {cadence} | {row['status']} | {gap} | {row['undated_doc_count']} |"
        )

    lines.extend([
        "",
        "## Topic Coverage",
        "",
        "| Topic | Latest Evidence | Docs | Evidence | Recent Sources | Missing Sources | Status |",
        "|---|---|---:|---:|---|---|---|",
    ])
    for row in topic_rows:
        recent_sources = ", ".join(row["recent_sources_present"]) if row["recent_sources_present"] else "-"
        missing_sources = ", ".join(row["missing_recent_sources"]) if row["missing_recent_sources"] else "-"
        latest = row["latest_evidence_date"] or "undated"
        lines.append(
            f"| {row['title']} | {latest} | {row['document_count']} | {row['evidence_count']} | "
            f"{recent_sources} | {missing_sources} | {row['status']} |"
        )

    lines.extend(["", "## Priority Warnings"])
    if warnings:
        for row in warnings[:12]:
            lines.append(f"- `{row['severity']}` {row['message']}")
    else:
        lines.append("- No active knowledge-health warnings.")

    lines.extend(["", "## Cross-Source Divergence"])
    if divergences:
        for row in divergences:
            lines.append(f"- `{row['severity']}` {row['message']}")
    else:
        lines.append("- No material cross-source divergence flags right now.")

    post = frontmatter.Post(
        "\n".join(lines).strip() + "\n",
        page_type="knowledge_health_summary",
        generated_at=lint_report["generated_at"],
        warning_count=lint_report["warning_count"],
        high_severity_count=lint_report["high_severity_count"],
    )
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(frontmatter.dumps(post), encoding="utf-8")


def build_health_reports(
    repo_root: Path,
    reports_dir: Path,
    documents_manifest: Path,
    section_index_path: Path,
    topic_config_path: Path,
    topic_evidence_path: Path,
    lint_report_path: Path,
    coverage_report_path: Path,
    summary_path: Path,
    generated_at: str,
):
    current_date = utc_today()
    documents, malformed_manifest = load_jsonl(documents_manifest)
    section_rows, malformed_sections = load_jsonl(section_index_path)
    topic_rows, malformed_topic_rows = load_jsonl(topic_evidence_path)
    if malformed_manifest or malformed_sections or malformed_topic_rows:
        raise ValueError(
            f"Cannot build health reports with malformed inputs: manifest={malformed_manifest}, "
            f"sections={malformed_sections}, topic_evidence={malformed_topic_rows}"
        )

    docs_by_id = load_document_metadata(repo_root, documents_manifest)
    topics = load_topics(topic_config_path.parent)

    source_health, source_warnings = build_source_health(documents, docs_by_id, current_date)
    topic_health, topic_warnings, divergences = build_topic_health(topics, topic_rows, docs_by_id, current_date)
    lint_report = build_lint_report(
        source_rows=source_health,
        topic_rows=topic_health,
        warnings=source_warnings + topic_warnings,
        divergences=divergences,
        generated_at=generated_at,
        current_date=current_date,
    )
    reports_dir.mkdir(parents=True, exist_ok=True)
    wiki_dir = topic_config_path.parent.parent / "wiki"
    wiki_page_count = len(list(wiki_dir.glob("*.md"))) - int((wiki_dir / "index.md").exists())
    coverage_report = build_coverage_report(
        documents=documents,
        section_rows=section_rows,
        topic_rows=topic_rows,
        topic_health=topic_health,
        source_health=source_health,
        divergences=divergences,
        wiki_page_count=max(wiki_page_count, 0),
        generated_at=generated_at,
        current_date=current_date,
    )

    lint_report_path.write_text(json.dumps(lint_report, indent=2, ensure_ascii=False), encoding="utf-8")
    coverage_report_path.write_text(json.dumps(coverage_report, indent=2, ensure_ascii=False), encoding="utf-8")
    render_health_summary(coverage_report, lint_report, summary_path)


def main():
    repo_root = Path(__file__).parent.parent
    knowledge_root = repo_root / "knowledge"
    build_health_reports(
        repo_root=repo_root,
        reports_dir=knowledge_root / "reports",
        documents_manifest=knowledge_root / "manifests" / "documents.jsonl",
        section_index_path=knowledge_root / "derived" / "section_index.jsonl",
        topic_config_path=knowledge_root / "config" / "wiki_topics.json",
        topic_evidence_path=knowledge_root / "derived" / "topic_evidence.jsonl",
        lint_report_path=knowledge_root / "manifests" / "lint_report.json",
        coverage_report_path=knowledge_root / "manifests" / "coverage_report.json",
        summary_path=knowledge_root / "reports" / "health_summary.md",
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
    )
    print("[HEALTH] rebuilt")


if __name__ == "__main__":
    main()
