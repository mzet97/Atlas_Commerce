-- 006: marketplace 3P (M10). Sellers are tenants owned by Control; the
-- settlement ledger is an auditable REPORT (owners keep canonical state).
CREATE TABLE IF NOT EXISTS sellers (
    seller_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS settlements (
    order_id TEXT NOT NULL,
    seller_id TEXT NOT NULL,
    gross_minor INT NOT NULL,
    commission_minor INT NOT NULL,
    net_minor INT NOT NULL,
    computed_by TEXT NOT NULL,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (order_id, seller_id)
);
