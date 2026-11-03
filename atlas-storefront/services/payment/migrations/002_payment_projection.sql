-- 002: payment projection (M3). Intent rows mirror the owner; the
-- `payment_intents` table is a read model, NOT payment truth. Webhook rows
-- prove delivery/dedup; `processed_events` keeps replays idempotent.
CREATE TABLE IF NOT EXISTS payment_intents (
    intent_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    amount_minor INT NOT NULL,
    currency TEXT NOT NULL,
    status TEXT NOT NULL,
    provider_ref TEXT,
    decline_code TEXT,
    projection_version INT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS payment_intents_order_idx ON payment_intents (order_id);
CREATE INDEX IF NOT EXISTS payment_intents_status_idx ON payment_intents (status);

CREATE TABLE IF NOT EXISTS payment_webhooks (
    provider_ref TEXT NOT NULL,
    event TEXT NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (provider_ref, event)
);

CREATE TABLE IF NOT EXISTS processed_events (
    consumer_id TEXT NOT NULL,
    event_id TEXT NOT NULL,
    aggregate_id TEXT NOT NULL,
    aggregate_version INT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (consumer_id, event_id)
);
