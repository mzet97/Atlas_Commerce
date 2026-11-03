"""Shared fixtures: test DBs are the host-mapped stack (dev gate).

testcontainers is unavailable here (docker daemon lives on the host, only
reachable via distrobox-host-exec), so integration tests target the same
images over localhost ports. Same binaries, same assertions.
"""

from __future__ import annotations

import os
import uuid

# directConnection: the RS member advertises as mongo:27017 (compose DNS),
# unresolvable from here; talk straight to the mapped localhost port.
os.environ.setdefault(
    "MONGO_URL",
    "mongodb://localhost:27017/catalog_test?replicaSet=rs0&directConnection=true",
)
os.environ.setdefault("CATALOG_DB", "catalog_test")
# Traces are proven on the live stack; tests stay signal-only.
os.environ.setdefault("OTEL_SDK_DISABLED", "true")

import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorClient

PG_TEST_DSN = os.getenv(
    "PG_TEST_DSN", "postgresql://postgres:atlas-pg-dev-only@localhost:5432/atlas"
)
KAFKA_TEST_BOOTSTRAP = os.getenv("KAFKA_TEST_BOOTSTRAP", "localhost:9092")


def unique(prefix: str) -> str:
    """Unique key per test: isolates tests without teardown ordering."""
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


@pytest_asyncio.fixture
async def mongo_db():
    """Given: a fresh handle on the test database."""
    client = AsyncIOMotorClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=5000)
    yield client.catalog_test
    client.close()
