"""AI curation tests: allowlist add/remove/list (live stack, atlas PG)."""

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


class TestAllowlist:
    async def test_curator_allows_and_lists(self, api: AsyncClient) -> None:
        """Given editor / When allow + list / Then row present."""
        token = await user_token("cara.catalog", "cara-dev-only")
        offer = unique("offer")
        added = await api.post(
            "/ops/ai/allowlist",
            json={"offer_id": offer, "reason": "test",
                  "correlation_id": unique("corr")},
            headers=_auth(token),
        )
        assert added.status_code == 201, added.text
        listed = await api.get("/ops/ai/allowlist", headers=_auth(token))
        assert offer in [r["offer_id"] for r in listed.json()]

    async def test_customer_cannot_curate(self, api: AsyncClient) -> None:
        """Given customer / When allow / Then 403."""
        token = await user_token("alice.customer", "alice-dev-only")
        response = await api.post(
            "/ops/ai/allowlist",
            json={"offer_id": unique("offer"), "correlation_id": unique("corr")},
            headers=_auth(token),
        )
        assert response.status_code == 403

    async def test_remove_missing_is_404(self, api: AsyncClient) -> None:
        """Given editor / When removing unknown / Then 404."""
        token = await user_token("cara.catalog", "cara-dev-only")
        response = await api.delete(
            "/ops/ai/allowlist/nope", headers=_auth(token)
        )
        assert response.status_code == 404
