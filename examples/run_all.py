"""Full workflow: import requirements, define tests, map, create campaign, run.

Run with:
    python examples/run_all.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["VERIFY_DB_PATH"] = "/tmp/verify-example.db"

# Import all models before init_db so SQLAlchemy can resolve cross-package
# string-based forward references (e.g. TestRun → Evidence)
import verify.evidence.models  # noqa: E402, F401
from verify.campaigns.service import CampaignServiceImpl
from verify.definitions.service import DefinitionServiceImpl
from verify.requirements.service import RequirementServiceImpl
from verify.shared.database import get_session_factory, init_db

init_db()
sf = get_session_factory()
req_svc = RequirementServiceImpl(sf)
def_svc = DefinitionServiceImpl(sf)
camp_svc = CampaignServiceImpl(sf)


EXAMPLES_DIR = os.path.dirname(os.path.abspath(__file__))

print("=" * 60)
print("Phase 1 — Import requirements")
print("=" * 60)

for name in ["kubernetes", "webui", "api"]:
    path = os.path.join(EXAMPLES_DIR, f"{name}-requirements.csv")
    created = req_svc.import_from_csv(path)
    for r in created:
        print(f"  [{r.domain:12s}] {r.key:8s}  {r.title}")

all_reqs = req_svc.list_all()
print(f"\nTotal requirements: {len(all_reqs)}")

print("\n" + "=" * 60)
print("Phase 2 — Create test definitions")
print("=" * 60)

definitions = [
    # Kubernetes tests
    def_svc.create(
        name="Run Kyverno policy scan",
        steps=["kyverno apply policies/ --cluster"],
        domain="kubernetes",
        tags=["automated"],
    ),
    def_svc.create(
        name="Check pod security contexts",
        steps=["kubectl get pods -A -o json | jq '.items[].spec.containers[].securityContext'"],
        domain="kubernetes",
        tags=["manual", "security"],
    ),
    def_svc.create(
        name="Verify resource quotas",
        steps=["kubectl get resourcequota -A"],
        domain="kubernetes",
        tags=["automated"],
    ),
    def_svc.create(
        name="Audit network policies",
        steps=["kubectl get netpol -A"],
        domain="kubernetes",
        tags=["automated", "networking"],
    ),
    def_svc.create(
        name="Verify image registries",
        steps=["kubectl get pods -A -o json | jq -r '.items[].spec.containers[].image'"],
        domain="kubernetes",
        tags=["automated", "supply-chain"],
    ),
    # WebUI tests
    def_svc.create(
        name="Login page smoke test",
        steps=["Navigate to /login", "Enter credentials", "Verify redirect to dashboard"],
        domain="webui",
        tags=["smoke", "authentication"],
    ),
    def_svc.create(
        name="Form field validation",
        steps=["Submit empty form", "Verify inline error messages"],
        domain="webui",
        tags=["forms", "validation"],
    ),
    def_svc.create(
        name="Accessibility audit",
        steps=["Run axe-core against all pages"],
        domain="webui",
        tags=["a11y", "automated"],
    ),
    def_svc.create(
        name="Responsive breakpoints check",
        steps=["Viewport 320px", "Viewport 768px", "Viewport 1280px"],
        domain="webui",
        tags=["layout"],
    ),
    def_svc.create(
        name="Session timeout behavior",
        steps=["Wait for session to approach expiry", "Verify warning modal"],
        domain="webui",
        tags=["session", "security"],
    ),
    # API tests
    def_svc.create(
        name="Authentication required",
        steps=["GET /api/v1/users without Authorization → 401", "GET with valid JWT → 200"],
        domain="api",
        tags=["auth", "security"],
    ),
    def_svc.create(
        name="Rate limiting behavior",
        steps=["Send 100 requests in 60s", "Verify 101st returns 429"],
        domain="api",
        tags=["rate-limit"],
    ),
    def_svc.create(
        name="Error response format",
        steps=["Send bad request", "Verify RFC 7807 Problem Details format"],
        domain="api",
        tags=["errors", "contract"],
    ),
    def_svc.create(
        name="Response time benchmark",
        steps=["Run 500 requests over 30s", "Verify p95 < 200ms"],
        domain="api",
        tags=["performance"],
    ),
    def_svc.create(
        name="Pagination headers",
        steps=["GET /api/v1/users?page=1", "Verify X-Total-Count and Link headers"],
        domain="api",
        tags=["pagination"],
    ),
    def_svc.create(
        name="CORS headers",
        steps=["OPTIONS with Origin header", "Verify CORS response headers"],
        domain="api",
        tags=["cors", "security"],
    ),
]

for td in definitions:
    print(f"  [{td.domain:12s}] {td.name}")

print(f"\nTotal test definitions: {len(definitions)}")

print("\n" + "=" * 60)
print("Phase 3 — Map tests to requirements")
print("=" * 60)

mappings = {
    "K8S-001": ["Run Kyverno policy scan", "Check pod security contexts"],
    "K8S-002": ["Run Kyverno policy scan", "Check pod security contexts"],
    "K8S-003": ["Verify resource quotas"],
    "K8S-005": ["Audit network policies"],
    "K8S-007": ["Verify image registries"],
    "UI-001": ["Login page smoke test"],
    "UI-002": ["Form field validation"],
    "UI-003": ["Responsive breakpoints check"],
    "UI-004": ["Accessibility audit"],
    "UI-005": ["Accessibility audit"],
    "UI-006": ["Session timeout behavior"],
    "UI-007": ["Form field validation"],
    "API-001": ["Rate limiting behavior"],
    "API-002": ["Authentication required"],
    "API-003": ["Error response format"],
    "API-004": ["Pagination headers"],
    "API-005": ["Error response format"],
    "API-007": ["CORS headers"],
    "API-009": ["Response time benchmark"],
}

td_by_name = {td.name: td for td in definitions}
mapped = 0
for req_key, td_names in mappings.items():
    req = req_svc.get_by_key(req_key)
    for td_name in td_names:
        td = td_by_name[td_name]
        def_svc.map_to_requirement(td.id, req.id)
        mapped += 1

print(f"  Created {mapped} requirement→test mappings")

print("\n" + "=" * 60)
print("Phase 4 — Create campaign and version")
print("=" * 60)

campaign = camp_svc.create(
    "Cross-domain Audit",
    "Kubernetes security, Web UI accessibility, and API contract validation",
)

test_ids = [td.id for td in definitions]
version = camp_svc.create_version(campaign.id, test_ids, notes="Initial baseline")

runs = camp_svc.get_test_runs(version.id)
print(f"  Campaign:  {campaign.name}")
print(f"  Version:   v{version.version_number} ({version.id})")
print(f"  Test runs: {len(runs)}")

print("\n" + "=" * 60)
print("Phase 5 — Simulate test execution")
print("=" * 60)

results = [
    ("Run Kyverno policy scan", "passed", "All policies compliant"),
    ("Check pod security contexts", "passed", None),
    ("Verify resource quotas", "failed", "3 deployments missing limits"),
    ("Audit network policies", "passed", None),
    ("Verify image registries", "failed", "nginx:latest from Docker Hub"),
    ("Login page smoke test", "passed", None),
    ("Form field validation", "passed", None),
    ("Accessibility audit", "failed", "2 contrast violations on /settings"),
    ("Responsive breakpoints check", "passed", None),
    ("Session timeout behavior", "passed", "Warning appears at T-60s"),
    ("Authentication required", "passed", None),
    ("Rate limiting behavior", "passed", "429 returned at 101 requests"),
    ("Error response format", "passed", None),
    ("Response time benchmark", "passed", "p95=142ms"),
    ("Pagination headers", "passed", None),
    ("CORS headers", "failed", "Missing Access-Control-Allow-Methods on /users"),
]

for tr in runs:
    td_name = tr.test_definition.name
    match = [r for r in results if r[0] == td_name]
    if match:
        _, status, notes = match[0]
        camp_svc.update_test_run_status(tr.id, status, notes)
        status_display = f"[{'PASS' if status == 'passed' else 'FAIL'}]"
        print(f"  {status_display} {td_name}")
        if notes:
            print(f"         → {notes}")

print("\n" + "=" * 60)
print("Phase 6 — Coverage report")
print("=" * 60)

uncovered = 0
for req in all_reqs:
    cov = req_svc.get_coverage(req.id)
    status = "COVERED" if cov["covered_by"] > 0 else "UNCOVERED"
    if cov["covered_by"] == 0:
        uncovered += 1
    print(f"  {status:9s} [{req.domain:12s}] {req.key:8s} {req.title}")

print(f"\n  Covered: {len(all_reqs) - uncovered}/{len(all_reqs)}")
print(f"  Uncovered: {uncovered}/{len(all_reqs)}")

print("\n" + "=" * 60)
print("Phase 7 — Campaign summary")
print("=" * 60)

summary = camp_svc.get_summary(version.id)
print(f"  Campaign:   {summary['campaign_name']}  v{summary['version_number']}")
print(f"  Total:      {summary['total_tests']}")
print(f"  Passed:     {summary['passed']}")
print(f"  Failed:     {summary['failed']}")
print(f"  Error:      {summary['error']}")
print(f"  Skipped:    {summary['skipped']}")
print(f"  Pending:    {summary['pending']}")
print(f"  Pass rate:  {summary['pass_rate']}%")

print("\n" + "=" * 60)
print("Done. Database at:", os.environ["VERIFY_DB_PATH"])
print("Run 'verify --db-path /tmp/verify-example.db campaign report <version-id>' for text report")
print("=" * 60)
