"""Refund + returns ops (M6): threshold, four-eyes with payload, queues."""

from __future__ import annotations

import os

import httpx
import pytest
import pytest_asyncio
from conftest import unique, user_token
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("PAYMENT_API_URL", "http://localhost:8105")
os.environ.setdefault("ORDER_API_URL", "http://localhost:8106")

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


async def _authorized_intent(amount: int = 5000) -> dict[str, object]:
    """AUTHORIZED intent on the live payment owner (4242 approves)."""
    async with httpx.AsyncClient(timeout=30) as http:
        response = await http.post(
            f"{PAYMENT_API_URL}/intents",
            json={
                "order_id": unique("order"),
                "customer_id": unique("cust"),
                "amount_minor": amount,
                "currency": "BRL",
                "card_last4": "4242",
                "idempotency_key": unique("idem"),
                "correlation_id": unique("corr"),
            },
        )
        assert response.status_code == 201, response.text
        parsed = response.json()
        assert isinstance(parsed, dict)
        return parsed


class TestRefundOps:
    async def test_below_threshold_executes_directly(
        self, api: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Given huge threshold / When erin refunds / Then 201 refunded now."""
        monkeypatch.setenv("APPROVAL_THRESHOLD_MINOR", "1000000000")
        erin = await user_token("erin.finance", "erin-dev-only")
        intent = await _authorized_intent(amount=500)
        response = await api.post(
            f"/ops/finance/payments/{intent['id']}/refund",
            json={"reason": "goodwill", "correlation_id": unique("corr")},
            headers=_auth(erin),
        )
        assert response.status_code == 201, response.text
        assert response.json()["refunded_minor"] == 500

    async def test_above_threshold_four_eyes_payload(
        self, api: AsyncClient
    ) -> None:
        """Given threshold 1 / When erin refunds 5000 / Then filed 202 with
        payload; felix approves and the refund executes."""
        erin = await user_token("erin.finance", "erin-dev-only")
        felix = await user_token("felix.finance", "felix-dev-only")
        intent = await _authorized_intent(amount=5000)
        filed = await api.post(
            f"/ops/finance/payments/{intent['id']}/refund",
            json={"correlation_id": unique("corr")},
            headers=_auth(erin),
        )
        assert filed.status_code == 202, filed.text
        body = filed.json()
        assert body["action"] == "payment:refund"
        assert body["payload"]["idempotency_key"].startswith("refund-")
        self_check = await api.post(
            f"/ops/finance/approvals/{body['approval_id']}/approve",
            json={"correlation_id": unique("corr")},
            headers=_auth(erin),
        )
        assert self_check.status_code == 403
        approved = await api.post(
            f"/ops/finance/approvals/{body['approval_id']}/approve",
            json={"correlation_id": unique("corr")},
            headers=_auth(felix),
        )
        assert approved.status_code in (200, 201), approved.text
        assert approved.json()["status"] == "EXECUTED"
        assert approved.json()["target"]["refunded_minor"] == 5000


class TestReturnsOps:
    async def test_returns_queue_reads_owner(self, api: AsyncClient) -> None:
        """Given gina / When listing returns / Then owner list passes through."""
        gina = await user_token("gina.fulfillment", "gina-dev-only")
        response = await api.get(
            "/ops/fulfillment/returns", headers=_auth(gina)
        )
        assert response.status_code == 200, response.text
        assert isinstance(response.json(), list)
