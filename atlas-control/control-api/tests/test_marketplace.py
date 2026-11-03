"""M10 marketplace: seller tenancy, concurrent offers, settlement split."""

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


def _offer_body(key: str, seller: str, price: int = 1000) -> dict[str, object]:
    return {
        "sku_id": unique("sku"),
        "seller_id": seller,
        "market_id": "BR",
        "channel": "web",
        "currency": "BRL",
        "price_minor": price,
        "idempotency_key": key,
        "correlation_id": unique("corr"),
    }


class TestSellerTenancy:
    async def test_admin_registers_seller(self, api: AsyncClient) -> None:
        """Given iam_admin / When register / Then 201 + listed."""
        boss = await user_token("boss.admin", "boss-dev-only")
        await api.post(
            "/ops/sellers",
            json={"seller_id": "seller-acme", "name": "Acme 3P",
                  "correlation_id": unique("corr")},
            headers=_auth(boss),
        )
        listed = await api.get("/ops/sellers", headers=_auth(boss))
        assert "seller-acme" in [r["seller_id"] for r in listed.json()]

    async def test_seller_publishes_in_own_tenant(self, api: AsyncClient) -> None:
        """Given paul + grant (seller-acme, BR) / When publish / Then 201."""
        paul = await user_token("paul.seller", "paul-dev-only")
        response = await api.post(
            "/ops/offers",
            json=_offer_body(unique("idem"), "seller-acme"),
            headers=_auth(paul),
        )
        assert response.status_code == 201, response.text
        assert response.json()["status"] == "ACTIVE"

    async def test_cross_tenant_is_403_audited(self, api: AsyncClient) -> None:
        """Given paul (seller-acme only) / When publish seller-outro / Then 403."""
        import os

        import asyncpg

        paul = await user_token("paul.seller", "paul-dev-only")
        corr = unique("corr")
        body = _offer_body(unique("idem"), "seller-outro")
        body["correlation_id"] = corr
        response = await api.post("/ops/offers", json=body, headers=_auth(paul))
        assert response.status_code == 403
        pool = await asyncpg.create_pool(os.environ["CONTROL_PG_DSN"])
        assert pool is not None
        row = await pool.fetchrow(
            "SELECT result FROM admin_actions WHERE correlation_id = $1", corr
        )
        await pool.close()
        assert row is not None and row["result"] == "denied"

    async def test_onep_regression_unaffected(self, api: AsyncClient) -> None:
        """Given cara.catalog / When publish atlas 1P / Then 201 (M2 gate)."""
        cara = await user_token("cara.catalog", "cara-dev-only")
        response = await api.post(
            "/ops/offers",
            json=_offer_body(unique("idem"), "atlas"),
            headers=_auth(cara),
        )
        assert response.status_code == 201, response.text
