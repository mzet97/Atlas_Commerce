-- 003: order projection (M3). Read model only, never checkout truth.
CREATE TABLE IF NOT EXISTS orders_view (
    order_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL,
    total_minor INT NOT NULL,
    currency TEXT NOT NULL,
    status TEXT NOT NULL,
    payment_intent_id TEXT,
    failure_reason TEXT,
    projection_version INT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS orders_view_status_idx ON orders_view (status);
CREATE INDEX IF NOT EXISTS orders_view_customer_idx ON orders_view (customer_id);

CREATE TABLE IF NOT EXISTS order_lines (
    order_id TEXT NOT NULL REFERENCES orders_view (order_id),
    offer_id TEXT NOT NULL,
    sku_id TEXT NOT NULL,
    quantity INT NOT NULL,
    price_minor INT NOT NULL,
    PRIMARY KEY (order_id, offer_id)
);

CREATE TABLE IF NOT EXISTS processed_events (
    consumer_id TEXT NOT NULL,
    event_id TEXT NOT NULL,
    aggregate_id TEXT NOT NULL,
    aggregate_version INT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (consumer_id, event_id)
);
