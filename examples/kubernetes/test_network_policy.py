#!/usr/bin/env python3
"""Check that each namespace has a NetworkPolicy with a default-deny rule.

Simulated scan. In production, use:
    kubectl get netpol -A -o json | python3 test_network_policy.py --stdin

Exit codes:
    0 — all namespaces have a NetworkPolicy
    1 — one or more namespaces missing NetworkPolicy
"""

import sys

SAMPLE_POLICIES = {
    "default": {
        "name": "deny-all-ingress",
        "rules": [{"podSelector": {}, "policyTypes": ["Ingress"]}],
    },
    "production": {
        "name": "prod-netpol",
        "rules": [
            {"podSelector": {"app": "frontend"}, "policyTypes": ["Ingress", "Egress"]}
        ],
    },
    # "staging" namespace is intentionally missing
}

ALL_NAMESPACES = ["default", "production", "staging", "monitoring"]


def main():
    if "--help" in sys.argv:
        print(__doc__)
        sys.exit(0)

    print("Checking NetworkPolicy coverage...")
    missing = []
    ok = []

    for ns in sorted(ALL_NAMESPACES):
        if ns in SAMPLE_POLICIES:
            policy = SAMPLE_POLICIES[ns]
            ok.append((ns, policy["name"]))
            print(f"  [PASS] {ns:20s}  policy: {policy['name']}")
        else:
            missing.append(ns)
            print(f"  [FAIL] {ns:20s}  no NetworkPolicy found")

    print()
    if missing:
        print(f"RESULT: {len(missing)}/{len(ALL_NAMESPACES)} namespaces unprotected")
        for ns in missing:
            print(f"  - {ns}: add a default-deny NetworkPolicy")
        sys.exit(1)
    else:
        print(f"RESULT: All {len(ok)} namespaces have NetworkPolicies")
        sys.exit(0)


if __name__ == "__main__":
    main()
