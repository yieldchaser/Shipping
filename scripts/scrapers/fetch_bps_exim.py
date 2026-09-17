#!/usr/bin/env python3
"""
fetch_bps_exim.py - Wrapper in scripts/scrapers/ pointing to scripts/acquire/fetch_bps_exim.py
"""
import sys
from pathlib import Path

ACQUIRE_SCRIPT = Path(__file__).resolve().parent.parent / "acquire" / "fetch_bps_exim.py"

if __name__ == "__main__":
    import runpy
    runpy.run_path(str(ACQUIRE_SCRIPT), run_name="__main__")
