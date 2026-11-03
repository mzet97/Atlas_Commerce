"""Order cancel ops (M4): threshold direct-exec + four-eyes above it."""

from __future__ import annotations

import os

import pytest
import pytest_asyncio
from conftest import unique, user_token
from httpx import ASGITransport, AsyncClient
from motor.motor_asyncio import AsyncIOMotorClient

from atlas_control.main import app as control_app

OWNER_MONGO = os.getenv(
    "OWNER_MONGO_URL",
    "mongodb://localhost:27017/order?replicaSet=rs0&directConnection=true",
)


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


async def _seed_owner_order(total_minor: int = 1000) -> str:
    """Insert a PENDING order straight into the owner DB (order-api view)."""
    client = AsyncIOMotorClient(OWNER_MONGO, serverSelectionTimeoutMS=5000)
    order_id = f"o-{unique('ctl')}"
    await client["order"].orders.insert_one(
        {
            "_id": order_id,
            "version": 1,
            "status": "PENDING",
            "quote_id": f"q-{unique('q')}",
            "customer_id": unique("cust"),
            "lines": [],
            "total_minor": total_minor,
            "currency": "BRL",
            "card_last4": "4242",
            "idempotency_key": unique("idem"),
            "reservation_ids": [],
            "created_at": "2026-11-03T00:00:00+00:00",
        }
    )
    client.close()
    return order_id


class TestOrderCancel:
    async def test_below_threshold_executes_immediately(
        self, api: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Given tiny order + huge threshold / When gina cancels / Then 200."""
        monkeypatch.setenv("APPROVAL_THRESHOLD_MINOR", "1000000000")
        gina = await user_token("gina.fulfillment", "gina-dev-only")
        order_id = await _seed_owner_order(total_minor=1000)
        response = await api.post(
            f"/ops/orders/{order_id}/cancel",
            json={"correlation_id": unique("corr")},
            headers=_auth(gina),
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "CANCELLED"

    async def test_above_threshold_takes_four_eyes(
        self, api: AsyncClient
    ) -> None:
        """Given threshold 1 / When gina cancels / Then filed 202; felix executes."""
        gina = await user_token("gina.fulfillment", "gina-dev-only")
        felix = await user_token("felix.finance", "felix-dev-only")
        order_id = await _seed_owner_order(total_minor=1000)
        filed = await api.post(
            f"/ops/orders/{order_id}/cancel",
            json={"correlation_id": unique("corr")},
            headers=_auth(gina),
        )
        assert filed.status_code == 202, filed.text
        assert filed.json()["resource_type"] == "order"
        self_check = await api.post(
            f"/ops/finance/approvals/{filed.json()['approval_id']}/approve",
            json={"correlation_id": unique("corr")},
            headers=_auth(gina),
        )
        assert self_check.status_code == 403
        approved = await api.post(
            f"/ops/finance/approvals/{filed.json()['approval_id']}/approve",
            json={"correlation_id": unique("corr")},
            headers=_auth(felix),
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["status"] == "EXECUTED"
        assert approved.json()["target"]["status"] == "CANCELLED"

    async def test_customer_is_403_audited(self, api: AsyncClient) -> None:
        """Given alice.customer / When cancel / Then 403 + audit denied."""
        import asyncpg

        alice = await user_token("alice.customer", "alice-dev-only")
        order_id = await _seed_owner_order()
        corr = unique("corr")
        response = await api.post(
            f"/ops/orders/{order_id}/cancel",
            json={"correlation_id": corr},
            headers=_auth(alice),
        )
        assert response.status_code == 403
        pool = await asyncpg.create_pool(os.environ["CONTROL_PG_DSN"])
        assert pool is not None
        row = await pool.fetchrow(
            "SELECT result FROM admin_actions WHERE action = 'order:cancel'"
            " AND correlation_id = $1",
            corr,
        )
        await pool.close()
        assert row is not None and row["result"] == "denied"

    async def test_duplicate_pending_is_409(self, api: AsyncClient) -> None:
        """Given filed cancel / When filed again / Then 409."""
        gina = await user_token("gina.fulfillment", "gina-dev-only")
        order_id = await _seed_owner_order(total_minor=1000)
        first = await api.post(
            f"/ops/orders/{order_id}/cancel",
            json={"correlation_id": unique("corr")},
            headers=_auth(gina),
        )
        assert first.status_code == 202
        second = await api.post(
            f"/ops/orders/{order_id}/cancel",
            json={"correlation_id": unique("corr")},
            headers=_auth(gina),
        )
        assert second.status_code == 409
