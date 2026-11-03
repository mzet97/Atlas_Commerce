"""Projection worker: Kafka payment events -> PostgreSQL read model.

Idempotent: (consumer_id, event_id) is the PK of processed_events, applied
in the SAME transaction as the projection row. Replays never duplicate.
"""

from __future__ import annotations

import asyncio
import json
import os

import asyncpg
from aiokafka import AIOKafkaConsumer
from pydantic import BaseModel, ConfigDict

CONSUMER_ID = "payment-projector-1"

TOPICS = (
    "atlas.payment.PaymentInitiated.v1",
    "atlas.payment.PaymentAuthorized.v1",
    "atlas.payment.PaymentDeclined.v1",
    "atlas.payment.PaymentUnknown.v1",
    "atlas.payment.PaymentWebhookReceived.v1",
    "atlas.payment.PaymentReconciled.v1",
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
            "PaymentInitiated",
            "PaymentAuthorized",
            "PaymentDeclined",
            "PaymentUnknown",
            "PaymentReconciled",
        ):
            await conn.execute(
                "INSERT INTO payment_intents"
                "(intent_id, order_id, customer_id, amount_minor, currency,"
                " status, provider_ref, decline_code, projection_version)"
                " VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)"
                " ON CONFLICT (intent_id) DO UPDATE SET"
                " status=EXCLUDED.status, provider_ref=EXCLUDED.provider_ref,"
                " decline_code=EXCLUDED.decline_code,"
                " projection_version=EXCLUDED.projection_version"
                " WHERE payment_intents.projection_version"
                " < EXCLUDED.projection_version",
                envelope.aggregate_id,
                payload.get("order_id", ""),
                payload.get("customer_id", ""),
                payload.get("amount_minor", 0),
                payload.get("currency", ""),
                payload.get("status", ""),
                payload.get("provider_ref"),
                payload.get("decline_code"),
                envelope.aggregate_version,
            )
        elif envelope.event_type == "PaymentWebhookReceived":
            await conn.execute(
                "INSERT INTO payment_webhooks"
                "(provider_ref, event, received_at)"
                " VALUES ($1, $2, NOW()) ON CONFLICT DO NOTHING",
                payload.get("provider_ref", ""),
                payload.get("event", ""),
            )
        return True


async def run_forever() -> None:
    """Worker boundary: poison records are skipped after logging, loop lives."""
    pool = await asyncpg.create_pool(os.environ["PG_DSN"], min_size=1, max_size=5)
    consumer = AIOKafkaConsumer(
        *TOPICS,
        bootstrap_servers=os.environ["KAFKA_BOOTSTRAP"],
        group_id="payment-projector",
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
