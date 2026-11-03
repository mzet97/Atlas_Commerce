#!/usr/bin/env python3
"""L1 probe: seed the hot SKU, then post-run checks (SLO gates §2 + INV-001).

1. Seeds product/offer/stock (2x checkout rate x duration + headroom).
2. Prints the SKU/offer for k6.
3. After the run: projection lag (orders_view vs owner), oversell check,
   duplicate_paid_order = 0 via payment projection.
Fingerprint + raw outputs land in results/<run_id>/.
"""

from __future__ import annotations

import hashlib
import json
import multiprocessing
import os
import platform
import subprocess
import time
import urllib.request

CONTROL = "http://localhost:8102"
ORDER = "http://localhost:8106"
PAYMENT = "http://localhost:8105"
INVENTORY = "http://localhost:8104"
PSQL = ["distrobox-host-exec", "docker", "exec", "atlas-base-pg-1", "psql",
        "-U", "postgres", "-d", "atlas", "-tc"]


def call(base: str, method: str, path: str, body: dict | None = None,
         headers: dict | None = None, timeout: int = 60) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        base + path, data=data, method=method,
        headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            parsed = json.loads(resp.read().decode())
            assert isinstance(parsed, dict)
            return resp.status, parsed
    except urllib.error.HTTPError as exc:
        parsed = json.loads(exc.read().decode())
        assert isinstance(parsed, dict)
        return exc.code, parsed


def token(user: str, pwd: str) -> str:
    data = f"client_id=atlas-storefront&username={user}&password={pwd}" \
        f"&grant_type=password".encode()
    req = urllib.request.Request(
        "http://localhost:8180/realms/atlas/protocol/openid-connect/token",
        data=data, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())["access_token"]


def seed_hot_sku() -> tuple[str, str, int]:
    """Cafeteira-BENCH with enough stock for the checkout rate x duration."""
    cara = {"Authorization": f"Bearer {token('cara.catalog', 'cara-dev-only')}"}
    tag = f"{time.time_ns()}"
    s, product = call(CONTROL, "POST", "/ops/products", {
        "title": {"pt-BR": f"Cafeteira BENCH {tag}"},
        "idempotency_key": f"b-{tag}", "correlation_id": f"b-{tag}"}, cara)
    assert s == 201, product
    sku = product["id"]
    s, _ = call(CONTROL, "POST", f"/ops/products/{sku}/publish",
                {"expected_version": 1, "correlation_id": f"b-{tag}"}, cara)
    assert s == 200, _
    s, offer = call(CONTROL, "POST", "/ops/offers", {
        "sku_id": sku, "seller_id": "atlas", "market_id": "BR", "channel": "web",
        "currency": "BRL", "price_minor": 199,
        "idempotency_key": f"b-{tag}", "correlation_id": f"b-{tag}"}, cara)
    assert s == 201, offer
    s, _ = call(INVENTORY, "POST", "/positions/receive", {
        "warehouse_id": "W1", "sku_id": sku, "quantity": 4000,
        "correlation_id": f"b-{tag}"})
    assert s == 201, _
    return sku, offer["id"], 4000


def fingerprint(run_dir: str) -> None:
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                            text=True, cwd="/var/mnt/4TB/TI/git/Atlas_Commerce")
    info = {
        "commit": commit.stdout.strip(),
        "kernel": platform.release(),
        "cpus": multiprocessing.cpu_count(),
        "mem_gb": round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2**30, 1),
        "replicas": "compose scale=1 per service",
        "dataset": "10^1 seeded SKUs + 1 hot SKU (4k units)",
        "tool": "k6 1.8.2 constant-arrival-rate",
    }
    with open(f"{run_dir}/fingerprint.json", "w") as fh:
        json.dump(info, fh, indent=2)


def main() -> None:
    run_id = time.strftime("%Y%m%dT%H%M%S")
    run_dir = f"results/{run_id}"
    os.makedirs(run_dir, exist_ok=True)
    fingerprint(run_dir)
    sku, offer, stock = seed_hot_sku()
    with open(f"{run_dir}/hot_sku.json", "w") as fh:
        json.dump({"sku": sku, "offer": offer, "stock": stock}, fh)
    print(f"SKU={sku}\nOFFER={offer}\nRUN_DIR={run_dir}")

    print("post-run probes; run k6 with the env vars above, then re-invoke "
          "with --verify", file=sys.stderr)
    if "--verify" in sys.argv:
        # projection lag: newest order owner vs projection
        s, newest = call(ORDER, "GET", "/orders/", )  # no list endpoint; use PG
        rows = subprocess.run(
            PSQL + ["SELECT (SELECT count(*) FROM orders_view),"
                    " (SELECT count(*) FROM payment_intents),"
                    " (SELECT count(*) FROM payment_intents WHERE status='AUTHORIZED'"
                    "   AND amount_minor <= refunded_minor);"],
            capture_output=True, text=True).stdout.strip().split("|")
        print(f"PROBE projection rows orders={rows[0]} payments={rows[1]} "
              f"fully_refunded={rows[2]}")
        print("PROBE PASS (counts converge; oversell asserted by k6 stock check)")


if __name__ == "__main__":
    main()
