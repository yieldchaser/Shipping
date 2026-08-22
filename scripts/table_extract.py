"""Geometry-based structured table extraction from image-backed market tables.

Pure-geometry core (row clustering, column detection, grid assembly) that is
fully unit-testable without tesseract, plus a thin OCR wrapper around
pytesseract.image_to_data. Used to recover Alibra time-charter and MMI iron
ore tables that arrive as screenshots inside archived Hellenic articles.

Word dict shape produced/consumed everywhere:
    {"x0": int, "y0": int, "x1": int, "y1": int, "text": str, "conf": float}

The public entry point extract_table_text() NEVER raises: missing pytesseract,
missing tesseract binary, or any geometry failure yields None so callers can
fall back to raw OCR text.
"""

from __future__ import annotations

import bisect
import math
import re
import statistics

NUMERIC_CELL_RE = re.compile(r"^[$€£]?-?[\d,]+(\.\d+)?%?$")
_ALPHA_START_RE = re.compile(r"^[A-Za-z]")


def words_from_image(image, min_conf: float = 30.0) -> list[dict]:
    """Run tesseract word-level OCR; return filtered word dicts.

    Raises RuntimeError("pytesseract unavailable") when pytesseract cannot be
    imported. Propagates pytesseract.TesseractNotFoundError when the tesseract
    binary itself is missing (callers should treat both as "no OCR").
    """
    try:
        import pytesseract
    except Exception as exc:
        raise RuntimeError("pytesseract unavailable") from exc

    data = pytesseract.image_to_data(
        image, output_type=pytesseract.Output.DICT, config="--psm 6"
    )
    texts = data.get("text") or []
    words: list[dict] = []
    for i in range(len(texts)):
        text = str(texts[i] or "").strip()
        if not text:
            continue
        try:
            conf = float(data["conf"][i])
            x0 = int(data["left"][i])
            y0 = int(data["top"][i])
            w = int(data["width"][i])
            h = int(data["height"][i])
        except (KeyError, IndexError, TypeError, ValueError):
            continue
        if conf < min_conf or w <= 0 or h <= 0:
            continue
        words.append({"x0": x0, "y0": y0, "x1": x0 + w, "y1": y0 + h, "text": text, "conf": conf})
    return words


def rows_from_words(words: list[dict], y_tol_ratio: float = 0.6) -> list[list[dict]]:
    """Greedy y-center clustering of words into visual rows.

    Words are processed in ascending y-center order and appended to the current
    row while their y-center stays within ``y_tol_ratio * median_word_height``
    of the row's running y-center. Each returned row is sorted by x0.
    """
    if not words:
        return []

    def y_center(w: dict) -> float:
        return (w["y0"] + w["y1"]) / 2.0

    ordered = sorted(words, key=y_center)
    med_h = float(statistics.median(w["y1"] - w["y0"] for w in words)) or 1.0
    tol = y_tol_ratio * med_h

    rows: list[list[dict]] = []
    current: list[dict] = []
    current_yc = 0.0
    for w in ordered:
        yc = y_center(w)
        if current and abs(yc - current_yc) > tol:
            rows.append(current)
            current = []
        current.append(w)
        current_yc = sum(y_center(x) for x in current) / len(current)
    if current:
        rows.append(current)
    return [sorted(row, key=lambda w: w["x0"]) for row in rows]


def columns_from_rows(rows: list[list[dict]]) -> list[float]:
    """Detect column boundaries from an x-coverage profile across all rows.

    Every word marks the [x0, x1) interval it covers. An x position is a gap
    candidate when it is uncovered in >= 60% of rows; maximal runs of such
    positions whose pixel length is >= max(0.8 * median_word_height, 6px)
    become boundaries placed at the run's midpoint.
    """
    flat = [w for row in rows for w in row]
    if not rows or not flat:
        return []
    med_h = float(statistics.median(w["y1"] - w["y0"] for w in flat))
    gap_threshold = max(med_h * 0.8, 6.0)

    xmin = int(min(w["x0"] for w in flat))
    xmax = int(max(w["x1"] for w in flat))
    span = xmax - xmin
    if span <= 0:
        return []

    needed = math.ceil(len(rows) * 0.6)
    uncovered_count = [0] * span
    for row in rows:
        delta = [0] * (span + 1)
        for w in row:
            a = max(int(w["x0"]) - xmin, 0)
            b = min(int(w["x1"]) - xmin, span)
            if b > a:
                delta[a] += 1
                delta[b] -= 1
        covered = 0
        for i in range(span):
            covered += delta[i]
            if covered == 0:
                uncovered_count[i] += 1

    boundaries: list[float] = []
    run_start: int | None = None
    for i, count in enumerate(uncovered_count):
        if count >= needed:
            if run_start is None:
                run_start = i
        else:
            if run_start is not None and (i - run_start) >= gap_threshold:
                boundaries.append(float(xmin) + (run_start + (i - 1)) / 2.0)
            run_start = None
    if run_start is not None and (span - run_start) >= gap_threshold:
        boundaries.append(float(xmin + (run_start + (span - 1)) / 2.0))
    return boundaries


def table_from_rows(rows: list[list[dict]]) -> list[list[str]] | None:
    """Assign words to detected columns by x-center; join cells with spaces.

    Returns None when fewer than 3 columns or fewer than 3 non-empty rows are
    recoverable (not table-like). All-empty rows are dropped first.
    """
    if not rows:
        return None
    boundaries = columns_from_rows(rows)
    ncols = len(boundaries) + 1
    if ncols < 3:
        return None

    grid: list[list[str]] = []
    for row in rows:
        cells: list[list[str]] = [[] for _ in range(ncols)]
        for w in row:
            xc = (w["x0"] + w["x1"]) / 2.0
            idx = min(bisect.bisect_right(boundaries, xc), ncols - 1)
            cells[idx].append(w["text"])
        grid.append([" ".join(cell).strip() for cell in cells])

    grid = [row for row in grid if any(cell for cell in row)]
    if len(grid) < 3:
        return None
    return grid


def is_market_table(grid: list[list[str]]) -> bool:
    """Heuristic: does this grid look like a numeric market/rate table?

    True when >= 3 columns, >= 3 rows, and >= 35% of body cells (row 0 treated
    as header and excluded) match NUMERIC_CELL_RE. As a secondary acceptance
    path, grids containing label-numeric rows (alpha first cell, all other
    non-empty cells numeric) pass with a lower 15% threshold, since segment/
    route labels make a rate table much more likely even when diluted by text.
    """
    if not grid or len(grid) < 3:
        return False
    if max(len(row) for row in grid) < 3:
        return False

    total = 0
    numeric = 0
    labeled_rows = 0
    for row in grid[1:]:
        stripped = [cell.strip() for cell in row]
        non_empty = [cell for cell in stripped if cell]
        total += len(non_empty)
        numeric += sum(1 for cell in non_empty if NUMERIC_CELL_RE.match(cell))
        if stripped and stripped[0] and _ALPHA_START_RE.match(stripped[0]):
            rest = [cell for cell in stripped[1:] if cell]
            if rest and all(NUMERIC_CELL_RE.match(cell) for cell in rest):
                labeled_rows += 1

    frac = (numeric / total) if total else 0.0
    if frac >= 0.35:
        return True
    return labeled_rows >= 1 and frac >= 0.15


def grid_to_markdown(grid: list[list[str]]) -> str:
    """Render a grid as a GitHub-flavored pipe table; literal pipes escaped."""
    if not grid:
        return ""
    width = max(len(row) for row in grid)

    def fmt(row: list[str]) -> str:
        padded = [str(row[i]).replace("|", "\\|").strip() if i < len(row) else "" for i in range(width)]
        return "| " + " | ".join(padded) + " |"

    lines = [fmt(grid[0]), "|" + "|".join("---" for _ in range(width)) + "|"]
    lines.extend(fmt(row) for row in grid[1:])
    return "\n".join(lines)


def extract_table_text(image, min_conf: float = 30.0) -> str | None:
    """OCR an image and return its market table as markdown, else None.

    Never raises: pytesseract missing, tesseract binary missing
    (pytesseract.TesseractNotFoundError), unusable input, or non-table content
    all yield None so callers keep their existing raw-OCR fallback path.
    """
    try:
        words = words_from_image(image, min_conf=min_conf)
        rows = rows_from_words(words)
        if not rows:
            return None
        grid = table_from_rows(rows)
        if grid is None or not is_market_table(grid):
            return None
        return grid_to_markdown(grid)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Self-test: fabricates synthetic word dicts; needs no tesseract installation.
# Run: python scripts/table_extract.py
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import random

    failures: list[str] = []

    def check(label: str, condition: bool) -> None:
        status = "PASS" if condition else "FAIL"
        print(f"[{status}] {label}")
        if not condition:
            failures.append(label)

    def synth_words(table_rows, col_x, y0=30.0, pitch=24.0, char_w=7.0, space_w=6.0,
                    h=14, seed=None, y_jitter=0, x_jitter=0):
        rng = random.Random(seed)
        words = []
        for ri, row in enumerate(table_rows):
            base_y = y0 + ri * pitch
            if y_jitter:
                base_y += rng.randint(-y_jitter, y_jitter)
            for ci, cell in enumerate(row):
                cx = col_x[ci]
                if x_jitter:
                    cx += rng.randint(-x_jitter, x_jitter)
                for part in str(cell).split(" ") if cell != "" else []:
                    ww = max(4, int(round(char_w * len(part))))
                    words.append({"x0": cx, "y0": base_y, "x1": cx + ww,
                                  "y1": base_y + h, "text": part, "conf": 92.0})
                    cx += ww + space_w
        return words

    COLS = [40, 170, 300, 430, 560, 690]

    # --- Case 1: clean Alibra-style time-charter table --------------------
    alibra_rows = [
        ["Segment", "Route", "1Y TC", "4-6M TC", "Spot", "Change"],
        ["CAPE", "Atlantic", "28,500", "26,200", "31,400", "+4.2%"],
        ["CAPE", "Pacific", "27,100", "25,800", "30,900", "+3.1%"],
        ["PANAMAX", "Atlantic", "19,750", "18,400", "22,600", "+1.8%"],
        ["PANAMAX", "Far East", "18,900", "17,200", "21,300", "-0.4%"],
        ["SUPRAMAX", "Atlantic", "15,200", "14,100", "16,800", "+0.9%"],
        ["HANDYSIZE", "Worldwide", "12,800", "11,900", "13,700", "-1.2%"],
    ]
    words = synth_words(alibra_rows, COLS)
    rows = rows_from_words(words)
    check("alibra: 7 visual rows clustered", len(rows) == 7)
    check("alibra: rows sorted by x0",
          all(all(r[i]["x0"] <= r[i + 1]["x0"] for i in range(len(r) - 1)) for r in rows))

    bounds = columns_from_rows(rows)
    check(f"alibra: 6 columns detected (got {len(bounds)} boundaries)", len(bounds) == 6 - 1)

    grid = table_from_rows(rows)
    check("alibra: grid extracted", grid is not None)
    assert grid is not None
    check("alibra: grid shape 7x6", len(grid) == 7 and all(len(r) == 6 for r in grid))
    check("alibra: exact row round-trip",
          grid[1] == ["CAPE", "Atlantic", "28,500", "26,200", "31,400", "+4.2%"])
    check("alibra: comma preserved in '28,500'", "28,500" in grid[1])
    check("alibra: multi-word cell joined ('Far East')",
          grid[4][1] == "Far East")
    check("alibra: header row intact", grid[0] == ["Segment", "Route", "1Y TC", "4-6M TC", "Spot", "Change"])
    check("alibra: is_market_table True", is_market_table(grid))

    md = grid_to_markdown(grid)
    def md_rows(markdown):
        out = []
        for line in markdown.splitlines():
            s = line.strip()
            if not s.startswith("|"):
                continue
            inner = s.strip("|")
            if inner and set(inner.replace("|", "")) <= {"-"}:
                continue
            parts = re.split(r"(?<!\\)\|", inner)
            out.append([p.strip().replace("\\|", "|") for p in parts])
        return out
    check("markdown: round-trips all cells exactly", md_rows(md) == grid)
    check("markdown: separator present", "|---|" in md.splitlines()[1])

    # --- Case 2: skewed/noisy scan -----------------------------------------
    noisy_words = synth_words(alibra_rows, COLS, seed=1234, y_jitter=3, x_jitter=2)
    noise_y = 30 + len(alibra_rows) * 24 + 30
    noisy_words += [
        {"x0": 40, "y0": noise_y, "x1": 96, "y1": noise_y + 14, "text": "Source:", "conf": 88.0},
        {"x0": 260, "y0": noise_y + 55, "x1": 316, "y1": noise_y + 69, "text": "Alibra", "conf": 90.0},
        {"x0": 520, "y0": noise_y + 55, "x1": 600, "y1": noise_y + 69, "text": "weekly", "conf": 91.0},
    ]
    nrows = rows_from_words(noisy_words)
    ngrid = table_from_rows(nrows)
    check("noisy: still recovers a grid", ngrid is not None)
    check("noisy: >= 6 columns kept", ngrid is not None and max(len(r) for r in ngrid) >= 6)
    expected_row = ["CAPE", "Atlantic", "28,500", "26,200", "31,400", "+4.2%"]
    check("noisy: CAPE Atlantic row recovered exactly", ngrid is not None and expected_row in ngrid)
    check("noisy: is_market_table True despite caption noise",
          ngrid is not None and is_market_table(ngrid))

    # --- Case 3: pure prose must yield None ---------------------------------
    vocab = ["the", "charterer", "reported", "that", "tonnage", "listings", "grew",
             "steadily", "across", "basins", "while", "owners", "held", "firm"]
    prose = []
    y = 30
    k = 0
    for li in range(6):
        x = 40.0
        while x < 545:
            t = vocab[(li * 7 + k) % len(vocab)]
            k += 1
            ww = 7 * len(t)
            prose.append({"x0": x, "y0": y, "x1": x + ww, "y1": y + 14, "text": t, "conf": 95.0})
            x += ww + 5
        y += 24
    prows = rows_from_words(prose)
    check("prose: 6 text lines clustered", len(prows) == 6)
    pbounds = columns_from_rows(prows)
    check(f"prose: no persistent column gaps (got {len(pbounds)})", len(pbounds) <= 1)
    check("prose: table_from_rows returns None", table_from_rows(prows) is None)

    # --- Direct unit checks --------------------------------------------------
    check("rows_from_words([]) == []", rows_from_words([]) == [])
    check("columns_from_rows([]) == []", columns_from_rows([]) == [])
    two_bands = [
        {"x0": 10, "y0": 100, "x1": 30, "y1": 114, "text": "a", "conf": 99.0},
        {"x0": 50, "y0": 102, "x1": 70, "y1": 116, "text": "b", "conf": 99.0},
        {"x0": 12, "y0": 160, "x1": 32, "y1": 174, "text": "c", "conf": 99.0},
        {"x0": 52, "y0": 161, "x1": 72, "y1": 175, "text": "d", "conf": 99.0},
    ]
    tb = rows_from_words(two_bands)
    check("clustering: two bands -> two rows sorted by x0",
          [[w["text"] for w in r] for r in tb] == [["a", "b"], ["c", "d"]])

    check("is_market_table: too few rows", not is_market_table([["a", "b", "c"], ["1", "2", "3"]]))
    check("is_market_table: too few cols",
          not is_market_table([["a", "b"], ["c", "1"], ["d", "2"]]))
    prose_grid = [["hello", "world", "again"], ["alpha", "beta", "gamma"], ["delta", "epsilon", "zeta"]]
    check("is_market_table: prose grid False", not is_market_table(prose_grid))
    diluted = [
        ["Item", "Q1", "Q2"],
        ["Cape", "100", "110"],
        ["Pana", "90", "95"],
        ["Notes", "see", "below"],
        ["Summary", "covers all segments", "and regions"],
    ]
    body_cells = [c for row in diluted[1:] for c in map(str.strip, row) if c]
    frac = sum(1 for c in body_cells if NUMERIC_CELL_RE.match(c)) / len(body_cells)
    check(f"is_market_table: label-row rescue ({frac:.0%} numeric) True", is_market_table(diluted))

    pipe_grid = [["a|b", "c", "d"], ["e", "f", "g"], ["h", "i", "j"]]
    pmd = grid_to_markdown(pipe_grid)
    check("markdown: literal pipe escaped and restored",
          "a\\|b" in pmd and md_rows(pmd)[0][0] == "a|b")

    check("extract_table_text: unusable input -> None (never raises)",
          extract_table_text(object()) is None)
    try:
        import pytesseract  # noqa: F401
        has_pytesseract = True
    except Exception:
        has_pytesseract = False
    if not has_pytesseract:
        try:
            words_from_image(object())
            check("words_from_image raises RuntimeError without pytesseract", False)
        except RuntimeError:
            check("words_from_image raises RuntimeError without pytesseract", True)
    else:
        print("[SKIP] words_from_image RuntimeError check (pytesseract installed)")

    print()
    if failures:
        print(f"{len(failures)} FAILURE(S): {failures}")
        raise SystemExit(1)
    print("ALL SELF-TESTS PASSED")
