# Verify Examples

End-to-end validation workflows for three domains: **Kubernetes**, **Web UI**, and **API**.

Each example follows the full Verify lifecycle: import requirements → define tests → map coverage → run a campaign → execute tests → collect evidence → report.

Prerequisite: `verify` is installed and on your PATH (see [README.md](../README.md)).

## Quick start — run all examples

```bash
python3 examples/run_all.py
```

This script:
1. Imports 24 requirements across 3 domains
2. Creates 7 executable test definitions (each with a real Python test script)
3. Maps 12 requirement→test coverage links
4. Creates a campaign and version
5. **Executes all 7 test scripts** — real subprocess calls, exit codes determine pass/fail
6. Collects stdout/stderr as evidence automatically
7. Prints coverage report and campaign summary (3 passed, 4 failed, 42.9% pass rate)

The database is at `/tmp/verify-example.db`. Inspect with:

```bash
verify --db-path /tmp/verify-example.db campaign report <version-id>
verify --db-path /tmp/verify-example.db evidence list --campaign-version <version-id>
```

## Test scripts

Each domain has standalone Python test scripts in `examples/<domain>/`. They run without external dependencies (stdlib only) and produce descriptive output. In production, replace the simulated data with real API calls, `kubectl` queries, or Selenium screenshots.

### Kubernetes tests

| Script | What it checks | Exit 0 = |
|--------|---------------|----------|
| `test_pod_security.py` | Every pod has `securityContext.runAsNonRoot=True` | All pods compliant |
| `test_resource_limits.py` | Every container has CPU and memory `limits` defined | All containers have limits |
| `test_network_policy.py` | Every namespace has a NetworkPolicy | All namespaces protected |

**How they work:**

- `test_pod_security.py` — scans a pod manifest (simulated or from `--data pods.json`). Checks each pod's `securityContext` for `runAsNonRoot`. Prints per-pod PASS/FAIL. Exits 1 if any pod runs as root.

- `test_resource_limits.py` — iterates over pod containers. Checks that `limits.cpu` and `limits.memory` are present. Reports missing fields per container. Exits 1 if any container lacks limits.

- `test_network_policy.py` — maps namespaces to NetworkPolicies. Flags any namespace without a policy. Exits 1 if gaps exist.

**Sample output (pod_security):**
```
Scanning 5 pods for runAsNonRoot compliance...
  [PASS] default/nginx-7b5d8f4c9-abc12
  [FAIL] default/redis-5c7d9b6f3-def34
  [PASS] production/api-gateway-5d8c6b7a2-ghi56
  [FAIL] dev/debug-shell
  [PASS] monitoring/monitoring-agent-3f9a2b1c

RESULT: 2/5 pods violate runAsNonRoot policy
```

**Integrating real data:**
```bash
# Pipe live kubectl output into the test
kubectl get pods -A -o json | python3 test_pod_security.py --stdin

# Or use static data
python3 test_pod_security.py --data production-pods.json
```

### WebUI tests

| Script | What it checks | Exit 0 = |
|--------|---------------|----------|
| `test_login_page.py` | Login page has `<form>`, password field, CSRF token, username field | All elements present |
| `test_page_quality.py` | Page has `<title>`, `<meta charset>`, `lang`, `alt` on images, no deprecated tags, no low-contrast patterns | All checks pass |

**How they work:**

- `test_login_page.py` — fetches the login page (or uses simulated HTML). Checks for `<form>`, `type="password"`, CSRF token hidden inputs, and username/email fields. Can target a real URL: `python3 test_login_page.py https://staging.example.com/login`.

- `test_page_quality.py` — static analysis on HTML. Checks for `<title>`, `<meta charset>`, `lang` attribute, `alt` on all `<img>` tags, deprecated tags (`<font>`, `<center>`), and inline color/background combos that may indicate poor contrast. Can target a real URL or local file.

**Sample output (page_quality):**
```
Using simulated page (no URL provided)
  [PASS] Has <title> element
  [PASS] Has <meta charset>
  [PASS] Has lang attribute on <html>
  [FAIL] All 2 <img> have alt attributes  → 1 image(s) missing alt text
  [PASS] No deprecated HTML tags (font, center, marquee)
  [FAIL] No obvious low-contrast patterns detected  → Inline color/background combos found — review for contrast

RESULT: 2/6 checks failed
```

### API tests

| Script | What it checks | Exit 0 = |
|--------|---------------|----------|
| `test_auth.py` | Endpoints return 401 without token, 401 with invalid token, and error responses are machine-readable | All auth checks pass |
| `test_error_format.py` | 400 responses follow RFC 7807 (Content-Type, type/title/status/detail fields), 404 responses are not HTML | Error format is compliant |

**How they work:**

- `test_auth.py` — sends requests without an `Authorization` header, with an invalid Bearer token. Expects HTTP 401 for both. Checks that the error response body is valid JSON with a recognizable error field. Connects to real URLs when provided; falls back to simulated checks (marked "server unreachable") for offline use.

- `test_error_format.py` — triggers a 400 by sending malformed JSON in a POST. Checks `Content-Type: application/problem+json`. Validates RFC 7807 required fields (`type`, `title`, `status`). Also triggers a 404 and verifies it's not HTML. Falls back to simulated checks offline.

**Sample output (error_format):**
```
Checking API error format on: https://api.example.com/v1
  [PASS] POST with malformed body → server unreachable (simulated)
  [PASS] Content-Type check — skipped
  [PASS] RFC 7807 body check — skipped
  [PASS] GET nonexistent → got 404 Content-Type=application/problem+json (expected 404, not HTML)

RESULT: Error format checks passed
```

---

## Running tests via Verify CLI

Once test definitions have `exec_command` set, you can run them through Verify:

```bash
# Run a single test run (executes the script, captures output as evidence)
verify test run <test-run-id>

# Run ALL pending test runs in a campaign version
verify campaign run <version-id>
```

After execution:
- Test run status is set automatically: exit 0 → `passed`, non-zero → `failed`, timeout → `error`
- stdout/stderr is captured as evidence (type: `command_output`)
- SHA-256 checksums are computed for all evidence files
- Evidence is stored in `<VERIFY_HOME>/evidence/<test-run-id>/`

## Writing your own executable test

1. **Create a test script** — any executable (Python, bash, compiled binary). It must:
   - Print meaningful output to stdout/stderr
   - Exit with code 0 for success, non-zero for failure

2. **Register it in Verify:**
   ```bash
   verify test create --name "My Check" --domain security \
     --exec 'python3 /path/to/my_check.py --flag value'
   ```

3. **Run it:**
   ```bash
   verify test run <test-run-id>
   # or as part of a campaign:
   verify campaign run <version-id>
   ```

**Minimal working example:**

```python
#!/usr/bin/env python3
"""check_port.py — verify a TCP port is open."""
import socket, sys

host, port = sys.argv[1], int(sys.argv[2])
s = socket.socket()
s.settimeout(5)
try:
    s.connect((host, port))
    print(f"Port {port} is OPEN on {host}")
    sys.exit(0)
except Exception as e:
    print(f"Port {port} is CLOSED: {e}")
    sys.exit(1)
```

```bash
verify test create --name "Port Check" --exec 'python3 check_port.py api-server 443'
verify test run <test-run-id>
```

---

## Files

```
examples/
├── README.md                          # This file
├── run_all.py                         # Full workflow demo (runs all tests)
├── kubernetes-requirements.csv        # 8 Kubernetes requirements
├── webui-requirements.csv             # 7 Web UI requirements
├── api-requirements.csv               # 9 API requirements
├── kubernetes/
│   ├── test_pod_security.py           # Check runAsNonRoot
│   ├── test_resource_limits.py        # Check CPU/memory limits
│   └── test_network_policy.py         # Check NetworkPolicy coverage
├── webui/
│   ├── test_login_page.py             # Check login form structure
│   └── test_page_quality.py           # Check HTML quality / a11y
└── api/
    ├── test_auth.py                   # Check auth rejection
    └── test_error_format.py           # Check RFC 7807 compliance
```
