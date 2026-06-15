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
print("Phase 2 — Create executable test definitions")
print("=" * 60)

K8S_DIR = os.path.join(EXAMPLES_DIR, "kubernetes")
WEBUI_DIR = os.path.join(EXAMPLES_DIR, "webui")
API_DIR = os.path.join(EXAMPLES_DIR, "api")

definitions = [
    # ── Kubernetes tests ──
    def_svc.create(
        name="Pod security (runAsNonRoot)",
        description="Scan pods for runAsNonRoot securityContext compliance",
        steps=["Run: python3 examples/kubernetes/test_pod_security.py"],
        domain="kubernetes",
        tags=["automated", "security"],
        exec_command=f"python3 {os.path.join(K8S_DIR, 'test_pod_security.py')}",
    ),
    def_svc.create(
        name="Resource limits check",
        description="Verify every container defines CPU and memory limits",
        steps=["Run: python3 examples/kubernetes/test_resource_limits.py"],
        domain="kubernetes",
        tags=["automated", "resources"],
        exec_command=f"python3 {os.path.join(K8S_DIR, 'test_resource_limits.py')}",
    ),
    def_svc.create(
        name="NetworkPolicy audit",
        description="Check that every namespace has a NetworkPolicy",
        steps=["Run: python3 examples/kubernetes/test_network_policy.py"],
        domain="kubernetes",
        tags=["automated", "networking"],
        exec_command=f"python3 {os.path.join(K8S_DIR, 'test_network_policy.py')}",
    ),
    # ── WebUI tests ──
    def_svc.create(
        name="Login page audit",
        description="Check login page for form, CSRF token, password field",
        steps=["Run: python3 examples/webui/test_login_page.py"],
        domain="webui",
        tags=["smoke", "security"],
        exec_command=f"python3 {os.path.join(WEBUI_DIR, 'test_login_page.py')}",
    ),
    def_svc.create(
        name="Page quality check",
        description="Check HTML for title, charset, alt attributes, deprecated tags",
        steps=["Run: python3 examples/webui/test_page_quality.py"],
        domain="webui",
        tags=["a11y", "quality"],
        exec_command=f"python3 {os.path.join(WEBUI_DIR, 'test_page_quality.py')}",
    ),
    # ── API tests ──
    def_svc.create(
        name="Auth endpoint check",
        description="Verify API rejects unauthenticated requests with 401",
        steps=["Run: python3 examples/api/test_auth.py"],
        domain="api",
        tags=["auth", "security"],
        exec_command=f"python3 {os.path.join(API_DIR, 'test_auth.py')}",
    ),
    def_svc.create(
        name="Error format check",
        description="Verify API errors follow RFC 7807 Problem Details",
        steps=["Run: python3 examples/api/test_error_format.py"],
        domain="api",
        tags=["errors", "contract"],
        exec_command=f"python3 {os.path.join(API_DIR, 'test_error_format.py')}",
    ),
]

for td in definitions:
    cmd_note = " [exec]" if td.exec_command else ""
    print(f"  [{td.domain:12s}] {td.name}{cmd_note}")

print(f"\nTotal test definitions: {len(definitions)}")

print("\n" + "=" * 60)
print("Phase 3 — Map tests to requirements")
print("=" * 60)

mappings = {
    "K8S-001": ["Pod security (runAsNonRoot)"],
    "K8S-002": ["Pod security (runAsNonRoot)"],
    "K8S-003": ["Resource limits check"],
    "K8S-005": ["NetworkPolicy audit"],
    "UI-001": ["Login page audit", "Page quality check"],
    "UI-004": ["Page quality check"],
    "UI-005": ["Page quality check"],
    "UI-007": ["Login page audit"],
    "API-002": ["Auth endpoint check"],
    "API-003": ["Error format check"],
    "API-005": ["Error format check"],
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
print("Phase 5 — Execute all test scripts")
print("=" * 60)

results = camp_svc.run_all(version.id)

for tr in results:
    status_display = (
        "[PASS]" if tr.status == "passed"
        else "[FAIL]" if tr.status == "failed"
        else f"[{tr.status.upper()}]"
    )
    td_name = tr.test_definition.name if tr.test_definition else "?"
    print(f"  {status_display} {td_name}")
    if tr.notes:
        print(f"         {tr.notes}")

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
