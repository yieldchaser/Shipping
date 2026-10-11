"""SEC corpus Markdown table repair (join continuation rows, bullet tables -> lists) and
the EX-99.x exhibit appender. No network access: the HTTP session is faked."""
from __future__ import annotations

import re

import pytest

from scripts.acquire import repair_sec_markdown_tables as R
from scripts.acquire import sec_exhibits as X


# ---------------------------------------------------------------- table repair

BROKEN_TABLE = (
    "Intro paragraph.\n"
    "\n"
    "| Title of each class | Trading Symbol(s) | Name of exchange on which registered |\n"
    "| :--- | :--- | :--- |\n"
    "| Common Shares,\n"
    "par value \\$0.01 per share | SBLK | Nasdaq\n"
    "Global Select Market |\n"
    "\n"
    "Closing paragraph.\n"
)


def test_continuation_lines_are_joined_into_the_row():
    fixed, stats = R.repair_markdown(BROKEN_TABLE)
    assert "| Common Shares, par value \\$0.01 per share | SBLK | Nasdaq Global Select Market |" in fixed
    assert stats == {"rows_joined": 1, "bullets_converted": 0}
    assert fixed.count("\n") == BROKEN_TABLE.count("\n") - 2


def test_joined_table_has_consistent_cell_counts():
    fixed, _ = R.repair_markdown(BROKEN_TABLE)
    rows = [l for l in fixed.split("\n") if l.startswith("|")]
    assert len(rows) == 3
    assert {len(re.split(r"(?<!\\)\|", r.rstrip()[:-1])) - 1 for r in rows} == {3}


def test_blank_line_inside_a_cell_is_tolerated():
    text = "| A | first\n\nsecond |\n"
    fixed, stats = R.repair_markdown(text)
    assert fixed == "| A | first second |\n"
    assert stats["rows_joined"] == 1


def test_open_row_without_a_closing_line_is_left_alone():
    text = "| A | never closed\nplain text\nmore text\n\n| B | C |\n"
    fixed, stats = R.repair_markdown(text)
    assert fixed == text
    assert stats["rows_joined"] == 0


def test_bullet_table_becomes_list_items():
    text = (
        "Factors include:\n"
        "\n"
        "| · | supply of, and demand for, drybulk commodities; |\n"
        "| · | changes in the exploration or production of energy resources and\n"
        "trade; |\n"
        "| • | embargoes and strikes; | |\n"
        "\n"
        "After.\n"
    )
    fixed, stats = R.repair_markdown(text)
    assert fixed == (
        "Factors include:\n"
        "\n"
        "- supply of, and demand for, drybulk commodities;\n"
        "- changes in the exploration or production of energy resources and trade;\n"
        "- embargoes and strikes;\n"
        "\n"
        "After.\n"
    )
    assert stats == {"rows_joined": 1, "bullets_converted": 3}


def test_real_tables_and_bullet_matrices_are_not_converted():
    text = (
        "| Capital KPIs | Sustainability KPIs |\n"
        "| :--- | :--- |\n"
        "| ● | ● |\n"
        "| · | text row inside a real table |\n"
        "\n"
        "| · | a | b |\n"
    )
    fixed, stats = R.repair_markdown(text)
    assert fixed == text
    assert stats == {"rows_joined": 0, "bullets_converted": 0}


def test_everything_else_is_byte_identical():
    text = (
        "---\nticker: X\n---\n\n"
        "# Heading\r\n\n"
        "Plain · bullet line stays\n"
        "· plain bullet paragraph stays\n"
        "- existing list\n"
        "  \n"
        "| A | B |\n| :--- | ---: |\n| 1 | 2 |\n"
        "trailing spaces   \n\n\n"
    )
    fixed, stats = R.repair_markdown(text)
    assert fixed == text
    assert stats == {"rows_joined": 0, "bullets_converted": 0}


def test_repair_is_idempotent():
    once, _ = R.repair_markdown(BROKEN_TABLE + "| · | item |\n")
    twice, stats = R.repair_markdown(once)
    assert twice == once
    assert stats == {"rows_joined": 0, "bullets_converted": 0}


def test_text_preservation_assertion_accepts_repair_and_rejects_loss():
    text = BROKEN_TABLE + "| · | item one |\n| · | item two |\n"
    fixed, stats = R.repair_markdown(text)
    R.assert_text_preserved(text, fixed, stats["bullets_converted"])
    with pytest.raises(AssertionError):
        R.assert_text_preserved(text, fixed.replace("Nasdaq", ""), stats["bullets_converted"])
    with pytest.raises(AssertionError):
        R.assert_text_preserved(text, fixed + "extra", stats["bullets_converted"])


def test_repair_file_preserves_crlf_and_dry_run_does_not_write(tmp_path):
    path = tmp_path / "a.md"
    path.write_bytes(BROKEN_TABLE.replace("\n", "\r\n").encode("utf-8"))
    original = path.read_bytes()

    R.repair_file(path, dry_run=True)
    assert path.read_bytes() == original

    stats = R.repair_file(path)
    assert stats["rows_joined"] == 1
    data = path.read_bytes().decode("utf-8")
    assert "\r\n" in data and "\n" not in data.replace("\r\n", "")
    assert "| Common Shares, par value" in data
    assert R.repair_file(path)["rows_joined"] == 0


# ---------------------------------------------------------------- exhibit appending

INDEX_HTML = """
<html><body><table class="tableFile" summary="Document Format Files">
<tr><th>Seq</th><th>Description</th><th>Document</th><th>Type</th><th>Size</th></tr>
<tr><td>1</td><td>6-K</td><td><a href="/Archives/edgar/data/1331284/000095015726000799/form6k.htm">form6k.htm</a></td><td>6-K</td><td>11813</td></tr>
<tr><td>2</td><td>PRESS RELEASE</td><td><a href="/Archives/edgar/data/1331284/000095015726000799/ex99-1.htm">ex99-1.htm</a></td><td>EX-99.1</td><td>6133</td></tr>
<tr><td>3</td><td>Presentation</td><td><a href="/Archives/edgar/data/1331284/000095015726000799/ex99-2.htm">ex99-2.htm</a></td><td>EX-99.2</td><td>900</td></tr>
<tr><td>4</td><td>Slides</td><td><a href="/Archives/edgar/data/1331284/000095015726000799/slides.pdf">slides.pdf</a></td><td>EX-99.3</td><td>900</td></tr>
<tr><td>5</td><td>XBRL</td><td><a href="/Archives/edgar/data/1331284/000095015726000799/x.htm">x.htm</a></td><td>EX-101.INS</td><td>900</td></tr>
<tr><td>6</td><td>COVER</td><td><a href="/Archives/edgar/data/1331284/000095015726000799/c.htm">c.htm</a></td><td>EX-104</td><td>900</td></tr>
<tr><td>7</td><td>CONSENT</td><td><a href="/Archives/edgar/data/1331284/000095015726000799/e.htm">e.htm</a></td><td>EX-23.1</td><td>900</td></tr>
<tr><td>8</td><td>GRAPHIC</td><td><a href="/Archives/edgar/data/1331284/000095015726000799/g.jpg">g.jpg</a></td><td>GRAPHIC</td><td>900</td></tr>
</table></body></html>
"""

ACCESSION = "0000950157-26-000799"
BASE = "https://www.sec.gov/Archives/edgar/data/1331284/000095015726000799/"
FRONTMATTER = (
    "---\nticker: DHT\ncik: \"0001331284\"\nform: 6-K\naccession_number: '" + ACCESSION + "'\n"
    "source: sec_edgar\nsource_file: corpus/10-companies/DHT/6-K/x.md\n---\n\n"
)


class FakeResponse:
    def __init__(self, status_code, content=b"", headers=None):
        self.status_code = status_code
        self.content = content
        self.headers = headers or {}


class FakeSession:
    """requests.Session stand-in serving canned bodies; `script` lets a URL fail first."""

    def __init__(self, pages, script=None):
        self.headers = {}
        self.pages = pages
        self.script = script or {}
        self.calls = []

    def get(self, url, timeout=None):
        self.calls.append(url)
        queue = self.script.get(url)
        if queue:
            return FakeResponse(queue.pop(0), b"", {"Retry-After": "0"})
        if url in self.pages:
            return FakeResponse(200, self.pages[url].encode("utf-8"))
        return FakeResponse(404)


def _client(tmp_path, session, sleeps=None):
    sleeps = sleeps if sleeps is not None else []
    return X.SecClient(cache_dir=tmp_path / "cache", session=session, sleep=sleeps.append)


def _pages():
    return {
        X.index_url("0001331284", ACCESSION): INDEX_HTML,
        BASE + "ex99-1.htm": "<DOCUMENT><TYPE>EX-99.1<TEXT><HTML><p>Q2 TCE</p></HTML></TEXT></DOCUMENT>",
        BASE + "ex99-2.htm": "<html><p>Fleet update</p></html>",
    }


def _converter(html):
    return re.sub(r"<[^>]+>", "", html).strip()


def test_only_ex99_text_exhibits_are_selected():
    refs = X.select_exhibits(X.parse_index_html(INDEX_HTML))
    assert [r.doc_type for r in refs] == ["EX-99.1", "EX-99.2"]
    assert refs[0].url == BASE + "ex99-1.htm"


def test_exhibits_are_appended_with_headings_and_frontmatter_key(tmp_path):
    session = FakeSession(_pages())
    sections = X.build_exhibit_sections(_client(tmp_path, session), "0001331284", ACCESSION, converter=_converter)
    assert [t for t, _ in sections] == ["EX-99.1", "EX-99.2"]
    assert sections[0][1] == "## Exhibit 99.1 — PRESS RELEASE\n\nQ2 TCE"  # SGML envelope removed

    main = FRONTMATTER + "Cover page text.\n"
    merged = X.append_exhibits(main, sections)
    assert merged.startswith(FRONTMATTER.replace("---\n\n", "exhibits: [EX-99.1, EX-99.2]\n---\n\n"))
    assert merged.endswith(
        "Cover page text.\n\n## Exhibit 99.1 — PRESS RELEASE\n\nQ2 TCE\n\n"
        "## Exhibit 99.2 — Presentation\n\nFleet update\n"
    )
    # frontmatter and main body are otherwise untouched
    assert merged.replace("exhibits: [EX-99.1, EX-99.2]\n", "", 1).startswith(main.rstrip("\n"))
    assert X.has_exhibits(merged) and not X.has_exhibits(main)


def test_append_is_a_noop_when_already_done_or_empty(tmp_path):
    main = FRONTMATTER + "Cover.\n"
    assert X.append_exhibits(main, []) == main
    once = X.append_exhibits(main, [("EX-99.1", "## Exhibit 99.1\n\nx")])
    assert X.append_exhibits(once, [("EX-99.1", "## Exhibit 99.1\n\nx")]) == once


def test_append_preserves_crlf():
    main = (FRONTMATTER + "Cover.\n").replace("\n", "\r\n")
    merged = X.append_exhibits(main, [("EX-99.1", "## Exhibit 99.1\n\nx")])
    assert "\r\nexhibits: [EX-99.1]\r\n---\r\n" in merged
    assert "\n" not in merged.replace("\r\n", "")


def test_raw_html_is_cached_so_reruns_make_no_requests(tmp_path):
    session = FakeSession(_pages())
    client = _client(tmp_path, session)
    X.build_exhibit_sections(client, "0001331284", ACCESSION, converter=_converter)
    first = len(session.calls)
    assert first == 3  # index + two exhibits
    X.build_exhibit_sections(client, "0001331284", ACCESSION, converter=_converter)
    assert len(session.calls) == first


def test_retry_with_backoff_on_429_and_503_and_rate_limit(tmp_path):
    url = BASE + "ex99-2.htm"
    session = FakeSession(_pages(), script={url: [429, 503]})
    sleeps = []
    client = _client(tmp_path, session, sleeps)
    assert "Fleet update" in client.get_text(url)
    assert session.calls.count(url) == 3
    assert len(sleeps) >= 2


def test_gives_up_with_clear_error_and_does_not_cache_failures(tmp_path):
    url = BASE + "ex99-2.htm"
    session = FakeSession(_pages(), script={url: [503] * 10})
    client = _client(tmp_path, session)
    with pytest.raises(X.SecFetchError):
        client.get_text(url)
    assert not client._cache_path(url).exists()
    with pytest.raises(X.SecFetchError):
        client.get_text(BASE + "missing.htm")  # 404 is not retried
    assert session.calls.count(BASE + "missing.htm") == 1


def test_request_rate_is_capped_at_eight_per_second(tmp_path):
    sleeps = []
    client = _client(tmp_path, FakeSession(_pages()), sleeps)
    assert client.min_interval == pytest.approx(0.125)


def test_index_parsing_handles_agent_quirks():
    html = """<table class="tableFile" summary="Document Format Files">
<tr><th>Seq</th><th>Description</th><th>Document</th><th>Type</th><th>Size</th></tr>
<tr><td>1</td><td></td><td><a href="/ix?doc=/Archives/edgar/data/863064/000162828026050377/rio-20260630.htm">rio-20260630.htm</a></td><td>6-K</td><td>9</td></tr>
<tr><td>2</td><td></td><td><a href="/Archives/edgar/data/1318885/000091957426004216/exh99_1.htm">exh99_1.htm</a></td><td>EX-99.1 CHARTER</td><td>9</td></tr>
<tr><td>3</td><td>&nbsp;</td><td><a href="/ix?doc=/Archives/edgar/data/863064/000162828026050377/rio_d2.htm">rio_d2.htm</a></td><td>EX-99.2</td><td>9</td></tr>
</table>"""
    refs = X.parse_index_html(html)
    assert refs[0].url == "https://www.sec.gov/Archives/edgar/data/863064/000162828026050377/rio-20260630.htm"
    assert (refs[1].doc_type, refs[1].description) == ("EX-99.1", "CHARTER")
    selected = X.select_exhibits(refs)
    assert [r.doc_type for r in selected] == ["EX-99.1", "EX-99.2"]
    assert selected[1].url.startswith("https://www.sec.gov/Archives/edgar/data/863064/")
    assert X.exhibit_heading(selected[0]) == "## Exhibit 99.1 \u2014 CHARTER"
    assert X.exhibit_heading(selected[1]) == "## Exhibit 99.2"
