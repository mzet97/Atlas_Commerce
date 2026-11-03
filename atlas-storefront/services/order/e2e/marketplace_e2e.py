#!/usr/bin/env python3
"""M10 marketplace drill: tenancy, concurrent offers, buybox, settlement.

M01 iam_admin registers seller-acme via Control.
M02 paul.seller publishes seller-acme offer on the SAME sku as the 1P
    atlas offer (lower price) -> 201 ACTIVE (concurrent offers).
M03 paul tries seller-outro -> 403 audited (zero tenant violation).
M04 storefront buybox shows the cheapest price (R$ 7,90 vs R$ 12,00).
M05 checkout CONFIRMED; finance computes split settlement (commission 10%)
    -> per-seller bruto/comissão/líquido correct; replay idempotent.
Exit nonzero on first failed assertion; prints PASS lines.
"""

from __future__ import annotations

import json
import time
import urllib.request

CONTROL = "http://localhost:8102"
ORDER = "http://localhost:8106"
INVENTORY = "http://localhost:8104"
KEYCLOAK = "http://localhost:8180"
STORE = "http://localhost:3100"

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
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode())


def _token(user: str, pwd: str) -> str:
    data = f"client_id=atlas-storefront&username={user}&password={pwd}" \
        f"&grant_type=password".encode()
    req = urllib.request.Request(
        f"{KEYCLOAK}/realms/atlas/protocol/openid-connect/token", data=data,
        method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())["access_token"]


def main() -> None:
    boss = {"Authorization": f"Bearer {_token('boss.admin', 'boss-dev-only')}"}
    cara = {"Authorization": f"Bearer {_token('cara.catalog', 'cara-dev-only')}"}
    paul = {"Authorization": f"Bearer {_token('paul.seller', 'paul-dev-only')}"}
    erin = {"Authorization": f"Bearer {_token('erin.finance', 'erin-dev-only')}"}
    tag = f"{time.time_ns()}"

    # M01: tenant onboarding.
    s, seller = _call(CONTROL, "POST", "/ops/sellers", {
        "seller_id": "seller-acme", "name": "Acme 3P",
        "correlation_id": f"c-{tag}"}, boss)
    check("M01-seller-registered", s == 201 and seller.get("seller_id") == "seller-acme",
          f"{s}")

    # Shared product (1P publishes it, both sellers offer it).
    s, product = _call(CONTROL, "POST", "/ops/products", {
        "title": {"pt-BR": f"Kit Chá M10 {tag}"},
        "idempotency_key": f"p-{tag}", "correlation_id": f"c-{tag}"}, cara)
    assert s == 201, product
    sku = product["id"]
    s, _ = _call(CONTROL, "POST", f"/ops/products/{sku}/publish",
                 {"expected_version": 1, "correlation_id": f"c-{tag}"}, cara)
    assert s == 200, _

    # 1P offer (atlas) at 1200 + stock for checkout.
    s, offer_1p = _call(CONTROL, "POST", "/ops/offers", {
        "sku_id": sku, "seller_id": "atlas", "market_id": "BR", "channel": "web",
        "currency": "BRL", "price_minor": 1200,
        "idempotency_key": f"o1-{tag}", "correlation_id": f"c-{tag}"}, cara)
    assert s == 201, offer_1p
    s, _ = _call(INVENTORY, "POST", "/positions/receive", {
        "warehouse_id": "W1", "sku_id": sku, "quantity": 50,
        "correlation_id": f"c-{tag}"})
    assert s == 201, _

    # M02: 3P concurrent offer (seller-acme, cheaper).
    s, offer_3p = _call(CONTROL, "POST", "/ops/offers", {
        "sku_id": sku, "seller_id": "seller-acme", "market_id": "BR",
        "channel": "web", "currency": "BRL", "price_minor": 790,
        "idempotency_key": f"o2-{tag}", "correlation_id": f"c-{tag}"}, paul)
    check("M02-concurrent-3p-offer", s == 201, f"{s}")

    # M03: cross-tenant refusal.
    s, denied = _call(CONTROL, "POST", "/ops/offers", {
        "sku_id": sku, "seller_id": "seller-outro", "market_id": "BR",
        "channel": "web", "currency": "BRL", "price_minor": 100,
        "idempotency_key": f"o3-{tag}", "correlation_id": f"c-{tag}"}, paul)
    check("M03-cross-tenant-403", s == 403, f"{s}")

    # M04: buybox shows the cheapest (790) — poll projection convergence.
    bought_box = ""
    deadline = time.time() + 90
    while time.time() < deadline:
        html = urllib.request.urlopen(f"{STORE}/", timeout=10).read().decode()
        if "7,90" in html:
            bought_box = "7,90"
            break
        time.sleep(2)
    check("M04-buybox-cheapest", bought_box == "7,90",
          f"html has 7,90={bool(bought_box)}")

    # Checkout the 3P (cheapest) offer: add items by offer id via owner API.
    s, cart = _call(ORDER, "POST", "/carts", {
        "customer_id": f"mkt-{tag}", "correlation_id": f"c-{tag}"})
    assert s == 201, cart
    s, _ = _call(ORDER, "POST", f"/carts/{cart['id']}/items", {
        "offer_id": offer_3p["id"], "quantity": 2, "correlation_id": f"c-{tag}"})
    assert s == 200, _
    quote: dict = {}
    deadline = time.time() + 90
    while time.time() < deadline:
        s, quote = _call(ORDER, "POST", f"/carts/{cart['id']}/quote")
        if s == 201:
            break
        time.sleep(2)
    assert quote.get("id"), quote
    s, order = _call(ORDER, "POST", "/checkouts", {
        "quote_id": quote["id"], "customer_id": f"mkt-{tag}", "card_last4": "4242",
        "idempotency_key": f"k-{tag}", "correlation_id": f"c-{tag}"}, timeout=90)
    check("M05-checkout-confirmed",
          s == 201 and order.get("status") == "CONFIRMED", f"{s}")

    # M05b: settlement split — commission 10% on the 3P line.
    deadline = time.time() + 90
    settle: dict = {}
    while time.time() < deadline:
        s, settle = _call(CONTROL, "POST",
                          f"/ops/finance/settlements/{order['id']}",
                          {"correlation_id": f"c-{tag}"}, erin)
        if s == 200:
            break
        time.sleep(2)
    rows = settle.get("settlements", [])
    acme = next((r for r in rows if r["seller_id"] == "seller-acme"), {})
    check("M05-settlement-split",
          s == 200 and acme.get("gross_minor") == 1580
          and acme.get("commission_minor") == 158
          and acme.get("net_minor") == 1422,
          str(acme))
    s, listed = _call(CONTROL, "GET",
                      f"/ops/finance/settlements/{order['id']}", None, erin)
    check("M05-settlement-replay", s == 200 and
          any(r["seller_id"] == "seller-acme" for r in listed), f"{s} {listed}")

    print(f"ALL PASS ({PASS_COUNT} checks)", flush=True)


if __name__ == "__main__":
    main()
