import { Pool } from "pg";

const pool = new Pool({ connectionString: process.env.DATABASE_URL });

export type ListedProduct = {
  product_id: string;
  title: string;
  status: string;
  projection_version: number;
  updated_at: string;
};

export async function listProducts(): Promise<ListedProduct[]> {
  const { rows } = await pool.query(
    `SELECT product_id, title, status, projection_version, updated_at
     FROM catalog_product_search ORDER BY updated_at DESC LIMIT 100`
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

export async function listProductsWithOffers(): Promise<OfferLine[]> {
  const { rows } = await pool.query(
    `SELECT p.product_id, p.title, p.status, p.projection_version, p.updated_at,
            o.offer_id, o.price_minor, o.currency, o.market_id,
            COALESCE(i.total_available, 0) AS total_available
     FROM catalog_product_search p
     LEFT JOIN LATERAL (
       SELECT * FROM available_offer_view o
       WHERE o.sku_id = p.product_id AND o.status = 'ACTIVE'
       ORDER BY o.projection_version DESC LIMIT 1
     ) o ON true
     LEFT JOIN LATERAL (
       SELECT SUM(on_hand - reserved - safety_stock)::int AS total_available
       FROM inventory_availability_view WHERE sku_id = p.product_id
     ) i ON true
     ORDER BY p.updated_at DESC LIMIT 100`
  );
  return rows;
}

export async function searchProducts(query: string): Promise<OfferLine[]> {
  const q = query.trim().slice(0, 80);
  if (q === "") return [];
  const { rows } = await pool.query(
    `SELECT p.product_id, p.title, p.status, p.projection_version, p.updated_at,
            o.offer_id, o.price_minor, o.currency, o.market_id,
            COALESCE(i.total_available, 0) AS total_available,
            similarity(p.title, $1) AS rank
     FROM catalog_product_search p
     LEFT JOIN LATERAL (
       SELECT * FROM available_offer_view o
       WHERE o.sku_id = p.product_id AND o.status = 'ACTIVE'
       ORDER BY o.projection_version DESC LIMIT 1
     ) o ON true
     LEFT JOIN LATERAL (
       SELECT SUM(on_hand - reserved - safety_stock)::int AS total_available
       FROM inventory_availability_view WHERE sku_id = p.product_id
     ) i ON true
     WHERE p.title ILIKE '%' || $1 || '%' OR similarity(p.title, $1) > 0.3
     ORDER BY rank DESC, p.updated_at DESC LIMIT 50`,
    [q]
  );
  return rows;
}

export async function listRecommendations(): Promise<OfferLine[]> {
  // AI surfacing contract (M7): allowlisted AND ACTIVE only. Anything not
  // curated here never renders on /recommendations, whatever its status.
  const { rows } = await pool.query(
    `SELECT p.product_id, p.title, p.status, p.projection_version, p.updated_at,
            o.offer_id, o.price_minor, o.currency, o.market_id,
            COALESCE(i.total_available, 0) AS total_available
     FROM ai_allowlist a
     JOIN available_offer_view o ON o.offer_id = a.offer_id AND o.status = 'ACTIVE'
     JOIN catalog_product_search p ON p.product_id = o.sku_id
     LEFT JOIN LATERAL (
       SELECT SUM(on_hand - reserved - safety_stock)::int AS total_available
       FROM inventory_availability_view WHERE sku_id = p.product_id
     ) i ON true
     ORDER BY total_available DESC, a.added_at DESC LIMIT 10`
  );
  return rows;
}

export function formatPrice(priceMinor: number | null, currency: string | null): string {
  if (priceMinor === null || currency === null) return "—";
  return `${(priceMinor / 100).toFixed(2)} ${currency}`;
}
