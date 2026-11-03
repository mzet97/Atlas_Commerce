-- 005: recommendation ranking inputs (M7). Curator sets weight + optional
-- expiry; expired entries stop surfacing without a rewrite (TTL by row).
ALTER TABLE ai_allowlist
    ADD COLUMN IF NOT EXISTS weight REAL NOT NULL DEFAULT 1.0,
    ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;
