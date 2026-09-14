"""CSV writers must write LF line endings on every platform.

pandas .to_csv() uses os.linesep (CRLF on Windows) and csv.writer defaults to CRLF
everywhere. Data files are stored LF (.gitattributes), so a CRLF write made any
local run show every row of files such as data/derived/vessel_valuations.csv as
changed and blocked pulls and rebases. Every writer passes lineterminator="\\n".
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _calls(src, opener):
    for m in re.finditer(re.escape(opener), src):
        depth, j = 1, m.end()
        while j < len(src) and depth:
            depth += {"(": 1, ")": -1}.get(src[j], 0)
            j += 1
        yield src[m.end():j - 1], src[:m.start()].count("\n") + 1


def test_every_csv_writer_sets_lf():
    offenders = []
    for path in sorted((ROOT / "scripts").rglob("*.py")):
        src = path.read_text(encoding="utf-8", errors="replace")
        for opener in (".to_csv(", "csv.writer(", "csv.DictWriter("):
            for args, line in _calls(src, opener):
                first = args.split(",")[0].strip()
                if opener == ".to_csv(" and (first in ("", "None") or "StringIO" in first or first.startswith(("buf", "sio", "io."))):
                    continue
                if "lineterminator" not in args:
                    offenders.append(f"{path.relative_to(ROOT)}:{line} {opener}{args[:60]}")
    assert not offenders, "CSV writers without lineterminator='\\n':\n" + "\n".join(offenders)
