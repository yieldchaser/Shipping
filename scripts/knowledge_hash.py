from __future__ import annotations

import hashlib
from pathlib import Path

SOURCE_HASH_VERSION = "content_sha1_v1"


def compute_source_hash(path: Path, repo_root: Path) -> str:
    digest = hashlib.sha1()
    root_resolved = repo_root.resolve()
    path_resolved = path.resolve()
    try:
        rel = path_resolved.relative_to(root_resolved).as_posix()
    except ValueError:
        rel = path_resolved.as_posix()
    digest.update(rel.encode("utf-8"))
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
