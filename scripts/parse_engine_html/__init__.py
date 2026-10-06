"""Deterministic parser for the Hellenic Shipping News "Weekly Vessel Valuations Report" (VesselsValue).

Reads the archived HTML article (sector commentary + deal lines) and the "VV Mini Matrix - Weekly Change"
image (free local OCR) and writes staged Markdown + .tables.json + series CSVs under
.reparse_staging/vessel_valuations/.
"""

PARSER_NAME = "parse_engine_html.vv"
PARSER_VERSION = "1.0.0"
