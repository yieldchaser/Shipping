"""Reject bot walls and mislabeled payloads before they are written to disk.

Why this exists
---------------
Three scrapers (breakwave insights, baltic, hellenic) and the HSN shipbroker
fetcher all did the same thing: take an HTTP response, decide the file extension
from the URL, and write the bytes. Nothing inspected the content.

Measured consequence on this repo's own archive (2026-09-22): 68 files under
reports/breakwave/pdfs/ carry a .pdf extension but are not PDFs. 67 are
5,174-byte login pages whose entire visible text is "Login Page"; one is a
search-results page. The baltic archive shows the same pattern - 850 files
classified as "bot-wall asset placeholder".

The damage is not the wasted bytes, it is that a mislabeled asset is worse than
a missing one:

  * it reads as corrupt data to a PDF extractor,
  * it inflates asset and document counts,
  * and it can fall between passes entirely. These 68 files were skipped by the
    PDF extractor (correctly: no %PDF header) and never seen by the HTML pass
    (which only globs *.html), so nothing downstream could detect them.

Call asset_payload_verdict() before every write of a downloaded asset.
"""
from __future__ import annotations

# Text meaning we were served a wall rather than the asset. The first two are
# the ones actually observed in this repo's archive; the rest are the common
# interstitials, included so the guard covers more than the cases already seen.
BOT_WALL_MARKERS = (
    b"login page",
    b"challenge validation",
    b"just a moment",
    b"enable javascript and cookies to continue",
    b"attention required",
    b"access denied",
    b"are you a robot",
    b"search results |",
)

# How much of the payload to scan for wall markers.
HEAD_BYTES = 4096


def asset_payload_verdict(payload: bytes, extension: str) -> tuple[bool, str]:
    """Decide whether a downloaded asset is real content or a wall.

    Returns (ok, reason); reason is empty when ok.

    A .pdf must actually begin with %PDF. Anything else that looks like a bot
    wall or login interstitial is refused regardless of extension, because the
    failure mode is not specific to PDFs - the baltic asset placeholders were
    plain HTML.
    """
    if not payload:
        return False, "empty payload"

    ext = (extension or "").lower()

    if ext == ".pdf" and not payload[:5].startswith(b"%PDF"):
        return False, "not a PDF despite .pdf extension"

    head = payload[:HEAD_BYTES].lower()
    for marker in BOT_WALL_MARKERS:
        if marker in head:
            return False, f"bot wall ({marker.decode('ascii', 'replace')})"

    return True, ""
