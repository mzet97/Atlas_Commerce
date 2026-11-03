-- 001: offer read model + shared event inbox (idempotent replay).
CREATE TABLE IF NOT EXISTS available_offer_view (
    offer_id TEXT PRIMARY KEY,
    sku_id TEXT NOT NULL DEFAULT '',
    seller_id TEXT NOT NULL DEFAULT '',
    market_id TEXT NOT NULL DEFAULT '',
    currency TEXT NOT NULL DEFAULT '',
    price_minor INT NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    projection_version INT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS offer_market_status_idx
    ON available_offer_view (market_id, status);
-- processed_events table is created by the catalog migration; keep the
-- shared inbox contract (consumer_id, event_id) PK in every projection DB.
