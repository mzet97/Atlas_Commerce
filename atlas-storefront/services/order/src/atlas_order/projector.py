"""Projection worker: Kafka order events -> PostgreSQL read model.

Idempotent: (consumer_id, event_id) is the PK of processed_events, applied
in the SAME transaction as the projection rows. Replays never duplicate.
"""

from __future__ import annotations

import asyncio
import json
import os

import asyncpg
from aiokafka import AIOKafkaConsumer
from pydantic import BaseModel, ConfigDict

CONSUMER_ID = "order-projector-1"

TOPICS = (
    "atlas.order.OrderPlaced.v1",
    "atlas.order.OrderConfirmed.v1",
    "atlas.order.OrderShipped.v1",
    "atlas.order.OrderCancelled.v1",
    "atlas.order.OrderRejected.v1",
)


class EventEnvelope(BaseModel):
    """Boundary parse of the versioned envelope (contracts N/N-1)."""

    model_config = ConfigDict(frozen=True)

    event_id: str
    event_type: str
    aggregate_id: str
    aggregate_version: int
    correlation_id: str


async def apply_event(pool: asyncpg.Pool, raw: bytes) -> bool:
    """Apply one record. Returns True when applied, False when duplicate."""
    decoded = json.loads(raw.decode())
    envelope = EventEnvelope.model_validate(decoded)
    payload = decoded.get("payload") or {}
    async with pool.acquire() as conn, conn.transaction():
        try:
            await conn.execute(
                "INSERT INTO processed_events"
                "(consumer_id, event_id, aggregate_id, aggregate_version)"
                " VALUES ($1, $2, $3, $4)",
                CONSUMER_ID,
                envelope.event_id,
                envelope.aggregate_id,
                envelope.aggregate_version,
            )
        except asyncpg.UniqueViolationError:
            return False
        if envelope.event_type in (
            "OrderPlaced",
            "OrderConfirmed",
            "OrderShipped",
            "OrderCancelled",
            "OrderRejected",
        ):
            await conn.execute(
                "INSERT INTO orders_view"
                "(order_id, customer_id, total_minor, currency, status,"
                " payment_intent_id, failure_reason, projection_version)"
                " VALUES ($1, $2, $3, $4, $5, $6, $7, $8)"
                " ON CONFLICT (order_id) DO UPDATE SET"
                " status=EXCLUDED.status,"
                " payment_intent_id=EXCLUDED.payment_intent_id,"
                " failure_reason=EXCLUDED.failure_reason,"
                " projection_version=EXCLUDED.projection_version"
                " WHERE orders_view.projection_version < EXCLUDED.projection_version",
                envelope.aggregate_id,
                payload.get("customer_id", ""),
                payload.get("total_minor", 0),
                payload.get("currency", ""),
                payload.get("status", ""),
                payload.get("payment_intent_id"),
                payload.get("failure_reason"),
                envelope.aggregate_version,
            )
            if envelope.event_type in ("OrderConfirmed", "OrderShipped"):
                # Notification outbox (M6): downstream dispatch reads here;
                # RabbitMQ transport is deferred, content contract is live.
                await conn.execute(
                    "INSERT INTO notification_queue"
                    "(order_id, event, status, created_at)"
                    " VALUES ($1, $2, 'QUEUED', NOW()) ON CONFLICT DO NOTHING",
                    envelope.aggregate_id,
                    envelope.event_type,
                )
            lines = payload.get("lines") or []
            if envelope.event_type == "OrderPlaced" and isinstance(lines, list):
                for line in lines:
                    if not isinstance(line, dict):
                        continue
                    await conn.execute(
                        "INSERT INTO order_lines"
                        "(order_id, offer_id, sku_id, quantity, price_minor)"
                        " VALUES ($1, $2, $3, $4, $5) ON CONFLICT DO NOTHING",
                        envelope.aggregate_id,
                        str(line.get("offer_id", "")),
                        str(line.get("sku_id", "")),
                        int(line.get("quantity", 0)),
                        int(line.get("price_minor", 0)),
                    )
        return True


async def run_forever() -> None:
    """Worker boundary: poison records are skipped after logging, loop lives."""
    pool = await asyncpg.create_pool(os.environ["PG_DSN"], min_size=1, max_size=5)
    consumer = AIOKafkaConsumer(
        *TOPICS,
        bootstrap_servers=os.environ["KAFKA_BOOTSTRAP"],
        group_id="order-projector",
        enable_auto_commit=False,
    )
    await consumer.start()
    try:
        async for record in consumer:
            try:
                applied = await apply_event(pool, record.value)
            except Exception as exc:  # worker boundary: skip poison, keep projecting
                print(f"projector record failed (skipped): {type(exc).__name__}: {exc}")
                applied = True
            if applied:
                await consumer.commit()
    finally:
        await consumer.stop()
        await pool.close()


if __name__ == "__main__":
    asyncio.run(run_forever())
