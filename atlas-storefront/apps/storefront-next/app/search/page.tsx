import { formatPrice, searchProducts } from "@/lib/db";

export const dynamic = "force-dynamic";

export default async function Search({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>;
}) {
  const q = ((await searchParams).q ?? "").trim();
  const results = q === "" ? [] : await searchProducts(q);
  return (
    <main>
      <h1>Buscar no catálogo</h1>
      <form action="/search" method="get">
        <input name="q" defaultValue={q} placeholder="cafeteira…" maxLength={80} />
        <button type="submit">Buscar</button>
      </form>
      {q === "" ? (
        <p className="note">Digite um termo para buscar na projeção do catálogo.</p>
      ) : results.length === 0 ? (
        <p>Nenhum produto para “{q}”.</p>
      ) : (
        <ul>
          {results.map((p) => (
            <li key={p.product_id}>
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
