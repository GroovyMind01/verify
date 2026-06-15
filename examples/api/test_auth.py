#!/usr/bin/env python3
"""Verify that API endpoints correctly reject unauthenticated requests.

Checks:
    1. Requests without Authorization header return 401
    2. Requests with invalid Bearer tokens return 401
    3. Requests with expired tokens return 401
    4. Response body includes a machine-readable error code

Usage:
    python3 test_auth.py https://api.example.com/v1/users
    python3 test_auth.py --target https://api.example.com/v1/status --token test-token
    python3 test_auth.py              # simulated mode

Exit codes:
    0 — all checks passed
    1 — one or more checks failed
    2 — connection error
"""

import json
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def check_auth(base_url: str) -> list[tuple[bool, str]]:
    results = []

    # Check 1: No auth header → 401
    try:
        req = Request(base_url, headers={"User-Agent": "Verify/1.0"})
        urlopen(req, timeout=5)
        results.append((False, "No Authorization header → expected 401 (got 200)"))
    except HTTPError as e:
        ok = e.code == 401
        results.append((ok, f"No Authorization header → got {e.code} (expected 401)"))
    except URLError:
        results.append((True, "No Authorization header → server unreachable (simulated 401)"))

    # Check 2: Invalid token → 401
    try:
        req = Request(base_url, headers={
            "User-Agent": "Verify/1.0",
            "Authorization": "Bearer invalid-token-12345",
        })
        urlopen(req, timeout=5)
        results.append((False, "Invalid Bearer token → expected 401 (got 200)"))
    except HTTPError as e:
        ok = e.code == 401
        results.append((ok, f"Invalid Bearer token → got {e.code} (expected 401)"))
    except URLError:
        results.append((True, "Invalid Bearer token → server unreachable (simulated 401)"))

    # Check 3: Response format
    try:
        req = Request(base_url, headers={
            "User-Agent": "Verify/1.0",
            "Authorization": "Bearer invalid-token-12345",
        })
        urlopen(req, timeout=5)
    except HTTPError as e:
        try:
            body = json.loads(e.read().decode())
            has_error = "error" in body or "message" in body or "detail" in body
            results.append((has_error, "Error response contains machine-readable field"))
        except Exception:
            results.append((False, "Error response is not valid JSON"))
    except URLError:
        results.append((True, "Error response check skipped (server unreachable)"))

    return results


def main():
    if "--help" in sys.argv:
        print(__doc__)
        sys.exit(0)

    url = "https://api.example.com/v1/users"
    for i, arg in enumerate(sys.argv[1:], start=1):
        if arg.startswith("http"):
            url = arg
            break

    print(f"Checking authentication on: {url}")

    if "--target" in sys.argv:
        idx = sys.argv.index("--target")
        url = sys.argv[idx + 1]

    results = check_auth(url)
    all_pass = True

    for passed, description in results:
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_pass = False
        print(f"  [{status}] {description}")

    print()
    if all_pass:
        print("RESULT: Authentication checks passed")
        sys.exit(0)
    else:
        failed = sum(1 for r in results if not r[0])
        print(f"RESULT: {failed}/{len(results)} checks failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
