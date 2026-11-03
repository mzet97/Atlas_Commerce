-- 004: notification outbox (M6). Dispatch transport (RabbitMQ) is
-- deferred; this table is the content contract: one QUEUED row per
-- customer-facing order event. Dispatcher marks SENT (append state).
CREATE TABLE IF NOT EXISTS notification_queue (
    order_id TEXT NOT NULL,
    event TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'QUEUED',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (order_id, event)
);
CREATE INDEX IF NOT EXISTS notification_queue_status_idx
    ON notification_queue (status);
