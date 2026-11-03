"""Four-eyes tests: maker files, a DIFFERENT checker decides (live stack)."""

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


async def _unknown_intent() -> dict[str, object]:
    async with httpx.AsyncClient(timeout=30) as http:
        response = await http.post(
            f"{PAYMENT_API_URL}/intents",
            json={
                "order_id": unique("order"),
                "customer_id": unique("cust"),
                "amount_minor": 999,
                "currency": "BRL",
                "card_last4": "4242",
                "idempotency_key": unique("idem"),
                "correlation_id": unique("corr"),
            },
        )
        assert response.status_code == 201, response.text
        parsed = response.json()
        assert isinstance(parsed, dict) and parsed["status"] == "UNKNOWN"
        return parsed


async def _request(api: AsyncClient, token: str, intent_id: str) -> dict[str, object]:
    response = await api.post(
        f"/ops/finance/payments/{intent_id}/reconcile",
        json={"correlation_id": unique("corr")},
        headers=_auth(token),
    )
    assert response.status_code == 202, response.text
    parsed = response.json()
    assert isinstance(parsed, dict)
    return parsed


class TestFourEyes:
    async def test_self_approval_is_denied(self, api: AsyncClient) -> None:
        """Given maker / When maker approves own / Then 403 + audit denied."""
        import asyncpg

        maker = await user_token("erin.finance", "erin-dev-only")
        intent = await _unknown_intent()
        approval = await _request(api, maker, str(intent["id"]))
        response = await api.post(
            f"/ops/finance/approvals/{approval['approval_id']}/approve",
            json={"correlation_id": unique("corr")},
            headers=_auth(maker),
        )
        assert response.status_code == 403
        pool = await asyncpg.create_pool(os.environ["CONTROL_PG_DSN"])
        assert pool is not None
        row = await pool.fetchrow(
            "SELECT result FROM admin_actions WHERE action = 'approval:decide'"
            " AND resource_id = $1 ORDER BY id DESC LIMIT 1",
            approval["approval_id"],
        )
        await pool.close()
        assert row is not None and row["result"] == "denied"

    async def test_checker_approves_and_executes(self, api: AsyncClient) -> None:
        """Given PENDING / When other analyst approves / Then EXECUTED + moved."""
        maker = await user_token("erin.finance", "erin-dev-only")
        checker = await user_token("felix.finance", "felix-dev-only")
        intent = await _unknown_intent()
        approval = await _request(api, maker, str(intent["id"]))
        response = await api.post(
            f"/ops/finance/approvals/{approval['approval_id']}/approve",
            json={"correlation_id": unique("corr")},
            headers=_auth(checker),
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "EXECUTED"
        assert body["intent"]["status"] == "AUTHORIZED"  # owner truth applied
        pending = await api.get("/ops/finance/approvals/pending",
                                headers=_auth(checker))
        assert approval["approval_id"] not in [
            row["approval_id"] for row in pending.json()]

    async def test_duplicate_pending_is_409(self, api: AsyncClient) -> None:
        """Given PENDING / When filed again / Then 409, single request."""
        maker = await user_token("erin.finance", "erin-dev-only")
        intent = await _unknown_intent()
        await _request(api, maker, str(intent["id"]))
        response = await api.post(
            f"/ops/finance/payments/{intent['id']}/reconcile",
            json={"correlation_id": unique("corr")},
            headers=_auth(maker),
        )
        assert response.status_code == 409

    async def test_checker_rejects(self, api: AsyncClient) -> None:
        """Given PENDING / When checker rejects / Then REJECTED, nothing moves."""
        maker = await user_token("erin.finance", "erin-dev-only")
        checker = await user_token("felix.finance", "felix-dev-only")
        intent = await _unknown_intent()
        approval = await _request(api, maker, str(intent["id"]))
        response = await api.post(
            f"/ops/finance/approvals/{approval['approval_id']}/reject",
            json={"correlation_id": unique("corr")},
            headers=_auth(checker),
        )
        assert response.status_code == 200
        assert response.json()["status"] == "REJECTED"
        current = await api.get(
            f"/ops/finance/payments/{intent['id']}", headers=_auth(maker)
        )
        assert current.json()["status"] == "UNKNOWN"
