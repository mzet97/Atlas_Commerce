"""Offers slice tests: idempotency + exactly-once projection (live stack)."""

from __future__ import annotations

import json
import os

import asyncpg
import pytest_asyncio
from aiokafka import AIOKafkaProducer
from conftest import KAFKA_TEST_BOOTSTRAP, PG_TEST_DSN, unique
from httpx import ASGITransport, AsyncClient
from motor.motor_asyncio import AsyncIOMotorClient

from atlas_offers.api import app as offers_app
from atlas_offers.mongo_repo import MongoOfferRepository
from atlas_offers.projector import apply_event
from atlas_offers.relay import publish_unpublished


@pytest_asyncio.fixture
async def stack():
    """Given: lifespan up (repo per test loop) + live producer and pool."""
    async with offers_app.router.lifespan_context(offers_app):
        client = AsyncIOMotorClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=5000)
        repo = MongoOfferRepository(client, db_name="offers_test")
        producer = AIOKafkaProducer(bootstrap_servers=KAFKA_TEST_BOOTSTRAP)
        await producer.start()
        pool = await asyncpg.create_pool(PG_TEST_DSN, min_size=1, max_size=2)
        assert pool is not None
        yield repo, producer, pool
        await producer.stop()
        await pool.close()
        client.close()


class TestExactlyOnceProjection:
    async def test_duplicate_delivery_projects_once(
        self, stack: tuple[MongoOfferRepository, AIOKafkaProducer, asyncpg.Pool]
    ) -> None:
        """Given relayed event / When applied twice / Then one row, one inbox."""
        repo, producer, pool = stack
        async with AsyncClient(
            transport=ASGITransport(app=offers_app), base_url="http://test"
        ) as http:
            body = {
                "sku_id": unique("sku"),
                "seller_id": "atlas",
                "market_id": "BR",
                "channel": "web",
                "currency": "BRL",
                "price_minor": 1999,
                "idempotency_key": unique("idem"),
                "correlation_id": unique("corr"),
            }
            response = await http.post("/offers", json=body)
            assert response.status_code == 201, response.text
        sent = await publish_unpublished(repo.database, producer)
        assert sent >= 1
        assert await publish_unpublished(repo.database, producer) == 0

        doc = await repo.database.outbox.find_one({"published": True}, sort=[("_id", -1)])
        assert doc is not None
        raw = json.dumps({k: v for k, v in doc.items() if k not in ("_id", "published")}).encode()
        assert await apply_event(pool, raw) is True
        assert await apply_event(pool, raw) is False
        row = await pool.fetchrow(
            "SELECT status, price_minor, projection_version FROM available_offer_view"
            " WHERE offer_id = $1",
            doc["aggregate_id"],
        )
        assert row is not None
        assert (row["status"], row["price_minor"]) == ("ACTIVE", 1999)
        inbox = await pool.fetchval(
            "SELECT COUNT(*) FROM processed_events WHERE event_id = $1",
            doc["event_id"],
        )
        assert inbox == 1
