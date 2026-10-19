"""
Drop-in LlamaParse replacement with a Nace NDI Parse fallback.

Every publisher parser builds ``LlamaParse(api_key=..., result_type="markdown", ...)`` and calls
``load_data`` / ``aload_data``. When the LlamaCloud keys are exhausted (all of them were on 2026-10-13) the
parsers fell back to a plain-text dump: no tables, ``issue_date: 2026-01-01``. Import ``LlamaParse`` from this
module instead and the same call tries LlamaParse first and, if it raises or returns nothing, parses the same
pages with Nace (parse_mode high, markdown tables, figures omitted: Nace does not turn charts into tables).

Nace keys: NACE_API_KEY, NACE_API_KEY_2 ... from the environment (GitHub secret on CI), then ~/.nace/keys.env
locally. A key without credit (402) is skipped. PARSE_BACKEND=nace skips LlamaParse; =llama disables Nace.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

PAGE_MARK = re.compile(r"(?m)^--- Page (\d+) ---\s*$")
_SUP = str.maketrans("0123456789,-+()", "⁰¹²³⁴⁵⁶⁷⁸⁹,⁻⁺⁽⁾")
_SUB = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")
_INLINE = re.compile(r"\\\((.{1,80}?)\\\)")


class Document:
    """Minimal stand-in for llama_index Document: callers only read ``.text`` and ``.metadata``."""

    def __init__(self, text: str, metadata: Optional[Dict[str, Any]] = None):
        self.text = text
        self.metadata = metadata or {}


def nace_keys() -> List[str]:
    keys: List[str] = []
    for name in ["NACE_API_KEY"] + [f"NACE_API_KEY_{i}" for i in range(2, 13)]:
        v = os.environ.get(name, "").strip()
        if v and v not in keys:
            keys.append(v)
    env_file = Path.home() / ".nace" / "keys.env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                v = v.strip().strip("\"'")
                if k.strip().startswith("NACE_API_KEY") and v and v not in keys:
                    keys.append(v)
    return keys


def _plain_inline_math(md: str) -> str:
    """Nace writes markers/units as inline LaTeX (\\( ^{1} \\), \\( SiO_{2} \\)); keep the simple ones as text."""

    def conv(m: re.Match) -> str:
        s = m.group(1).strip().replace("\\%", "%").replace("\\times", "×").replace("\\Delta", "Δ")
        s = s.replace("\\geq", "≥").replace("\\leq", "≤").replace("\\pm", "±").replace("\\sim", "~")
        s = s.replace("\\,", " ").replace("\\ ", " ").replace("\\$", "$")
        s = re.sub(r"\\frac\{(\d+)\}\{(\d+)\}", r"\1/\2", s)
        s = re.sub(r"\^\s*\{\s*\\circ\s*\}|\^\s*\\circ", "°", s)
        s = re.sub(r"\\(?:mathrm|text)\s*", "", s)
        for _ in range(3):
            s = re.sub(r"(?<![\^_])\{([^{}\\]*)\}", r"\1", s)
        s = re.sub(r"\^\{?(th|st|nd|rd)\}?", r"\1", s)
        s = re.sub(r"\^\{([\d,+\-()]+)\}", lambda x: x.group(1).translate(_SUP), s)
        s = re.sub(r"\^(\d)", lambda x: x.group(1).translate(_SUP), s)
        s = re.sub(r"\^\{([^{}\\^_]+)\}", r"\1", s)
        s = re.sub(r"_\{(\d+)\}", lambda x: x.group(1).translate(_SUB), s)
        s = re.sub(r"_(\d)", lambda x: x.group(1).translate(_SUB), s)
        s = re.sub(r"\s+", " ", s).strip()
        return m.group(0) if re.search(r"[\\^_{}]", s) else s

    return _INLINE.sub(conv, md)


_CAPS_TITLE = re.compile(r"^[A-Z0-9][A-Z0-9&/,'’()\-–:. ]{2,88}$")


def _promote_titles(md: str) -> str:
    """Nace writes section titles as plain lines on some runs and as '#' headings on others; the publisher
    extractors locate tables by heading. A standalone ALL-CAPS line (2+ letter words, no sentence period, not a
    table row) becomes '## TITLE', so the output does not depend on which form Nace chose."""
    lines = md.split("\n")
    for i, ln in enumerate(lines):
        s = ln.strip()
        if not s or s.startswith(("#", "|", "-", "*", ">")) or not _CAPS_TITLE.match(s) or s.endswith("."):
            continue
        if len(re.findall(r"[A-Z]{2,}", s)) < 2 or re.fullmatch(r"[\d\s.,%/()+\-–:]+", s):
            continue
        if i > 0 and lines[i - 1].strip() and not lines[i - 1].lstrip().startswith("#"):
            continue  # inside a paragraph
        lines[i] = "## " + s
    # A short standalone line right above a table is the table's title ("TC Rates", "Maritime Stock Data")
    for i, ln in enumerate(lines):
        s = ln.strip()
        if (not s or s.startswith(("#", "|", "-", "*", ">", "<")) or len(s) > 60 or len(s.split()) > 8
                or s.endswith((".", ",", ":", ";")) or not s[0].isalpha()):
            continue
        if i > 0 and lines[i - 1].strip():
            continue
        nxt = [x for x in lines[i + 1:i + 4] if x.strip()]
        if nxt and nxt[0].lstrip().startswith("|"):
            lines[i] = "### " + s
    return "\n".join(lines)


def _target_pages(spec: Optional[str], n_pages: int) -> List[int]:
    """LlamaParse ``target_pages`` is a 0-based comma list with ranges ("0,2-4"); default = all pages."""
    if not spec:
        return list(range(n_pages))
    out: List[int] = []
    for part in str(spec).split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            out.extend(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return [p for p in dict.fromkeys(out) if 0 <= p < n_pages]


# Nace's page-correction model sometimes returns its own prompt and reasoning instead of (or after) the page:
# "}Human: The attached image is one document page. The Markdown and layout blocks are first-pass OCR ..."
# (found in 3 committed MDs, 2026-10-19). The leak also swallows the next page's marker.
LEAK = re.compile(r"The attached image is one document page|first-pass OCR|Return only JSON matching the supplied schema"
                  r"|</?blocks>|^assistant\b|Assistant: I'll analy[sz]e the image", re.M)
_LEAK_START = re.compile(r"\}?\s*(?:Human|assistant)\s*:", re.I)


def _cut_leak(text: str) -> str:
    m = LEAK.search(text)
    if not m:
        return text
    starts = [s.start() for s in _LEAK_START.finditer(text, 0, m.start() + 1)]
    return text[:starts[-1] if starts else m.start()].rstrip()


def nace_parse_pdf(path: str, target_pages: Optional[str] = None, mode: str = "high",
                   _retry: bool = True) -> List[Document]:
    """Parse the given pages of a PDF with Nace; one Document per page, in page order. A page whose text carries a
    leaked model prompt is re-parsed on its own (with the page after it); if it still leaks, the leak is cut off."""
    import pymupdf

    keys = nace_keys()
    if not keys:
        raise RuntimeError("Nace fallback: no NACE_API_KEY configured")
    src = pymupdf.open(path)
    try:   # close the source: callers delete their temp PDF right after (Windows refuses an open file)
        return _parse_with_leak_guard(path, src, mode, keys, _target_pages(target_pages, len(src)), _retry)
    finally:
        src.close()


def _parse_with_leak_guard(path: str, src: Any, mode: str, keys: List[str], pages: List[int],
                           _retry: bool) -> List[Document]:
    if not pages:
        raise RuntimeError(f"Nace fallback: no pages selected in {path}")
    docs = _nace_parse_pages(path, src, pages, mode, keys)
    leaked = [i for i, d in enumerate(docs) if LEAK.search(d.text)]
    for i in leaked:
        logger.warning("Nace leaked its prompt on %s page %d", Path(path).name, pages[i] + 1)
    redo = sorted({j for i in leaked for j in (i, i + 1) if j < len(docs)})
    for j in redo:
        if _retry:
            try:
                again = _nace_parse_pages(path, src, [pages[j]], mode, keys)[0]
                if not LEAK.search(again.text) and again.text.strip():
                    docs[j] = again
                    continue
            except Exception as e:
                logger.warning("Nace re-parse of page %d failed: %s", pages[j] + 1, e)
        docs[j].text = _cut_leak(docs[j].text)
        docs[j].metadata["leak_cut"] = True
    if not any(d.text for d in docs):
        raise RuntimeError(f"Nace fallback: empty parse for {path}")
    logger.info("Nace parsed %s (%d pages)", Path(path).name, len(pages))
    return docs


def _nace_parse_pages(path: str, src: Any, pages: List[int], mode: str, keys: List[str]) -> List[Document]:
    import pymupdf
    from nace_sdk import NaceClient
    tmp = Path(tempfile.mkdtemp(prefix="nace_"))
    try:
        mini = pymupdf.open()
        for p in pages:
            mini.insert_pdf(src, from_page=p, to_page=p)
        sub = tmp / (Path(path).stem[:80] + ".pdf")
        mini.save(sub, garbage=4, deflate=True)
        last_err: Optional[Exception] = None
        for key in keys:
            try:
                with NaceClient(api_key=key, timeout=600) as c:
                    up = c.documents.upload(str(sub), path="ingest/" + sub.name, on_conflict="new_version")
                    job = c.documents.parse(
                        {"type": "workspace_file", "workspace_id": up.workspace_id, "file_id": up.file_id},
                        page_ranges=[{"start": 1, "end": len(pages)}], parse_mode=mode,
                        output={"formats": ["markdown"], "table_format": "markdown", "include_page_markers": True},
                        figures={"mode": "omit"}, wait_seconds=60)
                    t0 = time.time()
                    while job.status not in ("succeeded", "failed", "cancelled") and time.time() - t0 < 1800:
                        time.sleep(10)
                        job = c.jobs.get(job.job_id)
                    if job.status != "succeeded":
                        raise RuntimeError(f"Nace job {job.job_id} {job.status}")
                    doc = job.result["document"]
                    md = doc.get("markdown") or ""
                    if doc.get("content_url"):  # inline markdown is a preview past ~64 KB: fetch the full text
                        jid = job.job_id
                        dest = tmp / "full.md"
                        c.jobs.download(jid, doc["content_url"].split(f"/jobs/{jid}/", 1)[1], str(dest), wait_timeout=300)
                        md = dest.read_text(encoding="utf-8")
                break
            except Exception as e:  # 402 = no credit on this key: try the next one
                last_err = e
                if "402" in str(e) or "credit" in str(e).lower():
                    continue
                raise
        else:
            raise RuntimeError(f"Nace fallback: every key failed ({last_err})")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    md = _promote_titles(_plain_inline_math(md))
    parts = PAGE_MARK.split(md)
    texts: Dict[int, str] = {}
    if len(parts) > 1:
        for i in range(1, len(parts), 2):
            texts[int(parts[i])] = parts[i + 1].strip()
    else:
        texts[1] = md.strip()
    return [Document(texts.get(i + 1, ""), {"page": p + 1, "source": str(path), "parser": "nace"})
            for i, p in enumerate(pages)]


class LlamaParse:
    """Same constructor and load methods as llama_parse.LlamaParse; falls back to Nace on failure or empty output."""

    def __init__(self, api_key: Optional[str] = None, **kwargs: Any):
        self.api_key = api_key
        self.kwargs = kwargs
        self.backend_used: Optional[str] = None

    def _llama(self):
        from llama_parse import LlamaParse as _Real
        return _Real(api_key=self.api_key, **self.kwargs)

    def _want_llama(self) -> bool:
        return bool(self.api_key) and os.environ.get("PARSE_BACKEND", "").lower() != "nace"

    def _want_nace(self) -> bool:
        return os.environ.get("PARSE_BACKEND", "").lower() != "llama" and bool(nace_keys())

    def load_data(self, file_path: Any, extra_info: Optional[dict] = None, **kw: Any) -> List[Any]:
        err: Optional[Exception] = None
        if self._want_llama():
            try:
                docs = self._llama().load_data(file_path, extra_info=extra_info, **kw)
                if docs and any((getattr(d, "text", "") or "").strip() for d in docs):
                    self.backend_used = "llama"
                    return docs
                err = ValueError("Empty response returned by LlamaParse")
            except Exception as e:
                err = e
            logger.warning("LlamaParse failed on %s (%s)", Path(str(file_path)).name, str(err)[:160])
        if not self._want_nace():
            if err:
                raise err
            raise RuntimeError("LlamaParse has no key and the Nace fallback is not configured")
        docs = nace_parse_pdf(str(file_path), self.kwargs.get("target_pages"))
        if extra_info:
            for d in docs:
                d.metadata.update(extra_info)
        self.backend_used = "nace"
        return docs

    async def aload_data(self, file_path: Any, extra_info: Optional[dict] = None, **kw: Any) -> List[Any]:
        return await asyncio.to_thread(self.load_data, file_path, extra_info, **kw)
