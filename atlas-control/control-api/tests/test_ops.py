"""Control ops tests: auth gate + owner forwarding + audit (live stack)."""

from __future__ import annotations

import os

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("KEYCLOAK_ISSUER", "http://localhost:8180/realms/atlas")
os.environ.setdefault("CATALOG_API_URL", "http://localhost:8101")
os.environ.setdefault(
    "CONTROL_PG_DSN", "postgresql://postgres:atlas-pg-dev-only@localhost:5432/control"
)

from conftest import unique, user_token

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


class TestCatalogOpsGate:
    async def test_no_token_is_401(self, api: AsyncClient) -> None:
        """Given anonymous / When POST valid body / Then 401 (auth first)."""
        response = await api.post(
            "/ops/products",
            json={
                "title": {"pt-BR": "X"},
                "idempotency_key": unique("idem"),
                "correlation_id": unique("corr"),
            },
        )
        assert response.status_code == 401

    async def test_customer_cannot_create_product(self, api: AsyncClient) -> None:
        """Given customer JWT / When create / Then 403 (and audited)."""
        token = await user_token("alice.customer", "alice-dev-only")
        response = await api.post(
            "/ops/products",
            json={
                "title": {"pt-BR": "X"},
                "idempotency_key": unique("idem"),
                "correlation_id": unique("corr"),
            },
            headers=_auth(token),
        )
        assert response.status_code == 403

    async def test_editor_creates_and_publishes(self, api: AsyncClient) -> None:
        """Given catalog_editor JWT / When create+publish / Then 201+200."""
        token = await user_token("cara.catalog", "cara-dev-only")
        key = unique("idem")
        created = await api.post(
            "/ops/products",
            json={
                "title": {"pt-BR": "Café Control"},
                "idempotency_key": key,
                "correlation_id": unique("corr"),
            },
            headers=_auth(token),
        )
        assert created.status_code == 201, created.text
        product_id = created.json()["id"]
        published = await api.post(
            f"/ops/products/{product_id}/publish",
            json={"expected_version": 1, "correlation_id": unique("corr")},
            headers=_auth(token),
        )
        assert published.status_code == 200, published.text
        assert published.json()["status"] == "PUBLISHED"

    async def test_denied_attempt_is_audited(self, api: AsyncClient) -> None:
        """Given customer attempt / When denied / Then audit row exists."""
        import asyncpg

        token = await user_token("alice.customer", "alice-dev-only")
        corr = unique("corr")
        response = await api.post(
            "/ops/products",
            json={
                "title": {"pt-BR": "Y"},
                "idempotency_key": unique("idem"),
                "correlation_id": corr,
            },
            headers=_auth(token),
        )
        assert response.status_code == 403
        pool = await asyncpg.create_pool(os.environ["CONTROL_PG_DSN"])
        assert pool is not None
        row = await pool.fetchrow(
            "SELECT actor_sub, action, result FROM admin_actions WHERE correlation_id = $1",
            corr,
        )
        await pool.close()
        assert row is not None
        assert (row["action"], row["result"]) == ("catalog:create", "denied")
