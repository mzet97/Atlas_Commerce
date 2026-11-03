"""Shared fixtures: test DBs are the host-mapped stack (dev gate)."""

from __future__ import annotations

import os
import uuid

# directConnection: the RS member advertises as mongo:27017 (compose DNS),
# unresolvable from here; talk straight to the mapped localhost port.
os.environ.setdefault(
    "MONGO_URL",
    "mongodb://localhost:27017/offers_test?replicaSet=rs0&directConnection=true",
)
os.environ.setdefault("OFFERS_DB", "offers_test")
# Traces are proven on the live stack; tests stay signal-only.
os.environ.setdefault("OTEL_SDK_DISABLED", "true")

import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorClient

PG_TEST_DSN = os.getenv(
    "PG_TEST_DSN", "postgresql://postgres:atlas-pg-dev-only@localhost:5432/atlas"
)
KAFKA_TEST_BOOTSTRAP = os.getenv("KAFKA_TEST_BOOTSTRAP", "localhost:9092")


def unique(prefix: str) -> str:
    """Unique key per test: no ordering dependence, no teardown races."""
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


@pytest_asyncio.fixture
async def mongo_db():
    """Given: a fresh handle on the test database."""
    client = AsyncIOMotorClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=5000)
    yield client.offers_test
    client.close()
