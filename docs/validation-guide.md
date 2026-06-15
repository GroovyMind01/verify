# Validation Guide — Writing and Running Tests

## How test execution works

When Verify executes a test, it does three things:

1. Runs your command via `subprocess.run(shell=True, timeout=600)`
2. Captures **stdout + stderr** and stores the full output in the database
3. Writes the output to an **evidence file** with an SHA-256 checksum

The exit code determines pass/fail:

| Exit code | Status | Meaning |
|-----------|--------|---------|
| 0 | `passed` | Test succeeded |
| 1-127 | `failed` | Test failed |
| Timeout (>600s) | `error` | Test hung |
| Other crash | `error` | Subprocess error |

**Your script only needs to print output and `exit(0)` or `exit(1)`.** That's it. No evidence-collection code, no API calls, no SDK.

## Writing a test script

### Minimal Python test

```python
#!/usr/bin/env python3
"""Check that all pods are running in a namespace."""
import json
import subprocess
import sys

def main():
    result = subprocess.run(
        ["kubectl", "get", "pods", "-n", "production", "-o", "json"],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0:
        print("ERROR: cannot query cluster")
        print(result.stderr)
        sys.exit(1)

    pods = json.loads(result.stdout)
    not_running = [p["metadata"]["name"] for p in pods["items"]
                   if p["status"]["phase"] != "Running"]

    print(f"Total pods: {len(pods['items'])}")
    print(f"Not running: {len(not_running)}")

    if not_running:
        print("FAILED pods:")
        for name in not_running:
            print(f"  - {name}")
        sys.exit(1)

    print("All pods are running")
    sys.exit(0)

if __name__ == "__main__":
    main()
```

### Minimal bash test

```bash
#!/usr/bin/bash
set -euo pipefail

echo "Checking API health..."
status=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/health)
echo "HTTP status: $status"

if [ "$status" -eq 200 ]; then
    echo "API is healthy"
    exit 0
else
    echo "API is unhealthy"
    exit 1
fi
```

### Test script contract

| Requirement | Why |
|-------------|-----|
| Exit 0 = pass, non-zero = fail | Verify reads the exit code |
| Print diagnostics to stdout/stderr | Evidence is captured automatically |
| Should complete within 600 seconds | Tests time out after 10 minutes |
| Be self-contained (no external state) | Campaigns may run tests in any order |
| Use absolute paths or env vars | The working directory is the project root |

## Step-by-step: from script to evidence

### 1. Create the test definition

```bash
verify test create \
    --name "Pod Security Check" \
    --domain kubernetes \
    --description "Verify all pods run as non-root" \
    --tags "security,k8s" \
    --exec 'python3 /home/user/tests/test_pod_security.py'
```

The `--exec` command is stored in the database and becomes the default command for this test.

### 2. Map to a requirement

```bash
verify test map <test-id> K8S-001 --claim full
```

Coverage claims:
- `full` — this test completely verifies the requirement
- `partial` — this test covers part of the requirement (multiple tests needed)
- `indirect` — this test is related but doesn't directly verify

### 3. Run ad-hoc (development loop)

```bash
verify test exec <test-id>
```

Output:

```
✅  [PASSED]  Pod Security Check
    Exit code: 0
    ── output ──
    Total pods: 12
    All pods are running
    
    (full output saved as evidence — 'verify evidence list --test-run <uuid>')
```

Run as many times as needed — each execution creates a new test run. Fix your script, re-run immediately.

### 4. Override the command at runtime

```bash
# Run with a different environment
verify test exec <test-id> --exec 'python3 test_pod_security.py --env staging'

# Run an existing test run with override
verify test run <run-id> --exec 'python3 test_pod_security.py --env production'
```

The override does not change the stored command. It's a one-off.

### 5. Run as a campaign

```bash
verify campaign create "Q3 Security Audit"
verify campaign version <campaign-id> -t <test-a> -t <test-b> -t <test-c>
verify campaign run <version-id> --verbose
```

Campaign runs execute all pending test definitions in the version snapshot and record results.

## Interpreting results

### Per-test output

Use `--verbose` on campaign runs to see per-test output inline:

```bash
verify campaign run <version-id> --verbose
```

### Campaign summary

```bash
verify campaign status <version-id>
```

Shows total tests, pass/fail/error counts, and pass rate percentage.

### Evidence inspection

```bash
# List all evidence for a test run
verify evidence list --test-run <run-id>

# Read the full output (not truncated like the CLI display)
verify evidence preview <evidence-id>

# Verify the file hasn't been tampered with
verify evidence verify <evidence-id>
```

## Producing evidence from test scripts

Verify captures **stdout + stderr automatically** — but many tests produce richer artifacts: screenshots, HTML dumps, JSON reports, log files. Your test script creates these files, and you attach them with `verify evidence collect`.

### Evidence types at a glance

| Evidence type | How it's created | Collection method |
|---------------|-----------------|-------------------|
| stdout/stderr text | Print to stdout/stderr | **Automatic** — captured by Verify on every run |
| Screenshot (PNG/JPEG) | Script saves file to disk | `verify evidence collect <run-id> ./screen.png --type screenshot` |
| HTML page dump | Script fetches page, saves .html | `verify evidence collect <run-id> ./page.html --type html_dump` |
| JSON payload | Script writes structured data | `verify evidence collect <run-id> ./output.json --type json` |
| Log file | Script appends to a file | `verify evidence collect <run-id> ./test.log --type log` |
| PDF report | Script generates with a library | `verify evidence collect <run-id> ./report.pdf --type pdf` |

### General pattern

Every test script follows the same structure:

```
1. Run checks (assertions, comparisons, validations)
2. Print results to stdout (→ automatic evidence)
3. Save artifacts to a temporary directory (→ manual collect)
4. Print the artifact paths so the user knows what to collect
5. Exit with 0 (pass) or non-zero (fail)
```

### Web UI screenshots

For web UI validation, capture screenshots on failure so you can visually inspect what went wrong.

#### With Playwright (recommended)

Playwright is the most reliable choice for cross-browser screenshots:

```python
#!/usr/bin/env python3
"""Check login page renders correctly and capture a screenshot."""
import sys
from playwright.sync_api import sync_playwright

# This test script runs inside the Verify execution model.
# It captures screenshots, saves them to a temp dir, and
# prints the paths so the user can collect them as evidence.

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 720})
        page = context.new_page()

        artifacts_dir = "/tmp/verify-artifacts/login-test"
        import os
        os.makedirs(artifacts_dir, exist_ok=True)

        # Navigate and wait
        page.goto("https://example.com/login", wait_until="networkidle")
        page.screenshot(path=f"{artifacts_dir}/01-login-page-loaded.png")

        # Check the page title
        title = page.title()
        print(f"Page title: {title}")
        assert "Login" in title, f"Expected 'Login' in title, got '{title}'"

        # Check form elements exist
        username = page.locator("input[name='username']")
        password = page.locator("input[name='password']")
        submit = page.locator("button[type='submit']")

        print(f"Username field present: {username.is_visible()}")
        print(f"Password field present: {password.is_visible()}")
        print(f"Submit button present:  {submit.is_visible()}")

        # Try a failed login — screenshot for evidence
        username.fill("invalid_user")
        password.fill("invalid_pass")
        submit.click()
        page.wait_for_timeout(1000)  # wait for error message
        page.screenshot(path=f"{artifacts_dir}/02-failed-login-attempt.png")

        # Check for error message
        error = page.locator(".error-message")
        has_error = error.is_visible()
        print(f"Error message shown on bad credentials: {has_error}")

        # Print artifact paths for collection
        print(f"\nARTIFACTS: {artifacts_dir}")
        print(f"  Screenshot 1: {artifacts_dir}/01-login-page-loaded.png")
        print(f"  Screenshot 2: {artifacts_dir}/02-failed-login-attempt.png")

        browser.close()

        if not has_error:
            print("FAIL: no error message displayed on bad credentials")
            sys.exit(1)

        print("Login page validation PASSED")
        sys.exit(0)

if __name__ == "__main__":
    main()
```

After the test runs, collect the screenshots:

```bash
verify test exec <test-id>
# Output shows "ARTIFACTS: /tmp/verify-artifacts/login-test"
# Get the test run ID from the output
verify evidence list --test-run <run-id>
# Find the run ID in the output
verify evidence collect <run-id> /tmp/verify-artifacts/login-test/01-login-page-loaded.png --type screenshot
verify evidence collect <run-id> /tmp/verify-artifacts/login-test/02-failed-login-attempt.png --type screenshot
```

#### With Selenium

```python
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

options = Options()
options.add_argument("--headless=new")
options.add_argument("--no-sandbox")
driver = webdriver.Chrome(options=options)

driver.get("https://example.com/login")
driver.save_screenshot("/tmp/verify-artifacts/login-selenium.png")
print(f"Screenshot saved to /tmp/verify-artifacts/login-selenium.png")

# ... assertions ...

driver.quit()
```

#### With Puppeteer (Node.js)

```javascript
const puppeteer = require('puppeteer');
(async () => {
    const browser = await puppeteer.launch({ headless: 'new' });
    const page = await browser.newPage();
    await page.setViewport({ width: 1280, height: 720 });
    await page.goto('https://example.com/login', { waitUntil: 'networkidle0' });
    await page.screenshot({ path: '/tmp/verify-artifacts/login-puppeteer.png', fullPage: true });
    console.log('Screenshot saved');
    const title = await page.title();
    console.log(`Title: ${title}`);
    await browser.close();
    process.exit(title.includes('Login') ? 0 : 1);
})();
```

#### With a simple HTTP call and HTML dump (no browser)

For lightweight checks that don't need a real browser, capture the raw HTML:

```python
#!/usr/bin/env python3
"""Check login page structure without a browser."""
import sys
import os
from urllib.request import urlopen

def main():
    artifacts_dir = "/tmp/verify-artifacts/login-html"
    os.makedirs(artifacts_dir, exist_ok=True)

    response = urlopen("https://example.com/login")
    html = response.read().decode("utf-8")
    status = response.status

    # Save the HTML for manual inspection
    with open(f"{artifacts_dir}/login-page.html", "w") as f:
        f.write(html)

    # Basic checks on the raw HTML
    checks = {
        "login form present": 'input type="password"' in html,
        "has CSRF token": 'csrf' in html or 'CSRF' in html,
        "has submit button": 'type="submit"' in html,
        "HTTPS response": status == 200,
    }

    for name, result in checks.items():
        status_str = "PASS" if result else "FAIL"
        print(f"  [{status_str}] {name}")

    print(f"\nHTML saved to: {artifacts_dir}/login-page.html")

    failures = [n for n, r in checks.items() if not r]
    sys.exit(1 if failures else 0)

if __name__ == "__main__":
    main()
```

### JSON / structured evidence

For API validation, output structured data that can be parsed later:

```python
#!/usr/bin/env python3
"""Validate API responses and produce JSON evidence."""
import json, sys, os
from urllib.request import urlopen, Request

def main():
    artifacts_dir = "/tmp/verify-artifacts/api-test"
    os.makedirs(artifacts_dir, exist_ok=True)

    req = Request("https://api.example.com/v1/users", method="GET")
    req.add_header("Accept", "application/json")

    results = {"endpoint": "/v1/users", "checks": [], "passed": 0, "failed": 0}

    try:
        resp = urlopen(req, timeout=10)
        data = json.loads(resp.read().decode("utf-8"))
        results["status_code"] = resp.status

        checks = [
            ("returns list", isinstance(data, list)),
            ("non-empty", len(data) > 0),
            ("each user has id", all("id" in u for u in data)),
            ("each user has email", all("email" in u for u in data)),
        ]

        for name, ok in checks:
            results["checks"].append({"name": name, "passed": ok})
            if ok:
                results["passed"] += 1
                print(f"  [PASS] {name}")
            else:
                results["failed"] += 1
                print(f"  [FAIL] {name}")

        # Save structured evidence
        with open(f"{artifacts_dir}/api-results.json", "w") as f:
            json.dump(results, f, indent=2)

        print(f"\nJSON evidence: {artifacts_dir}/api-results.json")
        sys.exit(1 if results["failed"] else 0)

    except Exception as e:
        print(f"ERROR: {e}")
        results["error"] = str(e)
        with open(f"{artifacts_dir}/api-results.json", "w") as f:
            json.dump(results, f, indent=2)
        sys.exit(1)

if __name__ == "__main__":
    main()
```

Collect:

```bash
verify evidence collect <run-id> /tmp/verify-artifacts/api-test/api-results.json --type json
```

### Log file evidence

For long-running or multi-step tests, write to a log file and collect it:

```python
import logging, sys, os

artifacts_dir = "/tmp/verify-artifacts/log-test"
os.makedirs(artifacts_dir, exist_ok=True)

logging.basicConfig(
    filename=f"{artifacts_dir}/test-output.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

logging.info("Starting validation...")
logging.info("Step 1: check connectivity")
# ... steps ...
logging.info("Step 2: verify data")
# ... more steps ...
logging.info("Validation complete")

# Print for automatic evidence capture too
with open(f"{artifacts_dir}/test-output.log") as f:
    print(f.read())

sys.exit(0)
```

### Automating the collect step

Rather than typing `verify evidence collect` commands by hand, wrap everything in a small script:

```bash
#!/usr/bin/bash
# run-test.sh — runs a test and collects all evidence

TEST_ID="$1"
RUNDIR="/tmp/verify-artifacts/$(date +%s)"
mkdir -p "$RUNDIR"

# Run the test
verify test exec "$TEST_ID" 2>&1 | tee "$RUNDIR/run-output.txt"

# Extract the test run ID from the output
RUN_ID=$(grep -oP 'test-run \K[0-9a-f-]{36}' "$RUNDIR/run-output.txt" | head -1)

if [ -n "$RUN_ID" ] && [ -d "$RUNDIR/artifacts" ]; then
    for f in "$RUNDIR/artifacts"/*; do
        verify evidence collect "$RUN_ID" "$f" --type artifact
    done
fi
```

## Iterative workflows

### Fix and re-run failures

```bash
# After fixing bugs in your script, create a re-run version
verify campaign rerun <campaign-id> <previous-version-id>
verify campaign run <new-version-id>
```

This creates a new version containing only the tests that failed in the previous run.

### Compare results between versions

```bash
verify campaign compare <version-1> <version-2>
```

Shows:
- Tests whose status changed (e.g., `failed` → `passed`)
- Tests only in version A
- Tests only in version B

Useful for regression detection.

## Collecting additional evidence

Some tests produce files beyond stdout. Attach them manually:

```bash
verify evidence collect <test-run-id> ./screenshot.png --type screenshot
verify evidence collect <test-run-id> /var/log/test-output.json --type "test output"
```

Optionally attach JSON metadata:

```bash
verify evidence collect <run-id> ./report.pdf --type pdf --meta '{"page_count":5,"generated_by":"puppeteer"}'
```

## GPG signing

For audit requirements, sign evidence files:

```bash
verify evidence sign <evidence-id> --key <key-id>
```

## Tips for reliable test scripts

- **Be idempotent** — running the same test twice should give the same result
- **Report intermediate values** — print what you're checking; it makes debugging failures easier
- **Fail fast with clear messages** — print what condition failed and what the actual value was
- **Handle timeouts gracefully** — set internal timeouts shorter than Verify's 600s limit
- **Clean up resources** — don't leave behind temp files, port bindings, or processes
- **Use `set -euo pipefail` in bash** — catches errors early
- **Check prerequisites** — print a clear error if `kubectl`, `curl`, or other tools are missing

### Example: good failure output

```
Checking pod security context for namespace "production"...
  pod web-1: securityContext.runAsNonRoot = true       OK
  pod web-2: securityContext.runAsNonRoot = false      FAIL
  pod web-3: securityContext.runAsNonRoot = true       OK

FAILED: pod web-2 does not set runAsNonRoot=true
  kubectl get pod web-2 -n production -o jsonpath='{.spec.securityContext}'
```

This output makes it obvious what failed, where, and what to fix.

## Real examples

Check the `examples/` directory for complete, working test scripts:

| Script | Domain | What it checks |
|--------|--------|----------------|
| `examples/kubernetes/test_pod_security.py` | Kubernetes | Pod security contexts, privileged mode |
| `examples/kubernetes/test_resource_limits.py` | Kubernetes | CPU/memory limits on containers |
| `examples/kubernetes/test_network_policy.py` | Kubernetes | NetworkPolicy existence |
| `examples/webui/test_login_page.py` | Web UI | Login form elements and accessibility |
| `examples/webui/test_page_quality.py` | Web UI | Page title, description, HTTPS |
| `examples/api/test_auth.py` | API | Authentication endpoint behavior |
| `examples/api/test_error_format.py` | API | Error response format compliance |

Run them with:

```bash
verify test exec <test-id>
```

They use only stdlib and require no special infrastructure.
