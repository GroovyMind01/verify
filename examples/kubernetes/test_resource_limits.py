#!/usr/bin/env python3
"""Verify that every container defines CPU and memory resource limits.

Checks a static pod manifest. In production, pipe `kubectl get pods -A -o json`
into this script via --data.

Usage:
    python3 test_resource_limits.py
    kubectl get pods -A -o json | python3 test_resource_limits.py --stdin
    python3 test_resource_limits.py --data pods.json

Exit codes:
    0 — all containers have limits
    1 — one or more containers missing limits
"""

import json
import sys

SAMPLE_PODS = [
    {
        "name": "frontend-abc",
        "namespace": "production",
        "containers": [
            {"name": "app", "limits": {"cpu": "500m", "memory": "256Mi"}},
            {"name": "sidecar", "limits": {"cpu": "100m", "memory": "128Mi"}},
        ],
    },
    {
        "name": "backend-def",
        "namespace": "production",
        "containers": [
            {"name": "worker", "limits": {"cpu": "1", "memory": "512Mi"}},
        ],
    },
    {
        "name": "cache-ghi",
        "namespace": "production",
        "containers": [
            {"name": "redis", "limits": {}},  # missing limits — violation
        ],
    },
    {
        "name": "batch-job",
        "namespace": "staging",
        "containers": [
            {"name": "processor", "limits": None},  # no limits at all
        ],
    },
]


def check_limits(pods):
    violations = []
    for pod in pods:
        for c in pod.get("containers", []):
            limits = c.get("limits") or {}
            if "cpu" not in limits or "memory" not in limits:
                violations.append((pod, c))
    return violations


def main():
    if "--help" in sys.argv:
        print(__doc__)
        sys.exit(0)

    if "--stdin" in sys.argv:
        pods = json.load(sys.stdin).get("items", [])
    elif "--data" in sys.argv:
        idx = sys.argv.index("--data")
        with open(sys.argv[idx + 1]) as f:
            pods = json.load(f)
    else:
        pods = SAMPLE_PODS

    print("Checking resource limits...")
    violations = check_limits(pods)
    total_containers = sum(len(p.get("containers", [])) for p in pods)

    for pod in pods:
        for c in pod.get("containers", []):
            limits = c.get("limits") or {}
            has_cpu = "cpu" in limits
            has_mem = "memory" in limits
            if has_cpu and has_mem:
                status = "PASS"
                detail = f"cpu={limits['cpu']} mem={limits['memory']}"
            else:
                status = "FAIL"
                missing = []
                if not has_cpu:
                    missing.append("cpu")
                if not has_mem:
                    missing.append("memory")
                detail = f"missing: {', '.join(missing)}"
            print(f"  [{status}] {pod['namespace']}/{pod['name']}/{c['name']}  {detail}")

    print()
    if violations:
        print(f"RESULT: {len(violations)}/{total_containers} containers missing limits")
        sys.exit(1)
    else:
        print(f"RESULT: All {total_containers} containers have CPU and memory limits")
        sys.exit(0)


if __name__ == "__main__":
    main()
