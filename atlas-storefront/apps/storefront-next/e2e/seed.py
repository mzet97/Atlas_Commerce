#!/usr/bin/env python3
"""E2E seed: reproducible dataset for the Playwright specs (live stack, stdlib).

Creates exactly what the specs assert:
- "Cafeteira M2": published, offer 12990 BRL-minor, 7 available, allowlisted.
- "Item M6" / "Item Ship": published offers that must STAY OFF /recommendations
  (never allowlisted).

Idempotent-ish: every run uses a fresh idempotency tag; reruns create new
products, but the storefront assertion only needs one visible "Cafeteira M2".
Exits nonzero on first failed assertion; prints PASS lines for evidence.
"""

from __future__ import annotations

import json
import time
import urllib.request

CONTROL = "http://localhost:8102"
INVENTORY = "http://localhost:8104"
STORE = "http://localhost:3100"
KEYCLOAK = "http://localhost:8180"


def check(name: str, cond: bool, detail: str = "") -> None:
    """One seed assertion: PASS line or immediate red exit."""
    if not cond:
        raise SystemExit(f"FAIL {name} {detail}")
    print(f"PASS {name} {detail}", flush=True)


def _call(base: str, method: str, path: str, body: dict | None = None,
          headers: dict | None = None, timeout: int = 30) -> tuple[int, dict]:
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


def _token(user: str, pwd: str) -> str:
    data = f"client_id=atlas-storefront&username={user}&password={pwd}" \
        f"&grant_type=password".encode()
    req = urllib.request.Request(
        f"{KEYCLOAK}/realms/atlas/protocol/openid-connect/token", data=data,
        method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())["access_token"]


def seed_product(cara: dict[str, str], title: str, price_minor: int,
                 qty: int, seller: str, allow: bool) -> None:
    """Product -> publish -> offer -> stock (+ allowlist)."""
    tag = f"{time.time_ns()}"
    s, product = _call(CONTROL, "POST", "/ops/products", {
        "title": {"pt-BR": title}, "idempotency_key": f"seed-p-{tag}",
        "correlation_id": f"seed-{tag}"}, cara)
    assert s == 201, (title, s, product)
    sku = product["id"]
    s, _ = _call(CONTROL, "POST", f"/ops/products/{sku}/publish",
                 {"expected_version": 1, "correlation_id": f"seed-{tag}"}, cara)
    assert s == 200, _
    s, offer = _call(CONTROL, "POST", "/ops/offers", {
        "sku_id": sku, "seller_id": seller, "market_id": "BR", "channel": "web",
        "currency": "BRL", "price_minor": price_minor,
        "idempotency_key": f"seed-o-{tag}", "correlation_id": f"seed-{tag}"},
        cara)
    assert s == 201, offer
    s, _ = _call(INVENTORY, "POST", "/positions/receive", {
        "warehouse_id": "W1", "sku_id": sku, "quantity": qty,
        "correlation_id": f"seed-{tag}"})
    assert s == 201, _
    if allow:
        s, _ = _call(CONTROL, "POST", "/ops/ai/allowlist", {
            "offer_id": offer["id"], "reason": "e2e seed",
            "correlation_id": f"seed-{tag}"}, cara)
        assert s == 201, _
    print(f"PASS seed {title} offer={offer['id']}", flush=True)


def _store(path: str) -> str:
    with urllib.request.urlopen(f"{STORE}{path}", timeout=15) as resp:
        return resp.read().decode()


def await_convergence() -> None:
    """Poll the storefront until all seeded projections are visible."""
    deadline = time.time() + 120
    home = search = recs = ""
    while time.time() < deadline:
        try:
            home = _store("/")
            search = _store("/search?q=Cafeteira")
            recs = _store("/recommendations")
            if ("Cafeteira M2" in home and "129.90 BRL" in home
                    and "7 un." in home and "Cafeteira M2" in search
                    and "Cafeteira M2" in recs):
                break
        except urllib.error.URLError:
            pass  # storefront warming up
        time.sleep(3)
    check("home-lists-cafeteira", "Cafeteira M2" in home and "129.90 BRL" in home
          and "7 un." in home, "")
    check("search-finds-cafeteira", "Cafeteira M2" in search, "")
    check("recs-allowlist-only", "Cafeteira M2" in recs
          and "Item M6" not in recs and "Item Ship" not in recs, "")


def main() -> None:
    cara = {"Authorization": f"Bearer {_token('cara.catalog', 'cara-dev-only')}"}
    seed_product(cara, "Cafeteira M2", 12990, 7, "e2e-main", allow=True)
    seed_product(cara, "Item M6", 500, 5, "e2e-m6", allow=False)
    seed_product(cara, "Item Ship", 700, 5, "e2e-ship", allow=False)
    await_convergence()
    print("ALL PASS (seed ready)", flush=True)


if __name__ == "__main__":
    main()
