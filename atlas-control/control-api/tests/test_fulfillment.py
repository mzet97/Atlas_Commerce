"""Fulfillment ops tests: role gate + owner ship (live stack)."""

from __future__ import annotations

import os

import httpx
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("KEYCLOAK_ISSUER", "http://localhost:8180/realms/atlas")
os.environ.setdefault("CATALOG_API_URL", "http://localhost:8101")
os.environ.setdefault("OFFERS_API_URL", "http://localhost:8103")
os.environ.setdefault("INVENTORY_API_URL", "http://localhost:8104")
os.environ.setdefault("PAYMENT_API_URL", "http://localhost:8105")
os.environ.setdefault("ORDER_API_URL", "http://localhost:8106")
os.environ.setdefault(
    "CONTROL_PG_DSN", "postgresql://postgres:atlas-pg-dev-only@localhost:5432/control"
)

from conftest import unique, user_token

from atlas_control.main import app as control_app

ORDER_API_URL = os.environ["ORDER_API_URL"]


@pytest_asyncio.fixture
async def api():
    """Given: lifespan up (pool + config per test loop)."""
    async with (
        control_app.router.lifespan_context(control_app),
        AsyncClient(transport=ASGITransport(app=control_app), base_url="http://test") as http,
    ):
        yield http


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _setup_offer() -> tuple[str, str]:
    """Product -> publish -> offer(333) -> 20 stock (cara.catalog, W1)."""
    CONTROL, INVENTORY = "http://localhost:8102", "http://localhost:8104"
    async with httpx.AsyncClient(timeout=60) as http:
        token = await user_token("cara.catalog", "cara-dev-only")
        auth = {"Authorization": f"Bearer {token}"}
        tag = unique("m6")
        product = (await http.post(f"{CONTROL}/ops/products", json={
            "title": {"pt-BR": f"Item M6 {tag}"},
            "idempotency_key": f"p-{tag}", "correlation_id": f"c-{tag}"},
            headers=auth)).json()
        sku = product["id"]
        await http.post(f"{CONTROL}/ops/products/{sku}/publish", json={
            "expected_version": 1, "correlation_id": f"c-{tag}"}, headers=auth)
        offer = (await http.post(f"{CONTROL}/ops/offers", json={
            "sku_id": sku, "seller_id": "atlas", "market_id": "BR",
            "channel": "web", "currency": "BRL", "price_minor": 333,
            "idempotency_key": f"o-{tag}", "correlation_id": f"c-{tag}"},
            headers=auth)).json()
        await http.post(f"{INVENTORY}/positions/receive", json={
            "warehouse_id": "W1", "sku_id": sku, "quantity": 20,
            "correlation_id": f"c-{tag}"})
        return offer["id"], sku


async def _confirmed_order_id() -> str:
    """Drive a CONFIRMED order through the real saga (own 333 offer)."""
    offer_id, _ = await _setup_offer()
    async with httpx.AsyncClient(timeout=90) as http:
        cart = (await http.post(f"{ORDER_API_URL}/carts", json={
            "customer_id": unique("cust"), "correlation_id": unique("corr")})).json()
        await http.post(f"{ORDER_API_URL}/carts/{cart['id']}/items", json={
            "offer_id": offer_id, "quantity": 1,
            "correlation_id": unique("corr")})
        import asyncio

        quote: dict[str, object] = {}
        for _ in range(30):
            response = await http.post(
                f"{ORDER_API_URL}/carts/{cart['id']}/quote")
            if response.status_code == 201:
                parsed = response.json()
                assert isinstance(parsed, dict)
                quote = parsed
                break
            await asyncio.sleep(2)
        assert quote.get("id"), quote
        order = (await http.post(f"{ORDER_API_URL}/checkouts", json={
            "quote_id": quote["id"], "customer_id": unique("cust"),
            "card_last4": "4242", "idempotency_key": unique("idem"),
            "correlation_id": unique("corr")})).json()
        assert order["status"] == "CONFIRMED", order
        assert isinstance(order["id"], str)
        return order["id"]


class TestFulfillmentOps:
    async def test_customer_cannot_ship(self, api: AsyncClient) -> None:
        """Given customer JWT / When shipping / Then 403 + audit denied."""
        import asyncpg

        token = await user_token("alice.customer", "alice-dev-only")
        corr = unique("corr")
        response = await api.post(
            "/ops/fulfillment/orders/o-nope/ship",
            json={"correlation_id": corr},
            headers=_auth(token),
        )
        assert response.status_code == 403
        pool = await asyncpg.create_pool(os.environ["CONTROL_PG_DSN"])
        assert pool is not None
        row = await pool.fetchrow(
            "SELECT action, result FROM admin_actions WHERE correlation_id = $1",
            corr,
        )
        await pool.close()
        assert row is not None
        assert (row["action"], row["result"]) == ("order:ship", "denied")

    async def test_operator_ships_confirmed(self, api: AsyncClient) -> None:
        """Given CONFIRMED / When operator ships / Then SHIPPED via owner."""
        token = await user_token("gina.fulfillment", "gina-dev-only")
        order_id = await _confirmed_order_id()
        response = await api.post(
            f"/ops/fulfillment/orders/{order_id}/ship",
            json={"correlation_id": unique("corr")},
            headers=_auth(token),
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "SHIPPED"
