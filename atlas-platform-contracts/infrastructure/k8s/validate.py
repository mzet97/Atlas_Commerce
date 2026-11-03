#!/usr/bin/env python3
"""M8 structural gate: every manifest parses and honors the Atlas contract.

Checks: namespace pinning, selector/label match, per-role env completeness,
probes on serving APIs, resources everywhere, Service->Deployment wiring,
secret refs only to atlas-secrets (created in M8-increment-2), psp-fake
labeled dev-only. NOT a deploy proof: no cluster exists here (see README).
"""

from __future__ import annotations

import glob
import os
import sys

import yaml

K8S_DIR = os.path.dirname(os.path.abspath(__file__))
FAILURES: list[str] = []


def fail(msg: str) -> None:
    FAILURES.append(msg)
    print(f"FAIL {msg}")


def docs() -> list[dict]:
    """All manifest documents except this validator's own helpers."""
    found: list[dict] = []
    for path in sorted(glob.glob(os.path.join(K8S_DIR, "*.yaml"))):
        with open(path, encoding="utf-8") as fh:
            for doc in yaml.safe_load_all(fh):
                if doc:
                    found.append(doc)
    return found


def check_deployment(doc: dict) -> None:
    name = doc["metadata"]["name"]
    if doc["metadata"].get("namespace") != "atlas":
        fail(f"{name}: namespace must be atlas")
    spec = doc["spec"]
    labels = spec["template"]["metadata"]["labels"]
    if spec["selector"]["matchLabels"] != labels:
        fail(f"{name}: selector/labels mismatch")
    for container in spec["template"]["spec"]["containers"]:
        cname = container["name"]
        if not container.get("image"):
            fail(f"{name}/{cname}: image required")
        if not container.get("command"):
            fail(f"{name}/{cname}: command required (no shell default)")
        if not container.get("resources", {}).get("limits"):
            fail(f"{name}/{cname}: resources.limits required")
        env_names = {e["name"] for e in container.get("env", [])}
        for env in container.get("env", []):
            ref = (env.get("valueFrom") or {}).get("secretKeyRef", {}).get("name")
            if ref and ref != "atlas-secrets":
                fail(f"{name}/{cname}: secret must be atlas-secrets, got {ref}")
        serving = name.endswith("-api") or name in ("storefront-next",)
        worker = name.endswith(("-relay", "-projector")) or name == "psp-fake"
        if serving and not container.get("livenessProbe"):
            fail(f"{name}/{cname}: serving API needs livenessProbe")
        if worker and container.get("livenessProbe"):
            fail(f"{name}/{cname}: workers must not have probes")
        if "-api" in name and "OTEL_SERVICE_NAME" not in env_names:
            fail(f"{name}/{cname}: OTEL_SERVICE_NAME required")
    if name == "psp-fake" and doc["metadata"].get("labels", {}).get("dev-only") != "true":
        fail("psp-fake: dev-only=true label required")


def main() -> None:
    all_docs = docs()
    deployments = [d for d in all_docs if d.get("kind") == "Deployment"]
    services = [d for d in all_docs if d.get("kind") == "Service"]
    if len(deployments) != 18:
        fail(f"expected 18 Deployments, got {len(deployments)}")
    if len(services) != 8:
        fail(f"expected 8 Services, got {len(services)}")
    for doc in deployments:
        check_deployment(doc)
    wired = set()
    for doc in deployments:
        wired.add(tuple(sorted(doc["spec"]["template"]["metadata"]["labels"].items())))
    for svc in services:
        sel = tuple(sorted(svc["spec"]["selector"].items()))
        if sel not in wired:
            fail(f"Service {svc['metadata']['name']}: selector matches nothing")
    if FAILURES:
        raise SystemExit(f"{len(FAILURES)} structural violations")
    print(f"ALL PASS ({len(deployments)} Deployments, {len(services)} Services)")


if __name__ == "__main__":
    main()
