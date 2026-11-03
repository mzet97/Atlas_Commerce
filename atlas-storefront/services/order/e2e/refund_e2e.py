#!/usr/bin/env python3
"""M6 refund drill: ops refund, CONFIRMED cancel, RMA approve (live, stdlib).

Scenarios (compose defaults: APPROVAL_THRESHOLD_MINOR=100000, so small
orders take the single-analyst path):
R01 checkout CONFIRMED -> erin refunds via Control -> intent refunded,
    payment projection converges (refunded_minor == total).
R02 second checkout -> gina cancels via Control (money leg: refund first)
    -> order CANCELLED, intent refunded.
R03 third checkout -> RMA requested + approved via Control -> intent
    partially refunded, W1 restocked by the ledger.
Exit nonzero on first failed assertion; prints PASS lines.
"""

from __future__ import annotations

import json
import time
import urllib.request

CONTROL = "http://localhost:8102"
ORDER = "http://localhost:8106"
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


def _checkout(tag: str, price_minor: int) -> tuple[str, str, int]:
    """Own product/offer/stock -> CONFIRMED checkout. Returns (order_id,
    intent_id, charged_total)."""
    cara = {"Authorization": f"Bearer {_token('cara.catalog', 'cara-dev-only')}"}
    s, product = _call(CONTROL, "POST", "/ops/products", {
        "title": {"pt-BR": f"Refundo E2E {tag}"},
        "idempotency_key": f"p-{tag}", "correlation_id": f"c-{tag}"}, cara)
    assert s == 201, product
    sku = product["id"]
    s, _ = _call(CONTROL, "POST", f"/ops/products/{sku}/publish",
                 {"expected_version": 1, "correlation_id": f"c-{tag}"}, cara)
    assert s == 200, _
    s, offer = _call(CONTROL, "POST", "/ops/offers", {
        "sku_id": sku, "seller_id": "atlas", "market_id": "BR", "channel": "web",
        "currency": "BRL", "price_minor": price_minor,
        "idempotency_key": f"o-{tag}", "correlation_id": f"c-{tag}"}, cara)
    assert s == 201, offer
    s, _ = _call(INVENTORY, "POST", "/positions/receive", {
        "warehouse_id": "W1", "sku_id": sku, "quantity": 5,
        "correlation_id": f"c-{tag}"})
    assert s == 201, _
    s, cart = _call(ORDER, "POST", "/carts", {
        "customer_id": "e2e", "correlation_id": f"c-{tag}"})
    assert s == 201, cart
    _call(ORDER, "POST", f"/carts/{cart['id']}/items", {
        "offer_id": offer["id"], "quantity": 1, "correlation_id": f"c-{tag}"})
    quote: dict = {}
    deadline = time.time() + 90
    while time.time() < deadline:
        s, quote = _call(ORDER, "POST", f"/carts/{cart['id']}/quote")
        if s == 201:
            break
        time.sleep(2)
    assert quote.get("id"), quote
    s, order = _call(ORDER, "POST", "/checkouts", {
        "quote_id": quote["id"], "customer_id": "e2e", "card_last4": "4242",
        "idempotency_key": f"k-{tag}", "correlation_id": f"c-{tag}"}, timeout=90)
    assert s == 201 and order.get("status") == "CONFIRMED", (s, order)
    return order["id"], str(order["payment_intent_id"]), int(order["total_minor"])


def main() -> None:
    erin = {"Authorization": f"Bearer {_token('erin.finance', 'erin-dev-only')}"}
    gina = {"Authorization": f"Bearer {_token('gina.fulfillment', 'gina-dev-only')}"}

    # R01: direct ops refund below the value threshold.
    tag = f"{time.time_ns()}"
    _order_id, intent_id, total = _checkout(tag, 500)
    s, refunded = _call(CONTROL, "POST",
                        f"/ops/finance/payments/{intent_id}/refund",
                        {"reason": "drill R01", "correlation_id": f"c-{tag}"},
                        erin)
    check("R01-refund-201", s == 201 and refunded.get("refunded_minor") == total,
          f"{s} refunded={refunded.get('refunded_minor')} total={total}")

    # R02: CONFIRMED cancel with the refund leg first.
    tag2 = f"{time.time_ns()}"
    order2, intent2, total2 = _checkout(tag2, 700)
    s, cancelled = _call(CONTROL, "POST", f"/ops/orders/{order2}/cancel",
                         {"correlation_id": f"c-{tag2}"}, gina)
    check("R02-cancelled", s == 200 and cancelled.get("status") == "CANCELLED",
          f"{s} {cancelled.get('status')}")
    s, intent = _call(PAYMENT, "GET", f"/intents/{intent2}")
    check("R02-refunded", s == 200 and intent.get("refunded_minor") == total2,
          str(intent.get("refunded_minor")))

    # R03: RMA approve refunds + restocks.
    tag3 = f"{time.time_ns()}"
    order3, intent3, _total3 = _checkout(tag3, 900)
    s, sku_view = _call(CONTROL, "GET", f"/ops/fulfillment/orders/{order3}",
                        None, gina)
    lines = sku_view.get("lines") or []
    sku_id = str(lines[0]["sku_id"]) if lines else ""
    s, rma = _call(ORDER, "POST", "/returns", {
        "order_id": order3,
        "lines": [{"sku_id": sku_id, "quantity": 1, "price_minor": 900}],
        "reason": "drill R03"})
    check("R03-requested", s == 201 and rma.get("status") == "REQUESTED",
          f"{s}")
    s, approved = _call(CONTROL, "POST",
                        f"/ops/fulfillment/returns/{rma['id']}/approve",
                        {"correlation_id": f"c-{tag3}"}, gina)
    check("R03-approved", s == 200 and approved.get("status") == "APPROVED",
          f"{s} {approved.get('status')}")
    s, intent = _call(PAYMENT, "GET", f"/intents/{intent3}")
    check("R03-partial-refund", s == 200 and intent.get("refunded_minor") == 900,
          str(intent.get("refunded_minor")))
    s, position = _call(INVENTORY, "GET", f"/positions/W1/{sku_id}")
    check("R03-restocked", s == 200 and position.get("on_hand", 0) >= 5,
          f"s={s} sku={sku_id} body={str(position)[:120]}")

    print(f"ALL PASS ({PASS_COUNT} checks)", flush=True)


if __name__ == "__main__":
    main()
