"""LlamaParse client. Uses the v2 Parse API (REST, multipart upload):

  POST /api/v2/parse/upload   multipart: `file` + `configuration` (JSON string)
  GET  /api/v2/parse/{id}?expand=markdown,metadata

Endpoints/fields were taken from llama-cloud 0.1.46 (llama_cloud/resources/v_2/client.py
and its tier/version literals) and verified against the live validator. The SDK
`upload_file_multipart` is a stub without a file argument, hence direct REST.
`merge_continued_tables` is accepted by the server under output_options.markdown.tables
(it is rejected directly under output_options.markdown and absent from the SDK models).

If the v2 endpoint is unavailable (404/405/501) the v1 fallback
(`/api/parsing/upload`, 0-based `target_pages`, `parse_mode`) is used and recorded.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import requests

from scripts.parse_engine.config import CREDITS_PER_PAGE, spec_to_pages
from scripts.parse_engine.keys import KeyPool, mask

BASE_URL = "https://api.cloud.llamaindex.ai"
V1_PARSE_MODE = {
    "fast": "parse_page_without_llm",
    "cost_effective": "parse_page_with_llm",
    "agentic": "parse_page_with_agent",
    "agentic_plus": "parse_page_with_lvm",
}


class CreditsExhausted(RuntimeError):
    pass


class LlamaParseError(RuntimeError):
    pass


class _V2Unavailable(RuntimeError):
    pass


def estimate_credits(tier: str, n_pages: int) -> int:
    return CREDITS_PER_PAGE[tier] * n_pages


def build_v2_configuration(tier: str, version: str, pages: str, custom_prompt: str | None,
                           merge_continued_tables: bool, disable_cache: bool = True) -> dict[str, Any]:
    cfg: dict[str, Any] = {
        "tier": tier,
        "version": version,
        "page_ranges": {"target_pages": pages},
        "disable_cache": disable_cache,
    }
    if custom_prompt and tier in ("agentic", "agentic_plus"):
        cfg["agentic_options"] = {"custom_prompt": custom_prompt}
    if merge_continued_tables:
        cfg["output_options"] = {"markdown": {"tables": {"merge_continued_tables": True}}}
    return cfg


def _is_credit_error(status: int, text: str) -> bool:
    return status == 402 or "exceeded the maximum number of credits" in text.lower()


def _find_version(body: dict) -> str | None:
    """Best-effort: look for a resolved version string in job/metadata."""
    for section in (body.get("job") or {}, body.get("metadata") or {}):
        if isinstance(section, dict):
            for k in ("version", "resolved_version", "parse_version"):
                if isinstance(section.get(k), str):
                    return section[k]
    return None


class LlamaParseClient:
    def __init__(self, pool: KeyPool | None = None, poll_interval: float = 3.0, timeout: float = 900.0):
        self.pool = pool or KeyPool()
        self.poll_interval = poll_interval
        self.timeout = timeout

    def parse(self, pdf_path: Path, tier: str, version: str, pages: str,
              custom_prompt: str | None = None, merge_continued_tables: bool = True) -> dict[str, Any]:
        """Parse `pages` (1-based spec) and return a cacheable payload dict."""
        tried: list[str] = []
        while True:
            key = self.pool.current()
            if key is None:
                raise CreditsExhausted("all LlamaCloud keys exhausted this month (tried: %s)" % ", ".join(tried))
            try:
                try:
                    payload = self._parse_v2(key, pdf_path, tier, version, pages, custom_prompt,
                                             merge_continued_tables)
                except _V2Unavailable:
                    payload = self._parse_v1(key, pdf_path, tier, pages)
            except CreditsExhausted:
                self.pool.mark_exhausted(key)
                tried.append(mask(key))
                continue
            payload["key_prefix"] = mask(key)
            payload["keys_skipped_exhausted"] = tried
            return payload

    # -- v2 ---------------------------------------------------------------
    def _parse_v2(self, key, pdf_path, tier, version, pages, custom_prompt, merge) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {key}"}
        cfg = build_v2_configuration(tier, version, pages, custom_prompt, merge)
        with open(pdf_path, "rb") as fh:
            r = requests.post(f"{BASE_URL}/api/v2/parse/upload", headers=headers,
                              files={"file": (Path(pdf_path).name, fh, "application/pdf")},
                              data={"configuration": json.dumps(cfg)}, timeout=120)
        if _is_credit_error(r.status_code, r.text):
            raise CreditsExhausted(mask(key))
        if r.status_code in (404, 405, 501):
            raise _V2Unavailable(r.text[:200])
        if r.status_code >= 300:
            raise LlamaParseError(f"v2 upload failed {r.status_code}: {r.text[:500]}")
        job_id = r.json()["id"]
        deadline = time.time() + self.timeout
        while True:
            g = requests.get(f"{BASE_URL}/api/v2/parse/{job_id}", headers=headers,
                             params={"expand": "markdown,metadata"}, timeout=120)
            if _is_credit_error(g.status_code, g.text):
                raise CreditsExhausted(mask(key))
            if g.status_code >= 300:
                raise LlamaParseError(f"v2 poll failed {g.status_code}: {g.text[:500]}")
            body = g.json()
            status = str(body.get("job", {}).get("status", "")).upper()
            if status in ("COMPLETED", "SUCCESS"):
                break
            if status in ("FAILED", "CANCELLED", "ERROR"):
                msg = json.dumps(body.get("job", {}))
                if _is_credit_error(0, msg):
                    raise CreditsExhausted(mask(key))
                raise LlamaParseError(f"v2 job {job_id} {status}: {msg[:500]}")
            if time.time() > deadline:
                raise LlamaParseError(f"v2 job {job_id} timed out (last status {status})")
            time.sleep(self.poll_interval)
        md_pages = (body.get("markdown") or {}).get("pages") or []
        page_list = spec_to_pages(pages)
        markdown_pages = []
        for i, p in enumerate(md_pages):
            markdown_pages.append({
                "page": p.get("page_number") or (page_list[i] if i < len(page_list) else i + 1),
                "markdown": p.get("markdown") or "",
                "success": p.get("success", True),
                "error": p.get("error"),
            })
        return {
            "api": "v2",
            "engine": "llamaparse",
            "tier": tier,
            "version_requested": version,
            "version_resolved": _find_version(body) or version,
            "pages": pages,
            "configuration": cfg,
            "job_id": job_id,
            "job": body.get("job"),
            "metadata": body.get("metadata"),
            "markdown_pages": markdown_pages,
            "markdown": "\n\n".join(p["markdown"] for p in markdown_pages),
            "credits_estimated": estimate_credits(tier, len(page_list)),
            "parsed_at_epoch": int(time.time()),
        }

    # -- v1 fallback -------------------------------------------------------
    def _parse_v1(self, key, pdf_path, tier, pages) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {key}"}
        zero_based = ",".join(str(p - 1) for p in spec_to_pages(pages))  # v1 target_pages is 0-based
        data = {"parse_mode": V1_PARSE_MODE[tier], "target_pages": zero_based}
        with open(pdf_path, "rb") as fh:
            r = requests.post(f"{BASE_URL}/api/parsing/upload", headers=headers,
                              files={"file": (Path(pdf_path).name, fh, "application/pdf")},
                              data=data, timeout=120)
        if _is_credit_error(r.status_code, r.text):
            raise CreditsExhausted(mask(key))
        if r.status_code >= 300:
            raise LlamaParseError(f"v1 upload failed {r.status_code}: {r.text[:500]}")
        job_id = r.json()["id"]
        deadline = time.time() + self.timeout
        while True:
            s = requests.get(f"{BASE_URL}/api/parsing/job/{job_id}", headers=headers, timeout=60)
            if _is_credit_error(s.status_code, s.text):
                raise CreditsExhausted(mask(key))
            st = str(s.json().get("status", "")).upper()
            if st == "SUCCESS":
                break
            if st in ("ERROR", "CANCELED", "FAILED"):
                raise LlamaParseError(f"v1 job {job_id} {st}: {s.text[:300]}")
            if time.time() > deadline:
                raise LlamaParseError(f"v1 job {job_id} timed out")
            time.sleep(self.poll_interval)
        m = requests.get(f"{BASE_URL}/api/parsing/job/{job_id}/result/markdown", headers=headers, timeout=120)
        md = m.json().get("markdown", "")
        return {
            "api": "v1", "engine": "llamaparse", "tier": tier, "version_requested": "v1",
            "version_resolved": "v1", "pages": pages, "job_id": job_id, "markdown": md,
            "markdown_pages": [], "credits_estimated": estimate_credits(tier, len(spec_to_pages(pages))),
            "parsed_at_epoch": int(time.time()),
        }
