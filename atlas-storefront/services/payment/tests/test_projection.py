"""Relay + projector tests: outbox drains once, PG projection is idempotent."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import asyncpg
import pytest_asyncio
from conftest import PG_TEST_DSN, unique

from atlas_payment import domain
from atlas_payment.domain import CorrelationId, IdempotencyKey, IntentId, PaymentIntent
from atlas_payment.projector import apply_event
from atlas_payment.relay import publish_unpublished

MIGRATION = os.path.join(os.path.dirname(__file__), "..", "migrations",
                         "002_payment_projection.sql")


@pytest_asyncio.fixture
async def pool():
    """Given: projection tables exist (idempotent migration)."""
    handle = await asyncpg.create_pool(PG_TEST_DSN, min_size=1, max_size=2)
    assert handle is not None
    sql = await asyncio.to_thread(Path(MIGRATION).read_text, encoding="utf-8")
    await handle.execute(sql)
    yield handle
    await handle.close()


class StubProducer:
    """Captures relay sends without a broker."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, bytes]] = []

    async def send_and_wait(self, topic: str, value: bytes, key: bytes) -> None:
        self.sent.append((topic, value))


async def _initiated(repo: object, key: str) -> PaymentIntent:
    from atlas_payment.mongo_repo import MongoPaymentRepository

    assert isinstance(repo, MongoPaymentRepository)
    return await repo.initiate(
        PaymentIntent.initiate(
            IntentId(unique("pi")),
            unique("order"),
            unique("cust"),
            1999,
            "BRL",
            "4242",
            IdempotencyKey(key),
            CorrelationId(unique("corr")),
        )
    )


class TestRelayDrain:
    async def test_outbox_marks_published(self, repo) -> None:
        """Given new intent / When relay passes / Then one send + drain."""
        await _initiated(repo, unique("idem"))
        producer = StubProducer()
        before = await publish_unpublished(repo.database, producer)  # type: ignore[arg-type]
        assert before >= 1  # shared test DB may hold earlier rows
        topic, _raw = producer.sent[-1]
        assert topic == "atlas.payment.PaymentInitiated.v1"
        assert await publish_unpublished(repo.database, producer) == 0  # type: ignore[arg-type]

    async def test_envelope_feeds_projector(self, repo, pool) -> None:
        """Given relay envelope / When applied twice / Then True,False + row."""
        await _initiated(repo, unique("idem"))
        producer = StubProducer()
        await publish_unpublished(repo.database, producer)  # type: ignore[arg-type]
        _, raw = producer.sent[-1]
        assert await apply_event(pool, raw) is True
        assert await apply_event(pool, raw) is False  # replay: no duplicate
        envelope = json.loads(raw.decode())
        row = await pool.fetchrow(
            "SELECT status, projection_version FROM payment_intents WHERE intent_id=$1",
            envelope["aggregate_id"],
        )
        assert (row["status"], row["projection_version"]) == ("INITIATED", 1)

    async def test_out_of_order_version_kept(self, pool) -> None:
        """Given v2 applied / When v1 arrives late / Then v2 stands."""
        intent_id = unique("pi")
        for version, status in ((2, "AUTHORIZED"), (1, "INITIATED")):
            event = domain.new_event(
                "PaymentAuthorized" if version == 2 else "PaymentInitiated",
                IntentId(intent_id),
                version,
                CorrelationId(unique("corr")),
                {"intent_id": intent_id, "order_id": unique("order"),
                 "customer_id": unique("cust"), "amount_minor": 1999,
                 "currency": "BRL", "status": status,
                 "provider_ref": "psp-oo", "decline_code": None},
            )
            raw = json.dumps(event.envelope()).encode()
            assert await apply_event(pool, raw) is True
        row = await pool.fetchrow(
            "SELECT status FROM payment_intents WHERE intent_id=$1", intent_id
        )
        assert row["status"] == "AUTHORIZED"
