-- 003: AI allowlist (M7). The recommender surfaces ONLY rows listed
-- here AND ACTIVE in the offer view. Curation is merchandising
-- (catalog_editor via Control); the table is a read-model gate, not PII.
CREATE TABLE IF NOT EXISTS ai_allowlist (
    offer_id TEXT PRIMARY KEY,
    reason TEXT NOT NULL DEFAULT '',
    added_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
