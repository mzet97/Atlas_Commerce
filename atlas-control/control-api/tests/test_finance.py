"""Finance ops tests: role gate + owner view + reconcile trigger (live stack)."""

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
os.environ.setdefault(
    "CONTROL_PG_DSN", "postgresql://postgres:atlas-pg-dev-only@localhost:5432/control"
)

from conftest import unique, user_token

from atlas_control.main import app as control_app

PAYMENT_API_URL = os.environ["PAYMENT_API_URL"]


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


async def _create_intent(amount: int = 1999, card: str = "4242") -> dict[str, object]:
    async with httpx.AsyncClient(timeout=30) as http:
        response = await http.post(
            f"{PAYMENT_API_URL}/intents",
            json={
                "order_id": unique("order"),
                "customer_id": unique("cust"),
                "amount_minor": amount,
                "currency": "BRL",
                "card_last4": card,
                "idempotency_key": unique("idem"),
                "correlation_id": unique("corr"),
            },
        )
        assert response.status_code == 201, response.text
        parsed = response.json()
        assert isinstance(parsed, dict)
        return parsed


class TestFinanceGate:
    async def test_no_token_is_401(self, api: AsyncClient) -> None:
        """Given anonymous / When viewing payment / Then 401."""
        response = await api.get("/ops/finance/payments/pi-nope")
        assert response.status_code == 401

    async def test_customer_cannot_view(self, api: AsyncClient) -> None:
        """Given customer JWT / When viewing / Then 403 + audited."""
        import asyncpg

        token = await user_token("alice.customer", "alice-dev-only")
        corr = unique("corr")
        response = await api.get(
            "/ops/finance/payments/pi-nope",
            headers={**_auth(token), "X-Correlation-Id": corr},
        )
        assert response.status_code == 403
        pool = await asyncpg.create_pool(os.environ["CONTROL_PG_DSN"])
        assert pool is not None
        row = await pool.fetchrow(
            "SELECT action, result FROM admin_actions WHERE correlation_id = $1",
            "view-pi-nope",
        )
        await pool.close()
        assert row is not None
        assert (row["action"], row["result"]) == ("payment:view", "denied")

    async def test_analyst_views_payment(self, api: AsyncClient) -> None:
        """Given finance JWT / When viewing / Then owner view passes through."""
        token = await user_token("erin.finance", "erin-dev-only")
        intent = await _create_intent()
        response = await api.get(
            f"/ops/finance/payments/{intent['id']}", headers=_auth(token)
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "AUTHORIZED"

    async def test_analyst_files_reconcile_request(self, api: AsyncClient) -> None:
        """Given UNKNOWN / When analyst requests / Then 202 PENDING, no move."""
        token = await user_token("erin.finance", "erin-dev-only")
        intent = await _create_intent(amount=1999, card="9999")
        assert intent["status"] == "UNKNOWN"  # PSP 500 keeps ref, truth pending
        response = await api.post(
            f"/ops/finance/payments/{intent['id']}/reconcile",
            json={"correlation_id": unique("corr")},
            headers=_auth(token),
        )
        assert response.status_code == 202, response.text
        body = response.json()
        assert (body["status"], body["intent_id"]) == ("PENDING", intent["id"])
        current = await api.get(
            f"/ops/finance/payments/{intent['id']}", headers=_auth(token)
        )
        assert current.json()["status"] == "UNKNOWN"  # nothing moved yet
