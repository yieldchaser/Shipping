"""Paragraph rejoin (scripts/md_cleanup/join_wrapped_paragraphs.py) and lone list numbers (join_lone_list_numbers.py)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from md_cleanup.join_lone_list_numbers import join_numbers  # noqa: E402
from md_cleanup.join_wrapped_paragraphs import join_wrapped  # noqa: E402


def test_lowercase_continuation_joins_and_page_marker_moves_after():
    src = "The committee approved the\n\n<!-- Page 4 -->\n\nprogram of work in May.\n"
    out, n = join_wrapped(src)
    assert n == 1
    assert out == "The committee approved the program of work in May.\n\n<!-- Page 4 -->\n"


def test_sentence_end_heading_table_never_joined():
    src = "It ended here.\n\nnext starts lower\n\n## Heading\n\nlower text\n\n| a | b |\n|---|---|\n| 1 | 2 |\n"
    assert join_wrapped(src)[1] == 0


def test_hyphen_kept_without_space():
    out, n = join_wrapped("an economically impossible main-\n\ntain the service.\n")
    assert n == 1 and "main-tain the service." in out


def test_caption_jumped_only_for_prose_and_moved_after():
    src = ("Ship prices rose sharply in the second half as owners in the\n\n*Chart: Prices*\n\n"
           "Source: Clarksons\n\nbulk sector ordered more ships.\n")
    out, n = join_wrapped(src)
    assert n == 1
    assert out.index("owners in the bulk sector ordered") < out.index("*Chart: Prices*") < out.index("Source: Clarksons")


def test_caption_is_never_first_half():
    src = "Source: Macquarie Capital, USA\n\nultra-light crude oils can then be exported.\n"
    assert join_wrapped(src)[1] == 0


def test_prose_starting_with_figure_is_not_a_caption():
    out, n = join_wrapped("Figure 2.3 portrays the market and a typical owner. The\n\nleft-hand panel plots demand.\n")
    assert n == 1


def test_list_item_continuation_but_not_subitem():
    out, n = join_wrapped("1. Remuneration is reported in US$. The amounts have been\n\nconverted at average rates.\n")
    assert n == 1 and "have been converted" in out
    assert join_wrapped("15. Subsequent Events\n\na) On January 17, 2017, the Company drew down.\n")[1] == 0


def test_folios_and_running_headers_are_not_text():
    src = "pieces of equipment. Similarly, the superintendent\n\nl89\n\nmust inspect the ship.\n"
    out, n = join_wrapped(src)
    assert n == 1 and "superintendent must inspect" in out and out.rstrip().endswith("l89")
    words = ["fleet", "orderbook", "charter", "scrapping", "bunker"]
    hdr = "".join(f"The {w} outlook remained weak through the\n\nACME ANNUAL REPORT | {i}\n\n{w} season.\n\n"
                  for i, w in enumerate(words))
    out, n = join_wrapped(hdr)
    assert n == 5 and "weak through the bunker season." in out


def test_url_is_not_a_continuation():
    assert join_wrapped("London Office | Tel: +44 (0)208 144 6868\n\nwww.agoraships.com\n")[1] == 0


def test_idempotent_and_crlf_kept():
    src = "The committee approved the\r\n\r\nprogram of work.\r\n"
    out, n = join_wrapped(src)
    assert n == 1 and "\r\n" in out and join_wrapped(out)[1] == 0


def test_lone_numbers_joined_only_in_runs():
    src = "### Table 18.1\n\n1.\nStrategic Asset Management\n2.\nFinancial Management\n3.\nAccounting\n"
    out, n = join_numbers(src)
    assert n == 3 and "1. Strategic Asset Management\n2. Financial Management\n3. Accounting" in out
    year = "service faded away between 1960 and\n1972.\nDriven off their routes, liners cruised.\n"
    assert join_numbers(year)[1] == 0
