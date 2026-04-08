import hashlib
import json
from collections import Counter
from pathlib import Path

import frontmatter


REPO_ROOT = Path(__file__).parent.parent
REPORTS_ROOT = REPO_ROOT / "reports"
KNOWLEDGE_ROOT = REPO_ROOT / "knowledge"
DOCS_MANIFEST = KNOWLEDGE_ROOT / "manifests" / "documents.jsonl"
SIGNALS_PATH = KNOWLEDGE_ROOT / "derived" / "signals.jsonl"


ROW_ORDER = [
    ("breakwave", "drybulk", "breakwave/drybulk"),
    ("breakwave", "tankers", "breakwave/tankers"),
    ("baltic", "dry", "baltic/dry"),
    ("baltic", "tanker", "baltic/tanker"),
    ("baltic", "gas", "baltic/gas"),
    ("baltic", "container", "baltic/container"),
    ("baltic", "ningbo", "baltic/ningbo"),
    ("book", "book", "books"),
]


def load_jsonl(path: Path) -> tuple[list[dict], int]:
    rows = []
    malformed = 0
    if not path.exists():
        return rows, malformed
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                malformed += 1
    return rows, malformed


def source_hash(path: Path) -> str:
    stat = path.stat()
    payload = f"{path.relative_to(REPO_ROOT).as_posix()}:{stat.st_size}:{int(stat.st_mtime)}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def count_source_files():
    return {
        ("breakwave", "drybulk"): len(list((REPORTS_ROOT / "drybulk").rglob("*.pdf"))),
        ("breakwave", "tankers"): len(list((REPORTS_ROOT / "tankers").rglob("*.pdf"))),
        ("baltic", "dry"): len(list((REPORTS_ROOT / "baltic" / "dry").rglob("*.html"))),
        ("baltic", "tanker"): len(list((REPORTS_ROOT / "baltic" / "tanker").rglob("*.html"))),
        ("baltic", "gas"): len(list((REPORTS_ROOT / "baltic" / "gas").rglob("*.html"))),
        ("baltic", "container"): len(list((REPORTS_ROOT / "baltic" / "container").rglob("*.html"))),
        ("baltic", "ningbo"): len(list((REPORTS_ROOT / "baltic" / "ningbo").rglob("*.html"))),
        ("book", "book"): len(list(REPORTS_ROOT.glob("*.pdf"))),
    }


def count_processed_documents(documents: list[dict]):
    counts = {}
    for row in documents:
        key = (row.get("source"), row.get("category"))
        counts[key] = counts.get(key, 0) + 1
    return counts


def count_chunks(documents: list[dict]):
    chunk_counts = {}
    duplicate_chunk_ids = 0
    malformed_lines = 0
    seen_files = set()

    for row in documents:
        chunk_file = row.get("chunk_file")
        if not chunk_file or chunk_file in seen_files:
            continue
        seen_files.add(chunk_file)
        path = REPO_ROOT / chunk_file
        count = 0
        seen_chunk_ids = set()

        if path.exists():
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        malformed_lines += 1
                        continue
                    chunk_id = obj.get("chunk_id")
                    if chunk_id in seen_chunk_ids:
                        duplicate_chunk_ids += 1
                    else:
                        seen_chunk_ids.add(chunk_id)
                    count += 1

        if "books.jsonl" in chunk_file:
            key = ("book", "book")
        else:
            stem = path.stem
            if stem.startswith("breakwave_"):
                key = ("breakwave", stem.split("_", 1)[1])
            elif stem.startswith("baltic_"):
                key = ("baltic", stem.split("_", 1)[1])
            else:
                continue
        chunk_counts[key] = count

    return chunk_counts, duplicate_chunk_ids, malformed_lines


def validate_manifest(documents: list[dict]):
    source_counter = Counter(row.get("source_path") for row in documents if row.get("source_path"))
    doc_counter = Counter(row.get("doc_id") for row in documents if row.get("doc_id"))

    duplicate_source_paths = sorted(path for path, count in source_counter.items() if count > 1)
    duplicate_doc_ids = sorted(doc_id for doc_id, count in doc_counter.items() if count > 1)

    missing_source_files = []
    missing_doc_files = []
    hash_mismatches = []

    for row in documents:
        source_path = row.get("source_path")
        doc_path = row.get("doc_path")
        expected_hash = row.get("source_hash")

        if source_path:
            source_file = REPO_ROOT / source_path
            if not source_file.exists():
                missing_source_files.append(source_path)
            elif expected_hash and source_hash(source_file) != expected_hash:
                hash_mismatches.append(source_path)

        if doc_path and not (REPO_ROOT / doc_path).exists():
            missing_doc_files.append(doc_path)

    return {
        "duplicate_source_paths": duplicate_source_paths,
        "duplicate_doc_ids": duplicate_doc_ids,
        "missing_source_files": sorted(set(missing_source_files)),
        "missing_doc_files": sorted(set(missing_doc_files)),
        "hash_mismatches": sorted(set(hash_mismatches)),
    }


def validate_frontmatter(documents: list[dict]):
    bad = []
    breakwave_null_signals = 0
    for row in documents:
        doc_path = row.get("doc_path")
        if not doc_path:
            continue
        full_path = REPO_ROOT / doc_path
        if not full_path.exists():
            continue
        post = frontmatter.load(full_path)
        source = post.metadata.get("source")
        category = post.metadata.get("category")
        if not source or not category:
            bad.append(str(full_path))
            continue
        if source == "breakwave":
            signals = post.metadata.get("signals", {}) or {}
            required_key = "bdryff" if category == "drybulk" else "bwetff"
            if signals.get(required_key) is None:
                breakwave_null_signals += 1
    return bad, breakwave_null_signals


def count_signal_rows():
    rows, malformed = load_jsonl(SIGNALS_PATH)
    counts = {}
    for row in rows:
        key = ("breakwave", row.get("category"))
        counts[key] = counts.get(key, 0) + 1
    return counts, malformed


def print_table(rows):
    header = f"{'Source':24} {'Files':>7} {'Processed':>10} {'Missing':>9} {'Chunks':>9} {'Signals':>8}"
    print(header)
    print("-" * len(header))
    total_files = total_processed = total_missing = total_chunks = total_signals = 0
    for label, files, processed, missing, chunks, signals in rows:
        signals_str = f"{signals}" if signals is not None else "—"
        print(f"{label:24} {files:7} {processed:10} {missing:9} {chunks:9} {signals_str:>8}")
        total_files += files
        total_processed += processed
        total_missing += missing
        total_chunks += chunks
        if signals is not None:
            total_signals += signals
    print("-" * len(header))
    print(f"{'TOTAL':24} {total_files:7} {total_processed:10} {total_missing:9} {total_chunks:9} {total_signals:8}")


def main():
    documents, malformed_manifest_lines = load_jsonl(DOCS_MANIFEST)
    source_counts = count_source_files()
    processed_counts = count_processed_documents(documents)
    chunk_counts, duplicate_chunk_ids, malformed_chunk_lines = count_chunks(documents)
    signal_counts, malformed_signal_lines = count_signal_rows()
    manifest_issues = validate_manifest(documents)
    bad_frontmatter, breakwave_null_signals = validate_frontmatter(documents)

    rows = []
    total_missing = 0
    for source, category, label in ROW_ORDER:
        files = source_counts.get((source, category), 0)
        processed = processed_counts.get((source, category), 0)
        missing = files - processed
        total_missing += missing
        chunks = chunk_counts.get((source, category), 0)
        signals = signal_counts.get((source, category)) if source == "breakwave" else None
        rows.append((label, files, processed, missing, chunks, signals))

    print_table(rows)
    print()
    print(f"Malformed manifest lines: {malformed_manifest_lines}")
    print(f"Malformed chunk lines: {malformed_chunk_lines}")
    print(f"Malformed signal lines: {malformed_signal_lines}")
    print(f"Duplicate source paths: {len(manifest_issues['duplicate_source_paths'])}")
    print(f"Duplicate doc ids: {len(manifest_issues['duplicate_doc_ids'])}")
    print(f"Duplicate chunk ids: {duplicate_chunk_ids}")
    print(f"Missing source files in manifest: {len(manifest_issues['missing_source_files'])}")
    print(f"Missing generated docs in manifest: {len(manifest_issues['missing_doc_files'])}")
    print(f"Source hash mismatches: {len(manifest_issues['hash_mismatches'])}")
    print(f"Frontmatter errors: {len(bad_frontmatter)}")
    print(f"Breakwave reports with null primary signal: {breakwave_null_signals}")

    failures = (
        malformed_manifest_lines
        + malformed_chunk_lines
        + malformed_signal_lines
        + len(manifest_issues["duplicate_source_paths"])
        + len(manifest_issues["duplicate_doc_ids"])
        + duplicate_chunk_ids
        + len(manifest_issues["missing_source_files"])
        + len(manifest_issues["missing_doc_files"])
        + len(manifest_issues["hash_mismatches"])
        + len(bad_frontmatter)
        + breakwave_null_signals
        + total_missing
    )

    if failures:
        if manifest_issues["duplicate_source_paths"]:
            print("Duplicate source paths:")
            for path in manifest_issues["duplicate_source_paths"][:20]:
                print(f"- {path}")
        if manifest_issues["duplicate_doc_ids"]:
            print("Duplicate doc ids:")
            for doc_id in manifest_issues["duplicate_doc_ids"][:20]:
                print(f"- {doc_id}")
        if manifest_issues["hash_mismatches"]:
            print("Source hash mismatches:")
            for path in manifest_issues["hash_mismatches"][:20]:
                print(f"- {path}")
        if bad_frontmatter:
            print("Invalid frontmatter docs:")
            for path in bad_frontmatter[:20]:
                print(f"- {path}")
        return 1

    print("Validation status: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
