"""Shared fixtures: live Keycloak (host-mapped) for real JWTs."""

from __future__ import annotations

import os

# Traces are proven on the live stack; tests stay signal-only.
os.environ.setdefault("OTEL_SDK_DISABLED", "true")
os.environ.setdefault("KEYCLOAK_ISSUER", "http://localhost:8180/realms/atlas")
os.environ.setdefault("CATALOG_API_URL", "http://localhost:8101")
os.environ.setdefault("OFFERS_API_URL", "http://localhost:8103")
os.environ.setdefault("INVENTORY_API_URL", "http://localhost:8104")
os.environ.setdefault("PAYMENT_API_URL", "http://localhost:8105")
os.environ.setdefault("ORDER_API_URL", "http://localhost:8106")
# Four-eyes always in suites: the smallest value keeps every fixture at or
# above the threshold; threshold tests override explicitly.
os.environ.setdefault("APPROVAL_THRESHOLD_MINOR", "1")
os.environ.setdefault(
    "ATLAS_PG_DSN", "postgresql://postgres:atlas-pg-dev-only@localhost:5432/atlas"
)
os.environ.setdefault(
    "CONTROL_PG_DSN", "postgresql://postgres:atlas-pg-dev-only@localhost:5432/control"
)

import httpx

KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://localhost:8180")


async def user_token(username: str, password: str) -> str:
    """Password grant for smoke only; browsers use code+PKCE."""
    async with httpx.AsyncClient(timeout=15) as http:
        response = await http.post(
            f"{KEYCLOAK_URL}/realms/atlas/protocol/openid-connect/token",
            data={
                "client_id": "atlas-storefront",
                "username": username,
                "password": password,
                "grant_type": "password",
            },
        )
        response.raise_for_status()
        data = response.json()
        assert isinstance(data, dict) and isinstance(data["access_token"], str)
        return data["access_token"]


def unique(prefix: str) -> str:
    """Unique key per test: no ordering dependence, no teardown races."""
    import uuid

    return f"{prefix}-{uuid.uuid4().hex[:8]}"
