"""Coupon ops tests: pricing_manager creates, others 403 + audited."""

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


class TestCouponOps:
    async def test_pricing_manager_creates_coupon(self, api: AsyncClient) -> None:
        """Given pam.pricing + BR grant / When create market-scoped / Then 201."""
        token = await user_token("pam.pricing", "pam-dev-only")
        response = await api.post(
            "/ops/coupons",
            json={
                "code": unique("CP"),
                "kind": "PERCENT",
                "value": 10,
                "market_id": "BR",
                "correlation_id": unique("corr"),
            },
            headers=_auth(token),
        )
        assert response.status_code == 201, response.text
        assert response.json()["active"] is True

    async def test_catalog_editor_is_403_audited(self, api: AsyncClient) -> None:
        """Given cara.catalog (no pricing role) / When create / Then 403."""
        import os

        import asyncpg

        token = await user_token("cara.catalog", "cara-dev-only")
        corr = unique("corr")
        response = await api.post(
            "/ops/coupons",
            json={
                "code": unique("CP"),
                "kind": "FIXED",
                "value": 100,
                "correlation_id": corr,
            },
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
        assert (row["action"], row["result"]) == ("coupon:manage", "denied")

    async def test_list_and_deactivate(self, api: AsyncClient) -> None:
        """Given created coupon / When list + deactivate / Then states persist."""
        token = await user_token("pam.pricing", "pam-dev-only")
        code = unique("CP")
        created = await api.post(
            "/ops/coupons",
            json={
                "code": code,
                "kind": "FIXED",
                "value": 500,
                "correlation_id": unique("corr"),
            },
            headers=_auth(token),
        )
        assert created.status_code == 201, created.text
        listed = await api.get("/ops/coupons", headers=_auth(token))
        assert listed.status_code == 200
        assert code in [c["code"] for c in listed.json()]
        retired = await api.post(
            f"/ops/coupons/{code}/deactivate",
            json={"correlation_id": unique("corr")},
            headers=_auth(token),
        )
        assert retired.status_code == 200, retired.text
        assert retired.json()["active"] is False
