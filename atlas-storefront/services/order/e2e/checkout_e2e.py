#!/usr/bin/env python3
"""M3 checkout E2E: full vertical product->offer->stock->order (live, stdlib).

Env: PSP_WEBHOOK_SECRET not needed (no webhooks crafted here).
Exit nonzero on first failed assertion; prints PASS lines for evidence.

Setup (via Control as cara.catalog + owner APIs, like the M2 vertical):
product -> publish -> offer (333 BRL-cents) -> stock W1 -> quote visible.
Scenarios: C01 happy CONFIRMED, C02 decline CANCELLED+released,
C03 timeout PENDING->reconcile CONFIRMED, C04 replay same order,
C05 consumed quote 422.
"""

from __future__ import annotations

import json
import os
import time
import urllib.request

CONTROL = "http://localhost:8102"
ORDER = os.getenv("ORDER_API", "http://localhost:8106")
PAYMENT = "http://localhost:8105"
INVENTORY = "http://localhost:8104"
KEYCLOAK = "http://localhost:8180"

PASS_COUNT = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    """One drill assertion: PASS line or immediate red exit."""
    global PASS_COUNT
    if not cond:
        raise SystemExit(f"FAIL {name} {detail}")
    PASS_COUNT += 1
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


def setup_offer() -> tuple[str, str]:
    """Create product+offer+stock; return (offer_id, sku_id)."""
    token = _token("cara.catalog", "cara-dev-only")
    auth = {"Authorization": f"Bearer {token}"}
    tag = f"{time.time_ns()}"
    s, product = _call(CONTROL, "POST", "/ops/products", {
        "title": {"pt-BR": f"Cafeteira E2E {tag}"},
        "idempotency_key": f"e2e-prod-{tag}", "correlation_id": f"e2e-{tag}"},
        auth)
    assert s == 201, product
    sku = product["id"]
    s, _ = _call(CONTROL, "POST", f"/ops/products/{sku}/publish",
                 {"expected_version": 1, "correlation_id": f"e2e-{tag}"}, auth)
    assert s == 200, _
    s, offer = _call(CONTROL, "POST", "/ops/offers", {
        "sku_id": sku, "seller_id": "e2e-seller", "market_id": "BR",
        "channel": "web", "currency": "BRL", "price_minor": 333,
        "idempotency_key": f"e2e-offer-{tag}", "correlation_id": f"e2e-{tag}"},
        auth)
    assert s == 201, offer
    s, _ = _call(INVENTORY, "POST", "/positions/receive", {
        "warehouse_id": "W1", "sku_id": sku, "quantity": 20,
        "correlation_id": f"e2e-{tag}"})
    assert s == 201, _
    return offer["id"], sku


def quote_for(offer_id: str) -> dict:
    """Open cart, add offer, quote; poll until the read model converges."""
    s, cart = _call(ORDER, "POST", "/carts", {
        "customer_id": "e2e-cust", "correlation_id": f"e2e-{time.time_ns()}"})
    assert s == 201, cart
    s, _ = _call(ORDER, "POST", f"/carts/{cart['id']}/items",
                 {"offer_id": offer_id, "quantity": 1,
                  "correlation_id": f"e2e-{time.time_ns()}"})
    assert s == 200, _
    deadline = time.time() + 60
    while True:
        s, quote = _call(ORDER, "POST", f"/carts/{cart['id']}/quote")
        if s == 201:
            return quote
        if time.time() > deadline:
            raise SystemExit(f"FAIL quote-never-visible {s} {quote}")
        time.sleep(2)


def checkout(quote_id: str, card: str, key: str, qty_note: str = "") -> tuple[int, dict]:
    return _call(ORDER, "POST", "/checkouts", {
        "quote_id": quote_id, "customer_id": "e2e-cust", "card_last4": card,
        "idempotency_key": key, "correlation_id": f"e2e-{time.time_ns()}"},
        timeout=90)


def position(sku: str) -> dict:
    s, body = _call(INVENTORY, "GET", f"/positions/W1/{sku}")
    assert s == 200, body
    return body


def wait_status(order_id: str, want: str, budget_s: float) -> dict:
    """Poll owner view until status or budget out."""
    deadline = time.time() + budget_s
    while True:
        s, body = _call(ORDER, "GET", f"/orders/{order_id}")
        assert s == 200, body
        if body["status"] == want or time.time() > deadline:
            return body
        time.sleep(2)


def main() -> None:
    offer_id, sku = setup_offer()
    check("setup-offer", True, f"{offer_id} {sku}")
    base_available = position(sku)["available"]

    # C01 happy path: 333 approved -> CONFIRMED, stock committed.
    q1 = quote_for(offer_id)
    check("C01-quote", q1["total_minor"] == 333, f"total={q1['total_minor']}")
    s, o1 = checkout(q1["id"], "4242", f"e2e-c01-{time.time_ns()}")
    check("C01-confirmed", s == 201 and o1["status"] == "CONFIRMED", f"{s}")
    check("C01-stock-committed",
          position(sku)["available"] == base_available - 1,
          f"avail={position(sku)['available']}")
    s, intent = _call(PAYMENT, "GET", f"/intents/{o1['payment_intent_id']}")
    check("C01-paid", s == 200 and intent["status"] == "AUTHORIZED", "")

    # C02 decline: 402 CANCELLED, reservation released.
    q2 = quote_for(offer_id)
    s, o2 = checkout(q2["id"], "10002", f"e2e-c02-{time.time_ns()}")
    check("C02-cancelled", s == 402 and o2["status"] == "CANCELLED", f"{s}")
    check("C02-released", position(sku)["available"] == base_available - 1, "")

    # C03 timeout: qty hack -> total 666 via direct quote edit is impossible;
    # instead reuse the 333 offer x2 through a second cart line.
    s, cart = _call(ORDER, "POST", "/carts", {
        "customer_id": "e2e-cust", "correlation_id": f"e2e-{time.time_ns()}"})
    assert s == 201, cart
    _call(ORDER, "POST", f"/carts/{cart['id']}/items",
          {"offer_id": offer_id, "quantity": 2,
           "correlation_id": f"e2e-{time.time_ns()}"})
    deadline = time.time() + 60
    while True:
        s, q3 = _call(ORDER, "POST", f"/carts/{cart['id']}/quote")
        if s == 201:
            break
        if time.time() > deadline:
            raise SystemExit("FAIL C03-quote-never-visible")
        time.sleep(2)
    check("C03-quote-666", q3["total_minor"] == 666, "")
    s, o3 = checkout(q3["id"], "4242", f"e2e-c03-{time.time_ns()}")
    check("C03-pending", s == 202 and o3["status"] == "PENDING", f"{s}")
    settled = wait_status(o3["id"], "CONFIRMED", 20)
    if settled["status"] != "CONFIRMED":
        s, settled = _call(ORDER, "POST", f"/orders/{o3['id']}/reconcile",
                           {"correlation_id": f"e2e-{time.time_ns()}"},
                           timeout=90)
        settled = wait_status(o3["id"], "CONFIRMED", 60)
    check("C03-reconciled", settled["status"] == "CONFIRMED",
          f"status={settled['status']}")

    # C04 replay: same key -> same order, single payment intent.
    q4 = quote_for(offer_id)
    key = f"e2e-c04-{time.time_ns()}"
    s, first = checkout(q4["id"], "4242", key)
    s2, second = checkout(q4["id"], "4242", key)
    check("C04-replay", (s, s2) == (201, 201) and second["id"] == first["id"]
          and second["payment_intent_id"] == first["payment_intent_id"], "")

    # C05 consumed quote, new key -> 422.
    s, body = checkout(q4["id"], "4242", f"e2e-c05-{time.time_ns()}")
    check("C05-consumed-422", s == 422, f"{s} {body.get('detail', '')[:40]}")

    print(f"ALL PASS ({PASS_COUNT} checks)", flush=True)


if __name__ == "__main__":
    main()
