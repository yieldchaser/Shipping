"""GMS commentary rows come from the issue MD: the editorial keeps its lead paragraph and the announcements after the
rankings table, the table itself stays out, and a country page ends at its sales block."""
from __future__ import annotations

import sys

from scripts.parse_engine.config import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts/extract/publishers"))
import gms_commentary_series as g  # noqa: E402

MD = """---
title: GMS Week 41 – GLUM & GLOOMY!
issue_date: '2022-10-14'
report_week: 41
source_file: corpus/02-hellenic/demolition/pdfs/gms/2022-10-14_gms-week-41.pdf
---

# Highlights

- Withdrawing.
- No sales.

# Market Commentary

## GLUM & GLOOMY!

Lead paragraph.

Second paragraph.

### GMS Market Rankings

| Demo Rank | Location |
|---|---|
| 1 | Bangladesh |

*Small LDT

GMS celebrates its 30th year.

# Bangladesh

## LISTLESS!

*Margin notes: Mostly quiet. | Tanker sale.*

Country text.

### Market Sales Reported

| Vessel Name | Type |
|---|---|
| VALARIS | Semi |

# Important Dates
"""


def test_issue_rows_from_md(tmp_path):
    p = tmp_path / "gms.md"
    p.write_text(MD, encoding="utf-8")
    rows = {r["section"]: r for r in g.issue_rows(p)}
    ed = rows["General / Editorial"]
    assert (ed["issue_date"], ed["report_week"], ed["headline"]) == ("2022-10-14", "41", "GLUM & GLOOMY!")
    assert ed["highlights"] == "Withdrawing. | No sales."
    assert ed["body_text"] == "Lead paragraph.\n\nSecond paragraph.\n\nGMS celebrates its 30th year."
    assert ed["source_file"] == "2022-10-14_gms-week-41.pdf"
    bd = rows["Bangladesh"]
    assert (bd["headline"], bd["highlights"], bd["body_text"]) == ("LISTLESS!", "Mostly quiet. | Tanker sale.", "Country text.")
    assert set(rows) == {"General / Editorial", "Bangladesh"}
