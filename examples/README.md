# Verify Examples

End-to-end validation workflows for three domains: **Kubernetes**, **Web UI**, and **API**.

Each example follows the full Verify lifecycle: import requirements → define tests → map coverage → run a campaign → collect evidence → report.

Prerequisite: `verify` is installed and on your PATH (see [README.md](../README.md)).

---

## 1. Kubernetes Compliance

### 1.1 Import requirements

```bash
verify --db-path /tmp/k8s-validate.db req import examples/kubernetes-requirements.csv
```
```
Imported 8 requirement(s)
  K8S-001 — Pod must run as non-root
  K8S-002 — No privileged containers
  K8S-003 — Resource limits required
  K8S-004 — Read-only root filesystem
  K8S-005 — NetworkPolicy enforced
  K8S-006 — Liveness probe present
  K8S-007 — Image from trusted registry
  K8S-008 — No hostPath volumes
```

### 1.2 Create test definitions

Test definitions are created via the service API. For interactive use, the Python API is the entry point:

```python
from verify.shared.database import get_session_factory, init_db
from verify.definitions.service import DefinitionServiceImpl
from verify.requirements.service import RequirementServiceImpl

import os
os.environ["VERIFY_DB_PATH"] = "/tmp/k8s-validate.db"
init_db()

sf = get_session_factory()
defs = DefinitionServiceImpl(sf)
reqs = RequirementServiceImpl(sf)

# Create test definitions
t1 = defs.create(
    name="Run Kyverno policy scan",
    description="Scan all namespaces with Kyverno CLI and check for violations",
    steps=[
        "kyverno apply policies/ --cluster",
        "Parse results for violations of security policies",
    ],
    domain="kubernetes",
    tags=["automated", "admission"],
)

t2 = defs.create(
    name="Check pod security contexts",
    description="Inspect securityContext of every running pod",
    steps=[
        "kubectl get pods -A -o json | jq '.items[].spec.containers[].securityContext'",
        "Verify runAsNonRoot is true or unset",
        "Verify privileged is not true",
    ],
    domain="kubernetes",
    tags=["manual", "security"],
)

t3 = defs.create(
    name="Verify resource quotas",
    description="Check that every namespace has resource quotas and every pod has limits",
    steps=[
        "kubectl get resourcequota -A",
        "kubectl get pods -A -o json | jq '.items[] | select(.spec.containers[].resources.limits == null)'",
    ],
    domain="kubernetes",
    tags=["automated"],
)

t4 = defs.create(
    name="Audit network policies",
    description="Verify default-deny NetworkPolicy exists in every namespace",
    steps=[
        "kubectl get netpol -A",
        "Check each namespace has at least one deny-all policy",
    ],
    domain="kubernetes",
    tags=["automated", "networking"],
)

t5 = defs.create(
    name="Verify image registries",
    description="Check all running images come from allowed registries",
    steps=[
        "kubectl get pods -A -o json | jq -r '.items[].spec.containers[].image' | cut -d/ -f1 | sort -u",
        "Verify all registries match allowed list",
    ],
    domain="kubernetes",
    tags=["automated", "supply-chain"],
)
```

### 1.3 Map tests to requirements

```python
defs.map_to_requirement(t1.id, reqs.get_by_key("K8S-001").id, coverage_claim="full")
defs.map_to_requirement(t1.id, reqs.get_by_key("K8S-002").id, coverage_claim="full")
defs.map_to_requirement(t2.id, reqs.get_by_key("K8S-001").id, coverage_claim="full")
defs.map_to_requirement(t2.id, reqs.get_by_key("K8S-002").id, coverage_claim="full")
defs.map_to_requirement(t3.id, reqs.get_by_key("K8S-003").id, coverage_claim="full")
defs.map_to_requirement(t3.id, reqs.get_by_key("K8S-006").id, coverage_claim="partial")
defs.map_to_requirement(t4.id, reqs.get_by_key("K8S-005").id, coverage_claim="full")
defs.map_to_requirement(t5.id, reqs.get_by_key("K8S-007").id, coverage_claim="full")
```

### 1.4 Run a campaign

```bash
# Create campaign
verify --db-path /tmp/k8s-validate.db campaign create "Q3 Kubernetes Audit" \
  --description "Security posture audit across staging and production"

# Create version with all 5 test definitions (replace IDs from step 1.2)
verify --db-path /tmp/k8s-validate.db campaign version <campaign-id> \
  -t <t1-id> -t <t2-id> -t <t3-id> -t <t4-id> -t <t5-id> \
  --notes "Initial staging scan"
```

### 1.5 Collect evidence and report

```bash
# For each test run, update status and attach evidence
# (test-run-ids are listed by campaign status)

# Collect Kyverno scan output
kyverno apply policies/ --cluster > /tmp/kyverno-results.json
verify --db-path /tmp/k8s-validate.db evidence collect <test-run-id> \
  /tmp/kyverno-results.json --type policy_scan

# Update test run status (via API)
```

```python
from verify.campaigns.service import CampaignServiceImpl
cs = CampaignServiceImpl(sf)

# Set test run results
cs.update_test_run_status("<test-run-1-id>", "passed", "All policies compliant")
cs.update_test_run_status("<test-run-2-id>", "passed")
cs.update_test_run_status("<test-run-3-id>", "failed", "3 deployments missing resource limits in dev namespace")
cs.update_test_run_status("<test-run-4-id>", "passed")
cs.update_test_run_status("<test-run-5-id>", "failed", "Image nginx:latest from Docker Hub found in default namespace")
```

### 1.6 Generate report

```bash
verify --db-path /tmp/k8s-validate.db campaign report <version-id>
verify --db-path /tmp/k8s-validate.db campaign report <version-id> --format json -o k8s-report.json

# Check coverage
verify --db-path /tmp/k8s-validate.db req coverage K8S-001
verify --db-path /tmp/k8s-validate.db req coverage K8S-007
```

---

## 2. Web UI Testing

### 2.1 Import requirements

```bash
verify --db-path /tmp/ui-validate.db req import examples/webui-requirements.csv
```
```
Imported 7 requirement(s)
  UI-001 — Login page accessible
  UI-002 — Form validation feedback
  UI-003 — Responsive layout
  UI-004 — Keyboard navigation
  UI-005 — Color contrast minimum
  UI-006 — Session timeout warning
  UI-007 — CSRF token on forms
```

### 2.2 Define tests

```python
ui_login = defs.create(
    name="Login page smoke test",
    description="Verify login page loads and accepts valid credentials",
    steps=[
        "Navigate to /login",
        "Enter valid username and password",
        "Click Sign In",
        "Verify redirect to dashboard",
    ],
    expected_result="User is authenticated and sees dashboard",
    domain="webui",
    tags=["smoke", "authentication"],
)

ui_validation = defs.create(
    name="Form field validation",
    description="Check inline error messages for all form inputs",
    steps=[
        "Navigate to /signup",
        "Submit empty form",
        "Verify error messages appear next to required fields",
        "Enter invalid email and verify format error",
        "Enter short password and verify length error",
    ],
    expected_result="Inline errors shown for each invalid field without page reload",
    domain="webui",
    tags=["forms", "validation"],
)

ui_accessibility = defs.create(
    name="Accessibility audit",
    description="Run axe-core against all pages",
    steps=[
        "Run axe DevTools against /login, /dashboard, /settings, /signup",
        "Check for violations at WCAG 2.1 AA level",
    ],
    expected_result="Zero critical or serious violations",
    domain="webui",
    tags=["a11y", "automated"],
)

ui_responsive = defs.create(
    name="Responsive breakpoints check",
    description="Verify layout at mobile tablet and desktop widths",
    steps=[
        "Set viewport to 320x568 (mobile)",
        "Check no horizontal scroll, hamburger menu visible",
        "Set viewport to 768x1024 (tablet)",
        "Check sidebar collapses correctly",
        "Set viewport to 1280x800 (desktop)",
        "Check full navigation and multi-column layout",
    ],
    domain="webui",
    tags=["layout", "responsive"],
)

ui_session = defs.create(
    name="Session timeout behavior",
    description="Verify warning modal and graceful logout",
    steps=[
        "Log in and wait for session to approach expiry",
        "Verify warning modal appears at T-60s",
        "Click 'Extend Session' and verify timer resets",
        "Wait for full expiry without extending",
        "Verify redirect to /login with message",
    ],
    expected_result="Warning at 60s; extend works; redirect on expiry",
    domain="webui",
    tags=["session", "security"],
)
```

### 2.3 Map coverage

```python
defs.map_to_requirement(ui_login.id, reqs.get_by_key("UI-001").id)
defs.map_to_requirement(ui_validation.id, reqs.get_by_key("UI-002").id, coverage_claim="full")
defs.map_to_requirement(ui_validation.id, reqs.get_by_key("UI-007").id, coverage_claim="full")
defs.map_to_requirement(ui_accessibility.id, reqs.get_by_key("UI-004").id, coverage_claim="full")
defs.map_to_requirement(ui_accessibility.id, reqs.get_by_key("UI-005").id, coverage_claim="full")
defs.map_to_requirement(ui_responsive.id, reqs.get_by_key("UI-003").id, coverage_claim="full")
defs.map_to_requirement(ui_session.id, reqs.get_by_key("UI-006").id, coverage_claim="full")
```

### 2.4 Run campaign and collect evidence

```bash
# Create and snapshot
verify --db-path /tmp/ui-validate.db campaign create "Web UI v2.4 Release" \
  --description "Pre-release UI validation — all pages"
verify --db-path /tmp/ui-validate.db campaign version <campaign-id> \
  -t <uuid> -t <uuid> -t <uuid> -t <uuid> -t <uuid> --notes "v2.4-RC1"

# Collect screenshots as evidence
verify --db-path /tmp/ui-validate.db evidence collect <run-id> ./screenshots/login-passed.png --type screenshot
verify --db-path /tmp/ui-validate.db evidence collect <run-id> ./screenshots/form-errors.png --type screenshot
verify --db-path /tmp/ui-validate.db evidence collect <run-id> ./reports/axe-results.json --type a11y_report
verify --db-path /tmp/ui-validate.db evidence collect <run-id> ./screenshots/mobile-320.png --type screenshot --meta '{"viewport":"320x568"}'
verify --db-path /tmp/ui-validate.db evidence collect <run-id> ./screenshots/tablet-768.png --type screenshot --meta '{"viewport":"768x1024"}'
verify --db-path /tmp/ui-validate.db evidence collect <run-id> ./screenshots/desktop-1280.png --type screenshot --meta '{"viewport":"1280x800"}'

# Generate report
verify --db-path /tmp/ui-validate.db campaign report <version-id> -o ui-report.txt
```

---

## 3. API Validation

### 3.1 Import requirements

```bash
verify --db-path /tmp/api-validate.db req import examples/api-requirements.csv
```
```
Imported 9 requirement(s)
  API-001 — Rate limiting enforced
  API-002 — Bearer token auth
  API-003 — JSON error responses
  API-004 — Pagination headers
  API-005 — Request validation
  API-006 — Idempotency support
  API-007 — CORS headers configured
  API-008 — Request ID propagation
  API-009 — Response time SLA
```

### 3.2 Define tests

```python
api_auth = defs.create(
    name="Authentication required",
    description="All endpoints must reject unauthenticated requests",
    steps=[
        "GET /api/v1/users without Authorization header → expect 401",
        "GET /api/v1/users with Authorization: Bearer invalid → expect 401",
        "GET /api/v1/users with valid JWT → expect 200",
        "POST /api/v1/users with valid JWT but insufficient scope → expect 403",
    ],
    expected_result="401 for missing/invalid tokens; 403 for wrong scope; 200 for valid",
    domain="api",
    tags=["auth", "security"],
)

api_rate = defs.create(
    name="Rate limiting behavior",
    description="Verify 429 response after exceeding rate limit",
    steps=[
        "Send 100 GET /api/v1/status requests in 60s from same IP",
        "Verify request 101 returns 429 Too Many Requests",
        "Verify Retry-After header is present",
        "Wait 60s and verify requests succeed again",
    ],
    expected_result="Rate limit enforced at 100 req/min; Retry-After header present",
    domain="api",
    tags=["rate-limit"],
)

api_errors = defs.create(
    name="Error response format",
    description="Verify all error responses follow RFC 7807",
    steps=[
        "Send POST /api/v1/users with empty body → expect 400",
        "Verify response body has type title status detail instance fields",
        "GET /api/v1/users/does-not-exist → expect 404",
        "Verify 404 response also matches Problem Details format",
    ],
    expected_result="All 4xx/5xx responses follow RFC 7807 Problem Details",
    domain="api",
    tags=["errors", "contract"],
)

api_perf = defs.create(
    name="Response time benchmark",
    description="Measure response times under load",
    steps=[
        "Use k6/wrk to send 500 requests to GET /api/v1/status over 30s",
        "Record p50 p95 p99 latencies",
        "Verify p95 < 200ms",
    ],
    expected_result="p95 latency under 200ms at 500 concurrent requests",
    domain="api",
    tags=["performance"],
)

api_pagination = defs.create(
    name="Pagination headers",
    description="Verify list endpoints include pagination metadata",
    steps=[
        "GET /api/v1/users?page=1&per_page=10 → check X-Total-Count header",
        "Verify Link header contains rel=next and rel=last",
        "GET last page → verify Link header has no rel=next",
    ],
    expected_result="X-Total-Count matches total; Link header correct",
    domain="api",
    tags=["pagination"],
)

api_cors = defs.create(
    name="CORS headers",
    description="Verify preflight and actual requests include correct CORS headers",
    steps=[
        "OPTIONS /api/v1/users with Origin: https://app.example.com",
        "Verify Access-Control-Allow-Origin Access-Control-Allow-Methods headers",
        "GET /api/v1/users with Origin → verify CORS response headers",
    ],
    expected_result="CORS headers match configured allowed origins",
    domain="api",
    tags=["cors", "security"],
)
```

### 3.3 Map coverage

```python
defs.map_to_requirement(api_auth.id, reqs.get_by_key("API-002").id, coverage_claim="full")
defs.map_to_requirement(api_rate.id, reqs.get_by_key("API-001").id, coverage_claim="full")
defs.map_to_requirement(api_errors.id, reqs.get_by_key("API-003").id, coverage_claim="full")
defs.map_to_requirement(api_errors.id, reqs.get_by_key("API-005").id, coverage_claim="full")
defs.map_to_requirement(api_perf.id, reqs.get_by_key("API-009").id, coverage_claim="full")
defs.map_to_requirement(api_pagination.id, reqs.get_by_key("API-004").id, coverage_claim="full")
defs.map_to_requirement(api_cors.id, reqs.get_by_key("API-007").id, coverage_claim="full")
```

### 3.4 Run campaign and collect evidence

```bash
verify --db-path /tmp/api-validate.db campaign create "API v3 Compliance" \
  --description "Contract and SLA validation before v3 GA"

verify --db-path /tmp/api-validate.db campaign version <campaign-id> \
  -t <uuid> -t <uuid> -t <uuid> -t <uuid> -t <uuid> -t <uuid> \
  --notes "Full suite run on staging"

# Collect evidence from automated test tooling
verify --db-path /tmp/api-validate.db evidence collect <run-id> ./results/auth-tests.xml --type junit
verify --db-path /tmp/api-validate.db evidence collect <run-id> ./results/rate-limit.json --type api_log --meta '{"tool":"k6"}'
verify --db-path /tmp/api-validate.db evidence collect <run-id> ./reports/load-test-summary.json --type benchmark
verify --db-path /tmp/api-validate.db evidence collect <run-id> ./results/contract-tests.txt --type openapi_diff

# Report
verify --db-path /tmp/api-validate.db campaign report <version-id> --format json -o api-report.json
```

---

## 4. All-in-one script

Putting it together — a full Python script to set up a campaign from scratch:

```python
"""Full workflow: import requirements, define tests, map, create campaign, run."""
import os
os.environ["VERIFY_DB_PATH"] = "/tmp/verify-example.db"

from verify.shared.database import get_session_factory, init_db
from verify.definitions.service import DefinitionServiceImpl
from verify.requirements.service import RequirementServiceImpl
from verify.campaigns.service import CampaignServiceImpl

init_db()
sf = get_session_factory()
req_svc = RequirementServiceImpl(sf)
def_svc = DefinitionServiceImpl(sf)
camp_svc = CampaignServiceImpl(sf)

# 1. Import requirements
for name in ["kubernetes", "webui", "api"]:
    created = req_svc.import_from_csv(f"examples/{name}-requirements.csv")
    print(f"Imported {len(created)} {name} requirements")

# 2. Create test definitions
tests = def_svc.list_all()
print(f"Test definitions in DB: {len(tests)}")

# 3. Create campaign
campaign = camp_svc.create("Cross-domain Audit", "All three domains")
version = camp_svc.create_version(
    campaign.id,
    [t.id for t in tests],
    notes="Initial baseline",
)
print(f"Campaign: {campaign.name}  Version: v{version.version_number}")
print(f"Test runs: {len(camp_svc.get_test_runs(version.id))}")

# 4. Show status
summary = camp_svc.get_summary(version.id)
print(f"Passed: {summary['passed']}  Failed: {summary['failed']}  Pending: {summary['pending']}")

# 5. Coverage check
for req in req_svc.list_all():
    cov = req_svc.get_coverage(req.id)
    status = "COVERED" if cov["covered_by"] > 0 else "UNCOVERED"
    print(f"  {status:9s} {cov['requirement_key']}: {cov['requirement_title']}")
```

```bash
python examples/run_all.py
```
```
Imported 8 kubernetes requirements
Imported 7 webui requirements
Imported 9 api requirements

Campaign: Cross-domain Audit  Version: v1
Test runs: 0
Passed: 0  Failed: 0  Pending: 0

  UNCOVERED K8S-001: Pod must run as non-root
  UNCOVERED K8S-002: No privileged containers
  ...
```

---

## 5. Reporting from the command line

### Text report example

```
verify --db-path /tmp/k8s-validate.db campaign report <version-id>
```
```
Report: Q3 Kubernetes Audit
Version: v1
Created: 2026-06-11T12:00:00+00:00

Total tests:    5
  Passed:       3
  Failed:       2
  Error:        0
  Skipped:      0
  Pending:      0
Pass rate:      60.0%
Evidence items: 2

Test                   Status    Notes
---------------------  --------  -----------------------------------------
Run Kyverno policy     passed    All policies compliant
Check pod security     passed
Verify resource quotas failed    3 deployments missing limits
Audit network policies passed
Verify image registries failed    nginx:latest from Docker Hub
```

### JSON report (excerpt)

```json
{
  "campaign_name": "Q3 Kubernetes Audit",
  "version_number": 1,
  "total_tests": 5,
  "passed": 3,
  "failed": 2,
  "error": 0,
  "skipped": 0,
  "pending": 0,
  "coverage_percent": 60.0,
  "evidence_count": 2,
  "test_results": [
    {
      "test_run_id": "a1b2c3d4-...",
      "test_name": "Run Kyverno policy scan",
      "test_definition_id": "e5f6g7h8-...",
      "status": "passed",
      "notes": "All policies compliant"
    }
  ]
}
```

---

## Next steps

- Add **custom attributes** to requirements via the `attributes` JSON column (e.g. `severity`, `owner`, `sprint`)
- Create **version chains** with `req_svc.create_version("K8S-001", {"title": "Updated title"})`
- Build a **CI integration** that calls `verify evidence collect` from test runners
- Use the Python API directly for **scripted workflows** (no CLI needed)
