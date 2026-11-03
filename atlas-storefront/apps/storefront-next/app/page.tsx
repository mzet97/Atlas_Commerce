import { formatPrice, listProductsWithOffers } from "@/lib/db";

export const dynamic = "force-dynamic";

export default async function Home({
  searchParams,
}: {
  searchParams: Promise<{ v?: string }>;
}) {
  const expected = Number((await searchParams).v ?? NaN);
  const products = await listProductsWithOffers();
  return (
    <main>
      <h1>Atlas Storefront — catálogo (fatia M2)</h1>
      <p className="note">
        Leitura das projeções PostgreSQL, derivadas de eventos de domínio. A
        disponibilidade aqui é indicativa: o checkout revalida no serviço
        Inventory autoritativo (INV-CQRS-001).
      </p>
      {products.length === 0 ? (
        <p>Nenhum produto projetado ainda.</p>
      ) : (
        <ul>
          {products.map((p) => {
            const publishing =
              Number.isFinite(expected) && p.projection_version < expected;
            const available = p.status === "PUBLISHED" ? p.total_available : 0;
            return (
              <li key={p.product_id}>
                <div>
                  <strong>{p.title || "(sem título)"}</strong>
                  <span className="st">{p.status}</span>
                  {publishing && <span className="st">sincronizando…</span>}
                </div>
                <div>
                  {formatPrice(p.price_minor, p.currency)}
                  {" · "}
                  {available > 0 ? `${available} un.` : "indisponível"}
                </div>
                <div className="pid">
                  {p.product_id} · v{p.projection_version}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </main>
  );
}
