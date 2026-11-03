-- 001: catalog projection + event inbox (idempotent replay).
-- `projection_version` guards out-of-order delivery: older versions never
-- overwrite newer rows. `availability_hint` is intentionally absent here:
-- no read-model column may be mistaken for stock truth (INV-CQRS-001).
CREATE TABLE IF NOT EXISTS catalog_product_search (
    product_id TEXT PRIMARY KEY,
    title TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,
    projection_version INT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS catalog_search_status_idx
    ON catalog_product_search (status);

CREATE TABLE IF NOT EXISTS processed_events (
    consumer_id TEXT NOT NULL,
    event_id TEXT NOT NULL,
    aggregate_id TEXT NOT NULL,
    aggregate_version INT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (consumer_id, event_id)
);
