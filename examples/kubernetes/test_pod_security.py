#!/usr/bin/env python3
"""Check that pods have securityContext.runAsNonRoot set.

This script simulates a Kyverno/Gatekeeper policy scan. In a real deployment,
replace the simulated check with actual kubectl queries or policy engine output.

Usage:
    python3 test_pod_security.py           # verify from a kubeconfig
    python3 test_pod_security.py --data pods.json  # verify from static data
    python3 test_pod_security.py --help

Exit codes:
    0 — all pods compliant
    1 — one or more pods running as root or without securityContext
"""

import json
import sys

SAMPLE_PODS = [
    {
        "name": "nginx-7b5d8f4c9-abc12",
        "namespace": "default",
        "security_context": {"runAsNonRoot": True, "runAsUser": 1001},
    },
    {
        "name": "redis-5c7d9b6f3-def34",
        "namespace": "default",
        "security_context": {"runAsNonRoot": None},  # missing — violation
    },
    {
        "name": "api-gateway-5d8c6b7a2-ghi56",
        "namespace": "production",
        "security_context": {"runAsNonRoot": True, "runAsUser": 1000},
    },
    {
        "name": "debug-shell",
        "namespace": "dev",
        "security_context": {},
    },
    {
        "name": "monitoring-agent-3f9a2b1c",
        "namespace": "monitoring",
        "security_context": {"runAsNonRoot": True},
    },
]


def check_pods(pods):
    violations = []
    for pod in pods:
        sc = pod.get("security_context", {})
        if not sc.get("runAsNonRoot"):
            violations.append(pod)
    return violations


def main():
    if "--help" in sys.argv:
        print(__doc__)
        sys.exit(0)

    if "--data" in sys.argv:
        idx = sys.argv.index("--data")
        with open(sys.argv[idx + 1]) as f:
            pods = json.load(f)
    else:
        pods = SAMPLE_PODS

    print(f"Scanning {len(pods)} pods for runAsNonRoot compliance...")
    violations = check_pods(pods)

    for pod in pods:
        sc = pod.get("security_context", {})
        ok = sc.get("runAsNonRoot") is True
        status = "PASS" if ok else "FAIL"
        ns_name = f"{pod['namespace']}/{pod['name']}"
        print(f"  [{status}] {ns_name}")

    print()
    if violations:
        print(f"RESULT: {len(violations)}/{len(pods)} pods violate runAsNonRoot policy")
        for v in violations:
            print(f"  - {v['namespace']}/{v['name']}: runAsNonRoot not set or False")
        sys.exit(1)
    else:
        print(f"RESULT: All {len(pods)} pods compliant (runAsNonRoot=True)")
        sys.exit(0)


if __name__ == "__main__":
    main()
