import { Pool } from "pg";
import { DEFAULT_LOCALE, type Locale } from "./i18n";

const pool = new Pool({ connectionString: process.env.DATABASE_URL });

export type ListedProduct = {
  product_id: string;
  title: string;
  status: string;
  projection_version: number;
  updated_at: string;
};

/** Title for the locale with pt-BR fallback, straight from the projection. */
const TITLE_EXPR = "COALESCE(p.titles->>$1, p.title)";

export async function listProducts(locale: Locale = DEFAULT_LOCALE): Promise<ListedProduct[]> {
  const { rows } = await pool.query(
    `SELECT product_id, ${TITLE_EXPR} AS title, status, projection_version, updated_at
     FROM catalog_product_search p ORDER BY p.updated_at DESC LIMIT 100`,
    [locale],
  );
  return rows;
}

export type OfferLine = ListedProduct & {
  offer_id: string | null;
  price_minor: number | null;
  currency: string | null;
  market_id: string | null;
  total_available: number;
};

const JOINS = `
  LEFT JOIN LATERAL (
    SELECT * FROM available_offer_view o
    WHERE o.sku_id = p.product_id AND o.status = 'ACTIVE'
    ORDER BY o.projection_version DESC LIMIT 1
  ) o ON true
  LEFT JOIN LATERAL (
    SELECT SUM(on_hand - reserved - safety_stock)::int AS total_available
    FROM inventory_availability_view WHERE sku_id = p.product_id
  ) i ON true`;

export async function listProductsWithOffers(
  locale: Locale = DEFAULT_LOCALE,
): Promise<OfferLine[]> {
  const { rows } = await pool.query(
    `SELECT p.product_id, ${TITLE_EXPR} AS title, p.status, p.projection_version,
            p.updated_at, o.offer_id, o.price_minor, o.currency, o.market_id,
            COALESCE(i.total_available, 0) AS total_available
     FROM catalog_product_search p
     ${JOINS}
     ORDER BY p.updated_at DESC LIMIT 100`,
    [locale],
  );
  return rows;
}

export type SearchFacets = {
  markets: { market_id: string; count: number }[];
  prices: { bucket: string; count: number }[];
};

export type SearchPage = {
  results: OfferLine[];
  total: number;
  page: number;
  pages: number;
  facets: SearchFacets;
};

const PRICE_BUCKETS = `
  CASE WHEN o.price_minor < 10000 THEN '<100'
       WHEN o.price_minor < 50000 THEN '100-500'
       WHEN o.price_minor < 100000 THEN '500-1000'
       ELSE '>=1000' END`;

export async function searchProducts(
  query: string,
  locale: Locale = DEFAULT_LOCALE,
  page = 1,
  pageSize = 10,
  priceBucket = "",
  market = "",
): Promise<SearchPage> {
  const q = query.trim().slice(0, 80);
  if (q === "") {
    return { results: [], total: 0, page: 1, pages: 0, facets: { markets: [], prices: [] } };
  }
  const safePage = Math.max(1, page);
  const safeSize = Math.min(Math.max(1, pageSize), 50);
  const offset = (safePage - 1) * safeSize;
  const conds = [
    "(p.title ILIKE '%' || $1 || '%' OR similarity(p.title, $1) > 0.3"
    + " OR p.titles->>$2 ILIKE '%' || $1 || '%')",
  ];
  const params: unknown[] = [q, locale];
  if (priceBucket) {
    params.push(priceBucket);
    conds.push(`${PRICE_BUCKETS} = $${params.length}`);
  }
  if (market) {
    params.push(market);
    conds.push(`o.market_id = $${params.length}`);
  }
  const filters = "WHERE " + conds.join(" AND ");
  const { rows: totalRows } = await pool.query(
    `SELECT count(*)::int AS total FROM catalog_product_search p
     LEFT JOIN LATERAL (
       SELECT * FROM available_offer_view o
       WHERE o.sku_id = p.product_id AND o.status = 'ACTIVE'
       ORDER BY o.projection_version DESC LIMIT 1
     ) o ON true
     ${filters}`,
    params,
  );
  const total = totalRows[0]?.total ?? 0;
  const { rows } = await pool.query(
    `SELECT p.product_id, ${TITLE_EXPR} AS title, p.status, p.projection_version,
            p.updated_at, o.offer_id, o.price_minor, o.currency, o.market_id,
            COALESCE(i.total_available, 0) AS total_available,
            similarity(p.title, $1) AS rank
     FROM catalog_product_search p
     ${JOINS}
     ${filters}
     ORDER BY rank DESC, p.updated_at DESC
     LIMIT ${safeSize} OFFSET ${offset}`,
    params,
  );
  const { rows: marketRows } = await pool.query(
    `SELECT o.market_id, count(*)::int AS count FROM catalog_product_search p
     LEFT JOIN LATERAL (
       SELECT * FROM available_offer_view o
       WHERE o.sku_id = p.product_id AND o.status = 'ACTIVE'
       ORDER BY o.projection_version DESC LIMIT 1
     ) o ON true
     WHERE p.title ILIKE '%' || $1 || '%' OR similarity(p.title, $1) > 0.3
     GROUP BY o.market_id ORDER BY count DESC`,
    [q],
  );
  const { rows: priceRows } = await pool.query(
    `SELECT ${PRICE_BUCKETS} AS bucket, count(*)::int AS count
     FROM catalog_product_search p
     LEFT JOIN LATERAL (
       SELECT * FROM available_offer_view o
       WHERE o.sku_id = p.product_id AND o.status = 'ACTIVE'
       ORDER BY o.projection_version DESC LIMIT 1
     ) o ON true
     WHERE p.title ILIKE '%' || $1 || '%' OR similarity(p.title, $1) > 0.3
     GROUP BY bucket ORDER BY count DESC`,
    [q],
  );
  return {
    results: rows,
    total,
    page: safePage,
    pages: Math.max(1, Math.ceil(total / safeSize)),
    facets: { markets: marketRows, prices: priceRows },
  };
}

export async function listRecommendations(
  locale: Locale = DEFAULT_LOCALE,
): Promise<OfferLine[]> {
  // AI surfacing contract (M7): allowlisted AND ACTIVE only. Anything not
  // curated here never renders on /recommendations, whatever its status.
  const { rows } = await pool.query(
    `SELECT p.product_id, ${TITLE_EXPR} AS title, p.status, p.projection_version,
            p.updated_at, o.offer_id, o.price_minor, o.currency, o.market_id,
            COALESCE(i.total_available, 0) AS total_available
     FROM ai_allowlist a
     JOIN available_offer_view o ON o.offer_id = a.offer_id AND o.status = 'ACTIVE'
     JOIN catalog_product_search p ON p.product_id = o.sku_id
     LEFT JOIN LATERAL (
       SELECT SUM(on_hand - reserved - safety_stock)::int AS total_available
       FROM inventory_availability_view WHERE sku_id = p.product_id
     ) i ON true
     ORDER BY total_available DESC, a.added_at DESC LIMIT 10`,
    [locale],
  );
  return rows;
}

export function formatPrice(priceMinor: number | null, currency: string | null): string {
  if (priceMinor === null || currency === null) return "—";
  return `${(priceMinor / 100).toFixed(2)} ${currency}`;
}
