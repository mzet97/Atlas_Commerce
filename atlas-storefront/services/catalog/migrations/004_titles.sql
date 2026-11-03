-- 004: localized titles on the catalog read model (M5). `title` stays the
-- pt-BR fallback; `titles` carries every locale the owner published.
ALTER TABLE catalog_product_search
    ADD COLUMN IF NOT EXISTS titles JSONB NOT NULL DEFAULT '{}'::jsonb;
