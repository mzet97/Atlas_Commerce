#!/usr/bin/env python3
"""TASK-002-013 drill: coupon + tax + multi-warehouse checkout (live, stdlib).

Setup via Control as cara.catalog/pam.pricing. Flow:
S01 pam.pricing creates P10 coupon (BR-scoped) via Control -> 201.
S02 cara publishes offer (10000 BRL-minor, market BR), stock ONLY in W2.
S03 cart + item + coupon -> quote: subtotal 10000, discount 1000,
    tax 1380 (BR 15.5% on 9000), total 10380.
S04 checkout card 4242 -> CONFIRMED; reservation landed in W2 (W1 empty);
    payment intent amount = 10380; W2 position committed.
Exit nonzero on first failed assertion; prints PASS lines for evidence.
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


def main() -> None:
    cara = {"Authorization": f"Bearer {_token('cara.catalog', 'cara-dev-only')}"}
    pam = {"Authorization": f"Bearer {_token('pam.pricing', 'pam-dev-only')}"}
    tag = f"{time.time_ns()}"

    # S01: coupon rule via Control (pricing_manager + BR grant).
    code = f"E2E{tag[-6:]}"
    s, coupon = _call(CONTROL, "POST", "/ops/coupons", {
        "code": code, "kind": "PERCENT", "value": 10, "market_id": "BR",
        "correlation_id": f"c-{tag}"}, pam)
    check("S01-coupon-created", s == 201 and coupon.get("active") is True,
          f"{s} {code}")

    # S02: product + publish + offer (BR) + stock ONLY in W2.
    s, product = _call(CONTROL, "POST", "/ops/products", {
        "title": {"pt-BR": f"Cafeteira Cupom {tag}"},
        "idempotency_key": f"p-{tag}", "correlation_id": f"c-{tag}"}, cara)
    assert s == 201, product
    sku = product["id"]
    s, _ = _call(CONTROL, "POST", f"/ops/products/{sku}/publish",
                 {"expected_version": 1, "correlation_id": f"c-{tag}"}, cara)
    assert s == 200, _
    s, offer = _call(CONTROL, "POST", "/ops/offers", {
        "sku_id": sku, "seller_id": "atlas", "market_id": "BR", "channel": "web",
        "currency": "BRL", "price_minor": 10000,
        "idempotency_key": f"o-{tag}", "correlation_id": f"c-{tag}"}, cara)
    assert s == 201, offer
    s, _ = _call(INVENTORY, "POST", "/positions/receive", {
        "warehouse_id": "W2", "sku_id": sku, "quantity": 10,
        "correlation_id": f"c-{tag}"})
    assert s == 201, _

    # S03: cart + item + coupon; poll quote until the projection converges.
    s, cart = _call(ORDER, "POST", "/carts", {
        "customer_id": "e2e", "correlation_id": f"c-{tag}"})
    assert s == 201, cart
    s, _ = _call(ORDER, "POST", f"/carts/{cart['id']}/items", {
        "offer_id": offer["id"], "quantity": 1, "correlation_id": f"c-{tag}"})
    assert s == 200, _
    s, _ = _call(ORDER, "POST", f"/carts/{cart['id']}/coupon", {
        "code": code, "correlation_id": f"c-{tag}"})
    check("S03-coupon-set", s == 200, f"{s}")
    quote: dict = {}
    deadline = time.time() + 90
    while time.time() < deadline:
        s, quote = _call(ORDER, "POST", f"/carts/{cart['id']}/quote")
        if s == 201:
            break
        time.sleep(2)
    assert quote.get("id"), quote
    check("S03-breakdown",
          quote.get("subtotal_minor") == 10000
          and quote.get("discount_minor") == 1000
          and quote.get("tax_minor") == 1395
          and quote.get("total_minor") == 10395
          and quote.get("market_id") == "BR",
          str({k: quote.get(k) for k in
               ("subtotal_minor", "discount_minor", "tax_minor", "total_minor")}))

    # S04: checkout settles; reservation in W2; intent charged the total.
    s, order = _call(ORDER, "POST", "/checkouts", {
        "quote_id": quote["id"], "customer_id": "e2e", "card_last4": "4242",
        "idempotency_key": f"k-{tag}", "correlation_id": f"c-{tag}"}, timeout=90)
    check("S04-confirmed", s == 201 and order.get("status") == "CONFIRMED",
          f"{s} {order.get('status')}")
    check("S04-order-breakdown",
          order.get("discount_minor") == 1000 and order.get("tax_minor") == 1395
          and order.get("coupon_code") == code,
          str({k: order.get(k) for k in
               ("discount_minor", "tax_minor", "coupon_code", "total_minor")}))
    s, intent = _call(PAYMENT, "GET", f"/intents/{order['payment_intent_id']}")
    check("S04-intent-amount",
          s == 200 and intent.get("amount_minor") == 10395
          and intent.get("status") == "AUTHORIZED",
          str(intent.get("amount_minor")))
    s, w2 = _call(INVENTORY, "GET", f"/positions/W2/{sku}")
    check("S04-w2-committed",
          s == 200 and w2.get("available") == 9, f"avail={w2.get('available')}")
    s, _ = _call(INVENTORY, "GET", f"/positions/W1/{sku}")
    check("S04-w1-untouched", s == 404, f"{s}")

    print(f"ALL PASS ({PASS_COUNT} checks)", flush=True)


if __name__ == "__main__":
    main()
