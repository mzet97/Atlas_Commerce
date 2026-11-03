-- 001: inventory availability projection + shared event inbox.
-- Availability is ALWAYS derived (on_hand - reserved - safety_stock) at
-- query time; no stored column may drift from the components (INV-001).
CREATE TABLE IF NOT EXISTS inventory_availability_view (
    warehouse_id TEXT NOT NULL,
    sku_id TEXT NOT NULL,
    on_hand INT NOT NULL DEFAULT 0,
    reserved INT NOT NULL DEFAULT 0,
    safety_stock INT NOT NULL DEFAULT 0,
    projection_version INT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (warehouse_id, sku_id)
);
CREATE INDEX IF NOT EXISTS inventory_sku_idx
    ON inventory_availability_view (sku_id);
