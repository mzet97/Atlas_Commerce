"""PSP fake scenario tests: no network, no randomness, pure ASGI."""
from __future__ import annotations

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from atlas_psp_fake.app import app


@pytest_asyncio.fixture
async def api():
    """Given: in-memory PSP with no callback configured."""
    import atlas_psp_fake.app as psp

    psp.CALLBACK_URL = ""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as http:
        yield http


def _charge(key: str, **over: object) -> dict:
    body: dict[str, object] = {
        "amount_minor": 1999, "currency": "BRL", "card_last4": "4242",
        "idempotency_key": key, "order_id": "order-1",
    }
    body.update(over)
    return body


class TestDeterministicScenarios:
    async def test_default_approves(self, api: AsyncClient) -> None:
        """Given normal card / When charged / Then approved with ref."""
        response = await api.post("/charges", json=_charge("k1"))
        assert response.status_code == 200
        assert response.json()["approved"] is True
        assert "provider_ref" in response.json()

    async def test_declined_card(self, api: AsyncClient) -> None:
        """Given card ending 0002 / When charged / Then 200 declined."""
        response = await api.post("/charges", json=_charge("k2", card_last4="10002"))
        assert response.status_code == 200
        assert response.json() == {
            "approved": False, "code": "DECLINED",
            "provider_ref": response.json()["provider_ref"],
        }

    async def test_duplicate_key_returns_original(self, api: AsyncClient) -> None:
        """Given charged key / When charged again / Then original + duplicate."""
        first = await api.post("/charges", json=_charge("k3"))
        second = await api.post("/charges", json=_charge("k3"))
        assert second.json()["provider_ref"] == first.json()["provider_ref"]
        assert second.json()["duplicate"] is True

    async def test_unknown_resolves_via_status(self, api: AsyncClient) -> None:
        """Given amount 999 / When charged / Then 500 with ref; status approved."""
        response = await api.post("/charges", json=_charge("k4", amount_minor=999))
        assert response.status_code == 500
        ref = response.json()["provider_ref"]
        status = await api.get(f"/charges/{ref}")
        assert status.status_code == 200
        assert status.json()["status"] == "approved"

    async def test_by_key_lookup(self, api: AsyncClient) -> None:
        """Given charged key / When looked up / Then ref returned; 404 unknown."""
        first = await api.post("/charges", json=_charge("k6"))
        found = await api.get("/charges/by-key/k6")
        assert found.status_code == 200
        assert found.json()["provider_ref"] == first.json()["provider_ref"]
        assert (await api.get("/charges/by-key/nope")).status_code == 404

    async def test_unknown_same_key_returns_pending(self, api: AsyncClient) -> None:
        """Given UNKNOWN charged / When same key retried / Then same pending ref."""
        first = await api.post("/charges", json=_charge("k5", amount_minor=999))
        second = await api.post("/charges", json=_charge("k5", amount_minor=999))
        assert second.status_code == 500
        assert second.json()["provider_ref"] == first.json()["provider_ref"]
