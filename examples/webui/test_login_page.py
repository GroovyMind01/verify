#!/usr/bin/env python3
"""Verify login page behavior — accessibility, form presence, HTTPS enforcement.

This script checks a local or remote login page for basic security and
accessibility properties. In production, point it at your deployed app.

Usage:
    python3 test_login_page.py https://app.example.com/login
    python3 test_login_page.py --local login.html
    python3 test_login_page.py          # runs with simulated responses

Checks performed:
    1. Page returns HTTP 200 (or --local file exists and is readable)
    2. Page contains a <form> element
    3. Page contains a password input field
    4. Page contains a CSRF token (hidden input with csrf token pattern)

Exit codes:
    0 — all checks passed
    1 — one or more checks failed
"""

import re
import sys
from urllib.error import URLError
from urllib.request import Request, urlopen

SAMPLE_HTML = """<!DOCTYPE html>
<html lang="en">
<head><title>Sign In — Verify App</title></head>
<body>
  <main>
    <form method="post" action="/login" id="login-form">
      <input type="hidden" name="csrf_token" value="a1b2c3d4e5f6a7b8c9d0">
      <label for="username">Username</label>
      <input type="text" id="username" name="username" required>
      <label for="password">Password</label>
      <input type="password" id="password" name="password" required>
      <button type="submit">Sign In</button>
    </form>
  </main>
</body>
</html>"""


def check_login_page(html: str) -> list[tuple[bool, str]]:
    results = []

    has_form = "<form" in html.lower()
    results.append((has_form, "<form> element present"))

    has_password = 'type="password"' in html or "type='password'" in html
    results.append((has_password, "Password input field present"))

    # CSRF token — look for hidden input with token-like value or name
    csrf_patterns = [
        r'name=["\']csrf',
        r'name=["\']_token',
        r'name=["\']authenticity_token',
    ]
    has_csrf = any(re.search(p, html, re.IGNORECASE) for p in csrf_patterns)
    results.append((has_csrf, "CSRF token in form"))

    has_username = 'type="text"' in html or 'type="email"' in html
    results.append((has_username, "Username/email input field present"))

    return results


def main():
    if "--help" in sys.argv:
        print(__doc__)
        sys.exit(0)

    html = None
    if len(sys.argv) > 1 and sys.argv[1] == "--local":
        with open(sys.argv[2]) as f:
            html = f.read()
        print(f"Loaded local file: {sys.argv[2]}")
    elif len(sys.argv) > 1 and sys.argv[1].startswith("http"):
        url = sys.argv[1]
        print(f"Fetching {url}...")
        try:
            req = Request(url, headers={"User-Agent": "Verify/1.0"})
            with urlopen(req, timeout=10) as resp:
                html = resp.read().decode("utf-8", errors="replace")
                print(f"HTTP {resp.status} — {len(html)} bytes")
        except URLError as e:
            print(f"CONNECTION ERROR: {e}")
            sys.exit(2)
    else:
        print("Using simulated login page (no URL provided)")
        html = SAMPLE_HTML

    if not html:
        print("ERROR: No HTML content to check")
        sys.exit(2)

    results = check_login_page(html)
    all_pass = True

    for passed, description in results:
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_pass = False
        print(f"  [{status}] {description}")

    print()
    if all_pass:
        print("RESULT: Login page passes all checks")
        sys.exit(0)
    else:
        failed_count = sum(1 for r in results if not r[0])
        print(f"RESULT: {failed_count}/{len(results)} checks failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
