"""Notification dispatcher (M6): PG notification_queue -> RabbitMQ quorum.

ADR-0003 boundary: Kafka carries domain events; Rabbit carries point-of-
work tasks. The queue table is the content contract (order_id + event);
this worker is the transport. SENT is append state — a crash between
publish and the UPDATE at-least-once delivers again (consumers dedupe by
order_id+event, which is also the queue table's PK).
"""

from __future__ import annotations

import asyncio
import json
import os

import aio_pika
from aio_pika import DeliveryMode
from asyncpg import Pool

QUEUE = "atlas.notifications"
BATCH = 10


def _rabbit_url() -> str:
    return os.getenv(
        "RABBIT_URL", "amqp://atlas:atlas-rabbit-dev-only@localhost:5672/"
    )


async def dispatch_once(pool: Pool) -> int:
    """Claim a QUEUED batch, publish persistent, mark SENT. Returns count."""
    async with pool.acquire() as conn, conn.transaction():
        rows = await conn.fetch(
            "SELECT order_id, event FROM notification_queue"
            " WHERE status = 'QUEUED' ORDER BY created_at LIMIT $1"
            " FOR UPDATE SKIP LOCKED",
            BATCH,
        )
        if not rows:
            return 0
        connection = await aio_pika.connect_robust(_rabbit_url())
        try:
            channel = await connection.channel()
            queue = await channel.declare_queue(
                QUEUE, durable=True, arguments={"x-queue-type": "quorum"}
            )
            _ = queue  # declared durable; publishing rides the default exchange
            for row in rows:
                message = aio_pika.Message(
                    body=json.dumps(
                        {"order_id": row["order_id"], "event": row["event"]}
                    ).encode(),
                    delivery_mode=DeliveryMode.PERSISTENT,
                    headers={"event": row["event"]},
                )
                await channel.default_exchange.publish(message, routing_key=QUEUE)
            for row in rows:
                await conn.execute(
                    "UPDATE notification_queue SET status = 'SENT'"
                    " WHERE order_id = $1 AND event = $2 AND status = 'QUEUED'",
                    row["order_id"],
                    row["event"],
                )
        finally:
            await connection.close()
    return len(rows)


async def run_forever() -> None:
    """Worker boundary: a poisoned batch must never kill the dispatcher."""
    import asyncpg

    pool = await asyncpg.create_pool(os.environ["PG_DSN"], min_size=1, max_size=2)
    try:
        while True:
            try:
                sent = await dispatch_once(pool)
                await asyncio.sleep(5 if sent == 0 else 1)
            except Exception as exc:
                print(f"notifier batch failed (retried): {type(exc).__name__}: {exc}")
                await asyncio.sleep(5)
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(run_forever())
