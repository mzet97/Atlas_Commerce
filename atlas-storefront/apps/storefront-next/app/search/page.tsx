import { searchProducts } from "@/lib/db";
import { formatMoney, getLocale, t } from "@/lib/i18n";

export const dynamic = "force-dynamic";

const PRICE_BUCKETS = ["<100", "100-500", "500-1000", ">=1000"] as const;

function facetHref(
  base: Record<string, string | undefined>,
  key: string,
  value: string | undefined,
): string {
  const params = new URLSearchParams();
  const merged = { ...base, [key]: value };
  for (const [k, v] of Object.entries(merged)) {
    if (v) params.set(k, v);
  }
  return `/search?${params.toString()}`;
}

export default async function Search({
  searchParams,
}: {
  searchParams: Promise<{
    q?: string;
    page?: string;
    price?: string;
    market?: string;
  }>;
}) {
  const params = await searchParams;
  const locale = await getLocale();
  const q = (params.q ?? "").trim();
  const page = Math.max(1, Number(params.page ?? "1") || 1);
  const results = q
    ? await searchProducts(q, locale, page, 10, params.price ?? "", params.market ?? "")
    : { results: [], total: 0, page: 1, pages: 0, facets: { markets: [], prices: [] } };
  return (
    <main>
      <h1>{t(locale, "search.title")}</h1>
      <form action="/search" method="get">
        <input name="q" defaultValue={q} placeholder="cafeteira…" maxLength={80} />
        <input type="hidden" name="page" value="1" />
        <button type="submit">{t(locale, "nav.search")}</button>
      </form>
      {q === "" ? (
        <p className="note">{t(locale, "search.hint")}</p>
      ) : (
        <>
          <aside className="facets">
            <div>
              <strong>{t(locale, "search.facets.price")}</strong>
              <ul>
                <li>
                  <a href={facetHref({ q, market: params.market }, "price", undefined)}>
                    todas
                  </a>
                </li>
                {PRICE_BUCKETS.map((bucket) => (
                  <li key={bucket}>
                    <a
                      href={facetHref({ q, market: params.market }, "price", bucket)}
                      className={params.price === bucket ? "active" : undefined}
                    >
                      {bucket}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <strong>{t(locale, "search.facets.market")}</strong>
              <ul>
                {results.facets.markets.map((facet) => (
                  <li key={facet.market_id ?? "?"}>
                    <a
                      href={facetHref(
                        { q, price: params.price },
                        "market",
                        facet.market_id ?? "",
                      )}
                    >
                      {facet.market_id} ({facet.count})
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          </aside>
          {results.results.length === 0 ? (
            <p>{t(locale, "search.none")}</p>
          ) : (
            <ul>
              {results.results.map((p) => (
                <li key={p.product_id}>
                  <div>
                    <strong>{p.title}</strong>
                    <span className="st">{p.status}</span>
                  </div>
                  <div>
                    {formatMoney(p.price_minor, p.currency, locale)}
                    {" · "}
                    {p.total_available > 0
                      ? t(locale, "unit.units", { n: p.total_available })
                      : t(locale, "unit.unavailable")}
                  </div>
                </li>
              ))}
            </ul>
          )}
          {results.pages > 1 && (
            <nav className="pagination">
              {results.page > 1 && (
                <a
                  href={facetHref(
                    { q, price: params.price, market: params.market },
                    "page",
                    String(results.page - 1),
                  )}
                >
                  {t(locale, "search.pagination.prev")}
                </a>
              )}
              <span>{t(locale, "search.page", { page: results.page })}</span>
              {results.page < results.pages && (
                <a
                  href={facetHref(
                    { q, price: params.price, market: params.market },
                    "page",
                    String(results.page + 1),
                  )}
                >
                  {t(locale, "search.pagination.next")}
                </a>
              )}
            </nav>
          )}
        </>
      )}
      <p>
        <a href="/">← catálogo</a>
      </p>
    </main>
  );
}
