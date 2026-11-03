"""Control pricing/stock tests: ABAC scopes + forwarding (live stack)."""

from __future__ import annotations

import pytest_asyncio
from conftest import unique, user_token
from httpx import ASGITransport, AsyncClient

from atlas_control.main import app as control_app


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


def _offer_body(key: str, market: str = "BR") -> dict[str, object]:
    return {
        "sku_id": unique("sku"),
        "seller_id": "atlas",
        "market_id": market,
        "channel": "web",
        "currency": "BRL",
        "price_minor": 1999,
        "idempotency_key": key,
        "correlation_id": unique("corr"),
    }


class TestPricingOpsScope:
    async def test_editor_publishes_in_granted_market(self, api: AsyncClient) -> None:
        """Given catalog_editor + BR grant / When publish BR / Then 201."""
        token = await user_token("cara.catalog", "cara-dev-only")
        response = await api.post(
            "/ops/offers", json=_offer_body(unique("idem")), headers=_auth(token)
        )
        assert response.status_code == 201, response.text
        assert response.json()["status"] == "ACTIVE"

    async def test_editor_denied_outside_granted_market(self, api: AsyncClient) -> None:
        """Given grants only BR / When publish US / Then 403 + audit."""
        import os

        import asyncpg

        token = await user_token("cara.catalog", "cara-dev-only")
        corr = unique("corr")
        body = _offer_body(unique("idem"), market="US")
        body["correlation_id"] = corr
        response = await api.post("/ops/offers", json=body, headers=_auth(token))
        assert response.status_code == 403
        pool = await asyncpg.create_pool(os.environ["CONTROL_PG_DSN"])
        assert pool is not None
        row = await pool.fetchrow(
            "SELECT action, result FROM admin_actions WHERE correlation_id = $1",
            corr,
        )
        await pool.close()
        assert row is not None
        assert (row["action"], row["result"]) == ("offer:publish", "denied")


class TestStockOpsScope:
    async def test_editor_receives_in_granted_warehouse(self, api: AsyncClient) -> None:
        """Given inventory_operator + W1 grant / When receive / Then 201."""
        token = await user_token("cara.catalog", "cara-dev-only")
        response = await api.post(
            "/ops/stock/receive",
            json={
                "warehouse_id": "W1",
                "sku_id": unique("sku"),
                "quantity": 10,
                "correlation_id": unique("corr"),
            },
            headers=_auth(token),
        )
        assert response.status_code == 201, response.text
        assert response.json()["on_hand"] == 10

    async def test_editor_denied_outside_granted_warehouse(self, api: AsyncClient) -> None:
        """Given grants only W1 / When receive in W9 / Then 403."""
        token = await user_token("cara.catalog", "cara-dev-only")
        response = await api.post(
            "/ops/stock/receive",
            json={
                "warehouse_id": "W9",
                "sku_id": unique("sku"),
                "quantity": 10,
                "correlation_id": unique("corr"),
            },
            headers=_auth(token),
        )
        assert response.status_code == 403
