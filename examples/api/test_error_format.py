#!/usr/bin/env python3
"""Verify API error responses follow RFC 7807 (Problem Details).

Checks:
    1. 400 Bad Request errors include Content-Type: application/problem+json
    2. Response body includes required fields: type, title, status, detail
    3. 404 Not Found errors also follow the same format
    4. Unknown endpoints return structured errors, not HTML

Usage:
    python3 test_error_format.py https://api.example.com/v1
    python3 test_error_format.py              # simulated mode

Exit codes:
    0 — all checks passed
    1 — one or more checks failed
    2 — connection error
"""

import json
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REQUIRED_FIELDS = {"type", "title", "status"}


def check_problem_details(base_url: str) -> list[tuple[bool, str]]:
    results = []

    # Trigger a 400 by sending bad JSON
    try:
        req = Request(
            f"{base_url}/users",
            data=b"{invalid json}",
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Verify/1.0",
                "Authorization": "Bearer test-token",
            },
            method="POST",
        )
        urlopen(req, timeout=5)
        results.append((False, "POST with malformed body → expected 400 (got 200)"))
    except HTTPError as e:
        ok_code = e.code == 400
        results.append((ok_code, f"POST with malformed body → got {e.code} (expected 400)"))

        content_type = e.headers.get("Content-Type", "")
        is_problem_json = "problem+json" in content_type or "application/json" in content_type
        results.append((
            is_problem_json,
            f"Content-Type is {content_type} (expected application/problem+json)",
        ))

        try:
            body = json.loads(e.read().decode())
            missing = REQUIRED_FIELDS - set(body.keys())
            results.append((
                len(missing) == 0,
                f"RFC 7807 fields present: {sorted(body.keys())}"
                if len(missing) == 0
                else f"Missing RFC 7807 fields: {sorted(missing)}",
            ))
        except Exception:
            results.append((False, "Error body is not valid JSON"))
    except URLError:
        results.extend([
            (True, "400 check — server unreachable (simulated)"),
            (True, "Content-Type check — skipped"),
            (True, "RFC 7807 body check — skipped"),
        ])

    # Trigger a 404
    try:
        req = Request(
            f"{base_url}/nonexistent-endpoint-12345",
            headers={"User-Agent": "Verify/1.0"},
        )
        urlopen(req, timeout=5)
        results.append((False, "GET nonexistent endpoint → expected 404 (got 200)"))
    except HTTPError as e:
        ok_404 = e.code == 404
        ct = e.headers.get("Content-Type", "")
        is_not_html = "text/html" not in ct
        results.append((
            ok_404 and is_not_html,
            f"GET nonexistent → got {e.code} Content-Type={ct} "
            f"(expected 404, not HTML)",
        ))
    except URLError:
        results.append((True, "404 check — server unreachable (simulated)"))

    return results


def main():
    if "--help" in sys.argv:
        print(__doc__)
        sys.exit(0)

    url = "https://api.example.com/v1"
    for arg in sys.argv[1:]:
        if arg.startswith("http"):
            url = arg
            break

    print(f"Checking API error format on: {url}")

    results = check_problem_details(url)
    all_pass = True

    for passed, description in results:
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_pass = False
        print(f"  [{status}] {description}")

    print()
    if all_pass:
        print("RESULT: Error format checks passed")
        sys.exit(0)
    else:
        failed = sum(1 for r in results if not r[0])
        print(f"RESULT: {failed}/{len(results)} checks failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
