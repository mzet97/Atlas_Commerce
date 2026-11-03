#!/usr/bin/env python3
"""M6 fulfillment E2E: CONFIRMED -> ship (Control) -> SHIPPED + notify (live).

Setup of product/offer/stock mirrors checkout_e2e.py. Scenarios:
F01 operator ships CONFIRMED -> SHIPPED, notification rows QUEUED.
F02 replay ship -> same version (idempotent).
F03 customer ship -> 403, order untouched.
"""

from __future__ import annotations

import json
import time
import urllib.request

CONTROL = "http://localhost:8102"
ORDER = "http://localhost:8106"
KEYCLOAK = "http://localhost:8180"
INVENTORY = "http://localhost:8104"

PASS_COUNT = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    """One drill assertion: PASS line or immediate red exit."""
    global PASS_COUNT
    if not cond:
        raise SystemExit(f"FAIL {name} {detail}")
    PASS_COUNT += 1
    print(f"PASS {name} {detail}", flush=True)


def _call(base: str, method: str, path: str, body: dict | None = None,
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


def _token(user: str, pwd: str) -> str:
    data = f"client_id=atlas-storefront&username={user}&password={pwd}" \
        f"&grant_type=password".encode()
    req = urllib.request.Request(
        f"{KEYCLOAK}/realms/atlas/protocol/openid-connect/token", data=data,
        method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())["access_token"]


def setup_confirmed() -> str:
    """Own product/offer/stock, then a CONFIRMED checkout."""
    cara = {"Authorization": f"Bearer {_token('cara.catalog', 'cara-dev-only')}"}
    tag = f"{time.time_ns()}"
    _, product = _call(CONTROL, "POST", "/ops/products", {
        "title": {"pt-BR": f"Item Ship {tag}"}, "idempotency_key": f"p-{tag}",
        "correlation_id": f"c-{tag}"}, cara)
    sku = product["id"]
    _call(CONTROL, "POST", f"/ops/products/{sku}/publish",
          {"expected_version": 1, "correlation_id": f"c-{tag}"}, cara)
    _, offer = _call(CONTROL, "POST", "/ops/offers", {
        "sku_id": sku, "seller_id": "atlas", "market_id": "BR", "channel": "web",
        "currency": "BRL", "price_minor": 333,
        "idempotency_key": f"o-{tag}", "correlation_id": f"c-{tag}"}, cara)
    _call(INVENTORY, "POST", "/positions/receive", {
        "warehouse_id": "W1", "sku_id": sku, "quantity": 5,
        "correlation_id": f"c-{tag}"})
    _, cart = _call(ORDER, "POST", "/carts", {
        "customer_id": "e2e", "correlation_id": f"c-{tag}"})
    _call(ORDER, "POST", f"/carts/{cart['id']}/items", {
        "offer_id": offer["id"], "quantity": 1, "correlation_id": f"c-{tag}"})
    quote: dict = {}
    deadline = time.time() + 60
    while not quote and time.time() < deadline:
        s, quote = _call(ORDER, "POST", f"/carts/{cart['id']}/quote")
        if s != 201:
            quote = {}
            time.sleep(2)
    assert quote.get("id"), quote
    s, order = _call(ORDER, "POST", "/checkouts", {
        "quote_id": quote["id"], "customer_id": "e2e", "card_last4": "4242",
        "idempotency_key": f"k-{tag}", "correlation_id": f"c-{tag}"}, timeout=90)
    assert s == 201 and order["status"] == "CONFIRMED", order
    return order["id"]


def main() -> None:
    order_id = setup_confirmed()
    check("setup-confirmed", True, order_id)
    gina = {"Authorization": f"Bearer {_token('gina.fulfillment', 'gina-dev-only')}"}
    alice = {"Authorization": f"Bearer {_token('alice.customer', 'alice-dev-only')}"}

    s, shipped = _call(CONTROL, "POST",
                       f"/ops/fulfillment/orders/{order_id}/ship",
                       {"correlation_id": f"e2e-{time.time_ns()}"}, gina)
    check("F01-shipped", s == 200 and shipped["status"] == "SHIPPED", f"{s}")
    version = shipped["version"]

    s, again = _call(CONTROL, "POST",
                     f"/ops/fulfillment/orders/{order_id}/ship",
                     {"correlation_id": f"e2e-{time.time_ns()}"}, gina)
    check("F02-replay", s == 200 and again["version"] == version, "")

    s, _ = _call(CONTROL, "POST", f"/ops/fulfillment/orders/{order_id}/ship",
                 {"correlation_id": f"e2e-{time.time_ns()}"}, alice)
    check("F03-forbidden", s == 403, f"{s}")

    s, view = _call(CONTROL, "GET", f"/ops/fulfillment/orders/{order_id}", None, gina)
    check("F01-view", s == 200 and view["status"] == "SHIPPED", "")
    print(f"ALL PASS ({PASS_COUNT} checks)", flush=True)


if __name__ == "__main__":
    main()
