#!/usr/bin/env python3
"""Check that a web page meets basic accessibility and content requirements.

Runs static analysis on an HTML page to detect common issues.
In production, use axe-core or Lighthouse for comprehensive audits.

Usage:
    python3 test_page_quality.py https://app.example.com/dashboard
    python3 test_page_quality.py --local page.html

Checks:
    1. Page has a <title> element
    2. Page has a <meta charset> declaration
    3. Page has a lang attribute on <html>
    4. Images have alt attributes
    5. No <font> or <center> tags (deprecated HTML)
    6. Color contrast is reasonable (no light-gray text on white)

Exit codes:
    0 — all checks passed
    1 — one or more issues found
"""

import re
import sys
from urllib.error import URLError
from urllib.request import Request, urlopen

SAMPLE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Dashboard — Verify App</title>
</head>
<body>
  <nav><a href="/">Home</a></nav>
  <main>
    <h1>Dashboard</h1>
    <img src="chart.png" alt="Revenue chart Q3 2026">
    <img src="spacer.gif">
    <p style="color:#999; background:#fff">Hard to read text</p>
  </main>
</body>
</html>"""


def check_page(html: str) -> list[tuple[bool, str, str]]:
    results = []

    results.append(("<title" in html.lower(), "Has <title> element", ""))
    results.append((
        'charset' in html.lower(),
        "Has <meta charset>",
        'Add <meta charset="utf-8"> to <head>' if 'charset' not in html.lower() else "",
    ))
    results.append((
        'lang=' in html[:500].lower(),
        "Has lang attribute on <html>",
        'Add lang="en" to <html> tag' if 'lang=' not in html[:500].lower() else "",
    ))

    # Count images without alt
    img_tags = re.findall(r'<img\b[^>]*>', html, re.IGNORECASE)
    missing_alt = sum(1 for t in img_tags if 'alt=' not in t.lower())
    results.append((
        missing_alt == 0,
        f"All {len(img_tags)} <img> have alt attributes",
        f"{missing_alt} image(s) missing alt text" if missing_alt > 0 else "",
    ))

    deprecated = bool(re.search(r'</?(font|center|marquee)\b', html, re.IGNORECASE))
    results.append((
        not deprecated,
        "No deprecated HTML tags (font, center, marquee)",
        "Found deprecated HTML tags" if deprecated else "",
    ))

    # Check for low-contrast color patterns (light gray on white)
    low_contrast = bool(re.search(
        r'color\s*:\s*#[a-fA-F0-9]{3,6}.*background\s*:\s*#[a-fA-F0-9]{3,6}',
        html, re.IGNORECASE,
    ))
    results.append((
        not low_contrast,  # we flag it for human review, not auto-fail
        "No obvious low-contrast patterns detected",
        "Inline color/background combos found — review for contrast" if low_contrast else "",
    ))

    return results


def main():
    if "--help" in sys.argv:
        print(__doc__)
        sys.exit(0)

    html = None
    if "--local" in sys.argv:
        idx = sys.argv.index("--local")
        with open(sys.argv[idx + 1]) as f:
            html = f.read()
        print(f"Loaded local file: {sys.argv[idx + 1]}")
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
        print("Using simulated page (no URL provided)")
        html = SAMPLE_HTML

    if not html:
        print("ERROR: No HTML content to check")
        sys.exit(2)

    results = check_page(html)
    all_pass = True

    for passed, description, advice in results:
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_pass = False
        line = f"  [{status}] {description}"
        if not passed and advice:
            line += f"  → {advice}"
        print(line)

    print()
    if all_pass:
        print("RESULT: Page passes all quality checks")
        sys.exit(0)
    else:
        failed_count = sum(1 for r in results if not r[0])
        print(f"RESULT: {failed_count}/{len(results)} checks failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
