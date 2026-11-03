-- 002: storefront search (M5). PG trigram, no external engine (OPEN-05:
-- decided PG-only; an engine is re-evaluated only on measured L2 pressure).
-- `similarity` ranks typo-tolerant pt-BR titles; ILIKE keeps exact
-- substring hits. Read model only, never authority.
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX IF NOT EXISTS catalog_search_title_trgm_idx
    ON catalog_product_search USING gin (title gin_trgm_ops);
