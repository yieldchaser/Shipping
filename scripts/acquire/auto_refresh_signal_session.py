#!/usr/bin/env python3
"""
scripts/acquire/auto_refresh_signal_session.py
=============================================
Automated Signal Ocean Headless Session Refresher (Playwright)

Authenticates headlessly into app.signalocean.com:
1. Navigates to https://app.signalocean.com/Account/Login.
2. Enters Email into #enterEmailFormEmail and clicks Continue.
3. On https://app.signalocean.com/Account/LoginStep2, enters Password,
   ensures 'Remember Me' is checked, and clicks 'Log In'.
4. Waits for successful authentication redirect into the main platform.
5. Extracts active ASP.NET session cookies (.AspNetCore.Identity.Application, ai_user, etc.).
6. Saves cookie string to .signal_session (gitignored).
7. Optionally triggers scripts/acquire/sync_live_fleet_pipeline.py immediately.

Credentials:
- Reads SIGNAL_EMAIL and SIGNAL_PASSWORD from environment variables or .env/.signal_credentials.
"""

import os
import sys
import time
import logging
from pathlib import Path
from playwright.sync_api import sync_playwright

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SESSION_FILE = REPO_ROOT / ".signal_session"
CREDS_FILE = REPO_ROOT / ".signal_credentials"
ENV_FILE = REPO_ROOT / ".env"

def load_credentials():
    email = os.environ.get("SIGNAL_EMAIL")
    password = os.environ.get("SIGNAL_PASSWORD")

    # Check .signal_credentials or .env
    for fpath in (CREDS_FILE, ENV_FILE):
        if (not email or not password) and fpath.exists():
            for line in fpath.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k == "SIGNAL_EMAIL" and not email:
                    email = v
                elif k == "SIGNAL_PASSWORD" and not password:
                    password = v

    return email, password

def refresh_session_headless(email: str, password: str, headless: bool = True) -> str:
    logging.info("Launching Playwright Chromium (headless=%s)...", headless)
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox"
            ]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            viewport={"width": 1440, "height": 900}
        )
        page = context.new_page()

        # Step 1: Login Landing
        logging.info("Navigating to Signal Ocean Login...")
        page.goto("https://app.signalocean.com/Account/Login", wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(2000)

        # Accept cookie banner if present
        try:
            page.locator("button:has-text('Accept')").click(timeout=3000)
        except Exception:
            pass

        logging.info("Submitting email for step 1...")
        page.fill("#enterEmailFormEmail", email)
        page.click("#enterEmailFormSubmit")
        page.wait_for_timeout(3000)

        # Step 2: Password Step
        if "LoginStep2" not in page.url and not page.locator("#password").count():
            logging.error("Did not reach LoginStep2. Current URL: %s", page.url)
            browser.close()
            raise RuntimeError(f"Unexpected login redirection: {page.url}")

        logging.info("Entering password on LoginStep2...")
        page.fill("#password", password)
        page.wait_for_timeout(500)

        logging.info("Submitting credentials (clicking Log In)...")
        page.click("button[type='submit']:has-text('Log In'), input[type='submit'][value='Log In']")
        
        # Wait for authentication redirect into app
        logging.info("Waiting for authentication handshake...")
        page.wait_for_timeout(5000)

        current_url = page.url
        logging.info("Post-login URL: %s", current_url)

        # Verify we are authenticated
        cookies = context.cookies()
        auth_cookie = next((c for c in cookies if c["name"] == ".AspNetCore.Identity.Application"), None)

        if not auth_cookie:
            logging.error("Authentication failed: .AspNetCore.Identity.Application cookie not found!")
            browser.close()
            raise RuntimeError("Login failed. Check email/password or account status.")

        logging.info("SUCCESS: Captured active .AspNetCore.Identity.Application session cookie!")

        # Format full cookie string
        cookie_parts = [f"{c['name']}={c['value']}" for c in cookies]
        cookie_string = "; ".join(cookie_parts)

        browser.close()
        return cookie_string

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Headlessly authenticate and refresh Signal Ocean session cookie.")
    parser.add_argument("--email", help="Signal Ocean account email.")
    parser.add_argument("--password", help="Signal Ocean account password.")
    parser.add_argument("--headed", action="store_true", help="Launch visible browser window for inspection/debugging.")
    parser.add_argument("--run-pipeline", action="store_true", help="Automatically trigger sync_live_fleet_pipeline.py after refreshing session.")
    args = parser.parse_args()

    email = args.email
    password = args.password

    if not email or not password:
        env_email, env_pass = load_credentials()
        email = email or env_email
        password = password or env_pass

    if not email or not password:
        print("\n" + "=" * 80)
        print("  SIGNAL OCEAN AUTOMATED HEADLESS SESSION REFRESHER")
        print("=" * 80)
        print("\nError: Missing Signal Ocean credentials.")
        print("\nPlease provide your credentials in one of two ways:")
        print("1. Command-line flags:")
        print("   python scripts/acquire/auto_refresh_signal_session.py --email \"you@domain.com\" --password \"yourpass\"")
        print("\n2. Store in local gitignored file (.env or .signal_credentials):")
        print("   SIGNAL_EMAIL=\"you@domain.com\"")
        print("   SIGNAL_PASSWORD=\"yourpass\"")
        print("=" * 80 + "\n")
        sys.exit(1)

    try:
        cookie_str = refresh_session_headless(email, password, headless=not args.headed)
        SESSION_FILE.write_text(cookie_str, encoding="utf-8")
        logging.info("Saved fresh session cookie to %s (%d chars).", SESSION_FILE.name, len(cookie_str))

        if args.run_pipeline:
            logging.info("Triggering sync_live_fleet_pipeline.py immediately...")
            import subprocess
            subprocess.run([sys.executable, str(REPO_ROOT / "scripts/acquire/sync_live_fleet_pipeline.py")], check=True)

        print("\n[OK] Headless session refresh completed successfully! Active cookie saved.\n")
    except Exception as ex:
        logging.error("Headless refresh failed: %s", ex)
        sys.exit(1)

if __name__ == "__main__":
    main()
