import { formatPrice, listRecommendations } from "@/lib/db";

export const dynamic = "force-dynamic";

export default async function Recommendations() {
  const items = await listRecommendations();
  return (
    <main>
      <h1>Recomendados (curadoria AI allowlist)</h1>
      <p className="note">
        Somente ofertas ativas e curadas aparecem aqui. A disponibilidade é
        indicativa: o checkout revalida no Inventory autoritativo (INV-CQRS-001).
      </p>
      {items.length === 0 ? (
        <p>Nenhuma recomendação curada no momento.</p>
      ) : (
        <ul>
          {items.map((p) => (
            <li key={p.offer_id ?? p.product_id}>
              <div>
                <strong>{p.title || "(sem título)"}</strong>
                <span className="st">{p.status}</span>
              </div>
              <div>
                {formatPrice(p.price_minor, p.currency)}
                {" · "}
                {p.total_available > 0 ? `${p.total_available} un.` : "indisponível"}
              </div>
            </li>
          ))}
        </ul>
      )}
      <p>
        <a href="/">← catálogo</a>
      </p>
    </main>
  );
}
