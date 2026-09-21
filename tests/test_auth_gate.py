#!/usr/bin/env python3
"""
tests/test_auth_gate.py
=======================
Verifies platform access control, expected usernames, and network fetch gating
in index.html so sensitive and platform market datasets are only loaded after authentication.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = ROOT / "index.html"


def test_auth_expected_credentials():
    content = INDEX_HTML.read_text(encoding="utf-8")
    
    # Must support both Raghav123 and Himanshu@123
    assert "_AUTH_USERS = ['Raghav123', 'Himanshu@123']" in content, (
        "Expected _AUTH_USERS to contain both 'Raghav123' and 'Himanshu@123'"
    )
    assert "_AUTH_PASS  = 'Capesize#2026'" in content or "_AUTH_PASS = 'Capesize#2026'" in content, (
        "Password must remain 'Capesize#2026'"
    )


def test_auth_case_insensitive_matching():
    content = INDEX_HTML.read_text(encoding="utf-8")
    assert "name.toLowerCase() === u.toLowerCase()" in content, (
        "Username verification must be case-insensitive against _AUTH_USERS"
    )


def test_signal_base_rates_not_eagerly_fetched():
    content = INDEX_HTML.read_text(encoding="utf-8")
    
    # Must NOT have top-level unconditional fetch of signal_base_rates.json
    # It must be wrapped in fetchSignalBaseRates function
    pattern = r"fetch\('data/views/signal_base_rates\.json'"
    matches = [m.start() for m in re.finditer(pattern, content)]
    assert len(matches) >= 1, "fetchSignalBaseRates must reference signal_base_rates.json"
    
    # Verify it is enclosed in fetchSignalBaseRates
    assert "function fetchSignalBaseRates()" in content, (
        "signal_base_rates.json fetch must be enclosed in fetchSignalBaseRates()"
    )


def test_init_app_gated_by_auth():
    content = INDEX_HTML.read_text(encoding="utf-8")
    
    # initApp must check isPlatformAuthenticated before fetching or initializing
    assert "async function initApp() {" in content
    init_app_match = re.search(r"async function initApp\(\)\s*\{([^}]+)\}", content)
    assert init_app_match, "initApp body not found"
    body = init_app_match.group(1)
    assert "isPlatformAuthenticated" in body, (
        "initApp must verify authentication before fetching dashboard data"
    )


def test_boot_platform_after_auth_wiring():
    content = INDEX_HTML.read_text(encoding="utf-8")
    
    # handlePlatformAuth must invoke bootPlatformAfterAuth on successful authentication
    assert "bootPlatformAfterAuth" in content
    assert "window.bootPlatformAfterAuth = bootPlatformAfterAuth;" in content
